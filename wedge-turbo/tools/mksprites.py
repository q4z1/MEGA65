#!/usr/bin/env python3
"""The race's pictures as Wedge Turbo loads them: the scenery, cars and
backdrops drawn at build time (tools/mkscenery.py, mkcars.py,
mkbackdrops.py) in the sizes tools/gamedata.py gives, the messages
(mkhud.py), the panel (mkpanel.py) and the lap bar.

    mksprites.py GENDIR

Each bank becomes a file the game loads into attic RAM (banks.c), images
one byte per pixel, row after row: the colour, or SPR_CLEAR where the
picture behind shows.

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
    carhi.bin     the player's car near for the hardware sprites (on the
                  disk as CARHI, tools/mkcars.py hardware()): per angle
                  0-8, then again with the brake lights lit, the eight
                  sprites' data, packed as the banks' pixels
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
import mkhud  # noqa: E402
import mkpanel  # noqa: E402
import hand  # noqa: E402
import gamedata  # noqa: E402
import mkscenery  # noqa: E402

SPR_CLEAR = 0xFF
SPR_CARS = 0x40
SPR_HUD = 0x41
CAR_PAINT = 40
OPP_PAINT = 48     # the opponents' paints: colours OPP_PAINT + 2k (light), + 2k + 1 (dark)
OPP_MID = 116      # and OPP_MID + k (middle), after the road's mixed colours
OPP_COLOURS = 6
SPR_OPP = 0x42     # banks SPR_OPP .. SPR_OPP + 4: the opponents in colourings 1-5

# the snowy kinds: shaped as the green ones (their sizes, their drawing),
# in colours of their own
SAME_SHAPE = {0x92: 0x8F, 0x93: 0x90, 0x88: 0x87, 0xA6: 0xA5, 0xA8: 0xA7}
# the scenery's own colours (each type's 8-11 that its drawing uses) from
# this colour on, set for the race (main.c)
OBJ_COLOUR = 128
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
# rows, as tall as they get. tab_gate: where the banner sits, from size 7
# on (its bottom above the posts', how far in, the writing above it)

GATE_TYPE = 0x82
GATE_NEAR = 35


def scaled(im, f):
    """An image scaled by f (pixels repeated); at most 255 wide, narrowed
    to that"""
    w, h, px = im
    fx = min(f, 255 / w)
    nw, nh = max(1, round(w * fx)), max(1, round(h * f))
    return nw, nh, bytes(px[min(h - 1, int(y / f)) * w + min(w - 1, int(x / fx))]
                         for y in range(nh) for x in range(nw))


def gate_near(ims):
    """The gate's bank with the near sizes added; and per near size the
    banner's place (rise, inset, writing's rise), as tab_gate has it"""
    scale, size_of = gamedata.SCALE, gamedata.OBJECT_SIZE
    per = {}
    for s, v in zip(size_of, scale):
        if s >= 0:
            per.setdefault(s, []).append(v)
    factor = {s: sum(v) / len(v) / (sum(per[7]) / len(per[7])) for s, v in per.items()}
    table = gamedata.PROGRAM['tab_gate']
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


def race_palette(obj_colours, car_paint, opp_paints):
    """The race's colours as the sprites use them: number -> 12-bit colour"""
    pal = {0: 0x000}
    pal.update({1 + i: c for i, c in enumerate(gamedata.VIEW_COLOURS)})
    pal.update(mkpanel.COLOURS)
    pal.update({OBJ_COLOUR + i: c for i, c in enumerate(obj_colours)})
    pal.update({CAR_PAINT + i: c for i, c in enumerate(car_paint)})
    for k, (light, mid, dark) in enumerate(opp_paints):
        pal.update({OPP_PAINT + 2 * k: light, OPP_PAINT + 2 * k + 1: dark, OPP_MID + k: mid})
    return pal


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    gen = sys.argv[1]
    os.makedirs(gen, exist_ok=True)

    def sizes(t):
        """The sizes of type t's images, as images without pixels"""
        return [(w, h, b'') for w, h in gamedata.SCENERY_SIZES[t]]

    # the scenery: our own drawings (tools/mkscenery.py), in the sizes the
    # game has
    banks = {}
    drawn, drawn_dims = mkscenery.drawn_signs(), {}
    for t in range(0x80, 0xAC):
        shape = SAME_SHAPE.get(t, t)
        if shape in gamedata.SCENERY_SIZES:
            ims = sizes(shape)
        elif t in mkscenery.NEW_TYPES:  # a kind of our own, sized as the boards
            boards = sizes(0x96)
            banks[t - 0x80] = mkscenery.new_bank(t, [w / boards[0][0] for w, _, _ in boards])
            continue
        else:
            continue
        if t in drawn and t not in SAME_SHAPE and t != GATE_TYPE:  # its colours after all the others'
            drawn_dims[t] = [(w, h) for w, h, _ in ims]
            continue
        banks[t - 0x80] = mkscenery.gate(ims) if t == GATE_TYPE else mkscenery.bank(shape, ims)
    # each type's colours 8-11 that it uses become colours of its own
    type_colours = list(gamedata.OBJECT_COLOURS)
    for t, slots in mkscenery.COLOURS.items():  # the colours our drawings add
        for slot, rgb in slots.items():
            type_colours[(t - 0x80) * 4 + slot - 8] = rgb
    obj_colours = []
    for b, ims in banks.items():
        lut = bytearray(range(256))
        for k in range(4):
            if any(8 + k in px for _, _, px in ims):
                lut[8 + k] = OBJ_COLOUR + len(obj_colours)
                obj_colours.append(type_colours[b * 4 + k])
        banks[b] = [(w, h, px.translate(lut)) for w, h, px in ims]
    # the signs drawn elsewhere (art/signs): colours shared by them all, as
    # many as are left
    first = OBJ_COLOUR + len(obj_colours)
    drawn_banks, drawn_colours = mkscenery.sign_banks(drawn_dims, [0] + gamedata.VIEW_COLOURS, first,
                                                      SPR_CLEAR - first)
    for t, ims in drawn_banks.items():
        banks[t - 0x80] = ims
    obj_colours += drawn_colours
    assert OBJ_COLOUR + len(obj_colours) <= SPR_CLEAR
    banks[GATE_TYPE - 0x80], gate_places = gate_near(banks[GATE_TYPE - 0x80])
    # the cars: our own drawings (tools/mkcars.py), as many images and as
    # large as the game's, picked as it picks them (its table of images
    # per size and angle); the brake lights lit go behind the overlays
    car_table = gamedata.PROGRAM['tab_car_image']
    banks[SPR_CARS], marks, car_paint = mkcars.render(gamedata.CAR_SIZES, car_table,
                                                      (CAR_PAINT, CAR_PAINT + 1, CAR_PAINT + 2),
                                                      (OPP_PAINT, OPP_MID, OPP_PAINT + 1))
    opp_paints = mkcars.opponent_paints(car_paint)
    assert len(opp_paints) == OPP_COLOURS
    # pictures edited by hand instead (tools/hand.py, tools/sheets.py): in
    # the race's colours
    palette = race_palette(obj_colours, car_paint, opp_paints)
    for b in sorted(banks):
        if b < SPR_CARS:
            banks[b] = hand.sheet(f'scenery-{b + 0x80:02x}', banks[b], palette)
    cars = banks[SPR_CARS]
    banks[SPR_CARS] = (hand.sheet('cars-player', cars[:63], palette) +
                       hand.sheet('cars-opponent', cars[63:], palette))
    # the player's car near (the hardware sprites over its largest images);
    # edited by hand, the images beneath follow it (at half the size): the
    # sprites leave out the outer edges of the wider views, and where the
    # edit is clear the image beneath shows
    paint = (CAR_PAINT, CAR_PAINT + 1, CAR_PAINT + 2)
    near = mkcars.near_images([banks[SPR_CARS][car_table[a]] for a in range(9)], paint, palette)
    if hand.edited('car-near', False):
        for a in range(9):
            low = banks[SPR_CARS][car_table[a]]
            half = mkcars.halved(near[a])
            assert half[:2] == low[:2], f'car-near angle {a}: {near[a][:2]} is not twice {low[:2]}'
            banks[SPR_CARS][car_table[a]] = half
    # the brake lights lit: of the player's largest images, as they are now
    marks = [mkcars.overlay(banks[SPR_CARS][i]) for i in sorted(set(car_table[:9]))]
    banks[SPR_HUD] = hand.sheet('hud', mkhud.hud_images(), palette)
    car_brakes = len(banks[SPR_HUD])
    banks[SPR_HUD] += [brake for brake, _ in marks]
    for b, ims in banks.items():
        with open(os.path.join(gen, f'spr{b:02x}.bin'), 'wb') as f:
            f.write(bank_file(ims))

    hw_rows, hw_block, hw_data = mkcars.hardware(near, paint)
    with open(os.path.join(gen, 'carhi.bin'), 'wb') as f:
        f.write(pack(hw_data))
    with open(os.path.join(gen, 'lapbar.bin'), 'wb') as f:
        f.write(lapbar_file())
    with open(os.path.join(gen, 'panel.bin'), 'wb') as f:
        head, px = mkpanel.panel_file()
        f.write(head + pack(px))

    # the backdrops: our own (tools/mkbackdrops.py), each in the colours its
    # theme's courses start from (which of the three is light, middle,
    # dark)
    for n in range(BACKDROPS):
        cols = gamedata.BACKDROP_COLOURS[n]
        order = sorted(range(3), key=lambda i: -((cols[i] >> 8 & 15) * 3 + (cols[i] >> 4 & 15) * 6 + (cols[i] & 15)))
        px = mkbackdrops.backdrop(n, [BACK_COLOURS + i for i in order])
        back_palette = {**palette, **{BACK_COLOURS + i: c for i, c in enumerate(cols)}}
        [(_, _, px)] = hand.sheet(f'backdrop-{n}', [(BACK_W, BACK_H, px)], back_palette, clear=mkbackdrops.SKY)
        with open(os.path.join(gen, f'back{n}.bin'), 'wb') as f:
            f.write(pack(px))

    of_type = [t if t in banks else 0xFF for t in range(44)]
    largest = max(sum(w * h for w, h, _ in ims) for ims in banks.values())
    with open(os.path.join(gen, 'sprbanks.h'), 'w') as f:
        f.write('// Generated by tools/mksprites.py - do not edit\n#pragma once\n#include <stdint.h>\n'
                f'#define SPR_CLEAR 0x{SPR_CLEAR:02X}  // a pixel that is not drawn\n'
                f'#define SPR_CARS  0x{SPR_CARS:02X}  // the cars: 9 angles per size, the opponents from 63\n'
                f'#define SPR_HUD   0x{SPR_HUD:02X}  // messages, countdown, places, brake lights\n'
                f'#define CAR_PAINT {CAR_PAINT}  // the player\'s car\'s paint: colours CAR_PAINT + 0-2 (light, middle, dark)\n'
                f'#define OPP_PAINT {OPP_PAINT}  // opponents: colouring k in colours OPP_PAINT + 2k (light), + 1 (dark),\n'
                f'#define OPP_MID {OPP_MID}  // and OPP_MID + k (middle)\n'
                f'#define OPP_COLOURS {OPP_COLOURS}\n'
                f'#define SPR_OPP   0x{SPR_OPP:02X}  // the opponents in colourings 1-5: the cars\' images 63-125\n'
                f'#define SPR_BANKS 0x{SPR_OPP + OPP_COLOURS - 1:02X}\n'
                f'#define SPR_LARGEST {largest}  // pixels of the largest bank\n'
                f'#define BACK_W {BACK_W}  // a backdrop (BACKN): colours, row after row\n'
                f'#define BACK_H {BACK_H}\n'
                f'#define PANEL_W {mkpanel.PANEL_W}  // the panel (PANEL)\n'
                f'#define PANEL_H {mkpanel.PANEL_H}\n'
                f'#define PANEL_FIELDS {len(mkpanel.FIELDS)}\n'
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
                '// The player\'s car at its largest, per angle: where the lit brake\n'
                '// lights go (image CAR_BRAKES + angle), from the car image\'s top left\n'
                f'#define CAR_BRAKES {car_brakes}\n'
                'extern const int8_t car_brake[9][2];\n'
                '// The player\'s car\'s paint, light to dark (the drawing\'s)\n'
                'extern const uint16_t tab_panel_colours[6];  // colours 17-19 and 25-27: the panel\n'
                'extern const uint16_t car_paint[3];\n'
                '// The opponents\' paints in the palette\'s order: per colouring light\n'
                '// and dark (OPP_PAINT on), then the middle ones (OPP_MID on)\n'
                'extern const uint16_t opp_paint[3 * OPP_COLOURS];\n'
                '// The player\'s car near as the hardware sprites (CARHI): CARHI_SPRITES\n'
                '// of 16 colours side by side, each CARHI_ROWS high (400 to the screen),\n'
                '// 16 across (640), CARHI_BLOCK bytes; per angle 0-8, then lit, an image\n'
                '// of CARHI_IMAGE bytes; nybble 0 clear, 1-7 colours 0-6, 8-10 the paint\n'
                f'#define CARHI_SPRITES {mkcars.HW_SPRITES}\n'
                f'#define CARHI_W {mkcars.HW_W}\n'
                f'#define CARHI_ROWS {hw_rows}\n'
                f'#define CARHI_BLOCK {hw_block}\n'
                f'#define CARHI_IMAGE {mkcars.HW_SPRITES * hw_block}\n')
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
        f.write('const uint16_t tab_panel_colours[6] = {' + ', '.join(f'0x{c:03X}' for c in mkpanel.COLOURS.values()) + '};\n')
        f.write('const uint16_t car_paint[3] = {' + ', '.join(f'0x{c:03X}' for c in car_paint) + '};\n')
        order = [p[i] for p in opp_paints for i in (0, 2)] + [p[1] for p in opp_paints]
        f.write('const uint16_t opp_paint[3 * OPP_COLOURS] = {' + ', '.join(f'0x{c:03X}' for c in order) + '};\n')
        f.write('const int8_t car_brake[9][2] = {' + ', '.join(f'{{{x}, {y}}}' for _, (x, y) in marks) + '};\n')


if __name__ == '__main__':
    main()
