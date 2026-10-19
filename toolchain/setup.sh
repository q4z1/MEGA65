#!/bin/sh
# Sets up the complete toolchain under toolchain/. Whatever is already there
# is skipped; each step can also be run on its own.
#
#   llvm-mos/            C compiler, assembler, linker (target mos-mega65)
#   tools/               helper tools (tools/build-tools.sh)
#   xemu/build/bin/      Xemu, built from the git checkout
#   rom/MEGA65.ROM       the ROM (rom/build-rom.sh)
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

echo "All set."
