// A test oracle for Smaragd Dash's port of GDash's engine
// (smaragd-dash/src/gdengine.c, tests/test_gdengine.sh): GDash's own cave
// code (https://github.com/revvv/gdash-export-CrLi, MIT license), built
// without its user interface by tools/build-tools.sh, tells what it does.
//
//   gdash-oracle elements                 its element table
//   gdash-oracle scanned                  the names of the scanned twins
//   gdash-oracle props                    the cave properties, their defaults
//   gdash-oracle engines                  what each engine's defaults set
//   gdash-oracle save <file> <out.bd>     the file as GDash saves it (.gds too)
//   gdash-oracle cave <file.bd> <level>   each cave's values after the start
//   gdash-oracle play <file.bd> <level> <steps> [cave]
//                                         playing with pseudo-random input: a
//                                         line per step, the map's hash, state
//
// Element codes are GDash's elements without their scanned twins, in its
// order: smaragd-dash/tools/cavekit.py's.
#include "config.h"
#include <glib.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include "cave/caveset.hpp"
#include "cave/cavestored.hpp"
#define private public
#define protected public
#include "cave/caverendered.hpp"
#undef private
#undef protected
#include "cave/elementproperties.hpp"
#include "fileops/bdcffload.hpp"
#include "fileops/loadfile.hpp"
#include "cave/cavetypes.hpp"
#include "misc/logger.hpp"
#include "fileops/c64import.hpp"

static int code_of[O_MAX];   // GDash's element -> its index without scanned twins

static void codes() {
    int n = 0;
    for (int i = 0; i < O_MAX; i++)
        if (!(gd_element_properties[i].flags & P_SCANNED))
            code_of[i] = n++;
        else
            code_of[i] = -1;
    for (int i = 0; i < O_MAX; i++)
        if (code_of[i] < 0)
            code_of[i] = code_of[gd_element_properties[i].pair];
}

// A .bd file, or any other GDash reads (.gds: imported C64 games)
static CaveSet load(const char *path) {
    return load_caveset_from_file(path);
}

static unsigned lcg;
static unsigned next_rand() {
    lcg = lcg * 1103515245u + 12345u;
    return (lcg >> 16) & 0x7FFF;
}

int main(int argc, char **argv) {
    Logger logger(true);
    gd_cave_types_init();
    codes();
    if (!strcmp(argv[1], "scanned")) {
        // the names of the scanned twins, with the code of the element they belong to
        for (int i = 0; i < O_MAX; i++)
            if (gd_element_properties[i].flags & P_SCANNED)
                printf("%s %d %u\n", gd_element_properties[i].filename, code_of[i], gd_element_properties[i].flags);
        return 0;
    }
    if (!strcmp(argv[1], "elements")) {
        for (int i = 0; i < O_MAX; i++) {
            GdElementPorperty const &p = gd_element_properties[i];
            if (p.flags & P_SCANNED)
                continue;
            GdElementEnum h = gd_element_get_hammered(GdElementEnum(i));
            printf("%d\t%d\t%s\t%d\t%u\t%d\t%d\n", code_of[i], i, p.filename, p.character, p.flags, p.ckdelay,
                   h == O_NONE ? 255 : code_of[h]);
        }
        return 0;
    }
    if (!strcmp(argv[1], "props")) {
        // the cave properties with their defaults: GDash's, then those of each engine
        for (int eng = -1; eng < GD_ENGINE_MAX; eng++) {
            CaveStored c;
            if (eng >= 0)
                C64Import::cave_set_engine_defaults(c, GdEngineEnum(eng));
            PropertyDescription const *d = c.get_description_array();
            for (int i = 0; d[i].identifier; i++) {
                GdType t = d[i].type;
                if (t == GD_TAB || t == GD_LABEL || t == GD_TYPE_STRING || t == GD_TYPE_LONGSTRING || t == GD_TYPE_COLOR)
                    continue;
                std::unique_ptr<GetterBase> const &pr = d[i].prop;
                printf("%d\t%d\t%s\t%d\t%d\t%u\t", eng, i, d[i].identifier, (int)t, d[i].flags, pr->count);
                for (unsigned j = 0; j < pr->count; j++) {
                    int v = 0;
                    switch (t) {
                    case GD_TYPE_INT: v = c.get<GdInt>(pr); break;
                    case GD_TYPE_INT_LEVELS: v = c.get<GdIntLevels>(pr)[j]; break;
                    case GD_TYPE_PROBABILITY: v = c.get<GdProbability>(pr); break;
                    case GD_TYPE_PROBABILITY_LEVELS: v = c.get<GdProbabilityLevels>(pr)[j]; break;
                    case GD_TYPE_BOOLEAN: v = c.get<GdBool>(pr); break;
                    case GD_TYPE_BOOLEAN_LEVELS: v = c.get<GdBoolLevels>(pr)[j]; break;
                    case GD_TYPE_ELEMENT: case GD_TYPE_EFFECT: v = code_of[c.get<GdElement>(pr)]; break;
                    case GD_TYPE_DIRECTION: v = c.get<GdDirection>(pr); break;
                    case GD_TYPE_SCHEDULING: v = c.get<GdScheduling>(pr); break;
                    default: break;
                    }
                    printf("%s%d", j ? " " : "", v);
                }
                printf("\n");
            }
        }
        return 0;
    }
    if (!strcmp(argv[1], "engines")) {
        // what each engine's defaults set: run on two different poisoned caves,
        // a property set by it comes out the same from both
        for (int eng = 0; eng < GD_ENGINE_MAX; eng++) {
            CaveStored c[2];
            for (int k = 0; k < 2; k++) {
                PropertyDescription const *d = c[k].get_description_array();
                for (int i = 0; d[i].identifier; i++) {
                    std::unique_ptr<GetterBase> const &pr = d[i].prop;
                    for (unsigned j = 0; j < (pr ? pr->count : 0); j++)
                        switch (d[i].type) {
                        case GD_TYPE_INT: c[k].get<GdInt>(pr) = 7777 + k; break;
                        case GD_TYPE_INT_LEVELS: c[k].get<GdIntLevels>(pr)[j] = 7777 + k; break;
                        case GD_TYPE_PROBABILITY: c[k].get<GdProbability>(pr) = 7777 + k; break;
                        case GD_TYPE_PROBABILITY_LEVELS: c[k].get<GdProbabilityLevels>(pr)[j] = 7777 + k; break;
                        case GD_TYPE_BOOLEAN: c[k].get<GdBool>(pr) = k; break;
                        case GD_TYPE_ELEMENT: case GD_TYPE_EFFECT: c[k].get<GdElement>(pr) = k ? O_SKELETON : O_POT; break;
                        case GD_TYPE_DIRECTION: c[k].get<GdDirection>(pr) = k ? MV_UP_LEFT : MV_DOWN_LEFT; break;
                        case GD_TYPE_SCHEDULING: c[k].get<GdScheduling>(pr) = k ? GD_SCHEDULING_CRDR : GD_SCHEDULING_BD2_PLCK_ATARI; break;
                        default: break;
                        }
                }
                C64Import::cave_set_engine_defaults(c[k], GdEngineEnum(eng));
            }
            PropertyDescription const *d = c[0].get_description_array();
            for (int i = 0; d[i].identifier; i++) {
                GdType t = d[i].type;
                std::unique_ptr<GetterBase> const &pr = d[i].prop;
                if (!pr || t == GD_TYPE_STRING || t == GD_TYPE_LONGSTRING || t == GD_TYPE_COLOR || t == GD_TYPE_BOOLEAN_LEVELS || t == GD_TYPE_COORDINATE)
                    continue;
                bool same = true;
                std::string vals;
                for (unsigned j = 0; j < pr->count; j++) {
                    int v[2];
                    for (int k = 0; k < 2; k++)
                        switch (t) {
                        case GD_TYPE_INT: v[k] = c[k].get<GdInt>(pr); break;
                        case GD_TYPE_INT_LEVELS: v[k] = c[k].get<GdIntLevels>(pr)[j]; break;
                        case GD_TYPE_PROBABILITY: v[k] = c[k].get<GdProbability>(pr); break;
                        case GD_TYPE_PROBABILITY_LEVELS: v[k] = c[k].get<GdProbabilityLevels>(pr)[j]; break;
                        case GD_TYPE_BOOLEAN: v[k] = c[k].get<GdBool>(pr); break;
                        case GD_TYPE_ELEMENT: case GD_TYPE_EFFECT: v[k] = code_of[c[k].get<GdElement>(pr)]; break;
                        case GD_TYPE_DIRECTION: v[k] = c[k].get<GdDirection>(pr); break;
                        case GD_TYPE_SCHEDULING: v[k] = c[k].get<GdScheduling>(pr); break;
                        default: v[k] = 0; break;
                        }
                    if (v[0] != v[1])
                        same = false;
                    vals += (j ? "," : "") + std::to_string(v[0]);
                }
                if (same)
                    printf("%d\t%d\t%s\n", eng, i, vals.c_str());
            }
        }
        return 0;
    }
    CaveSet cs = load(argv[2]);
    int level = argc > 3 ? atoi(argv[3]) : 0;
    if (!strcmp(argv[1], "save")) {  // as GDash saves it: save <in> <out.bd>
        cs.save_to_file(argv[3]);
        return 0;
    }
    if (!strcmp(argv[1], "cave")) {
        for (unsigned n = 0; n < cs.caves.size(); n++) {
            CaveRendered r(cs.caves[n], level, 0);
            r.setup_for_game();
#define I(f) printf(#f "=%d\n", (int)r.f)
#define E(f) printf(#f "=%d\n", code_of[r.f])
            printf("CAVE %u\n", n + 1);
            I(w); I(h); I(x1); I(y1); I(x2); I(y2);
            I(time); I(timing_factor); I(max_time); I(time_bonus); I(time_penalty); I(diamonds_needed);
            I(diamond_value); I(extra_diamond_value); I(magic_wall_time); I(amoeba_time); I(amoeba_max_count);
            I(amoeba_2_time); I(amoeba_2_max_count); I(hatching_delay_time); I(hatching_delay_frame);
            I(speed); I(ckdelay); I(scheduling); I(intermission); I(pneumatic_hammer_frame);
            I(hammered_wall_reappear_frame); I(biter_delay_frame); I(replicator_delay_frame);
            I(creatures_direction_auto_change_time); I(gravity_change_time); I(skeletons_needed_for_pot);
            I(skeletons_worth_diamonds); I(pushing_stone_prob); I(pushing_stone_prob_sweet);
            I(amoeba_growth_prob); I(amoeba_fast_growth_prob); I(amoeba_2_growth_prob);
            I(amoeba_2_fast_growth_prob); I(slime_permeability); I(acid_spread_ratio); I(slime_permeability_c64);
            I(c64_rand.rand_seed_1); I(c64_rand.rand_seed_2);
            E(snap_element); E(magic_diamond_to); E(magic_stone_to); E(magic_mega_stone_to);
            E(magic_nitro_pack_to); E(magic_nut_to); E(magic_flying_stone_to); E(magic_flying_diamond_to);
            E(amoeba_too_big_effect); E(amoeba_enclosed_effect); E(amoeba_2_too_big_effect);
            E(amoeba_2_enclosed_effect); E(amoeba_2_explosion_effect); E(slime_eats_1); E(slime_converts_1);
            E(slime_eats_2); E(slime_converts_2); E(slime_eats_3); E(slime_converts_3); E(acid_eats_this);
            E(acid_turns_to); E(biter_eat); E(bladder_converts_by); E(nut_turns_to_when_crushed);
            E(stone_falling_effect); E(stone_bouncing_effect); E(diamond_falling_effect);
            E(diamond_bouncing_effect); E(firefly_explode_to); E(alt_firefly_explode_to);
            E(butterfly_explode_to); E(alt_butterfly_explode_to); E(stonefly_explode_to);
            E(dragonfly_explode_to); E(explosion_effect); E(explosion_3_effect); E(diamond_birth_effect);
            E(bomb_explosion_effect); E(nitro_explosion_effect); E(expanding_wall_looks_like);
            E(dirt_looks_like); E(amoeba_2_looks_like); I(gravity);
            I(diagonal_movements); I(active_is_first_found); I(mega_stones_pushable_with_sweet);
            I(infinite_rockets); I(hammered_walls_reappear); I(voodoo_collects_diamonds);
            I(voodoo_dies_by_stone); I(voodoo_disappear_in_explosion); I(voodoo_any_hurt_kills_player);
            I(amoeba_timer_started_immediately); I(amoeba_timer_wait_for_hatching);
            I(amoeba_2_explodes_by_amoeba); I(magic_timer_zero_is_infinite); I(magic_timer_wait_for_hatching);
            I(magic_wall_stops_amoeba); I(magic_wall_breakscan); I(slime_predictable);
            I(expanding_wall_changed); I(replicators_active); I(conveyor_belts_active);
            I(conveyor_belts_direction_changed); I(water_does_not_flow_down); I(creatures_backwards);
            I(creatures_direction_auto_change_on_start); I(gravity_switch_active); I(lineshift);
            I(border_scan_first_and_last); I(short_explosions); I(gravity_affects_all); I(pal_timing);
            I(player_x); I(player_y);
            printf("map=");
            for (int y = 0; y < r.h; y++)
                for (int x = 0; x < r.w; x++)
                    printf("%02x", code_of[r.map(x, y)]);
            printf("\n");
        }
        return 0;
    }
    if (!strcmp(argv[1], "play")) {
        int ticks = atoi(argv[4]);
        unsigned only = argc > 5 ? atoi(argv[5]) : 0;
        static const GdDirectionEnum dirs[] = {MV_STILL, MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT,
                                                MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_UP_RIGHT};
        for (unsigned n = 0; n < cs.caves.size(); n++) {
            if (only && n + 1 != only)
                continue;
            CaveRendered r(cs.caves[n], level, 0);
            r.setup_for_game();
            lcg = n + 1;
            printf("CAVE %u\n", n + 1);
            for (int t = 0; t < ticks; t++) {
                unsigned in = next_rand();
                GdDirectionEnum d = dirs[in % 10];
                bool fire = (in >> 4) % 8 == 0;
                r.iterate(d, fire, false);
                unsigned hash = 2166136261u;
                for (int y = 0; y < r.h; y++)
                    for (int x = 0; x < r.w; x++)
                        hash = (hash ^ code_of[r.map(x, y)]) * 16777619u;
                printf("%d %08x st=%d dia=%d time=%d score=%d speed=%d px=%d py=%d\n", t, hash,
                       (int)r.player_state, (int)r.diamonds_collected, (int)r.time, (int)r.score,
                       (int)r.speed, (int)r.player_x, (int)r.player_y);
                if (getenv("REFDUMP_STATE"))
                    printf("  amoeba=%d,%d,%d\n", (int)r.amoeba_state, (int)r.amoeba_time,
                           (int)r.amoeba_growth_prob);
                if (getenv("REFDUMP_MAP")) {
                    for (int y = 0; y < r.h; y++) {
                        for (int x = 0; x < r.w; x++)
                            printf("%02x", code_of[r.map(x, y)]);
                        printf("\n");
                    }
                }
            }
        }
    }
}
