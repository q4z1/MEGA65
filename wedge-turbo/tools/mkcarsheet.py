#!/usr/bin/env python3
"""art/cars.png from five drawings of the car, one per step of the turn the
race wants (tools/mkcars.py TURNS, the rear face's shift in car heights:
0 0.026 0.082 0.146 0.228): art/car-rear.png (straight from behind),
art/car-turn1.png to car-turn3.png and art/car-end.png (turned the most, the
nose to the left, the left flank seen). All on a transparent ground, drawn at
the same scale and camera - the three between drawn as one animation from
the straight drawing to the most turned one, and picked by their turn.

The drawings have a double tailpipe right of the silencer only; turned the
other way the race mirrors them, and the pipes would jump from one side to
the other. So they are mirrored to the silencer's left too.

Highlights in white (lines along the edges) are made the paint's light
green: white edges read as a comic's at the race's sizes.

Run by hand when the drawings change: python3 tools/mkcarsheet.py
"""
import os
import sys

import numpy as np
from PIL import Image

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'art')
VIEWS = ('car-rear.png', 'car-turn1.png', 'car-turn2.png', 'car-turn3.png', 'car-end.png')
SHEET = 'cars.png'
MAGENTA = (255, 0, 255)
LIGHT_GREEN = (87, 163, 102)
GAP = 24


def load(name):
    return np.asarray(Image.open(os.path.join(ART, name)).convert('RGBA')).copy()


def lum(c):
    return c @ np.array([0.3, 0.59, 0.11])


def calmed(im):
    """White highlights on the paint (light, greenish) in the light green"""
    c = im[:, :, :3].astype(int)
    light = (im[:, :, 3] > 0) & (lum(c) > 150)
    im[light & (c[:, :, 1] > c[:, :, 0] + 15) & (c[:, :, 1] > c[:, :, 2] + 15), :3] = LIGHT_GREEN
    return im


def runs(xs):
    """Consecutive columns: (first, last) each"""
    out = []
    for x in xs:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return out


def both_pipes(im, name):
    """The tailpipes right of the silencer mirrored to its left, about the
    silencer's middle: the silencer is the longest grey run in the car's
    lowest third (above it the number plate, grey too); right of it its
    cap, then the pipes"""
    c = im[:, :, :3].astype(int)
    w = im.shape[1]
    grey = (np.ptp(c, 2) < 14) & (lum(c) > 60) & (im[:, :, 3] > 0)
    car = np.nonzero((im[:, :, 3] > 0).any(1))[0]
    best = None
    for y in range(car[0] + 2 * (car[-1] - car[0]) // 3, car[-1] + 1):
        for s, e in runs(np.nonzero(grey[y])[0]):
            if best is None or e - s > best[2] - best[1]:
                best = (y, s, e)
    y0, s, e = best
    axis = (s + e) / 2
    rows = [y for y in range(y0 - 8, y0 + 8) if grey[y, s + 5:e - 5].mean() > 0.5 or grey[y, e + 1:e + 41].any()]
    ya, yb = min(rows) - 1, max(rows) + 1
    parts = runs([x for x in range(e + 1, min(w, e + 46)) if grey[ya:yb + 1, x].any()])
    if len(parts) < 2:
        sys.exit(f'art/{name}: no tailpipes right of the silencer')
    xa, xb = parts[0][1] + 2, parts[-1][1] + 2
    for y in range(ya, yb + 1):
        for x in range(xa, xb + 1):
            m = int(round(2 * axis - x))
            if im[y, x, 3] and im[y, m, 3]:
                im[y, m] = im[y, x]
    return im


def cut(im):
    ys, xs = np.nonzero(im[:, :, 3] > 0)
    return im[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def main():
    views = [cut(both_pipes(calmed(load(n)), n)) for n in VIEWS]
    h = max(v.shape[0] for v in views)
    sheet = Image.new('RGB', (sum(v.shape[1] for v in views) + GAP * (len(views) + 1), h + 2 * GAP), MAGENTA)
    x = GAP
    for v in views:  # all on the bottom line
        img = Image.fromarray(v, 'RGBA')
        sheet.paste(img, (x, GAP + h - v.shape[0]), img)
        x += v.shape[1] + GAP
    sheet.save(os.path.join(ART, SHEET))
    print(f'art/{SHEET}: {len(views)} views, {h} pixels high', file=sys.stderr)


if __name__ == '__main__':
    main()
