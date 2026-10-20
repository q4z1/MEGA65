#!/bin/sh
# Builds tests/check_render.c (the renderer's assembly against its C
# references, on the MEGA65), runs it in Xemu without a window and reports
# what it found. Needs a build (build.sh) first.
#
#   tests/check_render.sh [SECONDS]      (how long Xemu may take, default 120)

set -e
cd "$(dirname "$0")/.."
SECONDS_MAX=${1:-120}
TC=../toolchain
CC=${MEGA65_CC:-$TC/llvm-mos/bin/mos-mega65-clang}
OUT=build/check
mkdir -p $OUT
# Without link-time optimization: with it, llvm-mos got this program wrong
# (road_lines read garbage once the pattern check was inlined into main).
"$CC" -O2 -Wall -fno-lto -Isrc -Ibuild/gen -Droad_draw=ref_road_draw -c -o $OUT/ref_road_draw.o src/ref/road_draw.c
"$CC" -O2 -Wall -fno-lto -Isrc -Ibuild/gen -Dsprites_draw=ref_sprites_draw -c -o $OUT/ref_sprites_draw.o \
    src/ref/sprites_draw.c
"$CC" -Os -g -Wall -fno-lto -Isrc -Ibuild/gen -T link.ld -o $OUT/check_render.prg tests/check_render.c src/render.s \
    src/road.c src/road_draw.c src/road_pixels.c src/road_rows.c src/road_rows.s src/irq.s src/banks.c src/fb_mega65.c src/disk.c src/dma.c build/gen/tables.c \
    build/gen/roadpat.c build/gen/sprbanks.c $OUT/ref_road_draw.o $OUT/ref_sprites_draw.o
set --
for f in build/disk/TRACK* build/disk/SPR*; do
    set -- "$@" "$f=$(basename "$f")"
done
$TC/tools/bin/mkd81.py $OUT/check_render.d81 "CHECK RENDER" "$OUT/check_render.prg=CHECK" "$@" > /dev/null
rm -f $OUT/mem.bin
timeout -s INT "$SECONDS_MAX" $TC/tools/bin/xmega65 -headless -sleepless -testing -8 "$(pwd)/$OUT/check_render.d81" \
    -autoload -dumpmem "$(pwd)/$OUT/mem.bin" > /dev/null 2>&1 || true
python3 - "$OUT" <<'EOS'
import struct, subprocess, sys
out = sys.argv[1]
nm = subprocess.run(['../toolchain/llvm-mos/bin/llvm-nm', out + '/check_render.prg.elf'],
                    capture_output=True, text=True).stdout
sym = {l.split()[2]: int(l.split()[0], 16) for l in nm.splitlines() if len(l.split()) == 3}
m = open(out + '/mem.bin', 'rb').read()
get = lambda n, f: struct.unpack_from(f, m, sym[n])[0]
views, done, failed = get('check_views', '<I'), get('check_done', '<B'), get('check_failed', '<B')
if failed:
    what = ['', 'picture', '', 'loading', 'sprites', 'road line pattern'][failed]
    print(f"DIFFERENT: {what}, course {get('check_fail_course', '<B')}, "
          f"position ${get('check_fail_pos', '<I'):08X}, lateral {get('check_fail_lateral', '<h')}, "
          f"picture byte {get('check_fail_offset', '<H')} ({views} views the same before)")
    sys.exit(1)
sets, rows = get('check_sprite_sets', '<I'), get('check_rows', '<H')
print(f"{rows} road line patterns, {sets} sprite lists and {views} views the same" +
      ("" if done else " (not finished: give it more time)"))
sys.exit(0 if done else 1)
EOS
