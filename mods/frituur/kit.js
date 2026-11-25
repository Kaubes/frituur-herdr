// Shared bits: palette, font, sprites and small helpers.

import { image } from "gpui-kit";
import { shared, setShared } from "herdr";
import { SPRITES } from "./sprites-data.js";

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

/** A sprite with its anchor on (x, y), native pixels. `s` = { k: art scale, u: px per native pixel }. */
export function sprite(s, name, x, y) {
  const d = SPRITES[name];
  if (!d) return image(`${ART}/${s.k}x/s/vonk.png`).absolute().w(0).h(0);
  return image(`${ART}/${s.k}x/s/${name}.png`).absolute().left((x - d[2]) * s.u).top((y - d[3]) * s.u).w(d[0] * s.u).h(d[1] * s.u);
}

/** Two frames in turn: both always drawn, opposite opacity loops (a swap never loads an image). */
export function frames2(s, a, b, x, y, period) {
  return [
    sprite(s, a, x, y).loop("opacity", { from: 7, to: -6, period, easing: "linear" }),
    sprite(s, b, x, y).loop("opacity", { from: -6, to: 7, period, easing: "linear" }),
  ];
}

export function findNode(n, id) {
  if (n?.id === id) return n;
  for (const c of n?.children ?? []) {
    const f = findNode(c, id);
    if (f) return f;
  }
  return null;
}
