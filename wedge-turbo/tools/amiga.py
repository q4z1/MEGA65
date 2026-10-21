"""Amiga file formats needed to read the game's disk:
PowerPacker data (as packed into executables) and the hunk format of
AmigaDOS executables."""
import struct

HUNK_UNIT, HUNK_NAME, HUNK_CODE, HUNK_DATA, HUNK_BSS = 0x3e7, 0x3e8, 0x3e9, 0x3ea, 0x3eb
HUNK_RELOC32, HUNK_SYMBOL, HUNK_DEBUG, HUNK_END, HUNK_HEADER = 0x3ec, 0x3f0, 0x3f1, 0x3f2, 0x3f3


def pp_decrunch(packed, out_len, skip, table=(9, 10, 11, 11)):
    """PowerPacker: decodes `packed` (the bit stream, without the final
    long word that holds out_len and skip) backwards into out_len bytes."""
    out = bytearray(out_len)
    pos = len(packed)          # read position, long words from the end
    o = out_len                # write position, bytes from the end
    state = {'bits': 0, 'n': 0}

    def refill():
        nonlocal pos
        pos -= 4
        state['bits'] = struct.unpack_from('>I', packed, pos)[0]
        state['n'] = 32

    refill()
    state['bits'] >>= skip
    state['n'] = 32 - skip

    def get(count):
        v = 0
        for _ in range(count):
            if state['n'] == 0:
                refill()
            v = (v << 1) | (state['bits'] & 1)
            state['bits'] >>= 1
            state['n'] -= 1
        return v

    while o > 0:
        if get(1) == 0:
            run = 0
            while True:
                n = get(2)
                run += n
                if n != 3:
                    break
            for _ in range(run + 1):
                o -= 1
                out[o] = get(8)
            if o <= 0:
                break
        n = get(2)
        bits = table[n]
        length = n + 1
        if length == 4:
            if get(1) == 0:
                bits = 7
            offset = get(bits)
            while True:
                n = get(3)
                length += n
                if n != 7:
                    break
        else:
            offset = get(bits)
        for _ in range(length + 1):
            o -= 1
            out[o] = out[o + offset + 1]
    return bytes(out)


def parse_hunks(data):
    """Returns a list of hunks: dicts with type, data (bytes, BSS as zeros)
    and relocs {target hunk: [offsets]}."""
    p = 0

    def rl():
        nonlocal p
        v = struct.unpack_from('>I', data, p)[0]
        p += 4
        return v

    if rl() != HUNK_HEADER:
        raise ValueError('not an executable')
    while rl():                # resident library names
        pass
    count, first, last = rl(), rl(), rl()
    sizes = [rl() & 0x3fffffff for _ in range(last - first + 1)]
    hunks = []
    cur = None
    while p < len(data):
        t = rl() & 0x3fffffff
        if t in (HUNK_CODE, HUNK_DATA):
            n = rl() & 0x3fffffff
            cur = {'type': t, 'data': bytearray(data[p:p + 4 * n]), 'relocs': {}}
            cur['data'] += bytes(4 * sizes[len(hunks)] - len(cur['data']))
            p += 4 * n
            hunks.append(cur)
        elif t == HUNK_BSS:
            n = rl()
            cur = {'type': t, 'data': bytearray(4 * sizes[len(hunks)]), 'relocs': {}}
            hunks.append(cur)
        elif t == HUNK_RELOC32:
            while True:
                n = rl()
                if not n:
                    break
                target = rl()
                cur['relocs'].setdefault(target, []).extend(rl() for _ in range(n))
        elif t in (HUNK_SYMBOL,):
            while True:
                n = rl()
                if not n:
                    break
                p += 4 * n + 4
        elif t == HUNK_DEBUG:
            p += 4 * rl()
        elif t == HUNK_END:
            pass
        else:
            raise ValueError(f'unknown hunk type {t:#x} at {p - 4:#x}')
    return hunks


def relocate(hunks, bases):
    """Applies the relocations for hunks loaded at the given addresses."""
    out = []
    for h, base in zip(hunks, bases):
        d = bytearray(h['data'])
        for target, offs in h['relocs'].items():
            for o in offs:
                v = struct.unpack_from('>I', d, o)[0]
                struct.pack_into('>I', d, o, (v + bases[target]) & 0xffffffff)
        out.append(bytes(d))
    return out
