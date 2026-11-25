// The shop. A stage of 640x400 native pixels hung from the top of the block and clipped by it, scaled so
// the whole shop shows: pulling the terminal up covers the floor first, then the customers, then the
// counter, without changing the scale. Art is drawn from the next whole scale up (crisp enough between).
// Draw order: room, baskets, workers, counter, what stands on it, customers, furniture, talk.

import { div, image } from "gpui-kit";
import { h_flex } from "gpui-base";
import { layout, nextCommand, run, settings, shared } from "herdr";
import { ANCHORS as A } from "./anchors-data.js";
import { DECOR, OUTFITS, WEER } from "./sprites-data.js";
import { ART, C, FONT, KLEUR, animOn, beurt, clip, findNode, frames2, hash, leeft, sprite, toggleAnim } from "./kit.js";
import { Loper } from "./loper.js";
import { HOOGTE } from "./paal.js";
import { Staat, opRang } from "./staat.js";
import { T, zeg } from "./tekst.js";
import { KEUZE, haalWeer, moment, volgende } from "./weer.js";

const [W, H] = A.stage; // what is drawn: the 16:9 room and more floor below it
const [CORE_X0, CORE_X1, CORE_H] = A.core; // what must always show
const BALK = 38; // the tab bar's height in layouts/Frituur.json
const SLOTS = A.customer_slots, QUEUE = A.customer_queue;
const LANE_Y = A.customer_lane.feet[1]; // people walk along here, behind the stools
const DOOR = A.customer_entry.feet, LANE = A.customer_lane.feet;
const LADE = 420; // the drawer's working height
const ROEPT = 8000; // "Nummer 12!" is called this long
const BLIJFT = 4000; // a worker stays with a task at least this long
const COOKING = new Set(["denkt", "diepvries", "bakt", "schudt", "test", "olie", "wacht"]);
// A full round of two pictures that take turns, ms: the season's things and the weather.
const TEMPO = { regenL0: 260, regenR0: 260, sneeuwL0: 1500, sneeuwR0: 1500, lichtjes0: 1700, kerstboom0: 1900, ventilator0: 240 };

export default class Zaak {
  init(pr, cx) {
    this.staat = new Staat(pr.demo);
    this.staat.start(cx);
    this.pr = pr;
    this.nu = "";
    // The time of day, season and weather change a few times a day: once a minute is often enough to look.
    cx.timer.every(60000, (cx) => {
      const m = moment(this.pr);
      if (`${m.licht} ${m.seizoen} ${m.weer}` !== this.nu) cx.notify();
      if (this.pr.plaats) cx.spawn(async (cx) => { if (await haalWeer(this.pr.plaats)) cx.notify(); });
    });
    if (pr.plaats) cx.spawn(async (cx) => { if (await haalWeer(pr.plaats)) cx.notify(); });
    this.size = { width: 1690, height: 960 };
    this.klanten = new Map(); // address -> { loper, plek, s, weg }
    this.mand = new Map(); // address -> basket 0..3
    this.werkers = [0, 1].map((i) => ({ i, loper: new Loper(...A.worker_rest[i], 110), taak: null, since: 0 }));
    this.klok = null;
    cx.spawn(async (cx) => {
      for (;;) {
        const c = await nextCommand();
        if (c === "lade") this.lade();
        if (c === "animaties") toggleAnim();
        if (c in KEUZE) volgende(c); // frituur.tijd, frituur.seizoen, frituur.weer: the next choice
        cx.notify();
      }
    });
  }

  /** The drawer: down, working height, nearly everything. Hidden rather than squeezed: a terminal
   *  one row high would make its program redraw everything. */
  lade() {
    const main = findNode(layout(), "main");
    if (!main) return;
    const zoom = Number(settings()?.zoom ?? 1) || 1;
    const big = Math.max(LADE, Math.round(this.hoogte(zoom) / zoom) - 90);
    if (main.hidden) { run("layout.resize", { id: "main", px: LADE }); run("layout.show", { id: "main" }); }
    else if ((main.size?.px ?? 0) < big - 40) run("layout.resize", { id: "main", px: big });
    else run("layout.hide", { id: "main" });
  }

  /** The shop's height with the drawer closed, window px. */
  hoogte(zoom) {
    const vol = Number(shared(HOOGTE)) || 0;
    return Math.max(this.size.height, vol - BALK * zoom);
  }

  // ---------------------------------------------------------------- who stands where

  plan(list, now, still) {
    const here = new Set(list.map((s) => s.addr));
    const bezet = new Set([...this.klanten.values()].filter((k) => !k.weg && here.has(k.s.addr)).map((k) => k.plek));
    for (const s of list) {
      let k = this.klanten.get(s.addr);
      if (k?.weg) { this.klanten.delete(s.addr); k = null; }
      if (!k) {
        // people already here when the shop opens don't all walk in at once
        const aan = new Set([...this.klanten.values()].map((x) => x.kleed));
        let kleed = hash(s.addr) % OUTFITS;
        for (let n = 0; n < OUTFITS && aan.has(kleed); n++) kleed = (kleed + 1) % OUTFITS;
        k = { s, kleed, plek: null, loper: new Loper(...DOOR, 80), nieuw: this.open };
        // one through the door at a time
        if (k.nieuw) k.loper.vanaf = this.deur = Math.max(now, (this.deur ?? 0) + 1100);
        this.klanten.set(s.addr, k);
      }
      k.s = s;
    }
    // the counter first, in order of arrival; the rest queues near the door
    for (const k of this.klanten.values()) {
      if (!here.has(k.s.addr) || (k.plek ?? 9) < SLOTS.length) continue;
      const vrij = SLOTS.findIndex((_, i) => !bezet.has(i));
      if (vrij >= 0) { bezet.add(vrij); this.move(k, vrij, now, still); }
    }
    let q = 0;
    for (const k of this.klanten.values()) {
      if (!here.has(k.s.addr) || (k.plek ?? 9) < SLOTS.length) continue;
      const p = SLOTS.length + Math.min(q++, QUEUE.length);
      if (k.plek !== p) this.move(k, p, now, still);
    }
    this.extra = Math.max(0, q - QUEUE.length);
    for (const [addr, k] of this.klanten) {
      if (here.has(addr)) continue;
      if (!k.weg) {
        k.weg = true;
        const [x] = k.loper.at(now);
        k.loper.go([[x, LANE_Y], LANE, DOOR], now, still);
      }
      if (still || !k.loper.walking) this.klanten.delete(addr);
    }
    this.open = true;
    // baskets: one per session that cooks, as long as it cooks
    for (const [addr] of this.mand) {
      const s = list.find((x) => x.addr === addr);
      if (!s || !COOKING.has(s.fase) || !this.aanToog(addr)) this.mand.delete(addr);
    }
    for (const s of opRang(list)) {
      if (!COOKING.has(s.fase) || s.status === "idle" || this.mand.has(s.addr) || !this.aanToog(s.addr)) continue;
      const vrij = [0, 1, 2, 3].find((i) => ![...this.mand.values()].includes(i));
      if (vrij !== undefined) this.mand.set(s.addr, vrij);
    }
  }

  aanToog(addr) { return (this.klanten.get(addr)?.plek ?? 9) < SLOTS.length; }

  move(k, plek, now, still) {
    const was = k.plek;
    k.plek = plek;
    if (plek < SLOTS.length) {
      const [x, y] = SLOTS[plek].feet;
      if (was === null && !k.nieuw) { k.loper.x = x; k.loper.y = y; } else k.loper.go(was === null ? [LANE, [x, LANE_Y], [x, y]] : [[x, LANE_Y], [x, y]], now, still);
    } else {
      const p = QUEUE[plek - SLOTS.length]?.feet ?? DOOR;
      if (was === null && !k.nieuw) { k.loper.x = p[0]; k.loper.y = p[1]; } else k.loper.go([p], now, still);
    }
  }

  // ---------------------------------------------------------------- the workers

  /** Where a session wants a worker and what the worker does there, or null. */
  taak(s, now) {
    if (!this.aanToog(s.addr)) return null;
    const slot = SLOTS[this.klanten.get(s.addr).plek];
    const m = this.mand.get(s.addr);
    const fryer = m === undefined ? A.worker_frietbak : [A.worker_fryer[m][0] + 22, A.worker_fryer[m][1]];
    if (s.fase === "wacht") return { p: slot.worker, pose: "praat", spoed: true };
    if (s.fout) return { p: fryer, pose: "bak0", spoed: true };
    if (s.fase === "klaar") return now - s.sinds < ROEPT || this.staat.demo ? { p: slot.worker, pose: "roept", spoed: true } : null;
    if (s.status !== "working") return null;
    if (s.fase === "diepvries") return { p: A.worker_freezer, pose: "reik" };
    if (s.fase === "denkt") return { p: A.worker_frietbak, pose: "bak0" };
    if (s.fase === "schudt") return { p: fryer, pose: "bak0", pose2: "bak1" };
    return { p: fryer, pose: "bak0" };
  }

  dispatch(list, now, still) {
    const todo = opRang(list).map((s) => ({ s, t: this.taak(s, now) })).filter((x) => x.t);
    const top = todo.slice(0, this.werkers.length);
    const open = [...top];
    const pick = (w, x) => {
      const same = w.taak?.addr === x?.s.addr;
      if (!same) w.since = now;
      w.taak = x ? { addr: x.s.addr, ...x.t } : null;
    };
    const rest = [];
    for (const w of this.werkers) {
      const i = open.findIndex((x) => x.s.addr === w.taak?.addr);
      if (i >= 0) pick(w, open.splice(i, 1)[0]); else rest.push(w);
    }
    for (const w of rest) {
      const mine = todo.find((x) => x.s.addr === w.taak?.addr);
      // not called away every second: only for something urgent
      if (mine && now - w.since < BLIJFT && !open[0]?.t.spoed) pick(w, mine); else pick(w, open.shift() ?? null);
    }
    const [a, b] = this.werkers.map((w) => w.taak?.p ?? A.worker_rest[w.i]);
    const doel = [a, Math.abs(a[0] - b[0]) < 26 && Math.abs(a[1] - b[1]) < 14 ? [b[0] + 34, b[1]] : b];
    this.werkers.forEach((w, i) => {
      const [x, y] = doel[i], end = w.loper.todo.at(-1) ?? [w.loper.x, w.loper.y];
      if (end[0] !== x || end[1] !== y) w.loper.go([[x, y]], now, still);
    });
  }

  /** One 100 ms timer, only while somebody walks. */
  watch(cx) {
    const busy = [...this.klanten.values()].some((k) => k.loper.walking) || this.werkers.some((w) => w.loper.walking);
    if (busy && !this.klok) {
      this.klok = cx.timer.every(100, (cx) => {
        const now = Date.now();
        let changed = false;
        for (const o of [...this.klanten.values(), ...this.werkers]) changed = o.loper.step(now) || changed;
        const still = ![...this.klanten.values()].some((k) => k.loper.walking || k.weg) && !this.werkers.some((w) => w.loper.walking);
        if (still) { this.klok?.cancel(); this.klok = null; changed = true; }
        if (changed) cx.notify();
      });
    }
  }

  // ---------------------------------------------------------------- drawing

  text(s, size, color) { return div().font_family(FONT).text_size(size * s.u).line_height(1.05).text_color(color); }

  /** A box of talk above a head, its point at (x, y). */
  ballon(s, x, y, woord, bg, fg, rand) {
    const w = Math.min(62, Math.max(22, woord.length * 3.1 + 8)), h = woord.length > 17 ? 18 : 11;
    return div().absolute().left(Math.round((x - w / 2) * s.u)).top(Math.round((y - h) * s.u)).w(Math.round(w * s.u)).h(h * s.u)
      .bg(bg).border(s.u).border_color(rand).flex().items_center().justify_center()
      .child(this.text(s, 6.4, fg).text_center().child(woord));
  }

  klant(s, k, now, anim) {
    const { loper } = k, d = k.s, o = `k${k.kleed}`;
    const el = loper.place(div().id(`klant-${d.addr}`), s.u);
    const side = loper.walking ? loper.side : null;
    const inRij = (k.plek ?? 9) >= SLOTS.length;
    let kids;
    if (side) {
      const r = side === "r" ? "-r" : "";
      kids = anim ? frames2(s, `${o}-stap0${r}`, `${o}-stap1${r}`, 0, 0, 520) : [sprite(s, `${o}-stap1${r}`, 0, 0)];
    } else if (inRij && !loper.walking) kids = [sprite(s, `${o}-stap1`, 0, 0)];
    else if (d.fase === "wacht") kids = [sprite(s, `${o}-leun`, 0, 0)];
    else if (d.fase === "eet" && !k.weg) kids = anim ? leeft(s, `${o}-eet`, 0, 0, d.addr) : [sprite(s, `${o}-eet`, 0, 0)];
    else kids = anim ? leeft(s, `${o}-sta`, 0, 0, d.addr) : [sprite(s, `${o}-sta`, 0, 0)];
    return el.children(kids) // each sprite carries its own contact shadow
      .child(div().id(`klik-${d.addr}`).absolute().left(-22 * s.u).top(-98 * s.u).w(44 * s.u).h(98 * s.u).cursor_pointer()
        .on_click(() => {
          if (String(d.addr).startsWith("demo-")) return;
          run("agent.focus", { terminal: d.addr });
          if (findNode(layout(), "main")?.hidden) run("layout.show", { id: "main" });
        }));
  }

  /** What hangs above a customer at the counter: the bon, or something said. */
  praat(s, k, anim) {
    const d = k.s;
    if (k.weg || k.loper.walking || (k.plek ?? 9) >= SLOTS.length) return [];
    const slot = SLOTS[k.plek], x = slot.head[0] + 2, y = slot.head[1] - 5, seed = hash(d.addr);
    const pulse = (el) => (anim ? el.loop("opacity", { from: 0.75, to: 1, period: 900 }) : el);
    if (d.fase === "wacht") {
      return [pulse(this.ballon(s, x, y, zeg("wacht", seed), C.geel, C.inkt, C.rood))];
    }
    if (d.fout) return [this.ballon(s, x, y, zeg("fout", seed), C.rood, "#ffffff", C.rand)];
    if (d.fase === "klaar") return [pulse(this.ballon(s, x, y, T.nummer(d.ticket), C.groen, "#ffffff", C.rand))];
    if (d.fase === "koud") return [this.ballon(s, x, y, zeg("koud", seed), "#dfe5ea", C.koud, C.koud)];
    if (d.fase === "eet" || d.fase === "kiest") return [];
    // the bon: number, prompt, snacks
    const w = 50, h = 24;
    return [div().absolute().left(Math.round((x - w / 2) * s.u)).top(Math.round((y - h) * s.u)).w(w * s.u).h(h * s.u).overflow_hidden()
      .bg(C.papier).border_t(2 * s.u).border_color(KLEUR[d.fase]).px(2 * s.u).shadow_md()
      .child(h_flex().h(7 * s.u).items_center().justify_between().child(this.text(s, 6, C.inkt).child(T.nr(d.ticket)))
        .child(h_flex().gap(s.u).children(Array.from({ length: Math.min(3, d.snacks) }, () => div().w(4 * s.u).h(2 * s.u).bg("#8a4a1c").border(1).border_color(C.inkt)))))
      .child(this.text(s, 5.2, C.inkt).line_height(1.12).child(clip(d.prompt || "…", 34)))];
  }

  /** A basket and what comes out of the fryer, for basket `i` and the session that uses it. */
  frituurmand(s, i, d, anim) {
    const [x, y] = A.baskets[i], out = [];
    const stil = !d || d.fase === "denkt" || d.fase === "diepvries";
    const naam = !d ? "mand-leeg" : d.fout ? "mand-zwart" : stil ? (d.fase === "denkt" ? "mand-leeg" : "mand-rauw") : d.fase === "bakt" ? "mand-bad" : "mand-geel";
    if (d?.fase === "olie") out.push(sprite(s, "olie", x, y + 4));
    else {
      const b = sprite(s, naam, x, y);
      if (anim && d?.fase === "schudt" && !d.fout) {
        out.push(div().absolute().left(0).top(0).loop("left", { from: -s.u, to: s.u, period: 260, easing: "linear" }).child(b));
      } else out.push(b);
    }
    if (d && (d.fase === "bakt" || d.fase === "schudt") && !d.fout) {
      for (let n = 0; n < 6; n++) {
        const bx = x - 8 + ((n * 7) % 17), by = y - 5 + ((n * 5) % 9);
        const el = sprite(s, n % 3 ? "bel-klein" : "bel", bx, by);
        out.push(anim ? el.loop("opacity", { from: -0.6, to: 1, period: 520 + n * 130 }) : el);
      }
    }
    if (d && d.fase === "bakt" && !d.fout) out.push(...this.damp(s, "stoom", x, y - 16, 2, anim));
    if (d?.fout) out.push(...this.damp(s, "rook", x, y - 22, 4, anim));
    if (d?.fase === "test") out.push(anim ? sprite(s, "vonk", x + 9, y - 20).loop("opacity", { from: 0, to: 1, period: 700 }) : sprite(s, "vonk", x + 9, y - 20));
    // whose basket: a tag on the hood
    if (d) {
      out.push(div().absolute().left((x - 8) * s.u).top(88 * s.u).w(16 * s.u).h(9 * s.u).bg(d.fout ? C.rood : C.papier).border(1).border_color(C.rand)
        .flex().items_center().justify_center().child(this.text(s, 6.4, d.fout ? "#ffffff" : C.inkt).child(String(d.ticket))));
    }
    return out;
  }

  /** Puffs swaying above a point. */
  damp(s, naam, x, y, n, anim) {
    return Array.from({ length: n }, (_, i) => {
      const py = y - i * 5, px = x + (i % 2 ? 2 : -2);
      if (!anim) return sprite(s, naam, px, py).opacity(0.7);
      const period = 1500 + i * 370;
      return div().absolute().left(0).top(0).loop("left", { from: -2 * s.u, to: 2 * s.u, period: period * 1.3 }).loop("top", { from: 2 * s.u, to: -4 * s.u, period })
        .child(sprite(s, naam, px, py).loop("opacity", { from: 0.15, to: 0.95, period }));
    });
  }

  werker(s, w, anim) {
    const n = `w${w.i}`, side = w.loper.walking ? w.loper.side : null;
    let kids;
    if (side) {
      const r = side === "r" ? "-r" : "";
      kids = anim ? frames2(s, `${n}-stap0${r}`, `${n}-stap1${r}`, 0, 0, 440) : [sprite(s, `${n}-stap1${r}`, 0, 0)];
    } else if (w.taak?.pose2 && anim) kids = frames2(s, `${n}-${w.taak.pose}`, `${n}-${w.taak.pose2}`, 0, 0, 420);
    else {
      const naam = `${n}-${w.taak?.pose ?? "sta"}`; // standing and talking they blink, at rest they find something to do
      kids = anim ? leeft(s, naam, 0, 0, n) : [sprite(s, naam, 0, 0)];
    }
    return w.loper.place(div().id(`werker-${w.i}`), s.u).children(kids);
  }

  render(cx) {
    shared("frituur.anim"); // re-render when the switch flips
    const now = Date.now(), anim = animOn(), zoom = Number(settings()?.zoom ?? 1) || 1;
    const list = this.staat.list();
    this.plan(list, now, !anim);
    this.dispatch(list, now, !anim);
    this.watch(cx);

    // fill the block, but never so far in that part of the shop falls off
    const w = this.size.width, h = this.hoogte(zoom);
    let schaal = Math.min(Math.max(w / W, h / H), w / (CORE_X1 - CORE_X0), h / CORE_H);
    if (Math.abs(schaal - Math.round(schaal)) < 0.04) schaal = Math.round(schaal); // whole scales are sharpest
    schaal = Math.max(1, schaal);
    const k = Math.min(4, Math.max(2, Math.ceil(schaal)));
    const m = moment(this.pr);
    this.nu = `${m.licht} ${m.seizoen} ${m.weer}`;
    const s = { k, u: schaal / zoom, l: m.licht };
    // the season's things and the weather, per layer: achter (on the room), toog (on the counter), voor (in front of all)
    const extra = (waar) => [...(WEER[m.weer]?.[waar] ?? []), ...(DECOR[m.seizoen]?.[waar] ?? [])]
      .flatMap((g) => (anim ? beurt(s, g, 0, 0, TEMPO[g[0]] ?? 1200) : [sprite(s, g[0], 0, 0)]));
    const left = Math.round((w - W * schaal) / 2) / zoom;

    // beyond the queue one person in the doorway stands for all of them
    const op = [...this.klanten.values()].filter((x, i, l) => x.weg || x.plek !== SLOTS.length + QUEUE.length || l.findIndex((y) => y.plek === x.plek) === i).sort((a, b) => a.loper.y - b.loper.y);
    const bij = new Map([...this.mand].map(([addr, i]) => [i, list.find((x) => x.addr === addr)]));
    const rang = opRang(list);
    const led = rang.find((x) => x.fase === "wacht") ?? rang.find((x) => x.fase === "klaar") ?? rang.find((x) => x.status === "working") ?? rang[0];
    const bel = rang.find((x) => x.fase === "wacht");
    const laag = (naam) => image(`${ART}/${k}x/${m.licht}/${naam}.png`).absolute().left(0).top(0).w(W * s.u).h(H * s.u);
    const D = A.ticket_display;

    const stage = div().absolute().left(left).top(0).w(W * s.u).h(H * s.u)
      .child(laag("scene"))
      .children(extra("achter"))
      .children([0, 1, 2, 3].flatMap((i) => this.frituurmand(s, i, bij.get(i), anim)))
      .children([...this.werkers].sort((a, b) => a.loper.y - b.loper.y).map((w) => this.werker(s, w, anim)))
      .child(laag("counter_overlay"))
      .children(extra("toog"))
      // the live ticket number
      .child(div().absolute().left(D.x * s.u).top(D.y * s.u).w(D.w * s.u).h(D.h * s.u).flex().items_center().justify_center()
        .child(this.text(s, 12, C.led).child(led ? T.nr(led.ticket) : "")))
      .children(op.flatMap((x) => {
        if (x.weg || (x.plek ?? 9) >= SLOTS.length) return [];
        const [px, py] = SLOTS[x.plek].done;
        if (x.s.fase === "klaar") return [sprite(s, "puntzak-warm", px, py), ...this.damp(s, "stoom", px, py - 30, 3, anim)];
        return x.s.fase === "koud" ? [sprite(s, "puntzak-koud", px, py)] : [];
      }))
      .when(Boolean(bel), (el) => {
        const r = sprite(s, "rinkel", A.bell[0], A.bell[1] - 2);
        return el.child(anim ? r.loop("opacity", { from: -0.5, to: 1.5, period: 320, easing: "linear" }) : r);
      })
      .children(op.map((x) => this.klant(s, x, now, anim)))
      .child(laag("front_overlay"))
      .children(extra("voor"))
      .children(op.flatMap((x) => this.praat(s, x, anim)))
      .when(this.extra > 0, (el) => el.child(this.ballon(s, QUEUE[0].head[0] + 34, QUEUE[0].head[1] - 4, T.meer(this.extra), C.papier, C.inkt, C.rand)));

    return div().id("zaak-root").size_full().relative().overflow_hidden().bg(C.muur)
      .on_size_change((size, cx) => {
        if (size.width === this.size.width && size.height === this.size.height) return;
        this.size = size;
        cx.notify();
      })
      .child(stage);
  }
}
