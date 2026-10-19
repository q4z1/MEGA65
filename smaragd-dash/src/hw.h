// Smaragd Dash: register access

#ifndef HW_H
#define HW_H

#include <stdint.h>

#define POKE(a, v) (*(volatile uint8_t *)(a) = (v))
#define PEEK(a)    (*(volatile uint8_t *)(a))

#endif
