// Lotus Run: the road's lines into the picture, in C - the
// reference of render.s's road_draw (see road_draw.h), and what the host
// tests draw with.

#include "road_draw.h"

#include "math.h"
#include "roadpat.h"

// One road line: grass, then the pattern's runs, then grass
static void road_line(uint8_t y, const RoadLine *l, int16_t lateral8) {
    uint8_t w = (uint8_t)(l->scale >> 4);
    static uint8_t pattern[ROADPAT_MAX];
    fb_roadpat(roadpat_index[2 * w + (l->x & 1)], pattern);
    const uint8_t *p = pattern;
    // where the pattern's reference point (357 + w) lands on screen:
    // 159 - shift
    int16_t shift = (int16_t)(mul16s((int16_t)(l->scale * 2), (int16_t)(l->x + lateral8)) >> 16);
    int16_t x = (int16_t)(159 - shift + (int16_t)(p[0] | p[1] << 8));
    uint8_t n = p[2];
    p += 3;
    if (x > 0)
        fb_span(y, 0, x > FB_W ? FB_W : (uint16_t)x, COL_GRASS);
    while (n--) {
        uint8_t code = *p++;
        int16_t end = (int16_t)(x + (code & 63));
        if (end > 0 && x < FB_W)
            fb_span(y, x < 0 ? 0 : (uint16_t)x, end > FB_W ? FB_W : (uint16_t)end, COL_GRASS + (code >> 6));
        x = end;
    }
    if (x < 0)
        x = 0;
    if (x < FB_W)
        fb_span(y, (uint16_t)x, FB_W, COL_GRASS);
}

void road_draw(void) {
    uint8_t shown = 0xFF;
    road_changes = 0;
    for (uint8_t l = road_top; l < view_lines; l++) {
        uint8_t y = (uint8_t)(view_y0 + l);
        uint8_t set = (uint8_t)((render_lines[l].depth + road_phase) >> 8) & 4;
        if (set != shown) {
            if (road_changes < RENDER_COLOURS) {
                road_change_row[road_changes] = y;
                road_change_set[road_changes] = set;
                road_changes++;
            }
            shown = set;
        }
        road_line(y, &render_lines[l], road_lateral8);
    }
}
