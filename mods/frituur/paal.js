// The wooden post between the rail and the shop. It is as tall as the window, whatever the drawer
// hides, so it tells the shop how much height there is (shared "frituur.hoogte", window px).

import { div } from "gpui-kit";
import { setShared, shared } from "herdr";
import { C } from "./kit.js";

export const HOOGTE = "frituur.hoogte";

export default class Paal {
  init() {}

  render() {
    return div().id("paal-root").size_full().bg(C.houtLicht).border_l(1).border_r(1).border_color(C.rand)
      .on_size_change((size) => {
        if (shared(HOOGTE) !== size.height) setShared(HOOGTE, size.height);
      });
  }
}
