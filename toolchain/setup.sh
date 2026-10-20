#!/bin/sh
# Sets up the complete toolchain under toolchain/. Whatever is already there
# is skipped; each step can also be run on its own.
#
#   llvm-mos/            C compiler, assembler, linker (target mos-mega65)
#   tools/               helper tools (tools/build-tools.sh)
#   xemu/build/bin/      Xemu, built from the git checkout
#   rom/MEGA65.ROM       the ROM (rom/build-rom.sh)
#   vscode/              editor extensions (vscode/install-extensions.sh)
#   fonts/               free fonts (SIL Open Font License) for game screens
#
# Usage: toolchain/setup.sh

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

# Fonts for screens rendered at build time (Lotus Run's tools/mkpages.py):
# Exo 2, Rajdhani and Titillium Web from google/fonts, at a fixed commit
FONTS_COMMIT=47d54ca1ebb14fd864695f1d39dc734f39017c33
mkdir -p "$TC/fonts"
for f in "exo2/Exo2%5Bwght%5D.ttf:Exo2.ttf" "exo2/OFL.txt:Exo2-OFL.txt" \
         "rajdhani/Rajdhani-SemiBold.ttf:Rajdhani-SemiBold.ttf" "rajdhani/Rajdhani-Bold.ttf:Rajdhani-Bold.ttf" \
         "rajdhani/OFL.txt:Rajdhani-OFL.txt" \
         "titilliumweb/TitilliumWeb-Regular.ttf:TitilliumWeb-Regular.ttf" \
         "titilliumweb/TitilliumWeb-SemiBold.ttf:TitilliumWeb-SemiBold.ttf" \
         "titilliumweb/TitilliumWeb-Bold.ttf:TitilliumWeb-Bold.ttf" "titilliumweb/OFL.txt:TitilliumWeb-OFL.txt"; do
    src=${f%%:*} dst=${f#*:}
    if [ ! -f "$TC/fonts/$dst" ]; then
        echo "== font $dst"
        curl -L --fail -o "$TC/fonts/$dst" \
            "https://raw.githubusercontent.com/google/fonts/$FONTS_COMMIT/ofl/$src"
    fi
done

echo "== Helper tools"
"$TC/tools/build-tools.sh"

if [ ! -x "$TC/xemu/build/bin/xmega65.native" ]; then
    echo "== Xemu"
    # git submodule; after a clone without --recursive the folder is empty
    if [ ! -f "$TC/xemu/Makefile" ]; then
        git -C "$TC/.." submodule update --init toolchain/xemu
    fi
    make -C "$TC/xemu" -j"$(nproc)"
fi

# The submodule points to our fork (origin); the original project is
# kept as upstream for pulling in its changes
if ! git -C "$TC/xemu" remote get-url upstream >/dev/null 2>&1; then
    git -C "$TC/xemu" remote add upstream https://github.com/lgblgblgb/xemu.git
fi

if [ ! -f "$TC/rom/MEGA65.ROM" ]; then
    echo "== MEGA65.ROM"
    "$TC/rom/build-rom.sh"
fi

# Put the ROM into Xemu's data folder as well: "Update files on SD image" in
# Xemu's menu then takes it without a file selection (see README).
XEMU_DATA="$HOME/.local/share/xemu-lgb/mega65"
if [ ! -f "$XEMU_DATA/MEGA65.ROM" ]; then
    mkdir -p "$XEMU_DATA"
    cp "$TC/rom/MEGA65.ROM" "$XEMU_DATA/MEGA65.ROM"
fi

echo "== VS Code extensions"
"$TC/vscode/install-extensions.sh" || echo "Skipped; run toolchain/vscode/install-extensions.sh later."

echo "All set."
