// Smaragd Dash: sound effects (see sound.h). Every effect plays on the
// first SID ($D400, left) and the third ($D440, right) alike.

#include "sound.h"

#include "engine.h"
#include "hw.h"

#define SID   0xD400
#define RIGHT 0x40  // offset of the third SID

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
static uint8_t left[3];  // frames until the voice is switched off

// Start a sound on voice v (0-2): frequency, waveform, attack/decay and
// sustain/release. The gate is closed first so the envelope starts again.
static void play(uint8_t v, uint16_t freq, uint8_t wave, uint8_t ad, uint8_t sr) {
    uint16_t r = SID + v * 7;
    left[v] = decay_frames[ad & 15];
    for (uint8_t side = 0; side < 2; side++, r += RIGHT) {
        POKE(r + 4, wave);
        POKE(r + 0, (uint8_t)freq);
        POKE(r + 1, freq >> 8);
        POKE(r + 2, 0x00);
        POKE(r + 3, 0x08);  // pulse width 50 %
        POKE(r + 5, ad);
        POKE(r + 6, sr);
        POKE(r + 4, wave | 1);
    }
}

void sound_init(void) {
    for (uint8_t i = 0; i < 25; i++) {
        POKE(SID + i, 0);
        POKE(SID + RIGHT + i, 0);
    }
    POKE(SID + 24, 0x0F);  // volume
    POKE(SID + RIGHT + 24, 0x0F);
}

void sound_off(void) {
    for (uint8_t v = 4; v < 21; v += 7) {
        POKE(SID + v, 0);
        POKE(SID + RIGHT + v, 0);
    }
    left[0] = left[1] = left[2] = 0;
}

void sound_frame(void) {
    for (uint8_t v = 0; v < 3; v++)
        if (left[v] && !--left[v]) {
            POKE(SID + v * 7 + 4, 0);
            POKE(SID + RIGHT + v * 7 + 4, 0);
        }
}

void sound_tick(uint8_t ev) {
    // voice 1
    if (ev & SND_COLLECT)
        play(0, 0x6800 + rnd() * 16, TRI, 0x09, 0x00);
    else if (ev & SND_DIAMOND)
        play(0, 0x3000 + rnd() * 64, TRI, 0x06, 0x00);
    // voice 2
    if (ev & SND_EXPLODE)
        play(1, 0x1400, NOISE, 0x0B, 0x00);
    else if (ev & SND_BOULDER)
        play(1, 0x0700, NOISE, 0x07, 0x00);
    else if (ev & SND_DIRT)
        play(1, 0xB000, NOISE, 0x03, 0x00);
    else if (ev & SND_STEP)
        play(1, 0xF000, NOISE, 0x01, 0x00);
    // voice 3
    if (ev & SND_MAGIC)
        play(2, 0x5000 + rnd() * 64, TRI, 0x04, 0x00);
    else if (ev & SND_AMOEBA)
        play(2, 0x0300 + (rnd() & 0x3F) * 8, PULSE, 0x04, 0x00);
}

void sound_crackle(void) {
    play(2, 0x8000 + rnd() * 128, NOISE, 0x01, 0x00);
}

void sound_clock(void) {
    play(2, 0x2400, PULSE, 0x05, 0x00);
}

void sound_bonus(void) {
    play(0, 0x4000 + rnd() * 32, TRI, 0x02, 0x00);
}

void sound_exit(void) {
    play(2, 0x2000, NOISE, 0x0A, 0x00);
}

void sound_life(void) {
    play(2, 0x5800, SAW, 0x0A, 0x00);
}
