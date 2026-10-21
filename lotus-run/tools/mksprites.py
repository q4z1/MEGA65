#!/usr/bin/env python3
"""Converts the game's images - scenery objects, cars, race view overlays,
the backdrops - into what Lotus Run loads; the scenery, cars and backdrops
drawn anew (tools/mkscenery.py, mkcars.py, mkbackdrops.py) in the game's
sizes.

    mksprites.py ORIGDIR GENDIR

The data files keep the objects as Amiga blitter objects: per image width,
height, planes, plane size, then the planes and a mask (bit set: the image,
clear: the picture behind). Each bank becomes a file the game loads into
attic RAM (banks.c), images one byte per pixel, row after row: the colour
(0-15), or SPR_CLEAR where the picture behind shows.

A backdrop (files $60-$69) is three bitplanes of 320 x 96 pixels: three
strips of 320 x 32, side by side a panorama of 960 x 32. Its values 0-6 are
colours 4-7 and 12-14 - those three become BACK_COLOURS on - and 7 the sky
(colour 15).

Writes into GENDIR:
    sprNN.bin     bank NN (on the disk as SPRNN): u8 image count, per image
                  u8 width and u8 height, then all pixels, packed (pack():
                  runs of pixels as they are, repeated pixels, copies of
                  what came before)
    sprbanks.h/.c the banks: 00-2B the scenery objects $80-$AB,
                  SPR_CARS, SPR_HUD; the scenery's colours
    backN.bin     backdrop N (on the disk as BACKN): 960 x 32 colours, row
                  after row, packed as the banks' pixels
    lapbar.bin    the lap bar (on the disk as LAPBAR): overlay 23 as drawn
                  for 1-8 laps, then a box's row filled with each of 16
                  masks (16 pixels), packed as the banks' pixels
    panel.bin     the panel of the race view (on the disk as PANEL): u8
                  width, height, field count; per field u8 x, y, w, h and
                  state count; then packed as the banks' pixels:
                  the panel, then every field's states, w x h each
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkbackdrops  # noqa: E402
import mkcars  # noqa: E402
import mkscenery  # noqa: E402
import packers  # noqa: E402

SPR_CLEAR = 0xFF
SPR_CARS = 0x40
SPR_HUD = 0x41
CAR_PAINT = 40
OPP_PAINT = 48     # the opponents' paints: colours OPP_PAINT + 2k (light), + 2k + 1 (dark)
OPP_COLOURS = 6
SPR_OPP = 0x42     # banks SPR_OPP .. SPR_OPP + 4: the opponents in colourings 1-5

# the snowy kinds: shaped as the green ones (their sizes, their drawing),
# in colours of their own
SAME_SHAPE = {0x92: 0x8F, 0x93: 0x90, 0x88: 0x87, 0xA6: 0xA5, 0xA8: 0xA7}
# the scenery's own colours (each type's 8-11 that its drawing uses) from
# this colour on, set for the race (main.c)
OBJ_COLOUR = 128
# file $51 holds the banks of the types every course has, at these offsets
FILE51 = {0x80: 0x489E, 0x81: 0x34A2, 0x82: 0x5C9A, 0x83: 0x0000}
# file $50 holds the overlays of the race view (messages, countdown,
# places, brake lights) at this offset
FILE50_HUD = 0x1F02


def images(d, base=0):
    """The images of the bank at d[base:]: (width, height, pixels)"""
    count = struct.unpack_from('>I', d, base)[0] // 4
    for o in struct.unpack_from(f'>{count}I', d, base):
        o += base
        w, h, planes, plane_size = struct.unpack_from('>4H', d, o)
        bpr = plane_size // h
        if bpr * h != plane_size or bpr * 8 < w or not 0 < w < 256 or not 0 < h < 256:
            sys.exit(f'bank at {base:#x}: image at {o:#x} is not as expected')
        px = bytearray()
        for y in range(h):
            for x in range(w):
                def bit(p):
                    return d[o + 8 + p * plane_size + y * bpr + x // 8] >> (7 - x % 8) & 1
                if not bit(planes):
                    px.append(SPR_CLEAR)
                else:
                    px.append(sum(bit(k) << k for k in range(planes)))
        yield w, h, bytes(px)


def pack(d, chain=24):
    """Packs d as src/banks.c's file_unpack unpacks it, token by token:
    $00-$7F: the next 1-128 bytes as they are; $80-$BF: 2-65 times the next
    byte; $C0-$FF: 4-67 bytes from what is unpacked already, the next two
    bytes (low first) back - never overlapping what they make (one DMA
    job)."""
    n = len(d)
    out, lit = bytearray(), bytearray()
    heads = {}

    def note(p):
        if p + 3 <= n:
            heads.setdefault(d[p:p + 3], []).append(p)

    def flush():
        for k in range(0, len(lit), 128):
            part = lit[k:k + 128]
            out.append(len(part) - 1)
            out.extend(part)
        lit.clear()

    i = 0
    while i < n:
        run = 1
        while i + run < n and d[i + run] == d[i] and run < 65:
            run += 1
        best, at = 0, 0
        for p in reversed(heads.get(d[i:i + 3], [])[-chain:]):
            dist = i - p
            if dist > 0xFFFF:
                break
            most = min(67, dist, n - i)
            if most <= best:
                continue
            m = 0
            while m < most and d[p + m] == d[i + m]:
                m += 1
            if m > best:
                best, at = m, dist
        if run >= 3 and run >= best:
            flush()
            out += bytes([0x80 + run - 2, d[i]])
            step = run
        elif best >= 4:
            flush()
            out += bytes([0xC0 + best - 4, at & 0xFF, at >> 8])
            step = best
        else:
            lit.append(d[i])
            step = 1
        for p in range(i, i + step):
            note(p)
        i += step
    flush()
    return bytes(out)


BACKDROPS = 10
BACK_COLOURS = 20  # the backdrop's colours 12-14 (render.h: COL_BACKDROP); 15 is the sky
BACK_W, BACK_H = 960, 32


def backdrop(d):
    """The panorama's colours, row after row"""
    out = bytearray()
    for y in range(BACK_H):
        for x in range(BACK_W):
            strip, sx = divmod(x, 320)
            row = y + BACK_H * strip
            v = 0
            for p in range(3):
                v |= (d[p * 3840 + row * 40 + sx // 8] >> (7 - sx % 8) & 1) << p
            c = 4 + (v & 3) + ((v & 4) << 1)
            out.append(c if c < 12 or c == 15 else BACK_COLOURS + c - 12)
    return bytes(out)


# ---------------------------------------------------------------- the panel

# The panel at the right of the race view: hardware sprites whose data is
# the start of file $50 (at $36E1C when the game runs; addresses below are
# those): three 16-pixel columns of labels and values, three more for the
# bars beneath them. The values are written into the sprite data, one per
# picture; here every value they can show is drawn out.
P50 = 0x36E1C
PANEL_SPRITES = [0x36E1C, 0x37108, 0x373F4, 0x376E0, 0x37724, 0x37768]
# their colours: sprites 0-2 colours 17-19, 4-6 colours 25-27 (the game's
# 21-23 and 29-31 are the same)
PANEL_COLOURS = [(17, 18, 19)] * 3 + [(25, 26, 27)] * 3
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 406, 46, 48, 92  # sprite positions: player 1's panel
COL0, COL1, COL2 = 0x36E20, 0x3710C, 0x373F8  # the columns' data (player 1)


def panel_render(m):
    """The panel's colours, PANEL_W x PANEL_H; the lower sprites first, so
    the higher ones cover them"""
    px = bytearray([SPR_CLEAR]) * (PANEL_W * PANEL_H)
    for k in reversed(range(len(PANEL_SPRITES))):
        a = PANEL_SPRITES[k]
        while True:
            c0, c1 = struct.unpack_from('>HH', m, a - P50)
            if c0 == 0 and c1 == 0:
                break
            vs = c0 >> 8 | (c1 & 4) << 6
            ve = c1 >> 8 | (c1 & 2) << 7
            hs = (c0 & 0xFF) << 1 | (c1 & 1)
            for i in range(ve - vs):
                da, db = struct.unpack_from('>HH', m, a - P50 + 4 + 4 * i)
                y = vs + i - PANEL_Y
                for b in range(16):
                    v = (da >> (15 - b) & 1) | (db >> (15 - b) & 1) << 1
                    x = hs + b - PANEL_X
                    if v and 0 <= x < PANEL_W and 0 <= y < PANEL_H:
                        px[y * PANEL_W + x] = PANEL_COLOURS[k][v - 1]
            a += 4 + 4 * (ve - vs)
    return px


def panel_digit(m, digit, at):
    g = 0x37B62 + 7 * digit - P50
    for i in range(7):
        m[at - P50 + 4 * i] = m[g + i]
        m[at - P50 + 4 * i + 2] = m[g + 7 + 0x3F + i]


def panel_gear(m, gear):
    g = 0x37A90 + 0x15 * gear - P50
    for k, at in enumerate((COL0 + 0x21, COL1 + 0x20, COL1 + 0x21)):
        for i in range(7):
            m[at - P50 + 4 * i] = m[g + k + 3 * i]
            m[at - P50 + 4 * i + 2] = m[g + k + 0x69 + 3 * i]


def panel_place(m, place):
    g = 0x37BEE + 0x6E * (place - 1) - P50
    a0, a1, a2 = (c + 0x118 - P50 for c in (COL0, COL1, COL2))
    for i in range(22):
        for at, src in ((a0, 0), (a0 + 1, 1), (a1, 2), (a1 + 1, 3), (a2, 4)):
            m[at + 4 * i] = m[g + src + 5 * i]
            m[at + 4 * i + 2] = m[g + 0x898 + src + 5 * i]


def panel_bar(m, value, row, pattern):
    """Bar sprites 4-6, three rows from data offset row: rpm 4, fuel $14"""
    g = 0x377AC + 5 * value + pattern - P50
    cols = [0x376E0, 0x376E0 + 1, 0x37724, 0x37724 + 1, 0x37768]
    for k, base in enumerate(cols):
        at = base + row - P50
        for r in range(3):
            m[at + 4 * r] = m[g + k]
            m[at + 4 * r + 2] = m[g + k + 0x172]


# The values: name, number of states, how a state is written
PANEL_FIELDS = [
    ('hundreds', 10, lambda m, v: panel_digit(m, v, COL0 + 0x61)),
    ('tens', 10, lambda m, v: panel_digit(m, v, COL1 + 0x60)),
    ('units', 10, lambda m, v: panel_digit(m, v, COL1 + 0x61)),
    ('gear', 5, panel_gear),
    ('rpm', 37, lambda m, v: panel_bar(m, v, 4, 0)),
    ('fuel', 37, lambda m, v: panel_bar(m, v, 0x14, 0xB9)),
    ('place', 20, lambda m, v: panel_place(m, v + 1)),
]


def panel_file(d50):
    m = bytearray(d50[:0x1F02])
    base = panel_render(m)
    head = bytearray([PANEL_W, PANEL_H, len(PANEL_FIELDS)])
    states = []
    for name, n, write in PANEL_FIELDS:
        pics = []
        for v in range(n):
            mm = bytearray(m)
            write(mm, v)
            pics.append(panel_render(mm))
        changed = [i for i in range(PANEL_W * PANEL_H) if any(p[i] != base[i] for p in pics)]
        x0 = min(i % PANEL_W for i in changed)
        x1 = max(i % PANEL_W for i in changed) + 1
        y0 = min(i // PANEL_W for i in changed)
        y1 = max(i // PANEL_W for i in changed) + 1
        head += bytes([x0, y0, x1 - x0, y1 - y0, n])
        for p in pics:
            states += [p[y * PANEL_W + x] for y in range(y0, y1) for x in range(x0, x1)]
    return bytes(head) + pack(bytes(base) + bytes(states))


# ---------------------------------------------------------------- the lap bar

# Overlay 23 (194 x 9, three planes and a mask) is the lap bar at the top
# left; the game draws it at the start of a race - a box of 16 pixels per
# lap - and fills a lap's box as the car goes round (its mask, rows 2 and
# 3, one of 16 masks per box).
LAPBAR_W, LAPBAR_H, LAPBAR_LAPS = 194, 9, 8
LAP_MASKS = [0xC000, 0xC000, 0xE000, 0xF000, 0xF800, 0xFC00, 0xFE00, 0xFF00,
             0xFF80, 0xFFC0, 0xFFE0, 0xFFF0, 0xFFF8, 0xFFFC, 0xFFFE, 0xFFFF]


def lapbar_decode(m):
    bpr, plane = 26, 234
    out = bytearray()
    for y in range(LAPBAR_H):
        for x in range(LAPBAR_W):
            def bit(p):
                return m[p * plane + y * bpr + x // 8] >> (7 - x % 8) & 1
            out.append(sum(bit(k) << k for k in range(3)) if bit(3) else SPR_CLEAR)
    return out


def lapbar_drawn(laps):
    """The bar of a race of that many laps, as the game draws it"""
    m = bytearray(936)

    def put(off, word, w):
        struct.pack_into('>H', m, off + 2 * word, w)
    for w in range(laps):
        put(0x11E, w, 0x3FFF)
        put(0x138, w, 0x3FFF)
        put(0x2BE, w, 0x7FFF if w == 0 else 0xFFFF)
        put(0x2D8, w, 0xFFFF)
        put(0x2F2, w, 0xC000)
        put(0x30C, w, 0xC000)
        put(0x326, w, 0xFFFF)
        put(0x340, w, 0x7FFF if w == 0 else 0xFFFF)
    for off, v in ((0x2BE, 0x8000), (0x2D8, 0xC000), (0x2F2, 0xC000), (0x30C, 0xC000), (0x326, 0xC000),
                   (0x340, 0x8000)):
        put(off, laps, v)
    return m


def lapbar_file():
    out = bytearray()
    for laps in range(1, LAPBAR_LAPS + 1):
        out += lapbar_decode(lapbar_drawn(laps))
    # a lap's box filled with each mask: row 2 of the box (row 3 is the same)
    m = lapbar_drawn(1)
    for mask in LAP_MASKS:
        struct.pack_into('>H', m, 0x2F2, mask)
        struct.pack_into('>H', m, 0x30C, mask)
        px = lapbar_decode(m)
        if px[2 * LAPBAR_W:2 * LAPBAR_W + 16] != px[3 * LAPBAR_W:3 * LAPBAR_W + 16]:
            sys.exit('lap bar: rows 2 and 3 of a box differ')
        out += px[2 * LAPBAR_W:2 * LAPBAR_W + 16]
    return pack(bytes(out))


def repaint(cars):
    """The cars' paint into colours of their own: the player's car (images
    0-62: red 1-3) to CAR_PAINT + 0-2, the opponents (63-125: white 6, grey 5)
    to OPP_PAINT, OPP_PAINT + 1 - the game makes their other colourings from
    these (banks.c). Both are drawn alike, so image i and i + 63 tell paint
    from lights: where the opponent is red, a light, which stays red; where
    both have the same grey, the number plate and the like, which stay."""
    out = list(cars)
    for i in range(63):
        (w, h, own), (w2, h2, opp) = cars[i], cars[i + 63]
        if (w, h) != (w2, h2):
            sys.exit(f'cars: images {i} and {i + 63} differ in size')
        a, b = bytearray(own), bytearray(opp)
        for k in range(w * h):
            if own[k] in (1, 2, 3) and opp[k] in (5, 6):
                a[k] = CAR_PAINT + own[k] - 1
                b[k] = OPP_PAINT + (opp[k] == 5)
        out[i], out[i + 63] = (w, h, bytes(a)), (w, h, bytes(b))
    return out


# The gate over the road (type $82): posts in the 17 sizes, the banner and
# its writing only from size 7 on (images 17-26, 27-34) - nearer, the
# original's half-height view had them out of sight already. Here the view
# is taller: the banner and the writing for sizes 0-6 too (GATE_NEAR on),
# scaled from size 7's by the projection's scale, and the posts, cut at 96
# rows, as tall as they get. GATE_TABLE: where the banner sits, from size 7
# on (its bottom above the posts', how far in, the writing above it)
CAR_TABLE = 0xC21C00  # the game's images per car size and angle

GATE_TYPE = 0x82
GATE_NEAR = 35
GATE_TABLE = 0xC20B1E
CODE_BASE = 0xC18880
OBJECT_COLOURS = 0xC23484  # per object type colours 8-11 (0: as they are)
F59_SCALE, F59_OBJECT_SIZE = 0xD29C, 0xD39C


def scaled(im, f):
    """An image scaled by f (pixels repeated); at most 255 wide, narrowed
    to that"""
    w, h, px = im
    fx = min(f, 255 / w)
    nw, nh = max(1, round(w * fx)), max(1, round(h * f))
    return nw, nh, bytes(px[min(h - 1, int(y / f)) * w + min(w - 1, int(x / fx))]
                         for y in range(nh) for x in range(nw))


def gate_near(ims, orig, f59):
    """The gate's bank with the near sizes added; and per near size the
    banner's place (rise, inset, writing's rise), as GATE_TABLE has it"""
    scale = struct.unpack_from('>128H', f59, F59_SCALE)
    size_of = struct.unpack_from('>128h', f59, F59_OBJECT_SIZE)
    per = {}
    for s, v in zip(size_of, scale):
        if s >= 0:
            per.setdefault(s, []).append(v)
    factor = {s: sum(v) / len(v) / (sum(per[7]) / len(per[7])) for s, v in per.items()}
    code = open(os.path.join(orig, 'code.bin'), 'rb').read()
    table = struct.unpack_from('>28h', code, GATE_TABLE - CODE_BASE)
    ims = list(ims)
    post_h = ims[7][1]
    for s in range(5):
        w, h, px = ims[s]
        tall = round(post_h * factor[s])
        if tall > h:  # the post's top row repeated above
            ims[s] = (w, tall, px[:w] * (tall - h) + px)
    near = [scaled(ims[17], factor[s]) for s in range(7)] + [scaled(ims[27], factor[s]) for s in range(7)]
    places = [round(table[k] * factor[s]) for k in (0, 10, 20) for s in range(7)]
    return ims + near, places


def bank_file(ims):
    head = bytearray([len(ims)])
    for w, h, _ in ims:
        head += bytes([w, h])
    return bytes(head) + pack(b''.join(px for _, _, px in ims))


def main():
    orig, gen = sys.argv[1], sys.argv[2]
    os.makedirs(gen, exist_ok=True)

    def unpack(n):
        return packers.unpack_bytes(open(os.path.join(orig, f'{n:02X}.bin'), 'rb').read())

    # the scenery: our own drawings (tools/mkscenery.py), in the sizes the
    # game has
    code = open(os.path.join(orig, 'code.bin'), 'rb').read()
    banks = {}
    f51 = unpack(0x51)
    for t in range(0x80, 0xAC):
        shape = SAME_SHAPE.get(t, t)
        if shape in FILE51:
            ims = list(images(f51, FILE51[shape]))
        elif os.path.exists(os.path.join(orig, f'{shape:02X}.bin')):
            ims = list(images(unpack(shape)))
        else:
            continue
        banks[t - 0x80] = mkscenery.gate(ims) if t == GATE_TYPE else mkscenery.bank(shape, [(w, h) for w, h, _ in ims])
    # each type's colours 8-11 that it uses become colours of its own
    type_colours = struct.unpack_from('>176H', code, OBJECT_COLOURS - CODE_BASE)
    obj_colours = []
    for b, ims in banks.items():
        lut = bytearray(range(256))
        for k in range(4):
            if any(8 + k in px for _, _, px in ims):
                lut[8 + k] = OBJ_COLOUR + len(obj_colours)
                obj_colours.append(type_colours[b * 4 + k])
        banks[b] = [(w, h, px.translate(lut)) for w, h, px in ims]
    assert OBJ_COLOUR + len(obj_colours) <= 256
    banks[GATE_TYPE - 0x80], gate_places = gate_near(banks[GATE_TYPE - 0x80], orig, unpack(0x59))
    # the cars: our own models (tools/mkcars.py), as many images and as
    # large as the game's, picked as it picks them (its table of images
    # per size and angle); the brake lights lit go behind the overlays
    game_cars = list(images(unpack(0xC0)))
    car_table = list(code[CAR_TABLE - CODE_BASE:CAR_TABLE - CODE_BASE + 153])
    banks[SPR_CARS], marks = mkcars.render([(w, h) for w, h, _ in game_cars[:63]], car_table,
                                           (CAR_PAINT, CAR_PAINT + 1, CAR_PAINT + 2), (OPP_PAINT, OPP_PAINT + 1))
    banks[SPR_HUD] = list(images(unpack(0x50), FILE50_HUD))
    car_brakes = len(banks[SPR_HUD])
    banks[SPR_HUD] += [brake for _, brake, _ in marks]
    for b, ims in banks.items():
        with open(os.path.join(gen, f'spr{b:02x}.bin'), 'wb') as f:
            f.write(bank_file(ims))

    with open(os.path.join(gen, 'lapbar.bin'), 'wb') as f:
        f.write(lapbar_file())
    with open(os.path.join(gen, 'panel.bin'), 'wb') as f:
        f.write(panel_file(unpack(0x50)))

    # the backdrops: our own (tools/mkbackdrops.py), each in the colours its
    # theme's courses start from (the game's first course with it: which
    # of the three is light, middle, dark)
    for n in range(BACKDROPS):
        for t in range(32):
            header = open(os.path.join(orig, f'{t:02X}.bin'), 'rb').read()[2:164]
            if header[1] == n:
                break
        cols = struct.unpack_from('>3H', header, 2)
        order = sorted(range(3), key=lambda i: -((cols[i] >> 8 & 15) * 3 + (cols[i] >> 4 & 15) * 6 + (cols[i] & 15)))
        with open(os.path.join(gen, f'back{n}.bin'), 'wb') as f:
            f.write(pack(mkbackdrops.backdrop(n, [BACK_COLOURS + i for i in order])))

    of_type = [t if t in banks else 0xFF for t in range(44)]
    largest = max(sum(w * h for w, h, _ in ims) for ims in banks.values())
    with open(os.path.join(gen, 'sprbanks.h'), 'w') as f:
        f.write('// Generated by tools/mksprites.py - do not edit\n#pragma once\n#include <stdint.h>\n'
                f'#define SPR_CLEAR 0x{SPR_CLEAR:02X}  // a pixel that is not drawn\n'
                f'#define SPR_CARS  0x{SPR_CARS:02X}  // the cars: 9 angles per size, the opponents from 63\n'
                f'#define SPR_HUD   0x{SPR_HUD:02X}  // messages, countdown, places, brake lights\n'
                f'#define CAR_PAINT {CAR_PAINT}  // the player\'s car\'s paint: colours CAR_PAINT + 0-2 (light, middle, dark)\n'
                f'#define OPP_PAINT {OPP_PAINT}  // opponents: colouring k in colours OPP_PAINT + 2k (light), + 1 (dark)\n'
                f'#define OPP_COLOURS {OPP_COLOURS}\n'
                f'#define SPR_OPP   0x{SPR_OPP:02X}  // the opponents in colourings 1-5: the cars\' images 63-125\n'
                f'#define SPR_BANKS 0x{SPR_OPP + OPP_COLOURS - 1:02X}\n'
                f'#define SPR_LARGEST {largest}  // pixels of the largest bank\n'
                f'#define BACK_W {BACK_W}  // a backdrop (BACKN): colours, row after row\n'
                f'#define BACK_H {BACK_H}\n'
                f'#define PANEL_W {PANEL_W}  // the panel (PANEL)\n'
                f'#define PANEL_H {PANEL_H}\n'
                f'#define PANEL_FIELDS {len(PANEL_FIELDS)}\n'
                f'#define LAPBAR_W {LAPBAR_W}  // the lap bar (LAPBAR): overlay 23 for 1-LAPBAR_LAPS laps,\n'
                f'#define LAPBAR_H {LAPBAR_H}  // then a box\'s row for each of 16 masks\n'
                f'#define LAPBAR_LAPS {LAPBAR_LAPS}\n'
                '// The bank of scenery object type $80 + i ($FF: none, no course has it)\n'
                'extern const uint8_t spr_bank_of_type[44];\n'
                '// The scenery\'s colours: OBJ_COLOUR on, set for the race\n'
                f'#define OBJ_COLOUR {OBJ_COLOUR}\n'
                f'#define OBJ_COLOURS {len(obj_colours)}\n'
                'extern const uint16_t obj_colours[OBJ_COLOURS];\n'
                '// Per object type colours 8-11 to load as it comes near (0: leave it) -\n'
                '// none: each has colours of its own\n'
                'extern const uint16_t tab_object_colours[176];\n'
                '// The gate\'s banner for sizes 0-6: images GATE_NEAR + size, its writing\n'
                '// GATE_NEAR + 7 + size; gate_near: per size the banner\'s rise above the\n'
                '// posts\' bottom, then its inset, then the writing\'s rise above it\n'
                f'#define GATE_NEAR {GATE_NEAR}\n'
                'extern const uint8_t gate_near[21];\n'
                '// The player\'s car at its largest, per angle: where its number plate\'s\n'
                '// digit goes, and the lit brake lights (image CAR_BRAKES + angle), from\n'
                '// the car image\'s top left\n'
                f'#define CAR_BRAKES {car_brakes}\n'
                'extern const int8_t car_plate[9][2];\n'
                'extern const int8_t car_brake[9][2];\n')
    with open(os.path.join(gen, 'sprbanks.c'), 'w') as f:
        f.write('// Generated by tools/mksprites.py - do not edit\n#include "sprbanks.h"\n\n'
                'const uint8_t spr_bank_of_type[44] = {\n')
        for i in range(0, 44, 12):
            f.write('    ' + ', '.join(f'0x{b:02X}' for b in of_type[i:i + 12]) + ',\n')
        f.write('};\n')
        f.write('const uint16_t obj_colours[OBJ_COLOURS] = {\n')
        for i in range(0, len(obj_colours), 12):
            f.write('    ' + ', '.join(f'0x{v:03X}' for v in obj_colours[i:i + 12]) + ',\n')
        f.write('};\n')
        f.write('const uint16_t tab_object_colours[176] = {0};\n')
        f.write('const uint8_t gate_near[21] = {' + ', '.join(str(min(255, v)) for v in gate_places) + '};\n')
        f.write('const int8_t car_plate[9][2] = {' + ', '.join(f'{{{x}, {y}}}' for (x, y), _, _ in marks) + '};\n')
        f.write('const int8_t car_brake[9][2] = {' + ', '.join(f'{{{x}, {y}}}' for _, _, (x, y) in marks) + '};\n')


if __name__ == '__main__':
    main()
