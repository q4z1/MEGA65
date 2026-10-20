// Lotus Run: the sprite banks in attic RAM (see banks.h).
//
// A bank file is loaded to PICTURE (free before the race), then unpacked
// into attic RAM by DMA: a literal run is a copy, a repeated pixel a fill.
// What the program keeps of a bank is its directory: per image width,
// height and where its pixels are.

#include "banks.h"

#include "disk.h"
#include "dma.h"
#include "mem.h"
#include "sprbanks.h"
#include "sprites.h"

#define LOAD PICTURE

uint8_t banks_pool[BANKS_POOL];
uint16_t banks_dir[SPR_BANKS];
static uint16_t pool_used;
static uint32_t attic_used;

// The loaded file, through a window of 256 bytes
static uint8_t win[256];
static uint32_t win_at;

static uint8_t rd(uint32_t off) {
    uint32_t base = off & ~0xFFul;
    if (base != win_at) {
        dma_copy(LOAD + base, (uint16_t)win, sizeof win);
        dma_flush();
        win_at = base;
    }
    return win[(uint8_t)off];
}

static bool load_bank(uint8_t b) {
    if (banks_dir[b])
        return true;
    char name[] = "SPR00";
    name[3] = "0123456789ABCDEF"[b >> 4];
    name[4] = "0123456789ABCDEF"[b & 15];
    if (!disk_load(name, LOAD))
        return false;
    win_at = ~0ul;
    uint8_t n = rd(0);
    if (pool_used + 1 + 5u * n > BANKS_POOL)
        return false;
    uint8_t *e = banks_pool + pool_used;
    banks_dir[b] = pool_used + 1;
    pool_used += 1 + 5u * n;
    *e++ = n;
    uint32_t end = attic_used;
    for (uint8_t i = 0; i < n; i++) {
        uint8_t w = rd(1 + 2u * i), h = rd(2 + 2u * i);
        *e++ = w;
        *e++ = h;
        *e++ = (uint8_t)end;
        *e++ = (uint8_t)(end >> 8);
        *e++ = (uint8_t)(end >> 16);
        end += (uint16_t)(w * h);
    }
    uint32_t off = 1 + 2u * n, out = attic_used;
    while (out < end) {
        uint8_t c = rd(off++), len;
        if (c < 0x80) {
            len = c + 1;
            dma_copy(LOAD + off, ATTIC + out, len);
            off += len;
        } else {
            len = c - 0x7E;
            dma_fill(ATTIC + out, rd(off++), len);
        }
        out += len;
    }
    dma_flush();
    attic_used = end;
    return true;
}

bool banks_load(const Track *t) {
    for (uint8_t b = 0; b < SPR_BANKS; b++)
        banks_dir[b] = 0;
    pool_used = 0;
    attic_used = BANKS_ATTIC - ATTIC;
    if (!load_bank(SPR_CARS) || !load_bank(SPR_HUD))
        return false;
    // the scenery every course has ($80-$83), then the course's
    for (uint8_t i = 0; i < 4; i++)
        if (!load_bank(spr_bank_of_type[i]))
            return false;
    for (uint16_t s = 0; s < t->segments; s++)
        for (uint8_t q = 0; q < 4; q++) {
            uint8_t type = t->seg[s].object[q].type;
            if (type < 0x80 || type >= 0xAC)
                continue;
            uint8_t b = spr_bank_of_type[type - 0x80];
            if (b == 0xFF || !load_bank(b))
                return false;
        }
    return true;
}

static const uint8_t *entry(uint8_t bank, uint8_t image) {
    return banks_pool + banks_dir[bank] + 5u * image;
}

uint8_t sprite_width(uint8_t bank, uint8_t image) {
    return entry(bank, image)[0];
}

uint8_t sprite_height(uint8_t bank, uint8_t image) {
    return entry(bank, image)[1];
}

uint32_t sprite_pixels(uint8_t bank, uint8_t image) {
    const uint8_t *e = entry(bank, image);
    return ATTIC + (e[2] | (uint32_t)e[3] << 8 | (uint32_t)e[4] << 16);
}
