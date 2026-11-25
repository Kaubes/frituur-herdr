// Walking: someone goes along straight legs, each one a native left/top transition.
// A leg starts in a timer tick, so the element already stood somewhere before its target moves
// (GPUI only animates changes made after the transition exists).

export class Loper {
  constructor(x, y, speed) {
    this.x = x; this.y = y; // where it stands, or where the current leg ends
    this.speed = speed; // native pixels per second
    this.todo = []; // points still to walk to
    this.leg = null; // { ax, ay, t0, t1 } while walking towards x, y
    this.fresh = true; // not drawn yet
    this.vanaf = 0; // doesn't set off before this time
  }

  get walking() { return Boolean(this.leg || this.todo.length); }

  /** Where it is now. */
  at(now) {
    const l = this.leg;
    if (!l) return [this.x, this.y];
    const f = Math.min(1, Math.max(0, (now - l.t0) / (l.t1 - l.t0)));
    return [l.ax + (this.x - l.ax) * f, l.ay + (this.y - l.ay) * f];
  }

  /** Walk along these points from where it is now. Still = be there at once. */
  go(points, now, still) {
    if (still) {
      [this.x, this.y] = points[points.length - 1];
      this.leg = null; this.todo = [];
      return;
    }
    const [x, y] = this.at(now);
    if (this.leg) { this.x = x; this.y = y; this.leg = null; }
    this.todo = points.filter((p, i) => Math.hypot(p[0] - (i ? points[i - 1][0] : x), p[1] - (i ? points[i - 1][1] : y)) > 1);
  }

  /** A tick: ends and starts legs; true when something changed. */
  step(now) {
    let changed = false;
    if (this.leg && now >= this.leg.t1) { this.leg = null; changed = true; }
    if (!this.leg && this.todo.length && !this.fresh && now >= this.vanaf) {
      const [x, y] = this.todo.shift();
      const d = Math.hypot(x - this.x, y - this.y);
      this.leg = { ax: this.x, ay: this.y, t0: now, t1: now + (d / this.speed) * 1000, dx: x - this.x, dy: y - this.y };
      this.x = x; this.y = y;
      changed = true;
    }
    if (this.fresh && this.drawn) this.fresh = false;
    return changed;
  }

  /** "l", "r" while walking sideways, else null. */
  get side() {
    const l = this.leg;
    return l && Math.abs(l.dx) > Math.abs(l.dy) ? (l.dx < 0 ? "l" : "r") : null;
  }

  /** Puts an element (drawn around 0,0) where it stands or walks to. */
  place(el, u) {
    this.drawn = true;
    const duration = this.leg ? Math.max(16, this.leg.t1 - this.leg.t0) : 16;
    return el.absolute().w(0).h(0).left(Math.round(this.x * u)).top(Math.round(this.y * u))
      .transition("left", { duration, easing: "linear" }).transition("top", { duration, easing: "linear" });
  }
}
