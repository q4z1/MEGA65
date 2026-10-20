// Lotus Run: the season (see season.h).

#include "season.h"

#include "disk.h"
#include "dma.h"
#include "mem.h"
#include "progdata.h"
#include "race.h"
#include "texts.h"

LOW_RAM Season season;

// The course records: time, and who holds it (a driver, or HOLDER_FIRST:
// the name the game starts with, TEXT_RECORDS)
#define HOLDER_FIRST 0xFF
LOW_RAM static uint16_t record_time[32];
LOW_RAM static uint8_t record_by[32];

MENU bool season_load(void) {
    for (uint8_t c = 0; c < 32; c++) {
        record_time[c] = tab_course_time[c];
        record_by[c] = HOLDER_FIRST;
    }
    return disk_load("TEXTS", TEXTS_ATTIC);
}

MENU void season_start(uint8_t level) {
    season.level = level;
    season.race = 0;
    season.races = (uint8_t)(tab_course_base[level + 1] - tab_course_base[level]);
    for (uint8_t d = 0; d < DRIVERS; d++)
        season.points[d] = 0;
}

MENU uint8_t season_course(void) {
    return (uint8_t)(tab_course_base[season.level] + season.race);
}

// A random number 0 .. n - 1 (as the original scales them)
MENU static uint8_t random_below(uint8_t n) {
    return (uint8_t)(((uint32_t)race_random() * n) >> 16);
}

MENU void season_classify(void) {
    Player *p = &race.p[0];
    if (!p->fuel)
        p->place = 20;  // out of fuel: last
    // the opponents' order: 0-19, shuffled a little
    uint8_t shuffled[DRIVERS];
    for (uint8_t d = 0; d < DRIVERS; d++)
        shuffled[d] = d;
    for (uint8_t k = 0; k < 10; k++) {
        uint8_t a = random_below(15);
        uint8_t b = (uint8_t)(a + 1 + random_below(3));
        uint8_t t = shuffled[a];
        shuffled[a] = shuffled[b];
        shuffled[b] = t;
    }
    // the player at the place reached
    uint8_t *next = shuffled;
    for (uint8_t i = 0; i < DRIVERS; i++)
        season.order[i] = i == p->place - 1 ? DRIVER_P1 : *next++;
    season.place = (uint8_t)(p->place - 1);

    // the times of the first ten (the others have none): the cars over the
    // line their own, the others behind the one before; the first from the
    // course's record time
    uint8_t course = season_course();
    uint16_t t = (uint16_t)(tab_course_time[course] + (race_random() & 0xFF));
    for (uint8_t i = 0; i < DRIVERS; i++) {
        if (i < SCORING) {
            if (race.finish_frames[i])
                t = race.finish_frames[i];
            else
                t = (uint16_t)(t + 0x32 + (race_random() & 0x7F));
            season.time[i] = t;
        } else
            season.time[i] = 0;
        season.points[season.order[i]] += tab_points[i];
    }
    season.record = season.time[0] < record_time[course];
    if (season.record) {
        record_time[course] = season.time[0];
        record_by[course] = season.order[0];
    }

    // the championship: by points, the lower number first among equals
    uint16_t below = 0xFFFF;
    for (uint8_t k = 0; k < DRIVERS; k++) {
        uint16_t best = 0;
        uint8_t who = 0;
        for (uint8_t d = 0; d < DRIVERS; d++) {
            uint16_t key = (uint16_t)((season.points[d] << 5) + 20 - d);
            if (key < below && key >= best) {
                best = key;
                who = d;
            }
        }
        below = best;
        season.standing[k] = who;
    }
}

MENU bool season_next(void) {
    return ++season.race < season.races;
}

// TEXT_LEN characters from TEXTS record n into buf, the padding cut
MENU static void text(uint8_t n, char *buf) {
    dma_copy(TEXTS_ATTIC + (uint16_t)n * TEXT_LEN, (uint16_t)buf, TEXT_LEN);
    dma_flush();
    uint8_t len = TEXT_LEN;
    while (len && buf[len - 1] == ' ')
        len--;
    buf[len] = 0;
}

MENU static void copy(char *buf, const char *s) {
    while ((*buf++ = *s++))
        ;
}

MENU void season_name(uint8_t driver, char *buf) {
    if (driver == DRIVER_P1)
        copy(buf, "PLAYER ONE");
    else if (driver == DRIVER_P2)
        copy(buf, "OTTO MOTOR");  // with one player, the twentieth car
    else
        text((uint8_t)(TEXT_DRIVERS + driver), buf);
}

MENU uint16_t season_record(uint8_t course, char *buf) {
    if (record_by[course] == HOLDER_FIRST)
        text((uint8_t)(TEXT_RECORDS + course), buf);
    else
        season_name(record_by[course], buf);
    return record_time[course];
}
