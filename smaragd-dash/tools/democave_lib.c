// Smaragd Dash: GDash's engine (src/gdengine.c) as a library for
// tools/democave.py, which plays the demo caves with it on the host:
// the same steps as the game, with the game's random numbers (or, built
// with GD_EXACT, GDash's: tests/test_mechanics.py).

#include <stdio.h>

#include "gdengine.h"

void dc_start(const GdCaveFile *f, unsigned seed) {
    gd_start(f, seed);
}

void dc_step(int dir, int fire, int suicide) {
    static const uint8_t mv[] = {MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_STILL};
    gd_iterate(mv[dir], fire != 0, suicide != 0);
}

const uint8_t *dc_cave(void) {
    return cave;
}

// player state, x, y, diamonds collected, needed, gate open, visible time,
// score of the last step, keys 1-3, sweet, hammer
void dc_state(int *out) {
    out[0] = gd.player_state;
    out[1] = gd.player_x;
    out[2] = gd.player_y;
    out[3] = gd.diamonds_collected;
    out[4] = gd.diamonds_needed;
    out[5] = gd.gate_open;
    out[6] = gd_time_visible();
    out[7] = gd.score;
    out[8] = gd.key1;
    out[9] = gd.key2;
    out[10] = gd.key3;
    out[11] = gd.sweet_eaten;
    out[12] = gd.got_pneumatic_hammer;
    out[13] = gd.gravity;
    out[14] = gd.speed;
}

// The state after step t as a line, as the test oracle's "moves" prints it
// (toolchain/tools/gdash-oracle/oracle.cpp)
void dc_line(int t, char *out, int size) {
    uint32_t hash = 2166136261u;
    for (int y = 0; y < gd.h; y++)
        for (int x = 0; x < gd.w; x++)
            hash = (hash ^ cave[y * CAVE_W + x]) * 16777619u;
#define FLAG(f) ((gd.flags & GDF_##f) != 0)
    snprintf(out, size,
             "%d %08x st=%d dia=%d/%d time=%d score=%d speed=%d p=%d,%d keys=%d,%d,%d sweet=%d hammer=%d "
             "dkey=%d skel=%d grav=%d gate=%d amoeba=%d,%d magic=%d sw=%d%d%d%d%d%d",
             t, (unsigned)hash, gd.player_state, gd.diamonds_collected, gd.diamonds_needed, (int)gd.time, gd.score,
             gd.speed, gd.player_x, gd.player_y, gd.key1, gd.key2, gd.key3, gd.sweet_eaten,
             gd.got_pneumatic_hammer, gd.diamond_key_collected, gd.skeletons_collected, gd.gravity,
             gd.gate_open, gd.amoeba_state, gd.amoeba_2_state, gd.magic_wall_state, FLAG(CREATURES_BACKWARDS),
             FLAG(EXPANDING_WALL_CHANGED), FLAG(REPLICATORS_ACTIVE), FLAG(CONVEYOR_BELTS_ACTIVE),
             FLAG(CONVEYOR_BELTS_DIRECTION_CHANGED), FLAG(GRAVITY_SWITCH_ACTIVE));
}
