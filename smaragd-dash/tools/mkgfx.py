#!/usr/bin/env python3
"""Smaragd Dash graphics: draws all tiles, the status font and icons in
code, builds one 256-colour palette and writes C sources and the files for
the disk.

Usage: mkgfx.py <outdir> [preview.png]

Output:
  <outdir>/gfx.h, <outdir>/gfx.c
    pal_r/g/b  palette, nybble-swapped as the VIC-IV wants it
    font_bits  8x16 glyphs, 1 bit per pixel; coloured at run time
    icon_gfx   8x16 full-colour glyphs for the status line
    title_row, rank_row
               palette entries per pixel row for the big letters and for
               the high score table's places
    sep_gfx    one 8x8 character for the line under the status
    pal1_r/g/b palette 1 for the title screen: the logo's colours, plus the
               status font's at the same entries as in palette 0
  <outdir>/tiles.bin
               16x16 tiles, 256 bytes each, a file of its own on the disk
               (the game loads it into bank 1, see video.h): two bytes of
               load address, then the tiles in the order the full-colour
               character data needs them: the left 8 pixels as 16 rows of
               8 bytes (two stacked characters), then the right 8 pixels
  <outdir>/logo.bin
               gfx/logo.png at LOGO_W x LOGO_H for the title screen, a file
               of its own on the disk: two bytes of load address, then the
               pixels in strips of 8 columns (each LOGO_H rows of 8 bytes),
               ready to be copied into the framebuffer column by column
  preview.png  every tile, enlarged, plus a mock cave (optional)

Pixel value 0 is the screen colour (black, flashes white when the exit
opens), so "None" in a drawing is background.
"""

import math
import os
import random
import re
import sys

from PIL import Image

T = 16  # tile size
LOGO_W, LOGO_H = 288, 144
LOGO_SRC = os.path.join(os.path.dirname(__file__), "..", "gfx", "logo.png")


def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(round(v))))


def mix(a, b, t):
    return tuple(clamp(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ramp(stops, t):
    """Colour at t (0..1) along a list of colour stops."""
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(int(t * n), n - 1)
    return mix(stops[i], stops[i + 1], t * n - i)


def steps(stops, t, levels):
    """Like ramp, but quantised to a few levels (pixel-art shading)."""
    t = max(0.0, min(1.0, t))
    return ramp(stops, round(t * (levels - 1)) / (levels - 1))


def hexc(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


class Noise:
    """Tileable value noise on a 16x16 torus."""

    def __init__(self, seed, cells):
        r = random.Random(seed)
        self.cells = cells
        self.v = [[r.random() for _ in range(cells)] for _ in range(cells)]

    def __call__(self, x, y):
        c = self.cells
        fx, fy = x * c / T, y * c / T
        x0, y0 = int(fx) % c, int(fy) % c
        x1, y1 = (x0 + 1) % c, (y0 + 1) % c
        tx, ty = fx - int(fx), fy - int(fy)
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a = self.v[y0][x0] + (self.v[y0][x1] - self.v[y0][x0]) * tx
        b = self.v[y1][x0] + (self.v[y1][x1] - self.v[y1][x0]) * tx
        return a + (b - a) * ty


def new_tile():
    return [[None] * T for _ in range(T)]


# ---------------------------------------------------------------- terrain

def draw_dirt():
    n1, n2 = Noise(11, 4), Noise(12, 8)
    stops = [hexc("2a170c"), hexc("4a2c16"), hexc("6b4322"), hexc("8a5a30")]
    t = new_tile()
    for y in range(T):
        for x in range(T):
            v = 0.65 * n1(x, y) + 0.35 * n2(x, y)
            t[y][x] = steps(stops, v * 1.15 - 0.1, 5)
    # pebbles with a lit top and a shadow below
    r = random.Random(5)
    for _ in range(7):
        px, py = r.randrange(T), r.randrange(T)
        w = r.choice((1, 2, 2))
        for dx in range(w):
            t[py][(px + dx) % T] = hexc("b08050")
            t[(py + 1) % T][(px + dx) % T] = hexc("7a5030")
            t[(py + 2) % T][(px + dx) % T] = hexc("241208")
    return t


def draw_brick(mortar=hexc("2a2224"), glow=None):
    t = new_tile()
    r = random.Random(7)
    base = [hexc("8c3a24"), hexc("9c4a2c"), hexc("7c3220"), hexc("a45434")]
    for row in range(4):
        y0 = row * 4
        shift = 0 if row % 2 == 0 else 4
        for b in range(3):
            c = r.choice(base)
            for y in range(y0, y0 + 3):
                for x in range(T):
                    if (x + shift) // 8 != b and not (b == 2 and (x + shift) // 8 == 2):
                        pass
                    bx = (x + shift) % 8
                    if bx == 7:
                        continue
                    if ((x + shift) // 8) % 2 != b % 2:
                        continue
                    shade = c
                    if y == y0:
                        shade = mix(c, hexc("e09070"), 0.45)
                    elif y == y0 + 2:
                        shade = mix(c, hexc("200808"), 0.45)
                    if bx == 0 and y != y0:
                        shade = mix(shade, hexc("e09070"), 0.2)
                    t[y][x] = shade
    for y in range(T):
        for x in range(T):
            if t[y][x] is None:
                t[y][x] = glow[(x + y) % len(glow)] if glow else mortar
    return t


def draw_steel():
    t = new_tile()
    stops = [hexc("3c4456"), hexc("5c6880"), hexc("7c88a0"), hexc("a8b4c8")]
    n = Noise(21, 8)
    for y in range(T):
        for x in range(T):
            v = 0.45 + 0.25 * (1 - (x + y) / 30) + 0.12 * (n(x, y) - 0.5)
            if y % 3 == 1:
                v += 0.04  # brushed lines
            t[y][x] = steps(stops, v, 6)
    for i in range(T):
        t[0][i] = hexc("c8d4e8")
        t[i][0] = hexc("c8d4e8")
        t[T - 1][i] = hexc("1c2030")
        t[i][T - 1] = hexc("1c2030")
    t[T - 1][0] = hexc("5c6880")
    t[0][T - 1] = hexc("5c6880")
    for (rx, ry) in ((3, 3), (11, 3), (3, 11), (11, 11)):
        t[ry][rx] = hexc("e8f0ff")
        t[ry][rx + 1] = hexc("8c98b0")
        t[ry + 1][rx] = hexc("8c98b0")
        t[ry + 1][rx + 1] = hexc("262c3c")
    return t


# ---------------------------------------------------------------- objects

LIGHT = (-0.55, -0.65, 0.52)


def norm(v):
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v)


def draw_boulder():
    t = new_tile()
    cx, cy, r = 7.5, 8.0, 7.6
    n = Noise(31, 4)
    n2 = Noise(32, 8)
    L = norm(LIGHT)
    stops = [hexc("1e1a18"), hexc("4a423c"), hexc("78685a"), hexc("a8968a"), hexc("d8cabc")]
    for y in range(T):
        for x in range(T):
            dx, dy = (x + 0.5 - cx) / r, (y + 0.5 - cy) / r * 1.05
            d2 = dx * dx + dy * dy
            if d2 > 1:
                continue
            nz = math.sqrt(1 - d2)
            lam = max(0, dx * L[0] + dy * L[1] + nz * L[2])
            v = 0.12 + 0.78 * lam + 0.22 * (n(x, y) - 0.5) + 0.1 * (n2(x, y) - 0.5)
            if d2 > 0.78:
                v *= 0.55  # dark rim
            t[y][x] = steps(stops, v, 7)
    # a crack and a highlight
    for (x, y) in ((9, 9), (10, 10), (10, 11), (11, 12)):
        t[y][x] = hexc("1e1a18")
    t[4][5] = hexc("f4ece0")
    t[4][4] = hexc("d8cabc")
    t[5][4] = hexc("d8cabc")
    return t


def gem_shape():
    """Emerald cut: an octagon with a flat table in the middle. Returns a
    facet label per pixel."""
    lab = [[None] * T for _ in range(T)]
    x0, x1, y0, y1, cut = 1, 14, 2, 13, 3
    tx0, tx1, ty0, ty1 = 5, 10, 5, 10
    for y in range(T):
        for x in range(T):
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue
            # cut corners
            if (x - x0) + (y - y0) < cut or (x1 - x) + (y - y0) < cut or \
               (x - x0) + (y1 - y) < cut or (x1 - x) + (y1 - y) < cut:
                continue
            edge = ((x - x0) + (y - y0) == cut or (x1 - x) + (y - y0) == cut or
                    (x - x0) + (y1 - y) == cut or (x1 - x) + (y1 - y) == cut or
                    x in (x0, x1) or y in (y0, y1))
            if tx0 <= x <= tx1 and ty0 <= y <= ty1:
                f = "table"
            else:
                dx = max(tx0 - x, 0, x - tx1) / 4.0
                dy = max(ty0 - y, 0, y - ty1) / 3.0
                if dy > dx * 1.3:
                    f = "top" if y < ty0 else "bottom"
                elif dx > dy * 1.3:
                    f = "left" if x < tx0 else "right"
                else:
                    f = ("t" if y < ty0 else "b") + ("l" if x < tx0 else "r")
            lab[y][x] = ("edge", f) if edge else ("in", f)
    return lab


def draw_emerald(frame, frames=8):
    lab = gem_shape()
    shade = {"top": 0.82, "tl": 0.95, "tr": 0.62, "left": 0.7, "right": 0.42,
             "bl": 0.4, "br": 0.22, "bottom": 0.3, "table": 0.6}
    stops = [hexc("04281a"), hexc("0c5a30"), hexc("16904a"), hexc("3cc870"),
             hexc("8cf0b0"), hexc("e4fff0")]
    t = new_tile()
    # a bright band sweeps diagonally over the stone
    band = -6 + frame * 4.5
    for y in range(T):
        for x in range(T):
            if lab[y][x] is None:
                continue
            kind, f = lab[y][x]
            v = shade[f]
            if f == "table":
                v = 0.62 + 0.18 * (1 - (x - 5 + y - 5) / 10)
            d = (x + y) - 15 - band
            if abs(d) < 2.2:
                v += 0.28 * (1 - abs(d) / 2.2)
            if kind == "edge":
                v = v * 0.45
            t[y][x] = steps(stops, v, 9)
    # sparkle: a little star on the top-left facet in some frames
    star = {5: (4, 4, 1), 6: (4, 4, 2), 7: (4, 4, 1)}.get(frame)
    if star:
        sx, sy, s = star
        t[sy][sx] = hexc("ffffff")
        for i in range(1, s + 1):
            for (ax, ay) in ((sx + i, sy), (sx - i, sy), (sx, sy + i), (sx, sy - i)):
                if 0 <= ax < T and 0 <= ay < T:
                    t[ay][ax] = hexc("ffffff") if i == 1 else hexc("c8ffe0")
    return t


# Rockford: the adventurer from the title logo (fedora, leather jacket,
# white shirt, jeans, boots). Hand-drawn; letters are colours. He is put
# together from a head, a body and legs, seen from eight sides; the left
# ones are the right ones mirrored.
ROCK_PAL = {
    "k": hexc("140e10"),   # outline
    "H": hexc("a8642a"), "h": hexc("d89448"), "d": hexc("4a2410"),  # hat, band
    "r": hexc("4a2814"),                                            # hair
    "S": hexc("f4bc8c"), "s": hexc("c88458"),                       # skin
    "e": hexc("101028"), "E": hexc("f4f4ff"), "m": hexc("a83c3c"),  # eyes, mouth
    "J": hexc("82461e"), "j": hexc("552d14"), "l": hexc("b06a32"),  # jacket
    "T": hexc("ecece0"),                                            # shirt
    "B": hexc("3c64be"), "b": hexc("243c82"),                       # jeans
    "W": hexc("8a5224"), "w": hexc("4e2c10"),                       # boots
}

ROCK_HAT = [
    "......kkkk......",
    "....kkhhhHkk....",
    "...khHHHHHHHk...",
    "...kddddddddk...",
    ".kkhhHHHHHHHHkk.",
]
ROCK_HEADS = {
    "front": ROCK_HAT + [
        "..kkrSSSSSSrkk..",
        "...kSEeSSeESk...",
        "...kSSeSSeSSk...",
        "....ksSmmSsk....",
    ],
    "back": ROCK_HAT + [
        "..kkrrrrrrrrkk..",
        "...ksrrrrrrsk...",
        "...ksrrrrrrsk...",
        "....kssSSssk....",
    ],
    "right": [
        "....kkkkk.......",
        "...khhhHHk......",
        "..khHHHHHHk.....",
        "..kddddddddk....",
        "kkhhHHHHHHHHHkk.",
        ".kkrrrSSSSSSkk..",
        "..krrSsSSSEeSk..",
        "..krssSSSSEeSSk.",
        "...krsSSSSSmkk..",
    ],
    "front-right": [
        ".....kkkkk......",
        "....khhhHHkk....",
        "...khHHHHHHHk...",
        "...kddddddddk...",
        ".kkhhHHHHHHHHkk.",
        "..kkrrSSSSSSkk..",
        "...krsSEeSEeSk..",
        "...krsSSeSSeSk..",
        "....kssSSmmsk...",
    ],
    "back-right": [
        "......kkkkk.....",
        "....kkhhhHHk....",
        "...khHHHHHHHk...",
        "...kddddddddk...",
        ".kkhhHHHHHHHHkk.",
        "..kkrrrrrrrSkk..",
        "...krrrrrrsSk...",
        "...krrrrrrsSk...",
        "....krrrssSk....",
    ],
}
ROCK_BODIES = {
    "front": ["...kJJkTTkJJk...", "..kJlJJTTJJlJk..", "..kSkjJJJJjkSk.."],
    "front-swing": ["...kJJkTTkJJk...", "..kJlJJTTJJlJk..", "..kjkjJJJJjkSk.."],
    "front-right": ["...kJJJkTTJJk...", "..kJlJJJTTJlk...", "..kSkjJJJJjkSk.."],
    "back": ["...kJJjjjjJJk...", "..kJlJJJJJJlJk..", "..kSkJJJJJJkSk.."],
    "back-swing": ["...kJJjjjjJJk...", "..kJlJJJJJJlJk..", "..kSkJJJJJJkjk.."],
    "right": ["....kJlTTJJk....", "....kJJlTJJk....", "....kJSkJJJk...."],
    # running: near arm back and far arm forward, or the near fist forward
    "right-back": ["...kJJlTTJjjk...", "..kJJJlJTJjsk...", ".kSkJJJJJJk....."],
    "right-fist": ["...kJJlTTJkSSk..", "...kjJJlTJJkkk..", "...kjJJJJJk....."],
}
ROCK_LEGS = {
    "front": ["....kBBbbBBk....", "....kBBkkBBk....", "....kBbkkbBk....", "...kWWWkkWWWk..."],
    "front-pass": ["....kBBbbBBk....", "....kBBkkBBk....", "....kBbkkbBk....", "....kWWkkWWk...."],
    "front-step": ["....kBBbbBBk....", "...kWWWkkbBk....", "....kkk.kWWWk..."],
    "front-tap": ["....kBBbbBBk....", "....kBBkkBBk....", "....kBbkkWWWk...", "...kWWWk.kkkk..."],
    "back": ["....kBBbbBBk....", "....kBBkkBBk....", "....kBbkkbBk....", "...kwwwkkwwwk..."],
    "back-pass": ["....kBBbbBBk....", "....kBBkkBBk....", "....kBbkkbBk....", "....kwwkkwwk...."],
    "back-step": ["....kBBbbBBk....", "...kwwwkkbBk....", "....kkk.kwwwk..."],
    "right": [".....kBBbBk.....", ".....kBBbBk.....", ".....kBkbBk.....", ".....kWWkWWWk..."],
    # running: legs apart (the near one forward, or the far one), and
    # passing (the far knee up, or the near one)
    "right-near": ["....kbbBBBBk....", "...kbbk..kBBk...", "..kwwk....kWWWk."],
    "right-far": ["....kBBBBbbk....", "...kBBk..kbbk...", "..kWWWk...kwwwk."],
    "right-pass-far": ["....kBBBbbk.....", "....kBBkbbbk....", ".....kBBkwwk....", ".....kWWWk......"],
    "right-pass-near": ["....kbbBBBk.....", "....kbbkBBBk....", ".....kbbkWWk....", ".....kwwwk......"],
}


def rock_rows(head, body, legs, blink=False):
    """A Rockford tile from head, body and legs; with three rows of legs (a
    stride) he is one pixel lower."""
    h = list(ROCK_HEADS[head])
    if blink:
        h[6] = h[6].replace("E", "S").replace("e", "S")
        h[7] = h[7].replace("e", "k")
    rows = h + ROCK_BODIES[body] + ROCK_LEGS[legs]
    return ["." * T] * (T - len(rows)) + rows


def mirror(rows):
    return [r[::-1] for r in rows]


def from_rows(rows, pal):
    t = new_tile()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y][x] = pal[ch]
    return t


def draw_rockford_set():
    """RF_VIEW0-7: standing, seen from behind (0), then turning clockwise
    from above: right (2), front (4), left (6); a view is 2 * DIR_*.
    RF_BLINK, RF_TAP: idle, from the front. RF_UP0-3, RF_RIGHT0-3,
    RF_DOWN0-3, RF_LEFT0-3 (in the order of DIR_*): walking, a step with
    the one foot (stride, passing), then with the other."""
    views = [rock_rows("back", "back", "back"),
             rock_rows("back-right", "back", "back"),
             rock_rows("right", "right", "right"),
             rock_rows("front-right", "front-right", "front"),
             rock_rows("front", "front", "front")]
    views += [mirror(v) for v in views[3:0:-1]]
    walk = {
        "UP": [rock_rows("back", "back-swing", "back-step"), rock_rows("back", "back", "back-pass"),
               mirror(rock_rows("back", "back-swing", "back-step")), rock_rows("back", "back", "back-pass")],
        "RIGHT": [rock_rows("right", "right-back", "right-near"), rock_rows("right", "right", "right-pass-far"),
                  rock_rows("right", "right-fist", "right-far"), rock_rows("right", "right", "right-pass-near")],
        "DOWN": [rock_rows("front", "front-swing", "front-step"), rock_rows("front", "front", "front-pass"),
                 mirror(rock_rows("front", "front-swing", "front-step")), rock_rows("front", "front", "front-pass")],
    }
    walk["LEFT"] = [mirror(r) for r in walk["RIGHT"]]
    out = {f"RF_VIEW{i}": from_rows(v, ROCK_PAL) for i, v in enumerate(views)}
    out["RF_BLINK"] = from_rows(rock_rows("front", "front", "front", blink=True), ROCK_PAL)
    out["RF_TAP"] = from_rows(rock_rows("front", "front", "front-tap"), ROCK_PAL)
    for d in ("UP", "RIGHT", "DOWN", "LEFT"):
        for i, rows in enumerate(walk[d]):
            out[f"RF_{d}{i}"] = from_rows(rows, ROCK_PAL)
    return out


def draw_firefly(frame):
    t = new_tile()
    ang = frame * math.pi / 8
    stops = [hexc("400804"), hexc("a01c08"), hexc("f06414"), hexc("ffb030"), hexc("fff4c0")]
    for y in range(T):
        for x in range(T):
            dx, dy = x + 0.5 - 8, y + 0.5 - 8
            rx = dx * math.cos(ang) - dy * math.sin(ang)
            ry = dx * math.sin(ang) + dy * math.cos(ang)
            sq = max(abs(rx), abs(ry))          # rotating square ring
            ring = max(0, 1 - abs(sq - 5.2) / 1.6)
            core = max(0, 1 - math.hypot(dx, dy) / 3.2)
            v = max(ring * 0.85, core)
            if v < 0.12:
                continue
            t[y][x] = steps(stops, v, 6)
    return t


def draw_butterfly(frame):
    t = new_tile()
    span = [7.0, 5.0, 2.4, 5.0][frame]
    wing = [hexc("101850"), hexc("2850c8"), hexc("30b0f0"), hexc("a0f0ff")]
    for y in range(T):
        for x in range(T):
            dx, dy = abs(x + 0.5 - 8), y + 0.5 - 8
            if dx < 1:
                continue
            # two lobes per side: big upper wing, small lower wing
            u = (dx / span) ** 2 + ((dy + 2.2) / 4.6) ** 2
            l = (dx / (span * 0.75)) ** 2 + ((dy - 3.2) / 3.0) ** 2
            v = min(u, l)
            if v > 1:
                continue
            c = steps(wing, 1.05 - v * 0.9, 5)
            if v > 0.78:
                c = hexc("0c0c30")
            t[y][x] = c
            if 0.25 < u < 0.4 and dy < -1:
                t[y][x] = hexc("f070e0")  # eye spots
    for y in range(3, 14):
        t[y][7] = hexc("1c1028")
        t[y][8] = hexc("3c2448")
    t[2][6] = t[1][5] = hexc("1c1028")
    t[2][9] = t[1][10] = hexc("1c1028")
    return t


# What the creatures leave behind for a moment, in four stages: only a few
# pixels, it is meant to be seen in passing.

EMBERS_RED = [["fff4c0", "ffd060"], ["ffb030", "f06414"], ["e04810", "a01c08"], ["8a1808", "5a1006"]]
EMBERS_BLUE = [["ffffff", "a0f0ff"], ["a0f0ff", "30b0f0"], ["30b0f0", "2850c8"], ["2850c8", "101850"]]


def draw_embers(stage, colours=EMBERS_RED):
    """Firefly: embers that rise a little and die down, white-hot to dark
    red (the alternative firefly's in its blue)."""
    t = new_tile()
    cols = [hexc(c) for c in colours[stage]]
    r = random.Random(70)
    embers = [(r.uniform(2, 13), r.uniform(5, 13), r.uniform(-0.6, 0.6)) for _ in range(5)]
    for k, (x, y, drift) in enumerate(embers[:5 - stage]):
        ex = int(round(x + drift * stage * 2))
        ey = int(round(y - stage * 1.6))
        if 0 <= ex < T and 0 <= ey < T:
            t[ey][ex] = cols[k & 1]
            if stage == 0 and k < 2 and ey + 1 < T:
                t[ey + 1][ex] = cols[1]  # the hottest still have a tail
    return t


# The glitter's four colours, bright to dark, and a hint of the wings' eye spots
GLITTER_BLUE = (["a0f0ff", "30b0f0", "2850c8", "1c3480"], "a050a0")     # butterfly
GLITTER_ORANGE = (["ffb030", "f06414", "a01c08", "5a1006"], "ffd060")   # alternative butterfly
GLITTER_STONE = (["d8cabc", "a8968a", "78685a", "4a423c"], "a8968a")    # stonefly
GLITTER_GREEN = (["8cf0b0", "3cc870", "16904a", "0c5a30"], "a0f0ff")    # dragonfly
GLITTER_EMERALD = (["e4fff0", "8cf0b0", "3cc870", "16904a"], "8cf0b0")  # a falling emerald


def draw_glitter(stage, colours=GLITTER_BLUE):
    """Butterfly: a soft glitter in the colours of its wings that fades
    slowly - a calm trail behind the flutter (in each flier's colours)."""
    t = new_tile()
    r = random.Random(80 + stage)
    cols = [hexc(c) for c in colours[0]]
    n = [2, 2, 2, 1][stage]
    for k in range(n):
        x, y = r.randint(2, 13), r.randint(2, 13)
        c = cols[stage] if k == 0 else cols[min(stage + 1, 3)]
        if k == 1 and stage == 1:
            c = hexc(colours[1])
        t[y][x] = c
        if k == 0 and stage == 0:  # a small star: arms two shades darker
            for ax, ay in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                t[ay][ax] = cols[2]
    return t


def draw_mist(stage):
    """Ghost: a faint breath of mist that drifts up and is gone - a few
    dim pixels, so the dark shows through."""
    t = new_tile()
    cols = [hexc("6a7486"), hexc("4e5768"), hexc("3a4250"), hexc("2a303c")]
    r = random.Random(91)
    puffs = [(r.uniform(5, 11), r.uniform(7, 11), r.uniform(2.6, 3.4)) for _ in range(2)]
    for k, (px, py, pr) in enumerate(puffs[:2 - stage // 2]):
        cy = py - stage * 1.2
        rad = pr - stage * 0.3
        for y in range(T):
            for x in range(T):
                d = math.hypot(x + 0.5 - px, (y + 0.5 - cy) * 1.5)
                if d < rad and (x + 2 * y + k + stage) % 4 == 0:
                    t[y][x] = cols[stage]
    return t


CRUMBS_DIRT = [["8a5a30", "6b4322"], ["6b4322", "4a2c16"], ["4a2c16", "3a2210"]]
CRUMBS_BITER = [["8c30a0", "501860"], ["501860", "3a1046"], ["3a1046", "200828"]]
CRUMBS_GRIT = [["78685a", "4a423c"], ["4a423c", "3a3430"], ["3a3430", "1e1a18"]]


def draw_crumbs(stage, colours=CRUMBS_DIRT):
    """Dug dirt: a few crumbs that trickle down and darken - quietly, it
    happens at every step through dirt (and behind a cow; in purple behind
    the biter, grey grit behind the chasing boulder)."""
    t = new_tile()
    cols = [hexc(c) for c in colours[stage]]
    r = random.Random(90)
    crumbs = [(r.randint(3, 12), r.uniform(3, 9)) for _ in range(5)]
    for k, (x, y) in enumerate(crumbs[:[3, 2, 1][stage]]):
        cy = int(round(y + stage * (2.2 + 0.4 * k)))
        if cy < T:
            t[cy][x] = cols[k & 1]
    return t


def draw_drops(stage):
    """Bladder: two tiny bubbles that rise after it and burst - a pixel or
    two, pale blue, then gone."""
    t = new_tile()
    cols = [hexc("a0f0ff"), hexc("5aa8d0"), hexc("2c6890")]
    for k, (x, y) in enumerate(((6, 11), (10, 13))[:2 - stage // 2]):
        cy = y - stage * 2 - k
        if stage == 0 and k == 0:  # the bigger one: a little ring
            plot(t, [(x, cy - 1), (x - 1, cy), (x + 1, cy), (x, cy + 1)], cols[1])
        else:
            plot(t, [(x, cy)], cols[min(stage, 2)])
    return t


def draw_smoke(stage):
    """Rocket: a small puff of smoke that thins out and fades, with a
    spark at first"""
    t = new_tile()
    cols = [hexc("8a8e98"), hexc("5c606a"), hexc("3a3d44")]
    r = 2.6 - 0.5 * stage
    for y in range(T):
        for x in range(T):
            d = math.hypot(x + 0.5 - 8, (y + 0.5 - 8 + stage) * 1.2)
            if d < r and (x + y + stage) % 2 == 0:
                t[y][x] = cols[stage]
    if stage == 0:
        plot(t, [(8, 8)], hexc("ffc840"))
    return t


# The dust beside a landing boulder, for the cell on its right (x from the
# boulder's side): light and close first, then thinner, further out and a
# little higher. Letters: 1 light, 2 middle, 3 dark.
DUST = [
    ["               ",
     "               ",
     "1              ",
     "21 2           ",
     "112            "],
    ["  2  3         ",
     " 3 2           ",
     "   3  3        ",
     "  3  3         ",
     "               "],
]
DUST_COLS = {"1": hexc("a09484"), "2": hexc("7a6e62"), "3": hexc("4e463e")}


def draw_dust(stage, right):
    """A boulder lands: a puff of dust at its foot, in the cell beside it
    (right: the cell on its right, the puff at its left edge)."""
    t = new_tile()
    for y, row in enumerate(DUST[stage]):
        for x, ch in enumerate(row):
            if ch != " ":
                t[11 + y][x if right else T - 1 - x] = DUST_COLS[ch]
    return t


def draw_explosion(stage):
    t = new_tile()
    rad = [3.5, 6.0, 7.6, 7.8, 7.0][stage]
    hot = [1.0, 0.95, 0.8, 0.5, 0.25][stage]
    smoke = [0, 0.1, 0.3, 0.6, 0.85][stage]
    fire = [hexc("400800"), hexc("b02008"), hexc("f07010"), hexc("ffc840"), hexc("fffce8")]
    smk = [hexc("1c1414"), hexc("3c3030"), hexc("5c5050")]
    n = Noise(40 + stage, 8)
    r = random.Random(50 + stage)
    for y in range(T):
        for x in range(T):
            d = math.hypot(x + 0.5 - 8, y + 0.5 - 8) / rad
            d += 0.35 * (n(x, y) - 0.5)
            if d > 1:
                continue
            v = (1 - d) * hot + 0.25 * (n(x, y) - 0.5)
            if r.random() < smoke * (0.4 + 0.6 * d):
                t[y][x] = steps(smk, n(x, y) * 1.4 - 0.2, 3)
            elif v > 0.05:
                t[y][x] = steps(fire, v + 0.15, 7)
    return t


def draw_birth(stage):
    """Rockford appears: a ring of sparks closing in."""
    t = new_tile()
    rad = [7.0, 4.5, 2.2][stage]
    cols = [hexc("2060a0"), hexc("60c0ff"), hexc("ffffff")]
    for i in range(12):
        a = i * math.pi / 6 + stage * 0.4
        x = int(round(7.5 + rad * math.cos(a)))
        y = int(round(7.5 + rad * math.sin(a)))
        if 0 <= x < T and 0 <= y < T:
            t[y][x] = cols[2]
            for (ax, ay) in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= ax < T and 0 <= ay < T and t[ay][ax] is None:
                    t[ay][ax] = cols[1]
    c = 1 + stage
    for y in range(8 - c, 8 + c):
        for x in range(8 - c, 8 + c):
            if math.hypot(x + 0.5 - 8, y + 0.5 - 8) < c and t[y][x] is None:
                t[y][x] = cols[0] if stage < 2 else cols[1]
    return t


def draw_door(lit, inbox):
    """In- and outbox: a doorway in a steel frame."""
    t = draw_steel()
    glow = [hexc("082010"), hexc("106830"), hexc("30c060"), hexc("b0ffc8")] if not inbox else \
           [hexc("081828"), hexc("104878"), hexc("3090e0"), hexc("c0e8ff")]
    for y in range(3, 15):
        for x in range(3, 13):
            if y < 6 and math.hypot(x + 0.5 - 8, y - 6) > 5:
                continue  # arched top
            edge = x in (3, 12) or y == 14 or (y < 6 and math.hypot(x + 0.5 - 8, y - 6) > 4)
            v = (0.95 if edge else 0.15 + 0.5 * (y - 3) / 11) * (1.0 if lit else 0.45)
            t[y][x] = steps(glow, v, 4)
    return t


def draw_amoeba(frame):
    t = new_tile()
    n = Noise(60, 4)
    stops = [hexc("200828"), hexc("501860"), hexc("8c30a0"), hexc("c868d8"), hexc("f4c0ff")]
    for y in range(T):
        for x in range(T):
            ph = frame * math.pi / 2
            v = n(x, y) + 0.18 * math.sin(ph + (x + y) * 0.7) + 0.12 * math.sin(ph * 2 + x * 1.3 - y)
            t[y][x] = steps(stops, v, 6)
    # bubbles that move with the frames
    for (bx, by, rr) in ((4, 4, 2), (11, 9, 1), (6, 12, 1)):
        by = (by - frame * 2) % T
        for y in range(by - rr, by + rr + 1):
            for x in range(bx - rr, bx + rr + 1):
                if math.hypot(x - bx, y - by) <= rr:
                    t[y % T][x % T] = hexc("f4c0ff") if (x - bx) + (y - by) < 0 else hexc("c868d8")
    return t


def draw_magic(frame):
    glow = [ramp([hexc("ff3060"), hexc("ffd040"), hexc("40ff90"), hexc("40a0ff"), hexc("ff3060")],
                 ((i + frame * 2) % 8) / 8) for i in range(8)]
    return draw_brick(glow=glow)


def draw_cover(frame):
    """A covered cell, as the C64 shows it: the steel wall, moved up by
    two pixel rows in each of the eight frames"""
    steel = draw_steel()
    return [steel[(y + 2 * frame) % T][:] for y in range(T)]


def draw_space():
    return new_tile()


def draw_cursor():
    """The editor's cursor: a bright frame with a dark one inside it, so
    it shows on every tile; the rest is transparent"""
    t = new_tile()
    for i in range(T):
        for a, b in ((i, 0), (i, T - 1), (0, i), (T - 1, i)):
            t[b][a] = hexc("fff8c0")
        if 0 < i < T - 1:
            for a, b in ((i, 1), (i, T - 2), (1, i), (T - 2, i)):
                t[b][a] = hexc("301808")
    return t


# ---------------------------------------------------------------- font

FONT5x7 = {
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111",
    "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00010 01100",
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110",
    "D": "11100 10010 10001 10001 10001 10010 11100",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111",
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110",
    "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 10001 01010 00100 00100 00100",
    "Z": "11111 00001 00010 00100 01000 10000 11111",
    " ": "00000 00000 00000 00000 00000 00000 00000",
    "/": "00001 00001 00010 00100 01000 10000 10000",
    ":": "00000 01100 01100 00000 01100 01100 00000",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    "!": "00100 00100 00100 00100 00100 00000 00100",
    "-": "00000 00000 00000 11111 00000 00000 00000",
    ",": "00000 00000 00000 00000 01100 00100 01000",
    "x": "00000 10001 01010 00100 01010 10001 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000",
    "*": "00000 10101 01110 11111 01110 10101 00000",
    # arrows, for the gravity in GDash's caves: up, right, left, down
    "^": "00100 01110 10101 00100 00100 00100 00100",
    ">": "01000 00100 00010 11111 00010 00100 01000",
    "<": "00010 00100 01000 11111 01000 00100 00010",
    "_": "00100 00100 00100 00100 10101 01110 00100",
}

# Letters that the automatic bold would clog up, drawn bold already (7 wide)
FONT_BOLD = {
    "M": "1100011 1110111 1111111 1101011 1100011 1100011 1100011",
    "W": "1100011 1100011 1100011 1101011 1111111 1110111 1100011",
}

FONT_RAMP = [hexc("fff8c0"), hexc("ffe060"), hexc("ffb020"), hexc("e06810")]
FONT_SHADOW = hexc("301808")

# Big title letters: 16 colours of their own (one per two pixel rows), so
# the program can cycle them for a moving shine. The ramp is a closed loop.
TITLE_RAMP = [hexc("0c5a30"), hexc("16904a"), hexc("3cc870"), hexc("8cf0b0"),
              hexc("f0fff4"), hexc("8cf0b0"), hexc("3cc870"), hexc("16904a")]


# The high score table: gold (the font's own), silver and bronze for the
# best three, ice blue for the others; a new entry shines green like the
# big letters
RANK_RAMPS = [FONT_RAMP,
              [hexc("ffffff"), hexc("dce4f4"), hexc("a8b4d0"), hexc("68749c")],
              [hexc("ffe0c0"), hexc("f0a868"), hexc("c07038"), hexc("7c4020")],
              [hexc("e0f8ff"), hexc("90d4f4"), hexc("4890d0"), hexc("284c8c")]]


def rank_colours():
    return [ramp(r, max(0, y - 1) / 13) for r in RANK_RAMPS for y in range(16)]


def title_colours():
    return [ramp(TITLE_RAMP + [TITLE_RAMP[0]], i / 16) for i in range(16)]


def font_glyph_bits(ch):
    """8x16 bits: the 5x7 glyph made bold (6 wide), rows doubled."""
    out = [0] * 16
    if ch in FONT_BOLD:
        rows = [int(b, 2) << 1 for b in FONT_BOLD[ch].split()]
    else:
        rows = [int(b, 2) << 3 for b in FONT5x7[ch].split()]  # 5 bits at the top of a byte
        rows = [v | v >> 1 for v in rows]                       # bold
    for r, v in enumerate(rows):
        out[1 + 2 * r] = out[2 + 2 * r] = v & 0xFF
    return out


def font_row_colours():
    return [ramp(FONT_RAMP, max(0, r - 1) / 13) for r in range(16)]


def render_glyph(bits, cols):
    """For the preview: colour a glyph as the program does at run time."""
    t = [[None] * 8 for _ in range(16)]
    for y in range(16):
        for x in range(8):
            if bits[y] & (0x80 >> x):
                t[y][x] = cols[y]
            elif y and x and bits[y - 1] & (0x80 >> (x - 1)):
                t[y][x] = FONT_SHADOW
    return t


def draw_icon_emerald():
    t = [[None] * 8 for _ in range(16)]
    rows = ["..kkkk..", ".kLGGdk.", "kLGGGGdk", "kGGGGGdk", "kGGGGddk", ".kGGddk.", "..kddk..", "...kk..."]
    pal = {"k": hexc("04281a"), "L": hexc("e4fff0"), "G": hexc("3cc870"), "d": hexc("16904a")}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y + 4][x] = pal[ch]
    return t


def draw_icon_clock():
    t = [[None] * 8 for _ in range(16)]
    rows = ["..kkkk..", ".kWWWWk.", "kWWkWWWk", "kWWkWWWk", "kWWkkkWk", "kWWWWWWk", ".kWWWWk.", "..kkkk.."]
    pal = {"k": hexc("301808"), "W": hexc("fff8c0")}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y + 4][x] = pal[ch]
    return t


def draw_icon_life():
    t = [[None] * 8 for _ in range(16)]
    rows = ["..kkkk..", ".khHHHk.", ".kddddk.", "kHHHHHHk", ".kSSSSk.", ".kSeeSk.", "..kSSk..", "...kk..."]
    pal = dict(ROCK_PAL)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y + 4][x] = pal[ch]
    return t


SEP_ROWS = [None, hexc("4a2c10"), hexc("a07020"), hexc("ffd860"), hexc("c08828"), hexc("5a3410"), None, None]


# ---------------------------------------------------------------- GDash's elements

# The elements of GDash's caves (the own caves, src/gdengine.c) that the
# game's own caves do not have, drawn in the same way. They may bring only
# a few colours of their own (GD_NEW_COLOURS): the palette has room for 254,
# most of them taken by the game's own tiles, which keep theirs.

def lum(c):
    return (0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]) / 255


def by_lum(t, stops, levels=6, lo=0.0, hi=1.0):
    """The tile in other colours: each pixel by its brightness along stops"""
    return [[None if c is None else steps(stops, (lum(c) - lo) / (hi - lo), levels) for c in row] for row in t]


def overlay(base, top):
    out = [list(row) for row in base]
    for y in range(T):
        for x in range(T):
            if top[y][x] is not None:
                out[y][x] = top[y][x]
    return out


def sphere(t, cx, cy, r, stops, levels=6, rim=0.55, squash=1.0, noise=None):
    """A shaded ball, lit from the top left, into t"""
    L = norm(LIGHT)
    for y in range(T):
        for x in range(T):
            dx, dy = (x + 0.5 - cx) / r, (y + 0.5 - cy) / (r * squash)
            d2 = dx * dx + dy * dy
            if d2 > 1:
                continue
            nz = math.sqrt(1 - d2)
            v = 0.12 + 0.8 * max(0, dx * L[0] + dy * L[1] + nz * L[2])
            if noise:
                v += 0.2 * (noise(x, y) - 0.5)
            if d2 > 0.8:
                v *= rim
            t[y][x] = steps(stops, v, levels)
    return t


def plot(t, pts, c):
    for x, y in pts:
        if 0 <= x < T and 0 <= y < T:
            t[y][x] = c


def from_pic(rows, pal, t=None):
    """A tile from a picture in characters (pal: character -> colour; '.'
    and ' ' stay as they are)"""
    t = t or new_tile()
    oy = (T - len(rows)) // 2
    for y, row in enumerate(rows):
        ox = (T - len(row)) // 2
        for x, ch in enumerate(row):
            if ch not in ". ":
                t[oy + y][ox + x] = pal[ch]
    return t


def liquid(seed, stops, frame, bubbles=True, frames=2):
    """Water, acid, lava, slime: a surface that moves with the frames. With
    four frames (water) the waves move on a quarter of their length each,
    so they flow; with two they rock to and fro."""
    t = new_tile()
    n = Noise(seed, 4)
    shift = 4 if frames == 2 else 2 * math.pi / 0.8 / frames
    rise = 3 if frames == 2 else T // frames
    for y in range(T):
        for x in range(T):
            v = 0.55 * n(x, y) + 0.3 * math.sin((x + frame * shift) * 0.8 + y * 0.35) * 0.5 + 0.25
            t[y][x] = steps(stops, v, 5)
    if bubbles:
        for bx, by in ((4, 11), (11, 5), (8, 13)):
            by = (by - frame * rise) % T
            plot(t, [(bx, by)], stops[-1])
            plot(t, [(bx + 1, by + 1)], stops[-2])
    return t


def draw_slime(frame):
    t = liquid(70, [hexc("0c2410"), hexc("1c5a1c"), hexc("3c9a2c"), hexc("8cd84c"), hexc("e0ffa0")], frame)
    # a gooey edge on the top, dripping
    for x in range(T):
        plot(t, [(x, 0)], hexc("e0ffa0") if (x + frame) % 5 else hexc("3c9a2c"))
    return t


def draw_acid(frame):
    return liquid(72, [hexc("202808"), hexc("5a6c08"), hexc("a8c010"), hexc("e0f040"), hexc("fffcc0")], frame)


def draw_lava(frame):
    return liquid(74, [hexc("400800"), hexc("b02008"), hexc("f07010"), hexc("ffc840"), hexc("fffce8")], frame)


def draw_water(frame):
    return liquid(76, [hexc("081828"), hexc("104878"), hexc("3090e0"), hexc("a0f0ff"), hexc("e4fff0")], frame,
                  frames=4)


def draw_box():
    """Sokoban's box: planks with a brace"""
    wood = [hexc("2a170c"), hexc("6b4322"), hexc("8a5a30"), hexc("b08050"), hexc("e09070")]
    t = new_tile()
    for y in range(1, 15):
        for x in range(1, 15):
            v = 0.5 + 0.12 * math.sin(y * 1.7 + x * 0.2) + (0.15 if y % 4 == 1 else 0)
            if x in (1, 14) or y in (1, 14):
                v = 0.2
            elif abs(x - y) <= 1 or abs(x - (15 - y)) <= 1:
                v = 0.75
            t[y][x] = steps(wood, v, 5)
    for x, y in ((2, 2), (13, 2), (2, 13), (13, 13)):
        t[y][x] = hexc("c8d4e8")
    return t


def draw_key(col):
    """A key in its colour: bit, shaft, ring"""
    stops = [mix(col, hexc("000000"), 0.7), mix(col, hexc("000000"), 0.35), col, mix(col, hexc("ffffff"), 0.6)]
    t = new_tile()
    for y in range(T):
        for x in range(T):
            d = math.hypot(x + 0.5 - 5, y + 0.5 - 8)
            if 1.6 < d < 4.2:
                t[y][x] = steps(stops, 0.9 - (d - 1.6) / 3 + (0.2 if y < 8 else -0.1), 4)
    for x in range(8, 15):
        t[7][x] = stops[3]
        t[8][x] = stops[2]
        t[9][x] = stops[1]
    for x, h in ((11, 3), (13, 2)):
        for y in range(10, 10 + h):
            t[y][x] = stops[1]
            t[y][x + 1] = stops[0]
    return t


def draw_lock_door(col):
    """A locked door in its colour, in a steel frame"""
    t = draw_steel()
    stops = [mix(col, hexc("000000"), 0.7), mix(col, hexc("000000"), 0.4), col, mix(col, hexc("ffffff"), 0.5)]
    for y in range(2, 14):
        for x in range(3, 13):
            edge = x in (3, 12) or y in (2, 13)
            t[y][x] = stops[0] if edge else steps(stops, 0.45 + 0.4 * (1 - (x + y) / 26), 4)
    for (x, y) in ((7, 6), (8, 6), (7, 7), (8, 7), (7, 8), (7, 9), (8, 9), (7, 10)):
        t[y][x] = hexc("101010")
    return t


KEY_COLOURS = [hexc("ffd040"), hexc("40a0ff"), hexc("ff3060")]  # GDash's keys and doors 1-3


def draw_trapped_diamond():
    """An emerald behind bars, until the key comes"""
    t = draw_emerald(2)
    for x in (3, 7, 11):
        for y in range(T):
            t[y][x] = hexc("c8d4e8")
            t[y][x + 1] = hexc("5c6880")
    for x in range(T):
        t[0][x] = t[15][x] = hexc("7c88a0")
    return t


def draw_clock():
    t = new_tile()
    face = [hexc("301808"), hexc("a07020"), hexc("ffd860"), hexc("fff8c0")]
    for y in range(T):
        for x in range(T):
            d = math.hypot(x + 0.5 - 8, y + 0.5 - 8)
            if d < 7.3:
                t[y][x] = face[0] if d > 6.2 else (face[1] if d > 5.4 else face[3])
    for i in range(12):
        a = i * math.pi / 6
        plot(t, [(int(round(7.5 + 4.6 * math.cos(a))), int(round(7.5 + 4.6 * math.sin(a))))], face[1])
    plot(t, [(8, y) for y in range(4, 9)], hexc("301808"))
    plot(t, [(x, 8) for x in range(8, 12)], hexc("301808"))
    return t


def draw_bomb(lit, frame=0):
    t = sphere(new_tile(), 7.5, 9.0, 6.2, [hexc("08080c"), hexc("1c2030"), hexc("3c4456"), hexc("7c88a0"),
                                           hexc("c8d4e8")], 5)
    plot(t, [(9, 3), (10, 2), (11, 2)], hexc("8a5a30"))
    if lit:
        spark = [(12, 1), (12, 2), (11, 1), (13, 1)] if frame else [(12, 1), (13, 0), (11, 0), (13, 2)]
        plot(t, spark[1:], hexc("ffc840"))
        plot(t, spark[:1], hexc("fffce8"))
    return t


def draw_sweet():
    """A wrapped sweet"""
    t = new_tile()
    stops = [hexc("400828"), hexc("a01c60"), hexc("f070e0"), hexc("ffd0f0")]
    sphere(t, 8, 8, 4.4, stops, 4)
    for y in range(4, 12):
        w = abs(y - 7.5) / 1.5
        for x in range(0, 4):
            if x >= w - 1:
                t[y][x] = stops[2] if (x + y) % 2 else stops[1]
                t[y][15 - x] = stops[2] if (x + y) % 2 else stops[1]
    plot(t, [(x, 7) for x in range(5, 11, 2)], stops[3])
    return t


def draw_bladder(frame):
    """A bubble that rises"""
    t = new_tile()
    r = 6.0 + 0.5 * frame
    for y in range(T):
        for x in range(T):
            d = math.hypot(x + 0.5 - 8, (y + 0.5 - 8) * (1.08 - 0.08 * frame))
            if d < r:
                t[y][x] = hexc("a0f0ff") if d > r - 1 else (hexc("104878") if d > r - 2.2 else None)
    plot(t, [(5, 4), (4, 5), (5, 5)], hexc("ffffff"))
    return t


def draw_bladder_spender():
    t = draw_steel()
    for y in range(T):
        for x in range(T):
            d = math.hypot(x + 0.5 - 8, y + 0.5 - 6)
            if d < 3.5:
                t[y][x] = hexc("08080c") if d < 2.5 else hexc("a0f0ff")
    return t


def draw_switch(col, on=False):
    """A lever on a steel plate, the plate in the switch's colour; switched
    on, the lever leans the other way"""
    t = draw_steel()
    for y in range(9, 14):
        for x in range(3, 13):
            t[y][x] = col if y > 9 else mix(col, hexc("ffffff"), 0.5)
    lever = new_tile()
    for i in range(6):
        plot(lever, [(5 + i, 9 - i)], hexc("e8f0ff"))
        plot(lever, [(6 + i, 9 - i)], hexc("5c6880"))
    plot(lever, [(11, 3), (12, 3), (11, 2), (12, 2)], hexc("ff3060"))
    for y in range(T):
        for x in range(T):
            c = lever[y][T - 1 - x if on else x]
            if c is not None:
                t[y][x] = c
    return t


SWITCH_COLOURS = {"CREATURE_SWITCH": hexc("f06414"), "EXPANDING_WALL_SWITCH": hexc("a45434"),
                  "BITER_SWITCH": hexc("8c30a0"), "REPLICATOR_SWITCH": hexc("3cc870"),
                  "CONVEYOR_SWITCH": hexc("ffd040"), "CONVEYOR_DIR_SWITCH": hexc("30b0f0"),
                  "GRAVITY_SWITCH": hexc("2850c8")}
# the switches that show whether they are on (GDash's caverendered.cpp)
SWITCHES_ON = ("CREATURE_SWITCH", "EXPANDING_WALL_SWITCH", "REPLICATOR_SWITCH", "CONVEYOR_SWITCH",
               "CONVEYOR_DIR_SWITCH", "GRAVITY_SWITCH")


def draw_biter(frame):
    """A round thing that eats its way through: open and shut"""
    t = sphere(new_tile(), 8, 8, 6.6, [hexc("200828"), hexc("501860"), hexc("8c30a0"), hexc("c868d8"),
                                       hexc("f4c0ff")], 5)
    gape = 1 + 2 * frame
    for y in range(8 - gape, 8 + gape):
        for x in range(8, 16):
            if t[y][x] is not None and abs(y + 0.5 - 8) < gape * (x - 7) / 8:
                t[y][x] = None
    for x in range(9, 14, 2):
        plot(t, [(x, 8 - gape), (x, 7 + gape)], hexc("ffffff"))
    plot(t, [(6, 4), (7, 4)], hexc("101010"))
    return t


def draw_amoeba_2(frame):
    return by_lum(draw_amoeba(frame), [hexc("0c2410"), hexc("1c5a1c"), hexc("3c9a2c"), hexc("8cd84c"),
                                       hexc("e0ffa0")], 5)


def draw_falling_wall():
    t = draw_brick()
    plot(t, [(5, 1), (6, 2), (6, 3), (7, 4), (9, 8), (9, 9), (10, 10), (4, 11), (5, 12)], hexc("200808"))
    return t


def draw_alt_firefly(frame):
    return by_lum(draw_firefly(frame), [hexc("101850"), hexc("2850c8"), hexc("30b0f0"), hexc("a0f0ff"),
                                        hexc("ffffff")], 5)


def draw_alt_butterfly(frame):
    return by_lum(draw_butterfly(frame), [hexc("400804"), hexc("a01c08"), hexc("f06414"), hexc("ffb030"),
                                          hexc("fff4c0")], 5)


def draw_stonefly(frame):
    return by_lum(draw_butterfly(frame), [hexc("1e1a18"), hexc("4a423c"), hexc("78685a"), hexc("a8968a"),
                                          hexc("d8cabc")], 5)


def draw_dragonfly(frame):
    """Long body, two pairs of wings beating"""
    t = new_tile()
    body = [hexc("0c5a30"), hexc("16904a"), hexc("3cc870")]
    for y in range(2, 15):
        t[y][7] = body[1]
        t[y][8] = body[2] if y < 6 else body[0]
    plot(t, [(7, 2), (8, 2), (6, 3), (9, 3)], hexc("8cf0b0"))
    span = [7, 4][frame]
    for i in range(1, span):
        for dy in (0, 1):
            for side in (-1, 1):
                plot(t, [(int(7.5 + side * (i + 0.5)), 5 + dy + (i // 3)), (int(7.5 + side * (i + 0.5)), 8 + dy + (i // 3))],
                     hexc("a0f0ff") if dy == 0 else hexc("30b0f0"))
    return t


def draw_mega_boulder():
    t = draw_boulder()
    t = by_lum(t, [hexc("08080c"), hexc("1c2030"), hexc("3c4456"), hexc("7c88a0"), hexc("a8b4c8")], 6)
    plot(t, [(5, 6), (6, 7), (7, 7), (10, 4), (11, 5)], hexc("08080c"))
    return t


def draw_nut():
    t = sphere(new_tile(), 8, 8.5, 6.0, [hexc("2a170c"), hexc("4a2c16"), hexc("6b4322"), hexc("8a5a30"),
                                         hexc("b08050")], 5, squash=0.95)
    for y in range(3, 14):
        if t[y][8] is not None:
            t[y][8] = hexc("2a170c")
    plot(t, [(8, 1), (8, 2)], hexc("1c5a1c"))
    return t


def draw_teleporter(frame):
    t = new_tile()
    stops = [hexc("200828"), hexc("501860"), hexc("8c30a0"), hexc("c868d8"), hexc("f4c0ff")]
    for y in range(T):
        for x in range(T):
            dx, dy = x + 0.5 - 8, y + 0.5 - 8
            d = math.hypot(dx, dy)
            if d > 7.4:
                continue
            a = math.atan2(dy, dx) + d * 0.6 + frame * math.pi / 4  # four frames: a quarter turn of the pattern
            t[y][x] = steps(stops, 0.5 + 0.45 * math.sin(a * 2) * (1 - d / 9), 5)
    return t


def glued(t):
    """With drops of glue: it cannot be moved"""
    t = [list(row) for row in t]
    for x, y in ((3, 2), (3, 3), (11, 1), (11, 2), (11, 3), (6, 12), (12, 11), (12, 12)):
        t[y][x] = hexc("fff8c0")
    for x, y in ((3, 4), (11, 4), (6, 13), (12, 13)):
        t[y][x] = hexc("ffd860")
    return t


def eyes(t, shut):
    t = [list(row) for row in t]
    for ex in (5, 9):
        if shut:
            plot(t, [(ex, 7), (ex + 1, 7)], hexc("101010"))
        else:
            plot(t, [(ex, 6), (ex + 1, 6), (ex, 7), (ex + 1, 7)], hexc("ffffff"))
            plot(t, [(ex + 1, 7)], hexc("101010"))
    return t


def draw_replicator(frame):
    t = draw_steel()
    for y in range(4, 12):
        for x in range(4, 12):
            t[y][x] = hexc("1c2030") if x in (4, 11) or y in (4, 11) else \
                (hexc("3cc870") if (x + y + frame * 2) % 4 < 2 else hexc("16904a"))
    return t


def draw_steel_explodable():
    t = draw_steel()
    plot(t, [(4, 2), (5, 3), (5, 4), (6, 5), (9, 8), (10, 9), (10, 10), (11, 11), (7, 12), (8, 13)], hexc("1c2030"))
    return t


def draw_eatable(base):
    """A wall that Rockford can dig through: dirt shows through it"""
    t = [list(row) for row in base]
    d = draw_dirt()
    for y in range(T):
        for x in range(T):
            if (x * 3 + y * 5) % 7 < 2:
                t[y][x] = d[y][x]
    return t


def draw_pot():
    t = new_tile()
    stops = [hexc("08080c"), hexc("1c2030"), hexc("3c4456"), hexc("7c88a0")]
    sphere(t, 8, 9.5, 6.0, stops, 4, squash=0.9)
    for y in range(T):
        for x in range(T):
            if y < 6:
                t[y][x] = None
    for x in range(2, 14):
        t[5][x] = stops[3]
        t[6][x] = stops[2]
    plot(t, [(5, 3), (7, 2), (10, 3)], hexc("c8d4e8"))  # steam
    return t


def draw_skeleton():
    t = new_tile()
    bone = [hexc("4e463e"), hexc("a09484"), hexc("e8e0d0")]
    for y in range(T):
        for x in range(T):
            if math.hypot(x + 0.5 - 8, (y + 0.5 - 6) * 1.1) < 5.2:
                t[y][x] = bone[2] if (x + y) % 5 else bone[1]
    for x, y in ((6, 5), (6, 6), (5, 6), (10, 5), (10, 6), (11, 6), (8, 8)):
        t[y][x] = hexc("101010")
    for y in range(10, 14):
        for x in range(5, 12):
            t[y][x] = bone[1] if x % 2 else bone[2]
    return t


def draw_gravestone():
    t = new_tile()
    stone = [hexc("1c2030"), hexc("3c4456"), hexc("7c88a0"), hexc("a8b4c8")]
    for y in range(2, 15):
        for x in range(3, 13):
            if y < 6 and math.hypot(x + 0.5 - 8, y - 6) > 5:
                continue
            t[y][x] = steps(stone, 0.7 - 0.4 * (x - 3) / 10 - (0.2 if y == 14 else 0), 4)
    for y in range(5, 11):
        t[y][8] = stone[0]
    for x in range(6, 11):
        t[7][x] = stone[0]
    return t


def winged(t):
    """Flies up: small wings at the sides"""
    t = [list(row) for row in t]
    for i, x in enumerate((0, 1, 2)):
        plot(t, [(x, 4 + i), (15 - x, 4 + i)], hexc("fff8c0"))
        plot(t, [(x, 5 + i), (15 - x, 5 + i)], hexc("a0f0ff"))
    return t


def draw_nitro():
    t = new_tile()
    red = [hexc("400804"), hexc("a01c08"), hexc("f06414")]
    for y in range(2, 15):
        for x in range(3, 13):
            t[y][x] = red[0] if x in (3, 12) else red[1] if (x + y) % 6 else red[2]
    for x in range(3, 13):
        t[5][x] = t[11][x] = hexc("ffd040")
    plot(t, [(8, 0), (8, 1), (9, 0)], hexc("fff8c0"))
    return t


def draw_ghost(frame):
    t = new_tile()
    for y in range(T):
        for x in range(T):
            if y < 9 and math.hypot(x + 0.5 - 8, y + 0.5 - 8) < 6.5 or 8 <= y < 14 and 1.5 < x < 14.5:
                if y >= 13 and (x + frame * 2) % 4 < 2:
                    continue
                t[y][x] = hexc("e4fff0") if x < 9 else hexc("a8b4c8")
    for ex in (5, 9):
        plot(t, [(ex, 6), (ex + 1, 6), (ex, 7), (ex + 1, 7)], hexc("1c2030"))
    return t


def draw_hammer(active=False, frame=0):
    """The pneumatic hammer; at work in four frames: up, halfway, the
    strike (with sparks), halfway"""
    t = new_tile()
    head = [hexc("3c4456"), hexc("7c88a0"), hexc("c8d4e8")]
    top = 2 + ([0, 2, 4, 2][frame] if active else 0)
    for y in range(top, top + 4):
        for x in range(3, 13):
            t[y][x] = head[2] if y == top else head[1] if y < top + 3 else head[0]
    for y in range(top + 4, 15):
        t[y][7] = hexc("8a5a30")
        t[y][8] = hexc("4a2c16")
    if active and frame == 2:
        plot(t, [(2, 15), (13, 15), (4, 14), (11, 14)], hexc("ffc840"))
    return t


def draw_rocket_launcher():
    t = new_tile()
    for y in range(6, 10):
        for x in range(2, 14):
            t[y][x] = hexc("1c5a1c") if y in (6, 9) else hexc("3c9a2c")
    for y in range(10, 14):
        t[y][5] = hexc("4a2c16")
    plot(t, [(13, 7), (13, 8)], hexc("08080c"))
    return t


def draw_rocket(direction):
    """A rocket flying right (0), up, left, down"""
    t = new_tile()
    for x in range(3, 12):
        for y in (7, 8):
            t[y][x] = hexc("c8d4e8") if y == 7 else hexc("7c88a0")
    plot(t, [(12, 7), (12, 8), (13, 7)], hexc("ff3060"))
    plot(t, [(3, 5), (4, 6), (3, 10), (4, 9)], hexc("7c88a0"))
    plot(t, [(1, 7), (2, 8), (0, 8), (2, 7)], hexc("ffc840"))
    for _ in range(direction):  # turn a quarter left
        t = [[t[x][T - 1 - y] for x in range(T)] for y in range(T)]
    return t


def walled(item):
    """Something walled in: a brick wall with it inside"""
    t = draw_brick()
    small = item
    for y in range(4, 12):
        for x in range(4, 12):
            c = small[(y - 4) * 2][(x - 4) * 2]
            t[y][x] = c if c is not None else hexc("2a2224")
    return t


def sloped(base, corner):
    """A wall sloped so that what falls rolls off: the triangle without the
    corner up-right ('ur'), up-left, down-left, down-right"""
    t = [list(row) for row in base]
    for y in range(T):
        for x in range(T):
            cut = {"ur": x > y, "ul": x + y < T - 1, "dl": x < y, "dr": x + y > T - 1}[corner]
            if cut:
                t[y][x] = None
    return t


def draw_conveyor(left, frame):
    t = new_tile()
    for y in range(4, 12):
        for x in range(T):
            t[y][x] = hexc("1c2030") if y in (4, 11) else hexc("3c4456")
    for x in range(T):
        if (x + (frame if left else -frame) * 2) % 4 == 0:
            for y in range(5, 11):
                t[y][x] = hexc("a8b4c8")
    for x in (2, 13):
        for y in range(6, 10):
            t[y][x] = hexc("ffd040")
    return t


COW = {"W": "f0ece4", "w": "c4bcb0", "K": "1e1a18", "k": "3e3834", "P": "f0a8a8", "p": "c07478",
       "H": "e0d4a8", "E": "101010", "L": "8a8276", "F": "2a2420", "t": "8a8276"}


def draw_cow(frame):
    """A black and white cow, seen from the side, walking"""
    legs = [["..WW.W....W.W...", "..LL.L....L.L...", "..LL.L....L.L...", "..FF.F....F.F..."],
            ["..WW..W..W..W...", "..LL..L..L..L...", "..L...L..L...L..", ".FF...F..F...F.."]][frame]
    pic = ["...........H..H.",
           "..........KWWWWK",
           "...........WEWK.",
           "..........WWWKKP",
           "..kKKWWWWKKWWPpP",
           ".tKKKKWWWKKKWPPp",
           ".tWKKWWWWWKKW...",
           ".tWWWWWWKKWWW...",
           ".KWWWWWKKKWWW...",
           "..wwwwwwwwwww...",
           "..ww.wPPw.ww....",
           ] + legs
    return from_pic(pic, {k: hexc(v) for k, v in COW.items()})


def draw_dirt2():
    return by_lum(draw_dirt(), [hexc("1c1414"), hexc("3c3030"), hexc("5c5050"), hexc("7a6e62"),
                                hexc("a09484")], 5)


def draw_voodoo():
    """A doll of Rockford"""
    rf = draw_rockford_set()["RF_VIEW4"]
    return by_lum(rf, [hexc("200828"), hexc("501860"), hexc("8c30a0"), hexc("c868d8"), hexc("f4c0ff")], 5)


def draw_unknown():
    t = draw_steel()
    q = ["  ####  ", " ##  ## ", "     ## ", "    ##  ", "   ##   ", "   ##   ", "        ", "   ##   "]
    return from_pic(q, {"#": hexc("ff3060")}, t)


def gd_tiles():
    """The tiles of GDash's elements: (name, picture)"""
    out = [("DIRT2", draw_dirt2()), ("STEEL_EXPL", draw_steel_explodable()),
           ("STEEL_EAT", draw_eatable(draw_steel())), ("BRICK_EAT", draw_eatable(draw_brick())),
           ("FALLING_WALL", draw_falling_wall())]
    for name, base in (("BRICK", draw_brick()), ("STEEL", draw_steel()), ("DIRT", draw_dirt())):
        for corner in ("ur", "ul", "dl", "dr"):
            out.append((f"{name}_SLOPE_{corner.upper()}", sloped(base, corner)))
    out += [(f"SLIME{i}", draw_slime(i)) for i in range(2)]
    out += [(f"ACID{i}", draw_acid(i)) for i in range(2)]
    out += [(f"LAVA{i}", draw_lava(i)) for i in range(2)]
    out += [(f"WATER{i}", draw_water(i)) for i in range(4)]
    out += [("BOX", draw_box()), ("DIAMOND_KEY", draw_key(hexc("3cc870"))),
            ("TRAPPED_DIAMOND", draw_trapped_diamond()), ("CLOCK", draw_clock()), ("BOMB", draw_bomb(False))]
    out += [(f"BOMB_LIT{i}", draw_bomb(True, i)) for i in range(2)]
    out += [(f"KEY{i + 1}", draw_key(c)) for i, c in enumerate(KEY_COLOURS)]
    out += [(f"DOOR{i + 1}", draw_lock_door(c)) for i, c in enumerate(KEY_COLOURS)]
    out += [("SWEET", draw_sweet())]
    out += [(f"BLADDER{i}", draw_bladder(i)) for i in range(2)]
    out += [("BLADDER_SPENDER", draw_bladder_spender())]
    out += [(name, draw_switch(c)) for name, c in SWITCH_COLOURS.items()]
    out += [(name + "_ON", draw_switch(c, True)) for name, c in SWITCH_COLOURS.items() if name in SWITCHES_ON]
    out += [(f"BITER{i}", draw_biter(i)) for i in range(2)]
    out += [(f"AMOEBA2_{i}", draw_amoeba_2(i)) for i in range(4)]
    out += [(f"ALT_FIREFLY{i}", draw_alt_firefly(i)) for i in range(4)]
    out += [(f"ALT_BUTTERFLY{i}", draw_alt_butterfly(i)) for i in range(4)]
    out += [(f"STONEFLY{i}", draw_stonefly(i)) for i in range(4)]
    out += [(f"DRAGONFLY{i}", draw_dragonfly(i)) for i in range(2)]
    out += [("MEGA_BOULDER", draw_mega_boulder()), ("NUT", draw_nut())]
    out += [(f"TELEPORTER{i}", draw_teleporter(i)) for i in range(4)]
    out += [("BOULDER_GLUED", glued(draw_boulder())), ("DIAMOND_GLUED", glued(draw_emerald(0))),
            ("DIRT_GLUED", glued(draw_dirt())), ("RF_GLUED", glued(draw_rockford_set()["RF_VIEW4"])),
            ("BOULDER_WAITING", eyes(draw_boulder(), True)), ("BOULDER_CHASING", eyes(draw_boulder(), False))]
    out += [(f"REPLICATOR{i}", draw_replicator(i)) for i in range(2)]
    out += [("POT", draw_pot()), ("SKELETON", draw_skeleton()), ("GRAVESTONE", draw_gravestone()),
            ("BOULDER_FLYING", winged(draw_boulder())), ("DIAMOND_FLYING", winged(draw_emerald(0))),
            ("NITRO", draw_nitro())]
    out += [(f"GHOST{i}", draw_ghost(i)) for i in range(2)]
    out += [("HAMMER", draw_hammer())] + [(f"HAMMER_ACTIVE{i}", draw_hammer(True, i)) for i in range(4)]
    out += [("ROCKET_LAUNCHER", draw_rocket_launcher())]
    out += [(f"ROCKET{i}", draw_rocket(i)) for i in range(4)]
    out += [("WALLED_DIAMOND", walled(draw_emerald(0)))]
    out += [(f"WALLED_KEY{i + 1}", walled(draw_key(c))) for i, c in enumerate(KEY_COLOURS)]
    out += [(f"CONVEYOR_L{i}", draw_conveyor(True, i)) for i in range(2)]
    out += [(f"CONVEYOR_R{i}", draw_conveyor(False, i)) for i in range(2)]
    out += [(f"COW{i}", draw_cow(i)) for i in range(2)]
    out += [("VOODOO", draw_voodoo()), ("UNKNOWN", draw_unknown())]
    return out


# The tile of each of GDash's elements: GDash's name (O_...) as a pattern,
# the tile, and for one that moves on its own the number of its frames (2
# or 4) and how many screen frames each shows (a power of two, as its
# exponent). The first match counts. Some get their first tile and main.c
# animates them as the game's own (fireflies, butterflies, amoeba, magic
# wall, inbox, exit, the player as RF_VIEW4); SPARKLE is an emerald
# sparkling on its own.
GD_TILES = [
    (r"SPACE", "SPACE"),
    (r"DIRT2", "DIRT2"),
    (r"DIRT_GLUED", "DIRT_GLUED"),
    (r"(BRICK|STEEL|DIRT)_SLOPED_(UP|DOWN)_(LEFT|RIGHT)", "SLOPE"),
    (r"DIRT.*", "DIRT"),
    (r"BRICK_EATABLE", "BRICK_EAT"),
    (r"BRICK.*|(H_|V_)?EXPANDING_WALL", "BRICK"),
    (r"FALLING_WALL(_F)?", "FALLING_WALL"),
    (r"STEEL_EXPLODABLE", "STEEL_EXPL"),
    (r"STEEL_EATABLE", "STEEL_EAT"),
    (r"STEEL|(H_|V_)?EXPANDING_STEEL_WALL|PRE_OUTBOX|PRE_INVIS_OUTBOX|INVIS_OUTBOX|PRE_STEEL_\d", "STEEL"),
    (r"STONE(_F)?", "BOULDER"),
    (r"MEGA_STONE(_F)?", "MEGA_BOULDER"),
    (r"FLYING_STONE(_F)?", "BOULDER_FLYING"),
    (r"WAITING_STONE", "BOULDER_WAITING"),
    (r"CHASING_STONE", "BOULDER_CHASING"),
    (r"STONE_GLUED", "BOULDER_GLUED"),
    (r"DIAMOND(_F)?", "SPARKLE"),
    (r"FLYING_DIAMOND(_F)?", "DIAMOND_FLYING"),
    (r"DIAMOND_GLUED", "DIAMOND_GLUED"),
    (r"DIAMOND_KEY", "DIAMOND_KEY"),
    (r"TRAPPED_DIAMOND", "TRAPPED_DIAMOND"),
    (r"WALLED_DIAMOND", "WALLED_DIAMOND"),
    (r"NUT(_F)?", "NUT"),
    (r"INBOX", "INBOX0"),
    (r"OUTBOX", "OUTBOX0"),
    (r"MAGIC_WALL", "MAGIC0"),
    (r"(CREATURE|EXPANDING_WALL|BITER|REPLICATOR|CONVEYOR|CONVEYOR_DIR|GRAVITY)_SWITCH", "SWITCH"),
    (r"ACID", "ACID0", 2, 3),
    (r"BOX", "BOX"),
    (r"TIME_PENALTY|GRAVESTONE", "GRAVESTONE"),
    (r"CLOCK", "CLOCK"),
    (r"KEY_(\d)", "KEY"),
    (r"DOOR_(\d)", "DOOR"),
    (r"WALLED_KEY_(\d)", "WALLED_KEY"),
    (r"POT", "POT"),
    (r"PNEUMATIC_HAMMER", "HAMMER"),
    (r"PNEUMATIC_ACTIVE_(LEFT|RIGHT)", "HAMMER_ACTIVE0", 4, 2),
    (r"TELEPORTER", "TELEPORTER0", 4, 3),
    (r"SKELETON", "SKELETON"),
    (r"WATER(_\d+)?", "WATER0", 4, 3),
    (r"COW_\d|COW_ENCLOSED_\d", "COW0", 2, 3),
    (r"AMOEBA", "AMOEBA0"),
    (r"AMOEBA_2", "AMOEBA2_0", 4, 3),
    (r"REPLICATOR", "REPLICATOR0", 2, 3),
    (r"CONVEYOR_LEFT", "CONVEYOR_L0", 2, 2),
    (r"CONVEYOR_RIGHT", "CONVEYOR_R0", 2, 2),
    (r"LAVA", "LAVA0", 2, 3),
    (r"SWEET", "SWEET"),
    (r"VOODOO", "VOODOO"),
    (r"SLIME", "SLIME0", 2, 3),
    (r"BLADDER_SPENDER", "BLADDER_SPENDER"),
    (r"BLADDER(_\d)?", "BLADDER0", 2, 3),
    (r"GHOST", "GHOST0", 2, 2),
    (r"FIREFLY_\d", "FIREFLY0"),
    (r"ALT_FIREFLY_\d", "ALT_FIREFLY0", 4, 1),
    (r"BUTTER_\d", "BUTTERFLY0"),
    (r"ALT_BUTTER_\d", "ALT_BUTTERFLY0", 4, 2),
    (r"STONEFLY_\d", "STONEFLY0", 4, 2),
    (r"BITER_\d", "BITER0", 2, 2),
    (r"DRAGONFLY_\d", "DRAGONFLY0", 2, 1),
    (r"PLAYER_GLUED", "RF_GLUED"),
    (r"PLAYER.*", "RF_VIEW4"),
    (r"ROCKET_LAUNCHER", "ROCKET_LAUNCHER"),
    (r"ROCKET_(\d)", "ROCKET"),
    (r"BOMB", "BOMB"),
    (r"BOMB_TICK_\d", "BOMB_LIT0", 2, 1),
    (r"NITRO_PACK(_F|_EXPLODE)?", "NITRO"),
] + [(f"PRE_PL_{i + 1}", f"BIRTH{i}") for i in range(3)] + [
    (f"(EXPLODE|PRE_DIA|PRE_STONE|PRE_CLOCK|GHOST_EXPL|BOMB_EXPL|NITRO_EXPL|AMOEBA_2_EXPL|NUT_CRACK)_{i + 1}",
     f"EXPLODE{i}") for i in range(5)] + [
    (r".*", "UNKNOWN"),
]

SLOPE_CORNER = {"UP_RIGHT": "UR", "UP_LEFT": "UL", "DOWN_LEFT": "DL", "DOWN_RIGHT": "DR"}
SWITCH_TILE = {"CREATURE": "CREATURE_SWITCH", "EXPANDING_WALL": "EXPANDING_WALL_SWITCH",
               "BITER": "BITER_SWITCH", "REPLICATOR": "REPLICATOR_SWITCH", "CONVEYOR": "CONVEYOR_SWITCH",
               "CONVEYOR_DIR": "CONVEYOR_DIR_SWITCH", "GRAVITY": "GRAVITY_SWITCH"}


def gd_tile_table(tile_index):
    """gd_tile[], gd_anim[]: the tile of each of GDash's elements, and how
    it moves on its own (frames: low two bits as 0, 1 or 2 for 1, 2 or 4;
    above them the exponent of the screen frames per frame)"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cavekit import GD_EL
    tiles, anims = [], []
    for e in GD_EL:
        for pat, tile, *anim in GD_TILES:
            m = re.fullmatch(pat, e.name)
            if m:
                break
        if tile == "SLOPE":
            tile = f"{m.group(1)}_SLOPE_{SLOPE_CORNER[m.group(2) + '_' + m.group(3)]}"
        elif tile == "SWITCH":
            tile = SWITCH_TILE[m.group(1)]
        elif tile in ("KEY", "DOOR", "WALLED_KEY"):
            tile += m.group(1)
        elif tile == "ROCKET":
            tile = f"ROCKET{int(m.group(1)) - 1}"
        tiles.append(255 if tile == "SPARKLE" else tile_index[tile])
        frames, shift = (anim + [1, 0])[:2]
        anims.append({1: 0, 2: 1, 4: 2}[frames] | shift << 2)
    return tiles, anims


# ---------------------------------------------------------------- assembly

def build_tiles():
    tiles = [("SPACE", draw_space()), ("DIRT", draw_dirt()), ("BRICK", draw_brick()),
             ("STEEL", draw_steel()), ("BOULDER", draw_boulder())]
    tiles += [(f"DIAMOND{i}", draw_emerald(i)) for i in range(8)]
    tiles += list(draw_rockford_set().items())
    tiles += [(f"FIREFLY{i}", draw_firefly(i)) for i in range(4)]
    tiles += [(f"BUTTERFLY{i}", draw_butterfly(i)) for i in range(4)]
    tiles += [(f"EXPLODE{i}", draw_explosion(i)) for i in range(5)]
    tiles += [(f"BIRTH{i}", draw_birth(i)) for i in range(3)]
    tiles += [("INBOX0", draw_door(False, True)), ("INBOX1", draw_door(True, True)),
              ("OUTBOX0", draw_door(False, False)), ("OUTBOX1", draw_door(True, False))]
    tiles += [(f"AMOEBA{i}", draw_amoeba(i)) for i in range(4)]
    tiles += [(f"MAGIC{i}", draw_magic(i)) for i in range(4)]
    tiles += [(f"COVER{i}", draw_cover(i)) for i in range(8)]
    tiles += [(f"EMBERS{i}", draw_embers(i)) for i in range(4)]
    tiles += [(f"GLITTER{i}", draw_glitter(i)) for i in range(4)]
    tiles += [(f"EMBERS_ALT{i}", draw_embers(i, EMBERS_BLUE)) for i in range(4)]
    tiles += [(f"GLITTER_ALT{i}", draw_glitter(i, GLITTER_ORANGE)) for i in range(4)]
    tiles += [(f"GLITTER_STONE{i}", draw_glitter(i, GLITTER_STONE)) for i in range(4)]
    tiles += [(f"GLITTER_DRAGON{i}", draw_glitter(i, GLITTER_GREEN)) for i in range(4)]
    tiles += [(f"MIST{i}", draw_mist(i)) for i in range(4)]
    tiles += [(f"CRUMBS_BITER{i}", draw_crumbs(i, CRUMBS_BITER)) for i in range(3)]
    tiles += [(f"CRUMBS_GRIT{i}", draw_crumbs(i, CRUMBS_GRIT)) for i in range(3)]
    tiles += [(f"DROPS{i}", draw_drops(i)) for i in range(3)]
    tiles += [(f"GLINT{i}", draw_glitter(i, GLITTER_EMERALD)) for i in range(4)]
    tiles += [(f"SMOKE{i}", draw_smoke(i)) for i in range(3)]
    tiles += [(f"CRUMBS{i}", draw_crumbs(i)) for i in range(3)]
    tiles += [(f"DUSTL{i}", draw_dust(i, False)) for i in range(2)]
    tiles += [(f"DUSTR{i}", draw_dust(i, True)) for i in range(2)]
    tiles += [("CURSOR", draw_cursor())]
    tiles += gd_tiles()
    return tiles


class Palette:
    def __init__(self):
        self.index = {}
        self.colours = [(0, 0, 0)]  # 0: screen colour

    def unique(self, c):
        """An entry of its own, even if the colour exists already."""
        self.colours.append(c)
        if len(self.colours) > 255:
            raise SystemExit("mkgfx: more than 254 colours")
        return len(self.colours) - 1

    def __call__(self, c):
        if c is None:
            return 0
        if c not in self.index:
            if len(self.colours) >= 255:   # 255 would take the colour RAM colour
                raise SystemExit("mkgfx: more than 254 colours")
            self.index[c] = len(self.colours)
            self.colours.append(c)
        return self.index[c]


def quantise(images, maxcol=254):
    """Reduce all colours together if there are too many."""
    cols = {c for img in images for row in img for c in row if c is not None}
    if len(cols) <= maxcol:
        return images
    w = sum(len(img[0]) for img in images)
    h = max(len(img) for img in images)
    atlas = Image.new("RGB", (w, h), (0, 0, 0))
    ox = 0
    for img in images:
        for y, row in enumerate(img):
            for x, c in enumerate(row):
                if c is not None:
                    atlas.putpixel((ox + x, y), c)
        ox += len(img[0])
    q = atlas.quantize(colors=maxcol, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    out, ox = [], 0
    for img in images:
        out.append([[None if c is None else q.getpixel((ox + x, y)) for x, c in enumerate(row)]
                    for y, row in enumerate(img)])
        ox += len(img[0])
    return out


def gd_colours(gd, have, maxcol):
    """GDash's tiles (gd) in the colours of the game's own (have) and as
    many new ones as there is room for up to maxcol, the most used first;
    the others become the nearest colour there is"""
    have = set(have)
    count = {}
    for _, t in gd:
        for row in t:
            for c in row:
                if c is not None and c not in have:
                    count[c] = count.get(c, 0) + 1
    room = maxcol - len(have)
    have |= set(sorted(count, key=lambda c: -count[c])[:room])
    pal = list(have)
    near = {}

    def nearest(c):
        if c not in near:
            near[c] = c if c in have else min(pal, key=lambda p: sum((p[i] - c[i]) ** 2 for i in range(3)))
        return near[c]
    return [(n, [[None if c is None else nearest(c) for c in row] for row in t]) for n, t in gd]


def make_logo(ui_entries):
    """Scale the logo down and give it the palette entries the status font
    does not use. Returns the strip data and palette 1."""
    src = Image.open(LOGO_SRC).convert("RGBA")
    black = Image.new("RGBA", src.size, (0, 0, 0, 255))
    black.alpha_composite(src)
    rgb = black.convert("RGB").resize((LOGO_W, LOGO_H), Image.LANCZOS)
    alpha = src.getchannel("A").resize((LOGO_W, LOGO_H), Image.LANCZOS)
    free = [i for i in range(1, 255) if i not in ui_entries]
    q = rgb.quantize(colors=len(free), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qpal = q.getpalette()
    pix = q.load()
    out = [[0] * LOGO_W for _ in range(LOGO_H)]
    for y in range(LOGO_H):
        for x in range(LOGO_W):
            if alpha.getpixel((x, y)) >= 40:
                out[y][x] = free[pix[x, y]]
    pal1 = [(0, 0, 0)] * 256
    for k, entry in enumerate(free):
        if 3 * k + 2 < len(qpal):
            pal1[entry] = tuple(qpal[3 * k:3 * k + 3])
    data = [0x00, 0x20]  # load address (not used: the program gives its own)
    for strip in range(LOGO_W // 8):
        for y in range(LOGO_H):
            data += out[y][strip * 8:strip * 8 + 8]
    return bytes(data), pal1, out


def swap(v):
    return ((v & 15) << 4) | (v >> 4)


def c_array(name, data, ctype="uint8_t"):
    lines = []
    for i in range(0, len(data), 16):
        lines.append("    " + ", ".join(f"0x{b:02x}" for b in data[i:i + 16]) + ",")
    return f"const {ctype} {name}[{len(data)}] = {{\n" + "\n".join(lines) + "\n};\n"


def main():
    outdir = sys.argv[1]
    preview = sys.argv[2] if len(sys.argv) > 2 else None

    tiles = build_tiles()
    icons = [("EMERALD", draw_icon_emerald()), ("CLOCK", draw_icon_clock()), ("LIFE", draw_icon_life())]
    font_cols = font_row_colours()
    extra = [[font_cols + [FONT_SHADOW] + [c for c in SEP_ROWS if c]]]
    # GDash's tiles take what colours are left; the game's own keep theirs
    own = [n for n, _ in tiles].index("CURSOR") + 1
    gd = tiles[own:]
    tiles = tiles[:own]
    images = quantise([t for _, t in tiles] + [i for _, i in icons] + extra)
    tiles = [(n, img) for (n, _), img in zip(tiles, images[:len(tiles)])]
    icons = [(n, img) for (n, _), img in zip(icons, images[len(tiles):len(tiles) + len(icons)])]
    have = {c for img in images for row in img for c in row if c is not None}
    later = 1 + len(title_colours()) + len(set(rank_colours()) - have)  # entry 0, the shine, the ranks
    tiles += gd_colours(gd, have, 255 - later)
    font_cols = images[-1][0][:16]
    shadow = images[-1][0][16]
    sep_cols = images[-1][0][17:]

    pal = Palette()

    def tile_data(ts):
        out = []
        for _, t in ts:
            for half in (0, 8):
                for y in range(T):
                    out += [pal(t[y][half + x]) for x in range(8)]
        return out
    # GDash's tiles get their palette entries last: the others keep theirs
    tile_bytes = tile_data(tiles[:own])
    icon_bytes = []
    for _, t in icons:
        for y in range(16):
            icon_bytes += [pal(t[y][x]) for x in range(8)]
    font_bits = []
    chars = "".join(FONT5x7.keys())
    for ch in chars:
        font_bits += font_glyph_bits(ch)
    font_row = [pal(c) for c in font_cols]
    font_shadow = pal(shadow)
    sep = []
    it = iter(sep_cols)
    for c in SEP_ROWS:
        sep += [pal(next(it)) if c else 0] * 8
    title_row = [pal.unique(c) for c in title_colours()]
    rank_row = [pal(c) for c in rank_colours()]
    tile_bytes += tile_data(tiles[own:])

    ui_entries = set(font_row) | {font_shadow} | set(icon_bytes) | set(sep)
    logo, pal1, logo_pix = make_logo(ui_entries)
    for i in ui_entries:
        pal1[i] = pal.colours[i]
    with open(f"{outdir}/logo.bin", "wb") as f:
        f.write(logo)
    with open(f"{outdir}/tiles.bin", "wb") as f:
        f.write(bytes([0x00, 0x00]) + bytes(tile_bytes))  # $10000, as video.h

    cols = pal.colours
    tile_index = {n: i for i, (n, _) in enumerate(tiles)}
    gd_tiles, gd_anims = gd_tile_table(tile_index)
    with open(f"{outdir}/gfx.h", "w") as f:
        f.write("// Generated by tools/mkgfx.py - do not edit\n#ifndef GFX_H\n#define GFX_H\n#include <stdint.h>\n\n")
        for i, (n, _) in enumerate(tiles):
            f.write(f"#define T_{n} {i}\n")
        f.write(f"#define TILE_COUNT {len(tiles)}\n\n")
        for i, (n, _) in enumerate(icons):
            f.write(f"#define ICON_{n} {i}\n")
        f.write(f"#define PAL_COUNT {len(cols)}\n#define GLYPH_COUNT {len(chars)}\n\n")
        f.write("extern const uint8_t pal_r[PAL_COUNT], pal_g[PAL_COUNT], pal_b[PAL_COUNT];\n")
        f.write("extern const uint8_t font_bits[GLYPH_COUNT * 16];\n")
        f.write("extern const char font_chars[GLYPH_COUNT + 1];\n")
        f.write("extern const uint8_t font_row[16];\n")
        f.write("extern const uint8_t title_row[16];  // palette entries of the big letters\n")
        f.write("extern const uint8_t rank_row[4 * 16];  // font colours: gold, silver, bronze, blue\n")
        f.write(f"#define FONT_SHADOW {font_shadow}\n")
        f.write(f"extern const uint8_t icon_gfx[{len(icons)} * 128];\n")
        f.write("extern const uint8_t sep_gfx[64];\n")
        f.write(f"#define T_SPARKLE 255  // gd_tile: an emerald, sparkling\n")
        f.write(f"extern const uint8_t gd_tile[{len(gd_tiles)}];  // the tile of each of GDash's elements\n")
        f.write(f"extern const uint8_t gd_anim[{len(gd_tiles)}];  // its frames: 1 << (low 2 bits), each 1 << (the rest) screen frames\n")
        # the elements whose tile changes by itself: their own frames, or the
        # game's animated tiles (main.c, gtile_of)
        game_anim = {tile_index[n] for n in ("FIREFLY0", "BUTTERFLY0", "AMOEBA0", "MAGIC0", "INBOX0", "OUTBOX0",
                                             "RF_VIEW4")}
        moving = sum(1 for t, a in zip(gd_tiles, gd_anims) if a & 3 or t in game_anim)
        f.write(f"#define GD_MOVING {moving}  // elements with gd_anim frames or a tile of the game that moves\n")
        f.write(f"\n#define LOGO_W {LOGO_W}\n#define LOGO_H {LOGO_H}\n")
        f.write("extern const uint8_t pal1_r[256], pal1_g[256], pal1_b[256];\n\n#endif\n")
    with open(f"{outdir}/gfx.c", "w") as f:
        f.write("// Generated by tools/mkgfx.py - do not edit\n#include \"gfx.h\"\n\n")
        f.write(c_array("pal_r", [swap(c[0]) for c in cols]))
        f.write(c_array("pal_g", [swap(c[1]) for c in cols]))
        f.write(c_array("pal_b", [swap(c[2]) for c in cols]))
        f.write(c_array("font_bits", font_bits))
        f.write(c_array("font_row", font_row))
        f.write(c_array("title_row", title_row))
        f.write(c_array("rank_row", rank_row))
        f.write(c_array("icon_gfx", icon_bytes))
        f.write(c_array("sep_gfx", sep))
        f.write(c_array("gd_tile", gd_tiles))
        f.write(c_array("gd_anim", gd_anims))
        f.write(c_array("pal1_r", [swap(c[0]) for c in pal1]))
        f.write(c_array("pal1_g", [swap(c[1]) for c in pal1]))
        f.write(c_array("pal1_b", [swap(c[2]) for c in pal1]))
        esc = chars.replace("\\", "\\\\").replace('"', '\\"')
        f.write(f'const char font_chars[GLYPH_COUNT + 1] = "{esc}";\n')

    print(f"mkgfx: {len(tiles)} tiles, {len(icons)} icons, {len(chars)} glyphs, {len(cols)} colours")
    if preview:
        write_preview(preview, tiles, icons, chars, font_cols, shadow)
        logo_img = Image.new("RGB", (LOGO_W, LOGO_H))
        for y in range(LOGO_H):
            for x in range(LOGO_W):
                logo_img.putpixel((x, y), pal1[logo_pix[y][x]])
        logo_img.resize((LOGO_W * 3, LOGO_H * 3), Image.NEAREST).save(preview.replace(".png", "-logo.png"))


def write_preview(path, tiles, icons, chars, font_cols, shadow):
    S = 4
    per_row = 12
    rows = (len(tiles) + per_row - 1) // per_row
    mock_w, mock_h = 19, 8
    W = max(per_row * (T + 2), mock_w * T) * S
    H = (rows * (T + 2) + 20 + mock_h * T + 4) * S
    img = Image.new("RGB", (W, H), (24, 24, 24))

    def put(t, ox, oy):
        for y, row in enumerate(t):
            for x, c in enumerate(row):
                c = c or (0, 0, 0)
                for dy in range(S):
                    for dx in range(S):
                        img.putpixel(((ox + x) * S + dx, (oy + y) * S + dy), c)

    for i, (_, t) in enumerate(tiles):
        put(t, (i % per_row) * (T + 2), (i // per_row) * (T + 2))
    oy = rows * (T + 2) + 1
    x = 0
    for _, t in icons:
        put(t, x, oy)
        x += 8
    for ch in "SMARAGD DASH 0123456789":
        put(render_glyph(font_glyph_bits(ch), font_cols), x, oy)
        x += 8
    oy += 19
    byname = dict(tiles)
    mock = [
        "SSSSSSSSSSSSSSSSSSS",
        "S..r.d...  ...rr.dS",
        "S.rr....b  .q..r..S",
        "S..R1..d.  ....wwwS",
        "S...  ...rrr.....dS",
        "Sww.  ..rrdr..a..OS",
        "S...dd..E....aa..rS",
        "SSSSSSSSSSSSSSSSSSS",
    ]
    key = {"S": "STEEL", ".": "DIRT", "r": "BOULDER", "d": "DIAMOND0", " ": "SPACE", "R": "RF_VIEW4",
           "1": "RF_RIGHT2", "b": "BUTTERFLY0", "q": "FIREFLY0", "w": "BRICK", "a": "AMOEBA0",
           "O": "OUTBOX1", "E": "EXPLODE2"}
    for y, row in enumerate(mock):
        for x, ch in enumerate(row):
            put(byname[key[ch]], x * T, oy + y * T)
    img.save(path)


if __name__ == "__main__":
    main()
