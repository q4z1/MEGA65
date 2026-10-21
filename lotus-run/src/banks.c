// Lotus Run: the sprite banks in attic RAM (see banks.h).
//
// A bank file is loaded to PICTURE (free before the race), then unpacked
// into attic RAM by DMA (tools/mksprites.py's pack): bytes as they are are
// a copy from the file, a repeated byte a fill, a copy of what came before
// a copy within the output.
// What the program keeps of a bank is its directory: per image width,
// height and where its pixels are.

#include "banks.h"

#include "disk.h"
#include "dma.h"
#include "mem.h"
#include "sprbanks.h"
#include "sprites.h"

#define LOAD PICTURE

HIGH_RAM uint8_t banks_pool[BANKS_POOL];
LOW_RAM uint16_t banks_dir[SPR_BANKS];
LOW_RAM uint8_t banks_offset[SPR_BANKS][3];
static uint16_t pool_used;
static uint32_t attic_used;

// The loaded file, through a window of 256 bytes
LOW_RAM static uint8_t win[256];
static uint32_t win_at;
static uint32_t file_at;

bool file_open(const char *name, uint32_t at) {
    if (!disk_load(name, at))
        return false;
    file_at = at;
    win_at = ~0ul;
    return true;
}

uint8_t file_byte(uint32_t off) {
    uint32_t base = off & ~0xFFul;
    if (base != win_at) {
        dma_copy(file_at + base, (uint16_t)win, sizeof win);
        dma_flush();
        win_at = base;
    }
    return win[(uint8_t)off];
}

#define rd file_byte

uint32_t file_unpack(uint32_t off, uint32_t out, uint32_t end) {
    while (out < end) {
        uint8_t c = rd(off++), len;
        if (c < 0x80) {
            len = c + 1;
            dma_copy(file_at + off, out, len);
            off += len;
        } else if (c < 0xC0) {
            len = c - 0x7E;
            dma_fill(out, rd(off++), len);
        } else {
            len = c - 0xBC;
            uint8_t lo = rd(off++);
            uint8_t hi = rd(off++);
            dma_copy(out - (uint16_t)(hi << 8 | lo), out, len);
        }
        out += len;
    }
    dma_flush();
    return off;
}

#define unpack file_unpack

static bool load_bank(uint8_t b) {
    if (banks_dir[b])
        return true;
    char name[] = "SPR00";
    name[3] = "0123456789ABCDEF"[b >> 4];
    name[4] = "0123456789ABCDEF"[b & 15];
    if (!file_open(name, LOAD))
        return false;
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
    unpack(1 + 2u * n, ATTIC + attic_used, ATTIC + end);
    attic_used = end;
    return true;
}

_Static_assert((uint32_t)BACK_W * BACK_H <= BACKDROP_SIZE, "a backdrop does not fit into BACKDROP");

bool backdrop_load(uint8_t n) {
    char name[] = "BACK0";
    name[4] = (char)('0' + n);
    if (!file_open(name, LOAD))
        return false;
    unpack(0, BACKDROP, BACKDROP + (uint32_t)BACK_W * BACK_H);
    return true;
}

uint32_t backdrop_pixels(void) {
    return BACKDROP;
}

PanelField panel_fields[PANEL_FIELDS];

_Static_assert(PANEL_W * PANEL_H <= 0x1200, "the panel does not fit into PANEL_LIVE");

bool panel_load(void) {
    if (!file_open("PANEL", LOAD))
        return false;
    if (rd(0) != PANEL_W || rd(1) != PANEL_H || rd(2) != PANEL_FIELDS)
        return false;
    uint32_t at = PANEL_DATA + PANEL_W * PANEL_H;
    for (uint8_t f = 0; f < PANEL_FIELDS; f++) {
        PanelField *p = &panel_fields[f];
        p->x = rd(3 + 5u * f);
        p->y = rd(4 + 5u * f);
        p->w = rd(5 + 5u * f);
        p->h = rd(6 + 5u * f);
        p->states = rd(7 + 5u * f);
        p->pixels = at;
        at += (uint32_t)p->w * p->h * p->states;
    }
    if (at > PANEL_DATA + PANEL_SIZE)
        return false;
    unpack(3 + 5u * PANEL_FIELDS, PANEL_DATA, at);
    return true;
}

uint32_t panel_base(void) {
    return PANEL_DATA;
}

uint32_t panel_live(void) {
    return PANEL_LIVE;
}

#define LAPBAR_BYTES ((uint32_t)LAPBAR_W * LAPBAR_H * LAPBAR_LAPS + 16 * 16)
_Static_assert(LAPBAR_BYTES <= LAPBAR_SIZE, "the lap bar does not fit into LAPBAR_DATA");

bool lapbar_load(void) {
    if (!file_open("LAPBAR", LOAD))
        return false;
    unpack(0, LAPBAR_DATA, LAPBAR_DATA + LAPBAR_BYTES);
    return true;
}

uint32_t lapbar_pixels(void) {
    return LAPBAR_DATA;
}

void attic_copy(uint32_t src, uint32_t dst, uint16_t len) {
    dma_copy(src, dst, len);
}

// The opponents in their other colourings: their images (the cars' 63-125,
// one after the other) copied with the paint's colours moved to those of
// colouring k (OPP_PAINT + 2k, + 2k + 1); banks SPR_OPP + k - 1 are these,
// with the cars' directory and an offset to its addresses
static void opponent_colours(void) {
    LOW_RAM static uint8_t buf[256];
    uint32_t from = sprite_pixels(SPR_CARS, 63);
    uint32_t len = sprite_pixels(SPR_CARS, 125) + sprite_width(SPR_CARS, 125) * sprite_height(SPR_CARS, 125) - from;
    for (uint8_t k = 1; k < OPP_COLOURS; k++) {
        uint32_t to = ATTIC + attic_used, offset = to - from;
        for (uint32_t off = 0; off < len; off += sizeof buf) {
            uint16_t n = len - off < sizeof buf ? (uint16_t)(len - off) : (uint16_t)sizeof buf;
            dma_copy(from + off, (uint16_t)buf, n);
            dma_flush();
            for (uint16_t i = 0; i < n; i++)
                if ((uint8_t)(buf[i] - OPP_PAINT) < 2)
                    buf[i] += 2 * k;
            dma_copy((uint16_t)buf, to + off, n);
            dma_flush();
        }
        attic_used += len;
        uint8_t b = SPR_OPP + k - 1;
        banks_dir[b] = banks_dir[SPR_CARS];
        banks_offset[b][0] = (uint8_t)offset;
        banks_offset[b][1] = (uint8_t)(offset >> 8);
        banks_offset[b][2] = (uint8_t)(offset >> 16);
    }
}

bool banks_load(const Track *t) {
    for (uint8_t b = 0; b < SPR_BANKS; b++) {
        banks_dir[b] = 0;
        banks_offset[b][0] = banks_offset[b][1] = banks_offset[b][2] = 0;
    }
    pool_used = 0;
    attic_used = BANKS_ATTIC - ATTIC;
    if (!load_bank(SPR_CARS) || !load_bank(SPR_HUD))
        return false;
    opponent_colours();
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
    const uint8_t *o = banks_offset[bank];
    return ATTIC + (e[2] | (uint32_t)e[3] << 8 | (uint32_t)e[4] << 16) +
           (o[0] | (uint32_t)o[1] << 8 | (uint32_t)o[2] << 16);
}
