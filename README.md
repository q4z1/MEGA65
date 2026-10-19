# MEGA65 Playground

Programs for the **MEGA65** in C and 45GS02 assembly, built with
[llvm-mos](https://llvm-mos.org/) and run in
[Xemu](https://github.com/lgblgblgb/xemu) with the MEGA65 ROM 920413.

As in the Plus/4 playground, each subfolder is a self-contained program.

| Folder | What it is |
| --- | --- |
| [main/](main/) | Hello world: C with one routine in assembly. A template, and a check that everything works together. |

## How this was made

Ideas, design and direction come from decades of programming experience; the
implementation made intensive use of AI ([Claude](https://claude.ai) by Anthropic).

## Toolchain

| Piece | Role |
| --- | --- |
| **llvm-mos** (`mos-mega65-clang`) | C/C++ compiler, assembler and linker; knows the 45GS02 including the Q register and `map`/`eom` |
| **Xemu** (`xmega65`) | MEGA65 emulator |
| **MEGA65.ROM** | built from the C65 ROM 910828 and the official patch |

Everything lives under [toolchain/](toolchain/README.md) and can be set up
again with `toolchain/setup.sh`.

**Why llvm-mos and not cc65:** the installed cc65 2.18 does not know the
MEGA65 at all (only newer versions have a `mega65` target), and its code size
was already the reason the Plus/4 games moved to assembly. llvm-mos optimizes
across all files (LTO), keeps local variables in zero page instead of on a
software stack, and emits 45GS02 instructions on its own. Assembly files
(`.s`) are assembled and linked by the same tool; inline assembly works too.

## Building and running

In VS Code (with the repository root open):

- **F5** builds the program the active file belongs to and starts it in Xemu.
- **Ctrl+Shift+B** only builds; errors show up under "Problems".

Without an editor:

```sh
.vscode/run-current.sh main/main.c            # build and run
MEGA65_RUN=0 .vscode/run-current.sh main/     # build only
toolchain/tools/bin/xmega65                   # Xemu without a program
```

A program is a folder. Without a `build.sh` of its own, all `.c` and `.s`
files in it are built into `build/<folder>.prg` (plus `.prg.elf` with symbols
and a `.map`). Extra compiler flags go into a file `cflags` in the folder.
Anything more needs a `build.sh`; it gets the compiler in `$MEGA65_CC` and
must leave `build/<folder>.prg` behind.

To disassemble:

```sh
toolchain/llvm-mos/bin/llvm-objdump -d main/build/main.prg.elf
```

## C and assembly together

llvm-mos passes the first 8-bit arguments in `A` and `X`, pointers and further
arguments in the zero-page registers `__rc2`, `__rc3`, …; an 8-bit result is
returned in `A`. Example: [main/colors.s](main/colors.s). The details:
[calling convention](https://llvm-mos.org/wiki/C_calling_convention).

## Good to know

- A program using the llvm-mos runtime does not return to BASIC after `main`;
  `exit` ends in an endless loop. Reset to get back.
- Output through `printf`/`putchar` goes through the KERNAL (`$FFD2`); ASCII
  is translated to PETSCII on the way.
- The hardware registers are available as structs in `<mega65.h>`
  (`VICIV.bordercol`, DMA, hypervisor …).
