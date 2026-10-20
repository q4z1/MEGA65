#!/usr/bin/env python3
"""Renders the game's screens - title, menus, the car's pages - at build
time, for the MEGA65's 640 x 400 mode with 16-colour characters
(src/pages.c).

    mkpages.py GENDIR

The screen is 40 x 50 characters of 16 x 8 pixels, four bits a pixel.
Pixel 0 is the background (one colour for the whole screen), 1-15 come
from the character's palette bank (colour RAM). Banks 0-11 are the page's,
found here for each page; banks 12-15 are ramps from the background to a
text colour, for the text the game puts in at run time (pages.h).

Drawings come from art/NAME.png where there is one (our own artwork, a
transparent ground), else from tools/art.py.

Writes into GENDIR:
    pages/pNAME.bin  a page (on the disk as PNAME): the palette (16 banks of 16
                  colours, R G B), the number of characters (2 bytes), then,
                  each run-length coded on its own as
                  tools/mksprites.py does it: screen RAM (2 bytes a
                  character), colour RAM (2 bytes a character) - each
                  as all the low bytes, then all the high ones - and the
                  characters (64 bytes each)
    pages/glyphs.bin the text font (on the disk as GLYPHS): 8 x 16 pixels a
                  glyph (the ramp's levels), run-length coded
    pages_gen.h/.c the glyphs' order, the pages' character base and limits
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mksprites import rle  # noqa: E402
import art  # noqa: E402

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'toolchain', 'fonts')

W, H = 640, 400
COLS, ROWS = 40, 50
CW, CH = 16, 8

# Memory (src/mem.h): the characters from $40000 (character $1000 on); the
# text the game puts in gets characters of its own behind the page's
# (pages.c), 2 x PAGE_COLS per text row
CHAR_BASE = 0x40000 // 64
PAGE_CHARS = 2000

BG = (16, 18, 24)
WHITE = (245, 245, 245)
AMBER = (255, 170, 40)
GREY = (160, 166, 176)
RED = (214, 32, 38)
RAMPS = {12: WHITE, 13: AMBER, 14: GREY, 15: RED}
PAGE_BANKS = 12

GLYPH_SET = ' 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.,:;/-+\'!?()#%&*>'


def font(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    if weight is not None:
        f.set_variation_by_axes([weight])
    return f


def ramp(fg):
    return [tuple(round(b + (f - b) * k / 15) for b, f in zip(BG, fg)) for k in range(16)]


# ---------------------------------------------------------------- converting

def cells(img):
    px = img.load()
    for r in range(ROWS):
        for c in range(COLS):
            yield r, c, [px[c * CW + x, r * CH + y] for y in range(CH) for x in range(CW)]


def dist(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def pack(img, art):
    """Every cell's colours (but the background) into banks of 15. Cells
    without the drawings' colours (`art`) exactly, as few banks as they
    need; the drawings' cells grouped into the banks left (k-means: a bank
    has the 15 colours most used in its cells, a cell the bank it differs
    least from). Returns the banks, each cell's bank and its colour lookup."""
    px = img.load()
    counts = {}
    for r in range(ROWS):
        for c in range(COLS):
            count = {}
            for y in range(CH):
                for x in range(CW):
                    v = px[c * CW + x, r * CH + y]
                    if v != BG:
                        count[v] = count.get(v, 0) + 1
            counts[r, c] = count
    def nearest(bank, v):
        return min(bank, key=lambda k: dist(k, v))
    plain = [k for k in counts if not art & counts[k].keys()]
    drawn = [k for k in counts if art & counts[k].keys()]
    banks, where, remap = [], {}, {k: {} for k in counts}
    for key in plain:
        if len(counts[key]) > 15:
            # the rarest colours become the nearest of the 15 most used
            keep = sorted(counts[key], key=lambda v: -counts[key][v])[:15]
            for v in list(counts[key]):
                if v not in keep:
                    k = nearest(keep, v)
                    remap[key][v] = k
                    counts[key][k] += counts[key].pop(v)
    # text in one colour: its ramp's bank
    ramps = {bank: set(ramp(fg)[1:]) for bank, fg in RAMPS.items()}
    for key in list(plain):
        for bank, cols in ramps.items():
            if counts[key] and set(counts[key]) <= cols:
                where[key] = bank
                plain.remove(key)
                break
    for key in sorted(plain, key=lambda k: len(counts[k])):
        cs = set(counts[key])
        best = None
        for i, b in enumerate(banks):
            u = len(b | cs)
            if u <= 15 and (best is None or u < best[0]):
                best = (u, i)
        if best is not None:
            banks[best[1]] |= cs
            where[key] = best[1]
        elif len(banks) < PAGE_BANKS - (1 if drawn else 0):
            banks.append(cs)
            where[key] = len(banks) - 1
        else:
            # no room: the bank with most of its colours, the rest nearest
            i = max(range(len(banks)), key=lambda i: len(banks[i] & cs))
            for v in cs - banks[i]:
                remap[key][v] = nearest(banks[i], v)
            for v, m in list(remap[key].items()):
                if m not in banks[i]:
                    remap[key][v] = nearest(banks[i], m)
            where[key] = i
            print(f'page: cell {key} in bank {i} with nearest colours', file=sys.stderr)
    if drawn:
        n = PAGE_BANKS - len(banks)
        if n < 1:
            sys.exit('page: no bank left for the drawings')

        def error(key, pal):
            return sum(cnt * min(dist(v, p) for p in pal) for v, cnt in counts[key].items())
        # seeds: cells spread over the drawings' colours, by brightness
        order = sorted(drawn, key=lambda k: sum(sum(v) * cnt for v, cnt in counts[k].items()) /
                       max(1, sum(counts[k].values())))
        pals = []
        for i in range(n):
            key = order[(2 * i + 1) * len(order) // (2 * n)]
            pals.append(sorted(counts[key], key=lambda v: -counts[key][v])[:15])
        for _ in range(8):
            member = {key: min(range(n), key=lambda i: error(key, pals[i])) for key in drawn}
            for i in range(n):
                hist = {}
                for key, m in member.items():
                    if m == i:
                        for v, cnt in counts[key].items():
                            hist[v] = hist.get(v, 0) + cnt
                if hist:
                    pals[i] = sorted(hist, key=lambda v: -hist[v])[:15]
        base = len(banks)
        banks += [set(p) for p in pals]
        for key in drawn:
            i = member[key]
            where[key] = base + i
            for v in counts[key]:
                if v not in banks[base + i]:
                    remap[key][v] = nearest(banks[base + i], v)

    def cell_colour(r, c, x, y):
        v = px[x, y]
        return remap[r, c].get(v, v)
    return banks, where, cell_colour


def convert(img, art=frozenset()):
    """The page as palette banks, per cell a bank and 128 pixel indices"""
    img = img.convert('RGB')
    banks, where, colour = pack(img, set(art))
    order = [sorted(b) for b in banks] + [[]] * (16 - len(banks))
    palette = [[BG] * 16 for _ in range(16)]
    for i, b in enumerate(order):
        for k, v in enumerate(b):
            palette[i][1 + k] = v
    for bank, fg in RAMPS.items():
        palette[bank] = ramp(fg)
        order[bank] = ramp(fg)[1:]
    out = {}
    for (r, c), bank in where.items():
        idx = {v: 1 + k for k, v in enumerate(order[bank])}
        out[r, c] = (bank, [idx.get(colour(r, c, c * CW + x, r * CH + y), 0) for y in range(CH) for x in range(CW)])
    return palette, out


def char_bytes(pixels):
    """128 pixel indices as a 16-colour character: left pixel low nibble"""
    return bytes(pixels[i] | pixels[i + 1] << 4 for i in range(0, 128, 2))


def page_file(img):
    palette, cellmap = convert(img, ART)
    chars, ids = [], {}
    screen, colour = bytearray(), bytearray()
    for r in range(ROWS):
        for c in range(COLS):
            bank, pixels = cellmap[r, c]
            data = char_bytes(pixels)
            if data not in ids:
                ids[data] = len(chars)
                chars.append(data)
            ch = CHAR_BASE + ids[data]
            screen += bytes([ch & 0xFF, ch >> 8])
            colour += bytes([0x08, bank << 4 | 0x0F])  # 16 colours, the bank
    if len(chars) > PAGE_CHARS:
        sys.exit(f'page: {len(chars)} characters, at most {PAGE_CHARS}')
    pal = bytes(v for bank in palette for col in bank for v in col)
    count = bytes([len(chars) & 0xFF, len(chars) >> 8])
    # screen and colour RAM each as their low bytes, then their high ones:
    # that way they have runs to code
    return (pal + count + rle(bytes(screen[0::2] + screen[1::2])) + rle(bytes(colour[0::2] + colour[1::2])) +
            rle(b''.join(chars)), len(chars))


# ---------------------------------------------------------------- the font

def glyph_font():
    """The text font: per glyph 8 x 16 pixels, the ramp's levels, 4 bytes a
    row (left pixel low nibble) - two glyphs make a character's rows. Drawn
    large, scaled to caps 11 pixels high, the wide ones narrowed to 7."""
    big = 64
    f = font('Rajdhani-Bold.ttf', big)
    hb = f.getbbox('H')
    scale = 11 / (hb[3] - hb[1])
    out = bytearray()
    for ch in GLYPH_SET:
        im = Image.new('L', (big * 3, big * 3), 0)
        ImageDraw.Draw(im).text((big // 2, big // 2), ch, font=f, fill=255)
        g = Image.new('L', (8, 16), 0)
        bb = im.getbbox()
        if bb:
            w = bb[2] - bb[0]
            sx = min(scale, 7 / w)
            top = big // 2 + hb[1] - round(3 / scale)  # 3 pixels above the caps
            crop = im.crop((bb[0], top, bb[2], top + round(16 / scale)))
            nw = max(1, round(w * sx))
            g.paste(crop.resize((nw, 16), Image.LANCZOS), ((8 - nw) // 2, 0))
        px = [round(v * 15 / 255) for v in g.tobytes()]
        out += bytes(px[i] | px[i + 1] << 4 for i in range(0, 128, 2))
    return rle(bytes(out))


# ---------------------------------------------------------------- the pages

def text(img, xy, s, f, fg):
    """Text in fg on the flat background, its edges in the 16 levels of the
    ramp from the background to fg (shared by all text of that colour)"""
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).text(xy, s, font=f, fill=255)
    r = ramp(fg)
    px, mp = img.load(), mask.load()
    bb = mask.getbbox()
    if not bb:
        return
    for y in range(bb[1], bb[3]):
        for x in range(bb[0], bb[2]):
            k = round(mp[x, y] * 15 / 255)
            if k:
                px[x, y] = r[k]


def centred(img, y, s, f, fg):
    w = ImageDraw.Draw(img).textlength(s, font=f)
    text(img, ((W - w) / 2, y), s, f, fg)


ART = set()  # the colours of the page's drawings
ART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'art')


def drawing(name, width, fallback):
    """The drawing art/NAME.png (transparent ground), width pixels wide; if
    there is none, the one fallback(width) draws"""
    path = os.path.join(ART_DIR, name + '.png')
    if not os.path.exists(path):
        return fallback(width)
    im = Image.open(path).convert('RGBA')
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def paste_art(img, art_img, xy, colours=15):
    """A drawing onto the page in at most `colours` colours: the neutral
    ones (greys) and the others each get their share, so that a little
    chrome is not lost to much paint"""
    tile = Image.new('RGB', art_img.size, BG)
    tile.paste(art_img, (0, 0), art_img)
    px = tile.load()
    groups = {True: [], False: []}
    for y in range(tile.height):
        for x in range(tile.width):
            v = px[x, y]
            if dist(v, BG) < 3 * 10 ** 2:
                px[x, y] = BG
                continue
            groups[max(v) - min(v) < 40].append((x, y))
    n_grey = max(4, colours // 3) if groups[True] else 0
    for grey, budget in ((True, n_grey), (False, colours - n_grey)):
        where = groups[grey]
        if not where:
            continue
        strip = Image.new('RGB', (len(where), 1))
        strip.putdata([px[x, y] for x, y in where])
        q = strip.quantize(min(budget, 256), method=Image.Quantize.MEDIANCUT, kmeans=8,
                           dither=Image.Dither.NONE).convert('RGB')
        for i, (x, y) in enumerate(where):
            v = q.getpixel((i, 0))
            px[x, y] = v
    img.paste(tile, xy)
    ART.update(c for _, c in tile.getcolors(colours + 2) if c != BG)


def canvas():
    ART.clear()
    img = Image.new('RGB', (W, H), BG)
    return img, ImageDraw.Draw(img)


def page_title():
    img, d = canvas()
    for i in range(6):
        y0 = 230 + i * 10
        d.polygon([(0, y0), (W, y0 - 80), (W, y0 - 76), (0, y0 + 4)], fill=(90 + 20 * i, 16, 20))
    f = font('Exo2.ttf', 92, 900)
    centred(img, 36, 'LOTUS RUN', f, WHITE)
    tw = d.textlength('LOTUS RUN', font=f)
    d.rectangle([((W - tw) / 2, 146), ((W + tw) / 2, 150)], fill=RED)
    centred(img, 158, 'A  RACING  GAME  FOR  THE  MEGA65', font('Rajdhani-SemiBold.ttf', 22), GREY)
    centred(img, 352, 'PRESS  FIRE', font('Rajdhani-Bold.ttf', 26), AMBER)
    return img


def header(img, title, right=''):
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 40), (W, 43)], fill=RED)
    text(img, (16, 0), title, font('Exo2.ttf', 28, 800), WHITE)
    if right:
        f = font('Rajdhani-SemiBold.ttf', 20)
        text(img, (W - 16 - d.textlength(right, font=f), 9), right, f, GREY)


def footer(img, s):
    f = font('Rajdhani-SemiBold.ttf', 18)
    text(img, (W - 16 - ImageDraw.Draw(img).textlength(s, font=f), H - 26), s, f, GREY)


def facts(img, y, rows, label_w=150, step=24):
    fl = font('Rajdhani-Bold.ttf', 18)
    fv = font('TitilliumWeb-Regular.ttf', 17)
    for k, v in rows:
        text(img, (16, y), k, fl, AMBER)
        text(img, (16 + label_w, y - 2), v, fv, WHITE)
        y += step


CAR = 'LOTUS ESPRIT TURBO SE'


def page_spec1():
    img, d = canvas()
    header(img, 'SPECIFICATION', CAR + '   1 / 4')
    car = drawing('side-view', 470, art.esprit_side)
    paste_art(img, car, ((W - car.width) // 2, 52), 28)
    facts(img, 192, [
        ('ENGINE', '2174 cc, four cylinders in line, mid-mounted, rear-wheel drive'),
        ('VALVE GEAR', 'Twin overhead camshafts, four valves per cylinder'),
        ('FUEL & IGNITION', 'Multi-point injection, Garrett T03 turbocharger, intercooler'),
        ('POWER', '264 bhp'),
        ('TORQUE', '260 lb ft at 3900 rpm'),
        ('TRANSMISSION', 'Five-speed manual'),
        ('BRAKES', 'Ventilated discs 10.2 in front, discs 10.8 in rear'),
        ('TYRES', 'Goodyear Eagle, 215/50 ZR15 front, 245/50 ZR16 rear'),
    ], step=22)
    footer(img, 'FIRE: NEXT PAGE')
    return img


# The pages around the races: what is fixed drawn here, what changes the
# game puts in at run time (src/screens.c) - text rows are 8 pixels, a
# glyph 16 x 16; ROW(r) is where text of row r starts
def ROW(r):
    return r * CH


def label(img, row, s, x=16, fg=AMBER):
    text(img, (x, ROW(row) - 3), s, font('Rajdhani-Bold.ttf', 20), fg)


def page_level():
    img, _ = canvas()
    header(img, 'NEW SEASON', 'CHOOSE THE LEVEL')
    for row, name, info in ((12, 'EASY', 'seven races'), (18, 'MEDIUM', 'ten races'), (24, 'HARD', 'fifteen races')):
        text(img, (64, ROW(row) - 6), name, font('Exo2.ttf', 26, 800), WHITE)
        text(img, (240, ROW(row) - 1), info, font('TitilliumWeb-Regular.ttf', 18), GREY)
    centred(img, ROW(32), 'The first ten of each race score points; finish outside them', font('TitilliumWeb-Regular.ttf', 17), GREY)
    centred(img, ROW(35), 'and the season is over.', font('TitilliumWeb-Regular.ttf', 17), GREY)
    footer(img, 'UP / DOWN: CHOOSE    FIRE: START')
    return img


def page_controls():
    img, _ = canvas()
    header(img, 'CONTROLS', 'JOYSTICK IN PORT 2 OR KEYS')
    label(img, 10, 'GEARS')
    label(img, 15, 'ACCELERATE')
    label(img, 20, 'RADIO')
    label(img, 30, 'IN THE RACE', fg=GREY)
    footer(img, 'UP / DOWN: CHOOSE    LEFT / RIGHT: CHANGE    FIRE: GO ON')
    return img


def page_course():
    img, _ = canvas()
    header(img, 'NEXT RACE')
    for row, s in ((16, 'LOCATION'), (20, 'LAPS'), (24, 'THE TRACK'), (30, 'HAZARDS'), (36, 'COURSE RECORD')):
        label(img, row, s)
    footer(img, 'FIRE: RACE')
    return img


def page_result():
    img, _ = canvas()
    header(img, 'RACE RESULT')
    for x, s in ((16, 'PLACE'), (96, 'DRIVER'), (432, 'TIME'), (544, 'POINTS')):
        label(img, 7, s, x, GREY)
    footer(img, 'FIRE: GO ON')
    return img


def page_standing():
    img, _ = canvas()
    header(img, 'CHAMPIONSHIP')
    for x, s in ((16, 'PLACE'), (96, 'DRIVER'), (544, 'POINTS')):
        label(img, 7, s, x, GREY)
    footer(img, 'FIRE: GO ON')
    return img


def page_season():
    img, _ = canvas()
    header(img, 'SEASON OVER')
    footer(img, 'FIRE: GO ON')
    return img


# page_spec1: not shown yet, so not on the disk
PAGES = {'TITLE': page_title, 'LEVEL': page_level, 'CONTROLS': page_controls,
         'COURSE': page_course, 'RESULT': page_result, 'STANDING': page_standing, 'SEASON': page_season}


def main():
    gen = sys.argv[1]
    disk = os.path.join(gen, 'pages')
    os.makedirs(disk, exist_ok=True)
    with open(os.path.join(disk, 'glyphs.bin'), 'wb') as f:
        f.write(glyph_font())
    for name, fn in PAGES.items():
        data, n = page_file(fn())
        with open(os.path.join(disk, f'p{name.lower()}.bin'), 'wb') as f:
            f.write(data)
    with open(os.path.join(gen, 'pages_gen.h'), 'w') as f:
        f.write('// Generated by tools/mkpages.py - do not edit\n#pragma once\n#include <stdint.h>\n'
                f'#define PAGE_COLS {COLS}\n#define PAGE_ROWS {ROWS}\n'
                f'#define PAGE_CHAR_BASE 0x{CHAR_BASE:04X}  // the pages\' first character\n'
                f'#define PAGE_CHAR_END 0x{CHAR_BASE + PAGE_CHARS:04X}  // behind the last\n'
                f'#define GLYPHS {len(GLYPH_SET)}  // of 8 x 16 pixels, 64 bytes each\n'
                '// The text banks (ramps from the background to a colour)\n'
                '#define TEXT_WHITE 12\n#define TEXT_AMBER 13\n#define TEXT_GREY 14\n#define TEXT_RED 15\n'
                '// The glyph of a character (its index), 0 (space) for others\n'
                'uint8_t glyph_of(char c);\n')
    with open(os.path.join(gen, 'pages_gen.c'), 'w') as f:
        f.write('// Generated by tools/mkpages.py - do not edit\n#include "pages_gen.h"\n\n'
                f'static const char glyph_set[] = "{GLYPH_SET.replace(chr(92), chr(92) * 2)}";\n\n'
                'uint8_t glyph_of(char c) {\n'
                '    if (c >= \'a\' && c <= \'z\')\n        c -= 32;\n'
                f'    for (uint8_t i = 0; i < {len(GLYPH_SET)}; i++)\n'
                '        if (glyph_set[i] == c)\n            return i;\n'
                '    return 0;\n}\n')


if __name__ == '__main__':
    main()
