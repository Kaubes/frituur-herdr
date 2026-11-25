// What time of day, season and weather it is in the shop. Each follows the clock and the calendar, or is
// set by hand: with the buttons under the order rail (kept in shared state), with a key or command
// (frituur.tijd, frituur.seizoen, frituur.weer), or fixed for a layout in the props of the zaak block
// ("tijd": "nacht", "seizoen": "winter", "weer": "sneeuw").
//
// The weather is made up from the date, so it changes a few times a day and needs no network. With
// "plaats": [latitude, longitude] in the props it is the real weather there, asked from open-meteo.com.

import { setShared, shared } from "herdr";
import { hash } from "./kit.js";

export const KEUZE = {
  tijd: ["ochtend", "middag", "avond", "nacht"],
  seizoen: ["lente", "zomer", "herfst", "winter"],
  weer: ["helder", "bewolkt", "regen", "sneeuw"],
};
const KEY = { tijd: "frituur.tijd", seizoen: "frituur.seizoen", weer: "frituur.weer" };

// Sunrise and sunset in Belgium per month, on the clock (summer time included).
const ZON = [[8.7, 17.0], [8.0, 17.9], [6.9, 18.7], [6.9, 20.5], [5.9, 21.3], [5.5, 21.9], [5.7, 21.8], [6.4, 21.0], [7.2, 19.9], [8.0, 18.8], [7.8, 17.0], [8.6, 16.6]];
// Out of 100, per season: below the first number snow, below the second rain, below the third clouds.
const KANS = { lente: [0, 26, 56], zomer: [0, 18, 42], herfst: [0, 36, 68], winter: [8, 40, 72] };

function tijdVan(d) {
  const u = d.getHours() + d.getMinutes() / 60, [op, onder] = ZON[d.getMonth()];
  if (u < op - 0.5 || u >= onder + 0.4) return "nacht";
  if (u < Math.min(op + 3, 11.5)) return "ochtend";
  return u >= onder - 2.5 ? "avond" : "middag";
}

const seizoenVan = (d) => KEUZE.seizoen[Math.floor(((d.getMonth() + 10) % 12) / 3)]; // March starts spring

/** Made-up weather: the same for three hours, and for everybody on the same day. */
function weerVan(d, seizoen) {
  const r = hash(`${d.getFullYear()}-${d.getMonth()}-${d.getDate()}-${Math.floor(d.getHours() / 3)}`) % 100, [s, n, b] = KANS[seizoen];
  return r < s ? "sneeuw" : r < n ? "regen" : r < b ? "bewolkt" : "helder";
}

let echt = null; // the real weather, when the layout gives a place: { weer, t }

/** Asks the real weather for [latitude, longitude]; true when it changed. At most twice an hour. */
export async function haalWeer(plaats) {
  if (!Array.isArray(plaats) || plaats.length !== 2 || !plaats.every((v) => Number.isFinite(Number(v)))) return false;
  if (echt && Date.now() - echt.t < 29 * 60000) return false;
  try {
    const r = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${Number(plaats[0])}&longitude=${Number(plaats[1])}&current=weather_code`);
    const c = Number((await r.json())?.current?.weather_code);
    if (!Number.isFinite(c)) return false;
    // WMO codes: 0-1 clear, 2-48 clouds and fog, 71-77 and 85-86 snow, the rest of 51-99 rain
    const weer = c <= 1 ? "helder" : c <= 48 ? "bewolkt" : (c >= 71 && c <= 77) || c === 85 || c === 86 ? "sneeuw" : "regen";
    const was = echt?.weer;
    echt = { weer, t: Date.now() };
    return was !== weer;
  } catch {
    return false; // no network: the made-up weather stays
  }
}

/** What is set by hand for "tijd", "seizoen" or "weer": a value, or "auto". Read in render: it follows the buttons. */
export function gezet(naam, pr) {
  const s = shared(KEY[naam]);
  if (KEUZE[naam].includes(pr?.[naam])) return pr[naam];
  return KEUZE[naam].includes(s) ? s : "auto";
}

/** The next choice for a button: auto, then each value in turn. */
export function volgende(naam) {
  const list = ["auto", ...KEUZE[naam]], nu = shared(KEY[naam]);
  setShared(KEY[naam], list[(list.indexOf(KEUZE[naam].includes(nu) ? nu : "auto") + 1) % list.length]);
}

/** Now: { tijd, seizoen, weer, licht }. `licht` is the baked light to draw with: clouds, rain and snow turn the
 *  daylight grey, the night stays the night. */
export function moment(pr, d = new Date()) {
  const kies = (naam, auto) => { const g = gezet(naam, pr); return g === "auto" ? auto() : g; };
  const seizoen = kies("seizoen", () => seizoenVan(d));
  const tijd = kies("tijd", () => tijdVan(d));
  const weer = kies("weer", () => (pr?.plaats && echt ? echt.weer : weerVan(d, seizoen)));
  return { tijd, seizoen, weer, licht: tijd !== "nacht" && weer !== "helder" ? "grijs" : tijd };
}
