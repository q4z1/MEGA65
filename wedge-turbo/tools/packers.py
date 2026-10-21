"""The two packers of the game's data files.

Both read a bit stream backwards: long words from the end of the stream,
bits from the top, and the lowest set bit of every long word marks its end
(the first long word read already carries that marker).
"""
import struct


class BackBits:
    """The game's bit reader: add.l d0,d0 / bne / move.l -(a0),d0 / addx."""

    def __init__(self, data, end):
        self.data = data
        self.pos = end - 4
        self.cur = struct.unpack_from('>I', data, self.pos)[0]

    def bit(self):
        c = self.cur >> 31
        self.cur = (self.cur << 1) & 0xffffffff
        if self.cur == 0:
            self.pos -= 4
            v = struct.unpack_from('>I', self.data, self.pos)[0]
            c = v >> 31
            self.cur = ((v << 1) | 1) & 0xffffffff
        return c

    def bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v


def unpack_planar(data):
    """Picture packer: LZ77 on 5-bit pixels with a
    16 KB ring buffer, written out as five bitplanes, last byte first.

    Header: long words of the stream, bytes per line, lines, planes.
    Returns (planes, bytes_per_line, lines, plane_data)."""
    nlongs, bpl, lines, planes = struct.unpack_from('>4H', data, 0)
    end = 8 + 4 * nlongs
    psize = bpl * lines
    out = bytearray(psize * 5)
    a3 = psize                # write position in plane 0, backwards
    ring = bytearray(0x4000)
    d4 = d5 = 0x4000          # ring write position, conversion position
    pending = 0               # pixels not yet converted
    bs = BackBits(data, end)
    copy_len = {0: (0, 4), 1: (0, 5), 2: (0, 6), 3: (0, 7), 4: (1, 8), 5: (1, 10),
                6: (2, 12), 7: (2, 16), 8: (2, 20), 9: (3, 24), 10: (5, 32), 11: (8, 64)}

    def put(px):
        nonlocal d4, pending
        d4 = (d4 - 1) & 0x3fff
        ring[d4] = px
        pending += 1

    while a3 > 0:
        t = bs.bits(4)
        if t in copy_len:
            nb, base = copy_len[t]
            n = base + bs.bits(nb)
            off = bs.bits(14)
            src = (off + d4) & 0x3fff
            for _ in range(n):
                src = (src - 1) & 0x3fff
                put(ring[src])
        elif t == 12:
            n = 4 + bs.bits(4)
            px = bs.bits(5)
            for _ in range(n):
                put(px)
        elif t == 13:
            n = 20 + bs.bits(8)
            px = bs.bits(5)
            for _ in range(n):
                put(px)
        elif t == 14:
            put(bs.bits(5))
        else:
            n = 2 + bs.bits(3)
            for _ in range(n):
                put(bs.bits(5))
        # every 8 pixels become one byte in each plane
        while pending >= 8 and a3 > 0:
            d5 = (d5 - 8) & 0x3ff8
            pending -= 8
            px = ring[d5:d5 + 8]
            a3 -= 1
            for p in range(5):
                b = 0
                for x in px:
                    b = (b << 1) | ((x >> p) & 1)
                out[a3 + p * psize] = b
    return planes, bpl, lines, bytes(out[:psize * planes])


def unpack_bytes(data):
    """Byte packer: LZ77 with Huffman-coded lengths;
    literals come from a separate stream at the start. Output is written
    backwards. Returns the unpacked bytes."""
    nlit, nlongs, size = struct.unpack_from('>HHI', data, 0)
    p = 8

    def nibbles(n):
        nonlocal p
        out = []
        for b in data[p:p + n]:
            out += [b >> 4, b & 15]
        p += n
        return out

    symbols = nibbles(8)       # symbol of the i-th code
    levels = nibbles(8)        # code length - 1 of the i-th code
    extra = nibbles(8)         # extra bits per symbol
    base = []
    v = 2
    for i in range(12):        # symbols 0-11: matches, length from 2
        base.append(v)
        v += 1 << extra[i]
    v = 1
    for i in range(12, 16):    # symbols 12-15: literal runs, from 1
        base.append(v)
        v += 1 << extra[i]
    # decode table: [level * 256 + prefix] -> symbol, 0xff = longer code
    table = [0xff] * 0x800
    pos = 0
    for sym, lev in zip(symbols, levels):
        if pos >= 0x100:
            break
        table[pos + (lev << 8)] = sym
        pos += 0x80 >> lev
    lit = p + nlit             # literals are copied from the end backwards
    end = p + ((nlit + 1) & ~1) + 4 * nlongs
    bs = BackBits(data, end)
    out = bytearray(size)
    a3 = size
    total = 0
    limit, offbits = 0x10, 4
    while a3 > 0:
        d7, bitpos = 0, 7
        while True:
            if bs.bit():
                d7 |= 1 << bitpos
            s = table[d7]
            if s != 0xff:
                break
            d7 += 0x100
            bitpos -= 1
        n = base[s] + bs.bits(extra[s])
        total += n
        if s < 12:
            ob = 14 if n >= 5 else n * 2 + 4
            ob = min(ob, offbits)
            off = bs.bits(ob)
            src = a3 + off
            for _ in range(n):
                src -= 1
                a3 -= 1
                out[a3] = out[src]
        else:
            for _ in range(n):
                lit -= 1
                a3 -= 1
                out[a3] = data[lit]
        while offbits != 14 and limit <= total:
            limit *= 2
            offbits += 1
    return bytes(out)
