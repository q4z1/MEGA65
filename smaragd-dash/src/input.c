// Smaragd Dash: joysticks and keyboard (see input.h).

#include "input.h"

#include "hw.h"

#ifdef AUTOPLAY
// Test builds (build.sh with SMARAGD_CFLAGS=-DAUTOPLAY): a fixed walk
// instead of the controls (fire on the title screen first), for screenshots
// in the headless emulator.
static const uint8_t script[][2] = {
    {50, 0}, {5, IN_BUTTON}, {230, 0}, {8, IN_UP}, {98, IN_RIGHT}, {80, IN_DOWN}, {255, 0},
};
static uint8_t step, left = 50;

uint8_t input_read(void) {
    if (!left--) {
        if (step < sizeof script / sizeof *script - 1)
            step++;
        left = script[step][0];
    }
    return script[step][1];
}
#else
// Keyboard matrix through CIA 1: write a column to $DC00, read rows at $DC01
static uint8_t column(uint8_t sel) {
    POKE(0xDC00, sel);
    return ~PEEK(0xDC01);
}

uint8_t input_read(void) {
    POKE(0xDC02, 0xFF);  // port A drives the matrix columns
    POKE(0xDC03, 0x00);
    POKE(0xDC00, 0xFF);
    // Both joysticks: port 2 on $DC00, port 1 on $DC01 (bits as IN_*)
    uint8_t in = (~PEEK(0xDC00) | ~PEEK(0xDC01)) & 0x1F;

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
    if (column(0xDF) & 0x02)  // P
        in |= IN_PAUSE;
    POKE(0xDC00, 0xFF);
    return in;
}
#endif
