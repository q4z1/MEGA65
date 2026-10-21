// Wedge Turbo: the road line patterns as pixels, for render.s (see
// road_pixels.c)

#ifndef ROAD_PIXELS_H
#define ROAD_PIXELS_H

// Draws them out of ROADPAT, which must be loaded; once, from the code run
// at the start (mem.h's BOOT_CODE)
void road_pixels_init(void);

#endif
