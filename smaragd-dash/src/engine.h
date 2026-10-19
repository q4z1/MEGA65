// Smaragd Dash: the cave engine. Plain C without any hardware access, so it
// can be tested on the host as well (tests/).
//
// The rules follow the original Boulder Dash 1 engine: the cave is scanned
// once per tick from top left to bottom right, every cell is handled at most
// once per tick (SCANNED marks cells already moved into), boulders and
// diamonds fall and roll off round things, fireflies turn left, butterflies
// turn right, explosions are 3x3 and take five ticks.

#ifndef ENGINE_H
#define ENGINE_H

#include <stdbool.h>
#include <stdint.h>

#define CAVE_W    40
#define CAVE_H    22
#define CAVE_SIZE (CAVE_W * CAVE_H)

// Cell contents. Creatures carry their direction in the low two bits.
enum {
    E_SPACE,
    E_DIRT,
    E_BRICK,
    E_STEEL,
    E_BOULDER,
    E_BOULDER_F,                  // falling
    E_DIAMOND,
    E_DIAMOND_F,                  // falling
    E_ROCKFORD,
    E_INBOX,
    E_OUTBOX,                     // closed: looks like steel
    E_OUTBOX_OPEN,
    E_MAGIC,
    E_AMOEBA,
    E_FIREFLY,                    // +DIR_UP .. +DIR_LEFT
    E_BUTTERFLY = E_FIREFLY + 4,  // +DIR_UP .. +DIR_LEFT
    E_EXPLODE = E_BUTTERFLY + 4,  // 5 stages, then space
    E_EXPLODE_D = E_EXPLODE + 5,  // 5 stages, then a diamond
    E_BIRTH = E_EXPLODE_D + 5,    // 3 stages, then Rockford
    E_COUNT = E_BIRTH + 3
};

#define SCANNED 0x80  // cell was already handled in this tick

enum { DIR_UP, DIR_RIGHT, DIR_DOWN, DIR_LEFT, DIR_NONE };
#define IN_FIRE 0x08  // input for cave_tick: direction | IN_FIRE

// Player state
enum { PS_HATCHING, PS_ALIVE, PS_DEAD, PS_TIMEOUT, PS_EXITED };

// Magic wall and amoeba state
enum { MW_DORMANT, MW_ACTIVE, MW_EXPIRED };
enum { AM_GROWING, AM_ENCLOSED, AM_TOO_BIG };

// Sound events of the last tick (game.sound)
#define SND_BOULDER   0x01
#define SND_DIAMOND   0x02  // a diamond landed
#define SND_COLLECT   0x04
#define SND_DIRT      0x08  // stepped into or snapped dirt
#define SND_STEP      0x10  // stepped into empty space
#define SND_EXPLODE   0x20
#define SND_MAGIC     0x40  // magic wall is active
#define SND_AMOEBA    0x80  // amoeba is alive

typedef struct {
    const char *name;
    const uint8_t *map;       // CAVE_SIZE cells, E_* codes
    uint16_t time;            // seconds
    uint8_t diamonds_needed;
    uint8_t diamond_value;    // points per diamond until the exit opens
    uint8_t extra_value;      // points per diamond after that
    uint8_t amoeba_time;      // seconds of slow amoeba growth
    uint8_t magic_time;       // seconds the magic wall stays active
    uint8_t tick_ms;          // length of one cave tick
} CaveDef;

struct game {
    const CaveDef *def;
    uint8_t state;            // PS_*
    uint16_t player;          // cell index of Rockford (or of the inbox)
    uint8_t facing;           // direction of the last move or try (DIR_*)
    bool moving;              // Rockford moved or tried to in the last tick
    bool snapping;
    uint8_t hatch_ticks;      // ticks until Rockford appears
    uint16_t time;            // seconds left
    uint8_t collected;
    bool exit_open;
    bool flash;               // exit just opened: flash the screen
    uint32_t score;
    uint8_t magic_state, magic_timer;
    uint8_t amoeba_state, amoeba_timer;
    uint8_t sound;            // SND_* of the last tick
};

extern uint8_t cave[CAVE_SIZE];
extern struct game game;

// The moves of the last tick, for drawing them smoothly: per cell the
// direction its content moved in to get there, DIR_NONE if it did not move.
// The rules do not use it.
extern uint8_t moved[CAVE_SIZE];

// What else happened in the last tick, for the drawing's little effects
// (the rules do not use it either): a creature left a cell, a boulder
// landed, dirt was dug (the cell Rockford snapped, or the one he left).
enum { EV_FIREFLY, EV_BUTTERFLY, EV_LANDED, EV_DUG };
#define MAX_EVENTS 32  // more are left out
typedef struct {
    uint16_t cell;
    uint8_t what;  // EV_*
} Event;
extern Event events[MAX_EVENTS];
extern uint8_t nevents;

void cave_start(const CaveDef *def);
void cave_tick(uint8_t input);
void cave_second(void);  // call once per second while the player is alive
void cave_suicide(void); // Rockford gives up (Run/Stop)
uint8_t rnd(void);       // random numbers outside the cave (animations, sounds)

#endif
