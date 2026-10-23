// Smaragd Dash: GDash's engine (see gdengine.h).
//
// Ported from GDash's caverenderedengine.cpp (MIT license, Copyright (c)
// 2007-2018 GDash Project): the same steps in the same order, so the random
// numbers are drawn the same and a cave plays as there (tests/gdplay.c
// compares the two). What only shows - sounds as GDash plays them, its
// particles - is left out; the game takes its own sounds from what happens.
//
// GDash marks what moved down or right in a step as "scanned" - an element
// of its own, a twin, which GDash compares as another element and which has
// no properties but P_SCANNED (but for three expanding steel walls and the
// player). Here the cell keeps its element and a bit in gd_scanned[] says it
// is the twin: get() gives it as code | SCAN, so it compares unequal as in
// GDash, and flags() gives the twin's flags.

#include "gdengine.h"

#include <stddef.h>
#include <string.h>

// On the MEGA65 where the program sees them as well (shared.ld)
#ifndef __mos__
GdState gd;
uint8_t cave[CAVE_SIZE];
uint8_t moved[CAVE_SIZE];
#endif

#define SCAN 0x100  // get(): the scanned twin of the element

const int8_t gd_dx[] = {0, 0, 1, 1, 1, 0, -1, -1, -1, 0, 2, 2, 2, 0, -2, -2, -2};  // also src/gdcell.s
const int8_t gd_dy[] = {0, -1, -1, 0, 1, 1, 1, 0, -1, -2, -2, 0, 2, 2, 2, 0, -2};
static const uint8_t ccw_eighth[] = {MV_STILL, MV_UP_LEFT, MV_UP, MV_UP_RIGHT, MV_RIGHT, MV_DOWN_RIGHT,
                                     MV_DOWN, MV_DOWN_LEFT};
static const uint8_t ccw_fourth[] = {MV_STILL, MV_LEFT, MV_UP_LEFT, MV_UP, MV_UP_RIGHT, MV_RIGHT,
                                     MV_DOWN_RIGHT, MV_DOWN, MV_DOWN_LEFT, MV_LEFT};
static const uint8_t cw_eighth[] = {MV_STILL, MV_UP_RIGHT, MV_RIGHT, MV_DOWN_RIGHT, MV_DOWN, MV_DOWN_LEFT,
                                    MV_LEFT, MV_UP_LEFT, MV_UP};
static const uint8_t cw_fourth[] = {MV_STILL, MV_RIGHT, MV_DOWN_RIGHT, MV_DOWN, MV_DOWN_LEFT, MV_LEFT,
                                    MV_UP_LEFT, MV_UP, MV_UP_RIGHT};
static const uint8_t opposite[] = {MV_STILL, MV_DOWN, MV_DOWN_LEFT, MV_LEFT, MV_UP_LEFT, MV_UP,
                                   MV_UP_RIGHT, MV_RIGHT, MV_DOWN_RIGHT};
static const uint8_t twice[] = {MV_STILL, MV_UP_2, MV_UP_RIGHT_2, MV_RIGHT_2, MV_DOWN_RIGHT_2, MV_DOWN_2,
                                MV_DOWN_LEFT_2, MV_LEFT_2, MV_UP_LEFT_2};
// a creature's four directions (o_..._1 to _4), and backwards
static const uint8_t creature_dir[] = {MV_LEFT, MV_UP, MV_RIGHT, MV_DOWN};
static const uint8_t creature_chdir[] = {MV_RIGHT, MV_DOWN, MV_LEFT, MV_UP};

// ---------------------------------------------------------------- random numbers

#ifdef GD_EXACT
// GLib's g_rand: the Mersenne Twister, seeded with g_rand_set_seed
static uint32_t mt[624];
static uint16_t mti;

static void rand_seed(uint32_t seed) {
    mt[0] = seed;
    for (mti = 1; mti < 624; mti++)
        mt[mti] = 1812433253u * (mt[mti - 1] ^ (mt[mti - 1] >> 30)) + mti;
}

static uint32_t rand_int(void) {
    uint32_t y;
    if (mti >= 624) {
        for (uint16_t k = 0; k < 624; k++) {
            y = (mt[k] & 0x80000000u) | (mt[(k + 1) % 624] & 0x7FFFFFFFu);
            mt[k] = mt[(k + 397) % 624] ^ (y >> 1) ^ ((y & 1) ? 0x9908B0DFu : 0);
        }
        mti = 0;
    }
    y = mt[mti++];
    y ^= y >> 11;
    y ^= (y << 7) & 0x9D2C5680u;
    y ^= (y << 15) & 0xEFC60000u;
    y ^= y >> 18;
    return y;
}

// g_rand_int_range(0, n)
static uint32_t rand_below(uint32_t n) {
    uint32_t leftover = (0x80000000u % n) * 2;
    if (leftover >= n)
        leftover -= n;
    uint32_t top = 0xFFFFFFFFu - leftover, r;
    do
        r = rand_int();
    while (r > top);
    return r % n;
}
#else
// xorshift32: for the game, as GDash's are new in every game anyway
static uint32_t rng;

static void rand_seed(uint32_t seed) {
    rng = seed ? seed : 0x2F6B57A1u;
}

static uint32_t rand_int(void) {
    rng ^= rng << 13;
    rng ^= rng >> 17;
    rng ^= rng << 5;
    return rng;
}

// 0 to n - 1: the engine asks for 4 and 16, powers of two (a division of
// 32 bits takes thousands of cycles on the 6502)
#define rand_below(n) (rand_int() & ((n) - 1))
#endif

// g_rand_boolean
static bool rand_bool(void) {
    return (rand_int() & (1u << 15)) != 0;
}

// Probabilities are of a million: rand_int_range(0, 1000000) < p; for the
// game 0-999999 as the high half of the random number times a million (no
// division), on the MEGA65 by its multiplier (MULTINA, MULTINB, MULTOUT)
static bool chance(uint32_t p) {
#ifdef GD_EXACT
    return rand_below(1000000) < p;
#elif defined(GD_FAR)
    volatile uint8_t *const m = (volatile uint8_t *)0xD770;
    uint32_t r = rand_int();
    m[0] = (uint8_t)r;
    m[1] = (uint8_t)(r >> 8);
    m[2] = (uint8_t)(r >> 16);
    m[3] = (uint8_t)(r >> 24);
    m[4] = 0x40;  // 1000000 = $0F4240
    m[5] = 0x42;
    m[6] = 0x0F;
    m[7] = 0;
    r = m[12] | (uint16_t)m[13] << 8 | (uint32_t)m[14] << 16 | (uint32_t)m[15] << 24;
    return r < p;
#else
    return (uint32_t)((uint64_t)rand_int() * 1000000u >> 32) < p;
#endif
}

// The C64's random numbers, for the predictable slime
static uint8_t c64_seed_1, c64_seed_2;

static uint8_t c64_random(void) {
    uint8_t t1 = (c64_seed_1 & 1) << 7;
    uint8_t t2 = (c64_seed_2 >> 1) & 0x7F;
    uint16_t r = c64_seed_2 + ((c64_seed_2 & 1) << 7);
    uint8_t carry = r >> 8;
    r = (r & 0xFF) + carry + 0x13;
    carry = r >> 8;
    c64_seed_2 = r & 0xFF;
    r = c64_seed_1 + carry + t1;
    carry = r >> 8;
    r = (r & 0xFF) + carry + t2;
    c64_seed_1 = r & 0xFF;
    return c64_seed_1;
}

// ---------------------------------------------------------------- the cave

uint8_t gd_scanned[(CAVE_SIZE + 7) / 8];  // global: src/gdscan.s
static uint8_t hammered[CAVE_SIZE];  // frames until a hammered wall comes back

static bool flag(uint32_t f) {
    return (gd.flags & f) != 0;
}

#ifndef GD_FAR  // src/gdcell.s and src/gdscan.s on the MEGA65
// 1 << n without a loop: the 6502 shifts one bit at a time
static const uint8_t bit_of[8] = {1, 2, 4, 8, 16, 32, 64, 128};

static bool has_twin(uint8_t e) {
    return (gd_twin[e >> 3] & bit_of[e & 7]) != 0;
}
#endif

static const uint16_t row_at[CAVE_H] = {  // y * CAVE_W without multiplying
    0 * CAVE_W,  1 * CAVE_W,  2 * CAVE_W,  3 * CAVE_W,  4 * CAVE_W,  5 * CAVE_W,  6 * CAVE_W,  7 * CAVE_W,
    8 * CAVE_W,  9 * CAVE_W,  10 * CAVE_W, 11 * CAVE_W, 12 * CAVE_W, 13 * CAVE_W, 14 * CAVE_W, 15 * CAVE_W,
    16 * CAVE_W, 17 * CAVE_W, 18 * CAVE_W, 19 * CAVE_W, 20 * CAVE_W, 21 * CAVE_W};
_Static_assert(CAVE_H == 22, "row_at[]");

// What src/gdscan.s needs to know of each element (gd_class[], set by
// gd_start from GDash's tables)
#define GDC_PLAYER      0x01  // P_PLAYER
#define GDC_FIRST_STAGE 0x02  // P_EXPLOSION_FIRST_STAGE
#define GDC_PENALTY     0x04  // O_TIME_PENALTY
#define GDC_FALLS       0x08  // does nothing in the scan but do_start_fall with gravity
#define GDC_SPACE       0x10  // is_like_space
#define GDC_SLOPED_UP   0x20  // P_SLOPED_UP
#define GDC_ROUND       0x40  // P_SLOPED_LEFT and P_SLOPED_RIGHT: rolled off both ways
#define GDC_IDLE        0x80  // does nothing in the scan, adds no delay (bit 7: bmi)

#ifndef GD_FAR
#define clear_moved() memset(moved, DIR_NONE, CAVE_SIZE)
#endif

#ifdef GD_FAR
// On the MEGA65: src/gdcell.s, which knows where these are
uint16_t cell(int8_t x, int8_t y);
uint16_t get(int8_t x, int8_t y);
void store(int8_t x, int8_t y, uint8_t e);
bool has_flag(int8_t x, int8_t y, uint8_t dir, uint32_t f);
_Static_assert(O_LAVA == 116 && O_H_EXPANDING_STEEL_WALL == 47 && O_V_EXPANDING_STEEL_WALL == 48 &&
                   O_EXPANDING_STEEL_WALL == 49 && O_PLAYER == 163 && P_SCANNED == 0x1 &&
                   P_BLOWS_UP_FLIES == 0x100 && P_NON_EXPLODABLE == 0x800,
               "src/gdcell.s");
_Static_assert(offsetof(GdState, w) == 2 && offsetof(GdState, h) == 3 && offsetof(GdState, flags) == 4 &&
                   GDF_LINESHIFT == 0x02000000ul && CAVE_W == 40 && CAVE_H == 22,
               "src/gdcell.s");

uint8_t gd_class[O_COUNT];  // as gd_flags[]: the cave holds no other codes
void gd_clear_moved(void);
_Static_assert(DIR_NONE == 4 && CAVE_SIZE == 880, "src/gdscan.s");
#define clear_moved gd_clear_moved
uint8_t gd_cave_classes(bool first);
void gd_clear_scanned(void);
bool gd_find_player(bool first);
extern int8_t gd_found_x, gd_found_y;
_Static_assert(offsetof(GdState, gravity) == 46 && offsetof(GdState, gravity_disabled) == 92 && MV_DOWN == 5,
               "src/gdscan.s");
_Static_assert(offsetof(GdState, magic_wall_state) == 116 && offsetof(GdState, sound) == 126 &&
                   GD_MW_ACTIVE == 1 && SND_MAGIC == 0x40 && O_MAGIC_WALL == 17 && O_EXPANDING_WALL == 46 &&
                   O_EXPANDING_STEEL_WALL == 49,
               "src/gdscan.s");

static void set_classes(void) {
    for (uint8_t e = 0; e < O_COUNT; e++) {
        uint32_t p = gd_flags[e];
        uint8_t c = 0;
        if (p & P_PLAYER)
            c |= GDC_PLAYER;
        if (p & P_EXPLOSION_FIRST_STAGE)
            c |= GDC_FIRST_STAGE;
        if (e == O_TIME_PENALTY)
            c |= GDC_PENALTY;
        if (e == O_STONE || e == O_MEGA_STONE || e == O_DIAMOND || e == O_NUT || e == O_DIRT_BALL ||
            e == O_DIRT_LOOSE)
            c |= GDC_FALLS;
        if (e == O_SPACE || e == O_LAVA)
            c |= GDC_SPACE;
        if (p & P_SLOPED_UP)
            c |= GDC_SLOPED_UP;
        if ((p & (P_SLOPED_LEFT | P_SLOPED_RIGHT)) == (P_SLOPED_LEFT | P_SLOPED_RIGHT))
            c |= GDC_ROUND;
        if (e <= O_DIRT || e == O_BRICK || e == O_STEEL)
            c |= GDC_IDLE;
        gd_class[e] = c;
    }
}
#else
// The cell of x, y, wrapped round the cave as GDash does (perfectly or, as
// on the C64, line-shifted: off the right edge into the next row)
static uint16_t cell(int8_t x, int8_t y) {
    if ((uint8_t)x < gd.w && (uint8_t)y < gd.h)  // inside, as nearly always
        return row_at[(uint8_t)y] + (uint8_t)x;
    if (x < 0) {
        x += gd.w;
        if (flag(GDF_LINESHIFT))
            y--;
    } else if (x >= gd.w) {
        x -= gd.w;
        if (flag(GDF_LINESHIFT))
            y++;
    }
    if (y < 0)
        y += gd.h;
    else if (y >= gd.h)
        y -= gd.h;
    return row_at[(uint8_t)y] + (uint8_t)x;
}
#endif

#ifndef GD_FAR  // src/gdcell.s on the MEGA65
static bool scan_bit(uint16_t i) {
    return (gd_scanned[i >> 3] & bit_of[i & 7]) != 0;
}
#endif

#ifndef GD_FAR
// The element at x, y; with SCAN if it is scanned in this step
static uint16_t get(int8_t x, int8_t y) {
    uint16_t i = cell(x, y);
    return scan_bit(i) ? cave[i] | SCAN : cave[i];
}
#endif

static uint16_t get_dir(int8_t x, int8_t y, uint8_t dir) {
    return get(x + gd_dx[dir], y + gd_dy[dir]);
}

// The flags of an element as get() gives it
static uint32_t flags_of(uint16_t e) {
    if (e & SCAN) {
        e &= 0xFF;
        if (e == O_H_EXPANDING_STEEL_WALL || e == O_V_EXPANDING_STEEL_WALL || e == O_EXPANDING_STEEL_WALL)
            return P_SCANNED | P_NON_EXPLODABLE;
        return e == O_PLAYER ? P_SCANNED | P_BLOWS_UP_FLIES : P_SCANNED;
    }
    return gd_flags[e];
}

#ifndef GD_FAR  // src/gdcell.s on the MEGA65
static bool has_flag(int8_t x, int8_t y, uint8_t dir, uint32_t f) {
    return (flags_of(get_dir(x, y, dir)) & f) != 0;
}
#endif

#define explodes_by_hit(x, y, dir) has_flag(x, y, dir, P_EXPLODES_BY_HIT)
#define non_explodable(x, y)       has_flag(x, y, MV_STILL, P_NON_EXPLODABLE)
#define amoeba_eats(x, y, dir)     has_flag(x, y, dir, P_AMOEBA_CONSUMES)
#define blows_up_flies(x, y, dir)  has_flag(x, y, dir, P_BLOWS_UP_FLIES)
#define rotates_ccw(x, y)          has_flag(x, y, MV_STILL, P_CCW)
#define is_player(x, y)            has_flag(x, y, MV_STILL, P_PLAYER)
#define is_player_dir(x, y, dir)   has_flag(x, y, dir, P_PLAYER)
#define can_be_hammered(x, y, dir) has_flag(x, y, dir, P_CAN_BE_HAMMERED)
#define is_like_dirt(x, y, dir)    has_flag(x, y, dir, P_DIRT)
#define sloped_for_bladder(x, y, dir) has_flag(x, y, dir, P_BLADDER_SLOPED)
#define moved_by_conveyor_top(x, y, dir)    has_flag(x, y, dir, P_MOVED_BY_CONVEYOR_TOP)
#define moved_by_conveyor_bottom(x, y, dir) has_flag(x, y, dir, P_MOVED_BY_CONVEYOR_BOTTOM)
#define is_scanned(x, y)           has_flag(x, y, MV_STILL, P_SCANNED)
#define is_scanned_dir(x, y, dir)  has_flag(x, y, dir, P_SCANNED)

static bool sloped(int8_t x, int8_t y, uint8_t dir, uint8_t slop) {
    uint32_t f = flags_of(get_dir(x, y, dir));
    switch (slop) {
    case MV_LEFT:
        return (f & P_SLOPED_LEFT) != 0;
    case MV_RIGHT:
        return (f & P_SLOPED_RIGHT) != 0;
    case MV_UP:
        return (f & P_SLOPED_UP) != 0;
    case MV_DOWN:
        return (f & P_SLOPED_DOWN) != 0;
    }
    return false;
}

static bool is_like_element(int8_t x, int8_t y, uint8_t dir, uint16_t e) {
    uint16_t examined = get_dir(x, y, dir);
    if (flags_of(examined) & P_DIRT)
        examined = O_DIRT;
    if (flags_of(e) & P_DIRT)
        e = O_DIRT;
    if (examined == O_LAVA)
        examined = O_SPACE;
    return e == examined;
}

static bool is_like_space(int8_t x, int8_t y, uint8_t dir) {
    uint16_t e = get_dir(x, y, dir);
    return e == O_SPACE || e == O_LAVA;
}

// GDash keeps an element stored in a step as its scanned twin; lava takes
// what comes into it
#ifndef GD_FAR  // src/gdcell.s on the MEGA65
static void store(int8_t x, int8_t y, uint8_t e) {
    uint16_t i = cell(x, y);
    if (cave[i] == O_LAVA && !scan_bit(i))
        return;
    cave[i] = e;
    if (has_twin(e))
        gd_scanned[i >> 3] |= bit_of[i & 7];
    else
        gd_scanned[i >> 3] &= ~bit_of[i & 7];
}
#endif

// What scan_cell needs of the step besides the cell, and what it finds out
static uint8_t sc_move;
static bool sc_fire, sc_inbox_toggle, sc_amoeba_found_enclosed, sc_amoeba_2_found_enclosed;
static uint16_t sc_amoeba_count, sc_amoeba_2_count;
static bool st_taken;  // the player has taken sc_move and sc_fire in this step
uint32_t gd_scan_ckdelay;  // the C64's delay of the cells scan_cells passed

// Something for the drawing's little effects at x, y (gd.events, EV_*);
// the rules do not use them
// A sound of the step (SND_*, engine.h): each is a bit of one byte of
// gd.sound, which alone is changed
#define SOUND(f) (((uint8_t *)&gd.sound)[(f) > 0xFFFF ? 2 : (f) > 0xFF ? 1 : 0] |= \
                  (uint8_t)((f) >> ((f) > 0xFFFF ? 16 : (f) > 0xFF ? 8 : 0)))

static void event(int8_t x, int8_t y, uint8_t what) {
    if (gd.nevents < MAX_EVENTS) {
        Event *ev = &gd.events[gd.nevents++];
        ev->cell = cell(x, y);
        ev->what = what;
    }
}

// The same for a cell that something has just left (it is empty now)
static void left(int8_t x, int8_t y, uint8_t what) {
    if (get(x, y) == O_SPACE)
        event(x, y, what);
}

// The event of a thing that falls, is pushed or carried away from a cell
static uint8_t moved_event(uint16_t e) {
    switch (e) {
    case O_DIAMOND:
    case O_DIAMOND_F:
    case O_FLYING_DIAMOND:
    case O_FLYING_DIAMOND_F:
        return EV_FALLING_DIAMOND;
    case O_DIRT_BALL:
    case O_DIRT_BALL_F:
    case O_DIRT_LOOSE:
    case O_DIRT_LOOSE_F:
    case O_BOX:
        return EV_DUG;
    }
    return e >= O_BLADDER && e <= O_BLADDER_8 ? EV_BLADDER : EV_FALLING;
}

static void store_dir(int8_t x, int8_t y, uint8_t dir, uint8_t e) {
    store(x + gd_dx[dir], y + gd_dy[dir], e);
}

static void next(int8_t x, int8_t y) {
    cave[cell(x, y)]++;
}

// The drawing slides what moved by a cell (engine.h's moved[])
static void slid(int8_t x, int8_t y, uint8_t dir) {
    uint16_t i = cell(x + gd_dx[dir], y + gd_dy[dir]);
    switch (dir) {
    case MV_UP:
        moved[i] = DIR_UP;
        break;
    case MV_RIGHT:
        moved[i] = DIR_RIGHT;
        break;
    case MV_DOWN:
        moved[i] = DIR_DOWN;
        break;
    case MV_LEFT:
        moved[i] = DIR_LEFT;
        break;
    }
}

static void move(int8_t x, int8_t y, uint8_t dir, uint8_t e) {
    // what falls out of the bottom or the right edge stays where it is
    if ((y + gd_dy[dir] == gd.h && dir == MV_DOWN) || (x + gd_dx[dir] == gd.w && dir == MV_RIGHT)) {
        switch (get(x, y)) {
        case O_STONE:
        case O_MEGA_STONE:
        case O_DIAMOND:
        case O_NUT:
        case O_FLYING_STONE:
        case O_FLYING_DIAMOND:
        case O_FALLING_WALL:
        case O_NITRO_PACK:
            store(x, y, e);
            return;
        }
    }
    store_dir(x, y, dir, e);
    store(x, y, O_SPACE);
    slid(x, y, dir);
}

// ---------------------------------------------------------------- explosions

static void cell_explode(int8_t x, int8_t y, uint8_t explode_to) {
    if (non_explodable(x, y))
        return;
    uint16_t e = get(x, y);
    if (flag(GDF_VOODOO_ANY_HURT_KILLS_PLAYER) && e == O_VOODOO)
        gd.voodoo_touched = true;
    if (e == O_VOODOO && !flag(GDF_VOODOO_DISAPPEAR_IN_EXPLOSION))
        store(x, y, O_TIME_PENALTY);
    else if (e == O_NITRO_PACK || e == O_NITRO_PACK_F)
        store(x, y, O_NITRO_PACK_EXPLODE);
    else
        store(x, y, explode_to);
}

static void creature_explode(int8_t x, int8_t y, uint8_t explode_to) {
    gd.ckdelay_current += 1200;
    SOUND(SND_EXPLODE);
    for (int8_t yy = y - 1; yy <= y + 1; yy++)
        for (int8_t xx = x - 1; xx <= x + 1; xx++)
            cell_explode(xx, yy, explode_to);
}

static void nitro_explode(int8_t x, int8_t y) {
    gd.ckdelay_current += 1200;
    SOUND(SND_EXPLODE);
    for (int8_t yy = y - 1; yy <= y + 1; yy++)
        for (int8_t xx = x - 1; xx <= x + 1; xx++)
            cell_explode(xx, yy, O_NITRO_EXPL_1);
    store(x, y, O_NITRO_EXPL_1);
}

static void voodoo_explode(int8_t x, int8_t y) {
    if (flag(GDF_VOODOO_ANY_HURT_KILLS_PLAYER))
        gd.voodoo_touched = true;
    gd.ckdelay_current += 1000;
    SOUND(SND_EXPLODE);
    for (int8_t yy = y - 1; yy <= y + 1; yy++)
        for (int8_t xx = x - 1; xx <= x + 1; xx++)
            store(xx, yy, O_PRE_STEEL_1);
    store(x, y, O_TIME_PENALTY);
}

static void cell_explode_skip_voodoo(int8_t x, int8_t y, uint8_t expl) {
    if (non_explodable(x, y))
        return;
    if (!flag(GDF_VOODOO_DISAPPEAR_IN_EXPLOSION) && get(x, y) == O_VOODOO)
        return;
    if (flag(GDF_VOODOO_ANY_HURT_KILLS_PLAYER) && get(x, y) == O_VOODOO)
        gd.voodoo_touched = true;
    store(x, y, expl);
}

static void ghost_explode(int8_t x, int8_t y) {
    gd.ckdelay_current += 650;
    SOUND(SND_EXPLODE);
    cell_explode_skip_voodoo(x, y, O_GHOST_EXPL_1);
    cell_explode_skip_voodoo(x - 1, y - 1, O_GHOST_EXPL_1);
    cell_explode_skip_voodoo(x + 1, y + 1, O_GHOST_EXPL_1);
    cell_explode_skip_voodoo(x - 1, y + 1, O_GHOST_EXPL_1);
    cell_explode_skip_voodoo(x + 1, y - 1, O_GHOST_EXPL_1);
}

static void bomb_explode(int8_t x, int8_t y) {
    gd.ckdelay_current += 650;
    SOUND(SND_EXPLODE);
    cell_explode_skip_voodoo(x, y, O_BOMB_EXPL_1);
    cell_explode_skip_voodoo(x - 1, y, O_BOMB_EXPL_1);
    cell_explode_skip_voodoo(x + 1, y, O_BOMB_EXPL_1);
    cell_explode_skip_voodoo(x, y + 1, O_BOMB_EXPL_1);
    cell_explode_skip_voodoo(x, y - 1, O_BOMB_EXPL_1);
}

static void explode(int8_t x, int8_t y) {
    const GdCaveFile *f = gd.f;
    switch (get(x, y)) {
    case O_GHOST:
        ghost_explode(x, y);
        break;
    case O_BOMB_TICK_7:
        bomb_explode(x, y);
        break;
    case O_VOODOO:
        voodoo_explode(x, y);
        break;
    case O_NITRO_PACK:
    case O_NITRO_PACK_F:
    case O_NITRO_PACK_EXPLODE:
        nitro_explode(x, y);
        break;
    case O_AMOEBA_2:
        creature_explode(x, y, O_AMOEBA_2_EXPL_1);
        break;
    case O_FALLING_WALL_F:
    case O_ROCKET_1:
    case O_ROCKET_2:
    case O_ROCKET_3:
    case O_ROCKET_4:
        creature_explode(x, y, O_EXPLODE_1);
        break;
    case O_BUTTER_1:
    case O_BUTTER_2:
    case O_BUTTER_3:
    case O_BUTTER_4:
        creature_explode(x, y, f->butterfly_explode_to);
        break;
    case O_ALT_BUTTER_1:
    case O_ALT_BUTTER_2:
    case O_ALT_BUTTER_3:
    case O_ALT_BUTTER_4:
        creature_explode(x, y, f->alt_butterfly_explode_to);
        break;
    case O_FIREFLY_1:
    case O_FIREFLY_2:
    case O_FIREFLY_3:
    case O_FIREFLY_4:
        creature_explode(x, y, f->firefly_explode_to);
        break;
    case O_ALT_FIREFLY_1:
    case O_ALT_FIREFLY_2:
    case O_ALT_FIREFLY_3:
    case O_ALT_FIREFLY_4:
        creature_explode(x, y, f->alt_firefly_explode_to);
        break;
    case O_PLAYER:
    case O_PLAYER_BOMB:
    case O_PLAYER_GLUED:
    case O_PLAYER_STIRRING:
    case O_PLAYER_ROCKET_LAUNCHER:
    case O_PLAYER_PNEUMATIC_LEFT:
    case O_PLAYER_PNEUMATIC_RIGHT:
        creature_explode(x, y, O_EXPLODE_1);
        break;
    case O_STONEFLY_1:
    case O_STONEFLY_2:
    case O_STONEFLY_3:
    case O_STONEFLY_4:
        creature_explode(x, y, f->stonefly_explode_to);
        break;
    case O_DRAGONFLY_1:
    case O_DRAGONFLY_2:
    case O_DRAGONFLY_3:
    case O_DRAGONFLY_4:
        creature_explode(x, y, f->dragonfly_explode_to);
        break;
    }
}

static void explode_dir(int8_t x, int8_t y, uint8_t dir) {
    explode(x + gd_dx[dir], y + gd_dy[dir]);
}

// ---------------------------------------------------------------- the player

static uint8_t player_eat_element(uint16_t element, int8_t x, int8_t y, uint8_t dir) {
    int8_t from_x = x, from_y = y;
    x += gd_dx[dir];
    y += gd_dy[dir];
    switch (element) {
    case O_DIAMOND_KEY:
        SOUND(SND_PICKUP);
        gd.diamond_key_collected = true;
        return O_SPACE;
    case O_KEY_1:
        SOUND(SND_PICKUP);
        gd.key1++;
        return O_SPACE;
    case O_KEY_2:
        SOUND(SND_PICKUP);
        gd.key2++;
        return O_SPACE;
    case O_KEY_3:
        SOUND(SND_PICKUP);
        gd.key3++;
        return O_SPACE;
    case O_DOOR_1:
        if (!gd.key1)
            return O_NONE;
        SOUND(SND_DOOR);
        gd.key1--;
        return O_SPACE;
    case O_DOOR_2:
        if (!gd.key2)
            return O_NONE;
        SOUND(SND_DOOR);
        gd.key2--;
        return O_SPACE;
    case O_DOOR_3:
        if (!gd.key3)
            return O_NONE;
        SOUND(SND_DOOR);
        gd.key3--;
        return O_SPACE;
    case O_CREATURE_SWITCH:
        SOUND(SND_SWITCH);
        gd.flags ^= GDF_CREATURES_BACKWARDS;
        return O_CREATURE_SWITCH;
    case O_EXPANDING_WALL_SWITCH:
        SOUND(SND_SWITCH);
        gd.flags ^= GDF_EXPANDING_WALL_CHANGED;
        return O_EXPANDING_WALL_SWITCH;
    case O_BITER_SWITCH:
        SOUND(SND_SWITCH);
        if (++gd.biter_delay_frame == 4)
            gd.biter_delay_frame = 0;
        return O_BITER_SWITCH;
    case O_REPLICATOR_SWITCH:
        SOUND(SND_SWITCH);
        gd.flags ^= GDF_REPLICATORS_ACTIVE;
        return O_REPLICATOR_SWITCH;
    case O_CONVEYOR_SWITCH:
        SOUND(SND_SWITCH);
        gd.flags ^= GDF_CONVEYOR_BELTS_ACTIVE;
        return O_CONVEYOR_SWITCH;
    case O_CONVEYOR_DIR_SWITCH:
        SOUND(SND_SWITCH);
        gd.flags ^= GDF_CONVEYOR_BELTS_DIRECTION_CHANGED;
        return O_CONVEYOR_DIR_SWITCH;
    case O_GRAVITY_SWITCH:
        if (flag(GDF_GRAVITY_SWITCH_ACTIVE) && (dir == MV_LEFT || dir == MV_RIGHT || dir == MV_UP || dir == MV_DOWN)) {
            SOUND(SND_SWITCH);
            gd.gravity_will_change = (int32_t)gd.f->gravity_change_time * gd.timing_factor;
            gd.gravity_next_direction = dir;
            gd.flags &= ~GDF_GRAVITY_SWITCH_ACTIVE;
            return O_GRAVITY_SWITCH;
        }
        return O_NONE;
    case O_DIRT:
    case O_DIRT2:
    case O_DIRT_SLOPED_UP_RIGHT:
    case O_DIRT_SLOPED_UP_LEFT:
    case O_DIRT_SLOPED_DOWN_LEFT:
    case O_DIRT_SLOPED_DOWN_RIGHT:
    case O_DIRT_BALL:
    case O_DIRT_LOOSE:
    case O_STEEL_EATABLE:
    case O_BRICK_EATABLE:
        SOUND(SND_DIRT);
        if (sc_fire)  // crumbs where it was snapped, or where Rockford came from
            event(x, y, EV_DUG);
        else
            event(from_x, from_y, EV_DUG);
        return O_SPACE;
    case O_SPACE:
    case O_LAVA:
        SOUND(SND_STEP);
        return O_SPACE;
    case O_SWEET:
        SOUND(SND_PICKUP);
        gd.sweet_eaten = true;
        return O_SPACE;
    case O_PNEUMATIC_HAMMER:
        SOUND(SND_PICKUP);
        gd.got_pneumatic_hammer = true;
        return O_SPACE;
    case O_CLOCK:
        SOUND(SND_CLOCK);
        gd.time += (int32_t)gd.f->time_bonus * gd.timing_factor;
        if (gd.time > (int32_t)gd.f->max_time * gd.timing_factor)
            gd.time -= (int32_t)gd.f->max_time * gd.timing_factor;
        return O_DIRT;
    case O_DIAMOND:
    case O_FLYING_DIAMOND:
        gd.score += gd.diamond_value;
        gd.diamonds_collected++;
        SOUND(SND_COLLECT);
        if (gd.diamonds_needed == gd.diamonds_collected) {
            gd.gate_open = true;
            gd.diamond_value = gd.f->extra_diamond_value;
            gd.gate_open_flash = 1;
        }
        return O_SPACE;
    case O_SKELETON:
        SOUND(SND_PICKUP);
        gd.skeletons_collected++;
        for (uint8_t i = 0; i < gd.f->skeletons_worth_diamonds; i++)
            player_eat_element(O_DIAMOND, x, y, MV_STILL);
        return O_SPACE;
    case O_OUTBOX:
    case O_INVIS_OUTBOX:
        gd.player_state = GD_PL_EXITED;
        return O_SPACE;
    }
    return O_NONE;
}

// A Crazy Dream teleporter: the next one along the cave with room behind it
static bool do_teleporter(int8_t px, int8_t py, uint8_t player_move) {
    int8_t tx = px, ty = py;
    bool teleported = false;
    do {
        if (++tx >= gd.w) {
            tx = 0;
            if (++ty >= gd.h)
                ty = 0;
        }
        if (get(tx, ty) == O_TELEPORTER && is_like_space(tx, ty, player_move)) {
            store_dir(tx, ty, player_move, get(px, py));
            store(px, py, O_SPACE);
            teleported = true;
            SOUND(SND_TELEPORT);
        }
    } while (!teleported && (tx != px || ty != py));
    return teleported;
}

static uint8_t grav_compat(void) {
    return flag(GDF_GRAVITY_AFFECTS_ALL) ? gd.gravity : MV_DOWN;
}

static bool do_push(int8_t x, int8_t y, uint8_t player_move, bool player_fire) {
    uint16_t what = get_dir(x, y, player_move);
    uint8_t gc = grav_compat();
    bool result = false;
    switch (what) {
    case O_WAITING_STONE:
    case O_STONE:
    case O_NITRO_PACK:
    case O_CHASING_STONE:
    case O_MEGA_STONE:
    case O_FLYING_STONE:
    case O_NUT:
        if (player_move == ccw_fourth[gd.gravity] || player_move == cw_fourth[gd.gravity]) {
            uint32_t prob = 0;
            switch (what) {
            case O_WAITING_STONE:
                prob = 1000000;
                break;
            case O_CHASING_STONE:
                if (gd.sweet_eaten)
                    prob = 1000000;
                break;
            case O_MEGA_STONE:
                if (flag(GDF_MEGA_STONES_PUSHABLE_WITH_SWEET) && gd.sweet_eaten)
                    prob = 1000000;
                break;
            default:
                prob = gd.sweet_eaten ? gd.f->pushing_stone_prob_sweet : gd.f->pushing_stone_prob;
                break;
            }
            if (is_like_space(x, y, twice[player_move]) && chance(prob)) {
                SOUND(SND_BOULDER);
                store_dir(x, y, twice[player_move], what == O_STONE ? gd.f->stone_bouncing_effect : what);
                slid(x + gd_dx[player_move], y + gd_dy[player_move], player_move);
                result = true;
            }
        }
        break;
    case O_BLADDER:
    case O_BLADDER_1:
    case O_BLADDER_2:
    case O_BLADDER_3:
    case O_BLADDER_4:
    case O_BLADDER_5:
    case O_BLADDER_6:
    case O_BLADDER_7:
    case O_BLADDER_8:
        if (player_move != opposite[gc]) {
            if (player_move == gc) {
                if (is_like_space(x, y, twice[player_move]))
                    store_dir(x, y, twice[player_move], O_BLADDER), result = true;
                else if (is_like_space(x, y, cw_eighth[gc]))
                    store_dir(x, y, cw_eighth[gc], O_BLADDER), result = true;
                else if (is_like_space(x, y, ccw_eighth[gc]))
                    store_dir(x, y, ccw_eighth[gc], O_BLADDER), result = true;
            } else if (player_move == cw_fourth[gc]) {
                if (is_like_space(x, y, twice[cw_fourth[gc]]))
                    store_dir(x, y, twice[cw_fourth[gc]], O_BLADDER), result = true;
                else if (is_like_space(x, y, cw_eighth[gc]))
                    store_dir(x, y, cw_eighth[gc], O_BLADDER), result = true;
                else if (is_like_space(x, y, cw_eighth[player_move]))
                    store_dir(x, y, cw_eighth[player_move], O_BLADDER), result = true;
            } else if (player_move == ccw_fourth[gc]) {
                if (is_like_space(x, y, twice[player_move]))
                    store_dir(x, y, twice[player_move], O_BLADDER), result = true;
                else if (is_like_space(x, y, ccw_eighth[gc]))
                    store_dir(x, y, ccw_eighth[gc], O_BLADDER), result = true;
                else if (is_like_space(x, y, ccw_eighth[player_move]))
                    store_dir(x, y, ccw_eighth[player_move], O_BLADDER), result = true;
            }
        }
        break;
    case O_BOX:
        if (player_fire && (player_move == MV_LEFT || player_move == MV_RIGHT || player_move == MV_UP ||
                            player_move == MV_DOWN) && is_like_space(x, y, twice[player_move])) {
            store_dir(x, y, twice[player_move], O_BOX);
            SOUND(SND_BOULDER);
            result = true;
        }
        break;
    }
    if (result)  // where it was (Rockford steps in, but for a box)
        event(x + gd_dx[player_move], y + gd_dy[player_move], moved_event(what));
    return result;
}

// The players' own steps: what is shared by the player with a bomb, with
// a rocket launcher: pushing, teleporting, eating; true if he moves
static bool player_go(int8_t x, int8_t y, uint8_t player_move) {
    uint16_t what = get_dir(x, y, player_move);
    if (what == O_TELEPORTER && do_teleporter(x, y, player_move))
        return false;
    if (do_push(x, y, player_move, false))
        return true;
    return player_eat_element(what, x, y, player_move) != O_NONE;
}

// ---------------------------------------------------------------- falling

static void do_start_fall(int8_t x, int8_t y, uint8_t falling_direction, uint8_t falling_element) {
    if (gd.gravity_disabled)
        return;
    if (is_like_space(x, y, falling_direction)) {
        move(x, y, falling_direction, falling_element);
    } else if (sloped(x, y, falling_direction, opposite[falling_direction])) {
        if (sloped(x, y, falling_direction, cw_fourth[falling_direction]) &&
            is_like_space(x, y, cw_fourth[falling_direction]) && is_like_space(x, y, cw_eighth[falling_direction]))
            move(x, y, cw_fourth[falling_direction], falling_element);
        else if (sloped(x, y, falling_direction, ccw_fourth[falling_direction]) &&
                 is_like_space(x, y, ccw_fourth[falling_direction]) &&
                 is_like_space(x, y, ccw_eighth[falling_direction]))
            move(x, y, ccw_fourth[falling_direction], falling_element);
    }
    left(x, y, moved_event(falling_element));
}

static bool do_fall_try_crush_voodoo(int8_t x, int8_t y, uint8_t fall_dir) {
    if (get_dir(x, y, fall_dir) == O_VOODOO && flag(GDF_VOODOO_DIES_BY_STONE)) {
        explode_dir(x, y, fall_dir);
        return true;
    }
    return false;
}

static bool do_fall_try_eat_voodoo(int8_t x, int8_t y, uint8_t fall_dir) {
    if (get_dir(x, y, fall_dir) == O_VOODOO && flag(GDF_VOODOO_COLLECTS_DIAMONDS)) {
        player_eat_element(O_DIAMOND, x, y, fall_dir);
        store(x, y, O_SPACE);
        return true;
    }
    return false;
}

static bool do_fall_try_crack_nut(int8_t x, int8_t y, uint8_t fall_dir, uint8_t bouncing) {
    uint16_t e = get_dir(x, y, fall_dir);
    if (e == O_NUT || e == O_NUT_F) {
        store(x, y, bouncing);
        store_dir(x, y, fall_dir, gd.f->nut_turns_to_when_crushed);
        SOUND(SND_NUT);
        return true;
    }
    return false;
}

static bool do_fall_try_magic(int8_t x, int8_t y, uint8_t fall_dir, uint8_t magic) {
    if (get_dir(x, y, fall_dir) == O_MAGIC_WALL) {
        SOUND(SND_DIAMOND);
        if (gd.magic_wall_state == GD_MW_DORMANT)
            gd.magic_wall_state = GD_MW_ACTIVE;
        if (gd.magic_wall_state == GD_MW_ACTIVE && is_like_space(x, y, twice[fall_dir]))
            store_dir(x, y, twice[fall_dir], magic);
        store(x, y, O_SPACE);
        if (flag(GDF_MAGIC_WALL_BREAKSCAN) && gd.amoeba_state == GD_AM_AWAKE)
            gd.convert_amoeba_this_frame = true;
        return true;
    }
    return false;
}

static bool do_fall_try_crush(int8_t x, int8_t y, uint8_t fall_dir) {
    if (explodes_by_hit(x, y, fall_dir)) {
        explode_dir(x, y, fall_dir);
        return true;
    }
    return false;
}

static void landed(int8_t x, int8_t y) {
    uint16_t e = get(x, y);
    bool diamond = e == O_DIAMOND || e == O_DIAMOND_F || e == O_FLYING_DIAMOND_F;
    if (diamond)
        SOUND(SND_DIAMOND);
    else
        SOUND(SND_BOULDER);
    if (!diamond)
        event(x, y, EV_LANDED);
}

static void do_fall_roll_or_stop(int8_t x, int8_t y, uint8_t fall_dir, uint8_t bouncing) {
    if (is_like_space(x, y, fall_dir)) {
        move(x, y, fall_dir, get(x, y));
        return;
    }
    if (sloped(x, y, fall_dir, opposite[fall_dir])) {
        if (sloped(x, y, fall_dir, cw_fourth[fall_dir]) && is_like_space(x, y, cw_eighth[fall_dir]) &&
            is_like_space(x, y, cw_fourth[fall_dir])) {
            move(x, y, cw_fourth[fall_dir], get(x, y));
        } else if (sloped(x, y, fall_dir, ccw_fourth[fall_dir]) && is_like_space(x, y, ccw_eighth[fall_dir]) &&
                   is_like_space(x, y, ccw_fourth[fall_dir])) {
            move(x, y, ccw_fourth[fall_dir], get(x, y));
        } else {
            landed(x, y);
            store(x, y, bouncing);
        }
        return;
    }
    landed(x, y);
    store(x, y, bouncing);
}

// ---------------------------------------------------------------- creatures

// Fireflies, butterflies and their kind, cows: turn to their side first,
// then straight on, else turn the other way on the spot
static void creature_move(int8_t x, int8_t y, uint8_t base) {
    bool ccw = rotates_ccw(x, y);
    uint8_t dir = get(x, y) - base, dirn, dirp;
    const uint8_t *cm = flag(GDF_CREATURES_BACKWARDS) ? creature_chdir : creature_dir;
    if (flag(GDF_CREATURES_BACKWARDS))
        ccw = !ccw;
    if (ccw) {
        dirn = (dir + 3) & 3;
        dirp = (dir + 1) & 3;
    } else {
        dirn = (dir + 1) & 3;
        dirp = (dir + 3) & 3;
    }
    if (is_like_space(x, y, cm[dirn]))
        move(x, y, cm[dirn], base + dirn);
    else if (is_like_space(x, y, cm[dir]))
        move(x, y, cm[dir], base + dir);
    else {
        store(x, y, base + dirp);
        return;
    }
    switch (base) {  // the cell it left
    case O_FIREFLY_1:
        event(x, y, EV_FIREFLY);
        break;
    case O_ALT_FIREFLY_1:
        event(x, y, EV_ALT_FIREFLY);
        break;
    case O_BUTTER_1:
        event(x, y, EV_BUTTERFLY);
        break;
    case O_ALT_BUTTER_1:
        event(x, y, EV_ALT_BUTTERFLY);
        break;
    case O_STONEFLY_1:
        event(x, y, EV_STONEFLY);
        break;
    case O_COW_1:
        event(x, y, EV_COW);
        break;
    }
}

static bool touches(int8_t x, int8_t y, uint16_t e) {
    return get_dir(x, y, MV_LEFT) == e || get_dir(x, y, MV_RIGHT) == e || get_dir(x, y, MV_UP) == e ||
           get_dir(x, y, MV_DOWN) == e;
}

static bool flies_blow_up(int8_t x, int8_t y) {
    return blows_up_flies(x, y, MV_DOWN) || blows_up_flies(x, y, MV_UP) || blows_up_flies(x, y, MV_LEFT) ||
           blows_up_flies(x, y, MV_RIGHT);
}

static void chasing_stone(int8_t x, int8_t y) {
    int8_t px = gd.player_x_mem[0], py = gd.player_y_mem[0];
    bool horizontal = rand_bool();
    bool dont_move = false;
    int8_t i = 3;
    for (;;) {
        if (horizontal) {
            if (px == x) {
                i -= 1;
                horizontal = !horizontal;
                if (i == 2)
                    continue;
            } else {
                if (px > x && is_like_space(x, y, MV_RIGHT)) {
                    move(x, y, MV_RIGHT, O_CHASING_STONE);
                    dont_move = true;
                    break;
                } else if (px < x && is_like_space(x, y, MV_LEFT)) {
                    move(x, y, MV_LEFT, O_CHASING_STONE);
                    dont_move = true;
                    break;
                } else {
                    i -= 2;
                    if (i == 1) {
                        horizontal = !horizontal;
                        continue;
                    }
                }
            }
        } else {
            if (py == y) {
                i -= 1;
                horizontal = !horizontal;
                if (i == 2)
                    continue;
            } else {
                if (py > y && is_like_space(x, y, MV_DOWN)) {
                    move(x, y, MV_DOWN, O_CHASING_STONE);
                    dont_move = true;
                    break;
                } else if (py < y && is_like_space(x, y, MV_UP)) {
                    move(x, y, MV_UP, O_CHASING_STONE);
                    dont_move = true;
                    break;
                } else {
                    i -= 2;
                    if (i == 1) {
                        horizontal = !horizontal;
                        continue;
                    }
                }
            }
        }
        if (i != 0)
            dont_move = true;
        break;
    }
    if (!dont_move) {
        if (horizontal) {
            if (x >= px) {
                if (is_like_space(x, y, MV_UP) && is_like_space(x, y, MV_UP_LEFT))
                    move(x, y, MV_UP, O_CHASING_STONE);
                else if (is_like_space(x, y, MV_DOWN) && is_like_space(x, y, MV_DOWN_LEFT))
                    move(x, y, MV_DOWN, O_CHASING_STONE);
            } else {
                if (is_like_space(x, y, MV_UP) && is_like_space(x, y, MV_UP_RIGHT))
                    move(x, y, MV_UP, O_CHASING_STONE);
                else if (is_like_space(x, y, MV_DOWN) && is_like_space(x, y, MV_DOWN_RIGHT))
                    move(x, y, MV_DOWN, O_CHASING_STONE);
            }
        } else {
            if (y >= py) {
                if (is_like_space(x, y, MV_LEFT) && is_like_space(x, y, MV_UP_LEFT))
                    move(x, y, MV_LEFT, O_CHASING_STONE);
                else if (is_like_space(x, y, MV_RIGHT) && is_like_space(x, y, MV_UP_RIGHT))
                    move(x, y, MV_RIGHT, O_CHASING_STONE);
            } else {
                if (is_like_space(x, y, MV_LEFT) && is_like_space(x, y, MV_DOWN_LEFT))
                    move(x, y, MV_LEFT, O_CHASING_STONE);
                else if (is_like_space(x, y, MV_RIGHT) && is_like_space(x, y, MV_DOWN_RIGHT))
                    move(x, y, MV_RIGHT, O_CHASING_STONE);
            }
        }
    }
}

static void biter(int8_t x, int8_t y) {
    static const uint8_t biter_move[] = {MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT};
    uint8_t biter_try[] = {O_DIRT, gd.f->biter_eat, O_SPACE, O_STONE};
    uint8_t dir = get(x, y) - O_BITER_1;
    uint8_t dirn = (dir + 3) & 3, dirp = (dir + 1) & 3;
    uint8_t i;
    for (i = 0; i < 4; i++) {
        if (is_like_element(x, y, biter_move[dir], biter_try[i])) {
            move(x, y, biter_move[dir], O_BITER_1 + dir);
            break;
        } else if (is_like_element(x, y, biter_move[dirn], biter_try[i])) {
            move(x, y, biter_move[dirn], O_BITER_1 + dirn);
            break;
        } else if (is_like_element(x, y, biter_move[dirp], biter_try[i])) {
            move(x, y, biter_move[dirp], O_BITER_1 + dirp);
            break;
        }
    }
    if (i == 4)
        store(x, y, O_BITER_1 + dirp);
    else if (biter_try[i] == O_STONE)
        store(x, y, O_STONE);
    else if (biter_try[i] != O_SPACE)  // it ate
        SOUND(SND_NUT);
}

static void bladder(int8_t x, int8_t y) {
    uint8_t gc = grav_compat(), up = opposite[gc];
    uint8_t conv = gd.f->bladder_converts_by;
    if (is_like_element(x, y, up, conv) || is_like_element(x, y, cw_fourth[gc], conv) ||
        is_like_element(x, y, ccw_fourth[gc], conv)) {
        store(x, y, O_PRE_CLOCK_1);
        SOUND(SND_SLIME);
    } else if (is_like_space(x, y, up)) {
        if (get(x, y) == O_BLADDER_8)
            move(x, y, up, O_BLADDER_1), SOUND(SND_SLIME);
        else
            next(x, y);
    } else if (sloped_for_bladder(x, y, up) && sloped(x, y, up, up)) {
        if (sloped(x, y, up, ccw_fourth[up]) && is_like_space(x, y, ccw_fourth[up]) &&
            is_like_space(x, y, ccw_eighth[up])) {
            if (get(x, y) == O_BLADDER_8)
                move(x, y, ccw_fourth[up], O_BLADDER_8);
            else
                next(x, y);
        } else if (sloped(x, y, up, cw_fourth[up]) && is_like_space(x, y, cw_fourth[up]) &&
                   is_like_space(x, y, cw_eighth[up])) {
            if (get(x, y) == O_BLADDER_8)
                move(x, y, cw_fourth[up], O_BLADDER_8);
            else
                next(x, y);
        }
    } else {
        store(x, y, O_BLADDER_1);
    }
}

static void amoeba_grow(int8_t x, int8_t y, uint8_t e) {
    switch (rand_below(4)) {
    case 0:
        if (amoeba_eats(x, y, MV_UP))
            store_dir(x, y, MV_UP, e);
        break;
    case 1:
        if (amoeba_eats(x, y, MV_DOWN))
            store_dir(x, y, MV_DOWN, e);
        break;
    case 2:
        if (amoeba_eats(x, y, MV_LEFT))
            store_dir(x, y, MV_LEFT, e);
        break;
    case 3:
        if (amoeba_eats(x, y, MV_RIGHT))
            store_dir(x, y, MV_RIGHT, e);
        break;
    }
}

static bool amoeba_has_room(int8_t x, int8_t y) {
    return amoeba_eats(x, y, MV_UP) || amoeba_eats(x, y, MV_DOWN) || amoeba_eats(x, y, MV_LEFT) ||
           amoeba_eats(x, y, MV_RIGHT);
}

static void slime(int8_t x, int8_t y) {
    const GdCaveFile *f = gd.f;
    bool pass = flag(GDF_SLIME_PREDICTABLE) ? (c64_random() & f->slime_permeability_c64) == 0
                                            : chance(f->slime_permeability);
    if (!pass)
        return;
    uint8_t grav = gd.gravity, oppos = opposite[gd.gravity];
    if (is_like_space(x, y, grav)) {
        uint16_t e = get_dir(x, y, oppos);
        uint8_t to;
        if (e == f->slime_eats_1)
            to = f->slime_converts_1;
        else if (e == f->slime_eats_2)
            to = f->slime_converts_2;
        else if (e == f->slime_eats_3)
            to = f->slime_converts_3;
        else if (e == O_WAITING_STONE)
            to = O_WAITING_STONE;
        else if (e == O_CHASING_STONE)
            to = O_CHASING_STONE;
        else
            return;
        store_dir(x, y, grav, to);
        store_dir(x, y, oppos, O_SPACE);
        SOUND(SND_SLIME);
    } else if (is_like_space(x, y, oppos)) {
        uint16_t e = get_dir(x, y, grav);
        uint8_t to;
        if (e == O_BLADDER)
            to = O_BLADDER_1;
        else if (e == O_FLYING_STONE)
            to = O_FLYING_STONE_F;
        else if (e == O_FLYING_DIAMOND)
            to = O_FLYING_DIAMOND_F;
        else
            return;
        store_dir(x, y, grav, O_SPACE);
        store_dir(x, y, oppos, to);
        SOUND(SND_SLIME);
    }
}

// ---------------------------------------------------------------- the scan

// The players: GDash's O_PLAYER with what it can carry
static void player(int8_t x, int8_t y, uint16_t e, uint8_t player_move, bool player_fire) {
    if (gd.kill_player) {
        explode(x, y);
        return;
    }
    gd.player_seen_ago = 0;
    if (gd.player_state != GD_PL_EXITED)
        gd.player_state = GD_PL_LIVING;
    switch (e) {
    case O_PLAYER:
        if (player_fire && gd.got_pneumatic_hammer && is_like_space(x, y, player_move) &&
            !is_like_space(x, y, MV_DOWN)) {
            if (player_move == MV_LEFT && can_be_hammered(x, y, MV_DOWN_LEFT)) {
                gd.pneumatic_hammer_active_delay = gd.f->pneumatic_hammer_frame;
                store_dir(x, y, MV_LEFT, O_PNEUMATIC_ACTIVE_LEFT);
                SOUND(SND_HAMMER);
                store(x, y, O_PLAYER_PNEUMATIC_LEFT);
                return;
            }
            if (player_move == MV_RIGHT && can_be_hammered(x, y, MV_DOWN_RIGHT)) {
                gd.pneumatic_hammer_active_delay = gd.f->pneumatic_hammer_frame;
                store_dir(x, y, MV_RIGHT, O_PNEUMATIC_ACTIVE_RIGHT);
                SOUND(SND_HAMMER);
                store(x, y, O_PLAYER_PNEUMATIC_RIGHT);
                return;
            }
        }
        if (player_move != MV_STILL) {
            uint16_t what = get_dir(x, y, player_move);
            uint8_t remains = O_NONE;
            bool push;
            if (what == O_TELEPORTER && do_teleporter(x, y, player_move))
                return;
            push = do_push(x, y, player_move, player_fire);
            if (push) {
                remains = O_SPACE;
            } else {
                switch (what) {
                case O_BOMB:
                    SOUND(SND_PICKUP);
                    store_dir(x, y, player_move, O_SPACE);
                    if (player_fire)
                        store(x, y, O_PLAYER_BOMB);
                    else
                        move(x, y, player_move, O_PLAYER_BOMB);
                    break;
                case O_ROCKET_LAUNCHER:
                    SOUND(SND_PICKUP);
                    store_dir(x, y, player_move, O_SPACE);
                    if (player_fire)
                        store(x, y, O_PLAYER_ROCKET_LAUNCHER);
                    else
                        move(x, y, player_move, O_PLAYER_ROCKET_LAUNCHER);
                    break;
                case O_POT:
                    if (!player_fire && !flag(GDF_GRAVITY_SWITCH_ACTIVE) &&
                        gd.skeletons_collected >= gd.f->skeletons_needed_for_pot) {
                        gd.skeletons_collected -= gd.f->skeletons_needed_for_pot;
                        move(x, y, player_move, O_PLAYER_STIRRING);
                        SOUND(SND_SWITCH);
                        gd.gravity_disabled = true;
                    }
                    break;
                default:
                    remains = player_eat_element(what, x, y, player_move);
                    break;
                }
            }
            if (remains != O_NONE) {
                if (remains == O_SPACE && player_fire && !push)
                    remains = gd.f->snap_element;
                if (remains != O_SPACE || player_fire)
                    store_dir(x, y, player_move, remains);
                else
                    move(x, y, player_move, O_PLAYER);
            }
        }
        break;
    case O_PLAYER_BOMB:
        if (player_move != MV_STILL) {
            if (player_fire) {
                if (is_like_space(x, y, player_move) || is_like_dirt(x, y, player_move)) {
                    store_dir(x, y, player_move, O_BOMB_TICK_1);
                    SOUND(SND_BOMB);
                    store(x, y, O_PLAYER);
                }
                break;
            }
            if (player_go(x, y, player_move))
                move(x, y, player_move, O_PLAYER_BOMB);
        }
        break;
    case O_PLAYER_ROCKET_LAUNCHER:
        if (player_move != MV_STILL) {
            if (player_fire) {
                if (is_like_space(x, y, player_move)) {
                    uint8_t rocket = player_move == MV_RIGHT ? O_ROCKET_1 : player_move == MV_UP ? O_ROCKET_2
                                   : player_move == MV_LEFT ? O_ROCKET_3 : player_move == MV_DOWN ? O_ROCKET_4 : 0;
                    if (rocket) {
                        store_dir(x, y, player_move, rocket);
                        if (!flag(GDF_INFINITE_ROCKETS))
                            store(x, y, O_PLAYER);
                    }
                }
                break;
            }
            if (player_go(x, y, player_move))
                move(x, y, player_move, O_PLAYER_ROCKET_LAUNCHER);
        }
        break;
    case O_PLAYER_STIRRING:
        if (player_fire) {
            gd.gravity_disabled = false;
            store(x, y, O_PLAYER);
            gd.flags |= GDF_GRAVITY_SWITCH_ACTIVE;
        }
        break;
    case O_PLAYER_PNEUMATIC_LEFT:
    case O_PLAYER_PNEUMATIC_RIGHT:
        if (gd.pneumatic_hammer_active_delay == 0)
            store(x, y, O_PLAYER);
        break;
    }
}

static void expanding(int8_t x, int8_t y, uint8_t a, uint8_t b) {
    uint8_t e = get(x, y);
    if (is_like_space(x, y, a))
        store_dir(x, y, a, e), SOUND(SND_GROW);
    else if (is_like_space(x, y, b))
        store_dir(x, y, b, e), SOUND(SND_GROW);
}

static void conveyor(int8_t x, int8_t y) {
    if (gd.gravity_disabled || !flag(GDF_CONVEYOR_BELTS_ACTIVE))
        return;
    bool left = get(x, y) != O_CONVEYOR_RIGHT;
    if (flag(GDF_CONVEYOR_BELTS_DIRECTION_CHANGED))
        left = !left;
    const uint8_t *dir = left ? ccw_eighth : cw_eighth;
    if ((gd.gravity == MV_DOWN && moved_by_conveyor_top(x, y, MV_UP)) ||
        (gd.gravity == MV_UP && moved_by_conveyor_bottom(x, y, MV_UP))) {
        if (is_like_space(x, y, dir[MV_UP])) {
            uint16_t e = get_dir(x, y, MV_UP);
            store_dir(x, y, dir[MV_UP], e);
            store_dir(x, y, MV_UP, O_SPACE);
            event(x, y - 1, moved_event(e));
        }
    }
    if ((gd.gravity == MV_UP && moved_by_conveyor_top(x, y, MV_DOWN)) ||
        (gd.gravity == MV_DOWN && moved_by_conveyor_bottom(x, y, MV_DOWN))) {
        if (is_like_space(x, y, dir[MV_DOWN])) {
            uint16_t e = get_dir(x, y, MV_DOWN);
            store_dir(x, y, dir[MV_DOWN], e);
            store_dir(x, y, MV_DOWN, O_SPACE);
            event(x, y + 1, moved_event(e));
        }
    }
}

static void rocket(int8_t x, int8_t y, uint8_t dir, uint8_t e) {
    if (is_like_space(x, y, dir))
        move(x, y, dir, e);
    else
        explode(x, y);
}

static const uint8_t ghost_explode_to[] = {
    O_SPACE, O_SPACE, O_DIRT, O_DIRT, O_CLOCK, O_CLOCK, O_PRE_OUTBOX, O_BOMB, O_BOMB, O_PLAYER, O_GHOST,
    O_BLADDER, O_DIAMOND, O_SWEET, O_WAITING_STONE, O_BITER_1};

#if defined(GD_FAR) && defined(GDPROF_ENGINE)
// Built with -DGDPROF_ENGINE: where the time of a step goes (main.c's GDPROF
// reads it from a memory dump), by CIA 1's timer A
volatile uint32_t gd_prof[8];  // timer ticks: before the scan, scan, after it, find_player, rest;
                               // 5: in scan_cell, 6: its calls
static uint16_t prof_t;
static uint16_t prof_now(void) {
    uint8_t lo, hi;
    do {
        hi = *(volatile uint8_t *)0xDC05;
        lo = *(volatile uint8_t *)0xDC04;
    } while (hi != *(volatile uint8_t *)0xDC05);
    return (uint16_t)hi << 8 | lo;
}
static void prof_mark(uint8_t n) {
    uint16_t t = prof_now();
    if (n < 8)
        gd_prof[n] += (uint16_t)(prof_t - t);
    prof_t = t;
}
#define PROF_START uint16_t prof_c0 = prof_now(); gd_prof[6]++;
#define PROF_END   gd_prof[5] += (uint16_t)(prof_c0 - prof_now());
#else
#define prof_mark(n)
#define PROF_START
#define PROF_END
#endif


// One cell of the scan, not scanned yet in this step: its element e does
// what it does (scan_cells unscans it afterwards). Called from
// src/gdscan.s on the MEGA65.
void scan_cell(int8_t x, int8_t y, uint8_t e) {
    const GdCaveFile *f = gd.f;
    PROF_START
    switch (e) {
    case O_PLAYER:
    case O_PLAYER_BOMB:
    case O_PLAYER_ROCKET_LAUNCHER:
    case O_PLAYER_STIRRING:
    case O_PLAYER_PNEUMATIC_LEFT:
    case O_PLAYER_PNEUMATIC_RIGHT:
        player(x, y, e, sc_move, sc_fire);
        st_taken = true;
        break;
    case O_PNEUMATIC_ACTIVE_RIGHT:
    case O_PNEUMATIC_ACTIVE_LEFT:
        if (gd.pneumatic_hammer_active_delay == 0) {
            store(x, y, O_SPACE);
            uint16_t below = get_dir(x, y, MV_DOWN);
            uint8_t new_elem = below & SCAN ? O_NONE : gd_hammered[below];
            if (new_elem != O_NONE && new_elem != 255) {
                store_dir(x, y, MV_DOWN, new_elem);
                if (flag(GDF_HAMMERED_WALLS_REAPPEAR))
                    hammered[cell(x, (y + 1) % gd.h)] = f->hammered_wall_reappear_frame;
            }
        }
        break;
    case O_STONE:
        do_start_fall(x, y, gd.gravity, f->stone_falling_effect);
        break;
    case O_MEGA_STONE:
        do_start_fall(x, y, gd.gravity, O_MEGA_STONE_F);
        break;
    case O_DIAMOND:
        do_start_fall(x, y, gd.gravity, f->diamond_falling_effect);
        break;
    case O_NUT:
        do_start_fall(x, y, gd.gravity, O_NUT_F);
        break;
    case O_DIRT_BALL:
        do_start_fall(x, y, gd.gravity, O_DIRT_BALL_F);
        break;
    case O_DIRT_LOOSE:
        do_start_fall(x, y, gd.gravity, O_DIRT_LOOSE_F);
        break;
    case O_FLYING_STONE:
        do_start_fall(x, y, opposite[gd.gravity], O_FLYING_STONE_F);
        break;
    case O_FLYING_DIAMOND:
        do_start_fall(x, y, opposite[gd.gravity], O_FLYING_DIAMOND_F);
        break;
    case O_DIRT_BALL_F:
        if (!gd.gravity_disabled)
            do_fall_roll_or_stop(x, y, gd.gravity, O_DIRT_BALL);
        left(x, y, EV_DUG);
        break;
    case O_DIRT_LOOSE_F:
        if (!gd.gravity_disabled)
            do_fall_roll_or_stop(x, y, gd.gravity, O_DIRT_LOOSE);
        left(x, y, EV_DUG);
        break;
    case O_STONE_F:
        if (!gd.gravity_disabled) {
            if (do_fall_try_crush_voodoo(x, y, gd.gravity) ||
                do_fall_try_crack_nut(x, y, gd.gravity, f->stone_bouncing_effect) ||
                do_fall_try_magic(x, y, gd.gravity, f->magic_stone_to) ||
                do_fall_try_crush(x, y, gd.gravity))
                break;
            do_fall_roll_or_stop(x, y, gd.gravity, f->stone_bouncing_effect);
        }
        left(x, y, EV_FALLING);
        break;
    case O_MEGA_STONE_F:
        if (!gd.gravity_disabled) {
            if (do_fall_try_crush_voodoo(x, y, gd.gravity) ||
                do_fall_try_crack_nut(x, y, gd.gravity, O_MEGA_STONE) ||
                do_fall_try_magic(x, y, gd.gravity, f->magic_mega_stone_to) ||
                do_fall_try_crush(x, y, gd.gravity))
                break;
            do_fall_roll_or_stop(x, y, gd.gravity, O_MEGA_STONE);
        }
        left(x, y, EV_FALLING);
        break;
    case O_DIAMOND_F:
        if (!gd.gravity_disabled) {
            if (do_fall_try_eat_voodoo(x, y, gd.gravity) ||
                do_fall_try_magic(x, y, gd.gravity, f->magic_diamond_to) ||
                do_fall_try_crush(x, y, gd.gravity))
                break;
            do_fall_roll_or_stop(x, y, gd.gravity, f->diamond_bouncing_effect);
        }
        left(x, y, EV_FALLING_DIAMOND);
        break;
    case O_NUT_F:
        if (!gd.gravity_disabled) {
            if (do_fall_try_magic(x, y, gd.gravity, f->magic_nut_to) || do_fall_try_crush(x, y, gd.gravity))
                break;
            do_fall_roll_or_stop(x, y, gd.gravity, O_NUT);
        }
        left(x, y, EV_FALLING);
        break;
    case O_FLYING_STONE_F:
        if (!gd.gravity_disabled) {
            uint8_t fall_dir = opposite[gd.gravity];
            if (do_fall_try_crush_voodoo(x, y, fall_dir) ||
                do_fall_try_crack_nut(x, y, fall_dir, O_FLYING_STONE) ||
                do_fall_try_magic(x, y, fall_dir, f->magic_flying_stone_to) ||
                do_fall_try_crush(x, y, fall_dir))
                break;
            do_fall_roll_or_stop(x, y, fall_dir, O_FLYING_STONE);
        }
        left(x, y, EV_FALLING);
        break;
    case O_FLYING_DIAMOND_F:
        if (!gd.gravity_disabled) {
            uint8_t fall_dir = opposite[gd.gravity];
            if (do_fall_try_eat_voodoo(x, y, fall_dir) ||
                do_fall_try_magic(x, y, fall_dir, f->magic_flying_diamond_to) ||
                do_fall_try_crush(x, y, fall_dir))
                break;
            do_fall_roll_or_stop(x, y, fall_dir, O_FLYING_DIAMOND);
        }
        left(x, y, EV_FALLING_DIAMOND);
        break;
    case O_NITRO_PACK:
        do_start_fall(x, y, gd.gravity, O_NITRO_PACK_F);
        break;
    case O_NITRO_PACK_F:
        if (!gd.gravity_disabled) {
            if (is_like_space(x, y, gd.gravity))
                move(x, y, gd.gravity, O_NITRO_PACK_F);
            else if (do_fall_try_magic(x, y, gd.gravity, f->magic_nitro_pack_to)) {
            } else if (is_like_dirt(x, y, gd.gravity))
                store(x, y, O_NITRO_PACK);
            else
                explode(x, y);
        }
        left(x, y, EV_FALLING);
        break;
    case O_NITRO_PACK_EXPLODE:
        explode(x, y);
        break;
    case O_COW_1:
    case O_COW_2:
    case O_COW_3:
    case O_COW_4:
        if (!is_like_space(x, y, MV_UP) && !is_like_space(x, y, MV_DOWN) && !is_like_space(x, y, MV_LEFT) &&
            !is_like_space(x, y, MV_RIGHT))
            store(x, y, O_COW_ENCLOSED_1);
        else
            creature_move(x, y, O_COW_1);
        break;
    case O_COW_ENCLOSED_1:
    case O_COW_ENCLOSED_2:
    case O_COW_ENCLOSED_3:
    case O_COW_ENCLOSED_4:
    case O_COW_ENCLOSED_5:
    case O_COW_ENCLOSED_6:
    case O_COW_ENCLOSED_7:
        if (is_like_space(x, y, MV_UP) || is_like_space(x, y, MV_LEFT) || is_like_space(x, y, MV_RIGHT) ||
            is_like_space(x, y, MV_DOWN))
            store(x, y, O_COW_1);
        else if (e == O_COW_ENCLOSED_7)
            store(x, y, O_SKELETON);
        else
            next(x, y);
        break;
    case O_FIREFLY_1:
    case O_FIREFLY_2:
    case O_FIREFLY_3:
    case O_FIREFLY_4:
    case O_ALT_FIREFLY_1:
    case O_ALT_FIREFLY_2:
    case O_ALT_FIREFLY_3:
    case O_ALT_FIREFLY_4:
    case O_BUTTER_1:
    case O_BUTTER_2:
    case O_BUTTER_3:
    case O_BUTTER_4:
    case O_ALT_BUTTER_1:
    case O_ALT_BUTTER_2:
    case O_ALT_BUTTER_3:
    case O_ALT_BUTTER_4:
    case O_STONEFLY_1:
    case O_STONEFLY_2:
    case O_STONEFLY_3:
    case O_STONEFLY_4:
        if (touches(x, y, O_VOODOO))
            gd.voodoo_touched = true;
        if (flies_blow_up(x, y))
            explode(x, y);
        else
            creature_move(x, y, e >= O_FIREFLY_1 && e <= O_FIREFLY_4 ? O_FIREFLY_1
                              : e >= O_BUTTER_1 && e <= O_BUTTER_4 ? O_BUTTER_1
                              : e >= O_STONEFLY_1 && e <= O_STONEFLY_4 ? O_STONEFLY_1
                              : e >= O_ALT_FIREFLY_1 && e <= O_ALT_FIREFLY_4 ? O_ALT_FIREFLY_1
                              : O_ALT_BUTTER_1);
        break;
    case O_WAITING_STONE: {
        uint8_t gc = grav_compat();
        if (is_like_space(x, y, gc)) {
            move(x, y, gc, O_CHASING_STONE);
        } else if (sloped(x, y, gc, opposite[gc])) {
            if (sloped(x, y, gc, cw_fourth[gc]) && is_like_space(x, y, cw_fourth[gc]) &&
                is_like_space(x, y, cw_eighth[gc]))
                move(x, y, cw_fourth[gc], O_WAITING_STONE);
            else if (sloped(x, y, gc, ccw_fourth[gc]) && is_like_space(x, y, ccw_fourth[gc]) &&
                     is_like_space(x, y, ccw_eighth[gc]))
                move(x, y, ccw_fourth[gc], O_WAITING_STONE);
        }
        break;
    }
    case O_CHASING_STONE:
        chasing_stone(x, y);
        left(x, y, EV_CHASING_STONE);
        break;
    case O_REPLICATOR:
        if (gd.replicators_wait_frame == 0 && flag(GDF_REPLICATORS_ACTIVE) && !gd.gravity_disabled) {
            if (is_like_space(x, y, gd.gravity) && !is_player_dir(x, y, opposite[gd.gravity]) &&
                !is_scanned_dir(x, y, opposite[gd.gravity]))
                store_dir(x, y, gd.gravity, get_dir(x, y, opposite[gd.gravity])), SOUND(SND_GROW);
        }
        break;
    case O_BITER_1:
    case O_BITER_2:
    case O_BITER_3:
    case O_BITER_4:
        if (gd.biters_wait_frame == 0) {
            biter(x, y);
            left(x, y, EV_BITER);
        }
        break;
    case O_DRAGONFLY_1:
    case O_DRAGONFLY_2:
    case O_DRAGONFLY_3:
    case O_DRAGONFLY_4:
        if (touches(x, y, O_VOODOO))
            gd.voodoo_touched = true;
        if (flies_blow_up(x, y)) {
            explode(x, y);
        } else {
            bool ccw = rotates_ccw(x, y);
            uint8_t dir = e - O_DRAGONFLY_1, dirn;
            const uint8_t *cm = flag(GDF_CREATURES_BACKWARDS) ? creature_chdir : creature_dir;
            if (flag(GDF_CREATURES_BACKWARDS))
                ccw = !ccw;
            dirn = ccw ? (dir + 3) & 3 : (dir + 1) & 3;
            if (is_like_space(x, y, cm[dir])) {
                move(x, y, cm[dir], O_DRAGONFLY_1 + dir);
                event(x, y, EV_DRAGONFLY);
            } else
                store(x, y, O_DRAGONFLY_1 + dirn);
        }
        break;
    case O_BLADDER:
        store(x, y, O_BLADDER_1);
        break;
    case O_BLADDER_1:
    case O_BLADDER_2:
    case O_BLADDER_3:
    case O_BLADDER_4:
    case O_BLADDER_5:
    case O_BLADDER_6:
    case O_BLADDER_7:
    case O_BLADDER_8:
        bladder(x, y);
        left(x, y, EV_BLADDER);
        break;
    case O_GHOST:
        if (flies_blow_up(x, y)) {
            explode(x, y);
        } else {
            static const uint8_t dirs[] = {MV_UP, MV_DOWN, MV_LEFT, MV_RIGHT};
            for (uint8_t i = 0; i < 4; i++) {
                uint8_t random_dir = dirs[rand_below(4)];
                if (is_like_space(x, y, random_dir)) {
                    move(x, y, random_dir, O_GHOST);
                    event(x, y, EV_GHOST);
                    break;
                }
            }
        }
        break;
    case O_AMOEBA:
        if (gd.hatched && gd.amoeba_state == GD_AM_AWAKE)
            SOUND(SND_AMOEBA);
        if (gd.convert_amoeba_this_frame && sc_amoeba_found_enclosed) {
            store(x, y, f->amoeba_enclosed_effect);
            break;
        }
        sc_amoeba_count++;
        switch (gd.amoeba_state) {
        case GD_AM_TOO_BIG:
            store(x, y, f->amoeba_too_big_effect);
            break;
        case GD_AM_ENCLOSED:
            store(x, y, f->amoeba_enclosed_effect);
            break;
        default:
            if (sc_amoeba_found_enclosed && amoeba_has_room(x, y)) {
                sc_amoeba_found_enclosed = false;
                gd.amoeba_state = GD_AM_AWAKE;
            }
            if (gd.amoeba_state == GD_AM_AWAKE && chance(gd.amoeba_growth_prob))
                amoeba_grow(x, y, O_AMOEBA);
            break;
        }
        break;
    case O_AMOEBA_2:
        if (gd.hatched && gd.amoeba_2_state == GD_AM_AWAKE)
            SOUND(SND_AMOEBA);
        sc_amoeba_2_count++;
        if (flag(GDF_AMOEBA_2_EXPLODES_BY_AMOEBA) &&
            (is_like_element(x, y, MV_DOWN, O_AMOEBA) || is_like_element(x, y, MV_UP, O_AMOEBA) ||
             is_like_element(x, y, MV_LEFT, O_AMOEBA) || is_like_element(x, y, MV_RIGHT, O_AMOEBA))) {
            explode(x, y);
        } else {
            switch (gd.amoeba_2_state) {
            case GD_AM_TOO_BIG:
                store(x, y, f->amoeba_2_too_big_effect);
                break;
            case GD_AM_ENCLOSED:
                store(x, y, f->amoeba_2_enclosed_effect);
                break;
            default:
                if (sc_amoeba_2_found_enclosed && amoeba_has_room(x, y)) {
                    sc_amoeba_2_found_enclosed = false;
                    gd.amoeba_2_state = GD_AM_AWAKE;
                }
                if (gd.amoeba_2_state == GD_AM_AWAKE && chance(gd.amoeba_2_growth_prob))
                    amoeba_grow(x, y, O_AMOEBA_2);
                break;
            }
        }
        break;
    case O_ACID:
        if (chance(f->acid_spread_ratio + 1)) {  // rand_below(1000000) <= ratio
            SOUND(SND_HISS);
            store(x, y, f->acid_turns_to);
            if (is_like_element(x, y, MV_UP, f->acid_eats_this))
                store_dir(x, y, MV_UP, O_ACID);
            if (is_like_element(x, y, MV_DOWN, f->acid_eats_this))
                store_dir(x, y, MV_DOWN, O_ACID);
            if (is_like_element(x, y, MV_LEFT, f->acid_eats_this))
                store_dir(x, y, MV_LEFT, O_ACID);
            if (is_like_element(x, y, MV_RIGHT, f->acid_eats_this))
                store_dir(x, y, MV_RIGHT, O_ACID);
        }
        break;
    case O_WATER:
        if (!flag(GDF_WATER_DOES_NOT_FLOW_DOWN) && is_like_space(x, y, MV_DOWN))
            store_dir(x, y, MV_DOWN, O_WATER_1), SOUND(SND_HISS);
        if (is_like_space(x, y, MV_UP))
            store_dir(x, y, MV_UP, O_WATER_1), SOUND(SND_HISS);
        if (is_like_space(x, y, MV_LEFT))
            store_dir(x, y, MV_LEFT, O_WATER_1), SOUND(SND_HISS);
        if (is_like_space(x, y, MV_RIGHT))
            store_dir(x, y, MV_RIGHT, O_WATER_1), SOUND(SND_HISS);
        break;
    case O_WATER_16:
        store(x, y, O_WATER);
        break;
    case O_H_EXPANDING_WALL:
    case O_V_EXPANDING_WALL:
    case O_H_EXPANDING_STEEL_WALL:
    case O_V_EXPANDING_STEEL_WALL:
        if (((e == O_H_EXPANDING_WALL || e == O_H_EXPANDING_STEEL_WALL) && !flag(GDF_EXPANDING_WALL_CHANGED)) ||
            ((e == O_V_EXPANDING_WALL || e == O_V_EXPANDING_STEEL_WALL) && flag(GDF_EXPANDING_WALL_CHANGED)))
            expanding(x, y, MV_LEFT, MV_RIGHT);
        else
            expanding(x, y, MV_UP, MV_DOWN);
        break;
    case O_EXPANDING_WALL:
    case O_EXPANDING_STEEL_WALL:
        if (is_like_space(x, y, MV_LEFT))
            store_dir(x, y, MV_LEFT, e), SOUND(SND_GROW);
        if (is_like_space(x, y, MV_RIGHT))
            store_dir(x, y, MV_RIGHT, e), SOUND(SND_GROW);
        if (is_like_space(x, y, MV_UP))
            store_dir(x, y, MV_UP, e), SOUND(SND_GROW);
        if (is_like_space(x, y, MV_DOWN))
            store_dir(x, y, MV_DOWN, e), SOUND(SND_GROW);
        break;
    case O_SLIME:
        slime(x, y);
        break;
    case O_FALLING_WALL: {
        uint8_t gc = grav_compat();
        if (is_like_space(x, y, gc)) {
            int8_t yy;
            for (yy = y + 1; yy < y + gd.h; yy++)
                if (!is_like_space(x, yy, MV_STILL))
                    break;
            uint16_t below = get(x, yy);
            if (below == O_PLAYER || below == O_PLAYER_GLUED || below == O_PLAYER_BOMB)
                move(x, y, gc, O_FALLING_WALL_F);
        }
        break;
    }
    case O_FALLING_WALL_F: {
        uint8_t gc = grav_compat();
        if (is_player_dir(x, y, gc))
            explode(x, y);
        else if (is_like_space(x, y, gc))
            move(x, y, gc, O_FALLING_WALL_F);
        else
            store(x, y, O_FALLING_WALL);
        left(x, y, EV_FALLING);
        break;
    }
    case O_CONVEYOR_RIGHT:
    case O_CONVEYOR_LEFT:
        conveyor(x, y);
        break;
    case O_ROCKET_1:
        rocket(x, y, MV_RIGHT, O_ROCKET_1);
        left(x, y, EV_ROCKET);
        break;
    case O_ROCKET_2:
        rocket(x, y, MV_UP, O_ROCKET_2);
        left(x, y, EV_ROCKET);
        break;
    case O_ROCKET_3:
        rocket(x, y, MV_LEFT, O_ROCKET_3);
        left(x, y, EV_ROCKET);
        break;
    case O_ROCKET_4:
        rocket(x, y, MV_DOWN, O_ROCKET_4);
        left(x, y, EV_ROCKET);
        break;
    case O_EXPLODE_3:
        store(x, y, f->explosion_3_effect);
        break;
    case O_EXPLODE_5:
        store(x, y, f->explosion_effect);
        break;
    case O_NUT_CRACK_4:
        store(x, y, O_DIAMOND);
        break;
    case O_PRE_DIA_5:
        store(x, y, f->diamond_birth_effect);
        break;
    case O_PRE_STONE_4:
        store(x, y, O_STONE);
        break;
    case O_NITRO_EXPL_4:
        store(x, y, f->nitro_explosion_effect);
        break;
    case O_BOMB_EXPL_4:
        store(x, y, f->bomb_explosion_effect);
        break;
    case O_AMOEBA_2_EXPL_4:
        store(x, y, f->amoeba_2_explosion_effect);
        break;
    case O_GHOST_EXPL_4:
        store(x, y, ghost_explode_to[rand_below(16)]);
        break;
    case O_PRE_STEEL_4:
        store(x, y, O_STEEL);
        break;
    case O_PRE_CLOCK_4:
        store(x, y, O_CLOCK);
        break;
    case O_BOMB_TICK_7:
        explode(x, y);
        break;
    case O_TRAPPED_DIAMOND:
        if (gd.diamond_key_collected)
            store(x, y, O_DIAMOND);
        break;
    case O_PRE_OUTBOX:
        if (gd.gate_open)
            store(x, y, O_OUTBOX);
        break;
    case O_PRE_INVIS_OUTBOX:
        if (gd.gate_open)
            store(x, y, O_INVIS_OUTBOX);
        break;
    case O_INBOX:
        gd.player_seen_ago = 0;
        if (gd.hatched && !sc_inbox_toggle)
            store(x, y, O_PRE_PL_1);
        sc_inbox_toggle = !sc_inbox_toggle;
        break;
    case O_PRE_PL_1:
        gd.player_seen_ago = 0;
        store(x, y, O_PRE_PL_2);
        break;
    case O_PRE_PL_2:
        gd.player_seen_ago = 0;
        store(x, y, O_PRE_PL_3);
        break;
    case O_PRE_PL_3:
        gd.player_seen_ago = 0;
        store(x, y, O_PLAYER);
        break;
    case O_PRE_DIA_1:
    case O_PRE_DIA_2:
    case O_PRE_DIA_3:
    case O_PRE_DIA_4:
    case O_PRE_STONE_1:
    case O_PRE_STONE_2:
    case O_PRE_STONE_3:
    case O_BOMB_TICK_1:
    case O_BOMB_TICK_2:
    case O_BOMB_TICK_3:
    case O_BOMB_TICK_4:
    case O_BOMB_TICK_5:
    case O_BOMB_TICK_6:
    case O_PRE_STEEL_1:
    case O_PRE_STEEL_2:
    case O_PRE_STEEL_3:
    case O_BOMB_EXPL_1:
    case O_BOMB_EXPL_2:
    case O_BOMB_EXPL_3:
    case O_NUT_CRACK_1:
    case O_NUT_CRACK_2:
    case O_NUT_CRACK_3:
    case O_GHOST_EXPL_1:
    case O_GHOST_EXPL_2:
    case O_GHOST_EXPL_3:
    case O_EXPLODE_1:
    case O_EXPLODE_2:
    case O_EXPLODE_4:
    case O_PRE_CLOCK_1:
    case O_PRE_CLOCK_2:
    case O_PRE_CLOCK_3:
    case O_NITRO_EXPL_1:
    case O_NITRO_EXPL_2:
    case O_NITRO_EXPL_3:
    case O_AMOEBA_2_EXPL_1:
    case O_AMOEBA_2_EXPL_2:
    case O_AMOEBA_2_EXPL_3:
    case O_WATER_1:
    case O_WATER_2:
    case O_WATER_3:
    case O_WATER_4:
    case O_WATER_5:
    case O_WATER_6:
    case O_WATER_7:
    case O_WATER_8:
    case O_WATER_9:
    case O_WATER_10:
    case O_WATER_11:
    case O_WATER_12:
    case O_WATER_13:
    case O_WATER_14:
    case O_WATER_15:
        next(x, y);
        break;
    case O_BLADDER_SPENDER: {
        uint8_t up = opposite[grav_compat()];
        if (is_like_space(x, y, up)) {
            store_dir(x, y, up, O_BLADDER);
            SOUND(SND_SLIME);
            store(x, y, O_PRE_STEEL_1);
        }
        break;
    }
    case O_MAGIC_WALL:
        if (gd.magic_wall_state == GD_MW_ACTIVE)
            SOUND(SND_MAGIC);
        break;
    }
    PROF_END
}

void scan_cells(uint8_t ymin, uint8_t ymax, uint8_t w);

#ifndef GD_FAR
// The scan of rows ymin-ymax, w cells each, in GDash's order: each cell not
// scanned yet whose element does something goes to scan_cell, and all are
// unscanned. Space, dirt and walls do nothing and add no delay. On the
// MEGA65 this is src/gdscan.s.
void scan_cells(uint8_t ymin, uint8_t ymax, uint8_t w) {
    _Static_assert(CAVE_W % 8 == 0, "a row starts a byte of gd_scanned[]");
    for (uint8_t y = ymin; y <= ymax; y++) {
        const uint8_t *row = cave + row_at[y];
        uint8_t *srow = gd_scanned + row_at[y] / 8;
        uint16_t row_ckdelay = 0;  // at most 40 x 518
        for (uint8_t x = 0; x < w; x++) {
            uint8_t e = row[x];
            uint8_t *sp = srow + (x >> 3), bit = bit_of[x & 7];
            if (e > O_DIRT && e != O_BRICK && e != O_STEEL && !(*sp & bit)) {
                row_ckdelay += gd_ckdelay[e];
                scan_cell(x, y, e);
            }
            *sp &= ~bit;  // unscan(x, y)
        }
        gd_scan_ckdelay += row_ckdelay;
    }
}
#endif

// ---------------------------------------------------------------- a step

// Milliseconds per step, as GDash computes them for each scheduling
// (update_scheduling): for the C64's, from the cave's delay and what it has
static void update_scheduling(void) {
    int32_t cur = gd.ckdelay_current + gd.ckdelay_extra_for_animation, ck = gd.f->ckdelay;
    bool inter = flag(GDF_INTERMISSION);
    switch (gd.f->scheduling) {
    case 1:  // bd1: 88 ms + 3.66 per delay unit (60 for intermissions)
        gd.speed = (inter ? 60 : 88) + (366 * ck) / 100 + cur / 1000;
        break;
    case 5:  // bd1atari
        gd.speed = inter ? 65 + (288 * ck) / 100 + gd.ckdelay_current / 1000
                         : 74 + (320 * ck) / 100 + gd.ckdelay_current / 1000;
        break;
    case 2:  // bd2
        gd.speed = 60 + cur / 1000 > ck * 20 ? 60 + cur / 1000 : ck * 20;
        break;
    case 3:  // plck
        gd.speed = 65 + gd.ckdelay_current / 1000 > ck * 20 ? 65 + gd.ckdelay_current / 1000 : ck * 20;
        break;
    case 6:  // bd2ckatari
        gd.speed = 40 + gd.ckdelay_current / 1000 > ck * 20 ? 40 + gd.ckdelay_current / 1000 : ck * 20;
        break;
    case 4:  // crdr7
        cur = gd.ckdelay_current;
        if (flag(GDF_HAMMERED_WALLS_REAPPEAR))
            cur += 60000;
        gd.speed = 130 + cur / 1000 > ck * 20 ? 130 + cur / 1000 : ck * 20;
        break;
    }
}

// What GDash adds to the C64's time for animated elements (2.6 ms each kind)
static void ckdelay_extra(void) {
    bool amoeba = false, firefly = false, butterfly = false;
    gd.ckdelay_current = 0;
    for (uint8_t y = 0; y < gd.h; y++)
        for (uint8_t x = 0; x < gd.w; x++) {
            uint8_t e = cave[(uint16_t)y * CAVE_W + x];
            gd.ckdelay_current += gd_ckdelay[e];
            if (e >= O_FIREFLY_1 && e <= O_FIREFLY_4)
                firefly = true;
            else if (e >= O_BUTTER_1 && e <= O_BUTTER_4)
                butterfly = true;
            else if (e == O_AMOEBA)
                amoeba = true;
        }
    gd.ckdelay_extra_for_animation = 2600 * (amoeba * 2 + firefly + butterfly);
}

// The last inbox (inbox) or player in the cave, from the top left
// The last one in the cave, or the first with GDF_ACTIVE_IS_FIRST_FOUND
// (GDash searches backwards for that); no cell is scanned here
static void find_player(bool inbox) {
    bool first = flag(GDF_ACTIVE_IS_FIRST_FOUND);
#ifdef GD_FAR
    if (!inbox) {  // src/gdscan.s, by gd_class[]
        if (gd_find_player(first)) {
            gd.player_x = gd_found_x;
            gd.player_y = gd_found_y;
        }
        return;
    }
#endif
    for (int8_t y = 0; y < gd.h; y++) {
        const uint8_t *row = cave + (uint16_t)y * CAVE_W;
        for (int8_t x = 0; x < gd.w; x++) {
            uint8_t e = row[x];
            if (inbox ? e == O_INBOX : (gd_flags[e] & P_PLAYER) != 0) {
                gd.player_x = x;
                gd.player_y = y;
                if (first)
                    return;
            }
        }
    }
}

#ifdef GD_FAR
// What the engine keeps in the zero page with a value (gdengine.ld): no
// start-up routine copies it there, the first gd_start does
extern char __zp_data_load_start[], __zp_data_start[], __zp_data_size[];
#endif

void gd_start(const GdCaveFile *f, uint32_t seed) {
#ifdef GD_FAR
    memcpy(__zp_data_start, __zp_data_load_start, (uint16_t)__zp_data_size);
#endif
    memset(&gd, 0, sizeof gd);
#if defined(GD_FAR) && defined(GDPROF_ENGINE)
    memset((void *)gd_prof, 0, sizeof gd_prof);
#endif
#ifdef GD_FAR
    set_classes();
#endif
    gd.f = f;
    gd.w = f->w;
    gd.h = f->h;
    gd.flags = f->flags;
    gd.amoeba_state = gd.amoeba_2_state = GD_AM_SLEEPING;
    gd.magic_wall_state = GD_MW_DORMANT;
    gd.player_state = GD_PL_NOT_YET;
    gd.time = f->time;
    gd.diamonds_needed = f->diamonds_needed;
    gd.diamond_value = f->diamond_value;
    gd.magic_wall_time = f->magic_wall_time;
    gd.amoeba_time = f->amoeba_time;
    gd.amoeba_2_time = f->amoeba_2_time;
    gd.hatching_delay_time = f->hatching_delay_time;
    gd.hatching_delay_frame = f->hatching_delay_frame;
    gd.amoeba_growth_prob = f->amoeba_growth_prob;
    gd.amoeba_2_growth_prob = f->amoeba_2_growth_prob;
    gd.biter_delay_frame = f->biter_delay_frame;
    gd.gravity = f->gravity;
    gd.speed = f->scheduling ? 120 : f->speed;
    c64_seed_1 = f->c64_seed_1;
    c64_seed_2 = f->c64_seed_2;
    rand_seed(seed);
    memcpy(cave, f->map, CAVE_SIZE);
    memset(gd_scanned, 0, sizeof gd_scanned);
    memset(hammered, 0, sizeof hammered);
    clear_moved();

    // setup_for_game: where the player will be, the time in "milliseconds",
    // the speed
    find_player(true);
    for (uint8_t i = 0; i < 16; i++) {
        gd.player_x_mem[i] = gd.player_x;
        gd.player_y_mem[i] = gd.player_y;
    }
    gd.timing_factor = flag(GDF_PAL_TIMING) ? 1200 : 1000;
    gd.time *= gd.timing_factor;
    gd.magic_wall_time *= gd.timing_factor;
    gd.amoeba_time *= gd.timing_factor;
    gd.amoeba_2_time *= gd.timing_factor;
    gd.hatching_delay_time *= gd.timing_factor;
    ckdelay_extra();
    update_scheduling();
}

uint16_t gd_time_visible(void) {
    return (gd.time + gd.timing_factor - 1) / gd.timing_factor;
}

// Count the diamonds when asked for "all but n" (diamonds needed <= 0)
static void count_diamonds(void) {
    if (gd.diamonds_needed > 0)
        return;
    for (uint8_t y = 0; y < gd.h; y++)
        for (uint8_t x = 0; x < gd.w; x++)
            switch (cave[(uint16_t)y * CAVE_W + x]) {
            case O_DIAMOND:
            case O_DIAMOND_F:
            case O_FLYING_DIAMOND:
            case O_FLYING_DIAMOND_F:
                gd.diamonds_needed++;
                break;
            case O_SKELETON:
                gd.diamonds_needed += gd.f->skeletons_worth_diamonds;
                break;
            }
    if (gd.diamonds_needed < 0)
        gd.diamonds_needed = 0;
}

static int32_t count_down(int32_t t) {
    t -= gd.speed;
    return t < 0 ? 0 : t;
}


// A step in three parts, so the program can show its frames while a step
// that takes long is made (main.c): gd_step_begin, gd_step_rows as long as
// there is time, gd_step_end (which gd_step_rows calls after the last row).
// gd_iterate is all of them at once.
static uint8_t st_y, st_ymax;   // the next row of the scan, and its last
#ifdef GD_FAR
// the most raster lines a row took in this step, and gd_step_end in any step
static uint8_t st_most[2] = {0, 40};
static uint16_t st_end, st_lines;  // gd_step_rows' end and lines
#endif

// The player's input for scan_cell (MV_* | 0x80 for fire): without
// diagonals unless the cave has them
__attribute__((noinline)) static void step_input(uint8_t input) {
    uint8_t player_move = input & 0x7F;
    sc_fire = (input & 0x80) != 0;
    if (!flag(GDF_DIAGONAL_MOVEMENTS)) {
        if (player_move == MV_UP_RIGHT || player_move == MV_DOWN_RIGHT)
            player_move = MV_RIGHT;
        else if (player_move == MV_UP_LEFT || player_move == MV_DOWN_LEFT)
            player_move = MV_LEFT;
    }
    sc_move = player_move;
}

__attribute__((noinline)) void gd_step_begin(uint8_t player_move, bool player_fire, bool suicide) {
    prof_mark(255);
    gd.sound = 0;
    gd.nevents = 0;
    clear_moved();
    step_input(player_move | (player_fire ? 0x80 : 0));
    st_taken = false;
    if (gd.player_seen_ago < 100)
        gd.player_seen_ago++;
    if (gd.pneumatic_hammer_active_delay > 0)
        gd.pneumatic_hammer_active_delay--;
    gd.inbox_flash_toggle = !gd.inbox_flash_toggle;
    if (gd.gate_open_flash > 0)
        gd.gate_open_flash--;
    gd.score = 0;
    gd.convert_amoeba_this_frame = false;
    if (suicide && gd.player_state == GD_PL_LIVING && is_player(gd.player_x, gd.player_y))
        store(gd.player_x, gd.player_y, O_EXPLODE_1);
    if (flag(GDF_HAMMERED_WALLS_REAPPEAR))
        for (uint8_t y = 0; y < gd.h; y++)
            for (uint8_t x = 0; x < gd.w; x++) {
                uint16_t i = (uint16_t)y * CAVE_W + x;
                if (hammered[i] > 0 && --hammered[i] == 0)
                    store(x, y, O_BRICK), SOUND(SND_GROW);
            }
    gd.ckdelay_current = 0;
    sc_inbox_toggle = gd.inbox_flash_toggle;
    sc_amoeba_found_enclosed = true;
    sc_amoeba_2_found_enclosed = true;
    sc_amoeba_count = 0;
    sc_amoeba_2_count = 0;
    gd_scan_ckdelay = 0;
    if (flag(GDF_BORDER_SCAN_FIRST_AND_LAST)) {
        st_y = 0;
        st_ymax = gd.h - 1;
    } else {
        st_y = 1;
        st_ymax = gd.h - 2;
    }
#ifdef GD_FAR
    st_most[0] = 4;
#endif
    prof_mark(0);
}

#ifdef GD_FAR
// The raster lines from the physical raster line now to st_end, in a frame
// of st_lines; 0 once it is past (the windows the program gives are shorter
// than st_lines - 64). No lines: no end (gd_check).
__attribute__((noinline)) static uint16_t lines_left(void) {
    uint16_t end = st_end, lines = st_lines;
    if (!lines)
        return 0x7FFF;
    volatile uint8_t *const io = (volatile uint8_t *)0xD000;
    uint8_t lo, hi;
    do {
        hi = io[0x53];
        lo = io[0x52];
    } while (hi != io[0x53]);
    uint16_t r = (uint16_t)(hi & 7) << 8 | lo;
    uint16_t left = end >= r ? end - r : end + lines - r;
    return left > lines - 64 ? 0 : left;
}
#endif

// Rows of the scan while the raster is before `end` (raster lines, a frame
// of `lines`; on the host all of them), with the player's input (MV_* and
// fire: 0x80) for as long as he has not taken it; then gd_step_end. Bit 0
// of the result: the step is made; bit 1: the player has taken the input.
__attribute__((noinline)) uint8_t gd_step_rows(uint8_t input, uint16_t end, uint16_t lines) {
    if (!st_taken)
        step_input(input);
#ifdef GD_FAR
    st_end = end;
    st_lines = lines;
#else
    (void)end;
    (void)lines;
#endif
    for (;;) {
        bool last = st_y > st_ymax;  // the rows are done: gd_step_end
#ifdef GD_FAR
        uint16_t before = lines_left();
        if (before < (uint16_t)st_most[last] + 8)
            return st_taken ? 2 : 0;
#endif
        if (last)
            gd_step_end();
        else
            scan_cells(st_y, st_y, gd.w);
#ifdef GD_FAR
        uint16_t took = before - lines_left();
        if (took > st_most[last])
            st_most[last] = took > 250 ? 250 : took;
#endif
        if (last)
            return st_taken ? 3 : 1;
        st_y++;
    }
}

__attribute__((noinline)) void gd_step_end(void) {
    const GdCaveFile *f = gd.f;
    bool amoeba_found_enclosed, amoeba_2_found_enclosed;
    uint16_t amoeba_count, amoeba_2_count;
    bool start_signal = false;
    int16_t time_decrement_sec = 0;

    gd.ckdelay_current += gd_scan_ckdelay;
    amoeba_found_enclosed = sc_amoeba_found_enclosed;
    amoeba_2_found_enclosed = sc_amoeba_2_found_enclosed;
    amoeba_count = sc_amoeba_count;
    amoeba_2_count = sc_amoeba_2_count;

    // forget the scanned marks; a destroyed voodoo costs time
#ifdef GD_FAR
    // what the cave has, for the passes below; and where the player is
    uint8_t classes = gd_cave_classes(flag(GDF_ACTIVE_IS_FIRST_FOUND));
    bool changed = false;  // the cave since: then gd_found_x, gd_found_y are no longer right
    gd_clear_scanned();
#else
    uint8_t classes = 0xFF;
    memset(gd_scanned, 0, sizeof gd_scanned);
#endif
    if (classes & GDC_PENALTY)
        for (uint8_t y = 0; y < gd.h; y++) {
            const uint8_t *row = cave + row_at[y];
            for (uint8_t x = 0; x < gd.w; x++)
                if (row[x] == O_TIME_PENALTY) {
                    store(x, y, O_GRAVESTONE);
                    time_decrement_sec += f->time_penalty;
#ifdef GD_FAR
                    changed = true;
#endif
                }
        }
#ifdef GD_FAR
    gd_clear_scanned();
#else
    memset(gd_scanned, 0, sizeof gd_scanned);
#endif
    _Static_assert(P_EXPLOSION_FIRST_STAGE <= 0xFFFF, "in the low half of gd_flags[]");
    if (flag(GDF_SHORT_EXPLOSIONS) && (classes & GDC_FIRST_STAGE))
        for (uint8_t y = 0; y < gd.h; y++) {
            const uint8_t *row = cave + row_at[y];
            for (uint8_t x = 0; x < gd.w; x++) {
                uint8_t e = row[x];
                if (e > O_DIRT && e != O_BRICK && e != O_STEEL &&  // most of a cave
                    ((uint16_t)gd_flags[e] & (uint16_t)P_EXPLOSION_FIRST_STAGE)) {
                    next(x, y);
#ifdef GD_FAR
                    changed = true;
#endif
                }
            }
        }
    prof_mark(2);
    if (gd.player_state == GD_PL_LIVING) {
#ifdef GD_FAR
        if (!changed) {  // as gd_cave_classes found it
            if (classes & GDC_PLAYER) {
                gd.player_x = gd_found_x;
                gd.player_y = gd_found_y;
            }
        } else
#endif
            find_player(false);
    }
    prof_mark(3);
    memmove(gd.player_x_mem, gd.player_x_mem + 1, 15);
    memmove(gd.player_y_mem, gd.player_y_mem + 1, 15);
    gd.player_x_mem[15] = gd.player_x;
    gd.player_y_mem[15] = gd.player_y;

    update_scheduling();

    if ((gd.player_state == GD_PL_LIVING && gd.player_seen_ago > 15) || gd.kill_player)
        gd.player_state = GD_PL_DIED;
    if (gd.voodoo_touched)
        gd.kill_player = true;
    if (gd.amoeba_state == GD_AM_AWAKE) {
        if (amoeba_count >= f->amoeba_max_count)
            gd.amoeba_state = GD_AM_TOO_BIG;
        if (amoeba_found_enclosed)
            gd.amoeba_state = GD_AM_ENCLOSED;
    }
    if (flag(GDF_MAGIC_WALL_STOPS_AMOEBA) && gd.magic_wall_state == GD_MW_ACTIVE)
        gd.amoeba_state = GD_AM_ENCLOSED;
    if (gd.amoeba_2_state == GD_AM_AWAKE) {
        if (amoeba_2_count >= f->amoeba_2_max_count)
            gd.amoeba_2_state = GD_AM_TOO_BIG;
        if (amoeba_2_found_enclosed)
            gd.amoeba_2_state = GD_AM_ENCLOSED;
    }
    if (flag(GDF_MAGIC_WALL_STOPS_AMOEBA) && gd.magic_wall_state == GD_MW_ACTIVE)
        gd.amoeba_2_state = GD_AM_ENCLOSED;

    gd.time -= (int32_t)time_decrement_sec * gd.timing_factor;
    if (gd.time < 0)
        gd.time = 0;
    if (gd.hatched)
        gd.time = count_down(gd.time);
    if (gd.gravity_will_change > 0) {
        gd.gravity_will_change = count_down(gd.gravity_will_change);
        if (gd.gravity_will_change == 0)
            gd.gravity = gd.gravity_next_direction, SOUND(SND_SWITCH);
    }
    if (gd.creatures_direction_will_change > 0) {
        gd.creatures_direction_will_change = count_down(gd.creatures_direction_will_change);
        if (gd.creatures_direction_will_change == 0) {
            gd.flags ^= GDF_CREATURES_BACKWARDS;
            gd.creatures_direction_will_change = (int32_t)f->creatures_direction_auto_change_time * gd.timing_factor;
        }
    }
    if (gd.magic_wall_state == GD_MW_ACTIVE && (gd.hatched || !flag(GDF_MAGIC_TIMER_WAIT_FOR_HATCHING)) &&
        !(gd.magic_wall_time == 0 && flag(GDF_MAGIC_TIMER_ZERO_IS_INFINITE))) {
        gd.magic_wall_time = count_down(gd.magic_wall_time);
        if (gd.magic_wall_time == 0)
            gd.magic_wall_state = GD_MW_EXPIRED;
    }
    if (flag(GDF_AMOEBA_TIMER_STARTED_IMMEDIATELY) ||
        (gd.amoeba_state == GD_AM_AWAKE && (gd.hatched || !flag(GDF_AMOEBA_TIMER_WAIT_FOR_HATCHING)))) {
        gd.amoeba_time = count_down(gd.amoeba_time);
        if (gd.amoeba_time == 0)
            gd.amoeba_growth_prob = f->amoeba_fast_growth_prob;
    }
    if (flag(GDF_AMOEBA_TIMER_STARTED_IMMEDIATELY) ||
        (gd.amoeba_2_state == GD_AM_AWAKE && (gd.hatched || !flag(GDF_AMOEBA_TIMER_WAIT_FOR_HATCHING)))) {
        gd.amoeba_2_time = count_down(gd.amoeba_2_time);
        if (gd.amoeba_2_time == 0)
            gd.amoeba_2_growth_prob = f->amoeba_2_fast_growth_prob;
    }
    if (f->scheduling == 0) {
        if (gd.hatching_delay_frame > 0 && --gd.hatching_delay_frame == 0)
            start_signal = true;
    } else if (gd.hatching_delay_time > 0) {
        gd.hatching_delay_time -= gd.speed;
        if (gd.hatching_delay_time <= 0) {
            gd.hatching_delay_time = 0;
            start_signal = true;
        }
    }
    if (start_signal) {
        gd.hatched = true;
        count_diamonds();
        if (f->creatures_direction_auto_change_time) {
            gd.creatures_direction_will_change = (int32_t)f->creatures_direction_auto_change_time * gd.timing_factor;
            if (flag(GDF_CREATURES_DIRECTION_AUTO_CHANGE_ON_START))
                gd.flags ^= GDF_CREATURES_BACKWARDS;
        }
        if (gd.player_state == GD_PL_NOT_YET)
            gd.player_state = GD_PL_LIVING;
    }
    if (gd.biters_wait_frame == 0)
        gd.biters_wait_frame = gd.biter_delay_frame;
    else
        gd.biters_wait_frame--;
    if (gd.replicators_wait_frame == 0)
        gd.replicators_wait_frame = f->replicator_delay_frame;
    else
        gd.replicators_wait_frame--;
    if (gd.player_state != GD_PL_TIMEOUT && gd.time == 0)
        gd.player_state = GD_PL_TIMEOUT;
    gd.last_direction = sc_move;
    prof_mark(4);
}

#ifndef GD_FAR  // on the MEGA65 the program calls the parts (main.c)
void gd_iterate(uint8_t player_move, bool player_fire, bool suicide) {
    gd_step_begin(player_move, player_fire, suicide);
    while (!(gd_step_rows(player_move | (player_fire ? 0x80 : 0), 0xFFFF, 0) & 1))
        ;
}
#endif
