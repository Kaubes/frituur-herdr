#!/usr/bin/env python3
"""The people of the frituur: customers and workers.

Technique: a 3D base with hand-placed pixels. Every person is a small posable figure (a skeleton
with clothes, hair and props built from rounded solids) that is drawn once, at native size, by the
room's own camera (tools/scene.py: 25 degrees down, nearly orthographic) and lit for the spot where
it stands. That gives perspective, light direction and contact shadows that agree with the room
for every pose and every turn of a head. What a renderer cannot do at 100 pixels (faces, hands,
collars, hems, pockets, laces) is placed by hand, pixel by pixel, at points that ride on the body.

  python tools/sprites.py                   bakes everything, these people included (people.bake())
  python tools/people.py lineup out.png     all characters as black silhouettes, native size
  python tools/people.py sheet out.png      every sprite of every character, native size, with the brief's numbers
"""
import ast, math, os, sys, types
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


# ------------------------------------------------------------------ the room's camera and light
def _scene():
    """Camera, sun, lamps and dither matrix straight from scene.py, without rendering the room."""
    path = os.path.join(HERE, "scene.py")
    want = {"W", "H", "CH", "EPS", "A", "PITCH", "DIST", "TGT", "fwd", "CAM", "right", "up", "TANV", "TANH", "proj",
            "SUN", "SKY", "POINTS", "bayer", "SLOT_X", "SLOT_Z"}
    body = []
    for node in ast.parse(open(path, encoding="utf-8").read()).body:
        names = set()
        if isinstance(node, (ast.Import, ast.ImportFrom)): body.append(node); continue
        if isinstance(node, ast.FunctionDef): names = {node.name}
        elif isinstance(node, ast.Assign): names = {n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)}
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name): names = {node.target.id}
        if names and names <= want: body.append(node)
    g = {"__name__": "scene_consts", "__file__": path}
    saved = sys.argv; sys.argv = ["scene.py"]
    try: exec(compile(ast.Module(body, []), path, "exec"), g)
    finally: sys.argv = saved
    return types.SimpleNamespace(**{k: g[k] for k in want})

SC = _scene()
CAM = SC.CAM
Z_CUSTOMER = SC.SLOT_Z      # 2.56: where customers stand at the counter
Z_WORKER = 4.85             # workers move between z 4.5 and 5.2


# ------------------------------------------------------------------ small maths
def V(*c): return np.array(c[0] if len(c) == 1 else c, np.float64)
def unit(v):
    n = np.linalg.norm(v); return v / n if n > 1e-12 else v
def Rx(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def Ry(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def Rz(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def lerp(a, b, t): return a + (b - a) * t

class Fr:
    """A frame: an origin and three axes (the columns of R: right, up, forward)."""
    def __init__(s, o=(0, 0, 0), R=None): s.o = V(o); s.R = np.eye(3) if R is None else R
    def pt(s, *p): return s.o + s.R @ V(*p)
    def vec(s, *p): return s.R @ V(*p)
    def sub(s, o=(0, 0, 0), R=None): return Fr(s.pt(o), s.R if R is None else s.R @ R)
    @property
    def x(s): return s.R[:, 0]
    @property
    def y(s): return s.R[:, 1]
    @property
    def z(s): return s.R[:, 2]


# ------------------------------------------------------------------ solids (signed distance fields)
INF = float("inf")
class S:
    """A solid: distance function plus a bounding sphere."""
    __slots__ = ("f", "c", "r")
    def __init__(s, f, c, r): s.f = f; s.c = np.asarray(c, np.float64); s.r = float(r)
    def __call__(s, P): return s.f(P)
    def __or__(a, b): return U(a, b)
    def __sub__(a, b): return S(lambda P: np.maximum(a.f(P), -b.f(P)), a.c, a.r)
    def __and__(a, b):
        c, r = (a.c, a.r) if a.r <= b.r else (b.c, b.r)
        return S(lambda P: np.maximum(a.f(P), b.f(P)), c, r)
    def grow(a, t): return S(lambda P: a.f(P) - t, a.c, a.r + t)
    def shell(a, t): return S(lambda P: np.abs(a.f(P)) - t, a.c, a.r + t)

def U(*ss):
    ss = [s for s in ss if s is not None]
    if len(ss) == 1: return ss[0]
    c = np.mean([s.c for s in ss], 0); r = max(np.linalg.norm(s.c - c) + s.r for s in ss); fs = [s.f for s in ss]
    def f(P):
        d = fs[0](P)
        for g in fs[1:]: d = np.minimum(d, g(P))
        return d
    return S(f, c, r)

def SU(a, b, k=0.03):
    """Smooth union: the two solids melt into each other over a distance k."""
    c = (a.c + b.c) / 2; r = max(np.linalg.norm(a.c - c) + a.r, np.linalg.norm(b.c - c) + b.r)
    def f(P):
        da, db = a.f(P), b.f(P); h = np.clip(0.5 + 0.5 * (db - da) / k, 0, 1)
        return db + (da - db) * h - k * h * (1 - h)
    return S(f, c, r)

def at(fr, s):
    """A solid given in a frame's own coordinates."""
    o, R = fr.o, fr.R
    return S(lambda P: s.f((P - o) @ R), o + R @ s.c if np.isfinite(s.r) else o, s.r)

def ell(c, r):
    c = V(c); r = V(r) if np.ndim(r) else V(r, r, r); r2 = r * r; rmin = float(r.min())
    def f(P):
        q = P - c; k0 = np.sqrt(((q / r) ** 2).sum(1)); k1 = np.sqrt(((q / r2) ** 2).sum(1))
        return np.where(k1 > 1e-9, k0 * (k0 - 1) / np.maximum(k1, 1e-9), -rmin)
    return S(f, c, float(r.max()))

def cap(a, b, ra, rb=None):
    """A limb: a capsule from a to b whose radius runs from ra to rb."""
    a, b = V(a), V(b); rb = ra if rb is None else rb; ba = b - a; l2 = max(float(ba @ ba), 1e-12)
    def f(P):
        pa = P - a; t = np.clip((pa @ ba) / l2, 0, 1)
        return np.sqrt(((pa - ba * t[:, None]) ** 2).sum(1)) - (ra + (rb - ra) * t)
    return S(f, (a + b) / 2, math.sqrt(l2) / 2 + max(ra, rb))

def box(c, h, rd=0.0):
    c, h = V(c), V(h); hh = h - rd
    def f(P):
        q = np.abs(P - c) - hh
        return np.sqrt((np.maximum(q, 0) ** 2).sum(1)) + np.minimum(q.max(1), 0) - rd
    return S(f, c, float(np.linalg.norm(h)))

def cone(a, b, ra, rb):
    """A capped cone from a (radius ra) to b (radius rb), flat ends."""
    a, b = V(a), V(b); ba = b - a; baba = float(ba @ ba); rba = rb - ra; k = rba * rba + baba
    def f(P):
        pa = P - a; papa = (pa * pa).sum(1); paba = (pa @ ba) / baba
        x = np.sqrt(np.maximum(papa - paba * paba * baba, 0))
        cax = np.maximum(0, x - np.where(paba < 0.5, ra, rb)); cay = np.abs(paba - 0.5) - 0.5
        ff = np.clip((rba * (x - ra) + paba * baba) / k, 0, 1)
        cbx = x - ra - ff * rba; cby = paba - ff
        s = np.where((cbx < 0) & (cay < 0), -1.0, 1.0)
        return s * np.sqrt(np.minimum(cax * cax + cay * cay * baba, cbx * cbx + cby * cby * baba))
    return S(f, (a + b) / 2, math.sqrt(baba) / 2 + max(ra, rb))

def tor(c, R, r):
    """A ring around the local y axis."""
    c = V(c)
    def f(P):
        q = P - c; return np.sqrt((np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - R) ** 2 + q[:, 1] ** 2) - r
    return S(f, c, R + r)

def hs(o, n):
    """Half-space: everything behind the plane through o with normal n."""
    o, n = V(o), unit(V(n))
    return S(lambda P: (P - o) @ n, o, INF)

def loft(levels, rd=0.0):
    """Stacked ellipses along the local y axis: (y, half-width, half-depth[, centre x, centre z]).
    The workhorse for torsos, coats, skirts and bags."""
    L = np.array([tuple(l) + (0, 0) * (len(l) == 3) for l in levels], np.float64)
    y, a, b, cx, cz = L.T
    a = np.maximum(a - rd, 2e-3); b = np.maximum(b - rd, 2e-3)
    yy = y[0] + rd + (y - y[0]) * ((y[-1] - y[0] - 2 * rd) / (y[-1] - y[0]))
    def f(P):
        py = P[:, 1]; yc = np.clip(py, yy[0], yy[-1])
        A_ = np.interp(yc, yy, a); B_ = np.interp(yc, yy, b)
        u = P[:, 0] - np.interp(yc, yy, cx); v = P[:, 2] - np.interp(yc, yy, cz)
        k0 = np.sqrt((u / A_) ** 2 + (v / B_) ** 2); k1 = np.sqrt((u / (A_ * A_)) ** 2 + (v / (B_ * B_)) ** 2)
        d2 = np.where(k1 > 1e-9, k0 * (k0 - 1) / np.maximum(k1, 1e-9), -np.minimum(A_, B_))
        w = np.abs(py - yc)
        return np.where(w > 0, np.sqrt(np.maximum(d2, 0) ** 2 + w * w), d2) - rd
    c = V((cx.min() + cx.max()) / 2, (y[0] + y[-1]) / 2, (cz.min() + cz.max()) / 2)
    r = max(math.sqrt((yi - c[1]) ** 2 + (max(ai, bi) + rd + math.hypot(xi - c[0], zi - c[2])) ** 2) for yi, ai, bi, xi, zi in zip(y, a, b, cx, cz))
    return S(f, c, r)


# ------------------------------------------------------------------ drawing: the room's camera, native pixels
class Part:
    __slots__ = ("sdf", "mat", "grp")
    def __init__(s, sdf, mat, grp): s.sdf, s.mat, s.grp = sdf, mat, grp

class Model:
    """Everything that makes up one person in one pose."""
    def __init__(s): s.parts = []; s.grp = 0; s.lines = []; s.marks = []
    def add(s, sdf, mat, grp=None):
        if grp is None: s.grp += 1; grp = s.grp
        s.parts.append(Part(sdf, mat, grp)); return s

PX0, PX1, PY0, PY1 = -52, 52, -128, 14   # the window around the anchor that is drawn, native pixels

def trace(parts, anchor):
    """Nearest hit per native pixel: depth, part index. `anchor` is the floor point between the feet."""
    ax, ay = SC.proj(anchor); ax = int(round(float(ax))); ay = int(round(float(ay)))
    x0, y0 = ax + PX0, ay + PY0; w, h = PX1 - PX0, PY1 - PY0
    j, i = np.mgrid[y0:y0 + h, x0:x0 + w]
    xs = (i + 0.5) / SC.W * 2 - 1; ys = 1 - (j + 0.5) / SC.H * 2
    D = SC.fwd + SC.right * (xs * SC.TANH)[..., None] + SC.up * (ys * SC.TANV)[..., None]
    D = (D / np.linalg.norm(D, axis=2, keepdims=True)).reshape(-1, 3)
    T = np.full(len(D), INF); ID = np.full(len(D), -1)
    for k, p in enumerate(parts):
        oc = p.sdf.c - CAM; tc = D @ oc; d2 = oc @ oc - tc * tc; R2 = p.sdf.r ** 2
        idx = np.nonzero(d2 < R2)[0]
        if not len(idx): continue
        hl = np.sqrt(R2 - d2[idx]); t = tc[idx] - hl; t1 = tc[idx] + hl; Dk = D[idx]
        hit = np.zeros(len(idx), bool); live = np.arange(len(idx))
        for it in range(56):
            d = p.sdf.f(CAM + Dk[live] * t[live, None])
            done = d < 1.2e-3
            hit[live[done]] = True
            t[live] += np.where(done, 0, np.maximum(d, 6e-4) * 0.8)
            live = live[~done & (t[live] < t1[live])]
            if not len(live): break
        g = idx[hit]; tg = t[hit]; m = tg < T[g]
        T[g[m]] = tg[m]; ID[g[m]] = k
    return types.SimpleNamespace(T=T.reshape(h, w), ID=ID.reshape(h, w), D=D.reshape(h, w, 3), x0=x0, y0=y0, ax=ax - x0, ay=ay - y0, w=w, h=h)

def clean(mask):
    """Pixel-art hygiene for a silhouette: no stray single pixels, no pinholes."""
    m = mask.copy()
    for _ in range(2):
        p = np.pad(m, 1); n4 = p[:-2, 1:-1].astype(int) + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
        m = (m & (n4 >= 1)) | (~m & (n4 == 4))
    return m


# ------------------------------------------------------------------ anatomy
def anatomy(H=1.68, head=1.18, sh=0.185, depth=0.105, waist=0.145, hip=0.165, belly=0.0, bulk=1.0, legs=0.485,
            neck=1.0, arms=1.0, feet=1.0, butt=0.0, bust=0.0):
    """Measures of one body, in metres: realistic, with head and hands only slightly enlarged so they read at 100 pixels."""
    k = H / 1.72; B = types.SimpleNamespace(H=H, k=k, sh=sh, depth=depth, waist=waist, hip=hip, belly=belly, bulk=bulk, butt=butt, bust=bust)
    B.hr = V(0.100, 0.118, 0.110) * head * 0.92 * (0.80 + 0.20 * k)   # skull radii, a touch over life size; children keep big heads
    B.neck = 0.060 * neck * k; B.neck_r = 0.050 * (0.6 + 0.4 * bulk) * (0.55 + 0.45 * k)
    B.shY = H - 2 * B.hr[1] - B.neck                                # height of the shoulder joints
    B.hipY = legs * H; B.ankle = 0.075 * k ** 0.7
    B.thigh = (B.hipY - B.ankle) * 0.52; B.shin = (B.hipY - B.ankle) * 0.48
    B.pelY = B.hipY + 0.04 * k; B.spine = B.shY - B.pelY
    B.ua = 0.158 * H * arms; B.fa = 0.142 * H * arms; B.hand = 0.054 * (0.45 + 0.55 * k)
    q = bulk * (0.5 + 0.5 * k)
    B.r_sh, B.r_el, B.r_wr = 0.056 * q, 0.046 * q, 0.037 * q
    B.r_hip, B.r_kn, B.r_an = 0.092 * q, 0.065 * q, 0.047 * q
    B.foot = 0.25 * feet * (0.35 + 0.65 * k)
    return B

POSE = dict(yaw=0, sway=0.0, drop=0.0, pz=0.0, ptilt=0, hiptilt=0, twist=0, lean=0, side=0, hyaw=0, hpitch=0, hroll=0, fhp=0.0,
            stance=0.19, footL=(0, 0, 0, 10, 0), footR=(0, 0, 0, 10, 0), armL="hang", armR="hang")

def ik(a, t, l1, l2, pole):
    """Two-bone reach from a towards t; the middle joint bends towards `pole`."""
    d = t - a; L = float(np.linalg.norm(d)); dn = d / max(L, 1e-9)
    L2 = min(max(L, abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    x = (l1 * l1 - l2 * l2 + L2 * L2) / (2 * L2); hh = math.sqrt(max(l1 * l1 - x * x, 0))
    p = pole - dn * float(pole @ dn)
    if np.linalg.norm(p) < 1e-6: p = np.cross(dn, V(1, 0, 0))
    return a + dn * x + unit(p) * hh, a + dn * L2

def arm_goal(r, B, side, spec):
    """Where a hand goes and which way its elbow points, in world space. side: -1 left, +1 right."""
    if callable(spec): return spec(r, B, side)
    sh = r.sh[side]; S_, C, Pl, Hd = r.S, r.chest, r.pel, r.head; L = B.ua + B.fa
    o = side
    if spec == "hang": return sh + V(0, -L * 0.985, 0) + S_.z * 0.035 + S_.x * o * 0.03, -S_.z + S_.x * o * 0.3
    if spec == "pocket": return Pl.pt(o * (B.hip + 0.035), -0.03, 0.045), -S_.z * 1.0 + S_.x * o * 0.9
    if spec == "coatpocket": return Pl.pt(o * (B.hip + 0.01), 0.07, 0.10), -S_.z * 0.7 + S_.x * o * 1.0
    if spec == "hip": return Pl.pt(o * (B.hip + 0.045), 0.085, -0.015), -S_.z * 0.55 + S_.x * o * 1.0
    if spec == "back": return Pl.pt(o * 0.035, 0.07, -B.depth - 0.07), -S_.z * 0.4 + S_.x * o * 1.0
    if spec == "phone": return C.pt(o * 0.075, -0.25, 0.23), -S_.y * 1.0 + S_.x * o * 0.5 - S_.z * 0.4
    if spec == "strap": return C.pt(o * 0.125, -0.12, 0.125), -S_.y * 1.0 + S_.x * o * 0.6 - S_.z * 0.5
    if spec == "neck": return Hd.pt(o * 0.025, -B.hr[1] * 0.75, -B.hr[2] - 0.035), S_.x * o * 1.0 + S_.y * 0.35 - S_.z * 0.25
    if spec == "crossA": return C.pt(-o * 0.105, -0.215, B.depth + 0.055), -S_.y * 0.8 + S_.x * o * 1.0
    if spec == "crossB": return C.pt(-o * 0.075, -0.25, B.depth + 0.075), -S_.y * 0.8 + S_.x * o * 1.0
    raise KeyError(spec)

def rig(B, pose, anchor):
    """Joints and frames of a body in a pose, in world space."""
    P = dict(POSE); P.update(pose); r = types.SimpleNamespace(B=B, P=P)
    k = B.k; r.S = S_ = Fr(anchor, Ry(P["yaw"]))
    r.foot, r.ank, r.hipj, r.knee = {}, {}, {}, {}
    for side, key in ((-1, "footL"), (1, "footR")):
        dx, dz, lift, toe, heel = P[key]
        F0 = S_.sub((side * (P["stance"] / 2 + dx), lift, dz), Ry(side * toe))
        ball = F0.pt(0, 0, 0.44 * B.foot); F = Fr(ball, F0.R @ Rx(heel)); F.o = F.pt(0, 0, -0.44 * B.foot)
        r.foot[side] = F; r.ank[side] = F.pt(0, B.ankle, 0)
    r.pel = Pl = S_.sub((P["sway"], B.pelY - P["drop"], P["pz"]), Rz(-P["hiptilt"]) @ Rx(P["ptilt"]))
    for side in (-1, 1):
        r.hipj[side] = Pl.pt(side * B.hip * 0.56, -0.04 * k, 0)
        r.knee[side], r.ank[side] = ik(r.hipj[side], r.ank[side], B.thigh, B.shin, r.foot[side].z + S_.x * side * 0.12)
    waist = Pl.pt(0, 0.10 * k, 0)
    Rc = Pl.R @ Ry(P["twist"]) @ Rx(P["lean"]) @ Rz(-P["side"])
    r.chest = C = Fr(waist + Rc @ V(0, B.spine - 0.10 * k, 0), Rc)
    r.waist = waist
    Rh = Rc @ Ry(P["hyaw"]) @ Rx(P["hpitch"]) @ Rz(-P["hroll"])
    r.neck0 = C.pt(0, 0.035 * k, -0.012)
    r.head = Fr(r.neck0 + Rc @ V(0, B.neck * 0.45, P["fhp"]) + Rh @ V(0, B.hr[1] * 0.93 + B.neck * 0.5, 0.014), Rh)
    r.sh, r.el, r.wr, r.hand = {}, {}, {}, {}
    for side in (-1, 1): r.sh[side] = C.pt(side * (B.sh - 0.018), -0.058 * k, 0)
    for side, key in ((-1, "armL"), (1, "armR")):
        goal, pole = arm_goal(r, B, side, P[key])
        r.el[side], r.wr[side] = ik(r.sh[side], goal, B.ua, B.fa, pole)
        fz = unit(r.wr[side] - r.el[side]); fx = unit(np.cross(S_.y if abs(fz @ S_.y) < 0.95 else S_.z, fz)); fy = np.cross(fz, fx)
        r.hand[side] = Fr(r.wr[side], np.stack([fx, fy, fz], 1))
    return r


# ------------------------------------------------------------------ body and wardrobe
class Doll:
    """One person being put together: a rig, and the solids hung on it."""
    def __init__(s, B, pose, anchor):
        s.B = B; s.r = rig(B, pose, V(anchor)); s.m = Model(); s.anchor = V(anchor)
    def add(s, sdf, mat, grp=None): s.m.add(sdf, mat, grp); return s

    # ---- skin
    def head(s, skin="skin", nose=1.0, jaw=1.0, chin=0.0, ears=True, cheeks=0.0):
        B = s.B; a, b, c = B.hr; hf = s.r.head
        sk = SU(ell((0, 0, 0), (a, b, c)), ell((0, -b * 0.50 - chin, c * 0.20), (a * 0.80 * jaw + cheeks, b * 0.55, c * 0.76)), 0.03)
        sk = sk | ell((0, -b * 0.17, c * 0.97), (0.014, 0.024, 0.027 * nose))
        if ears: sk = sk | ell((-a * 0.97, -b * 0.13, -c * 0.06), (0.016, 0.030, 0.020)) | ell((a * 0.97, -b * 0.13, -c * 0.06), (0.016, 0.030, 0.020))
        s.add(at(hf, sk), skin, "head")
        s.add(cap(s.r.neck0, hf.pt(0, -b * 0.55, -c * 0.12), B.neck_r * 1.08, B.neck_r), skin, "head")
    def hand(s, side, skin="skin", size=1.0):
        q = s.B.hand / 0.054 * size
        s.add(at(s.r.hand[side], ell((0, 0, 0.050 * q), (0.033 * q, 0.043 * q, 0.058 * q))), skin, f"hand{side}")
    def forearm(s, side, skin="skin", t0=0.0):
        B = s.B; e, w = s.r.el[side], s.r.wr[side]
        s.add(cap(lerp(e, w, t0), w, lerp(B.r_el, B.r_wr, t0), B.r_wr), skin, f"arm{side}")
    def upperarm(s, side, skin="skin"):
        B = s.B; s.add(cap(s.r.sh[side], s.r.el[side], B.r_sh, B.r_el), skin, f"arm{side}")
    def shin(s, side, skin="skin", t0=0.0):
        B = s.B; kn, an = s.r.knee[side], s.r.ank[side]
        s.add(cap(lerp(kn, an, t0), an, lerp(B.r_kn, B.r_an, t0), B.r_an), skin, f"leg{side}")

    # ---- hair: a shell over the skull, cut away over the face
    def hair(s, mat="hair", t=0.014, front=0.52, ang=38, nape=-0.70, lift=0.0, back=0.0, extra=None, grp="hair"):
        a, b, c = s.B.hr
        sh = ell((0, lift, -0.006 - back / 2), (a + t, b + t, c + t + back / 2))
        sh = sh & hs((0, b * front, c * 0.72), (0, -math.sin(math.radians(ang)), math.cos(math.radians(ang)))) & hs((0, nape * b, 0), (0, -1, 0))
        if extra is not None: sh = sh | extra
        s.add(at(s.r.head, sh), mat, grp)

    # ---- clothes
    def torso_solids(s, g=0.012, hem=None, flare=0.0, hemb=None, sho=0.0, rd=0.03, neck=1.0):
        """An upper-body garment: shoulders to waist on the chest, waist to hem on the hips. g: thickness."""
        B = s.B; k = B.k; Lc = B.spine - 0.10 * k; bw = B.depth * 0.92 + B.belly * 0.8
        up = loft([(-Lc - 0.05, B.waist + g, bw + g, 0, B.belly * 0.5),
                   (-Lc * 0.55, (B.waist + B.sh) / 2 + 0.008 + g, B.depth + B.belly * 0.35 + g, 0, B.belly * 0.25 + B.bust * 0.4),
                   (-Lc * 0.24, B.sh * 0.98 + g + sho, B.depth + g, 0, B.bust * 0.3),
                   (-0.012 * k, B.sh + 0.016 + g + sho, B.depth * 0.84 + g, 0, 0),
                   (0.050 * k + g * 0.5, (B.sh * 0.42 + 0.024) * neck + g * 0.6, 0.064 + g * 0.6, 0, -0.008)], rd)
        hem = 0.10 * k if hem is None else hem
        lo = loft([(-hem, B.hip + 0.012 + g + flare, (0.102 + g + flare * 0.7) if hemb is None else hemb, 0, -B.butt * 0.5),
                   (-0.02 * k, B.hip + 0.014 + g + flare * 0.25, 0.106 + B.butt * 0.5 + g, 0, -B.butt * 0.5),
                   (0.10 * k + 0.03, B.waist + g, bw + g, 0, B.belly * 0.5)], min(rd, 0.02))
        return up, lo
    def torso(s, mat, grp="torso", **kw):
        up, lo = s.torso_solids(**kw); s.add(at(s.r.chest, up), mat, grp); s.add(at(s.r.pel, lo), mat, grp)
    # ---- placed by hand: single pixels and thin lines that ride on the body
    def line(s, a, b, mat):
        """A thin strap, leash or handle: one pixel wide, also over empty space."""
        s.m.lines.append((V(a), V(b), mat)); s.m.marks.append(("wire", V(a), V(b), base_colour(mat), None, 0.03))
    def dot(s, P, v, offs=((0, 0),), grp=None, tol=0.03):
        """Pixels at a point of the body, if it faces us. v: a colour, or a number of steps lighter (+) or darker (-)."""
        s.m.marks.append(("dot", V(P), tuple(offs), v, grp, tol))
    def stroke(s, a, b, v, grp=None, tol=0.03):
        """A seam, hem or pocket line across the body."""
        s.m.marks.append(("stroke", V(a), V(b), v, grp, tol))
    def face(s, eye=(49, 36, 36), brow=None, mouth=-2, blush=None, smile=False, open_=False):
        """Eyes, brows and mouth: the few pixels that make a face. They only show where the head is turned to us."""
        a, b, c = s.B.hr; hf = s.r.head; g = ("head",)
        for o in (-1, 1):
            s.dot(hf.pt(o * a * 0.42, b * 0.04, c * 0.90), eye, grp=g, tol=0.022)
            if brow is not None: s.dot(hf.pt(o * a * 0.42, b * 0.26, c * 0.90), brow, grp=g, tol=0.022)
            if blush is not None: s.dot(hf.pt(o * a * 0.60, -b * 0.26, c * 0.76), blush, grp=g, tol=0.022)
        offs = ((-1, 0), (0, 0), (-1, 1), (0, 1)) if open_ else ((-1, 0), (0, 0), (-2, -1), (1, -1)) if smile else ((0, 0),)
        s.dot(hf.pt(0, -b * 0.55, c * 0.93), (102, 11, 8) if open_ else mouth, offs, grp=g, tol=0.022)
    def sleeve(s, side, mat, g=0.012, to=1.0, wide=0.0, grp=None):
        B = s.B; sh, e, w = s.r.sh[side], s.r.el[side], s.r.wr[side]; grp = grp or f"arm{side}"
        if to <= 0.5:
            t = to * 2; s.add(cap(sh, lerp(sh, e, t), B.r_sh + g, lerp(B.r_sh, B.r_el, t) + g + wide), mat, grp); return
        s.add(cap(sh, e, B.r_sh + g, B.r_el + g), mat, grp)
        t = (to - 0.5) * 2; s.add(cap(e, lerp(e, w, t), B.r_el + g, lerp(B.r_el, B.r_wr, t) + g + wide), mat, grp)
    def hips(s, mat, g=0.010, grp="legs"):
        B = s.B; k = B.k
        s.add(at(s.r.pel, loft([(-0.125 * k, B.hip * 0.86 + g, 0.092 + g, 0, 0), (-0.02 * k, B.hip + 0.012 + g, 0.104 + B.butt * 0.5 + g, 0, -B.butt * 0.5),
                                (0.10 * k + 0.02, B.waist + g, B.depth * 0.92 + B.belly * 0.8 + g, 0, B.belly * 0.5)], 0.025)), mat, grp)
    def leg(s, side, mat, g=0.010, to=1.0, flare=0.0, grp=None):
        B = s.B; h, kn, an = s.r.hipj[side], s.r.knee[side], s.r.ank[side]; grp = grp or f"leg{side}"
        if to <= 0.5:
            t = to * 2; s.add(cap(h, lerp(h, kn, t), B.r_hip + g, lerp(B.r_hip, B.r_kn, t) + g + flare), mat, grp); return
        s.add(cap(h, kn, B.r_hip + g, B.r_kn + g), mat, grp)
        t = (to - 0.5) * 2; s.add(cap(kn, lerp(kn, an, t), B.r_kn + g, lerp(B.r_kn, B.r_an, t) + g + flare), mat, grp)
    def shoe(s, side, mat="shoe", sole="sole", hi=0.0, chunky=1.0):
        B = s.B; F = s.r.foot[side]; L = B.foot; w = 0.048 * (0.5 + 0.5 * B.k) * chunky; hh = 0.047 * chunky
        up = box((0, hh + 0.012, L * 0.20), (w, hh, L * 0.47), 0.032) | ell((0, 0.035, L * 0.50), (w * 0.95, 0.034 * chunky, L * 0.2))
        if hi > 0: up = up | cap((0, 0.06, 0), (0, 0.06 + hi, -0.004), B.r_an + 0.018, B.r_an + 0.022)
        s.add(at(F, up), mat, f"foot{side}")
        s.add(at(F, box((0, 0.011, L * 0.20), (w + 0.004, 0.011, L * 0.485), 0.008)), sole, f"foot{side}")


# ------------------------------------------------------------------ pictures
def px(t, P):
    """A world point as a pixel of the traced window."""
    x, y = SC.proj(P); return int(math.floor(float(x))) - t.x0, int(math.floor(float(y))) - t.y0

def render_mask(model, anchor):
    """The silhouette: every solid, plus the thin lines (straps, leashes) that are placed by hand."""
    t = trace(model.parts, anchor); m = clean(t.ID >= 0)
    if model.lines:
        im = Image.fromarray(m.astype(np.uint8) * 255); dr = ImageDraw.Draw(im)
        for a, b, _ in model.lines: dr.line([px(t, a), px(t, b)], fill=255)
        m = np.asarray(im) > 0
    return m, t

# Base colours, every one of them out of the room's own 96. The room has no blue, so denim is slate-brown.
SKIN = {"fair": (222, 193, 147), "light": (221, 184, 126), "tan": (191, 142, 88), "brown": (147, 100, 63), "dark": (108, 67, 49)}
HAIR = {"black": (49, 36, 36), "dark": (64, 55, 44), "brown": (90, 60, 51), "chestnut": (115, 65, 38), "auburn": (146, 77, 33), "blond": (207, 156, 87), "grey": (176, 144, 115), "white": (234, 209, 167)}
CREAM, WHITE, COOL = (234, 209, 167), (240, 229, 204), (222, 227, 218)
SLATE, CHARCOAL, TAUPE, SAND, KHAKI = (106, 74, 57), (64, 55, 44), (136, 104, 84), (195, 164, 122), (166, 120, 79)
RED, DEEPRED, RUST, ORANGE, OCHRE, YELLOW = (181, 61, 26), (135, 20, 11), (148, 60, 24), (203, 92, 26), (198, 136, 54), (239, 194, 94)
GREEN, SAGE, BROWN, DARKBROWN, LEATHER = (64, 115, 59), (140, 170, 125), (115, 65, 38), (80, 37, 26), (124, 60, 30)
COL = {
 "k0": dict(skin=SKIN["brown"], hair=HAIR["black"], phones=CREAM, hoodie=SAGE, rib=GREEN, jeans=CHARCOAL, shoe=WHITE, sole=TAUPE, phone=CHARCOAL),
 "k1": dict(skin=SKIN["fair"], hair=HAIR["white"], coat=TAUPE, collar=DARKBROWN, tights=SAND, shoe=DARKBROWN, sole=CHARCOAL, handbag=LEATHER, bag=RED, handle=CREAM, leek=GREEN, bread=OCHRE),
 "k2": dict(skin=SKIN["light"], hair=HAIR["brown"], helm=WHITE, hoodie=SLATE, vest=YELLOW, cargo=KHAKI, boot=OCHRE, sole=CHARCOAL, pouch=LEATHER, hammer=BROWN, cooler=DEEPRED, coolerlid=CREAM),
 "k3": dict(skin=SKIN["light"], hair=HAIR["chestnut"], helm=WHITE, jersey=RED, shorts=CHARCOAL, sock=WHITE, shoe=CREAM, sole=CHARCOAL, bidon=COOL),
 "k4": dict(skin=SKIN["brown"], hair=HAIR["black"], jacket=RED, bag=GREEN, bagflap=SAGE, charm=YELLOW, leggings=SLATE, boot=OCHRE, sole=CHARCOAL),
 "k5": dict(skin=SKIN["fair"], hair=HAIR["brown"], shirt=COOL, trousers=SLATE, shoe=DARKBROWN, sole=CHARCOAL, jacket=TAUPE, tie=DEEPRED, bag=CHARCOAL),
 "k6": dict(skin=SKIN["fair"], hair=HAIR["blond"], hat=DEEPRED, pom=WHITE, jacket=SLATE, scarf=RED, jeans=TAUPE, shoe=WHITE, sole=CREAM),
 "k7": dict(skin=SKIN["fair"], hair=HAIR["auburn"], coat=GREEN, tights=CHARCOAL, welly=OCHRE, sole=CHARCOAL, umbrella=DEEPRED),
 "k8": dict(skin=SKIN["tan"], hair=HAIR["dark"], sweater=OCHRE, carrier=SLATE, baby=CREAM, bootie=WHITE, babyskin=SKIN["tan"], babyhat=WHITE, jeans=SLATE, shoe=BROWN, sole=CREAM, rabbit=SAND),
 "k9": dict(skin=SKIN["dark"], hair=HAIR["black"], scrubs=SAGE, under=WHITE, clog=WHITE, sole=CREAM, tote=OCHRE, strap=BROWN),
 "k10": dict(skin=SKIN["tan"], hair=HAIR["black"], cap=DEEPRED, jacket=CHARCOAL, cube=ORANGE, lid=CHARCOAL, strap=CHARCOAL, joggers=TAUPE, shoe=WHITE, sole=CREAM, phone=CHARCOAL),
 "k11": dict(skin=SKIN["fair"], hair=HAIR["white"], cap=TAUPE, shirt=CREAM, trousers=KHAKI, shoe=DARKBROWN, sole=CHARCOAL, cane=BROWN, dog=WHITE, leash=DEEPRED),
 "k12": dict(skin=SKIN["fair"], hair=HAIR["brown"], jacket=LEATHER, shirt=CREAM, jeans=SLATE, boot=DARKBROWN, sole=CHARCOAL, gigbag=KHAKI, gigpocket=TAUPE),
 "k13": dict(skin=SKIN["tan"], scarf=SAND, coat=RUST, belt=DARKBROWN, trousers=CHARCOAL, boot=DARKBROWN, sole=CHARCOAL, tote=CREAM, strap=BROWN, card=COOL),
 "w0": dict(skin=SKIN["fair"], hair=HAIR["chestnut"], band=RED, blouse=WHITE, cuff=CREAM, trousers=CHARCOAL, clog=WHITE, sole=CREAM, apron=RED, towel=WHITE),
 "x": dict(cone=WHITE, fries=YELLOW, mayo=CREAM),
 "w1": dict(skin=SKIN["tan"], hair=HAIR["dark"], cap=WHITE, shirt=DEEPRED, trousers=CHARCOAL, shoe=DARKBROWN, sole=CHARCOAL, apron=WHITE, pad=CREAM, pen=DEEPRED),
}
def base_colour(mat):
    who, what = mat.split("."); return COL[who][what]
def debug_shade(model, anchor):
    """Base colours with a simple light: for checking shapes while modelling, not the final look."""
    t = trace(model.parts, anchor); h, w = t.ID.shape; out = np.zeros((h, w, 4), np.uint8); hit = t.ID >= 0
    P = CAM + t.D * np.where(hit, t.T, 0)[..., None]; e = 2.5e-3
    for k, p in enumerate(model.parts):
        q = t.ID == k
        if not q.any(): continue
        Pk = P[q]; f = p.sdf.f
        n = np.stack([f(Pk + V(e, 0, 0)) - f(Pk - V(e, 0, 0)), f(Pk + V(0, e, 0)) - f(Pk - V(0, e, 0)), f(Pk + V(0, 0, e)) - f(Pk - V(0, 0, e))], 1)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        c = base_colour(p.mat)
        l = 0.42 + 0.5 * np.clip(n @ SC.SUN, 0, 1) + 0.18 * np.clip(n[:, 1], 0, 1)
        out[q, :3] = np.clip(np.array(c)[None] * l[:, None], 0, 255); out[q, 3] = 255
    names = sorted({str(p.grp) for p in model.parts}); grp = np.array([names.index(str(p.grp)) for p in model.parts] + [-1])[t.ID]
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        ng = np.roll(grp, (dy, dx), (0, 1)); nt = np.roll(t.T, (dy, dx), (0, 1))
        ed = hit & (ng != grp) & (ng >= 0) & (t.T > nt + 0.02); out[ed, :3] = (out[ed, :3] * 0.7).astype(np.uint8)
    return Image.fromarray(out, "RGBA"), t


# ------------------------------------------------------------------ finishing a picture the way the room is finished
def _palette():
    im = np.asarray(Image.open(os.path.join(ROOT, "assets", "frituur_scene_1x.png")).convert("RGB"))[:SC.H]
    return np.unique(im.reshape(-1, 3), axis=0)
PAL = _palette(); PALF = PAL.astype(np.float64)        # the room's 96 colours
TOP = 0.945                                            # no pixel of a person is brighter: bell, steam and bubbles stay on top
USE = np.nonzero(PAL.max(1) / 255.0 <= TOP)[0]

AMB = V(0.19, 0.14, 0.18)                              # scene.py: ambient, sky dome, sun colour, exposure, grade
SKYD = [(V(0, 1, 0), 0.30)] + [(V(math.cos(math.radians(52)) * math.cos(math.radians(20 + 60 * k)), math.sin(math.radians(52)),
                                  math.cos(math.radians(52)) * math.sin(math.radians(20 + 60 * k))), 0.14) for k in range(6)]
SUNCOL = V(3.6, 1.9, 0.70)
# Customers stand where the low sun reaches some of them and not others, so they get it at part strength,
# from its true direction; behind the counter there is only lamp light. `fill` is the lit room behind the viewer.
LIGHT = {"k": dict(sun=0.20, fill=V(0.26, 0.21, 0.17)), "w": dict(sun=0.0, fill=V(0.30, 0.25, 0.20))}

def expose(col): return 1 - np.exp(-np.clip(col, 0, None) * 1.45)
def grade(img):
    lum = img.mean(-1, keepdims=True); img = lum + (img - lum) * 1.22
    img = img + ((1 - np.clip(lum, 0, 1)) ** 3) * V(0.06, 0.015, 0.04)
    img = np.clip(img, 0, 1); return np.clip(img * img * (3 - 2 * img) * 0.55 + img * 0.45, 0, 1)

_X = np.linspace(0, 1, 513); _G = _X * _X * (3 - 2 * _X) * 0.55 + _X * 0.45
LREF = V(0.86, 0.74, 0.62)                             # the light under which a material shows its base colour
def albedo(rgb):
    """The surface colour that the room's exposure and grade turn into `rgb` under ordinary light."""
    v = np.interp(V(rgb) / 255.0, _G, _X); lum = v.mean(); v = lum + (v - lum) / 1.22
    return -np.log(1 - np.clip(v, 0, 0.985)) / 1.45 / LREF

def nearest(rgb, idx):
    """Index (into idx) of the palette colour nearest to each rgb (0..1)."""
    return ((rgb[:, None, :] * 255.0 - PALF[idx][None]) ** 2).sum(2).argmin(1)

LUM = V(0.30, 0.59, 0.11)
LREFS = 0.80                                           # the amount of light under which a material shows its base colour
NS, LS0, LS1 = 96, math.log(0.16), math.log(2.6)       # light levels a ramp is tabulated for
def _hue(s_):
    """Shade leans to the room's maroon, light to its warm cream: the hue shift every surface in the room shows."""
    t = np.clip(np.log(s_) / math.log(2.6), -1, 1)
    return np.where((t < 0)[:, None], 1 + np.outer(-t, V(-0.10, -0.20, -0.08)), 1 + np.outer(t, V(0.10, 0.02, -0.16)))
def _near(rgb, idx):
    """Nearest room colour, judged on hue before brightness so a ramp stays in its colour family."""
    def yc(c): y = c @ LUM; return np.stack([y * 0.6, (c[..., 0] - y) * 2.2, (c[..., 2] - y) * 2.2], -1)
    return ((yc(rgb * 255.0)[:, None, :] - yc(PALF[idx])[None]) ** 2).sum(2).argmin(1)
FAMILY = {SAGE: [(30, 19, 20), (49, 36, 36), (64, 115, 59), (140, 170, 125)], GREEN: [(30, 19, 20), (49, 36, 36), (64, 115, 59), (140, 170, 125)]}
RIM = {SAGE: (222, 227, 218)}
_RAMP = {}
def ramp(mat):
    """A material's ramp: the room colour it takes at each light level, from deep shade to full light."""
    if mat not in _RAMP:
        a = albedo(base_colour(mat)); s_ = np.exp(np.linspace(LS0, LS1, NS))
        want = grade(expose(a * LREF * s_[:, None] * _hue(s_)))
        if base_colour(mat) in FAMILY:
            fam = np.array([int(((PALF - V(c)) ** 2).sum(1).argmin()) for c in FAMILY[base_colour(mat)]])
            tb = fam[np.abs((want * 255.0) @ LUM - (PALF[fam] @ LUM)[:, None]).argmin(0)]
        else: tb = USE[_near(want, USE)]
        for i in range(1, NS):                              # never darker as the light grows
            if PALF[tb[i]] @ LUM < PALF[tb[i - 1]] @ LUM: tb[i] = tb[i - 1]
        steps = [tb[0]]; first = [0]
        for i, v in enumerate(tb[1:], 1):
            if v != steps[-1]: steps.append(v); first.append(i)
        last = first[1:] + [NS]; mid = np.array([(a_ + b_ - 1) / 2 for a_, b_ in zip(first, last)])
        _RAMP[mat] = (np.array(steps), steps, mid)
    return _RAMP[mat]

def union(parts, P):
    """Distance from each point to the nearest solid of the whole figure."""
    d = np.full(len(P), INF)
    for p in parts:
        i = np.nonzero(np.linalg.norm(P - p.sdf.c, axis=1) - p.sdf.r < d)[0]
        if len(i): d[i] = np.minimum(d[i], p.sdf.f(P[i]))
    return d

def lighting(P, N, ao, sunvis, where):
    lt = LIGHT[where]; L = np.outer(0.45 + 0.55 * ao, AMB)
    for dv, wgt in SKYD: L += SC.SKY * (wgt * 1.6 * np.clip(N @ dv, 0, 1) * ao)[:, None]
    if lt["sun"]: L += SUNCOL * lt["sun"] * (np.clip(N @ SC.SUN, 0, 1) * sunvis)[:, None]
    L += lt["fill"] * (np.clip(-N[:, 2] * 0.8 + 0.2, 0, 1) * (0.5 + 0.5 * ao))[:, None]
    for pos, c, inten, rad in SC.POINTS:
        v = V(pos) - P; dist = np.linalg.norm(v, axis=1); nl = np.clip((N * v).sum(1) / np.maximum(dist, 1e-6), 0, 1)
        L += V(c) * (inten * (0.25 + 0.75 * nl) / (1 + (dist / rad) ** 2) ** 2)[:, None]
    return L

SHADOW = (30, 9, 9)
DITHER = 0.30                                          # share of the way between two ramp steps that is dithered (4x4 Bayer, as the room)
SOFT = 0.62
def shade(model, anchor, where="k", ground=0.0, reach=0.50):
    """One person or thing, finished: lit for the spot, the room's exposure and grade, its edge rules, its dither and its
    96 colours. `ground`: the height of the surface it stands on (None: it hangs, no shadow); `reach`: how far its shadow runs."""
    parts = model.parts; t = trace(parts, anchor); h, w = t.ID.shape; hit = t.ID >= 0
    P = CAM + t.D * np.where(hit, t.T, 0)[..., None]; N = np.zeros((h, w, 3)); alb = np.zeros((h, w, 3)); e = 2.5e-3
    mats = sorted({p.mat for p in parts}); grps = sorted({str(p.grp) for p in parts})
    MI = np.full((h, w), -1); G = np.full((h, w), -1)
    for k, p in enumerate(parts):
        q = t.ID == k
        if not q.any(): continue
        Pk = P[q]; f = p.sdf.f
        n = np.stack([f(Pk + V(e, 0, 0)) - f(Pk - V(e, 0, 0)), f(Pk + V(0, e, 0)) - f(Pk - V(0, e, 0)), f(Pk + V(0, 0, e)) - f(Pk - V(0, 0, e))], 1)
        N[q] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        alb[q] = albedo(base_colour(p.mat)); MI[q] = mats.index(p.mat); G[q] = grps.index(str(p.grp))
    Pf, Nf = P[hit], N[hit]
    ao = np.ones(len(Pf))                                  # soft shade where forms come close: under the chin, arm against body
    for hh, wgt in ((0.03, 0.40), (0.07, 0.35), (0.15, 0.25)): ao -= wgt * np.clip(1 - union(parts, Pf + Nf * hh) / hh, 0, 1)
    ao = np.clip(ao, 0, 1); sv = np.ones(len(Pf))
    if LIGHT[where]["sun"]:                                # the figure's own shadow from the sun
        i = np.nonzero(Nf @ SC.SUN > 0)[0]; O = Pf[i] + Nf[i] * 0.014; tt = np.full(len(i), 0.01); vis = np.ones(len(i), bool)
        for _ in range(20):
            dd = union(parts, O + SC.SUN * tt[:, None]); vis &= dd > 0.003; tt += np.clip(dd, 0.012, 0.25)
        sv[:] = 0; sv[i] = vis
    sval = np.zeros((h, w)); sval[hit] = lighting(Pf, Nf, ao, sv, where) @ LUM / LREFS      # light per pixel, 1 = base colour
    # the room's edge rules: the far side of a step in depth is 30% darker, an edge that faces up gets a thin highlight
    far = np.zeros((h, w), bool); open_ = np.zeros((h, w), bool)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nh = np.roll(hit, (dy, dx), (0, 1)); ng = np.roll(G, (dy, dx), (0, 1)); nt = np.roll(t.T, (dy, dx), (0, 1))
        far |= hit & nh & (ng != G) & (t.T > nt + 0.02)
        if (dy, dx) != (1, 0): open_ |= hit & ~nh          # the outline, except where the open side is above
    uh = np.roll(hit, 1, 0); ug = np.roll(G, 1, 0); ut = np.roll(t.T, 1, 0)
    top = hit & (N[..., 1] > 0.15) & (~uh | ((ug != G) & (ut > t.T + 0.02)))
    sval = np.where(sval > 1, 1 + (sval - 1) * SOFT, sval)                       # strong light rolls off: base colours stay themselves
    sval[far] *= 0.62; sval[open_ & ~top & ~far] *= 0.76
    sval[top] = sval[top] * 1.22 + 0.03
    thr = np.tile(SC.bayer + 0.47 + 1 / 32, (h // 4 + 2, w // 4 + 2))[(t.y0 % 4):(t.y0 % 4) + h, (t.x0 % 4):(t.x0 % 4) + w]
    u = (np.log(np.clip(sval, 1e-3, None)) - LS0) / (LS1 - LS0) * (NS - 1)       # position on the ramp
    PI = np.full((h, w), -1)                               # palette index per pixel
    for k, m in enumerate(mats):
        q = MI == k
        if not q.any(): continue
        cols, _, mid = ramp(m); uq = u[q]
        if len(cols) == 1: PI[q] = cols[0]; continue
        i = np.clip(np.searchsorted(mid, uq) - 1, 0, len(mid) - 2); f = (uq - mid[i]) / (mid[i + 1] - mid[i])
        PI[q] = cols[i + (np.clip((f - 0.5) / DITHER + 0.5, 0, 1) > thr[q])]     # ordered dither, only where two steps meet
        if base_colour(m) in RIM:
            e_ = q & top & (sval > 1.0) & (PI == cols[-1]); PI[e_] = int(((PALF - V(RIM[base_colour(m)])) ** 2).sum(1).argmin())
    # what is placed by hand
    D = np.linalg.norm
    def at_px(Pw, tol):
        x, y = px(t, Pw)
        return (x, y) if 0 <= x < w and 0 <= y < h and hit[y, x] and D(Pw - CAM) <= t.T[y, x] + tol else None
    def put(x, y, v, grp):
        if not (0 <= x < w and 0 <= y < h) or not hit[y, x] or (grp is not None and grps[G[y, x]] not in grp): return
        if isinstance(v, int):
            r_ = ramp(mats[MI[y, x]])[1]; j = r_.index(PI[y, x]) if PI[y, x] in r_ else len(r_) - 1; PI[y, x] = r_[min(max(j + v, 0), len(r_) - 1)]
        else: PI[y, x] = int(((PALF - V(v)) ** 2).sum(1).argmin())
    wires = []
    for kind, a, b, v, grp, tol in model.marks:
        if kind == "dot":
            c = at_px(a, tol)
            if c:
                for ox, oy in b: put(c[0] + ox, c[1] + oy, v, grp)
        else:
            (x0, y0), (x1, y1) = px(t, a), px(t, b); n = max(abs(x1 - x0), abs(y1 - y0), 1)
            for i in range(n + 1):
                x = round(x0 + (x1 - x0) * i / n); y = round(y0 + (y1 - y0) * i / n); Pw = a + (b - a) * (i / n)
                if not (0 <= x < w and 0 <= y < h): continue
                if kind == "wire":
                    if not hit[y, x] or D(Pw - CAM) <= t.T[y, x] + tol: wires.append((x, y, v))
                elif D(Pw - CAM) <= t.T[y, x] + tol: put(x, y, v, grp)
    out = np.zeros((h, w, 4), np.uint8); out[hit, :3] = PAL[PI[hit]]; out[hit, 3] = 255
    for x, y, v in wires: out[y, x, :3] = PAL[int(((PALF - V(v)) ** 2).sum(1).argmin())]; out[y, x, 3] = 255
    # the contact shadow: where the figure hides the floor from the sun, close to the feet, and a darker core right under them
    if ground is None: return Image.fromarray(out, "RGBA"), t
    solid = out[..., 3] > 0; ty = (ground - CAM[1]) / t.D[..., 1]; F = CAM + t.D * ty[..., None]
    rows = slice(max(0, t.ay - 16), h); q = np.zeros((h, w), bool); q[rows] = ~solid[rows]
    Fq = F[q] + V(0, 0.004, 0); sd = -SC.SUN * 0 + SC.SUN; tt = np.full(len(Fq), 0.02); occ = np.zeros(len(Fq)); live = np.ones(len(Fq), bool)
    REACH = reach
    for _ in range(22):
        dd = union(parts, Fq + sd * tt[:, None]); hitn = live & (dd < 0.004)
        occ[hitn] = 1 - tt[hitn] / REACH; live &= ~hitn & (tt < REACH); tt += np.clip(dd, 0.012, 0.2)
    core = np.clip(1 - union(parts, Fq + V(0, 0.02, 0)) / 0.075, 0, 1)
    a = np.zeros(len(Fq), np.uint8); a[(occ > 0.08) | (core > 0.15)] = 58; a[(occ > 0.55) | (core > 0.55)] = 100
    sh = np.zeros((h, w), np.uint8); sh[q] = a
    out[sh > 0, :3] = SHADOW; out[..., 3] = np.where(solid, 255, sh)
    return Image.fromarray(out, "RGBA"), t

def finish(model, anchor, where, ground=0.0, reach=0.50):
    """A finished sprite, cropped, and the pixel of its anchor in it."""
    im, t = shade(model, anchor, where, ground, reach)
    a = np.asarray(im)[..., 3] > 0; ys, xs = np.nonzero(a); b = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    return im.crop(b), (int(t.ax - b[0]), int(t.ay - b[1]))

def sprite(ch, pose):
    """One person in one pose; the anchor is the floor point between the feet."""
    d = build(ch, pose); return finish(d.m, d.anchor, "w" if ch.key[0] == "w" else "k")

def measure(im):
    """The numbers the brief asks for, over the opaque pixels of a sprite."""
    a = np.asarray(im); c = a[a[..., 3] == 255][:, :3].astype(np.float64); v = c.max(1) / 255.0
    dist = np.sqrt(((c[:, None, :] - PALF[None]) ** 2).sum(2)).min(1)
    return dict(dark=float((v < 0.17).mean()), median=float(np.median(v)), top=float(v.max()), palette=float((dist <= 24).mean()))


# ------------------------------------------------------------------ the cast
CAST = []   # customers k0.., then the two workers

def blobs(pts, r): return U(*[ell(p[:3], p[3] if len(p) > 3 else r) for p in pts])
# hand goals: a point in a frame of the body, and the direction the elbow points (in the stance frame)
def chest(x, y, z, pole=(0, -1, -0.4)): return lambda r, B, o: (r.chest.pt(x, y, z), r.S.vec(*pole))
def pelv(x, y, z, pole=(0, 0, -1)): return lambda r, B, o: (r.pel.pt(x, y, z), r.S.vec(*pole))
def stand(x, y, z, pole=(0, 0, -1)): return lambda r, B, o: (r.S.pt(x, y, z), r.S.vec(*pole))
def mouthward(side): return lambda r, B, o: (r.head.pt(-side * 0.02, -B.hr[1] * 0.75, B.hr[2] + 0.085), r.S.vec(-side * 0.7, -1, 0.2))
def slab(z0, z1): return hs((0, 0, z1), (0, 0, 1)) & hs((0, 0, z0), (0, 0, -1))
def above(y): return hs((0, y, 0), (0, -1, 0))
def below(y): return hs((0, y, 0), (0, 1, 0))
def LR(): return (-1, 1)
def swing(a, out=0.03, bend=0.965):
    """An arm swung a degrees forward (+) or back (-) from hanging."""
    return lambda r, B, o: (r.sh[o] + (r.S.z * math.sin(math.radians(a)) - r.S.y * math.cos(math.radians(a))) * (B.ua + B.fa) * bend + r.S.x * o * out, -r.S.z + r.S.x * o * 0.3)
def walk(B, **kw):
    """stap0: mid-stride. stap1: feet passing, close to standing still (it is also how people stand in the queue)."""
    st = 0.122 * B.H
    a = dict(yaw=-90, lean=4, drop=0.015 * B.k, stance=0.13 * B.k, footL=(0, st, 0, 3, -14), footR=(0, -st * 0.95, 0, 3, 36), armL=swing(-22), armR=swing(24))
    b = dict(yaw=-90, lean=2, stance=0.13 * B.k, footL=(0, -0.015, 0, 5, 0), footR=(0, 0.045, 0, 5, 0), armL=swing(4), armR=swing(-5))
    a.update(kw); b.update(kw); return dict(stap0=a, stap1=b)

def person(key, title, B, side=1, walk_=None, **poses):
    """Registers a character. `side`: the way a customer tends to turn (+1 right, -1 left); the hand on that side is
    the one that leans on the counter and holds the cone. Poses not given are filled in from the common ones."""
    def reg(fn):
        P = dict(poses)
        if key[0] == "k":
            near = "armR" if side > 0 else "armL"
            gl = dict(yaw=side * 6, lean=20, pz=0.04, hpitch=-12, stance=0.20, **{near: stand(side * 0.17, 1.085, 0.43, (side * 0.7, -0.6, -0.5))})
            gl.update(P.get("leun", {})); P["leun"] = gl
            ge = dict(yaw=side * 64, hyaw=side * 16, hpitch=8, stance=0.18, cone=side, **{near: chest(side * 0.075, -0.25, 0.25, (side * 0.6, -1, -0.4))})
            ge.update(P.get("eet", {})); P["eet"] = ge
        w = walk(B, **(walk_ or {}))
        for n in ("stap0", "stap1"):
            P.setdefault(n, w[n]); P[n + "-r"] = dict(P[n], yaw=90)
        CAST.append(types.SimpleNamespace(key=key, title=title, B=B, poses=P, dress=fn, side=side)); return fn
    return reg

def build(ch, pose="sta"):
    d = Doll(ch.B, ch.poses[pose], (0, 0, Z_WORKER if ch.key[0] == "w" else Z_CUSTOMER))
    d.pose = pose; d.walking = pose.startswith("stap"); d.side = ch.side; d.right = pose.endswith("-r"); ch.dress(d)
    if d.r.P.get("cone"): fries(d, d.r.P["cone"])
    return d

def ring(d, fr, y, a, b, v, grp=None, tol=0.045, cz=0.0, cx=0.0, arc=(0, 360)):
    """A line around a part of the body: a belt, a hem, a reflective band, a stripe on a hat."""
    ts = np.radians(np.linspace(arc[0], arc[1], max(3, int(abs(arc[1] - arc[0]) / 30) + 1)))
    pts = [fr.pt(cx + a * math.sin(t), y, cz + b * math.cos(t)) for t in ts]
    for p, q in zip(pts, pts[1:]): d.stroke(p, q, v, grp, tol)

def fries(d, o):
    """A paper cone of fries with a dab of mayonnaise, in hand o."""
    F = Fr(d.r.hand[o].pt(0, 0, 0.05), d.r.S.R)
    d.add(at(F, cone((0, -0.14, 0), (0, 0.07, 0), 0.012, 0.068)), "x.cone", "cone")
    d.add(at(F, ell((0, 0.075, 0), (0.064, 0.028, 0.064)) | U(*[cap((x, 0.07, z), (x * 1.35, 0.07 + hh, z * 1.35), 0.012)
          for x, z, hh in ((-0.032, 0.01, 0.075), (0.022, -0.02, 0.09), (0.036, 0.026, 0.06), (-0.01, 0.036, 0.07), (0.0, -0.036, 0.055))])), "x.fries", "fries")
    d.add(at(F, ell((0.012, 0.108, -0.02), (0.03, 0.02, 0.028))), "x.mayo", "mayo")
    for ang in (20, 140, 260):
        t = math.radians(ang); d.stroke(F.pt(0.066 * math.sin(t), 0.06, 0.066 * math.cos(t)), F.pt(0.02 * math.sin(t), -0.10, 0.02 * math.cos(t)), (181, 61, 26), ("cone",), 0.05)


@person("k0", "student", anatomy(H=1.74, head=1.12, sh=0.175, waist=0.130, hip=0.150, bulk=0.90, legs=0.50), side=1,
        sta=dict(yaw=36, lean=7, fhp=0.04, hyaw=50, hpitch=20, sway=-0.03, hiptilt=4, stance=0.17, footR=(0.04, 0.06, 0, 26, 0),
                 armR=chest(0.185, -0.31, 0.20, (0.5, -1, -0.5)), armL="coatpocket"),
        leun=dict(yaw=8, lean=21, hyaw=-6, hpitch=-14, stance=0.21, footR=(0, -0.10, 0, 12, 22), footL=(0, 0.06, 0, 8, 0),
                  armL=lambda r, B, o: (r.head.pt(-B.hr[0] - 0.085, -0.035, 0.0), r.S.vec(-0.9, -1, -0.1))),
        eet=dict(armL="coatpocket", lean=4, fhp=0.03), walk_=dict(hpitch=10, fhp=0.03))
def student(d):
    """Tall and lanky, big headphones, hoodie, eyes on his phone."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("k0.skin")
    d.hair("k0.hair", t=0.018, front=0.56, extra=blobs([(-0.05, b * 0.70, 0.0), (0.05, b * 0.72, 0.01), (0, b * 0.76, -0.035), (-0.04, b * 0.66, -0.075), (0.05, b * 0.66, -0.065), (0, b * 0.70, 0.055)], 0.048))
    band = ell((0, 0, -0.026), (a + 0.030, b + 0.040, 0.2)).shell(0.011) & slab(-0.040, -0.012) & above(0)
    d.add(at(r.head, band), "k0.phones", "phones")
    for o in LR(): d.add(at(r.head, cone((o * (a - 0.005), -0.02, -0.026), (o * (a + 0.040), -0.02, -0.026), 0.047, 0.041)), "k0.phones", "phones")
    d.torso("k0.hoodie", g=0.022, hem=0.16)
    d.add(at(r.chest, ell((0, 0.005, -B.depth - 0.045), (0.125, 0.08, 0.06))), "k0.hoodie", "hood")
    d.hips("k0.jeans", g=0.006)
    for o in LR():
        d.sleeve(o, "k0.hoodie", g=0.020); d.leg(o, "k0.jeans", g=0.004); d.shoe(o, "k0.shoe", "k0.sole", chunky=1.06)
        d.add(cap(lerp(r.el[o], r.wr[o], 0.88), r.wr[o], B.r_wr + 0.024, B.r_wr + 0.022), "k0.rib", f"arm{o}")
    d.add(at(r.pel, loft([(-0.165, B.hip + 0.036, 0.128), (-0.13, B.hip + 0.038, 0.13)], 0.008)), "k0.rib", "torso")
    if d.pose not in ("sta", "eet"): d.hand(-1, "k0.skin")
    d.hand(1, "k0.skin")
    if d.pose == "sta": d.add(at(r.hand[1].sub((0, 0.035, 0.05), Rx(-45)), box((0, 0, 0.03), (0.036, 0.008, 0.07), 0.004)), "k0.phone", "phone")
    d.face(eye=(30, 19, 20), mouth=-1)
    for o in LR():
        d.dot(r.head.pt(o * (a + 0.042), -0.02, -0.026), -2, grp=("phones",))
        d.stroke(r.pel.pt(o * 0.085, 0.0, -0.118), r.pel.pt(o * 0.085, -0.075, -0.112), -1, grp=("legs",))
        d.stroke(r.pel.pt(o * 0.085, -0.075, -0.112), r.pel.pt(o * 0.03, -0.075, -0.112), -1, grp=("legs",))
    d.stroke(r.chest.pt(-0.10, 0.03, -B.depth - 0.10), r.chest.pt(0.10, 0.03, -B.depth - 0.10), 1, grp=("hood",))


OMA_ARM = chest(0.20, -0.30, 0.13, (0.6, -0.5, -1))
@person("k1", "oma", anatomy(H=1.47, head=1.20, sh=0.155, waist=0.155, hip=0.180, belly=0.03, butt=0.02, legs=0.46, depth=0.108), side=-1,
        sta=dict(yaw=-12, lean=11, fhp=0.035, hyaw=-58, hpitch=-12, stance=0.15, armR=OMA_ARM, armL="hang"),
        leun=dict(lean=17, fhp=0.03, hpitch=-16, stance=0.15, armR=OMA_ARM, armL=stand(-0.15, 1.085, 0.40, (-0.7, -0.6, -0.5))),
        eet=dict(lean=8, fhp=0.03, armR=OMA_ARM), walk_=dict(lean=9, fhp=0.035, armR=OMA_ARM, armL=swing(2)))
def oma(d):
    """Small, a little stooped, a fresh perm, long coat; shopping bag with a leek beside her."""
    B, r = d.B, d.r; a, b, c = B.hr; S_ = r.S
    d.head("k1.skin", nose=1.1)
    d.hair("k1.hair", t=0.034, front=0.62, ang=30, nape=-0.52, extra=blobs([(0, b + 0.012, -0.01), (-a - 0.008, b * 0.35, -0.02), (a + 0.008, b * 0.35, -0.02), (0, b * 0.3, -c - 0.012),
            (-0.065, b * 0.80, -0.06), (0.065, b * 0.80, -0.06), (-0.055, b * 0.86, 0.05), (0.055, b * 0.86, 0.05), (-0.085, b * 0.1, -0.09), (0.085, b * 0.1, -0.09)], 0.052))
    d.torso("k1.coat", g=0.024, hem=0.43, flare=0.05, hemb=0.15)
    d.add(at(r.chest, ell((0, 0.048, -0.012), (0.105, 0.034, 0.095))), "k1.collar", "collar")
    for o in LR(): d.sleeve(o, "k1.coat", g=0.022, to=0.97); d.hand(o, "k1.skin"); d.leg(o, "k1.tights", g=0.0); d.shoe(o, "k1.shoe", "k1.sole")
    mid = lerp(r.el[1], r.wr[1], 0.6)                                   # handbag in the crook of her arm
    d.add(at(Fr(mid + V(0, -0.155, 0), S_.R), box((0, 0, 0), (0.045, 0.072, 0.095), 0.02)), "k1.handbag", "handbag")
    d.line(mid, mid + V(0, -0.09, 0) + S_.z * 0.06, "k1.handbag"); d.line(mid, mid + V(0, -0.09, 0) - S_.z * 0.06, "k1.handbag")
    if d.walking: bag = Fr(r.hand[-1].pt(0, 0, 0.06) + V(0, -0.36, 0), S_.R @ Ry(90))      # carried, or standing beside her
    else: bag = Fr(S_.pt(-0.262, 0, 0.03), S_.R @ Ry(12))
    d.add(at(bag, box((0, 0.15, 0), (0.125, 0.15, 0.07), 0.015)), "k1.bag", "bag")
    for z in (-0.045, 0.045): d.add(at(bag.sub((0, 0.30, z), Rx(90)), tor((0, 0, 0), 0.055, 0.011)), "k1.handle", "bag")
    d.add(at(bag, cap((-0.04, 0.24, 0.0), (-0.08, 0.45, -0.02), 0.026, 0.034) | cap((-0.08, 0.45, -0.02), (-0.125, 0.58, -0.03), 0.034, 0.020) | cap((-0.08, 0.45, -0.02), (-0.04, 0.585, 0.0), 0.032, 0.018)), "k1.leek", "leek")
    d.add(at(bag, cap((0.055, 0.25, 0.01), (0.085, 0.50, 0.03), 0.034, 0.030)), "k1.bread", "bread")
    d.face(mouth=-1)
    for y in (0.07, 0.15, 0.23):
        for z in (-0.071, 0.071): d.stroke(bag.pt(-0.12, y, z), bag.pt(0.12, y, z), (234, 209, 167), ("bag",))
        for x in (-0.126, 0.126): d.stroke(bag.pt(x, y, -0.065), bag.pt(x, y, 0.065), (234, 209, 167), ("bag",))
    ring(d, r.pel, -0.40, B.hip + 0.075, 0.155, -1, ("torso",))                    # hem
    d.stroke(r.chest.pt(0, -0.05, -B.depth - 0.03), r.pel.pt(0, -0.40, -0.16), -1, ("torso",))     # back seam


@person("k2", "bouwvakker", anatomy(H=1.71, head=1.13, sh=0.215, waist=0.185, hip=0.185, belly=0.045, bulk=1.28, depth=0.125, neck=0.8), side=1,
        sta=dict(yaw=16, hyaw=60, hpitch=4, stance=0.30, lean=-3, footL=(0, 0, 0, 16, 0), footR=(0, 0, 0, 16, 0), armL="hang", armR="hip"),
        leun=dict(stance=0.28, lean=17), eet=dict(stance=0.27), walk_=dict(armL=swing(3)))
def builder(d):
    """Stocky, straight from the site: hard hat, hi-vis vest over a hoodie, hammer on the belt, lunch cooler in his fist."""
    B, r = d.B, d.r; a, b, c = B.hr; Lc = B.spine - 0.10 * B.k
    d.head("k2.skin", jaw=1.08, nose=1.1)
    d.hair("k2.hair", t=0.010, front=0.5)
    hat = (ell((0, b * 0.26, 0.0), (a + 0.030, b * 0.90, c + 0.034)) & above(b * 0.26)) | ell((0, b * 0.27, 0.030), (a + 0.034, 0.015, c + 0.052)) | cap((0, b * 1.15, -0.07), (0, b * 1.15, 0.07), 0.016)
    d.add(at(r.head, hat), "k2.helm", "hat")
    d.torso("k2.hoodie", g=0.020, hem=0.14)
    d.torso("k2.vest", g=0.034, hem=0.10, grp="vest")
    d.hips("k2.cargo", g=0.014)
    for o in LR():
        d.sleeve(o, "k2.hoodie", g=0.022); d.hand(o, "k2.skin"); d.leg(o, "k2.cargo", g=0.016, flare=0.006); d.shoe(o, "k2.boot", "k2.sole", hi=0.09, chunky=1.3)
        mid = lerp(r.hipj[o], r.knee[o], 0.62)
        d.add(at(Fr(mid, r.S.R), box((o * 0.085, 0, 0), (0.022, 0.065, 0.055), 0.012)), "k2.cargo", f"pocket{o}")
    d.add(at(r.pel, box((0.19, -0.03, -0.05), (0.045, 0.07, 0.065), 0.015)), "k2.pouch", "pouch")
    d.add(at(r.pel, cap((0.24, -0.03, -0.02), (0.25, -0.31, -0.035), 0.014) | box((0.24, 0.0, -0.02), (0.02, 0.022, 0.05), 0.006)), "k2.hammer", "hammer")
    K = Fr(r.hand[-1].pt(0, 0, 0.06) + V(0, -0.15, 0), r.S.R)
    d.add(at(K, box((0, 0, 0), (0.075, 0.085, 0.115), 0.02)), "k2.cooler", "cooler"); d.add(at(K, box((0, 0.085, 0), (0.08, 0.02, 0.12), 0.012)), "k2.coolerlid", "cooler")
    for z in (-0.08, 0.08): d.line(K.pt(0, 0.10, z), K.pt(0, 0.15, 0), "k2.coolerlid")
    d.face(mouth=-1)
    refl = (222, 227, 218)                                                  # reflective bands
    for y in (-Lc * 0.50, -Lc * 0.86): ring(d, r.chest, y, B.sh + 0.03, B.depth + 0.045, refl, ("vest",), 0.05)
    for o in LR():
        d.stroke(r.chest.pt(o * 0.10, 0.02, -B.depth - 0.035), r.chest.pt(o * 0.10, -Lc * 0.50, -B.depth - 0.045), refl, ("vest",), 0.05)
        d.stroke(r.chest.pt(o * 0.10, 0.02, B.depth + 0.03), r.chest.pt(o * 0.10, -Lc * 0.50, B.depth + 0.05), refl, ("vest",), 0.05)


@person("k3", "wielrenster", anatomy(H=1.70, head=1.12, sh=0.165, waist=0.125, hip=0.155, bulk=0.88, legs=0.515, bust=0.015), side=-1,
        sta=dict(yaw=-24, hyaw=-56, hpitch=-4, sway=0.035, hiptilt=-5, stance=0.17, footL=(0.03, -0.09, 0, 6, 42), armL="hip", armR=chest(0.235, -0.27, 0.10, (0.6, -1, -0.6))),
        leun=dict(armR=chest(0.235, -0.27, 0.10, (0.6, -1, -0.6)), footR=(0, -0.08, 0, 8, 30)), eet=dict(armR="hip"))
def cyclist(d):
    """Lean, still in her kit: helmet, short ponytail, jersey, bare calves, bidon in hand."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("k3.skin")
    d.hair("k3.hair", t=0.010, front=0.5)
    helm = SU(ell((0, b * 0.30, -0.012), (a + 0.026, b * 0.88, c + 0.034)), cap((0, b * 0.55, -c * 0.5), (0, b * 0.50, -c - 0.060), 0.06, 0.030), 0.04) & hs((0, b * 0.10, 0), (0, -1, 0.30))
    d.add(at(r.head, helm), "k3.helm", "hat")
    d.add(at(r.head, cap((0, -b * 0.30, -c - 0.005), (0, -b * 1.25, -c - 0.03), 0.036, 0.016)), "k3.hair", "hair")
    d.torso("k3.jersey", g=0.006, hem=0.10)
    d.hips("k3.shorts", g=0.006)
    for o in LR():
        d.upperarm(o, "k3.skin"); d.forearm(o, "k3.skin"); d.sleeve(o, "k3.jersey", g=0.006, to=0.36); d.hand(o, "k3.skin")
        d.leg(o, "k3.skin", g=0.0); d.leg(o, "k3.shorts", g=0.006, to=0.40)
        d.add(cap(lerp(r.knee[o], r.ank[o], 0.80), r.ank[o], B.r_an + 0.010, B.r_an + 0.008), "k3.sock", f"leg{o}")
        d.shoe(o, "k3.shoe", "k3.sole", chunky=0.95)
    if d.pose in ("sta", "leun"):
        hc = r.hand[1].pt(0, 0, 0.055)
        d.add(cap(hc + V(0, 0.10, 0), hc + V(0, -0.06, 0), 0.036) | cap(hc + V(0, 0.11, 0), hc + V(0, 0.16, 0), 0.02, 0.014), "k3.bidon", "bidon")
    d.face(mouth=-1)
    for x in (-0.05, 0.0, 0.05):                                            # vents in the helmet
        d.stroke(r.head.pt(x, b * 1.12 - abs(x) * 0.5, 0.07), r.head.pt(x, b * 1.10 - abs(x) * 0.5, -0.08), (64, 55, 44), ("hat",), 0.06)
    ring(d, r.chest, -0.02, B.sh * 0.5, 0.075, (240, 229, 204), ("torso",), 0.04)   # collar
    for o in LR(): d.stroke(r.chest.pt(o * (B.sh - 0.035), -0.10, -B.depth - 0.012), r.pel.pt(o * (B.hip - 0.02), -0.05, -0.115), (240, 229, 204), ("torso",))


@person("k4", "kind", anatomy(H=1.13, head=1.20, sh=0.120, waist=0.110, hip=0.122, belly=0.02, bulk=0.95, legs=0.45, depth=0.085), side=-1,
        sta=dict(yaw=-10, lean=6, hyaw=-50, hpitch=-20, stance=0.13, drop=-0.05, footL=(0, 0, 0, 10, 38), footR=(0, 0, 0, 10, 38),
                 armL=stand(-0.26, 1.06, 0.20, (-0.6, -1, -0.3)), armR=chest(0.085, -0.10, 0.10, (0.6, -1, -0.5))),
        leun=dict(yaw=-4, lean=14, pz=0.10, hpitch=-26, stance=0.13, drop=-0.05, footL=(0, 0, 0, 10, 38), footR=(0, 0, 0, 10, 38),
                  armL=stand(-0.10, 1.075, 0.42, (-0.8, -0.8, -0.3)), armR=stand(0.10, 1.075, 0.42, (0.8, -0.8, -0.3))),
        eet=dict(hpitch=14, armL=chest(-0.06, -0.14, 0.17, (-0.6, -1, -0.4)), armR=chest(0.02, -0.12, 0.17, (0.7, -1, -0.3))))
def child(d):
    """Seven years old, on tiptoe, pointing at what she wants; two hair puffs and a school bag as big as her back."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("k4.skin", nose=0.7, cheeks=0.006)
    d.hair("k4.hair", t=0.012, front=0.55, extra=blobs([(-a * 0.80, b * 0.70, -c * 0.30), (a * 0.80, b * 0.70, -c * 0.30)], 0.072))
    d.torso("k4.jacket", g=0.026, hem=0.085, flare=0.035)
    d.add(at(r.chest, box((0, -0.125, -B.depth - 0.085), (0.125, 0.145, 0.068), 0.04)), "k4.bag", "bag")
    d.add(at(r.chest, box((0, -0.04, -B.depth - 0.10), (0.128, 0.06, 0.07), 0.035)), "k4.bagflap", "bag")
    d.add(at(r.chest, ell((0.135, -0.25, -B.depth - 0.11), 0.024)), "k4.charm", "charm")
    d.hips("k4.leggings", g=0.004)
    for o in LR(): d.sleeve(o, "k4.jacket", g=0.024); d.hand(o, "k4.skin"); d.leg(o, "k4.leggings", g=0.003); d.shoe(o, "k4.boot", "k4.sole", hi=0.07, chunky=1.2)
    d.face(eye=(30, 19, 20), mouth=-1)
    for o in LR(): d.dot(r.head.pt(o * a * 0.62, b * 0.52, -c * 0.20), (181, 61, 26), tol=0.06)                 # hair bobbles
    d.dot(r.chest.pt(0, -0.20, -B.depth - 0.155), (239, 194, 94), ((0, 0), (1, 0), (0, 1), (1, 1)), ("bag",), 0.04)   # reflector


OFF_ARM = chest(0.165, 0.03, 0.075, (0.5, -1, 0.15))
@person("k5", "bediende", anatomy(H=1.74, head=1.13, sh=0.185, waist=0.170, hip=0.172, belly=0.055, depth=0.110), side=-1,
        sta=dict(yaw=-24, hyaw=-52, hpitch=2, sway=0.035, hiptilt=-4, stance=0.20, footL=(0.02, 0.05, 0, 22, 0), armR=OFF_ARM, armL="pocket"),
        leun=dict(armR=OFF_ARM), eet=dict(armR=OFF_ARM), walk_=dict(armR=OFF_ARM, armL=swing(3)))
def office(d):
    """End of the week: sleeves rolled, tie loosened, jacket hooked on a finger over his shoulder, laptop bag at his feet."""
    B, r = d.B, d.r; a, b, c = B.hr; S_ = r.S
    d.head("k5.skin", nose=1.1)
    d.hair("k5.hair", t=0.012, front=0.5)
    d.m.parts[-1].sdf = d.m.parts[-1].sdf & at(r.head, below(b * 0.60) | hs((0, 0, -c * 0.55), (0, 0, 1)))   # thinning on top
    d.torso("k5.shirt", g=0.008, hem=0.04)
    d.hips("k5.trousers", g=0.013)
    for o in LR(): d.forearm(o, "k5.skin"); d.sleeve(o, "k5.shirt", g=0.010, to=0.60); d.hand(o, "k5.skin"); d.leg(o, "k5.trousers", g=0.012); d.shoe(o, "k5.shoe", "k5.sole")
    J = r.chest.sub((0.125, -0.25, -B.depth - 0.05), Rz(-5))                # the jacket down his back
    d.add(at(J, loft([(-0.31, 0.125, 0.034), (-0.12, 0.118, 0.040), (0.10, 0.092, 0.046), (0.24, 0.045, 0.036)], 0.022)), "k5.jacket", "jacket")
    d.add(at(J, cap((0.085, 0.10, -0.035), (0.135, -0.33, -0.02), 0.036, 0.03)), "k5.jacket", "jsleeve")
    d.add(at(r.chest, cap((0, -0.03, B.depth - 0.002), (0.012, -0.27, B.depth + B.belly * 0.5 + 0.012), 0.020, 0.024)), "k5.tie", "tie")   # loosened, hanging
    if d.walking: Lb = Fr(r.hand[-1].pt(0, 0, 0.06) + V(0, -0.30, 0), S_.R @ Ry(90))    # laptop bag: carried, or leaning on his leg
    else: Lb = Fr(S_.pt(0.27, 0, 0.06), S_.R @ Ry(14) @ Rz(-6))
    d.add(at(Lb, box((0, 0.125, 0), (0.135, 0.115, 0.045), 0.02)), "k5.bag", "bag")
    d.add(at(Lb.sub((0, 0.24, 0), Rx(90)), tor((0, 0, 0), 0.05, 0.011)), "k5.bag", "bag")
    d.face(mouth=-1)
    for o in LR(): d.stroke(r.head.pt(o * a * 0.50, b * 0.05, c * 0.86), r.head.pt(o * a * 0.98, b * 0.02, 0.0), (64, 55, 44), ("head",), 0.025)   # glasses
    ring(d, r.pel, 0.085, B.waist + 0.016, B.depth + B.belly * 0.8 + 0.012, (44, 22, 22), ("legs",), cz=B.belly * 0.5)    # belt
    d.stroke(Lb.pt(-0.13, 0.17, -0.047), Lb.pt(0.13, 0.17, -0.047), 1, ("bag",)); d.stroke(Lb.pt(-0.13, 0.17, 0.047), Lb.pt(0.13, 0.17, 0.047), 1, ("bag",))


@person("k6", "supporter", anatomy(H=1.66, head=1.20, sh=0.195, waist=0.200, hip=0.190, belly=0.085, bulk=1.15, depth=0.120, neck=0.7), side=1,
        sta=dict(yaw=20, hyaw=58, lean=-5, stance=0.27, footL=(0, 0, 0, 18, 0), footR=(0, 0, 0, 18, 0),
                 armL=pelv(-0.20, 0.07, 0.10, (-0.45, 0, -1)), armR=pelv(0.20, 0.07, 0.10, (0.45, 0, -1))),
        leun=dict(armL=pelv(-0.20, 0.07, 0.10, (-0.45, 0, -1)), stance=0.25), eet=dict(armL=pelv(-0.20, 0.07, 0.10, (-0.45, 0, -1)), lean=-3, stance=0.24))
def fan(d):
    """Round and cheerful, on his way to the match: bobble hat and a long striped scarf, hands deep in his pockets."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("k6.skin", jaw=1.1, cheeks=0.008)
    d.hair("k6.hair", t=0.010, front=0.5)
    hat = (ell((0, 0.02, -0.005), (a + 0.022, b * 0.86 + 0.02, c + 0.024)) & above(-0.005)) | ell((0, 0.014, -0.004), (a + 0.034, 0.034, c + 0.036))
    d.add(at(r.head, hat), "k6.hat", "hat"); d.add(at(r.head, ell((0, b * 0.88 + 0.075, -0.012), 0.062)), "k6.pom", "pom")
    d.torso("k6.jacket", g=0.030, hem=0.09)
    d.add(at(r.chest, ell((0, 0.058, -0.005), (0.125, 0.048, 0.118))), "k6.scarf", "scarf")
    A_ = r.chest.sub((-0.15, 0.03, -B.depth - 0.03), Rz(13)); B_ = r.chest.sub((0.06, 0.02, -B.depth - 0.05), Rz(-5))
    d.add(at(A_, box((0, -0.25, 0), (0.046, 0.26, 0.016), 0.008)), "k6.scarf", "scarfA")
    d.add(at(B_, box((0, -0.15, 0), (0.046, 0.16, 0.016), 0.008)), "k6.scarf", "scarfB")
    d.hips("k6.jeans", g=0.012)
    for o in LR(): d.sleeve(o, "k6.jacket", g=0.028); d.leg(o, "k6.jeans", g=0.010); d.shoe(o, "k6.shoe", "k6.sole", chunky=1.1)
    if d.pose != "sta":
        for o in LR(): d.hand(o, "k6.skin")
    d.face(mouth=-1, blush=(219, 142, 94))
    cream = (240, 229, 204)
    for F_, n in ((A_, 6), (B_, 4)):                                        # bars on the scarf
        for i in range(n):
            y = -0.05 - i * 0.085
            for z in (-0.018, 0.018): d.stroke(F_.pt(-0.046, y, z), F_.pt(0.046, y, z), cream, ("scarfA", "scarfB"), 0.03)
    ring(d, r.head, b * 0.30, a + 0.03, c + 0.03, cream, ("hat",), 0.04, cz=-0.005)
    ring(d, r.pel, -0.075, B.hip + 0.045, 0.135, -1, ("torso",))


def umbrella_arm(r, B, o): return r.S.pt(0.275, 0.84, 0.06), r.S.vec(0.6, -0.3, -1)
@person("k7", "regenjas", anatomy(H=1.63, head=1.15, sh=0.165, waist=0.140, hip=0.170), side=-1,
        sta=dict(yaw=-18, hyaw=-60, hpitch=10, lean=6, stance=0.16, armR=umbrella_arm, armL="coatpocket"),
        leun=dict(armR=umbrella_arm), eet=dict(armR=lambda r, B, o: (r.S.pt(0.275, 0.84, 0.0), r.S.vec(0.6, -0.3, -1)), hpitch=10),
        walk_=dict(armR=swing(14), armL=swing(-14), hpitch=8))
def raincoat(d):
    """Came in out of the rain: pointed hood still up, wide raincoat, wellies, dripping umbrella."""
    B, r = d.B, d.r; a, b, c = B.hr; S_ = r.S
    d.head("k7.skin")
    d.hair("k7.hair", t=0.012, front=0.40, ang=30)
    hood = SU(ell((0, 0.012, -0.022), (a + 0.036, b + 0.032, c + 0.04)), cap((0, b * 0.9, -0.03), (0, b + 0.085, -0.115), 0.07, 0.014), 0.05) & hs((0, 0, c * 0.50), (0, -0.25, 1))
    d.add(at(r.head, hood), "k7.coat", "hood")
    d.add(at(r.chest, loft([(-0.06, B.sh + 0.03, B.depth + 0.03), (0.04, 0.14, 0.125), (0.13, 0.115, 0.115)], 0.03)), "k7.coat", "hood")
    d.torso("k7.coat", g=0.030, hem=0.37, flare=0.075, hemb=0.17, sho=0.008)
    for o in LR(): d.sleeve(o, "k7.coat", g=0.028, wide=0.006); d.leg(o, "k7.tights", g=0.004); d.shoe(o, "k7.welly", "k7.sole", hi=0.22, chunky=1.15)
    d.hand(1, "k7.skin")
    if d.pose != "sta": d.hand(-1, "k7.skin")
    top = r.hand[1].pt(0, 0, 0.05); tip = top + V(0, -0.74, 0) + S_.z * 0.16 if d.walking else S_.pt(0.295, 0.0, 0.10 if d.pose != "eet" else 0.04)
    d.add(cone(top + (tip - top) * 0.08, lerp(top, tip, 0.88), 0.046, 0.020) | cap(lerp(top, tip, 0.88), tip, 0.012, 0.009) | cap(top, top + V(0, 0.07, 0), 0.013) | cap(top + V(0, 0.07, 0), top + V(0, 0.075, 0) - S_.z * 0.05, 0.013), "k7.umbrella", "umbrella")
    d.face(mouth=-1)
    ring(d, r.pel, -0.345, B.hip + 0.105, 0.172, -1, ("torso",))
    d.stroke(r.chest.pt(0, -0.07, -B.depth - 0.035), r.pel.pt(0, -0.34, -0.175), -1, ("torso",))
    for o in LR(): d.stroke(r.pel.pt(o * 0.13, 0.02, -0.14), r.pel.pt(o * 0.16, -0.06, -0.15), -1, ("torso",))           # pocket flaps
    ring(d, r.foot[-1], 0.225, 0.062, 0.062, 1, ("foot-1",), 0.05); ring(d, r.foot[1], 0.225, 0.062, 0.062, 1, ("foot1",), 0.05)


PAPA_ARM = pelv(-0.14, 0.03, -0.20, (-1, 0, -0.5))
@person("k8", "papa", anatomy(H=1.74, head=1.12, sh=0.190, waist=0.155, hip=0.165), side=1,
        sta=dict(yaw=28, hyaw=50, hpitch=6, sway=-0.035, hiptilt=5, stance=0.19, footR=(0.03, 0.03, 0, 20, 0), armL=PAPA_ARM, armR="hang"),
        leun=dict(armL=PAPA_ARM, lean=14), eet=dict(armL=PAPA_ARM), walk_=dict(armL=PAPA_ARM, armR=swing(4)))
def papa(d):
    """A father rocking on his feet so the baby on his back stays asleep; a plush rabbit dangles from his hand."""
    B, r = d.B, d.r; a, b, c = B.hr; zb = -B.depth - 0.085
    d.head("k8.skin")
    d.hair("k8.hair", t=0.014, front=0.52, extra=ell((0, b * 0.62, -c * 0.80), 0.05))
    d.add(at(r.head, ell((0, -b * 0.62, c * 0.34), (a * 0.80, b * 0.42, c * 0.62))), "k8.hair", "beard")
    d.torso("k8.sweater", g=0.018, hem=0.12)
    d.add(at(r.chest, box((0, -0.175, zb), (0.135, 0.165, 0.065), 0.045)), "k8.carrier", "carrier")
    d.add(at(r.pel, loft([(0.045, B.waist + 0.03, B.depth + 0.03), (0.105, B.waist + 0.03, B.depth + 0.03)], 0.012)), "k8.carrier", "belt")
    for o in LR():
        d.add(at(r.chest, cap((o * 0.105, 0.03, -0.06), (o * 0.115, -0.04, 0.09), 0.024) | cap((o * 0.105, 0.03, -0.06), (o * 0.10, -0.05, zb + 0.03), 0.024)), "k8.carrier", "strap")
        d.add(at(r.chest, cap((o * 0.125, -0.28, zb), (o * 0.225, -0.355, zb + 0.02), 0.036, 0.030)), "k8.baby", f"babyleg{o}")
        d.add(at(r.chest, ell((o * 0.235, -0.375, zb + 0.03), (0.036, 0.032, 0.048))), "k8.bootie", f"babyleg{o}")
        d.add(at(r.chest, cap((o * 0.095, -0.035, zb + 0.01), (o * 0.13, 0.025, zb + 0.07), 0.026, 0.024)), "k8.baby", f"babyarm{o}")
    bh = r.chest.sub((-0.125, 0.075, zb - 0.02), Ry(-122) @ Rz(-14))        # the baby's head, lolling over dad's shoulder
    d.add(at(bh, ell((0, 0, 0), (0.080, 0.084, 0.084)) | ell((0, -0.02, 0.076), (0.012, 0.014, 0.014))), "k8.babyskin", "babyhead")
    d.add(at(bh, (ell((0, 0.012, -0.006), (0.088, 0.088, 0.092)) & hs((0, 0.01, 0.045), (0, -0.55, 1))) | blobs([(-0.064, 0.080, -0.01), (0.064, 0.080, -0.01)], 0.030)), "k8.babyhat", "babyhat")
    d.hips("k8.jeans", g=0.010)
    for o in LR(): d.sleeve(o, "k8.sweater", g=0.016); d.hand(o, "k8.skin"); d.leg(o, "k8.jeans", g=0.009); d.shoe(o, "k8.shoe", "k8.sole", chunky=1.08)
    if d.pose in ("sta",) or d.walking:
        R_ = Fr(r.hand[1].pt(0, 0, 0.06), r.S.R)                            # the rabbit, held by one ear
        d.add(at(R_, cap((0, 0, 0), (0.005, -0.075, 0), 0.013, 0.015) | cap((0.01, -0.085, 0), (0.05, -0.05, 0.0), 0.014, 0.011) | ell((0.005, -0.105, 0), 0.036) | ell((0.005, -0.18, 0), (0.036, 0.052, 0.032))
                 | cap((-0.02, -0.21, 0), (-0.035, -0.265, 0), 0.016, 0.014) | cap((0.03, -0.21, 0), (0.045, -0.262, 0), 0.016, 0.014) | cap((-0.03, -0.155, 0), (-0.05, -0.185, 0), 0.013) | cap((0.04, -0.155, 0), (0.06, -0.185, 0), 0.013)), "k8.rabbit", "rabbit")
    d.face(mouth=-1)
    for o in LR(): d.dot(bh.pt(o * 0.034, -0.005, 0.07), (90, 60, 51), ((0, 0), (1, 0)), ("babyhead",), 0.03)     # the baby's closed eyes
    for y in (-0.10, -0.25): d.stroke(r.chest.pt(-0.13, y, zb - 0.068), r.chest.pt(0.13, y, zb - 0.068), 1, ("carrier",), 0.04)


@person("k9", "verpleegster", anatomy(H=1.64, head=1.17, sh=0.170, waist=0.150, hip=0.180, butt=0.02, bust=0.02), side=-1,
        sta=dict(yaw=-12, hyaw=-50, hroll=-8, hpitch=10, sway=-0.035, hiptilt=5, stance=0.18, footR=(0.03, 0.02, 0, 22, 0), armR="neck", armL="hang"))
def nurse(d):
    """After a long shift: scrubs and clogs, hair in a bun, tote on her shoulder, a hand rubbing her neck."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("k9.skin")
    d.hair("k9.hair", t=0.010, front=0.52, extra=ell((0, b * 0.72, -c * 0.72), 0.062))
    d.torso("k9.scrubs", g=0.014, hem=0.17, flare=0.012)
    d.hips("k9.scrubs", g=0.016)
    for o in LR():
        d.sleeve(o, "k9.under", g=0.005); d.sleeve(o, "k9.scrubs", g=0.016, to=0.40, wide=0.004); d.hand(o, "k9.skin")
        d.leg(o, "k9.scrubs", g=0.018, flare=0.010); d.shoe(o, "k9.clog", "k9.sole", chunky=1.12)
    T = r.chest.sub((-B.sh - 0.02, -0.43, -0.06), Ry(-66))                # tote hanging behind her left arm
    d.add(at(T, box((0, 0, 0), (0.14, 0.15, 0.04), 0.02)), "k9.tote", "tote")
    for x in (-0.07, 0.07): d.line(T.pt(x, 0.15, 0), r.chest.pt(-B.sh + 0.03, 0.02, -0.01 + x * 0.3), "k9.strap")
    d.face(eye=(30, 19, 20), mouth=-1)
    ring(d, r.pel, -0.155, B.hip + 0.036, 0.125, -1, ("torso",))
    for o in LR(): d.stroke(r.pel.pt(o * 0.05, -0.05, -0.132), r.pel.pt(o * 0.14, -0.05, -0.125), -1, ("torso",))        # hip pockets
    d.stroke(T.pt(-0.13, 0.05, -0.042), T.pt(0.13, 0.05, -0.042), -1, ("tote",)); d.stroke(T.pt(-0.13, 0.05, 0.042), T.pt(0.13, 0.05, 0.042), -1, ("tote",))


PHONE_ARM = chest(0.19, -0.30, 0.20, (0.5, -1, -0.5))
@person("k10", "koerier", anatomy(H=1.66, head=1.15, sh=0.170, waist=0.135, hip=0.150, bulk=0.92), side=1,
        sta=dict(yaw=26, hyaw=32, hpitch=20, lean=4, sway=0.03, hiptilt=-4, stance=0.18, footL=(0.03, 0.04, 0, 20, 0), armR=PHONE_ARM, armL="hang"),
        leun=dict(lean=16), eet=dict(yaw=58))
def courier(d):
    """A food courier between two runs: big square thermal bag on his back, cap turned backwards, checking the next order."""
    B, r = d.B, d.r; a, b, c = B.hr; zb = -B.depth - 0.02
    d.head("k10.skin")
    d.hair("k10.hair", t=0.010, front=0.5)
    capd = (ell((0, 0.02, -0.005), (a + 0.018, b * 0.92 + 0.016, c + 0.02)) & above(b * 0.14)) | ell((0, b * 0.20, -c - 0.05), (a * 0.78, 0.014, 0.075))
    d.add(at(r.head, capd), "k10.cap", "hat")
    d.torso("k10.jacket", g=0.020, hem=0.11)
    d.add(at(r.chest, box((0, -0.165, zb - 0.165), (0.18, 0.195, 0.165), 0.022)), "k10.cube", "cube")
    d.add(at(r.chest, box((0, 0.028, zb - 0.165), (0.185, 0.024, 0.17), 0.014)), "k10.lid", "cube")
    for o in LR(): d.add(at(r.chest, cap((o * 0.11, 0.035, -0.04), (o * 0.12, -0.05, 0.09), 0.022)), "k10.strap", "strap")
    d.hips("k10.joggers", g=0.014)
    for o in LR(): d.sleeve(o, "k10.jacket", g=0.018); d.hand(o, "k10.skin"); d.leg(o, "k10.joggers", g=0.016, flare=-0.006); d.shoe(o, "k10.shoe", "k10.sole", chunky=1.1)
    if d.pose == "sta": d.add(at(r.hand[1].sub((0, 0.035, 0.05), Rx(-45)), box((0, 0, 0.03), (0.036, 0.008, 0.07), 0.004)), "k10.phone", "phone")
    d.face(mouth=-1)
    zc = zb - 0.165; refl = (222, 227, 218)                                 # a reflective strip around the bag, a seam down its faces
    for x0, z0, x1, z1 in ((-0.182, zc - 0.167, 0.182, zc - 0.167), (-0.182, zc - 0.167, -0.182, zc + 0.16), (0.182, zc - 0.167, 0.182, zc + 0.16)):
        d.stroke(r.chest.pt(x0, -0.30, z0), r.chest.pt(x1, -0.30, z1), refl, ("cube",), 0.035)
        d.stroke(r.chest.pt((x0 + x1) / 2, 0.0, (z0 + z1) / 2), r.chest.pt((x0 + x1) / 2, -0.28, (z0 + z1) / 2), -1, ("cube",), 0.035)
    for o in LR(): ring(d, Fr(r.ank[o], r.S.R), 0.03, B.r_an + 0.012, B.r_an + 0.012, -1, (f"leg{o}",), 0.04)


def dog(d, x, leash_from):
    """Opa's small dog: sitting and looking up at him, or trotting along."""
    S_ = d.r.S; white = "k11.dog"; sg = -1.0 if x > 0 else 1.0                # which way its head turns: towards its master
    if not d.walking:
        D = Fr(S_.pt(x, 0, -0.02), S_.R)
        d.add(at(D, SU(ell((0, 0.105, -0.015), (0.085, 0.10, 0.10)), ell((0, 0.20, 0.045), (0.068, 0.09, 0.065)), 0.03) | ell((-0.07, 0.03, 0.04), (0.03, 0.03, 0.05)) | ell((0.07, 0.03, 0.04), (0.03, 0.03, 0.05))
                 | cap((-0.028, 0.16, 0.085), (-0.028, 0.012, 0.095), 0.02, 0.018) | cap((0.028, 0.16, 0.085), (0.028, 0.012, 0.095), 0.02, 0.018) | cap((0, 0.05, -0.10), (-0.055 * sg, 0.135, -0.165), 0.02, 0.011)), white, "dog")
        hd = (0.012 * sg, 0.318, 0.055); sn = (0.105 * sg, 0.34, 0.065)
        d.add(at(D, ell(hd, (0.058, 0.055, 0.06)) | cap((0.03 * sg, 0.315, 0.06), sn, 0.032, 0.021) | ell((-0.022, 0.372, 0.04), (0.017, 0.034, 0.014)) | ell((0.034, 0.376, 0.04), (0.017, 0.034, 0.014))), white, "doghead")
        neck = D.pt(0.0, 0.262, 0.03); eye = D.pt(0.045 * sg, 0.335, 0.02)
    else:
        f = 1 if d.pose.startswith("stap0") else -1
        D = Fr(S_.pt(x, 0, 0.10), S_.R)
        legs = U(*[cap((sx * 0.035, 0.15, z), (sx * 0.035, 0.012, z + dz * f), 0.02, 0.016) for sx, z, dz in ((-1, 0.09, 0.05), (1, 0.09, -0.05), (-1, -0.10, -0.05), (1, -0.10, 0.05))])
        d.add(at(D, ell((0, 0.185, 0), (0.062, 0.068, 0.155)) | legs | cap((0, 0.21, -0.15), (0, 0.31, -0.20), 0.02, 0.011)), white, "dog")
        hd = (0, 0.275, 0.17); sn = (0, 0.265, 0.26)
        d.add(at(D, ell(hd, (0.055, 0.055, 0.06)) | cap((0, 0.268, 0.19), sn, 0.032, 0.021) | ell((-0.03, 0.33, 0.15), (0.015, 0.032, 0.016)) | ell((0.03, 0.33, 0.15), (0.015, 0.032, 0.016))), white, "doghead")
        neck = D.pt(0, 0.25, 0.11); eye = D.pt(0.05 * (1 if d.right else -1), 0.29, 0.19)
    d.dot(D.pt(*sn), (49, 36, 36), grp=("doghead",), tol=0.05); d.dot(eye, (49, 36, 36), grp=("doghead",), tol=0.05)
    d.dot(D.pt(hd[0] - 0.02 * sg, hd[1] + 0.02, hd[2] - 0.05), (146, 77, 33), ((0, 0), (1, 0), (0, 1)), ("doghead", "dog"), 0.06)   # a brown patch
    d.line(leash_from, neck, "k11.leash")

def cane_arm(r, B, o): return r.S.pt(0.25, 0.80, 0.07), r.S.vec(0.7, -0.2, -1)
@person("k11", "opa", anatomy(H=1.64, head=1.18, sh=0.175, waist=0.190, hip=0.180, belly=0.075, bulk=1.05, legs=0.47, depth=0.115), side=-1,
        sta=dict(yaw=-22, hyaw=-48, hpitch=14, lean=9, fhp=0.035, stance=0.19, armR=cane_arm, armL="hang"),
        leun=dict(lean=17, fhp=0.03, armR=cane_arm), eet=dict(lean=8, fhp=0.03, armR=cane_arm),
        walk_=dict(lean=9, fhp=0.035, armR=lambda r, B, o: (r.S.pt(0.24, 0.80, 0.16), r.S.vec(0.7, -0.2, -1)), armL=swing(3)))
def opa(d):
    """Flat cap, braces over a round belly, a walking stick, and a small dog that knows exactly where it is."""
    B, r = d.B, d.r; a, b, c = B.hr; S_ = r.S
    d.head("k11.skin", nose=1.25, jaw=1.05)
    d.hair("k11.hair", t=0.010, front=0.5)
    cp = Fr((0, b * 0.60, 0.012), Rx(9))
    d.add(at(r.head, at(cp, ell((0, 0, 0), (a + 0.026, 0.05, c + 0.036)) | ell((0, -0.016, c + 0.035), (a * 0.80, 0.012, 0.052)))), "k11.cap", "hat")
    d.torso("k11.shirt", g=0.010, hem=0.04)
    d.add(at(r.pel, loft([(-0.125, B.hip * 0.86 + 0.018, 0.11), (-0.02, B.hip + 0.03, 0.125), (0.10, B.waist + 0.02, B.depth * 0.92 + B.belly * 0.8 + 0.02, 0, B.belly * 0.5),
                          (0.215, B.waist + 0.016, B.depth + B.belly * 0.62 + 0.016, 0, B.belly * 0.42)], 0.02)), "k11.trousers", "legs")
    for o in LR(): d.sleeve(o, "k11.shirt", g=0.012); d.hand(o, "k11.skin"); d.leg(o, "k11.trousers", g=0.018, flare=0.004); d.shoe(o, "k11.shoe", "k11.sole", chunky=1.05)
    top = r.hand[1].pt(0, 0, 0.05); tip = S_.pt(0.255, 0.0, 0.25) if d.walking else S_.pt(0.265, 0.0, 0.09)
    d.add(cap(top, tip, 0.013, 0.011) | cap(top - S_.z * 0.05, top + S_.z * 0.045, 0.015), "k11.cane", "cane")
    near = 1 if d.right else -1                                             # the dog walks on the side we can see
    dog(d, (0.30 * near) if d.walking else -0.30, r.hand[near if d.walking else -1].pt(0, 0, 0.06) if d.pose != "eet" else top)
    d.face(mouth=-1)
    Lc = B.spine - 0.10 * B.k; red = (135, 20, 11)                          # braces
    for o in LR():
        d.stroke(r.chest.pt(o * 0.085, 0.03, -B.depth * 0.4), r.chest.pt(o * 0.03, -Lc * 0.62, -B.depth - 0.012), red, ("torso",), 0.04)
        d.stroke(r.chest.pt(o * 0.085, 0.03, B.depth * 0.3), r.chest.pt(o * 0.09, -Lc * 0.75, B.depth + B.belly * 0.4 + 0.012), red, ("torso",), 0.04)
    d.stroke(r.chest.pt(0.0, -Lc * 0.62, -B.depth - 0.012), r.chest.pt(0.0, -Lc * 0.95, -B.depth - 0.014), red, ("torso",), 0.04)
    ring(d, r.head, b * 0.60, a + 0.02, c + 0.03, -1, ("hat",), 0.05, cz=0.012)


@person("k12", "muzikante", anatomy(H=1.70, head=1.13, sh=0.165, waist=0.125, hip=0.152, bulk=0.88, legs=0.51, bust=0.015), side=-1,
        sta=dict(yaw=-28, hyaw=-44, hpitch=4, sway=0.03, hiptilt=-5, stance=0.17, footL=(0.04, 0.05, 0, 24, 0),
                 armR=chest(0.135, -0.11, 0.115, (0.6, -1, -0.5)), armL="pocket"),
        leun=dict(armR=chest(0.135, -0.11, 0.115, (0.6, -1, -0.5)), lean=15), eet=dict(armR=chest(0.135, -0.11, 0.115, (0.6, -1, -0.5))),
        walk_=dict(armR=chest(0.135, -0.11, 0.115, (0.6, -1, -0.5))))
def musician(d):
    """Straight from rehearsal: long hair, short leather jacket, heavy boots, a guitar on her back."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("k12.skin")
    d.hair("k12.hair", t=0.020, front=0.34, ang=24, nape=-1.2)
    d.add(at(r.chest, loft([(-0.20, 0.105, 0.045, 0, -B.depth - 0.012), (0.0, 0.118, 0.06, 0, -B.depth + 0.01), (0.14, 0.115, 0.075, 0, -0.05)], 0.03)), "k12.hair", "hair")
    d.torso("k12.jacket", g=0.018, hem=0.045)
    d.torso("k12.shirt", g=0.008, hem=0.13, grp="shirt")
    d.hips("k12.jeans", g=0.005)
    for o in LR(): d.sleeve(o, "k12.jacket", g=0.016); d.hand(o, "k12.skin"); d.leg(o, "k12.jeans", g=0.004); d.shoe(o, "k12.boot", "k12.sole", hi=0.13, chunky=1.22)
    G = r.chest.sub((0.035, -0.13, -B.depth - 0.085), Rz(-21))            # gig bag, slung across the back
    d.add(at(G, loft([(-0.50, 0.10, 0.05), (-0.44, 0.175, 0.06), (-0.32, 0.19, 0.06), (-0.20, 0.14, 0.055), (-0.10, 0.155, 0.055), (0.0, 0.11, 0.05), (0.05, 0.055, 0.04)], 0.03)), "k12.gigbag", "gigbag")
    d.add(at(G, box((0, 0.25, 0), (0.048, 0.23, 0.032), 0.016) | box((0, 0.44, 0), (0.06, 0.06, 0.03), 0.02)), "k12.gigbag", "gigbag")
    d.add(at(G, box((0.0, -0.27, -0.06), (0.10, 0.085, 0.012), 0.01)), "k12.gigpocket", "gigbag")
    d.face(mouth=(135, 40, 17))
    d.stroke(G.pt(0, 0.48, -0.034), G.pt(0, 0.04, -0.045), 1, ("gigbag",), 0.04)                                   # zip
    for o in LR(): ring(d, Fr(lerp(r.knee[o], r.ank[o], 0.62), r.S.R), 0.0, B.r_an + 0.03, B.r_an + 0.03, 1, (f"foot{o}",), 0.05)


CARD_ARM = chest(0.20, -0.25, 0.19, (0.5, -1, -0.5)); STRAP_ARM = chest(-0.13, -0.11, 0.115, (-0.6, -1, -0.5))
@person("k13", "hoofddoek", anatomy(H=1.62, head=1.16, sh=0.165, waist=0.140, hip=0.175, bust=0.02, butt=0.015), side=1,
        sta=dict(yaw=20, hyaw=52, sway=-0.03, hiptilt=4, stance=0.17, footR=(0.03, 0.03, 0, 20, 0), armR=CARD_ARM, armL=STRAP_ARM),
        leun=dict(armL=STRAP_ARM), eet=dict(armL=STRAP_ARM), walk_=dict(armL=STRAP_ARM))
def hijabi(d):
    """Headscarf and a long belted coat, tote on her shoulder, bank card already in her hand."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("k13.skin", ears=False)
    scarf = ell((0, 0.006, -0.03), (a + 0.024, b + 0.022, c + 0.05)) & hs((0, 0, c * 0.52), (0, -0.15, 1))
    d.add(at(r.head, scarf), "k13.scarf", "scarf")
    d.add(at(r.chest, loft([(-0.13, B.sh + 0.012, B.depth + 0.03), (-0.02, B.sh - 0.01, B.depth + 0.03), (0.07, 0.125, 0.12), (0.16, 0.11, 0.115)], 0.035)), "k13.scarf", "scarf")
    d.torso("k13.coat", g=0.022, hem=0.53, flare=0.03, hemb=0.14)
    d.add(at(r.pel, loft([(0.065, B.waist + 0.03, B.depth + 0.03), (0.115, B.waist + 0.03, B.depth + 0.03)], 0.012)), "k13.belt", "belt")
    for o in LR(): d.sleeve(o, "k13.coat", g=0.020); d.hand(o, "k13.skin"); d.leg(o, "k13.trousers", g=0.02, flare=0.012); d.shoe(o, "k13.boot", "k13.sole", chunky=1.05)
    T = r.chest.sub((-B.sh - 0.05, -0.44, -0.04), Ry(-62))
    d.add(at(T, box((0, 0, 0), (0.14, 0.15, 0.04), 0.02)), "k13.tote", "tote")
    for x in (-0.07, 0.07): d.line(T.pt(x, 0.15, 0), r.chest.pt(-B.sh + 0.03, 0.02, -0.01 + x * 0.3), "k13.strap")
    if d.pose == "sta": d.add(at(r.hand[1].sub((0, 0.03, 0.06), Rx(-60)), box((0, 0, 0.02), (0.03, 0.004, 0.045), 0.002)), "k13.card", "card")
    d.face(mouth=(135, 40, 17))
    ring(d, r.pel, -0.50, B.hip + 0.06, 0.14, -1, ("torso",))
    d.stroke(r.pel.pt(0, -0.02, -0.135), r.pel.pt(0, -0.50, -0.142), -1, ("torso",))                               # back vent
    d.stroke(T.pt(-0.13, 0.06, -0.042), T.pt(0.13, 0.06, -0.042), (181, 61, 26), ("tote",)); d.stroke(T.pt(-0.13, 0.06, 0.042), T.pt(0.13, 0.06, 0.042), (181, 61, 26), ("tote",))


def apron(d, mat, bib=True, hem=0.40, g=0.03):
    """A cook's apron: a skirt around the front of the hips and, with `bib`, a panel up the chest."""
    B, r = d.B, d.r; Lc = B.spine - 0.10 * B.k
    up, lo = d.torso_solids(g=g, hem=hem, flare=0.02)
    d.add(at(r.pel, lo & hs((0, 0, -0.035), (0, 0, -1)) & below(0.135)), mat, "apron")
    if bib: d.add(at(r.chest, up & hs((0, 0, 0.03), (0, 0, -1)) & box((0, -Lc * 0.5 - 0.075, 0.2), (0.118, Lc * 0.5 + 0.005, 0.2))), mat, "apron")

def ties(d, mat, col):
    """Apron strings round the waist, and the bow at the back."""
    B, r = d.B, d.r
    for o in LR(): d.stroke(r.pel.pt(o * (B.waist + 0.03), 0.09, 0.02), r.pel.pt(o * 0.05, 0.085, -B.depth - 0.07), col)
    zb = -B.depth - 0.03 - B.butt * 0.5 - 0.035
    d.add(at(r.pel, ell((-0.045, 0.075, zb), (0.04, 0.022, 0.015)) | ell((0.045, 0.075, zb), (0.04, 0.022, 0.015))
             | cap((-0.012, 0.07, zb), (-0.03, -0.03, zb + 0.01), 0.012) | cap((0.012, 0.07, zb), (0.035, -0.05, zb + 0.01), 0.012)), mat, "bow")

def worker_poses(B, s, basket, pad=None):
    """What both workers do. s: the hand that holds things up (+1 right, -1 left). Facing us is yaw 180."""
    up = "armR" if s > 0 else "armL"; other = "armL" if s > 0 else "armR"
    P = dict(
        praat=dict(yaw=180, lean=10, hyaw=-6 * s, hroll=5 * s, stance=0.21, **{up: chest(s * 0.15, -0.22, 0.27, (s * 0.7, -0.8, -0.3)), other: "hip"}),
        roept=dict(yaw=180, hyaw=8 * s, hpitch=-8, stance=0.21, cone=s, **{up: chest(s * 0.22, 0.20, 0.20, (s * 0.8, -0.5, -0.2)), other: "hip"}),
        bak0=dict(yaw=-16, lean=11, hyaw=-10, hpitch=16, stance=0.22, armL=chest(-0.20, basket, 0.30, (-0.7, -0.6, -0.6)), armR=chest(-0.03, basket - 0.03, 0.33, (0.8, -0.6, -0.5))),
        bak1=dict(yaw=-16, lean=14, hyaw=-10, hpitch=16, sway=-0.02, stance=0.22, armL=chest(-0.25, basket - 0.04, 0.27, (-0.7, -0.6, -0.6)), armR=chest(-0.08, basket - 0.07, 0.30, (0.8, -0.6, -0.5))),
        reik=dict(yaw=0, lean=13, hpitch=-8, stance=0.22, footR=(0, -0.08, 0, 8, 28), armL=stand(-0.24, 1.26, 0.42, (-0.6, -0.6, -0.6)), armR=stand(0.03, 1.02, 0.36, (0.8, -0.5, -0.5))))
    return P

@person("w0", "Marleen", anatomy(H=1.60, head=1.20, sh=0.180, waist=0.200, hip=0.210, belly=0.07, bust=0.04, butt=0.03, bulk=1.15, depth=0.12, neck=0.8),
        sta=dict(yaw=180, hyaw=-12, hroll=5, stance=0.22, armL="hip", armR="hip"),
        **worker_poses(None, 1, -0.34))
def marleen(d):
    """Runs the place: small and round, curls and a bun, bib apron, sleeves rolled, tea towel over her shoulder."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("w0.skin", cheeks=0.01, jaw=1.08)
    d.hair("w0.hair", t=0.028, front=0.60, ang=32, nape=-0.45, extra=blobs([(0, b * 0.95, -0.03, 0.07), (-a - 0.006, b * 0.25, -0.01), (a + 0.006, b * 0.25, -0.01), (-0.07, b * 0.78, 0.03), (0.07, b * 0.78, 0.03), (0, b * 0.2, -c - 0.01)], 0.05))
    d.dot(r.head.pt(a * 0.78, b * 0.62, c * 0.35), (181, 61, 26), ((0, 0), (1, 0)), tol=0.05)                    # a red hair clip
    d.torso("w0.blouse", g=0.019, hem=0.13)
    d.hips("w0.trousers", g=0.014)
    for o in LR():
        d.forearm(o, "w0.skin"); d.sleeve(o, "w0.blouse", g=0.016, to=0.62, wide=0.006); d.hand(o, "w0.skin"); d.leg(o, "w0.trousers", g=0.014); d.shoe(o, "w0.clog", "w0.sole", chunky=1.1)
        d.add(cap(lerp(r.sh[o], r.el[o], 0.92), lerp(r.el[o], r.wr[o], 0.26), B.r_el + 0.026, B.r_el + 0.024), "w0.cuff", f"arm{o}")   # the rolled sleeve
    apron(d, "w0.apron", bib=True, hem=0.42)
    zf = B.depth + 0.045
    d.face(brow=(124, 60, 30), mouth=(167, 36, 15), blush=(219, 142, 94), smile=d.pose != "roept", open_=d.pose == "roept")
    for o in LR(): d.stroke(r.chest.pt(o * 0.10, -0.085, zf - 0.01), r.chest.pt(o * 0.085, 0.045, 0.03), (135, 20, 11))            # neck strap
    ties(d, "w0.apron", (135, 20, 11))
    zp = B.depth + B.belly + 0.05
    d.stroke(r.pel.pt(-0.09, -0.06, zp), r.pel.pt(0.09, -0.06, zp), -1, grp=("apron",))                                        # pocket
    for o in LR(): d.stroke(r.pel.pt(o * 0.09, -0.06, zp), r.pel.pt(o * 0.09, -0.15, zp - 0.005), -1, grp=("apron",))
    d.add(at(r.chest, box((-0.125, -0.13, B.depth + 0.035), (0.05, 0.125, 0.012), 0.008) | box((-0.125, -0.09, -B.depth - 0.03), (0.05, 0.10, 0.012), 0.008) | cap((-0.125, 0.0, -B.depth * 0.5), (-0.125, 0.0, B.depth * 0.6), 0.03)), "w0.towel", "towel")
    for y in (-0.20, -0.165): d.stroke(r.chest.pt(-0.172, y, zf + 0.005), r.chest.pt(-0.078, y, zf + 0.005), (181, 61, 26), grp=("towel",))
    for y in (-0.15, -0.115): d.stroke(r.chest.pt(-0.172, y, -B.depth - 0.045), r.chest.pt(-0.078, y, -B.depth - 0.045), (181, 61, 26), grp=("towel",))


JEF_PAD = chest(-0.10, -0.26, 0.20, (-0.6, -1, -0.3))
@person("w1", "Jef", anatomy(H=1.80, head=1.08, sh=0.175, waist=0.135, hip=0.150, bulk=0.88, legs=0.50),
        sta=dict(yaw=180, hyaw=14, sway=0.03, hiptilt=-4, stance=0.19, armL=JEF_PAD, armR="hang"),
        **dict(worker_poses(None, -1, -0.38), praat=dict(yaw=180, lean=12, hpitch=10, hyaw=6, stance=0.19, armL=JEF_PAD, armR=chest(-0.02, -0.22, 0.25, (0.8, -0.8, -0.2)))))
def jef(d):
    """Tall and thin, paper cap on his curls, long apron tied at the waist, a pen behind his ear and the order pad in his hand."""
    B, r = d.B, d.r; a, b, c = B.hr
    d.head("w1.skin", nose=1.15)
    d.hair("w1.hair", t=0.024, front=0.58, extra=blobs([(-a - 0.004, b * 0.30, -0.02), (a + 0.004, b * 0.30, -0.02), (0, b * 0.3, -c - 0.012), (-0.07, b * 0.1, -0.09), (0.07, b * 0.1, -0.09)], 0.045))
    d.add(at(r.head.sub((0, b * 0.52, 0.0), Rx(-6)), loft([(0.0, a * 1.0, c + 0.036), (0.085, a * 0.64, c + 0.03), (0.108, 0.02, c + 0.012)], 0.008)), "w1.cap", "hat")
    d.torso("w1.shirt", g=0.010, hem=0.10)
    d.hips("w1.trousers", g=0.010)
    for o in LR(): d.upperarm(o, "w1.skin"); d.forearm(o, "w1.skin"); d.sleeve(o, "w1.shirt", g=0.012, to=0.42, wide=0.006); d.hand(o, "w1.skin"); d.leg(o, "w1.trousers", g=0.010); d.shoe(o, "w1.shoe", "w1.sole")
    apron(d, "w1.apron", bib=False, hem=0.50, g=0.024)
    if d.pose in ("sta", "praat"): d.add(at(r.hand[-1].sub((0, 0.035, 0.05), Rx(-50)), box((0, 0, 0.03), (0.04, 0.008, 0.055), 0.003)), "w1.pad", "pad")
    d.line(r.head.pt(-a - 0.004, 0.0, 0.03), r.head.pt(-a - 0.01, 0.045, -0.07), "w1.pen")
    d.face(mouth=(135, 40, 17), smile=d.pose != "roept", open_=d.pose == "roept")
    d.stroke(r.head.pt(-a * 0.30, -b * 0.36, c * 0.95), r.head.pt(a * 0.30, -b * 0.36, c * 0.95), (64, 55, 44), ("head",), 0.025)   # moustache
    ties(d, "w1.apron", (181, 61, 26))
    ring(d, r.head, b * 0.56, a + 0.012, c + 0.04, (181, 61, 26), ("hat",), 0.05)                                 # a red line round the paper cap
    ring(d, r.chest, -0.02, B.sh * 0.5, 0.075, (240, 229, 204), ("torso",), 0.04)
    zp = B.depth + 0.05
    d.stroke(r.pel.pt(-0.08, -0.10, zp), r.pel.pt(0.08, -0.10, zp), -1, grp=("apron",))
    for o in LR(): d.stroke(r.pel.pt(o * 0.08, -0.10, zp), r.pel.pt(o * 0.08, -0.20, zp), -1, grp=("apron",))

N = sum(ch.key[0] == "k" for ch in CAST)   # number of customers
POSES_K = ("sta", "leun", "eet", "stap0", "stap1", "stap0-r", "stap1-r")
POSES_W = ("sta", "praat", "roept", "bak0", "bak1", "reik", "stap0", "stap1", "stap0-r", "stap1-r")

def bake(report=print):
    """Every sprite of every person: name -> (image, anchor). Called by tools/sprites.py."""
    out = {}
    for i, ch in enumerate(CAST):
        for pose in (POSES_K if ch.key[0] == "k" else POSES_W): out[f"{ch.key}-{pose}"] = sprite(ch, pose)
    if report: report(f"people: {len(out)} sprites, {N} customers")
    return out


# ------------------------------------------------------------------ line-up: plain silhouettes, native size
def lineup(path, pose="sta", cols=8, shaded=False):
    cells = []
    for ch in CAST:
        d = build(ch, pose)
        if shaded: im, t = debug_shade(d.m, d.anchor); m = np.asarray(im)[..., 3] > 0
        else: m, t = render_mask(d.m, d.anchor); im = None
        cells.append((ch, m, t, im))
    cw, chh, base = 64, 132, 116
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw + 8, rows * chh + 6), (233, 196, 127)); dr = ImageDraw.Draw(sheet)
    for i, (ch, m, t, im) in enumerate(cells):
        ox = 4 + (i % cols) * cw + cw // 2 - t.ax; oy = 4 + (i // cols) * chh + base - t.ay
        dr.line([ox + t.ax - 26, oy + t.ay + 4, ox + t.ax + 26, oy + t.ay + 4], fill=(198, 136, 54))
        if im is not None: sheet.paste(im, (ox, oy), im)
        else: sheet.paste((30, 9, 9), (ox, oy), Image.fromarray(m.astype(np.uint8) * 255))
        dr.text((4 + (i % cols) * cw + 3, 4 + (i // cols) * chh + base + 5), f"{ch.key} {ch.title}"[:10], fill=(90, 60, 51))
    sheet.save(path)
    return cells

def distinct(cells):
    """How alike two silhouettes are: overlap / union with the feet on the same spot, also tried mirrored."""
    def canvas(m, t, flip=False):
        c = np.zeros((160, 140), bool); m = m[:, ::-1] if flip else m; ax = (m.shape[1] - 1 - t.ax) if flip else t.ax
        c[130 - t.ay:130 - t.ay + m.shape[0], 70 - ax:70 - ax + m.shape[1]] = m; return c
    out = []
    for i in range(len(cells)):
        for j in range(i + 1, len(cells)):
            a = canvas(cells[i][1], cells[i][2]); best = 0
            for fl in (False, True):
                b = canvas(cells[j][1], cells[j][2], fl); best = max(best, (a & b).sum() / (a | b).sum())
            out.append((best, cells[i][0].key, cells[j][0].key))
    return sorted(out, reverse=True)

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] in ("lineup", "shaded"):
        cells = lineup(sys.argv[2], shaded=sys.argv[1] == "shaded")
        for ch, m, t, _ in cells:
            ys, xs = np.nonzero(m); print(f"{ch.key:4} {ch.title:13} {xs.max() - xs.min() + 1:3} wide {t.ay - ys.min() + 1:4} tall")
        if sys.argv[1] == "lineup":
            print("most alike (overlap / union, 1 = identical):")
            for v, a, b in distinct(cells)[:6]: print(f"  {a:4} {b:4} {v:.2f}")
    elif len(sys.argv) >= 3 and sys.argv[1] == "sheet":
        cw, chh = 66, 126; sh = Image.new("RGBA", (10 * cw, len(CAST) * chh), (233, 196, 127, 255))
        for j, ch in enumerate(CAST):
            for i, pose in enumerate(POSES_K if ch.key[0] == "k" else POSES_W):
                im, (ax, ay) = sprite(ch, pose); sh.alpha_composite(im, (i * cw + cw // 2 - ax, j * chh + 110 - ay))
                if pose == "sta": m = measure(im); print(f"{ch.key:4} {ch.title:13} below 0.17: {m['dark']:5.1%}  median {m['median']:.2f}  brightest {m['top']:.2f}  room colours {m['palette']:.0%}")
        sh.convert("RGB").save(sys.argv[2])
    else: print(__doc__)
