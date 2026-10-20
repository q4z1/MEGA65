// Lotus Run: the renderer's assembly (src/render.s) against its
// references in C (src/ref/) - a MEGA65 program, run in Xemu by
// tests/check_render.sh.
//
// Every road line pattern is drawn out by both (road_rows.s, road_rows.c).
// Views of every course - positions along it, the camera to the sides, in
// two scales - are drawn by both, and made-up lists of sprites (any image
// of the first course's banks or of the opponents' colourings, partly off
// the picture, cut by their clip row); the pictures must be the same byte for byte, and so must what they
// note besides. The result is left in memory (check_views, check_failed,
// ...) and shown in the border: green when all is the same, red at the
// first difference; then Xemu exits (check.h).

#include <stdint.h>
#include <string.h>

#include "banks.h"
#include "disk.h"
#include "dma.h"
#include "check.h"
#include "hw.h"
#include "mem.h"
#include "render.h"
#include "road.h"
#include "road_draw.h"
#include "road_pixels.h"
#include "road_rows.h"
#include "roadpat.h"
#include "sprites.h"
#include "tracks.h"

// ref/road_draw.c and ref/sprites_draw.c, compiled with their functions
// renamed (check_render.sh)
void ref_road_draw(void);
void ref_sprites_draw(void);

// sprites.c's list (sprites_place is not part of this)
Sprite sprite_list[SPRITES_MAX];
uint8_t sprite_count;

static uint8_t track_buf[TRACK_SIZE];
static RoadStep steps[ROAD_STEPS];

volatile uint16_t check_rows;        // road line patterns compared
volatile uint32_t check_views;       // views compared
volatile uint32_t check_sprite_sets; // sprite lists compared
volatile uint8_t check_failed;       // 0, or what differed: 1 picture, 3 loading,
                                     // 4 sprites (course: the list, position: the scale),
                                     // 5 a road line pattern (course: the variant,
                                     // position: the width, lateral: the phase)
volatile uint8_t check_fail_course;
volatile uint32_t check_fail_pos;
volatile int16_t check_fail_lateral;
volatile uint16_t check_fail_offset; // the picture's first byte that differed
volatile uint8_t check_done;

// The reference's picture is kept here
#define SAVED (ATTIC + 0x100000ul)

static void fail(uint8_t what, uint8_t course, uint32_t pos, int16_t lateral, uint16_t offset) {
    check_failed = what;
    check_fail_course = course;
    check_fail_pos = pos;
    check_fail_lateral = lateral;
    check_fail_offset = offset;
    check_done = 1;
    check_exit(1);
}

static uint8_t a[256], b[256];

// The first byte of the picture that differs from the saved one, or $FFFF
static uint16_t compare_pictures(void) {
    for (uint16_t off = 0; off < 64000u; off += 256) {
        dma_copy(PICTURE + off, (uint16_t)a, 256);
        dma_copy(SAVED + off, (uint16_t)b, 256);
        dma_flush();
        if (memcmp(a, b, 256))
            for (uint16_t i = 0;; i++)
                if (a[i] != b[i])
                    return off + i;
    }
    return 0xFFFF;
}

static void clear_picture(void) {
    dma_fill(PICTURE, 0xEE, 64000u);
    dma_flush();
}


static void check_view(uint8_t course, uint32_t pos, int16_t lateral) {
    const Track *t = (const Track *)track_buf;
    int16_t top;
    uint8_t count = road_project(t, pos, steps, &top);
    road_lines(steps, count, render_lines);
    road_top = (uint8_t)top;
    road_lateral8 = (int16_t)(lateral * 8);
    road_phase = (uint16_t)(pos >> 4) & 0x7FF;

    clear_picture();
    ref_road_draw();
    dma_flush();
    dma_copy(PICTURE, SAVED, 64000u);
    dma_flush();

    clear_picture();
    road_draw();
    dma_flush();
    uint16_t off = compare_pictures();
    if (off != 0xFFFF)
        fail(1, course, pos, lateral, off);
    check_views++;
}

// Every road line pattern by road_row_draw against road_row, the shades
// as colours (drawn to SAVED, then read back)
static void check_patterns(void) {
    static uint8_t shades[ROAD_SHADES], got[ROAD_LEN_MAX];
    static RoadRow row;
    for (uint8_t s = 0; s < ROAD_SHADES; s++)
        shades[s] = s;
    rr_colours = rr_colours_b = shades;
    for (uint16_t w2 = 0; w2 < ROAD_WIDTHS; w2++)
        for (uint8_t v = 0; v < 2; v++)
            for (uint8_t p = 0; p < 4; p++) {
                rr_w2 = w2;
                rr_v = v;
                rr_p = p;
                rr_dst = SAVED;
                rr_dst_b = SAVED + 0x1000;
                road_row_draw();
                dma_flush();
                road_row(w2, v, p, &row);
                if (rr_start != row.start || rr_len != row.len || rr_dst != SAVED + row.len)
                    fail(5, v, w2, p, 0xFFFF);
                for (uint8_t set = 0; set < 2; set++) {
                    dma_copy(SAVED + (set ? 0x1000 : 0), (uint16_t)got, row.len);
                    dma_flush();
                    uint16_t off = 0;
                    for (uint8_t k = 0; k < row.n; k++)
                        for (uint16_t i = 0; i < row.run[k].len; i++, off++)
                            if (got[off] != row.run[k].shade)
                                fail(5, v, w2, p, off);
                }
                check_rows++;
            }
}

// Made-up sprites
static uint32_t seed = 4711;

static uint16_t rnd(void) {
    seed = seed * 1103515245ul + 12345;
    return (uint16_t)(seed >> 16);
}

static void check_sprites(uint8_t set) {
    static const uint8_t banks[] = {SPR_CARS, SPR_HUD, 0, 1, 2, 3, SPR_OPP, SPR_OPP + 2, SPR_OPP + 4};
    sprite_count = (uint8_t)(1 + rnd() % 24);
    for (uint8_t i = 0; i < sprite_count; i++) {
        Sprite *s = &sprite_list[i];
        s->bank = banks[rnd() % sizeof banks];
        s->image = (uint8_t)(rnd() % banks_pool[banks_dir[s->bank] - 1]);
        if (s->bank >= SPR_OPP)
            s->image = (uint8_t)(63 + s->image % 63);  // the opponents' images in another colouring
        s->x = (int16_t)(rnd() % 520) - 120;
        s->y = (int16_t)(rnd() % (view_lines + 60)) - 20;
        s->clip = (int16_t)(rnd() % view_lines);
    }
    clear_picture();
    ref_sprites_draw();
    dma_flush();
    dma_copy(PICTURE, SAVED, 64000u);
    dma_flush();
    clear_picture();
    sprites_draw();
    dma_flush();
    uint16_t off = compare_pictures();
    if (off != 0xFFFF)
        fail(4, set, view_lines, 0, off);
    check_sprite_sets++;
}

int main(void) {
    check_init();
    POKE(0xD020, 6);
    check_patterns();
    if (!disk_load("TRACK00", (uint16_t)track_buf) || !banks_load((const Track *)track_buf))
        fail(3, 0, 0, 0, 0);
    for (uint8_t scale = 0; scale < 2; scale++) {
        view_lines = scale ? 192 : 96;
        view_y0 = scale ? 4 : 0;
        for (uint8_t set = 0; set < 120; set++)
            check_sprites(set);
    }
    road_pixels_init();
    for (uint8_t course = 0; course < 32; course++) {
        char name[] = "TRACK00";
        name[5] = "0123456789ABCDEF"[course >> 4];
        name[6] = "0123456789ABCDEF"[course & 15];
        if (!disk_load(name, (uint16_t)track_buf))
            fail(3, course, 0, 0, 0);
        const Track *t = (const Track *)track_buf;
        // a 96-line view, and the full screen's
        for (uint8_t scale = 0; scale < 2; scale++) {
            view_scale = scale ? 512 : 256;
            view_lines = scale ? 192 : 96;
            view_y0 = scale ? 4 : 0;
            road_view();
            for (uint16_t s = course & 3; s < t->segments; s += 7) {
                uint32_t pos = (uint32_t)s << 16 | (uint16_t)(s * 0x2F1Bu);
                static const int16_t laterals[] = {0, -90, 140, -400, 600};
                check_view(course, pos, laterals[s % 5]);
            }
        }
    }
    check_done = 1;
    check_exit(0);
}
