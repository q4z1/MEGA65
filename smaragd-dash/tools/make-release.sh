#!/bin/sh
# Makes the release: build/release/smaragd-dash-VERSION.zip with the disk
# (smaragd-dash.d81), the manuals (README.md, EDITOR.md) and
# tools/cavekit.py, for players without the repository. The disk is built
# afresh - the default high score table, the demo caves (demo/) in the
# first game's slots, no files of the test builds; the build's own disk,
# with the caves and high scores kept on it, is left as it was.
#
#   tools/make-release.sh

set -e
cd "$(dirname "$0")/.."
VERSION=$(cat VERSION)
OUT=build/release
DISK=build/smaragd-dash.d81
mkdir -p $OUT
rm -rf $OUT/zip
mkdir -p $OUT/zip

[ -f $DISK ] && mv $DISK $OUT/kept.d81
trap '[ -f $OUT/kept.d81 ] && mv $OUT/kept.d81 $DISK' EXIT
SMARAGD_CFLAGS= ./build.sh >$OUT/build.log 2>&1 || { tail $OUT/build.log; exit 1; }
cp $DISK $OUT/zip/smaragd-dash.d81
rm $DISK
python3 tools/cavekit.py import $OUT/zip/smaragd-dash.d81 demo/*.bd

cp README.md EDITOR.md tools/cavekit.py $OUT/zip/
cp $OUT/zip/smaragd-dash.d81 $OUT/smaragd-dash-$VERSION.d81
rm -f $OUT/smaragd-dash-$VERSION.zip
(cd $OUT/zip && zip -q -X ../smaragd-dash-$VERSION.zip smaragd-dash.d81 README.md EDITOR.md cavekit.py)
rm -rf $OUT/zip
echo "$OUT/smaragd-dash-$VERSION.zip:"
unzip -l $OUT/smaragd-dash-$VERSION.zip
