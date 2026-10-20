// Lotus Run: fb.h on the MEGA65 - the picture in bank 4 (mem.h),
// 320 bytes per row, which video_show turns into characters.

#include "fb.h"

#include "dma.h"
#include "mem.h"
#include "sprbanks.h"

void fb_span(uint8_t y, uint16_t x0, uint16_t x1, uint8_t c) {
    dma_fill_low(PICTURE + (uint16_t)(y * FB_W + x0), c, x1 - x0);
}

void fb_rows(uint8_t y0, uint8_t y1, uint8_t c) {
    if (y1 > y0)
        dma_fill_low(PICTURE + (uint16_t)(y0 * FB_W), c, (uint16_t)((y1 - y0) * FB_W));
}

void fb_sprite_row(uint8_t y, uint16_t x, uint32_t src, uint16_t len) {
    dma_copy_transparent(src, PICTURE + (uint16_t)(y * FB_W + x), len, SPR_CLEAR);
}

void fb_key_row(uint8_t y, uint16_t x, uint32_t src, uint16_t len, uint8_t key) {
    dma_copy_transparent(src, PICTURE + (uint16_t)(y * FB_W + x), len, key);
}
