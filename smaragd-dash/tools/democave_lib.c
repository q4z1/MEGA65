// Smaragd Dash: GDash's engine (src/gdengine.c) as a library for
// tools/democave.py, which plays the demo caves with it on the host:
// the same steps as the game, with the game's random numbers.

#include "gdengine.h"

void dc_start(const GdCaveFile *f, unsigned seed) {
    gd_start(f, seed);
}

void dc_step(int dir, int fire) {
    static const uint8_t mv[] = {MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_STILL};
    gd_iterate(mv[dir], fire != 0, false);
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
