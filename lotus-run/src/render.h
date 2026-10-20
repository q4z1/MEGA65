// Lotus Run: drawing the race view.
//
// The drawing goes through fb.h, which the MEGA65 (fb_mega65.c) and the
// host tests implement. The race view has 16 colours, palette indices
// 0-15: 1-7 the cars, 8-11 the scenery's (set per picture), 12-15 changing
// down the screen - backdrop and sky above the horizon, the stripes' grass,
// kerb, road and lane below. render_view fills a table of those
// changes (render_colours) that irq.s plays while the picture is shown.

#ifndef RENDER_H
#define RENDER_H

#include <stdint.h>

#include "road.h"

#define COL_SKY   15  // above the horizon
#define COL_GRASS 12  // below: grass, kerb, road, lane
#define COL_ROAD  14

// What a picture of the race needs
typedef struct {
    const Track *track;
    uint32_t pos;     // the camera's position on the track
    int16_t lateral;  // the camera's sideways position (player +$4C)
    int16_t slope;    // the course's slope there: tilts the backdrop
    uint16_t angle;   // the direction (low 12 bits): scrolls the backdrop
} View;


// The changes of colours 12-15 down the picture: from screen row
// line[i] on, colours[i] (four colours $0RGB)
#define RENDER_COLOURS 64
typedef struct {
    uint8_t count;
    uint8_t line[RENDER_COLOURS];
    uint16_t colours[RENDER_COLOURS][4];
} ColourTable;
extern ColourTable render_colours;

void render_view(const View *v);

#endif
