// Wedge Turbo: the road's projection: 128 depth steps from a position on the
// track, then the values for every screen line between them.
//
// Lines are counted in units of a 96-line view, the horizon near 39;
// view_scale makes the view taller.

#ifndef ROAD_H
#define ROAD_H

#include <stdint.h>

#include "track.h"

#define ROAD_STEPS 128

// One depth step
typedef struct {
    int16_t x;     // road centre, world units; bit 0: road line variant
    int16_t line;  // screen line
    int16_t top;   // highest line of the road up to here (hills hide more)
    int16_t dx;    // direction
} RoadStep;

// One screen line
typedef struct {
    int16_t x;       // road centre (as RoadStep.x)
    uint16_t scale;  // perspective: road width is about scale / 8 pixels
    uint16_t depth;  // depth step * 256, for the stripes
} RoadLine;

// The view: lines 0 .. view_lines - 1; line = base + y * scale >> 16, both
// scaled by view_scale / 256 (256: 96 lines). road_view
// takes a change of view_scale over.
extern uint16_t view_lines;
extern uint16_t view_scale;
// On screen, line l is row view_y0 + l
extern int16_t view_y0;
void road_view(void);

// Projects the road from pos (high word: segment, low word: way through it).
// Fills steps[]; returns their count and the highest road line in *top.
uint8_t road_project(const Track *t, uint32_t pos, RoadStep *steps, int16_t *top);

// Fills lines[top .. view_lines - 1] from the steps.
void road_lines(const RoadStep *steps, uint8_t count, RoadLine *lines);

#endif
