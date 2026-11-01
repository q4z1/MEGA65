// Smaragd Dash: copying and filling with the DMA controller (see dma.h).

#include "dma.h"

#include "hw.h"
#include "mem.h"

uint8_t *dma_p, *dma_last;

// Not inlined: called from many places, these are smaller as calls.

// The options: F018A format, the source and target megabytes, end. Each
// job is followed by the end of the (empty) option list of the next one.
__attribute__((noinline)) void dma_begin(uint8_t src_mb, uint8_t dst_mb) {
    uint8_t *p = DMA_LIST;
    p[0] = 0x0A;
    p[1] = 0x80;
    p[2] = src_mb;
    p[3] = 0x81;
    p[4] = dst_mb;
    p[5] = 0x00;
    dma_p = p + 6;
}

__attribute__((noinline)) void dma_job(uint8_t cmd, uint16_t src, uint8_t sbank, uint16_t dst, uint8_t dbank, uint16_t len) {
    uint8_t *p = dma_p;
    dma_last = p;
    p[0] = cmd | 4;  // chained; the last job's bit is cleared in dma_run
    p[1] = (uint8_t)len;
    p[2] = len >> 8;
    p[3] = (uint8_t)src;
    p[4] = src >> 8;
    p[5] = sbank;
    p[6] = (uint8_t)dst;
    p[7] = dst >> 8;
    p[8] = dbank;
    p[9] = 0;
    p[10] = 0;
    p[11] = 0;
    dma_p = p + 12;
}

// src/dmastart.s: a call the compiler cannot look into, so it keeps every
// write to the list before it (with the POKEs here it moved them behind
// the start, or dropped those that a next list overwrote)
void dma_start(const uint8_t *list);

__attribute__((noinline)) void dma_run(void) {
    *dma_last &= ~4;
    dma_start(DMA_LIST);
}

__attribute__((noinline)) void dma_once(uint16_t src, uint8_t sbank, uint16_t dst, uint8_t dbank, uint16_t len) {
    uint8_t *p = DMA_ONCE;
    p[0] = 0x0A;  // the options as dma_begin(0, 0)
    p[1] = 0x80;
    p[2] = 0x00;
    p[3] = 0x81;
    p[4] = 0x00;
    p[5] = 0x00;
    p += 6;
    p[0] = 0;  // copy, the last job
    p[1] = (uint8_t)len;
    p[2] = len >> 8;
    p[3] = (uint8_t)src;
    p[4] = src >> 8;
    p[5] = sbank;
    p[6] = (uint8_t)dst;
    p[7] = dst >> 8;
    p[8] = dbank;
    p[9] = 0;
    p[10] = 0;
    dma_start(DMA_ONCE);
}
