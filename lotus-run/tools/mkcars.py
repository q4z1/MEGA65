#!/usr/bin/env python3
"""Lotus Run's cars: two models of our own, rendered at build time.

The race shows a car from behind, turned a little either way, in up to
nine angles and 17 sizes (the bank's images as tools/mksprites.py has them:
the player's car 0-62, the opponents' 63-125, as many and as large as
before, so that everything around them stays). The cars are made of flat
faces - body, glass, lights, wheels - drawn back to front four times as
large and brought down to the image size, in the race's colours: paint in
three shades (the player's) or two (the opponents', which the game colours
six ways), lights red, the rest black and greys.

render() gives the bank's images; with them, for the player's largest
size, where the number plate's digit and the brake lights go.
"""
import math
from array import array

from PIL import Image

CLEAR = 0xFF
BLACK, LIGHT_RED, RED, DARK_RED, DARK_GREY, GREY, LIGHT_GREY = 0, 1, 2, 3, 4, 5, 6
LIT = 0xF0  # a brake light when it is lit (only for the overlay)

# materials: 'paint' is shaded by the face's direction
PAINT = 'paint'


def box(x0, x1, y0, y1, z0, z1, mat, faces):
    """A box's faces"""
    p = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for f in ([p[0], p[1], p[3], p[2]], [p[4], p[5], p[7], p[6]], [p[0], p[1], p[5], p[4]],
              [p[2], p[3], p[7], p[6]], [p[0], p[2], p[6], p[4]], [p[1], p[3], p[7], p[5]]):
        faces.append((f, mat))


def rect(x0, x1, y0, y1, mat, decals):
    """A flat piece on the rear panel (drawn over it, in order)"""
    decals.append(([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], mat))


def both(x0, x1, y0, y1, mat, decals):
    rect(x0, x1, y0, y1, mat, decals)
    rect(-x1, -x0, y0, y1, mat, decals)


def body(f, w, rw, bottom, top, length, front, chamfer):
    """The body: a rear panel (half width rw) with its corners cut back to
    the sides (half width w), a deck to the cabin, the sides, the bonnet"""
    deck = top + 0.04
    f.append(([(-rw, bottom, 0), (rw, bottom, 0), (rw, top, 0), (-rw, top, 0)], PAINT))
    for s in (-1, 1):
        f.append(([(s * rw, bottom, 0), (s * w, bottom, chamfer), (s * w, top, chamfer), (s * rw, top, 0)], PAINT))
        f.append(([(s * w, bottom, chamfer), (s * w, top, chamfer), (s * w, front + 0.06, length),
                   (s * w, bottom + 0.02, length)], PAINT))
    f.append(([(-rw, top, 0), (rw, top, 0), (w, deck, chamfer), (-w, deck, chamfer)], PAINT))
    return deck


def wheels(f, x0, x1, rear, front):
    for s in (-1, 1):
        for zc in (rear, front):
            a, b = sorted((s * x0, s * x1))
            box(a, b, 0.0, 0.62, zc - 0.32, zc + 0.32, BLACK, f)


def wedge():
    """The player's car: low, a wedge forward, a wing on struts over the
    tail, a strip of lights right across, louvres on the engine cover"""
    f, d = [], []
    w = 0.98
    deck = body(f, w, 0.90, 0.20, 0.66, 4.25, 0.56, 0.12)
    f.append(([(-w, deck, 0.12), (w, deck, 0.12), (w, 0.76, 1.05), (-w, 0.76, 1.05)], PAINT))
    f.append(([(-w, 0.76, 1.05), (w, 0.76, 1.05), (w, 0.72, 3.1), (-w, 0.72, 3.1)], PAINT))
    f.append(([(-w, 0.72, 3.1), (w, 0.72, 3.1), (w, 0.58, 4.25), (-w, 0.58, 4.25)], PAINT))
    for k in range(4):  # louvres
        z = 0.30 + 0.17 * k
        f.append(([(-0.50, deck + 0.012, z), (0.50, deck + 0.012, z), (0.50, deck + 0.012, z + 0.07),
                   (-0.50, deck + 0.012, z + 0.07)], BLACK))
    f.append(([(-0.66, 0.76, 1.05), (0.66, 0.76, 1.05), (0.54, 1.10, 1.8), (-0.54, 1.10, 1.8)], DARK_GREY))
    f.append(([(-0.54, 1.10, 1.8), (0.54, 1.10, 1.8), (0.54, 1.10, 2.35), (-0.54, 1.10, 2.35)], PAINT))
    for s in (-1, 1):
        f.append(([(s * 0.66, 0.76, 1.05), (s * 0.54, 1.10, 1.8), (s * 0.54, 1.10, 2.35),
                   (s * 0.70, 0.73, 3.1)], BLACK))
        f.append(([(s * (w + 0.005), 0.40, 1.25), (s * (w + 0.005), 0.60, 1.25), (s * (w + 0.005), 0.58, 1.75),
                   (s * (w + 0.005), 0.40, 1.75)], BLACK))
    f.append(([(-0.54, 1.10, 2.35), (0.54, 1.10, 2.35), (0.70, 0.73, 3.1), (-0.70, 0.73, 3.1)], DARK_GREY))
    for s in (-1, 1):
        box(s * 0.56 - 0.04, s * 0.56 + 0.04, deck, 0.98, 0.14, 0.24, BLACK, f)
        box(s * 0.90 - 0.025, s * 0.90 + 0.025, 0.90, 1.06, -0.04, 0.34, PAINT, f)
    box(-0.90, 0.90, 0.97, 1.02, -0.04, 0.32, PAINT, f)
    wheels(f, 0.78, 0.97, 0.85, 3.4)
    # the rear
    rect(-0.84, 0.84, 0.47, 0.64, BLACK, d)
    both(0.30, 0.82, 0.50, 0.61, RED, d)
    both(0.30, 0.82, 0.50, 0.53, DARK_RED, d)
    both(0.30, 0.38, 0.50, 0.61, LIGHT_GREY, d)
    rect(-0.84, 0.84, 0.20, 0.29, DARK_GREY, d)
    rect(-0.24, 0.24, 0.31, 0.43, LIGHT_GREY, d)
    both(0.32, 0.46, 0.22, 0.29, GREY, d)
    return f, d


def coupe():
    """The opponents' car: rounder and higher, a long rear window, a lip
    over the tail, round lights two a side"""
    f, d = [], []
    w = 0.96
    deck = body(f, w, 0.86, 0.22, 0.72, 4.4, 0.60, 0.22)
    f.append(([(-0.80, 0.74, 0.0), (0.80, 0.74, 0.0), (0.80, 0.82, -0.05), (-0.80, 0.82, -0.05)], PAINT))
    f.append(([(-0.80, 0.82, -0.05), (0.80, 0.82, -0.05), (w, deck, 0.22), (-w, deck, 0.22)], PAINT))
    f.append(([(-w, deck, 0.22), (w, deck, 0.22), (w, 0.80, 0.50), (-w, 0.80, 0.50)], PAINT))
    f.append(([(-w, 0.80, 0.50), (w, 0.80, 0.50), (w, 0.70, 3.2), (-w, 0.70, 3.2)], PAINT))
    f.append(([(-w, 0.70, 3.2), (w, 0.70, 3.2), (w, 0.60, 4.4), (-w, 0.60, 4.4)], PAINT))
    f.append(([(-0.72, 0.80, 0.50), (0.72, 0.80, 0.50), (0.58, 1.18, 1.9), (-0.58, 1.18, 1.9)], DARK_GREY))
    f.append(([(-0.58, 1.18, 1.9), (0.58, 1.18, 1.9), (0.58, 1.18, 2.5), (-0.58, 1.18, 2.5)], PAINT))
    for s in (-1, 1):
        f.append(([(s * 0.72, 0.80, 0.50), (s * 0.58, 1.18, 1.9), (s * 0.58, 1.18, 2.5),
                   (s * 0.76, 0.74, 3.2)], BLACK))
    f.append(([(-0.58, 1.18, 2.5), (0.58, 1.18, 2.5), (0.76, 0.74, 3.2), (-0.76, 0.74, 3.2)], DARK_GREY))
    wheels(f, 0.76, 0.95, 0.95, 3.5)
    for x0 in (0.46, 0.64):
        both(x0, x0 + 0.13, 0.54, 0.67, DARK_RED, d)
        both(x0 + 0.02, x0 + 0.11, 0.56, 0.65, RED, d)
    rect(-0.24, 0.24, 0.34, 0.46, LIGHT_GREY, d)
    rect(-0.80, 0.80, 0.22, 0.30, BLACK, d)
    rect(-0.22, -0.08, 0.23, 0.30, GREY, d)
    return f, d


# ------------------------------------------------------------ drawing

EYE = (0.0, 1.9, -9.5)
TARGET = (0.0, 0.5, 1.5)
LIGHT = (-0.35, 0.85, -0.4)


def norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1
    return tuple(c / n for c in v)


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


FWD = norm(sub(TARGET, EYE))
RIGHT = norm(cross((0, 1, 0), FWD))
UP = cross(FWD, RIGHT)


def view(p, yaw):
    """A point of the car turned by yaw (degrees, nose to the right), seen
    from the camera: screen x, y (up) and depth"""
    a = math.radians(yaw)
    x, y, z = p
    z -= 1.5
    x, z = x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)
    z += 1.5
    d = sub((x, y, z), EYE)
    cx, cy, cz = dot(d, RIGHT), dot(d, UP), dot(d, FWD)
    return 2.6 * cx / cz, 2.6 * cy / cz, cz


def shade(face, yaw, paint):
    """The paint's shade for a face: light from above, dark at the sides"""
    a = math.radians(yaw)
    p = [(x * math.cos(a) + z * math.sin(a), y, -x * math.sin(a) + z * math.cos(a)) for x, y, z in face[:3]]
    n = norm(cross(sub(p[1], p[0]), sub(p[2], p[0])))
    if dot(n, sub(TARGET, EYE)) > 0:
        n = tuple(-c for c in n)
    up, side = abs(n[1]), abs(n[0])
    if up > 0.55:
        return paint[0]
    if side > 0.6:
        return paint[-1]
    return paint[1 if len(paint) > 2 else 0]


def draw(model, yaw, paint, scale, lit=False):
    """The car at yaw, scale pixels a unit (four times the image), as a
    grey image of colour numbers: every face where it is nearest, the
    pieces on the rear panel just in front of it, the paint's panels edged
    in its darkest shade"""
    faces, decals = model
    shapes = []
    for face, mat in faces:
        col = shade(face, yaw, paint) if mat == PAINT else mat
        shapes.append(([view(p, yaw) for p in face], col, mat == PAINT))
    for face, mat in decals:
        col = LIT if lit and mat in (RED, DARK_RED) else mat
        pts = [view(p, yaw) for p in face]
        shapes.append(([(x, y, z - 0.02 - 0.001 * len(shapes)) for x, y, z in pts], col, False))
    xs = [x for pts, _, _ in shapes for x, _, _ in pts]
    ys = [y for pts, _, _ in shapes for _, y, _ in pts]
    x0, y0 = min(xs), min(ys)
    w = int((max(xs) - x0) * scale) + 4
    h = int((max(ys) - y0) * scale) + 4
    depth = array('f', [1e30]) * (w * h)
    colour = bytearray([CLEAR]) * (w * h)
    ident = array('i', [-1]) * (w * h)
    for k, (pts, col, edged) in enumerate(shapes):
        sp = [((x - x0) * scale + 2, h - 2 - (y - y0) * scale, z) for x, y, z in pts]
        mark = k if edged else -2 - k
        for i in range(1, len(sp) - 1):
            triangle(sp[0], sp[i], sp[i + 1], w, h, depth, colour, ident, col, mark)
    # panel edges: where a painted face meets another face, two pixels wide
    edge = bytearray(w * h)
    for y in range(h):
        row = y * w
        for x in range(w):
            k = ident[row + x]
            if k < 0:
                continue
            for n in (row + x - 1 if x else -1, row + x + 1 if x < w - 1 else -1,
                      row + x - w if y else -1, row + x + w if y < h - 1 else -1):
                if n >= 0 and ident[n] != k and ident[n] != -1:
                    edge[row + x] = 1
                    break
    for i in range(w * h):
        if edge[i] or (i % w and edge[i - 1]) or (i >= w and edge[i - w]):
            if ident[i] >= 0:
                colour[i] = paint[-1]
    return Image.frombytes('L', (w, h), bytes(colour))


def triangle(a, b, c, w, h, depth, colour, ident, col, mark):
    """A triangle (screen x, y, depth) into the buffers where it is nearest"""
    a, b, c = sorted((a, b, c), key=lambda p: p[1])
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = a, b, c
    if cy - ay < 1e-9:
        return
    for y in range(max(0, int(ay + 0.5)), min(h, int(cy + 0.5))):
        py = y + 0.5
        t = (py - ay) / (cy - ay)
        xl, zl = ax + (cx - ax) * t, az + (cz - az) * t
        if py < by:
            if by - ay < 1e-9:
                continue
            u = (py - ay) / (by - ay)
            xr, zr = ax + (bx - ax) * u, az + (bz - az) * u
        else:
            if cy - by < 1e-9:
                continue
            u = (py - by) / (cy - by)
            xr, zr = bx + (cx - bx) * u, bz + (cz - bz) * u
        if xr < xl:
            xl, xr, zl, zr = xr, xl, zr, zl
        x1, x2 = max(0, int(xl + 0.5)), min(w, int(xr + 0.5))
        if x1 >= x2:
            continue
        dz = (zr - zl) / (xr - xl) if xr - xl > 1e-9 else 0
        row = y * w
        for x in range(x1, x2):
            z = zl + (x + 0.5 - xl) * dz
            i = row + x
            if z < depth[i]:
                depth[i] = z
                colour[i] = col
                ident[i] = mark


def reduce(img, w, h):
    """Four by four pixels into one, at the bottom centre of a w x h image:
    the colour most of them have (lights and the plate count double), clear
    if most are"""
    big = Image.new('L', (w * 4, h * 4), CLEAR)
    big.paste(img, ((w * 4 - img.width) // 2, h * 4 - img.height))
    px = big.load()
    out = bytearray()
    for y in range(h):
        for x in range(w):
            count = {}
            for dy in range(4):
                for dx in range(4):
                    v = px[x * 4 + dx, y * 4 + dy]
                    k = 2 if v in (RED, DARK_RED, LIGHT_GREY, LIT, LIGHT_RED) else 1
                    count[v] = count.get(v, 0) + k
            clear = count.pop(CLEAR, 0)
            out.append(CLEAR if clear > 8 or not count else max(count, key=count.get))
    return bytes(out)


MAX_YAW = 14.0


def yaw_of(angle):
    """Angle 0-8 (0: nose to the left, 4: straight on) as degrees"""
    return (angle - 4) * MAX_YAW / 4


def render(dims, car_table, player_paint, opp_paint):
    """The bank's 126 images in the sizes dims[i]; car_table: per size and
    angle the image (as the race picks them). Returns the images and, per
    angle of the largest size, the plate's centre and the lit brake lights
    (image, x, y from the car image's top left)"""
    angles = {}
    for k, i in enumerate(car_table):
        angles.setdefault(i, []).append((k // 9, k % 9))
    images = [None] * 126
    extras = []
    for model, faces, paint, base in (('player', wedge(), player_paint, 0), ('opp', coupe(), opp_paint, 63)):
        dark = paint[-1]
        # the scale of each size: its straight-on image's height
        straight = draw(faces, 0, paint, 100)
        for i in range(63):
            size = angles[i][0][0]
            a = sum(angle for s, angle in angles[i] if s == size) / len([1 for s, _ in angles[i] if s == size])
            w, h = dims[i]
            ref = dims[car_table[size * 9 + 4]]
            scale = 100 * min((ref[1] * 4 - 2) / straight.height, (ref[0] * 4 - 2) / straight.width)
            img = draw(faces, yaw_of(a), paint, scale)
            images[base + i] = (w, h, reduce(img, w, h))
            if model == 'player' and size == 0:
                lit = reduce(draw(faces, yaw_of(a), paint, scale, lit=True), w, h)
                extras.append(overlay(images[i], lit))
    return images, extras


def overlay(car, lit):
    """The plate's centre in the car image, and the brake lights lit: an
    image of them alone and where it goes"""
    w, h, px = car
    plate = [(i % w, i // w) for i, v in enumerate(px) if v == LIGHT_GREY]
    px_c = (sum(x for x, _ in plate) // len(plate), sum(y for _, y in plate) // len(plate)) if plate else (w // 2, h - 8)
    on = [(i % w, i // w) for i, v in enumerate(lit) if v == LIT]
    x0, x1 = min(x for x, _ in on), max(x for x, _ in on)
    y0, y1 = min(y for _, y in on), max(y for _, y in on)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    img = bytes(LIGHT_RED if lit[(y0 + y) * w + x0 + x] == LIT else CLEAR for y in range(bh) for x in range(bw))
    return px_c, (bw, bh, img), (x0, y0)
