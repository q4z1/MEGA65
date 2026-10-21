// Wedge Turbo: the race logic in assembly (src/race.s) against its
// reference in C (src/ref/race.c) - a MEGA65 program, run in Xemu by
// tests/check_race.sh.
//
// A made-up driver (pseudo-random joystick moves, held for a while) drives
// several courses with different settings. Every frame both versions start
// from the same state; the whole Race must come out the same, byte for
// byte. So must race_picture's. The result is left in memory
// (check_frames, check_failed, ...) and shown in the border: green when
// all is the same, red at the first difference; then Xemu exits (check.h).

#include <stdint.h>
#include <string.h>

#include "disk.h"
#include "check.h"
#include "hw.h"
#include "race.h"
#include "tracks.h"

// ref/race.c, compiled with its functions renamed (check_race.sh)
void ref_race_frame(void);
void ref_race_picture(void);

static uint8_t track_buf[TRACK_SIZE];
static Race saved, expected;

volatile uint32_t check_frames;      // frames compared
volatile uint16_t check_failed;      // 0, or 1 + the configuration that differed
volatile uint32_t check_fail_frame;  // its frame
volatile uint16_t check_fail_offset; // the first byte of Race that differed
volatile uint8_t check_fail_what;    // 1 race_frame, 2 race_picture
volatile uint8_t check_done;

// The made-up driver: a move held for a number of frames
static uint32_t seed = 12345;

static uint8_t rnd(void) {
    seed = seed * 1103515245ul + 12345;
    return (uint8_t)(seed >> 16);
}

typedef struct {
    uint8_t joy, left;
} Driver;

static uint8_t drive(Driver *d) {
    if (!d->left) {
        uint8_t r = rnd();
        uint8_t j = 0;
        if (r < 180)
            j |= JOY_UP;
        else if (r < 205)
            j |= JOY_DOWN;
        r = rnd();
        if (r < 70)
            j |= JOY_LEFT;
        else if (r < 140)
            j |= JOY_RIGHT;
        if (rnd() < 40)
            j |= JOY_FIRE;
        d->joy = j;
        d->left = (uint8_t)(2 + (rnd() & 63));
        if (j & JOY_FIRE)
            d->left = 1 + (rnd() & 3);  // gear changes: short pushes
    }
    d->left--;
    return d->joy;
}

static void fail(uint8_t config, uint32_t frame, const void *a, const void *b, uint8_t what) {
    const uint8_t *x = a, *y = b;
    uint16_t i = 0;
    while (x[i] == y[i])
        i++;
    check_failed = config + 1;
    check_fail_frame = frame;
    check_fail_offset = i;
    check_fail_what = what;
    check_done = 1;
    check_exit(1);
}

// What a configuration changes before and during its race
typedef struct {
    uint8_t course, two_players, automatic, fire_accel, difficulty;
    uint8_t low_fuel;       // little fuel: running dry, the pits
    uint8_t near_finish;    // the finish line close: crossing it, the end
} Config;

static const Config configs[] = {
    {0, 0, 0, 0, 0, 0, 0},
    {5, 0, 1, 0, 1, 0, 0},
    {12, 0, 0, 1, 2, 0, 0},
    {20, 1, 0, 0, 0, 0, 0},
    {31, 1, 1, 1, 2, 0, 0},
    {3, 0, 0, 0, 0, 1, 0},
    {8, 0, 0, 0, 1, 0, 1},
    {17, 1, 0, 1, 0, 0, 1},
    {26, 0, 0, 0, 3, 0, 0},
};
#define CONFIGS (sizeof configs / sizeof configs[0])
#define FRAMES  2500

int main(void) {
    check_init();
    POKE(0xD020, 6);
    for (uint8_t c = 0; c < CONFIGS; c++) {
        const Config *k = &configs[c];
        char name[] = "TRACK00";
        name[5] = "0123456789ABCDEF"[k->course >> 4];
        name[6] = "0123456789ABCDEF"[k->course & 15];
        if (!disk_load(name, (uint16_t)track_buf))
            fail(c, 0, "", "x", 3);
        memset(&race, 0, sizeof race);
        race_track = (const Track *)track_buf;
        race.segments = ((const Track *)track_buf)->segments;
        race.course = k->course;
        race.two_players = k->two_players;
        race.difficulty = k->difficulty;
        race.random[0] = 0x1234567u + c;
        race.random[2] = 0x89ABCDEu;
        race_init();
        for (uint8_t n = 0; n < 2; n++) {
            race.p[n].automatic = k->automatic;
            race.p[n].fire_accel = k->fire_accel;
        }
        Driver d[2] = {{0, 0}, {0, 0}};
        for (uint16_t f = 0; f < FRAMES; f++) {
            if (f == 300) {
                for (uint8_t n = 0; n < 2; n++) {
                    if (k->low_fuel)
                        race.p[n].fuel = 0x00400000ul;
                }
                if (k->near_finish)
                    race.finish = race.p[0].pos + 0x30000ul;
            }
            race_joy[0] = drive(&d[0]);
            race_joy[1] = drive(&d[1]);
            saved = race;
            ref_race_frame();
            expected = race;
            race = saved;
            race_frame();
            if (memcmp(&race, &expected, sizeof race))
                fail(c, f, &race, &expected, 1);
            if (f & 1) {
                saved = race;
                ref_race_picture();
                expected = race;
                race = saved;
                race_picture();
                if (memcmp(&race, &expected, sizeof race))
                    fail(c, f, &race, &expected, 2);
            }
            check_frames++;
        }
    }
    check_done = 1;
    check_exit(0);
}
