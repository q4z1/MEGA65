// Wedge Turbo: the screen (see video.h).
//
// The characters lie in bank 5 row after row, so in a pixel row of the
// screen the 8 pixels of a character follow each other and the next
// character's are 64 bytes on. A pixel row of the picture thus goes into
// the characters with 8 DMA jobs, one per pixel position within a
// character: every 8th byte of the row to every 64th byte. The 1600 jobs
// for the whole picture are built once (CONV_LIST, bank 1).

#include "video.h"

#include "dma.h"
#include "hw.h"
#include "irq.h"
#include "mem.h"

#define COLS     40
#define ROWS     25
#define LINESTEP (COLS * 2)

static uint16_t bottom;  // first raster line of the bottom border

static uint16_t raster(void) {
    uint8_t lo, hi;
    do {
        hi = PEEK(0xD053);
        lo = PEEK(0xD052);
    } while (hi != PEEK(0xD053));
    return ((hi & 7) << 8) | lo;
}

void video_colour(uint8_t i, uint16_t rgb4) {
    // a 4-bit channel n is n * 17 in 8 bits: both nybbles the same,
    // so the VIC-IV's swapped nybbles change nothing
    POKE(0xD100 + i, (rgb4 >> 8 & 15) * 17);
    POKE(0xD200 + i, (rgb4 >> 4 & 15) * 17);
    POKE(0xD300 + i, (rgb4 & 15) * 17);
}

// The VIC-IV keeps the nybbles of a channel swapped
static uint8_t swap(uint8_t v) {
    return (uint8_t)(v << 4 | v >> 4);
}

void video_rgb(uint8_t i, uint8_t r, uint8_t g, uint8_t b) {
    POKE(0xD100 + i, swap(r));
    POKE(0xD200 + i, swap(g));
    POKE(0xD300 + i, swap(b));
}

uint8_t video_frame(void) {
    return PEEK(0xD7FA);
}

// The screen: character (c, r) is character number CHARS / 64 + r * 40 + c
static void build_screen(void) {
    LOW_RAM static uint8_t row[LINESTEP];
    for (uint8_t r = 0; r < ROWS; r++) {
        uint16_t ch = (uint16_t)(CHARS / 64) + r * COLS;
        for (uint8_t c = 0; c < COLS; c++, ch++) {
            row[c * 2] = (uint8_t)ch;
            row[c * 2 + 1] = ch >> 8;
        }
        dma_copy((uint16_t)row, SCREEN + r * LINESTEP, LINESTEP);
        dma_flush();
    }
}

// The conversion list: per pixel row y and position k in a character,
// 40 bytes from PICTURE + y * 320 + k (every 8th) to the characters
static void build_conversion(void) {
    LOW_RAM static uint8_t jobs[8 * CONV_JOB];
    for (uint8_t y = 0; y < 200; y++) {
        uint8_t *q = jobs;
        for (uint8_t k = 0; k < 8; k++) {
            uint32_t src = PICTURE + (uint16_t)y * 320 + k;
            uint32_t dst = CHARS + (uint16_t)(y >> 3) * (COLS * 64) + (y & 7) * 8 + k;
            static const uint8_t opts[13] = {0x0A, 0x80, 0, 0x81, 0, 0x82, 0x00, 0x83, 0x08,
                                             0x84, 0x00, 0x85, 0x40};
            for (uint8_t i = 0; i < 13; i++)
                q[i] = opts[i];
            q[2] = (uint8_t)(src >> 20);
            q[4] = (uint8_t)(dst >> 20);
            q[13] = 0x00;  // end of options
            q[14] = (y == 199 && k == 7) ? 0 : 4;  // copy, chained but the last
            q[15] = COLS;
            q[16] = 0;
            q[17] = (uint8_t)src;
            q[18] = (uint8_t)(src >> 8);
            q[19] = (uint8_t)(src >> 16) & 0x0F;
            q[20] = (uint8_t)dst;
            q[21] = (uint8_t)(dst >> 8);
            q[22] = (uint8_t)(dst >> 16) & 0x0F;
            q[23] = 0;  // modulo (unused)
            q[24] = 0;
            q += CONV_JOB;
        }
        dma_copy((uint16_t)jobs, CONV_LIST + (uint16_t)y * (8 * CONV_JOB), sizeof jobs);
        dma_flush();
    }
}

void video_on(void) {
    // 40x25 characters at the standard position: let the "hot" VIC-II
    // registers set up the VIC-IV, then take over.
    POKE(0xD05D, PEEK(0xD05D) | 0x80);
    POKE(0xD031, (PEEK(0xD031) & ~0xA8) | 0x40);  // no H640/V400/attributes; fast
    POKE(0xD016, 0xC8);
    POKE(0xD011, 0x1B);
    bottom = PEEK(0xD04A) | ((PEEK(0xD04B) & 0x0F) << 8);
    POKE(0xD05D, PEEK(0xD05D) & 0x7F);  // hot registers off

    POKE(0xD020, 0);
    POKE(0xD021, 0);
    POKE(0xD015, 0);                    // no sprites
    POKE(0xD054, PEEK(0xD054) | 0x47);  // 16-bit chars, full colour for all, fast
    POKE(0xD058, LINESTEP);
    POKE(0xD059, 0);
    POKE(0xD05E, COLS);
    POKE(0xD064, 0);                    // colour RAM from its start
    POKE(0xD065, 0);
    POKE(0xD070, 0x00);                 // edit and use palette 0
    POKE(0xD030, PEEK(0xD030) | 0x04);  // colours 0-15 from palette RAM too
    for (uint16_t i = 0; i < 256; i++)
        video_colour((uint8_t)i, 0);

    // Colour RAM all 0 (no attributes): its first 2K at $D800
    POKE(0xD030, PEEK(0xD030) | 0x01);
    for (uint16_t i = 0; i < ROWS * LINESTEP; i++)
        POKE(0xD800 + i, 0);
    POKE(0xD030, PEEK(0xD030) & ~0x01);

    dma_fill(PICTURE, 0, 0);  // 0: 64K
    dma_fill(CHARS, 0, 0);
    dma_flush();
    POKE(0xD060, (uint8_t)SCREEN);
    POKE(0xD061, (uint8_t)(SCREEN >> 8));
    POKE(0xD062, (uint8_t)(SCREEN >> 16));
    POKE(0xD063, 0);

}

void video_init(void) {
    build_screen();
    build_conversion();
    irq_init();
    video_on();
}

void video_show(void) {
    dma_flush();
    uint16_t r;
    do
        r = raster();
    while (r < bottom || r >= bottom + 40);
    dma_run_list(CONV_LIST);
}
