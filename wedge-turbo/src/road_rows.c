// Wedge Turbo: a road line pattern with smooth edges (see road_rows.h).
//
// The edges of the pattern of width w2 lie at road_edge * s / 32 +
// ROAD_EDGE_BASE / 64 for the width s = w2 / 2 + 1/4 (the middle of the
// widths it stands for), in 1/64 pixel: road_edge * w2 + road_edge / 2 +
// ROAD_EDGE_BASE (tools/mkdata.py has the same). Every pixel takes what
// covers it: one colour, or the two that cover most of it, mixed in
// quarters.

#include "road_rows.h"

#include "roadpat.h"

static int16_t edge(int8_t c, uint16_t w2) {
    return (int16_t)((int16_t)c * (int16_t)w2 + (c >> 1) + ROAD_EDGE_BASE);
}

static RoadRow *out;
static uint8_t cover[4], covered;  // of the pixel being worked on, in 1/64

static void put(uint16_t len, uint8_t shade) {
    if (out->n && out->run[out->n - 1].shade == shade) {
        out->run[out->n - 1].len += len;
        return;
    }
    out->run[out->n].len = len;
    out->run[out->n].shade = shade;
    out->n++;
}

// The shade of the pixel covered
static uint8_t mixed(void) {
    uint8_t a = 0;
    for (uint8_t i = 1; i < 4; i++)
        if (cover[i] > cover[a])
            a = i;
    uint8_t b = a ? 0 : 1;
    for (uint8_t i = 0; i < 4; i++)
        if (i != a && cover[i] > cover[b])
            b = i;
    uint8_t quarters = (uint8_t)((cover[b] + 8) >> 4);  // of b: 0-2
    if (!quarters)
        return a;
    uint8_t i = a < b ? a : b, j = a ^ b ^ i;
    uint8_t pair = i ? i + j : j - 1;
    return (uint8_t)(ROAD_MIX + 3 * pair + (b == j ? quarters - 1 : 3 - quarters));
}

// Colour c from at to end (1/64 pixel from the pattern's start)
static void run(uint16_t at, uint16_t end, uint8_t c) {
    while (at < end) {
        if (!(at & 63) && end - at >= 64) {
            uint16_t n = (end - at) >> 6;
            put(n, c);
            at += n << 6;
            continue;
        }
        uint16_t to = (at | 63) + 1;
        if (to > end)
            to = end;
        cover[c] += (uint8_t)(to - at);
        covered += (uint8_t)(to - at);
        at = to;
        if (covered == 64) {
            put(1, mixed());
            cover[0] = cover[1] = cover[2] = cover[3] = 0;
            covered = 0;
        }
    }
}

// The first pixel and the end of the pattern: from the first edge in
// phase 3 to the last in phase 0
static int16_t first_pixel(uint16_t w2, uint8_t v) {
    return (int16_t)((edge(road_edge[v][0], w2) - 48) >> 6);
}

static int16_t end_pixel(uint16_t w2, uint8_t v) {
    return (int16_t)((edge(road_edge[v][road_runs[v]], w2) + 63) >> 6);
}

uint16_t road_row_len(uint16_t w2, uint8_t v) {
    return (uint16_t)(end_pixel(w2, v) - first_pixel(w2, v));
}

void road_row(uint16_t w2, uint8_t v, uint8_t p, RoadRow *row) {
    const int8_t *c = road_edge[v];
    uint8_t runs = road_runs[v];
    row->start = first_pixel(w2, v);
    row->len = road_row_len(w2, v);
    row->n = 0;
    out = row;
    // positions from the pattern's start, phase p further left
    int16_t from = (int16_t)(row->start * 64 + 16 * p);
    uint16_t at = 0;
    for (uint8_t k = 0; k <= runs; k++) {
        uint16_t e = (uint16_t)(edge(c[k], w2) - from);
        run(at, e, k ? road_colour[v][k - 1] : 0);
        at = e;
    }
    run(at, row->len * 64, 0);
}
