#!/bin/sh
# Baut MEGA65.ROM (Version 920413) aus dem Commodore-65-ROM 910828 und dem
# bsdiff-Patch 920413.bdf aus 920413_Sn7YEw.zip (files.mega65.org).
#
# Das C65-ROM selbst darf nicht weitergegeben werden; Cloanto stellt es mit
# "C64 Forever" kostenlos fuer den privaten Gebrauch bereit. Das Skript macht
# unter Linux dasselbe wie SETUP.cmd aus mega65go unter Windows:
#
#   1. c64-forever-11-setup.msi und den Patch laden (nach toolchain/downloads)
#   2. die CAB-Archive aus dem MSI holen, auspacken (cabextract)
#   3. darin das C65-ROM 910828 suchen (128 KB, Pruefsumme siehe unten)
#   4. mit 920413.bdf patchen -> toolchain/rom/MEGA65.ROM
#
# Aufruf: toolchain/rom/build-rom.sh

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

# SHA-1 der beiden ROMs, damit ein falsches Ausgangs-ROM auffaellt
C65_SHA1=b63d970727a2b8da72a0a8e234f3c30a20cbcb26
MEGA65_SHA1=4214ba4615a6ad852ddfc48b51a1d0ceca34a622

mkdir -p "$DL" "$WORK"

if [ ! -f "$MSI" ]; then
    echo "Lade C64 Forever (Cloanto) ..."
    curl -L --fail -o "$MSI.part" "$MSI_URL"
    mv "$MSI.part" "$MSI"
fi

if [ ! -f "$PATCH_ZIP" ]; then
    echo "Lade den ROM-Patch 920413 ..."
    curl -L --fail -o "$PATCH_ZIP.part" "$PATCH_URL"
    mv "$PATCH_ZIP.part" "$PATCH_ZIP"
fi

if [ ! -x "$TOOLS/cabextract" ] || [ ! -f "$TC/tools/python/olefile/__init__.py" ]; then
    echo "Hilfswerkzeuge fehlen, baue sie ..."
    "$TC/tools/build-tools.sh"
fi

echo "Hole CAB-Archive aus dem MSI ..."
rm -rf "$WORK/cab" "$WORK/files" "$WORK/920413"
python3 -I "$TOOLS/msi-extract-cabs.py" "$MSI" "$WORK/cab" >/dev/null
# bsdtar scheitert an diesem CAB (LZX), daher cabextract
for cab in "$WORK/cab"/*.cab; do
    "$TOOLS/cabextract" -q -d "$WORK/files" "$cab"
done

# Im MSI 11 ist es file_Shared_54 (die README zum Patch nennt fuer eine
# aeltere Ausgabe _53), daher wird ueber die Pruefsumme gesucht.
echo "Suche C65-ROM 910828 ..."
C65=""
for f in "$WORK/files"/*; do
    [ "$(stat -c %s "$f")" = 131072 ] || continue
    if [ "$(sha1sum "$f" | cut -d' ' -f1)" = "$C65_SHA1" ]; then
        C65=$f
        break
    fi
done
if [ -z "$C65" ]; then
    echo "Fehler: C65-ROM 910828 nicht im MSI gefunden." >&2
    exit 1
fi
cp "$C65" "$HERE/c-65-19910828.rom"

echo "Patche mit 920413.bdf ..."
bsdtar -xf "$PATCH_ZIP" -C "$WORK"
python3 -I "$TOOLS/bspatch.py" "$HERE/c-65-19910828.rom" "$HERE/MEGA65.ROM" \
    "$WORK/920413/920413.bdf"

if [ "$(sha1sum "$HERE/MEGA65.ROM" | cut -d' ' -f1)" != "$MEGA65_SHA1" ]; then
    echo "Fehler: MEGA65.ROM hat nicht die erwartete Pruefsumme." >&2
    exit 1
fi

rm -rf "$WORK"
echo "Fertig: $HERE/MEGA65.ROM"
