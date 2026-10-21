// Wedge Turbo: the race's sounds - the engines and the effects (countdown,
// start, crashes, the kerb, low fuel), as the original makes them, played
// by the MEGA65's audio DMA from the original's samples (SOUNDS).
//
// sound_frame runs once a frame before the race's logic, as the original's
// does: it reads what the last frame left (race.h), and while the cars wait
// for the start it takes random numbers from the race's generator.

#ifndef SOUND_H
#define SOUND_H

#include <stdbool.h>

// Loads the samples (SOUNDS) into attic RAM
bool sound_load(void);

// A race starts (after race_init): the samples into chip RAM, the engines
// on - with music on the radio more quietly
void sound_race_start(bool radio);

// Once a frame, before race_frame
void sound_frame(void);

// Silence (the race is over)
void sound_off(void);

#endif
