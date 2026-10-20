// Lotus Run: the sprite banks a course needs and its backdrop
// (tools/mksprites.py), in attic RAM.
//
// Each bank is a file SPRnn on the disk; banks_load loads those of a
// course: the scenery it has, the scenery every course has, the cars, the
// overlays of the race view. sprites.h's sprite_width and sprite_height
// give the images' sizes.

#ifndef BANKS_H
#define BANKS_H

#include <stdbool.h>
#include <stdint.h>

#include "sprbanks.h"
#include "track.h"

// False if a file cannot be loaded or there is no room left
bool banks_load(const Track *t);

// Where the pixels of an image lie, row after row (28-bit address)
uint32_t sprite_pixels(uint8_t bank, uint8_t image);

// Backdrop n (BACKn, 0-9) into attic RAM; false if it cannot be loaded.
// backdrop_pixels: where its BACK_W x BACK_H colours lie, row after row
bool backdrop_load(uint8_t n);
uint32_t backdrop_pixels(void);

// The panel of the race view (PANEL): its picture without values
// (PANEL_W x PANEL_H), where it is shown from, and per value field its place
// in it and the pictures of its states (w x h each, one after the other)
typedef struct {
    uint8_t x, y, w, h, states;
    uint32_t pixels;
} PanelField;
extern PanelField panel_fields[PANEL_FIELDS];
bool panel_load(void);
uint32_t panel_base(void);
uint32_t panel_live(void);

// The lap bar's pictures (LAPBAR): overlay 23 as drawn for 1-LAPBAR_LAPS
// laps (LAPBAR_W x LAPBAR_H each), then a box's row (16 pixels) filled with
// each of 16 masks
bool lapbar_load(void);
uint32_t lapbar_pixels(void);

// Copies len bytes from src to dst (both from these addresses)
void attic_copy(uint32_t src, uint32_t dst, uint16_t len);

// The directories (for render.s): per bank its image count, then per image
// width, height and the 24-bit offset of its pixels in ATTIC; banks_dir[b]
// is 1 + where bank b's is in banks_pool (0: not loaded), so the entry of
// image i is at banks_pool + banks_dir[b] + 5 * i
#define BANKS_POOL 2560
extern uint8_t banks_pool[BANKS_POOL];
extern uint16_t banks_dir[SPR_BANKS];

#endif
