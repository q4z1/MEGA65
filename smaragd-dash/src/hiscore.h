// Smaragd Dash: the high score table, as in the arcades: the best eight
// with three letters each. It is kept on the disk (SMARAGD.SCORES, which
// build.sh puts there and keeps from one build to the next) and written
// back whenever someone enters it.

#ifndef HISCORE_H
#define HISCORE_H

#include <stdbool.h>
#include <stdint.h>

#define HS_COUNT 8

typedef struct {
    char name[3];
    uint8_t cave, level;  // where the game ended, from 0
    uint32_t score;
} HiScore;

extern HiScore hs_table[HS_COUNT];  // best first

void hiscore_load(void);  // from the disk, or the default table
bool hiscore_save(void);

// The place a score would get (0 = best), or HS_COUNT if it is too low
uint8_t hiscore_rank(uint32_t score);

// Make room at `rank` for a new entry and return it
HiScore *hiscore_insert(uint8_t rank);

#endif
