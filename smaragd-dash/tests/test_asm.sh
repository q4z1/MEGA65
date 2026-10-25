#!/bin/sh
# The assembler of the game against the C it comes from: the build with
# -DASM_CHECK plays the music with src/music.s and src/music.c (4000 frames
# as PAL and 4000 as NTSC) and the sounds with src/sound.s and src/sound.c
# (6000 times random events of a tick, now and then a sound of its own,
# two frames; both get the same random numbers), each into a copy of the
# SIDs' registers, and counts the frames where the copies (or the random
# numbers taken) differ; the same for covering the cave (src/cover.s and
# cover_cells_c in src/main.c, 400 times); Xemu dumps the memory at the end. The normal
# build is made again afterwards.
#
#   tests/test_asm.sh

set -e
cd "$(dirname "$0")/.."
OUT=build/test
mkdir -p $OUT
SMARAGD_CFLAGS="-DASM_CHECK" ./build.sh >$OUT/build.log 2>&1 || { tail $OUT/build.log; exit 1; }
rm -f $OUT/asm.mem
SDL_AUDIODRIVER=dummy timeout 300 ../toolchain/tools/bin/xmega65 -headless -sleepless -testing -besure \
    -8 build/smaragd-dash.d81 -autoload -dumpmem $OUT/asm.mem >$OUT/xemu.log 2>&1 || true
set +e
python3 - $OUT/asm.mem <<'PY'
import subprocess, sys
nm = subprocess.run(["../toolchain/llvm-mos/bin/llvm-nm", "build/smaragd-dash.prg.elf"],
                    capture_output=True, text=True).stdout
at = {l.split()[2]: int(l.split()[0], 16) for l in nm.splitlines() if len(l.split()) == 3}
m = open(sys.argv[1], "rb").read()
word = lambda n: m[at[n]] | m[at[n] + 1] << 8
ok = True
for name, count, want in (("music", "frames", 8000), ("sound", "frames", 6000), ("cover", "runs", 400)):
    bad, n = word(f"{name}_bad"), word(f"{name}_{count}")
    print(f"{name}: {n} {count}, {bad} not as the C's", end="; " if name != "cover" else "\n")
    ok = ok and not bad and n == want
sys.exit(0 if ok else 1)
PY
status=$?
./build.sh >$OUT/build.log 2>&1
exit $status
