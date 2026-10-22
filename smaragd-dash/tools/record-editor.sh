#!/bin/sh
# Records the video of the cave editor, build/cave-editor.mp4 (copied to
# screenshots/cave-editor.mp4 by hand): the game built with -DEDITDEMO
# plays the editor's script in src/main.c (test_script) on a disk whose
# slots 1-3 hold the caves of tools/editor-demo and caves/04-butterflies.cave
# - loading slots, the help page, putting and drawing elements, values and
# name, trying the changed cave to its exit, saving it and loading it
# again - and tells the emulator to stop at its end. The normal build is
# made again afterwards.
#
#   tools/record-editor.sh

set -e
cd "$(dirname "$0")/.."
DISK=build/editor-demo.d81
SMARAGD_CFLAGS="-DEDITDEMO $SMARAGD_CFLAGS" ./build.sh >build/editor-demo.log 2>&1 ||
    { tail build/editor-demo.log; exit 1; }
cp build/smaragd-dash.d81 $DISK
python3 tools/cavekit.py empty $DISK >/dev/null
python3 tools/cavekit.py import $DISK tools/editor-demo/1-old-shaft.cave caves/04-butterflies.cave \
    tools/editor-demo/3-gdash-elements.bd
../toolchain/tools/bin/mega65-cast -x 1 -s 2 -o build/cave-editor.mp4 $DISK
./build.sh >build/editor-demo.log 2>&1
