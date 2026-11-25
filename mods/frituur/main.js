// Frituur: every Claude Code session is a customer in a Belgian frituur. One mod, four roles
// (props.role):
//   zaak    the shop: customers, workers, fryer, bell (zaak.js)
//   bonnen  the order rail on the left, one bon per session (bonnen.js)
//   tabs    the bar at the bottom: the drawer's handle, spaces, tabs (tabs.js)
//   paal    the post beside the shop, measures the window's height (paal.js)

import { View, div } from "gpui-kit";
import { props } from "herdr";
import Zaak from "./zaak.js";
import Bonnen from "./bonnen.js";
import Tabs from "./tabs.js";
import Paal from "./paal.js";

const ROLES = { zaak: Zaak, bonnen: Bonnen, tabs: Tabs, paal: Paal };

export default class Frituur extends View {
  init(p, cx) {
    const pr = props() ?? p ?? {};
    const R = ROLES[pr.role];
    if (R) {
      this.role = new R();
      this.role.init(pr, cx);
    } else {
      // No role (herdr-app check): every role with demo sessions, so the check covers them all.
      this.all = Object.values(ROLES).map((K) => {
        const r = new K();
        r.init({ ...pr, demo: true }, cx);
        return r;
      });
    }
  }

  render(cx) {
    if (this.role) return this.role.render(cx);
    return div().flex().flex_col().size_full().children(this.all.map((r) => div().h(400).child(r.render(cx))));
  }
}
