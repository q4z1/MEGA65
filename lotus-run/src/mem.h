// Lotus Run: where everything lies.
//
// The program itself - code, data, variables - is the linker's, in bank 0
// from $2001 up. All the memory the game takes besides is here, in the
// order of the addresses; the file `memmap` repeats it for mega65-mem.

#ifndef MEM_H
#define MEM_H

#include <stdint.h>

// ---------------------------------------------------------------- bank 0

// The projection's depth steps (render.c): in what was the KERNAL's and
// BASIC's work area; the KERNAL is switched out from video_init on
#define ROAD_STEPS_AT      0x0400
#define ROAD_STEPS_AT_SIZE 0x0400u

// The DMA list being collected (dma.c): below the program, where BASIC had
// its screen; the game never goes back to BASIC.
#define DMA_LIST      ((uint8_t *)0x0800)
#define DMA_LIST_SIZE 0x0C00u

// Variables that need no clearing, beside the program (link.ld): WORK_RAM
// in the KERNAL's work area $0200-$03FF, LOW_RAM behind the DMA list up to
// the program, HIGH_RAM behind the course under the KERNAL (WORK_RAM and
// HIGH_RAM only once irq_init has switched that out). Not on the host.
#define LOW_RAM_AT    0x1400
#define HIGH_RAM_AT   0xF100
_Static_assert(0x0800 + DMA_LIST_SIZE <= LOW_RAM_AT, "the DMA list reaches LOW_RAM");
// The code of the pages between the races (link.ld's .menu, built with
// LOTUS_MENU_OVERLAY): copied to MENU_AT from MENU_ATTIC before it runs, in
// place of the course and HIGH_RAM, which the race fills again
#define MENU_AT   0xE000
#define MENU_SIZE 0x1FFAu
#if defined(__mos__) && defined(LOTUS_MENU_OVERLAY)
#define MENU __attribute__((section(".menu")))
#else
#define MENU
#endif
#ifdef __mos__
#define WORK_RAM __attribute__((section(".workram")))
#define LOW_RAM  __attribute__((section(".lowram")))
#define HIGH_RAM __attribute__((section(".highram")))
#else
#define WORK_RAM
#define LOW_RAM
#define HIGH_RAM
#endif

// The course (TRACKnn from the disk): in the RAM under the KERNAL, which
// irq_init switches out - so it is loaded (by DMA) and read only after that
#define TRACK_BUF      ((uint8_t *)0xE000)
#define TRACK_BUF_SIZE 0x1100u
_Static_assert(0xE000 + TRACK_BUF_SIZE <= HIGH_RAM_AT, "the course reaches HIGH_RAM");

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

// The race's sound samples (sound.c, from SOUNDS in attic RAM): the audio
// DMA reads chip RAM only. They share the room with the pages' screen, so
// they are copied here at the start of every race.
#define SOUND_CHIP      0x1A500ul
#define SOUND_CHIP_SIZE 0x5300u
_Static_assert(CONV_LIST + CONV_LIST_SIZE <= SOUND_CHIP, "the conversion list reaches the sound samples");
_Static_assert(SOUND_CHIP + SOUND_CHIP_SIZE <= 0x1F800, "the sound samples reach the colour RAM at $1F800");

// The screen of the 640 x 400 pages (pages.c): 40 x 50 characters of 2 bytes
#define PAGE_SCREEN      0x1E000ul
#define PAGE_SCREEN_SIZE (40 * 50 * 2u)
_Static_assert(PAGE_SCREEN + PAGE_SCREEN_SIZE <= 0x1F800, "the pages' screen reaches the colour RAM at $1F800");
_Static_assert(PAGE_SCREEN >= SOUND_CHIP, "the pages' screen is part of the sound samples' room");

// ---------------------------------------------------------------- banks 4 and 5

// The picture is drawn into PICTURE, 320 x 200 pixels, one byte each, row
// after row; CHARS holds what the VIC-IV shows: 1000 characters of 8 x 8
// pixels, row after row (video.c). The pages (pages.c) take both banks for
// their 16-colour characters, from PAGE_CHARS on.
#define PICTURE 0x40000ul
#define CHARS   0x50000ul
#define PAGE_CHARS 0x40000ul

// ---------------------------------------------------------------- attic RAM

#define ATTIC 0x8000000ul

// The course's backdrop (960 x 32), then its sprite banks (banks.c), one
// byte per pixel
#define BACKDROP     ATTIC
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
// a page as loaded from the disk, the text font (pages.c), from 1M on
#define PAGE_LOAD    (ATTIC + 0x100000ul)
#define GLYPHS_ATTIC (ATTIC + 0x120000ul)
// a page's screen or colour RAM as in the file, before it is put together
#define PAGE_PLANES  (ATTIC + 0x130000ul)
// the names (season.c, TEXTS)
#define TEXTS_ATTIC  (ATTIC + 0x140000ul)
// the race's sound samples (sound.c, SOUNDS), copied to SOUND_CHIP
#define SOUNDS_ATTIC (ATTIC + 0x148000ul)
// where every road line pattern lies as pixels in ROADPIX (road_pixels.c):
// per width scale >> 3 (512) and variant (2) an entry of 8 bytes, read by
// road_draw through a 32-bit pointer
#define ROADIDX      (ATTIC + 0x150000ul)
#define ROADIDX_SIZE (1024 * 8u)
// the code of the pages (MENU), and the course coming next as on the disk
// (its header for the pages; to TRACK_BUF for the race)
#define MENU_ATTIC   (ATTIC + 0x154000ul)
#define TRACK_ATTIC  (ATTIC + 0x158000ul)
// The road line patterns as pixels (road_pixels.c), from 2M on: in the
// colours of stripe set A, from ROADPIX + ROADPIX_B on in those of set B
#define ROADPIX      (ATTIC + 0x200000ul)
#define ROADPIX_B    0x130000ul
#define ROADPIX_SIZE (2 * ROADPIX_B)

// ---------------------------------------------------------------- colour RAM

// $FF80000, all 0 (no attributes): written through its first 2K at $D800
// (video.c)

#endif
