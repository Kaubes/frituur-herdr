// The bar at the bottom: the drawer's handle, the spaces, the shown space's tabs and the + menu.

import { div, image, svg } from "gpui-kit";
import { h_flex, ScrollHandle } from "gpui-base";
import { layout, openOverlay, panes, run, spaces } from "herdr";
import { C, FONT, clip, findNode } from "./kit.js";
import { T } from "./tekst.js";

const STIP = { blocked: "#ff6a4d", done: "#9dbb5c", working: C.geel, idle: "#8a6f5c" };
const stop = (_e, cx) => cx.stop_propagation();

export default class Tabs {
  init() { this.scroll = ScrollHandle.new(); }

  pil(id, label, on, status, extra) {
    return h_flex().id(id).flex_none().h(28).px(11).gap(7).items_center().cursor_pointer()
      .bg(on ? C.houtLicht : C.hout).border(1).border_color(on ? C.geel : C.rand).hover((el) => el.bg(C.houtLicht))
      .children(extra ?? [])
      .child(div().font_family(FONT).text_size(17).max_w(190).truncate().text_color(on ? C.geel : C.creme).child(clip(label, 28)))
      .when(Boolean(status), (el) => el.child(div().size(8).bg(STIP[status] ?? C.staal)));
  }

  render() {
    const all = spaces(), space = all.find((x) => x.active), tabs = (space?.tabs ?? []).filter((t) => !t.settled);
    const op = !findNode(layout(), "main")?.hidden;
    const label = (t) => {
      const lead = panes().find((p) => p.tab === t.id && p.program?.agent) ?? panes().find((p) => p.tab === t.id);
      return { naam: t.named ? t.name : lead?.program?.name ?? t.name, prog: lead?.program };
    };
    return h_flex().id("tabs-root").size_full().min_w(0).px(8).gap(6).items_center().bg(C.donker).border_t(2).border_color(C.rand)
      .child(this.pil("lade", op ? T.terminalNeer : T.terminalOp, false, null).on_click(() => run(op ? "layout.hide" : "layout.show", { id: "main" })))
      .when(all.length > 1, (el) => el.child(h_flex().flex_none().gap(4).px(4).children(all.map((sp) =>
        this.pil(`space-${sp.id}`, sp.name, sp.active, sp.status).on_click(() => run("space.select", { id: sp.id }))
          .on_mouse_down("right", (_e, cx) => { cx.stop_propagation(); openOverlay({ mod: "menu", kind: "popup", width: 200, props: { tab: "space", target: { id: sp.id } } }); })))))
      .when(all.length > 1, (el) => el.child(div().flex_none().w(2).h(22).bg(C.houtLicht)))
      .child(h_flex().id("tabs-scroll").flex_1().min_w(0).h_full().gap(4).items_center().overflow_x_scroll().track_scroll(this.scroll)
        .children(tabs.map((t) => {
          const { naam, prog } = label(t);
          const icon = prog?.icon ? [prog.tint ? svg(prog.icon).size(14).text_color(C.creme) : image(prog.icon).size(14)] : [];
          return this.pil(`tab-${t.id}`, naam, t.active, t.status, icon)
            .on_mouse_down("left", (e, cx) => { cx.stop_propagation(); if (e.click_count === 2) run("tab.rename", { id: t.id }); })
            .on_click(() => {
              run("tab.select", { id: t.id });
              if (!op) run("layout.show", { id: "main" });
            })
            .on_mouse_down("right", (_e, cx) => { cx.stop_propagation(); openOverlay({ mod: "menu", kind: "popup", width: 200, props: { tab: "tab", target: { id: t.id, space: space.id } } }); })
            .when(t.active, (el) => el.child(div().id(`dicht-${t.id}`).text_color(C.inktZacht).hover((x) => x.text_color(C.creme))
              .on_mouse_down("left", stop).on_click((_e, cx) => { cx.stop_propagation(); run("tab.close", { id: t.id }); }).child("×")));
        }))
        .child(this.pil("tab-nieuw", "+", false, null).on_mouse_down("left", stop)
          .on_click(() => openOverlay({ mod: "new-menu", kind: "popup", width: 250, height: 512 }))));
  }
}
