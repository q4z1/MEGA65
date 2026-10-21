# toolchain

Everything needed to build and run: compiler, emulator, ROM and the small
tools around them. `setup.sh` restores the whole folder from the net; whatever
is already there is skipped.

```sh
toolchain/setup.sh
```

| Path | What | Source |
| --- | --- | --- |
| `llvm-mos/` | C/C++ compiler, assembler and linker for the 45GS02 (`mos-mega65-clang`) | [llvm-mos-sdk](https://github.com/llvm-mos/llvm-mos-sdk) v23.3.0, Linux release |
| `xemu/` | the Xemu emulator, built into `xemu/build/bin/xmega65.native` | git submodule of our fork [q4z1/xemu](https://github.com/q4z1/xemu) of [lgblgblgb/xemu](https://github.com/lgblgblgb/xemu) |
| `rom/build-rom.sh` | builds `rom/MEGA65.ROM` (version 920413) | see below |
| `disks/` | D81 disks: slideshow, FCM demos, palette and character editors (with the manual as PDF) – local only, not in the repo | files.mega65.org |
| `mega65go/` | the Windows setup mega65go and its `Instructions.txt` – the model for `build-rom.sh`; local only, not in the repo | files.mega65.org |
| `tools/bin/xmega65` | starts Xemu with the ROM built here | written here |
| `tools/bin/mega65-cc` | `mos-mega65-clang` that also records its compile commands for clangd (`MEGA65_CDB_DIR`, used by `.vscode/run-current.sh`) and adds `MEGA65_CFLAGS` to every call | written here |
| `tools/bin/mega65-cast` | records a PRG or D81 as an MP4 video with sound (see below) | written here |
| `tools/bin/bspatch.py` | applies bsdiff patches (replaces `bspatch.exe` from mega65go) | written here |
| `tools/bin/msi-extract-cabs.py` | pulls the CAB archives out of an `.msi` | written here |
| `tools/bin/mkd81.py` | writes a D81 disk image with given files (a program's `build.sh` uses it); `--keep NAME` keeps a file the program writes itself from the previous image | written here |
| `tools/bin/mega65-mem` | where a program's memory goes: RAM range by range, the program by source file, the disk (reads the build's map, ELF and D81, plus the program's `memmap`; see the main README) | written here |
| `tools/bin/cabextract` | unpacks the CABs (bsdtar fails on their LZX) | [cabextract 1.11](https://www.cabextract.org.uk/), built from `tools/src/` |
| `vscode/mega65-asm/` | VS Code syntax highlighting for 45GS02 assembly in llvm-mos syntax (all 45GS02 opcodes incl. `ldz`, `map`/`eom`, the Q instructions; `mos16lo()` & co.) | written here |
| `vscode/install-extensions.sh` | packs `mega65-asm` into `vscode/build/mega65-asm.vsix` and installs it together with the clangd extension | written here |
| `tools/bin/adf.py` | lists and extracts the files of an Amiga disk image (ADF, OFS/FFS) | written here |
| `tools/bin/m68k-dis.py` | recursive-descent 68000 disassembler: follows branches and calls, so code and data come apart; labels from a symbol file | written here |
| `tools/bin/amiga-run` | Amiga emulator without a window, driven by a command script: frames, joystick, mouse, keys, screenshots, memory dumps, breakpoints, traces, snapshots (see below) | `tools/amiga-run/`, on the core of [vAmiga](https://github.com/dirkwhoffmann/vAmiga) (pinned commit, cloned into `tools/src/vAmiga`) |
| `*.rom` | an Amiga Kickstart ROM (1.3 for the A500), for `amiga-run` – local only, not in the repo | your own copy |
| `fonts/` | free fonts (SIL Open Font License): Exo 2, Rajdhani, Titillium Web – for screens rendered at build time | [google/fonts](https://github.com/google/fonts), pinned commit, by `setup.sh` |
| `tools/python/` | Python modules `olefile` (reading the MSI), `capstone` (disassembler), `Pillow` (images for the build tools, e.g. Lotus Run's pages, cars) and `numpy` (analysis scripts), installed by `tools/build-tools.sh` at fixed versions; `lotus-run/build.sh` puts them on `PYTHONPATH` | pip |
| `downloads/` | the downloaded archives (SDK, MSI, ROM patch, sources) | |

Third-party files are listed in `.gitignore` and stay out of the repo:
`disks/`, `mega65go/`, `downloads/`, the SDK and the ROMs.
`char-editor-fcm3.zip` is unpacked into `disks/`; the original is in
`downloads/`.

To insert a disk: `tools/bin/xmega65 -8 disks/slideshow.d81`. With
`-autoload` Xemu also types `RUN "*` and starts the first program on it:

```sh
tools/bin/xmega65 -8 disks/demos-fcm.d81 -autoload        # Flying Craft (full color mode)
tools/bin/xmega65 -8 disks/slideshow.d81 -autoload        # IFF image slideshow
tools/bin/xmega65 -8 disks/palette-editor1.d81 -autoload  # palette editor
tools/bin/xmega65 -8 disks/char-editor-fcm3.d81 -autoload # character editor
```

`demos-fcm.d81` holds two more demos that `-autoload` does not reach. Insert
the disk without it and type `RUN "SHOW-FCM-RAND4"` or `RUN "ICONS-FCM"`
(in Xemu `"` is Shift+2). In VS Code the task *MEGA65: Run demo disk* offers
the disks in a list.

## The ROM

The MEGA65 ROM may not be redistributed; only a patch against the Commodore 65
ROM 910828 is published. That ROM in turn is given away by Cloanto for
personal use as part of *C64 Forever*. `rom/build-rom.sh` does on Linux what
mega65go's `SETUP.cmd` does on Windows:

1. download `c64-forever-11-setup.msi` (268 MB, into `downloads/`)
2. pull the CAB archives out of the MSI and unpack them
3. find the C65 ROM 910828 among them – `file_Shared_54` in this MSI release,
   recognized by its SHA-1 `b63d9707…`; it is kept as `rom/c-65-19910828.rom`
4. patch it with `920413.bdf` from `920413_Sn7YEw.zip` (from files.mega65.org,
   into `downloads/`) → `rom/MEGA65.ROM`, checked against SHA-1 `4214ba46…`

With this ROM, Xemu reports *"Closed-ROMs detected with version 920413"* at
startup. The ROM and the C65 ROM are listed in `.gitignore`.

## Xemu

`tools/bin/xmega65` starts the emulator with `-rom rom/MEGA65.ROM`; all other
arguments are passed on, e.g. `-prg file.prg` or `-8 disk.d81`. Settings and
the SD card image live in `~/.local/share/xemu-lgb/mega65/`. Inside VS Code's
Flatpak sandbox Xemu would use `~/.var/app/com.visualstudio.code/data/`
instead; the wrapper sets `XDG_DATA_HOME` so that sandbox and host share the
same data. It also sets `GDK_BACKEND=x11` whenever X11 is available
(`DISPLAY`): Xemu's right-click menu is a GTK popup, and under Wayland GTK
does not open it over the SDL window.

### Our changes to Xemu

The submodule is our fork, with changes of our own on top of upstream (each
on a branch of its own, for a pull request upstream):

- `-recvideo`, `-recaudio`: recording, used by `mega65-cast` (branch
  `recorder`)
- `-screenshot` saves the last complete frame (`recorder`)
- the temporary file of a saved setting is named per process, so that
  several Xemus can start at once (`save-file-race`)
- the sound is rendered line by line in step with the emulated time, into a
  buffer the audio device plays from - what a program writes to the SIDs is
  heard when it wrote it, not up to a buffer's length (some 23 ms) later or
  earlier; `-audiocallback` renders it the old way (`audio-sync`)
- a raster interrupt's flag stays set until it is acknowledged, as on the
  real VIC, also when the line went by while a DMA job held the CPU
  (`audio-sync`)

### Gamepads

Xemu uses SDL2's plain joystick interface and treats every joystick as the
one joystick of a port (port 2 unless changed in its menu): left stick and
D-pad move, any button fires. No mapping is needed. On the Steam Deck the
built-in controller (`28de:1205`) is a joystick as well; the wrapper hides it
from SDL (`SDL_GAMECONTROLLER_IGNORE_DEVICES`) as soon as another joystick is
connected, so an external gamepad does not have to share the port with it.
`MEGA65_PAD_IGNORE` overrides the list (`vendor/product`, comma separated;
empty hides nothing).

### Once: system files onto the SD image

A freshly created SD image is only formatted, and Xemu then reports *"Cannot
find Xemu's signature on the SD-card image"* at startup. To fix it, once per
image:

1. right-click into the Xemu window → *Disks / Cart* → *SD-card* →
   *Update files on SD image*
2. answer *"Use the previously installed ROM?"* with **Yes**

`setup.sh` has already copied the ROM to `~/.local/share/xemu-lgb/mega65/` for
this; otherwise Xemu asks for a ROM file – pick `rom/MEGA65.ROM`. Xemu writes
the ROM, the character set, the Hyppo files and an empty default D81 onto the
image, sets its signature and restarts. The message does not appear after
that. The wrapper still passes `-rom`, so the ROM built here is always the one
that runs.

### Patching Xemu

`xemu/` is a submodule of the fork [q4z1/xemu](https://github.com/q4z1/xemu)
(`origin`); the original project is the remote `upstream`. Changes to Xemu
are made on a branch in the fork:

```sh
cd toolchain/xemu
git switch -c fix-something       # branch off master
# ... edit, then rebuild
make -j"$(nproc)"
git commit -am "..."
git push -u origin fix-something
cd ../..
git add toolchain/xemu            # record the new submodule commit
git commit -m "Xemu: ..."
```

Push the submodule commit before the main repository's commit, otherwise a
fresh clone points to a commit the fork does not have. To pick up upstream
changes:

```sh
cd toolchain/xemu
git fetch upstream
git switch master && git merge --ff-only upstream/master && git push
```

### Recording videos

Our Xemu (branch `recorder` of the fork) has two more options:
`-recvideo FILE` writes every frame as raw RGB24, 704x576 pixels (the visible
area, as the window shows it), and `-recaudio FILE` the sound as raw 16-bit
stereo samples at 44100 Hz. The sound is rendered once per emulated frame,
as long as the frame lasted, instead of by the sound card's callback, so
picture and sound stay in step at any emulation speed - also with
`-headless -sleepless`. Both files may be named pipes.

`tools/bin/mega65-cast` puts it together: Xemu headless and as fast as it
can, the frames through a pipe into ffmpeg, then an MP4 (H.264, AAC):

```sh
tools/bin/mega65-cast prog.prg                        # -> prog.mp4
tools/bin/mega65-cast -t 60 -s 2 -o out.mp4 disk.d81  # at most 60 s, cut the first 2 s
```

`-x` enlarges the picture (default 2, sharp pixels). Xemu runs with
`-testing`, so the program can end the recording itself: 0, then `$42` to
`$D6CF`. A program that does not do that is recorded for `-t` seconds
(default 600). Xemu options can follow after `--`.

Useful for automated tests:

```sh
tools/bin/xmega65 -headless -sleepless -prg x.prg -screenshot x.png
```

(The screenshot is taken on exit; `-dumpmem file` saves the 384K of chip
RAM on exit as well.)

## Running Amiga programs

`tools/bin/amiga-run` emulates an Amiga (the vAmiga core) without a window,
as fast as it can (about four times real time), and does what a script
says, line by line:

```sh
cat > boot.txt <<'EOS'
config A500_OCS_1MB
rom "toolchain/Kickstart v1.3 rev 34.5 (1987)(Commodore)(A500-A1000-A2000-CDTV).rom"
disk 0 game.adf
power
frames 1500              # 30 seconds (PAL)
mouse 1 left             # click
frames 250
joy 2 up fire            # joystick in port 2
frames 100
joy 2 release
shot title.ppm           # screenshot, 368 x 287 lores pixels
dump chip.bin 0 80000    # memory (hex address and length)
until 1c2f0 500          # run to an address (at most 500 frames), print the registers
save title.vasnap        # snapshot; "load" continues from it
EOS
toolchain/tools/bin/amiga-run boot.txt
```

All commands are listed at the top of
[tools/amiga-run/amiga-run.cpp](tools/amiga-run/amiga-run.cpp). A Kickstart
ROM is needed; it is not included (it may not be redistributed) and goes
into `toolchain/` as a `.rom` file, which `.gitignore` keeps out.

`tools/bin/m68k-dis.py` turns the code into a listing, `tools/bin/adf.py`
gets the files off a disk image.
