#!/bin/sh
# Builds MEGA65.ROM (version 920413) from the Commodore 65 ROM 910828 and the
# bsdiff patch 920413.bdf from 920413_Sn7YEw.zip (files.mega65.org).
#
# The C65 ROM itself may not be redistributed; Cloanto gives it away for
# personal use as part of "C64 Forever". This script does on Linux what
# mega65go's SETUP.cmd does on Windows:
#
#   1. download c64-forever-11-setup.msi and the patch (into toolchain/downloads)
#   2. pull the CAB archives out of the MSI and unpack them (cabextract)
#   3. find the C65 ROM 910828 among them (128 KB, checksum see below)
#   4. patch it with 920413.bdf -> toolchain/rom/MEGA65.ROM
#
# Usage: toolchain/rom/build-rom.sh

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
TC=$(dirname "$HERE")
TOOLS="$TC/tools/bin"
DL="$TC/downloads"
WORK="$HERE/work"

MSI_URL=https://cdn.cloanto.com/pub/c64forever/c64-forever-11-setup.msi
MSI="$DL/c64-forever-11-setup.msi"
PATCH_URL=https://files.mega65.org/files/other/920413_Sn7YEw.zip
PATCH_ZIP="$DL/920413_Sn7YEw.zip"

# SHA-1 of both ROMs, so that a wrong source ROM is noticed
C65_SHA1=b63d970727a2b8da72a0a8e234f3c30a20cbcb26
MEGA65_SHA1=4214ba4615a6ad852ddfc48b51a1d0ceca34a622

mkdir -p "$DL" "$WORK"

if [ ! -f "$MSI" ]; then
    echo "Downloading C64 Forever (Cloanto) ..."
    curl -L --fail -o "$MSI.part" "$MSI_URL"
    mv "$MSI.part" "$MSI"
fi

if [ ! -f "$PATCH_ZIP" ]; then
    echo "Downloading the ROM patch 920413 ..."
    curl -L --fail -o "$PATCH_ZIP.part" "$PATCH_URL"
    mv "$PATCH_ZIP.part" "$PATCH_ZIP"
fi

if [ ! -x "$TOOLS/cabextract" ] || [ ! -f "$TC/tools/python/olefile/__init__.py" ]; then
    echo "Helper tools missing, building them ..."
    "$TC/tools/build-tools.sh"
fi

echo "Extracting CAB archives from the MSI ..."
rm -rf "$WORK/cab" "$WORK/files" "$WORK/920413"
python3 -I "$TOOLS/msi-extract-cabs.py" "$MSI" "$WORK/cab" >/dev/null
# bsdtar fails on this CAB (LZX), hence cabextract
for cab in "$WORK/cab"/*.cab; do
    "$TOOLS/cabextract" -q -d "$WORK/files" "$cab"
done

# In MSI 11 it is file_Shared_54 (the patch's README names _53 for an older
# release), so it is looked up by its checksum.
echo "Looking for the C65 ROM 910828 ..."
C65=""
for f in "$WORK/files"/*; do
    [ "$(stat -c %s "$f")" = 131072 ] || continue
    if [ "$(sha1sum "$f" | cut -d' ' -f1)" = "$C65_SHA1" ]; then
        C65=$f
        break
    fi
done
if [ -z "$C65" ]; then
    echo "Error: C65 ROM 910828 not found in the MSI." >&2
    exit 1
fi
cp "$C65" "$HERE/c-65-19910828.rom"

echo "Patching with 920413.bdf ..."
bsdtar -xf "$PATCH_ZIP" -C "$WORK"
python3 -I "$TOOLS/bspatch.py" "$HERE/c-65-19910828.rom" "$HERE/MEGA65.ROM" \
    "$WORK/920413/920413.bdf"

if [ "$(sha1sum "$HERE/MEGA65.ROM" | cut -d' ' -f1)" != "$MEGA65_SHA1" ]; then
    echo "Error: MEGA65.ROM does not have the expected checksum." >&2
    exit 1
fi

rm -rf "$WORK"
echo "Done: $HERE/MEGA65.ROM"
