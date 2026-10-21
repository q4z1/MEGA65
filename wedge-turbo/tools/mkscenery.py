#!/usr/bin/env python3
"""Wedge Turbo's scenery: trees, rocks, signs and billboards of our own,
drawn at build time.

Every object type keeps the place it has in the race - its bank's 17
sizes, its colours: the race view's 0-7 and the type's own 8-11
(tab_object_colours, which the race loads as the object comes near; the
snowy trees and bushes share the green ones' images and are white by their
colours). What it shows is new: drawn four times as large in those colours
and brought down to each size.

bank(type, dims) gives a bank's images, gate(images) the start gate's;
sign_banks() those of the signs drawn elsewhere (art/signs).
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

CLEAR = 0xFF
BLACK, LIGHT_RED, RED, DARK_RED, DARK_GREY, GREY, LIGHT_GREY, DARK_GREEN = range(8)
C8, C9, C10, C11 = 8, 9, 10, 11  # the type's own colours

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'toolchain', 'fonts')


def font(size, name='Rajdhani-Bold.ttf'):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


# ------------------------------------------------------------ drawing kit

class Pen:
    """A canvas of colour numbers, w x h, its bottom row the ground"""

    def __init__(self, w, h, rng):
        self.img = Image.new('L', (w, h), CLEAR)
        self.d = ImageDraw.Draw(self.img)
        self.d.fontmode = '1'  # no smoothing: crisp writing
        self.w, self.h, self.rng = w, h, rng

    def rect(self, x0, y0, x1, y1, c, outline=None, width=1):
        if x1 >= x0 and y1 >= y0:  # (nothing left of it in the smallest sizes)
            self.d.rectangle([x0, y0, x1, y1], fill=c, outline=outline, width=width)

    def poly(self, pts, c):
        self.d.polygon(pts, fill=c)

    def ellipse(self, x0, y0, x1, y1, c):
        if x1 >= x0 and y1 >= y0:
            self.d.ellipse([x0, y0, x1, y1], fill=c)

    def line(self, pts, c, width):
        self.d.line(pts, fill=c, width=width)

    def text(self, xy, s, size, c, name='Exo2.ttf', anchor='mm'):
        if size >= 4:
            f = font(size, name)
            if name == 'Exo2.ttf':
                f.set_variation_by_axes([800])
            self.d.text(xy, s, fill=c, font=f, anchor=anchor)

    def blob(self, cx, cy, r, c, lumps=9, rough=0.25):
        """A round shape with a lumpy edge"""
        pts = []
        phase = self.rng.uniform(0, 6.3)
        for k in range(lumps * 4):
            a = 2 * math.pi * k / (lumps * 4)
            rr = r * (1 + rough * math.sin(lumps * a + phase) * self.rng.uniform(0.6, 1.0))
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a) * 0.9))
        self.poly(pts, c)

    def posts(self, xs, top, c=DARK_GREY, width=None):
        """Posts down to the ground: lit on the left, a shadow at the foot"""
        width = width or max(1, round(self.w / 28))
        for x in xs:
            x0 = int(x - width / 2)
            self.rect(x0, top, x0 + width - 1, self.h - 1, c)
            if width >= 2:
                self.rect(x0, top, x0, self.h - 1, GREY if c != GREY else LIGHT_GREY)
            self.rect(x0 - 1, self.h - 1, x0 + width + 1, self.h - 1, BLACK)

    def bevel(self, x0, y0, x1, y1):
        """A frame's edges: black around, lit at the top and left, in shade
        at the bottom and right"""
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        if x1 < x0 or y1 < y0:
            return
        self.d.rectangle([x0, y0, x1, y1], outline=BLACK)
        if x1 - x0 > 6 and y1 - y0 > 6:
            self.d.line([(x0 + 1, y1 - 1), (x0 + 1, y0 + 1), (x1 - 1, y0 + 1)], fill=LIGHT_GREY)
            self.d.line([(x0 + 2, y1 - 1), (x1 - 1, y1 - 1), (x1 - 1, y0 + 2)], fill=DARK_GREY)


def outline(px, w, h):
    """The edge of a shape (a pixel next to the clear) in black"""
    px = bytearray(px)

    def clear(x, y):
        return x < 0 or x >= w or y < 0 or px[y * w + x] == CLEAR

    edge = [i for i in range(w * h) if px[i] != CLEAR and
            (clear(i % w - 1, i // w) or clear(i % w + 1, i // w) or clear(i % w, i // w - 1))]
    for i in edge:
        px[i] = BLACK
    return bytes(px)


def reduce(img, w, h):
    """img (w * 4 x h * 4) down to w x h: per 4 x 4 the colour most have -
    the small details (light greys, reds) count double - clear if most are"""
    px = img.load()
    out = bytearray()
    for y in range(h):
        for x in range(w):
            count = {}
            for dy in range(4):
                for dx in range(4):
                    v = px[x * 4 + dx, y * 4 + dy]
                    k = 2 if v in (LIGHT_GREY, LIGHT_RED, RED, C8) else 1
                    count[v] = count.get(v, 0) + k
            clear = count.pop(CLEAR, 0)
            out.append(CLEAR if clear > 8 or not count else max(count, key=count.get))
    return bytes(out)


# ------------------------------------------------------------ signs

def chevrons(p, right):
    """A red board, white arrows (to the side of the bend), on two legs"""
    w, h = p.w, p.h
    p.posts((w * 0.25, w * 0.75), h * 0.6, BLACK)
    p.rect(0, 0, w - 1, h * 0.72, RED, outline=BLACK, width=max(2, w // 40))
    for k in range(3):
        cx = w * (0.22 + 0.28 * k)
        s = h * 0.22
        pts = [(cx - s * 0.6, h * 0.36 - s), (cx + s * 0.3, h * 0.36), (cx - s * 0.6, h * 0.36 + s),
               (cx - s * 0.1, h * 0.36 + s), (cx + s * 0.8, h * 0.36), (cx - s * 0.1, h * 0.36 - s)]
        if not right:
            pts = [(w - 1 - x, y) for x, y in pts]
        p.poly(pts, LIGHT_GREY)


def roadworks(p):
    """An orange diamond on a post: a man with a shovel"""
    w, h = p.w, p.h
    p.posts((w / 2,), h * 0.5)
    c = (w / 2, h * 0.42)
    r = min(w, h) * 0.42
    p.poly([(c[0], c[1] - r), (c[0] + r, c[1]), (c[0], c[1] + r), (c[0] - r, c[1])], BLACK)
    r2 = r * 0.86
    p.poly([(c[0], c[1] - r2), (c[0] + r2, c[1]), (c[0], c[1] + r2), (c[0] - r2, c[1])], C8)
    s = r * 0.12
    p.ellipse(c[0] - s * 2.2, c[1] - s * 4.4, c[0] - s * 0.4, c[1] - s * 2.6, BLACK)
    p.line([(c[0] - s * 1.3, c[1] - s * 2.4), (c[0] - s * 0.4, c[1] + s * 0.6)], BLACK, int(s * 1.3))
    p.line([(c[0] - s * 0.4, c[1] + s * 0.6), (c[0] - s * 1.8, c[1] + s * 3)], BLACK, int(s))
    p.line([(c[0] - s * 0.4, c[1] + s * 0.6), (c[0] + s * 0.8, c[1] + s * 3)], BLACK, int(s))
    p.line([(c[0] - s * 1.2, c[1] - s * 1.5), (c[0] + s * 2.6, c[1] + s * 1.6)], BLACK, int(s * 0.7))
    p.poly([(c[0] + s * 2.2, c[1] + s * 1.4), (c[0] + s * 3.4, c[1] + s * 1.6), (c[0] + s * 2.8, c[1] + s * 2.6)],
           BLACK)


def badge(p, txt):
    """A board with a monogram, in greys"""
    w, h = p.w, p.h
    p.posts((w * 0.3, w * 0.7), h * 0.6)
    p.rect(w * 0.04, h * 0.04, w * 0.96, h * 0.72, BLACK, outline=GREY, width=max(3, w // 30))
    p.rect(w * 0.1, h * 0.12, w * 0.9, h * 0.64, DARK_GREY)
    for k, c in enumerate((RED, LIGHT_RED, LIGHT_GREY)):
        y = h * (0.16 + 0.05 * k)
        p.rect(w * 0.14, y, w * 0.86, y + h * 0.03, c)
    p.text((w / 2, h * 0.47), txt, int(h * 0.3), LIGHT_GREY)


def pit_sign(p):
    """A round orange sign on a post: P for the pits"""
    w, h = p.w, p.h
    p.posts((w / 2,), h * 0.5)
    r = w * 0.45
    p.ellipse(w / 2 - r, h * 0.05, w / 2 + r, h * 0.05 + 2 * r, BLACK)
    r2 = r * 0.84
    p.ellipse(w / 2 - r2, h * 0.05 + r - r2, w / 2 + r2, h * 0.05 + r + r2, C8)
    p.text((w / 2, h * 0.05 + r), 'P', int(r * 1.5), BLACK)


def warning(p):
    """A red triangle on a post: falling rocks"""
    w, h = p.w, p.h
    p.posts((w / 2,), h * 0.6)
    p.poly([(w / 2, 0), (w - 1, h * 0.72), (0, h * 0.72)], RED)
    p.poly([(w / 2, h * 0.16), (w * 0.84, h * 0.64), (w * 0.16, h * 0.64)], LIGHT_GREY)
    for cx, cy, r in ((w * 0.45, h * 0.44, w * 0.06), (w * 0.56, h * 0.53, w * 0.05), (w * 0.4, h * 0.56, w * 0.04)):
        p.ellipse(cx - r, cy - r, cx + r, cy + r, BLACK)


def barrier(p):
    """A barrier across the lane: yellow and black, a lamp on top"""
    w, h = p.w, p.h
    p.posts((w * 0.15, w * 0.85), h * 0.3, DARK_GREY)
    p.rect(0, h * 0.3, w - 1, h * 0.62, C10)
    step = w / 6
    for k in range(-1, 7):
        x = k * step
        p.poly([(x, h * 0.62), (x + step * 0.5, h * 0.62), (x + step, h * 0.3), (x + step * 0.5, h * 0.3)], BLACK)
    p.rect(0, h * 0.3, w - 1, h * 0.62, None, outline=BLACK, width=2)
    p.ellipse(w * 0.44, h * 0.06, w * 0.56, h * 0.28, C10)


def keep_side(p, right):
    """A white square sign, a blue arrow down to the side to drive"""
    w, h = p.w, p.h
    p.posts((w / 2,), h * 0.5)
    p.rect(w * 0.08, 0, w * 0.92, h * 0.78, C11, outline=LIGHT_GREY, width=max(3, w // 16))
    pts = [(0.3, 0.2), (0.62, 0.52), (0.62, 0.34), (0.74, 0.34), (0.74, 0.66), (0.42, 0.66), (0.42, 0.54),
           (0.54, 0.54), (0.22, 0.28)]
    if not right:
        pts = [(1 - x, y) for x, y in pts]
    p.poly([(x * w, y * h) for x, y in pts], LIGHT_GREY)


def puddle(p, c):
    """A flat puddle with a lighter rim"""
    w, h = p.w, p.h
    p.ellipse(0, h * 0.1, w - 1, h - 1, c)
    for _ in range(4):
        x = p.rng.uniform(0.1, 0.8) * w
        p.ellipse(x, h * 0.3, x + w * 0.15, h * 0.6, CLEAR if c == BLACK else c)
    p.ellipse(w * 0.2, h * 0.25, w * 0.5, h * 0.5, DARK_GREY if c == BLACK else LIGHT_GREY)


# ------------------------------------------------------------ plants and rocks

def clumps(p, cx, cy, rx, ry, r, lit, shade, dense=1.0):
    """Leaves as many small clumps on a crown round (cx, cy): the crown in
    shade, each clump with a lit top left (lit) - the light from the upper
    left, more lit up there, more shade down on the right, a few dark
    holes there"""
    pts = []
    for k in range(48):
        a = 2 * math.pi * k / 48
        f = 0.92 + 0.08 * math.sin(7 * a + p.rng.uniform(0, 1))
        pts.append((cx + math.cos(a) * rx * f, cy + math.sin(a) * ry * f))
    p.poly(pts, shade)
    n = int(dense * 1.6 * rx * ry / (r * r))
    spots = []
    for _ in range(n):
        a = p.rng.uniform(0, 2 * math.pi)
        d = math.sqrt(p.rng.random())
        spots.append((cx + math.cos(a) * rx * d, cy + math.sin(a) * ry * d, r * p.rng.uniform(0.75, 1.1)))
    spots.sort(key=lambda s: s[1])
    for x, y, rr in spots:
        u, v = (x - cx) / rx, (y - cy) / ry
        if u + v > 0.9 and p.rng.random() < 0.35:
            p.blob(x, y, rr * 0.55, BLACK, lumps=5, rough=0.3)
            continue
        p.blob(x, y, rr, shade, lumps=6, rough=0.3)
        t = 0.55 - 0.45 * u - 0.5 * v
        if t > 0.12:
            p.blob(x - rr * 0.25, y - rr * 0.3, rr * min(0.85, t + 0.1), lit, lumps=5, rough=0.3)


def fir(p):
    """A fir: tiers of drooping branches, their ends jagged, lit (10) on the
    left, in shade (DARK_GREEN) on the right, black under each tier"""
    w, h = p.w, p.h
    p.rect(w * 0.46, h * 0.8, w * 0.54, h - 1, C11)
    p.rect(w * 0.5, h * 0.8, w * 0.54, h - 1, C9)
    tiers = 7
    for k in range(tiers):
        top = h * (0.0 + 0.105 * k)
        bottom = h * (0.2 + 0.105 * k) if k < tiers - 1 else h * 0.86
        half = w * (0.1 + 0.058 * k)
        teeth = 5 + k
        edge = []
        for j in range(teeth * 2 + 1):
            x = w / 2 - half + 2 * half * j / (teeth * 2)
            sag = (1 - ((x - w / 2) / half) ** 2) * h * 0.02  # the branch ends hang
            y = bottom - (h * 0.035 if j % 2 else 0) + sag * 0
            edge.append((x, y - sag))
        apex = (w / 2, top)
        p.poly([apex] + [(x, y + h * 0.012) for x, y in edge], BLACK)
        p.poly([apex] + edge, DARK_GREEN)
        lit = [(x, y) for x, y in edge if x <= w / 2 + half * 0.1]
        p.poly([(w / 2 + half * 0.1, top + h * 0.02)] + [(x, y - h * 0.008) for x, y in lit], C10)
        for _ in range(int(teeth * 1.5)):  # needles
            x = p.rng.uniform(w / 2 - half * 0.9, w / 2 + half * 0.9)
            y = p.rng.uniform(top + (bottom - top) * 0.35, bottom - h * 0.03)
            if abs(x - w / 2) > half * (y - top) / (bottom - top):
                continue
            c = DARK_GREEN if x < w / 2 else C10
            p.line([(x, y), (x + (w * 0.025 if x > w / 2 else -w * 0.025), y + h * 0.018)], c, max(2, w // 70))


def oak(p, crown=0.7, leaf=C10, shade=DARK_GREEN, trunk=C11, light=None):
    """A broad tree: a trunk forking into branches under a round crown of
    clumps of leaves (leaf lit, shade underneath; light: lit the most)"""
    w, h = p.w, p.h
    top = h * (1 - crown)
    bottom = h * (1 - crown * 0.22)
    p.poly([(w * 0.42, h - 1), (w * 0.47, bottom - h * 0.1), (w * 0.53, bottom - h * 0.1), (w * 0.58, h - 1)],
           trunk)
    if light is None:
        clumps(p, w / 2, (top + bottom) / 2, w * 0.45, (bottom - top) / 2, w * 0.08, leaf, shade)
    else:  # autumn: the leaves lit (light), the rest in leaf, the darkest shade
        clumps(p, w / 2, (top + bottom) / 2, w * 0.46, (bottom - top) / 2, w * 0.075, light, leaf)
        for _ in range(int(w / 20)):
            x = p.rng.uniform(w * 0.3, w * 0.85)
            y = p.rng.uniform((top + bottom) / 2, bottom - h * 0.02)
            p.blob(x, y, w * 0.035, shade, lumps=5)
    # the trunk and two branches where the crown opens below
    p.rect(w * 0.47, bottom - h * 0.06, w * 0.53, h * 0.9, trunk)
    for dx in (-0.12, 0.12):
        p.line([(w / 2, bottom - h * 0.02), (w / 2 + dx * w, bottom - h * 0.08)], trunk, max(3, w // 30))


def shrub(p):
    """A bush: clumps of leaves on the ground"""
    w, h = p.w, p.h
    clumps(p, w / 2, h * 0.52, w * 0.46, h * 0.4, w * 0.09, C10, DARK_GREEN)
    p.rect(w * 0.12, h * 0.9, w * 0.88, h - 1, C11)


def poplar(p):
    """A slim, tall tree: a column of small clumps"""
    w, h = p.w, p.h
    p.rect(w * 0.46, h * 0.8, w * 0.54, h - 1, C11)
    clumps(p, w / 2, h * 0.43, w * 0.3, h * 0.42, w * 0.1, C10, DARK_GREEN, dense=1.2)


def palm(p):
    """A palm: a bent trunk in rings (10), fronds (11) arching out and
    hanging, their leaflets in shade (DARK_GREEN) underneath"""
    w, h = p.w, p.h
    pts = [(w * 0.5 + math.sin(t * 1.5) * w * 0.1, h - 1 - t * h * 0.72) for t in [k / 16 for k in range(17)]]
    for k in range(len(pts) - 1):
        width = w * (0.1 - 0.04 * k / 16)
        p.line([pts[k], pts[k + 1]], C10, max(3, int(width)))
        if k % 2:
            x, y = pts[k]
            p.line([(x - width / 2, y), (x + width / 2, y + h * 0.006)], DARK_GREY, max(2, w // 60))
    tx, ty = pts[-1]
    fronds = []
    for k in range(12):
        a = 2 * math.pi * k / 12 + p.rng.uniform(-0.15, 0.15)  # round the top, seen from aside
        side = math.cos(a)  # how far out to the side, -1 left .. 1 right
        depth = math.sin(a)  # towards (> 0) or away from us
        reach = w * 0.44 * (0.35 + 0.65 * abs(side))
        lift = h * (0.1 - 0.05 * abs(side) - 0.03 * depth)
        droop = h * (0.1 + 0.06 * abs(side) + 0.04 * depth)
        fronds.append((depth, side, reach, lift, droop))
    for depth, side, reach, lift, droop in sorted(fronds):  # those away first
        arc = []
        for j in range(13):
            t = j / 12
            arc.append((tx + side * reach * t, ty - lift * 4 * t * (1 - t) + droop * t * t))
        # the frond: a leaf along the arc, its lower edge jagged (leaflets)
        upper, lower, lit = [], [], []
        for j, (x, y) in enumerate(arc):
            t = j / 12
            x2, y2 = arc[min(12, j + 1)] if j < 12 else (2 * x - arc[11][0], 2 * y - arc[11][1])
            dx, dy = x2 - x, y2 - y
            n = math.hypot(dx, dy) or 1
            nx, ny = -dy / n, dx / n
            if ny < 0:
                nx, ny = -nx, -ny  # the normal pointing down
            wf = h * 0.06 * math.sin(math.pi * min(1, 0.15 + t * 0.95))
            jag = 1.0 if j % 2 else 0.55
            upper.append((x - nx * wf * 0.35, y - ny * wf * 0.35))
            lower.append((x + nx * wf * jag, y + ny * wf * jag))
            lit.append((x + nx * wf * 0.2, y + ny * wf * 0.2))
        p.poly(upper + lower[::-1], DARK_GREEN)
        p.poly(upper + lit[::-1], C11)
    p.blob(tx, ty + h * 0.01, w * 0.035, DARK_GREY, lumps=5)


def cactus(p, arms):
    """A column cactus, arms bent upwards"""
    w, h = p.w, p.h
    t = w * 0.28
    p.rect(w / 2 - t / 2, h * 0.08, w / 2 + t / 2, h - 1, C8)
    p.ellipse(w / 2 - t / 2, h * 0.02, w / 2 + t / 2, h * 0.14, C8)
    p.rect(w / 2 + t * 0.1, h * 0.1, w / 2 + t / 2, h - 1, C9)
    for k in range(arms):
        side = 1 if k % 2 == 0 else -1
        y = h * (0.35 + 0.18 * k)
        x0 = w / 2 + side * t / 2
        x1 = w / 2 + side * (t / 2 + w * 0.2)
        p.rect(min(x0, x1), y, max(x0, x1), y + t * 0.7, C8)
        p.rect(x1 - t * 0.35, y - h * 0.18, x1 + t * 0.35, y + t * 0.7, C8)
        p.ellipse(x1 - t * 0.35, y - h * 0.22, x1 + t * 0.35, y - h * 0.14, C8)


def rock(p, flat):
    """A boulder: lit on the left, cracks"""
    w, h = p.w, p.h
    pts = []
    n = 11
    for k in range(n):
        a = math.pi + math.pi * k / (n - 1)
        r = 1 + p.rng.uniform(-0.12, 0.12)
        pts.append((w / 2 + math.cos(a) * w * 0.48 * r, h - 1 + math.sin(a) * h * (0.95 if not flat else 0.9) * r))
    p.poly(pts, C8)
    p.poly([pts[0], pts[1], pts[2], pts[3], (w * 0.42, h - 1)], LIGHT_GREY if not flat else GREY)
    p.poly([pts[-1], pts[-2], pts[-3], (w * 0.6, h - 1)], DARK_GREY)
    for _ in range(3):
        x = p.rng.uniform(0.3, 0.7) * w
        p.line([(x, h * p.rng.uniform(0.3, 0.6)), (x + w * p.rng.uniform(-0.1, 0.1), h - 1)], DARK_GREY,
               max(2, w // 30))


# ------------------------------------------------------------ billboards

def billboard(p, lines, bg, fg, frame=LIGHT_GREY, pic=None, legs=2, round_=False):
    """A board on legs: lines of text, maybe a picture"""
    w, h = p.w, p.h
    board = h * 0.78
    p.posts([w * (k + 1) / (legs + 1) for k in range(legs)], board * 0.8)
    if round_:
        p.ellipse(0, 0, w - 1, board, BLACK)
        p.ellipse(1, 1, w - 2, board - 1, frame)
        p.ellipse(w * 0.06, board * 0.07, w * 0.94, board * 0.93, bg)
    else:
        p.rect(0, 0, w - 1, board, frame)
        p.bevel(0, 0, w - 1, board)
        p.rect(w * 0.045, board * 0.07, w * 0.955, board * 0.91, bg)
        p.bevel(int(w * 0.045) - 1, int(board * 0.07) - 1, int(w * 0.955) + 1, int(board * 0.91) + 1)
    if pic:
        pic(p, board)
    for (s, y, size, col) in lines:
        p.text((w / 2, board * y), s, int(board * size), col)


def sun_sea(p, board):
    """Sky (9), sun (11), sea, sand (10)"""
    w = p.w
    p.ellipse(w * 0.6, board * 0.5, w * 0.84, board * 0.78, C11)
    p.rect(w * 0.03, board * 0.66, w * 0.97, board * 0.8, C9)
    for k in range(2):
        y = board * (0.69 + 0.06 * k)
        p.line([(w * (0.12 + 0.1 * k), y), (w * (0.5 + 0.1 * k), y)], LIGHT_GREY, max(2, w // 60))
    p.rect(w * 0.03, board * 0.8, w * 0.97, board * 0.94, C10)


def planet(p, board):
    """A planet (9, lit 10) with a ring"""
    w = p.w
    p.ellipse(w * 0.28, board * 0.14, w * 0.72, board * 0.6, C9)
    p.ellipse(w * 0.33, board * 0.18, w * 0.52, board * 0.34, C10)
    p.line([(w * 0.08, board * 0.5), (w * 0.92, board * 0.24)], LIGHT_GREY, max(3, w // 30))
    for x, y in ((0.14, 0.14), (0.86, 0.6), (0.2, 0.62), (0.8, 0.12)):
        p.rect(w * x, board * y, w * x + 4, board * y + 4, LIGHT_GREY)


def joystick(p, board):
    w = p.w
    p.rect(w * 0.08, board * 0.6, w * 0.3, board * 0.84, BLACK)
    p.line([(w * 0.19, board * 0.62), (w * 0.22, board * 0.3)], DARK_GREY, max(4, w // 30))
    p.ellipse(w * 0.17, board * 0.22, w * 0.27, board * 0.36, RED)
    p.ellipse(w * 0.24, board * 0.64, w * 0.28, board * 0.7, RED)


def pizza(p, board):
    """A pizza: crust (9), cheese (8), salami"""
    w = p.w
    p.ellipse(w * 0.22, board * 0.42, w * 0.78, board * 0.92, C9)
    p.ellipse(w * 0.27, board * 0.46, w * 0.73, board * 0.88, C8)
    for x, y in ((0.4, 0.56), (0.58, 0.54), (0.5, 0.7), (0.36, 0.74), (0.64, 0.74)):
        p.ellipse(w * (x - 0.05), board * (y - 0.05), w * (x + 0.05), board * (y + 0.05), RED)


def wave_car(p, board):
    w = p.w
    p.poly([(w * 0.56, board * 0.86), (w * 0.62, board * 0.7), (w * 0.8, board * 0.66), (w * 0.92, board * 0.74),
            (w * 0.94, board * 0.86)], C11)
    for x in (0.64, 0.88):
        p.ellipse(w * x - w * 0.035, board * 0.8, w * x + w * 0.035, board * 0.92, BLACK)


# ------------------------------------------------------------ the banks
# (the type's own colours as the race has them: 8-11 below each)

def draw_type(t, w, h, rng):
    """Type t's drawing, w x h (four times its largest size)"""
    p = Pen(w, h, rng)
    D = {
        0x80: lambda: chevrons(p, False),
        0x81: lambda: chevrons(p, True),
        0x83: lambda: roadworks(p),                                     # C80 orange
        0x84: lambda: badge(p, 'M65'),
        0x85: lambda: billboard(p, [('SID', 0.34, 0.46, C8), ('SOUND', 0.74, 0.3, LIGHT_GREY)], C11, C8,
                                frame=C10),                             # AA0 851 060 04D
        0x86: lambda: pit_sign(p),                                      # C80 B50
        0x87: lambda: fir(p),                                           # 000 530 360/8AE 320
        0x89: lambda: rock(p, False),                                   # 444
        0x8A: lambda: rock(p, False),
        0x8B: lambda: rock(p, True),
        0x8C: lambda: rock(p, True),
        0x8F: lambda: shrub(p),                                         # 360/8AE 320
        0x90: lambda: shrub(p),                                         # 360/8AE 000
        0x91: lambda: billboard(p, [('PIXEL', 0.14, 0.2, DARK_RED), ('PIZZA', 0.31, 0.2, DARK_RED)], LIGHT_GREY,
                                C9, frame=C11, pic=pizza),              # 880 420 686 464
        0x94: lambda: billboard(p, [('TURBO', 0.34, 0.28, LIGHT_GREY), ('CUP', 0.64, 0.3, C10)], C9, C10,
                                frame=LIGHT_GREY, round_=True),         # 000 02E 08F 444
        0x95: lambda: oak(p, 0.8, leaf=C9, shade=C10, trunk=C11, light=C8),  # C62 942 632 422
        0x96: lambda: billboard(p, [('RALLY', 0.3, 0.36, C11), ('8 BIT', 0.7, 0.24, RED)], C10, C11, frame=C8,
                                pic=wave_car),                          # 444 08F CC1 00C
        0x97: lambda: billboard(p, [('ORBIT', 0.8, 0.18, LIGHT_GREY)], BLACK, LIGHT_GREY, frame=C11, pic=planet,
                                legs=1, round_=True),                   # 000 04A 06C 060
        0x98: lambda: billboard(p, [('FM', 0.32, 0.44, C9), ('RADIO 65', 0.74, 0.22, LIGHT_GREY)], C8, C9,
                                frame=LIGHT_GREY),                      # 00C CC0
        0x99: lambda: palm(p),                                          # 000 000 444 360
        0x9A: lambda: warning(p),
        0x9B: lambda: billboard(p, [('OASIS', 0.32, 0.36, C10), ('MOTEL', 0.68, 0.26, BLACK)], C11, C10,
                                frame=LIGHT_GREY, legs=3),              # 000 000 060 08F
        0x9C: lambda: billboard(p, [('MEGA 65', 0.36, 0.32, C8), ('RACING', 0.7, 0.22, LIGHT_GREY)], DARK_GREY, C8,
                                frame=C9, legs=3),                      # C80 B50
        0x9D: lambda: cactus(p, 2),                                     # 150 030
        0x9E: lambda: cactus(p, 1),
        0x9F: lambda: barrier(p),                                       # 000 000 CC0
        0xA0: lambda: keep_side(p, True),                               # 000 000 000 00C
        0xA1: lambda: keep_side(p, False),
        0xA2: lambda: puddle(p, BLACK),
        0xA3: lambda: puddle(p, C11),                                   # 00C
        0xA5: lambda: oak(p, 0.9),                                      # 360/8AE 320
        0xA7: lambda: poplar(p),                                        # 360/8AE 320
        0xA9: lambda: billboard(p, [('TURBO', 0.3, 0.32, LIGHT_GREY), ('TYRES', 0.68, 0.32, BLACK)], RED, LIGHT_GREY,
                                frame=LIGHT_GREY, legs=3),
        0xAA: lambda: billboard(p, [('SUN', 0.2, 0.26, LIGHT_GREY), ('COAST', 0.44, 0.2, C11)], C9, C11,
                                frame=LIGHT_GREY, pic=sun_sea),         # 000 06F CA8 C53
        0xAB: lambda: billboard(p, [('STAR', 0.22, 0.26, LIGHT_GREY), ('ARCADE', 0.46, 0.2, C9)], C8, C9,
                                frame=LIGHT_GREY, pic=joystick),        # 507 08D
    }
    if t not in D:
        return None
    D[t]()
    return p.img


OUTLINED = {0x87, 0x89, 0x8A, 0x8B, 0x8C, 0x8F, 0x90, 0x95, 0x99, 0x9D, 0x9E, 0xA5, 0xA7}


def bank(t, ims):
    """Type t's images in the sizes of ims (the game's), each drawn in its
    size (the textured kinds pixel by pixel, the others with crisp lines
    and writing) or the game's written anew; None if we have none"""
    if t in BOARDS or t in AS_THEY_ARE:
        return board(t, ims)
    dims = [(w, h) for w, h, _ in ims]
    if t in TEXTURED:
        out = []
        for k, (w, h) in enumerate(dims):
            px = TEXTURED[t](w, h, np.random.default_rng(0x5CE0 + t * 32 + k))
            out.append((w, h, bytes(np.asarray(px, np.uint8).flatten())))
        return out
    # the others drawn in each size as they are: lines and writing crisp
    out = []
    for k, (w, h) in enumerate(dims):
        img = draw_type(t, w, h, random.Random(0x5CE + t))
        if img is None:
            return None
        out.append((w, h, img.tobytes()))
    return out


def gate(ims):
    """The start gate's bank (its sizes as ims has them): posts 0-16 in red
    and white rings, banners 17-26 chequered, writing 27-34 the race's"""
    out = []
    for w, h, _ in ims[:17]:
        px = bytearray()
        ring = max(2, w * 2)
        for y in range(h):
            band = RED if (h - 1 - y) // ring % 2 else LIGHT_GREY
            for x in range(w):
                px.append(BLACK if w >= 3 and x in (0, w - 1) else band)
        out.append((w, h, bytes(px)))
    for w, h, _ in ims[17:27]:
        sq = max(1, h // 2)
        out.append((w, h, bytes(BLACK if y in (0, h - 1) and h >= 4 else
                                (LIGHT_GREY if (x // sq + y // sq) % 2 else BLACK)
                                for y in range(h) for x in range(w))))
    w0, h0, _ = ims[27]
    p = Pen(w0 * 4, h0 * 4, random.Random(0x6A7E))
    p.rect(0, 0, w0 * 4 - 1, h0 * 4 - 1, BLACK)
    p.text((w0 * 2, h0 * 2 + 2), 'MEGA 65', h0 * 4, LIGHT_GREY)
    for x in (h0 * 2, w0 * 4 - h0 * 2):
        p.ellipse(x - h0, h0, x + h0, h0 * 3, RED)
    for w, h, _ in ims[27:35]:
        out.append((w, h, reduce(p.img.resize((w * 4, h * 4), Image.NEAREST), w, h)))
    return out


# ------------------------------------------------------------ textured, pixel by pixel
#
# Plants and rocks are drawn for every size anew, pixel by pixel, so their
# texture stays one pixel fine however small: shapes of lit round lobes,
# the light from the upper left and the front; leaves, needles and stone
# as noise on top, in three or four shades and black where it is deepest.

import numpy as np  # noqa: E402

# colours the textured kinds have besides the race's: per type its slots
# 8-11 as 12-bit colours (mksprites.py gives them the type's own palette
# entries); the snowy kinds' snow where the green kinds' leaves are lit
GREEN_LIGHT, SNOW_LIGHT, BARK_LIGHT = 0x491, 0xDEF, 0x642
COLOURS = {
    0x87: {8: GREEN_LIGHT}, 0x88: {8: SNOW_LIGHT},
    0xA5: {8: GREEN_LIGHT, 9: BARK_LIGHT}, 0xA6: {8: SNOW_LIGHT, 9: BARK_LIGHT},
    0xA7: {8: GREEN_LIGHT, 9: BARK_LIGHT}, 0xA8: {8: SNOW_LIGHT, 9: BARK_LIGHT},
    0x8F: {8: GREEN_LIGHT, 9: BARK_LIGHT}, 0x92: {8: SNOW_LIGHT, 9: BARK_LIGHT},
    0x90: {8: GREEN_LIGHT, 9: BARK_LIGHT, 11: 0x320}, 0x93: {8: SNOW_LIGHT, 9: BARK_LIGHT, 11: 0x320},
    0x99: {8: GREEN_LIGHT, 9: 0x777},
    0x9D: {10: 0x3A3}, 0x9E: {10: 0x3A3},
}


def noise(rng, h, w, cell):
    """Smooth value noise in 0..1, features about cell pixels large"""
    gh, gw = int(h / cell) + 2, int(w / cell) + 2
    g = rng.random((gh, gw))
    ys, xs = np.arange(h) / cell, np.arange(w) / cell
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a, b = g[y0][:, x0], g[y0][:, x0 + 1]
    c, d = g[y0 + 1][:, x0], g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


LIGHT = np.array([-0.55, -0.6, 0.58])  # from the upper left and the front


def lobes(h, w, parts, rng, ragged=0.18, front=False):
    """A shape of round parts (cx, cy, rx, ry - pixels): where it is, and
    how lit (-1..1); its edge frayed by noise a pixel or two large. front:
    each part in front of those before it, lit as itself (clusters with
    their own light and shade), else the parts as one"""
    yy, xx = np.mgrid[0:h, 0:w].astype(float) + 0.5
    fray = noise(rng, h, w, 1.5) - 0.5
    inside = np.zeros((h, w), bool)
    lit = np.full((h, w), -1.0)
    for cx, cy, rx, ry in parts:
        nx, ny = (xx - cx) / rx, (yy - cy) / ry
        d = nx * nx + ny * ny
        m = d < (1 + ragged * 2 * fray) ** 2
        nz = np.sqrt(np.clip(1 - d, 0, 1))
        s = (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2])
        lit = np.where(m, s if front else np.maximum(lit, s), lit)
        inside |= m
    return inside, lit


def tones(v, colours, cuts):
    """v (0..1) into colours by the cuts between them"""
    out = np.full(v.shape, colours[-1], np.uint8)
    for c, cut in reversed(list(zip(colours[:-1], cuts))):
        out[v < cut] = c
    return out


def leafy(img, inside, lit, rng, dark, mid, light, holes=True, grain=0.5):
    """Leaves on the shape: light and shade, the leaves' noise, black in
    the deepest gaps"""
    h, w = img.shape
    v = 0.45 + 0.42 * lit + grain * (0.55 * (rng.random((h, w)) - 0.5) + 0.6 * (noise(rng, h, w, 2.2) - 0.5))
    shade = tones(v, [BLACK if holes else dark, dark, mid, light], [0.15, 0.45, 0.76])
    img[inside] = shade[inside]


def shadow(img, cx, y, rx):
    """The shadow on the ground under it: a black line or two"""
    h, w = img.shape
    for dy, f in ((0, 1.0), (-1, 0.75)):
        r = max(1, int(rx * f))
        if 0 <= y + dy < h:
            x0, x1 = max(0, int(cx - r)), min(w, int(cx + r) + 1)
            row = img[y + dy, x0:x1]
            row[row == CLEAR] = BLACK


def trunk(img, cx, y0, y1, w0, w1, rng, bark, lit):
    """A trunk from row y0 (narrow, w0) down to y1 (w1): bark, lit on the left"""
    h, w = img.shape
    for y in range(max(0, int(y0)), min(h, int(y1))):
        t = (y - y0) / max(1, y1 - y0)
        half = (w0 + (w1 - w0) * t * t) / 2
        for x in range(max(0, int(cx - half)), min(w, int(cx + half) + 1)):
            u = (x + 0.5 - cx) / max(half, 0.5)
            r = rng.random()
            img[y, x] = BLACK if r < 0.08 else lit if u < -0.2 and r < 0.75 else bark if u < 0.55 else BLACK


def edge_dark(img):
    """The edge facing away from the light (right, below) a shade darker:
    black where it meets nothing"""
    h, w = img.shape
    solid = img != CLEAR
    right = np.zeros_like(solid)
    right[:, :-1] = ~solid[:, 1:]
    right[:, -1] = True
    below = np.zeros_like(solid)
    below[:-1, :] = ~solid[1:, :]
    below[-1, :] = True
    img[solid & (right | below)] = BLACK


def clusters(cx, cy, rx, ry, n, size, rng):
    """n round clusters over an ellipse, the upper ones last (in front)"""
    parts = [(cx, cy, rx * 0.85, ry * 0.85)]
    for _ in range(n):
        a = rng.uniform(0, 2 * np.pi)
        d = np.sqrt(rng.uniform(0, 1)) * 0.78
        r = size * rng.uniform(0.8, 1.2)
        parts.append((cx + np.cos(a) * rx * d, cy + np.sin(a) * ry * d, r * rx, r * ry))
    return parts[:1] + sorted(parts[1:], key=lambda p: -p[1])


def render_oak(w, h, rng, leaf=C10, dark=DARK_GREEN, light=C8, bark=C11, bark_lit=C9, crown=0.78):
    img = np.full((h, w), CLEAR, np.uint8)
    top, bottom = h * (1 - crown), h * (1 - crown * 0.18)
    cx, cy, rx, ry = w / 2, (top + bottom) / 2, w * 0.46, (bottom - top) / 2
    trunk(img, cx, bottom - h * 0.12, h - 1, max(1.5, w * 0.07), max(2, w * 0.13), rng, bark, bark_lit)
    inside, lit = lobes(h, w, clusters(cx, cy, rx, ry, 16, 0.32, rng), rng, front=True)
    leafy(img, inside, lit, rng, dark, leaf, light)
    # branches where the crown opens: dark lines from the trunk out
    if w >= 24:
        for k in range(5):
            a = np.pi * (1.15 + 0.7 * k / 4)
            ex, ey = cx + np.cos(a) * rx * 0.75, cy + np.sin(a) * ry * 0.2 + ry * 0.35
            n = int(abs(ex - cx) + abs(ey - bottom)) + 1
            for i in range(n):
                t = i / n
                x, y = int(cx + (ex - cx) * t), int(bottom - h * 0.06 + (ey - bottom) * t)
                if 0 <= x < w and 0 <= y < h and img[y, x] in (BLACK, dark) and rng.random() < 0.8:
                    img[y, x] = bark if rng.random() < 0.5 else BLACK
    shadow(img, cx, h - 1, w * 0.3)
    return img


def render_autumn(w, h, rng):
    return render_oak(w, h, rng, leaf=C9, dark=C10, light=C8, bark=C11, bark_lit=C10, crown=0.8)


def render_bush(w, h, rng):
    img = np.full((h, w), CLEAR, np.uint8)
    inside, lit = lobes(h, w, clusters(w / 2, h * 0.55, w * 0.46, h * 0.42, 12, 0.36, rng), rng, front=True)
    inside[int(h * 0.94):, :] = False
    leafy(img, inside, lit, rng, DARK_GREEN, C10, C8)
    shadow(img, w / 2, h - 1, w * 0.42)
    return img


def render_poplar(w, h, rng):
    img = np.full((h, w), CLEAR, np.uint8)
    cx = w / 2
    trunk(img, cx, h * 0.8, h - 1, max(1.5, w * 0.08), max(2, w * 0.12), rng, C11, C9)
    parts = [(cx, h * 0.44, w * 0.3, h * 0.4)]
    for k in range(14):
        y = h * (0.06 + 0.76 * rng.uniform(0, 1))
        bulge = np.sin(np.pi * min(1, max(0, (y / h) / 0.85)))
        parts.append((cx + rng.uniform(-1, 1) * w * 0.12 * bulge, y, w * (0.12 + 0.14 * bulge), h * 0.07))
    parts = parts[:1] + sorted(parts[1:], key=lambda p: -p[1])
    inside, lit = lobes(h, w, parts, rng, ragged=0.22, front=True)
    leafy(img, inside, lit, rng, DARK_GREEN, C10, C8)
    shadow(img, cx, h - 1, w * 0.25)
    return img


def render_fir(w, h, rng):
    img = np.full((h, w), CLEAR, np.uint8)
    cx = w / 2
    trunk(img, cx, h * 0.8, h - 1, max(1.5, w * 0.08), max(2, w * 0.1), rng, C11, C9)
    yy, xx = np.mgrid[0:h, 0:w].astype(float) + 0.5
    grain = rng.random((h, w))
    needles = noise(rng, h, w, 1.6)
    tiers = 7
    for k in range(tiers):
        top = h * (0.0 + 0.1 * k)
        bottom = h * (0.2 + 0.1 * k) if k < tiers - 1 else h * 0.84
        half = w * (0.12 + 0.055 * k)
        u = (xx - cx) / half
        teeth = max(3, int(half / 2.5))
        jag = (np.abs(((xx - cx) / half * teeth) % 2 - 1)) * h * 0.035 + (needles - 0.5) * h * 0.02
        lower = bottom + h * 0.025 * u * u - jag
        upper = top + np.abs(u) * (bottom - top) * 0.85
        m = (np.abs(u) <= 1) & (yy >= upper) & (yy <= lower)
        # lit on the left, in shade under the tier above, the needles' grain
        depth = (yy - upper) / np.maximum(lower - upper, 1)
        v = 0.62 - 0.32 * u - 0.25 * (1 - depth) * (k > 0) + 0.45 * (0.5 * (grain - 0.5) + 0.6 * (needles - 0.5))
        img[m] = tones(v, [BLACK, DARK_GREEN, C10, C8], [0.14, 0.42, 0.72])[m]
    shadow(img, cx, h - 1, w * 0.3)
    return img


def render_palm(w, h, rng):
    img = Image.new('L', (w, h), CLEAR)
    d = ImageDraw.Draw(img)
    pts = [(w * 0.5 + np.sin(t * 1.5) * w * 0.1, h - 1 - t * h * 0.68) for t in np.linspace(0, 1, 14)]
    tw = max(1, round(w * 0.07))
    for k in range(len(pts) - 1):
        d.line([pts[k], pts[k + 1]], fill=C10, width=tw)
    for k in range(1, len(pts) - 1, 2):  # the rings
        x, y = pts[k]
        d.point((x + tw / 2, y), fill=BLACK)
        d.point((x - tw / 2, y), fill=C9)
    tx, ty = pts[-1]
    fronds = []
    for k in range(13):
        a = 2 * np.pi * k / 13 + rng.uniform(-0.2, 0.2)
        side, depth = np.cos(a), np.sin(a)
        fronds.append((depth, side, w * 0.47 * (0.3 + 0.7 * abs(side)), h * (0.09 - 0.04 * abs(side)),
                       h * (0.1 + 0.07 * abs(side) + 0.05 * depth)))
    for depth, side, reach, lift, droop in sorted(fronds):
        arc = [(tx + side * reach * t, ty - lift * 4 * t * (1 - t) + droop * t * t) for t in np.linspace(0, 1, 14)]
        upper, lower = [], []
        for j, (x, y) in enumerate(arc):  # a leaf along the arc, its lower edge in leaflets
            t = j / 13
            width = h * 0.055 * np.sin(np.pi * min(1, 0.12 + t * 0.95))
            upper.append((x, y - width * 0.3))
            lower.append((x, y + width * (1.0 if j % 2 else 0.45)))
        lit, mid = (C8, C11) if depth < -0.2 else (C11, DARK_GREEN) if depth < 0.5 else (DARK_GREEN, BLACK)
        d.polygon(upper + lower[::-1], fill=mid)
        d.line(arc, fill=lit, width=max(1, round(w / 70)))
    out = np.array(img, np.uint8)
    shadow(out, w / 2, h - 1, w * 0.15)
    return out


def render_cactus(w, h, rng, arms):
    img = np.full((h, w), CLEAR, np.uint8)
    t = max(3, w * 0.26)

    def column(x0, x1, y0, y1):
        for y in range(max(0, int(y0)), min(h, int(y1))):
            for x in range(max(0, int(x0)), min(w, int(np.ceil(x1)))):
                u = (x + 0.5 - x0) / max(x1 - x0, 1)
                rib = (x - int(x0)) % 3 == 2
                img[y, x] = C10 if u < 0.3 and not rib else C9 if u > 0.75 or rib else C8
            r = (x1 - x0) / 2
        cx = (x0 + x1) / 2
        for x in range(max(0, int(x0)), min(w, int(np.ceil(x1)))):  # a round top
            if abs(x + 0.5 - cx) > (x1 - x0) * 0.35 and 0 <= int(y0) < h:
                img[int(y0), x] = CLEAR
    column(w / 2 - t / 2, w / 2 + t / 2, h * 0.04, h - 1)
    for k in range(arms):
        side = 1 if k % 2 == 0 else -1
        y = h * (0.38 + 0.16 * k)
        xa = w / 2 + side * (t / 2 + w * 0.17)
        x0, x1 = sorted((w / 2, xa))
        for yy in range(int(y), int(y + t * 0.6)):  # the elbow
            for xx in range(int(x0), int(x1)):
                if 0 <= yy < h and 0 <= xx < w:
                    img[yy, xx] = C8 if yy < y + t * 0.3 else C9
        column(xa - t * 0.38, xa + t * 0.38, y - h * 0.2, y + t * 0.6)
    edge_dark(img)
    shadow(img, w / 2, h - 1, w * 0.25)
    return img


def render_rock(w, h, rng, flat):
    img = np.full((h, w), CLEAR, np.uint8)
    parts = [(w * 0.5, h * 1.0, w * 0.48, h * (0.95 if not flat else 0.85))]
    for k in range(3):
        parts.append((w * rng.uniform(0.3, 0.7), h * rng.uniform(0.55, 0.9), w * rng.uniform(0.2, 0.32),
                      h * rng.uniform(0.35, 0.6)))
    inside, lit = lobes(h, w, parts, rng, ragged=0.06)
    v = 0.42 + 0.45 * lit + 0.22 * (rng.random((h, w)) - 0.5) + 0.3 * (noise(rng, h, w, 3) - 0.5)
    img[inside] = tones(v, [BLACK, DARK_GREY, C8, GREY, LIGHT_GREY], [0.14, 0.4, 0.66, 0.9])[inside]
    for _ in range(max(1, w // 12)):  # cracks
        x, y = rng.uniform(0.25, 0.75) * w, rng.uniform(0.35, 0.8) * h
        for _ in range(int(h * 0.3)):
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h and img[yi, xi] != CLEAR:
                img[yi, xi] = BLACK if rng.random() < 0.7 else DARK_GREY
            x += rng.uniform(-0.8, 0.8)
            y += 1
    edge_dark(img)
    return img


TEXTURED = {
    0x87: render_fir, 0xA5: render_oak, 0x95: render_autumn, 0x8F: render_bush, 0x90: render_bush,
    0xA7: render_poplar, 0x99: render_palm,
    0x9D: lambda w, h, rng: render_cactus(w, h, rng, 2), 0x9E: lambda w, h, rng: render_cactus(w, h, rng, 1),
    0x89: lambda w, h, rng: render_rock(w, h, rng, False), 0x8A: lambda w, h, rng: render_rock(w, h, rng, False),
    0x8B: lambda w, h, rng: render_rock(w, h, rng, True), 0x8C: lambda w, h, rng: render_rock(w, h, rng, True),
}


# ------------------------------------------------------------ the game's boards, written anew
#
# The boards along the road keep the game's pictures - their colours,
# frames, shading - in all their sizes, but say something else: what they
# said (and any maker's mark) is taken out, filled with what is around it,
# and our writing put in, in the board's colours with a dark edge; most
# pictures are mirrored. The traffic signs stay as they are.

def _rect(img, x0, y0, x1, y1):
    h, w = img.shape
    return (slice(max(0, int(y0 * h)), min(h, int(np.ceil(y1 * h)))),
            slice(max(0, int(x0 * w)), min(w, int(np.ceil(x1 * w)))))


def erase(img, x0, y0, x1, y1, colours, fill=None):
    """In the rectangle (fractions of the image) the given colours become
    fill - or the colour most of the rest there has"""
    area = img[_rect(img, x0, y0, x1, y1)]
    hit = np.isin(area, list(colours))
    if fill is None:
        rest = area[~hit & (area != CLEAR)]
        fill = np.bincount(rest).argmax() if rest.size else BLACK
    area[hit] = fill


def erase_oval(img, cx, cy, rx, ry, colours, fill_above, fill_below, split):
    """The same in an ellipse, filled by one colour above row split
    (fraction) and another below it"""
    h, w = img.shape
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    m = (((xx / w - cx) / rx) ** 2 + ((yy / h - cy) / ry) ** 2 <= 1) & np.isin(img, list(colours))
    img[m & (yy / h < split)] = fill_above
    img[m & (yy / h >= split)] = fill_below


def write(img, s, cx, cy, height, fill, edge=BLACK, name='Exo2.ttf'):
    """Writing centred at (cx, cy), height (fractions); edged with a dark
    pixel all round where it is large enough"""
    h, w = img.shape
    size = int(height * h * 1.35)
    if size < 4:
        return
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    f = font(size, name)
    if name == 'Exo2.ttf':
        f.set_variation_by_axes([800])
    # as wide as there is room: smaller if it would not fit
    while size > 4 and d.textlength(s, font=f) > w * 0.94:
        size -= 1
        f = font(size, name)
        if name == 'Exo2.ttf':
            f.set_variation_by_axes([800])
    x, y = cx * w, cy * h
    if edge is not None and size >= 7:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (1, -1), (-1, 1)):
            d.text((x + dx, y + dy), s, fill=edge, font=f, anchor='mm')
    d.text((x, y), s, fill=fill, font=f, anchor='mm')
    img[:] = np.array(im)


def disc(img, cx, cy, r, fill, ring):
    """A round badge: r a fraction of the width"""
    h, w = img.shape
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    d = np.hypot(xx - cx * w, yy - cy * h)
    rr = r * w
    img[d <= rr] = ring
    img[d <= rr - max(1, rr * 0.15)] = fill


BOARDS = {
    0x84: lambda i: (erase(i, 0.06, 0.07, 0.94, 0.72, {GREY, LIGHT_GREY}, BLACK),
                     write(i, 'M65', 0.5, 0.4, 0.42, LIGHT_GREY, GREY)),
    0x85: lambda i: (erase(i, 0.05, 0.12, 0.95, 0.68, set(range(16)) - {CLEAR}, BLACK),
                     [i.__setitem__(_rect(i, 0.08, y, 0.92, y + 0.025), c)
                      for y, c in ((0.52, C8), (0.555, RED), (0.59, C10), (0.625, C11))],
                     write(i, 'SID SOUND', 0.5, 0.33, 0.26, LIGHT_GREY, C11)),
    0x86: lambda i: (erase_oval(i, 0.5, 0.31, 0.45, 0.26, {DARK_GREY, GREY, LIGHT_GREY, DARK_GREEN}, C8, C9, 0.5),
                     disc(i, 0.5, 0.32, 0.2, DARK_GREEN, LIGHT_GREY),
                     write(i, 'P', 0.5, 0.31, 0.2, LIGHT_GREY, None)),
    0x91: lambda i: (i.__setitem__(slice(None), i[:, ::-1]),
                     erase(i, 0.04, 0.04, 0.96, 0.4, {BLACK}, LIGHT_GREY),
                     write(i, 'MEGA', 0.5, 0.13, 0.15, BLACK, None),
                     write(i, 'BITE', 0.5, 0.3, 0.15, BLACK, None)),
    0x94: lambda i: (i.__setitem__(slice(None), i[:, ::-1]),
                     erase(i, 0.0, 0.56, 1.0, 0.97, {LIGHT_GREY}),
                     write(i, 'FAT TYRES', 0.5, 0.79, 0.12, LIGHT_GREY)),
    0x96: lambda i: (i.__setitem__(slice(None), i[:, ::-1]),
                     erase(i, 0.03, 0.1, 0.47, 0.82, {C10, LIGHT_RED, RED, DARK_RED, BLACK}),
                     write(i, 'MONSTER', 0.255, 0.3, 0.13, C10),
                     write(i, 'TRUCKS', 0.255, 0.52, 0.13, C10),
                     write(i, 'LIVE!', 0.255, 0.72, 0.1, RED, BLACK)),
    0x97: lambda i: (i.__setitem__(slice(None), i[:, ::-1]),
                     erase(i, 0.12, 0.22, 0.88, 0.62, {LIGHT_GREY, BLACK}),
                     write(i, 'OUR', 0.5, 0.31, 0.13, LIGHT_GREY),
                     write(i, 'PLANET', 0.5, 0.49, 0.13, LIGHT_GREY)),
    0x98: lambda i: (i.__setitem__(slice(None), i[:, ::-1]),
                     erase(i, 0.12, 0.55, 0.88, 0.93, {C9, BLACK}, DARK_GREEN),
                     write(i, 'FAST', 0.5, 0.66, 0.15, C9),
                     write(i, 'LOADER', 0.5, 0.83, 0.1, C9)),
    0x9B: lambda i: (i.__setitem__(slice(None), i[:, ::-1]),
                     erase(i, 0.04, 0.06, 0.96, 0.52, {LIGHT_RED, RED, DARK_RED, BLACK}),
                     write(i, 'Palm Bay', 0.5, 0.2, 0.14, RED, DARK_RED, 'TitilliumWeb-Bold.ttf'),
                     write(i, 'Hotel', 0.5, 0.39, 0.14, RED, DARK_RED, 'TitilliumWeb-Bold.ttf')),
    0x9C: lambda i: (erase(i, 0.1, 0.09, 0.9, 0.2, {BLACK, LIGHT_GREY}, GREY),
                     erase(i, 0.04, 0.68, 0.96, 0.8, {BLACK, LIGHT_GREY}, GREY),
                     erase_oval(i, 0.5, 0.41, 0.15, 0.2, {BLACK, DARK_RED, DARK_GREY, GREY, LIGHT_GREY, DARK_GREEN},
                                C8, C9, 0.45),
                     disc(i, 0.5, 0.41, 0.11, DARK_GREEN, LIGHT_GREY),
                     write(i, '65', 0.5, 0.41, 0.13, LIGHT_GREY, None),
                     write(i, 'WEDGE TURBO', 0.5, 0.145, 0.09, LIGHT_GREY, None, 'Rajdhani-Bold.ttf'),
                     write(i, 'RACING SERIES', 0.5, 0.74, 0.09, LIGHT_GREY, None, 'Rajdhani-Bold.ttf')),
    0xA9: lambda i: (erase(i, 0.03, 0.05, 0.97, 0.95, {LIGHT_GREY, GREY, BLACK, LIGHT_RED, DARK_RED}, RED),
                     write(i, 'Max\'s', 0.25, 0.17, 0.13, LIGHT_RED, DARK_RED, 'TitilliumWeb-Bold.ttf'),
                     write(i, 'TYRE', 0.55, 0.37, 0.22, LIGHT_GREY),
                     write(i, 'SERVICE', 0.5, 0.63, 0.22, LIGHT_GREY),
                     write(i, 'DEPOTS', 0.5, 0.84, 0.11, GREY)),
    0xAA: lambda i: (i.__setitem__(slice(None), i[:, ::-1]),
                     erase(i, 0.04, 0.0, 0.96, 0.33, {LIGHT_GREY, GREY, BLACK}),
                     write(i, 'SUNNY', 0.5, 0.11, 0.17, LIGHT_GREY, BLACK, 'TitilliumWeb-Bold.ttf'),
                     write(i, 'BAY', 0.5, 0.26, 0.1, LIGHT_GREY)),
    0xAB: lambda i: (i.__setitem__(slice(None), i[:, ::-1]),
                     erase(i, 0.25, 0.07, 0.8, 0.36, {LIGHT_GREY, BLACK}),
                     write(i, 'TEE', 0.52, 0.15, 0.12, LIGHT_GREY),
                     write(i, 'TIME', 0.52, 0.29, 0.12, LIGHT_GREY)),
}
# the traffic signs: as the game has them
AS_THEY_ARE = {0x80, 0x81, 0x83, 0x9A, 0x9F, 0xA0, 0xA1, 0xA2, 0xA3}


def board(t, ims):
    """The game's images of type t, written anew"""
    out = []
    for w, h, px in ims:
        img = np.frombuffer(px, np.uint8).reshape(h, w).copy()
        if t in BOARDS:
            BOARDS[t](img)
        out.append((w, h, img.tobytes()))
    return out


# ------------------------------------------------------------ signs drawn elsewhere
#
# A sign's or board's drawing in art/signs/NN-name.png (NN its type in hex)
# takes its place: any size, its ground transparent - or a plain colour all
# round it, the colour at the corners. Cropped to what is not ground, it is
# brought down to each of the type's sizes, edge to edge (undistorted if its
# shape is not theirs), and its colours to the race view's 0-7 and colours
# of the drawings' own, shared by all of them.

ART_SIGNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'art', 'signs')
SIGN_WEIGHT = np.array([3.0, 4.0, 2.0])  # how much red, green, blue tell colours apart
SIGN_STRETCH = 0.03  # how far a drawing's shape may be from its sizes' to be stretched to them


def drawn_signs():
    """The types that have a drawing in art/signs: type -> its file"""
    out = {}
    if os.path.isdir(ART_SIGNS):
        for f in sorted(os.listdir(ART_SIGNS)):
            if not f.lower().endswith('.png'):
                continue
            try:
                t = int(f[:2], 16)
            except ValueError:
                sys.exit(f'art/signs/{f}: the name does not start with the type (e.g. 9B-hotel.png)')
            if t in out:
                sys.exit(f'art/signs: two drawings of type {t:02X}')
            out[t] = os.path.join(ART_SIGNS, f)
    return out


def sign_art(path):
    """The drawing, RGBA, its ground transparent, cropped to the rest"""
    im = Image.open(path).convert('RGBA')
    keyed = im.getextrema()[3][0] == 255
    if keyed:  # no transparency: the plain colour round it, from the corners in
        ground = np.array(im.getpixel((0, 0))[:3], float)
        for corner in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)):
            ImageDraw.floodfill(im, corner, (0, 0, 0, 0), thresh=40)
    a = np.array(im)
    if keyed and np.ptp(ground) > 150:  # a loud key colour (magenta): in the gaps it encloses too
        a[np.abs(a[:, :, :3] - ground).sum(axis=2) <= 40, 3] = 0
    solid = a[:, :, 3] >= 128
    if keyed:  # its edge mixed with the ground: two pixels off
        for _ in range(2):
            solid[1:-1, 1:-1] &= solid[:-2, 1:-1] & solid[2:, 1:-1] & solid[1:-1, :-2] & solid[1:-1, 2:]
    a[:, :, 3] = np.where(solid, 255, 0)
    ys, xs = np.nonzero(solid)
    if not ys.size:
        sys.exit(f'{path}: nothing but ground')
    return Image.fromarray(a).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def sign_fit(im, w, h):
    """The drawing in w x h: stretched to it if its shape is near enough
    (3 %), else as large as it fits undistorted, centred, on the ground"""
    ratio = im.width / im.height / (w / h)
    if abs(ratio - 1) <= SIGN_STRETCH:
        return im.resize((w, h), Image.LANCZOS)
    fw, fh = (w, max(1, round(h / ratio))) if ratio > 1 else (max(1, round(w * ratio)), h)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out.paste(im.resize((fw, fh), Image.LANCZOS), ((w - fw) // 2, h - fh))
    return out


def _nearest(px, pal):
    d = (((px[:, None, :] - pal[None, :, :]) ** 2) * SIGN_WEIGHT).sum(axis=2)
    return d.argmin(axis=1)


def sign_banks(dims_of, view, first, room):
    """The drawn signs: per type of dims_of (type -> its sizes) whose drawing
    there is, its images in those sizes - colours 0-7 the race view's
    (view: their 12-bit colours), first on those of the drawings - and
    those (12-bit), at most room"""
    art = drawn_signs()
    smalls = {}
    for t, dims in dims_of.items():
        if t in art:
            im = sign_art(art[t])
            smalls[t] = [np.asarray(sign_fit(im, w, h), float) for w, h in dims]
    if not smalls:
        return {}, []
    # what the drawings have, on the 12-bit grid; small parts count more
    # than their pixels (the square root of how many)
    px = np.concatenate([s[s[:, :, 3] >= 128][:, :3] for ims in smalls.values() for s in ims])
    grid = np.clip(np.rint(px / 17), 0, 15).astype(int)
    codes, counts = np.unique(grid[:, 0] << 8 | grid[:, 1] << 4 | grid[:, 2], return_counts=True)
    rgb = np.stack([codes >> 8, codes >> 4 & 15, codes & 15], axis=1) * 17.0
    fixed = np.array([[(c >> 8 & 15) * 17, (c >> 4 & 15) * 17, (c & 15) * 17] for c in view], float)
    weight = np.sqrt(counts)
    free = _nearest(rgb, fixed)
    free = (((rgb - fixed[free]) ** 2) * SIGN_WEIGHT).sum(axis=1) > 0
    if free.sum() <= room:  # room for every one
        own = rgb[free]
    else:  # weighted k-means; the race view's colours stay where they are
        rng = np.random.default_rng(0x5167)
        own = rgb[free][rng.choice(free.sum(), room, replace=False, p=weight[free] / weight[free].sum())]
        for _ in range(30):
            near = _nearest(rgb, np.concatenate([fixed, own]))
            for k in range(room):
                m = near == len(fixed) + k
                if m.any():
                    own[k] = (rgb[m] * weight[m, None]).sum(axis=0) / weight[m].sum()
        own = np.unique(np.clip(np.rint(own / 17), 0, 15) * 17, axis=0)
        own = own[(((own[:, None] - fixed[None]) ** 2) * SIGN_WEIGHT).sum(axis=2).min(axis=1) > 0]
    pal = np.concatenate([fixed, own])
    index = np.concatenate([np.arange(len(fixed)), first + np.arange(len(own))]).astype(np.uint8)
    banks = {}
    for t, ims in smalls.items():
        out = []
        for s in ims:
            h, w = s.shape[:2]
            flat = s.reshape(-1, 4)
            pix = np.full(w * h, CLEAR, np.uint8)
            solid = flat[:, 3] >= 128
            if solid.any():
                pix[solid] = index[_nearest(flat[solid, :3], pal)]
            out.append((w, h, pix.tobytes()))
        banks[t] = out
    colours = [int(r // 17) << 8 | int(g // 17) << 4 | int(b // 17) for r, g, b in own]
    return banks, colours


# ------------------------------------------------------------ kinds of our own
#
# Two kinds the game has numbers for but never used ($8D, $8E - never
# touched, no width to run into): wind turbines and fields of solar
# panels, set further from the road than the trees (mkcourses.py). Their
# sizes: the game's for its boards, from BASE on.

NEW_TYPES = {0x8D: (84, 168), 0x8E: (120, 40)}
COLOURS.update({
    0x8D: {8: 0xEEE, 9: 0x99A},                          # white, its shade
    0x8E: {8: 0x124, 9: 0x358, 10: 0x8BE, 11: 0x999},    # panels dark, mid, the sky in them; frames
})


def render_turbine(w, h, rng):
    """A wind turbine: a white tower, lit on the left, the nacelle, three
    blades with red tips"""
    img = Image.new('L', (w, h), CLEAR)
    d = ImageDraw.Draw(img)
    cx, hub = w / 2, h * 0.33
    base, top = max(1.0, w * 0.045), max(1.0, w * 0.022)
    d.polygon([(cx - base, h - 1), (cx - top, hub), (cx + top, hub), (cx + base, h - 1)], fill=LIGHT_GREY)
    d.polygon([(cx, h - 1), (cx, hub), (cx + top, hub), (cx + base, h - 1)], fill=C9)
    if base >= 2:
        d.line([(cx - base, h - 1), (cx - top, hub)], fill=C8)
    turn = 0.35
    for k in range(3):
        a = turn + k * 2 * np.pi / 3
        ln = h * 0.3
        ex, ey = cx + np.cos(a) * ln, hub - np.sin(a) * ln
        nx, ny = -np.sin(a), -np.cos(a)  # across the blade
        wb = max(0.6, w * 0.022)
        d.polygon([(cx + nx * wb, hub + ny * wb), (ex, ey), (cx - nx * wb, hub - ny * wb)], fill=C8)
        d.line([(cx - nx * wb, hub - ny * wb), (ex, ey)], fill=C9)
        tip = 0.86
        d.line([(cx + (ex - cx) * tip, hub + (ey - hub) * tip), (ex, ey)], fill=RED, width=max(1, round(wb)))
    r = max(1, w * 0.03)
    d.rectangle([cx - r * 1.6, hub - r, cx + r * 1.2, hub + r], fill=LIGHT_GREY)  # the nacelle
    d.ellipse([cx - r, hub - r, cx + r, hub + r], fill=C8)
    out = np.array(img, np.uint8)
    shadow(out, cx, h - 1, w * 0.1)
    return out


def render_solar(w, h, rng):
    """A field of solar panels: rows of tilted panels, framed, the sky
    shining in them, on short legs"""
    img = Image.new('L', (w, h), CLEAR)
    d = ImageDraw.Draw(img)
    rows = 3
    for k in range(rows):  # the far row first, higher up and shorter
        f = 1 - 0.12 * (rows - 1 - k)
        x0, x1 = w * (0.5 - 0.5 * f), w * (0.5 + 0.5 * f) - 1
        top = h * (0.06 + 0.24 * k)
        depth = h * 0.26
        bottom = top + depth
        lean = depth * 0.45
        d.polygon([(x0 + lean, top), (x1 + lean, top), (x1, bottom), (x0, bottom)], fill=C9)
        # the sky in them, brighter to the left
        d.polygon([(x0 + lean, top), (x0 + lean + (x1 - x0) * 0.35, top), (x0 + (x1 - x0) * 0.22, bottom),
                   (x0, bottom)], fill=C10)
        d.line([(x0 + lean, top), (x0, bottom)], fill=C11)
        cells = max(1, int((x1 - x0) / 6))
        for c in range(1, cells):  # the panels' frames
            t = c / cells
            xa = x0 + lean + (x1 - x0) * t
            d.line([(xa, top), (xa - lean, bottom)], fill=C8)
        d.line([(x0 + lean, top), (x1 + lean, top)], fill=C11)
        d.line([(x0, bottom), (x1, bottom)], fill=BLACK)
        for c in range(0, cells + 1, 2):  # the legs
            xa = x0 + (x1 - x0) * c / cells
            d.line([(xa, bottom), (xa, min(h - 1, bottom + h * 0.08))], fill=DARK_GREY)
    return np.array(img, np.uint8)


RENDER_NEW = {0x8D: render_turbine, 0x8E: render_solar}


def new_bank(t, ratios):
    """A kind of our own: its images in the sizes base * ratios"""
    bw, bh = NEW_TYPES[t]
    out = []
    for k, r in enumerate(ratios):
        w, h = max(1, round(bw * r)), max(1, min(255, round(bh * r)))
        px = RENDER_NEW[t](w, h, np.random.default_rng(0x77E0 + t * 32 + k))
        out.append((w, h, bytes(np.asarray(px, np.uint8).flatten())))
    return out
