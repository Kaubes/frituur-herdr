# Frituur — a Herdr layout that shows Claude Code agents as a Belgian frituur

## Goal

Build a custom layout/mod for the **Herdr desktop app** (herdr-app, built on herdr-core) that
shows what each Claude Code session is doing as a scene in a frituur:

- every Claude Code session is a **customer** with a ticket number
- the session's work is their **order** being cooked behind the counter

Built and running on Herdr 0.1.18 (Windows). Herdr's own documentation is
`~/.config/herdr-app/AGENTS.md`, with the types in `herdr.d.ts` and `gpui-kit.d.ts` beside it. The
plumbing follows World of Codecraft (https://github.com/kevinpardo/world-of-codecraft).

## What is in this folder

| Path | What |
|---|---|
| `layouts/Frituur.json`, `themes/Frituur.json` | The window (order rail, shop, terminal drawer, tab bar) and its colours |
| `mods/frituur/` | The mod: `zaak.js` (shop), `bonnen.js` (rail), `tabs.js` (bar), `paal.js` (post), `staat.js` (sessions), `loper.js` (walking), `tekst.js` (every string) |
| `mods/frituur/art/{2,3,4}x`, `*-data.js` | **Generated**, never edit: 1:1 art per scale, anchors and sprite sizes |
| `integrations/claude-code/frituur-hook.py` | Claude Code hook, writes `~/.local/state/frituur/<HC_TERMINAL_ID>.json` |
| `tools/scene.py`, `tools/people.py`, `tools/props.py`, `tools/sprites.py` | Draw the room / the people / the food and tools; `python tools/sprites.py` bakes them all, with the effects (45 s; needs numpy + Pillow) |
| `tools/install.py` | Copies everything into Herdr (`--hook` registers the hook, `--bel` sets the bell sound, `--unhook` undoes) |
| `tools/fake_sessions.py` | Tests the hook. `tools/fake_agent.py`: a pretend Claude for a Herdr terminal |
| `assets/` | The room at native size and 3x, and `anchors.json` (generated, native pixels) |

Working on it: edit here, `python tools/install.py`, `herdr-app check mods/frituur`, `herdr-app status`
(no errors), `herdr-app shot x.png` and look at it. `"demo": true` in a block's props shows fixed
sessions, `"demo": "rondje"` walks through every state.

Things learned the hard way:
- The shop scales to fit the block (`schaal` in `zaak.js`): whole scales draw 1:1, others draw the next baked
  scale up, smoothed a little by Herdr. `paal.js` measures the window's height, so the drawer never changes it.
- The stage is 640x400: the 16:9 room plus 40 rows of floor for taller windows. `core` in the anchors always shows.
- `line_height(n)` is a multiplier, not pixels.
- `loop` swings back and forth on one shared clock; nothing can loop one way.
- Closing the drawer hides the terminals (`layout.hide main`): resizing them to nothing would make
  the programs in them redraw.
- The front overlay holds whole objects only (no floor), else it cuts off the feet of people who queue.
- A second Herdr window needs its own short `HERDR_APP_HOME`; the terminal engine is shared anyway.

## Data: how the scene knows what agents are doing

Two sources, combined:

1. **Claude Code hooks** (detail). A small hook script registered in `~/.claude/settings.json`
   writes one JSON file per session, `~/.local/state/frituur/<HC_TERMINAL_ID>.json`.
   Every hook receives `session_id`, so parallel sessions never mix. The fields:
   see the top of the hook script.
2. **Herdr's own agent state** (fallback): working / blocked / done / idle, for agents without the hook.

World of Codecraft uses this same hook-writes-JSON approach; copy its plumbing.

## Event → scene mapping

| Event | What happens in the frituur |
|---|---|
| Session starts | A customer walks in from the door and takes a ticket number |
| Prompt submitted | The order appears on a bon above the customer (shortened prompt) |
| Reading/searching files | Worker checks the freezer |
| Editing files | Fries go into that session's fryer basket, oil bubbles |
| Running commands | Worker shakes the basket |
| Subagent started | An extra snack is added to the customer's tray |
| Tests fail / tool error | Smoke, burnt fries |
| Context compaction | Changing the oil |
| Blocked (needs permission or input) | Bell rings; customer leans in: "Welke saus?" |
| Turn finished | "Nummer 12!" — a cone of fries appears on the counter |
| Finished but ignored for a while | Steam stops, fries go cold |

## Several sessions at once

- One customer slot and one fryer basket per session (5 customer slots, 4 baskets in `anchors.json`).
- More sessions than slots: extra customers wait near the door (`customer_queue_overflow`) with a "+N".
- There are few workers; send one to whichever session has the most important event:
  blocked first, then errors, then most recent activity.
- If two sessions are blocked, the one waiting longest gets the bell.

## Style notes

- Speech bubbles in Flemish, short and dry.
- Warm evening palette; status effects (bell, bubbles, steam, smoke) should be the brightest things on screen.
- No real brand names on menus or products.
