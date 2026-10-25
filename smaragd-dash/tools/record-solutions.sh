#!/bin/sh
# Records the own caves of a disk being solved, one after the other, in
# their first level: build/<disk>-solutions.mp4. Each slot's way through
# is found by tools/solve.c (tools/democave.py solve), from where the moves
# of <moves dir>/NN.moves end, if that file is there (for what the search
# cannot find by itself: dropping boulders on purpose, say; it can also
# give the search its settings). A slot without a way through is left out
# of the video. The game is
# built with -DSCREENCAST -DTOUR, the ways go onto its disk as TOUR01, ...,
# the caves from the given disk into its slots; it plays them and tells the
# emulator to stop after the last. The normal build is made again
# afterwards.
#
#   tools/record-solutions.sh <disk.d81> [<moves dir>] [-- mega65-cast options]
#
#   tools/record-solutions.sh build/Boulder_Dash_1.d81 solutions/Boulder_Dash_1

set -e
cd "$(dirname "$0")/.."
SRC=$(realpath "$1")
shift
MOVES=""
if [ $# -gt 0 ] && [ "$1" != -- ]; then
    MOVES=$(realpath "$1")
    shift
fi
[ "$1" = -- ] && shift
CAST_OPTS="$*"  # without spaces in them
NAME=$(basename "$SRC" .d81)
WORK=build/solutions
rm -rf build/tour $WORK
mkdir -p build/tour $WORK

# build/solve, which the search needs
./build.sh >$WORK/build.log 2>&1 || { tail $WORK/build.log; exit 1; }
SLOTS=$(python3 -c "
import sys; sys.path.insert(0, 'tools')
import cavekit as ck
d = ck.Disk(sys.argv[1])
print(' '.join(str(i + 1) for i, s in enumerate(d.slots()) if ck.read_slot(d, s)))
" "$SRC")
python3 -c "import sys; sys.path.insert(0, 'tools'); import democave; democave.library()"
# the slots at once (the search takes minutes), each into its log
for slot in $SLOTS; do
    set -- solve "$SRC" build/tour/tour$slot.bin --cave "${slot#0}"
    [ -n "$MOVES" ] && [ -f "$MOVES/$slot.moves" ] && set -- "$@" --moves "$MOVES/$slot.moves"
    python3 tools/democave.py "$@" >$WORK/solve$slot.log 2>&1 &
done
wait
for slot in $SLOTS; do
    cat $WORK/solve$slot.log
    [ -f build/tour/tour$slot.bin ] || echo "slot $slot is left out of the video" >&2
done

SMARAGD_CFLAGS="-DSCREENCAST -DTOUR $SMARAGD_CFLAGS" ./build.sh >$WORK/build.log 2>&1 ||
    { tail $WORK/build.log; exit 1; }
# the caves of the disk into the slots of the game's (same version: same files)
DISK=$WORK/$NAME.d81
cp build/smaragd-dash.d81 $DISK
python3 -c "
import sys; sys.path.insert(0, 'tools')
import cavekit as ck
src, dst = ck.Disk(sys.argv[1]), ck.Disk(sys.argv[2])
for name in src.files():
    if name.startswith(ck.SLOT) and dst.has(name):
        dst.rewrite(name, src.read(name))
dst.save()
" "$SRC" $DISK
mkdir -p build/cast-tmp
TMPDIR=$PWD/build/cast-tmp ../toolchain/tools/bin/mega65-cast -x 1 -s 2 -t 3600 $CAST_OPTS \
    -o "$PWD/build/$NAME-solutions.mp4" $DISK
./build.sh >$WORK/build.log 2>&1
