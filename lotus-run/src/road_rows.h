// Lotus Run: one road line pattern with smooth edges, as runs (see
// road_rows.c) - drawn out once into attic RAM (road_pixels.c) and drawn
// straight into the picture by road_draw's reference (ref/road_draw.c).

#ifndef ROAD_ROWS_H
#define ROAD_ROWS_H

#include <stdint.h>

// What a pixel shows: 0 grass, 1 kerb, 2 road, 3 lane, or from ROAD_MIX on
// two of them mixed: ROAD_MIX + 3 * pair + k for the pair (i, j), i < j,
// numbered (0,1) (0,2) (0,3) (1,2) (1,3) (2,3), with (k + 1) / 4 of j
#define ROAD_MIX    4
#define ROAD_MIXES  18
#define ROAD_SHADES (ROAD_MIX + ROAD_MIXES)

// The widths there are patterns for: a line's scale >> 3
#define ROAD_WIDTHS 512

typedef struct {
    uint16_t len;
    uint8_t shade;
} RoadRun;

typedef struct {
    int16_t start;  // its first pixel, relative to the line's reference point
    uint16_t len;   // its pixels: the same in all four phases
    uint8_t n;      // its runs
    RoadRun run[48];
} RoadRow;

// The pattern of width w2 and variant v (a line's x & 1) in phase p (0-3:
// the road p quarter pixels further left)
void road_row(uint16_t w2, uint8_t v, uint8_t p, RoadRow *row);

// Its length, without drawing it
uint16_t road_row_len(uint16_t w2, uint8_t v);

// The same in assembly, on the MEGA65 (road_rows.s): the pattern of width
// rr_w2, variant rr_v, phase rr_p drawn by DMA (dma.h's list) to rr_dst
// with each shade s in colour rr_colours[s], and to rr_dst_b in colour
// rr_colours_b[s]; both moved on past it; its start and length into
// rr_start, rr_len
extern uint16_t rr_w2;
extern uint8_t rr_v, rr_p;
extern const uint8_t *rr_colours, *rr_colours_b;
extern uint32_t rr_dst, rr_dst_b;
extern int16_t rr_start;
extern uint16_t rr_len;
void road_row_draw(void);

#endif
