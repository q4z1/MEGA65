#!/bin/sh
# Takes the pictures of the README: screenshots/title.png (the title),
# cave.png (the screencast in the first cave) and explosion.png (a boulder
# falls onto Rockford in the first cave: the moves of tools/shots/, played
# by the -DTOUR build). Each is Xemu's -screenshot at the moment the game,
# built with -DSHOT_AT=n, tells it to stop: after n frames. The pictures of
# EDITOR.md come from tools/record-editor.sh --shots. The normal build is
# made again afterwards.
#
#   tools/record-shots.sh

set -e
cd "$(dirname "$0")/.."
OUT=build/shots
mkdir -p $OUT

# shot NAME FRAMES CFLAGS [CAVE.bd MOVES]: screenshots/NAME.png
shot() {
    SMARAGD_CFLAGS="-DSHOT_AT=$2 $3" ./build.sh >$OUT/build.log 2>&1 || { tail $OUT/build.log; exit 1; }
    cp build/smaragd-dash.d81 $OUT/shot.d81
    if [ -n "$4" ]; then
        python3 tools/cavekit.py empty $OUT/shot.d81 >/dev/null
        python3 tools/cavekit.py import $OUT/shot.d81 "$4" >/dev/null
    fi
    rm -f $OUT/shot.png
    SDL_AUDIODRIVER=dummy timeout 300 ../toolchain/tools/bin/xmega65 -headless -sleepless -testing \
        -besure -8 $OUT/shot.d81 -autoload -screenshot $OUT/shot.png >$OUT/xemu.log 2>&1 || true
    [ -f $OUT/shot.png ] || { echo "$1: no screenshot" >&2; exit 1; }
    # the screen without the border, as the other pictures
    python3 -c "
import sys
from PIL import Image
Image.open(sys.argv[1]).crop((96, 100, 704, 508)).save(sys.argv[2])
" $OUT/shot.png screenshots/$1.png
    echo "screenshots/$1.png"
}

shot title 30 "-DSCREENCAST"
shot cave 1450 "-DSCREENCAST"
# the explosion's moves, from the start of the cave, as the tour loads them
rm -rf build/tour
mkdir -p build/tour
python3 -c "
import sys
sys.path.insert(0, 'tools')
import democave as dc
p, _, _ = dc.play('caves/01-first-steps.bd', 'tools/shots/explosion.moves', quiet=True)
open('build/tour/tour01.bin', 'wb').write(dc.pack(p.inputs))
"
shot explosion 566 "-DSCREENCAST -DTOUR" caves/01-first-steps.bd
rm -rf build/tour
./build.sh >$OUT/build.log 2>&1
