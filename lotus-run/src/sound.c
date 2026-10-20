// Lotus Run: the race's sounds (see sound.h).
//
// The original plays player 1's effects on one channel and player 2's on
// another (with one player, player 2's are the countdown's and the
// start's), and an engine for each. An effect is a sample at a period; a
// number: lower ones go first, and one keeps those from its own number on
// off for sound_times[n] frames. An engine is a loop at a period from the
// rpm: 0xF80C0 / rpm. Here the channels are the MEGA65's four audio DMA
// channels, all mixed to the middle - with music on the radio more quietly,
// in the background.

#include "sound.h"

#include "disk.h"
#include "dma.h"
#include "hw.h"
#include "math.h"
#include "mem.h"
#include "race.h"
#include "sounds.h"

_Static_assert(SOUNDS_SIZE <= SOUND_CHIP_SIZE, "the sound samples do not fit into SOUND_CHIP");

// The audio DMA: per channel 16 registers from $D720
#define CH(n)    (0xD720 + 16 * (n))
#define C_ENABLE 0x80
#define C_LOOP   0x40
#define C_8BIT   0x02  // 8-bit samples, signed

#define CH_EFFECT 0  // + player: the effects
#define CH_ENGINE 2  // + player: the engines

// Paula's clock (PAL) per period, as the DMA's step: added every 40.5 MHz
// cycle, a sample on every overflow of 24 bits
#define STEP_PERIOD 1469319ul

// The original's state
static uint16_t rev[2] = {2000, 2000};  // the engines revving before the start
static uint16_t rev_up[2];
static uint16_t engine_rpm[2], engine_volume[2];
static uint32_t kerb_from[2];  // the kerb sounds again from here on
static uint8_t busy[2];        // frames the last effect keeps others off
static int8_t current[2];      // which it is

bool sound_load(void) {
    return disk_load("SOUNDS", SOUNDS_ATTIC);
}

// A channel playing sample s at a period (one-shot or its loop)
static void play(uint8_t ch, uint8_t s, uint16_t period, uint8_t volume) {
    const SoundSample *x = &sound_samples[s];
    uint32_t start = SOUND_CHIP + x->at, end = start + x->len;
    uint16_t r = CH(ch);
    POKE(r, 0);  // stop it first
    POKE(r + 1, (uint8_t)start);
    POKE(r + 2, (uint8_t)(start >> 8));
    POKE(r + 3, (uint8_t)(start >> 16));
    POKE(r + 7, (uint8_t)end);
    POKE(r + 8, (uint8_t)(end >> 8));
    POKE(r + 10, (uint8_t)start);  // the current address
    POKE(r + 11, (uint8_t)(start >> 8));
    POKE(r + 12, (uint8_t)(start >> 16));
    uint32_t step = div32u(STEP_PERIOD, period);
    POKE(r + 4, (uint8_t)step);
    POKE(r + 5, (uint8_t)(step >> 8));
    POKE(r + 6, (uint8_t)(step >> 16));
    POKE(r + 9, volume >= 64 ? 0xFF : (uint8_t)(volume * 4));
    POKE(r, C_ENABLE | C_8BIT | (x->loop_len ? C_LOOP : 0));
}

static void effect(uint8_t player, int8_t e) {
    const SoundNote *n = &sound_notes[e];
    if (n->sample != 0xFF)
        play((uint8_t)(CH_EFFECT + player), n->sample, n->period, sound_samples[n->sample].volume);
}

// An engine's pitch and loudness (Paula's period and volume 0-64)
static void engine(uint8_t player, uint16_t period, uint8_t volume) {
    uint16_t r = CH(CH_ENGINE + player);
    uint32_t step = div32u(STEP_PERIOD, period);
    POKE(r + 4, (uint8_t)step);
    POKE(r + 5, (uint8_t)(step >> 8));
    POKE(r + 6, (uint8_t)(step >> 16));
    POKE(r + 9, volume >= 64 ? 0xFF : (uint8_t)(volume * 4));
}

void sound_off(void) {
    for (uint8_t ch = 0; ch < 4; ch++)
        POKE(CH(ch), 0);
}

// A coefficient of the audio mixer; the mixer needs 32 cycles before the
// next one is selected
static void mixer(uint8_t reg, uint8_t value) {
    POKE(0xD6F4, reg);
    POKE(0xD6F5, value);
    for (volatile uint8_t i = 0; i < 8; i++)
        ;
}

void sound_race_start(bool radio) {
    sound_off();
    dma_copy(SOUNDS_ATTIC, SOUND_CHIP, SOUNDS_SIZE);
    dma_flush();
    // the digital channels to the middle (mixer: left $10-$13, right
    // $30-$33), softer under music; audio DMA on
    uint8_t level = radio ? 0x50 : 0xBE;
    for (uint8_t i = 0; i < 4; i++) {
        mixer((uint8_t)(0x10 + i), level);
        mixer((uint8_t)(0x30 + i), level);
    }
    POKE(0xD711, PEEK(0xD711) | 0x80);
    for (uint8_t n = 0; n < 2; n++) {
        kerb_from[n] = race.p[n].pos | 0x3FFF;
        busy[n] = 0;
        current[n] = 0;
        play((uint8_t)(CH_ENGINE + n), sound_notes[8].sample, sound_notes[8].period, 0);
    }
}

// Before the start the engines rev at random
static void revving(uint8_t n) {
    uint16_t rpm = rev[n];
    if (rev_up[n]) {
        if (rpm >= 5000 && race_random() < 0x1000)
            rev_up[n] = (uint16_t)~rev_up[n];
        else
            rpm = (uint16_t)(rpm + (uint16_t)(((uint32_t)(8000 - rpm) * 0xA00) >> 16));
    } else {
        rpm = (uint16_t)(((uint32_t)rpm * 0xFC00) >> 16);
        if (rpm < 1000)
            rpm = 1000;
        if (rpm < 3000 && race_random() < 0x1000)
            rev_up[n] = (uint16_t)~rev_up[n];
    }
    rev[n] = rpm;
}

// The engine fades out with the camera's distance from the car
static uint16_t distance_volume(const Player *p) {
    int32_t d = (int32_t)(p->pos_view - p->pos_shown);
    if (d < 0)
        d = -d;
    int16_t v = (int16_t)(0x40 - (int16_t)((uint32_t)d >> 12));
    return v < 0 ? 0 : (uint16_t)v;
}

// On the kerb (one sound a quarter segment)
static bool kerb(uint8_t n) {
    const Player *p = &race.p[n];
    int16_t lo = 0xB0, hi = 0x120;
    if (p->pit_lane) {
        lo = 0x140;
        hi = 0x1B0;
    }
    int16_t x = (int16_t)(p->x >> 16);
    if (x >= hi || x < -0x120 || (x < lo && x >= -0xB0) || (int32_t)(p->pos - kerb_from[n]) < 0)
        return false;
    kerb_from[n] = p->pos | 0x3FFF;
    return true;
}

// The crash noise of a player dies down; loud enough, it is the screech
static bool screech(uint16_t *level) {
    *level = (int16_t)(*level - 0x200) < 0 ? 0 : (uint16_t)(*level - 0x200);
    if (*level < 0x4000)
        return false;
    *level = 0;
    return true;
}

void sound_frame(void) {
    int16_t clock = race.clock;
    if (clock < 0) {
        for (uint8_t n = 0; n < 2; n++) {
            revving(n);
            engine_rpm[n] = rev[n];
            engine_volume[n] = 0x40;
        }
    } else {
        for (uint8_t n = 0; n < 2; n++) {
            const Player *p = &race.p[n];
            if ((n == 0 || race.two_players) && p->speed_view) {
                engine_rpm[n] = p->rpm;
                engine_volume[n] = distance_volume(p);
            }
        }
    }
    if (race.paused)
        engine_volume[0] = engine_volume[1] = 0;

    // the effects: the countdown, the start (both players' channels in
    // turn), the screech, the kerb, low fuel, crashes
    int8_t e[2] = {-1, -1};
    if (clock < 0x32) {
        if (clock == -150 || clock == -100 || clock == -50)
            e[0] = e[1] = 3;
        else if (clock == 0 || clock == 10 || clock == 20)
            e[1] = 4;
        else if (clock == 5 || clock == 15 || clock == 25)
            e[0] = 4;
    }
    if (!(race.difficulty == 2 && (race.race_no == 3 || race.race_no == 12))) {
        if (screech(&race.sound_p1))
            e[0] = 7;
        if (screech(&race.sound_p2))
            e[1] = 7;
        if (kerb(0))
            e[0] = 6;
        if (kerb(1))
            e[1] = 6;
    }
    if ((race.p[0].fuel >> 16) < 0x3800 && !(clock & 0x3F))
        e[0] = 5;
    if (race.two_players && (race.p[1].fuel >> 16) < 0x3800 && (clock & 0x3F) == 0x10)
        e[1] = 5;
    for (uint8_t n = 0; n < 2; n++) {
        if (race.crash[n])
            e[n] = (int8_t)race.crash[n];
        race.crash[n] = 0;
        if (race.p[n].stopped)
            e[n] = -1;
        if (clock >= 0x32 && busy[n]) {
            busy[n]--;
            if (e[n] >= current[n])
                e[n] = -1;
        }
        if (e[n] >= 0) {
            busy[n] = sound_times[e[n]];
            current[n] = e[n];
            effect(n, e[n]);
        }
        // the engine; without rpm this frame (standing) silent
        if (engine_rpm[n]) {
            uint16_t period = (uint16_t)(0xF80C0ul / engine_rpm[n]);
            engine(n, period < 0x7C ? 0x7C : period, (uint8_t)engine_volume[n]);
        } else {
            engine(n, 0x3F8, 0);
        }
        engine_rpm[n] = 0;
    }
}
