#!/bin/sh
# The cave editor in Xemu. For each stop of the script in src/main.c
# (test_script) the game is built with -DEDITTEST=n, run headless on a copy
# of the disk with empty slots, and the screen at that stop is kept as
# build/test/editor-n.png. After the last stop the cave the script saved
# is checked on that disk. The normal build is made again at the end.
#
#   tests/test_editor.sh [stops]      (default: all 10)

set -e
cd "$(dirname "$0")/.."
OUT=build/test
STOPS=${1:-10}
mkdir -p $OUT
for n in $(seq 1 "$STOPS"); do
    SMARAGD_CFLAGS="-DEDITTEST=$n" ./build.sh >$OUT/build.log 2>&1 || { tail $OUT/build.log; exit 1; }
    cp build/smaragd-dash.d81 $OUT/editor.d81
    python3 tools/cavekit.py empty $OUT/editor.d81 >/dev/null
    rm -f $OUT/editor-$n.png
    SDL_AUDIODRIVER=dummy timeout 300 ../toolchain/tools/bin/xmega65 -headless -sleepless -testing \
        -besure -8 $OUT/editor.d81 -autoload -screenshot $OUT/editor-$n.png >$OUT/xemu.log 2>&1 || true
    if [ -f $OUT/editor-$n.png ]; then
        echo "stop $n: $OUT/editor-$n.png"
    else
        echo "stop $n: no screenshot (see $OUT/xemu.log)"
        exit 1
    fi
done
if [ "$STOPS" -ge 8 ]; then
    # what the script saved in slot 1: name, time, a boulder at 3,2 and a
    # firefly starting upwards at 3,3
    python3 - $OUT/editor.d81 <<'PY'
import sys
sys.path.insert(0, "tools")
import cavekit
cave = cavekit.read_slot(cavekit.Disk(sys.argv[1]), "OWN01")
ok = cave and cave.name == "TEST" and cave.time == 153 and cave.cells[2 * 40 + 3] == "r" \
    and cave.cells[3 * 40 + 3] == "o"
print("slot 1:", "as saved" if ok else f"wrong: {cave and (cave.name, cave.time, cave.rows()[2:4])}")
sys.exit(0 if ok else 1)
PY
fi
./build.sh >$OUT/build.log 2>&1
