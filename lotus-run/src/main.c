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
#include "progdata.h"
#include "race.h"
#include "render.h"
#include "road_pixels.h"
#include "track.h"
#include "tracks.h"
#include "video.h"

// The course from the disk (tools/mkdata.py: TRACKnn)
static uint8_t track_buf[TRACK_SIZE];

// The race view's colours 1-7 (those of 12-15 change down the screen,
// render.c; 8-11 are the scenery's, per picture)
static void view_colours(void) {
    for (uint8_t i = 0; i < 7; i++)
        video_colour(1 + i, tab_view_colours[i]);
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
    if (!disk_load(name, (uint16_t)track_buf) || !disk_load("ROADPAT", ROADPAT))
        halt(2);
    road_pixels_init();
    Track *t = (Track *)track_buf;
    if (!banks_load(t))
        halt(7);
    view_colours();
    race_track = t;
    race.segments = t->segments;
    race.random[0] = 0x12345678;
    race_init();

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
        const Player *p = &race.p[0];
        View v = {t, p->pos_view, (int16_t)(p->x_view >> 16)};
        render_view(&v);
        video_show();
        for (uint8_t i = 0; i < 4; i++)
            video_colour(8 + i, p->colours[i]);
    }
}
