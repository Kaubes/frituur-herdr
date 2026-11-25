#!/usr/bin/env python3
"""The food and tools of the frituur: the cone of fries on the counter, the fryer baskets, the snacks, the oil can.
Also what changes with the season (tulips, a fan, pumpkins and leaves, a Christmas tree and lights) and the weather
(rain and snow on the glass of the window and the door).

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
    can=(236, 178, 92), label=(240, 229, 204), dop=(64, 55, 44),
    vaas=(240, 229, 204), steel=(64, 115, 59), blad=(140, 170, 125), tulp1=(181, 61, 26), tulp2=(236, 178, 92), tulp3=(190, 116, 48),
    pompoen=(190, 116, 48), pompoen2=(198, 136, 54), spar=(64, 115, 59), pot=(148, 60, 24), stam=(90, 60, 51), fan=(176, 144, 115), fan2=(106, 74, 57),
    bak=(64, 55, 44), plu1=(148, 60, 24), plu2=(64, 115, 59), plu3=(198, 136, 54), greep=(90, 60, 51), sneeuw=(222, 227, 218))
WIRE, RED = (176, 144, 115), (181, 61, 26)
BZ = 6.11            # where the baskets hang, in the room


class Thing:
    """Something that is not a person: solids and hand-placed pixels around an anchor."""
    def __init__(s, *anchor): s.m = pp.Model(); s.anchor = V(*anchor)
    add, dot, stroke = pp.Doll.add, pp.Doll.dot, pp.Doll.stroke
    def done(s, ground=None, reach=0.14, where="w", fixed=False):
        """What bake() needs to finish it in every light. fixed: it has its own place in the room (see place())."""
        return (s.m, s.anchor, where, ground, reach, fixed)


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


# ------------------------------------------------------------------ the season: on top of the snack display, and around
VIT = (-3.32, 1.605, 3.42)

def tulpen():
    """Spring: a vase of tulips."""
    x, y, z = VIT; t = Thing(*VIT)
    t.add(cone((x, y, z), (x, y + 0.17, z), 0.05, 0.066), "p.vaas", "vaas")
    for i, (dx, dz, h, c) in enumerate(((-0.075, 0.0, 0.37, "tulp1"), (0.0, -0.03, 0.44, "tulp2"), (0.08, 0.01, 0.38, "tulp1"), (-0.03, 0.035, 0.31, "tulp3"), (0.045, 0.04, 0.34, "tulp2"))):
        top = V(x + dx * 1.7, y + h, z + dz); t.add(cap((x + dx * 0.4, y + 0.15, z + dz * 0.4), top, 0.012), "p.steel", f"st{i}")
        t.add(ell(top + V(0, 0.035, 0), (0.036, 0.05, 0.036)), f"p.{c}", f"bl{i}")
    for dx in (-0.10, 0.11): t.add(ell((x + dx, y + 0.24, z), (0.022, 0.085, 0.03)), "p.blad", "blad")
    return t.done(ground=y, where="k", fixed=True)

def pompoen():
    """Autumn: two pumpkins."""
    x, y, z = VIT; t = Thing(*VIT)
    t.add(ell((x - 0.07, y + 0.105, z), (0.145, 0.105, 0.13)), "p.pompoen", "a"); t.add(cap((x - 0.07, y + 0.20, z), (x - 0.05, y + 0.255, z), 0.018, 0.012), "p.stam", "sa")
    t.add(ell((x + 0.15, y + 0.07, z + 0.04), (0.095, 0.07, 0.09)), "p.pompoen2", "b"); t.add(cap((x + 0.15, y + 0.135, z + 0.04), (x + 0.165, y + 0.175, z + 0.04), 0.014, 0.010), "p.stam", "sb")
    for dx in (-0.07, 0.0, 0.07): t.stroke((x - 0.07 + dx, y + 0.20, z - 0.11), (x - 0.07 + dx * 1.2, y + 0.02, z - 0.12), -1, ("a",), 0.06)
    return t.done(ground=y, where="k", fixed=True)

def kerstboom(frame):
    """Winter: a small Christmas tree in a pot; its lights take turns."""
    x, y, z = VIT; t = Thing(*VIT)
    t.add(cone((x, y, z), (x, y + 0.10, z), 0.065, 0.085), "p.pot", "pot"); t.add(cap((x, y + 0.10, z), (x, y + 0.18, z), 0.02), "p.stam", "stam")
    for i, (y0, y1, r0, r1) in enumerate(((0.15, 0.36, 0.17, 0.06), (0.30, 0.50, 0.125, 0.04), (0.44, 0.62, 0.08, 0.012))):
        t.add(cone((x, y + y0, z), (x, y + y1, z), r0, r1), "p.spar", f"tak{i}")
    t.dot((x, y + 0.64, z), (236, 178, 92), ((0, 0), (0, -1), (-1, 0), (1, 0)), tol=0.2)                       # the star
    balls = (((-0.10, 0.20), (181, 61, 26)), ((0.07, 0.24), (236, 178, 92)), ((-0.02, 0.31), (240, 229, 204)), ((0.09, 0.36), (181, 61, 26)),
             ((-0.07, 0.38), (236, 178, 92)), ((0.02, 0.47), (181, 61, 26)), ((-0.03, 0.54), (240, 229, 204)), ((0.0, 0.22), (240, 229, 204)))
    for i, ((dx, dy), c) in enumerate(balls):
        if i % 2 == frame: t.dot((x + dx, y + dy, z - 0.17 + dy * 0.26), c, tol=0.12)
    return t.done(ground=y, where="k", fixed=True)

def ventilator(frame):
    """Summer: a fan, turning."""
    x, y, z = VIT; t = Thing(*VIT); c = V(x, y + 0.36, z)
    t.add(ell((x, y + 0.02, z), (0.11, 0.022, 0.09)), "p.fan2", "voet"); t.add(cap((x, y + 0.03, z), (x, y + 0.24, z), 0.016), "p.fan2", "paal")
    t.add(ell(c, (0.17, 0.17, 0.045)), "p.fan", "kooi"); t.add(ell(c + V(0, 0, -0.03), (0.04, 0.04, 0.03)), "p.fan2", "naaf")
    for a in ((0, 90) if frame == 0 else (45, 135)):
        r = math.radians(a); d = V(math.cos(r), math.sin(r), 0) * 0.15
        t.stroke(c - d + V(0, 0, -0.05), c + d + V(0, 0, -0.05), -2, ("kooi",), 0.08)
    for a in range(0, 360, 30):                                                                                    # the rim of the cage
        r0, r1 = math.radians(a), math.radians(a + 30)
        t.stroke(c + V(math.cos(r0), math.sin(r0), 0) * 0.165, c + V(math.cos(r1), math.sin(r1), 0) * 0.165, -1, ("kooi",), 0.09)
    return t.done(ground=y, where="k", fixed=True)

DEUR = (3.98, 0.0, 1.0)      # against the wall, just inside the door
def paraplubak():
    """Rain: the umbrella stand by the door, three wet umbrellas in it."""
    x, y, z = DEUR; t = Thing(*DEUR)
    t.add(cone((x, 0, z), (x, 0.42, z), 0.105, 0.115) - cone((x, 0.30, z), (x, 0.50, z), 0.085, 0.095), "p.bak", "bak")
    for i, (dx, dz, tx, tz, c) in enumerate(((-0.04, 0.02, -0.13, 0.03, "plu1"), (0.03, -0.03, 0.10, -0.05, "plu2"), (0.02, 0.04, 0.03, 0.12, "plu3"))):
        a = V(x + dx, 0.06, z + dz); b = V(x + tx, 0.78, z + tz)
        t.add(cap(a, b, 0.016, 0.042), f"p.{c}", f"plu{i}"); t.add(cap(b, b + (b - a) * 0.16, 0.012), "p.greep", f"greep{i}")
    return t.done(ground=0.0, reach=0.3, where="k", fixed=True)

def sneeuwhoop():
    """Snow: what was walked in and swept aside at the door."""
    x, y, z = 3.22, 0.0, 1.62; t = Thing(x, y, z)
    for i, (dx, dz, r) in enumerate(((0.0, 0.0, 0.15), (-0.20, 0.10, 0.11), (0.10, 0.26, 0.09), (-0.36, 0.34, 0.07), (-0.50, 0.12, 0.05))):
        t.add(ell((x + dx, 0.0, z + dz), (r, r * 0.55, r * 0.8)) & pp.above(0.0), "p.sneeuw", f"hoop{i}")
    return t.done(ground=0.0, reach=0.2, where="k", fixed=True)

SEASON = {"paraplubak": paraplubak, "sneeuwhoop": sneeuwhoop, "tulpen": tulpen, "pompoen": pompoen, "kerstboom0": lambda: kerstboom(0), "kerstboom1": lambda: kerstboom(1),
          "ventilator0": lambda: ventilator(0), "ventilator1": lambda: ventilator(1)}
# For the mod. Per season and per kind of weather, per layer, groups of sprites; two names in a group take turns.
# The layers follow the mod's drawing order: achter is on the back wall, before anybody; toog comes after the counter
# layer (which also holds the floor, the window and the door), behind the customers; voor is in front of everybody.
DECOR = {"lente": {"toog": [["tulpen"]]}, "zomer": {"toog": [["ventilator0", "ventilator1"]]},
         "herfst": {"toog": [["blaren"], ["pompoen"]]}, "winter": {"achter": [["lichtjes0", "lichtjes1"]], "toog": [["kerstboom0", "kerstboom1"]]}}
WEER = {"regen": {"toog": [["regenL0", "regenL1"], ["regenR0", "regenR1"]], "voor": [["paraplubak"]]},
        "sneeuw": {"toog": [["sneeuwL0", "sneeuwL1"], ["sneeuwR0", "sneeuwR1"], ["sneeuwhoop"]]}}


def place(ims, an, anchor):
    """A sprite that has its own place in the room: drawn with its anchor on (0, 0), it lands there."""
    x, y = pp.SC.proj(V(anchor)); return ims, (an[0] - int(round(float(x))), an[1] - int(round(float(y))))

def room_colour(c):
    """The colour of the room, in the present light, nearest to a colour picked in the evening."""
    return tuple(int(v) for v in pp.PAL[int(((pp.PALF - pp._relit([c], "k")[0]) ** 2).sum(1).argmin())])

def drawn(lichten, G):
    """What is drawn straight onto the picture of the room: fairy lights, fallen leaves, rain and snow on the glass."""
    W, CH = G["W"], G["CH"]; out = {}; rg = np.random.default_rng(7)
    def px(P): x, y = G["proj"](P); return int(math.floor(float(x))), int(math.floor(float(y)))
    # fairy lights: a wire that sags from nail to nail under the menu boards, a bulb every 30 cm
    nails = (-4.0, -1.95, 0.1, 2.38); wire = []; bulbs = []
    for a, b in zip(nails, nails[1:]):
        for i in range(int((b - a) / 0.01) + 1):
            x = a + i * 0.01; u = (x - a) / (b - a); P = (x, 2.44 - 0.13 * 4 * u * (1 - u), 6.47); wire.append(px(P))
            if i % 29 == 14: bulbs.append(px(P))
    glow = ((232, 96, 60), (240, 182, 70), (120, 180, 96), (238, 222, 180))
    leaves = [((rg.uniform(2.95, 4.1), 0.0, rg.uniform(1.25, 2.6)), int(rg.integers(0, 4)), int(rg.integers(0, 3))) for _ in range(13)]
    shapes = (((0, 0), (1, 0)), ((0, 0), (1, 0), (0, 1)), ((0, 0), (1, 0), (2, 0), (1, -1)))
    ys, xs = np.nonzero(G["RAAM"]); side = {"L": xs < W // 2, "R": xs >= W // 2}
    for l in lichten:
        pp.use(l)
        for f in (0, 1):
            im = Image.new("RGBA", (W, CH), (0, 0, 0, 0)); dark = room_colour((64, 55, 44)) + (255,)
            for x, y in wire: im.putpixel((x, y), dark)
            for i, (x, y) in enumerate(bulbs):
                c = glow[i % 4]; c = c if i % 2 == f else tuple(int(v * 0.5) for v in c)
                for dx, dy in ((0, 1), (1, 1), (0, 2), (1, 2)): im.putpixel((x + dx, y + dy), c + (255,))
            out.setdefault(f"lichtjes{f}", {})[l] = im
        im = Image.new("RGBA", (W, CH), (0, 0, 0, 0)); cols = [room_colour(c) + (255,) for c in ((190, 116, 48), (148, 60, 24), (198, 136, 54), (115, 65, 38))]
        for P, c, sh in leaves:
            x, y = px(P)
            for dx, dy in shapes[sh]: im.putpixel((x + dx, y + dy), cols[c])
        out.setdefault("blaren", {})[l] = im
        # rain and snow: a grey veil over the bright glass of the day, and streaks or flakes that move between two frames
        room = np.asarray(G["KAMER"][l][0]).astype(float); lum = (room[ys, xs] @ pp.LUM).mean() / 255.0; day = lum > 0.4
        veil = (52, 60, 80, 120 if day else 0); streak = (40, 50, 74, 210) if day else (176, 196, 236, 215)
        for kind in ("regen", "sneeuw"):
            for f in (0, 1):
                a = np.zeros((CH, W, 4), np.uint8); a[ys, xs] = veil
                if kind == "regen":
                    on = ((3 * xs + ys + 4 * f) % 8 == 0) & ((ys + 2 * xs + 3 * f) % 7 < 5); a[ys[on], xs[on]] = streak
                else:
                    yy = ys - 3 * f; xx = xs + f; on = ((xx * 7 + yy * 13) % 17 == 0) & ((xx * 3 + yy * 5) % 4 != 1); a[ys[on], xs[on]] = (250, 251, 255, 255)
                for sd, m in side.items():
                    b = np.zeros_like(a); b[ys[m], xs[m]] = a[ys[m], xs[m]]
                    out.setdefault(f"{kind}{sd}{f}", {})[l] = Image.fromarray(b, "RGBA")
    res = {}
    for n, ims in out.items():                              # one box for all lights
        box_ = None
        for im in ims.values():
            b = im.getbbox() or (0, 0, 1, 1); box_ = b if box_ is None else (min(box_[0], b[0]), min(box_[1], b[1]), max(box_[2], b[2]), max(box_[3], b[3]))
        res[n] = ({l: im.crop(box_) for l, im in ims.items()}, (-box_[0], -box_[1]))
    return res


def bake(lichten=("avond",), scene=None, report=print):
    """name -> ({light: image}, anchor). Called by tools/sprites.py, which passes the baked room for what is drawn onto it."""
    spec = {f"puntzak-{k}": puntzak(k) for k in ("warm", "koud", "zwart")}
    for nm, fr in (("leeg", None), ("geel", "warm"), ("rauw", "rauw"), ("zwart", "zwart")): spec[f"mand-{nm}"] = basket(fr)
    spec["mand-bad"] = in_oil()
    for k in range(4): spec[f"snack{k}"] = snack(k)
    spec["olie"] = oil_can()
    for n, fn in SEASON.items(): spec[n] = fn()
    out = {}
    for n, (m, anchor, where, ground, reach, fixed) in spec.items():
        r = pp.finish_all(m, anchor, where, ground, reach, lichten); out[n] = place(*r, anchor) if fixed else r
    if scene is not None: out.update(drawn(lichten, scene))
    if report: report(f"props: {len(out)} sprites")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit()
    sp = {n: (ims["avond"], an) for n, (ims, an) in bake().items()}; K = 4; W = sum(im.width + 6 for im, _ in sp.values()) + 6; H = max(im.height for im, _ in sp.values()) + 12
    sh = Image.new("RGBA", (W, H * 2), (233, 196, 127, 255)); sh.paste((120, 68, 41, 255), (0, H, W, H * 2)); x = 6
    for n, (im, an) in sp.items():
        for row in (0, 1): sh.alpha_composite(im, (x, row * H + H - 6 - im.height))
        x += im.width + 6
    sh.convert("RGB").resize((W * K, H * 2 * K), Image.NEAREST).save(sys.argv[1])
