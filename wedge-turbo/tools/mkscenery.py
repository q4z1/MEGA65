#!/usr/bin/env python3
"""Wedge Turbo's scenery: trees, rocks, signs and billboards of our own,
drawn at build time.

Every object type keeps the place it has in the race - its bank's 17
sizes, its colours: the race view's 0-7 and the type's own 8-11
(tab_object_colours, which the race loads as the object comes near; the
snowy trees and bushes share the green ones' images and are white by their
colours). What it shows is new: drawn four times as large in those colours
and brought down to each size.

bank(type, dims) gives a bank's images, gate(images) the start gate's.
"""
import math
import os
import random

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
        self.w, self.h, self.rng = w, h, rng

    def rect(self, x0, y0, x1, y1, c, outline=None, width=1):
        self.d.rectangle([x0, y0, x1, y1], fill=c, outline=outline, width=width)

    def poly(self, pts, c):
        self.d.polygon(pts, fill=c)

    def ellipse(self, x0, y0, x1, y1, c):
        self.d.ellipse([x0, y0, x1, y1], fill=c)

    def line(self, pts, c, width):
        self.d.line(pts, fill=c, width=width)

    def text(self, xy, s, size, c, name='Rajdhani-Bold.ttf', anchor='mm'):
        self.d.text(xy, s, fill=c, font=font(size, name), anchor=anchor)

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
        width = width or max(4, self.w // 28)
        for x in xs:
            self.rect(x - width // 2, top, x + width // 2, self.h - 1, c)


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
        p.ellipse(0, 0, w - 1, board, frame)
        p.ellipse(w * 0.05, board * 0.05, w * 0.95, board * 0.95, bg)
    else:
        p.rect(0, 0, w - 1, board, frame)
        p.rect(w * 0.03, board * 0.04, w * 0.97, board * 0.94, bg)
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


def bank(t, dims):
    """Type t's images in the bank's sizes; None if we have no drawing of
    it. The drawing has the shape most sizes have (the game squeezed the
    nearest into 96 rows), squeezed as they are."""
    ratios = sorted(h / w for w, h in dims if w >= 8)
    ratio = ratios[len(ratios) // 2]
    w0 = dims[0][0]
    master = draw_type(t, w0 * 4, round(w0 * ratio) * 4, random.Random(0x5CE + t))
    if master is None:
        return None
    out = []
    for w, h in dims:
        px = reduce(master.resize((w * 4, h * 4), Image.NEAREST), w, h)
        if t in OUTLINED and w >= 12:
            px = outline(px, w, h)
        out.append((w, h, px))
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
