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

// The calls into GDash's engine (link.ld's .lowcode, src/gdfar.s), behind
// the DMA list: SMARAGD.LOW, loaded at the start
#define LOW_AT    0x1F80
_Static_assert(0x0800 + DMA_LIST_SIZE <= LOW_AT, "the DMA list reaches the calls into GDash's engine");

// What the program shares with GDash's engine lies at $C000, outside the
// engine's $4000-$BFFF (shared.ld, which has these numbers): cave[] and
// moved[] (engine.h), gd (gdengine.h), the cave being played (main.c's
// file); the C stack behind it, below $D000
#define GD_STATE_SIZE 256u    // gd at $C6E0
#define FILE_SIZE     0x410u  // file at $C7E0, to $CBF0

// The cave editor's code (link.ld's .editor): an overlay in the RAM under
// the KERNAL, which main.c switches out at the start; loaded from the disk
// (SMARAGD.EDIT) when the editor is opened
#define EDIT_AT   0xE000
#define EDIT_SIZE 0x1FFAu  // up to the CPU's vectors

// ---------------------------------------------------------------- bank 1

// The tiles from the disk, which only DMA reads: bank 0 keeps its room for
// the program. They take the DOS's work area as well (the game loads with
// its own loader and never calls the DOS), up to the colour RAM's first 2K
// at $1F800.
#define GFX_BANK  1
#define TILES_OFF 0x0000u  // SMARAGD.TILES at $10000, TILE_COUNT x 256 bytes
_Static_assert(TILES_OFF + TILE_COUNT * 256ul <= 0xF800, "the tiles reach the colour RAM at $1F800");

// ---------------------------------------------------------------- banks 2 and 3

// Where the C65 ROM is. The game needs none of it - the KERNAL is switched
// out, the disk read without the DOS - and makes it writable at the start
// (main.c; a copy in the attic RAM goes back before BASIC, a reset loads
// the ROM again): GDash's engine for the own caves (gdengine.ld, linked for
// $4000-$BFFF, where gdfar.s maps it while it runs), the title logo and the
// editor's cave while the editor is closed.
#define GD_BANK   2
#define GD_OFF    0x4000u  // SMARAGD.GD at $24000-$2BFFF
#define GD_SIZE   0x8000u
#define LOGO_BANK 3
#define LOGO_OFF  0x0000u  // SMARAGD.LOGO at $30000, LOGO_W x LOGO_H pixels
_Static_assert(LOGO_OFF + (uint32_t)LOGO_W * LOGO_H <= 0x10000, "the logo leaves bank 3");
// A step of GDash's engine while it is made in parts (main.c, "steps"):
// what lies at $C000 - cave[], moved[], gd (shared.ld) -, the step's and a
// copy of the one shown, behind the logo
#define STEP_AT    0xC000u
#define STEP_SIZE  0x7E0u    // to file at $C7E0
#define STEP_BANK  3
#define STEP_SHOWN 0xC000u   // $3C000
#define STEP_WORK  0xC800u   // $3C800
_Static_assert(LOGO_OFF + (uint32_t)LOGO_W * LOGO_H <= STEP_SHOWN, "the logo reaches the steps");
_Static_assert(STEP_SHOWN + STEP_SIZE <= STEP_WORK && STEP_WORK + STEP_SIZE <= 0xE000u, "the steps");

// The editor's cave while the editor is closed (main.c's edit_keep), in
// front of GDash's engine
#define KEEP_BANK 2
#define KEEP_OFF  0x0000u  // $20000, FILE_SIZE bytes
_Static_assert(KEEP_OFF + FILE_SIZE <= GD_OFF, "the kept cave reaches GDash's engine");

// ---------------------------------------------------------------- attic RAM

// The C65 ROM's banks 2 and 3 as they were at the start, copied back before
// the game goes back to BASIC (main.c's to_basic); behind them a byte that
// tells if the attic RAM is there, and BASIC's palette
#define ROM_SAVE_MB    0x80     // $8000000-$801FFFF
#define ROM_SAVE_BANKS 2        // the probe at $8020000
#define PAL_SAVE_OFF   0x0100u  // BASIC's palette at $8020100, 768 bytes

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
// Behind them the palettes from the disk (SMARAGD.PAL, mkgfx.py's pal.bin),
// which video.c sets once: two of 3 x 256 bytes
#define PAL_BANK    FB_BANK_B
#define PAL_OFF     0xF000u
_Static_assert(SCREEN_B + (uint32_t)SCREEN_SIZE <= PAL_OFF, "screen B reaches the palettes");
_Static_assert(PAL_OFF + 6 * 256ul <= 0x10000, "the palettes leave bank 5");

// ---------------------------------------------------------------- colour RAM

// $FF80000, all 0 (no attributes): written through its first 2K at $D800
// (video.c)

#endif
