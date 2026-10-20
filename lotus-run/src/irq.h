// Lotus Run: the machine for the game (irq.s)

#ifndef IRQ_H
#define IRQ_H

// Switches the KERNAL out (its RAM under $E000 free) and takes over the
// interrupt vectors; no interrupt is on
void irq_init(void);

// What an interrupt calls (with A, X, Y and Z saved), once a raster
// interrupt is on (music.c); at first nothing
extern void (*irq_frame)(void);

#endif
