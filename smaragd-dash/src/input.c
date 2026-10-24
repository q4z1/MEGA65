// Smaragd Dash: joysticks and keyboard (see input.h).

#include "input.h"

#include <stdbool.h>

#include "hw.h"

// Joystick 1 pulls the matrix rows at $DC01 low as keys do: what it holds
// is left out of the keys (down read as Return, P and I: fire and pause).
// It is read again after each column: a stick moved (or a contact
// bouncing) between two reads is not taken for a key.
static uint8_t joy1;

// Keyboard matrix through CIA 1: write a column to $DC00, read rows at $DC01
static uint8_t column(uint8_t sel) {
    POKE(0xDC00, sel);
    uint8_t rows = ~PEEK(0xDC01);
    POKE(0xDC00, 0xFF);
    joy1 |= ~PEEK(0xDC01) & 0x1F;
    return rows & ~joy1;
}

// P counts once it was seen in two reads in a row (a frame apart): a
// joystick in port 1 can still look like it for a moment
static bool p_was;

uint8_t input_read(void) {
    // The C65's extra column (Tab, Help, Esc, F9-F13) not selected: the ROM
    // can leave it on, and then its keys read as joystick 1 and as the keys
    // of every column (Help: right, Tab: down and P)
    POKE(0xD608, 0x02);  // KEYCOL8 an output ...
    POKE(0xD607, 0x03);  // ... high
    POKE(0xDC02, 0xFF);  // port A drives the matrix columns
    POKE(0xDC03, 0x00);
    POKE(0xDC00, 0xFF);
    // Both joysticks: port 2 on $DC00, port 1 on $DC01 (bits as IN_*)
    joy1 = ~PEEK(0xDC01) & 0x1F;
    uint8_t in = (~PEEK(0xDC00) & 0x1F) | joy1;

    // Cursor keys: on the MEGA65, left and up are shift + right / down in
    // the matrix; $D60F tells them apart.
    uint8_t lu = PEEK(0xD60F);
    uint8_t c0 = column(0xFE);
    if (lu & 1)
        in |= IN_LEFT;
    else if (c0 & 0x04)
        in |= IN_RIGHT;
    if (lu & 2)
        in |= IN_UP;
    else if (c0 & 0x80)
        in |= IN_DOWN;
    if (c0 & 0x02)  // Return
        in |= IN_BUTTON;
    uint8_t c7 = column(0x7F);
    if (c7 & 0x10)  // Space
        in |= IN_BUTTON;
    if (c7 & 0x80)  // Run/Stop
        in |= IN_RESTART;
    bool p = column(0xDF) & 0x02;  // P
    if (p && p_was)
        in |= IN_PAUSE;
    p_was = p;
    if (column(0xEF) & 0x02)  // I
        in |= IN_ITEMS;
    POKE(0xDC00, 0xFF);
    return in;
}
