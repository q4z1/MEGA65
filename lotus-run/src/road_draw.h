// Lotus Run: the road's lines into the picture - render.c's inner
// loop. In assembly on the MEGA65 (render.s); ref/road_draw.c is its
// reference in C, and draws through fb.h for the host tests.
//
// Every line is grass, then the runs of its road line pattern (kerb, road,
// lane) where the pattern for its width lands, then grass - in the colours
// of its stripe set (bit 10 of the line's depth + the phase): COL_GRASS or
// COL_SET_B on.

#ifndef ROAD_DRAW_H
#define ROAD_DRAW_H

#include <stdint.h>

#include "fb.h"
#include "render.h"
#include "road.h"

// What road_draw reads: the lines (road_lines), the first one, the
// camera's sideways position * 8, the stripe phase from the position
extern RoadLine render_lines[FB_H];
extern uint8_t road_top;
extern int16_t road_lateral8;
extern uint16_t road_phase;

// Lines road_top .. view_lines - 1 into screen rows view_y0 + line
void road_draw(void);

#endif
