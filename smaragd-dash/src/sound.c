// Smaragd Dash: sound effects (see sound.h). Every effect plays on two SIDs
// alike, left and right: voices 1-3 on the first ($D400) and the third
// ($D440), voices 4-6 on the second ($D420) and the fourth ($D460), which
// the title's music has (music.c) - in a cave they are the effects'.

#include "sound.h"

#include "engine.h"
#include "hw.h"

#define SID   0xD400
#define SID2  0xD420
#define RIGHT 0x40  // offset of the third SID from the first (the fourth from the second)

#define VOICES 6

#define TRI   0x10
#define SAW   0x20
#define PULSE 0x40
#define NOISE 0x80

// Frames until an envelope with this decay (attack 0, sustain 0) has died
// away, at 60 frames a second and with two to spare. The waveform is
// switched off then: a SID still lets a voice at envelope 0 be heard
// faintly while a waveform is on. Only decays up to 11 are used.
static const uint8_t decay_frames[16] = {
    3, 4, 5, 7, 10, 13, 15, 17, 21, 47, 92, 146, 182, 255, 255, 255};
static uint8_t left[VOICES];  // frames until the voice is switched off

// A sound is not cut off by one of lower rank in the first third of its
// decay, while it is loud: a boulder landing in the tick after an
// explosion would end it before it was heard. The sounds outside the
// ticks have the top rank.
#define TOP 255
static uint8_t rank[VOICES], hold[VOICES];

// A sound starts in two parts: play() closes the gate and sets the test bit
// (the oscillator and the noise generator start afresh), sound_frame()
// opens the gate with the waveform. A SID clocked at 1 MHz, as the real
// MEGA65's, may not see a gate closed and opened again a microsecond later,
// as Xemu does: the envelope would not start again, and with sustain 0 the
// sound stays silent.
#define TEST 0x08
static uint8_t start[VOICES];  // the waveform to open the gate with, 0: none

// The amoeba and the magic wall sound as long as they are alive, as in
// GDash, whose looped sounds come from the C64: a triangle on voice 6 that
// takes a random frequency (its high byte) every frame - the amoeba's
// 120-490 Hz each frame, the magic wall's 2020-2380 Hz every second one,
// both alive: the frames take turns. A sound of voice 6 interrupts it; it
// comes back when that one has died away.
#define HUM_VOICE 5
#define HUM_AMOEBA 1
#define HUM_MAGIC  2
static uint8_t hum;      // HUM_* the last tick wanted; 0: quiet
static uint8_t humming;  // the hum has the voice, its gate is open
static uint8_t hum_odd;  // the frames take turns

static uint16_t voice_reg(uint8_t v) {
    return v < 3 ? SID + v * 7 : SID2 + (v - 3) * 7;
}

// Start a sound on voice v (0-5) of rank r: frequency, waveform and
// attack/decay. The gate opens in the next sound_frame (see start).
static void play(uint8_t v, uint8_t r, uint16_t freq, uint8_t wave, uint8_t ad) {
    if (hold[v] && r < rank[v])
        return;
    rank[v] = r;
    if (v == HUM_VOICE)
        humming = 0;
    left[v] = decay_frames[ad & 15];
    hold[v] = left[v] / 3;
    start[v] = wave;
    uint16_t reg = voice_reg(v);
    for (uint8_t side = 0; side < 2; side++, reg += RIGHT) {
        POKE(reg + 4, TEST);
        POKE(reg + 0, (uint8_t)freq);
        POKE(reg + 1, freq >> 8);
        POKE(reg + 2, 0x00);
        POKE(reg + 3, 0x08);  // pulse width 50 %
        POKE(reg + 5, ad);
        POKE(reg + 6, 0x00);
    }
}

void sound_init(void) {
    for (uint8_t i = 0; i < 25; i++) {
        POKE(SID + i, 0);
        POKE(SID + RIGHT + i, 0);
        POKE(SID2 + i, 0);
        POKE(SID2 + RIGHT + i, 0);
    }
    POKE(SID + 24, 0x0F);  // volume
    POKE(SID + RIGHT + 24, 0x0F);
    POKE(SID2 + 24, 0x0F);
    POKE(SID2 + RIGHT + 24, 0x0F);
}

void sound_off(void) {
    for (uint8_t v = 0; v < VOICES; v++) {
        uint16_t reg = voice_reg(v) + 4;
        POKE(reg, 0);
        POKE(reg + RIGHT, 0);
        left[v] = hold[v] = start[v] = 0;
    }
    hum = humming = 0;
}

void sound_still(void) {
    hum = 0;
}

// Voice 6 in a frame without a sound of its own: the hum starts, goes on
// with a new frequency or ends (its waveform goes off with left, as a
// sound's does)
static void hum_frame(void) {
    uint16_t reg = voice_reg(HUM_VOICE);
    if (!hum) {
        if (humming) {
            humming = 0;
            left[HUM_VOICE] = 3;
            for (uint8_t side = 0; side < 2; side++, reg += RIGHT)
                POKE(reg + 4, TRI);  // gate closed: release 0
        }
        return;
    }
    hum_odd ^= 1;
    uint8_t hi;
    if (hum & HUM_MAGIC && (hum_odd || !(hum & HUM_AMOEBA)))
        hi = 0x86;  // the magic wall
    else
        hi = 0x08;  // the amoeba
    if (hi == 0x86 && !hum_odd && humming)
        return;  // the magic wall alone keeps its frequency for two frames
    hi += (rnd() * 25) >> 8;
    for (uint8_t side = 0; side < 2; side++, reg += RIGHT) {
        POKE(reg + 0, 0);
        POKE(reg + 1, hi);
        if (!humming) {
            POKE(reg + 5, 0x20);  // attack 2: no click
            POKE(reg + 6, 0x70);  // sustain 7, release 0
            POKE(reg + 4, TRI | 1);
        }
    }
    humming = 1;
    rank[HUM_VOICE] = hold[HUM_VOICE] = 0;
}

void sound_frame(void) {
    for (uint8_t v = 0; v < VOICES; v++) {
        if (start[v]) {  // the frames of the sound count from here
            uint16_t reg = voice_reg(v) + 4;
            POKE(reg, start[v] | 1);
            POKE(reg + RIGHT, start[v] | 1);
            start[v] = 0;
            continue;
        }
        if (hold[v])
            hold[v]--;
        if (left[v] && !--left[v]) {
            uint16_t reg = voice_reg(v) + 4;
            POKE(reg, 0);
            POKE(reg + RIGHT, 0);
            continue;  // the gate stays closed for a frame
        }
        if (v == HUM_VOICE && !left[v])
            hum_frame();
    }
}

// The sounds of a cave tick: on each voice the first one wanted plays, and
// it ranks above those behind it
static const struct {
    uint32_t flag;
    uint8_t voice;
    uint16_t freq;
    uint8_t vary;  // the frequency goes up by rnd() times this
    uint8_t wave, ad;
} tick_fx[] = {
    // voice 1: what Rockford takes (and the time counted into the score)
    {SND_CLOCK, 0, 0x3800, 0, PULSE, 0x0A},  // a bell
    {SND_COLLECT, 0, 0x6800, 16, TRI, 0x09},
    {SND_PICKUP, 0, 0x5400, 0, PULSE, 0x08},
    // voice 2: what falls
    {SND_NUT, 1, 0x2800, 0, NOISE, 0x05},  // a crack
    {SND_BOULDER, 1, 0x0700, 0, NOISE, 0x07},
    // voice 3: diamonds landing (and the exit, the last seconds, a life)
    {SND_CRACK, 2, 0x2000, 0, NOISE, 0x08},  // Rockford hatches: as the exit opens
    {SND_DIAMOND, 2, 0x3000, 64, TRI, 0x06},
    // voice 4: explosions and machines
    {SND_EXPLODE, 3, 0x1400, 0, NOISE, 0x0B},
    {SND_DOOR, 3, 0x0B00, 0, SAW, 0x07},     // a creak
    {SND_HAMMER, 3, 0x4000, 0, NOISE, 0x02},  // a rattle
    {SND_BOMB, 3, 0x3000, 0, PULSE, 0x02},    // a tick
    {SND_GROW, 3, 0x0900, 0, PULSE, 0x06},    // a low knock
    // voice 5: Rockford's steps
    {SND_DIRT, 4, 0xB000, 0, NOISE, 0x03},
    {SND_STEP, 4, 0xF000, 0, NOISE, 0x01},
    // voice 6: what goes on in the cave
    {SND_TELEPORT, 5, 0x7000, 0, SAW, 0x09},
    {SND_SWITCH, 5, 0x4800, 0, PULSE, 0x01},  // a click
    {SND_SLIME, 5, 0x1800, 8, PULSE, 0x05},  // a blob
    {SND_HISS, 5, 0xD000, 0, NOISE, 0x03},
};
#define TICK_FX (sizeof tick_fx / sizeof *tick_fx)

void sound_tick(uint32_t ev) {
    hum = ev & SND_MAGIC ? HUM_MAGIC : ev & SND_AMOEBA ? HUM_AMOEBA : 0;
    uint8_t done = 0;  // a bit for each voice that has had its sound
    for (uint8_t i = 0; i < TICK_FX; i++) {
        uint8_t v = tick_fx[i].voice;
        if (!(ev & tick_fx[i].flag) || (done & 1 << v))
            continue;
        done |= 1 << v;
        uint16_t freq = tick_fx[i].freq;
        if (tick_fx[i].vary)
            freq += rnd() * tick_fx[i].vary;
        play(v, TICK_FX - i, freq, tick_fx[i].wave, tick_fx[i].ad);
    }
}

void sound_crackle(void) {
    play(2, TOP, 0x8000 + rnd() * 128, NOISE, 0x01);
}

void sound_clock(void) {
    play(2, TOP, 0x2400, PULSE, 0x05);
}

void sound_bonus(void) {
    play(0, TOP, 0x4000 + rnd() * 32, TRI, 0x02);
}

void sound_exit(void) {
    play(2, TOP, 0x2000, NOISE, 0x08);
}

void sound_life(void) {
    play(2, TOP, 0x5800, SAW, 0x0A);
}
