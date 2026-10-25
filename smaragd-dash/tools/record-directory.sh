#!/bin/sh
# Records the disk's directory as BASIC shows it, and the game started from
# there and left again: build/disk-directory.mp4. Xemu starts BASIC with
# the disk in drive 8 (mega65-cast -b) and runs a little program (its
# -importbas): the disk's directory with the partitions CAVES, OWN1, OWN2
# and OWN3, then into CAVES and OWN1 (the DOS command /0:NAME) with the
# first files of each, back, and RUN "SMARAGD DASH". The game is built with
# -DBASIC_DEMO: on the title it presses Run/Stop twice by itself, after 3
# and 4 seconds - back to BASIC. The normal build is made again afterwards.
#
#   tools/record-directory.sh

set -e
cd "$(dirname "$0")/.."
WORK=build/cast-tmp
mkdir -p $WORK
SMARAGD_CFLAGS="-DBASIC_DEMO" ./build.sh >$WORK/directory-build.log 2>&1 || { tail $WORK/directory-build.log; exit 1; }
cp build/smaragd-dash.d81 $WORK/directory.d81
cat >$WORK/directory.bas <<'BASIC'
10 SCNCLR:PRINT "THE DISK - THE CAVES AND THREE GAMES OF OWN CAVES ARE PARTITIONS (CBM):":PRINT:DIR:SLEEP 8
20 OPEN 1,8,15
30 PRINT#1,"/0:CAVES":SCNCLR:PRINT "IN THE PARTITION CAVES: CAVE01-1 TO CAVE25-4 (CAVE, LEVEL). THE FIRST:":PRINT:DIR "CAVE01*":SLEEP 7
40 PRINT#1,"/":PRINT#1,"/0:OWN1":SCNCLR:PRINT "IN THE PARTITION OWN1 (A GAME): 20 SLOTS IN 5 LEVELS. THE FIRST:":PRINT:DIR "OWN01*":SLEEP 7
50 PRINT#1,"/":CLOSE 1:SCNCLR:PRINT "BACK IN THE DISK'S OWN DIRECTORY:":PRINT:DIR:SLEEP 6
60 PRINT:PRINT "AND THE GAME, LEFT WITH RUN/STOP TWICE:":SLEEP 3:RUN "SMARAGD DASH"
BASIC
TMPDIR=$PWD/$WORK ../toolchain/tools/bin/mega65-cast -b -t 42 -o "$PWD/build/disk-directory.mp4" \
    $WORK/directory.d81 -- -importbas "$PWD/$WORK/directory.bas"
./build.sh >$WORK/directory-build.log 2>&1
