#!/bin/sh
# GDash's engine as the game has it (src/gdengine.c), against GDash itself:
# the caves of GDash's own collection, made by tools/cavekit.py and started
# and played by the port on the host (tests/gdplay.c, built with
# GD_EXACT: GDash's random numbers), must start and play step by step as
# GDash's own code has them (toolchain/tools/bin/gdash-oracle, built by
# toolchain/tools/build-tools.sh, with the caves in toolchain/tools/src/gdash).
#
#   tests/test_gdengine.sh           a few of them, level 1, 300 steps
#   tests/test_gdengine.sh --all     all 200 files, all five levels (an hour)
#   tests/test_gdengine.sh --gds     the ~1850 C64 games (.gds) GDash imports,
#                                    as GDash saves them as .bd, level 1,
#                                    200 steps (hours). Two caves differ:
#                                    Bilder_Dash cave 16 (GDash saves a
#                                    probability rounded to 4 places) and
#                                    Crazy_Dream_7 cave 3 (its amoeba starts
#                                    "scanned", which a slot cannot hold: it
#                                    grows a step later)

set -e
cd "$(dirname "$0")/.."
ORACLE=../toolchain/tools/bin/gdash-oracle
CAVES=../toolchain/tools/src/gdash/caves
[ -x $ORACLE ] || { echo "no $ORACLE: toolchain/tools/build-tools.sh" >&2; exit 1; }
mkdir -p build/gen build/caves
python3 tools/mkcave.py build/caves build/gen caves/*.cave >/dev/null
cc -O2 -Wall -Wno-array-bounds -DGD_EXACT -Isrc -Ibuild/gen -o build/gdplay \
    tests/gdplay.c src/gdengine.c build/gen/gdcave.c
if [ "$1" = --all ]; then
    find $CAVES -name "*.bd" | sort | xargs python3 tests/gdcompare.py $ORACLE build/gdplay 1,2,3,4,5 400
elif [ "$1" = --gds ]; then
    find $CAVES -name "*.gds" | sort | xargs python3 tests/gdcompare.py $ORACLE build/gdplay 1 200
else
    python3 tests/gdcompare.py $ORACLE build/gdplay 1 300 \
        $CAVES/First_Star_Software/Boulder_Dash_1.bd $CAVES/First_Star_Software/Boulder_Dash_2.bd \
        $CAVES/Thomas_Mauritz/Emerald_Dash_1.bd $CAVES/Marek_Roth/Crazy_Dream/Crazy_Dream_8.bd \
        $CAVES/Marek_Roth/Crazy_Dream/Crazy_Dream_9.bd $CAVES/Sendy/Crli_Caves.bd \
        $CAVES/Dustin/Rock_Fort_3_-_Rockford_s_Dream.bd tests/cavekit/objects.bd
fi
