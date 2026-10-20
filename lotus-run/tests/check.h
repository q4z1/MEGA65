// Lotus Run: starting and ending a check program (check_*.c) in Xemu.
//
// Started with -testing, Xemu exits when $42 is written to $D6CF, with the
// value written there before as its exit code (on a real MEGA65 the same
// would reconfigure the FPGA: these programs are for Xemu only). The
// border shows the result as well: green all the same, red a difference.

#ifndef CHECK_H
#define CHECK_H

#include "hw.h"
#include "irq.h"

// The machine as the game has it (irq.s): all 64K of bank 0 RAM - the C65
// KERNAL is mapped from $8000 on otherwise - and no interrupts
static inline void check_init(void) {
    irq_init();
}

static inline void check_exit(uint8_t failed) {
    POKE(0xD020, failed ? 2 : 5);
    POKE(0xD6CF, failed);
    POKE(0xD6CF, 0x42);
    for (;;)
        ;
}

#endif
