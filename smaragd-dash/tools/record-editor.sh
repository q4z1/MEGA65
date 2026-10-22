#!/bin/sh
# Records the video of the cave editor, build/cave-editor.mp4 (copied to
# screenshots/cave-editor.mp4 by hand): the game built with -DEDITDEMO
# plays the editor's script in src/main.c (test_script) on a disk whose
# slots 1-3 hold the caves of tools/editor-demo and caves/04-butterflies.cave
# - loading slots, the help page, putting and drawing elements, values and
# name, trying the changed cave to its exit, saving it and loading it
# again - and tells the emulator to stop at its end. With --shots it takes
# the pictures of EDITOR.md instead: built with -DEDITTEST=n the script
# stops at its n-th SHOT, and Xemu's screenshot of it, cut to the screen,
# goes to screenshots/editor-<name>.png. The normal build is made again
# afterwards.
#
#   tools/record-editor.sh [--shots]

set -e
cd "$(dirname "$0")/.."
DISK=build/editor-demo.d81
SHOTS="cave gdash new help changed values try saved title"  # in the script's order

# The game with the script, and a disk with the caves in its slots
prepare() {
    SMARAGD_CFLAGS="-DEDITDEMO $1 $SMARAGD_CFLAGS" ./build.sh >build/editor-demo.log 2>&1 ||
        { tail build/editor-demo.log; exit 1; }
    cp build/smaragd-dash.d81 $DISK
    python3 tools/cavekit.py empty $DISK >/dev/null
    python3 tools/cavekit.py import $DISK tools/editor-demo/1-old-shaft.cave caves/04-butterflies.cave \
        tools/editor-demo/3-gdash-elements.bd >/dev/null
}

if [ "$1" = --shots ]; then
    n=0
    for name in $SHOTS; do
        n=$((n + 1))
        prepare "-DEDITTEST=$n"
        rm -f build/editor-shot.png
        SDL_AUDIODRIVER=dummy timeout 300 ../toolchain/tools/bin/xmega65 -headless -sleepless -testing \
            -besure -8 $DISK -autoload -screenshot build/editor-shot.png >build/editor-demo.log 2>&1 || true
        [ -f build/editor-shot.png ] || { echo "shot $n: no screenshot" >&2; exit 1; }
        # the screen without the border, as the other pictures
        python3 -c "
import sys
from PIL import Image
Image.open(sys.argv[1]).crop((96, 100, 704, 508)).save(sys.argv[2])
" build/editor-shot.png screenshots/editor-$name.png
        echo "screenshots/editor-$name.png"
    done
else
    prepare ""
    ../toolchain/tools/bin/mega65-cast -x 1 -s 2 -o build/cave-editor.mp4 $DISK
fi
./build.sh >build/editor-demo.log 2>&1
