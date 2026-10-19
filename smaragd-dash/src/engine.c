// Smaragd Dash: the cave engine (see engine.h).

#include "engine.h"

#include <string.h>

uint8_t cave[CAVE_SIZE];
struct game game;
uint8_t moved[CAVE_SIZE];

// Cell offsets for DIR_UP, DIR_RIGHT, DIR_DOWN, DIR_LEFT
static const int8_t dir_off[4] = {-CAVE_W, 1, CAVE_W, -1};

// Element properties
#define P_ROUND 1  // boulders and diamonds roll off it
#define P_HARD  2  // survives explosions
#define P_CRUSH 4  // explodes when something falls on it

static const uint8_t props[E_COUNT] = {
    [E_BRICK] = P_ROUND,
    [E_STEEL] = P_HARD,
    [E_BOULDER] = P_ROUND,
    [E_BOULDER_F] = P_ROUND,
    [E_DIAMOND] = P_ROUND,
    [E_DIAMOND_F] = P_ROUND,
    [E_ROCKFORD] = P_CRUSH,
    [E_INBOX] = P_HARD,
    [E_OUTBOX] = P_HARD,
    [E_OUTBOX_OPEN] = P_HARD,
    [E_FIREFLY + 0] = P_CRUSH,
    [E_FIREFLY + 1] = P_CRUSH,
    [E_FIREFLY + 2] = P_CRUSH,
    [E_FIREFLY + 3] = P_CRUSH,
    [E_BUTTERFLY + 0] = P_CRUSH,
    [E_BUTTERFLY + 1] = P_CRUSH,
    [E_BUTTERFLY + 2] = P_CRUSH,
    [E_BUTTERFLY + 3] = P_CRUSH,
};

// Ticks from the start until Rockford hatches (the inbox flashes meanwhile)
#define HATCH_TICKS 20

#define AMOEBA_MAX 200

// xorshift16
static uint8_t xorshift(uint16_t *r) {
    *r ^= *r << 7;
    *r ^= *r >> 9;
    *r ^= *r << 8;
    return (uint8_t)*r;
}

// For everything outside the cave: animations, sounds
static uint16_t rng = 0xACE1;

uint8_t rnd(void) {
    return xorshift(&rng);
}

// The cave's own random numbers start the same in every run of a cave, so a
// cave plays the same with the same moves (the screencast depends on it).
#define CAVE_SEED 0x2F6B
static uint16_t cave_rng;

static uint8_t cave_rnd(void) {
    return xorshift(&cave_rng);
}

void cave_start(const CaveDef *def) {
    memset(&game, 0, sizeof game);
    game.def = def;
    memcpy(cave, def->map, CAVE_SIZE);
    memset(moved, DIR_NONE, CAVE_SIZE);
    for (uint16_t i = 0; i < CAVE_SIZE; i++)
        if (cave[i] == E_INBOX)
            game.player = i;
    game.state = PS_HATCHING;
    game.facing = DIR_RIGHT;
    game.hatch_ticks = HATCH_TICKS;
    game.time = def->time;
    game.magic_timer = def->magic_time;
    game.amoeba_timer = def->amoeba_time;
    cave_rng = CAVE_SEED;
}

void cave_second(void) {
    if (game.state != PS_ALIVE)
        return;
    if (game.time && --game.time == 0)
        game.state = PS_TIMEOUT;
    if (game.magic_state == MW_ACTIVE && game.magic_timer && --game.magic_timer == 0)
        game.magic_state = MW_EXPIRED;
    if (game.amoeba_timer)
        game.amoeba_timer--;
}

// Blow up the 3x3 cells around c; they turn into `kind` (E_EXPLODE or
// E_EXPLODE_D). Steel and the in/outbox survive.
static void explode(uint16_t c, uint8_t kind) {
    uint16_t j = c - CAVE_W - 1;
    for (uint8_t y = 0; y < 3; y++, j += CAVE_W - 3)
        for (uint8_t x = 0; x < 3; x++, j++) {
            uint8_t e = cave[j] & ~SCANNED;
            if (props[e] & P_HARD)
                continue;
            if (e == E_ROCKFORD)
                game.state = PS_DEAD;
            cave[j] = kind | SCANNED;
            moved[j] = DIR_NONE;
        }
    game.sound |= SND_EXPLODE;
}

void cave_suicide(void) {
    if (game.state == PS_ALIVE)
        explode(game.player, E_EXPLODE);
}

static void collect(void) {
    const CaveDef *d = game.def;
    game.score += game.exit_open ? d->extra_value : d->diamond_value;
    if (game.collected < 255)
        game.collected++;
    if (!game.exit_open && game.collected >= d->diamonds_needed) {
        game.exit_open = true;
        game.flash = true;
    }
    game.sound |= SND_COLLECT;
}

// Boulder or diamond at i (falling or not) on a round thing: roll off to the
// left or right if both the side and the cell below it are free.
static bool roll(uint16_t i, uint8_t falling) {
    if (cave[i - 1] == E_SPACE && cave[i + CAVE_W - 1] == E_SPACE) {
        cave[i - 1] = falling | SCANNED;
        cave[i] = E_SPACE;
        moved[i - 1] = DIR_LEFT;
        return true;
    }
    if (cave[i + 1] == E_SPACE && cave[i + CAVE_W + 1] == E_SPACE) {
        cave[i + 1] = falling | SCANNED;
        cave[i] = E_SPACE;
        moved[i + 1] = DIR_RIGHT;
        return true;
    }
    return false;
}

static void move_rockford(uint16_t i, uint8_t input) {
    uint8_t dir = input & 7;
    game.moving = false;
    game.snapping = false;
    if (dir == DIR_NONE)
        return;
    if (dir == DIR_LEFT || dir == DIR_RIGHT)
        game.facing = dir;
    game.moving = true;
    uint16_t j = i + dir_off[dir];
    uint8_t t = cave[j];

    if (input & IN_FIRE) {  // snap: take what is next to Rockford without moving
        game.snapping = true;
        if (t == E_DIRT) {
            cave[j] = E_SPACE;
            game.sound |= SND_DIRT;
        } else if (t == E_DIAMOND) {
            cave[j] = E_SPACE;
            collect();
        }
        return;
    }
    switch (t) {
    case E_SPACE:
        game.sound |= SND_STEP;
        break;
    case E_DIRT:
        game.sound |= SND_DIRT;
        break;
    case E_DIAMOND:
        collect();
        break;
    case E_OUTBOX_OPEN:
        cave[i] = E_SPACE;
        game.state = PS_EXITED;
        game.player = j;
        return;
    case E_BOULDER:
        // Pushing sideways works only now and then, as in the original
        if (dir == DIR_LEFT || dir == DIR_RIGHT) {
            uint16_t k = j + dir_off[dir];
            if (cave[k] == E_SPACE && (cave_rnd() & 3) == 0) {
                cave[k] = E_BOULDER | SCANNED;
                moved[k] = dir;
                game.sound |= SND_BOULDER;
                break;
            }
        }
        return;
    default:
        return;
    }
    cave[j] = E_ROCKFORD | SCANNED;
    cave[i] = E_SPACE;
    moved[j] = dir;
    game.player = j;
}

void cave_tick(uint8_t input) {
    uint16_t amoeba_count = 0;
    bool amoeba_room = false;
    uint8_t amoeba_odds = game.amoeba_timer ? 8 : 64;  // of 256

    game.sound = 0;
    memset(moved, DIR_NONE, CAVE_SIZE);
    if (game.hatch_ticks)
        game.hatch_ticks--;

    // The outer frame is always steel and needs no work.
    for (uint16_t i = CAVE_W; i < CAVE_SIZE - CAVE_W; i++) {
        uint8_t e = cave[i];
        if (e & SCANNED)
            continue;
        switch (e) {
        case E_BOULDER:
        case E_DIAMOND: {
            uint8_t below = cave[i + CAVE_W];
            uint8_t falling = e + 1;
            if (below == E_SPACE) {
                cave[i + CAVE_W] = falling | SCANNED;
                cave[i] = E_SPACE;
                moved[i + CAVE_W] = DIR_DOWN;
            } else if (props[below & ~SCANNED] & P_ROUND) {
                roll(i, falling);
            }
            break;
        }
        case E_BOULDER_F:
        case E_DIAMOND_F: {
            uint8_t below = cave[i + CAVE_W] & ~SCANNED;
            uint8_t still = e - 1;
            if (below == E_SPACE) {
                cave[i + CAVE_W] = e | SCANNED;
                cave[i] = E_SPACE;
                moved[i + CAVE_W] = DIR_DOWN;
            } else if (props[below] & P_CRUSH) {
                uint8_t bfly = below >= E_BUTTERFLY && below < E_BUTTERFLY + 4;
                explode(i + CAVE_W, bfly ? E_EXPLODE_D : E_EXPLODE);
            } else if (below == E_MAGIC && game.magic_state != MW_EXPIRED) {
                // Through the magic wall: boulders come out as diamonds and
                // the other way round, if there is room below the wall.
                game.magic_state = MW_ACTIVE;
                cave[i] = E_SPACE;
                if (cave[i + 2 * CAVE_W] == E_SPACE)
                    cave[i + 2 * CAVE_W] = (e == E_BOULDER_F ? E_DIAMOND_F : E_BOULDER_F) | SCANNED;
                game.sound |= e == E_BOULDER_F ? SND_BOULDER : SND_DIAMOND;
            } else if (!((props[below] & P_ROUND) && roll(i, e))) {
                cave[i] = still;
                game.sound |= e == E_BOULDER_F ? SND_BOULDER : SND_DIAMOND;
            }
            break;
        }
        case E_ROCKFORD:
            if (game.state == PS_ALIVE) {
                game.player = i;
                move_rockford(i, input);
            }
            break;
        case E_INBOX:
            if (!game.hatch_ticks)
                cave[i] = E_BIRTH;
            break;
        case E_BIRTH:
        case E_BIRTH + 1:
            cave[i] = e + 1;
            break;
        case E_BIRTH + 2:
            cave[i] = E_ROCKFORD;
            game.player = i;
            game.state = PS_ALIVE;
            break;
        case E_OUTBOX:
            if (game.exit_open)
                cave[i] = E_OUTBOX_OPEN;
            break;
        case E_AMOEBA:
            if (game.amoeba_state == AM_TOO_BIG) {
                cave[i] = E_BOULDER;
                break;
            }
            if (game.amoeba_state == AM_ENCLOSED) {
                cave[i] = E_DIAMOND;
                break;
            }
            amoeba_count++;
            for (uint8_t d = 0; d < 4 && !amoeba_room; d++) {
                uint8_t n = cave[i + dir_off[d]];
                amoeba_room = n == E_SPACE || n == E_DIRT;
            }
            if (cave_rnd() < amoeba_odds) {
                uint16_t j = i + dir_off[cave_rnd() & 3];
                if (cave[j] == E_SPACE || cave[j] == E_DIRT)
                    cave[j] = E_AMOEBA | SCANNED;
            }
            break;
        case E_EXPLODE + 4:
            cave[i] = E_SPACE;
            break;
        case E_EXPLODE_D + 4:
            cave[i] = E_DIAMOND;
            break;
        default:
            if (e >= E_EXPLODE && e < E_EXPLODE_D + 4) {
                cave[i] = e + 1;
            } else if (e >= E_FIREFLY && e < E_BUTTERFLY + 4) {
                bool fly = e < E_BUTTERFLY;
                uint8_t base = fly ? E_FIREFLY : E_BUTTERFLY;
                uint8_t dir = e - base;
                // Touching Rockford or the amoeba blows a creature up
                uint8_t d;
                for (d = 0; d < 4; d++) {
                    uint8_t n = cave[i + dir_off[d]] & ~SCANNED;
                    if (n == E_ROCKFORD || n == E_AMOEBA)
                        break;
                }
                if (d < 4) {
                    explode(i, fly ? E_EXPLODE : E_EXPLODE_D);
                    break;
                }
                // Fireflies try to turn left first, butterflies right; then
                // straight on; otherwise they turn the other way on the spot.
                uint8_t turn = fly ? (dir + 3) & 3 : (dir + 1) & 3;
                uint16_t j = i + dir_off[turn];
                if (cave[j] == E_SPACE) {
                    cave[j] = (base + turn) | SCANNED;
                    cave[i] = E_SPACE;
                    moved[j] = turn;
                } else if (cave[j = i + dir_off[dir]] == E_SPACE) {
                    cave[j] = e | SCANNED;
                    cave[i] = E_SPACE;
                    moved[j] = dir;
                } else {
                    cave[i] = base + (fly ? (dir + 1) & 3 : (dir + 3) & 3);
                }
            }
            break;
        }
    }

    for (uint16_t i = 0; i < CAVE_SIZE; i++)
        cave[i] &= ~SCANNED;

    if (amoeba_count) {
        if (amoeba_count >= AMOEBA_MAX)
            game.amoeba_state = AM_TOO_BIG;
        else if (!amoeba_room)
            game.amoeba_state = AM_ENCLOSED;
        game.sound |= SND_AMOEBA;
    }
    if (game.magic_state == MW_ACTIVE)
        game.sound |= SND_MAGIC;
}
