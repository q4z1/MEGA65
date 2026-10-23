// Smaragd Dash: sound effects on six voices (two SIDs left, two right; the
// second and fourth only in a cave, the title's music has them):
//   voice 1: clocks, diamonds, keys and what else Rockford takes, the time
//            counted into the score
//   voice 2: boulders, nuts   voice 3: diamonds landing, the exit, the last
//   seconds, a life, the cave being covered   voice 4: explosions, doors,
//   bombs, the hammer, expanding walls   voice 5: Rockford's steps
//   voice 6: teleporters, switches, magic wall, slime, water, amoeba
// A sound of lower rank does not cut one off in its first third (sound.c).

#ifndef SOUND_H
#define SOUND_H

#include <stdint.h>

void sound_init(void);
void sound_tick(uint32_t events);  // SND_* flags of a cave tick
void sound_crackle(void);         // covering/uncovering the cave
void sound_clock(void);           // last seconds
void sound_bonus(void);           // time is counted into the score
void sound_exit(void);            // the exit opens
void sound_life(void);            // extra life
void sound_off(void);
void sound_frame(void);           // once per frame: ended sounds off

#endif
