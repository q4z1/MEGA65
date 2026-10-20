// Lotus Run: drawing the race view (see render.h).
//
// The road is drawn line by line from pre-drawn road lines: the pattern
// for the line's width, shifted by the road's position (road_draw.h). Its
// stripes are not drawn: colours 12-15 change where the stripe phase
// changes (irq.s), and so does the sky above the horizon.

#include "render.h"

#include "banks.h"
#include "fb.h"
#include "road_draw.h"
#include "sprites.h"

ColourTable render_colours;

static RoadStep steps[ROAD_STEPS];

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
        fb_image_row(sy, 0, src + x, first);
        if (first < FB_W)
            fb_image_row(sy, first, src, FB_W - first);
    }
}

static uint16_t header_word(const Track *t, uint8_t i) {
    return (uint16_t)(t->header[2 * i] << 8 | t->header[2 * i + 1]);
}

// From screen row y on: colours 12-15 the course's header words
// first .. first + 3, colour 15 sky instead if given
static void colours_at(int16_t y, const Track *t, uint8_t first, uint16_t sky) {
    ColourTable *c = &render_colours;
    if (c->count == RENDER_COLOURS)
        return;
    uint8_t i = c->count++;
    c->line[i] = (uint8_t)(y < 0 ? 0 : y);
    for (uint8_t k = 0; k < 4; k++)
        c->colours[i][k] = header_word(t, (uint8_t)(first + k));
    if (sky)
        c->colours[i][3] = sky;
}

void render_view(const View *v) {
    const Track *t = v->track;
    int16_t top;
    uint8_t count = road_project(t, v->pos, steps, &top);
    road_lines(steps, count, render_lines);
    render_colours.count = 0;

    // above the horizon: colour 15, the course's 16 sky colours in bands of
    // 4 lines (scaled) ending at the horizon, the first one above them;
    // 12-14 the backdrop's (header words 1-3)
    int16_t horizon = (int16_t)(view_y0 + top);
    fb_rows(0, (uint8_t)horizon, COL_SKY);
    backdrop(v, top);
    int16_t band = (int16_t)(4 * view_scale >> 8);
    for (uint8_t k = 0; k < 16; k++) {
        int16_t from = (int16_t)(horizon - band * (16 - k));
        if (from + band <= 0 && k != 15)
            continue;
        colours_at(render_colours.count ? from : 0, t, 1, header_word(t, (uint8_t)(12 + k)));
    }

    // the road; where the stripe phase changes, the other set of colours
    road_top = (uint8_t)top;
    road_lateral8 = (int16_t)(v->lateral * 8);
    road_phase = (uint16_t)(v->pos >> 4) & 0x7FF;
    road_draw();
    for (uint8_t i = 0; i < road_changes; i++)
        colours_at(road_change_row[i], t, road_change_set[i] ? 8 : 4, 0);

    sprites_place(steps, count);
    sprites_draw();
}
