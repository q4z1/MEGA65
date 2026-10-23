#!/bin/sh
# The playfield's DMA jobs of src/render.s against the C loop they come
# from (video_render, src/video.c): the screencast build (-DSCREENCAST, the
# game plays its first caves by itself) with -DRENDER_CHECK makes each
# frame's jobs both ways and counts the frames where they differ; Xemu
# dumps the memory at the end. The screencast must get through all those
# caves (it stops at the first one Rockford does not get out of). The
# normal build is made again afterwards.
#
#   tests/test_render.sh [caves]      (default: the first 6)
#
# $RENDER_CFLAGS goes into the build as well (tests/run-all.sh: -DDISK_FLAKY,
# the loader with a controller that fails every third try, and -DNMI_STORM,
# an NMI somewhere in every frame).

set -e
cd "$(dirname "$0")/.."
OUT=build/test
mkdir -p $OUT
CAVES=${1:-6}
SMARAGD_CFLAGS="-DSCREENCAST -DRENDER_CHECK -DDEMO_LAST=$CAVES $RENDER_CFLAGS" ./build.sh >$OUT/build.log 2>&1 ||
    { tail $OUT/build.log; exit 1; }
rm -f $OUT/render.mem
SDL_AUDIODRIVER=dummy timeout 1200 ../toolchain/tools/bin/xmega65 -headless -sleepless -testing -besure \
    -8 build/smaragd-dash.d81 -autoload -dumpmem $OUT/render.mem >$OUT/xemu.log 2>&1 || true
python3 - $OUT/render.mem $CAVES <<'PY'
import subprocess, sys
nm = subprocess.run(["../toolchain/llvm-mos/bin/llvm-nm", "build/smaragd-dash.prg.elf"],
                    capture_output=True, text=True).stdout
at = {l.split()[2]: int(l.split()[0], 16) for l in nm.splitlines() if len(l.split()) == 3}
m = open(sys.argv[1], "rb").read()
word = lambda n: m[at[n]] | m[at[n] + 1] << 8
bad, frames = word("render_bad"), word("render_frames")
done, caves = m[at["cave_no"]], int(sys.argv[2])
print(f"{done} of {caves} caves solved, {frames} frames, {bad} with other jobs than the C loop's")
sys.exit(1 if bad or not frames or done != caves else 0)
PY
status=$?
./build.sh >$OUT/build.log 2>&1
exit $status
