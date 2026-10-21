#!/bin/sh
# Builds or installs the small helper tools under toolchain/tools:
#
#   bin/cabextract   from source (tools/src), for the CABs in the C64 Forever MSI
#   python/olefile   Python module for reading the MSI (OLE compound file)
#   python/capstone  disassembler module, used by bin/m68k-dis.py
#   python/X.Y/      Pillow (images for the build tools, e.g. Wedge Turbo's
#                    tools/mkpages.py, tools/mkcars.py) and numpy (arrays for
#                    the analysis scripts), per Python version
#                    (python-modules.sh)
#   bin/amiga-run    script-driven Amiga emulator (amiga-run/, on the vAmiga
#                    core from tools/src/vAmiga) for running Amiga programs
#
# bin/bspatch.py, bin/msi-extract-cabs.py and bin/xmega65 are scripts and
# are ready to use as they are.

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
DL="$(dirname "$HERE")/downloads"
CABX=cabextract-1.11
# vAmiga's core, pinned to a known-good commit
VAMIGA_REPO=https://github.com/dirkwhoffmann/vAmiga.git
VAMIGA_COMMIT=c38fa527ea97b9b0036c0e58526cf2714fd97213

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

if [ ! -f "$HERE/python/capstone/__init__.py" ]; then
    python3 -m pip install -q --target "$HERE/python" capstone
fi

# for the build tools and the analysis scripts, at fixed versions
"$HERE/python-modules.sh" > /dev/null

if [ ! -x "$HERE/bin/amiga-run" ]; then
    if [ ! -d "$HERE/src/vAmiga/.git" ]; then
        git clone -q "$VAMIGA_REPO" "$HERE/src/vAmiga"
    fi
    git -C "$HERE/src/vAmiga" fetch -q --depth 1 origin "$VAMIGA_COMMIT" 2>/dev/null || true
    git -C "$HERE/src/vAmiga" checkout -q "$VAMIGA_COMMIT"
    # this vAmiga commit uses std::format without including <format>
    cmake -S "$HERE/amiga-run" -B "$HERE/src/amiga-run-build" -DCMAKE_BUILD_TYPE=Release \
        -DVAMIGA_CORE="$HERE/src/vAmiga/Core" -DCMAKE_CXX_FLAGS="-include format" >/dev/null
    cmake --build "$HERE/src/amiga-run-build" -j"$(nproc)" --target amiga-run >/dev/null
    cp "$HERE/src/amiga-run-build/amiga-run" "$HERE/bin/"
fi

echo "Tools ready in $HERE/bin."
