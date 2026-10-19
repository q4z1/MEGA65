#!/usr/bin/env python3
"""bspatch in Python: wendet einen BSDIFF40-Patch (bsdiff 4.x) an.

Ersatz fuer das bspatch.exe aus mega65go - der MEGA65-ROM-Patch
920413.bdf liegt in diesem Format vor.

Aufruf: bspatch.py <alte-datei> <neue-datei> <patch>
"""

import bz2
import sys


def offtin(b):
    """64-Bit-Zahl in bsdiffs Vorzeichen-Betrag-Darstellung."""
    v = int.from_bytes(b[:8], "little")
    if v & (1 << 63):
        return -(v & ~(1 << 63))
    return v


def bspatch(old, patch):
    if patch[:8] != b"BSDIFF40":
        raise ValueError("kein BSDIFF40-Patch")
    ctrllen = offtin(patch[8:16])
    difflen = offtin(patch[16:24])
    newsize = offtin(patch[24:32])
    if ctrllen < 0 or difflen < 0 or newsize < 0:
        raise ValueError("kaputter Patch-Kopf")

    ctrl = bz2.decompress(patch[32:32 + ctrllen])
    diff = bz2.decompress(patch[32 + ctrllen:32 + ctrllen + difflen])
    extra = bz2.decompress(patch[32 + ctrllen + difflen:])

    new = bytearray(newsize)
    oldpos = newpos = 0
    cpos = dpos = epos = 0
    while newpos < newsize:
        x = offtin(ctrl[cpos:cpos + 8])
        y = offtin(ctrl[cpos + 8:cpos + 16])
        z = offtin(ctrl[cpos + 16:cpos + 24])
        cpos += 24
        if x < 0 or y < 0 or newpos + x > newsize:
            raise ValueError("kaputter Patch (diff)")
        # diff-Block: Bytes der alten Datei plus Differenz
        for i in range(x):
            o = old[oldpos + i] if 0 <= oldpos + i < len(old) else 0
            new[newpos + i] = (diff[dpos + i] + o) & 0xFF
        dpos += x
        newpos += x
        oldpos += x
        if newpos + y > newsize:
            raise ValueError("kaputter Patch (extra)")
        # extra-Block: neue Bytes unveraendert uebernehmen
        new[newpos:newpos + y] = extra[epos:epos + y]
        epos += y
        newpos += y
        oldpos += z
    return bytes(new)


def main():
    if len(sys.argv) != 4:
        sys.exit("Aufruf: bspatch.py <alte-datei> <neue-datei> <patch>")
    with open(sys.argv[1], "rb") as f:
        old = f.read()
    with open(sys.argv[3], "rb") as f:
        patch = f.read()
    new = bspatch(old, patch)
    with open(sys.argv[2], "wb") as f:
        f.write(new)


if __name__ == "__main__":
    main()
