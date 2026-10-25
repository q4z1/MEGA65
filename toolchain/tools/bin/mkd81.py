#!/usr/bin/env python3
"""Writes a D81 disk image (1581 format, as the MEGA65's internal drive
uses) with the given files, all of type PRG.

Usage: mkd81.py [--keep <name>]... <out.d81> <disk name> <file>[=<name on disk>] ...

The first file is the one `RUN "*"` (and Xemu's -autoload) starts. Names
are upper-cased; files are stored as they are, so a PRG keeps its load
address in its first two bytes.

A name with a directory, DIR/NAME, puts the file into the partition DIR:
a 1581 partition (type CBM in the directory) of whole tracks with a header,
a BAM and a directory of its own, as the 1581's subdirectories have them -
DOS and programs reach its files as in a disk of their own. It gets as many
tracks as its files need (at least three, none of them track 40).

--keep <name>: if <out.d81> exists already and holds a file of that name
(DIR/NAME for one in a partition) with the same length as the new one, the
file keeps its old contents. For files the program writes itself (a high
score table, say), which would otherwise be reset by every build.
"""

import os
import sys

TRACKS, SECTORS = 80, 40
DIR_TRACK = 40
PRG, CBM = 0x82, 0x85  # closed file types


def petscii_name(s, n=16):
    b = s.upper().encode("ascii")
    if len(b) > n:
        raise SystemExit(f"mkd81: name '{s}' is longer than {n} characters")
    return b + b"\xa0" * (n - len(b))


class D81:
    def __init__(self):
        self.img = bytearray(TRACKS * SECTORS * 256)
        self.used = set()

    def sector(self, t, s):
        o = ((t - 1) * SECTORS + s) * 256
        return memoryview(self.img)[o:o + 256]

    def alloc(self, tracks):
        for t in tracks:
            for s in range(SECTORS):
                if (t, s) not in self.used:
                    self.used.add((t, s))
                    return t, s
        raise SystemExit("mkd81: disk full")

    def write_file(self, data, tracks):
        chunks = [data[i:i + 254] for i in range(0, len(data), 254)] or [b""]
        blocks = [self.alloc(tracks) for _ in chunks]
        for i, (chunk, (t, s)) in enumerate(zip(chunks, blocks)):
            sec = self.sector(t, s)
            if i + 1 < len(blocks):
                sec[0], sec[1] = blocks[i + 1]
            else:
                sec[0], sec[1] = 0, len(chunk) + 1  # last byte used
            sec[2:2 + len(chunk)] = chunk
        return blocks[0], len(blocks)

    def header(self, t, name, disk_id):
        """The header sector of a disk (40/0) or a partition (its first
        track, sector 0): directory at t/3"""
        h = self.sector(t, 0)
        h[0], h[1], h[2] = t, 3, ord("D")
        h[4:20] = petscii_name(name)
        h[20:22] = b"\xa0\xa0"
        h[22:24] = disk_id
        h[24] = 0xA0
        h[25], h[26] = ord("3"), ord("D")
        h[27:29] = b"\xa0\xa0"

    def directory(self, t, entries):
        """The directory from t/3 on: entries (name, type, (track, sector),
        blocks); the sectors it takes"""
        sectors = {(t, s) for s in range(0, 3 + (len(entries) + 7) // 8)}
        for k in range(0, max(1, len(entries)), 8):
            s = 3 + k // 8
            sec = self.sector(t, s)
            more = k + 8 < len(entries)
            sec[0], sec[1] = (t, s + 1) if more else (0, 0xFF)
            for j, (name, typ, (ft, fs), blocks) in enumerate(entries[k:k + 8]):
                e = 32 * j
                sec[e + 2] = typ
                sec[e + 3], sec[e + 4] = ft, fs
                sec[e + 5:e + 21] = petscii_name(name)
                sec[e + 30], sec[e + 31] = blocks & 0xFF, blocks >> 8
        return sectors

    def bam(self, t, own, disk_id):
        """The BAM at t/1 and t/2: free what is not used of the tracks
        `own` (the disk's: all; a partition's: its own)"""
        for half in (0, 1):
            b = self.sector(t, 1 + half)
            b[0], b[1] = (t, 2) if half == 0 else (0, 0xFF)
            b[2], b[3] = ord("D"), 0xBB
            b[4:6] = disk_id
            b[6] = 0xC0
            for i in range(40):
                tr = half * 40 + i + 1
                free = [s for s in range(SECTORS) if tr in own and (tr, s) not in self.used]
                o = 0x10 + 6 * i
                b[o] = len(free)
                b[o + 1:o + 6] = sum(1 << s for s in free).to_bytes(5, "little")


def partition_tracks(files):
    """Tracks a partition needs for its files [(name, data)]: the header,
    BAM and directory sectors and every file's blocks, at least three"""
    blocks = 3 + (len(files) + 7) // 8 + sum(max(1, (len(d) + 253) // 254) for _, d in files)
    return max(3, (blocks + SECTORS - 1) // SECTORS)


def build(disk_name, files, disk_id=b"ED"):
    """The image of files [(name, data)]; DIR/NAME go into partition DIR"""
    d = D81()
    root, parts = [], {}
    for name, data in files:
        if "/" in name:
            part, _, base = name.partition("/")
            parts.setdefault(part, []).append((base, data))
        root.append(name)
    # The partitions from the last track down, each on whole tracks that
    # do not hold track 40; the files of the disk itself from track 1 up
    top, ranges = TRACKS, {}
    for part, pfiles in parts.items():
        n = partition_tracks(pfiles)
        if top > DIR_TRACK and top - n + 1 <= DIR_TRACK:
            top = DIR_TRACK - 1
        if top - n + 1 < 1:
            raise SystemExit("mkd81: disk full")
        ranges[part] = list(range(top - n + 1, top + 1))
        top -= n
    taken = {t for r in ranges.values() for t in r}
    disk_tracks = [t for t in range(1, TRACKS + 1) if t != DIR_TRACK and t not in taken]
    entries, seen, report = [], set(), []
    for name, data in files:
        if "/" in name:
            part = name.split("/")[0]
            if part not in seen:
                seen.add(part)
                tracks = ranges[part]
                first = tracks[0]
                for s in range(0, 3 + (len(parts[part]) + 7) // 8):
                    d.used.add((first, s))
                pentries = []
                for base, pdata in parts[part]:
                    start, blocks = d.write_file(pdata, tracks)
                    pentries.append((base, PRG, start, blocks))
                    report.append((f"{part}/{base}", blocks))
                d.header(first, part, disk_id)
                d.directory(first, pentries)
                d.bam(first, set(tracks), disk_id)
                entries.append((part, CBM, (first, 0), len(tracks) * SECTORS))
            continue
        start, blocks = d.write_file(data, disk_tracks)
        entries.append((name, PRG, start, blocks))
        report.append((name, blocks))
    for t in taken:  # the partitions' sectors are used, for the disk's BAM
        d.used.update((t, s) for s in range(SECTORS))
    d.header(DIR_TRACK, disk_name, disk_id)
    d.used.update(d.directory(DIR_TRACK, entries))
    d.bam(DIR_TRACK, set(range(1, TRACKS + 1)), disk_id)
    return d.img, report


def _sector(img, t, s):
    o = ((t - 1) * SECTORS + s) * 256
    return img[o:o + 256]


def directory(img, t=DIR_TRACK):
    """The files in the image `img`, in directory order: (name, type, first
    track, first sector, blocks). The type is the entry's byte 2 (0x82: PRG,
    0x85: a partition, both closed); the name is the 16 bytes without their
    padding. t: the directory of the partition that starts on track t."""
    out = []
    s = 3
    while t:
        sec = _sector(img, t, s)
        for e in range(0, 256, 32):
            if sec[e + 2]:
                out.append((bytes(sec[e + 5:e + 21]).rstrip(b"\xa0"), sec[e + 2],
                            sec[e + 3], sec[e + 4], sec[e + 30] | sec[e + 31] << 8))
        t, s = sec[0], sec[1]
    return out


def all_files(img):
    """directory(img) with the files of each partition after it, named
    DIR/NAME"""
    out = []
    for name, typ, t, s, blocks in directory(img):
        out.append((name, typ, t, s, blocks))
        if typ & 7 == CBM & 7:
            out += [(name + b"/" + n, ty, tt, ss, b) for n, ty, tt, ss, b in directory(img, t)]
    return out


def file_data(img, t, s):
    """The contents of the file that starts at track t, sector s."""
    data = b""
    while t:
        blk = _sector(img, t, s)
        t, s = blk[0], blk[1]
        data += blk[2:] if t else blk[2:s + 1]
    return data


def free_blocks(img):
    """The blocks free on the disk, as the directory reports them (3160 on
    an empty disk: the directory track does not count)."""
    return sum(_sector(img, DIR_TRACK, 1 + half)[0x10 + 6 * i]
               for half in (0, 1) for i in range(40)
               if half * 40 + i + 1 != DIR_TRACK)


def read_file(img, name):
    """The contents of file `name` (DIR/NAME: in partition DIR) in the
    image `img`, or None."""
    want = b"/".join(petscii_name(p).rstrip(b"\xa0") for p in name.split("/"))
    for n, typ, t, s, _ in all_files(img):
        if n == want and typ & 7 != CBM & 7:
            return file_data(img, t, s)
    return None


def main():
    args = sys.argv[1:]
    keep = set()
    while len(args) > 1 and args[0] == "--keep":
        keep.add(args[1].upper())
        args = args[2:]
    if len(args) < 3:
        sys.exit(__doc__)
    out, disk_name, specs = args[0], args[1], args[2:]
    old = None
    if keep and os.path.exists(out):
        with open(out, "rb") as f:
            old = f.read()
        if len(old) != TRACKS * SECTORS * 256:
            old = None
    files, kept = [], []
    for spec in specs:
        path, _, name = spec.partition("=")
        name = (name or path.rsplit("/", 1)[-1].rsplit(".", 1)[0]).upper()
        for part in name.split("/"):
            petscii_name(part)
        with open(path, "rb") as f:
            data = f.read()
        if old and name in keep:
            prev = read_file(old, name)
            if prev is not None and len(prev) == len(data):
                data = prev
                kept.append(name)
        files.append((name, data))
    img, report = build(disk_name, files)
    with open(out, "wb") as f:
        f.write(img)
    print(f"mkd81: {out}: " + ", ".join(f"{n} ({b} blocks)" for n, b in report))
    if kept:
        print("mkd81: kept from the old image: " + ", ".join(kept))


if __name__ == "__main__":
    main()
