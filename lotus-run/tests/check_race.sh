#!/bin/sh
# Builds tests/check_race.c (the race logic in assembly against its C
# reference, on the MEGA65), runs it in Xemu without a window and reports
# what it found. Needs a build (build.sh) first.
#
#   tests/check_race.sh [SECONDS]      (how long Xemu may take, default 120)

set -e
cd "$(dirname "$0")/.."
SECONDS_MAX=${1:-120}
TC=../toolchain
CC=${MEGA65_CC:-$TC/llvm-mos/bin/mos-mega65-clang}
OUT=build/check
mkdir -p $OUT
REF="-Drace_frame=ref_race_frame -Drace_picture=ref_race_picture -Drace_random=ref_race_random -Drace_seg_lookup=ref_race_seg_lookup"
# shellcheck disable=SC2086
"$CC" -O2 -Wall -Isrc -Ibuild/gen $REF -c -o $OUT/ref_race.o src/ref/race.c
"$CC" -Os -g -Wall -Isrc -Ibuild/gen -T link.ld -o $OUT/check.prg tests/check_race.c src/race.s \
    src/race_setup.c src/race_data.c src/disk.c src/dma.c src/irq.s build/gen/progdata.c build/gen/courses.c $OUT/ref_race.o
set --
for f in build/disk/TRACK*; do
    set -- "$@" "$f=$(basename "$f")"
done
$TC/tools/bin/mkd81.py $OUT/check.d81 "CHECK RACE" "$OUT/check.prg=CHECK" "$@" > /dev/null
rm -f $OUT/mem.bin
timeout -s INT "$SECONDS_MAX" $TC/tools/bin/xmega65 -headless -sleepless -testing -8 "$(pwd)/$OUT/check.d81" -autoload \
    -dumpmem "$(pwd)/$OUT/mem.bin" > /dev/null 2>&1 || true
python3 - "$OUT" <<'EOS'
import struct, subprocess, sys
out = sys.argv[1]
nm = subprocess.run(['../toolchain/llvm-mos/bin/llvm-nm', out + '/check.prg.elf'],
                    capture_output=True, text=True).stdout
sym = {l.split()[2]: int(l.split()[0], 16) for l in nm.splitlines() if len(l.split()) == 3}
m = open(out + '/mem.bin', 'rb').read()
get = lambda n, f: struct.unpack_from(f, m, sym[n])[0]
frames, done = get('check_frames', '<I'), get('check_done', '<B')
failed = get('check_failed', '<H')
if failed:
    print(f"DIFFERENT: configuration {failed - 1}, frame {get('check_fail_frame', '<I')}, "
          f"{['', 'race_frame', 'race_picture', 'loading'][get('check_fail_what', '<B')]}, "
          f"Race byte ${get('check_fail_offset', '<H'):X} ({frames} frames the same before)")
    sys.exit(1)
print(f"{frames} frames the same" + ("" if done else " (not finished: give it more time)"))
sys.exit(0 if done else 1)
EOS
