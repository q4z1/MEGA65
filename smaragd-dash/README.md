# Smaragd Dash

A Boulder Dash style game for the MEGA65: dig through the cave, collect
emeralds, mind the boulders, reach the exit before the time runs out.

The aim is to play like the original Boulder Dash on the C64, with clearly
better graphics. The rules are the Boulder Dash 1 engine's; levels and
graphics are our own. Rockford is the adventurer from the title logo
(`gfx/logo.png`).

The title screen plays our own title music in stereo: six voices on two
SIDs, with chord arpeggios, a filtered bass, drums and an echo of the
melody on the right channel. Fire starts the game.

![Title screen](screenshots/title.png)

![In the first cave](screenshots/cave.png) ![A boulder fell on Rockford](screenshots/explosion.png)

## Controls

| | |
| --- | --- |
| joystick (either port), gamepad, cursor keys | move |
| fire, Space, Return + direction | snap: take dirt or an emerald next to you without moving |
| P | pause |
| Run/Stop | give up the life (when you are stuck) |

## Building and running

In VS Code: open any file of the folder and press **F5**. Without the editor:

```sh
.vscode/run-current.sh smaragd-dash/        # from the repository root
smaragd-dash/build.sh                       # build only
```

`build.sh` generates the graphics (`tools/mkgfx.py`), the caves
(`tools/mkcave.py`) and the music (`tools/mkmusic.py`) into `build/gen/`,
then compiles everything into `build/smaragd-dash.prg` and puts it on the
disk image `build/smaragd-dash.d81` together with the title logo
(`SMARAGD.LOGO`). F5 starts the disk (`-8 … -autoload`). Started as a bare
PRG, without the disk, the title shows the name in big letters instead of
the logo. `build/preview.png` shows all tiles enlarged,
`build/preview-logo.png` the logo as the MEGA65 shows it.

The engine tests run on the host:

```sh
cc -Wall -Isrc -o build/test_engine tests/test_engine.c src/engine.c && build/test_engine
```

For screenshots of the running game without a keyboard,
`SMARAGD_CFLAGS=-DAUTOPLAY` builds a version that walks a fixed path
(`src/input.c`); the pictures in `screenshots/` were taken that way with
Xemu's `-headless -screenshot`.

## How it works

| File | |
| --- | --- |
| `src/engine.c` | the cave rules, without hardware access |
| `src/main.c` | the game: title screen, covering and uncovering, ticks, camera, status line, lives |
| `src/video.c` | screen setup, drawing via DMA, status line, text screens |
| `src/input.c` | joysticks and keyboard |
| `src/sound.c` | sound effects on the first and third SID (left and right) |
| `src/music.c` | music player on the second and fourth SID |
| `src/disk.c`, `src/disk.s` | loading files from the disk through the KERNAL |
| `tools/mkgfx.py` | draws all graphics in code, builds the palette |
| `tools/mkcave.py` | converts the cave files |
| `tools/mkmusic.py` | the title music as text, converted into tables |
| `caves/*.cave` | the caves, as text |
| `gfx/logo.png` | the title logo (scaled down by `tools/mkgfx.py`) |

**The rules** follow Boulder Dash 1: the cave is scanned once per tick
from top left to bottom right, and what moves down or right is marked so it
is not moved twice. Boulders and emeralds fall, and roll off boulders,
emeralds and brick walls when there is room beside and below. Only a falling
one kills. Rockford pushes a boulder sideways only now and then (one try in
four). Fireflies try to turn left, butterflies right; touching Rockford or
the amoeba blows them up, and butterflies leave nine emeralds. The amoeba
grows slowly, then fast; shut in it turns to emeralds, at 200 cells to
boulders. The magic wall turns boulders into emeralds and back for a while.
A tick takes the cave's `speed` (140 ms in the first cave); Rockford moves
one cell per tick and the screen is redrawn every frame.

**The screen** is 40x25 characters in full-colour mode (256 colours, one
byte per pixel). Rows 0-1 are the status line, row 2 a thin line, rows 3-24
the playfield: 19 x 11 tiles of 16x16 pixels. Every playfield character is
unique, so the playfield is a framebuffer (banks 4 and 5, two of them,
alternating). Its characters are stored column by column, so the pixel rows
of a column follow each other 8 bytes apart and a tile half lands on any
pixel row with one DMA copy: about 480 chained DMA jobs draw the view each
frame, and vertical scrolling costs nothing extra. Horizontal fine scrolling
moves the character generator (TEXTXPOS); it is switched while the thin line
is drawn, whose pixel rows are single colours, so the status line stays in
place. The frame loop: game logic during the vertical blank, the
switch at the line, drawing, then waiting for the next blank to show the new
framebuffer.

**The music** is written in `tools/mkmusic.py`: a chord per bar, the
melody as note names with lengths in sixteenths, bass and drum patterns, and
instruments (waveform, envelope, pulse width sweep, vibrato, arpeggio, pitch
sweep for the kick drum). The player in `src/music.c` steps one row every
6 frames (125 beats per minute), closes each note's gate shortly before the
next note, and slowly opens and closes the filter on the bass. The left SID
plays melody, bass and chords, the right one the echo, the bass again and
the drums.

**The title logo** does not fit into the program: below $D000 there is
room for about 44K of code and data, the logo at 288x144 pixels takes
41K. So it is a file of its own on the disk. Before the program takes the
machine over, `disk_load` has the KERNAL load it into bank 1 at $12000,
from where DMA copies it into both framebuffers for the title screen.
`mkgfx.py` scales it down and gives it palette 1: all entries the status
font and icons do not use (they keep theirs, so the status line looks the
same); the title screen switches the text palette to 1, the game back to 0.

Calling the KERNAL from an llvm-mos program needs some care (`disk.s`): the
start-up code has switched the ROM at $C000 and BASIC out, and our
variables can lie under BASIC, so the parameters go to SETBNK, SETNAM and
SETLFS first and the ROM configuration comes back only for LOAD; the DOS
uses zero page $02-$8F, which holds llvm-mos's registers and stack pointer,
so that is saved and restored; and it leaves the Z register non-zero,
while llvm-mos stores zeros with STZ, which on the 45GS02 stores Z.

Without the logo the title text is drawn with the status font; the big
letters are the same font at twice the size, in 16 palette entries of
their own that the title screen cycles for the shine.

## Cave files

See `tools/mkcave.py` for the format. A cave is 40x22 cells with a steel
frame; the first one, `caves/01-first-steps.cave`, needs 12 of its 25
emeralds in 150 seconds.
