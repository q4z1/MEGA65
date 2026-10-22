// Plays an own cave with src/gdengine.c on the host, as GDash's own code
// does in the test oracle (tests/test_gdengine.sh): with the same
// pseudo-random input, it prints a line per step - the map's hash, the
// player's state, diamonds, time, score, speed and position.
//
//   gdplay cave <file>                   the values after the start
//   gdplay play <file> <steps> <seed>    playing; seed: of the input
//
// <file> holds a GdCaveFile (tools/cavekit.py). Built with GD_EXACT.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "gdengine.h"

static GdCaveFile cave_file;
static unsigned lcg;

static unsigned next_rand(void) {
    lcg = lcg * 1103515245u + 12345u;
    return (lcg >> 16) & 0x7FFF;
}

static unsigned hash_map(void) {
    unsigned hash = 2166136261u;
    for (int y = 0; y < gd.h; y++)
        for (int x = 0; x < gd.w; x++)
            hash = (hash ^ cave[y * CAVE_W + x]) * 16777619u;
    return hash;
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[2], "rb");
    if (!f || fread(&cave_file, sizeof cave_file, 1, f) != 1) {
        fprintf(stderr, "gdplay: cannot read %s\n", argv[2]);
        return 1;
    }
    fclose(f);
    gd_start(&cave_file, 0);
    if (!strcmp(argv[1], "cave")) {
        printf("time=%d\nspeed=%d\nplayer_x=%d\nplayer_y=%d\nmap=", (int)gd.time, gd.speed, gd.player_x,
               gd.player_y);
        for (int y = 0; y < gd.h; y++)
            for (int x = 0; x < gd.w; x++)
                printf("%02x", cave[y * CAVE_W + x]);
        printf("\n");
        return 0;
    }
    static const uint8_t dirs[] = {MV_STILL, MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT,
                                   MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_UP_RIGHT};
    int steps = atoi(argv[3]);
    lcg = atoi(argv[4]);
    for (int t = 0; t < steps; t++) {
        unsigned in = next_rand();
        gd_iterate(dirs[in % 10], (in >> 4) % 8 == 0, false);
        printf("%d %08x st=%d dia=%d time=%d score=%d speed=%d px=%d py=%d\n", t, hash_map(), gd.player_state,
               gd.diamonds_collected, (int)gd.time, gd.score, gd.speed, gd.player_x, gd.player_y);
        if (getenv("REFDUMP_STATE"))
            printf("  amoeba=%d,%d,%d\n", gd.amoeba_state, (int)gd.amoeba_time, (int)gd.amoeba_growth_prob);
        if (getenv("REFDUMP_MAP"))
            for (int y = 0; y < gd.h; y++) {
                for (int x = 0; x < gd.w; x++)
                    printf("%02x", cave[y * CAVE_W + x]);
                printf("\n");
            }
    }
    return 0;
}
