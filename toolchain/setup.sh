#!/bin/sh
# Richtet die komplette Werkzeugkette unter toolchain/ ein. Was schon da
# ist, wird uebersprungen; jeder Schritt laesst sich auch einzeln aufrufen.
#
#   llvm-mos/            C-Compiler, Assembler, Linker (Ziel mos-mega65)
#   tools/               Hilfswerkzeuge (tools/build-tools.sh)
#   xemu/build/bin/      Xemu, aus dem Git-Checkout gebaut
#   rom/MEGA65.ROM       das ROM (rom/build-rom.sh)
#
# Aufruf: toolchain/setup.sh

set -e

TC=$(cd "$(dirname "$0")" && pwd)
DL="$TC/downloads"
LLVM_MOS_VERSION=v23.3.0

mkdir -p "$DL"

if [ ! -x "$TC/llvm-mos/bin/mos-mega65-clang" ]; then
    echo "== llvm-mos $LLVM_MOS_VERSION"
    if [ ! -f "$DL/llvm-mos-linux.tar.xz" ]; then
        curl -L --fail -o "$DL/llvm-mos-linux.tar.xz" \
            "https://github.com/llvm-mos/llvm-mos-sdk/releases/download/$LLVM_MOS_VERSION/llvm-mos-linux.tar.xz"
    fi
    tar xf "$DL/llvm-mos-linux.tar.xz" -C "$TC"
fi

echo "== Hilfswerkzeuge"
"$TC/tools/build-tools.sh"

if [ ! -x "$TC/xemu/build/bin/xmega65.native" ]; then
    echo "== Xemu"
    # Git-Submodul; nach einem Klon ohne --recursive ist der Ordner leer
    if [ ! -f "$TC/xemu/Makefile" ]; then
        git -C "$TC/.." submodule update --init toolchain/xemu
    fi
    make -C "$TC/xemu" -j"$(nproc)"
fi

if [ ! -f "$TC/rom/MEGA65.ROM" ]; then
    echo "== MEGA65.ROM"
    "$TC/rom/build-rom.sh"
fi

# Das ROM auch in Xemus Datenordner legen: "Update files on SD image" im
# Xemu-Menue nimmt es dann ohne Dateiauswahl (siehe README).
XEMU_DATA="$HOME/.local/share/xemu-lgb/mega65"
if [ ! -f "$XEMU_DATA/MEGA65.ROM" ]; then
    mkdir -p "$XEMU_DATA"
    cp "$TC/rom/MEGA65.ROM" "$XEMU_DATA/MEGA65.ROM"
fi

echo "Alles bereit."
