#!/bin/sh
# How smooth the caves play: the screencast build with -DSCROLLPROF plays
# the caves with their moves in Xemu, and
# what it counted is read from Xemu's memory dump: frames dropped (by cave),
# the view's steps in pixels per frame, the raster lines the game's work
# before video_sync and the drawing before video_show took, and the most a
# step of GDash's engine took. The normal build is made again at the end.
#
#   tools/scroll-profile.sh [cflags]   e.g. "-DDEMO_FIRST=20 -DDEMO_LAST=21"

set -e
cd "$(dirname "$0")/.."
OUT=build/test
mkdir -p $OUT
SMARAGD_CFLAGS="-DSCREENCAST -DSCROLLPROF $1" ./build.sh >$OUT/profile-build.log 2>&1 ||
    { tail $OUT/profile-build.log; exit 1; }
cp build/smaragd-dash.d81 $OUT/profile.d81
rm -f $OUT/profile.bin
SDL_AUDIODRIVER=dummy timeout 1800 ../toolchain/tools/bin/xmega65 -headless -sleepless -testing -besure \
    -8 $OUT/profile.d81 -autoload -dumpmem $OUT/profile.bin >$OUT/profile-xemu.log 2>&1 || true
python3 - $OUT/profile.bin build/smaragd-dash.prg.elf ../toolchain/llvm-mos/bin/llvm-nm <<'PY'
import struct
import subprocess
import sys

dump = open(sys.argv[1], "rb").read()
syms = {}
for line in subprocess.run([sys.argv[3], sys.argv[2]], capture_output=True, text=True).stdout.splitlines():
    p = line.split()
    if len(p) == 3:
        syms[p[2]] = int(p[0], 16)


def words(name, n):
    a = syms[name]
    return list(struct.unpack("<%dH" % n, dump[a:a + 2 * n]))


print("loops by the frames they took (1, 2, 3, more):", words("sp_frames", 4))
print("frames dropped while Rockford lives, by cave:",
      {i + 1: v for i, v in enumerate(words("sp_drop", 26)) if v} or "none")
print("the view's steps (pixels: frames):", {i: v for i, v in enumerate(words("sp_step", 17)) if v})
print("the game before video_sync (1 ms each):", words("sp_logic", 20), "too late:", words("sp_sync_late", 1)[0])
print("the drawing before video_show (1 ms each):", words("sp_draw", 20), "too late:", words("sp_show_late", 1)[0])
print("the most raster lines (32 us) a step of GDash's engine took:", words("sp_step_lines", 1)[0])
print("... by cave:", {i + 1: v for i, v in enumerate(words("sp_cave_lines", 26)) if v})
PY
./build.sh >$OUT/profile-build.log 2>&1
