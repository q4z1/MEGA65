#!/bin/sh
# Baut bzw. installiert die kleinen Hilfswerkzeuge unter toolchain/tools:
#
#   bin/cabextract   aus den Quellen (tools/src), fuer die CABs im C64-Forever-MSI
#   python/olefile   Python-Modul zum Lesen des MSI (OLE-Verbunddatei)
#
# bin/bspatch.py, bin/msi-extract-cabs.py und bin/xmega65 sind Skripte und
# liegen fertig im Verzeichnis.

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
DL="$(dirname "$HERE")/downloads"
CABX=cabextract-1.11

mkdir -p "$DL" "$HERE/src" "$HERE/bin"

if [ ! -x "$HERE/bin/cabextract" ]; then
    if [ ! -f "$DL/$CABX.tar.gz" ]; then
        curl -L --fail -o "$DL/$CABX.tar.gz" \
            "https://www.cabextract.org.uk/$CABX.tar.gz"
    fi
    rm -rf "$HERE/src/$CABX"
    tar xzf "$DL/$CABX.tar.gz" -C "$HERE/src"
    (cd "$HERE/src/$CABX" && ./configure -q && make -s)
    cp "$HERE/src/$CABX/cabextract" "$HERE/bin/"
fi

if [ ! -f "$HERE/python/olefile/__init__.py" ]; then
    python3 -m pip install -q --target "$HERE/python" olefile
fi

echo "Werkzeuge in $HERE/bin bereit."
