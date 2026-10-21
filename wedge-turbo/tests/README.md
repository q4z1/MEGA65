# Tests

The game's race logic and the renderer's inner loops run in 45GS02
assembly; each has a reference in C ([src/ref/](../src/ref/)). The checks
here build MEGA65 programs with both, run them in Xemu without a window
(after `build.sh`) and compare what they produce, byte for byte.

## The race logic

`check_race.sh` builds `check_race.c` with [src/race.s](../src/race.s) and
[src/ref/race.c](../src/ref/race.c): a made-up driver drives nine courses
with different settings (two players, automatic gears, fire accelerates,
little fuel, the finish close), and every frame both versions start from
the same state; the whole race state must come out the same - also that of
`race_picture`.

```sh
tests/check_race.sh            # "22500 frames the same"
```

## The renderer

`check_render.sh` builds `check_render.c` with [src/render.s](../src/render.s)
and its references [src/ref/road_draw.c](../src/ref/road_draw.c) and
[src/ref/sprites_draw.c](../src/ref/sprites_draw.c): `road_draw` (one DMA
copy per road line of its pattern, drawn out in attic RAM) and
`sprites_draw` (a transparent DMA copy per visible row of a sprite). The
pictures must be the same: views of all 32 courses in two scales
(positions along the course, the camera to the sides), and made-up lists of
sprites cut at every edge.

```sh
tests/check_render.sh          # "240 sprite lists and 1490 views the same"
```

Both check programs end Xemu when they are done (`check.h`: `-testing`,
then $42 to $D6CF), with the result in the exit code and in memory.
