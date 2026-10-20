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

// The course (TRACKnn from the disk): in the RAM under the KERNAL, which
// irq_init switches out - so it is loaded (by DMA) and read only after that
#define TRACK_BUF      ((uint8_t *)0xE000)
#define TRACK_BUF_SIZE 0x1FF0u
_Static_assert(0xE000 + TRACK_BUF_SIZE <= 0xFFFA, "the course reaches the interrupt vectors");

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

// The road line patterns as pixels (road_pixels.c), the course's backdrop
// (960 x 32), then its sprite banks (banks.c), one byte per pixel
#define ROADPIX      ATTIC
#define ROADPIX_SIZE 0x24000ul
#define BACKDROP     (ROADPIX + ROADPIX_SIZE)
#define BACKDROP_SIZE 0x7800ul
// the panel (banks.c, panel.c): as shown, then as on the disk (its picture
// without values, then the values' pictures)
#define PANEL_LIVE   (BACKDROP + BACKDROP_SIZE)
#define PANEL_DATA   (PANEL_LIVE + 0x1200ul)
#define PANEL_SIZE   0x9000ul
// the lap bar's pictures (banks.c, panel.c)
#define LAPBAR_DATA  (PANEL_DATA + PANEL_SIZE)
#define LAPBAR_SIZE  0x3800ul
#define BANKS_ATTIC  (LAPBAR_DATA + LAPBAR_SIZE)

// ---------------------------------------------------------------- colour RAM

// $FF80000, all 0 (no attributes): written through its first 2K at $D800
// (video.c)

#endif
