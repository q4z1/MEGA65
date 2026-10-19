#!/bin/sh
# Baut das Programm, zu dem die uebergebene Datei gehoert, fuer den MEGA65
# und startet es in Xemu.
#
# Ein Programm ist ein Ordner (main/, ...). Bringt er ein eigenes build.sh
# mit, baut das; sonst werden alle .c- und .s-Dateien direkt im Ordner mit
# llvm-mos zu build/<ordner>.prg uebersetzt.
#
# Aufruf: run-current.sh <pfad/zur/datei>
#   MEGA65_RUN=0       nur bauen, nicht starten
#   MEGA65_PRG=<name>  ein anderes Programm aus build/ starten

set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TC="$ROOT/toolchain"
CC="$TC/llvm-mos/bin/mos-mega65-clang"
SRC="$1"

if [ -z "$SRC" ] || [ ! -e "$SRC" ]; then
    echo "Fehler: keine Datei uebergeben oder '$SRC' existiert nicht." >&2
    echo "In VS Code muss eine Datei des Programms im Editor aktiv sein." >&2
    exit 1
fi

# Programmordner: der naechste Ordner nach oben mit build.sh, sonst der
# Ordner der Datei selbst (oder der uebergebene Ordner)
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
        echo "Fehler: '$SRC' gehoert zu keinem Programmordner." >&2
        exit 1
        ;;
esac

NAME=$(basename "$DIR")
OUT="$DIR/build"
mkdir -p "$OUT"

if [ -f "$DIR/build.sh" ]; then
    echo "Baue $NAME ueber $DIR/build.sh ..."
    MEGA65_CC="$CC" sh "$DIR/build.sh"
else
    # Eigene Compilerschalter: Datei cflags im Programmordner
    EXTRA=""
    [ -f "$DIR/cflags" ] && EXTRA=$(cat "$DIR/cflags")
    set --
    for f in "$DIR"/*.c "$DIR"/*.s; do
        [ -f "$f" ] && set -- "$@" "$f"
    done
    if [ $# = 0 ]; then
        echo "Fehler: keine .c- oder .s-Dateien in $DIR." >&2
        exit 1
    fi
    echo "Baue $NAME ..."
    # -g und die .elf-Datei fuer Disassembly/Symbole, .map fuer die Belegung
    # shellcheck disable=SC2086
    "$CC" -Os -g -Wall $EXTRA -o "$OUT/$NAME.prg" \
        -Wl,-Map="$OUT/$NAME.map" "$@"
fi
START=${MEGA65_PRG:-$NAME}
echo "Fertig: $OUT/$START.prg"

[ "$MEGA65_RUN" = 0 ] && exit 0

echo "Starte Xemu ..."
exec "$TC/tools/bin/xmega65" -prg "$OUT/$START.prg"
