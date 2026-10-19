// Smaragd Dash: copying and filling with the DMA controller.
//
// A list of chained jobs is built at DMA_LIST (mem.h) and run in one go;
// the CPU waits until it is done. Enhanced list, F018A jobs: an address is
// 16 bits and a bank (bits 16-19); the megabyte (bits 20-27) is given once
// for all sources and once for all targets.

#ifndef DMA_H
#define DMA_H

#include <stdint.h>

void dma_begin(uint8_t src_mb, uint8_t dst_mb);
void dma_job(uint8_t cmd, uint16_t src, uint8_t sbank, uint16_t dst, uint8_t dbank, uint16_t len);
void dma_run(void);

#define dma_copy(src, sbank, dst, dbank, len) dma_job(0, src, sbank, dst, dbank, len)
#define dma_fill(val, dst, dbank, len)        dma_job(3, val, 0, dst, dbank, len)  // len 0: 64K

// For lists written without dma_job (video.c's frame): where the next job
// goes, and the command byte of the last one, whose chain bit dma_run
// clears.
extern uint8_t *dma_p, *dma_last;

#endif
