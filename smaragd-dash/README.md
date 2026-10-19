# Smaragd Dash

A Boulder Dash style game for the MEGA65: dig through the cave, collect
emeralds, mind the boulders, reach the exit before the time runs out.

The aim is to play like the original Boulder Dash on the C64, with clearly
better graphics. The rules are the Boulder Dash 1 engine's; levels and
graphics are our own. Rockford is the adventurer from the title logo
(`gfx/logo.png`).

There are 25 caves, each in four levels, as in the original: 100 in all.
On the title screen the joystick picks the level (up and down) and the cave
to start with (left and right: 1, 6, 11, 16 or 21). After the last cave
the game goes on with the first one of the next level.

The title screen plays our own title music in stereo: six voices on two
SIDs, with chord arpeggios, a filtered bass, drums and an echo of the
melody on the right channel. Fire starts the game.

### High scores

As in the arcades: the best eight scores, each with three letters, the
score and the cave and level where the game ended. The title screen shows
the table in turn with the logo (15 seconds logo, 10 seconds table); the
best score is in its status line. Gold, silver and bronze for the first
three, ice blue for the others.

When a game ends with a score for the table, the game asks for the three
letters: up and down go through the letters (A-Z, 0-9, `.`, `-`, `!` and
space; held, they repeat), fire or right takes one, left goes back. Or type
them: a letter or digit is taken at once, Del goes back. There are 30
seconds for it; then the letters stay as they are. The next entry starts
with the last name. After that the table comes first on the title, the new
entry shining green with Rockford walking beside it.

The table is written back to the disk at once (`SMARAGD.SCORES`), so it is
still there the next time; a new build keeps it, too (`mkd81.py --keep`).
To start again from the default table, delete `build/smaragd-dash.d81`
before building.

![Title screen](screenshots/title.png)

![In the first cave](screenshots/cave.png) ![A boulder fell on Rockford](screenshots/explosion.png)

**[Video: the game plays the first six caves](screenshots/first-six-caves.mp4)**
(4½ minutes, with music and sound; recorded as described under
[Screencast](#screencast)).

## Controls

| | |
| --- | --- |
| joystick (either port), gamepad, cursor keys | move; on the title: up/down level, left/right first cave |
| fire, Space, Return + direction | snap: take dirt or an emerald next to you without moving |
| P | pause |
| Run/Stop | give up the life (when you are stuck) |
| up/down, fire/right, left; or type | the name for the high score table |

## Building and running

In VS Code: open any file of the folder and press **F5**. Without the editor:

```sh
.vscode/run-current.sh smaragd-dash/        # from the repository root
smaragd-dash/build.sh                       # build only
```

`build.sh` generates the graphics (`tools/mkgfx.py`) and the music
(`tools/mkmusic.py`) into `build/gen/`, the caves (`tools/mkcave.py`) into
`build/caves/`, then compiles everything into `build/smaragd-dash.prg` and
puts it on the disk image `build/smaragd-dash.d81` together with the title
logo (`SMARAGD.LOGO`), the high scores (`SMARAGD.SCORES`), the caves
(`CAVE01-1` ... `CAVE25-4`: cave and level) and the moves for the
screencast (`DEMO01`, ...; see below). F5 starts
the disk (`-8 … -autoload`). Started as a bare PRG, without the disk, the
title shows the name in big letters instead of the logo, and there are no
caves to play. `build/preview.png` shows all tiles enlarged,
`build/preview-logo.png` the logo as the MEGA65 shows it.

The engine tests run on the host:

```sh
cc -Wall -Isrc -o build/test_engine tests/test_engine.c src/engine.c && build/test_engine
```

### Screencast

*Terminal → Run Task… → MEGA65: Record screencast (active program)* (or
`MEGA65_CAST=1 .vscode/run-current.sh smaragd-dash/` from the repository
root) records the game playing itself as `build/smaragd-dash.mp4`, with
the music and the sounds: the title for fifteen seconds, then all caves of
level 1, solved.
Built with `-DSCREENCAST`, the game presses fire on the title by itself,
loads the moves for each cave with it from the disk (`DEMO01`, `DEMO02`, ...,
written by the solver as `build/caves/demoNN.bin`), and stops the emulator
after the last cave, which ends the recording.

The moves come from `tools/solve.c`, which `build.sh` compiles and runs on
the host at every build. It plays the caves with the game's own engine
(`src/engine.c`) and counts frames and ticks like `play_cave`: from the
nearest few emeralds it picks one, walks there, round falling things and
away from creatures, until the exit is open, and takes back any choice that
gets Rockford killed or stuck. What it cannot find by itself - dropping
boulders on purpose, pushing one aside - a cave gives it as opening moves
(the `demo` key of its `.cave` file); the search goes on from there. If it
finds no way through a cave, the screencast ends before that cave. As the
cave's random numbers (pushing a boulder works one time in four) start the
same in every run of a cave, the same moves play the same in the game. So a changed cave or rule gives new
moves with the next build.

The pictures in `screenshots/` were taken with Xemu's `-headless -screenshot`,
the video `screenshots/first-six-caves.mp4` with
`MEGA65_CAST=1 MEGA65_CAST_OPTS="-x 1 -s 2" .vscode/run-current.sh smaragd-dash/`
(original size, without the boot screen) and copied there.

## How it works

| File | |
| --- | --- |
| `src/engine.c` | the cave rules, without hardware access |
| `src/main.c` | the game: title screen, covering and uncovering, ticks, camera, status line, lives, high score screens |
| `src/hiscore.c` | the high score table and its file |
| `src/video.c` | screen setup, drawing via DMA, status line, text screens |
| `src/input.c` | joysticks and keyboard |
| `src/sound.c` | sound effects on the first and third SID (left and right) |
| `src/music.c` | music player on the second and fourth SID |
| `src/disk.c` | loading files from the disk, and writing one back, through the floppy controller |
| `tools/mkgfx.py` | draws all graphics in code, builds the palette |
| `tools/mkcave.py` | converts the cave files for the disk (and into C for `solve.c`) |
| `tools/solve.c` | finds the moves through the caves for the screencast (runs on the host) |
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
frame, and vertical scrolling costs nothing extra. Their list (6K) lies
below the program at $0800, where BASIC had its screen; the game never
goes back to BASIC. Horizontal fine scrolling
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
41K. So it is a file of its own on the disk, loaded at the start into
bank 1 at $12000, from where DMA copies it into both framebuffers for the
title screen.
`mkgfx.py` scales it down and gives it palette 1: all entries the status
font and icons do not use (they keep theirs, so the status line looks the
same); the title screen switches the text palette to 1, the game back to 0.

**The caves** come from the disk as well, one file each, loaded when the
game gets to them; after the last cave of a level on the disk the game goes
on with the first one of the next level, and after the last level it stays
there. So the program holds no maps, and more caves cost no memory; it only
knows how many there are (`levels.h`, written by `mkcave.py`), for the
choice on the title.

**The loader** (`disk.c`) does without the KERNAL: it finds the file in
the D81's directory and reads its sectors through the F011 floppy
controller, waiting for each one by polling and copying it with DMA from
the controller's sector buffer ($FFD6C00). It needs neither the ROM nor
interrupts, so it works at any time, and after each sector it calls a
hook: while loading, the status line shows an emerald that turns. It
reads the disk image mounted in drive 0; a real floppy would also need the
head stepped to the track. Writing goes the other way: `disk_save`
rewrites a file that is on the disk already, in place - each sector is
read, changed in the controller's buffer and written back. That is how the
high scores get onto the disk: `build.sh` puts a file of one sector there,
`hiscore.c` fills it.

Without the logo the title text is drawn with the status font; the big
letters are the same font at twice the size, in 16 palette entries of
their own that the title screen cycles for the shine.

## Cave files

See `tools/mkcave.py` for the format. A cave is 40x22 cells with a steel
frame. The first six follow the first caves of Boulder Dash 1 in idea, not
in layout; the others bring one idea each, getting a little harder from cave
to cave - more boulders and creatures, a little less time to spare - but
always with time to look around: each limit is at least three and a half
times what the solver needs (the maze and the amoeba, where it has to wait,
twice), and no cave asks for much more than half of
its emeralds unless it makes more of them (magic walls, butterflies, the
amoeba). Like the original's, most are a random fill with walls, rooms and
creatures drawn over it.

| | | needs | |
| --- | --- | --- | --- |
| 1 | FIRST STEPS | 12 in 150 s | dirt, boulders and emeralds |
| 2 | ROOMS | 20 in 120 s | brick walls make six rooms; two fireflies wait in theirs |
| 3 | MAZE | 22 in 120 s | a maze with emeralds in its dead ends; fireflies guard three of them |
| 4 | BUTTERFLIES | 36 in 150 s | dig under the boulders above the hall: a butterfly hit by a falling one leaves nine emeralds |
| 5 | ENCHANTED WALL | 30 in 150 s | boulders falling through the magic wall come out as emeralds, for 20 seconds |
| 6 | AMOEBA | 40 in 150 s | drop the two boulders into the openings of the nest before the amoeba gets out: shut in, it turns to emeralds |
| 7 | FIREFLY DENS | 18 in 120 s | four fireflies circle in their dens |
| 8 | TREASURE ROOM | 24 in 60 s | a small room full of emeralds, one minute |
| 9 | BOULDER RAIN | 20 in 120 s | plenty of boulders over plenty of holes |
| 10 | TRACKS | 22 in 120 s | fireflies run up and down brick tracks; cross at the ends |
| 11 | BUTTERFLY GARDEN | 24 in 120 s | a butterfly in each garden, a boulder above it |
| 12 | STAIRWAY | 24 in 120 s | brick stairs; what lies on them rolls |
| 13 | VEINS | 26 in 100 s | emeralds run through the rock in veins |
| 14 | MAGIC WELLS | 26 in 130 s | three wells with a magic floor, boulders above them |
| 15 | VAULTS | 28 in 120 s | small brick vaults with emeralds, one door each |
| 16 | AMOEBA FIELD | 26 in 120 s | the amoeba spreads from a corner; at 200 cells it turns to boulders |
| 17 | CAVERNS | 20 in 110 s | big caverns with fireflies circling in them |
| 18 | LABYRINTH | 24 in 150 s | a bigger maze, and fireflies in it |
| 19 | WATERFALL | 28 in 100 s | emeralds and boulders stacked in shafts; dig below and they pour out |
| 20 | ROCKFALL | 28 in 110 s | more boulders than dirt, and a slightly faster tick |
| 21 | SWARM | 26 in 110 s | butterflies round the amoeba's nest blow up into emeralds when it reaches them |
| 22 | MAGIC FACTORY | 32 in 120 s | two magic floors, one above the other |
| 23 | FORTRESS | 32 in 100 s | a brick fortress full of emeralds, fireflies at the gates |
| 24 | SERPENTINE | 32 in 130 s | one long way back and forth through the cave |
| 25 | GRAND FINALE | 40 in 150 s | a bit of everything: maze, magic floor, fireflies and the amoeba |

The table shows level 1. As in Boulder Dash 1, every cave comes in four
levels, which `mkcave.py` makes from the one map: each level gives a tenth
less time (in steps of 5 s), asks for a tenth more emeralds and ticks 5 ms
faster than the one before, and its random fill is different. The original
fills each level of a cave from its own seed; here the dirt, boulders and
emeralds of the fill swap places with others close by (up to three cells
to the side, one up or down), so every part of the cave keeps its mix and
its idea. What is next to walls, creatures, the exit, the inbox or the way
of the opening moves (`demo`) stays as drawn. A cave can give its own
values per level, keep its map (`shuffle = no`) or name other seeds; the
maze, the amoeba cave and the grand finale give their own times or emerald
counts, four caves other seeds. At every build the solver plays all 100
and names any it finds no way through; at present it solves all of them,
with at least 1.7 times the time it needs (the maze), 2.4 times in all
others but the amoeba cave.
