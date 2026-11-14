#!/usr/bin/env python3
"""Wedge Turbo's messages over the race, drawn at build time: the writing
the race puts in the middle of the view (sprites.c message()), in the
sizes the race has room for.

hud_images() gives the bank's images as (width, height, pixels), the pixels
colour numbers of the race view (0-7) or CLEAR:

    0-3     OUT OF FUEL, PAUSED, RACE OVER, FINAL LAP
    4-7     the countdown: 3, 2, 1, GO!
    8-17    the place at the finish: 1ST ... 10TH
    18-22   unused, empty
    23-24   the lap bar's room (panel.c writes it at the start of a race)

Writing: Exo 2 at its heaviest, light grey getting darker downwards, a black
edge round it; GO! in red.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'toolchain', 'fonts')
CLEAR = 0xFF
BLACK, LIGHT_RED, RED, DARK_RED, DARK_GREY, GREY, LIGHT_GREY = 0, 1, 2, 3, 4, 5, 6

MESSAGES = ['OUT OF FUEL', 'PAUSED', 'RACE OVER', 'FINAL LAP']
COUNTDOWN = ['3', '2', '1', 'GO!']
PLACES = ['1ST', '2ND', '3RD', '4TH', '5TH', '6TH', '7TH', '8TH', '9TH', '10TH']
# the sizes (the race's room for each)
SIZES = ([(106, 14), (65, 14), (91, 14), (89, 14)] + [(18, 26), (18, 26), (16, 26), (46, 26)]
         + [(40, 22)] * 10 + [(5, 5), (6, 5), (3, 4), (4, 4), (5, 4)] + [(194, 9)] * 2)


def font(size, weight=900):
    f = ImageFont.truetype(os.path.join(FONTS, 'Exo2.ttf'), size)
    f.set_variation_by_axes([weight])
    return f


def ink(text, size, spacing):
    """The writing's pixels (True where it is), cut to its extent"""
    f = font(size)
    widths = [f.getlength(c) for c in text]
    w = int(sum(widths) + spacing * (len(text) - 1)) + size
    im = Image.new('1', (w, size * 2), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    x = size // 2
    for c, cw in zip(text, widths):
        d.text((x, size // 2), c, fill=1, font=f)
        x += cw + spacing
    a = np.array(im, bool)
    ys, xs = np.nonzero(a)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def fit(text, w, h, spacing=1):
    """The largest writing that fits into w x h with its edge"""
    best = None
    for size in range(4, 3 * h):
        a = ink(text, size, spacing)
        if a.shape[0] > h - 2 or a.shape[1] > w - 2:
            break
        best = a
    return best


def draw(text, w, h, top, bottom, spacing=1):
    """text centred in w x h: from colour top (upper half) to bottom (lower),
    edged black"""
    a = fit(text, w, h, spacing)
    px = np.full((h, w), CLEAR, np.uint8)
    ah, aw = a.shape
    y0, x0 = (h - ah) // 2, (w - aw) // 2
    solid = np.zeros((h, w), bool)
    solid[y0:y0 + ah, x0:x0 + aw] = a
    edge = np.zeros_like(solid)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            edge |= np.roll(np.roll(solid, dy, 0), dx, 1)
    px[edge] = BLACK
    rows = np.arange(h)[:, None].repeat(w, 1)
    px[solid & (rows < y0 + ah * 0.55)] = top
    px[solid & (rows >= y0 + ah * 0.55)] = bottom
    return px


def hud_images():
    out = []
    for text, (w, h) in zip(MESSAGES, SIZES[0:4]):
        out.append((w, h, draw(text, w, h, LIGHT_GREY, GREY, 1)))
    for text, (w, h) in zip(COUNTDOWN, SIZES[4:8]):
        top, bottom = (LIGHT_RED, RED) if text == 'GO!' else (LIGHT_GREY, GREY)
        out.append((w, h, draw(text, w, h, top, bottom, 0)))
    for text, (w, h) in zip(PLACES, SIZES[8:18]):
        out.append((w, h, draw(text, w, h, LIGHT_GREY, GREY, 0)))
    for w, h in SIZES[18:]:
        out.append((w, h, np.full((h, w), CLEAR, np.uint8)))
    return [(w, h, px.tobytes()) for w, h, px in out]


if __name__ == '__main__':
    import sys
    ims = hud_images()
    pal = {CLEAR: (40, 40, 90), BLACK: (0, 0, 0), LIGHT_RED: (204, 68, 68), RED: (170, 0, 0),
           GREY: (102, 102, 102), LIGHT_GREY: (204, 204, 204)}
    W = sum(w + 2 for w, _, _ in ims[:18])
    sheet = Image.new('RGB', (W, 26), pal[CLEAR])
    x = 0
    for w, h, px in ims[:18]:
        a = np.frombuffer(px, np.uint8).reshape(h, w)
        sheet.paste(Image.fromarray(np.array([[pal[v] for v in row] for row in a], np.uint8)), (x, 26 - h))
        x += w + 2
    sheet.resize((W * 3, 78), Image.NEAREST).save(sys.argv[1])
