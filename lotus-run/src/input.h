// Lotus Run: joysticks (either port) and keyboard.
//   cursor keys        move
//   Space / Return     fire (with a direction: snap)
//   P                  pause
//   Run/Stop           give up

#ifndef INPUT_H
#define INPUT_H

#include <stdint.h>

#define IN_UP      0x01
#define IN_DOWN    0x02
#define IN_LEFT    0x04
#define IN_RIGHT   0x08
#define IN_BUTTON  0x10
#define IN_PAUSE   0x20
#define IN_RESTART 0x40

uint8_t input_read(void);

#endif
