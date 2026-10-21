// Wedge Turbo: copying and filling with the DMA controller (see dma.h).
//
// Every job carries all its options (list format, megabytes, steps,
// transparency): options last into the next job of a chain (Xemu resets
// them only when a list starts), so a job without transparency switches it
// off. A job is: options, $00, then the 11 bytes of an F018A job (command,
// count, source, target, modulo).

#include "dma.h"

#include "hw.h"
#include "mem.h"

uint8_t *dma_p = DMA_LIST;
uint8_t *dma_last_cmd;

#define JOB_MAX 32  // the most bytes one job takes

static void job(uint8_t cmd, uint32_t src, uint16_t src_step, uint32_t dst, uint16_t dst_step,
                uint16_t len, uint8_t transparent, uint8_t clear) {
    if (dma_p + JOB_MAX > DMA_LIST + DMA_LIST_SIZE)
        dma_flush();
    uint8_t *q = dma_p;
    *q++ = 0x0A;  // F018A jobs
    *q++ = 0x80;
    *q++ = (uint8_t)(src >> 20);
    *q++ = 0x81;
    *q++ = (uint8_t)(dst >> 20);
    if (src_step != 0x0100) {
        *q++ = 0x82;
        *q++ = (uint8_t)src_step;
        *q++ = 0x83;
        *q++ = (uint8_t)(src_step >> 8);
    }
    if (dst_step != 0x0100) {
        *q++ = 0x84;
        *q++ = (uint8_t)dst_step;
        *q++ = 0x85;
        *q++ = (uint8_t)(dst_step >> 8);
    }
    if (transparent) {
        *q++ = 0x07;  // transparency on
        *q++ = 0x86;
        *q++ = clear;
    } else {
        *q++ = 0x06;
    }
    *q++ = 0x00;
    dma_last_cmd = q;
    *q++ = cmd | 4;  // chained; dma_flush clears it on the last job
    *q++ = (uint8_t)len;
    *q++ = (uint8_t)(len >> 8);
    *q++ = (uint8_t)src;
    *q++ = (uint8_t)(src >> 8);
    *q++ = (uint8_t)(src >> 16) & 0x0F;
    *q++ = (uint8_t)dst;
    *q++ = (uint8_t)(dst >> 8);
    *q++ = (uint8_t)(dst >> 16) & 0x0F;
    *q++ = 0;
    *q++ = 0;
    dma_p = q;
}

void dma_fill_low(uint32_t dst, uint8_t val, uint16_t len) {
    if (dma_p + 16 > DMA_LIST + DMA_LIST_SIZE)
        dma_flush();
    uint8_t *q = dma_p;
    *q++ = 0x0A;
    *q++ = 0x06;
    *q++ = 0x81;
    *q++ = 0x00;
    *q++ = 0x00;
    dma_last_cmd = q;
    *q++ = 3 | 4;  // fill, chained
    *q++ = (uint8_t)len;
    *q++ = (uint8_t)(len >> 8);
    *q++ = val;
    *q++ = 0;
    *q++ = 0;
    *q++ = (uint8_t)dst;
    *q++ = (uint8_t)(dst >> 8);
    *q++ = (uint8_t)(dst >> 16);
    *q++ = 0;
    *q++ = 0;
    dma_p = q;
}

void dma_copy(uint32_t src, uint32_t dst, uint16_t len) {
    job(0, src, 0x0100, dst, 0x0100, len, 0, 0);
}

void dma_copy_transparent(uint32_t src, uint32_t dst, uint16_t len, uint8_t clear) {
    job(0, src, 0x0100, dst, 0x0100, len, 1, clear);
}

void dma_fill(uint32_t dst, uint8_t val, uint16_t len) {
    job(3, val, 0x0100, dst, 0x0100, len, 0, 0);
}

void dma_copy_step(uint32_t src, uint16_t src_step, uint32_t dst, uint16_t dst_step, uint16_t len) {
    job(0, src, src_step, dst, dst_step, len, 0, 0);
}

void dma_run_list(uint32_t list) {
    POKE(0xD702, (uint8_t)(list >> 16) & 0x7F);
    POKE(0xD704, (uint8_t)(list >> 20));
    POKE(0xD701, (uint8_t)(list >> 8));
    POKE(0xD705, (uint8_t)list);  // enhanced job: starts it, the CPU waits
}

void dma_flush(void) {
    if (dma_p == DMA_LIST)
        return;
    *dma_last_cmd &= ~4;
    dma_run_list((uint32_t)(uint16_t)DMA_LIST);
    dma_p = DMA_LIST;
}
