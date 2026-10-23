#!/bin/sh
# The cave editor and GDash's engine in Xemu. For each stop of the script
# in src/main.c (test_script) the game is built with -DEDITTEST=n, run
# headless on a copy of the disk - slot 2 with the first cave of
# tests/cavekit/objects.bd, the others empty - and the screen at that stop
# is kept as build/test/editor-n.png. After the last stop the cave the
# script saved is checked on that disk. The last stop is BASIC, where the
# game no longer tells Xemu to stop: it is stopped from outside, and its
# screen must be BASIC's. The normal build is made again at the end.
#
#   tests/test_editor.sh [stops]      (default: all 18)

set -e
cd "$(dirname "$0")/.."
OUT=build/test
STOPS=${1:-18}
BASIC_STOP=18
mkdir -p $OUT
for n in $(seq 1 "$STOPS"); do
    SMARAGD_CFLAGS="-DEDITTEST=$n" ./build.sh >$OUT/build.log 2>&1 || { tail $OUT/build.log; exit 1; }
    cp build/smaragd-dash.d81 $OUT/editor.d81
    python3 tools/cavekit.py empty $OUT/editor.d81 >/dev/null
    python3 tools/cavekit.py import $OUT/editor.d81 tests/cavekit/objects.bd --cave 1 --slot 2 >/dev/null
    rm -f $OUT/editor-$n.png
    if [ "$n" = $BASIC_STOP ]; then
        stop="-s INT 150"  # time enough to get there
    else
        stop=300
    fi
    # shellcheck disable=SC2086
    SDL_AUDIODRIVER=dummy timeout $stop ../toolchain/tools/bin/xmega65 -headless -sleepless -testing \
        -besure -8 $OUT/editor.d81 -autoload -screenshot $OUT/editor-$n.png >$OUT/xemu.log 2>&1 || true
    if [ -f $OUT/editor-$n.png ]; then
        echo "stop $n: $OUT/editor-$n.png"
    else
        echo "stop $n: no screenshot (see $OUT/xemu.log)"
        exit 1
    fi
done
if [ "$STOPS" -ge $BASIC_STOP ]; then
    # BASIC's screen: its blue, with text
    python3 - $OUT/editor-$BASIC_STOP.png <<'PY'
import sys
from PIL import Image
img = Image.open(sys.argv[1]).convert("RGB")
count, (r, g, b) = max(img.getcolors(1 << 16))
ok = count > img.width * img.height * 0.8 and b > 2 * (r + g) and len(img.getcolors(1 << 16)) > 2
print("BASIC:", "its screen" if ok else f"not its screen (most common colour {(r, g, b)})")
sys.exit(0 if ok else 1)
PY
fi
if [ "$STOPS" -ge 8 ]; then
    # what the script saved in slot 1: name, time, a boulder at 3,2 and a
    # firefly starting upwards at 3,3 (GDash's elements)
    python3 - $OUT/editor.d81 <<'PY'
import sys
sys.path.insert(0, "tools")
import cavekit
cave = cavekit.read_slot(cavekit.Disk(sys.argv[1]), "OWN01")
O = cavekit.O
ok = cave and cave.name == "TEST" and cave.time == 153 and cave.cells[2 * 40 + 3] == O["STONE"] \
    and cave.cells[3 * 40 + 3] == O["FIREFLY_2"]
print("slot 1:", "as saved" if ok else f"wrong: {cave and (cave.name, cave.time, cave.rows()[2:4])}")
sys.exit(0 if ok else 1)
PY
fi
./build.sh >$OUT/build.log 2>&1
