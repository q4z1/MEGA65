// Lotus Run: the road line patterns as pixels, for render.s's
// road_draw: the road lines pre-drawn.
//
// Every pattern (road_rows.h: 512 widths, 2 variants, 4 phases) is drawn
// out once (road_rows.s, by DMA) into ROADPIX in attic RAM - in the colours of stripe set A, and
// from ROADPIX_B on in those of set B - the four phases of a width and
// variant one after the other. ROADIDX gets per width and variant: the
// pattern's start relative to the line's reference point, its length and
// where its first phase is (24 bits from ATTIC).
//
// Their sizes are known beforehand (road_row_len), so that no width and
// variant's patterns are cut by a bank boundary.

#include "road_pixels.h"

#include "dma.h"
#include "mem.h"
#include "render.h"
#include "road_rows.h"
#include "roadpat.h"

_Static_assert(ROAD_PIXELS <= ROADPIX_B, "the road patterns do not fit into ROADPIX");

_Static_assert((ROADPIX & 0xFFFF) == 0 && (ROADPIX_B & 0xFFFF) == 0, "ROADPIX must start a bank");

// Each shade's colour in stripe set A, B
static uint8_t colours_a[ROAD_SHADES], colours_b[ROAD_SHADES];

void road_pixels_init(void) {
    static uint8_t entry[8];
    for (uint8_t s = 0; s < ROAD_SHADES; s++) {
        colours_a[s] = (uint8_t)(s < ROAD_MIX ? COL_GRASS + s : COL_MIX + s - ROAD_MIX);
        colours_b[s] = (uint8_t)(s < ROAD_MIX ? COL_SET_B + s : COL_MIX + ROAD_MIXES + s - ROAD_MIX);
    }
    rr_colours = colours_a;
    rr_colours_b = colours_b;
    uint32_t at = ROADPIX - ATTIC;
    for (uint16_t w2 = 0; w2 < ROAD_WIDTHS; w2++)
        for (uint8_t v = 0; v < 2; v++) {
            // the four phases together, not across 64K: a DMA job keeps to
            // its bank (ROADPIX starts one)
            uint16_t size = 4 * road_row_len(w2, v);
            if ((uint16_t)at + size < (uint16_t)at)
                at = (at | 0xFFFF) + 1;
            rr_dst = ATTIC + at;
            rr_dst_b = rr_dst + ROADPIX_B;
            rr_w2 = w2;
            rr_v = v;
            for (rr_p = 0; rr_p < 4; rr_p++)
                road_row_draw();
            entry[0] = (uint8_t)rr_start;
            entry[1] = (uint8_t)(rr_start >> 8);
            entry[2] = (uint8_t)rr_len;
            entry[3] = (uint8_t)(rr_len >> 8);
            entry[4] = (uint8_t)at;
            entry[5] = (uint8_t)(at >> 8);
            entry[6] = (uint8_t)(at >> 16);
            entry[7] = 0;
            dma_copy((uint16_t)entry, ROADIDX + 8u * (2 * w2 + v), sizeof entry);
            dma_flush();
            at += size;
        }
}
