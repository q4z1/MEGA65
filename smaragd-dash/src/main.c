// Smaragd Dash: a Boulder Dash style game for the MEGA65.
//
// main.c runs the game: the title screen with its music, where the joystick
// picks the level and the cave to start with, and which takes turns with
// the high score table; then the caves: a cave is
// loaded from the disk, uncovered, Rockford hatches, and the cave
// runs in ticks of the cave's speed while the screen is redrawn every frame
// (50 Hz PAL, 60 Hz NTSC). After the game a good score gets three letters
// in the table, as in the arcades. The rules are in engine.c, the display
// in video.c, the table and its file in hiscore.c.
//
// E on the title opens the cave editor: it edits the own caves, which lie
// in slots on the disk (OWN01, OWN02, ...; tools/cavekit.py puts caves from
// GDash there), tries them out and saves them. The title offers them to
// play after the game's caves.
//
// Built with -DSCREENCAST (toolchain/tools/bin/mega65-cast), the game plays
// itself: the title runs for a while, then the caves play the moves that
// tools/solve.c found for them (DEMO01, DEMO02, ... on the disk, loaded with
// each cave), and after the last one the emulator is told to stop, which
// ends the recording.

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "disk.h"
#include "dma.h"
#include "engine.h"
#include "gdengine.h"
#include "gdnew.h"
#include "gfx.h"
#include "hiscore.h"
#include "hw.h"
#include "input.h"
#include "levels.h"
#include "mem.h"
#include "music.h"
#include "sound.h"
#include "version.h"
#include "video.h"

#ifdef SCREENCAST
#include "demo.h"
#ifndef DEMO_LAST
#define DEMO_LAST DEMO_CAVES  // the caves it plays; -DDEMO_LAST=6: the first six
#endif
#endif

#define LIVES       3
#define LIFE_POINTS 500   // an extra life every so many points
#define START_STEP  5     // the title offers caves 1, 6, 11, ... to start with
#define MAX_X       (CAVE_W * 16 - VIEW_W)
#define MAX_Y       (CAVE_H * 16 - VIEW_H)

#define ICON(n) (0x80 + (n))

static uint8_t tiles[CAVE_SIZE];    // tile per cell, for video_render
static uint8_t covered[CAVE_SIZE];  // 1: cell still hidden (start and end)
static bool any_covered;
static uint8_t etile[E_COUNT];      // tile per element, animated
static uint8_t gtile[O_COUNT];      // the same for GDash's elements (gd_tile, gfx.h)

// What moved in the last tick slides from its old cell into the new one
// until the next tick: the rules stay in cells, only the drawing is smooth.
#define MAX_SPRITES 64              // more are drawn in their cells
static Sprite sprites[MAX_SPRITES];
static uint8_t nsprites;

// What is left behind for a moment, on an empty cell: where a firefly was,
// embers that rise and die down quickly; where a butterfly was, a soft
// glitter that fades slowly, calm behind its quick round; crumbs where
// Rockford dug, and dust beside a boulder that lands. Only the drawing
// knows of it.
enum { TR_NONE, TR_EMBERS, TR_GLITTER, TR_CRUMBS, TR_DUST_L, TR_DUST_R };
static const uint8_t trail_first[] = {0, T_EMBERS0, T_GLITTER0, T_CRUMBS0, T_DUSTL0, T_DUSTR0};
static const uint8_t trail_last[] = {0, T_EMBERS3, T_GLITTER3, T_CRUMBS2, T_DUSTL1, T_DUSTR1};
static const uint8_t trail_step[] = {0, 3, 5, 3, 5, 5};  // frames per stage
#define TRAILS 48
static uint16_t trail_cell[TRAILS];
static uint8_t trail_kind[TRAILS];  // TR_*
static uint8_t trail_tile[TRAILS];  // its stage now
static uint8_t trail_wait[TRAILS];  // frames until the next
static uint8_t trail_next;

static bool pal;
static uint8_t frame;
static uint8_t held, pressed;       // IN_* now, and newly pressed this frame
static uint16_t cam_x, cam_y;
static bool scroll_x, scroll_y;
static uint8_t idle;                // Rockford's idle animation
static uint8_t rf_view;             // Rockford's view shown, 0-7 (T_RF_VIEW0)
static uint8_t rf_rest;             // frames he has been standing
static uint8_t rf_foot;             // the foot of his step, flips with every cell
static uint8_t slide;               // pixels the last tick's moves have still to go
static uint8_t flash;               // frames left of the exit flash

static uint8_t lives;
static uint8_t cave_no, level;      // from 0
static uint8_t start_cave, start_level;  // picked on the title; CAVE_COUNT: the own caves
enum { PLAY_CAVES, PLAY_OWN, PLAY_TEST };  // the game's caves, the own ones, one in the editor
static uint8_t play_mode;
static bool show_cursor;            // the editor's, at cur_x, cur_y
static uint8_t cur_x, cur_y;
static uint32_t score;              // before the current cave
static uint32_t next_life;
static bool have_logo;              // the logo file was on the disk

// The cave being played, as loaded from the disk: one of the game's
// (CAVE01-1, ...: its layout is described in tools/mkcave.py), or an own
// one (a slot OWN01, ...: GdCaveFile, tools/cavekit.py; time 0 is an empty
// slot), which GDash's engine plays and which the editor edits here.
// It lies where GDash's engine sees it (shared.ld, mem.h).
typedef union {
    struct {
        uint16_t time;
        uint8_t diamonds, value, extra, amoeba, magic, speed;
        char name[24];
        uint8_t map[CAVE_SIZE];
    } game;
    GdCaveFile own;
} CaveFile;
extern CaveFile file;
_Static_assert(sizeof(CaveFile) <= FILE_SIZE, "the cave reaches the C stack (shared.ld)");
_Static_assert(sizeof(GdState) <= GD_STATE_SIZE, "GdState reaches the cave (shared.ld)");
static CaveDef cave_def;
static uint8_t loaded = 0xFF, loaded_level;  // cave_no and level of file.game
static bool by_gdash;               // the cave plays by GDash's rules (an own one)
static bool have_gdash;             // GDash's engine is there (bank 2)
#ifdef SCREENCAST
static uint8_t demo_moves[DEMO_MAX];  // the cave's moves (DEMOnn, see tools/solve.c)
#endif

#if defined(EDITDEMO) && !defined(EDITTEST)
#define EDITTEST 255  // the editor's video: its script to the end
#endif
#ifdef EDITTEST
// The editor's test (tests/test_editor.sh builds with -DEDITTEST=n): keys
// and joystick come from this script, a step per line: so many frames with
// these IN_* held, the key typed in the first of them. A step of 0 frames
// is a stop: at the n-th, Xemu (with -testing) is told to exit and writes
// its screenshot. Built with -DEDITDEMO, the script is the one of the
// editor's video (tools/record-editor.sh): it plays to its end, or with
// -DEDITTEST=n to its n-th stop, a picture for EDITOR.md (SHOT).
#ifndef TRY_WAIT
#define TRY_WAIT 200  // frames from T until Rockford can walk
#endif
#define STEP1(key) {1, key, 0}, {10, 0, 0}  // a key and a short look
#define MOVE(in)   {2, 0, in}, {10, 0, 0}   // the cursor one cell on
#define PUT        {3, 0, IN_BUTTON}, {16, 0, 0}
#define SHOT       {0, 0, 0}
static const uint8_t test_script[][3] = {
#ifdef EDITDEMO
    {150, 0, 0}, {1, 'E', 0}, {120, 0, 0},                // the title, E: the editor on slot 1
    SHOT,                                                 // 1: editor-cave
    {1, '+', 0}, {120, 0, 0}, {1, '+', 0}, {150, 0, 0},   // loading slots 2 and 3
    SHOT,                                                 // 2: editor-gdash
    {1, '+', 0}, {120, 0, 0},                             // slot 4, empty: a new cave
    SHOT,                                                 // 3: editor-new
    {1, '-', 0}, {60, 0, 0}, {1, '-', 0}, {60, 0, 0}, {1, '-', 0}, {100, 0, 0},  // slot 1 again
    {1, 'H', 0}, {150, 0, 0},                             // the help page
    SHOT,                                                 // 4: editor-help
    {100, 0, 0}, {1, ' ', 0}, {40, 0, 0},
    {1, '6', 0}, {45, 0, 0},                              // three emeralds
    MOVE(IN_RIGHT), PUT, MOVE(IN_RIGHT), PUT, MOVE(IN_RIGHT), PUT,
    {1, 'X', 0}, {45, 0, 0},                              // an exit
    MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), PUT,
    {1, '5', 0}, {45, 0, 0},                              // two boulders above
    MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_UP), PUT, MOVE(IN_LEFT), PUT,
    {1, '3', 0}, {45, 0, 0},                              // a wall, drawn
    MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT),
    {36, 0, IN_BUTTON | IN_DOWN}, {80, 0, 0},
    SHOT,                                                 // 5: editor-changed
    {1, 'V', 0}, {60, 0, 0}, MOVE(IN_DOWN), {20, 0, 0},   // values: 3 emeralds to open the exit
    MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT),
    MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), {40, 0, 0},
    MOVE(IN_UP), MOVE(IN_UP), {20, 0, 0},                 // the name: OLD TUNNEL
    STEP1(0x14), STEP1(0x14), STEP1(0x14), STEP1(0x14), STEP1(0x14),
    STEP1('T'), STEP1('U'), STEP1('N'), STEP1('N'), STEP1('E'), STEP1('L'), {60, 0, 0},
    SHOT,                                                 // 6: editor-values
    {1, '\r', 0}, {80, 0, 0},
    {1, 'T', 0}, {TRY_WAIT, 0, 0}, {45, 0, IN_RIGHT},     // trying it: to the exit
    SHOT,                                                 // 7: editor-try
    {75, 0, IN_RIGHT}, {250, 0, 0}, {150, 0, 0},
    {1, 'S', 0}, {60, 0, 0},                              // saved
    SHOT,                                                 // 8: editor-saved
    {60, 0, 0},
    {1, '+', 0}, {80, 0, 0}, {1, '-', 0}, {150, 0, 0},    // loaded again: as saved
    {2, 0, IN_RESTART}, {100, 0, 0},                      // the title, the own caves
    {2, 0, IN_RIGHT}, {10, 0, 0}, {2, 0, IN_RIGHT}, {10, 0, 0}, {2, 0, IN_RIGHT}, {10, 0, 0},
    {2, 0, IN_RIGHT}, {10, 0, 0}, {2, 0, IN_RIGHT}, {60, 0, 0},
    SHOT,                                                 // 9: editor-title
    {90, 0, 0},
    {0, 0, 0},
#else
    {60, 0, 0}, {1, 'E', 0}, {90, 0, 0},                  // title, E: the editor
    {1, '5', 0}, {2, 0, IN_RIGHT}, {2, 0, 0},             // a boulder at 3,2
    {4, 0, IN_BUTTON}, {2, 0, 0},
    {1, '7', 0}, {1, '7', 0}, {2, 0, IN_DOWN}, {2, 0, 0}, // a firefly (up) at 3,3
    {4, 0, IN_BUTTON}, {10, 0, 0},
    {0, 0, 0},                                            // 1: the editor
    {1, 'H', 0}, {30, 0, 0}, {0, 0, 0},                   // 2: help
    {1, 'Q', 0}, {1, 'V', 0}, {10, 0, 0},                 // values: time 153
    {2, 0, IN_RIGHT}, {2, 0, 0}, {2, 0, IN_RIGHT}, {2, 0, 0}, {2, 0, IN_RIGHT}, {2, 0, 0},
    {2, 0, IN_UP}, {2, 0, 0},                             // the name: TEST
    {1, 'T', 0}, {1, 0, 0}, {1, 'E', 0}, {1, 0, 0}, {1, 'S', 0}, {1, 0, 0}, {1, 'T', 0}, {10, 0, 0},
    {0, 0, 0},                                            // 3: values
    {1, '\r', 0}, {1, 'S', 0}, {30, 0, 0}, {0, 0, 0},     // 4: saved
    {1, 'T', 0}, {250, 0, 0}, {150, 0, 0}, {0, 0, 0},     // 5: trying it, Rockford out
    {2, 0, IN_RESTART}, {250, 0, 0}, {2, 0, IN_BUTTON}, {150, 0, 0},  // dead after 15 steps
    {0, 0, 0},                                            // 6: back in the editor
    {1, '+', 0}, {100, 0, 0}, {0, 0, 0},                  // 7: slot 2, a cave from GDash
    {1, 'T', 0}, {250, 0, 0}, {250, 0, 0}, {0, 0, 0},     // 8: trying it
    {2, 0, IN_RESTART}, {250, 0, 0}, {2, 0, IN_BUTTON}, {150, 0, 0},
    {1, '-', 0}, {100, 0, 0}, {0, 0, 0},                  // 9: slot 1 again
    {2, 0, IN_RESTART}, {120, 0, 0},                      // the title, own caves
    {2, 0, IN_RIGHT}, {2, 0, 0}, {2, 0, IN_RIGHT}, {2, 0, 0}, {2, 0, IN_RIGHT}, {2, 0, 0},
    {2, 0, IN_RIGHT}, {2, 0, 0}, {2, 0, IN_RIGHT}, {2, 0, 0}, {10, 0, 0},
    {0, 0, 0},                                            // 10: the title
    {2, 0, IN_BUTTON}, {250, 0, 0}, {200, 0, 0}, {0, 0, 0},  // 11: playing own cave 1
    {0, 0, 0}, {0, 0, 0}, {0, 0, 0}, {0, 0, 0}, {0, 0, 0},
#endif
};
static uint8_t test_pos, test_left, test_in, test_key, test_stops;

static uint8_t test_input(void) {
    while (!test_left) {
        const uint8_t *step = test_script[test_pos];
        if (test_pos < sizeof test_script / 3 - 1)
            test_pos++;
        if (!step[0]) {
            if (++test_stops >= EDITTEST) {
                POKE(0xD6CF, 0);
                POKE(0xD6CF, 0x42);
                for (;;)
                    ;
            }
            continue;
        }
        test_left = step[0];
        test_key = step[1];
        test_in = step[2];
    }
    test_left--;
    return test_in;
}
#define input_read test_input
#endif

// ---------------------------------------------------------------- drawing

// Top left pixel of cell i as drawn: still on its way if it moved
static void cell_pos(uint16_t i, uint16_t *x, uint16_t *y) {
    *x = (i % CAVE_W) * 16;
    *y = (i / CAVE_W) * 16;
    switch (moved[i]) {
    case DIR_UP:
        *y += slide;
        break;
    case DIR_RIGHT:
        *x -= slide;
        break;
    case DIR_DOWN:
        *y -= slide;
        break;
    case DIR_LEFT:
        *x += slide;
        break;
    }
}

static void init_tiles(void) {
    etile[E_SPACE] = T_SPACE;
    etile[E_DIRT] = T_DIRT;
    etile[E_BRICK] = T_BRICK;
    etile[E_STEEL] = T_STEEL;
    etile[E_BOULDER] = etile[E_BOULDER_F] = T_BOULDER;
    etile[E_DIAMOND] = T_SPARKLE;
    etile[E_OUTBOX] = T_STEEL;  // the closed exit looks like steel
    for (uint8_t i = 0; i < 5; i++)
        etile[E_EXPLODE + i] = etile[E_EXPLODE_D + i] = T_EXPLODE0 + i;
    for (uint8_t i = 0; i < 3; i++)
        etile[E_BIRTH + i] = T_BIRTH0 + i;
}

// Rockford turns through his eight views one at a time, the shorter way
// round (half way round past the front): one per frame while he walks, one
// every other frame while he stands. Walking, he makes one step per cell,
// in time with the sliding: the stride in its first half, passing in the
// second. Standing for a while, he turns to the front.
#define VIEW_FRONT (2 * DIR_DOWN)   // the view in a direction is 2 * DIR_*
#define REST_TURN  16               // frames standing before he turns to the front

static uint8_t rockford_tile(void) {
    uint8_t want = game.facing * 2;
    if (game.moving)
        rf_rest = 0;
    else if (rf_rest < REST_TURN)
        rf_rest++;
    else
        want = VIEW_FRONT;
    if (rf_view != want) {
        if (game.moving || (frame & 1)) {
            uint8_t d = (want - rf_view) & 7;
            if (d < 4 || (d == 4 && ((VIEW_FRONT - rf_view) & 7) < 4))
                rf_view = (rf_view + 1) & 7;
            else
                rf_view = (rf_view - 1) & 7;
        }
        return T_RF_VIEW0 + rf_view;
    }
    if (game.moving && !game.snapping) {
        // moved into his cell: in step; pushing or blocked: on the spot
        uint8_t phase = moved[game.player] != DIR_NONE ? rf_foot * 2 + (slide < 8) : (frame >> 2) & 3;
        return T_RF_UP0 + game.facing * 4 + phase;
    }
    if (rf_view != VIEW_FRONT)
        return T_RF_VIEW0 + rf_view;
    // From the front: now and then blink or tap a foot
    if ((frame & 15) == 0) {
        uint8_t r = rnd();
        idle = r < 48 ? 1 : r < 80 ? 2 : 0;
    }
    if (idle == 1 && (frame & 15) < 4)
        return T_RF_BLINK;
    if (idle == 2 && (frame & 4))
        return T_RF_TAP;
    return T_RF_VIEW0 + VIEW_FRONT;
}

static void add_trail(uint16_t cell, uint8_t kind) {
    trail_cell[trail_next] = cell;
    trail_kind[trail_next] = kind;
    trail_tile[trail_next] = trail_first[kind];
    trail_wait[trail_next] = trail_step[kind];
    trail_next = (trail_next + 1) % TRAILS;
}

// After a tick: what it leaves behind (engine.h)
static void add_trails(void) {
    for (uint8_t k = 0; k < nevents; k++) {
        uint16_t c = events[k].cell;
        switch (events[k].what) {
        case EV_FIREFLY:
            add_trail(c, TR_EMBERS);
            break;
        case EV_BUTTERFLY:
            add_trail(c, TR_GLITTER);
            break;
        case EV_DUG:
            add_trail(c, TR_CRUMBS);
            break;
        case EV_LANDED:
            add_trail(c - 1, TR_DUST_L);
            add_trail(c + 1, TR_DUST_R);
            break;
        }
    }
}

// The trails over the empty cells (update_tiles has just set them)
static void draw_trails(void) {
    for (uint8_t k = 0; k < TRAILS; k++) {
        uint8_t kind = trail_kind[k];
        if (!kind)
            continue;
        uint16_t c = trail_cell[k];
        if (tiles[c] == T_SPACE && cave[c] == E_SPACE)
            tiles[c] = trail_tile[k];
        if (!--trail_wait[k]) {
            if (trail_tile[k] == trail_last[kind]) {
                trail_kind[k] = TR_NONE;
            } else {
                trail_tile[k]++;
                trail_wait[k] = trail_step[kind];
            }
        }
    }
}

// Each emerald sparkles at its own moment
static const uint8_t glint[16] = {3, 6, 0, 5, 2, 7, 4, 1, 6, 2, 5, 0, 7, 3, 1, 4};

// The tile of one of GDash's elements in frame f: its own (gd_tile) and
// frames (gd_anim), or the game's for the ones it has too (etile, just set)
static uint8_t gtile_of(uint8_t e, uint8_t f) {
    uint8_t t = gd_tile[e];
    uint8_t a = gd_anim[e];
    if (a & 3)
        t += (f >> (a >> 2)) & ((1 << (a & 3)) - 1);
    switch (t) {
    case T_FIREFLY0:
        return etile[E_FIREFLY];
    case T_BUTTERFLY0:
        return etile[E_BUTTERFLY];
    case T_AMOEBA0:
        return etile[E_AMOEBA];
    case T_MAGIC0:
        return etile[E_MAGIC];
    case T_INBOX0:
        return etile[E_INBOX];
    case T_OUTBOX0:
        return etile[E_OUTBOX_OPEN];
    case T_RF_VIEW4:
        return etile[E_ROCKFORD];
    }
    return t;
}

// The elements whose tile can change from frame to frame: the ones above
// that move, and the ones the switches and "looks like" set below
static const uint8_t gtile_set[] = {
    O_CREATURE_SWITCH, O_EXPANDING_WALL_SWITCH, O_GRAVITY_SWITCH, O_REPLICATOR_SWITCH, O_REPLICATOR,
    O_CONVEYOR_DIR_SWITCH, O_CONVEYOR_SWITCH, O_CONVEYOR_LEFT, O_CONVEYOR_RIGHT, O_DIRT, O_EXPANDING_WALL,
    O_V_EXPANDING_WALL, O_H_EXPANDING_WALL, O_AMOEBA_2, O_PRE_OUTBOX, O_PRE_INVIS_OUTBOX};
static uint8_t gtile_dyn[GD_MOVING + sizeof gtile_set], gtile_ndyn;

// GDash's elements in this frame (gtile[]); what GDash shows of the
// switches and the "looks like" effects. The tiles that never change are
// set once.
static void update_gtiles(void) {
    uint8_t f = frame;
    if (!gtile_ndyn) {
        for (uint8_t e = 0; e < O_COUNT; e++) {
            uint8_t t = gd_tile[e];
            bool dyn = (gd_anim[e] & 3) || t == T_FIREFLY0 || t == T_BUTTERFLY0 || t == T_AMOEBA0 ||
                       t == T_MAGIC0 || t == T_INBOX0 || t == T_OUTBOX0 || t == T_RF_VIEW4 ||
                       memchr(gtile_set, e, sizeof gtile_set);
            gtile[e] = gtile_of(e, f);
            if (dyn)  // at most GD_MOVING + those of gtile_set
                gtile_dyn[gtile_ndyn++] = e;
        }
    } else {
        for (uint8_t k = 0; k < gtile_ndyn; k++) {
            uint8_t e = gtile_dyn[k];
            gtile[e] = gtile_of(e, f);
        }
    }
    uint32_t fl = gd.flags;
    if (fl & GDF_CREATURES_BACKWARDS)
        gtile[O_CREATURE_SWITCH] = T_CREATURE_SWITCH_ON;
    if (fl & GDF_EXPANDING_WALL_CHANGED)
        gtile[O_EXPANDING_WALL_SWITCH] = T_EXPANDING_WALL_SWITCH_ON;
    if (fl & GDF_GRAVITY_SWITCH_ACTIVE)
        gtile[O_GRAVITY_SWITCH] = T_GRAVITY_SWITCH_ON;
    if (fl & GDF_REPLICATORS_ACTIVE)
        gtile[O_REPLICATOR_SWITCH] = T_REPLICATOR_SWITCH_ON;
    else
        gtile[O_REPLICATOR] = T_REPLICATOR0;
    uint8_t left = T_CONVEYOR_L0, right = T_CONVEYOR_R0;
    if (fl & GDF_CONVEYOR_BELTS_DIRECTION_CHANGED) {
        left = T_CONVEYOR_R0;
        right = T_CONVEYOR_L0;
        gtile[O_CONVEYOR_DIR_SWITCH] = T_CONVEYOR_DIR_SWITCH_ON;
    }
    if (fl & GDF_CONVEYOR_BELTS_ACTIVE) {  // running: both frames
        gtile[O_CONVEYOR_SWITCH] = T_CONVEYOR_SWITCH_ON;
        left += (f >> 2) & 1;
        right += (f >> 2) & 1;
    }
    gtile[O_CONVEYOR_LEFT] = left;
    gtile[O_CONVEYOR_RIGHT] = right;
    gtile[O_DIRT] = gtile[file.own.dirt_looks_like];
    gtile[O_EXPANDING_WALL] = gtile[O_V_EXPANDING_WALL] = gtile[O_H_EXPANDING_WALL] =
        gtile[file.own.expanding_wall_looks_like];
    gtile[O_AMOEBA_2] = gtile[file.own.amoeba_2_looks_like];
    if (show_cursor)  // the editor shows the closed exit as an exit
        gtile[O_PRE_OUTBOX] = gtile[O_PRE_INVIS_OUTBOX] = T_OUTBOX0;
}

static void update_tiles(void) {
    uint8_t f = frame;
    etile[E_DIAMOND_F] = T_DIAMOND0 + ((f >> 2) & 7);
    etile[E_INBOX] = (f & 8) ? T_INBOX1 : T_INBOX0;
    etile[E_OUTBOX_OPEN] = (f & 8) ? T_OUTBOX1 : T_OUTBOX0;
    etile[E_MAGIC] = game.magic_state == MW_ACTIVE ? T_MAGIC0 + ((f >> 2) & 3) : T_BRICK;
    etile[E_AMOEBA] = T_AMOEBA0 + ((f >> 3) & 3);
    for (uint8_t d = 0; d < 4; d++) {
        etile[E_FIREFLY + d] = T_FIREFLY0 + ((f >> 1) & 3);
        etile[E_BUTTERFLY + d] = T_BUTTERFLY0 + ((f >> 2) & 3);
    }
    etile[E_ROCKFORD] = rockford_tile();
    const uint8_t *et = etile;
    if (by_gdash) {
        update_gtiles();
        et = gtile;
    }

    // only the cells in view, and around it what may slide into it
    uint8_t x0 = cam_x >> 4, y0 = cam_y >> 4;
    uint8_t x1 = x0 + VIEW_W / 16 + 1, y1 = y0 + VIEW_H / 16 + 1;
    if (x0)
        x0--;
    if (y0)
        y0--;
    if (x1 >= CAVE_W)
        x1 = CAVE_W - 1;
    if (y1 >= CAVE_H)
        y1 = CAVE_H - 1;
    uint8_t cover = T_COVER0 + ((f >> 1) & 1);
    uint8_t sparkle = f >> 2;
    nsprites = 0;
    for (uint8_t y = y0; y <= y1; y++) {
        uint16_t i = y * CAVE_W + x0;
        for (uint8_t x = x0; x <= x1; x++, i++) {
            if (any_covered && covered[i]) {
                tiles[i] = cover;
                continue;
            }
            uint8_t t = et[cave[i]];
            if (t == T_SPARKLE)
                t = T_DIAMOND0 + ((sparkle + glint[(x + y * 7) & 15]) & 7);
            if (slide && moved[i] != DIR_NONE && nsprites < MAX_SPRITES) {
                Sprite *s = &sprites[nsprites++];
                cell_pos(i, &s->x, &s->y);
                s->tile = t;
                t = T_SPACE;
            }
            tiles[i] = t;
        }
    }
    draw_trails();
}

// The view follows Rockford like the original: it starts to scroll when he
// comes near an edge and scrolls until he is in the middle again.
static void follow(uint16_t *cam, bool *active, uint16_t p, uint16_t view, uint16_t max, uint16_t margin) {
    int16_t rel = (int16_t)p - (int16_t)*cam;
    if (rel < (int16_t)margin || rel > (int16_t)(view - margin))
        *active = true;
    if (!*active)
        return;
    int16_t target = (int16_t)p - (int16_t)(view / 2);
    if (target < 0)
        target = 0;
    if (target > (int16_t)max)
        target = max;
    int16_t diff = target - (int16_t)*cam;
    uint8_t step = (rel < 24 || rel > (int16_t)view - 24) ? 4 : 2;
    if (diff > step)
        *cam += step;
    else if (diff < -(int16_t)step)
        *cam -= step;
    else {
        *cam = target;
        *active = false;
    }
}

// The view to pixel px, py of the cave (Rockford's or the editor's cursor)
static void camera_at(uint16_t px, uint16_t py, bool jump) {
    if (jump) {
        cam_x = px < VIEW_W / 2 ? 0 : px - VIEW_W / 2;
        cam_y = py < VIEW_H / 2 ? 0 : py - VIEW_H / 2;
        if (cam_x > MAX_X)
            cam_x = MAX_X;
        if (cam_y > MAX_Y)
            cam_y = MAX_Y;
        return;
    }
    follow(&cam_x, &scroll_x, px, VIEW_W, MAX_X, 80);
    follow(&cam_y, &scroll_y, py, VIEW_H, MAX_Y, 48);
}

static void camera(bool jump) {
    uint16_t px, py;
    cell_pos(game.player, &px, &py);
    camera_at(px + 8, py + 8, jump);
}

// ---------------------------------------------------------------- status

// Without division, which is slow on the 6502: each power of ten is taken
// away as often as it goes. Only the last `digits` digits are shown. Not
// inlined: it is called from many places.
static const uint32_t pow10[] = {1, 10, 100, 1000, 10000, 100000, 1000000};

__attribute__((noinline)) static void put_num(uint8_t col, uint32_t v, uint8_t digits) {
    while (v >= pow10[digits])
        v -= pow10[digits];
    while (digits--) {
        uint32_t p = pow10[digits];
        uint8_t d = '0';
        while (v >= p) {
            v -= p;
            d++;
        }
        status_put(col++, d);
    }
}

static void status_clear(void) {
    for (uint8_t c = 1; c < 39; c++)
        status_put(c, ' ');
}

static void status_center(const char *text) {
    status_begin();
    status_print((40 - strlen(text)) / 2, text);
    status_end();
}

// The numbers are redrawn only when they change (32-bit division is slow)
static void status_game(void) {
    static uint8_t last_collected, last_value, last_lives;
    static uint16_t last_time;
    static uint32_t last_score;
    static bool valid;
    const CaveDef *d = game.def;
    uint8_t value = game.exit_open ? d->extra_value : d->diamond_value;
    uint32_t total = score + game.score;
    bool layout = status_code_at(2) != ICON(ICON_EMERALD);
    if (layout) {
        status_begin();
        status_put(2, ICON(ICON_EMERALD));
        status_put(6, '/');
        status_put(9 + 2, 'x');
        status_put(17, ICON(ICON_CLOCK));
        status_put(25, ICON(ICON_LIFE));
        put_num(7, d->diamonds_needed, 2);
        valid = false;
    }
    if (!valid || game.collected != last_collected)
        put_num(4, last_collected = game.collected, 2);
    if (!valid || value != last_value)
        put_num(12, last_value = value, 2);
    if (!valid || game.time != last_time)
        put_num(19, last_time = game.time, 3);
    if (!valid || lives != last_lives)
        put_num(27, last_lives = lives, 1);
    if (!valid || total != last_score)
        put_num(31, last_score = total, 6);
    valid = true;
    if (layout)
        status_end();
}

// GDash's caves: what Rockford carries - keys, skeletons, the sweet, the
// hammer, the diamond key - and where gravity pulls, as GDash's second
// status line. It shows for three seconds when any of it changes, while
// gravity is about to turn, and while I is held. False if it does not show.
static bool items_fresh;  // a new cave: what it starts with is no change

static uint8_t gd_secs(int32_t t) {  // GDash's time_visible, up to 99
    uint8_t s = 0;
    while (t > 0 && s < 99) {
        t -= gd.timing_factor;
        s++;
    }
    return s;
}

static bool status_items(void) {
    static uint8_t last[8], left, shown_secs;
    bool pending = gd.gravity_will_change > 0;
    uint8_t now[8] = {gd.key1 > 9 ? 9 : gd.key1, gd.key2 > 9 ? 9 : gd.key2, gd.key3 > 9 ? 9 : gd.key3,
                      gd.skeletons_collected, gd.sweet_eaten, gd.got_pneumatic_hammer,
                      gd.diamond_key_collected, pending ? gd.gravity_next_direction : gd.gravity};
    bool changed = memcmp(now, last, sizeof now) != 0;
    if (changed) {
        memcpy(last, now, sizeof now);
        left = items_fresh ? 0 : pal ? 150 : 180;
        items_fresh = false;
    }
    bool gravity = pending || now[7] != MV_DOWN;
    bool any = gravity;
    for (uint8_t k = 0; k < 7; k++)
        any |= now[k] != 0;
    if (left)
        left--;
    if (!any || !(left || pending || (held & IN_ITEMS)))
        return false;
    uint8_t secs = pending ? gd_secs(gd.gravity_will_change) : 0;
    if (!changed && secs == shown_secs && status_code_at(2) == 0xFF)
        return true;  // as it is
    shown_secs = secs;
    status_begin();
    static const uint8_t tile[7] = {T_KEY1, T_KEY2, T_KEY3, T_SKELETON, T_SWEET, T_HAMMER, T_DIAMOND_KEY};
    uint8_t col = 2;
    for (uint8_t k = 0; k < 7; k++) {
        if (!now[k])
            continue;
        status_tile(col, tile[k]);
        col += 2;
        if (k < 4) {  // how many
            uint8_t digits = k < 3 ? 1 : 2;
            put_num(col, now[k], digits);
            col += digits;
        }
        col++;
    }
    if (gravity) {
        status_tile(col, T_GRAVITY_SWITCH);
        status_put(col + 2, now[7] == MV_UP ? '^' : now[7] == MV_LEFT ? '<' : now[7] == MV_RIGHT ? '>' : '_');
        if (pending)
            put_num(col + 3, secs, 2);
    }
    status_end();
    return true;
}

static void status_play(void) {
    if (!by_gdash || !status_items())
        status_game();
}

// "CAVE 12/3": cave and level, as the original's "A/1"; "OWN 12" for an
// own cave, "TEST" for the one in the editor
static void status_intro(void) {
    status_begin();
    status_put(2, ICON(ICON_LIFE));
    put_num(4, lives, 1);
    uint8_t col;
    if (play_mode == PLAY_CAVES) {
        status_print(7, "CAVE");
        col = cave_no >= 9 ? 14 : 13;
        put_num(12, cave_no + 1, col - 12);
        status_put(col, '/');
        put_num(col + 1, level + 1, 1);
        col += 3;
    } else if (play_mode == PLAY_OWN) {
        status_print(7, "OWN");
        put_num(11, cave_no + 1, 2);
        col = 14;
    } else {
        status_print(7, "TEST");
        col = 12;
    }
    status_print(col, game.def->name);
    status_end();
}

// ---------------------------------------------------------------- frames

static void next_frame(void) {
    video_sync();
    update_tiles();
    if (show_cursor && (frame & 31) < 24 && nsprites < MAX_SPRITES) {
        Sprite *s = &sprites[nsprites++];
        s->x = cur_x * 16;
        s->y = cur_y * 16;
        s->tile = T_CURSOR;
    }
    video_render(tiles, cam_x, cam_y, sprites, nsprites);
    video_show();
    sound_frame();
    frame++;
    if (flash && !--flash)
        video_flash(false);
    uint8_t in = input_read();
    pressed = in & ~held;
    held = in;
}

static uint8_t joy_dir(uint8_t in) {
    if (in & IN_LEFT)
        return DIR_LEFT;
    if (in & IN_RIGHT)
        return DIR_RIGHT;
    if (in & IN_UP)
        return DIR_UP;
    if (in & IN_DOWN)
        return DIR_DOWN;
    return DIR_NONE;
}

// Uncover (on = 0) or cover (on = 1) the cave: a few random cells per row
// each frame, then the rest.
static void cover_cave(uint8_t on) {
    any_covered = true;
    for (uint8_t f = 0; f < 60; f++) {
        for (uint8_t y = 0; y < CAVE_H; y++)
            for (uint8_t k = 0; k < 3; k++)
                covered[y * CAVE_W + ((rnd() * CAVE_W) >> 8)] = on;
        if (f & 1)
            sound_crackle();
        next_frame();
    }
    memset(covered, on, sizeof covered);
    any_covered = on;
}

// Wait for the button, but at most `frames` frames
static void wait_button(uint16_t frames) {
    while (frames-- && !(pressed & IN_BUTTON))
        next_frame();
}

// ---------------------------------------------------------------- loading

static uint8_t spin_frame;

// The loader calls this after each sector: the emerald in the status line
// turns, one step every four frames as in the cave.
static void spin(void) {
    uint8_t f = PEEK(0xD7FA);  // frame counter
    if ((f >> 2) != spin_frame) {
        spin_frame = f >> 2;
        status_tile(2, T_DIAMOND0 + (spin_frame & 7));
    }
}

// The spinner and `what` in the status line while the disk is busy
static void busy(const char *what) {
    status_begin();
    status_print(5, what);
    status_end();
    spin_frame = 0xFF;
    spin();
    disk_busy = spin;
}

static void not_busy(void) {
    disk_busy = 0;
    status_clear();
}

// Load a file with the spinner and `what` in the status line
static bool load(const char *what, const char *file, uint8_t bank, uint16_t addr) {
    busy(what);
    bool ok = disk_load(file, bank, addr);
    not_busy();
    return ok;
}

static void use_cave_file(void);

// Cave n of the level from the disk (CAVEnn-l), unless it is there already
static bool load_cave(uint8_t n) {
    if (n == loaded && level == loaded_level)
        return true;
    static char name[] = "CAVE00-0";
    static char what[] = "LOADING CAVE 00/0";
    uint8_t tens = (n + 1) / 10, ones = (n + 1) % 10;
    name[4] = '0' + tens;
    name[5] = '0' + ones;
    name[7] = '1' + level;
    char *num = what + 13;
    if (tens)
        *num++ = '0' + tens;
    *num++ = '0' + ones;
    *num++ = '/';
    *num++ = '1' + level;
    *num = 0;
    loaded = 0xFF;
    if (!load(what, name, 0, (uint16_t)&file.game))
        return false;
#ifdef SCREENCAST
    static char demo_file[] = "DEMO00";
    demo_file[4] = name[4];
    demo_file[5] = name[5];
    if (!disk_load(demo_file, 0, (uint16_t)demo_moves))
        demo_moves[0] = 0;
#endif
    loaded = n;
    loaded_level = level;
    use_cave_file();
    return true;
}

// The game's cave in file.game for its own engine
static void use_cave_file(void) {
    by_gdash = false;
    cave_def.name = file.game.name;
    cave_def.map = file.game.map;
    cave_def.time = file.game.time;
    cave_def.diamonds_needed = file.game.diamonds;
    cave_def.diamond_value = file.game.value;
    cave_def.extra_value = file.game.extra;
    cave_def.amoeba_time = file.game.amoeba;
    cave_def.magic_time = file.game.magic;
    cave_def.tick_ms = file.game.speed;
}

// The own cave in file.own for GDash's engine
static void use_own_cave(void) {
    by_gdash = true;
    cave_def.name = file.own.name;
}

// The cave cave_no; after the last one on the disk the first of the next
// level, and after the last level that one again
static bool next_cave(void) {
    if (load_cave(cave_no))
        return true;
    cave_no = 0;
    if (level < LEVELS - 1)
        level++;
    return load_cave(0);
}

// The file of slot n (from 0): OWN01, ...
static const char *own_name(uint8_t n) {
    static char file[] = "OWN00";
    file[3] = '0' + (n + 1) / 10;
    file[4] = '0' + (n + 1) % 10;
    return file;
}

// Slot n from the disk into file.own; false if the disk has no such slot.
// An empty one has time 0.
static bool load_own(uint8_t n) {
    loaded = 0xFF;
    return load("LOADING OWN CAVE", own_name(n), 0, (uint16_t)&file.own);
}

// The own cave cave_no, or the next one that is not empty (after the last
// slot the first again); false if there is none
static bool next_own(void) {
    for (uint8_t k = 0; k < OWN_SLOTS; k++, cave_no++) {
        if (cave_no >= OWN_SLOTS)
            cave_no = 0;
        if (!have_gdash || !load_own(cave_no))
            return false;
        if (file.own.time) {
            use_own_cave();
            return true;
        }
    }
    return false;
}

// ---------------------------------------------------------------- screencast

#ifdef SCREENCAST
#define DEMO_TITLE_FRAMES 768  // the title with all its lines once

static const uint8_t *demo_p;
static uint8_t demo_left, demo_in;

// The input of the next tick: (count, input) pairs, closed by 0
static uint8_t demo_next(void) {
    if (!demo_left) {
        if (!demo_p[0])
            return DIR_NONE;
        demo_left = demo_p[0];
        demo_in = demo_p[1];
        demo_p += 2;
    }
    demo_left--;
    return demo_in;
}

// A second on the covered cave, then Xemu (with -testing) exits: the exit
// code to $D6CF, then $42.
static void demo_end(void) {
    for (uint8_t f = 0; f < 50; f++)
        next_frame();
    POKE(0xD6CF, 0);
    POKE(0xD6CF, 0x42);
    for (;;)
        next_frame();
}
#endif

// ---------------------------------------------------------------- title

// Text on the title screens goes a few letters per frame (title_frame): a
// whole line at once takes longer than a frame, and the music would stumble.
#define TEXT_STEP 8
static char text_buf[39];
static uint8_t text_pos, text_col, text_y;
static const uint8_t *text_rows;

static void text_more(uint8_t n) {
    char one[2] = {0, 0};
    for (; n && text_buf[text_pos]; n--, text_pos++) {
        one[0] = text_buf[text_pos];
        video_text_in(text_col + text_pos, text_y, one, text_rows);
    }
}

// Text drawn over the next frames; what still waits is drawn first
static void text_later(uint8_t col, uint8_t y, const char *text, const uint8_t *rows) {
    text_more(255);
    strcpy(text_buf, text);
    text_pos = 0;
    text_col = col;
    text_y = y;
    text_rows = rows;
}

// A new page: what still waits is not drawn
static void text_cancel(void) {
    text_buf[0] = 0;
    text_pos = 0;
}

static void title_frame(void) {
    video_sync();
    video_show();
    music_frame();
    sound_frame();
    text_more(TEXT_STEP);
    frame++;
    uint8_t in = input_read();
    pressed = in & ~held;
    held = in;
}

// Centre a text of n characters (big: 2 columns each) in columns 1-38
#define CENTRE(n) (1 + (38 - (n)) / 2)

// One line of text under the logo, centred over the full width
static void title_line(const char *text) {
    static char line[39];
    uint8_t n = strlen(text);
    memset(line, ' ', 38);
    memcpy(line + (38 - n) / 2, text, n);
    line[38] = 0;
    text_later(1, 152, line, font_row);
}

// The status line on the title: what the game starts with, and the hi-score
static void title_status(void) {
    status_begin();
    if (start_cave == CAVE_COUNT) {
        status_print(2, "OWN CAVES");
    } else {
        status_print(2, "LEVEL");
        put_num(8, start_level + 1, 1);
        status_print(11, "CAVE");
        put_num(start_cave >= 9 ? 16 : 17, start_cave + 1, start_cave >= 9 ? 2 : 1);
    }
    status_print(22, "HI-SCORE");
    put_num(31, hs_table[0].score, 6);
    status_end();
}

// Up and down pick the level, left and right the cave to start with; right
// of the last one come the own caves
#define LAST_START ((CAVE_COUNT - 1) / START_STEP * START_STEP)

static void title_pick(void) {
    uint8_t l = start_level, c = start_cave;
    if ((pressed & IN_UP) && l < LEVELS - 1)
        l++;
    if ((pressed & IN_DOWN) && l)
        l--;
    if ((pressed & IN_RIGHT) && c < CAVE_COUNT)
        c = c == LAST_START ? CAVE_COUNT : c + START_STEP;
    if ((pressed & IN_LEFT) && c)
        c = c == CAVE_COUNT ? LAST_START : c - START_STEP;
    if (l != start_level || c != start_cave) {
        start_level = l;
        start_cave = c;
        title_status();
        sound_crackle();
    }
}

// ---------------------------------------------------------------- high scores

#define HS_COL 6   // the table's lines: "1ST  ROC  012345  CAVE 12/3"
#define HS_Y0  42  // its first line; one every 16 pixel rows

static uint8_t hs_new = HS_COUNT;  // the entry of the last game, shining

static const char places[] = "1ST2ND3RD4TH5TH6TH7TH8TH";

static const uint8_t *place_colours(uint8_t rank) {
    return rank_row + (rank < 3 ? rank : 3) * 16;
}

// v as six digits from p on
static void digits6(char *p, uint32_t v) {
    for (uint8_t k = 6; k--; v /= 10)
        p[k] = '0' + v % 10;
}

static void hs_line(uint8_t i) {
    static char line[28];
    const HiScore *e = &hs_table[i];
    memset(line, ' ', 27);
    memcpy(line, places + i * 3, 3);
    memcpy(line + 5, e->name, 3);
    digits6(line + 10, e->score);
    memcpy(line + 18, "CAVE", 4);
    char *p = line + 23;
    uint8_t c = e->cave + 1;
    if (c >= 10)
        *p++ = '0' + c / 10;
    *p++ = '0' + c % 10;
    *p++ = '/';
    *p = '1' + e->level;
    text_later(HS_COL, HS_Y0 + i * 16, line, i == hs_new ? title_row : place_colours(i));
}

static void scores_page(void) {
    text_cancel();
    video_clear();
    video_palette(0);
    video_big_text(CENTRE(22), 2, "HIGH SCORES");
}

// The table builds up line by line, emeralds turn beside the heading, and
// Rockford walks beside the new entry, which shines like the heading.
static void scores_frame(uint16_t pf) {
    if (pf >= 8 && pf < 8 + 6 * HS_COUNT && (pf - 8) % 6 == 0)
        hs_line((pf - 8) / 6);
    if ((pf & 3) == 0) {
        uint8_t t = T_DIAMOND0 + ((pf >> 2) & 7);
        video_tile(5, 10, t);
        video_tile(33, 10, t);
        if (hs_new < HS_COUNT && pf >= 8 + 6 * hs_new)
            video_tile(HS_COL - 3, HS_Y0 + hs_new * 16, T_RF_RIGHT0 + ((pf >> 2) & 3));
    }
    if (pf % 3 == 0)
        video_shine(pf / 3);
}

// The letters of a name; up and down go through them
static const char letters[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-! ";
#define LETTERS     (sizeof letters - 1)
#define NAME_COL    15  // the three big letters at columns 15, 19 and 23
#define NAME_Y      72
#define CURSOR_Y    (NAME_Y + 38)
#define NAME_TIME   30  // seconds to enter it
static char last_name[3] = {'A', 'A', 'A'};  // what the next one starts with

static void big_letter(uint8_t i, char ch) {
    char text[2] = {ch, 0};
    video_big_text(NAME_COL + i * 4, NAME_Y, text);
}

static uint8_t letter_index(char ch) {
    uint8_t i = 0;
    while (i < LETTERS - 1 && letters[i] != ch)
        i++;
    return i;
}

// Three letters for the entry at `rank`, arcade style: up and down change
// the letter, fire or right take it, left goes back. The keyboard works
// too: a letter or digit is taken at once, Del goes back.
static void enter_name(HiScore *e, uint8_t rank) {
    static char line[] = "000000 POINTS - 1ST PLACE";
    const uint8_t fps = pal ? 50 : 60;
    video_clear();
    video_palette(0);
    video_big_text(CENTRE(28), 4, "NEW HIGH SCORE");
    digits6(line, e->score);
    memcpy(line + 16, places + rank * 3, 3);
    video_text_in(CENTRE(25), 44, line, place_colours(rank));
    video_text(CENTRE(31), 136, "UP/DOWN LETTER   FIRE/RIGHT OK");
    video_text(CENTRE(32), 156, "LEFT BACK - OR TYPE THE LETTERS");
    memcpy(e->name, last_name, 3);
    for (uint8_t i = 0; i < 3; i++)
        big_letter(i, e->name[i]);
    status_clear();
    status_print(2, "ENTER YOUR NAME");
    status_put(30, ICON(ICON_CLOCK));
    while (PEEK(0xD610))  // forget the keys typed so far
        POKE(0xD610, 0);

    uint8_t pos = 0, shown = 0, rep = 0, sec = 0, left = NAME_TIME;
    bool armed = false;  // fire from the last life must be let go first
    put_num(32, left, 2);
    for (uint16_t f = 0; pos < 3; f++) {
        if (shown != pos) {  // the emerald goes under the letter being entered
            video_blank(NAME_COL + shown * 4, CURSOR_Y, 2, 16);
            shown = pos;
        }
        if ((f & 3) == 0)
            video_tile(NAME_COL + pos * 4, CURSOR_Y, T_DIAMOND0 + ((f >> 2) & 7));
        if (f % 3 == 0)
            video_shine(f / 3);
        title_frame();

        uint8_t step = 0;  // 1 up, 2 down
        uint8_t ud = held & (IN_UP | IN_DOWN);
        if (!ud)
            rep = 0;
        else {
            if (rep == 0 || rep == 16)  // at once, then repeated while held
                step = ud & IN_UP ? 1 : 2;
            if (++rep > 16)
                rep = 12;
        }
        if (step) {
            uint8_t i = letter_index(e->name[pos]);
            i = step == 1 ? (i + 1) % LETTERS : (i + LETTERS - 1) % LETTERS;
            e->name[pos] = letters[i];
            big_letter(pos, letters[i]);
            sound_crackle();
        }
        uint8_t key = PEEK(0xD610);
        if (key) {
            POKE(0xD610, 0);
            if (key >= 'a' && key <= 'z')
                key -= 'a' - 'A';
            if (key == 0x14 && pos) {  // Del
                pos--;
                sound_crackle();
            } else if (key != ' ' && letters[letter_index(key)] == key) {
                e->name[pos] = key;
                big_letter(pos++, key);
                sound_bonus();
            }
        } else if ((pressed & IN_LEFT) && pos) {
            pos--;
            sound_crackle();
        } else if ((pressed & IN_RIGHT) || (armed && (pressed & IN_BUTTON))) {
            pos++;
            sound_bonus();
        }
        if (!(held & IN_BUTTON))
            armed = true;
        if (++sec >= fps) {
            sec = 0;
            put_num(32, --left, 2);
            if (left < 10)
                sound_clock();
            if (!left)
                break;
        }
    }
    memcpy(last_name, e->name, 3);
    video_blank(NAME_COL, CURSOR_Y, 10, 16);
    status_center("WELL DONE!");
    sound_life();
    for (uint8_t f = 0; f < 75; f++) {
        if (f % 3 == 0)
            video_shine(f / 3);
        title_frame();
    }
}

// The table back onto the disk; the scores stay in memory either way
static void save_scores(void) {
    busy("SAVING HIGH SCORES");
    bool ok = hiscore_save();
    not_busy();
    if (!ok) {
        status_center("HIGH SCORES NOT SAVED");
        for (uint8_t f = 0; f < 100; f++)
            title_frame();
    }
}

// ---------------------------------------------------------------- title screen

#define LOGO_FRAMES   768  // the logo page with all its lines once
#define SCORES_FRAMES 500  // the high score table (twice as long with a new entry)

static void logo_page(void) {
    text_cancel();
    video_clear();
    if (have_logo) {
        video_palette(1);
        video_logo(CENTRE(LOGO_W / 8), 2);
    } else {  // started without the disk: the logo as text
        video_palette(0);
        video_big_text(CENTRE(14), 8, "SMARAGD");
        video_big_text(CENTRE(8), 44, "DASH");
        video_text(CENTRE(26), 88, "DIG  -  COLLECT  -  ESCAPE");
        video_text(CENTRE(32), 136, "JOYSTICK, GAMEPAD OR CURSOR KEYS");
        video_text(CENTRE(35), 156, "P PAUSE  RUN/STOP GIVE UP  E EDITOR");
    }
}

static void logo_frame(uint16_t pf) {
    static const char press[] = "PRESS FIRE TO START";
    static const char blank[] = "                   ";
    if (have_logo) {
        // the line under the logo: "press fire", blinking, and in
        // between the controls and the version; 8 lines of 96 frames
        if ((pf & 31) == 0) {
            switch (pf / 96) {
            case 1:
                title_line("JOYSTICK, GAMEPAD OR CURSOR KEYS");
                break;
            case 3:
                title_line("UP/DOWN: LEVEL   LEFT/RIGHT: CAVE");
                break;
            case 5:
                title_line("P PAUSE  RUN/STOP GIVE UP  E EDITOR");
                break;
            case 7:
                title_line("VERSION " VERSION);
                break;
            default:
                title_line((pf & 32) ? "" : press);
            }
        }
    } else {
        if ((pf & 31) == 0)
            text_later(CENTRE(19), 112, (pf & 32) ? blank : press, font_row);
        if (pf % 3 == 0)
            video_shine(pf / 3);
    }
}

// A key typed (ASCII, letters in upper case), or 0
static uint8_t get_key(void) {
#ifdef EDITTEST
    uint8_t key = test_key;
    test_key = 0;
#else
    uint8_t key = PEEK(0xD610);
    if (key) {
        POKE(0xD610, 0);
        if (key >= 'a' && key <= 'z')
            key -= 'a' - 'A';
    }
#endif
    return key;
}

// The logo and the high score table take turns, like an arcade machine
// waiting for a player; after a game the table comes first. True if E was
// pressed for the editor, false for a game.
static bool title_screen(bool scores) {
    if (scores)
        scores_page();
    else
        logo_page();
    title_status();
    sound_off();
    music_start();
    // The button counts only after it was let go once (Return from the
    // emulator's RUN, or fire still held from the last game)
    bool armed = false;
    bool editor = false;
    uint16_t pf = 0;  // frames on this page
    while (get_key())  // forget the keys typed in the game
        ;
    for (;;) {
        if (scores)
            scores_frame(pf);
        else
            logo_frame(pf);
        title_frame();
        title_pick();
        if (armed && (pressed & IN_BUTTON))
            break;
        if (get_key() == 'E') {
            editor = true;
            break;
        }
#ifdef SCREENCAST
        if (pf == DEMO_TITLE_FRAMES)  // on the logo page, the first
            break;
#endif
        if (!(held & IN_BUTTON))
            armed = true;
        if (++pf > (scores ? (hs_new < HS_COUNT ? 2 * SCORES_FRAMES : SCORES_FRAMES) : LOGO_FRAMES)) {
            pf = 0;
            scores = !scores;
            video_shine(0);
            if (scores)
                scores_page();
            else
                logo_page();
        }
    }
    music_stop();
    video_shine(0);
    text_cancel();
    video_clear();  // the logo goes before the game's palette comes
    video_palette(0);
    sound_init();
    return editor;
}

// ---------------------------------------------------------------- caves

enum { END_DIED, END_EXITED };

// ---------------------------------------------------------------- the rules

// A cave plays by the game's own rules (engine.c) or, an own one, by
// GDash's (gdengine.c, mapped in for each step by gdfar.s). The game's
// engine keeps `game` itself; from GDash's it is taken after each step, for
// the status line, the drawing and the sounds.
static bool gd_suicide;  // Run/Stop, for GDash's next step

static void game_from_gd(void) {
    static const uint8_t state[] = {PS_HATCHING, PS_ALIVE, PS_TIMEOUT, PS_DEAD, PS_EXITED};
    game.state = state[gd.player_state];
    game.player = gd.player_y * CAVE_W + gd.player_x;
    game.time = gd_time_visible();
    game.collected = gd.diamonds_collected > 255 ? 255 : gd.diamonds_collected;
    game.exit_open = gd.gate_open;
    game.flash = gd.gate_open_flash == 1;
    game.score += gd.score;
    game.sound = gd.sound;
    game.magic_state = gd.magic_wall_state;
    cave_def.diamonds_needed = gd.diamonds_needed > 255 ? 255 : gd.diamonds_needed;
    cave_def.diamond_value = cave_def.extra_value = gd.diamond_value > 99 ? 99 : gd.diamond_value;
}

static void rules_start(void) {
    if (!by_gdash) {
        cave_start(&cave_def);
        return;
    }
    memset(&game, 0, sizeof game);
    game.def = &cave_def;
    game.facing = DIR_DOWN;
    gd_suicide = false;
    items_fresh = true;
    gd_start(&file.own, (uint32_t)rnd() << 16 | (uint16_t)rnd() << 8 | frame);
    nevents = 0;
    game_from_gd();
}

static void rules_tick(uint8_t in) {
    if (!by_gdash) {
        cave_tick(in);
        return;
    }
    static const uint8_t mv[] = {MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_STILL};
    uint8_t dir = in & 7;
    gd_iterate(mv[dir], (in & IN_FIRE) != 0, gd_suicide);
    gd_suicide = false;
    nevents = 0;
    game.moving = dir != DIR_NONE;
    game.snapping = game.moving && (in & IN_FIRE);
    if (game.moving)
        game.facing = dir;
    game_from_gd();
}

static uint8_t play_cave(void) {
    const CaveDef *d = &cave_def;
    const uint8_t frame_len = pal ? 60 : 50;
    const uint8_t fps = pal ? 50 : 60;
    uint16_t tick_len;  // in 1/3 ms
    uint16_t tick_acc = 0;
    uint8_t sec = 0;
    uint16_t shown_time = 0;  // for the clock's tick under ten seconds (GDash's)
    uint8_t latched = DIR_NONE;
    uint8_t last_dir = DIR_NONE;  // the direction held in the frame before
    bool fire_latched = false;
    bool paused = false;
    uint8_t after = 0;  // frames since Rockford died
    uint8_t last_frame = PEEK(0xD7FA);  // the MEGA65's frame counter

    rules_start();
    tick_len = (by_gdash ? gd.speed : d->tick_ms) * 3;
    memset(trail_kind, TR_NONE, sizeof trail_kind);
    slide = 0;
    rf_view = VIEW_FRONT;
    memset(covered, 1, sizeof covered);
    camera(true);
    status_intro();
    cover_cave(0);

    for (;;) {
        if (pressed & IN_PAUSE) {
            paused = !paused;
            if (paused) {
                sound_off();
                status_center("PAUSED");
            }
        }
        if (paused) {
            next_frame();
            last_frame = PEEK(0xD7FA);
            continue;
        }
        if ((pressed & IN_RESTART) && game.state == PS_ALIVE) {
            if (by_gdash)
                gd_suicide = true;
            else
                cave_suicide();
        }

        // A direction or the button pressed only briefly between two ticks
        // still counts in the next tick. Only a new press is kept: one that
        // was still held at the last tick has had its step.
        uint8_t dir = joy_dir(held);
        if (dir != DIR_NONE && dir != last_dir)
            latched = dir;
        last_dir = dir;
        if (held & IN_BUTTON)
            fire_latched = true;

        // The time goes by the frames shown: a step that takes longer than
        // a frame (GDash's engine in a full cave) does not slow the cave down
        uint8_t now = PEEK(0xD7FA), frames = now - last_frame;
        last_frame = now;
        if (frames == 0)
            frames = 1;
        else if (frames > 3)  // a pause or the start: no steps to catch up
            frames = 3;
        tick_acc += frame_len * frames;
        if (tick_acc >= tick_len && game.state != PS_TIMEOUT && game.state != PS_EXITED) {
            tick_acc -= tick_len;
            uint8_t in = dir != DIR_NONE ? dir : latched;
            if (fire_latched)
                in |= IN_FIRE;
#ifdef SCREENCAST
            in = demo_next();
#endif
            latched = DIR_NONE;
            fire_latched = false;
            rules_tick(in);
            if (by_gdash)  // GDash's steps take as long as it says
                tick_len = gd.speed * 3;
            add_trails();
            if (moved[game.player] != DIR_NONE)
                rf_foot ^= 1;
            sound_tick(game.sound);
            if (game.flash) {
                game.flash = false;
                flash = 2;
                video_flash(true);
                sound_exit();
            }
        }
        // How far the moves of the tick have come: they end with the next
        // one, so what stops always reaches its cell.
        slide = tick_acc >= tick_len ? 0 : 16 - tick_acc * 16 / tick_len;
        if (by_gdash) {  // GDash's engine counts the time itself
            if (game.state == PS_ALIVE && game.time != shown_time) {
                shown_time = game.time;
                if (game.time && game.time < 10)
                    sound_clock();
            }
        } else if (game.state == PS_ALIVE && ++sec >= fps) {
            sec = 0;
            cave_second();
            if (game.time && game.time < 10)
                sound_clock();
        }
        if (score + game.score >= next_life) {
            next_life += LIFE_POINTS;
            if (lives < 9)
                lives++;
            sound_life();
        }

        switch (game.state) {
        case PS_ALIVE:
        case PS_HATCHING:
            status_play();
            camera(false);
            break;
        case PS_DEAD:
            status_play();
            // the cave goes on; after a while the button ends it
            if (after < 255)
                after++;
            if ((after > 50 && (pressed & IN_BUTTON)) || after == 255) {
                cover_cave(1);
                return END_DIED;
            }
            break;
        case PS_TIMEOUT:
            status_center("OUT OF TIME");
            if (pressed & IN_BUTTON) {
                cover_cave(1);
                return END_DIED;
            }
            break;
        case PS_EXITED:
            // the time left is counted into the score (GDash's caves give
            // their own points per second)
            if (game.time) {
                game.time--;
                game.score += by_gdash ? file.own.timevalue : 1;
                if (!(frame & 1))
                    sound_bonus();
                status_game();
            } else {
                cover_cave(1);
                return END_EXITED;
            }
            break;
        }
        next_frame();
    }
}

// ---------------------------------------------------------------- editor

// The editor changes an own cave in file.own - GDash's elements, played by
// GDash's engine - and shows it from cave[], both alike; a try plays it
// from file.own. Its keys (also on its help page, H):
//   cursor keys, joystick   move the cursor
//   fire, Space, Return     put the element chosen; held, it draws
//   1-9, 0, I, X            choose the element; again: a firefly or a
//                           butterfly gets its next starting direction
//   G                       take the element under the cursor
//   V                       name and values      T  try the cave
//   S                       save it into its slot
//   + -                     the next and the last slot
//   C                       a new cave           D  empty the slot
//   Run/Stop                back to the title
// What would lose changes not saved, or the slot, wants its key twice.

// The editor's code is an overlay (link.ld): in the RAM under the KERNAL,
// loaded from the disk when E is pressed on the title
#ifdef __mos__
#define EDITOR      __attribute__((section(".editor"), noinline))
#define EDITOR_DATA __attribute__((section(".editor.data")))
#else
#define EDITOR
#define EDITOR_DATA
#endif

#define PENS     12
#define PEN_FLY  6   // the firefly; the butterfly is next
#define NAME_LEN 21  // what the status line has room for (mkcave.py)
#define KEY_STOP 0x03  // Run/Stop, as the editor's key
#define KEY_DEL  0x14

static const char pen_keys[PENS] = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 'I', 'X'};
static const uint8_t pen_elem[PENS] = {O_SPACE, O_DIRT, O_BRICK, O_STEEL, O_STONE, O_DIAMOND, O_FIREFLY_1,
                                       O_BUTTER_1, O_AMOEBA, O_MAGIC_WALL, O_INBOX, O_PRE_OUTBOX};
static const uint8_t pen_tile[PENS] = {T_SPACE, T_DIRT, T_BRICK, T_STEEL, T_BOULDER, T_DIAMOND0,
                                       T_FIREFLY0, T_BUTTERFLY0, T_AMOEBA0, T_MAGIC0, T_INBOX0, T_OUTBOX0};
static const char *const pen_name[PENS] = {"SPACE", "DIRT", "BRICK WALL", "STEEL WALL", "BOULDER",
                                           "EMERALD", "FIREFLY", "BUTTERFLY", "AMOEBA",
                                           "MAGIC WALL", "INBOX", "EXIT"};
static const char *const dir_name[4] = {"UP", "RIGHT", "DOWN", "LEFT"};
static const char name_chars[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /:.!-,";  // as cavekit.py

static uint8_t slot;          // the one edited, from 0
static uint8_t pen;           // the element chosen
static uint8_t pen_dir = DIR_LEFT;  // a firefly's or butterfly's
static bool dirty;            // changed since loaded or saved
static bool have_slot;        // the slot is on the disk
static uint8_t again;         // the key that does it when pressed again
static uint8_t note;          // frames a note stays in the status line
static bool edit_shown;       // the status line shows the editor's line
// what a new cave starts with: Boulder Dash 1's rules (tools/cavekit.py)
static const uint8_t new_params[GD_NEW_PARAMS_SIZE] EDITOR_DATA = GD_NEW_PARAMS;

static EDITOR bool pen_fly(void) {
    return pen == PEN_FLY || pen == PEN_FLY + 1;
}

static EDITOR void digits2(char *p, uint8_t v) {
    p[0] = '0' + v / 10;
    p[1] = '0' + v % 10;
}

// v right-aligned in three characters
static EDITOR void digits3(char *p, uint16_t v) {
    for (uint8_t k = 3; k--;) {
        p[k] = v || k == 2 ? '0' + v % 10 : ' ';
        v /= 10;
    }
}

// The element, where the cursor is, the slot, * if not saved:
// "[tile] FIREFLY LEFT      12,05  OWN 03*"
static EDITOR void edit_status(void) {
    static char line[36];
    memset(line, ' ', 35);
    uint8_t n = strlen(pen_name[pen]);
    memcpy(line, pen_name[pen], n);
    if (pen_fly())
        memcpy(line + n + 1, dir_name[pen_dir], strlen(dir_name[pen_dir]));
    digits2(line + 18, cur_x);
    line[20] = ',';
    digits2(line + 21, cur_y);
    memcpy(line + 25, "OWN", 3);
    digits2(line + 29, slot + 1);
    line[31] = dirty ? '*' : ' ';
    status_tile(2, pen_tile[pen]);
    status_print(4, line);
    edit_shown = true;
}

// A note in the status line for two seconds
static EDITOR void edit_note(const char *text) {
    status_center(text);
    note = 100;
    edit_shown = false;
}

static EDITOR void set_dirty(void) {
    dirty = true;
    edit_shown = false;
}

// A new cave: steel frame, dirt, the inbox top left, the exit bottom right
// (as cavekit.py's empty_map), with Boulder Dash 1's rules
static EDITOR void new_cave(void) {
    memset(&file.own, 0, sizeof file.own);
    memcpy(&file.own, new_params, sizeof new_params);
    uint8_t *m = file.own.map;
    memset(m, O_DIRT, CAVE_SIZE);
    memset(m, O_STEEL, CAVE_W);
    memset(m + CAVE_SIZE - CAVE_W, O_STEEL, CAVE_W);
    for (uint16_t i = CAVE_W; i < CAVE_SIZE; i += CAVE_W)
        m[i - 1] = m[i] = O_STEEL;
    m[2 * CAVE_W + 2] = O_INBOX;
    m[(CAVE_H - 3) * CAVE_W + CAVE_W - 1] = O_PRE_OUTBOX;
}

// The edited cave on the screen, still: magic walls and the exit as such
static EDITOR void edit_view(void) {
    memcpy(cave, file.own.map, CAVE_SIZE);
    memset(&game, 0, sizeof game);
    game.magic_state = MW_ACTIVE;
    memset(moved, DIR_NONE, CAVE_SIZE);
    memset(trail_kind, TR_NONE, sizeof trail_kind);
    slide = 0;
    by_gdash = true;
    show_cursor = true;
    edit_shown = false;
    note = 0;
}

static EDITOR void edit_camera(bool jump) {
    camera_at(cur_x * 16 + 8, cur_y * 16 + 8, jump);
}

// The slot from the disk; an empty one (or none) gives a new cave
static EDITOR void edit_load(void) {
    have_slot = load_own(slot);
    if (!have_slot || !file.own.time)
        new_cave();
    if (cur_x >= file.own.w)
        cur_x = file.own.w - 1;
    if (cur_y >= file.own.h)
        cur_y = file.own.h - 1;
    dirty = false;
    edit_view();
}

// What keeps the cave from being played, or 0
static EDITOR const char *edit_check(void) {
    bool inbox = false, exit = false;
    for (uint16_t i = 0; i < CAVE_SIZE; i++) {
        uint8_t e = file.own.map[i];
        if (e == O_INBOX || (e >= O_PLAYER && e <= O_PLAYER_STIRRING))  // or GDash's player at once
            inbox = true;
        if (e >= O_PRE_OUTBOX && e <= O_INVIS_OUTBOX)
            exit = true;
    }
    return !inbox ? "THE CAVE NEEDS AN INBOX" : exit ? 0 : "THE CAVE NEEDS AN EXIT";
}

// A firefly's or butterfly's element: GDash's go left, up, right, down
static EDITOR uint8_t pen_element(void) {
    return pen_elem[pen] + (pen_fly() ? (pen_dir + 1) & 3 : 0);
}

// The element chosen where the cursor is. There is one inbox: the old one
// turns to dirt.
static EDITOR void edit_put(void) {
    uint16_t i = cur_y * CAVE_W + cur_x;
    uint8_t e = pen_element();
    if (file.own.map[i] == e)
        return;
    if (e == O_INBOX)
        for (uint16_t j = 0; j < CAVE_SIZE; j++)
            if (file.own.map[j] == O_INBOX)
                file.own.map[j] = cave[j] = O_DIRT;
    file.own.map[i] = cave[i] = e;
    set_dirty();
    sound_crackle();
}

// The element under the cursor becomes the one chosen
static EDITOR void edit_take(void) {
    uint8_t e = file.own.map[cur_y * CAVE_W + cur_x];
    for (uint8_t k = 0; k < PENS; k++) {
        uint8_t b = pen_elem[k];
        uint8_t fly = k == PEN_FLY || k == PEN_FLY + 1;
        if (e == b || (fly && e >= b && e < b + 4)) {
            pen = k;
            if (fly)
                pen_dir = (e - b + 3) & 3;
        }
    }
    edit_shown = false;
}

// Play the cave once, then back to the editor
static EDITOR void edit_try(void) {
    const char *why = edit_check();
    if (why) {
        edit_note(why);
        return;
    }
    if (!have_gdash) {
        edit_note("NO GDASH ENGINE ON THE DISK");
        return;
    }
    use_own_cave();
    show_cursor = false;
    lives = 1;
    score = 0;
    next_life = 0xFFFFFFFF;
    play_cave();
    edit_view();
    edit_camera(true);
    cover_cave(0);
}

static EDITOR void edit_save(void) {
    const char *why = edit_check();
    if (why) {
        edit_note(why);
        return;
    }
    busy("SAVING");
    bool ok = have_slot && disk_save(own_name(slot), &file.own, sizeof file.own);
    not_busy();
    if (ok) {
        dirty = false;
        sound_bonus();
    }
    edit_note(ok ? "SAVED" : "COULD NOT SAVE");
}

// The slot empty again on the disk (its cave is no longer played)
static EDITOR void edit_empty(void) {
    memset(&file.own, 0, sizeof file.own);
    busy("SAVING");
    bool ok = have_slot && disk_save(own_name(slot), &file.own, sizeof file.own);
    not_busy();
    new_cave();
    dirty = false;
    edit_view();
    edit_note(ok ? "THE SLOT IS EMPTY" : "COULD NOT SAVE");
}

// Some keys act only when pressed twice in a row: they would lose what is
// not saved (when it is all saved: once is enough, unless always)
static EDITOR bool twice(uint8_t key, bool always, const char *what) {
    if (again == key || (!dirty && !always)) {
        again = 0;
        return true;
    }
    again = key;
    edit_note(what);
    return false;
}

// Wait on a page of the editor for a key or the button
static EDITOR void page_wait(void) {
    bool armed = false;
    for (;;) {
        title_frame();
        if (get_key() || (pressed & IN_RESTART) || (armed && (pressed & IN_BUTTON)))
            break;
        if (!(held & IN_BUTTON))
            armed = true;
    }
}

static EDITOR void edit_help(void) {
    static const char *const lines[8] = {
        "MOVE     CURSOR KEYS OR JOYSTICK",
        "PUT      FIRE OR SPACE, HELD: DRAW",
        "1-0 I X  CHOOSE, AGAIN: DIRECTION",
        "G        CHOOSE WHAT THE CURSOR IS ON",
        "V        NAME AND VALUES   T  TRY IT",
        "S        SAVE   + -  NEXT, LAST SLOT",
        "C        NEW CAVE   D  EMPTY THE SLOT",
        "RUN/STOP BACK TO THE TITLE",
    };
    video_clear();
    status_center("ANY KEY: BACK");
    video_text_in(CENTRE(11), 0, "CAVE EDITOR", title_row);
    for (uint8_t i = 0; i < 8; i++)
        video_text(2, 16 + i * 16, lines[i]);
    // the elements with their keys, two rows of six
    char key[2] = {0, 0};
    for (uint8_t k = 0; k < PENS; k++) {
        uint8_t col = 2 + (k % 6) * 6, y = 144 + (k / 6) * 16;
        key[0] = pen_keys[k];
        video_text(col, y, key);
        video_tile(col + 2, y, pen_tile[k]);
    }
    page_wait();
    video_clear();
    edit_shown = false;
    note = 0;
}

// The values page: a line each, the one chosen shining
#define VALUES 8
#define VAL_Y0 8
static const char *const val_text[VALUES] = {
    "NAME", "TIME          SECONDS", "EMERALDS      TO OPEN THE EXIT", "VALUE         POINTS EACH",
    "EXTRA         EACH AFTER THAT", "SPEED         MS PER STEP", "AMOEBA        SECONDS SLOW",
    "MAGIC         SECONDS, 0: NO END"};
static const uint8_t val_min[VALUES] = {0, 1, 0, 0, 0, 50, 0, 0};
static const uint16_t val_max[VALUES] = {0, 999, 255, 99, 99, 250, 999, 999};
static uint16_t c64_speed;  // a C64 cave's speed (GDash's scheduling) as it starts

static EDITOR uint16_t val_get(uint8_t i) {
    GdCaveFile *f = &file.own;
    switch (i) {
    case 1:
        return f->time;
    case 2:
        return f->diamonds_needed < 0 ? 0 : f->diamonds_needed;
    case 3:
        return f->diamond_value;
    case 4:
        return f->extra_diamond_value;
    case 5:
        return f->scheduling ? c64_speed : f->speed;
    case 6:
        return f->amoeba_time;
    }
    return f->magic_wall_time;
}

// A new speed is in milliseconds, also for a C64 cave
static EDITOR void val_set(uint8_t i, uint16_t v) {
    GdCaveFile *f = &file.own;
    switch (i) {
    case 1:
        f->time = v;
        break;
    case 2:
        f->diamonds_needed = v;
        break;
    case 3:
        f->diamond_value = v;
        break;
    case 4:
        f->extra_diamond_value = v;
        break;
    case 5:
        f->scheduling = 0;
        f->speed = v;
        break;
    case 6:
        f->amoeba_time = v;
        break;
    default:
        f->magic_wall_time = v;
    }
}

static EDITOR void val_line(uint8_t i, bool chosen) {
    static char line[37];
    memset(line, ' ', 36);
    memcpy(line, val_text[i], strlen(val_text[i]));
    if (i)
        digits3(line + 9, val_get(i));
    else
        memcpy(line + 10, file.own.name, strlen(file.own.name));
    video_text_in(2, VAL_Y0 + i * 16, line, chosen ? title_row : font_row);
}

// Up and down choose a line, left and right change its value (held: on and
// on, faster after a while), letters and Del the name. Return, V, Run/Stop
// or the button (but not on the name, where Space is a space) go back.
static EDITOR void edit_values(void) {
    if (file.own.scheduling && have_gdash) {  // the speed GDash starts it with
        gd_start(&file.own, 0);
        c64_speed = gd.speed;
        memcpy(cave, file.own.map, CAVE_SIZE);
    }
    video_clear();
    status_center("NAME AND VALUES");
    video_text(CENTRE(33), 144, "UP/DOWN CHOOSE  LEFT/RIGHT CHANGE");
    video_text(CENTRE(31), 160, "TYPE THE NAME  RETURN OR V BACK");
    uint8_t sel = 1, rep = 0;
    bool armed = false;
    for (uint8_t i = 0; i < VALUES; i++)
        val_line(i, i == sel);
    for (uint16_t f = 0;; f++) {
        if (f % 3 == 0)
            video_shine(f / 3);
        title_frame();
        uint8_t key = get_key();
        uint8_t old = sel;
        if ((pressed & IN_UP) && sel)
            sel--;
        if ((pressed & IN_DOWN) && sel < VALUES - 1)
            sel++;
        if (sel != old) {
            val_line(old, false);
            val_line(sel, true);
        }
        uint8_t lr = held & (IN_LEFT | IN_RIGHT);
        if (!lr)
            rep = 0;
        else if (sel && (rep == 0 || (rep >= 20 && (rep & 1)))) {
            uint16_t v = val_get(sel), d = rep >= 100 ? 10 : 1;
            if (lr & IN_RIGHT)
                v = v + d > val_max[sel] ? val_max[sel] : v + d;
            else
                v = v < val_min[sel] + d ? val_min[sel] : v - d;
            val_set(sel, v);
            val_line(sel, true);
            dirty = true;
        }
        if (lr && rep < 255)
            rep++;
        if (!sel && key && key != '\r') {
            uint8_t n = strlen(file.own.name);
            if (key == KEY_DEL && n)
                file.own.name[n - 1] = 0;
            else if (n < NAME_LEN && key && strchr(name_chars, key))
                file.own.name[n] = key;
            else
                continue;
            dirty = true;
            val_line(0, true);
            armed = false;  // Space was a space
            continue;
        }
        if (key == '\r' || key == 'V' || (pressed & IN_RESTART) || (sel && armed && (pressed & IN_BUTTON)))
            break;
        if (!(held & IN_BUTTON))
            armed = true;
    }
    video_shine(0);
    video_clear();
    edit_shown = false;
    note = 0;
}

static EDITOR void editor(void) {
    play_mode = PLAY_TEST;
    again = 0;
    edit_load();
    cur_x = cur_y = 2;
    edit_camera(true);
    memset(covered, 1, sizeof covered);
    cover_cave(0);
    bool armed = false;  // fire from the title must be let go first
    uint8_t rep = 0;
    for (;;) {
        if (note && !--note)
            edit_shown = false;
        if (!edit_shown && !note)
            edit_status();
        next_frame();
        edit_camera(false);
        uint8_t key = get_key();
        if (pressed & IN_RESTART)
            key = KEY_STOP;
        if (key && key != again)
            again = 0;

        // move: at once, then on and on while held
        uint8_t dir = held & (IN_UP | IN_DOWN | IN_LEFT | IN_RIGHT);
        if (!dir) {
            rep = 0;
        } else {
            if (rep == 0 || (rep >= 12 && (rep & 3) == 0)) {
                if ((dir & IN_LEFT) && cur_x)
                    cur_x--;
                if ((dir & IN_RIGHT) && cur_x < file.own.w - 1)
                    cur_x++;
                if ((dir & IN_UP) && cur_y)
                    cur_y--;
                if ((dir & IN_DOWN) && cur_y < file.own.h - 1)
                    cur_y++;
                edit_shown = false;
            }
            if (++rep > 15)
                rep = 12;
        }
        if (!(held & IN_BUTTON))
            armed = true;
        else if (armed)
            edit_put();

        for (uint8_t k = 0; k < PENS; k++)
            if (key == pen_keys[k]) {
                if (k == pen && pen_fly())
                    pen_dir = (pen_dir + 1) & 3;
                pen = k;
                edit_shown = false;
            }
        switch (key) {
        case 'G':
            edit_take();
            break;
        case 'H':
            edit_help();
            armed = false;
            break;
        case 'V':
            edit_values();
            armed = false;
            break;
        case 'T':
            edit_try();
            armed = false;
            break;
        case 'S':
            edit_save();
            break;
        case 'C':
            if (twice(key, true, "C AGAIN: A NEW CAVE")) {
                new_cave();
                edit_view();
                set_dirty();
            }
            break;
        case 'D':
            if (twice(key, true, "D AGAIN: EMPTY THE SLOT"))
                edit_empty();
            break;
        case '+':
        case '-':
            if (twice(key, false, key == '+' ? "NOT SAVED - + AGAIN: NEXT SLOT" : "NOT SAVED - - AGAIN: LAST SLOT")) {
                slot = key == '+' ? (slot + 1) % OWN_SLOTS : (slot + OWN_SLOTS - 1) % OWN_SLOTS;
                edit_load();
            }
            break;
        case KEY_STOP:
            if (twice(key, false, "NOT SAVED - RUN/STOP AGAIN: LEAVE")) {
                show_cursor = false;
                cover_cave(1);
                return;
            }
            break;
        }
    }
}

// A game: the caves from the one picked on the title, or the own caves,
// until the lives are gone; then a good score gets into the table (the
// game's caves only)
static void play_game(void) {
    lives = LIVES;
    score = 0;
    next_life = LIFE_POINTS;
    play_mode = start_cave == CAVE_COUNT ? PLAY_OWN : PLAY_CAVES;
    cave_no = play_mode == PLAY_OWN ? 0 : start_cave;
    level = start_level;
    bool have_cave = true;
    while (lives) {
#ifdef SCREENCAST
        // after the last cave with moves
        if (cave_no >= DEMO_LAST || cave_no >= DEMO_CAVES)
            demo_end();
#endif
        if (!(have_cave = play_mode == PLAY_OWN ? next_own() : next_cave()))
            break;
#ifdef SCREENCAST
        demo_p = demo_moves;
        demo_left = 0;
#endif
        uint8_t end = play_cave();
        score += game.score;
        if (end == END_EXITED)
            cave_no++;
        else
            lives--;
#ifdef SCREENCAST
        if (end != END_EXITED)  // something went wrong
            demo_end();
#endif
    }
    status_center(have_cave ? "GAME OVER" : play_mode == PLAY_OWN ? "NO OWN CAVES ON THE DISK" : "NO CAVES ON THE DISK");
    sound_off();
    wait_button(250);
    uint8_t rank = have_cave && play_mode == PLAY_CAVES ? hiscore_rank(score) : HS_COUNT;
    hs_new = rank;
    if (rank < HS_COUNT) {
        HiScore *e = hiscore_insert(rank);
        e->score = score;
        e->cave = cave_no;
        e->level = level;
        enter_name(e, rank);
        save_scores();
    }
}

// What the NMI vector points to: RTI
static const uint8_t rti = 0x40;

// Banks 2 and 3 take a byte (the C65 ROM there is write-protected at first)
static bool rom_takes(uint8_t v) {
    static uint8_t probe;
    dma_begin(0, 0);
    dma_fill(v, 0xFFF0, LOGO_BANK, 1);
    dma_copy(0xFFF0, LOGO_BANK, (uint16_t)&probe, 0, 1);
    dma_run();
    return probe == v;
}

// The C65 ROM's banks 2 and 3 writable (mem.h): the hypervisor's call $70
// turns its write protection on or off
static bool rom_writable(void) {
    if (rom_takes(0xA5) && rom_takes(0x5A))
        return true;
    __asm__ volatile("lda #$70\n sta $d640\n clv\n sei\n ldz #0" ::: "a", "x", "y", "memory");
    return rom_takes(0xA5) && rom_takes(0x5A);
}

int main(void) {
    __asm__ volatile("sei");
    POKE(0x00, 65);                     // 40 MHz
    POKE(0xD02F, 0x47);                 // VIC-IV registers on
    POKE(0xD02F, 0x53);
    POKE(0xDC0D, 0x7F);                 // no CIA interrupts
    POKE(0xDD0D, 0x7F);
    PEEK(0xDC0D);
    PEEK(0xDD0D);
    POKE(0xD01A, 0x00);                 // no VIC interrupts
    POKE(0xD019, 0xFF);
    // The KERNAL out of the way, for the editor's code under it (mem.h): no
    // mapping in the upper 32K, where the C65 KERNAL is mapped, and RAM at
    // $E000 through the CPU port; Restore's NMI returns at once.
    __asm__ volatile("lda #0\n tax\n tay\n taz\n map\n eom\n lda #$35\n sta $01\n ldz #0"
                     ::: "a", "x", "y", "memory");
    POKE(0xFFFA, (uint16_t)&rti);
    POKE(0xFFFB, (uint16_t)&rti >> 8);
    pal = !(PEEK(0xD06F) & 0x80);

    video_init();
    sound_init();
    init_tiles();
    // The tiles from the disk - without the spinner, which is made of
    // them -, the title logo and the high scores (mem.h)
    disk_load("SMARAGD.TILES", GFX_BANK, TILES_OFF);
    bool rom_ram = rom_writable();
    have_logo = rom_ram && load("LOADING", "SMARAGD.LOGO", LOGO_BANK, LOGO_OFF);
    // GDash's engine for the own caves, and the calls into it
    have_gdash = rom_ram && disk_load("SMARAGD.LOW", 0, LOW_AT) && load("LOADING", "SMARAGD.GD", GD_BANK, GD_OFF);
    hiscore_load();

    for (bool scores = false;;) {
        if (title_screen(scores)) {
            if (load("LOADING THE EDITOR", "SMARAGD.EDIT", 0, EDIT_AT))
                editor();
            scores = false;
        } else {
            play_game();
            scores = true;  // the table comes first after a game
        }
    }
}
