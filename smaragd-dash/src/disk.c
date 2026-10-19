// Smaragd Dash: loading files from the disk (see disk.h).
//
// The loader talks to the F011 floppy controller directly: it asks for a
// sector, waits until the controller is no longer busy, and copies the
// sector with DMA from the controller's buffer at $FFD6C00. So it needs
// neither the ROM nor interrupts, and between two sectors disk_busy can
// show that something is happening. It reads the disk image mounted in
// drive 0 (a real disk would also need the head stepped to the track).
// Writing goes the same way back: a sector is read, changed in the
// controller's buffer and written, so a file can be rewritten in place.
//
// The D81 (1581 format) has 80 tracks of 40 logical sectors of 256 bytes;
// the controller reads physical sectors of 512 bytes, 10 per side: logical
// sector s of track t is physical track t - 1, side s / 20, sector
// (s % 20) / 2 + 1, and its half s & 1. The directory starts at track 40,
// sector 3: eight entries of 32 bytes per sector, each with the file type
// at 2 (0: empty), the first track and sector at 3 and 4 and the name,
// padded with $A0, at 5-20. Every sector starts with the track and sector
// of the next one; track 0 marks the last, and its second byte is then the
// offset of the last byte used.

#include "disk.h"

#include <string.h>

#include "hw.h"

#define FDC_CONTROL 0xD080  // drive, side, motor, LED
#define FDC_COMMAND 0xD081
#define FDC_STATUS  0xD082  // bit 7 busy, bit 4 record not found, bit 3 CRC error
#define FDC_TRACK   0xD084
#define FDC_SECTOR  0xD085
#define FDC_SIDE    0xD086

#define DIR_TRACK  40
#define DIR_SECTOR 3

void (*disk_busy)(void);

static uint8_t blk[256];               // the logical sector last read
static uint8_t in_buf_track = 0xFF;    // physical sector in the controller's buffer
static uint8_t in_buf_sector, in_buf_side;

// One DMA copy job, enhanced list: source and target megabyte, then F018A
static uint8_t dma_list[] = {
    0x0A, 0x80, 0x00, 0x81, 0x00, 0x00,
    0x00,                // copy
    0, 0,                // length
    0, 0, 0,             // source
    0, 0, 0,             // target
    0, 0,                // modulo
};

static void dma_copy(uint8_t src_mb, uint32_t src, uint8_t dst_mb, uint32_t dst, uint16_t len) {
    dma_list[2] = src_mb;
    dma_list[4] = dst_mb;
    dma_list[7] = (uint8_t)len;
    dma_list[8] = len >> 8;
    dma_list[9] = (uint8_t)src;
    dma_list[10] = (uint8_t)(src >> 8);
    dma_list[11] = (src >> 16) & 0x0F;
    dma_list[12] = (uint8_t)dst;
    dma_list[13] = (uint8_t)(dst >> 8);
    dma_list[14] = (dst >> 16) & 0x0F;
    POKE(0xD702, 0);
    POKE(0xD704, 0);
    POKE(0xD701, (uint16_t)dma_list >> 8);
    POKE(0xD705, (uint8_t)(uint16_t)dma_list);  // enhanced job, starts it
}

static void wait_ready(void) {
    while (PEEK(FDC_STATUS) & 0x80)
        ;
}

// Logical sector s of track t into blk[]
static bool read_sector(uint8_t t, uint8_t s) {
    if (t < 1 || t > 80 || s >= 40)
        return false;
    uint8_t side = s >= 20;
    uint8_t track = t - 1;
    uint8_t sector = (s - side * 20) / 2 + 1;
    if (track != in_buf_track || sector != in_buf_sector || side != in_buf_side) {
        wait_ready();
        POKE(FDC_CONTROL, 0x60 | side << 3);  // drive 0, motor and LED on
        wait_ready();
        POKE(FDC_TRACK, track);
        POKE(FDC_SECTOR, sector);
        POKE(FDC_SIDE, side);
        POKE(FDC_COMMAND, 0x01);  // buffer pointers to the start
        wait_ready();
        POKE(FDC_COMMAND, 0x40);  // read the sector
        wait_ready();
        if (PEEK(FDC_STATUS) & 0x18) {
            in_buf_track = 0xFF;
            return false;
        }
        in_buf_track = track;
        in_buf_sector = sector;
        in_buf_side = side;
        if (disk_busy)
            disk_busy();
    }
    dma_copy(0xFF, 0xD6C00 + ((uint16_t)(s & 1) << 8), 0, (uint16_t)blk, 256);
    return true;
}

// blk[] back as logical sector s of the physical sector read last
// (read_sector of the same s just before): into its half of the
// controller's buffer, and the whole buffer onto the disk
static bool write_sector(uint8_t s) {
    dma_copy(0, (uint16_t)blk, 0xFF, 0xD6C00 + ((uint16_t)(s & 1) << 8), 256);
    wait_ready();
    POKE(FDC_TRACK, in_buf_track);
    POKE(FDC_SECTOR, in_buf_sector);
    POKE(FDC_SIDE, in_buf_side);
    POKE(FDC_COMMAND, 0x01);  // buffer pointers to the start
    wait_ready();
    POKE(FDC_COMMAND, 0x80);  // write the sector
    wait_ready();
    if (PEEK(FDC_STATUS) & 0x18) {
        in_buf_track = 0xFF;
        return false;
    }
    return true;
}

// The first track and sector of the file `name`
static bool find(const char *name, uint8_t *t, uint8_t *s) {
    uint8_t len = strlen(name);
    uint8_t dt = DIR_TRACK, ds = DIR_SECTOR;
    while (dt) {
        if (!read_sector(dt, ds))
            return false;
        for (const uint8_t *e = blk; e < blk + 256; e += 32) {
            if (!e[2])
                continue;
            uint8_t i = 0;
            while (i < 16 && e[5 + i] == (i < len ? (uint8_t)name[i] : 0xA0))
                i++;
            if (i == 16) {
                *t = e[3];
                *s = e[4];
                return true;
            }
        }
        dt = blk[0];
        ds = blk[1];
    }
    return false;
}

bool disk_load(const char *name, uint8_t bank, uint16_t addr) {
    uint8_t t, s;
    bool ok = find(name, &t, &s);
    uint32_t dst = (uint32_t)bank << 16 | addr;
    uint8_t from = 4;  // the first sector: after the link, the load address
    while (ok && t) {
        if (!(ok = read_sector(t, s)))
            break;
        uint16_t end = blk[0] ? 256 : blk[1] + 1;
        if (end > from) {
            dma_copy(0, (uint16_t)blk + from, 0, dst, end - from);
            dst += end - from;
        }
        from = 2;
        t = blk[0];
        s = blk[1];
    }
    POKE(FDC_CONTROL, 0);  // motor and LED off
    return ok;
}

bool disk_save(const char *name, const void *data, uint16_t len) {
    uint8_t t, s;
    bool ok = find(name, &t, &s);
    const uint8_t *src = data;
    uint8_t from = 4;
    while (ok && t && len) {
        if (!(ok = read_sector(t, s)))
            break;
        uint16_t end = blk[0] ? 256 : blk[1] + 1;
        if (end > from) {
            uint16_t n = end - from;
            if (n > len)
                n = len;
            memcpy(blk + from, src, n);
            src += n;
            len -= n;
            ok = write_sector(s);
        }
        from = 2;
        t = blk[0];
        s = blk[1];
    }
    POKE(FDC_CONTROL, 0);
    return ok && !len;
}
