// Lotus Run: the screen.
//
// 40 x 25 characters in full-colour mode (8 x 8 pixels, one byte per pixel),
// every one of them its own: a 320 x 200 picture. The game draws into a
// plain picture of 320 x 200 bytes (fb_mega65.c); video_show turns it into
// the characters with one DMA list while the beam is in the lower border,
// so the picture changes as a whole.

#ifndef VIDEO_H
#define VIDEO_H

#include <stdint.h>

void video_init(void);

// Back to the race's screen (after pages.h's 640 x 400): black until there
// is a picture
void video_on(void);

// Palette entry i from a 12-bit colour ($0RGB)
void video_colour(uint8_t i, uint16_t rgb4);

// Waits for the lower border and shows what was drawn
void video_show(void);

// The frame counter, counted up by the VIC-IV ($D7FA)
uint8_t video_frame(void);

#endif
