#!/usr/bin/env python3
"""The food and tools of the frituur: the cone of fries on the counter, the fryer baskets, the snacks, the oil can.

Small models finished exactly like the people (tools/people.py): the room's camera, light for the
spot where they stand, the room's edge rules and its 96 colours, and a few pixels placed by hand.

  python tools/props.py sheet.png     all of them, 4x
"""
import math, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import people as pp
from people import V, box, cap, cone, ell

pp.COL["p"] = dict(
    paper=(240, 229, 204), tray=(148, 60, 24), holder=(176, 144, 115), mayo=(240, 229, 204),
    warm=(236, 178, 92), warm2=(198, 136, 54), koud=(195, 164, 122), koud2=(167, 134, 108), zwart=(64, 55, 44), zwart2=(90, 60, 51),
    rauw=(234, 209, 167), rauw2=(209, 188, 155), mesh=(106, 74, 57), inside=(64, 55, 44), handle=(49, 36, 36),
    frikandel=(115, 65, 38), kroket=(198, 136, 54), bal=(190, 116, 48), bun=(207, 156, 87), sla=(64, 115, 59), burger=(80, 37, 26),
    can=(236, 178, 92), label=(240, 229, 204), dop=(64, 55, 44))
WIRE, RED = (176, 144, 115), (181, 61, 26)
BZ = 6.11            # where the baskets hang, in the room


class Thing:
    """Something that is not a person: solids and hand-placed pixels around an anchor."""
    def __init__(s, *anchor): s.m = pp.Model(); s.anchor = V(*anchor)
    add, dot, stroke = pp.Doll.add, pp.Doll.dot, pp.Doll.stroke
    def done(s, ground=None, reach=0.14): return pp.finish(s.m, s.anchor, "w", ground, reach)


def heap(t, c, r, kind, n, lo, hi, seed, flat=1.0):
    """A pile of fries: a mound, and single fries standing out of it in two tones."""
    rg = np.random.default_rng(seed); c = V(c)
    t.add(ell(c, (r, 0.03, r * flat)), f"p.{kind}", "heap")
    for k in range(n):
        a = rg.uniform(0, 6.283); q = r * 0.78 * math.sqrt(rg.uniform(0, 1)); p0 = c + V(q * math.cos(a), 0, q * math.sin(a) * flat)
        tip = p0 + V(rg.uniform(-0.03, 0.03), rg.uniform(lo, hi), rg.uniform(-0.02, 0.02))
        t.add(cap(p0, tip, 0.014), f"p.{kind}{'2' if k % 3 == 0 else ''}", f"fry{k}")


def puntzak(kind):
    """A cone of fries in its holder, on a tray on the counter."""
    t = Thing(0, 1.06, 3.1)
    t.add(box((0, 1.0675, 3.1), (0.11, 0.0075, 0.10), 0.004), "p.tray", "tray")
    t.add(cone((0, 1.075, 3.1), (0, 1.16, 3.1), 0.062, 0.066), "p.holder", "holder")
    t.add(cone((0, 1.085, 3.1), (0, 1.345, 3.1), 0.014, 0.085), "p.paper", "cone")
    heap(t, (0, 1.345, 3.1), 0.080, kind, 14, *((0.02, 0.05) if kind == "koud" else (0.07, 0.14)), seed=5)
    if kind == "warm": t.add(ell((0.012, 1.42, 3.06), (0.042, 0.03, 0.034)), "p.mayo", "mayo")
    for ang in (-62, 0, 62):                                 # the red stripes of the paper
        a = math.radians(ang); t.stroke((0.086 * math.sin(a), 1.335, 3.1 - 0.086 * math.cos(a)), (0.03 * math.sin(a), 1.17, 3.1 - 0.03 * math.cos(a)), RED, ("cone",), 0.05)
    return t.done(ground=1.06)


def basket(fries, y=1.0):
    """The fryer basket hanging on its rail: empty, or full of raw, golden or burnt fries."""
    t = Thing(0, 0.906, BZ); x1, z0, z1, h = 0.15, BZ - 0.19, BZ + 0.19, 0.17
    t.add(box((0, y + h / 2, BZ), (x1, h / 2, 0.19), 0.006), "p.mesh" if fries is None else f"p.{fries}2", "basket")
    if fries is None: t.add(box((0, y + h - 0.004, BZ), (x1 - 0.022, 0.006, 0.19 - 0.022)), "p.inside", "inside")
    else: heap(t, (0, y + h, BZ), 0.135, fries, 18, 0.03, 0.09, seed=3, flat=1.25)
    t.add(box((0, y + 0.155, (5.50 + z0) / 2 + 0.01), (0.015, 0.015, (z0 - 5.50) / 2 + 0.01), 0.004), "p.handle", "handle")
    for x in np.linspace(-x1, x1, 5): t.stroke((x, y + h, z0 - 0.002), (x, y + 0.004, z0 - 0.002), WIRE, ("basket",), 0.03)   # the wire
    for yy in (y + 0.06, y + 0.115):
        t.stroke((-x1, yy, z0 - 0.002), (x1, yy, z0 - 0.002), WIRE, ("basket",), 0.03)
        for xs in (-x1 - 0.002, x1 + 0.002): t.stroke((xs, yy, z0), (xs, yy, z1), WIRE, ("basket",), 0.03)
    for a, b in (((-x1, z0), (x1, z0)), ((x1, z0), (x1, z1)), ((-x1, z0), (-x1, z1)), ((-x1, z1), (x1, z1))):
        t.stroke((a[0], y + h, a[1]), (b[0], y + h, b[1]), WIRE, ("basket", "inside"), 0.03)
    return t.done()


def in_oil():
    """The basket down in the oil: only the top of the fries and the handle show."""
    t = Thing(0, 0.906, BZ)
    t.add(box((0, 0.9205, BZ), (0.15, 0.0145, 0.23), 0.004), "p.warm2", "basket")
    heap(t, (0, 0.93, BZ), 0.12, "warm", 12, 0.01, 0.03, seed=4, flat=1.5)
    t.add(box((0, 0.9475, (5.52 + BZ - 0.21) / 2), (0.012, 0.0125, (BZ - 0.21 - 5.52) / 2), 0.004), "p.handle", "handle")
    for a, b in (((-0.15, BZ - 0.23), (0.15, BZ - 0.23)), ((0.15, BZ - 0.23), (0.15, BZ + 0.23)), ((-0.15, BZ - 0.23), (-0.15, BZ + 0.23)), ((-0.15, BZ + 0.23), (0.15, BZ + 0.23))):
        t.stroke((a[0], 0.935, a[1]), (b[0], 0.935, b[1]), WIRE, ("basket",), 0.03)
    return t.done()


def snack(kind):
    """What goes with the fries: frikandel, kroket, bitterballen, a burger. They sit on the order bons."""
    t = Thing(0, 1.06, 3.05)
    if kind == 0:
        t.add(cap((-0.10, 1.092, 3.05), (0.10, 1.092, 3.05), 0.030), "p.frikandel", "snack")
        for x in (-0.05, 0.0, 0.05): t.stroke((x - 0.012, 1.118, 3.03), (x + 0.012, 1.10, 3.022), -1, ("snack",), 0.04)
    if kind == 1:
        t.add(cap((-0.08, 1.104, 3.05), (0.08, 1.104, 3.05), 0.042), "p.kroket", "snack")
        for x, yy in ((-0.07, 1.12), (-0.02, 1.10), (0.04, 1.125), (0.08, 1.105)): t.dot((x, yy, 3.012), -1, grp=("snack",), tol=0.05)
    if kind == 2:
        for i, (dx, dy) in enumerate(((-0.06, 0), (0.06, 0), (0.0, 0.045))): t.add(ell((dx, 1.10 + dy, 3.05), (0.042, 0.040, 0.042)), "p.bal", f"bal{i}")
    if kind == 3:
        t.add(cone((0, 1.062, 3.05), (0, 1.098, 3.05), 0.076, 0.080), "p.bun", "bun0"); t.add(cone((0, 1.098, 3.05), (0, 1.118, 3.05), 0.090, 0.088), "p.sla", "sla")
        t.add(cone((0, 1.118, 3.05), (0, 1.146, 3.05), 0.083, 0.083), "p.burger", "burger"); t.add(ell((0, 1.146, 3.05), (0.082, 0.056, 0.082)) & pp.above(1.146), "p.bun", "bun1")
        for x, yy, z in ((-0.03, 1.19, 3.01), (0.025, 1.195, 3.02), (0.0, 1.178, 2.985), (0.05, 1.18, 3.0)): t.dot((x, yy, z), (240, 229, 204), grp=("bun1",), tol=0.06)
    return t.done()


def oil_can():
    """The can of fresh oil, on the floor by the fryer."""
    t = Thing(0, 0, 5.4)
    t.add(cone((0, 0, 5.4), (0, 0.50, 5.4), 0.20, 0.20), "p.can", "can"); t.add(cone((0, 0.16, 5.4), (0, 0.34, 5.4), 0.206, 0.206), "p.label", "label")
    t.add(cone((0, 0.50, 5.4), (0, 0.56, 5.4), 0.06, 0.06), "p.dop", "dop")
    for yy in (0.215, 0.285): t.stroke((-0.12, yy, 5.4 - 0.17), (0.12, yy, 5.4 - 0.17), RED, ("label",), 0.06)
    return t.done(ground=0.0, reach=0.30)


def bake(report=print):
    """name -> (image, anchor). Called by tools/sprites.py."""
    out = {f"puntzak-{k}": puntzak(k) for k in ("warm", "koud", "zwart")}
    for nm, fr in (("leeg", None), ("geel", "warm"), ("rauw", "rauw"), ("zwart", "zwart")): out[f"mand-{nm}"] = basket(fr)
    out["mand-bad"] = in_oil()
    for k in range(4): out[f"snack{k}"] = snack(k)
    out["olie"] = oil_can()
    if report: report(f"props: {len(out)} sprites")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit()
    sp = bake(); K = 4; W = sum(im.width + 6 for im, _ in sp.values()) + 6; H = max(im.height for im, _ in sp.values()) + 12
    sh = Image.new("RGBA", (W, H * 2), (233, 196, 127, 255)); sh.paste((120, 68, 41, 255), (0, H, W, H * 2)); x = 6
    for n, (im, an) in sp.items():
        for row in (0, 1): sh.alpha_composite(im, (x, row * H + H - 6 - im.height))
        x += im.width + 6
    sh.convert("RGB").resize((W * K, H * 2 * K), Image.NEAREST).save(sys.argv[1])
