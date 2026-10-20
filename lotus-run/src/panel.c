// Lotus Run: the panel (see panel.h).
//
// The values, in turn, one per picture: speed, rpm, gear, fuel, speed, rpm,
// place, the lap. Each field shows one of its pictures (tools/mksprites.py);
// a new one is copied into the panel as shown. The lap is the bar at the
// top left (overlay 23, which sprites.c places).

#include "panel.h"

#include "banks.h"
#include "fb.h"
#include "progdata.h"
#include "race.h"
#include "road.h"

// The fields, as tools/mksprites.py has them
enum { F_HUNDREDS, F_TENS, F_UNITS, F_GEAR, F_RPM, F_FUEL, F_PLACE };

// Where the panel is: its left column and first row in the view; columns
// from 320 on are not shown
#define PANEL_X 277
#define PANEL_Y 2

static uint8_t shown[PANEL_FIELDS];
uint8_t panel_turn;

static void set(uint8_t f, uint8_t state) {
    const PanelField *p = &panel_fields[f];
    if (shown[f] == state || state >= p->states)
        return;
    shown[f] = state;
    uint32_t src = p->pixels + (uint32_t)state * p->w * p->h;
    uint32_t dst = panel_live() + (uint16_t)(p->y * PANEL_W + p->x);
    for (uint8_t r = 0; r < p->h; r++, src += p->w, dst += PANEL_W)
        attic_copy(src, dst, p->w);
}

static void speed(void) {
    uint16_t mph = (uint16_t)(((uint32_t)race.p[0].speed_view * 0x640) >> 16);
    set(F_UNITS, (uint8_t)(mph % 10));
    mph /= 10;
    set(F_TENS, (uint8_t)(mph % 10));
    set(F_HUNDREDS, (uint8_t)(mph / 10));
}

// The rpm bar: speed / the gear's ratio, 0-36
static void rpm(void) {
    const Player *p = &race.p[0];
    uint32_t q = ((uint32_t)p->speed_view << 16) / tab_gear_ratio[p->gear];
    if (q > 0xFFFF)
        q = 0;  // the division overflows: what is left is 0
    q = q * 0x1C / 0x1964;
    set(F_RPM, (uint8_t)(q < 0x24 ? q : 0x24));
}

// The fuel bar, 0-36; below 8 it blinks
static void fuel(void) {
    uint16_t f = (uint16_t)(((race.p[0].fuel >> 16) * 0x25) >> 16);
    if (f < 8 && (race.clock & 16))
        f = 0;
    set(F_FUEL, (uint8_t)f);
}

// ---------------------------------------------------------------- the lap bar

// Overlay 23 at the top left: a box per lap, the box of the lap being
// driven filled as far as the car has come round (16 steps)
static void lap_box(uint8_t box, uint8_t step) {
    uint32_t src = lapbar_pixels() + (uint32_t)LAPBAR_W * LAPBAR_H * LAPBAR_LAPS + 16u * step;
    uint32_t dst = sprite_pixels(SPR_HUD, 23) + 16u * box;
    attic_copy(src, dst + 2 * LAPBAR_W, 16);
    attic_copy(src, dst + 3 * LAPBAR_W, 16);
}

// The lap the car is on (from 1; 0 before the start line), and how far
// round: on the last lap the message of its timer comes up once
static void lap(void) {
    Player *p = &race.p[0];
    uint16_t seg = (uint16_t)(p->pos >> 16);
    uint16_t done = seg / race.segments, rest = seg % race.segments;
    if (done == race.laps && (int16_t)p->timer < 0)
        p->timer = (uint16_t)(0x60 + (~race.clock & 0x1F));
    if (done > race.laps) {
        done = race.laps;
        rest = race.segments - 1;
    }
    if (!done)
        return;
    uint16_t frac = (uint16_t)(((uint32_t)rest << 16) / race.segments);
    lap_box((uint8_t)(done - 1), (uint8_t)(frac >> 12));
}

// ----------------------------------------------------------------

void panel_reset(void) {
    uint8_t laps = race.laps < 1 ? 1 : race.laps > LAPBAR_LAPS ? LAPBAR_LAPS : (uint8_t)race.laps;
    attic_copy(lapbar_pixels() + (uint32_t)LAPBAR_W * LAPBAR_H * (laps - 1), sprite_pixels(SPR_HUD, 23),
               LAPBAR_W * LAPBAR_H);
    for (uint8_t r = 0; r < PANEL_H; r++)
        attic_copy(panel_base() + r * PANEL_W, panel_live() + r * PANEL_W, PANEL_W);
    for (uint8_t f = 0; f < PANEL_FIELDS; f++)
        shown[f] = 0xFF;
    speed();
    rpm();
    set(F_GEAR, (uint8_t)race.p[0].gear);
    fuel();
    set(F_PLACE, (uint8_t)(race.p[0].place - 1));
}

void panel_picture(void) {
    switch (++panel_turn & 7) {
    case 0:
    case 4:
        speed();
        break;
    case 1:
    case 5:
        rpm();
        break;
    case 2:
        set(F_GEAR, (uint8_t)race.p[0].gear);
        break;
    case 3:
        fuel();
        break;
    case 6:
        set(F_PLACE, (uint8_t)(race.p[0].place - 1));
        break;
    default:
        lap();
        break;
    }
}

void panel_draw(void) {
    uint32_t src = panel_live();
    for (uint8_t r = 0; r < PANEL_H; r++, src += PANEL_W)
        fb_sprite_row((uint8_t)(view_y0 + PANEL_Y + r), PANEL_X, src, FB_W - PANEL_X);
}
