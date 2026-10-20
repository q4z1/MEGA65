// Lotus Run: what road_draw reads (see road_draw.h); the
// drawing itself is in render.s, and in ref/road_draw.c.

#include "road_draw.h"

RoadLine render_lines[FB_H];
uint8_t road_top;
int16_t road_lateral8;
uint16_t road_phase;
