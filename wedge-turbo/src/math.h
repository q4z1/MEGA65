// Wedge Turbo: multiplying and dividing.
//
// On the MEGA65 the math unit does it in hardware (MULTINA/MULTINB at
// $D770/$D774, product at $D778, quotient at $D76C); elsewhere (host tests)
// plain C. The unit multiplies unsigned 32-bit numbers into 64 bits: the
// low 32 bits of that are the signed product of sign-extended numbers as
// well.

#ifndef MATH_H
#define MATH_H

#include <stdint.h>

#ifdef __mos__
#include "hw.h"

static inline int32_t mul16s(int16_t a, int16_t b) {
    *(volatile int32_t *)0xD770 = a;
    *(volatile int32_t *)0xD774 = b;
    return *(volatile int32_t *)0xD778;
}

// a / b for 32-bit a and 16-bit b > 0, both unsigned
static inline uint32_t div32u(uint32_t a, uint16_t b) {
    *(volatile uint32_t *)0xD770 = a;
    *(volatile uint32_t *)0xD774 = b;
    // the divider needs 16 cycles at 40 MHz; DIVBUSY is $D70F bit 7
    while (PEEK(0xD70F) & 0x80)
        ;
    return *(volatile uint32_t *)0xD76C;
}
#else
static inline int32_t mul16s(int16_t a, int16_t b) {
    return (int32_t)a * b;
}

static inline uint32_t div32u(uint32_t a, uint16_t b) {
    return a / b;
}
#endif

#endif
