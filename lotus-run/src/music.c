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

// A raster interrupt every frame, at the top border's line 8
MENU void music_init(void) {
    music_stop();
    irq_frame = music_frame;
    POKE(0xD012, 8);
    POKE(0xD011, PEEK(0xD011) & 0x7F);
    POKE(0xD019, 0xFF);
    POKE(0xD01A, 0x01);
}
