// Lotus Run: where everything lies.
//
// The program itself - code, data, variables - is the linker's, in bank 0
// from $2001 up. All the memory the game takes besides is here, in the
// order of the addresses; the file `memmap` repeats it for mega65-mem.

#ifndef MEM_H
#define MEM_H

#include <stdint.h>

// ---------------------------------------------------------------- bank 0

// The DMA list being collected (dma.c): below the program, where BASIC had
// its screen; the game never goes back to BASIC.
#define DMA_LIST      ((uint8_t *)0x0800)
#define DMA_LIST_SIZE 0x1800u
_Static_assert(0x0800 + DMA_LIST_SIZE <= 0x2000, "the DMA list reaches the program");

// ---------------------------------------------------------------- bank 1

// The screen: 40 x 25 characters of 2 bytes, each pointing to its own
// character in bank 5 (video.c)
#define SCREEN      0x10000ul
#define SCREEN_SIZE (40 * 25 * 2u)

// The DMA list that turns the picture into the characters (video.c):
// 8 jobs per pixel row
#define CONV_LIST      0x10800ul
#define CONV_JOB       25u  // 13 bytes of options, end, 11 of the job
#define CONV_LIST_SIZE (200 * 8 * CONV_JOB + 1)
_Static_assert(SCREEN + SCREEN_SIZE <= CONV_LIST, "the screen reaches the conversion list");
_Static_assert(CONV_LIST + CONV_LIST_SIZE <= 0x1F800, "the conversion list reaches the colour RAM at $1F800");

// The road line patterns (ROADPAT from the disk, tools/mkdata.py)
#define ROADPAT 0x1A800ul
_Static_assert(CONV_LIST + CONV_LIST_SIZE <= ROADPAT, "the conversion list reaches the road patterns");
_Static_assert(ROADPAT + 9600 <= 0x1D000, "the road patterns reach their index");

// Where every road line pattern lies as pixels in ROADPIX (road_pixels.c):
// 512 entries of 8 bytes
#define ROADIDX      0x1D000ul
#define ROADIDX_SIZE (512 * 8u)
_Static_assert(ROADIDX + ROADIDX_SIZE <= 0x1F800, "the road pattern index reaches the colour RAM at $1F800");

// ---------------------------------------------------------------- banks 4 and 5

// The picture is drawn into PICTURE, 320 x 200 pixels, one byte each, row
// after row; CHARS holds what the VIC-IV shows: 1000 characters of 8 x 8
// pixels, row after row (video.c).
#define PICTURE 0x40000ul
#define CHARS   0x50000ul

// ---------------------------------------------------------------- attic RAM

#define ATTIC 0x8000000ul

// The road line patterns as pixels (road_pixels.c), then the sprite banks
// of the course (banks.c), one byte per pixel
#define ROADPIX      ATTIC
#define ROADPIX_SIZE 0x24000ul
#define BANKS_ATTIC  (ROADPIX + ROADPIX_SIZE)

// ---------------------------------------------------------------- colour RAM

// $FF80000, all 0 (no attributes): written through its first 2K at $D800
// (video.c)

#endif
