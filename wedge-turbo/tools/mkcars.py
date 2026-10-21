#!/usr/bin/env python3
"""Wedge Turbo's cars: drawn by us (art/cars.png), brought to the race's
images at build time.

The race shows a car from behind, turned a little either way, in up to
nine angles and 17 sizes (the bank's images as tools/mksprites.py has them:
the player's car 0-62, the opponents' 63-125, as many and as large as
before, so that everything around them stays).

art/cars.png holds the drawings, each in a magenta box of its own, in
rows; VIEWS says which are which. Turned to the right is the drawing
turned as far to the left, mirrored. Each image takes the drawing of its
angle, in the race's colours and brought down to its size - as high as
the game's image, as wide as the drawing is then, so that the car keeps
its size as it turns. The colours first, on the drawing as large as it
is: where it is paint, the paint - in three shades (the player's, from the
drawing: CAR_PAINT) or two (the opponents': the same car, which the game
colours six ways) - as light as the paint around there, so the shades lie
in calm areas; the rest (glass, lights, wheels, plate) black, reds and
greys. Then down to the size, each pixel the colour most of its area has
(none mixed, the edges stay sharp), the drawing's thick outline thinned.

render() gives the bank's images; with them, for the player's largest
size, where the number plate's digit and the brake lights go, and the
player's paint.
"""
import os

import numpy as np
from PIL import Image, ImageFilter

CLEAR = 0xFF
BLACK, LIGHT_RED, RED, DARK_RED, DARK_GREY, GREY, LIGHT_GREY = 0, 1, 2, 3, 4, 5, 6
FIXED = [0x000, 0xC44, 0xA00, 0x600, 0x222, 0x666, 0xCCC]

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'art', 'cars.png')
# the drawings for angles 0-4 (the nose to the left, most first, then
# straight on): their places in art/cars.png, in reading order (boxes too
# small to use not counted), and whether the drawing is turned the other
# way (then mirrored); the large ones, the finest. Turned only a little - at angle 0 the flank
# shows on a sixth of the width - as the race picks the angle by where the
# car is as much as by its turns
VIEWS = ((2, True), (3, True), (3, True), (0, False), (0, False))


def rgb12(c):
    return np.array([(c >> 8 & 15) * 17, (c >> 4 & 15) * 17, (c & 15) * 17], float)


def to12(c):
    return sum(min(15, round(v / 17)) << s for v, s in zip(c, (8, 4, 0)))


def boxes(mag):
    """The magenta boxes (x0, y0, x1, y1) in reading order: each the bounds
    of a magenta area that hangs together (looked at in cells of 4 x 4)"""
    h, w = mag.shape[0] // 4, mag.shape[1] // 4
    cells = mag[:h * 4, :w * 4].reshape(h, 4, w, 4).mean((1, 3)) > 0.5
    seen = np.zeros_like(cells)
    found = []
    for y, x in zip(*np.nonzero(cells)):
        if seen[y, x]:
            continue
        seen[y, x] = True
        todo, x0, y0, x1, y1 = [(y, x)], x, y, x, y
        while todo:
            cy, cx = todo.pop()
            x0, y0, x1, y1 = min(x0, cx), min(y0, cy), max(x1, cx), max(y1, cy)
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and cells[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    todo.append((ny, nx))
        if (x1 - x0) * (y1 - y0) >= 16:
            found.append((x0 * 4, y0 * 4, x1 * 4 + 4, y1 * 4 + 4))
    rows = []
    for b in sorted(found, key=lambda b: b[1]):
        for r in rows:
            if abs(r[0][1] - b[1]) < 12:
                r.append(b)
                break
        else:
            rows.append([b])
    return [b for r in rows for b in sorted(r)]


def drawings():
    """The drawings in art/cars.png: per magenta box (but the smallest) the
    car (RGB, and how much each pixel is the car), cut to its bounds"""
    im = np.asarray(Image.open(ART).convert('RGB')).astype(int)
    # magenta, and where the car's edge took on some of it
    mag = (im[:, :, 0] - im[:, :, 1] > 40) & (im[:, :, 2] - im[:, :, 1] > 40)
    out = []
    found = boxes(mag)
    tallest = max(y1 - y0 for _, y0, _, y1 in found)
    for x0, y0, x1, y1 in found:
        if y1 - y0 < tallest // 5:  # a scrap, or a drawing too small to use
            continue
        car = ~mag[y0:y1, x0:x1]
        car[:3, :] = car[-3:, :] = False  # the box's soft edge
        car[:, :3] = car[:, -3:] = False
        ys, xs = np.nonzero(car)
        by0, by1, bx0, bx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        out.append((im[y0 + by0:y0 + by1, x0 + bx0:x0 + bx1].astype(float), car[by0:by1, bx0:bx1].astype(float)))
    return out


def is_paint(col):
    """Where a drawing is paint: green above all"""
    return (col[:, :, 1] > col[:, :, 0] + 30) & (col[:, :, 1] > col[:, :, 2] + 30)


def coloured(drawing, shades, details):
    """A drawing in the race's colours, at its own size: where it is paint,
    the shade (shades: [(index, rgb)], light to dark) as light as the paint
    around there - smoothed, so the shades lie in calm areas, not in specks
    - else the nearest of details ({index: rgb}); CLEAR where it is not the
    car"""
    col, alpha = drawing
    paint = is_paint(col) & (alpha > 0)
    lum = col @ np.array([0.3, 0.59, 0.11])

    def blur(v, r):  # v 0-255
        return np.asarray(Image.fromarray(np.clip(v, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)),
                          float)

    r = max(1.0, col.shape[1] / 120)
    smooth = blur(lum * paint, r) * 255 / np.maximum(blur(paint * 255.0, r), 1e-6)
    shade_lum = np.array([rgb @ np.array([0.3, 0.59, 0.11]) for _, rgb in shades])
    shade = np.array([i for i, _ in shades])[np.abs(smooth[:, :, None] - shade_lum).argmin(2)]
    idx = list(details)
    pal = np.array([details[i] for i in idx])
    d = (((col[:, :, None, :] - pal[None, None, :, :]) ** 2) * np.array([0.3, 0.59, 0.11])).sum(3)
    rest = np.array(idx)[d.argmin(2)]
    out = np.where(paint, shade, rest)
    out[alpha <= 0] = CLEAR
    return out


# what counts more where a small area decides: the lights, the plate
WEIGHT = {LIGHT_RED: 1.8, RED: 1.8, DARK_RED: 1.5, LIGHT_GREY: 1.6}


def shrink(indices, w, h, mirror):
    """Colour indices down to w x h: per pixel the colour most of its area
    has (no colours mixed: the edges stay sharp), clear where most of it
    is"""
    if mirror:
        indices = indices[:, ::-1]
    best, score = None, None
    for v in np.unique(indices):
        share = np.asarray(Image.fromarray(((indices == v) * 255).astype(np.uint8)).resize((w, h), Image.BOX), float)
        share = share * (1 if v == CLEAR else WEIGHT.get(int(v), 1.0))
        if best is None:
            best, score = np.full((h, w), v), share
        else:
            better = share > score
            best[better], score[better] = v, share[better]
    return bytes(best.astype(np.uint8).flatten())


def thinned(px, w, h):
    """The drawing's dark outline (a comic's, thick) thinned: a dark pixel
    on the edge goes where the one inside it is dark too - one pixel of
    outline stays"""
    out = bytearray(px)
    dark = (BLACK, DARK_GREY)

    def at(x, y):
        return px[y * w + x] if 0 <= x < w and 0 <= y < h else CLEAR

    for y in range(h):
        for x in range(w):
            if px[y * w + x] not in dark:
                continue
            for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                if at(x + dx, y + dy) == CLEAR and at(x - dx, y - dy) in dark:
                    out[y * w + x] = CLEAR
                    break
    return bytes(out)


def paint_shades(drawing):
    """The player's paint: three shades of the drawing's green, light to
    dark"""
    col, alpha = drawing
    green = col[is_paint(col) & (alpha > 0)]
    lum = green @ np.array([0.3, 0.59, 0.11])
    order = np.sort(lum)
    cuts = [order[len(order) // 3], order[2 * len(order) // 3]]
    shades = [green[lum >= cuts[1]], green[(lum >= cuts[0]) & (lum < cuts[1])], green[lum < cuts[0]]]
    return [to12(s.mean(0)) for s in shades]


def render(dims, car_table, player_paint, opp_paint):
    """The bank's 126 images, as high as dims[i]; car_table: per size and
    angle the image (as the race picks them). Returns the images; per angle
    of the largest size the plate's centre and the lit brake lights (image,
    x, y from the car image's top left); the player's paint (three 12-bit
    colours, light to dark)"""
    d = drawings()
    paint = paint_shades(d[VIEWS[4][0]])
    details = {i: rgb12(c) for i, c in enumerate(FIXED)}
    # the player's paint in its three shades; the opponents' in two, as
    # light as the white colouring's (main.c) - the same car, painted so
    player = [(p, rgb12(c)) for p, c in zip(player_paint, paint)]
    opp = [(opp_paint[0], rgb12(paint[0])), (opp_paint[0], rgb12(paint[1])), (opp_paint[1], rgb12(paint[2]))]

    angles = {}
    for k, i in enumerate(car_table):
        angles.setdefault(i, []).append((k // 9, k % 9))
    images = [None] * 126
    marks = []
    for base, shades in ((0, player), (63, opp)):
        views = [(coloured(d[v], shades, details), flip) for v, flip in VIEWS]
        for i in range(63):
            size = angles[i][0][0]
            a = [angle for s, angle in angles[i] if s == size]
            turn = sum(a) / len(a) - 4  # < 0: the nose to the left
            view, flip = views[4 - round(abs(turn))]
            h = dims[i][1]
            w = max(1, round(h * view.shape[1] / view.shape[0]))
            images[base + i] = (w, h, thinned(shrink(view, w, h, (turn > 0) != flip), w, h))
            if base == 0 and size == 0:
                marks.append(overlay(images[i]))
    return images, marks, paint


def overlay(car):
    """The plate's centre in the car image (its light grey), and the brake
    lights lit: the car's reds a shade lighter, an image of them alone and
    where it goes"""
    w, h, px = car
    plate = [(i % w, i // w) for i, v in enumerate(px) if v == LIGHT_GREY and i // w > h // 3]
    centre = (sum(x for x, _ in plate) // len(plate), sum(y for _, y in plate) // len(plate)) if plate else (w // 2, h * 2 // 3)
    lit = {RED: LIGHT_RED, DARK_RED: RED, LIGHT_RED: LIGHT_RED}
    on = [(i % w, i // w) for i, v in enumerate(px) if v in lit]
    x0, x1 = min(x for x, _ in on), max(x for x, _ in on)
    y0, y1 = min(y for _, y in on), max(y for _, y in on)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    img = bytes(lit.get(px[(y0 + y) * w + x0 + x], CLEAR) for y in range(bh) for x in range(bw))
    return centre, (bw, bh, img), (x0, y0)
