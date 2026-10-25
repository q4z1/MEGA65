#!/bin/sh
# Records the disk's directory as BASIC shows it: build/disk-directory.mp4.
# Xemu starts BASIC with the disk in drive 8 (mega65-cast -b) and runs a
# little program (its -importbas): the disk's directory with the partitions
# CAVES, OWN1, OWN2 and OWN3, then into CAVES and OWN1 (the DOS command
# /0:NAME) with the first files of each, and back.
#
#   tools/record-directory.sh [<disk.d81>]   (default: build/smaragd-dash.d81)

set -e
cd "$(dirname "$0")/.."
DISK=$(realpath "${1:-build/smaragd-dash.d81}")
WORK=build/cast-tmp
mkdir -p $WORK
cp "$DISK" $WORK/directory.d81
cat >$WORK/directory.bas <<'EOF'
10 SCNCLR:PRINT "THE DISK - THE CAVES AND THREE GAMES OF OWN CAVES ARE PARTITIONS (CBM):":PRINT:DIR:SLEEP 8
20 OPEN 1,8,15
30 PRINT#1,"/0:CAVES":SCNCLR:PRINT "IN THE PARTITION CAVES: CAVE01-1 TO CAVE25-4 (CAVE, LEVEL). THE FIRST:":PRINT:DIR "CAVE01*":SLEEP 7
40 PRINT#1,"/":PRINT#1,"/0:OWN1":SCNCLR:PRINT "IN THE PARTITION OWN1 (A GAME): 20 SLOTS IN 5 LEVELS. THE FIRST:":PRINT:DIR "OWN01*":SLEEP 7
50 PRINT#1,"/":CLOSE 1:SCNCLR:PRINT "BACK IN THE DISK'S OWN DIRECTORY:":PRINT:DIR:SLEEP 6
EOF
TMPDIR=$PWD/$WORK ../toolchain/tools/bin/mega65-cast -b -t 34 -o "$PWD/build/disk-directory.mp4" \
    $WORK/directory.d81 -- -importbas "$PWD/$WORK/directory.bas"
