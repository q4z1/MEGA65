// Smaragd Dash: a Boulder Dash style game for the MEGA65.
//
// main.c runs the game: the title screen with its music, where the joystick
// picks the level and the cave to start with, and which takes turns with
// the high score table; then the caves: a cave is
// loaded from the disk, uncovered, Rockford hatches, and the cave
// runs in steps of the cave's speed while the screen is redrawn every frame
// (50 Hz PAL, 60 Hz NTSC). After the game a good score gets three letters
// in the table, as in the arcades. The rules are GDash's (gdengine.c, in
// bank 2), the display is in video.c, the table and its file in hiscore.c.
//
// E on the title opens the cave editor: it edits the own caves, which lie
// in slots on the disk (OWN01, OWN02, ...; tools/cavekit.py puts caves from
// GDash there), tries them out and saves them. The title offers them to
// play after the game's caves.
//
// Built with -DSCREENCAST (toolchain/tools/bin/mega65-cast), the game plays
// itself: the title runs for a while, then the caves play the moves that
// tools/solve.c found for them (DEMOnn on the disk, nn the cave's number,
// loaded with each cave; the caves without are left out), and after the
// last one the emulator is told to stop, which ends the recording.
// With -DTOUR as well (tools/record-tour.sh) it plays the demo caves in
// the slots instead, with their moves (TOUR01, ...).

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
#endif                        // of them (DEMO_LIST: the caves with moves)
#ifndef DEMO_FIRST
#define DEMO_FIRST 1          // -DDEMO_FIRST=9 -DDEMO_LAST=9: the ninth alone
#endif
#ifndef TOUR
static const uint8_t demo_list[] = DEMO_LIST;
static uint8_t demo_at = DEMO_FIRST - 1;  // in demo_list
#endif
#endif

#define LIVES       3
#define LIFE_POINTS 500   // an extra life every so many points
#define START_STEP  5     // the title offers caves 1, 6, 11, ... to start with
#define MAX_X       (CAVE_W * 16 - VIEW_W)
#define MAX_Y       (CAVE_H * 16 - VIEW_H)

#define ICON(n) (0x80 + (n))

// tile per cell, for video_render; written in every frame before it is read
static uint8_t tiles[CAVE_SIZE] __attribute__((section(".lowbss")));
static uint8_t covered[CAVE_SIZE / 8];  // a bit per cell, 1: still hidden (start and end)
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
// glitter that fades slowly, calm behind its quick round (both in the
// colours of the creature: the alternative ones, the stonefly and the
// dragonfly have their own); a faint mist that drifts up where the ghost
// was; crumbs where Rockford dug and behind a cow, purple ones behind the
// biter, grit behind the chasing boulder and whatever falls or flies, a
// glint behind a falling emerald, smoke behind a rocket, tiny bubbles
// behind a bladder; dust beside a boulder that lands. Only the drawing
// knows of it.
enum {
    TR_NONE, TR_EMBERS, TR_GLITTER, TR_CRUMBS, TR_DUST_L, TR_DUST_R,
    TR_EMBERS_ALT, TR_GLITTER_ALT, TR_GLITTER_STONE, TR_GLITTER_DRAGON, TR_MIST,
    TR_CRUMBS_BITER, TR_CRUMBS_GRIT, TR_DROPS, TR_GLINT, TR_SMOKE
};
static const uint8_t trail_first[] = {0, T_EMBERS0, T_GLITTER0, T_CRUMBS0, T_DUSTL0, T_DUSTR0,
                                      T_EMBERS_ALT0, T_GLITTER_ALT0, T_GLITTER_STONE0, T_GLITTER_DRAGON0, T_MIST0,
                                      T_CRUMBS_BITER0, T_CRUMBS_GRIT0, T_DROPS0, T_GLINT0, T_SMOKE0};
static const uint8_t trail_last[] = {0, T_EMBERS3, T_GLITTER3, T_CRUMBS2, T_DUSTL1, T_DUSTR1,
                                     T_EMBERS_ALT3, T_GLITTER_ALT3, T_GLITTER_STONE3, T_GLITTER_DRAGON3, T_MIST3,
                                     T_CRUMBS_BITER2, T_CRUMBS_GRIT2, T_DROPS2, T_GLINT3, T_SMOKE2};
static const uint8_t trail_step[] = {0, 3, 5, 3, 5, 5, 3, 5, 5, 4, 5, 3, 3, 4, 3, 10};  // frames per stage
// The trail of each creature's event (EV_*; 0: none)
static const uint8_t event_trail[] = {TR_EMBERS, TR_GLITTER, 0, 0, TR_EMBERS_ALT, TR_GLITTER_ALT,
                                      TR_GLITTER_STONE, TR_GLITTER_DRAGON, TR_MIST, TR_CRUMBS,
                                      TR_CRUMBS_BITER, TR_DROPS, TR_CRUMBS_GRIT, TR_CRUMBS_GRIT, TR_GLINT,
                                      TR_SMOKE};
#define TRAILS 64
static uint16_t trail_cell[TRAILS];
static uint8_t trail_kind[TRAILS];  // TR_*
static uint8_t trail_tile[TRAILS];  // its stage now
static uint8_t trail_wait[TRAILS];  // frames until the next
static uint8_t trail_next;

static bool pal;
static uint8_t frame;
static uint8_t held, pressed;       // IN_* now, and newly pressed this frame
// Keys as the MEGA65 types them ($D610)
#define KEY_RUNSTOP 0x03
#define KEY_HELP    0x1F
#define KEY_F1      0xF1
#ifdef SHOT_AT
// -DSHOT_AT=n (tools/record-shots.sh): after n frames the emulator is told
// to stop (0, then $42 to $D6CF, with -testing), and Xemu's -screenshot
// takes the picture of that moment
static uint16_t shot_frames;

static void shot_tick(void) {
    if (++shot_frames == SHOT_AT) {
        POKE(0xD6CF, 0);
        POKE(0xD6CF, 0x42);
        for (;;)
            ;
    }
}
#define SHOT_TICK() shot_tick()
#else
#define SHOT_TICK()
#endif
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
static uint8_t start_game, start_own;    // ... of this game, from this slot

// The own caves' games: the partitions of the disk (but CAVES), OWN1, ...
// at first, renamed in the editor; each with OWN_SLOTS slots. A disk
// without them (of an older version) has its slots in the directory
// itself: one game without a name.
#define GAMES_MAX 3
static char game_name[GAMES_MAX][9];
static uint8_t games = 1, own_game;     // own_game: the one played or edited
enum { PLAY_CAVES, PLAY_OWN, PLAY_TEST };  // the game's caves, the own ones, one in the editor
static uint8_t play_mode;
static bool show_cursor;            // the editor's, at cur_x, cur_y
static uint8_t cur_x, cur_y;
static uint32_t score;              // before the current cave
static uint32_t next_life;
static bool have_logo;              // the logo file was on the disk
static bool rom_ram;                // the C65 ROM's banks 2 and 3 writable (mem.h)
#ifndef SCREENCAST
static bool rom_toggled;            // ... by the hypervisor, which protects them again
static bool rom_saved;              // ... and kept in the attic RAM, for BASIC
#endif
static bool kept;                   // the editor's cave kept (KEEP_BANK) ...
static bool dirty;                  // ... changed since loaded or saved

// The cave being played, as loaded from the disk - one of the game's
// (CAVE01-1, ..., tools/mkcave.py) or an own one (a slot OWN01, ...; time 0
// is an empty slot) -, as GDash's engine plays it (GdCaveFile,
// tools/cavekit.py), and as the editor edits it. It lies where GDash's
// engine sees it (shared.ld, mem.h).
typedef struct {
    GdCaveFile own;
} CaveFile;
extern CaveFile file;
_Static_assert(sizeof(CaveFile) <= FILE_SIZE, "the cave reaches the C stack (shared.ld)");
_Static_assert(sizeof(GdState) <= GD_STATE_SIZE, "GdState reaches the cave (shared.ld)");
static CaveDef cave_def;
static uint8_t loaded = 0xFF, loaded_level;  // cave_no and level of file, one of the game's
static bool have_gdash;             // GDash's engine is there (bank 2): no caves without it
struct game game;

// For everything outside the cave: animations, sounds (xorshift16)
uint16_t rnd_state = 0xACE1;  // not static: the check of src/sound.s (sound.c)

__attribute__((noinline)) uint8_t rnd(void) {
    rnd_state ^= rnd_state << 7;
    rnd_state ^= rnd_state >> 9;
    rnd_state ^= rnd_state << 8;
    return (uint8_t)rnd_state;
}
#ifdef SCREENCAST
// the cave's moves (DEMOnn, see tools/solve.c), where the editor's code
// would be: the screencast never opens the editor
#define demo_moves ((uint8_t *)EDIT_AT)
_Static_assert(DEMO_MAX <= EDIT_SIZE, "the moves in the editor's place");
#endif

#if defined(EDITDEMO) && !defined(EDITTEST)
#define EDITTEST 255  // the editor's video: its script to the end
#endif
#if defined(EDITTEST) || defined(FLOWTEST)
// The editor's test (tests/test_editor.sh builds with -DEDITTEST=n): keys
// and joystick come from this script, a step per line: so many frames with
// these IN_* held, the key typed in the first of them. A step of 0 frames
// is a stop: at the n-th, Xemu (with -testing) is told to exit and writes
// its screenshot. Built with -DEDITDEMO, the script is the one of the
// editor's video (tools/record-editor.sh): it plays to its end, or with
// -DEDITTEST=n to its n-th stop, a picture for EDITOR.md (SHOT).
//
// The game's flow (tests/test_flow.py builds with -DFLOWTEST) has a script
// of its own: a stop is a checkpoint (flow_check), a step of 0 frames with a
// W_* as its key waits, its IN_* held, until that happens (FLOW_WAIT frames
// at most), and FLOW_END tells Xemu to stop.
#ifndef TRY_WAIT
#define TRY_WAIT 200  // frames from T until Rockford can walk
#endif
#define STEP1(key) {1, key, 0}, {10, 0, 0}  // a key and a short look
#define MOVE(in)   {2, 0, in}, {10, 0, 0}   // the cursor one cell on
#define PUT        {3, 0, IN_BUTTON}, {16, 0, 0}
#define SHOT       {0, 0, 0}
#ifdef FLOWTEST
enum { SCR_NONE, SCR_TITLE, SCR_CAVE, SCR_NAME };  // where the game is
enum { W_TITLE = 1, W_ALIVE, W_EXITED, W_DEAD, W_TIMEOUT, W_NAME, FLOW_END };
#define FLOW_WAIT 3000
#define WAIT(w, in) {0, w, in}
#define CAVE_OUT    WAIT(W_ALIVE, 0), SHOT, {40, 0, IN_RIGHT}, WAIT(W_EXITED, 0)
#define GIVE_UP     {2, 0, IN_RESTART}, WAIT(W_DEAD, 0), {80, 0, 0}, {2, 0, IN_BUTTON}
#define NEXT_START  {2, 0, IN_RIGHT}, {10, 0, 0}
#define CAVE_FAILS  WAIT(W_ALIVE, 0), SHOT, WAIT(W_TIMEOUT, 0), {60, 0, 0}, {2, 0, IN_BUTTON}
_Static_assert(CAVE_COUNT == 56 && START_STEP == 5, "the flow script picks cave 51 and plays it to the last");
#endif
static const uint8_t test_script[][3] = {
#ifdef FLOWTEST
    WAIT(W_TITLE, 0), SHOT,                               // 1: the title
    {100, 0, 0}, NEXT_START, NEXT_START, NEXT_START, NEXT_START, NEXT_START,
    NEXT_START, NEXT_START, NEXT_START, NEXT_START, NEXT_START,
    SHOT,                                                 // 2: cave 51 picked
    {2, 0, IN_BUTTON},
    CAVE_FAILS, CAVE_OUT, CAVE_OUT, CAVE_OUT, CAVE_OUT, CAVE_OUT,  // 3-8: caves 51-56
    WAIT(W_ALIVE, 0), SHOT,                               // 9: level 2, cave 1
    {2, 0, IN_PAUSE}, {100, 0, 0}, SHOT, {100, 0, 0}, SHOT,  // 10, 11: paused
    {2, 0, IN_PAUSE}, {100, 0, 0}, SHOT,                  // 12: on again
    WAIT(W_TIMEOUT, 0), SHOT,                             // 13: out of time
    {60, 0, 0}, {2, 0, IN_BUTTON}, WAIT(W_ALIVE, 0), SHOT,  // 14: a life less
    GIVE_UP, WAIT(W_ALIVE, 0), SHOT,                      // 15: Run/Stop
    GIVE_UP, WAIT(W_ALIVE, 0), SHOT,                      // 16: again
    GIVE_UP, WAIT(W_ALIVE, 0), GIVE_UP, WAIT(W_ALIVE, 0),  // the intermissions' lives
    GIVE_UP, WAIT(W_NAME, 0), {30, 0, 0}, SHOT,           // 17: game over, a high score
    {1, 'Z', 0}, {10, 0, 0}, {1, 'Q', 0}, {10, 0, 0}, {1, 'X', 0}, {10, 0, 0},
    WAIT(W_TITLE, 0), SHOT,                               // 18: the table first
    {250, 0, 0}, {250, 0, 0}, {250, 0, 0}, {250, 0, 0}, {250, 0, 0}, {250, 0, 0},
    {250, 0, 0}, {250, 0, 0}, {250, 0, 0}, {250, 0, 0}, {250, 0, 0}, {250, 0, 0},
    SHOT,                                                 // 19: a minute later
    NEXT_START, NEXT_START, {2, 0, IN_UP}, {10, 0, 0}, {2, 0, IN_UP}, {10, 0, 0},
    {2, 0, IN_BUTTON},                                    // the own caves in level 3
    WAIT(W_ALIVE, 0), SHOT,                               // 20: slot 1, level 3's own file
    {40, 0, IN_RIGHT}, WAIT(W_EXITED, 0),
    WAIT(W_ALIVE, 0), SHOT,                               // 21: the next level, the first's file
    {1, KEY_F1, 0}, WAIT(W_TITLE, 0),
    SHOT, WAIT(FLOW_END, 0),                              // 22: the end
#elif defined(EDITDEMO)
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
    {1, 'E', 0}, {60, 0, 0},                              // all elements: to the clock
    MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT),
    MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT),
    MOVE(IN_DOWN), MOVE(IN_DOWN), MOVE(IN_LEFT), MOVE(IN_DOWN), {80, 0, 0},
    SHOT,                                                 // 5: editor-elements
    {2, 0, IN_UP}, {10, 0, 0}, {2, 0, IN_UP}, {10, 0, 0}, {2, 0, IN_UP}, {10, 0, 0},
    MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT),
    MOVE(IN_RIGHT), MOVE(IN_RIGHT), {40, 0, 0}, {3, 0, IN_BUTTON}, {60, 0, 0},  // the clock taken
    {1, '6', 0}, {45, 0, 0},                              // three emeralds
    MOVE(IN_RIGHT), PUT, MOVE(IN_RIGHT), PUT, MOVE(IN_RIGHT), PUT,
    {1, 'X', 0}, {45, 0, 0},                              // an exit
    MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), PUT,
    {1, '5', 0}, {45, 0, 0},                              // two boulders above
    MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_UP), PUT, MOVE(IN_LEFT), PUT,
    {1, '3', 0}, {45, 0, 0},                              // a wall, drawn
    MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT), MOVE(IN_RIGHT),
    {36, 0, IN_BUTTON | IN_DOWN}, {80, 0, 0},
    SHOT,                                                 // 6: editor-changed
    {1, 'V', 0}, {60, 0, 0}, MOVE(IN_DOWN), {20, 0, 0},   // values: 3 emeralds to open the exit
    MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT),
    MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), MOVE(IN_LEFT), {40, 0, 0},
    MOVE(IN_UP), MOVE(IN_UP), {20, 0, 0},                 // the name: OLD TUNNEL
    STEP1(0x14), STEP1(0x14), STEP1(0x14), STEP1(0x14), STEP1(0x14),
    STEP1('T'), STEP1('U'), STEP1('N'), STEP1('N'), STEP1('E'), STEP1('L'), {60, 0, 0},
    SHOT,                                                 // 7: editor-values
    {1, '\r', 0}, {80, 0, 0},
    {1, 'T', 0}, {TRY_WAIT, 0, 0}, {45, 0, IN_RIGHT},     // trying it: to the exit
    SHOT,                                                 // 8: editor-try
    {75, 0, IN_RIGHT}, {250, 0, 0}, {150, 0, 0},
    {1, 'S', 0}, {60, 0, 0},                              // saved
    SHOT,                                                 // 9: editor-saved
    {60, 0, 0},
    {1, '+', 0}, {80, 0, 0}, {1, '-', 0}, {150, 0, 0},    // loaded again: as saved
    {2, 0, IN_RESTART}, {100, 0, 0},                      // the title, the own caves
    {2, 0, IN_RIGHT}, {10, 0, 0}, {2, 0, IN_RIGHT}, {10, 0, 0}, {2, 0, IN_RIGHT}, {10, 0, 0},
    {2, 0, IN_RIGHT}, {10, 0, 0}, {2, 0, IN_RIGHT}, {20, 0, 0},  // the line under the logo whole
    SHOT,                                                 // 10: editor-title
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
    {2, 0, IN_DOWN}, {2, 0, 0}, {2, 0, IN_DOWN}, {2, 0, 0}, {2, 0, IN_DOWN}, {2, 0, 0}, {2, 0, IN_DOWN}, {2, 0, 0},
    {2, 0, IN_DOWN}, {2, 0, 0}, {2, 0, IN_DOWN}, {2, 0, 0}, {2, 0, IN_DOWN}, {2, 0, 0}, {2, 0, IN_DOWN}, {2, 0, 0},
    {1, 'X', 0}, {10, 0, 0},                              // the game: OWN1X
    {0, 0, 0},                                            // 3: values
    {1, '\r', 0}, {1, 'S', 0}, {30, 0, 0}, {0, 0, 0},     // 4: saved
    {1, 'T', 0}, {250, 0, 0}, {150, 0, 0}, {0, 0, 0},     // 5: trying it, Rockford out
    {2, 0, IN_RESTART}, {250, 0, 0}, {2, 0, IN_BUTTON}, {150, 0, 0},  // dead after 15 steps
    {0, 0, 0},                                            // 6: back in the editor
    {1, '+', 0}, {100, 0, 0}, {0, 0, 0},                  // 7: slot 2, a cave from GDash
    {1, 'M', 0}, {20, 0, 0}, {2, 0, IN_DOWN}, {2, 0, 0}, {2, 0, IN_RIGHT}, {40, 0, 0},
    {0, 0, 0},                                            // 8: its map, the cursor at 3,3
    {1, 'M', 0}, {20, 0, 0},
    {1, 'T', 0}, {250, 0, 0}, {250, 0, 0}, {0, 0, 0},     // 9: trying it
    {2, 0, IN_RESTART}, {250, 0, 0}, {2, 0, IN_BUTTON}, {150, 0, 0},
    {1, '-', 0}, {100, 0, 0}, {0, 0, 0},                  // 10: slot 1 again
    {2, 0, IN_RESTART}, {120, 0, 0},                      // the title, own caves
    {2, 0, IN_RIGHT}, {2, 0, 0}, {2, 0, IN_RIGHT}, {2, 0, 0}, {2, 0, IN_RIGHT}, {2, 0, 0},
    {2, 0, IN_RIGHT}, {2, 0, 0}, {2, 0, IN_RIGHT}, {2, 0, 0}, {10, 0, 0},
    {0, 0, 0},                                            // 11: the title
    {2, 0, IN_BUTTON}, {250, 0, 0}, {200, 0, 0}, {0, 0, 0},  // 12: playing own cave 1
    {1, KEY_F1, 0}, {150, 0, 0}, {0, 0, 0},               // 13: F1, the title again
    {1, 'H', 0}, {60, 0, 0}, {0, 0, 0},                   // 14: help, how to play
    {1, ' ', 0}, {60, 0, 0}, {0, 0, 0},                   // 15: help, the elements
    {1, ' ', 0}, {60, 0, 0}, {1, 'E', 0}, {120, 0, 0},    // the editor: slot 1 as it was left
    {1, '4', 0}, {4, 0, IN_BUTTON}, {10, 0, 0},           // steel at 3,3, not saved
    {1, 'E', 0}, {20, 0, 0}, {2, 0, IN_DOWN}, {10, 0, 0}, {2, 0, IN_DOWN}, {30, 0, 0},
    {0, 0, 0},                                            // 16: all elements, on the biter
    {3, 0, IN_BUTTON}, {20, 0, 0}, {1, 'R', 0}, {2, 0, IN_RIGHT}, {10, 0, 0},
    {4, 0, IN_BUTTON}, {10, 0, 0},                        // a biter going right at 4,3
    {2, 0, IN_RESTART}, {120, 0, 0}, {1, 'E', 0}, {120, 0, 0},
    {0, 0, 0},                                            // 17: kept, with the steel, the biter and *
    {2, 0, IN_RESTART}, {120, 0, 0}, {2, 0, IN_RESTART}, {10, 0, 0},
    {0, 0, 0},                                            // 18: Run/Stop on the title: BASIC?
    {2, 0, IN_RESTART}, {0, 0, 0},                        // 19: BASIC (Xemu is stopped from outside)
#endif
};
static uint8_t test_pos, test_left, test_in, test_key;
#ifndef FLOWTEST
static uint8_t test_stops;
#endif

#ifdef FLOWTEST
static uint8_t flow_screen;   // SCR_*
static uint8_t flow_wait;     // the W_* waited for
static uint16_t flow_waited;  // frames so far
static void flow_check(bool timed_out);

static bool flow_happened(uint8_t w) {
    switch (w) {
    case W_TITLE:
        return flow_screen == SCR_TITLE;
    case W_ALIVE:  // and born: he stands in his cell, he can walk
        return flow_screen == SCR_CAVE && game.state == PS_ALIVE && cave[game.player] == O_PLAYER;
    case W_EXITED:
        return game.state == PS_EXITED;
    case W_DEAD:
        return game.state == PS_DEAD;
    case W_TIMEOUT:
        return game.state == PS_TIMEOUT;
    case W_NAME:
        return flow_screen == SCR_NAME;
    }
    return false;
}
#define FLOW_SCREEN(scr) (flow_screen = (scr))
#endif

static uint8_t test_input(void) {
#ifdef FLOWTEST
    if (flow_wait) {
        if (flow_happened(flow_wait)) {
            flow_wait = 0;
        } else if (++flow_waited > FLOW_WAIT) {
            flow_wait = 0;
            flow_check(true);
        } else {
            return test_in;
        }
    }
#endif
    while (!test_left) {
        const uint8_t *step = test_script[test_pos];
        if (test_pos < sizeof test_script / 3 - 1)
            test_pos++;
        if (!step[0]) {
#ifdef FLOWTEST
            if (step[1] == FLOW_END) {
                POKE(0xD6CF, 0);
                POKE(0xD6CF, 0x42);
                for (;;)
                    ;
            }
            if (step[1]) {
                flow_wait = step[1];
                flow_waited = 0;
                return test_in = step[2];
            }
            flow_check(false);
#else
            if (++test_stops >= EDITTEST) {
                POKE(0xD6CF, 0);
                POKE(0xD6CF, 0x42);
                for (;;)
                    ;
            }
#endif
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
#ifndef FLOWTEST
#define FLOW_SCREEN(scr)  // where the game is, for the flow test
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
    for (uint8_t k = 0; k < gd.nevents; k++) {
        uint16_t c = gd.events[k].cell;
        switch (gd.events[k].what) {
        default:
            add_trail(c, event_trail[gd.events[k].what]);
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
        if (tiles[c] == T_SPACE && cave[c] == O_SPACE)
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

#ifdef SCROLLPROF
// Built with -DSCROLLPROF: how smooth the view moves while a cave plays,
// read from a memory dump: frames of the loop by the MEGA65's frames they
// took (1 is right, more: frames dropped), and the view's steps in pixels
// per frame
volatile uint16_t sp_frames[4];   // 1, 2, 3, more
volatile uint16_t sp_step[17];    // |dx| + |dy| of the view, 0-16
volatile uint16_t sp_drop[26];    // frames dropped, by cave
volatile uint16_t sp_step_lines;  // the most raster lines a step took
volatile uint16_t sp_cave_lines[26];  // ... by cave
#endif

#ifdef GDPROF
// Built with -DGDPROF: how long GDash's engine and the frames take while a
// cave from GDash plays, read from a memory dump (CIA 1's timer A runs
// free at about 1 MHz; the game uses no CIA interrupts)
volatile uint32_t prof_engine;    // raster lines of GDash's steps since the cave started
volatile uint16_t prof_steps;     // its steps
volatile uint16_t prof_busy[16];  // frames by their work before the wait, 2 ms each

volatile uint32_t prof_render[3];  // video_render: building the jobs, running them, sprites

uint16_t prof_timer(void) {
    uint8_t lo, hi;
    do {
        hi = PEEK(0xDC05);
        lo = PEEK(0xDC04);
    } while (hi != PEEK(0xDC05));
    return (uint16_t)hi << 8 | lo;
}
static uint16_t prof_synced;
#endif

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
    // running, the belts' stripes move the way they carry: the four frames
    // forwards to the left, backwards to the right
    uint8_t left = 0, right = 0;
    if (fl & GDF_CONVEYOR_BELTS_ACTIVE) {
        gtile[O_CONVEYOR_SWITCH] = T_CONVEYOR_SWITCH_ON;
        left = (f >> 1) & 3;
        right = -left & 3;
    }
    if (fl & GDF_CONVEYOR_BELTS_DIRECTION_CHANGED) {
        uint8_t t = left;
        left = right;
        right = t;
        gtile[O_CONVEYOR_DIR_SWITCH] = T_CONVEYOR_DIR_SWITCH_ON;
    }
    gtile[O_CONVEYOR_LEFT] = T_CONVEYOR0 + left;
    gtile[O_CONVEYOR_RIGHT] = T_CONVEYOR0 + right;
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
    update_gtiles();  // GDash's elements: some take the tiles just set
    const uint8_t *et = gtile;

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
    uint8_t cover = T_COVER0 + ((f >> 1) & 7);  // the steel wall moving up
    uint8_t sparkle = f >> 2;
    nsprites = 0;
    for (uint8_t y = y0; y <= y1; y++) {
        uint16_t i = y * CAVE_W + x0;
        for (uint8_t x = x0; x <= x1; x++, i++) {
            if (any_covered && (covered[i >> 3] & 1 << (i & 7))) {
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

// Playing, the view moves with Rockford: inside a box round the middle he
// walks on a still cave; at its edge the cave moves under him exactly as
// far as he goes, frame by frame, as smooth as his own steps. What jumps
// farther (a teleporter, round the edge of the cave) is followed by at
// most 8 pixels a frame.
#define TRACK_MAX 8

// The view stays inside the part of the cave that is shown (GDash's x1-x2,
// y1-y2): cam_lo to cam_hi. A part at most a cell larger than the view (an
// intermission, 20 x 12) stands still in the middle, as on the C64's
// screen. So does a small room in a cave of steel wall (a cave of the
// editor, or one of the game's, 40 x 22): steel wall never changes, so
// what lies round the room with its steel border is never seen.
static uint16_t cam_lo_x, cam_hi_x, cam_lo_y, cam_hi_y;

__attribute__((noinline)) static void bounds(uint16_t *lo, uint16_t *hi, uint8_t a, uint8_t b, uint16_t view, uint16_t max) {
    uint16_t l = a * 16, end = (b + 1) * 16;
    uint16_t h = end > view ? end - view : 0;
    if (h <= l + 16)
        l = h = (l + h) / 2;
    if (h > max)
        h = max;
    *lo = l < h ? l : h;
    *hi = h;
}

// The room a to b (its cells that are not steel) in the shown part lo to hi:
// if it fits into the view, it stands still with its border of steel, or
// without, when that is a cell too many (an exit in the border).
__attribute__((noinline)) static void room_bounds(uint16_t *cl, uint16_t *ch, uint8_t a, uint8_t b, uint8_t lo, uint8_t hi,
                                                  uint16_t view, uint16_t max) {
    if (a <= b && b - a < view / 16) {
        if (a > lo && b < hi && b - a + 2 < view / 16 + 1) {
            a--;
            b++;
        }
        lo = a;
        hi = b;
    }
    bounds(cl, ch, lo, hi, view, max);
}

__attribute__((noinline)) static void view_bounds(void) {
    const GdCaveFile *f = &file.own;
    uint8_t x1 = f->x2, x2 = f->x1, y1 = f->y2, y2 = f->y1;  // the room: what is not steel
    for (uint8_t y = f->y1; y <= f->y2; y++)
        for (uint8_t x = f->x1; x <= f->x2; x++)
            if (f->map[y * CAVE_W + x] != O_STEEL) {
                if (x < x1)
                    x1 = x;
                if (x > x2)
                    x2 = x;
                if (y < y1)
                    y1 = y;
                if (y > y2)
                    y2 = y;
            }
    room_bounds(&cam_lo_x, &cam_hi_x, x1, x2, f->x1, f->x2, VIEW_W, MAX_X);
    room_bounds(&cam_lo_y, &cam_hi_y, y1, y2, f->y1, f->y2, VIEW_H, MAX_Y);
}

__attribute__((noinline)) static int16_t within(int16_t v, uint16_t lo, uint16_t hi) {
    if (v < (int16_t)lo)
        return lo;
    return v > (int16_t)hi ? hi : v;
}

static void track(uint16_t *cam, uint16_t p, uint16_t view, uint16_t lo, uint16_t hi, uint16_t margin) {
    int16_t low = (int16_t)p - (int16_t)(view - margin);  // the view's least position for p
    int16_t high = (int16_t)p - (int16_t)margin;          // its greatest
    int16_t c = *cam, to = c;
    if (to < low)
        to = low;
    if (to > high)
        to = high;
    to = within(to, lo, hi);
    if (to > c + TRACK_MAX)
        to = c + TRACK_MAX;
    if (to < c - TRACK_MAX)
        to = c - TRACK_MAX;
    *cam = to;
}

static void camera(bool jump) {
    uint16_t px, py;
    cell_pos(game.player, &px, &py);
    if (jump) {
        cam_x = within((int16_t)px + 8 - VIEW_W / 2, cam_lo_x, cam_hi_x);
        cam_y = within((int16_t)py + 8 - VIEW_H / 2, cam_lo_y, cam_hi_y);
        return;
    }
    track(&cam_x, px + 8, VIEW_W, cam_lo_x, cam_hi_x, VIEW_W / 2 - 32);  // a box of 64 x 32 pixels
    track(&cam_y, py + 8, VIEW_H, cam_lo_y, cam_hi_y, VIEW_H / 2 - 16);
}

// ---------------------------------------------------------------- status

// The last n digits of v at out, without division (src/text.s)
void to_digits(char *out, uint32_t v, uint8_t n);

// Not inlined: it is called from many places.
__attribute__((noinline)) static void put_num(uint8_t col, uint32_t v, uint8_t n) {
    static char d[6];
    to_digits(d, v, n);
    for (uint8_t i = 0; i < n; i++)
        status_put(col++, d[i]);
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
    if (!status_items())
        status_game();
}

// "CAVE 12/3": cave and level, as the original's "A/1"; "OWN1 12/3" for an
// own cave (the game's name), "TEST" for the one in the editor
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
    } else if (play_mode == PLAY_OWN) {  // "OWN1 12/3"
        const char *name = game_name[own_game][0] ? game_name[own_game] : "OWN";
        status_print(7, name);
        col = 8 + strlen(name);
        put_num(col, cave_no + 1, 2);
        status_put(col + 2, '/');
        put_num(col + 3, level + 1, 1);
        col += 5;
    } else {
        status_print(7, "TEST");
        col = 12;
    }
    status_print(col, game.def->name);
    status_end();
}

// ---------------------------------------------------------------- frames

// ---------------------------------------------------------------- steps

// A step of GDash's engine is made in parts in the frames before its tick,
// in the time each frame leaves before video_sync and before video_show
// (gd_step_rows watches the raster), and shown at its tick: a step that
// takes longer than a frame leaves (a full cave) costs no frame. The
// screen meanwhile shows the last step. Between the parts the step's state
// (what lies at $C000: cave[], moved[], gd) waits in STEP_BANK at
// STEP_WORK and the shown one is at $C000 (a copy at STEP_SHOWN), so all
// but the engine see the step shown.
enum { ST_IDLE, ST_MAKING, ST_MADE };
static uint8_t step_state;
static bool step_begun;       // gd_step_begin has run
static bool step_taken;       // the player has taken his input
static uint8_t step_in;       // the input (IN_*) given to the step
static uint16_t step_cost;    // raster lines the parts took
static uint16_t step_lines;   // ... in the last steps, at most (it decays)
static bool gd_suicide;       // Run/Stop, for GDash's next step
static uint8_t latched = DIR_NONE;  // a direction pressed since the last step took one
static bool fire_latched;     // ... and fire
_Static_assert(2 * CAVE_SIZE + GD_STATE_SIZE == STEP_SIZE, "what lies at $C000 (shared.ld)");

static void step_dma(uint16_t off, bool in) {
    dma_begin(0, 0);
    if (in)
        dma_copy(off, STEP_BANK, STEP_AT, 0, STEP_SIZE);
    else
        dma_copy(STEP_AT, 0, off, STEP_BANK, STEP_SIZE);
    dma_run();
}

// GDash's directions for IN_*
static uint8_t step_move(uint8_t in) {
    static const uint8_t mv[] = {MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_STILL};
    return mv[in & 7] | (in & IN_FIRE ? 0x80 : 0);
}

// Work on the step until the raster is near `end`
static void step_work(uint16_t end) {
    if (step_state != ST_MAKING)
        return;
    uint16_t r0 = video_raster();
    end = (end + video_lines - 12) % video_lines;  // the copies below
    if (!step_begun) {
        step_dma(STEP_SHOWN, false);
        gd_step_begin(step_move(step_in) & 0x7F, (step_in & IN_FIRE) != 0, gd_suicide);
        gd_suicide = false;
        step_begun = true;
    } else {
        step_dma(STEP_WORK, true);
    }
    uint8_t r = gd_step_rows(step_move(step_in), end, video_lines);
    step_dma(STEP_WORK, false);
    step_dma(STEP_SHOWN, true);
    if ((r & 2) && !step_taken) {  // what was pressed until now is used
        step_taken = true;
        latched = DIR_NONE;
        fire_latched = false;
    }
    if (r & 1)
        step_state = ST_MADE;
    uint16_t r1 = video_raster();
    step_cost += r1 >= r0 ? r1 - r0 : r1 + video_lines - r0;
}

static void next_frame(void) {
#ifdef GDPROF
    if (!show_cursor) {
        uint16_t busy = (uint16_t)(prof_synced - prof_timer()) / 2000;
        prof_busy[busy > 15 ? 15 : busy]++;
    }
#endif
    step_work(video_sync_line);
    video_sync();
#ifdef GDPROF
    prof_synced = prof_timer();
#endif
    update_tiles();
    if (show_cursor && (frame & 31) < 24 && nsprites < MAX_SPRITES) {
        Sprite *s = &sprites[nsprites++];
        s->x = cur_x * 16;
        s->y = cur_y * 16;
        s->tile = T_CURSOR;
    }
    video_render(tiles, cam_x, cam_y, sprites, nsprites);
    step_work(video_show_line);
    video_show();
    SHOT_TICK();
    sound_frame();
    frame++;
    if (flash && !--flash)
        video_flash(false);
    uint8_t in = input_read();
    pressed = in & ~held;
    held = in;
#ifdef NMI_STORM
    // The NMI test (tests/test_render.sh with -DNMI_STORM): CIA 2's timer
    // gives an NMI somewhere in each frame, as Restore does
    PEEK(0xDD0D);  // the last one acknowledged
    uint16_t at = (frame * 4099u & 0x3FFF) + 16;
    POKE(0xDD04, at);
    POKE(0xDD05, at >> 8);
    POKE(0xDD0D, 0x81);  // timer A's NMI on
    POKE(0xDD0E, 0x19);  // once, loaded, started
#endif
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

// Uncover (on = 0) or cover (on = 1) the cave as the C64 does (GDash's
// gamecontrol.cpp): every 40 ms (two frames) a random cell of each row,
// 70 times, while it is uncovered; eight cells of each row, 8 times, while
// it is covered - and in the editor, as GDash tests a cave, also while it
// is uncovered; then the rest
// In each row per_row random cells covered or uncovered (src/cover.s)
void cover_cells(uint8_t on, uint8_t per_row, uint8_t *bits);

#ifdef ASM_CHECK
// The C cover_cells came from, and the check of it (tests/test_asm.sh):
// cover_bad of cover_runs not as the C's
static void cover_cells_c(uint8_t on, uint8_t per_row, uint8_t *bits) {
    for (uint8_t y = 0; y < CAVE_H; y++)
        for (uint8_t k = 0; k < per_row; k++) {
            uint16_t i = y * CAVE_W + ((rnd() * CAVE_W) >> 8);
            if (on)
                bits[i >> 3] |= 1 << (i & 7);
            else
                bits[i >> 3] &= ~(1 << (i & 7));
        }
}

uint16_t cover_bad, cover_runs;

static void cover_check(void) {
    static uint8_t a[CAVE_SIZE / 8], b[CAVE_SIZE / 8];
    memset(a, 0x5A, sizeof a);
    memset(b, 0x5A, sizeof b);
    for (uint16_t n = 0; n < 400; n++) {
        uint8_t on = n & 1, per_row = n & 2 ? 8 : 1;
        uint16_t r = rnd_state;
        cover_cells(on, per_row, a);
        uint16_t after = rnd_state;
        rnd_state = r;
        cover_cells_c(on, per_row, b);
        cover_bad += memcmp(a, b, sizeof a) != 0 || rnd_state != after;
        cover_runs++;
    }
}
#endif

static void cover_cave(uint8_t on) {
    any_covered = true;
    sound_still();
    bool quick = on || play_mode == PLAY_TEST;
    uint8_t steps = quick ? 8 : 70, per_row = quick ? 8 : 1;
    for (uint8_t n = 0; n < steps; n++) {
        cover_cells(on, per_row, covered);
        sound_crackle();
        next_frame();
        next_frame();
    }
    memset(covered, on ? 0xFF : 0, sizeof covered);
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

// A sector that could not be read: the file, the sector and the
// controller's status in the status line ("CAVE07-1 ERROR T12 S05 18"),
// until the button (or 30 seconds), for whoever tests on a MEGA65 to
// tell. A file that is not there says nothing: an own cave without a file
// for a level is played from the first level's.
static void disk_failed(const char *file) {
    if (!disk_err_track)
        return;
    uint8_t col = 2 + strlen(file);
    status_begin();
    status_print(2, file);
    status_print(col + 1, "ERROR T");
    put_num(col + 8, disk_err_track, 2);
    status_put(col + 11, 'S');
    put_num(col + 12, disk_err_sector, 2);
    for (uint8_t i = 0; i < 2; i++) {  // the status in hex
        uint8_t h = i ? disk_err_status & 15 : disk_err_status >> 4;
        status_put(col + 15 + i, h < 10 ? '0' + h : 'A' - 10 + h);
    }
    status_end();
    wait_button(1500);
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
    if (!ok)
        disk_failed(file);
    return ok;
}

static void use_own_cave(void);

// Cave n of the level from the disk (CAVEnn-l; a level the same as the
// first has no file, the first's is played), unless it is there already;
// false after the last cave
static bool load_cave(uint8_t n) {
    static const uint8_t cave_levels[CAVE_COUNT] = CAVE_LEVELS;
    if (n >= CAVE_COUNT)
        return false;
    if (n == loaded && level == loaded_level)
        return true;
    static char name[] = "CAVES/CAVE00-0";
    static char what[] = "LOADING CAVE 00/0";
    uint8_t tens = (n + 1) / 10, ones = (n + 1) % 10;
    name[10] = '0' + tens;
    name[11] = '0' + ones;
    name[13] = '1' + ((cave_levels[n] >> level) & 1 ? level : 0);
    char *num = what + 13;
    if (tens)
        *num++ = '0' + tens;
    *num++ = '0' + ones;
    *num++ = '/';
    *num++ = '1' + level;
    *num = 0;
    loaded = 0xFF;
    if (!have_gdash || !load(what, name, 0, (uint16_t)&file.own))
        return false;
#ifdef SCREENCAST
    static char demo_file[] = "DEMO00";
    demo_file[4] = name[10];  // the cave's number in CAVES/CAVE00-0
    demo_file[5] = name[11];
    if (!disk_load(demo_file, 0, (uint16_t)demo_moves))
        demo_moves[0] = 0;
#endif
    loaded = n;
    loaded_level = level;
    use_own_cave();
    return true;
}

// The cave in file for GDash's engine
static void use_own_cave(void) {
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

// The file of slot n (from 0) in level lv (from 0) of own_game: OWN01, ...
// in the first level, OWN01-2, ... in the others, in the game's partition:
// OWN1/OWN01-2
static const char *own_name(uint8_t n, uint8_t lv) {
    static char file[18];
    char *p = file;
    for (const char *g = game_name[own_game]; *g;)
        *p++ = *g++;
    if (p != file)
        *p++ = '/';
    memcpy(p, "OWN", 3);
    p[3] = '0' + (n + 1) / 10;
    p[4] = '0' + (n + 1) % 10;
    p[5] = lv ? '-' : 0;
    p[6] = '1' + lv;
    p[7] = 0;
    return file;
}

// Slot n from the disk into file.own in level lv: the level's own file if
// it holds a cave (tools/cavekit.py writes one where a level of GDash's
// differs from the first; the editor and an older disk have none), else
// the first level's. False if the disk has no such slot; an empty one has
// time 0.
static bool load_own(uint8_t n, uint8_t lv) {
    loaded = 0xFF;
    if (lv && load("LOADING OWN CAVE", own_name(n, lv), 0, (uint16_t)&file.own) && file.own.time)
        return true;
    return load("LOADING OWN CAVE", own_name(n, 0), 0, (uint16_t)&file.own);
}

// The own cave cave_no in the level, or the next one that is not empty;
// after the last slot the first of the next level, and after the last
// level that one again. False if there is none
static bool next_own(void) {
    for (uint8_t k = 0; k < OWN_SLOTS; k++, cave_no++) {
        if (cave_no >= OWN_SLOTS) {
            cave_no = 0;
            if (level < OWN_LEVELS - 1)
                level++;
        }
        if (!have_gdash || !load_own(cave_no, level))
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
#ifdef TOUR
#define DEMO_TITLE_FRAMES 150  // the demo caves' video: a moment of the title
#else
#define DEMO_TITLE_FRAMES 768  // the title with all its lines once
#endif

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

// The music goes by the frames that went by, however many: a page drawn at
// once (the help) takes a few. Drawing it, this comes now and then, so
// they are not many at a time.
static uint8_t music_last;  // the frame it played last

static void music_catch_up(void) {
    uint8_t now = PEEK(0xD7FA), n = now - music_last;
    music_last = now;
    while (n--)
        music_frame();
}

static void title_frame(void) {
    video_sync();
    video_show();
    SHOT_TICK();
    music_catch_up();
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
    const char *name = "CAVE";
    uint8_t n = start_cave;
    if (start_cave == CAVE_COUNT) {  // the game's name and the slot: "OWN1 12"
        name = game_name[start_game][0] ? game_name[start_game] : "OWN";
        n = start_own;
    }
    uint8_t col = 2 + strlen(name) + 1;
    status_print(2, name);
    put_num(col, n + 1, n >= 9 ? 2 : 1);
    col = col + 4 > 11 ? col + 4 : 11;
    status_print(col, "LEVEL");
    put_num(col + 6, start_level + 1, 1);
    status_print(23, "HI-SCORE");
    put_num(32, hs_table[0].score, 6);
    status_end();
}

// Up and down pick the level, left and right the cave to start with; right
// of the last one come the own caves, one by one, game after game, with
// GDash's levels (an empty slot starts with the next own cave)
#define LAST_START ((CAVE_COUNT - 1) / START_STEP * START_STEP)

static void title_pick(void) {
    uint8_t l = start_level, c = start_cave, g = start_game, o = start_own;
    if (pressed & IN_RIGHT) {
        if (c < CAVE_COUNT) {
            c = c == LAST_START ? CAVE_COUNT : c + START_STEP;
        } else if (o < OWN_SLOTS - 1) {
            o++;
        } else if (g < games - 1) {
            g++;
            o = 0;
        }
    }
    if (pressed & IN_LEFT) {
        if (c == CAVE_COUNT && o) {
            o--;
        } else if (c == CAVE_COUNT && g) {
            g--;
            o = OWN_SLOTS - 1;
        } else if (c) {
            c = c == CAVE_COUNT ? LAST_START : c - START_STEP;
        }
    }
    uint8_t top = (c == CAVE_COUNT ? OWN_LEVELS : LEVELS) - 1;
    if ((pressed & IN_UP) && l < top)
        l++;
    if ((pressed & IN_DOWN) && l)
        l--;
    if (l > top)
        l = top;
    if (l != start_level || c != start_cave || g != start_game || o != start_own) {
        start_level = l;
        start_cave = c;
        start_game = g;
        start_own = o;
        title_status();
        sound_crackle();
    }
}

// ---------------------------------------------------------------- high scores

#define HS_COL 6   // the table's lines: "1ST  ROC  012345  CAVE 12/3"
#define HS_Y0  42  // its first line; one every 16 pixel rows

static uint8_t hs_new = HS_COUNT;  // the entry of the last game, shining

static const char places[] = "1ST2ND3RD4TH5TH6TH7TH8TH";

#ifdef FLOWTEST
// A checkpoint of the flow test: what the game knows now, 16 bytes, into
// free memory after the status line (mem.h) that tests/test_flow.py reads
// from Xemu's dump - the number of checkpoints at $4FA00, then one after
// the other from $4FA10. A wait that timed out writes one with number 0.
#define FLOW_AT 0xFA00  // in bank 4
static void flow_check(bool timed_out) {
    static uint8_t n, stops, r[16];
    static uint32_t total;
    r[0] = timed_out ? 0 : ++stops;
    r[1] = timed_out;
    r[2] = flow_screen;
    r[3] = lives;
    r[4] = cave_no;
    r[5] = level;
    r[6] = game.state;
    r[7] = hs_new;
    r[8] = start_cave;
    r[9] = start_level;
    r[10] = (uint8_t)game.time;
    r[11] = game.time >> 8;
    total = score + (flow_screen == SCR_CAVE ? game.score : 0);  // after a cave, score has it
    memcpy(r + 12, &total, 4);
    if (n == 94)  // as many as there is room for
        return;
    dma_begin(0, 0);
    dma_copy((uint16_t)r, 0, FLOW_AT + 16 + n * 16, 4, 16);
    dma_run();
    n++;
    dma_begin(0, 0);
    dma_copy((uint16_t)&n, 0, FLOW_AT, 4, 1);
    dma_run();
}
#endif

static const uint8_t *place_colours(uint8_t rank) {
    return rank_row + (rank < 3 ? rank : 3) * 16;
}

static void hs_line(uint8_t i) {
    static char line[28];
    const HiScore *e = &hs_table[i];
    memset(line, ' ', 27);
    memcpy(line, places + i * 3, 3);
    memcpy(line + 5, e->name, 3);
    to_digits(line + 10, e->score, 6);
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
static uint8_t get_key(void);

static void enter_name(HiScore *e, uint8_t rank) {
    static char line[] = "000000 POINTS - 1ST PLACE";
    const uint8_t fps = pal ? 50 : 60;
    video_clear();
    video_palette(0);
    video_big_text(CENTRE(28), 4, "NEW HIGH SCORE");
    to_digits(line, e->score, 6);
    memcpy(line + 16, places + rank * 3, 3);
    video_text_in(CENTRE(25), 44, line, place_colours(rank));
    video_text(CENTRE(31), 136, "UP/DOWN LETTER   FIRE/RIGHT OK");
    video_text(CENTRE(32), 156, "LEFT BACK - OR TYPE THE LETTERS");
    memcpy(e->name, last_name, 3);
    for (uint8_t i = 0; i < 3; i++)
        big_letter(i, e->name[i]);
    status_clear();
    status_print(2, "ENTER YOUR NAME");
    FLOW_SCREEN(SCR_NAME);
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
        uint8_t key = get_key();
        if (key) {
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
    music_catch_up();
    if (have_logo) {
        video_palette(1);
        video_logo(CENTRE(LOGO_W / 8), 2);
    } else {  // started without the disk: the logo as text
        video_palette(0);
        video_big_text(CENTRE(14), 8, "SMARAGD");
        video_big_text(CENTRE(8), 44, "DASH");
        video_text(CENTRE(26), 88, "DIG  -  COLLECT  -  ESCAPE");
        video_text(CENTRE(32), 136, "JOYSTICK, GAMEPAD OR CURSOR KEYS");
        video_text(CENTRE(34), 156, "HELP OR H: HOW TO PLAY   E: EDITOR");
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
                title_line("HELP OR H: HOW TO PLAY   E: EDITOR");
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

// A key typed (ASCII, letters in upper case), or 0. Run/Stop is left out:
// it is read from the matrix (IN_RESTART); typed as well, it would count
// twice.
static uint8_t get_key(void) {
#if defined(EDITTEST) || defined(FLOWTEST)
    uint8_t key = test_key;
    test_key = 0;
#else
    uint8_t key;
    do {
        key = PEEK(0xD610);
        if (key)
            POKE(0xD610, 0);
    } while (key == KEY_RUNSTOP);
    if (key >= 'a' && key <= 'z')
        key -= 'a' - 'A';
#endif
    return key;
}

// Wait on a page for a key or the button
__attribute__((noinline)) static void page_wait(void) {
    bool armed = false;
    for (;;) {
        title_frame();
        if (get_key() || (pressed & IN_RESTART) || (armed && (pressed & IN_BUTTON)))
            break;
        if (!(held & IN_BUTTON))
            armed = true;
    }
}

#ifndef SCREENCAST  // which plays the caves: no help, no BASIC (room in bank 0)
// The title's help (Help or H): how to play, then the elements of the
// game's caves
static void help_pages(void) {
    static const char *const keys[7] = {
        "MOVE      JOYSTICK OR CURSOR KEYS",
        "SNAP      FIRE AND A DIRECTION",
        "P         PAUSE",
        "RUN/STOP  GIVE UP THE LIFE",
        "F1        END THE GAME",
        "I         HELD: WHAT ROCKFORD CARRIES",
        "TITLE     E EDITOR  RUN/STOP BASIC",
    };
    static const uint8_t tile[10] = {T_DIAMOND0, T_OUTBOX0, T_BOULDER, T_FIREFLY0, T_BUTTERFLY0,
                                     T_AMOEBA0, T_MAGIC0, T_SLIME0, T_NUT, T_CLOCK};
    static const char *const what[10] = {
        "EMERALD    COLLECT THEM",
        "EXIT       OPENS WITH ENOUGH",
        "BOULDER    FALLS AND ROLLS",
        "FIREFLY    DEADLY, EXPLODES",
        "BUTTERFLY  EXPLODES INTO EMERALDS",
        "AMOEBA     ENCLOSED: EMERALDS",
        "MAGIC WALL BOULDERS INTO EMERALDS",
        "SLIME      THINGS DROP THROUGH",
        "NUT        A BOULDER CRACKS IT",
        "CLOCK      MORE TIME",
    };
    text_cancel();
    video_clear();
    music_catch_up();
    video_palette(0);
    status_center("ANY KEY: THE ELEMENTS");
    video_text_in(CENTRE(11), 0, "HOW TO PLAY", title_row);
    video_text(1, 16, "DIG FOR EMERALDS: ENOUGH OF THEM OPEN");
    video_text(1, 32, "THE EXIT. GET THERE BEFORE TIME IS UP.");
    for (uint8_t i = 0; i < 7; i++) {
        music_catch_up();
        video_text(2, 56 + i * 16, keys[i]);
    }
    page_wait();
    video_clear();
    music_catch_up();
    status_center("ANY KEY: BACK");
    video_text_in(CENTRE(12), 0, "THE ELEMENTS", title_row);
    for (uint8_t i = 0; i < 10; i++) {
        music_catch_up();
        video_tile(2, 16 + i * 16, tile[i]);
        video_text(5, 16 + i * 16, what[i]);
    }
    page_wait();
}

// ---------------------------------------------------------------- back to BASIC

static void rom_toggle(void);

// The C65 ROM's banks 2 and 3 (128K) to or from the attic RAM, in jobs of
// 32K
static void rom_copy(bool back) {
    dma_begin(back ? ROM_SAVE_MB : 0, back ? 0 : ROM_SAVE_MB);
    for (uint8_t k = 0; k < 4; k++) {
        uint16_t off = (k & 1) ? 0x8000 : 0;
        uint8_t rom_bank = 2 + (k >> 1), save_bank = k >> 1;
        if (back)
            dma_copy(off, save_bank, off, rom_bank, 0x8000);
        else
            dma_copy(off, rom_bank, off, save_bank, 0x8000);
    }
    dma_run();
}

// What the game changes of the VIC-IV, as BASIC had it at the start: put
// back in this order, the "hot" registers last, which set up the rest. The
// KERNAL's reset does not touch most of them.
static const uint8_t vic_reg[] = {0x54, 0x58, 0x59, 0x5E, 0x5C, 0x5D, 0x60, 0x61, 0x62, 0x63, 0x64, 0x65,
                                  0x4C, 0x4D, 0x4E, 0x4F, 0x15, 0x20, 0x21, 0x31, 0x18, 0x16, 0x11};
static uint8_t vic_was[sizeof vic_reg];
static uint8_t d030_was;

// BASIC's palette 0 (red, green, blue: 768 bytes) to or from the attic RAM,
// behind the ROM's copy, through a piece in bank 0
static void basic_palette(bool back) {
    static uint8_t part[64] __attribute__((section(".lowbss")));  // no value needed (link.ld)
    POKE(0xD070, 0x00);  // edit palette 0
    for (uint16_t i = 0; i < 768; i += 64) {
        volatile uint8_t *reg = (volatile uint8_t *)(0xD100 + i);
        if (back) {
            dma_begin(ROM_SAVE_MB, 0);
            dma_copy(PAL_SAVE_OFF + i, ROM_SAVE_BANKS, (uint16_t)part, 0, 64);
            dma_run();
            for (uint8_t k = 0; k < 64; k++)
                reg[k] = part[k];
        } else {
            for (uint8_t k = 0; k < 64; k++)
                part[k] = reg[k];
            dma_begin(0, ROM_SAVE_MB);
            dma_copy((uint16_t)part, 0, PAL_SAVE_OFF + i, ROM_SAVE_BANKS, 64);
            dma_run();
        }
    }
}

// The screen as BASIC had it, before the game changes it
static void basic_save(void) {
    for (uint8_t i = 0; i < sizeof vic_reg; i++)
        vic_was[i] = PEEK(0xD000 + vic_reg[i]);
    d030_was = PEEK(0xD030);
    if (rom_saved)
        basic_palette(false);
}

// BASIC as after switching on: the ROM and the screen as they were, then
// the KERNAL's reset
__attribute__((noreturn)) static void to_basic(void) {
    music_stop();
    sound_off();
    if (rom_saved) {
        rom_copy(true);
        basic_palette(true);
    }
    if (rom_toggled)
        rom_toggle();
    for (uint8_t i = 0; i < sizeof vic_reg; i++)
        POKE(0xD000 + vic_reg[i], vic_was[i]);
    POKE(0xD070, 0x00);
    POKE(0xD030, rom_saved ? d030_was : d030_was & ~0x04);  // else the ROM's colours
    // The KERNAL's reset opens the monitor while Run/Stop is held (and goes
    // to C64 mode with the C= key): both let go, and a few frames for the
    // key to settle
    POKE(0xDC02, 0xFF);
    POKE(0xDC00, 0x7F);  // the matrix column of both
    for (uint8_t f = 0; f < 3;) {
        uint8_t now = PEEK(0xD7FA);
        while (PEEK(0xD7FA) == now)
            ;
        f = (PEEK(0xDC01) & 0xA0) == 0xA0 ? f + 1 : 0;
    }
    while (PEEK(0xD610))  // no keys for BASIC
        POKE(0xD610, 0);
    // The KERNAL at $E000 (C65 ROM bank 3), the stack as at a reset
    __asm__ volatile("sei\n lda #0\n tax\n tay\n taz\n map\n eom\n"
                     " lda #$37\n sta $01\n lda $d030\n ora #$80\n sta $d030\n"
                     " lda #0\n tab\n see\n ldy #1\n tys\n ldx #$ff\n txs\n"
                     " jmp ($fffc)" ::: "a", "x", "y", "memory");
    __builtin_unreachable();
}
#endif

// The logo and the high score table take turns, like an arcade machine
// waiting for a player; after a game the table comes first. True if E was
// pressed for the editor, false for a game.
static bool title_screen(bool scores) {
    FLOW_SCREEN(SCR_TITLE);
    if (scores)
        scores_page();
    else
        logo_page();
    title_status();
    sound_off();
    music_start();
    music_last = PEEK(0xD7FA) - 1;
    // The button counts only after it was let go once (Return from the
    // emulator's RUN, or fire still held from the last game)
    bool armed = false;
    bool editor = false;
    uint16_t pf = 0;  // frames on this page
    uint8_t basic = 0;  // frames Run/Stop again goes back to BASIC
    while (get_key())  // forget the keys typed in the game
        ;
    for (;;) {
        if (scores)
            scores_frame(pf);
        else
            logo_frame(pf);
        title_frame();
#ifdef BASIC_DEMO
        // tools/record-directory.sh: back to BASIC by itself, Run/Stop twice
        if (pf == 150 || pf == 200)
            pressed |= IN_RESTART;
#endif
        if (basic && (!--basic || (pressed & ~IN_RESTART))) {
            basic = 0;
            title_status();
        }
        title_pick();
        if (armed && (pressed & IN_BUTTON)) {
            if (!scores)
                break;
            // on the high score table the button brings the logo first
            scores = false;
            pf = 0;
            video_shine(0);
            logo_page();
            continue;
        }
        uint8_t key = get_key();
        if (key == 'E') {
            editor = true;
            break;
        }
#ifndef SCREENCAST
        if (key == 'H' || key == KEY_HELP) {
            help_pages();
            scores = false;
            logo_page();
            title_status();
            pf = 0;
            armed = false;
            basic = 0;
            continue;
        }
        // Run/Stop twice: back to BASIC, unless the ROM is gone
        if (pressed & IN_RESTART) {
            bool can = !rom_ram || rom_saved;
            if (basic && can)
                to_basic();
            status_center(!can            ? "FOR BASIC, RESET THE MEGA65"
                          : kept && dirty ? "CAVE NOT SAVED - RUN/STOP AGAIN: BASIC"
                                          : "RUN/STOP AGAIN: BACK TO BASIC");
            basic = 150;
        }
#else
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

enum { END_DIED, END_EXITED, END_QUIT };  // QUIT: F1 ends the game

// ---------------------------------------------------------------- the rules

// Every cave plays by GDash's rules (gdengine.c, mapped in for each step by
// gdfar.s); `game` is taken from its state after each step, for the status
// line, the drawing and the sounds.
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

// GDash's steps take as long as it says - but it makes at most one in each
// of its 40 ms cycles (gamecontrol.cpp, main_int): 25 a second at most
static uint16_t gd_step_ms(void) {
    return gd.speed < 40 ? 40 : gd.speed;
}

// A step's length in 1/3 ms, in whole frames (frame_len each) as on the
// C64: every step then moves alike - 16 pixels in 8 frames of 2 - where
// GDash's 155 ms would give a 1 or a 3 now and then, at other places each
// time
static uint16_t step_len(uint8_t frame_len) {
    return (gd_step_ms() * 3 + frame_len / 2) / frame_len * frame_len;
}

static void rules_start(void) {
    memset(&game, 0, sizeof game);
    game.def = &cave_def;
    game.facing = DIR_DOWN;
    gd_suicide = false;
    step_state = ST_IDLE;
    step_lines = 0;
    latched = DIR_NONE;
    fire_latched = false;
    items_fresh = true;
#ifdef GDPROF
    prof_engine = 0;
    prof_steps = 0;
    memset((void *)prof_busy, 0, sizeof prof_busy);
    POKE(0xDC04, 0xFF);  // timer A from $FFFF, free running
    POKE(0xDC05, 0xFF);
    POKE(0xDC0E, 0x11);
#endif
#ifdef SCREENCAST
    gd_start(&file.own, 0);  // the random numbers tools/solve.c played with
#else
    gd_start(&file.own, (uint32_t)rnd() << 16 | (uint16_t)rnd() << 8 | frame);
#endif
    game_from_gd();
}

// The step made at its tick: shown from now on. One not made yet is made at
// once (the frames wait for it then).
static void rules_tick(void) {
    while (step_state == ST_MAKING)  // a whole frame
        step_work((video_raster() + video_lines - 70) % video_lines);
    step_dma(STEP_WORK, true);
    step_state = ST_IDLE;
    if (!step_taken) {  // no player took it
        latched = DIR_NONE;
        fire_latched = false;
    }
    step_lines = step_cost > step_lines ? step_cost : step_lines - step_lines / 8;
#ifdef GDPROF
    prof_engine += step_cost;
    prof_steps++;
#endif
    uint8_t in = step_in, dir = in & 7;
    game.moving = dir != DIR_NONE;
    game.snapping = game.moving && (in & IN_FIRE);
    if (game.moving)
        game.facing = dir;
    game_from_gd();
}

static uint8_t play_cave(void) {
    const uint8_t frame_len = pal ? 60 : 50;
    uint16_t tick_len;  // in 1/3 ms
    uint16_t tick_acc = 0;
    uint16_t shown_time = 0;  // for the clock's tick under ten seconds (GDash's)
    uint8_t last_dir = DIR_NONE;  // the direction held in the frame before
    bool paused = false;
    uint8_t after = 0;  // frames since Rockford died
    uint8_t last_frame = PEEK(0xD7FA);  // the MEGA65's frame counter

    rules_start();
    FLOW_SCREEN(SCR_CAVE);
    tick_len = step_len(frame_len);
    memset(trail_kind, TR_NONE, sizeof trail_kind);
    slide = 0;
    rf_view = VIEW_FRONT;
    memset(covered, 0xFF, sizeof covered);
    view_bounds();
    camera(true);
    status_intro();
    cover_cave(0);

    for (;;) {
        uint8_t key = get_key();
        if (key == KEY_F1) {
            sound_off();
            step_state = ST_IDLE;  // a step being made is not shown
            cover_cave(1);
            return END_QUIT;
        }
        // P typed: the MEGA65's own key queue, which no joystick touches (in
        // the matrix P shares its line with joystick 1's down)
        if (key == 'P' || (pressed & IN_PAUSE)) {
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
        if ((pressed & IN_RESTART) && game.state == PS_ALIVE)
            gd_suicide = true;

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
        bool ticks = game.state != PS_TIMEOUT && game.state != PS_EXITED;
        if (!ticks)
            sound_still();
        // The next step is begun as many frames before its tick as the
        // last ones took (at least one), and takes the input until the
        // player has taken it
        if (ticks && step_state == ST_IDLE) {
            uint16_t left = tick_acc >= tick_len ? 0 : (tick_len - tick_acc + frame_len - 1) / frame_len;
            uint16_t ahead = 1 + step_lines / (video_lines * 2 / 5);
            if (left <= ahead) {
                step_state = ST_MAKING;
                step_begun = step_taken = false;
                step_cost = 0;
#ifdef SCREENCAST
                step_in = demo_next();
#endif
            }
        }
#ifndef SCREENCAST
        if (step_state == ST_MAKING && !step_taken)
            step_in = (dir != DIR_NONE ? dir : latched) | (fire_latched ? IN_FIRE : 0);
#else
        (void)(latched | fire_latched);  // the moves come from the disk
#endif
        if (tick_acc >= tick_len && ticks) {
            tick_acc -= tick_len;
            rules_tick();
            tick_len = step_len(frame_len);  // GDash's steps take as long as it says
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
#ifdef SCROLLPROF
        sp_frames[frames > 3 ? 3 : frames - 1]++;
        if (frames > 1 && game.state == PS_ALIVE)
            sp_drop[cave_no < 25 ? cave_no : 25] += frames - 1;
        if (step_lines > sp_step_lines)
            sp_step_lines = step_lines;
        if (step_lines > sp_cave_lines[cave_no < 25 ? cave_no : 25])
            sp_cave_lines[cave_no < 25 ? cave_no : 25] = step_lines;
#endif
        // How far the moves of the tick have come: they end with the next
        // one, so what stops always reaches its cell.
        slide = tick_acc >= tick_len ? 0 : 16 - tick_acc * 16 / tick_len;
        if (game.state == PS_ALIVE && game.time != shown_time) {  // GDash's engine counts the time
            shown_time = game.time;
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
        case PS_HATCHING: {
#ifdef SCROLLPROF
            uint16_t ox = cam_x, oy = cam_y;
#endif
            status_play();
            camera(false);
#ifdef SCROLLPROF
            uint8_t st = (cam_x > ox ? cam_x - ox : ox - cam_x) + (cam_y > oy ? cam_y - oy : oy - cam_y);
            sp_step[st > 16 ? 16 : st]++;
#endif
            break;
        }
        case PS_DEAD:
            status_play();
            // the cave goes on; after a while the button ends it
            if (after < 255)
                after++;
            if ((after > 50 && (pressed & IN_BUTTON)) || after == 255) {
                step_state = ST_IDLE;  // a step being made is not shown
                cover_cave(1);
                return END_DIED;
            }
            break;
        case PS_TIMEOUT:
            status_center("OUT OF TIME");
            if (pressed & IN_BUTTON) {
                step_state = ST_IDLE;  // a step being made is not shown
                cover_cave(1);
                return END_DIED;
            }
            break;
        case PS_EXITED:
            // the time left is counted into the score (GDash's caves give
            // their own points per second)
            if (game.time) {
                game.time--;
                game.score += file.own.timevalue;
                if (!(frame & 1))
                    sound_bonus();
                status_game();
            } else {
                step_state = ST_IDLE;  // a step being made is not shown
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
// from file.own. Its keys (also on its help page, H or Help):
//   cursor keys, joystick   move the cursor
//   fire, Space, Return     put the element chosen; held, it draws
//   1-9, 0, I, X            choose the element; again: a firefly or a
//                           butterfly gets its next starting direction
//   E                       choose among all elements (edit_pick)
//   R                       the next starting direction of what walks
//   G                       take the element under the cursor
//   V                       name and values      T  try the cave
//   S                       save it into its slot
//   + -                     the next and the last slot
//   C                       a new cave           D  empty the slot
//   Run/Stop                back to the title; the cave stays as it is
//                           until the editor is opened again
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
#define NAME_LEN 21  // what the status line has room for (mkcave.py)
#define KEY_STOP KEY_RUNSTOP  // Run/Stop (IN_RESTART), as the editor's key
#define KEY_DEL  0x14

static const char pen_keys[PENS] = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 'I', 'X'};
static const uint8_t pen_elem[PENS] = {O_SPACE, O_DIRT, O_BRICK, O_STEEL, O_STONE, O_DIAMOND, O_FIREFLY_1,
                                       O_BUTTER_1, O_AMOEBA, O_MAGIC_WALL, O_INBOX, O_PRE_OUTBOX};
static const char *const dir_name[4] = {"UP", "RIGHT", "DOWN", "LEFT"};

// All the elements to choose from (E), in rows of PICK_W as the page shows
// them, and their names (at most 20 letters, with a direction 19). One that
// walks is there with its first direction (pen_element).
#define PICKS  95
#define PICK_W 19
static const uint8_t pick_elem[PICKS] EDITOR_DATA = {
    O_SPACE, O_DIRT, O_BRICK, O_STEEL, O_STONE, O_DIAMOND, O_FIREFLY_1, O_BUTTER_1, O_AMOEBA, O_MAGIC_WALL,
    O_INBOX, O_PRE_OUTBOX, O_PRE_INVIS_OUTBOX, O_PLAYER, O_SLIME, O_NUT, O_CLOCK, O_ACID, O_LAVA,
    O_H_EXPANDING_WALL, O_V_EXPANDING_WALL, O_EXPANDING_WALL, O_H_EXPANDING_STEEL_WALL,
    O_V_EXPANDING_STEEL_WALL, O_EXPANDING_STEEL_WALL, O_EXPANDING_WALL_SWITCH, O_FALLING_WALL,
    O_STEEL_EXPLODABLE, O_STEEL_EATABLE, O_BRICK_EATABLE, O_DIRT2, O_DIRT_GLUED, O_BOX, O_WATER, O_AMOEBA_2,
    O_REPLICATOR, O_TELEPORTER, O_GRAVITY_SWITCH,
    O_ALT_FIREFLY_1, O_ALT_BUTTER_1, O_STONEFLY_1, O_BITER_1, O_DRAGONFLY_1, O_COW_1, O_GHOST, O_VOODOO,
    O_BLADDER, O_BLADDER_SPENDER, O_WAITING_STONE, O_CHASING_STONE, O_FLYING_STONE, O_MEGA_STONE,
    O_STONE_GLUED, O_FLYING_DIAMOND, O_DIAMOND_GLUED, O_TRAPPED_DIAMOND, O_WALLED_DIAMOND,
    O_KEY_1, O_KEY_2, O_KEY_3, O_DOOR_1, O_DOOR_2, O_DOOR_3, O_WALLED_KEY_1, O_WALLED_KEY_2, O_WALLED_KEY_3,
    O_DIAMOND_KEY, O_SWEET, O_POT, O_PNEUMATIC_HAMMER, O_ROCKET_LAUNCHER, O_BOMB, O_NITRO_PACK, O_SKELETON,
    O_GRAVESTONE, O_TIME_PENALTY,
    O_CONVEYOR_LEFT, O_CONVEYOR_RIGHT, O_CONVEYOR_SWITCH, O_CONVEYOR_DIR_SWITCH, O_REPLICATOR_SWITCH,
    O_CREATURE_SWITCH, O_BITER_SWITCH, O_DIRT_SLOPED_UP_RIGHT, O_DIRT_SLOPED_UP_LEFT,
    O_DIRT_SLOPED_DOWN_LEFT, O_DIRT_SLOPED_DOWN_RIGHT, O_BRICK_SLOPED_UP_RIGHT, O_BRICK_SLOPED_UP_LEFT,
    O_BRICK_SLOPED_DOWN_LEFT, O_BRICK_SLOPED_DOWN_RIGHT, O_STEEL_SLOPED_UP_RIGHT, O_STEEL_SLOPED_UP_LEFT,
    O_STEEL_SLOPED_DOWN_LEFT, O_STEEL_SLOPED_DOWN_RIGHT};
static const char pick_names[] =  // in bank 0: the overlay is full
    "SPACE\0DIRT\0BRICK WALL\0STEEL WALL\0BOULDER\0EMERALD\0FIREFLY\0BUTTERFLY\0AMOEBA\0MAGIC WALL\0"
    "INBOX\0EXIT\0HIDDEN EXIT\0ROCKFORD\0SLIME\0NUT\0CLOCK\0ACID\0LAVA\0"
    "WALL, GROWS ACROSS\0WALL, GROWS UP/DOWN\0WALL, GROWS 4 WAYS\0STEEL, GROWS ACROSS\0"
    "STEEL, GROWS UP/DOWN\0STEEL, GROWS 4 WAYS\0GROWING WALL SWITCH\0FALLING WALL\0"
    "STEEL, EXPLODES\0STEEL, DIGGABLE\0BRICK, DIGGABLE\0DIRT 2\0GLUED DIRT\0BOX\0WATER\0AMOEBA 2\0"
    "REPLICATOR\0TELEPORTER\0GRAVITY SWITCH\0"
    "ALT FIREFLY\0ALT BUTTERFLY\0STONEFLY\0BITER\0DRAGONFLY\0COW\0GHOST\0VOODOO\0"
    "BLADDER\0BLADDER MAKER\0WAITING BOULDER\0CHASING BOULDER\0FLYING BOULDER\0MEGA BOULDER\0"
    "GLUED BOULDER\0FLYING EMERALD\0GLUED EMERALD\0TRAPPED EMERALD\0WALLED EMERALD\0"
    "KEY 1\0KEY 2\0KEY 3\0DOOR 1\0DOOR 2\0DOOR 3\0WALLED KEY 1\0WALLED KEY 2\0WALLED KEY 3\0"
    "EMERALD KEY\0SWEET\0POT\0HAMMER\0ROCKET LAUNCHER\0BOMB\0NITRO PACK\0SKELETON\0"
    "GRAVESTONE\0TIME PENALTY\0"
    "CONVEYOR LEFT\0CONVEYOR RIGHT\0CONVEYOR SWITCH\0CONVEYOR DIR SWITCH\0REPLICATOR SWITCH\0"
    "CREATURE SWITCH\0BITER SWITCH\0SLOPED DIRT\0SLOPED DIRT\0"
    "SLOPED DIRT\0SLOPED DIRT\0SLOPED BRICK\0SLOPED BRICK\0"
    "SLOPED BRICK\0SLOPED BRICK\0SLOPED STEEL\0SLOPED STEEL\0"
    "SLOPED STEEL\0SLOPED STEEL";
static const char name_chars[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /:.!-,";  // as cavekit.py

static uint8_t slot;          // the one edited, from 0
static uint8_t pen;           // the element chosen (one that walks: its first direction)
static uint8_t pen_dir = DIR_LEFT;  // where one that walks starts
static bool have_slot;        // the slot is on the disk
static uint8_t again;         // the key that does it when pressed again
static uint8_t note;          // frames a note stays in the status line
static bool edit_shown;       // the status line shows the editor's line
// what a new cave starts with: Boulder Dash 1's rules (tools/cavekit.py)
static const uint8_t new_params[GD_NEW_PARAMS_SIZE] EDITOR_DATA = GD_NEW_PARAMS;

// How an element that walks has its four directions in GDash: 1 left, up,
// right, down (fireflies, butterflies, stoneflies, dragonflies, cows); 2 up,
// right, down, left (biters); 0 it does not walk
static EDITOR uint8_t walks(uint8_t e) {
    switch (e) {
    case O_FIREFLY_1:
    case O_ALT_FIREFLY_1:
    case O_BUTTER_1:
    case O_ALT_BUTTER_1:
    case O_STONEFLY_1:
    case O_DRAGONFLY_1:
    case O_COW_1:
        return 1;
    case O_BITER_1:
        return 2;
    }
    return 0;
}

// Its place among the elements to choose from, or PICKS
static EDITOR uint8_t pick_index(uint8_t e) {
    uint8_t i = 0;
    while (i < PICKS && pick_elem[i] != e)
        i++;
    return i;
}

static EDITOR const char *pick_name(uint8_t i) {
    const char *p = pick_names;
    while (i--)
        p += strlen(p) + 1;
    return p;
}

// What an element looks like in the editor, still
static EDITOR uint8_t elem_tile(uint8_t e) {
    uint8_t t = gtile[e];
    return t == T_SPARKLE ? T_DIAMOND0 : t;
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

// The direction of what walks in cell e (dir_name's order), or 4
static EDITOR uint8_t walks_to(uint8_t e) {
    static const uint8_t first[] EDITOR_DATA = {O_FIREFLY_1, O_ALT_FIREFLY_1, O_BUTTER_1, O_ALT_BUTTER_1,
                                                O_STONEFLY_1, O_DRAGONFLY_1, O_COW_1, O_BITER_1};
    for (uint8_t k = 0; k < sizeof first; k++) {
        uint8_t b = first[k];
        if (e >= b && e < b + 4)
            return walks(b) == 1 ? (e - b + 3) & 3 : e - b;
    }
    return 4;
}

// The element, where the cursor is (with an arrow if what is there walks:
// its direction), the slot, * if not saved:
// "[tile] FIREFLY LEFT         12,05<OWN1 03*" (the last column the
// screen shows is 38)
static EDITOR void edit_status(void) {
    static char line[36];
    memset(line, ' ', 35);
    const char *name = pick_name(pick_index(pen));
    uint8_t n = strlen(name);
    memcpy(line, name, n);
    if (walks(pen))
        memcpy(line + n + 1, dir_name[pen_dir], strlen(dir_name[pen_dir]));
    digits2(line + 21, cur_x);
    line[23] = ',';
    digits2(line + 24, cur_y);
    line[26] = "^>V< "[walks_to(file.own.map[cur_y * CAVE_W + cur_x])];
    const char *g = game_name[own_game][0] ? game_name[own_game] : "OWN";
    uint8_t n4 = strlen(g);
    memcpy(line + 27, g, n4 < 4 ? n4 : 4);  // the game, its first 4 letters
    digits2(line + 32, slot + 1);
    line[34] = dirty ? '*' : ' ';
    status_tile(2, elem_tile(pen));
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
    show_cursor = true;
    edit_shown = false;
    note = 0;
}

static EDITOR void edit_camera(bool jump) {
    camera_at(cur_x * 16 + 8, cur_y * 16 + 8, jump);
}

// The slot from the disk; an empty one (or none) gives a new cave
static EDITOR void edit_load(void) {
    have_slot = load_own(slot, 0);
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

// The element chosen, one that walks in its direction
static EDITOR uint8_t pen_element(void) {
    uint8_t w = walks(pen);
    return pen + (w == 1 ? (pen_dir + 1) & 3 : w == 2 ? pen_dir : 0);
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

// The element under the cursor becomes the one chosen; one that walks
// with its direction
static EDITOR void edit_take(void) {
    uint8_t e = file.own.map[cur_y * CAVE_W + cur_x];
    for (uint8_t i = 0; i < PICKS; i++) {
        uint8_t b = pick_elem[i], w = walks(b);
        if (e == b || (w && e >= b && e < b + 4)) {
            pen = b;
            if (w)
                pen_dir = w == 1 ? (e - b + 3) & 3 : e - b;
            edit_shown = false;
            return;
        }
    }
    edit_note("NOT AMONG THE ELEMENTS");
}

// All the elements on a page of their own (E): in the cave's view, rows of
// PICK_W on every second line, as they move in the cave; the cursor keys
// or the joystick choose one, the button takes it, E or Run/Stop leave it
// as it was. Taken again, one that walks turns.
static EDITOR void edit_pick(void) {
    static char line[36];
    uint8_t x = cur_x, y = cur_y;
    uint8_t sel = pick_index(pen), shown = PICKS, rep = 0;
    if (sel == PICKS)
        sel = 0;
    memset(cave, O_SPACE, CAVE_SIZE);
    for (uint8_t i = 0; i < PICKS; i++)
        cave[(1 + i / PICK_W * 2) * CAVE_W + i % PICK_W] = pick_elem[i];
    camera_at(0, 0, true);
    bool armed = false;
    for (;;) {
        cur_x = sel % PICK_W;
        cur_y = 1 + sel / PICK_W * 2;
        if (sel != shown) {
            shown = sel;
            memset(line, ' ', 35);
            const char *name = pick_name(sel);
            memcpy(line, name, strlen(name));
            memcpy(line + 22, "FIRE: TAKE IT", 13);
            status_tile(2, elem_tile(pick_elem[sel]));
            status_print(4, line);
        }
        next_frame();
        uint8_t key = get_key();
        if (key == 'E' || (pressed & IN_RESTART))
            break;
        if (armed && (pressed & IN_BUTTON)) {
            if (pen == pick_elem[sel] && walks(pen))
                pen_dir = (pen_dir + 1) & 3;
            pen = pick_elem[sel];
            break;
        }
        if (!(held & IN_BUTTON))
            armed = true;
        // at once, then on and on while held
        uint8_t dir = held & (IN_UP | IN_DOWN | IN_LEFT | IN_RIGHT);
        if (!dir) {
            rep = 0;
            continue;
        }
        if (rep == 0 || (rep >= 12 && (rep & 3) == 0)) {
            if (dir & IN_LEFT)
                sel = sel ? sel - 1 : PICKS - 1;
            if (dir & IN_RIGHT)
                sel = sel < PICKS - 1 ? sel + 1 : 0;
            if ((dir & IN_UP) && sel >= PICK_W)
                sel -= PICK_W;
            if ((dir & IN_DOWN) && sel + PICK_W < PICKS)
                sel += PICK_W;
        }
        if (++rep > 15)
            rep = 12;
    }
    cur_x = x;
    cur_y = y;
    edit_view();
    edit_camera(true);
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

// The slot's other levels empty (time 0): what the editor saves is played
// in all of them (load_own). An older disk has no files for them.
static EDITOR void edit_levels_empty(void) {
    static const uint16_t none = 0;
    if (have_slot)
        for (uint8_t lv = 1; lv < OWN_LEVELS; lv++)
            disk_save(own_name(slot, lv), &none, sizeof none);
}

static EDITOR void edit_save(void) {
    const char *why = edit_check();
    if (why) {
        edit_note(why);
        return;
    }
    busy("SAVING");
    bool ok = have_slot && disk_save(own_name(slot, 0), &file.own, sizeof file.own);
    edit_levels_empty();
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
    bool ok = have_slot && disk_save(own_name(slot, 0), &file.own, sizeof file.own);
    edit_levels_empty();
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

// The editor's cursor: at once, then on and on while a direction is held;
// true if it moved
static bool cursor_move(uint8_t *rep) {
    uint8_t dir = held & (IN_UP | IN_DOWN | IN_LEFT | IN_RIGHT);
    if (!dir) {
        *rep = 0;
        return false;
    }
    bool now = *rep == 0 || (*rep >= 12 && (*rep & 3) == 0);
    if (now) {
        if ((dir & IN_LEFT) && cur_x)
            cur_x--;
        if ((dir & IN_RIGHT) && cur_x < file.own.w - 1)
            cur_x++;
        if ((dir & IN_UP) && cur_y)
            cur_y--;
        if ((dir & IN_DOWN) && cur_y < file.own.h - 1)
            cur_y++;
    }
    if (++*rep > 15)
        *rep = 12;
    return now;
}

// The editor's map (M): the whole cave at once, each cell a character in
// the colour of its tile (mkgfx.py's tile_colours), the cursor a blinking
// white cell that moves as in the editor. The view has 38 columns: a wider
// cave moves under the cursor at its right edge.
#define MAP_COLS (VIEW_W / 8)
static uint8_t map_col, map_row, map_off;  // where cell map_off, 0 is shown

static EDITOR void map_cell(uint8_t x, uint8_t y, bool cursor) {
    video_cell(map_col + x - map_off, (map_row + y) * 8,
               cursor ? T_CURSOR : elem_tile(file.own.map[y * CAVE_W + x]));
}

#define MAP_OFF() (cur_x >= MAP_COLS ? cur_x - (MAP_COLS - 1) : 0)

static EDITOR void map_draw(void) {
    map_off = MAP_OFF();
    uint8_t w = file.own.w < MAP_COLS ? file.own.w : MAP_COLS;
    for (uint8_t y = 0; y < file.own.h; y++)
        for (uint8_t x = map_off; x < map_off + w; x++)
            map_cell(x, y, false);
}

__attribute__((noinline)) static void edit_map(void) {
    map_col = 1 + (file.own.w < MAP_COLS ? (MAP_COLS - file.own.w) / 2 : 0);
    map_row = (VIEW_H / 8 - file.own.h) / 2;
    video_clear();
    status_center("THE WHOLE CAVE  M OR FIRE: BACK");
    map_draw();
    uint8_t rep = 0;
    bool armed = false;
    for (;;) {
        title_frame();
        uint8_t x = cur_x, y = cur_y;
        if (cursor_move(&rep)) {
            if (MAP_OFF() != map_off)
                map_draw();
            else
                map_cell(x, y, false);
            map_cell(cur_x, cur_y, true);
        } else if ((frame & 15) == 0) {
            map_cell(cur_x, cur_y, frame & 16);
        }
        if (get_key() || (pressed & IN_RESTART) || (armed && (pressed & IN_BUTTON)))
            break;
        if (!(held & IN_BUTTON))
            armed = true;
    }
    video_clear();
    edit_shown = false;
    note = 0;
}

static EDITOR void edit_help(void) {
    static const char *const lines[9] = {
        "MOVE     CURSOR KEYS OR JOYSTICK",
        "PUT      FIRE OR SPACE, HELD: DRAW",
        "E        CHOOSE AMONG ALL ELEMENTS",
        "1-0 I X  CHOOSE ONE OF THESE BELOW",
        "G        CHOOSE WHAT THE CURSOR IS ON",
        "R        THE WAY WHAT WALKS STARTS",
        "V        NAME AND VALUES   T  TRY IT",
        "S        SAVE   + -  NEXT, LAST SLOT",
        "C NEW  D EMPTY  M MAP  RUN/STOP TITLE",
    };
    video_clear();
    status_center("ANY KEY: BACK");
    video_text_in(CENTRE(11), 0, "CAVE EDITOR", title_row);
    for (uint8_t i = 0; i < 9; i++)
        video_text(2, 16 + i * 16, lines[i]);
    // the elements with their keys, in a row
    char key[2] = {0, 0};
    for (uint8_t k = 0; k < PENS; k++) {
        uint8_t col = 2 + k * 3;
        key[0] = pen_keys[k];
        video_text(col, 160, key);
        video_tile(col + 1, 160, elem_tile(pen_elem[k]));
    }
    page_wait();
    video_clear();
    edit_shown = false;
    note = 0;
}

// The values page: a line each, the one chosen shining
#define VALUES 9
#define VAL_GAME 8  // the game's name (the slot's partition), not the cave's
#define VAL_Y0 4
static const char *const val_text[VALUES] = {
    "NAME", "TIME          SECONDS", "EMERALDS      TO OPEN THE EXIT", "VALUE         POINTS EACH",
    "EXTRA         EACH AFTER THAT", "SPEED         MS PER STEP", "AMOEBA        SECONDS SLOW",
    "MAGIC         SECONDS, 0: NO END", "GAME"};
static const uint8_t val_min[VALUES] = {0, 1, 0, 0, 0, 50, 0, 0, 0};
static const uint16_t val_max[VALUES] = {0, 999, 255, 99, 99, 250, 999, 999, 0};
static char game_edit[9];  // the game's name as it is typed
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
    const char *text = i == VAL_GAME ? game_edit : i ? 0 : file.own.name;
    if (text)
        memcpy(line + 10, text, strlen(text));
    else
        digits3(line + 9, val_get(i));
    video_text_in(2, VAL_Y0 + i * 16, line, chosen ? title_row : font_row);
}

// Up and down choose a line, left and right change its value (held: on and
// on, faster after a while), letters and Del the names - the cave's, and
// the game's (renamed on the disk as the page is left; not on an older
// disk, whose slots have no game). Return, V, Run/Stop or the button (but
// not on a name, where Space is a space) go back.
static EDITOR void edit_values(void) {
    if (file.own.scheduling && have_gdash) {  // the speed GDash starts it with
        gd_start(&file.own, 0);
        c64_speed = gd.speed;
        memcpy(cave, file.own.map, CAVE_SIZE);
    }
    video_clear();
    status_center("NAME AND VALUES  RETURN OR V: BACK");
    video_text(CENTRE(33), 156, "UP/DOWN CHOOSE  LEFT/RIGHT CHANGE");
    uint8_t sel = 1, rep = 0;
    bool armed = false;
    strcpy(game_edit, game_name[own_game]);
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
        char *field = !sel ? file.own.name : sel == VAL_GAME && game_edit[0] ? game_edit : 0;
        uint8_t lr = held & (IN_LEFT | IN_RIGHT);
        if (!lr)
            rep = 0;
        else if (!field && sel != VAL_GAME && (rep == 0 || (rep >= 20 && (rep & 1)))) {
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
        if (field && key && key != '\r') {
            uint8_t n = strlen(field);
            if (key == KEY_DEL && n > (field == game_edit))  // a game keeps a name
                field[n - 1] = 0;
            else if (n < (field == game_edit ? 8 : NAME_LEN) && strchr(name_chars, key) && key != '/')
                field[n] = key;
            else
                continue;
            if (field == file.own.name)
                dirty = true;
            val_line(sel, true);
            armed = false;  // Space was a space
            continue;
        }
        if (key == '\r' || key == 'V' || (pressed & IN_RESTART) || (!field && armed && (pressed & IN_BUTTON)))
            break;
        if (!(held & IN_BUTTON))
            armed = true;
    }
    video_shine(0);
    video_clear();
    edit_shown = false;
    note = 0;
    if (strcmp(game_edit, game_name[own_game])) {  // a new name for the game
        if (disk_rename(game_name[own_game], game_edit)) {
            strcpy(game_name[own_game], game_edit);
            edit_note("THE GAME IS RENAMED");
        } else {
            edit_note("CANNOT RENAME THE GAME");
        }
    }
}

// The edited cave in KEEP_BANK (mem.h) when the editor is left, and back
// from there when it is opened again: it stays as it was, saved or not,
// until the game ends. Not without the ROM's banks as RAM.
static EDITOR void edit_keep(bool back) {
    dma_begin(0, 0);
    if (back)
        dma_copy(KEEP_OFF, KEEP_BANK, (uint16_t)&file, 0, sizeof file);
    else
        dma_copy((uint16_t)&file, 0, KEEP_OFF, KEEP_BANK, sizeof file);
    dma_run();
}

static EDITOR void editor(void) {
    play_mode = PLAY_TEST;
    again = 0;
    if (kept) {
        edit_keep(true);
        loaded = 0xFF;
        edit_view();
    } else {
        edit_load();
        cur_x = cur_y = 2;
    }
    edit_camera(true);
    memset(covered, 0xFF, sizeof covered);
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

        if (cursor_move(&rep))
            edit_shown = false;
        if (!(held & IN_BUTTON))
            armed = true;
        else if (armed)
            edit_put();

        for (uint8_t k = 0; k < PENS; k++)
            if (key == pen_keys[k]) {
                if (pen_elem[k] == pen && walks(pen))
                    pen_dir = (pen_dir + 1) & 3;
                pen = pen_elem[k];
                edit_shown = false;
            }
        switch (key) {
        case 'E':
            edit_pick();
            armed = false;
            break;
        case 'G':
            edit_take();
            break;
        case 'R':
            if (!walks(pen)) {
                edit_note("R TURNS WHAT WALKS: FIREFLIES, ...");
                break;
            }
            pen_dir = (pen_dir + 1) & 3;
            edit_shown = false;
            break;
        case 'H':
        case KEY_HELP:
            edit_help();
            armed = false;
            break;
        case 'V':
            edit_values();
            armed = false;
            break;
        case 'M':
            edit_map();
            edit_camera(true);
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
                // the slots of all games one after the other
                if (key == '+' && ++slot == OWN_SLOTS) {
                    slot = 0;
                    own_game = (own_game + 1) % games;
                } else if (key == '-' && !slot--) {
                    slot = OWN_SLOTS - 1;
                    own_game = (own_game + games - 1) % games;
                }
                edit_load();
            }
            break;
        case KEY_STOP:  // nothing is lost: the cave is kept
            if (rom_ram) {
                edit_keep(false);
                kept = true;
            } else if (!twice(key, false, "NOT SAVED - RUN/STOP AGAIN: LEAVE")) {
                break;
            }
            show_cursor = false;
            cover_cave(1);
            return;
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
    cave_no = play_mode == PLAY_OWN ? start_own : start_cave;
    own_game = start_game;
    level = start_level;
    bool have_cave = true;
    while (lives) {
#ifdef TOUR
        // the caves in the slots, each with its moves (TOURnn, from
        // tools/democave.py), up to the first empty slot; a slot without
        // moves is left out
        static char tour_file[] = "TOUR00";
        for (;; cave_no++) {
            tour_file[4] = '0' + (cave_no + 1) / 10;
            tour_file[5] = '0' + (cave_no + 1) % 10;
            if (cave_no >= OWN_SLOTS || !load_own(cave_no, 0) || !file.own.time)
                demo_end();
            if (disk_load(tour_file, 0, (uint16_t)demo_moves))
                break;
        }
        use_own_cave();
#else
#ifdef SCREENCAST
        // after the last cave with moves; the next one with moves
        if (demo_at >= DEMO_LAST || demo_at >= DEMO_CAVES)
            demo_end();
        cave_no = demo_list[demo_at] - 1;
#endif
        if (!(have_cave = play_mode == PLAY_OWN ? next_own() : next_cave()))
            break;
#endif
#ifdef SCREENCAST
        demo_p = demo_moves;
        demo_left = 0;
#endif
        // An intermission is played once, as in GDash: a life for it at its
        // start (instantlife) or at its exit; not got out, no life is lost
        // and the next cave comes
        bool inter = file.own.flags & GDF_INTERMISSION;
        bool instant = file.own.flags & GDF_INTERMISSION_INSTANTLIFE;
        if (inter && instant && lives < 9)
            lives++;
        uint8_t end = play_cave();
        if (end == END_QUIT) {  // straight back to the title
            hs_new = HS_COUNT;
            return;
        }
        score += game.score;
        if (end == END_EXITED) {
            cave_no++;
            if (inter && !instant && lives < 9)
                lives++;
        } else if (inter) {
            cave_no++;
        } else {
            lives--;
        }
#ifdef SCREENCAST
        if (end != END_EXITED)  // something went wrong
            demo_end();
#ifndef TOUR
        demo_at++;
#endif
#endif
    }
    status_center(have_cave ? "GAME OVER" : play_mode == PLAY_OWN ? "NO OWN CAVES ON THE DISK" : "NO CAVES ON THE DISK");
    sound_off();
    wait_button(pal ? 125 : 150);  // 2.5 seconds, or the button
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

// What the NMI vector points to: RTI. Below $4000, where GDash's engine
// never shows (gdfar.s maps it in while it runs, and Restore's NMI can come
// then); link.ld's .lowbss is not loaded, so main() writes it.
static uint8_t rti __attribute__((section(".lowbss")));

// Banks 2 and 3 take a byte (the C65 ROM there is write-protected at first)
static bool rom_takes(uint8_t v) {
    static uint8_t probe;
    dma_begin(0, 0);
    dma_fill(v, 0xFFF0, LOGO_BANK, 1);
    dma_copy(0xFFF0, LOGO_BANK, (uint16_t)&probe, 0, 1);
    dma_run();
    return probe == v;
}

// The hypervisor's call $70 turns the write protection of the C65 ROM's
// banks 2 and 3 on or off
static void rom_toggle(void) {
    __asm__ volatile("lda #$70\n sta $d640\n clv\n sei\n ldz #0" ::: "a", "x", "y", "memory");
}

#ifndef SCREENCAST
// The attic RAM is there: it takes a byte (behind the ROM's copy)
static bool attic_takes(uint8_t v) {
    static uint8_t probe;
    dma_begin(0, ROM_SAVE_MB);
    dma_fill(v, 0, ROM_SAVE_BANKS, 1);
    dma_run();
    dma_begin(ROM_SAVE_MB, 0);
    dma_copy(0, ROM_SAVE_BANKS, (uint16_t)&probe, 0, 1);
    dma_run();
    return probe == v;
}
#endif

// The C65 ROM's banks 2 and 3 writable (mem.h; rom_toggle)
static bool rom_writable(void) {
    if (rom_takes(0xA5) && rom_takes(0x5A))
        return true;
    rom_toggle();
#ifndef SCREENCAST
    rom_toggled = true;
#endif
    return rom_takes(0xA5) && rom_takes(0x5A);
}

#ifdef GDCHECK
// tests/test_gdmega65.py: every own cave on the disk played for
// GDCHECK_STEPS steps with the input tests/gdplay.c gives it (seed: the
// slot's number) - or, if its file CHECKnn has moves, with those (as a
// demo file: count and input, DIR_* | IN_FIRE | CHECK_SUICIDE; then
// standing still) -, the digest of each step (gddigest.h) into bank 4, slot
// after slot; then the emulator is told to stop.
#include "gddigest.h"
#ifndef GDCHECK_STEPS
#define GDCHECK_STEPS 200
#endif
#define GDCHECK_BANK  4
#define CHECK_MOVES   760   // bytes of CHECKnn (build.sh: 3 blocks)
#define CHECK_SUICIDE 0x10  // Run/Stop (tools/democave.py's IN_SUICIDE)
_Static_assert(OWN_SLOTS * GDCHECK_STEPS * 4UL <= 0x10000, "the digests in one bank");

// A whole step at once, as gd_iterate on the host
static void gd_check_step(uint8_t move, bool fire, bool suicide) {
    gd_step_begin(move, fire, suicide);
    while (!(gd_step_rows(move | (fire ? 0x80 : 0), 0, 0) & 1))
        ;
}

static void gd_check(void) {
    static const uint8_t dirs[] = {MV_STILL, MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT,
                                   MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_UP_RIGHT};
    static const uint8_t mv[] = {MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_STILL};
    static uint8_t moves[CHECK_MOVES];
    static char moves_file[] = "CHECK00";
    static uint32_t d;
    dma_begin(0, 0);
    dma_fill(0, 0, GDCHECK_BANK, 0);
    dma_run();
    for (uint8_t n = 0; n < OWN_SLOTS; n++) {
        if (!load_own(n, 0) || !file.own.time)
            continue;
        moves_file[5] = '0' + (n + 1) / 10;
        moves_file[6] = '0' + (n + 1) % 10;
        if (!disk_load(moves_file, 0, (uint16_t)moves))
            moves[0] = 0;
        const uint8_t *p = moves;
        uint8_t left = 0, step = DIR_NONE;
        bool scripted = moves[0] != 0;
        gd_start(&file.own, 0);
        uint32_t lcg = n + 1;
        uint16_t at = (uint16_t)n * GDCHECK_STEPS * 4;
        for (uint16_t t = 0; t < GDCHECK_STEPS; t++, at += 4) {
            if (scripted) {
                if (!left && p[0]) {
                    left = p[0];
                    step = p[1];
                    p += 2;
                }
                if (left)
                    left--;
                else
                    step = DIR_NONE;
                gd_check_step(mv[step & 7], (step & IN_FIRE) != 0, (step & CHECK_SUICIDE) != 0);
            } else {
                lcg = lcg * 1103515245u + 12345u;
                uint16_t in = (lcg >> 16) & 0x7FFF;
                gd_check_step(dirs[in % 10], (in >> 4) % 8 == 0, false);
            }
            d = gd_digest();
            dma_begin(0, 0);
            dma_copy((uint16_t)&d, 0, at, GDCHECK_BANK, 4);
            dma_run();
        }
    }
    POKE(0xD6CF, 0);
    POKE(0xD6CF, 0x42);
    for (;;)
        ;
}
#endif

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
    rti = 0x40;
    POKE(0xFFFA, (uint16_t)&rti);
    POKE(0xFFFB, (uint16_t)&rti >> 8);
    pal = !(PEEK(0xD06F) & 0x80);

    // The ROM's banks 2 and 3 into the attic RAM, before anything is
    // written there (rom_takes' probe too), and the screen as BASIC had it:
    // for the way back
#ifndef SCREENCAST
    if (attic_takes(0xA5) && attic_takes(0x5A)) {
        rom_copy(false);
        rom_saved = true;
    }
    basic_save();
#endif
    video_init();
    sound_init();
    init_tiles();
    // The tiles from the disk - without the spinner, which is made of
    // them -, the title logo and the high scores (mem.h)
    disk_load("SMARAGD.PAL", PAL_BANK, PAL_OFF);
    video_palettes();
    disk_load("SMARAGD.TILES", GFX_BANK, TILES_OFF);
    rom_ram = rom_writable();
    have_logo = rom_ram && load("LOADING", "SMARAGD.LOGO", LOGO_BANK, LOGO_OFF);
    // GDash's engine for the own caves, and the calls into it
    have_gdash = rom_ram && disk_load("SMARAGD.LOW", 0, LOW_AT) && load("LOADING", "SMARAGD.GD", GD_BANK, GD_OFF);
    games = disk_partitions(game_name, GAMES_MAX, "CAVES");
    if (!games)
        games = 1;  // an older disk: the slots in its directory
    hiscore_load();
#ifdef TOUR
    start_cave = CAVE_COUNT;  // the own caves: the demo caves
#elif defined(SCREENCAST)
    start_cave = DEMO_CAVES ? demo_list[DEMO_FIRST - 1] - 1 : 0;
#endif
#ifdef GDCHECK
    gd_check();
#endif
#ifdef ASM_CHECK
    music_check();
    sound_check();
    cover_check();
    POKE(0xD6CF, 0);
    POKE(0xD6CF, 0x42);
    for (;;)
        ;
#endif

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
