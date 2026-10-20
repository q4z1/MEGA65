// Lotus Run: drawing the race view (see render.h).
//
// The road is drawn line by line from pre-drawn road lines: the pattern
// for the line's width, shifted by the road's position to a quarter pixel,
// in the colours of its stripe set (road_draw.h). Above the horizon the sky's bands, the
// backdrop over them.

#include "render.h"

#include "banks.h"
#include "fb.h"
#include "mem.h"
#include "road_draw.h"
#include "road_rows.h"
#include "sprites.h"
#include "video.h"

// the depth steps: on the MEGA65 at a fixed place (mem.h)
#ifdef __mos__
#define steps ((RoadStep *)ROAD_STEPS_AT)
_Static_assert(ROAD_STEPS * sizeof(RoadStep) <= ROAD_STEPS_AT_SIZE, "the depth steps do not fit");
#else
static RoadStep steps[ROAD_STEPS];
#endif

// The backdrop above the horizon (row top of the picture): 32 rows, its
// bottom at (16 - slope) / 2 + 32 in a 96-line view (scaled), no lower
// than the horizon; scrolled by the direction (960 pixels a turn)
static void backdrop(const View *v, int16_t top) {
    int16_t bottom = (int16_t)(((int16_t)(16 - v->slope) >> 1) + 32);
    bottom = (int16_t)(((int32_t)bottom * view_scale) >> 8);
    int16_t y = (int16_t)(bottom - BACK_H), row = 0;
    if (y < 0) {
        row = (int16_t)-y;
        y = 0;
    }
    if (bottom > top)
        bottom = top;
    uint16_t x = (uint16_t)((((uint32_t)(v->angle & 0xFFF) * 0x3C00) >> 16) + 1);
    if (x >= BACK_W)
        x -= BACK_W;
    uint32_t src = backdrop_pixels() + (uint32_t)row * BACK_W;
    for (; y < bottom; y++, src += BACK_W) {
        // the panorama goes round: from x to its end, then from its start
        uint16_t first = BACK_W - x < FB_W ? BACK_W - x : FB_W;
        uint8_t sy = (uint8_t)(view_y0 + y);
        fb_key_row(sy, 0, src + x, first, COL_SKY_KEY);
        if (first < FB_W)
            fb_key_row(sy, first, src, FB_W - first, COL_SKY_KEY);
    }
}

static uint16_t header_word(const Track *t, uint8_t i) {
    return (uint16_t)(t->header[2 * i] << 8 | t->header[2 * i + 1]);
}

// 4-bit channels a and b mixed, q quarters of b: as light (about the
// square of the value, in quarters so that it stays in 16 bits), back to
// 8 bits
__attribute__((noinline)) static uint8_t mix(uint8_t a, uint8_t b, uint8_t q) {
    uint8_t a8 = (uint8_t)(a * 17), b8 = (uint8_t)(b * 17);
    uint16_t m = (uint16_t)(((uint16_t)a8 * a8 >> 2) * (uint8_t)(4 - q) + ((uint16_t)b8 * b8 >> 2) * q);
    uint8_t r = 0;
    for (uint8_t bit = 128; bit; bit >>= 1)
        if ((uint16_t)(r | bit) * (uint16_t)(r | bit) <= m)
            r |= bit;
    return r;
}

// A stripe set's colours (header words from `word` on) mixed in pairs, in
// road_rows.h's order, into palette entries from `to` on
static void mixes(const Track *t, uint8_t word, uint8_t to) {
    uint8_t rgb[3];
    for (uint8_t i = 0; i < 4; i++)
        for (uint8_t j = i + 1; j < 4; j++) {
            uint16_t a = header_word(t, (uint8_t)(word + i)), b = header_word(t, (uint8_t)(word + j));
            for (uint8_t q = 1; q < 4; q++) {
                for (uint8_t c = 0; c < 3; c++) {
                    uint8_t shift = (uint8_t)(8 - 4 * c);
                    rgb[c] = mix(a >> shift & 15, b >> shift & 15, q);
                }
                video_rgb(to++, rgb[0], rgb[1], rgb[2]);
            }
        }
}

void render_palette(const Track *t) {
    for (uint8_t k = 0; k < 4; k++) {
        video_colour(COL_GRASS + k, header_word(t, (uint8_t)(4 + k)));
        video_colour(COL_SET_B + k, header_word(t, (uint8_t)(8 + k)));
    }
    mixes(t, 4, COL_MIX);
    mixes(t, 8, COL_MIX + ROAD_MIXES);
    for (uint8_t k = 0; k < 3; k++)
        video_colour(COL_BACKDROP + k, header_word(t, (uint8_t)(1 + k)));
    for (uint8_t k = 0; k < 16; k++)
        video_colour(COL_SKY + k, header_word(t, (uint8_t)(12 + k)));
}

// The sky down to the horizon (screen row): 16 bands of 4 lines (scaled)
// ending at it, the first one on screen reaching up to the top
static void sky(int16_t horizon) {
    int16_t band = (int16_t)(4 * view_scale >> 8);
    uint8_t first = 1;
    for (uint8_t k = 0; k < 16; k++) {
        int16_t y0 = (int16_t)(horizon - band * (16 - k)), y1 = (int16_t)(y0 + band);
        if (y1 <= 0)
            continue;
        if (first) {
            y0 = 0;
            first = 0;
        }
        if (y1 > horizon)
            y1 = horizon;
        if (y0 < y1)
            fb_rows((uint8_t)y0, (uint8_t)y1, (uint8_t)(COL_SKY + k));
    }
}

void render_view(const View *v) {
    int16_t top;
    uint8_t count = road_project(v->track, v->pos, steps, &top);
    road_lines(steps, count, render_lines);
    sky((int16_t)(view_y0 + top));
    backdrop(v, top);
    road_top = (uint8_t)top;
    road_lateral8 = (int16_t)(v->lateral * 8);
    road_phase = (uint16_t)(v->pos >> 4) & 0x7FF;
    road_draw();

    sprites_place(steps, count);
    sprites_draw();
}
