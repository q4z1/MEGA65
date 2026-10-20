// Lotus Run: the framebuffer the race view is drawn into.
//
// 320 x FB_H pixels, one palette index each. Implemented by fb_mega65.c on
// the MEGA65 and on the host for tests.

#ifndef FB_H_INCLUDED
#define FB_H_INCLUDED

#include <stdint.h>

#define FB_W 320
#define FB_H 200

// Pixels x0 .. x1 - 1 of row y in colour c; x0 < x1, both within 0 .. FB_W
void fb_span(uint8_t y, uint16_t x0, uint16_t x1, uint8_t c);

// Rows y0 .. y1 - 1 in colour c (nothing if y1 <= y0)
void fb_rows(uint8_t y0, uint8_t y1, uint8_t c);

// Pixels x .. x + len - 1 of row y from the sprite pixels at src (attic RAM
// on the MEGA65, banks.h), leaving out those of value SPR_CLEAR; all
// within the framebuffer
void fb_sprite_row(uint8_t y, uint16_t x, uint32_t src, uint16_t len);

// ROADPAT_MAX bytes of the road patterns (roadpat.h) from offset on, into
// buf: they are not in the program's memory on the MEGA65
void fb_roadpat(uint16_t offset, uint8_t *buf);

#endif
