// Lotus Run: what road_draw reads and notes (see road_draw.h); the
// drawing itself is in render.s, and in ref/road_draw.c.

#include "road_draw.h"

RoadLine render_lines[FB_H];
uint8_t road_top;
int16_t road_lateral8;
uint16_t road_phase;
uint8_t road_changes;
uint8_t road_change_row[RENDER_COLOURS];
uint8_t road_change_set[RENDER_COLOURS];
