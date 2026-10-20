// Lotus Run: a racing game for the MEGA65, after Lotus Esprit Turbo
// Challenge.
//
// For now: the first race of the season on the whole screen, the road, the
// scenery and the cars, driven with the joystick in port 2 (or the cursor
// keys and space).

#include <stdint.h>

#include "banks.h"
#include "disk.h"
#include "hw.h"
#include "input.h"
#include "mem.h"
#include "pages.h"
#include "panel.h"
#include "progdata.h"
#include "race.h"
#include "render.h"
#include "road_pixels.h"
#include "track.h"
#include "tracks.h"

_Static_assert(TRACK_SIZE <= TRACK_BUF_SIZE, "the largest course does not fit into TRACK_BUF");
#include "video.h"


// The race view's colours 1-7 (those of 12-15 change down the screen,
// render.c; 8-11 are the scenery's, per picture), the panel's 17-19, 25-27
static void view_colours(void) {
    for (uint8_t i = 0; i < 7; i++)
        video_colour(1 + i, tab_view_colours[i]);
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
        race_joy[0] = joystick();
        race_frame();
        frame_done++;
    }
}

int main(void) {
    video_init();
    race.course = 0;
    char name[] = "TRACK00";
    name[5] = "0123456789ABCDEF"[race.course >> 4];
    name[6] = "0123456789ABCDEF"[race.course & 15];
    if (!disk_load(name, (uint16_t)TRACK_BUF) || !disk_load("ROADPAT", ROADPAT))
        halt(2);
    road_pixels_init();
    Track *t = (Track *)TRACK_BUF;
    if (!banks_load(t) || !backdrop_load(t->header[1]) || !panel_load() || !lapbar_load() ||
        !pages_load())
        halt(7);

    // the title until fire, or 8 seconds
    pages_on();
    if (!page_show("PTITLE"))
        halt(8);
    uint8_t f = video_frame();
    for (uint16_t frames = 0; frames < 400 && !(joystick() & JOY_FIRE);)
        if (video_frame() != f) {
            f = video_frame();
            frames++;
        }
    pages_off();
    view_colours();
    race_track = t;
    race.segments = t->segments;
    race.random[0] = 0x12345678;
    race_init();
    panel_reset();

    view_scale = 512;
    view_lines = 192;
    view_y0 = 4;
    road_view();
    frame_done = video_frame();
    uint8_t last_picture = frame_done;
    for (;;) {
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
}
