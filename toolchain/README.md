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
| `tools/bin/mega65-cc` | `mos-mega65-clang` that also records its compile commands for clangd (`MEGA65_CDB_DIR`, used by `.vscode/run-current.sh`) | written here |
| `tools/bin/bspatch.py` | applies bsdiff patches (replaces `bspatch.exe` from mega65go) | written here |
| `tools/bin/msi-extract-cabs.py` | pulls the CAB archives out of an `.msi` | written here |
| `tools/bin/cabextract` | unpacks the CABs (bsdtar fails on their LZX) | [cabextract 1.11](https://www.cabextract.org.uk/), built from `tools/src/` |
| `vscode/mega65-asm/` | VS Code syntax highlighting for 45GS02 assembly in llvm-mos syntax (all 45GS02 opcodes incl. `ldz`, `map`/`eom`, the Q instructions; `mos16lo()` & co.) | written here |
| `vscode/install-extensions.sh` | packs `mega65-asm` into `vscode/build/mega65-asm.vsix` and installs it together with the clangd extension | written here |
| `tools/python/` | Python module `olefile` for reading the MSI | pip |
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

Useful for automated tests:

```sh
tools/bin/xmega65 -headless -sleepless -prg x.prg -screenshot x.png
```

(The screenshot is taken on exit.)
