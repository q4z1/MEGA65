// Lotus Run: where the pictures go - scenery, cars, the overlays of the
// race view - for every picture: farthest first, so nearer ones cover them.
//
// The images are the sprite banks of tools/mksprites.py (sprbanks.h).
// Positions: x a screen column, y in the road's lines (road.h, view_lines
// tall).

#ifndef SPRITES_H
#define SPRITES_H

#include <stdint.h>

#include "road.h"
#include "sprbanks.h"

// One image to draw: rows y - height + 1 .. y; if y > clip only those above
// clip (the road's top line where the object stands: hills hide the rest)
typedef struct {
    uint8_t bank, image;
    int16_t x, y;  // left column, bottom row
    int16_t clip;
} Sprite;

#define SPRITES_MAX 80
extern Sprite sprite_list[SPRITES_MAX];
extern uint8_t sprite_count;

// The sizes of the images (the banks of the course, loaded)
uint8_t sprite_width(uint8_t bank, uint8_t image);
uint8_t sprite_height(uint8_t bank, uint8_t image);

// What the placement keeps from one image to the next, and from picture to
// picture
typedef struct {
    uint16_t last_w;  // the last image placed by its middle: width,
    int16_t last_x;   // left column
    int16_t last_y;   // and bottom row
    uint16_t angle;   // the last car's angle (0-8)
    int16_t dx;       // the road's direction where the last thing stood
} SpriteState;
extern SpriteState sprite_state;

// The pictures of player 1's view, from its projection (road_project): fills
// sprite_list. Uses race (race.h) and race_track.
void sprites_place(const RoadStep *steps, uint8_t count);

// The sprites of sprite_list into the picture (through fb.h's
// fb_sprite_row; render.s writes the DMA jobs itself): the rows down to the
// bottom row, or those above the clip row if it reaches below it; on
// screen, line y is row view_y0 + y
void sprites_draw(void);

#endif
