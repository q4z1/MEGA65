// Lotus Run: the machine for the game (irq.s)

#ifndef IRQ_H
#define IRQ_H

// Switches the KERNAL out (its RAM under $E000 free) and takes over the
// interrupt vectors; no interrupt is used
void irq_init(void);

#endif
