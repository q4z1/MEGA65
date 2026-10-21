// Wedge Turbo: copying and filling with the DMA controller.
//
// Jobs are collected in a list in bank 0 (DMA_LIST, mem.h) and run in one
// go when it is full or on dma_flush; the CPU waits until they are done.
// Enhanced (F018B) jobs; addresses are 28 bits.

#ifndef DMA_H
#define DMA_H

#include <stdint.h>

// Copy len bytes; transparent: bytes of value `clear` are skipped
void dma_copy(uint32_t src, uint32_t dst, uint16_t len);
void dma_copy_transparent(uint32_t src, uint32_t dst, uint16_t len, uint8_t clear);
// Fill len bytes with val
void dma_fill(uint32_t dst, uint8_t val, uint16_t len);
// The same for the first megabyte (dst < $100000), with a shorter job
void dma_fill_low(uint32_t dst, uint8_t val, uint16_t len);
// Copy len bytes, stepping through source and target by the given amounts
// (8.8 fixed point, e.g. 0x0800 for every 8th byte)
void dma_copy_step(uint32_t src, uint16_t src_step, uint32_t dst, uint16_t dst_step, uint16_t len);

// Run what is collected
void dma_flush(void);

// The list being collected, for code that writes jobs itself (render.s):
// where the next job goes, and the command byte of the last one (its
// "chained" bit is cleared by dma_flush)
extern uint8_t *dma_p;
extern uint8_t *dma_last_cmd;

// Run a list that is already in memory (28-bit address)
void dma_run_list(uint32_t list);

#endif
