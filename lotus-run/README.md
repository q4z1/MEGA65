# Lotus Run

A racing game for the MEGA65 after **Lotus Esprit Turbo Challenge** (Amiga,
1990), with the race on the whole screen.

Work in progress: the first race of the season can be driven - road,
scenery, opponents and the own car, at 25 pictures per second.

## Building

The build needs data that is not part of this repository (`LOTUS_ZIP` in
`build.sh` says where it looks for it). Then

```sh
./build.sh
```

makes `build/lotus-run.d81`.

## Playing

Mount `build/lotus-run.d81` and run `LOTUS RUN` (in Xemu: `-8` with the
image and `-autoload`). Joystick in port 2, or the cursor keys and space:

* forward accelerates, back brakes, left and right steer
* fire with forward / back shifts up / down

## Inside

* [src/](src/): the game in C and 45GS02 assembly - the race
  ([race.s](src/race.s)), the road ([road.c](src/road.c),
  [render.s](src/render.s); its lines drawn out with smooth edges at the
  start, [road_rows.s](src/road_rows.s)), scenery and cars ([sprites.c](src/sprites.c)),
  the screen ([video.c](src/video.c)): the picture is drawn into 320×200
  plain bytes and turned into full-colour characters by one DMA list in the
  lower border.
* [tools/](tools/): turn that data into what the build uses.
* [tests/](tests/): the assembly checked against its C reference.
