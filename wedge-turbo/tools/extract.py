#!/usr/bin/env python3
"""Unpacks the game's data: finds the disk image the build needs (an
AmigaDOS disk, known by its SHA-1) in ARCHIVE and writes into OUTDIR

    disk.adf      the disk image itself
    NN.bin        data file NN (hex): the files named ..._NN on the disk
    main.bin      the game program, unpacked (an AmigaDOS executable)
    code.bin      its code hunk, relocated to the address it runs at (the
                  tables mkdata.py takes from it are named by address)

    extract.py ARCHIVE OUTDIR

ARCHIVE is the outer zip (with one zip per disk image inside), a zip holding
the ADF, or the ADF itself. None of it is kept in the repository; the
build does this each time.
"""
import hashlib
import io
import os
import re
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', 'toolchain', 'tools', 'bin'))
import amiga  # noqa: E402
from adf import Adf  # noqa: E402

ADF_SHA1 = '590609b22934280df1e3292947a3d7d4a332ac48'
# where the hunks are when the game runs
HUNK_BASES = [0xC18880, 0x00B168, 0x00D080, 0xC240C0, 0xC292D8]


def find_adf(data):
    """The ADF with the right checksum, searched through nested zips."""
    if len(data) == 901120:
        return data if hashlib.sha1(data).hexdigest() == ADF_SHA1 else None
    if data[:2] != b'PK':
        return None
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            found = find_adf(z.read(name))
            if found:
                return found
    return None


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], 'rb') as f:
        adf_data = find_adf(f.read())
    if adf_data is None:
        sys.exit(f'{sys.argv[1]}: no disk image with SHA-1 {ADF_SHA1} found')
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'disk.adf'), 'wb') as f:
        f.write(adf_data)
    adf = Adf(adf_data)
    count = 0
    exe = None
    for path, block, st in adf.walk():
        if path.endswith('/'):
            continue
        data, _ = adf.file_data(block)
        m = re.fullmatch(r'[A-Za-z]+_([0-9A-Fa-f]{2})', path)
        if m:
            with open(os.path.join(out, m.group(1).upper() + '.bin'), 'wb') as f:
                f.write(data)
            count += 1
        elif data[:4] == b'\0\0\x03\xf3' and (exe is None or len(data) > len(exe)):
            exe = data  # the program: the largest executable
    if exe is None:
        sys.exit('the game program is missing on the disk')
    # The program: a PowerPacker decruncher hunk, the packed program in hunk 1
    hunks = amiga.parse_hunks(exe)
    packed = bytes(hunks[1]['data'])
    end = struct.unpack_from('>I', bytes(hunks[0]['data']), 0x158)[0]
    last = struct.unpack_from('>I', packed, end - 4)[0]
    main_exe = amiga.pp_decrunch(packed[:end - 4], last >> 8, last & 0xff)
    with open(os.path.join(out, 'main.bin'), 'wb') as f:
        f.write(main_exe)
    code = amiga.relocate(amiga.parse_hunks(main_exe), HUNK_BASES)[0]
    with open(os.path.join(out, 'code.bin'), 'wb') as f:
        f.write(code)
    print(f'{count} data files, program {len(main_exe)} bytes -> {out}')


if __name__ == '__main__':
    main()
