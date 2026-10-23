#!/bin/sh
# Records the demo caves being solved: build/tour.mp4. The caves of
# demo/*.bd (in the order of their names) go into the slots of a disk of the
# game built with -DSCREENCAST -DTOUR, their moves (demo/<name>.moves,
# checked and packed by tools/democave.py) onto it as TOUR01, TOUR02, ...;
# the game plays them one after the other and tells the emulator to stop
# after the last. The normal build is made again afterwards.
#
#   tools/record-tour.sh [demo/NAME.bd ...]

set -e
cd "$(dirname "$0")/.."
[ $# -gt 0 ] || set -- demo/*.bd
rm -rf build/tour
mkdir -p build/tour
n=0
for bd in "$@"; do
    n=$((n + 1))
    python3 tools/democave.py pack "$bd" "${bd%.bd}.moves" "$(printf 'build/tour/tour%02d.bin' $n)" | tail -1
done
SMARAGD_CFLAGS="-DSCREENCAST -DTOUR $SMARAGD_CFLAGS" ./build.sh >build/tour/build.log 2>&1 ||
    { tail build/tour/build.log; exit 1; }
DISK=build/tour/tour.d81
cp build/smaragd-dash.d81 $DISK
python3 tools/cavekit.py empty $DISK >/dev/null
python3 tools/cavekit.py import $DISK "$@" | tail -1
../toolchain/tools/bin/mega65-cast -x 1 -s 2 -o "$PWD/build/tour.mp4" $DISK
./build.sh >build/tour/build.log 2>&1
