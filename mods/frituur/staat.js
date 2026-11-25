// The sessions: Herdr's agents joined with the files the Claude Code hook writes
// (~/.local/state/frituur/<terminal>.json, integrations/claude-code/frituur-hook.py).
// Agents without a file still show, from Herdr's own status.

import { agents, home, readTextFile, watchFolder, window as appWindow } from "herdr";

const MAP = () => `${home().replace(/\\/g, "/")}/.local/state/frituur`;
const TICK = 1000;
const HERLEES = 10_000; // read everything again this often, whatever the watch says
const KOUD = 5 * 60_000; // finished and nobody looked: cold
const FOUT = 7000; // smoke lasts this long after a failure
const VERS = 12 * 3600_000; // an older file says nothing about what happens now
const ACTS = new Set(["denkt", "diepvries", "bakt", "schudt", "test", "olie"]);
const RANG = { wacht: 0, fout: 1, klaar: 2, koud: 3, olie: 4, test: 4, schudt: 4, bakt: 4, diepvries: 4, denkt: 4, eet: 5, kiest: 6 };

export class Staat {
  constructor(demo) {
    this.demo = demo;
    this.files = new Map(); // address -> parsed file
    this.seen = new Map(); // address -> { status, since }
    this.dirty = true;
    this.readAt = 0;
    this.sig = "";
    this.busy = false;
  }

  start(cx) {
    if (this.demo) {
      if (this.demo === "rondje") cx.timer.every(TICK, (cx) => cx.notify());
      return;
    }
    cx.timer.every(TICK, (cx) => this.tick(cx));
    this.watch(cx);
  }

  /** Marks the files dirty when the hook writes. Without the folder (no session yet): tries again later. */
  watch(cx) {
    cx.spawn(async (cx) => {
      try {
        for (;;) {
          this.kijkt = true;
          await watchFolder(MAP());
          this.dirty = true;
        }
      } catch {
        this.kijkt = false;
        cx.timer.after(5000, (cx) => this.watch(cx));
      }
    });
  }

  async tick(cx) {
    if (this.busy || appWindow()?.visible === false) return;
    this.busy = true;
    try {
      const now = Date.now();
      if (this.dirty || now - this.readAt > (this.kijkt ? HERLEES : 2000)) {
        this.dirty = false;
        this.readAt = now;
        const live = agents();
        for (const a of live) {
          let s = null;
          try { s = JSON.parse((await readTextFile(`${MAP()}/${a.address}.json`)) ?? "null"); } catch { s = this.files.get(a.address) ?? null; }
          if (s) this.files.set(a.address, s); else this.files.delete(a.address);
        }
        const here = new Set(live.map((a) => a.address));
        for (const k of [...this.files.keys()]) if (!here.has(k)) this.files.delete(k);
      }
      const sig = JSON.stringify(this.list().map((s) => [s.addr, s.fase, s.fout, s.ticket, s.prompt, s.tool, s.snacks, Math.floor((now - s.sinds) / 60000)]));
      if (sig !== this.sig) {
        this.sig = sig;
        cx.notify();
      }
    } finally {
      this.busy = false;
    }
  }

  /** Every session, in Herdr's order. */
  list() {
    const now = Date.now();
    if (this.demo) return demoList(now, this.demo);
    const live = agents().filter((a) => a.status);
    const here = new Set(live.map((a) => a.address));
    for (const k of [...this.seen.keys()]) if (!here.has(k)) this.seen.delete(k);
    return live.map((a) => {
      let was = this.seen.get(a.address);
      if (!was || was.status !== a.status) this.seen.set(a.address, (was = { status: a.status, since: now, ate: Boolean(was?.ate || was?.status === "working" || was?.status === "done") }));
      return session(a, this.files.get(a.address), was, now);
    });
  }
}

/** One session as the scene sees it. `f` is the hook's file or undefined. */
export function session(a, f, was, now) {
  if (f && now - (f.t ?? 0) > VERS) f = undefined;
  const snacks = f?.snacks?.length ?? 0;
  let fase, sinds = was.since;
  if (a.status === "blocked") fase = "wacht";
  else if (a.status === "working") {
    fase = f ? (ACTS.has(f.act) ? f.act : "denkt") : "bakt";
    if (f && ACTS.has(f.act)) sinds = f.sinds ?? sinds;
  } else if (a.status === "done") {
    sinds = Math.max(was.since, f?.act === "klaar" ? f.klaarT ?? 0 : 0);
    fase = now - sinds > KOUD ? "koud" : "klaar";
  } else fase = (f ? f.bestelling > 0 : was.ate || titel(a)) ? "eet" : "kiest";
  return {
    addr: a.address,
    status: a.status,
    fase,
    sinds,
    ticket: f?.ticket ?? ((Number(String(a.address).replace(/\D/g, "")) || 1) - 1) % 99 + 1,
    prompt: f?.prompt || (f ? "" : titel(a)),
    // only the hook knows that nothing was ordered; Herdr alone can only say nothing happened since we looked
    besteld: f ? f.bestelling > 0 : null,
    tool: f?.tool ?? "",
    snacks,
    fout: a.status === "working" && f?.fouten > 0 && now - (f.foutT ?? 0) < FOUT,
    t: f?.t ?? was.since,
    focused: Boolean(a.focused),
    plek: [a.space_name, a.tab_name && !/^\d+$/.test(a.tab_name) ? a.tab_name : ""].filter(Boolean).join(" · "),
    naam: a.program?.name ?? "agent",
  };
}

/** The terminal's title when it says what the agent does (no hook: the next best thing), else "". */
function titel(a) {
  const t = String(a.title ?? "").replace(/^[^\p{L}\p{N}]+/u, "").trim();
  const naam = a.program?.name ?? "";
  if (!t || t === a.address || t === naam || t.toLowerCase() === a.program?.key || /^[A-Za-z]:\\|^[~/]|\.exe$|@/.test(t)) return "";
  return t;
}

/** Most urgent first: waiting longest, errors, finished, then the most recent activity. */
export function opRang(list) {
  const rang = (s) => (s.fout ? RANG.fout : RANG[s.fase]);
  return [...list].sort((a, b) => rang(a) - rang(b) || (rang(a) === 0 ? a.sinds - b.sinds : b.t - a.t));
}

// ------------------------------------------------------------------ demo (screenshots, herdr-app check)

const D = (n, fase, prompt, extra = {}) => ({
  addr: `demo-${n}`, status: "working", fase, ticket: n, prompt, tool: "", snacks: 0, besteld: true, fout: false, focused: false, plek: "demo", naam: "Claude Code", min: 1, ...extra,
});
const DEMO = [
  D(12, "wacht", "Maak de inlogpagina af", { status: "blocked", min: 3 }),
  D(13, "bakt", "Nieuwe menukaart in het Frans", { snacks: 2, focused: true }),
  D(14, "schudt", "Zoek uit waarom de build faalt", { fout: true }),
  D(15, "klaar", "Ruim de oude tests op", { status: "done" }),
  D(16, "diepvries", "Hoe werkt de betaalmodule?"),
  D(17, "eet", "Dank u, dat was alles", { status: "idle", min: 22 }),
  D(18, "kiest", "", { status: "idle", besteld: false }),
  D(19, "koud", "Vertaal de website", { status: "done", min: 14 }),
];
const FASES = ["kiest", "denkt", "diepvries", "bakt", "schudt", "test", "olie", "wacht", "klaar", "koud", "eet"];

function demoList(now, demo) {
  // "rondje": the first sessions walk through every fase, a few seconds each
  const list = demo === "rondje" ? DEMO.slice(0, 5).map((s, i) => ({ ...s, fase: FASES[(Math.floor(now / 6000) + i * 3) % FASES.length], fout: false })) : DEMO;
  return list.map((s) => ({ ...s, sinds: now - s.min * 60000, t: now - s.min * 60000 }));
}
