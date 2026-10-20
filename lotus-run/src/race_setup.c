// Lotus Run: getting a race ready (see race.h). Not part of the frame's
// logic, so in C for both the reference (ref/race.c) and the MEGA65's
// assembly (race.s).

#include "race.h"

#include "progdata.h"

static int16_t hi(int32_t v) {
    return (int16_t)((uint32_t)v >> 16);
}

// ---------------------------------------------------------------- the course

// What the game adds to the course's segments - the sums of curve
// and hill up to each segment (bytes 12, 13) and how far out the opponents
// may drive (14, 15: inside the nearest scenery, and widening slowly)
void race_track_setup(Track *t) {
    uint16_t n = t->segments;
    uint8_t curve = 0, hill = 0;
    for (uint16_t i = 0; i < n; i++) {
        Segment *g = &t->seg[i];
        g->spare[0] = curve;
        g->spare[1] = hill;
        curve = (uint8_t)(curve + (uint8_t)g->curve);
        hill = (uint8_t)(hill + (uint8_t)g->hill);
    }
    for (uint16_t i = 0; i < n; i++) {
        Segment *g = &t->seg[i];
        uint8_t left = 0xEE, right = 0x12;
        for (int8_t q = 3; q >= 0; q--) {
            uint8_t type = g->object[q].type;
            if (!type || type == 0x82)
                continue;
            uint8_t x = (uint8_t)g->object[q].x;
            if (x & 0x80) {
                if (x >= left)  // unsigned
                    left = x;
            } else if (x < right) {
                right = x;
            }
        }
        g->spare[2] = (uint8_t)(left + 8);
        g->spare[3] = (uint8_t)(right - 8);
    }
    // from the end backwards: limits widen by one per segment at most
    int8_t left = -10, right = 10;
    for (int16_t i = (int16_t)(n - 1); i >= 0; i--) {
        Segment *g = &t->seg[i];
        int8_t l = (int8_t)g->spare[2];
        if (l != left) {
            if ((int8_t)(l - left) >= 0)
                left = l;
            else
                left--;
        }
        g->spare[2] = (uint8_t)left;
        int8_t r = (int8_t)g->spare[3];
        if (r != right) {
            if ((int8_t)(r - right) < 0)
                right = r;
            else
                right++;
        }
        g->spare[3] = (uint8_t)right;
    }
    // the 8 segments repeated at the end
    for (uint8_t i = 0; i < 8; i++)
        t->seg[n + i] = t->seg[i];
}

// ---------------------------------------------------------------- the start

void race_init(void) {
    race.laps = tab_laps[race.course];
    race.opp_bonus = (uint16_t)((uint32_t)tab_opp_bonus[race.course] * 0x2000 / 0xC0);
    race.opponents = (uint16_t)(19 - race.two_players);
    for (uint8_t i = 0; i < 20; i++)
        race.finish_frames[i] = 0;
    race.frames = 0;
    race.next_finisher = 0;
    race.finished = 0;
    race.paused = 0;
    race.over = 0;
    race.over_timer = 0;
    race.p[0].stopped = 0;
    race.p[1].stopped = 0;
    race_track_setup((Track *)race_track);

    // the grid: the player at the back in the first race, then by the
    // last race's place
    uint16_t slot1, slot2;
    if (race.difficulty == 3) {
        slot1 = 0;
        slot2 = 1;
    } else if (race.race_no && !race.demo) {
        slot1 = (uint16_t)(20 - race.p[0].place);
        slot2 = (uint16_t)(20 - race.p[1].place);
    } else {
        slot1 = 19;
        slot2 = 18;
    }
    race.p[0].place = (uint16_t)(slot1 + 1);
    race.p[1].place = (uint16_t)(slot2 + 1);
    uint32_t lap = (uint32_t)race.segments << 16;
    Opponent *o = race.opp;
    for (uint8_t k = 0; k < 20; k++) {
        uint32_t pos = tab_grid_pos[19 - k] + lap;
        int16_t x = tab_grid_x[19 - k];
        Player *p = 0;
        if (k == slot1)
            p = &race.p[0];
        else if (race.two_players && k == slot2)
            p = &race.p[1];
        if (p) {
            p->pos = pos;
            p->x = (int32_t)((uint32_t)(uint16_t)x << 16 | (uint16_t)p->x);
            continue;
        }
        o->pos = pos;
        o->x = x;
        o->speed = 0;
        o->target = (uint16_t)((race_random() & 0x7FF) - 0x400);
        int16_t dx;
        do {
            uint16_t r = race_random() & 7;
            dx = (int16_t)(r - 2);
            if (r >= 5)
                dx = 0;
        } while (!dx);
        o->dx = dx;
        o++;
    }
    if (race.difficulty == 3) {
        race.p[0].pos = 0xFFFF0000ul;
        race.p[1].pos = 0xFFFF0000ul;
    }
    for (uint8_t n = 0; n < 2; n++) {
        Player *p = &race.p[n];
        p->cam_pos = p->pos - 0x2C3D0;  // the camera flies in from behind
        p->cam_x = hi(p->x);
    }
    race.seg_bias = (uint32_t)race.segments * 100;
    race.opp_length = (uint32_t)(race.segments - 16) << 16;
    for (uint8_t n = 0; n < 2; n++) {
        Player *p = &race.p[n];
        p->u96 = 3;
        p->fuel = 0xFFFFFFFFul;
        p->pit_request = -1;
        p->pit_timer = 0;
        p->pit_lane = 0;
        p->gear = 0;
        p->speed = 0;
        p->u16 = 0;
        p->curve = 0;
        p->in_pits = 0;
        p->steer = 0;
        p->slope = 0;
        p->push_x = 0;
        p->push_steer = 0;
        p->accelerating = 0;
        p->rpm = 0;
        p->timer = 0xFFFF;
        // the colours of the scenery ahead, and the course where the car is
        race_lookup_pos = p->pos - 0x80000;
        for (uint8_t i = 0; i < 32; i++, race_lookup_pos += 0x4000)
            race_seg_lookup(n);
    }
    race.finish = (uint32_t)(uint16_t)((uint32_t)(race.laps + 1) * race.segments) << 16;
    race.clock = -250;
    race.buffer = 2;
}

