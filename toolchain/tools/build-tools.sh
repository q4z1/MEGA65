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
#   bin/gdash-oracle GDash's own cave code (tools/src/gdash) as a test oracle
#                    for Smaragd Dash's port of its engine (gdash-oracle/);
#                    tools/src/gdash/caves has GDash's caves for its tests
#
# bin/bspatch.py, bin/msi-extract-cabs.py and bin/xmega65 are scripts and
# are ready to use as they are.

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
DL="$(dirname "$HERE")/downloads"
CABX=cabextract-1.11
# GDash (the fork with its caves), pinned
GDASH_REPO=https://github.com/revvv/gdash-export-CrLi.git
GDASH_COMMIT=4c0ab8411ac9fb632a9c8da64da47436a6fb10bc
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

# made anew when its own sources changed
if [ ! -x "$HERE/bin/gdash-oracle" ] || [ -n "$(find "$HERE/gdash-oracle" -newer "$HERE/bin/gdash-oracle")" ]; then
    if [ ! -d "$HERE/src/gdash/.git" ]; then
        git clone -q "$GDASH_REPO" "$HERE/src/gdash"
    fi
    git -C "$HERE/src/gdash" fetch -q --depth 1 origin "$GDASH_COMMIT" 2>/dev/null || true
    git -C "$HERE/src/gdash" checkout -q "$GDASH_COMMIT"
    # its cave code only: no user interface, no autotools (gdash-oracle/config.h)
    G="$HERE/src/gdash/src"
    # one fix: GDash saves a part of the cave above 1 (an amoeba threshold
    # bigger than the cave, as its C64 imports have) but refuses it when it
    # loads the file again; Smaragd Dash's cavekit.py takes it
    P="$HERE/src/gdash-oracle-build"
    mkdir -p "$P"
    sed '/GdInt &i, double conversion_ratio/,/^}/s/read <= 1)/read * conversion_ratio <= 16383)/' \
        "$G/cave/cavetypes.cpp" >"$P/cavetypes.cpp"
    set -- "$P/cavetypes.cpp"
    for f in "$G"/cave/*.cpp "$G"/cave/helper/*.cpp "$G"/cave/object/*.cpp; do
        case "$f" in
            */gamecontrol.cpp | */gamerender.cpp | */titleanimation.cpp | */cavetypes.cpp) ;;
            *) set -- "$@" "$f" ;;
        esac
    done
    g++ -O1 -w -std=c++17 -I"$HERE/gdash-oracle" -I"$G" -I"$HERE/src/gdash/include" \
        $(pkg-config --cflags glib-2.0) -o "$HERE/bin/gdash-oracle" \
        "$HERE/gdash-oracle/oracle.cpp" "$HERE/gdash-oracle/stubs.cpp" "$@" \
        "$G/fileops/bdcffload.cpp" "$G/fileops/bdcffsave.cpp" "$G/fileops/bdcffhelper.cpp" \
        "$G/fileops/c64import.cpp" "$G/fileops/loadfile.cpp" "$G/fileops/binaryimport.cpp" \
        "$G/fileops/brcimport.cpp" "$G/misc/logger.cpp" "$G/misc/printf.cpp" "$G/misc/util.cpp" \
        $(pkg-config --libs glib-2.0)
fi

echo "Tools ready in $HERE/bin."
