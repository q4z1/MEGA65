// Smaragd Dash: where everything lies.
//
// The program itself - code, data, variables - is the linker's, in bank 0
// from $2001 up, with the soft stack growing down from $D000. All the
// memory the game takes besides is here, in the order of the addresses, and
// checked at compile time; the file `memmap` repeats it for mega65-mem,
// which shows the whole RAM with what is left free.
//
// Nothing here is swapped: everything has its own place for the whole
// game. Only two things are used for more than one purpose: the
// framebuffers hold the title screens as well as the cave, and cave_file
// (main.c) takes one cave after the other from the disk.

#ifndef MEM_H
#define MEM_H

#include <stdint.h>

#include "gfx.h"  // TILE_COUNT, LOGO_W, LOGO_H

// ---------------------------------------------------------------- bank 0

// The DMA list (dma.c): below the program, where BASIC had its screen; the
// game never goes back to BASIC. A frame takes up to 480 copy jobs.
#define DMA_LIST      ((uint8_t *)0x0800)
#define DMA_JOBS      500
#define DMA_LIST_SIZE (6 + DMA_JOBS * 12)  // header and jobs of 12 bytes
_Static_assert(0x0800 + DMA_LIST_SIZE <= 0x2000, "the DMA list reaches the program");

// ---------------------------------------------------------------- bank 1

// The graphics from the disk, which only DMA reads: bank 0 keeps its room
// for the program. The tiles take the DOS's work area as well (the game
// loads with its own loader and never calls the DOS), the logo ends at the
// colour RAM's first 2K at $1F800. In between there is room for more tiles.
#define GFX_BANK  1
#define TILES_OFF 0x0000u  // SMARAGD.TILES at $10000, TILE_COUNT x 256 bytes
#define LOGO_OFF  0x5600u  // SMARAGD.LOGO at $15600, LOGO_W x LOGO_H pixels
_Static_assert(TILES_OFF + TILE_COUNT * 256ul <= LOGO_OFF, "the tiles reach the logo");
_Static_assert(LOGO_OFF + (uint32_t)LOGO_W * LOGO_H <= 0xF800, "the logo reaches the colour RAM at $1F800");

// ---------------------------------------------------------------- banks 4 and 5

// A framebuffer at the start of each bank (video.c): 40 columns of 22
// characters of 64 bytes, column by column. Behind A the status line's
// characters, behind B the two screens that point to them.
#define FB_BANK_A   4
#define FB_BANK_B   5
#define FB_SIZE     (40 * 22 * 64u)  // $DC00
#define STATUS_BANK FB_BANK_A
#define STATUS_OFF  FB_SIZE          // 40 columns x 3 characters (2 rows, separator)
#define STATUS_SIZE (40 * 3 * 64u)
#define SCREEN_BANK FB_BANK_B
#define SCREEN_A    FB_SIZE          // 40x25 characters of 2 bytes
#define SCREEN_B    (SCREEN_A + 0x800u)
#define SCREEN_SIZE (40 * 25 * 2u)
_Static_assert(STATUS_OFF + (uint32_t)STATUS_SIZE <= 0x10000, "the status line leaves bank 4");
_Static_assert(SCREEN_A + SCREEN_SIZE <= SCREEN_B, "screen A reaches screen B");
_Static_assert(SCREEN_B + (uint32_t)SCREEN_SIZE <= 0x10000, "screen B leaves bank 5");

// ---------------------------------------------------------------- colour RAM

// $FF80000, all 0 (no attributes): written through its first 2K at $D800
// (video.c)

#endif
