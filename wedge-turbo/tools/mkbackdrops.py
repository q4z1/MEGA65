#!/usr/bin/env python3
"""Wedge Turbo's backdrops: ten panoramas of our own, drawn at build time.

A backdrop is 960 x 32 pixels that go round the course once (its left and
right edges meet), behind the road: what its theme is about - table
mountains, a pine forest, savanna, volcanoes, glaciers, karst towers, a
city, farmland, wooded hills with a castle, prairie - in the colours a
backdrop has: the course's three (BACK_COLOURS on: their brightness tells
which is light, middle and dark), the race view's dark grey, grey, light
grey and dark green (4-7), and the sky (15). Slopes are shaded with a
2 x 2 dither, as pixel art of the time did.

backdrop(theme, order) gives the pixels, row after row; order: the
course colours' numbers from light to dark.
"""
import math
import random

W, H = 960, 32
SKY = 15
DARK_GREY, GREY, LIGHT_GREY, DARK_GREEN = 4, 5, 6, 7


def wave(x, parts):
    """A height that goes round: sine waves of whole periods over W"""
    return sum(a * math.sin(2 * math.pi * (f * x / W) + p) for a, f, p in parts)


def parts(rng, spec):
    return [(a, f, rng.uniform(0, 2 * math.pi)) for a, f in spec]


def noise(rng, octaves=((1.0, 12), (0.5, 30), (0.25, 80), (0.12, 192))):
    """Fractal noise that goes round: per octave random values at points
    spaced evenly over W, smoothly in between; -1 .. 1"""
    tables = [(amp, n, [rng.uniform(-1, 1) for _ in range(n)]) for amp, n in octaves]
    total = sum(amp for amp, _, _ in tables)

    def f(x):
        v = 0
        for amp, n, t in tables:
            p = (x % W) * n / W
            i = int(p)
            k = (1 - math.cos((p - i) * math.pi)) / 2
            v += amp * (t[i % n] * (1 - k) + t[(i + 1) % n] * k)
        return v / total
    return f


class Canvas:
    def __init__(self, light, mid, dark):
        self.px = [[SKY] * W for _ in range(H)]
        self.light, self.mid, self.dark = light, mid, dark

    def set(self, x, y, c):
        if 0 <= y < H:
            self.px[y][x % W] = c

    def column(self, x, top, bottom, c):
        for y in range(max(0, int(top)), min(H, int(bottom))):
            self.px[y][x % W] = c

    def dither(self, x, y, a, b):
        """a or b in a 2 x 2 checker"""
        return a if (x + y) % 2 else b

    def ridge(self, height, base, lit, shade, slope_light=True, rng=None, dark=None):
        """A ridge: everything below height(x) down to base; the slopes that
        face left lit, those that face right in shade, dithered between, a
        lit rim on the crest; with dark, some rock in it"""
        rng = rng or random.Random(1)
        for x in range(W):
            top = H - height(x)
            d = height(x + 1.5) - height(x - 1.5)
            for y in range(max(0, int(top)), base):
                depth = y - top
                if depth < 1 and d > -0.3:
                    c = lit
                elif d > 0.5 and slope_light:
                    c = lit
                elif d > 0.1:
                    c = self.dither(x, y, lit, shade)
                else:
                    c = shade
                if dark is not None and rng.random() < 0.06 + 0.02 * depth:
                    c = dark if c == shade else shade
                self.set(x, y, c)

    def ground(self, rows, rng, a, b):
        """The strip of land in front: a and b mixed, a ragged top"""
        for x in range(W):
            top = H - rows - (1 if rng.random() < 0.3 else 0)
            for y in range(int(top), H):
                self.set(x, y, a if rng.random() < 0.7 else b)

    def pixels(self):
        return bytes(c for row in self.px for c in row)


def mesas(c, rng):
    """Table mountains: flat tops, steep sides, layered rock"""
    far = noise(rng)
    c.ridge(lambda x: 12 + 5 * far(x), H, c.light, c.mid, rng=rng)
    for _ in range(11):
        x0, w, h = rng.randrange(W), rng.randint(30, 90), rng.randint(17, 27)
        rough = noise(rng, ((1, 8), (0.5, 40)))
        for x in range(x0, x0 + w):
            edge = min(x - x0, x0 + w - 1 - x)
            top = H - h + max(0, 5 - edge) * 2 + rough(x) * 1.2
            for y in range(max(0, int(top)), H):
                band = (y - int(top)) % 5 == 4
                if x - x0 < 4:
                    col = c.light
                elif x0 + w - 1 - x < 5:
                    col = c.dark
                else:
                    col = c.dark if band else c.dither(x, y, c.mid, c.dark) if y > H - 8 else c.mid
                c.set(x, y, col)
    c.ground(3, rng, c.dark, DARK_GREY)


def forest(c, rng):
    """Low fells, a pine forest in front"""
    fell = noise(rng)
    c.ridge(lambda x: 17 + 6 * fell(x), H, LIGHT_GREY, c.light, rng=rng, dark=c.mid)
    tops = noise(rng, ((1, 20), (0.6, 60)))
    for x in range(0, W, 3):
        h = int(10 + 4 * tops(x) + rng.randint(0, 3))
        for k in range(h):
            half = k // 3
            for dx in range(-half, half + 1):
                c.set(x + dx, H - h + k, c.dark if (dx * 2 + k) % 5 else DARK_GREEN)
    c.ground(3, rng, DARK_GREEN, c.dark)


def savanna(c, rng):
    """Flat land under a big sky, a far range, acacias"""
    far = noise(rng, ((1, 6), (0.5, 20), (0.3, 70)))
    c.ridge(lambda x: 15 + 5 * far(x), H, c.light, c.mid, rng=rng)
    # one great mountain far off, snow on its top
    x0, h, w = rng.randrange(W), 28, 150
    for x in range(x0 - w, x0 + w):
        t = abs(x - x0) / w
        top = H - h + (t ** 1.5) * h
        for y in range(max(0, int(top)), H):
            snow = y < H - h + 5 + (x * 7) % 3
            c.set(x, y, LIGHT_GREY if snow and x <= x0 else c.dither(x, y, LIGHT_GREY, c.light) if snow
                  else c.light if x < x0 else c.mid)
    near = noise(rng, ((1, 10), (0.4, 50)))
    c.ridge(lambda x: 7 + 1.5 * near(x), H, c.mid, c.dark)
    for _ in range(30):
        x0, h = rng.randrange(W), rng.randint(8, 14)
        c.column(x0, H - h, H - 2, c.dark)
        c.set(x0 - 1, H - h + 2, c.dark)
        c.set(x0 + 1, H - h + 3, c.dark)
        w = rng.randint(5, 10)
        for dx in range(-w, w + 1):
            c.set(x0 + dx, H - h, c.dark)
            if abs(dx) < w - 1:
                c.set(x0 + dx, H - h - 1, DARK_GREEN if dx % 3 else c.dark)
            if abs(dx) < w - 3:
                c.set(x0 + dx, H - h - 2, c.dark)
    c.ground(2, rng, c.mid, c.dark)


def volcanoes(c, rng):
    """Cones with snow on top, a ragged range behind"""
    back = noise(rng)
    c.ridge(lambda x: 13 + 6 * back(x), H, c.light, c.mid, rng=rng, dark=c.dark)
    for _ in range(4):
        x0, h, w = rng.randrange(W), rng.randint(24, 30), rng.randint(60, 100)
        rough = noise(rng, ((1, 30), (0.5, 90)))
        for x in range(x0 - w, x0 + w):
            t = abs(x - x0) / w
            top = H - h + (t ** 0.8) * h + rough(x) * 1.5
            if abs(x - x0) < 3:
                top = H - h + 2
            for y in range(max(0, int(top)), H):
                snow = y < H - h + 7 + rough(x * 3) * 2
                if snow:
                    col = LIGHT_GREY if x <= x0 else c.dither(x, y, LIGHT_GREY, c.light)
                else:
                    col = c.light if x < x0 - w // 3 else c.mid if x < x0 else c.dither(x, y, c.mid, c.dark)
                c.set(x, y, col)
    c.ground(3, rng, c.dark, DARK_GREY)


def glaciers(c, rng):
    """Ice fields: sharp peaks, glaciers between them, cracks"""
    peaks = noise(rng, ((1, 14), (0.6, 40), (0.3, 120)))
    c.ridge(lambda x: 18 + 9 * peaks(x), H, LIGHT_GREY, c.light)
    front = noise(rng, ((1, 10), (0.4, 50)))
    c.ridge(lambda x: 8 + 3 * front(x), H, c.light, c.mid)
    for _ in range(50):
        x0, y0 = rng.randrange(W), rng.randint(H - 10, H - 4)
        for k in range(rng.randint(2, 4)):
            c.set(x0 + k, y0 + k // 2, c.dark)
    c.ground(2, rng, c.mid, c.dark)


def karst(c, rng):
    """Limestone towers in mist, pagodas"""
    mist = noise(rng, ((1, 8), (0.5, 30)))
    c.ridge(lambda x: 9 + 3 * mist(x), H, c.light, c.light)
    for _ in range(24):
        x0, w, h = rng.randrange(W), rng.randint(9, 20), rng.randint(13, 29)
        far = rng.random() < 0.4
        for x in range(x0, x0 + w):
            t = (x - x0) / (w - 1) * 2 - 1
            top = H - h + (1 - math.sqrt(max(0, 1 - t * t))) * 7
            for y in range(max(0, int(top)), H):
                if far:
                    col = c.mid
                else:
                    col = c.mid if t < -0.4 else c.dither(x, y, c.mid, c.dark) if t < 0.3 else c.dark
                    if rng.random() < 0.05:
                        col = DARK_GREEN
                c.set(x, y, col)
    for _ in range(3):
        x0 = rng.randrange(W)
        for k, half in enumerate((1, 4, 2, 5, 3, 6)):
            for dx in range(-half, half + 1):
                c.set(x0 + dx, H - 18 + k * 2, DARK_GREY)
            for dx in range(-half + 2, half - 1):
                c.set(x0 + dx, H - 17 + k * 2, DARK_GREY)
        c.column(x0, H - 6, H, DARK_GREY)
    c.ground(3, rng, DARK_GREEN, c.dark)


def city(c, rng):
    """Hills behind a skyline: towers with windows, masts"""
    hills = noise(rng)
    c.ridge(lambda x: 14 + 5 * hills(x), H, c.mid, c.dark, rng=rng)
    x = 0
    while x < W:
        w = rng.randint(5, 13)
        if rng.random() < 0.7:
            h = rng.randint(6, 24)
            stepped = rng.random() < 0.3
            for xx in range(x, x + w):
                hh = h - (3 if stepped and xx - x in (0, w - 1) else 0)
                for y in range(H - hh, H):
                    window = (xx - x) % 3 == 1 and (y - (H - hh)) % 3 == 1
                    c.set(xx, y, LIGHT_GREY if window and rng.random() < 0.8 else c.light if xx == x else GREY)
            if h > 17 and rng.random() < 0.5:
                c.column(x + w // 2, H - h - 5, H - h, DARK_GREY)
        x += w + rng.randint(0, 5)
    c.ground(2, rng, DARK_GREY, DARK_GREEN)


def farmland(c, rng):
    """Rolling hills with fields and hedges, windmills"""
    far = noise(rng, ((1, 5), (0.5, 15), (0.25, 50)))
    c.ridge(lambda x: 20 + 6 * far(x), H, c.light, c.mid)
    near = noise(rng, ((1, 8), (0.5, 25)))
    c.ridge(lambda x: 12 + 5 * near(x), H, c.mid, c.dark)
    for x in range(W):
        for y in range(H - 16, H - 2):
            if c.px[y][x] != SKY and (x // 37 + y // 4) % 3 == 0:
                c.set(x, y, c.light if c.px[y][x] == c.mid else c.mid)
        if x % 37 == 0:
            for y in range(H - 14, H - 2):
                if c.px[y][x] != SKY:
                    c.set(x, y, DARK_GREEN)
    for _ in range(6):
        x0 = rng.randrange(W)
        base = H - 6
        c.column(x0, base - 11, base + 4, LIGHT_GREY)
        for k in range(1, 6):
            for dx, dy in ((k, -k), (-k, k)):
                c.set(x0 + dx, base - 11 + dy, LIGHT_GREY)
    c.ground(2, rng, DARK_GREEN, c.dark)


def castle_hills(c, rng):
    """Wooded domes, a castle on one"""
    back = noise(rng)
    c.ridge(lambda x: 21 + 6 * back(x), H, c.light, c.mid, rng=rng)
    domes = noise(rng, ((1, 9), (0.5, 22)))
    c.ridge(lambda x: 14 + 7 * domes(x), H, c.mid, c.dark)
    for x in range(0, W, 2):
        top = next((y for y in range(H) if c.px[y][x] in (c.mid, c.dark)), H)
        if top < H - 2:
            c.set(x, top - 1, c.dark)
            if rng.random() < 0.5:
                c.set(x, top - 2, DARK_GREEN)
    for _ in range(2):
        x0 = rng.randrange(W)
        top = next((y for y in range(H) if c.px[y][x0 % W] != SKY), H - 8)
        for dx in range(-7, 8):
            c.column(x0 + dx, top - 6, top + 2, GREY if dx > -3 else LIGHT_GREY)
            if dx % 2 == 0:
                c.set(x0 + dx, top - 7, GREY)
        for tx in (-7, 7):
            c.column(x0 + tx, top - 12, top - 6, GREY)
            c.set(x0 + tx, top - 13, DARK_GREY)
            c.set(x0 + tx - 1, top - 12, DARK_GREY)
            c.set(x0 + tx + 1, top - 12, DARK_GREY)
    c.ground(3, rng, DARK_GREEN, c.dark)


def prairie(c, rng):
    """Wide land, a low ridge, silos, a water tower, poles"""
    ridge = noise(rng, ((1, 6), (0.5, 20), (0.25, 60)))
    c.ridge(lambda x: 16 + 6 * ridge(x), H, c.light, c.mid, rng=rng)
    near = noise(rng, ((1, 12),))
    c.ridge(lambda x: 7 + near(x), H, c.mid, c.dark)
    for _ in range(5):
        x0 = rng.randrange(W)
        for k in range(rng.randint(1, 3)):
            hh = rng.randint(11, 16)
            for dx in range(4):
                c.column(x0 + k * 5 + dx, H - hh, H - 2, LIGHT_GREY if dx < 2 else GREY)
            for dx in range(1, 3):
                c.set(x0 + k * 5 + dx, H - hh - 1, GREY)
    for _ in range(2):
        x0 = rng.randrange(W)
        for dx in range(-3, 4):
            c.column(x0 + dx, H - 20, H - 15, GREY if dx > -2 else LIGHT_GREY)
        for dx in (-3, 3):
            c.column(x0 + dx, H - 15, H - 2, DARK_GREY)
    for x in range(0, W, 21):
        c.column(x, H - 10, H - 2, c.dark)
        for dx in (-2, -1, 1, 2):
            c.set(x + dx, H - 9, c.dark)
    c.ground(3, rng, c.mid, c.dark)


THEMES = [mesas, forest, savanna, volcanoes, glaciers, karst, city, farmland, castle_hills, prairie]


def backdrop(theme, order):
    """Backdrop `theme`'s pixels, row after row; order: the course colours'
    numbers, light to dark"""
    c = Canvas(*order)
    THEMES[theme](c, random.Random(0xBAC0 + theme))
    return c.pixels()
