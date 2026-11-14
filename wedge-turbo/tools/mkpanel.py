#!/usr/bin/env python3
"""Wedge Turbo's panel at the right of the race view, drawn at build time:
gear, speed, rpm, fuel and place of player 1, over the view.

panel_file() gives the panel as src/banks.c loads it (PANEL): u8 width,
height, number of fields; per field u8 x, y, w, h, states; then, packed by
the caller, the panel without values (width x height colour numbers, CLEAR
where the view shows through) and every field's states (w x h each, one
after the other). The fields, in the order src/panel.c has them:

    hundreds, tens, units   the speed's digits (mph), 10 states each
    gear                    5 states: gears 1-5
    rpm                     37 states: the bar, 0-36
    fuel                    37 states: the bar, 0-36 (blinks below 8)
    place                   20 states: 1ST-20TH

Its colours are the sprite colours 17-19 and 25-27 (COLOURS): an edge, the
values, the labels; the bars' green, yellow, red. The labels and digits are
a small pixel font of our own; the place is Exo 2 at its heaviest.
Only columns 0-42 are seen (src/panel.c: from x 277 of 320).
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'toolchain', 'fonts')
CLEAR = 0xFF
PANEL_W, PANEL_H = 48, 92
SEEN = 43  # the columns shown
ROOM = 0x9000  # src/mem.h PANEL_SIZE: the panel and its states, unpacked
EDGE, VALUE, LABEL, GREEN, YELLOW, RED = 17, 18, 19, 25, 26, 27
COLOURS = {EDGE: 0x000, VALUE: 0xFFF, LABEL: 0xFA2, GREEN: 0x2D4, YELLOW: 0xEE3, RED: 0xE33}

# The labels' letters, 5 rows high
SMALL = {
    'A': ['.##.', '#..#', '####', '#..#', '#..#'],
    'D': ['###.', '#..#', '#..#', '#..#', '###.'],
    'E': ['####', '#...', '###.', '#...', '####'],
    'F': ['####', '#...', '###.', '#...', '#...'],
    'G': ['.###', '#...', '#.##', '#..#', '.###'],
    'H': ['#..#', '#..#', '####', '#..#', '#..#'],
    'L': ['#...', '#...', '#...', '#...', '####'],
    'M': ['#...#', '##.##', '#.#.#', '#...#', '#...#'],
    'N': ['#..#', '##.#', '#.##', '#..#', '#..#'],
    'O': ['.##.', '#..#', '#..#', '#..#', '.##.'],
    'P': ['###.', '#..#', '###.', '#...', '#...'],
    'R': ['###.', '#..#', '###.', '#.#.', '#..#'],
    'S': ['.###', '#...', '.##.', '...#', '###.'],
    'T': ['###', '.#.', '.#.', '.#.', '.#.'],
    'U': ['#..#', '#..#', '#..#', '#..#', '.##.'],
}
# The values' digits, 7 rows high, two pixels wide strokes
DIGITS = {
    '0': ['.###.', '##.##', '##.##', '##.##', '##.##', '##.##', '.###.'],
    '1': ['..##.', '.###.', '..##.', '..##.', '..##.', '..##.', '.####'],
    '2': ['.###.', '##.##', '...##', '..##.', '.##..', '##...', '#####'],
    '3': ['####.', '...##', '...##', '.###.', '...##', '...##', '####.'],
    '4': ['...##', '..###', '.#.##', '##.##', '#####', '...##', '...##'],
    '5': ['#####', '##...', '####.', '...##', '...##', '##.##', '.###.'],
    '6': ['.###.', '##...', '####.', '##.##', '##.##', '##.##', '.###.'],
    '7': ['#####', '...##', '..##.', '..##.', '.##..', '.##..', '.##..'],
    '8': ['.###.', '##.##', '##.##', '.###.', '##.##', '##.##', '.###.'],
    '9': ['.###.', '##.##', '##.##', '.####', '...##', '...##', '.###.'],
}

# Where things are: the labels' rows, the fields
GEAR_Y, SPEED_Y, RPM_Y, FUEL_Y, POS_Y = 0, 11, 28, 44, 60
BAR_X, BAR_W, BAR_H = 2, 39, 6  # the bars' frame (inside: 37 x 4)
PLACE_Y, PLACE_H = 69, 22


def glyphs(text, font):
    """The pixels of text in a bitmap font, a column apart"""
    rows = len(next(iter(font.values())))
    cols = []
    for c in text:
        if c == ' ':
            cols += [[False] * rows] * 3
            continue
        g = font[c]
        cols += [[g[r][x] == '#' for r in range(rows)] for x in range(len(g[0]))]
        cols.append([False] * rows)
    return np.array(cols[:-1], bool).T


def edged(px, solid, x, y, colour):
    """solid at (x, y) in colour, a black edge round it (over clear only)"""
    h, w = solid.shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for yy, xx in zip(*np.nonzero(solid)):
                Y, X = y + yy + dy, x + xx + dx
                if 0 <= Y < PANEL_H and 0 <= X < PANEL_W and px[Y, X] == CLEAR:
                    px[Y, X] = EDGE
    sub = px[y:y + h, x:x + w]
    sub[solid] = colour


def label(px, text, y, value_room=0):
    """A label, centred over the seen columns (or left of value_room) with
    a rule each side"""
    g = glyphs(text, SMALL)
    room = SEEN - value_room
    x = (room - g.shape[1]) // 2
    edged(px, g, x, y + 1, LABEL)
    for x0, x1 in ((1, x - 3), (x + g.shape[1] + 2, room - 2)):
        if x1 > x0:
            edged(px, np.ones((1, x1 - x0), bool), x0, y + 3, LABEL)


def heavy(text, h, w):
    """text in Exo 2 at its heaviest, as large as fits into w x h"""
    best = None
    for size in range(6, 4 * h):
        f = ImageFont.truetype(os.path.join(FONTS, 'Exo2.ttf'), size)
        f.set_variation_by_axes([900])
        im = Image.new('1', (size * 4, size * 2), 0)
        d = ImageDraw.Draw(im)
        d.fontmode = '1'
        d.text((size // 2, size // 2), text, fill=1, font=f)
        a = np.array(im, bool)
        ys, xs = np.nonzero(a)
        a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        if a.shape[0] > h or a.shape[1] > w:
            break
        best = a
    return best


def base():
    px = np.full((PANEL_H, PANEL_W), CLEAR, np.uint8)
    label(px, 'GEAR', GEAR_Y, 12)
    label(px, 'MPH', SPEED_Y)
    label(px, 'RPM', RPM_Y)
    label(px, 'FUEL', FUEL_Y)
    label(px, 'POS', POS_Y)
    for y in (RPM_Y + 8, FUEL_Y + 8):
        px[y:y + BAR_H, BAR_X:BAR_X + BAR_W] = EDGE
    return px


def gear_state(px, g):
    edged(px, glyphs(str(g + 1), DIGITS), SEEN - 9, GEAR_Y + 1, VALUE)


def digit_state(k):
    def put(px, v):
        if k == 0 and v == 0:
            return  # no leading zero
        x = (SEEN - 17) // 2 + 6 * k
        edged(px, glyphs(str(v), DIGITS), x, SPEED_Y + 8, VALUE)
    return put


def bar_state(y, colour_of):
    def put(px, v):
        for i in range(v):
            px[y + 1:y + BAR_H - 1, BAR_X + 1 + i] = colour_of(i, v)
    return put


def rpm_colour(i, v):
    return GREEN if i < 25 else YELLOW if i < 32 else RED


def fuel_colour(i, v):
    return RED if v < 8 else YELLOW if v < 16 else GREEN


def place_state(px, p):
    suffix = {1: 'ST', 2: 'ND', 3: 'RD'}.get((p + 1) % 10 if p + 1 not in (11, 12, 13) else 0, 'TH')
    s = glyphs(suffix, SMALL)
    n = heavy(str(p + 1), PLACE_H - 2, SEEN - 4 - s.shape[1])
    w = n.shape[1] + 2 + s.shape[1]
    x = max(1, (SEEN - w) // 2)
    edged(px, n, x, PLACE_Y + 1, VALUE)
    edged(px, s, x + n.shape[1] + 2, PLACE_Y + 2, LABEL)


FIELDS = [
    ('hundreds', 10, digit_state(0)),
    ('tens', 10, digit_state(1)),
    ('units', 10, digit_state(2)),
    ('gear', 5, gear_state),
    ('rpm', 37, bar_state(RPM_Y + 8, rpm_colour)),
    ('fuel', 37, bar_state(FUEL_Y + 8, fuel_colour)),
    ('place', 20, place_state),
]


def panel_pictures():
    """The panel without values, and per field its states (whole panels)"""
    b = base()
    fields = []
    for name, n, put in FIELDS:
        pics = []
        for v in range(n):
            p = b.copy()
            put(p, v)
            pics.append(p)
        fields.append((name, pics))
    return b, fields


def panel_file():
    """PANEL's header and its pixels (unpacked): the header, the base, then
    per field the states inside the field's rectangle"""
    b, fields = panel_pictures()
    head = bytearray([PANEL_W, PANEL_H, len(fields)])
    states = bytearray()
    for name, pics in fields:
        changed = np.zeros_like(b, bool)
        for p in pics:
            changed |= p != b
        ys, xs = np.nonzero(changed)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        head += bytes([x0, y0, x1 - x0, y1 - y0, len(pics)])
        for p in pics:
            states += p[y0:y1, x0:x1].tobytes()
    px = b.tobytes() + bytes(states)
    assert len(px) <= ROOM, f'the panel takes {len(px)} bytes, room for {ROOM} (src/mem.h PANEL_SIZE)'
    return bytes(head), px


if __name__ == '__main__':
    import sys
    b, fields = panel_pictures()
    show = [b] + [dict(fields)[k][v] for k, v in (('place', 8),)]
    p = b.copy()
    for (name, pics), v in zip(fields, (1, 3, 1, 4, 20, 30, 8)):
        sel = pics[v] != b
        p[sel] = pics[v][sel]
    low = b.copy()
    for (name, pics), v in zip(fields, (0, 0, 7, 0, 5, 6, 0)):
        sel = pics[v] != b
        low[sel] = pics[v][sel]
    rgb = {CLEAR: (60, 110, 200)}
    rgb.update({k: ((c >> 8 & 15) * 17, (c >> 4 & 15) * 17, (c & 15) * 17) for k, c in COLOURS.items()})
    sheet = Image.new('RGB', (3 * (PANEL_W + 4), PANEL_H), (0, 0, 0))
    for k, pic in enumerate((b, p, low)):
        im = Image.new('RGB', (PANEL_W, PANEL_H))
        im.putdata([rgb[v] for v in pic.flatten()])
        sheet.paste(im.crop((0, 0, SEEN, PANEL_H)), (k * (PANEL_W + 4), 0))
    sheet.resize((sheet.width * 5, sheet.height * 5), Image.NEAREST).save(sys.argv[1])
