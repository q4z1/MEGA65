#!/usr/bin/env python3
"""Converts the game's images - scenery objects, cars, race view overlays,
the backdrops - into what Lotus Run loads.

    mksprites.py ORIGDIR GENDIR

The data files keep the objects as Amiga blitter objects: per image width,
height, planes, plane size, then the planes and a mask (bit set: the image,
clear: the picture behind). Each bank becomes a file the game loads into
attic RAM (banks.c), images one byte per pixel, row after row: the colour
(0-15), or SPR_CLEAR where the picture behind shows.

A backdrop (files $60-$69) is three bitplanes of 320 x 96 pixels: three
strips of 320 x 32, side by side a panorama of 960 x 32. Its values 0-6 are
colours 4-7 and 12-14, 7 the sky (colour 15).

Writes into GENDIR:
    sprNN.bin     bank NN (on the disk as SPRNN): u8 image count, per image
                  u8 width and u8 height, then all pixels, run-length coded:
                  a byte n < $80 is followed by n + 1 pixels, n >= $80 by one
                  pixel repeated n - $7E times
    sprbanks.h/.c the banks: 00-2B the scenery objects $80-$AB (the types
                  without a file of their own share another's bank),
                  SPR_CARS, SPR_HUD
    backN.bin     backdrop N (on the disk as BACKN): 960 x 32 colours, row
                  after row, run-length coded as the banks' pixels
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import packers  # noqa: E402

SPR_CLEAR = 0xFF
SPR_CARS = 0x40
SPR_HUD = 0x41

# object types without a file use these
ALIASES = {0x92: 0x8F, 0x93: 0x90, 0x88: 0x87, 0xA6: 0xA5, 0xA8: 0xA7}
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


def rle(d):
    out, i = bytearray(), 0
    while i < len(d):
        j = i
        while j < len(d) and d[j] == d[i] and j - i < 129:
            j += 1
        if j - i >= 2:
            out += bytes([0x7E + j - i, d[i]])
            i = j
            continue
        j = i + 1
        while j < len(d) and j - i < 128 and not (j + 1 < len(d) and d[j] == d[j + 1]):
            j += 1
        out += bytes([j - i - 1]) + d[i:j]
        i = j
    return out


BACKDROPS = 10
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
            out.append(4 + (v & 3) + ((v & 4) << 1))
    return bytes(out)


def bank_file(ims):
    head = bytearray([len(ims)])
    for w, h, _ in ims:
        head += bytes([w, h])
    return bytes(head) + rle(b''.join(px for _, _, px in ims))


def main():
    orig, gen = sys.argv[1], sys.argv[2]
    os.makedirs(gen, exist_ok=True)

    def unpack(n):
        return packers.unpack_bytes(open(os.path.join(orig, f'{n:02X}.bin'), 'rb').read())

    banks = {}
    f51 = unpack(0x51)
    for t in range(0x80, 0xAC):
        if t in ALIASES:
            continue
        if t in FILE51:
            banks[t - 0x80] = list(images(f51, FILE51[t]))
        elif os.path.exists(os.path.join(orig, f'{t:02X}.bin')):
            banks[t - 0x80] = list(images(unpack(t)))
    banks[SPR_CARS] = list(images(unpack(0xC0)))
    banks[SPR_HUD] = list(images(unpack(0x50), FILE50_HUD))
    for b, ims in banks.items():
        with open(os.path.join(gen, f'spr{b:02x}.bin'), 'wb') as f:
            f.write(bank_file(ims))

    for n in range(BACKDROPS):
        with open(os.path.join(gen, f'back{n}.bin'), 'wb') as f:
            f.write(rle(backdrop(unpack(0x60 + n))))

    of_type = [ALIASES.get(t, t) - 0x80 for t in range(0x80, 0xAC)]
    of_type = [b if b in banks else 0xFF for b in of_type]
    largest = max(sum(w * h for w, h, _ in ims) for ims in banks.values())
    with open(os.path.join(gen, 'sprbanks.h'), 'w') as f:
        f.write('// Generated by tools/mksprites.py - do not edit\n#pragma once\n#include <stdint.h>\n'
                f'#define SPR_CLEAR 0x{SPR_CLEAR:02X}  // a pixel that is not drawn\n'
                f'#define SPR_CARS  0x{SPR_CARS:02X}  // the cars: 9 angles per size, the opponents from 63\n'
                f'#define SPR_HUD   0x{SPR_HUD:02X}  // messages, countdown, places, brake lights\n'
                f'#define SPR_BANKS 0x{SPR_HUD + 1:02X}\n'
                f'#define SPR_LARGEST {largest}  // pixels of the largest bank\n'
                f'#define BACK_W {BACK_W}  // a backdrop (BACKN): colours, row after row\n'
                f'#define BACK_H {BACK_H}\n'
                '// The bank of scenery object type $80 + i ($FF: none, no course has it)\n'
                'extern const uint8_t spr_bank_of_type[44];\n')
    with open(os.path.join(gen, 'sprbanks.c'), 'w') as f:
        f.write('// Generated by tools/mksprites.py - do not edit\n#include "sprbanks.h"\n\n'
                'const uint8_t spr_bank_of_type[44] = {\n')
        for i in range(0, 44, 12):
            f.write('    ' + ', '.join(f'0x{b:02X}' for b in of_type[i:i + 12]) + ',\n')
        f.write('};\n')


if __name__ == '__main__':
    main()
