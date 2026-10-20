// Lotus Run: the road's projection (see road.h).
//
// 16-bit arithmetic throughout; only the vertical tables are scaled.

#include "road.h"

#include "math.h"
#include "tables.h"

uint16_t view_lines = 96;
uint16_t view_scale = 256;
int16_t view_y0 = 0;

// The line of depth step i: vbase[i] + (y * vscale[i]) >> 16, the tables
// scaled by view_scale (road_view)
static int16_t vbase[ROAD_STEPS];
static int16_t vscale[ROAD_STEPS];

void road_view(void) {
    for (uint8_t i = 0; i < ROAD_STEPS; i++) {
        vbase[i] = (int16_t)(((uint32_t)tab_base[i] * view_scale) >> 8);
        vscale[i] = (int16_t)(((uint32_t)tab_scale[i] * view_scale) >> 8);
    }
}

uint8_t road_project(const Track *t, uint32_t pos, RoadStep *steps, int16_t *top) {
    RoadStep *s = steps;
    uint8_t sub = (uint8_t)((uint16_t)pos >> 12);  // depth step within the segment
    uint16_t seg = (uint16_t)((pos >> 16) % t->segments);
    const Segment *g = &t->seg[seg];
    int16_t dx = 0, dy = 0, x = 0, y = 0;
    int16_t highest = (int16_t)view_lines;
    uint8_t i = 0;
    // 16 steps per segment: the rest of this one, 7 whole, the start of the 9th
    uint8_t n = 15 - sub;
    for (uint8_t k = 0; k < 9; k++) {
        int16_t curve = g->curve, hill = (int16_t)(g->hill * 2);
        uint8_t variant = g->variant;
        for (; n; n--) {
            dx += curve;
            dy -= hill;
            x += dx;
            y += dy;
            int16_t line = (int16_t)(mul16s(y, vscale[i]) >> 16) + vbase[i];
            i++;
            s->x = (int16_t)((x & ~1) | variant);
            s->line = line;
            if ((uint16_t)line >= view_lines) {
                if (line >= (int16_t)view_lines) {
                    // below the view: the steps so far
                    uint8_t count = (uint8_t)(s - steps);
                    steps[0].x &= 1;
                    steps[0].line = steps[0].top = (int16_t)view_lines;
                    steps[0].dx = 0;
                    *top = highest;
                    return count;
                }
                // above the view: this step ends the road
                s->line = 0;
                s->top = 0;
                uint8_t count = (uint8_t)(s - steps) + 1;
                steps[0].x &= 1;
                steps[0].line = steps[0].top = (int16_t)view_lines;
                steps[0].dx = 0;
                *top = 0;
                return count;
            }
            if (line < highest)
                highest = line;
            s->top = highest;
            s->dx = dx;
            s++;
        }
        g++;
        n = k < 7 ? 16 : sub + 1;
    }
    steps[0].x &= 1;
    steps[0].line = steps[0].top = (int16_t)view_lines;
    steps[0].dx = 0;
    *top = highest;
    return ROAD_STEPS;
}

void road_lines(const RoadStep *steps, uint8_t count, RoadLine *lines) {
    const RoadStep *s = &steps[count - 1];
    int16_t line = s->line;              // the line done last (farther)
    uint16_t scale = tab_scale[count - 1];
    int16_t depth = (int16_t)((count - 2) << 8);
    RoadLine *l = &lines[line];
    for (;;) {
        s--;
        uint8_t k = (uint8_t)(s - steps);
        int16_t near_line = s->line;
        int16_t x = s->x;
        uint16_t near_scale = tab_scale[k];
        if (near_line != line) {
            int16_t gap = line - near_line;
            if (gap == -1) {
                l->x = x;
                l->scale = scale;
                l->depth = (uint16_t)depth;
                l++;
            } else if (gap > 0) {
                // hidden behind a hill: go back up
                l -= gap;
            } else {
                uint16_t n = (uint16_t)-gap;
                int16_t ddepth = (int16_t)(256 / n);
                // (delta & ~15) / n in 16.16, in multiples of $1000
                uint16_t delta = (near_scale - scale) & 0xFFF0;
                int32_t step = (int32_t)(div32u((uint32_t)delta << 16, n) & ~0xFFFul);
                uint32_t sc = (uint32_t)scale << 16;
                for (uint16_t j = 0; j < n; j++) {
                    l->x = x;
                    l->scale = (uint16_t)(sc >> 16);
                    l->depth = (uint16_t)depth;
                    l++;
                    depth -= ddepth;
                    sc += (uint32_t)step;
                }
                depth = (int16_t)((depth & 0xFF00) + 0x100);
            }
            line = near_line;
        }
        scale = near_scale;
        depth -= 0x100;
        if (depth < 0)
            break;
    }
}
