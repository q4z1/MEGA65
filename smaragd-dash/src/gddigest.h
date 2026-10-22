// Smaragd Dash: the digest of a step of GDash's engine, to compare the
// engine as the MEGA65 runs it with src/gdengine.c on the host
// (tests/test_gdmega65.py): the cave's map and what the game takes from
// the engine's state. Used by main.c (built with -DGDCHECK) and
// tests/gdplay.c alike.

#ifndef GDDIGEST_H
#define GDDIGEST_H

#include <stdint.h>

#include "gdengine.h"

static uint32_t gd_mix(uint32_t h, uint32_t v) {
    for (uint8_t k = 0; k < 4; k++, v >>= 8)
        h = (h << 5) + h + (uint8_t)v;
    return h;
}

static uint32_t gd_digest(void) {
    uint32_t h = 5381;
    for (uint8_t y = 0; y < gd.h; y++) {
        const uint8_t *row = cave + (uint16_t)y * CAVE_W;
        for (uint8_t x = 0; x < gd.w; x++)
            h = (h << 5) + h + row[x];
    }
    h = gd_mix(h, gd.player_state);
    h = gd_mix(h, (uint32_t)(uint8_t)gd.player_x << 8 | (uint8_t)gd.player_y);
    h = gd_mix(h, gd.diamonds_collected);
    h = gd_mix(h, (uint32_t)gd.time);
    h = gd_mix(h, gd.score);
    h = gd_mix(h, gd.speed);
    h = gd_mix(h, gd.sound);
    return h;
}

#endif
