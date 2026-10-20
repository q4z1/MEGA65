// Lotus Run: the raster interrupt (irq.s) - palette entries 12-15
// changed at raster lines.

#ifndef IRQ_H
#define IRQ_H

#include <stdint.h>

#define IRQ_ENTRIES 64

// The table being shown: entry i from raster line irq_line_lo[i] |
// (irq_line_hi[i] & $80) << 1 on; colour field k (R, G, B of colour 12,
// then 13, ...) at irq_colours[k * IRQ_ENTRIES + i]
extern uint8_t irq_count;
extern uint8_t irq_line_lo[IRQ_ENTRIES], irq_line_hi[IRQ_ENTRIES];
extern uint8_t irq_colours[12 * IRQ_ENTRIES];

// Switches the KERNAL out and starts the interrupt (the table must not
// be empty)
void irq_init(void);
// From the first entry of the table on: after changing it, interrupts off
void irq_restart(void);

#endif
