// Smaragd Dash: what the game knows of a cave while it plays: the map and
// moves GDash's engine (gdengine.h) leaves, the player's state, and the
// codes and events both use. GDash's engine plays every cave; struct game
// is what main.c takes from it for the status line, the sounds and the
// drawing.
//
// The E_* codes are those of the game's first engine, which GDash's
// replaced: main.c still keeps its animated tiles by them (etile[]), and
// tools/cavekit.py's .cave files name the elements of the game's caves by
// the same map characters.

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

enum { DIR_UP, DIR_RIGHT, DIR_DOWN, DIR_LEFT, DIR_NONE };
#define IN_FIRE 0x08  // input of a step: direction | IN_FIRE

// Player state
enum { PS_HATCHING, PS_ALIVE, PS_DEAD, PS_TIMEOUT, PS_EXITED };

// Magic wall state (GDash's GD_MW_*)
enum { MW_DORMANT, MW_ACTIVE, MW_EXPIRED };

// Sound events of the last step (game.sound, gd.sound)
#define SND_BOULDER   0x01
#define SND_DIAMOND   0x02  // a diamond landed
#define SND_COLLECT   0x04
#define SND_DIRT      0x08  // stepped into or snapped dirt
#define SND_STEP      0x10  // stepped into empty space
#define SND_EXPLODE   0x20
#define SND_MAGIC     0x40  // magic wall is active
#define SND_AMOEBA    0x80  // amoeba is alive
#define SND_CLOCK     0x100  // a clock taken
#define SND_NUT       0x200  // a nut cracked
#define SND_SLIME     0x400  // something went through slime
#define SND_GROW      0x800  // an expanding wall grew

// What the status line shows of the cave
typedef struct {
    const char *name;
    uint8_t diamonds_needed;
    uint8_t diamond_value;    // points per diamond until the exit opens
    uint8_t extra_value;      // points per diamond after that
} CaveDef;

struct game {
    const CaveDef *def;
    uint8_t state;            // PS_*
    uint16_t player;          // cell index of Rockford (or of the inbox)
    uint8_t facing;           // direction of the last move or try (DIR_*)
    bool moving;              // Rockford moved or tried to in the last step
    bool snapping;
    uint16_t time;            // seconds left
    uint8_t collected;
    bool exit_open;
    bool flash;               // exit just opened: flash the screen
    uint32_t score;
    uint8_t magic_state;      // MW_*
    uint16_t sound;           // SND_* of the last step
};

// GDash's engine's map (its O_* codes) and moves: on the MEGA65 they lie
// where both see them (shared.ld, mem.h)
extern uint8_t cave[CAVE_SIZE];
extern struct game game;

// The moves of the last step, for drawing them smoothly: per cell the
// direction its content moved in to get there, DIR_NONE if it did not move.
// The rules do not use it.
extern uint8_t moved[CAVE_SIZE];

// What else happened in the last step, for the drawing's little effects
// (gd.events; the rules do not use them): a creature left a cell, a
// boulder landed, dirt was dug (the cell Rockford snapped, or the one he
// left).
enum {
    EV_FIREFLY, EV_BUTTERFLY, EV_LANDED, EV_DUG,
    EV_ALT_FIREFLY, EV_ALT_BUTTERFLY, EV_STONEFLY, EV_DRAGONFLY, EV_GHOST, EV_COW,
    EV_BITER, EV_BLADDER, EV_CHASING_STONE, EV_FALLING, EV_FALLING_DIAMOND, EV_ROCKET
};
#define MAX_EVENTS 32  // more are left out
typedef struct {
    uint16_t cell;
    uint8_t what;  // EV_*
} Event;

uint8_t rnd(void);  // random numbers outside the cave: animations, sounds (main.c)

#endif
