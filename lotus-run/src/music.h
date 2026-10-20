// Lotus Run: the music - the game's five tunes, arranged for the MEGA65's
// four SIDs (tools/mkmusic.py): song 0 for the title and the pages, 1-4 on
// the radio during the race. A raster interrupt plays them (music.s), so
// they go on while the program loads or waits.

#ifndef MUSIC_H
#define MUSIC_H

#include <stdbool.h>
#include <stdint.h>

// Loads the songs (MUSIC) into attic RAM
bool music_load(void);

// The interrupt on: from now on music_start plays
void music_init(void);

// A song from its start (0 - MUSIC_SONGS - 1), stopping what plays
void music_start(uint8_t song);

// Silence
void music_stop(void);

#endif
