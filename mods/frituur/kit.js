// Shared bits: palette, font, sprites and small helpers.

import { div, image } from "gpui-kit";
import { shared, setShared } from "herdr";
import { IDLE, SPRITES } from "./sprites-data.js";

export const ART = "mods/frituur/art";
export const FONT = "Jersey 15"; // fonts/, OFL
export const ANIM = "frituur.anim"; // shared: false = still images

export const C = {
  donker: "#1c0f0a", muur: "#5a3018", hout: "#3a1f12", houtLicht: "#5a3018", rand: "#170a06", staal: "#a8a39a", staalDonker: "#5d5953",
  papier: "#fbf1d8", papierOud: "#efdfb8", inkt: "#3a1c12", inktZacht: "#8a6650", rood: "#c2281c", geel: "#ffd23f",
  groen: "#2f7d32", led: "#ff5a30", ledUit: "#1a1010", creme: "#fff3d6", koud: "#7c8894",
};

/** The color of a fase: on the bon's edge and word. */
export const KLEUR = {
  kiest: "#9a8a78", denkt: "#b06a1c", diepvries: "#3b7ea1", bakt: "#b8860b", schudt: "#b8860b", test: "#6a5aa8", olie: "#6b6b2a",
  wacht: "#c2281c", klaar: "#2f7d32", koud: "#6f7c88", eet: "#8a7a60", fout: "#c2281c",
};

export const animOn = () => shared(ANIM) !== false;
export const toggleAnim = () => setShared(ANIM, !animOn());

export function hash(s) {
  let h = 2166136261;
  for (const ch of String(s)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  h ^= h >>> 15; h = Math.imul(h, 0x846ca68b); h ^= h >>> 16;
  return h >>> 0;
}

export function clip(s, n) {
  s = String(s ?? "");
  return s.length > n ? s.slice(0, Math.max(1, n - 1)).trimEnd() + "…" : s;
}

/** A sprite with its anchor on (x, y), native pixels. `s` = { k: art scale, u: px per native pixel, l: the light
 *  (ochtend, middag, avond, nacht, grijs; the art is baked once for each) }. */
export function sprite(s, name, x, y) {
  const d = SPRITES[name], l = s.l ?? "avond";
  if (!d) return image(`${ART}/${s.k}x/${l}/s/vonk.png`).absolute().w(0).h(0);
  return image(`${ART}/${s.k}x/${l}/s/${name}.png`).absolute().left((x - d[2]) * s.u).top((y - d[3]) * s.u).w(d[0] * s.u).h(d[1] * s.u);
}

/** Two frames in turn: both always drawn, opposite opacity loops (a swap never loads an image). */
export function frames2(s, a, b, x, y, period) {
  return [
    sprite(s, a, x, y).loop("opacity", { from: 7, to: -6, period, easing: "linear" }),
    sprite(s, b, x, y).loop("opacity", { from: -6, to: 7, period, easing: "linear" }),
  ];
}

/** One name: that sprite. Two: they take turns, a full round every `period` ms. */
export function beurt(s, namen, x, y, period) {
  return namen.length > 1 ? frames2(s, namen[0], namen[1], x, y, period) : [sprite(s, namen[0], x, y)];
}

// How often (ms, plus a share of the second number that differs per person) and how long each idle thing is done.
const RITME = { oog: [3600, 2600, 150], kijk: [15000, 12000, 1700], hap: [3800, 2400, 800], kwispel: [6500, 3000, 1300], zak: [11000, 6000, 2200], veeg0: [21000, 9000, 3000], schrijf: [17000, 8000, 2600] };
const STEIL = 240; // how sharply one picture gives way to the other

/** A standing sprite that lives: now and then another sprite takes its place for a moment (a blink, a look at the
 *  menu, a bite), each on a rhythm of its own. It is all opacity loops, so no timer runs and nothing is redrawn. */
export function leeft(s, naam, x, y, seed) {
  let el = [sprite(s, naam, x, y)];
  for (const g of IDLE[naam] ?? []) {
    const [om, spreiding, duur] = RITME[g[0].split("-").at(-1)] ?? RITME.kijk;
    const T = om + (hash(`${seed}-${g[0]}`) % spreiding), f = duur / T, laag = 0.5 - STEIL * (1 - f), hoog = 0.5 + STEIL * f;
    el = [
      div().absolute().left(0).top(0).loop("opacity", { from: 1 - laag, to: 1 - hoog, period: T, easing: "linear" }).children(el),
      div().absolute().left(0).top(0).loop("opacity", { from: laag, to: hoog, period: T, easing: "linear" }).children(beurt(s, g, x, y, 760)),
    ];
  }
  return el;
}

export function findNode(n, id) {
  if (n?.id === id) return n;
  for (const c of n?.children ?? []) {
    const f = findNode(c, id);
    if (f) return f;
  }
  return null;
}
