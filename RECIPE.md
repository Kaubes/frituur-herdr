# Frituur

A Belgian frituur for Herdr. Every coding agent is a customer with a ticket number, its work is the
order being cooked behind the counter. The shop fills the window in pixel art; the terminal is a
drawer pulled up over it, and the orders hang as paper bons on a rail at the left.

![Frituur](preview.png)

## What you see

- **Order rail** (left, 230 px, full height): "Bestellingen" and a count, a steel rail, then one paper
  bon per agent, most urgent on top: `NR 12`, time in this state, the prompt's first 40 characters, a
  state word in its colour, a snack per subagent, space and tab. The focused agent's bon has a gold
  edge; cold and eaten orders are darker paper. At the bottom the "Animaties" switch.
- **Shop** (the rest): menu boards, ticket display, freezer, four-basket fryer, frietbak, sauces,
  counter with five customer spots, a two-person queue by the drinks fridge and a "+N" beyond that.
  Stage of 640x400 native pixels scaled to fit the window, hung from the top and clipped.
- **Drawer** (bottom, 420 px, resizable): the shown tab's terminals.
- **Bar** (bottom, 38 px): drawer handle, spaces (when more than one), tabs, + menu.

## How it behaves

- **A new agent** walks in from the door to the counter; when it ends, it walks out and the queue moves up.
- **working:** denkt (worker at the frietbak), diepvries (reading: worker at the freezer), bakt
  (editing: basket in the oil, bubbles, steam), schudt (commands: basket shakes), test (spark), olie
  (compacting: oil can). The basket's hood tag shows whose it is. A failed tool: burnt basket, smoke,
  "Aangebrand." for 7 s.
- **blocked:** the customer leans in, "Welke saus?", the bell flashes, a worker comes to the counter.
- **done:** "Nummer 12!" and a steaming cone; after 5 minutes the cone goes cold.
- **idle:** eats (after an order) or looks at the menu.
- **Two workers** go to the most urgent: blocked longest, errors, just finished, then latest activity.
- **Clicks:** a bon or customer focuses the agent and opens the drawer. Keys (`layout:Frituur`):
  ctrl-shift-j cycles the drawer (closed, 420 px, nearly full), ctrl-shift-b hides the rail.

## Built from

- **Tree:** row [`rail` block, `paal` block, `rechts` column [`vloer` column [`zaak` block, `main` tab block], `tabs` block]].
- **Mod** `frituur`, roles `zaak`, `bonnen`, `tabs`, `paal` by `props.role`; shipped `pane`, `menu`, `new-menu`.
- **herdr:** `agents`, `spaces`, `panes`, `layout`, `settings`, `shared`, `window`, `readTextFile`,
  `watchFolder`, `setAgentOrder`, `nextCommand`; commands `agent.focus`, `layout.show/hide/resize`,
  `space.select`, `tab.select/rename/close`.
- **Files read:** `~/.local/state/frituur/<terminal>.json`, written by the optional Claude Code hook.
  No programs run, no network.
- **Art:** `tools/scene.py` (a small numpy ray tracer), `tools/people.py` and `tools/props.py` (people, food and tools:
  small models drawn with the room's camera, light and 96 colours), baked together by `tools/sprites.py`. Font: Jersey 15 (OFL). The plumbing follows World of Codecraft (MIT).

## Watch out

- Herdr smooths scaled images: draw a fractional scale from the next whole baked scale up, and snap to
  whole scales when close. Measure the height outside the drawer's column, or pulling it up zooms the shop.
- Hide the terminals to close the drawer; never shrink them to nothing.
- `line_height(n)` multiplies. `loop` only swings. Declare `transition` on every render.
- Very wide, low windows show plain wall colour at the sides.
- Without the hook an agent still shows, from Herdr's status only.

## Done when

- `herdr-app check mods/frituur` passes and `herdr-app status` shows no errors.
- `python tools/fake_sessions.py` says "all good".
- An agent that blocks rings the bell and tops the rail; one that ends walks out; a ninth shows "+N".
- ctrl-shift-j opens, enlarges and closes the drawer, and the room never moves.
