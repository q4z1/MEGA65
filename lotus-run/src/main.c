// Lotus Run: a racing game for the MEGA65, after Lotus Esprit Turbo
// Challenge.
//
// The title, the level and the controls, then the season: before each
// race its course, after it the result and the championship, until the
// season is over or the player is out of it. The race on the whole screen,
// driven with the joystick in port 2 (or the cursor keys and space);
// Run/Stop gives up.

#include <stdint.h>

#include "banks.h"
#include "disk.h"
#include "dma.h"
#include "hw.h"
#include "input.h"
#include "mem.h"
#include "pages.h"
#include "panel.h"
#include "progdata.h"
#include "race.h"
#include "sprbanks.h"
#include "render.h"
#include "road_pixels.h"
#include "screens.h"
#include "season.h"
#include "sound.h"
#include "track.h"
#include "tracks.h"

_Static_assert(TRACK_SIZE <= TRACK_BUF_SIZE, "the largest course does not fit into TRACK_BUF");
#include "video.h"


// The player's car's paint (CAR_PAINT): green, light to dark; the
// opponents' (OPP_PAINT): white, blue, yellow, anthracite, orange, violet,
// each light and dark
static const uint16_t car_paint[3] = {0x4D1, 0x091, 0x040};
static const uint16_t opp_paint[2 * OPP_COLOURS] = {0xCCC, 0x666, 0x59E, 0x236, 0xED3, 0x870,
                                                    0x555, 0x222, 0xF94, 0x942, 0xB7D, 0x535};

// The race view's colours 1-7 (those of 12-15 change down the screen,
// render.c; 8-11 are the scenery's, per picture), the player's car's paint,
// the panel's 17-19, 25-27
static void view_colours(void) {
    for (uint8_t i = 0; i < 7; i++)
        video_colour(1 + i, tab_view_colours[i]);
    for (uint8_t i = 0; i < 3; i++)
        video_colour(CAR_PAINT + i, car_paint[i]);
    for (uint8_t i = 0; i < 2 * OPP_COLOURS; i++)
        video_colour(OPP_PAINT + i, opp_paint[i]);
    for (uint8_t i = 0; i < 3; i++) {
        video_colour(17 + i, tab_panel_colours[i]);
        video_colour(25 + i, tab_panel_colours[3 + i]);
    }
}

static void halt(uint8_t colour) {
    POKE(0xD020, colour);
    for (;;)
        ;
}

// The joystick (and keys) as the race's bits
static uint8_t joystick(void) {
    uint8_t in = input_read(), j = 0;
    if (in & IN_LEFT)
        j |= JOY_LEFT;
    if (in & IN_RIGHT)
        j |= JOY_RIGHT;
    if (in & IN_UP)
        j |= JOY_UP;
    if (in & IN_DOWN)
        j |= JOY_DOWN;
    if (in & IN_BUTTON)
        j |= JOY_FIRE;
    return j;
}

// The logic of every frame that has passed since the last call
static uint8_t frame_done;

static void catch_up(void) {
    while (frame_done != video_frame()) {
        sound_frame();  // as the original: before the logic, from the last frame
        race_joy[0] = joystick();
#ifdef LOTUS_AUTOTEST
        // the joystick held by a simple driver: fire, steering back to the
        // middle (screens.c goes on by itself)
        int16_t x = (int16_t)(race.p[0].x >> 16);
        race_joy[0] = (uint8_t)(JOY_FIRE | (x >= 0x20 ? JOY_LEFT : 0) | (x < -0x60 ? JOY_RIGHT : 0));
#endif
        race_frame();
        frame_done++;
    }
}

// The pages' code (the MENU overlay, mem.h) where it runs: before any of
// it is called, again after every race
static void menu_in(void) {
    dma_copy(MENU_ATTIC, MENU_AT, MENU_SIZE);
    dma_flush();
}

// Course n from the disk to TRACK_ATTIC, for its page
static bool load_course(uint8_t n) {
    char name[] = "TRACK00";
    name[5] = "0123456789ABCDEF"[n >> 4];
    name[6] = "0123456789ABCDEF"[n & 15];
    return disk_load(name, TRACK_ATTIC);
}

// The course to TRACK_BUF, in place of the pages' code, and what the race
// needs of it; false if something cannot be loaded
static bool course_in(void) {
    const Track *t = (const Track *)TRACK_BUF;
    dma_copy(TRACK_ATTIC, (uint16_t)TRACK_BUF, TRACK_SIZE);
    dma_flush();
    return banks_load(t) && backdrop_load(t->header[1]);
}

// The race on course n until it is over; false if the player gave up
// (Run/Stop)
static bool race_run(uint8_t n, const Controls *c) {
    Track *t = (Track *)TRACK_BUF;
    pages_off();
    view_colours();
    render_palette(t);
    race_track = t;
    race.course = n;
    race.race_no = season.race;
    race.difficulty = season.level;
    race.segments = t->segments;
    race.p[0].automatic = c->automatic;
    race.p[0].fire_accel = c->fire_accel;
    race_init();
    panel_reset();
    sound_race_start();

    view_scale = 512;
    view_lines = 192;
    view_y0 = 4;
    road_view();
    frame_done = video_frame();
    uint8_t last_picture = frame_done;
    while (race.over_timer != 150) {
        if (input_read() & IN_RESTART) {
            sound_off();
            return false;
        }
        // a picture every second frame at most
        do
            catch_up();
        while ((uint8_t)(frame_done - last_picture) < 2);
        last_picture = frame_done;
        race_picture();
        panel_picture();
        const Player *p = &race.p[0];
        View v = {t, p->pos_view, (int16_t)(p->x_view >> 16), p->slope_view, (uint16_t)p->u16_view};
        render_view(&v);
        panel_draw();
        video_show();
        for (uint8_t i = 0; i < 4; i++)
            video_colour(8 + i, p->colours[i]);
    }
    sound_off();
    return true;
}

int main(void) {
    video_init();
    if (!disk_load("MENU", MENU_ATTIC))
        halt(7);
    menu_in();
    if (!panel_load() || !lapbar_load() || !pages_load() || !season_load() || !sound_load())
        halt(7);
    pages_on();
    if (!page_show("PTITLE"))
        halt(8);
    // the road's lines drawn out while the title is shown
    road_pixels_init();
    race.random[0] = 0x12345678;
    Controls controls = {true, true};
    uint8_t level = 0;
    for (;;) {
        screen_wait_fire();
        level = screen_level(level);
        screen_controls(&controls);
        season_start(level);
        bool out = false, gave_up = false;
        do {
            uint8_t n = season_course();
            pages_on();  // dark while the course comes in
            if (!load_course(n))
                halt(2);
            screen_course(n);
            pages_on();
            if (!course_in())
                halt(2);
            bool done = race_run(n, &controls);
            menu_in();
            if (!done) {
                gave_up = true;
                break;
            }
            pages_on();
#ifdef LOTUS_AUTOTEST
            race.p[0].place = 1;  // the simple driver is no racer: on to the next race
#endif
            season_classify();
            screen_result();
            if (season.place >= SCORING) {
                out = true;
                break;
            }
            // the championship from the second race on
            if (season.race)
                screen_standing();
        } while (season_next());
        if (!gave_up)
            screen_season_over(out);
        else
            pages_on();
        page_show("PTITLE");
    }
}
