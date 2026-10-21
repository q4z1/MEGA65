// Wedge Turbo: the season - a level's courses one after the other, each
// race's classification, points and the championship, as the original
// keeps them.
//
// Twenty drivers: 0-17 the opponents of the names in TEXTS (texts.h), 18
// the other car (player 2's), 19 player 1. A race's classification is not
// the opponents' real order: they are shuffled a little, the player is put
// in at the place reached. The first ten score (tab_points); a player who is
// not among them is out.

#ifndef SEASON_H
#define SEASON_H

#include <stdbool.h>
#include <stdint.h>

#define DRIVERS   20
#define DRIVER_P1 19
#define DRIVER_P2 18
#define LEVELS    3   // easy, medium, hard
#define SCORING   10  // places that score; a player must be among them

typedef struct {
    uint8_t level;                // 0-2
    uint8_t race;                 // race of the season (0: the first)
    uint8_t races;                // how many the level has
    uint16_t points[DRIVERS];     // the championship
    uint8_t order[DRIVERS];       // the last race's classification: drivers
    uint16_t time[DRIVERS];       // ... and their times (frames)
    uint8_t place;                // player 1's place in it (0: first)
    bool record;                  // the winner broke the course record
    uint8_t standing[DRIVERS];    // the championship: drivers by points
} Season;

extern Season season;

// Loads the names (TEXTS); the course records as the game starts with them
bool season_load(void);

// A new season of a level
void season_start(uint8_t level);

// The course of this race (0-31)
uint8_t season_course(void);

// After a race (race.h): its classification, the points, the record, the
// championship
void season_classify(void);

// On to the next race; false when the season is over
bool season_next(void);

// A driver's name, upper case, into buf (TEXT_LEN + 1 bytes)
void season_name(uint8_t driver, char *buf);

// A course's record: time (frames) and holder's name into buf
uint16_t season_record(uint8_t course, char *buf);

#endif
