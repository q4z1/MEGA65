# MEGA65 Playground

Programs for the **MEGA65** in C and 45GS02 assembly, built with
[llvm-mos](https://llvm-mos.org/) and run in
[Xemu](https://github.com/lgblgblgb/xemu) with the MEGA65 ROM 920413.

Each subfolder is a self-contained program.

| Folder | What it is |
| --- | --- |
| [main/](main/) | Hello world: C with one routine in assembly. A template, and a check that everything works together. |
| [wedge-turbo/](wedge-turbo/README.md) | Wedge Turbo: a racing game in the style of the Amiga's, with the race on the whole screen. Work in progress. |
| [smaragd-dash/](smaragd-dash/README.md) | Smaragd Dash: a Boulder Dash style game in 256 colours with smooth scrolling, title logo and stereo music, on a D81. 25 caves in four levels each (100), loaded from the disk; a cave editor, and GDash's engine for caves of its own and from GDash ([EDITOR.md](smaragd-dash/EDITOR.md)). |

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

**Why llvm-mos and not cc65:** cc65 2.18, the version installed here, does
not know the MEGA65 at all (only newer versions have a `mega65` target), and
it produces a good deal more code than hand-written assembly. llvm-mos
optimizes across all files (LTO), keeps local variables in zero page instead
of on a software stack, and emits 45GS02 instructions on its own. Assembly files
(`.s`) are assembled and linked by the same tool; inline assembly works too.

## Building and running

In VS Code (with the repository root open):

- **F5** builds the program the active file belongs to and starts it in Xemu.
- **Ctrl+Shift+B** only builds; errors show up under "Problems".
- *Terminal → Run Task… → MEGA65: Run demo disk* starts one of the demo disks
  from `toolchain/disks/` (see [toolchain/README.md](toolchain/README.md)).

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
must leave `build/<folder>.prg` behind. If it also leaves a disk image
`build/<folder>.d81` (made with `toolchain/tools/bin/mkd81.py`), F5 starts
that instead: in drive 8, with its first program run (`-autoload`).

Every build is also copied into [RetroDeck](../RetroDeck)'s games folder,
`~/Games/Retro/MEGA65`: the disk image if there is one, else the `.prg`,
replacing the one before - so the latest build can be played and compared
there next to the rest (*Bibliothek neu einlesen* in RetroDeck's menu if it
is already running). Not a screencast build, and not a program with a file
`.no-retrodeck` in its folder (`main/`); `RETRO_GAMES=<dir>` copies
elsewhere, `RETRO_GAMES=` (empty) not at all.

### Screencasts

*Terminal → Run Task… → MEGA65: Record screencast (active program)* builds
the program with `-DSCREENCAST` and records it as `build/<folder>.mp4`, with
sound, without opening a window:

```sh
MEGA65_CAST=1 .vscode/run-current.sh smaragd-dash/
MEGA65_CAST=1 MEGA65_CAST_OPTS="-t 30" .vscode/run-current.sh main/   # at most 30 s
```

Built that way, a program should play itself and end the recording when it
is done by writing 0 and then `$42` to `$D6CF`; otherwise the recording stops
after 10 minutes (`-t`). Xemu runs headless and as fast as it can (about three
times real time), and hands every frame and the sound in step with the
emulated time to ffmpeg, so the video does not stutter however fast the
machine running it is. [toolchain/tools/bin/mega65-cast](toolchain/tools/bin/mega65-cast)
does the recording and also works on its own, with any PRG or D81.

### Memory map

*Terminal → Run Task… → MEGA65: Memory map (active program)* builds the
program and shows where its memory goes:
[toolchain/tools/bin/mega65-mem](toolchain/tools/bin/mega65-mem) lists bank 0
and chip RAM banks 1-5 range by range - the linker's sections, the MEGA65's
own areas (KERNAL, I/O, ROM, ...), what the program places by hand - and
what is free, largest first; then the program by source file (code,
read-only data, data, BSS, zero page; from the debug information, so it
works with LTO), its largest symbols, and the files on the disk with their
blocks, bytes and load address.

```sh
toolchain/tools/bin/mega65-mem main/                # after a build
toolchain/tools/bin/mega65-mem --files smaragd-dash/  # every file on the disk
```

What the linker cannot know goes into a file `memmap` in the program folder
(an example: [smaragd-dash/memmap](smaragd-dash/memmap)):

```
ram  $0800+6006      DMA list for a frame         # bank 0, by hand
ram  $40000-$4DBFF   framebuffer A                # up to 28-bit addresses
file SMARAGD.LOGO   @$12000     title logo        # loaded to an address
file CAVE??-?       @cave_file  a cave            # loaded into a variable
```

`ram` marks memory as the program's; overlaps with the linker's sections
or with each other are reported. `file` describes files on the disk (with
`*`, `?`, `[...]`); with `@` it also says where the program loads them
(without the load address): to an address, which then counts as used up to
the end of the largest of them, or into a variable, which each file is
checked against.

To disassemble:

```sh
toolchain/llvm-mos/bin/llvm-objdump -d main/build/main.prg.elf
```

## Editor

C is checked by **clangd from llvm-mos** (`.vscode/settings.json`), so the
editor sees exactly what the compiler sees: target `mos`, 16-bit `int`, the
MEGA65 headers, 45GS02 inline assembly. Microsoft's C/C++ IntelliSense is
switched off for this workspace.

clangd takes the flags from the real build: `run-current.sh` builds with
`toolchain/tools/bin/mega65-cc`, which records every compile command, and
writes them to `<program>/build/compile_commands.json`. So include paths and
defines of a `build.sh` (e.g. `-Ibuild/gen` for generated headers) are known
as soon as the program has been built once – as long as `build.sh` compiles
with `$MEGA65_CC`. Until then, and for loose files, the root
[compile_flags.txt](compile_flags.txt) applies. A folder with code for the
host (such as host tests) brings its own `compile_flags.txt`, e.g.
`--target=x86_64-unknown-linux-gnu`. If clangd still complains after the first
build: *clangd: Restart language server*.

Assembly files (`.s`, `.inc`) are highlighted by the 45GS02 grammar in
[toolchain/vscode/](toolchain/vscode/mega65-asm/). Both extensions are
installed by `toolchain/vscode/install-extensions.sh` (also part of
`setup.sh`).

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
