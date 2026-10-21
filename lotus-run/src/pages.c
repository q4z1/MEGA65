// Lotus Run: the 640 x 400 pages (see pages.h).
//
// The VIC-IV shows 40 x 50 characters of 16 x 8 pixels in 16 colours: per
// character two bytes of screen RAM (its number) and two of colour RAM
// (16-colour mode, its palette bank). A page from the disk is the palette,
// then screen RAM, colour RAM and its characters, each packed
// (tools/mkpages.py), then its animation: frame count, first row, rows,
// and per frame its rows of screen RAM, then of colour RAM, as they are -
// put in by DMA from the file (in attic RAM while the page is shown). Text put in
// at run time gets characters of its own
// behind the page's: each text row its 2 x PAGE_COLS, two glyphs of 8 x 16
// pixels side by side making a character's top and bottom.

#include "pages.h"

#include "banks.h"
#include "dma.h"
#include "hw.h"
#include "mem.h"
#include "video.h"

#define COLOUR_RAM 0xFF80000ul
#define CELLS      (PAGE_COLS * PAGE_ROWS)

MENU bool pages_load(void) {
    if (!file_open("GLYPHS", PAGE_LOAD))
        return false;
    file_unpack(0, GLYPHS_ATTIC, GLYPHS_ATTIC + (GLYPHS + DIGIT_CHARS) * 64ul);
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
}

void pages_off(void) {
    video_on();
}

// Screen or colour RAM from the file at off: the cells' low bytes, then
// their high ones, put together (returns where they end in the file)
MENU static uint32_t planes(uint32_t off, uint32_t to) {
    off = file_unpack(off, PAGE_PLANES, PAGE_PLANES + CELLS * 2);
    dma_copy_step(PAGE_PLANES, 0x0100, to, 0x0200, CELLS);
    dma_copy_step(PAGE_PLANES + CELLS, 0x0100, to + 1, 0x0200, CELLS);
    dma_flush();
    return off;
}

// The text rows' characters: from text_base, TEXT_ROW_CHARS per row put in
// (row_slot: its number + 1, 0: none yet)
#define TEXT_ROW_CHARS (2 * PAGE_COLS)
static uint16_t text_base, text_end;
// The page's animation (page_frame, pages.s): its frames, the first one's
// rows in the file (in attic RAM), how long a frame's rows of screen RAM
// are, where they go
LOW_RAM uint8_t anim_frames;
LOW_RAM uint32_t anim_src;
LOW_RAM uint16_t anim_len, anim_at;
static uint8_t row_slot[PAGE_ROWS], slots;

MENU bool page_show(const char *name) {
    if (!file_open(name, PAGE_LOAD))
        return false;
    POKE(0xD011, 0x0B);  // blank while the page comes in
    for (uint16_t i = 0; i < 256; i++)
        video_rgb((uint8_t)i, file_byte(3 * i), file_byte(3 * i + 1), file_byte(3 * i + 2));
    uint16_t chars = file_byte(768) | (uint16_t)file_byte(769) << 8;
    text_base = (uint16_t)(PAGE_CHAR_BASE + chars);
    text_end = PAGE_CHAR_END;
    for (uint8_t r = 0; r < PAGE_ROWS; r++)
        row_slot[r] = 0;
    slots = 0;
    uint32_t off = planes(770, PAGE_SCREEN);
    off = planes(off, COLOUR_RAM);
    uint32_t at = file_unpack(off, PAGE_CHARS, PAGE_CHARS + chars * 64ul);
    anim_frames = file_byte(at);
    anim_at = (uint16_t)file_byte(at + 1) * (PAGE_COLS * 2);
    anim_len = (uint16_t)file_byte(at + 2) * (PAGE_COLS * 2);
    anim_src = PAGE_LOAD + at + 3;
    POKE(0xD011, 0x1B);
    return true;
}

MENU void page_text(uint8_t col, uint8_t row, const char *s, uint8_t colour) {
    WORK_RAM static uint8_t glyph[2][64], pair[128];
    WORK_RAM static uint8_t top[PAGE_COLS * 2], bottom[PAGE_COLS * 2], attr[PAGE_COLS * 2];
    if (!row_slot[row]) {
        if (text_base + (slots + 1) * TEXT_ROW_CHARS > text_end)
            return;  // no characters left
        row_slot[row] = ++slots;
    }
    uint16_t ch = (uint16_t)(text_base + (row_slot[row] - 1) * TEXT_ROW_CHARS + 2 * col);
    uint8_t n = 0;
    for (; *s && col + n < PAGE_COLS; n++, ch += 2) {
        // two glyphs, the second a space at the end
        for (uint8_t g = 0; g < 2; g++) {
            dma_copy(GLYPHS_ATTIC + 64u * glyph_of(*s), (uint16_t)glyph[g], 64);
            if (*s)
                s++;
        }
        dma_flush();
        for (uint8_t y = 0; y < 16; y++) {
            uint8_t *to = pair + (y < 8 ? 8 * y : 64 + 8 * (y - 8));
            const uint8_t *a = glyph[0] + 4 * y, *b = glyph[1] + 4 * y;
            for (uint8_t i = 0; i < 4; i++) {
                to[i] = a[i];
                to[4 + i] = b[i];
            }
        }
        dma_copy((uint16_t)pair, PAGE_CHARS + (uint32_t)(ch - PAGE_CHAR_BASE) * 64, sizeof pair);
        dma_flush();
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

// The digits' characters at the end, before the text's
#define DIGIT_BASE (PAGE_CHAR_END - DIGIT_CHARS)

MENU void page_digits_in(void) {
    dma_copy(GLYPHS_ATTIC + GLYPHS * 64ul, PAGE_CHARS + (uint32_t)(DIGIT_BASE - PAGE_CHAR_BASE) * 64,
             DIGIT_CHARS * 64u);
    dma_flush();
    text_end = DIGIT_BASE;
}

MENU void page_digit(uint8_t col, uint8_t row, bool big, uint8_t d) {
    WORK_RAM static uint8_t cells[DIGIT_BIG_W * 2], attr[DIGIT_BIG_W * 2];
    const uint8_t *c = big ? digit_big[d] : digit_small[d];
    uint8_t w = big ? DIGIT_BIG_W : DIGIT_SMALL_W, h = big ? DIGIT_BIG_H : DIGIT_SMALL_H;
    for (uint8_t r = 0; r < h; r++) {
        for (uint8_t i = 0; i < w; i++) {
            uint16_t ch = (uint16_t)(DIGIT_BASE + *c++);
            cells[2 * i] = (uint8_t)ch;
            cells[2 * i + 1] = (uint8_t)(ch >> 8);
            attr[2 * i] = 0x08;
            attr[2 * i + 1] = TEXT_LCD << 4 | 0x0F;
        }
        uint16_t at = (uint16_t)((row + r) * PAGE_COLS + col) * 2;
        dma_copy((uint16_t)cells, PAGE_SCREEN + at, 2u * w);
        dma_copy((uint16_t)attr, COLOUR_RAM + at, 2u * w);
        dma_flush();
    }
}

