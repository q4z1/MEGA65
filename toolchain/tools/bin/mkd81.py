#!/usr/bin/env python3
"""Writes a D81 disk image (1581 format, as the MEGA65's internal drive
uses) with the given files, all of type PRG.

Usage: mkd81.py <out.d81> <disk name> <file>[=<name on disk>] ...

The first file is the one `RUN "*"` (and Xemu's -autoload) starts. Names
are upper-cased; files are stored as they are, so a PRG keeps its load
address in its first two bytes.
"""

import sys

TRACKS, SECTORS = 80, 40
DIR_TRACK = 40


def petscii_name(s, n=16):
    b = s.upper().encode("ascii")[:n]
    return b + b"\xa0" * (n - len(b))


class D81:
    def __init__(self):
        self.img = bytearray(TRACKS * SECTORS * 256)
        self.used = set()

    def sector(self, t, s):
        o = ((t - 1) * SECTORS + s) * 256
        return memoryview(self.img)[o:o + 256]

    def alloc(self):
        for t in list(range(1, DIR_TRACK)) + list(range(DIR_TRACK + 1, TRACKS + 1)):
            for s in range(SECTORS):
                if (t, s) not in self.used:
                    self.used.add((t, s))
                    return t, s
        raise SystemExit("mkd81: disk full")

    def write_file(self, data):
        chunks = [data[i:i + 254] for i in range(0, len(data), 254)] or [b""]
        blocks = [self.alloc() for _ in chunks]
        for i, (chunk, (t, s)) in enumerate(zip(chunks, blocks)):
            sec = self.sector(t, s)
            if i + 1 < len(blocks):
                sec[0], sec[1] = blocks[i + 1]
            else:
                sec[0], sec[1] = 0, len(chunk) + 1  # last byte used
            sec[2:2 + len(chunk)] = chunk
        return blocks[0], len(blocks)

    def finish(self, disk_name, entries, disk_id=b"ED"):
        # header (40/0)
        h = self.sector(DIR_TRACK, 0)
        h[0], h[1], h[2] = DIR_TRACK, 3, ord("D")
        h[4:20] = petscii_name(disk_name)
        h[20:22] = b"\xa0\xa0"
        h[22:24] = disk_id
        h[24] = 0xA0
        h[25], h[26] = ord("3"), ord("D")
        h[27:29] = b"\xa0\xa0"
        # directory (40/3 on)
        for k in range(0, max(1, len(entries)), 8):
            s = 3 + k // 8
            sec = self.sector(DIR_TRACK, s)
            more = k + 8 < len(entries)
            sec[0], sec[1] = (DIR_TRACK, s + 1) if more else (0, 0xFF)
            for j, (name, (t, ss), blocks) in enumerate(entries[k:k + 8]):
                e = 32 * j
                sec[e + 2] = 0x82  # PRG, closed
                sec[e + 3], sec[e + 4] = t, ss
                sec[e + 5:e + 21] = petscii_name(name)
                sec[e + 30], sec[e + 31] = blocks & 0xFF, blocks >> 8
        dir_sectors = {(DIR_TRACK, s) for s in range(0, 3 + (len(entries) + 7) // 8)}
        # BAM (40/1 for tracks 1-40, 40/2 for 41-80)
        for half in (0, 1):
            b = self.sector(DIR_TRACK, 1 + half)
            b[0], b[1] = (DIR_TRACK, 2) if half == 0 else (0, 0xFF)
            b[2], b[3] = ord("D"), 0xBB
            b[4:6] = disk_id
            b[6] = 0xC0
            for i in range(40):
                t = half * 40 + i + 1
                free = [s for s in range(SECTORS)
                        if (t, s) not in self.used and (t, s) not in dir_sectors]
                bits = sum(1 << s for s in free)
                o = 0x10 + 6 * i
                b[o] = len(free)
                b[o + 1:o + 6] = bits.to_bytes(5, "little")


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    out, disk_name, files = sys.argv[1], sys.argv[2], sys.argv[3:]
    d = D81()
    entries = []
    for spec in files:
        path, _, name = spec.partition("=")
        name = name or path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        with open(path, "rb") as f:
            start, blocks = d.write_file(f.read())
        entries.append((name, start, blocks))
    d.finish(disk_name, entries)
    with open(out, "wb") as f:
        f.write(d.img)
    print(f"mkd81: {out}: " + ", ".join(f"{n} ({b} blocks)" for n, _, b in entries))


if __name__ == "__main__":
    main()
