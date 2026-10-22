// Smaragd Dash: sound effects on the first SID.
//   voice 1: Rockford and diamonds   voice 2: boulders, dirt, explosions
//   voice 3: amoeba, magic wall, clock, exit

#ifndef SOUND_H
#define SOUND_H

#include <stdint.h>

void sound_init(void);
void sound_tick(uint8_t events);  // SND_* flags of a cave tick
void sound_crackle(void);         // covering/uncovering the cave
void sound_clock(void);           // last seconds
void sound_bonus(void);           // time is counted into the score
void sound_exit(void);            // the exit opens
void sound_life(void);            // extra life
void sound_off(void);
void sound_frame(void);           // once per frame: ended sounds off

#endif
