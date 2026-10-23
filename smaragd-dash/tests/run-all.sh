#!/bin/sh
# All of Smaragd Dash's tests, one after the other, with a line for each and
# a summary at the end; the log of each in build/test/NAME.log.
#
#   tests/run-all.sh           the host's tests (a minute) and those in Xemu
#                              (some 15 minutes)
#   tests/run-all.sh --host    the host's only
#
# Host: tools/cavekit.py, GDash's engine against GDash itself (a few games
# with pseudo-random input, tests/test_gdengine.sh) and every mechanic of
# it (tests/test_mechanics.py), the build with the solver. Xemu: the engine
# as the MEGA65 runs it against the host (tests/test_gdmega65.py, with the
# mechanics' scenarios), the DMA jobs of render.s against the C loop over
# all 25 caves of level 1 (tests/test_render.sh, which also has the
# screencast build solve them), the same for 6 caves with a floppy
# controller that fails every third try (-DDISK_FLAKY: the loader must ask
# again) and an NMI in every frame (-DNMI_STORM, as Restore gives), the editor (tests/test_editor.sh), and the game's flow from the
# title to the high score table on the disk (tests/test_flow.py).
# They all build into build/, so they run one by one; the normal build is
# made again at the end.

cd "$(dirname "$0")/.."
OUT=build/test
mkdir -p $OUT
failed=0
passed=0

run() {
    name=$1
    shift
    start=$(date +%s)
    if "$@" >$OUT/$name.log 2>&1; then
        passed=$((passed + 1))
        result=ok
    else
        failed=$((failed + 1))
        result=FAIL
    fi
    printf '%-5s %-12s %4ss  %s\n' $result "$name" $(($(date +%s) - start)) "$(tail -1 $OUT/$name.log)"
}

run build ./build.sh
run cavekit python3 tests/test_cavekit.py
run gdengine tests/test_gdengine.sh
run mechanics python3 tests/test_mechanics.py
if [ "$1" != --host ]; then
    run gdmega65 python3 tests/test_gdmega65.py
    run render tests/test_render.sh 25
    run flakydisk env RENDER_CFLAGS="-DDISK_FLAKY -DNMI_STORM" tests/test_render.sh 6
    run editor tests/test_editor.sh
    run flow python3 tests/test_flow.py
fi
./build.sh >$OUT/build.log 2>&1
echo "$passed passed, $failed failed (logs in $OUT)"
[ $failed -eq 0 ]
