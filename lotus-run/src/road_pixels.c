// Lotus Run: the road line patterns as pixels, for render.s's
// road_draw: the road lines pre-drawn.
//
// ROADPAT (from the disk) has every pattern as runs of colour; here they
// are drawn out once, one after the other, into ROADPIX in attic RAM, and
// ROADIDX gets per pattern: its start relative to its reference point
// (as ROADPAT's), its length and where its pixels are (24 bits from ATTIC).

#include "road_pixels.h"

#include <string.h>

#include "dma.h"
#include "fb.h"
#include "mem.h"
#include "render.h"
#include "roadpat.h"

_Static_assert(ROADPAT_PIXELS <= ROADPIX_SIZE, "the road patterns do not fit into ROADPIX");

void road_pixels_init(void) {
    uint32_t at = ROADPIX - ATTIC;
    static uint8_t pat[ROADPAT_MAX];
    static uint8_t entry[8];
    for (uint16_t i = 0; i < 512; i++) {
        fb_roadpat(roadpat_index[i], pat);
        uint32_t first = at;
        for (uint8_t k = 0; k < pat[2]; k++) {
            uint8_t code = pat[3 + k];
            dma_fill(ATTIC + at, (uint8_t)(COL_GRASS + (code >> 6)), code & 63);
            at += code & 63;
        }
        entry[0] = pat[0];
        entry[1] = pat[1];
        entry[2] = (uint8_t)(at - first);
        entry[3] = (uint8_t)((at - first) >> 8);
        entry[4] = (uint8_t)first;
        entry[5] = (uint8_t)(first >> 8);
        entry[6] = (uint8_t)(first >> 16);
        entry[7] = 0;
        dma_copy((uint16_t)entry, ROADIDX + 8u * i, sizeof entry);
        dma_flush();
    }
}
