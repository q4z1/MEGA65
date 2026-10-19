#!/bin/sh
# Builds the program the given file belongs to for the MEGA65 and starts it
# in Xemu.
#
# A program is a folder (main/, ...). If it brings its own build.sh, that
# builds it; otherwise all .c and .s files directly in the folder are built
# with llvm-mos into build/<folder>.prg.
#
# Usage: run-current.sh <path/to/file>
#   MEGA65_RUN=0       only build, don't start
#   MEGA65_PRG=<name>  start another program from build/

set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TC="$ROOT/toolchain"
# The compiler, recording its commands for clangd (see below)
CC="$TC/tools/bin/mega65-cc"
SRC="$1"

if [ -z "$SRC" ] || [ ! -e "$SRC" ]; then
    echo "Error: no file given, or '$SRC' does not exist." >&2
    echo "In VS Code, a file of the program must be active in the editor." >&2
    exit 1
fi

# Program folder: the nearest folder upwards with a build.sh, otherwise the
# file's own folder (or the folder given)
if [ -d "$SRC" ]; then
    DIR=$(cd "$SRC" && pwd)
else
    DIR=$(cd "$(dirname "$SRC")" && pwd)
fi
D=$DIR
while [ "$D" != "$ROOT" ] && [ "$D" != / ] && [ ! -f "$D/build.sh" ]; do
    D=$(dirname "$D")
done
[ -f "$D/build.sh" ] && DIR=$D
case "$DIR" in
    "$ROOT"|"$TC"|"$TC"/*|"$ROOT/.vscode")
        echo "Error: '$SRC' does not belong to a program folder." >&2
        exit 1
        ;;
esac

NAME=$(basename "$DIR")
OUT="$DIR/build"
mkdir -p "$OUT"

# Every compiler call leaves its commands in $MEGA65_CDB_DIR; after the build
# they become build/compile_commands.json, where clangd finds them for all
# files of the program (include paths, defines and flags of the real build).
export MEGA65_CDB_DIR="$OUT/.cdb"
rm -rf "$MEGA65_CDB_DIR"
merge_cdb() {
    if ls "$MEGA65_CDB_DIR"/*.json >/dev/null 2>&1; then
        # Each entry ends in "},"; the last comma has to go
        { echo "["; cat "$MEGA65_CDB_DIR"/*.json | sed '$ s/,[[:space:]]*$//'; echo "]"; } \
            > "$OUT/compile_commands.json"
    fi
    rm -rf "$MEGA65_CDB_DIR"
}
# also when the build fails - that is when clangd is needed most
trap merge_cdb EXIT

if [ -f "$DIR/build.sh" ]; then
    echo "Building $NAME via $DIR/build.sh ..."
    MEGA65_CC="$CC" sh "$DIR/build.sh"
else
    # Extra compiler flags: file cflags in the program folder
    EXTRA=""
    [ -f "$DIR/cflags" ] && EXTRA=$(cat "$DIR/cflags")
    set --
    for f in "$DIR"/*.c "$DIR"/*.s; do
        [ -f "$f" ] && set -- "$@" "$f"
    done
    if [ $# = 0 ]; then
        echo "Error: no .c or .s files in $DIR." >&2
        exit 1
    fi
    echo "Building $NAME ..."
    # -g and the .elf file for disassembly/symbols, .map for the memory layout
    # shellcheck disable=SC2086
    "$CC" -Os -g -Wall $EXTRA -o "$OUT/$NAME.prg" \
        -Wl,-Map="$OUT/$NAME.map" "$@"
fi
merge_cdb
trap - EXIT

START=${MEGA65_PRG:-$NAME}
echo "Done: $OUT/$START.prg"

[ "$MEGA65_RUN" = 0 ] && exit 0

echo "Starting Xemu ..."
exec "$TC/tools/bin/xmega65" -prg "$OUT/$START.prg"
