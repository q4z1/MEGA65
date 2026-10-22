// Smaragd Dash: GDash's engine, for the own caves (the slots OWN01, ...).
//
// A port of GDash's cave engine (CaveRendered::iterate and what it calls,
// https://github.com/revvv/gdash-export-CrLi; MIT license, Copyright (c)
// 2007-2018 GDash Project), so the caves of GDash play as they do there:
// all of its elements, its properties, its timing. The caves come from
// tools/cavekit.py, as GDash draws them in a level (GdCaveFile,
// build/gen/gdcave.h). It plays in the arrays of the game's own engine
// (engine.h: cave[] with GDash's element codes, moved[] for the drawing) and
// keeps `game` up to date for the status line.
//
// Plain C without any hardware access: tests/gdplay.c plays it on the host
// beside GDash itself. Built with GD_EXACT it uses GDash's random numbers
// (GLib's Mersenne Twister, 2.5K) and plays exactly as GDash does; the game
// has smaller ones of its own.

#ifndef GDENGINE_H
#define GDENGINE_H

#include <stdbool.h>
#include <stdint.h>

#include "engine.h"
#include "gdcave.h"

// GDash's directions: the eight around, and twice as far
enum {
    MV_STILL, MV_UP, MV_UP_RIGHT, MV_RIGHT, MV_DOWN_RIGHT, MV_DOWN, MV_DOWN_LEFT, MV_LEFT, MV_UP_LEFT,
    MV_UP_2, MV_UP_RIGHT_2, MV_RIGHT_2, MV_DOWN_RIGHT_2, MV_DOWN_2, MV_DOWN_LEFT_2, MV_LEFT_2, MV_UP_LEFT_2
};

// GDash's states of the player, the amoeba and the magic wall
enum { GD_PL_NOT_YET, GD_PL_LIVING, GD_PL_TIMEOUT, GD_PL_DIED, GD_PL_EXITED };
enum { GD_AM_SLEEPING, GD_AM_AWAKE, GD_AM_TOO_BIG, GD_AM_ENCLOSED };
enum { GD_MW_DORMANT, GD_MW_ACTIVE, GD_MW_EXPIRED };

// What GDash's CaveRendered keeps while a cave is played
typedef struct {
    const GdCaveFile *f;          // the cave as loaded, not changed
    uint8_t w, h;
    uint32_t flags;               // GDF_*, some of which change in the game
    int32_t time;                 // "milliseconds" left (timing_factor per second)
    int32_t magic_wall_time, amoeba_time, amoeba_2_time, hatching_delay_time;
    uint16_t timing_factor;       // 1000, or 1200 for PAL timing
    uint8_t hatching_delay_frame;
    uint16_t speed;               // milliseconds per step
    int16_t diamonds_needed;
    uint16_t diamond_value;       // becomes the extra value once the exit opens
    uint32_t amoeba_growth_prob, amoeba_2_growth_prob;
    uint8_t biter_delay_frame;
    uint8_t gravity, gravity_next_direction;
    uint8_t player_state;         // GD_PL_*
    int8_t player_x, player_y;
    int8_t player_x_mem[16], player_y_mem[16];  // for the chasing stones
    uint8_t player_seen_ago;
    bool kill_player, voodoo_touched, sweet_eaten, got_pneumatic_hammer, diamond_key_collected;
    bool hatched, gate_open, inbox_flash_toggle, gravity_disabled, convert_amoeba_this_frame;
    uint8_t gate_open_flash;
    uint8_t pneumatic_hammer_active_delay;
    uint8_t key1, key2, key3;
    uint8_t biters_wait_frame, replicators_wait_frame;
    int32_t creatures_direction_will_change, gravity_will_change;
    uint16_t diamonds_collected;
    uint8_t skeletons_collected;
    uint16_t score;               // points of the last step
    uint8_t amoeba_state, amoeba_2_state, magic_wall_state;  // GD_AM_*, GD_MW_*
    int32_t ckdelay_current, ckdelay_extra_for_animation;
    uint8_t last_direction;
    uint8_t sound;                // SND_* (engine.h) of the last step
} GdState;

extern GdState gd;

// The cave from f, started as GDash does (CaveRendered + setup_for_game);
// seed: its random numbers
void gd_start(const GdCaveFile *f, uint32_t seed);

// A step: the player's direction (MV_*) and fire, or giving up (suicide)
void gd_iterate(uint8_t player_move, bool player_fire, bool suicide);

// The seconds left as GDash shows them
uint16_t gd_time_visible(void);

#endif
