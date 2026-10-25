// Smaragd Dash: the music player in C - the reference for src/music.s,
// which the game plays. Built only for the check (-DASM_CHECK,
// tests/test_music.sh): both play the song for thousands of frames, PAL
// and NTSC, each into a copy of the SIDs' registers in RAM, and every
// frame the copies must be the same.
//
// Six voices on the second ($D420, left) and fourth ($D460, right) SID;
// the sound effects keep the first and third. Called once per frame; the
// song is written for 50 frames a second, so at 60 (NTSC) every sixth
// frame is left out.

#include "music.h"

#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include "hw.h"
#include "song.h"

// The numbers src/music.s stands on
_Static_assert(SONG_TEMPO == 6 && SONG_VOICES == 6, "src/music.s: TEMPO, VOICES");
_Static_assert(sizeof(struct instrument) == 11 && offsetof(struct instrument, pw) == 3 &&
                   offsetof(struct instrument, noise) == 10,
               "src/music.s: I_*");
_Static_assert(SONG_INSTRUMENTS * sizeof(struct instrument) <= 256, "src/music.s: v_in");

#ifdef ASM_CHECK
static uint16_t sid_l, sid_r;  // the copies of the SIDs
#define SID_L sid_l
#define SID_R sid_r

struct voice {
    const uint8_t *p;
    const struct instrument *in;
    uint16_t reg;     // SID voice registers
    uint16_t freq;
    uint16_t pw;
    int8_t pwm;
    uint8_t note;
    uint8_t len;      // rows per note
    uint8_t rows;     // rows left of the current note
    uint8_t t;        // frames since the note started
    bool gate;
};

static struct voice voices[SONG_VOICES];
static uint8_t row_frame;
static uint16_t filter_t;
static bool playing;
static bool ntsc;
static uint8_t ntsc_frame;  // counts to 6: the sixth is left out

static const int8_t arp_steps[3][3] = {{0, 0, 0}, {0, 3, 7}, {0, 4, 7}};
static const int8_t vib_wave[8] = {0, 1, 2, 1, 0, -1, -2, -1};

static void next_event(struct voice *v) {
    for (;;) {
        uint8_t b = *v->p++;
        if (b == 0xFF) {
            v->p = song_voice[v - voices];
        } else if (b >= 0xC0) {
            v->len = (b & 0x3F) + 1;
        } else if (b >= 0x80) {
            v->in = &song_instr[b & 0x3F];
        } else {
            v->rows = v->len;
            if (b == 0x7F) {  // rest
                POKE(v->reg + 4, v->in->wave);
                v->gate = false;
                return;
            }
            const struct instrument *in = v->in;
            v->note = b;
            v->freq = note_freq[b];
            v->pw = in->pw;
            v->pwm = in->pwm;
            v->t = 0;
            v->gate = true;
            POKE(v->reg + 4, 0x08);  // test bit: restart the oscillator
            POKE(v->reg + 5, in->ad);
            POKE(v->reg + 6, in->sr);
            return;
        }
    }
}

static void sid_setup(uint16_t sid) {
    for (uint8_t i = 0; i < 25; i++)
        POKE(sid + i, 0);
    POKE(sid + 0x17, 0xA2);  // resonance 10, filter on voice 2 (bass)
    POKE(sid + 0x18, 0x1F);  // low pass, full volume
}

static void music_c_start(void) {
    sid_setup(SID_L);
    sid_setup(SID_R);
    for (uint8_t i = 0; i < SONG_VOICES; i++) {
        struct voice *v = &voices[i];
        v->p = song_voice[i];
        v->in = &song_instr[0];
        v->reg = (i < 3 ? SID_L : SID_R) + (i % 3) * 7;
        v->rows = 1;
        v->len = 1;
        v->gate = false;
    }
    row_frame = SONG_TEMPO - 1;
    filter_t = 0;
    ntsc = PEEK(0xD06F) & 0x80;
    ntsc_frame = 0;
    playing = true;
}

static void music_c_stop(void) {
    playing = false;
    POKE(SID_L + 0x18, 0);
    POKE(SID_R + 0x18, 0);
    for (uint8_t i = 0; i < SONG_VOICES; i++)
        POKE(voices[i].reg + 4, 0);
}

static void music_c_frame(void) {
    if (!playing)
        return;
    if (ntsc && ++ntsc_frame == 6) {
        ntsc_frame = 0;
        return;
    }
    bool row = ++row_frame == SONG_TEMPO;
    if (row)
        row_frame = 0;

    for (uint8_t i = 0; i < SONG_VOICES; i++) {
        struct voice *v = &voices[i];
        if (row && --v->rows == 0)
            next_event(v);
        const struct instrument *in = v->in;
        if (!v->gate)
            continue;
        // close the gate shortly before the next note, so it starts fresh
        if (v->rows == 1 && row_frame == SONG_TEMPO - 2) {
            v->gate = false;
            POKE(v->reg + 4, in->wave);
            continue;
        }
        uint16_t f = v->freq;
        if (in->arp) {
            f = note_freq[v->note + arp_steps[in->arp][v->t % 3]];
        } else if (in->sweep) {
            v->freq -= v->freq >> in->sweep;
            f = v->freq;
        } else if (in->vib_depth && v->t > in->vib_delay) {
            f += (int16_t)(f >> in->vib_depth) * vib_wave[v->t & 7] / 2;
        }
        if (v->pwm) {
            v->pw += v->pwm;
            if (v->pw < 0x200 || v->pw > 0xE00)
                v->pwm = -v->pwm;
        }
        uint8_t wave = v->t < in->noise ? 0x80 : in->wave;
        POKE(v->reg + 0, (uint8_t)f);
        POKE(v->reg + 1, f >> 8);
        POKE(v->reg + 2, (uint8_t)v->pw);
        POKE(v->reg + 3, v->pw >> 8);
        POKE(v->reg + 4, wave | 1);
        if (v->t < 255)
            v->t++;
    }

    // the bass filter opens and closes slowly (one cycle every 8 bars)
    filter_t++;
    uint16_t phase = filter_t & 0x3FF;
    uint16_t cutoff = 0x180 + (phase < 0x200 ? phase : 0x3FF - phase);
    POKE(SID_L + 0x15, cutoff & 7);
    POKE(SID_L + 0x16, cutoff >> 3);
    POKE(SID_R + 0x15, cutoff & 7);
    POKE(SID_R + 0x16, cutoff >> 3);
}

// The check: music_bad frames of music_frames were not the same
extern uint16_t music_sid_l, music_sid_r;  // src/music.s
extern uint8_t music_ntsc;
uint16_t music_bad, music_frames;

void music_check(void) {
    static uint8_t a[0x80], b[0x80];  // two SIDs each, $40 apart
    for (uint8_t n = 0; n < 2; n++) {
        memset(a, 0, sizeof a);
        memset(b, 0, sizeof b);
        music_sid_l = (uint16_t)a;
        music_sid_r = (uint16_t)a + 0x40;
        sid_l = (uint16_t)b;
        sid_r = (uint16_t)b + 0x40;
        music_start();
        music_c_start();
        music_ntsc = ntsc = n;
        for (uint16_t k = 0; k < 4000; k++) {  // more than two times the song
            music_frame();
            music_c_frame();
            music_bad += memcmp(a, b, sizeof a) != 0;
            music_frames++;
        }
        music_stop();
        music_c_stop();
        music_bad += memcmp(a, b, sizeof a) != 0;
    }
    music_sid_l = 0xD420;
    music_sid_r = 0xD460;
}
#endif
