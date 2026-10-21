// Lotus Run: the race (see race.h) - the reference in C.
//
// The MEGA65 runs the same in assembly (src/race.s); this one is what the
// assembly is checked against on the MEGA65 (tests/check_race.c).
//
// The arithmetic is exact to the bit: 16-bit words that wrap, divisions
// that leave the register alone when the quotient does not fit (divu/divs
// below), bytes added as bytes.

#include "../race.h"

#include "progdata.h"
#include "sprbanks.h"


// ---------------------------------------------------------------- arithmetic

// divu.w: d = d / b, quotient in the low word and remainder in the high
// word; when the quotient does not fit into 16 bits, d stays as it is
static uint32_t divu(uint32_t d, uint16_t b) {
    uint32_t q = d / b;
    if (q > 0xFFFF)
        return d;
    return (d % b) << 16 | q;
}

// divs.w, the same signed
static uint32_t divs(int32_t d, int16_t b) {
    int32_t q = d / b;
    if (q > 32767 || q < -32768)
        return (uint32_t)d;
    return (uint32_t)(d % b) << 16 | (uint16_t)q;
}

static int16_t hi(int32_t v) {
    return (int16_t)((uint32_t)v >> 16);
}

// The segment number of pos: ext.l, then divu by the segment count, the
// remainder. Before the course (a negative position, which only the unused
// second player's car has) the division overflows and it ends up
// with -1: the 16 bytes in front of the segments, zeros.
static int16_t seg_of(uint32_t pos) {
    if (hi((int32_t)pos) < 0)
        return -1;
    return (int16_t)(divu((uint32_t)(int32_t)hi((int32_t)pos), race.segments) >> 16);
}

static const Segment *seg_at(int16_t i) {
    static const Segment none;
    return i < 0 ? &none : &race_track->seg[i];
}

static const Segment *segment(uint32_t pos) {
    return seg_at(seg_of(pos));
}

// ---------------------------------------------------------------- random

uint16_t race_random(void) {
    // four long words, each added with carry to the sum so far and a constant
    static const uint32_t k[4] = {0x7362541F, 0x7FBE6475, 0x83265984, 0xF0293747};
    uint32_t d0 = 0;
    uint8_t x = 0;
    for (uint8_t i = 0; i < 4; i++) {
        uint32_t s = race.random[i] + d0;
        uint8_t c = s < d0;
        s += x;
        c |= s < x;
        d0 = s + k[i];
        x = d0 < s;
        d0 += c;
        x |= d0 < c;
        race.random[i] = d0;
    }
    return (uint16_t)d0;
}

// ---------------------------------------------------------------- the course

// Curve and slope at pos, and the scenery colours of the objects ahead
static void seg_lookup(Player *p, uint32_t pos) {
    int16_t i = seg_of(pos);
    const Segment *g = seg_at(i);
    uint16_t way = (uint16_t)pos >> 4;
    int16_t hill2 = (int8_t)(uint8_t)(g->hill + g->hill);  // add.b: a byte
    int16_t slope = (int16_t)((int32_t)hill2 * (int16_t)way >> 8);
    slope = (int16_t)(slope + (int8_t)g->spare[1] * 32);
    int16_t curve2 = (int16_t)(g->curve * 2);
    int16_t bend = (int16_t)((int32_t)curve2 * (int16_t)way >> 8);
    bend = (int16_t)(bend + (int8_t)g->spare[0] * 32);
    p->curve = curve2;
    p->slope = (int16_t)-slope;
    p->u16 = (int16_t)-bend;
    // the object 7 segments on, in this quarter
    uint8_t type = seg_at((int16_t)(i + 7))->object[(uint16_t)pos >> 14].type;
    if (type) {
        const uint16_t *c = &tab_object_colours[(type - 0x80) * 4];
        for (uint8_t i = 0; i < 4; i++)
            if (c[i])
                p->colours[i] = c[i];
    }
}

// the course where the car (or the camera) is
static void seg_here(Player *p) {
    uint32_t pos = p->pos;
    if (race.clock < 0 || (p->stopped && p->fuel && p->place < 11))
        pos = p->cam_pos;
    seg_lookup(p, pos);
}

// ---------------------------------------------------------------- one car

// moving on, and sideways
static void move(Player *p) {
    int32_t x = p->x;
    p->pos += (uint32_t)(int32_t)(int16_t)p->speed;
    if (!p->push_x) {
        uint16_t s = p->speed;
        if (p->accelerating && s >= 0x0A00)
            s = (uint16_t)((s - 0x0A00) / 2 + 0x0A00);
        if (s < 0x0A00)
            s = (uint16_t)(s + 0x0A00) >> 1;
        int16_t d = (int16_t)(p->speed_view - s);
        if (d >= 0) {
            int32_t m = (int32_t)d * p->steer;
            uint16_t w = (uint16_t)m;
            if (m < 0)
                w = (uint16_t)-w;
            race.scrape = w >> 5;
        }
        x += 5 * ((int32_t)(int16_t)s * p->steer);
    }
    int16_t c = p->curve;
    c = (int16_t)(c * 12);
    x += (int32_t)c * (int16_t)p->speed;
    x += (int32_t)p->push_x * 0x8000;  // swap, clr, asr.l #1
    int16_t xi = hi(x);
    if (xi < -0x180)
        x = (int32_t)0xFE80FFFFul;  // the fraction's word stays here
    else if (xi >= 0x180)
        x = 0x01800000;
    p->x = x;
}

// fuel
static void burn(Player *p) {
    if (p->stopped)
        return;
    int16_t over = (int16_t)(p->rpm - 5000);
    uint32_t use = (uint16_t)((over < 0 ? 0 : over) + p->rpm);
    use <<= 6;
    if (p->fuel < use)
        p->fuel = 0;
    else
        p->fuel -= use;
}

// into the pits
static void pit_check(Player *p) {
    if (p->fuel && p->stopped)
        return;
    const Segment *g = segment(p->pos_view);
    p->pit_lane = 0;
    if (!g->variant)
        return;
    p->pit_lane = 1;
    int16_t x = hi(p->x_view);
    if (x < 0xE8 || x >= 0x138 || p->speed_view >= 0x42A)
        return;
    if (!(p->joy & JOY_DOWN) || p->pit_timer)
        return;
    p->pit_request = 1;
    p->gear = 0;
    p->speed = 0;
    p->pit_timer = 25;
}

// in the pits - refuel, leave with the accelerator
static void in_pits(Player *p) {
    if ((p->joy & (p->fire_accel ? JOY_FIRE : JOY_UP)) && !p->pit_timer) {
        p->pit_request = 0;
        p->pit_timer = 25;
    }
    if (!p->fuel)
        p->stopped = 0;
    uint32_t f = p->fuel + 0x00800000ul;  // addi.w to the high word
    p->fuel = f < p->fuel ? 0xFFFFFFFFul : f;
}

static void timers(Player *p) {
    if (p->pit_timer)
        p->pit_timer--;
    if (p->pit_request >= 0) {
        p->in_pits = (uint16_t)p->pit_request;
        p->pit_request = -1;
    }
}

// A crash: speed and a push to the side (and its relatives)
static void push(Player *p, int16_t side, int16_t strength) {
    int16_t steer = -8;
    race.hit = 1;
    if (side >= 0) {
        strength = (int16_t)-strength;
        steer = 8;
    }
    p->push_steer = steer;
    p->push_x = strength;
}

// the scenery of the car's quarter segment
static void hit_scenery(Player *p) {
    race.hit = 0;
    uint32_t pos = p->pos + 0x2000;
    if (pos & 0x2000)
        return;
    const Segment *g = segment(pos);
    uint8_t q = (uint8_t)((uint16_t)pos >> 14);
    uint8_t type = g->object[q].type;
    if (!type)
        return;
    int16_t px = hi(p->x);
    int16_t d = (int16_t)(g->object[q].x * 16 - px);
    uint8_t w = tab_object_width[type - 0x80];
    if (!w) {
        // a gate: its two posts
        if ((uint16_t)(-0x120 - px + 0x28) >= 0x50 && (uint16_t)(0x120 - px + 0x28) >= 0x50)
            return;
        d = (int16_t)(-0x120 - px);  // only its sign matters below
        if ((uint16_t)(d + 0x28) >= 0x50)
            d = (int16_t)(0x120 - px);
    } else {
        uint16_t half = (uint16_t)(w + 0x40) >> 1;
        if ((uint16_t)(d + half) >= (uint16_t)(2 * half))
            return;
        if (type == 0xA2) {
            // a ramp?: noise and a sideways push, no loss of speed
            race.scrape = 0x6000;
            int16_t s = (int16_t)((p->speed >> 9) + 0x10);
            int16_t steer = -8;
            if (d >= 0) {
                s = (int16_t)-s;
                steer = 8;
            }
            if (!p->push_steer) {
                p->push_steer = steer;
                p->push_x = s;
            }
            return;
        }
        if (type == 0xA3) {
            // slows down
            int16_t over = (int16_t)(p->speed - 0xD55);
            if (over >= 0)
                p->speed -= (uint16_t)over >> 1;
            return;
        }
    }
    uint16_t s = p->speed;
    p->speed = s >> 1;
    push(p, d, (int16_t)((s >> 9) + 0x10));
}

// the opponents
static void hit_opponents(Player *p) {
    race.hit = 0;
    int32_t lap = (int32_t)race.segments << 16;
    Opponent *o = race.opp;
    int32_t from = (int32_t)p->pos - 0x2000, to = (int32_t)p->pos + 0x2000;
    while (from >= (int32_t)o[0].pos) {
        from -= lap;
        to -= lap;
    }
    // the last opponent: the game patches this offset to the count it has
    while (to < (int32_t)o[race.opponents - 1].pos) {
        from += lap;
        to += lap;
    }
    for (uint8_t i = 0; i < race.opponents; i++, o++) {
        int32_t d = (int32_t)o->pos;
        if (d < from)
            return;
        d -= to;
        if (d >= 0)
            continue;
        int16_t dx = (int16_t)(o->x - hi(p->x));
        if (dx < -0x40 || dx >= 0x40)
            return;
        d += 0x2000;
        if (d >= 0 && o->speed < p->speed) {
            // into its back
            p->pos += (uint32_t)(d - 0x2000);
            uint16_t s = p->speed;
            p->speed = (uint16_t)(((uint32_t)s * 0xA000) >> 16);
            push(p, dx, (int16_t)((s >> 11) + 0x10));
            return;
        }
        // side by side: it moves away
        if (dx >= 0) {
            dx = 0x40;
            if (o->dx < 0)
                o->dx = (int16_t)-o->dx;
        } else {
            dx = -0x40;
            if (o->dx >= 0)
                o->dx = (int16_t)-o->dx;
        }
        o->x = (int16_t)(dx + hi(p->x));
        return;
    }
}

// the other player's car
static void hit_other(Player *p, const Player *other) {
    race.hit = 0;
    int16_t dx = (int16_t)(hi(other->x) - hi(p->x));
    if (dx < -0x40 || dx >= 0x40)
        return;
    uint32_t d = other->pos - p->pos;
    uint32_t q = divu((uint32_t)((int32_t)hi((int32_t)d) + race.seg_bias), race.segments);
    d = (q & 0xFFFF0000ul) | (uint16_t)d;
    if (d >= 0x2000)
        return;
    race.p[1].pos += d - 0x2000;  // player 2 is moved either way
    p->speed = (uint16_t)(((uint32_t)p->speed * 0xA000) >> 16);
    push(p, dx, (int16_t)((p->speed >> 10) + 0x10));
}

// steering, engine, gears
static void drive(Player *p) {
    int16_t steer = p->steer;
    int16_t speed = (int16_t)p->speed;
    uint16_t gear = p->gear;
    uint16_t ratio = tab_gear_ratio[gear];
    uint16_t rpm;
    p->accelerating = 0;
    if (!p->push_x) {
        if (p->joy & JOY_LEFT)
            steer -= 2;
        if (p->joy & JOY_RIGHT)
            steer += 2;
        rpm = (uint16_t)divu((uint32_t)(uint16_t)speed << 16, ratio);
        if (rpm >= 0x1F40)
            rpm = 0x1F3F;
        const int16_t *torque = tab_torque;
        if (p->joy & (p->fire_accel ? JOY_FIRE : JOY_UP)) {
            torque = tab_torque_acc;
            p->accelerating = 0xFFFF;
        }
        int32_t t = (int32_t)torque[rpm >> 7] * 3 * 1024;
        speed = (int16_t)(speed + (int16_t)divs(t, (int16_t)(ratio >> 1)));
    }
    steer = (int16_t)(steer + p->push_steer);
    if (steer > 0)
        steer--;
    else if (steer < 0)
        steer++;
    if (steer >= 0x20)
        steer = 0x20;
    if (steer < -0x20)
        steer = -0x20;
    if (p->push_steer)
        p->push_steer += p->push_steer < 0 ? 1 : -1;
    if (p->push_x)
        p->push_x += p->push_x < 0 ? 1 : -1;
    // off the road: the grass slows down
    int8_t grip = tab_grip[(uint16_t)(hi(p->x_view) + 0x200) >> 4];
    if (grip)
        speed = (int16_t)(speed - ((speed >> grip) >> 1));
    speed = (int16_t)(speed + (p->slope_view >> 5));
    if (p->joy & JOY_DOWN)
        speed = (int16_t)(speed - 0x30);
    if (speed < 0x1AA)
        speed = 0x1AA;
    // the engine's speed, kept between 1000 and 7999
    rpm = (uint16_t)divu((uint32_t)(int32_t)speed << 16, ratio);
    if ((int16_t)rpm < 0x3E8)
        rpm = 0x3E8;
    if ((int16_t)rpm >= 0x1F3F)
        rpm = 0x1F3F;
    speed = (int16_t)(((uint32_t)rpm * ratio) >> 16);
    // gears
    int16_t to = -1;
    if (!p->stopped && !p->automatic) {
        uint8_t up, down;
        if (p->fire_accel) {
            up = p->joy_new & JOY_UP;
            down = p->joy_new & JOY_DOWN;
        } else {
            up = (p->joy & JOY_UP) && (p->joy_new & JOY_FIRE);
            down = (p->joy & JOY_DOWN) && (p->joy_new & JOY_FIRE);
        }
        if (up && gear != 4)
            to = (int16_t)(gear + 1);
        else if (down && gear)
            to = (int16_t)(gear - 1);
    } else if (rpm > p->rpm) {
        if (rpm >= 0xFA0 && gear != 4)
            to = (int16_t)(gear + 1);
    } else if (rpm < 0x9C4 && gear) {
        to = (int16_t)(gear - 1);
    }
    if (to >= 0) {
        uint16_t r = tab_gear_ratio[to];
        uint16_t n = (uint16_t)divu((uint32_t)(int32_t)speed << 16, r);
        if (n >= 0x3E8 && n < 0x1F3F) {
            rpm = n;
            speed = (int16_t)(((uint32_t)n * r) >> 16);
            gear = (uint16_t)to;
        }
    }
    p->gear = gear;
    p->steer = steer;
    p->speed = (uint16_t)speed;
    p->rpm = rpm;
}

static void drive_or_coast(Player *p) {
    if (!p->speed_view)
        p->joy = 0;
    if (!p->stopped) {
        drive(p);
        return;
    }
    uint16_t s = p->speed;
    drive(p);
    int16_t v = (int16_t)(s - 0x18);
    p->speed = v < 0 ? 0 : (uint16_t)v;
}

// One player's frame
static void player_frame(uint8_t n) {
    Player *p = &race.p[n];
    if (p->in_pits) {
        in_pits(p);
        timers(p);
        return;
    }
    race.scrape = 0;
    move(p);
    if (n)
        race.sound_p2 += race.scrape;
    else
        race.sound_p1 += race.scrape;
    burn(p);
    seg_here(p);
    pit_check(p);
    race.scrape = 0;
    hit_scenery(p);
    race.sound_p1 += race.scrape;  // both players' scraping goes here
    if (race.hit)
        race.crash[n] = 1;
    if (race.difficulty != 3) {
        hit_opponents(p);
        if (race.hit)
            race.crash[n] = 2;
    }
    if (race.two_players) {
        hit_other(p, &race.p[n ^ 1]);
        if (race.hit)
            race.crash[n] = 2;
    }
    drive_or_coast(p);
    timers(p);
}

// ---------------------------------------------------------------- opponents

static void opponents(void) {
    Opponent *o = race.opp;
    int16_t n = (int16_t)race.opponents;
    for (int16_t i = 0; i < n; i++, o++) {
        uint32_t pos = o->pos;
        int16_t x = o->x;
        uint16_t speed = o->speed;
        uint16_t target = o->target;
        int16_t dx = o->dx;
        uint16_t want = (uint16_t)(target + race.opp_bonus);
        speed = (uint16_t)(speed + (((uint16_t)(want - speed) >> 7) + 1));
        if (want < speed)
            speed = want;
        const Segment *g = segment(pos);
        int16_t right = (int16_t)((int8_t)g->spare[3] * 16);
        int16_t left = (int16_t)((int8_t)g->spare[2] * 16);
        if (x >= right) {
            x -= 4;
            if (dx >= 0)
                dx = (int16_t)-dx;
        } else if (x < left) {
            x += 4;
            if (dx < 0)
                dx = (int16_t)-dx;
        } else {
            x = (int16_t)(x + dx);
        }
        pos += (uint32_t)(int32_t)(int16_t)speed;
        // no overtaking: running into the car ahead, take its place behind
        // it and swap speed and manner with it
        uint32_t limit;
        Opponent *ahead;
        if (i != 0) {
            ahead = o - 1;
            limit = ahead->pos - 0x4000;
        } else {
            // the leader against the last one, a lap on (offsets the game
            // patches to the number of opponents)
            ahead = &race.opp[race.opponents - 1];
            limit = ahead->pos + race.opp_length;
        }
        if (limit < pos) {
            pos = limit;
            uint16_t s = ahead->speed;
            ahead->speed = speed;
            speed = s;
            uint16_t t = ahead->target;
            int16_t a = ahead->dx;
            ahead->target = target;
            ahead->dx = dx;
            target = t;
            dx = a;
        }
        o->pos = pos;
        o->x = x;
        o->speed = speed;
        o->target = target;
        o->dx = dx;
    }
}

// ---------------------------------------------------------------- the whole race

// the joysticks, as bits per player (race_joy)
static void input(void) {
    for (uint8_t n = 0; n < 2; n++) {
        Player *p = &race.p[n];
        uint8_t now = race_joy[n];
        p->joy = now;
        p->joy_new = (uint8_t)((p->joy_last ^ now) & now);
        p->joy_last = now;
    }
}

// the computer drives in the demo
static void autopilot(void) {
    int16_t x = hi(race.p[0].x);
    uint8_t j = JOY_FIRE;
    if (x >= 0x20)
        j |= JOY_LEFT;
    if (x < -0x60)
        j |= JOY_RIGHT;
    race.p[0].joy = j;
    x = hi(race.p[1].x);
    j = JOY_FIRE;
    if (x >= 0x60)
        j |= JOY_LEFT;
    if (x < -0x20)
        j |= JOY_RIGHT;
    race.p[1].joy = j;
}

// random counters for the pictures, every 8th frame
static void animate(uint16_t buffer) {
    if (buffer & 7)
        return;
    uint16_t r = race_random();
    if (r >= 0x4000)
        race.p[0].flicker++;
    if (r < 0xC000)
        race.p[1].flicker++;
    if (r >= 0x8000)
        race.p[0].flicker_r = r;
    else
        race.p[1].flicker_r = r;
}

// place of a car at pos (the other player at other)
static uint16_t place_of(uint32_t pos, uint32_t other) {
    uint16_t place = 1;
    if (race.difficulty != 3)
        for (uint8_t i = 0; i < race.opponents; i++)
            if (pos < race.opp_pic[i])
                place++;
    if (race.two_players && pos < other)
        place++;
    return place;
}

static void places(void) {
    Player *a = &race.p[0], *b = &race.p[1];
    if (!a->fuel || !a->stopped)
        a->place = place_of(a->pos, b->pos);
    if (race.two_players && (!b->fuel || !b->stopped))
        b->place = place_of(b->pos, a->pos);
}

// crossing the finish line
static void laps(void) {
    uint16_t done = race.finished;
    for (uint8_t n = 0; n < 2; n++) {
        Player *p = &race.p[n];
        if (!p->stopped && !p->fuel)
            p->stopped = 1;
    }
    for (uint8_t n = 0; n < 2; n++) {
        Player *p = &race.p[n];
        if (n && !race.two_players)
            break;
        if (p->place >= 11 || (int32_t)(race.finish - p->pos) >= 0)
            continue;
        if (p->stopped) {
            if (p->fuel)
                continue;
            p->fuel = 1;
        }
        p->stopped = 1;
        p->cam_pos = (p->pos & 0xFFFF0000ul) | (p->cam_pos & 0xFFFF);
        p->cam_x = hi(p->x);
        race.finish_frames[done++] = race.frames;
    }
    uint16_t i = race.next_finisher;
    while (i != race.opponents && (int32_t)(race.finish - race.opp[i].pos) < 0) {
        race.finish_frames[done++] = race.frames;
        i++;
    }
    race.next_finisher = i;
    race.finished = done;
    if (done >= 10) {
        race.p[0].stopped = 1;
        race.p[1].stopped = 1;
    }
}

static uint8_t race_over(void) {
    const Player *a = &race.p[0], *b = &race.p[1];
    if (!a->stopped)
        return 0;
    if (!a->in_pits_shown && a->speed_view)
        return 0;
    if (race.two_players) {
        if (!b->stopped)
            return 0;
        if (!b->in_pits_shown && b->speed_view)
            return 0;
    }
    return 1;
}

// before the start the camera flies in
static void fly_in(void) {
    int16_t d = (int16_t)(-race.clock - 100);
    if (d < 0)
        return;
    uint32_t step = (uint32_t)((int32_t)d * 16);
    race.p[0].cam_pos += step;
    race.p[1].cam_pos += step;
}

// race_init's way to the course's colours: seg_lookup for player n at
// race_lookup_pos
void race_seg_lookup(uint8_t n) {
    seg_lookup(&race.p[n], race_lookup_pos);
}

void race_frame(void) {
    if (race.clock < 0) {
        fly_in();
        seg_here(&race.p[0]);
        seg_here(&race.p[1]);
    } else {
        if (race.over && race.over_timer != 150)
            race.over_timer++;
        if (!race.paused) {
            animate(race.buffer);
            if (race.difficulty != 3)
                opponents();
            input();
            if (race.demo)
                autopilot();
            race.control = 0;
            player_frame(0);
            race.control = race.control2;
            if (race.two_players)
                player_frame(1);
            race.frames++;
            for (uint8_t n = 0; n < 2; n++) {
                Player *p = &race.p[n];
                if ((int16_t)p->timer > 0)
                    p->timer--;
            }
            places();
            laps();
            if (race_over())
                race.over = 1;
        }
    }
    if (++race.clock == 0x200)
        race.clock = 0x100;
}

// At the start of a picture
void race_picture(void) {
    if (++race.buffer == 3)
        race.buffer = 0;
    for (uint8_t n = 0; n < 2; n++) {
        Player *p = &race.p[n];
        p->pos_pic = p->pos;
        p->x_pic = p->x;
        p->pos_pic2 = p->pos;
        p->x_pic2 = p->x;
        p->in_pits_pic = p->in_pits;
        if (race.clock < 0 || (p->stopped && p->fuel && p->place < 11)) {
            p->pos_pic = p->cam_pos;
            p->x_pic = (int32_t)((uint32_t)(uint16_t)p->cam_x << 16 | (uint16_t)p->x_pic);
        }
        p->speed_view = p->speed;
        p->steer_view = p->steer;
        p->curve_view = p->curve;
        p->u16_view = p->u16;
        p->slope_view = p->slope;
    }
    for (uint8_t i = 0; i < OPPONENTS; i++) {
        race.opp_pic[i] = race.opp[i].pos;
        race.opp_pic_x[i] = race.opp[i].x;
    }
    for (uint8_t n = 0; n < 2; n++) {
        Player *p = &race.p[n];
        p->pos_shown = p->pos_pic2;
        p->x_shown = p->x_pic2;
        p->pos_view = p->pos_pic;
        p->x_view = p->x_pic;
        p->in_pits_shown = p->in_pits_pic;
    }
}
