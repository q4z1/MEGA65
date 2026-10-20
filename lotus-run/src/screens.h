// Lotus Run: the pages between the races (pages.h), with what changes on
// them put in as text, and the joystick to choose and go on.

#ifndef SCREENS_H
#define SCREENS_H

#include <stdbool.h>
#include <stdint.h>

#include "track.h"

// The controls: automatic gears, accelerate with fire (else with forward);
// and the radio in the race: a song (1-4), or 0 for the engines' sound
typedef struct {
    bool automatic;
    bool fire_accel;
    uint8_t radio;
} Controls;

// The pages need the 640 x 400 mode (pages_on), and their code where it
// runs (main.c: the MENU overlay, mem.h)

// The level of a new season (0-2), starting from `level`
uint8_t screen_level(uint8_t level);

// The controls, changed on their page (the radio's song plays while it is
// chosen)
void screen_controls(Controls *c);

// Before a race: the course (as loaded to TRACK_ATTIC), and which race of
// the season it is
void screen_course(uint8_t course);

// After a race: its classification; then the championship
void screen_result(void);
void screen_standing(void);

// The season is over: won, finished without the title, or out
void screen_season_over(bool out);

// Waits until fire is let go, then pressed
void screen_wait_fire(void);

#endif
