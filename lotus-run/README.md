# Lotus Run

A racing game for the MEGA65 after **Lotus Esprit Turbo Challenge** (Amiga,
1990), with the race on the whole screen.

Work in progress: a season can be driven - choose the level (7, 10 or 15
races) and the controls, then course after course, with the result and the
championship after each race; finish outside the first ten and the season
is over for you. Road, scenery, opponents and the own car at 25 pictures per
second, with the engines and the sound effects of the race - or the radio:
the game's tunes in new arrangements for the four SIDs, in stereo.

## Building

The build needs data that is not part of this repository (`LOTUS_ZIP` in
`build.sh` says where it looks for it). Then

```sh
./build.sh
```

makes `build/lotus-run.d81`.

## Playing

Mount `build/lotus-run.d81` and run `LOTUS RUN` (in Xemu: `-8` with the
image and `-autoload`). Joystick in port 2, or the cursor keys and space.
The controls page sets the gears (automatic or manual) and what
accelerates (the fire button or the joystick forward) and shows what each
direction does. Then the radio: left and right choose one of four tracks
for the race (each plays while it is chosen, the display counts its time;
the engines and the sound effects go on more quietly under it) or 00, off.
Run/Stop gives up a race.

`LOTUS_CFLAGS=-DLOTUS_AUTOTEST ./build.sh` makes a build that goes through
the pages by itself and drives on its own (full gas, holding a line,
round slower cars) with the radio's tracks in turn, for recordings.

## Inside

* [src/](src/): the game in C and 45GS02 assembly - the race
  ([race.s](src/race.s)), the road ([road.c](src/road.c),
  [render.s](src/render.s); its lines drawn out with smooth edges at the
  start, [road_rows.s](src/road_rows.s)), the season
  ([season.c](src/season.c)) and its pages ([screens.c](src/screens.c), an
  overlay loaded between the races: [link.ld](link.ld)), the sounds
  ([sound.c](src/sound.c)), the music ([music.s](src/music.s), played by
  a timer interrupt; arranged at build time by
  [tools/mkmusic.py](tools/mkmusic.py)),
  scenery and cars ([sprites.c](src/sprites.c)),
  the screen ([video.c](src/video.c)): the picture is drawn into 320×200
  plain bytes and turned into full-colour characters by one DMA list in the
  lower border.
* [tools/](tools/): turn that data into what the build uses.
* [tests/](tests/): the assembly checked against its C reference.
