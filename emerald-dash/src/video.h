// Emerald Dash: the screen.
//
// 40x25 characters in full-colour mode (FCM, 8x8 pixels, one byte per
// pixel). Rows 0-1 are the status line, row 2 a separator, rows 3-24 the
// playfield: 304x176 visible pixels, 19 x 11 tiles.
//
// Every playfield character is unique, so the playfield is a framebuffer
// that DMA fills with 16x16 tiles each frame. Its characters are stored
// column by column, so within a column the pixel rows follow each other
// 8 bytes apart and a tile half can be placed at any pixel row with one DMA
// copy: vertical scrolling is free. Horizontal fine scrolling uses the
// character generator position (TEXTXPOS), switched while the separator row
// is drawn so the status line stays put. Two framebuffers alternate.

#ifndef VIDEO_H
#define VIDEO_H

#include <stdbool.h>
#include <stdint.h>

#define VIEW_W 304  // visible playfield in pixels
#define VIEW_H 176

void video_init(void);

// A frame: video_sync waits until the separator row is on screen and sets
// the playfield's horizontal scroll; video_render then draws the hidden
// framebuffer and video_show waits for the vertical blank and shows it.
// Game logic runs between video_show and the next video_sync.
void video_sync(void);

// tiles[] holds a tile number per cave cell (only the cells in view are
// read), (cam_x, cam_y) is the top left pixel of the view.
void video_render(const uint8_t *tiles, uint16_t cam_x, uint16_t cam_y);

void video_show(void);

// Background (pixel value 0) white for the exit flash, or black again
void video_flash(bool on);

// Status line: 38 usable columns (1-38). Text uses the characters of the
// generated font; a byte >= 0x80 is icon number (byte - 0x80).
void status_print(uint8_t col, const char *text);
void status_put(uint8_t col, uint8_t ch);
uint8_t status_code_at(uint8_t col);  // what is shown in a column

// Text screens in the playfield area (both framebuffers, no scrolling):
// col is the character column (1-38 visible), y the pixel row (0-175).
void video_clear(void);
void video_text(uint8_t col, uint8_t y, const char *text);
void video_big_text(uint8_t col, uint8_t y, const char *text);  // 2 columns per letter
void video_shine(uint8_t phase);  // cycle the big letters' colours

#endif
