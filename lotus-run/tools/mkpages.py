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

Writes into GENDIR:
    pages/pNAME.bin  a page (on the disk as PNAME): the palette (16 banks of 16
                  colours, R G B), the number of characters (2 bytes), then,
                  each run-length coded on its own as
                  tools/mksprites.py does it: screen RAM (2 bytes a
                  character), colour RAM (2 bytes a character), the
                  characters (64 bytes each)
    pages/glyphs.bin the text font (on the disk as GLYPHS): 2 characters per
                  glyph (16 x 16 pixels, the ramp's levels), run-length coded
    pages_gen.h/.c the glyphs' order, the pages' character base and limits
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mksprites import rle  # noqa: E402

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'toolchain', 'fonts')

W, H = 640, 400
COLS, ROWS = 40, 50
CW, CH = 16, 8

# Memory (src/mem.h): the characters from $40000 (character $1000 on), the
# text font's at the end of the 128K
CHAR_BASE = 0x40000 // 64
GLYPH_CHARS = 160
PAGE_CHARS = 2000 - GLYPH_CHARS
GLYPH_BASE = CHAR_BASE + PAGE_CHARS

BG = (16, 18, 24)
WHITE = (245, 245, 245)
AMBER = (255, 170, 40)
GREY = (160, 166, 176)
RED = (214, 32, 38)
RAMPS = {12: WHITE, 13: AMBER, 14: GREY, 15: RED}
PAGE_BANKS = 12

GLYPH_SET = ' 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.,:;/-+\'!?()#%&*'


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


def pack(img, colours=None):
    """Every cell's colours (but the background) into banks of 15; None if
    they do not fit"""
    if colours is None:
        q = img
        rgb = None
    else:
        q = img.quantize(colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pal = q.getpalette()[:3 * colours]
        rgb = [tuple(pal[3 * i:3 * i + 3]) for i in range(colours)]
    px = q.load()

    def colour(x, y):
        return px[x, y] if rgb is None else rgb[px[x, y]]
    sets = {}
    for r in range(ROWS):
        for c in range(COLS):
            sets[r, c] = {colour(c * CW + x, r * CH + y) for y in range(CH) for x in range(CW)} - {BG}
    banks, where = [], {}
    for key in sorted(sets, key=lambda k: -len(sets[k])):
        cs = sets[key]
        if len(cs) > 15:
            return None
        best = None
        for i, b in enumerate(banks):
            u = len(b | cs)
            if u <= 15 and (best is None or u < best[0]):
                best = (u, i)
        if best is None:
            if len(banks) == PAGE_BANKS:
                return None
            banks.append(set(cs))
            where[key] = len(banks) - 1
        else:
            banks[best[1]] |= cs
            where[key] = best[1]
    return banks, where, colour


def convert(img):
    """The page as palette banks, per cell a bank and 128 pixel indices"""
    img = img.convert('RGB')
    packed = pack(img)
    for colours in (180, 150, 120, 96, 72, 56, 40):
        if packed:
            break
        packed = pack(img, colours)
    if not packed:
        sys.exit('page: too many colours')
    banks, where, colour = packed
    order = [sorted(b) for b in banks]
    palette = [[BG] * 16 for _ in range(16)]
    for i, b in enumerate(order):
        for k, v in enumerate(b):
            palette[i][1 + k] = v
    for bank, fg in RAMPS.items():
        palette[bank] = ramp(fg)
    out = {}
    for (r, c), bank in where.items():
        idx = {v: 1 + k for k, v in enumerate(order[bank])}
        out[r, c] = (bank, [idx.get(colour(c * CW + x, r * CH + y), 0) for y in range(CH) for x in range(CW)])
    return palette, out


def char_bytes(pixels):
    """128 pixel indices as a 16-colour character: left pixel low nibble"""
    return bytes(pixels[i] | pixels[i + 1] << 4 for i in range(0, 128, 2))


def page_file(img):
    palette, cellmap = convert(img)
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
    return pal + count + rle(bytes(screen)) + rle(bytes(colour)) + rle(b''.join(chars)), len(chars)


# ---------------------------------------------------------------- the font

def glyph_font():
    f = font('Rajdhani-Bold.ttf', 17)
    out = bytearray()
    for ch in GLYPH_SET:
        im = Image.new('L', (16, 16), 0)
        d = ImageDraw.Draw(im)
        w = d.textlength(ch, font=f)
        d.text(((16 - w) / 2, -2), ch, font=f, fill=255)
        px = [round(im.getpixel((x, y)) * 15 / 255) for y in range(16) for x in range(16)]
        out += char_bytes(px[:128]) + char_bytes(px[128:])
    if len(GLYPH_SET) * 2 > GLYPH_CHARS:
        sys.exit('glyphs: too many')
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


def canvas():
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


PAGES = {'TITLE': page_title}


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
                f'#define GLYPH_BASE 0x{GLYPH_BASE:04X}  // the font\'s: 2 per glyph (top, bottom)\n'
                f'#define GLYPHS {len(GLYPH_SET)}\n'
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
