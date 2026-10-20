// Lotus Run: the road's lines into the picture - render.c's inner
// loop. In assembly on the MEGA65 (render.s); ref/road_draw.c is its
// reference in C, and draws through fb.h for the host tests.
//
// Every line is grass, then the runs of its road line pattern (kerb, road,
// lane) where the pattern for its width lands, then grass.

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

// What it notes: the screen rows where the stripe set changes (bit 10 of
// the line's depth + the phase) and the new set (0 or 4: that bit in the
// high byte), for the colour table
extern uint8_t road_changes;
extern uint8_t road_change_row[RENDER_COLOURS];
extern uint8_t road_change_set[RENDER_COLOURS];

// Lines road_top .. view_lines - 1 into screen rows view_y0 + line
void road_draw(void);

#endif
