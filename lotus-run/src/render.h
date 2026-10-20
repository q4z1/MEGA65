// Lotus Run: drawing the race view.
//
// The drawing goes through fb.h, which the MEGA65 (fb_mega65.c) and the
// host tests implement. The race view's colours are palette entries: 1-7 the
// cars, 8-11 the scenery's (set per picture); the course's colours for the
// rest, set by render_palette: the road's stripes in two sets of grass,
// kerb, road and lane (COL_GRASS, COL_SET_B) and those mixed for smooth
// edges (COL_MIX), the backdrop's three, the sky's 16 bands down to the
// horizon. The stripes and the bands are drawn
// in their own colours - nothing changes while a picture is shown.

#ifndef RENDER_H
#define RENDER_H

#include <stdint.h>

#include "road.h"

#define COL_GRASS    12  // the stripes, set A: grass, kerb, road, lane
#define COL_SET_B    32  // set B: the same
#define COL_BACKDROP 20  // the backdrop: three colours
#define COL_SKY      64  // the sky: 16 bands
#define COL_SKY_KEY  15  // in the backdrop's pictures: the sky shows
#define COL_MIX      80  // the stripes' colours mixed (road_rows.h): set A's 18, then set B's

// What a picture of the race needs
typedef struct {
    const Track *track;
    uint32_t pos;     // the camera's position on the track
    int16_t lateral;  // the camera's sideways position (player +$4C)
    int16_t slope;    // the course's slope there: tilts the backdrop
    uint16_t angle;   // the direction (low 12 bits): scrolls the backdrop
} View;


// The palette entries of a course's colours
void render_palette(const Track *t);

void render_view(const View *v);

#endif
