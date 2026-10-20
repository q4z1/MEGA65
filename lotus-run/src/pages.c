// Lotus Run: the 640 x 400 pages (see pages.h).
//
// The VIC-IV shows 40 x 50 characters of 16 x 8 pixels in 16 colours: per
// character two bytes of screen RAM (its number) and two of colour RAM
// (16-colour mode, its palette bank). A page from the disk is the palette,
// then screen RAM, colour RAM and its characters, each run-length coded;
// the font's characters lie behind the page's (tools/mkpages.py).

#include "pages.h"

#include "banks.h"
#include "dma.h"
#include "hw.h"
#include "mem.h"
#include "video.h"

#define COLOUR_RAM 0xFF80000ul
#define CELLS      (PAGE_COLS * PAGE_ROWS)

bool pages_load(void) {
    if (!file_open("GLYPHS", PAGE_LOAD))
        return false;
    file_unpack(0, GLYPHS_ATTIC, GLYPHS_ATTIC + GLYPHS * 128ul);
    return true;
}

void pages_on(void) {
    // the VIC-IV's geometry for 640 x 400 from the "hot" registers, then
    // 40 characters a row of 16 pixels
    POKE(0xD05D, PEEK(0xD05D) | 0x80);
    POKE(0xD031, PEEK(0xD031) | 0xC8);  // H640, fast, V400
    POKE(0xD016, 0xC8);
    POKE(0xD011, 0x1B);
    POKE(0xD05D, PEEK(0xD05D) & 0x7F);
    POKE(0xD011, 0x0B);  // blank until a page is there
    POKE(0xD058, PAGE_COLS * 2);
    POKE(0xD059, 0);
    POKE(0xD05E, PAGE_COLS);
    POKE(0xD060, (uint8_t)PAGE_SCREEN);
    POKE(0xD061, (uint8_t)(PAGE_SCREEN >> 8));
    POKE(0xD062, (uint8_t)(PAGE_SCREEN >> 16));
    POKE(0xD063, 0);
    POKE(0xD020, 0);
    POKE(0xD021, 0);
    dma_copy(GLYPHS_ATTIC, PAGE_CHARS + (GLYPH_BASE - PAGE_CHAR_BASE) * 64ul, GLYPHS * 128u);
    dma_flush();
}

void pages_off(void) {
    video_on();
}

// A palette entry from 8-bit R, G, B (the VIC-IV keeps their nibbles swapped)
static uint8_t swap(uint8_t v) {
    return (uint8_t)(v << 4 | v >> 4);
}

bool page_show(const char *name) {
    if (!file_open(name, PAGE_LOAD))
        return false;
    POKE(0xD011, 0x0B);  // blank while the page comes in
    for (uint16_t i = 0; i < 256; i++) {
        POKE(0xD100 + i, swap(file_byte(3 * i)));
        POKE(0xD200 + i, swap(file_byte(3 * i + 1)));
        POKE(0xD300 + i, swap(file_byte(3 * i + 2)));
    }
    uint16_t chars = file_byte(768) | (uint16_t)file_byte(769) << 8;
    uint32_t off = file_unpack(770, PAGE_SCREEN, PAGE_SCREEN + CELLS * 2);
    off = file_unpack(off, COLOUR_RAM, COLOUR_RAM + CELLS * 2);
    file_unpack(off, PAGE_CHARS, PAGE_CHARS + chars * 64ul);
    POKE(0xD011, 0x1B);
    return true;
}

void page_text(uint8_t col, uint8_t row, const char *s, uint8_t colour) {
    static uint8_t top[PAGE_COLS * 2], bottom[PAGE_COLS * 2], attr[PAGE_COLS * 2];
    uint8_t n = 0;
    for (; *s && col + n < PAGE_COLS; s++, n++) {
        uint16_t ch = GLYPH_BASE + 2 * glyph_of(*s);
        top[2 * n] = (uint8_t)ch;
        top[2 * n + 1] = (uint8_t)(ch >> 8);
        bottom[2 * n] = (uint8_t)(ch + 1);
        bottom[2 * n + 1] = (uint8_t)((ch + 1) >> 8);
        attr[2 * n] = 0x08;
        attr[2 * n + 1] = (uint8_t)(colour << 4 | 0x0F);
    }
    if (!n)
        return;
    uint16_t at = (uint16_t)(row * PAGE_COLS + col) * 2;
    dma_copy((uint16_t)top, PAGE_SCREEN + at, 2u * n);
    dma_copy((uint16_t)bottom, PAGE_SCREEN + at + PAGE_COLS * 2, 2u * n);
    dma_copy((uint16_t)attr, COLOUR_RAM + at, 2u * n);
    dma_copy((uint16_t)attr, COLOUR_RAM + at + PAGE_COLS * 2, 2u * n);
    dma_flush();
}
