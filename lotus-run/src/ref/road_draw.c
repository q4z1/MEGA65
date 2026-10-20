// Lotus Run: the road's lines into the picture, in C - the
// reference of render.s's road_draw (see road_draw.h), and what the host
// tests draw with.

#include "road_draw.h"

#include "math.h"
#include "road_rows.h"

// One road line: grass, then the pattern for its width and variant where
// it lands, in the colours of its set (base: grass, kerb, road, lane;
// mixes: the mixed ones)
static void road_line(uint8_t y, const RoadLine *l, int16_t lateral8, uint8_t base, uint8_t mixes) {
    static RoadRow row;
    // the reference point lands at 159 - (scale * 2 * (x + lateral8)) / 65536:
    // to a quarter pixel, the rest is the phase
    int32_t m = mul16s((int16_t)(l->scale * 2), (int16_t)(l->x + lateral8)) + 0x2000;
    road_row(l->scale >> 3, l->x & 1, (uint8_t)(m >> 14) & 3, &row);
    int16_t x = (int16_t)(159 - (int16_t)(m >> 16) + row.start);
    fb_span(y, 0, FB_W, base);
    for (uint8_t k = 0; k < row.n; k++) {
        uint8_t s = row.run[k].shade;
        uint8_t c = (uint8_t)(s < ROAD_MIX ? base + s : mixes + s - ROAD_MIX);
        int16_t end = (int16_t)(x + row.run[k].len);
        if (end > 0 && x < FB_W)
            fb_span(y, x < 0 ? 0 : (uint16_t)x, end > FB_W ? FB_W : (uint16_t)end, c);
        x = end;
    }
}

void road_draw(void) {
    for (uint8_t l = road_top; l < view_lines; l++) {
        uint8_t set = (uint8_t)((render_lines[l].depth + road_phase) >> 8) & 4;
        road_line((uint8_t)(view_y0 + l), &render_lines[l], road_lateral8, set ? COL_SET_B : COL_GRASS,
                  set ? COL_MIX + ROAD_MIXES : COL_MIX);
    }
}
