// Lotus Run: loading the music and starting its interrupt (see music.h;
// the player is music.s).

#include "music.h"

#include "disk.h"
#include "hw.h"
#include "irq.h"
#include "mem.h"

void music_frame(void);

MENU bool music_load(void) {
    return disk_load("MUSIC", MUSIC_ATTIC);
}

// The interrupt: CIA 1's timer A every 1000 of its cycles - 20 times a
// frame at 1 MHz (fewer in Xemu, whose CIAs run slower), so that a step
// comes at most a millisecond after its frame; it waits until it is taken,
// also through a long DMA job
MENU void music_init(void) {
    music_stop();
    irq_frame = music_frame;
    POKE(0xDC04, (uint8_t)1000);
    POKE(0xDC05, 1000 >> 8);
    POKE(0xDC0E, 0x11);  // load, run continuously
    PEEK(0xDC0D);
    POKE(0xDC0D, 0x81);  // timer A interrupts
}
