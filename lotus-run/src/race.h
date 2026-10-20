// Lotus Run: the race, 50 times a second: the players' cars, the
// opponents, laps and positions.
//
// A Player is $B6 bytes, every field at a fixed offset (checked below), so
// the assembly (race.s) can use them as they are. Fields whose use is not
// known yet are named after their offset.

#ifndef RACE_H
#define RACE_H

#include <stddef.h>
#include <stdint.h>

#include "track.h"

// packed: the host's compiler would align the long words otherwise
typedef struct __attribute__((packed)) {
    int32_t x;            // +00 sideways position, 16.16; the road is about -$100..$100
    uint32_t pos;         // +04 position on the course (high word: segment)
    uint8_t u08[8];       // +08
    uint16_t speed;       // +10
    int16_t steer;        // +12 steering, -32..32
    int16_t curve;        // +14 the course's curve here (drifts the car outwards)
    int16_t u16;          // +16
    uint16_t in_pits;     // +18
    int16_t slope;        // +1A the course's slope here
    int32_t x_pic;        // +1C x when the picture being drawn was started
    uint32_t pos_pic;     // +20 pos, the same
    int32_t x_pic2;       // +24
    uint32_t pos_pic2;    // +28
    uint8_t u2c[8];       // +2C
    uint16_t in_pits_pic; // +34
    uint8_t u36[2];       // +36
    uint32_t pos_shown;   // +38 pos of the picture on screen
    int32_t x_shown;      // +3C
    uint16_t in_pits_shown; // +40
    uint16_t stopped;     // +42 the race is over for this car
    uint32_t cam_pos;     // +44 where the camera is when not at the car:
                          // flying in before the start, after the finish
    int16_t cam_x;        // +48
    uint8_t u4a[2];       // +4A
    int32_t x_view;       // +4C x of the last picture
    uint32_t pos_view;    // +50 pos of the last picture
    uint8_t u54[2];       // +54
    int16_t slope_view;   // +56 slope of the last picture
    int16_t u16_view;     // +58
    uint8_t u5a[14];      // +5A
    uint16_t speed_view;  // +68 speed of the last picture
    int16_t steer_view;   // +6A
    int16_t curve_view;   // +6C
    uint16_t automatic;   // +6E automatic gears
    uint8_t u70[2];       // +70
    int16_t push_x;       // +72 sideways push after a crash
    int16_t push_steer;   // +74
    uint8_t u76[4];       // +76
    uint32_t fuel;        // +7A
    uint16_t place;       // +7E position in the race (1 = leading)
    uint8_t u80[2];       // +80
    uint16_t colours[4];  // +82 scenery colours ahead
    uint16_t accelerating;// +8A
    uint16_t gear;        // +8C 0-4
    uint8_t u8e[2];       // +8E
    uint16_t rpm;         // +90
    int16_t pit_request;  // +92 -1: none
    uint16_t pit_lane;    // +94 on a pit lane segment
    uint16_t u96;         // +96 (3 at the start)
    uint16_t flicker;     // +98 counted up at random (every 8th picture), for the pictures
    uint16_t flicker_r;   // +9A a random number, the same
    uint8_t u9c[8];       // +9C
    uint8_t joy_last;     // +A4 joystick bits of the last frame
    uint8_t ua5;          // +A5
    uint8_t joy_new;      // +A6 bits that came on this frame
    uint8_t ua7;          // +A7
    uint8_t joy;          // +A8 JOY_* bits now
    uint8_t ua9[7];       // +A9
    uint16_t fire_accel;  // +B0 accelerate with fire (else with forward)
    uint16_t timer;       // +B2 counted down every frame
    uint16_t pit_timer;   // +B4
} Player;

#define JOY_LEFT  0x01
#define JOY_RIGHT 0x02
#define JOY_DOWN  0x04
#define JOY_UP    0x08
#define JOY_FIRE  0x10

// An opponent (the table is sorted by position)
typedef struct __attribute__((packed)) {
    uint32_t pos;    // +0
    int16_t x;       // +4
    uint16_t speed;  // +6
    uint16_t target; // +8 speed it drives towards
    int16_t dx;      // +A sideways movement
} Opponent;

#define OPPONENTS 19

// What the race keeps besides (packed and without pointers: the same
// layout on the host and the MEGA65, tools/offsets.c gives it to race.s)
typedef struct __attribute__((packed)) {
    Player p[2];
    Opponent opp[OPPONENTS];
    uint16_t segments;
    uint16_t opponents;    // how many drive
    uint32_t opp_length;   // the course's length for the opponents' ring
    uint32_t seg_bias;     // a multiple of the segments, keeps a division positive
    uint32_t finish;       // position of the finish line
    uint16_t opp_bonus;    // added to the opponents' target speeds
    int16_t clock;         // frames since the start (negative: countdown)
    uint16_t two_players;
    uint16_t difficulty;
    uint16_t control2;     // player 2 on the keyboard (1)
    uint16_t demo;         // the computer drives
    uint16_t frames;       // counted up every frame of the race
    uint16_t finished;     // cars over the line
    uint16_t next_finisher;// opponent index to check next
    uint16_t finish_frames[24]; // frame of each car over the line
    uint16_t over;         // the race is over
    uint16_t over_timer;   // counts to 150 after that
    uint16_t paused;
    uint32_t random[4];
    uint16_t sound_p1, sound_p2; // crash noise levels
    uint16_t scrape;       // noise of this frame
    uint16_t hit;          // the last collision check hit something
    uint16_t crash[2];     // crash of this frame per player (1, 2), for the sounds
    uint16_t control;      // control of the player being moved
    uint16_t buffer;       // which of three pictures is drawn (0-2)
    uint16_t course;       // number of the course (0-31: file and tables)
    uint16_t race_no;      // race of the season (0: the first)
    uint16_t laps;
    uint32_t opp_pic[OPPONENTS]; // the opponents' positions when the picture was started
    int16_t opp_pic_x[OPPONENTS];
} Race;

extern Race race;
// The course of the race
extern const Track *race_track;

// What the game works out from a course before the race
void race_track_setup(Track *t);

// A race on the course race_track (race.course, race_no, difficulty,
// two_players, demo set): the grid, the opponents, the cars
void race_init(void);

// One frame (1/50 s) of the race
void race_frame(void);
// At the start of every picture: what the race keeps of it (some of the
// physics uses these values)
void race_picture(void);
uint16_t race_random(void);

// The joystick bits (JOY_*) per player for the next race_frame
extern uint8_t race_joy[2];

// For race_init: the course at race_lookup_pos for player n (curve, slope,
// the scenery's colours)
extern uint32_t race_lookup_pos;
void race_seg_lookup(uint8_t n);

#define CHECK(f, o) _Static_assert(offsetof(Player, f) == (o), "Player." #f " is not at +" #o)
CHECK(speed, 0x10);
CHECK(slope, 0x1A);
CHECK(x_pic, 0x1C);
CHECK(in_pits_pic, 0x34);
CHECK(pos_shown, 0x38);
CHECK(stopped, 0x42);
CHECK(cam_x, 0x48);
CHECK(x_view, 0x4C);
CHECK(slope_view, 0x56);
CHECK(speed_view, 0x68);
CHECK(push_x, 0x72);
CHECK(fuel, 0x7A);
CHECK(colours, 0x82);
CHECK(rpm, 0x90);
CHECK(joy_last, 0xA4);
CHECK(joy, 0xA8);
CHECK(fire_accel, 0xB0);
CHECK(pit_timer, 0xB4);
_Static_assert(sizeof(Player) == 0xB6, "a Player is $B6 bytes");
#undef CHECK

#endif
