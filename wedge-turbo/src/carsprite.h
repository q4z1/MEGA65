// Wedge Turbo: the player's car near as the MEGA65's hardware sprites.
//
// The race's picture is 320 x 200; the player's car, the nearest and
// largest thing in it, is shown finer: by the eight hardware sprites of 16
// colours side by side, in 640 x 400 pixels (CARHI, tools/mkcars.py's
// hardware()). sprites.c says when and where; the image is copied to
// chip RAM when it changes, and the sprites are placed when a picture is
// shown.

#ifndef CARSPRITE_H
#define CARSPRITE_H

#include <stdbool.h>
#include <stdint.h>

// CARHI into attic RAM, once; false
// if it cannot be loaded
bool car_sprite_load(void);

// Before a race: their colours (palette 1, which the sprites use), sizes,
// pointers
void car_sprite_race(void);

// What the next shown picture has: image 0-17 (the angle, + 9 with the
// brake lights lit) or CAR_SPRITE_OFF; the car's middle (640 across) and
// its bottom row (of the picture)
#define CAR_SPRITE_OFF 0xFF
extern uint8_t car_sprite_image;
extern int16_t car_sprite_x, car_sprite_row;

// With the picture being shown (video_show): the sprites as set
void car_sprite_show(void);

// Off (for the pages)
void car_sprite_off(void);

#endif
