#!/usr/bin/env python3
"""Frituur interior: tiny numpy ray tracer -> lighting -> pixel-art post-process."""
import numpy as np, json, math, os, sys, time
from PIL import Image, ImageDraw, ImageFilter

W = int(sys.argv[1]) if len(sys.argv) > 1 else 640
H = W * 9 // 16
CH = H + 40 * W // 640  # rows drawn: more floor below the 16:9 frame, for windows that are taller than wide
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "assets", "frituur_scene")
rng = np.random.default_rng(11)
EPS = 1e-3
A = lambda *c: np.array(c, np.float64)

# ------------------------------------------------------------------ camera
PITCH = math.radians(25); DIST = 24.0
TGT = A(0, 1.3, 3.25)
fwd = A(0, -math.sin(PITCH), math.cos(PITCH))
CAM = TGT - fwd * DIST
right = A(1, 0, 0); up = np.cross(fwd, right)
TANV = 2.9 / DIST; TANH = TANV * W / H

def proj(P):
    v = np.asarray(P, np.float64) - CAM
    zc = v @ fwd
    return ((v @ right) / (zc * TANH) + 1) / 2 * W, (1 - (v @ up) / (zc * TANV)) / 2 * H

# ------------------------------------------------------------------ noise
def h2(a, b):
    v = np.sin(a * 127.1 + b * 311.7) * 43758.5453
    return v - np.floor(v)

def vnoise(u, v):
    iu = np.floor(u); iv = np.floor(v); fu = u - iu; fv = v - iv
    fu = fu * fu * (3 - 2 * fu); fv = fv * fv * (3 - 2 * fv)
    a = h2(iu, iv); b = h2(iu + 1, iv); c = h2(iu, iv + 1); d = h2(iu + 1, iv + 1)
    return (a * (1 - fu) + b * fu) * (1 - fv) + (c * (1 - fu) + d * fu) * fv

# ------------------------------------------------------------------ pixel font
FONT = {
 "A":"010101111101101","B":"110101110101110","C":"011100100100011","D":"110101101101110",
 "E":"111100110100111","F":"111100110100100","G":"011100101101011","H":"101101111101101",
 "I":"111010010010111","J":"001001001101010","K":"101101110101101","L":"100100100100111",
 "M":"101111111101101","N":"110101101101101","O":"010101101101010","P":"110101110100100",
 "Q":"010101101110011","R":"110101110101101","S":"011100010001110","T":"111010010010010",
 "U":"101101101101111","V":"101101101101010","W":"101101111111101","X":"101101010101101",
 "Y":"101101010010010","Z":"111001010100111",
 "0":"111101101101111","1":"010110010010111","2":"110001010100111","3":"110001010001110",
 "4":"101101111001001","5":"111100110001110","6":"011100111101111","7":"111001010010010",
 "8":"111101111101111","9":"111101111001110",
 ",":"000000000010100",".":"000000000000010","-":"000000111000000","!":"010010010000010",
 "'":"010010000000000",
}
def txt(d, x, y, s, col, sc=1, bold=False):
    adv = (5 if bold else 4) * sc
    for ch in s:
        g = FONT.get(ch)
        if g:
            for i, b in enumerate(g):
                if b == "1":
                    r, c = divmod(i, 3)
                    x0 = x + c * sc; y0 = y + r * sc
                    d.rectangle([x0, y0, x0 + sc - 1, y0 + sc - 1], fill=col)
        x += adv
    return x
def txtw(s, sc=1, bold=False):
    return len(s) * (5 if bold else 4) * sc - sc

# ------------------------------------------------------------------ decals (drawn 1:1 in screen pixels)
def steel_img(w, h, seed=0, base=(176, 172, 164)):
    r = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h)[:, None]
    k = 0.90 + 0.12 * np.sin(yy * 5.5 + 0.6) + 0.03 * r.standard_normal((h, 1))
    arr = np.clip(np.array(base)[None, None, :] * (k[:, :, None] * np.ones((1, w, 1))), 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def D_menu(title, items, accent):
    def gen(w, h):
        im = Image.new("RGB", (w, h), (252, 234, 186)); d = ImageDraw.Draw(im)
        hb = 9
        d.rectangle([0, 0, w - 1, hb], fill=accent)
        txt(d, (w - txtw(title, 1, True)) // 2, 2, title, (255, 240, 200), 1, True)
        rows = max(1, (h - hb - 4) // 6)
        for i, (name, price) in enumerate(items[:rows]):
            y = hb + 3 + i * 6
            x = txt(d, 4, y, name, (86, 44, 30))
            px = w - 5 - txtw(price)
            for xx in range(x + 1, px - 2, 2): d.point((xx, y + 4), fill=(190, 150, 110))
            txt(d, px, y, price, (190, 40, 30))
        d.rectangle([0, 0, w - 1, h - 1], outline=(70, 38, 24))
        return im, 0.95
    return gen

CANS = [(214, 40, 40), (240, 150, 30), (40, 150, 80), (40, 90, 190), (245, 215, 60), (40, 30, 30), (240, 240, 235), (230, 90, 140), (60, 180, 190)]
def D_fridge(title, seed):
    def gen(w, h):
        r = np.random.default_rng(seed)
        im = Image.new("RGB", (w, h), (34, 34, 44)); d = ImageDraw.Draw(im)
        em = Image.new("L", (w, h), 0); e = ImageDraw.Draw(em)
        hb = 11
        d.rectangle([2, 2, w - 3, hb], fill=(206, 44, 36)); e.rectangle([2, 2, w - 3, hb], fill=230)
        txt(d, (w - txtw(title, 1, True)) // 2, 4, title, (255, 240, 200), 1, True)
        gx0, gy0, gx1, gy1 = 4, hb + 3, w - 5, h - 9
        d.rectangle([gx0, gy0, gx1, gy1], fill=(196, 228, 224)); e.rectangle([gx0, gy0, gx1, gy1], fill=215)
        n = 5; sh = (gy1 - gy0) / n
        for s in range(n):
            yb = int(gy0 + (s + 1) * sh) - 1
            d.line([gx0, yb, gx1, yb], fill=(110, 140, 140))
            ch = int(sh) - 4
            col = CANS[r.integers(len(CANS))]
            x = gx0 + 2
            while x + 3 <= gx1 - 1:
                if r.random() < 0.3: col = CANS[r.integers(len(CANS))]
                if r.random() > 0.08:
                    tall = ch if s % 2 == 0 else max(4, ch - 3)
                    d.rectangle([x, yb - tall, x + 2, yb - 1], fill=col)
                    d.point((x, yb - tall), fill=(250, 250, 250))
                    d.line([x + 2, yb - tall + 1, x + 2, yb - 1], fill=tuple(int(c * 0.7) for c in col))
                    if s % 2 == 0: d.rectangle([x + 1, yb - tall - 2, x + 1, yb - tall - 1], fill=(235, 235, 235))
                x += 4
        mx = w // 2
        d.rectangle([mx - 1, gy0 - 1, mx, gy1 + 1], fill=(34, 34, 44)); e.rectangle([mx - 1, gy0 - 1, mx, gy1 + 1], fill=0)
        for hx in (mx - 4, mx + 3):
            d.rectangle([hx, (gy0 + gy1) // 2 - 9, hx, (gy0 + gy1) // 2 + 9], fill=(150, 150, 160)); e.rectangle([hx, (gy0 + gy1) // 2 - 9, hx, (gy0 + gy1) // 2 + 9], fill=0)
        for yy in range(h - 7, h - 2, 2): d.line([4, yy, w - 5, yy], fill=(60, 60, 72))
        # glass streaks
        for k in range(0, w + h, 23):
            for t in range(8):
                x = k - t * 1 - (gy0 % 3);
        return im, np.asarray(em, np.float64) / 255.0
    return gen

def D_freezer(w, h):
    im = steel_img(w, h, 3); d = ImageDraw.Draw(im)
    sy = int(h * 0.48)
    d.rectangle([0, 0, w - 1, h - 1], outline=(96, 94, 92))
    d.line([1, sy, w - 2, sy], fill=(84, 82, 82)); d.line([1, sy + 1, w - 2, sy + 1], fill=(214, 210, 200))
    for y0, y1 in ((sy - 22, sy - 5), (sy + 6, sy + 23)):
        d.rectangle([w - 8, y0, w - 6, y1], fill=(70, 70, 76)); d.line([w - 8, y0, w - 8, y1], fill=(225, 222, 214))
    d.rectangle([5, 5, 16, 9], fill=(20, 30, 24)); txt(d, 6, 5, "-18", (90, 240, 120))
    for yy in range(h - 10, h - 3, 2): d.line([5, yy, w - 6, yy], fill=(92, 90, 90))
    em = np.zeros((h, w)); em[5:10, 5:17] = 0.8
    return im, em

def D_fryer(w, h):
    im = steel_img(w, h, 5); d = ImageDraw.Draw(im)
    em = np.zeros((h, w))
    n = 4; pw = w / n
    top = max(9, int(h * 0.26))
    d.rectangle([0, 0, w - 1, top], fill=(150, 146, 140))
    for i in range(n):
        x0 = int(i * pw); x1 = int((i + 1) * pw) - 1; cx = (x0 + x1) // 2
        d.rectangle([x0 + 2, top + 2, x1 - 2, h - 7], outline=(104, 100, 98))
        d.line([x0 + 3, top + 3, x1 - 3, top + 3], fill=(222, 218, 208))
        d.rectangle([x0 + 4, top + 6, x0 + 5, top + 14], fill=(74, 74, 80))
        d.ellipse([cx - 3, 2, cx + 3, 8], fill=(36, 34, 38)); d.point((cx, 3), fill=(240, 240, 240))
        col = (255, 120, 30) if i != 2 else (90, 230, 110)
        d.rectangle([cx + 6, 4, cx + 7, 5], fill=col); em[4:6, cx + 6:cx + 8] = 1.0
    d.rectangle([0, h - 5, w - 1, h - 1], fill=(52, 50, 54))
    return im, em

def D_doors(n, seed):
    def gen(w, h):
        im = steel_img(w, h, seed); d = ImageDraw.Draw(im)
        dr = max(8, int(h * 0.2)); pw = w / n
        d.line([0, dr, w - 1, dr], fill=(100, 98, 96)); d.line([0, dr + 1, w - 1, dr + 1], fill=(220, 216, 206))
        for i in range(n):
            x0 = int(i * pw); x1 = int((i + 1) * pw) - 1; cx = (x0 + x1) // 2
            d.rectangle([x0 + 1, dr + 3, x1 - 1, h - 7], outline=(104, 100, 98))
            d.rectangle([cx - 5, dr // 2 - 1, cx + 5, dr // 2], fill=(78, 78, 84))
            d.rectangle([x1 - 5, dr + 8, x1 - 4, dr + 17], fill=(78, 78, 84))
        d.rectangle([0, h - 5, w - 1, h - 1], fill=(52, 50, 54))
        return im, 0.0
    return gen

def D_backdoor(w, h):
    im = Image.new("RGB", (w, h), (112, 52, 36)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(62, 30, 22))
    d.rectangle([3, 3, w - 4, h - 12], outline=(140, 72, 48))
    r = max(4, w // 5); cx = w // 2; cy = int(h * 0.28)
    d.ellipse([cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1], fill=(170, 160, 150))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(60, 74, 84))
    d.line([cx - r + 2, cy - 1, cx - 1, cy - r + 2], fill=(150, 180, 190))
    d.rectangle([4, h - 11, w - 5, h - 3], fill=(150, 146, 138))
    d.rectangle([w - 8, int(h * 0.5), w - 6, int(h * 0.5) + 9], fill=(190, 186, 176))
    txt(d, (w - txtw("PRIVE")) // 2, int(h * 0.46), "PRIVE", (240, 220, 180))
    return im, 0.0

def D_led(w, h):
    im = Image.new("RGB", (w, h), (22, 16, 16)); d = ImageDraw.Draw(im)
    em = Image.new("L", (w, h), 0); e = ImageDraw.Draw(em)
    d.rectangle([0, 0, w - 1, h - 1], outline=(70, 64, 60))
    return im, np.asarray(em, np.float64) / 255.0  # the mod draws the live number

def cone_icon(d, cx, y, s=1):
    for i, dx in enumerate((-5, -3, -1, 1, 3, 5)):
        hh = (9, 12, 10, 13, 11, 8)[i]
        d.rectangle([cx + dx * s - 1, y - hh * s, cx + dx * s, y + 2], fill=(250, 200, 70) if i % 2 else (236, 170, 50))
    d.polygon([(cx - 7 * s, y), (cx + 7 * s, y), (cx, y + 15 * s)], fill=(250, 244, 230))
    for k in (-4, 0, 4):
        d.line([cx + k * s, y, cx + k * s // 3, y + 10 * s], fill=(206, 44, 36))
    d.line([cx - 7 * s, y, cx + 7 * s, y], fill=(206, 44, 36))

def D_sign(w, h):
    im = Image.new("RGB", (w, h), (128, 30, 26)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(240, 190, 80)); d.rectangle([2, 2, w - 3, h - 3], outline=(170, 60, 40))
    sc = 2 if h >= 24 else 1
    s = "FRITUUR"; x = (w - txtw(s, sc, True)) // 2; y = 4
    txt(d, x + 1, y + 1, s, (70, 14, 14), sc, True); txt(d, x, y, s, (252, 214, 96), sc, True)
    s2 = "VERS GEBAKKEN"
    if h >= 24: txt(d, (w - txtw(s2)) // 2, y + 5 * sc + 4, s2, (250, 236, 200))
    for sx in (9, w - 10):
        d.polygon([(sx, h // 2 - 4), (sx + 4, h // 2), (sx, h // 2 + 4), (sx - 4, h // 2)], fill=(252, 214, 96))
    return im, 0.0

def D_poster_fries(w, h):
    im = Image.new("RGB", (w, h), (250, 226, 150)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(190, 44, 34)); d.rectangle([1, 1, w - 2, h - 2], outline=(190, 44, 34))
    cone_icon(d, w // 2, h // 2 - 3)
    s = "FRIET!"; txt(d, (w - txtw(s)) // 2, h - 9, s, (160, 30, 26))
    return im, 0.0

def D_poster_burger(w, h):
    im = Image.new("RGB", (w, h), (60, 120, 110)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(240, 220, 170)); d.rectangle([1, 1, w - 2, h - 2], outline=(240, 220, 170))
    cx = w // 2; y = h // 2 - 8
    d.pieslice([cx - 10, y, cx + 10, y + 16], 180, 360, fill=(226, 160, 70))
    d.point((cx - 4, y + 3), fill=(250, 236, 190)); d.point((cx + 3, y + 2), fill=(250, 236, 190)); d.point((cx, y + 5), fill=(250, 236, 190))
    d.rectangle([cx - 11, y + 9, cx + 11, y + 10], fill=(90, 190, 70))
    d.rectangle([cx - 10, y + 11, cx + 10, y + 13], fill=(110, 56, 30))
    d.rectangle([cx - 11, y + 14, cx + 11, y + 14], fill=(250, 200, 60))
    d.rectangle([cx - 10, y + 15, cx + 10, y + 18], fill=(214, 146, 60))
    s = "BURGER"; txt(d, (w - txtw(s)) // 2, h - 9, s, (250, 236, 200))
    return im, 0.0

def D_regdisp(w, h):
    im = Image.new("RGB", (w, h), (14, 22, 16)); d = ImageDraw.Draw(im)
    txt(d, max(0, (w - txtw("3,50")) // 2), max(0, (h - 5) // 2), "3,50", (110, 250, 130))
    return im, 0.9

# ------------------------------------------------------------------ procedural materials
def mat(col=(0.8, 0.8, 0.8), fn=None, emit=0.0, shadow=True, glass=False, decal=None, sunonly=False):
    return dict(col=A(*col), fn=fn, emit=emit, shadow=shadow, glass=glass, decal=decal, sunonly=sunonly)

def floor_fn(P, N):
    s = 0.4
    u = P[:, 0] / s; v = P[:, 2] / s
    iu = np.floor(u); iv = np.floor(v); fu = u - iu; fv = v - iv
    chk = ((iu + iv) % 2 == 0)
    hh = h2(iu, iv)
    col = np.where(chk[:, None], A(0.86, 0.74, 0.54), A(0.60, 0.26, 0.17)) * (0.90 + 0.18 * hh[:, None])
    col *= (0.96 + 0.08 * vnoise(P[:, 0] * 9, P[:, 2] * 9))[:, None]
    du = np.minimum(fu, 1 - fu) * s; dv = np.minimum(fv, 1 - fv) * s
    cov = np.maximum(np.clip((0.02 - du) / 0.02, 0, 1), np.clip((0.035 - dv) / 0.035, 0, 1))
    return col * (1 - cov[:, None]) + A(0.34, 0.20, 0.15) * cov[:, None]

def plaster(a, b):
    return A(0.94, 0.79, 0.56) * (0.94 + 0.09 * vnoise(a * 1.7, b * 1.7))[:, None]

def backwall_fn(P, N):
    x = P[:, 0]; y = P[:, 1]; s = 0.2
    u = x / s; v = y / s; iu = np.floor(u); iv = np.floor(v); fu = u - iu; fv = v - iv
    hh = h2(iu, iv)
    base = A(0.88, 0.81, 0.68) * (0.93 + 0.09 * hh)[:, None]
    band = (iv == 6)
    base[band] = A(0.74, 0.20, 0.14) * (0.88 + 0.2 * hh[band])[:, None]
    acc = (iv == 7) & (iu % 2 == 0)
    base[acc] = A(0.93, 0.70, 0.30) * (0.92 + 0.12 * hh[acc])[:, None]
    du = np.minimum(fu, 1 - fu) * s; dv = np.minimum(fv, 1 - fv) * s
    cov = np.clip((0.017 - np.minimum(du, dv)) / 0.017, 0, 1) * 0.85
    col = base * (1 - cov[:, None]) + A(0.60, 0.52, 0.44) * cov[:, None]
    pl = y > 2.36
    col[pl] = plaster(x[pl], y[pl])
    rail = (y > 2.30) & (y <= 2.36)
    col[rail] = A(0.40, 0.22, 0.12)
    return col

def sidewall_fn(P, N):
    z = P[:, 2]; y = P[:, 1]
    col = plaster(z, y)
    kitchen = z > 3.86
    col[kitchen] = A(0.92, 0.88, 0.78) * (0.95 + 0.06 * vnoise(z[kitchen] * 5, y[kitchen] * 5))[:, None]
    band = kitchen & (y > 1.2) & (y < 1.4)
    col[band] = A(0.74, 0.20, 0.14)
    w = (y < 1.0) & ~kitchen
    pz = z[w] / 0.16; ip = np.floor(pz)
    c = A(0.52, 0.29, 0.15) * (0.9 + 0.2 * h2(ip, ip * 0.7))[:, None]
    c[(pz - ip) < 0.12] *= 0.7
    col[w] = c
    return col

def wood(c, pw=0.14, axis=0, gaxis=1, var=0.14):
    c = A(*c)
    def fn(P, N):
        u = P[:, axis] / pw; iu = np.floor(u); fu = u - iu
        tone = 1 + var * (h2(iu, iu * 0.37) - 0.5) * 2
        g = vnoise(P[:, axis] * 45, P[:, gaxis] * 3.5)
        col = c * (tone * (0.93 + 0.14 * g))[:, None]
        col[fu < 0.08] *= 0.70
        return col
    return fn

def steel(c=(0.72, 0.70, 0.67)):
    c = A(*c)
    def fn(P, N):
        g = vnoise(P[:, 0] * 2.5 + P[:, 2] * 2.5, P[:, 1] * 70 + P[:, 2] * 70)
        band = 0.5 + 0.5 * np.sin(P[:, 1] * 6.0 + P[:, 0] * 0.9)
        k = 0.88 + 0.10 * g + 0.12 * band * (np.abs(N[:, 1]) < 0.5)
        return c * k[:, None]
    return fn

def stone_fn(P, N):
    k = 0.93 + 0.10 * vnoise(P[:, 0] * 30, P[:, 2] * 30) - 0.10 * (h2(np.floor(P[:, 0] * 90), np.floor(P[:, 2] * 90)) > 0.93)
    return A(0.90, 0.84, 0.72) * k[:, None]

def fries_fn(P, N):
    a = vnoise(P[:, 0] * 50, P[:, 2] * 13 + P[:, 1] * 25); b = vnoise(P[:, 0] * 13 + 7, P[:, 2] * 50 + P[:, 1] * 9)
    k = 0.70 + 0.42 * np.maximum(a, b)
    return A(1.0, 0.78, 0.27) * k[:, None]

def oil_fn(P, N):
    b = vnoise(P[:, 0] * 60, P[:, 2] * 60)
    col = A(0.62, 0.38, 0.08) * (0.8 + 0.5 * b)[:, None]
    col[b > 0.72] = A(0.98, 0.80, 0.40)
    return col

def mesh_fn(P, N):
    g = ((P[:, 0] / 0.035) % 1 < 0.3) | ((P[:, 1] / 0.035) % 1 < 0.3)
    col = np.where(g[:, None], A(0.70, 0.68, 0.64), A(0.72, 0.52, 0.16))
    top = N[:, 1] > 0.5
    if top.any(): col[top] = fries_fn(P[top], N[top]) * 0.9
    return col

def window_fn(P, N):
    y = P[:, 1]
    t = np.clip((y - 1.0) / 1.6, 0, 1)[:, None]
    col = A(1.0, 0.62, 0.26) * (1 - t) + A(1.0, 0.88, 0.56) * t
    sky = vnoise(P[:, 2] * 2.3 + P[:, 0] * 2.3, y * 6)
    col *= (0.9 + 0.15 * sky)[:, None]
    roofs = y < 1.28 + 0.22 * (h2(np.floor((P[:, 2] + P[:, 0]) * 2.6), 3.0))
    col[roofs] = A(0.80, 0.40, 0.22)
    return col

def stripes_fn(cx, cz, n, c1, c2):
    c1 = A(*c1); c2 = A(*c2)
    def fn(P, N):
        ang = np.arctan2(P[:, 2] - cz, P[:, 0] - cx)
        s = np.floor((ang / (2 * np.pi) + 0.5) * n) % 2 == 0
        return np.where(s[:, None], c1, c2)
    return fn

def bucket_fn(y0, lab):
    lab = A(*lab)
    def fn(P, N):
        col = np.tile(A(0.94, 0.93, 0.88), (len(P), 1))
        yy = P[:, 1] - y0
        col[(yy > 0.06) & (yy < 0.19)] = lab
        return col
    return fn

def bench_fn(P, N):
    k = 0.92 + 0.12 * (np.abs(((P[:, 2] / 0.22) % 1) - 0.5) * 2)
    return A(0.16, 0.58, 0.56) * k[:, None]

def mat_fn(P, N):
    col = np.tile(A(0.46, 0.14, 0.12), (len(P), 1))
    e = (P[:, 0] < 3.36) | (P[:, 0] > 4.09) | (P[:, 2] < 1.31) | (P[:, 2] > 2.09)
    col[e] = A(0.25, 0.10, 0.09)
    col *= (0.9 + 0.2 * h2(np.floor(P[:, 0] * 60), np.floor(P[:, 2] * 25)))[:, None]
    return col

def clock_fn(cx, cy, r):
    def fn(P, N):
        dx = (P[:, 0] - cx) / r; dy = (P[:, 1] - cy) / r; rr = np.hypot(dx, dy)
        col = np.tile(A(0.96, 0.93, 0.84), (len(P), 1))
        col[rr > 0.78] = A(0.70, 0.16, 0.12)
        def seg(ax, ay, wd):
            t = np.clip((dx * ax + dy * ay) / (ax * ax + ay * ay), 0, 1)
            return np.hypot(dx - t * ax, dy - t * ay) < wd
        hands = seg(0.0, 0.62, 0.09) | seg(0.42, -0.1, 0.11)
        col[hands & (rr < 0.75)] = A(0.12, 0.10, 0.10)
        return col
    return fn

def hood_fn(P, N):
    col = STEELF(P, N)
    f = (N[:, 2] < -0.5) & (P[:, 1] < 1.84)
    slot = f & (((P[:, 0] / 0.09) % 1) < 0.55)
    col[f] *= 0.8
    col[slot] = A(0.20, 0.19, 0.20)
    return col

def leaf_fn(c):
    c = A(*c)
    def fn(P, N):
        k = 0.85 + 0.3 * vnoise(P[:, 1] * 22, P[:, 0] * 8 + P[:, 2] * 8)
        return c * k[:, None]
    return fn

STEELF = steel()
STEEL = mat(fn=STEELF)
CHROME = mat((0.78, 0.77, 0.74))
DARK = mat((0.16, 0.14, 0.15))
BLACK = mat((0.08, 0.07, 0.08))
RED = mat((0.74, 0.15, 0.11))
REDV = mat((0.78, 0.18, 0.13))
WOODD = mat(fn=wood((0.36, 0.20, 0.11), 0.2))
WHITE = mat((0.95, 0.93, 0.88))
FRY = lambda: mat(tuple(A(1.0, 0.78, 0.27) * rng.uniform(0.8, 1.08)))

# ------------------------------------------------------------------ scene
prims = []
def box(x0, x1, y0, y1, z0, z1, m):
    prims.append(dict(k="box", lo=A(x0, y0, z0), hi=A(x1, y1, z1), m=m)); return prims[-1]
def cyl(cx, cz, y0, y1, r0, m, r1=None):
    prims.append(dict(k="cyl", cx=cx, cz=cz, y0=y0, y1=y1, r0=r0, r1=r0 if r1 is None else r1, m=m)); return prims[-1]
def ell(cx, cy, cz, rx, ry, rz, m):
    prims.append(dict(k="ell", c=A(cx, cy, cz), r=A(rx, ry, rz), m=m)); return prims[-1]

XL, XR, ZB = -4.2, 4.2, 6.6

# room shell
box(-6, 6, -0.3, 0, -2, ZB + 0.4, mat(fn=floor_fn))
box(-6, 6, 0, 3.9, ZB, ZB + 0.4, mat(fn=backwall_fn))
LW = mat(fn=sidewall_fn)
WZ0, WZ1, WY0, WY1 = 0.8, 2.8, 1.05, 2.55
box(-4.6, XL, 0, WY0, -2, ZB, LW); box(-4.6, XL, WY1, 3.9, -2, ZB, LW)
box(-4.6, XL, WY0, WY1, -2, WZ0, LW); box(-4.6, XL, WY0, WY1, WZ1, ZB, LW)
box(-4.25, -4.22, WY0, WY1, WZ0, WZ1, mat(fn=window_fn, emit=1.35, shadow=False))
TALL = mat(fn=sidewall_fn, shadow=False)
box(-4.6, XL, 3.9, 14, -2, ZB, TALL); box(XR, 4.6, 3.9, 14, -2, ZB, TALL)
HID = mat(sunonly=True)
box(-4.6, 4.6, 3.9, 4.0, -16, ZB + 0.4, HID); box(-4.6, XL, 0, 14, -16, -2, HID); box(-4.8, -4.6, 3.9, 40, -16, ZB + 0.4, HID)
FR = mat(fn=wood((0.40, 0.21, 0.11), 0.5))
for z in (WZ0, 1.47, 2.13, WZ1 - 0.06): box(-4.26, -4.19, WY0, WY1, z, z + 0.06, FR)
for y in (WY0, 1.78, WY1 - 0.06): box(-4.26, -4.19, y, y + 0.06, WZ0, WZ1, FR)
box(-4.2, -4.04, WY0 - 0.05, WY0, WZ0 - 0.06, WZ1 + 0.06, FR)
box(-4.2, -4.16, 1.0, 1.06, -2, 3.86, FR)                       # chair rail
# right wall with glass door
DZ0, DZ1, DY1 = 1.2, 2.2, 2.2
box(XR, 4.6, DY1, 3.9, -2, ZB, LW); box(XR, 4.6, 0, DY1, -2, DZ0, LW); box(XR, 4.6, 0, DY1, DZ1, ZB, LW)
box(4.22, 4.25, 0, DY1, DZ0, DZ1, mat(fn=window_fn, emit=1.1, shadow=False))
for z in (DZ0, 1.67, DZ1 - 0.06): box(4.19, 4.26, 0, DY1, z, z + 0.06, FR)
for y in (0.0, 0.55, 1.1, 1.62, DY1 - 0.06): box(4.19, 4.26, y, y + 0.07, DZ0, DZ1, FR)
box(4.16, 4.2, 1.0, 1.06, -2, DZ0, FR); box(4.16, 4.2, 1.0, 1.06, DZ1, 3.86, FR)
box(4.17, 4.2, 1.25, 2.0, 2.45, 2.95, mat((0.16, 0.45, 0.45)))   # poster right wall
box(4.165, 4.2, 1.2, 2.05, 2.4, 3.0, FR)
box(-4.2, -4.17, 1.3, 2.1, 3.05, 3.6, mat((0.80, 0.30, 0.16)))  # poster left wall
# cornice
CORN = mat(fn=wood((0.42, 0.23, 0.12), 0.6))
box(-4.2, 4.2, 3.2, 3.5, ZB - 0.12, ZB, CORN)

# ---- counter (toonbank)
CX0, CX1 = -4.2, 2.4
box(CX0, CX1, 0.1, 1.0, 3.05, 3.8, mat(fn=wood((0.62, 0.36, 0.18), 0.16)))
box(CX0, CX1, 0, 0.1, 3.12, 3.8, DARK)
box(CX0, CX1, 0.88, 0.95, 3.03, 3.05, RED)
box(CX0, CX1, 0.12, 0.18, 3.03, 3.05, mat((0.34, 0.18, 0.10)))
box(CX0, CX1 + 0.05, 1.0, 1.06, 2.95, 3.86, mat(fn=stone_fn))
box(CX0 + 0.1, CX1 - 0.1, 0.20, 0.235, 2.90, 2.935, mat((0.86, 0.66, 0.24)))  # brass foot rail
for x in np.arange(CX0 + 0.3, CX1, 1.05): box(x, x + 0.03, 0.2, 0.235, 2.92, 3.05, mat((0.70, 0.52, 0.2)))
box(-0.95, 0.75, 0.30, 0.82, 3.02, 3.05, mat(decal=D_sign))
box(-2.3, -1.75, 0.26, 0.84, 3.02, 3.05, mat(decal=D_poster_fries))
box(-3.5, -2.95, 0.26, 0.84, 3.02, 3.05, mat(decal=D_poster_burger))
# tray-return bin against the counter
box(1.72, 2.3, 0, 0.92, 2.62, 3.03, mat(fn=wood((0.50, 0.28, 0.14), 0.145)))
box(1.70, 2.32, 0.92, 0.96, 2.60, 3.03, STEEL)
cyl(2.01, 2.8, 0.955, 0.965, 0.13, BLACK)
box(1.78, 2.24, 0.965, 0.985, 2.66, 2.72, mat((0.55, 0.30, 0.16)))
# swing gate + customer fridge
box(2.47, 2.98, 0.22, 0.95, 3.4, 3.44, mat(fn=wood((0.66, 0.20, 0.13), 0.13)))
box(2.45, 2.47, 0, 1.0, 3.38, 3.46, DARK)
box(3.0, 4.1, 0, 2.0, 3.05, 3.75, mat((0.14, 0.14, 0.18), decal=D_fridge("FRISDRANK", 5)))

# ---- on the counter: snack vitrine
VX0, VX1, VZ0, VZ1, VY0, VY1 = -3.9, -1.4, 3.1, 3.7, 1.06, 1.6
box(VX0, VX1, VY0, VY0 + 0.04, VZ0, VZ1, STEEL)
box(VX0, VX1, VY0 + 0.04, VY1, VZ1 - 0.03, VZ1, mat((0.80, 0.78, 0.72)))
for x in (VX0, VX1 - 0.03, (VX0 + VX1) / 2 - 0.015):
    box(x, x + 0.03, VY0, VY1, VZ0, VZ0 + 0.03, CHROME)
for x in (VX0, VX1 - 0.03): box(x, x + 0.03, VY1 - 0.03, VY1, VZ0, VZ1, CHROME)
box(VX0, VX1, VY1 - 0.03, VY1, VZ0, VZ0 + 0.03, CHROME)
box(VX0, VX1, VY1 - 0.03, VY1, VZ1 - 0.05, VZ1, CHROME)
box(VX0 + 0.03, VX1 - 0.03, VY1 - 0.07, VY1 - 0.04, VZ0 + 0.03, VZ0 + 0.07, mat((1.0, 0.92, 0.7), emit=1.3, shadow=False))
GL = mat((1, 1, 1), glass=True, shadow=False)
box(VX0, VX1, VY0 + 0.04, VY1, VZ0 - 0.005, VZ0, GL)
box(VX0, VX1, VY1, VY1 + 0.005, VZ0, VZ1, GL)
ntr = 6; tw = (VX1 - VX0 - 0.1) / ntr
SN = [("stick", (0.47, 0.23, 0.11)), ("ball", (0.76, 0.48, 0.15)), ("stick", (0.74, 0.14, 0.10)),
      ("disc", (0.42, 0.22, 0.12)), ("stick", (0.86, 0.60, 0.20)), ("ball", (0.60, 0.34, 0.14))]
for i, (kind, c) in enumerate(SN):
    x0 = VX0 + 0.05 + i * tw + 0.02; x1 = x0 + tw - 0.04; y = VY0 + 0.04
    box(x0, x1, y, y + 0.02, 3.2, 3.62, mat((0.56, 0.55, 0.53)))
    y += 0.02
    V = lambda: mat(tuple(np.clip(A(*c) * rng.uniform(0.82, 1.15), 0, 1)))
    if kind == "stick":
        n = 5; dx = (x1 - x0 - 0.04) / n
        for j in range(n): box(x0 + 0.02 + j * dx, x0 + 0.02 + j * dx + dx * 0.8, y, y + 0.045, 3.23, 3.59, V())
        for j in range(n - 2): box(x0 + 0.05 + j * dx, x0 + 0.05 + j * dx + dx * 0.8, y + 0.045, y + 0.09, 3.3, 3.58, V())
    elif kind == "ball":
        for j in range(4):
            for q in range(4): ell(x0 + 0.055 + j * (x1 - x0 - 0.11) / 3, y + 0.035, 3.25 + q * 0.105, 0.04, 0.036, 0.04, V())
        for j in range(3):
            for q in range(2): ell(x0 + 0.1 + j * (x1 - x0 - 0.2) / 2, y + 0.09, 3.38 + q * 0.11, 0.04, 0.036, 0.04, V())
    else:
        for j in range(2):
            for q in range(3):
                cx_ = x0 + 0.09 + j * (x1 - x0 - 0.18); cz_ = 3.27 + q * 0.14
                cyl(cx_, cz_, y, y + 0.03, 0.065, mat((0.86, 0.62, 0.30))); cyl(cx_, cz_, y + 0.03, y + 0.05, 0.068, V())
                cyl(cx_, cz_, y + 0.05, y + 0.09, 0.062, mat((0.88, 0.60, 0.26)), r1=0.045)
    box((x0 + x1) / 2 - 0.05, (x0 + x1) / 2 + 0.05, VY0 + 0.04, VY0 + 0.085, 3.12, 3.13, WHITE)

# cash register, card terminal, bell
box(-0.95, -0.4, 1.06, 1.2, 3.3, 3.72, mat((0.20, 0.19, 0.22)))
box(-0.9, -0.45, 1.2, 1.5, 3.56, 3.62, mat((0.24, 0.23, 0.26)))
box(-0.84, -0.60, 1.21, 1.30, 3.28, 3.30, mat(decal=D_regdisp))
box(-0.86, -0.58, 1.06, 1.20, 3.295, 3.30, DARK)
box(-0.2, -0.06, 1.06, 1.10, 3.02, 3.2, DARK)
box(-0.18, -0.08, 1.10, 1.105, 3.04, 3.10, mat((0.4, 0.8, 0.95), emit=0.9, shadow=False))
cyl(0.28, 3.15, 1.06, 1.075, 0.07, DARK)
ell(0.28, 1.075, 3.15, 0.058, 0.055, 0.058, mat((0.95, 0.74, 0.25)))
cyl(0.28, 3.15, 1.12, 1.145, 0.012, DARK)
# sauce pumps
for x, c in ((0.75, (0.96, 0.90, 0.66)), (0.98, (0.78, 0.13, 0.08)), (1.21, (0.94, 0.50, 0.18))):
    cyl(x, 3.5, 1.06, 1.34, 0.08, mat(c)); cyl(x, 3.5, 1.14, 1.25, 0.083, WHITE)
    cyl(x, 3.5, 1.34, 1.36, 0.083, WHITE); cyl(x, 3.5, 1.36, 1.46, 0.014, CHROME)
    box(x - 0.012, x + 0.012, 1.44, 1.46, 3.36, 3.5, CHROME)
# napkins, forks
box(1.48, 1.68, 1.06, 1.24, 3.1, 3.26, STEEL); box(1.5, 1.66, 1.09, 1.21, 3.095, 3.1, WHITE)
cyl(1.88, 3.16, 1.06, 1.17, 0.045, RED)
for a in range(5): box(1.86 + a * 0.012 - 0.01, 1.865 + a * 0.012 - 0.01, 1.17, 1.22 + 0.02 * (a % 2), 3.14 + 0.01 * (a % 3), 3.15 + 0.01 * (a % 3), mat((0.86, 0.70, 0.45)))

def sticks(cx, cz, y, r, n, hmin, hmax, th):
    for _ in range(n):
        a = rng.uniform(0, 2 * np.pi); rr = r * math.sqrt(rng.uniform(0, 1))
        x = cx + rr * math.cos(a); z = cz + rr * math.sin(a)
        box(x - th / 2, x + th / 2, y, y + rng.uniform(hmin, hmax), z - th / 2, z + th / 2, FRY())

def fries_cone(cx, cz, y0, hgt=0.3, r=0.085):
    cyl(cx, cz, y0, y0 + hgt, 0.012, mat(fn=stripes_fn(cx, cz, 8, (0.96, 0.94, 0.88), (0.80, 0.16, 0.12))), r1=r)
    ell(cx, y0 + hgt, cz, r * 0.92, 0.03, r * 0.92, mat(fn=fries_fn))
    sticks(cx, cz, y0 + hgt - 0.02, r * 0.8, 12, 0.05, 0.13, 0.016)

# cone stand with two filled puntzakken
box(1.98, 2.36, 1.06, 1.08, 3.2, 3.42, STEEL); box(1.98, 2.36, 1.2, 1.215, 3.2, 3.42, STEEL)
for x in (1.985, 2.34): box(x, x + 0.015, 1.06, 1.2, 3.2, 3.42, STEEL)
fries_cone(2.08, 3.31, 1.09); fries_cone(2.26, 3.31, 1.09)
ell(2.08, 1.42, 3.29, 0.035, 0.025, 0.035, mat((0.97, 0.93, 0.74)))
# tray with a bakje on the counter
box(-1.3, -1.02, 1.06, 1.075, 3.08, 3.32, mat((0.60, 0.20, 0.14)))
cyl(-1.16, 3.2, 1.075, 1.14, 0.05, WHITE, r1=0.075)
ell(-1.16, 1.14, 3.2, 0.07, 0.025, 0.07, mat(fn=fries_fn)); sticks(-1.16, 3.2, 1.13, 0.06, 9, 0.03, 0.07, 0.014)

# ---- worker area, against the back wall
EZ = 5.65
box(-4.15, -3.2, 0, 2.0, 5.7, 6.6, mat((0.66, 0.65, 0.62), fn=STEELF, decal=D_freezer))
# fryer
box(-3.1, -1.1, 0, 0.9, EZ, 6.6, mat((0.68, 0.67, 0.64), fn=STEELF, decal=D_fryer))
box(-3.1, -1.1, 0.9, 1.3, 6.5, 6.6, STEEL)
for i in range(4):
    x = -3.03 + i * 0.49
    box(x, x + 0.4, 0.9, 0.906, 5.82, 6.4, mat(fn=oil_fn, emit=0.12))
N_BASKETS = len(prims)  # the mod draws the baskets: built here (keeps the random sequence), then dropped
x = -3.03
box(x + 0.05, x + 0.35, 0.906, 0.93, 5.88, 6.34, mat(fn=mesh_fn, emit=0.1))
box(x + 0.19, x + 0.21, 0.93, 0.955, 5.52, 5.9, BLACK)
x = -3.03 + 2 * 0.49
box(x + 0.05, x + 0.35, 1.0, 1.17, 5.95, 6.33, mat(fn=mesh_fn))
ell(x + 0.2, 1.17, 6.14, 0.15, 0.06, 0.19, mat(fn=fries_fn)); sticks(x + 0.2, 6.14, 1.17, 0.12, 14, 0.03, 0.09, 0.016)
box(x + 0.19, x + 0.21, 1.15, 1.18, 5.55, 5.97, BLACK)
box(x + 0.02, x + 0.38, 1.17, 1.19, 6.33, 6.5, CHROME)
del prims[N_BASKETS:]
# hood
box(-3.2, -1.0, 1.74, 2.1, 5.8, 6.6, mat(fn=hood_fn))
box(-3.2, -1.0, 1.70, 1.74, 5.76, 6.6, STEEL)
for x in (-2.7, -1.5): box(x - 0.15, x + 0.15, 1.685, 1.70, 6.0, 6.1, mat((1.0, 0.95, 0.8), emit=1.3, shadow=False))
# frietbak (salting station)
box(-1.0, 0.6, 0, 0.9, EZ, 6.6, mat((0.68, 0.67, 0.64), fn=STEELF, decal=D_doors(2, 8)))
box(-0.9, 0.3, 0.9, 0.98, 5.78, 6.45, STEEL)
box(-0.86, 0.26, 0.975, 0.985, 5.82, 6.41, mat(fn=fries_fn))
ell(-0.3, 0.98, 6.12, 0.52, 0.17, 0.27, mat(fn=fries_fn))
for _ in range(46):
    x = rng.uniform(-0.75, 0.15); z = rng.uniform(5.9, 6.34); y = 0.98 + 0.15 * max(0, 1 - ((x + 0.3) / 0.5) ** 2 - ((z - 6.12) / 0.26) ** 2)
    L = rng.uniform(0.07, 0.13)
    if rng.random() < 0.5: box(x, x + L, y, y + 0.022, z, z + 0.018, FRY())
    else: box(x, x + 0.018, y, y + 0.022, z, z + L, FRY())
cyl(0.46, 5.88, 0.9, 1.04, 0.04, CHROME); cyl(0.46, 5.88, 1.04, 1.06, 0.03, CHROME)
box(0.34, 0.58, 0.9, 0.93, 6.1, 6.4, STEEL)
for q in range(3): cyl(0.46, 6.25, 0.93 + q * 0.012, 0.99 + q * 0.012, 0.05, WHITE, r1=0.075)
for xl in (-0.6, 0.0):
    box(xl - 0.012, xl + 0.012, 1.74, 1.76, 6.12, 6.6, CHROME)
    cyl(xl, 6.12, 1.5, 1.74, 0.16, mat((0.80, 0.24, 0.10)), r1=0.045)
    cyl(xl, 6.12, 1.495, 1.5, 0.15, mat((1.0, 0.62, 0.2), emit=1.2, shadow=False))
ell(0.25, 2.02, ZB, 0.17, 0.17, 0.035, mat(fn=clock_fn(0.25, 2.02, 0.17)))
# prep counter with sauces
box(0.7, 2.3, 0, 0.9, EZ, 6.6, mat((0.68, 0.67, 0.64), fn=STEELF, decal=D_doors(3, 9)))
LAB = [(0.96, 0.84, 0.3), (0.80, 0.14, 0.1), (0.94, 0.5, 0.18), (0.3, 0.6, 0.3), (0.55, 0.3, 0.15)]
for i in range(4):
    x = 0.9 + i * 0.31
    cyl(x, 6.36, 0.9, 1.16, 0.115, mat(fn=bucket_fn(0.9, LAB[i])), r1=0.135); cyl(x, 6.36, 1.16, 1.18, 0.14, mat(LAB[i]))
box(0.78, 1.38, 0.9, 1.0, 5.75, 6.12, STEEL)                                   # bain-marie
for x in (0.93, 1.23): cyl(x, 5.93, 1.0, 1.015, 0.12, mat((0.80, 0.79, 0.75))); cyl(x, 5.93, 1.015, 1.04, 0.02, BLACK)
for i, c in enumerate(((0.80, 0.14, 0.1), (0.96, 0.84, 0.3), (0.94, 0.5, 0.18))):
    x = 1.56 + i * 0.11
    cyl(x, 5.82, 0.9, 1.07, 0.04, mat(c)); cyl(x, 5.82, 1.07, 1.13, 0.04, mat(c), r1=0.008)
box(1.9, 2.25, 0.9, 0.92, 5.74, 6.0, mat((0.84, 0.66, 0.42)))                  # cutting board
for q in range(4): cyl(2.08, 5.87, 0.92 + q * 0.012, 0.975 + q * 0.012, 0.05, WHITE, r1=0.078)
box(0.7, 2.3, 1.62, 1.66, 6.28, 6.6, STEEL)                                    # wall shelf
for x in (0.75, 2.22): box(x, x + 0.03, 1.5, 1.62, 6.4, 6.6, STEEL)
for i in range(3):
    x = 0.9 + i * 0.3
    cyl(x, 6.44, 1.66, 1.9, 0.11, mat(fn=bucket_fn(1.66, LAB[(i + 2) % 5])), r1=0.125); cyl(x, 6.44, 1.9, 1.92, 0.13, mat(LAB[(i + 2) % 5]))
box(1.68, 1.98, 1.66, 1.88, 6.32, 6.56, mat((0.72, 0.52, 0.30))); box(1.7, 1.96, 1.88, 2.0, 6.34, 6.54, mat((0.66, 0.46, 0.26)))
for i in range(2): cyl(2.1 + i * 0.1, 6.42, 1.66, 1.82, 0.045, mat((0.86, 0.72, 0.2)));
# back door + ticket number display
box(2.45, 3.4, 0, 2.1, 6.56, 6.6, mat((0.44, 0.2, 0.14), decal=D_backdoor))
box(2.4, 2.45, 0, 2.15, 6.54, 6.6, FR); box(3.4, 3.45, 0, 2.15, 6.54, 6.6, FR); box(2.4, 3.45, 2.1, 2.15, 6.54, 6.6, FR)
box(2.5, 3.35, 2.2, 2.44, 6.52, 6.6, mat((0.1, 0.08, 0.08), decal=D_led))
# potato crates
CR = mat(fn=wood((0.64, 0.44, 0.24), 0.11, axis=1, gaxis=0))
box(3.52, 4.16, 0, 0.42, 5.85, 6.55, CR); box(3.55, 4.14, 0.42, 0.84, 5.9, 6.52, CR); box(3.56, 4.12, 0.84, 1.24, 5.94, 6.5, CR)
box(3.6, 4.08, 1.2, 1.25, 5.98, 6.46, mat((0.30, 0.2, 0.12)))
for _ in range(16):
    ell(rng.uniform(3.68, 4.0), 1.27 + rng.uniform(0, 0.05), rng.uniform(6.05, 6.4), 0.075, 0.05, 0.06, mat(tuple(A(0.80, 0.62, 0.34) * rng.uniform(0.8, 1.1))))
# menu boards
MENUS = [("FRIETEN", [("KLEIN", "2,80"), ("MIDDEL", "3,30"), ("GROOT", "3,80"), ("FAMILIEPAK", "7,50")], (196, 40, 32)),
         ("SNACKS", [("FRIKANDEL", "2,20"), ("CERVELA", "3,00"), ("BOULET", "2,60"), ("BITTERBALLEN", "3,80")], (196, 40, 32)),
         ("BURGERS", [("HAMBURGER", "3,50"), ("CHEESEBURGER", "4,00"), ("KIPBURGER", "4,20"), ("STOOFVLEES", "5,50")], (196, 40, 32)),
         ("SAUZEN", [("MAYONAISE", "0,90"), ("ANDALOUSE", "0,90"), ("SAMURAI", "0,90"), ("STOOFVLEESSAUS", "1,50")], (196, 40, 32))]
for i, (t, it, ac) in enumerate(MENUS):
    x0 = -4.05 + i * 2.05
    box(x0, x0 + 1.95, 2.46, 3.16, 6.5, 6.6, mat((0.3, 0.16, 0.1), decal=D_menu(t, it, ac)))

# ---- customer area
# bench under the window
box(-4.2, -3.72, 0, 0.38, 0.9, 2.8, WOODD)
box(-4.2, -3.68, 0.38, 0.49, 0.9, 2.8, mat(fn=bench_fn))
box(-4.2, -4.07, 0.49, 0.96, 0.9, 2.8, mat(fn=bench_fn))
def table(x0, z0):
    box(x0, x0 + 0.72, 0.72, 0.76, z0, z0 + 0.62, mat((0.93, 0.88, 0.76)))
    box(x0 - 0.01, x0 + 0.73, 0.70, 0.72, z0 - 0.01, z0 + 0.63, RED)
    cyl(x0 + 0.36, z0 + 0.31, 0.03, 0.7, 0.04, CHROME); cyl(x0 + 0.36, z0 + 0.31, 0, 0.03, 0.22, DARK)
def chair(x, z):
    s = 0.19
    box(x - s, x + s, 0.42, 0.47, z - s, z + s, REDV)
    box(x + s - 0.04, x + s, 0.47, 0.9, z - s, z + s, REDV)
    for dx in (-s + 0.01, s - 0.04):
        for dz in (-s + 0.01, s - 0.04): box(x + dx, x + dx + 0.03, 0, 0.42, z + dz, z + dz + 0.03, CHROME)
table(-3.6, 1.0); table(-3.6, 2.02)
chair(-2.6, 1.3); chair(-2.62, 2.36)
# things on the tables
box(-3.5, -3.14, 0.76, 0.775, 1.1, 1.36, mat((0.60, 0.20, 0.14)))
cyl(-3.38, 1.22, 0.775, 0.84, 0.05, WHITE, r1=0.075); ell(-3.38, 0.84, 1.22, 0.07, 0.025, 0.07, mat(fn=fries_fn)); sticks(-3.38, 1.22, 0.83, 0.06, 9, 0.03, 0.07, 0.014)
cyl(-3.2, 1.3, 0.775, 0.9, 0.035, RED, r1=0.042)
cyl(-3.0, 1.48, 0.76, 0.92, 0.035, mat((0.80, 0.14, 0.1))); cyl(-3.0, 1.48, 0.92, 0.97, 0.035, mat((0.80, 0.14, 0.1)), r1=0.008)
cyl(-3.25, 2.5, 0.76, 0.92, 0.035, mat((0.96, 0.84, 0.3))); cyl(-3.25, 2.5, 0.92, 0.97, 0.035, mat((0.96, 0.84, 0.3)), r1=0.008)
cyl(-3.14, 2.52, 0.76, 0.92, 0.035, mat((0.80, 0.14, 0.1))); cyl(-3.14, 2.52, 0.92, 0.97, 0.035, mat((0.80, 0.14, 0.1)), r1=0.008)
box(-3.5, -3.36, 0.76, 0.88, 2.14, 2.24, STEEL); box(-3.49, -3.37, 0.79, 0.86, 2.135, 2.14, WHITE)
# standing table + stools
def stool(x, z):
    cyl(x, z, 0, 0.03, 0.2, DARK); cyl(x, z, 0.03, 0.7, 0.03, CHROME); cyl(x, z, 0.26, 0.28, 0.15, CHROME)
    cyl(x, z, 0.70, 0.725, 0.185, CHROME); cyl(x, z, 0.725, 0.79, 0.18, REDV, r1=0.165)
cyl(1.3, 1.2, 0, 0.03, 0.27, DARK); cyl(1.3, 1.2, 0.03, 1.04, 0.045, CHROME)
cyl(1.3, 1.2, 1.04, 1.06, 0.40, RED); cyl(1.3, 1.2, 1.06, 1.09, 0.39, mat((0.93, 0.88, 0.76)))
stool(0.66, 1.34); stool(1.92, 0.92)
box(1.12, 1.4, 1.09, 1.105, 1.0, 1.22, mat((0.60, 0.20, 0.14)))
fries_cone(1.2, 1.1, 1.105, 0.02, 0.07)
cyl(1.34, 1.12, 1.105, 1.22, 0.035, RED, r1=0.042)
cyl(1.5, 1.34, 1.09, 1.25, 0.035, mat((0.96, 0.84, 0.3))); cyl(1.5, 1.34, 1.25, 1.3, 0.035, mat((0.96, 0.84, 0.3)), r1=0.008)
# door mat
box(3.3, 4.15, 0, 0.015, 1.25, 2.15, mat(fn=mat_fn))
# giant fries cone statue
SX, SZ = 3.5, 0.72
cyl(SX, SZ, 0, 0.1, 0.3, DARK)
cyl(SX, SZ, 0.1, 1.05, 0.10, mat(fn=stripes_fn(SX, SZ, 10, (0.96, 0.94, 0.88), (0.80, 0.16, 0.12))), r1=0.36)
ell(SX, 1.05, SZ, 0.34, 0.12, 0.34, mat(fn=fries_fn))
for _ in range(22):
    a = rng.uniform(0, 2 * np.pi); rr = 0.27 * math.sqrt(rng.uniform(0, 1)); x = SX + rr * math.cos(a); z = SZ + rr * math.sin(a)
    box(x - 0.035, x + 0.035, 1.0, 1.0 + rng.uniform(0.22, 0.5), z - 0.035, z + 0.035, FRY())
ell(SX - 0.05, 1.42, SZ - 0.1, 0.16, 0.1, 0.14, mat((0.98, 0.95, 0.80)))
# plant, front-left
PX, PZ = -3.75, 0.42
cyl(PX, PZ, 0, 0.42, 0.15, mat((0.72, 0.36, 0.2)), r1=0.22); cyl(PX, PZ, 0.42, 0.44, 0.2, mat((0.22, 0.14, 0.1)))
GREENS = [(0.16, 0.66, 0.24), (0.30, 0.80, 0.26), (0.10, 0.50, 0.24), (0.46, 0.86, 0.28)]
for i in range(20):
    a_ = i * 2.4 + rng.uniform(-0.3, 0.3); lvl = i / 19.0
    rr = 0.10 + 0.26 * (1 - abs(lvl - 0.45) * 1.6) * rng.uniform(0.7, 1.0)
    hgt = 0.55 + 0.75 * lvl
    ell(PX + rr * math.cos(a_), hgt, PZ + rr * math.sin(a_), 0.05 + 0.13 * abs(math.cos(a_)), 0.035 + 0.05 * lvl, 0.05 + 0.11 * abs(math.sin(a_)), mat(fn=leaf_fn(GREENS[i % 4])))
cyl(PX, PZ, 0.44, 1.2, 0.02, mat((0.24, 0.36, 0.18)))

# ------------------------------------------------------------------ intersections
def isect(p, O, D):
    k = p["k"]
    if k == "box":
        inv = 1.0 / D
        t1 = (p["lo"] - O) * inv; t2 = (p["hi"] - O) * inv
        tn = np.minimum(t1, t2); tf = np.maximum(t1, t2)
        tmin = tn.max(1); tmax = tf.min(1)
        hit = (tmax >= tmin) & (tmin > EPS)
        t = np.where(hit, tmin, np.inf)
        ax = tn.argmax(1); n = np.zeros_like(D); idx = np.arange(len(D))
        n[idx, ax] = -np.sign(D[idx, ax])
        return t, n
    if k == "ell":
        Os = (O - p["c"]) / p["r"]; Ds = D / p["r"]
        a = (Ds * Ds).sum(1); b = 2 * (Os * Ds).sum(1); c = (Os * Os).sum(-1) - 1
        disc = b * b - 4 * a * c; ok = disc > 0
        t = (-b - np.sqrt(np.where(ok, disc, 0))) / (2 * a)
        ok &= t > EPS
        Pn = (Os + t[:, None] * Ds) / p["r"]
        Pn /= np.maximum(np.linalg.norm(Pn, axis=1, keepdims=True), 1e-9)
        return np.where(ok, t, np.inf), Pn
    cx, cz, y0, y1, r0, r1 = p["cx"], p["cz"], p["y0"], p["y1"], p["r0"], p["r1"]
    Ob = np.broadcast_to(O, D.shape)
    ox = Ob[:, 0] - cx; oz = Ob[:, 2] - cz; oy = Ob[:, 1] - y0
    dx, dy, dz = D[:, 0], D[:, 1], D[:, 2]
    kk = (r1 - r0) / (y1 - y0); R0 = r0 + kk * oy
    a = dx * dx + dz * dz - kk * kk * dy * dy
    b = 2 * (ox * dx + oz * dz - kk * R0 * dy)
    c = ox * ox + oz * oz - R0 * R0
    disc = b * b - 4 * a * c; ok = disc > 0
    sq = np.sqrt(np.where(ok, disc, 0)); a = np.where(np.abs(a) < 1e-9, 1e-9, a)
    ts = np.minimum((-b - sq) / (2 * a), (-b + sq) / (2 * a))
    y = oy + ts * dy
    oks = ok & (ts > EPS) & (y >= 0) & (y <= y1 - y0)
    t = np.where(oks, ts, np.inf)
    n = np.stack([ox + ts * dx, -kk * (r0 + kk * y), oz + ts * dz], 1)
    for yc, rc, ny in ((y1 - y0, r1, 1.0), (0.0, r0, -1.0)):
        tc = (yc - oy) / dy
        qx = ox + tc * dx; qz = oz + tc * dz
        okc = (tc > EPS) & (qx * qx + qz * qz <= rc * rc) & (tc < t)
        t = np.where(okc, tc, t); n[okc] = (0, ny, 0)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    return t, n

def aabb(p):
    if p["k"] == "box": return p["lo"], p["hi"]
    if p["k"] == "ell": return p["c"] - p["r"], p["c"] + p["r"]
    r = max(p["r0"], p["r1"])
    return A(p["cx"] - r, p["y0"], p["cz"] - r), A(p["cx"] + r, p["y1"], p["cz"] + r)
for p in prims:
    lo, hi = aabb(p)
    p["corn"] = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])

# ------------------------------------------------------------------ primary rays
t0 = time.time()
jj, ii = np.mgrid[0:CH, 0:W]
xs = (ii + 0.5) / W * 2 - 1; ys = 1 - (jj + 0.5) / H * 2
Dimg = fwd[None, None, :] + right[None, None, :] * (xs * TANH)[..., None] + up[None, None, :] * (ys * TANV)[..., None]
Dimg /= np.linalg.norm(Dimg, axis=2, keepdims=True)
Dimg[np.abs(Dimg) < 1e-7] = 1e-7

def trace_primary(sel):
    bt = np.full((CH, W), np.inf); bid = np.full((CH, W), -1, np.int32); bn = np.zeros((CH, W, 3))
    for k, p in enumerate(prims):
        if not sel(p): continue
        px, py = proj(p["corn"])
        x0 = max(0, int(px.min()) - 2); x1 = min(W, int(px.max()) + 3)
        y0 = max(0, int(py.min()) - 2); y1 = min(CH, int(py.max()) + 3)
        if x0 >= x1 or y0 >= y1: continue
        t, n = isect(p, CAM, Dimg[y0:y1, x0:x1].reshape(-1, 3))
        t = t.reshape(y1 - y0, x1 - x0); n = n.reshape(y1 - y0, x1 - x0, 3)
        m = t < bt[y0:y1, x0:x1]
        bt[y0:y1, x0:x1][m] = t[m]; bid[y0:y1, x0:x1][m] = k; bn[y0:y1, x0:x1][m] = n[m]
    return bt, bid, bn

bt, bid, bn = trace_primary(lambda p: not p["m"]["glass"] and not p["m"]["sunonly"])
hitm = bid >= 0
P = CAM[None, None, :] + Dimg * np.where(hitm, bt, 0)[..., None]
print("primary", round(time.time() - t0, 1), "s, prims:", len(prims))

# ------------------------------------------------------------------ albedo / emission
alb = np.zeros((CH, W, 3)); emi = np.zeros((CH, W))
for k in np.unique(bid[hitm]):
    p = prims[k]; m = p["m"]; mask = bid == k
    Pk = P[mask]; Nk = bn[mask]
    col = m["fn"](Pk, Nk) if m["fn"] is not None else np.tile(m["col"], (len(Pk), 1))
    em = np.full(len(Pk), float(m["emit"]))
    if m["decal"] is not None:
        lo, hi = p["lo"], p["hi"]
        px, py = proj(np.array([[lo[0], hi[1], lo[2]], [lo[0], lo[1], lo[2]], [hi[0], hi[1], lo[2]], [hi[0], lo[1], lo[2]]]))
        x0 = int(round(px[:2].min())); x1 = int(round(px[2:].max())); y0 = int(round(py[[0, 2]].min())); y1 = int(round(py[[1, 3]].max()))
        w = max(4, x1 - x0); h = max(4, y1 - y0)
        im, e = m["decal"](w, h)
        tex = np.asarray(im, np.float64) / 255.0
        f = Nk[:, 2] < -0.5
        u = np.clip(ii[mask][f] - x0, 0, w - 1); v = np.clip(jj[mask][f] - y0, 0, h - 1)
        col[f] = tex[v, u]
        em[f] = e[v, u] if isinstance(e, np.ndarray) else e
    alb[mask] = col; emi[mask] = em

# ------------------------------------------------------------------ lighting
Pf = P[hitm]; Nf = bn[hitm]
SUNC = [p for p in prims if p["m"]["shadow"] and not p["m"]["glass"]]
SKYC = [p for p in SUNC if not p["m"]["sunonly"]]

def occluded(Pp, Np, d, casters):
    d = d / np.linalg.norm(d)
    e1 = np.cross(d, A(0, 1, 0) if abs(d[1]) < 0.9 else A(1, 0, 0)); e1 /= np.linalg.norm(e1); e2 = np.cross(d, e1)
    O = Pp + Np * 4e-3
    a = O @ e1; b = O @ e2; s = O @ d
    occ = np.zeros(len(O), bool)
    for p in casters:
        c = p["corn"]; ca = c @ e1; cb = c @ e2; cs = c @ d
        m = (a >= ca.min()) & (a <= ca.max()) & (b >= cb.min()) & (b <= cb.max()) & (s < cs.max()) & ~occ
        idx = np.nonzero(m)[0]
        if len(idx) == 0: continue
        Dd = np.tile(np.where(np.abs(d) < 1e-7, 1e-7, d), (len(idx), 1))
        t, _ = isect(p, O[idx], Dd)
        occ[idx[np.isfinite(t)]] = True
    return occ

light = np.tile(A(0.19, 0.14, 0.18), (len(Pf), 1))
SKY = A(1.0, 0.82, 0.62) * 0.78
dirs = [(A(0, 1, 0), 0.30)]
for k in range(6):
    ph = math.radians(20 + 60 * k); el = math.radians(52)
    dirs.append((A(math.cos(el) * math.cos(ph), math.sin(el), math.cos(el) * math.sin(ph)), 0.14))
for d, wgt in dirs:
    nd = Nf @ d; m = nd > 0.01
    idx = np.nonzero(m)[0]
    occ = occluded(Pf[idx], Nf[idx], d, SKYC)
    lit = idx[~occ]
    light[lit] += SKY * (wgt * nd[lit] * 1.6)[:, None]
SUN = A(-0.80, 0.50, -0.33); SUN /= np.linalg.norm(SUN)
nd = Nf @ SUN; idx = np.nonzero(nd > 0.01)[0]
occ = occluded(Pf[idx], Nf[idx], SUN, SUNC)
lit = idx[~occ]
sunmask = np.zeros(len(Pf)); sunmask[lit] = nd[lit]
light += A(3.6, 1.9, 0.70) * sunmask[:, None]
print("shadows", round(time.time() - t0, 1), "s")

POINTS = [((-3.0, 2.55, 6.1), (1.0, 0.82, 0.5), 0.55, 1.3), ((-1.0, 2.55, 6.1), (1.0, 0.82, 0.5), 0.55, 1.3),
          ((1.1, 2.55, 6.1), (1.0, 0.82, 0.5), 0.55, 1.3), ((3.1, 2.55, 6.1), (1.0, 0.82, 0.5), 0.55, 1.3),
          ((-2.1, 1.62, 6.05), (1.0, 0.92, 0.75), 1.0, 0.8), ((-0.3, 1.42, 6.12), (1.0, 0.45, 0.12), 1.7, 0.6),
          ((-2.65, 1.5, 3.3), (1.0, 0.86, 0.6), 1.2, 0.45), ((3.55, 1.0, 2.55), (0.35, 0.85, 0.95), 0.9, 1.0),
          ((-2.0, 0.35, 2.3), (1.0, 0.6, 0.3), 0.45, 1.6), ((3.6, 1.2, 1.7), (1.0, 0.72, 0.40), 0.85, 1.3),
          ((-3.5, 1.7, 1.8), (1.0, 0.70, 0.36), 0.95, 1.5), ((0.0, 2.2, 4.9), (1.0, 0.88, 0.70), 1.0, 2.4), ((-2.6, 2.0, 5.0), (1.0, 0.88, 0.70), 0.5, 1.6), ((2.2, 2.0, 5.0), (1.0, 0.88, 0.70), 0.5, 1.6)]
for pos, c, inten, rad in POINTS:
    v = A(*pos) - Pf; dist = np.linalg.norm(v, axis=1)
    nl = np.clip((Nf * v).sum(1) / np.maximum(dist, 1e-6), 0, 1)
    light += A(*c) * (inten * (0.25 + 0.75 * nl) / (1 + (dist / rad) ** 2) ** 2)[:, None]

col = np.zeros((CH, W, 3)); af = alb[hitm]; ef = emi[hitm]
col[hitm] = af * light * (1 - 0.8 * np.clip(ef, 0, 1))[:, None] + af * ef[:, None]
emap = np.zeros((CH, W, 3)); emap[hitm] = af * ef[:, None]

# ------------------------------------------------------------------ sun beams (dusty light)
bayer = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.47)
dm = np.tile(bayer, (CH // 4 + 1, W // 4 + 1))[:CH, :W]
NS = 20
tz0 = (-0.4 - CAM[2]) / Dimg[..., 2]
tend = np.where(hitm, bt, tz0); tstart = np.minimum(tz0, tend)
acc = np.zeros((CH, W)); zero = np.zeros((CH * W, 3))
for si in range(NS):
    tt = tstart + (tend - tstart) * ((si + dm + 0.47) / NS)
    Ps = (CAM[None, None, :] + Dimg * tt[..., None]).reshape(-1, 3)
    acc += (~occluded(Ps, zero, SUN, SUNC)).reshape(CH, W) * (tend - tstart) / NS
col += acc[..., None] * A(1.0, 0.70, 0.34) * 0.13
print("beams", round(time.time() - t0, 1), "s")

# ------------------------------------------------------------------ glass overlay
gt, gid, gn = trace_primary(lambda p: p["m"]["glass"])
gm = gt < bt
if gm.any():
    Pg = CAM + Dimg[gm] * gt[gm][:, None]
    streak = (((Pg[:, 0] * 1.0 + Pg[:, 1] * 1.6) / 0.42) % 1) < 0.16
    col[gm] = col[gm] * 0.90 + A(0.05, 0.06, 0.06) + streak[:, None] * 0.13

# ------------------------------------------------------------------ post
img = 1 - np.exp(-np.clip(col, 0, None) * 1.45)
# outlines on the far side of depth edges, highlights on top edges
edge = np.zeros((CH, W), bool)
for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
    nid = np.roll(bid, (dy, dx), (0, 1)); nt = np.roll(bt, (dy, dx), (0, 1))
    edge |= (nid != bid) & (bt > nt + 0.03)
img[edge & (emi < 0.5)] *= 0.70
below_n = np.roll(bn, -1, 0); below_id = np.roll(bid, -1, 0)
hl = (below_id == bid) & (bn[..., 1] > 0.9) & (below_n[..., 1] < 0.5)
img[hl] = np.clip(img[hl] * 1.18 + 0.03, 0, 1)
# bloom from emissive surfaces
E = Image.fromarray((np.clip(emap, 0, 1) * 255).astype(np.uint8))
g1 = np.asarray(E.filter(ImageFilter.GaussianBlur(W / 640 * 3)), np.float64) / 255
g2 = np.asarray(E.filter(ImageFilter.GaussianBlur(W / 640 * 10)), np.float64) / 255
glow = 0.45 * g1 + 0.55 * g2
img = img + glow * (1 - img) * 0.85
# grade: warm shadows, a little extra saturation
lum = img.mean(2, keepdims=True)
img = lum + (img - lum) * 1.22

img = img + ((1 - np.clip(lum, 0, 1)) ** 3) * A(0.06, 0.015, 0.04)
img = np.clip(img, 0, 1)
img = np.clip(img * img * (3 - 2 * img) * 0.55 + img * 0.45, 0, 1)
# ordered dither + palette reduction
img8 = (np.clip(img + dm[..., None] * 0.035, 0, 1) * 255).astype(np.uint8)
frame = Image.fromarray(img8[:H]).quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
pim = Image.fromarray(img8).quantize(palette=frame, dither=Image.Dither.NONE).convert("RGB")
pim.paste(frame.convert("RGB"), (0, 0))

S = 1920 // W
pim.save(OUT + "_1x.png")
pim.resize((W * S, CH * S), Image.NEAREST).save(OUT + ".png")
# overlays so characters can be drawn behind the counter / behind the front furniture
rgba = np.dstack([np.asarray(pim), np.zeros((CH, W), np.uint8)])
# front: whole objects standing in front of the customers, never the floor, walls or door mat
zc = np.array([(p["corn"][:, 2].min() + p["corn"][:, 2].max()) / 2 for p in prims])
flat = np.array([p["m"]["fn"] in (floor_fn, sidewall_fn, backwall_fn, mat_fn, window_fn) or p["m"] is FR for p in prims])
front = hitm & ((zc < 2.5) & ~flat)[bid]
LAYERS = {"counter_overlay": hitm & (P[..., 2] < 3.9), "front_overlay": front}
for name, mask in LAYERS.items():
    a = rgba.copy(); a[..., 3] = 255; a[~mask] = 0
    LAYERS[name] = Image.fromarray(a, "RGBA")
    LAYERS[name].resize((W * S, CH * S), Image.NEAREST).save(f"{OUT}_{name}.png")

# ------------------------------------------------------------------ anchors (native pixels, from the same proj())
def at(x, y, z):
    a, b = proj((x, y, z)); return [round(float(a) * 640 / W), round(float(b) * 640 / W)]
def stand(x, z): return {"feet": at(x, 0, z), "head": at(x, 1.7, z)}
def rect(x0, x1, y0, y1, z):
    a = at(x0, y1, z); b = at(x1, y0, z); return {"x": a[0], "y": a[1], "w": b[0] - a[0], "h": b[1] - a[1]}
SLOT_X = (-2.05, -1.18, -0.32, 0.54, 1.4); SLOT_Z = 2.56
ANCHORS = {
    "note": "Generated by tools/scene.py. Native pixels (640x360); multiply by the scale.",
    "size": [640, 360],
    "stage": [640, 400],
    "core": [40, 600, 325],
    "customer_slots": [stand(x, SLOT_Z) | {"done": at(x + 0.36, 1.06, 3.1), "worker": at(x, 0, 4.5)} for x in SLOT_X],
    "customer_entry": stand(4.0, 1.75),
    "customer_lane": stand(3.2, 2.1),
    "customer_queue": [stand(2.75, 1.95), stand(2.2, 1.95)],
    "worker_rest": [at(-0.65, 0, 4.6), at(1.35, 0, 4.6)],
    "worker_freezer": at(-3.45, 0, 5.25),
    "worker_fryer": [at(-3.03 + i * 0.49 + 0.2, 0, 5.2) for i in range(4)],
    "worker_frietbak": at(-0.3, 0, 5.2),
    "baskets": [at(-3.03 + i * 0.49 + 0.2, 0.906, 6.11) for i in range(4)],
    "hang": [at(-3.03 + i * 0.49 + 0.2, 1.05, 6.14) for i in range(4)],
    "freezer_door": at(-3.67, 1.3, 5.7),
    "bell": at(0.28, 1.1, 3.15),
    "oil": at(-0.98, 0, 5.4),
    "ticket_display": rect(2.5, 3.35, 2.2, 2.44, 6.52),
    "register_display": rect(-0.84, -0.60, 1.21, 1.30, 3.28),
}
if __name__ == "__main__" or globals().get("BAKE"):
    with open(os.path.join(ROOT, "assets", "anchors.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(ANCHORS, f, indent=1)
    with open(os.path.join(ROOT, "mods", "frituur", "anchors-data.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("// Generated by tools/scene.py: positions in native pixels (640x360).\nexport const ANCHORS = "
                + json.dumps(ANCHORS, separators=(",", ":")) + ";\n")
    # 1:1 art for every scale: Herdr smooths scaled images, so nothing may be scaled on screen
    for k in (2, 3, 4):
        d = os.path.join(ROOT, "mods", "frituur", "art", f"{k}x"); os.makedirs(d, exist_ok=True)
        for name, im in [("scene", pim)] + list(LAYERS.items()):
            im.resize((W * k, CH * k), Image.NEAREST).save(os.path.join(d, name + ".png"), optimize=True)
print("done", round(time.time() - t0, 1), "s")
