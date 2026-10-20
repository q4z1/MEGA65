// Lotus Run: the race's state (race.h), shared by the logic in
// assembly (race.s) and its reference in C (ref/race.c).

#include "race.h"

Race race;
const Track *race_track;
uint8_t race_joy[2];
uint32_t race_lookup_pos;
