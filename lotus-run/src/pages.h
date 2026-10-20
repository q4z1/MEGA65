// Lotus Run: the screens around the race - title, menus, the car's pages -
// in 640 x 400 with 16-colour characters (tools/mkpages.py renders them).
//
// The race uses the same memory for its picture, so pages_on and pages_off
// switch between the two; the race's video is set up again by video_on.

#ifndef PAGES_H_INCLUDED
#define PAGES_H_INCLUDED

#include <stdbool.h>
#include <stdint.h>

#include "pages_gen.h"

// Loads what the pages need from the disk (the font)
bool pages_load(void);

// The 640 x 400 mode on, off (back to the race's video, video.h)
void pages_on(void);
void pages_off(void);

// Shows page `name` (the disk's file P + name, e.g. "PTITLE")
bool page_show(const char *name);

// Text at a cell (col 0-39, row 0-48: two glyphs to a column, each two
// rows high) in one of the TEXT_* colours
void page_text(uint8_t col, uint8_t row, const char *s, uint8_t colour);

#endif
