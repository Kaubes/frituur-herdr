// The order rail: one paper bon per session, the most urgent on top. Click one to go to its
// terminal (the drawer comes up when it was down).

import { div, image } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { layout, run, setAgentOrder, shared } from "herdr";
import { ART, C, FONT, KLEUR, animOn, clip, findNode, hash, toggleAnim } from "./kit.js";
import { SPRITES } from "./sprites-data.js";
import { Staat, opRang } from "./staat.js";
import { T, WOORD, sinds } from "./tekst.js";

const txt = (s, size, color) => div().font_family(FONT).text_size(size).line_height(1.05).text_color(color).child(s);

export default class Bonnen {
  init(pr, cx) {
    this.staat = new Staat(pr.demo);
    this.staat.start(cx);
  }

  bon(s, now) {
    const fase = s.fout ? "fout" : s.fase;
    const kleur = KLEUR[fase];
    const roept = fase === "wacht" || fase === "klaar" || fase === "fout";
    const strip = animOn() && fase === "wacht" ? div().h(5).bg(kleur).loop("opacity", { from: 0.25, to: 1, period: 900 }) : div().h(5).bg(kleur);
    const oud = fase === "koud" || fase === "eet";
    return v_flex().id(`bon-${s.addr}`).relative().flex_none().w(196).ml(hash(s.addr) % 9).mb(10)
      .bg(oud ? C.papierOud : C.papier).border(s.focused ? 2 : 1).border_color(s.focused ? C.geel : C.rand).shadow_md().cursor_pointer()
      .hover((el) => el.bg("#ffffff"))
      .on_click(() => {
        if (String(s.addr).startsWith("demo-")) return;
        run("agent.focus", { terminal: s.addr });
        if (findNode(layout(), "main")?.hidden) run("layout.show", { id: "main" });
      })
      // the nail it hangs from
      .child(div().absolute().left(92).top(-7).w(10).h(12).rounded(2).bg(C.staal).border(1).border_color(C.rand))
      .child(strip)
      .child(v_flex().px(10).pt(6).pb(7).gap(3)
        .child(h_flex().items_center().justify_between()
          .child(txt(T.nr(s.ticket), 27, C.inkt))
          .child(txt(sinds(now - s.sinds), 15, C.inktZacht)))
        .child(txt(s.prompt ? clip(s.prompt, 40) : s.besteld === false ? T.zonder : T.onbekend, 17, s.prompt ? C.inkt : C.inktZacht))
        .child(h_flex().items_center().justify_between().gap(6).pt(2)
          .child(h_flex().flex_none().h(20).px(6).items_center().bg(roept ? kleur : "#00000000").border(1).border_color(kleur)
            .child(txt(WOORD[fase], 16, roept ? "#ffffff" : kleur)))
          .child(h_flex().gap(2).items_center().children(Array.from({ length: Math.min(3, s.snacks) }, (_, i) => {
            const n = `snack${i % 4}`, d = SPRITES[n];
            return image(`${ART}/2x/s/${n}.png`).flex_none().w(d[0]).h(d[1]);
          })).when(s.snacks > 3, (el) => el.child(txt(T.meer(s.snacks - 3), 14, C.inktZacht)))))
        .when(Boolean(s.plek), (el) => el.child(txt(clip(s.plek, 26), 14, C.inktZacht).truncate())));
  }

  knop(id, label, actie) {
    return h_flex().id(id).flex_1().h(28).items_center().justify_center().bg(C.hout).border(1).border_color(C.houtLicht).cursor_pointer()
      .hover((el) => el.bg(C.houtLicht)).on_click(actie).child(txt(label, 16, C.creme));
  }

  render(_cx) {
    shared("frituur.anim"); // re-render when the switch flips
    const now = Date.now();
    const list = opRang(this.staat.list());
    if (!this.staat.demo) setAgentOrder(list.map((s) => s.addr));
    return v_flex().id("bonnen-root").size_full().bg(C.donker)
      .child(h_flex().flex_none().h(40).px(14).items_center().justify_between().bg(C.hout)
        .child(txt(T.bestellingen, 23, C.geel)).child(txt(String(list.length), 23, C.creme)))
      // the steel rail the bons hang from
      .child(div().flex_none().h(9).bg(C.staal).border_t(1).border_b(2).border_color(C.staalDonker))
      .child(v_flex().id("bonnen-lijst").flex_1().min_h(0).pt(8).px(10).overflow_y_scroll()
        .children(list.length ? list.map((s) => this.bon(s, now)) : [txt(T.leeg, 18, C.inktZacht).pt(8)]))
      .child(v_flex().flex_none().p(8).gap(6)
        .child(h_flex().child(this.knop("bon-anim", animOn() ? T.animAan : T.animUit, () => toggleAnim()))));
  }
}
