// Emerald Dash: a Boulder Dash style game for the MEGA65.
//
// main.c runs the game: the title screen with its music, then the caves:
// a cave is uncovered, Rockford hatches, and the cave runs in ticks of the
// cave's speed while the screen is redrawn every frame (50 Hz PAL, 60 Hz
// NTSC). The rules are in engine.c, the display in video.c.

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "caves.h"
#include "engine.h"
#include "gfx.h"
#include "hw.h"
#include "input.h"
#include "music.h"
#include "sound.h"
#include "video.h"

#define LIVES       3
#define LIFE_POINTS 500   // an extra life every so many points
#define MAX_X       (CAVE_W * 16 - VIEW_W)
#define MAX_Y       (CAVE_H * 16 - VIEW_H)

#define ICON(n) (0x80 + (n))

static uint8_t tiles[CAVE_SIZE];    // tile per cell, for video_render
static uint8_t covered[CAVE_SIZE];  // 1: cell still hidden (start and end)
static bool any_covered;
static uint8_t etile[E_COUNT];      // tile per element, animated

static bool pal;
static uint8_t frame;
static uint8_t held, pressed;       // IN_* now, and newly pressed this frame
static uint16_t cam_x, cam_y;
static bool scroll_x, scroll_y;
static uint8_t idle;                // Rockford's idle animation
static uint8_t flash;               // frames left of the exit flash

static uint8_t lives;
static uint8_t cave_no;
static uint32_t score;              // before the current cave
static uint32_t next_life;
static uint32_t hiscore;

// ---------------------------------------------------------------- drawing

static void init_tiles(void) {
    etile[E_SPACE] = T_SPACE;
    etile[E_DIRT] = T_DIRT;
    etile[E_BRICK] = T_BRICK;
    etile[E_STEEL] = T_STEEL;
    etile[E_BOULDER] = etile[E_BOULDER_F] = T_BOULDER;
    etile[E_OUTBOX] = T_STEEL;  // the closed exit looks like steel
    for (uint8_t i = 0; i < 5; i++)
        etile[E_EXPLODE + i] = etile[E_EXPLODE_D + i] = T_EXPLODE0 + i;
    for (uint8_t i = 0; i < 3; i++)
        etile[E_BIRTH + i] = T_BIRTH0 + i;
}

static uint8_t rockford_tile(void) {
    if (game.moving)
        return (game.facing == DIR_LEFT ? T_RF_LEFT0 : T_RF_RIGHT0) + ((frame >> 2) & 3);
    // Standing still: now and then blink or tap a foot
    if ((frame & 15) == 0) {
        uint8_t r = rnd();
        idle = r < 48 ? 1 : r < 80 ? 2 : 0;
    }
    if (idle == 1 && (frame & 15) < 4)
        return T_RF_BLINK;
    if (idle == 2 && (frame & 4))
        return T_RF_TAP;
    return T_RF_STAND;
}

static void update_tiles(void) {
    uint8_t f = frame;
    etile[E_DIAMOND] = etile[E_DIAMOND_F] = T_DIAMOND0 + ((f >> 2) & 7);
    etile[E_INBOX] = (f & 8) ? T_INBOX1 : T_INBOX0;
    etile[E_OUTBOX_OPEN] = (f & 8) ? T_OUTBOX1 : T_OUTBOX0;
    etile[E_MAGIC] = game.magic_state == MW_ACTIVE ? T_MAGIC0 + ((f >> 2) & 3) : T_BRICK;
    etile[E_AMOEBA] = T_AMOEBA0 + ((f >> 3) & 3);
    for (uint8_t d = 0; d < 4; d++) {
        etile[E_FIREFLY + d] = T_FIREFLY0 + ((f >> 1) & 3);
        etile[E_BUTTERFLY + d] = T_BUTTERFLY0 + ((f >> 2) & 3);
    }
    etile[E_ROCKFORD] = rockford_tile();

    // only the cells in view
    uint8_t x0 = cam_x >> 4, y0 = cam_y >> 4;
    uint8_t x1 = x0 + VIEW_W / 16 + 1, y1 = y0 + VIEW_H / 16 + 1;
    if (x0)
        x0--;
    if (x1 >= CAVE_W)
        x1 = CAVE_W - 1;
    if (y1 >= CAVE_H)
        y1 = CAVE_H - 1;
    uint8_t cover = T_COVER0 + ((f >> 1) & 1);
    for (uint8_t y = y0; y <= y1; y++) {
        uint16_t i = y * CAVE_W + x0;
        for (uint8_t x = x0; x <= x1; x++, i++)
            tiles[i] = (any_covered && covered[i]) ? cover : etile[cave[i]];
    }
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

static void camera(bool jump) {
    uint16_t px = (game.player % CAVE_W) * 16 + 8;
    uint16_t py = (game.player / CAVE_W) * 16 + 8;
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

// ---------------------------------------------------------------- status

static void put_num(uint8_t col, uint32_t v, uint8_t digits) {
    col += digits;
    while (digits--) {
        status_put(--col, '0' + v % 10);
        v /= 10;
    }
}

static void status_clear(void) {
    for (uint8_t c = 1; c < 39; c++)
        status_put(c, ' ');
}

static void status_center(const char *text) {
    status_clear();
    status_print((40 - strlen(text)) / 2, text);
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
    if (status_code_at(2) != ICON(ICON_EMERALD)) {
        status_clear();
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
}

static void status_intro(void) {
    status_clear();
    status_put(2, ICON(ICON_LIFE));
    put_num(4, lives, 1);
    status_print(7, "CAVE");
    put_num(12, cave_no + 1, 1);
    status_print(15, game.def->name);
}

// ---------------------------------------------------------------- frames

static void next_frame(void) {
    video_sync();
    update_tiles();
    video_render(tiles, cam_x, cam_y);
    video_show();
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

// ---------------------------------------------------------------- title

static void title_frame(void) {
    video_sync();
    video_show();
    music_frame();
    frame++;
    uint8_t in = input_read();
    pressed = in & ~held;
    held = in;
}

// Centre a text of n characters (big: 2 columns each) in columns 1-38
#define CENTRE(n) (1 + (38 - (n)) / 2)

static void title_screen(void) {
    static const char press[] = "PRESS FIRE TO START";
    static const char blank[] = "                   ";
    video_clear();
    video_big_text(CENTRE(14), 8, "EMERALD");
    video_big_text(CENTRE(8), 44, "DASH");
    video_text(CENTRE(26), 88, "DIG  -  COLLECT  -  ESCAPE");
    video_text(CENTRE(32), 136, "JOYSTICK, GAMEPAD OR CURSOR KEYS");
    video_text(CENTRE(26), 156, "P PAUSE   RUN/STOP GIVE UP");
    status_clear();
    status_put(2, ICON(ICON_EMERALD));
    status_print(12, "HI-SCORE");
    put_num(21, hiscore, 6);
    status_put(37, ICON(ICON_EMERALD));
    sound_off();
    music_start();
    // The button counts only after it was let go once (Return from the
    // emulator's RUN, or fire still held from the last game)
    bool armed = false;
    for (uint16_t f = 0;; f++) {
        if ((f & 31) == 0)
            video_text(CENTRE(19), 112, (f & 32) ? blank : press);
        if (f % 3 == 0)
            video_shine(f / 3);
        title_frame();
        if (armed && (pressed & IN_BUTTON))
            break;
        if (!(held & IN_BUTTON))
            armed = true;
    }
    music_stop();
    video_shine(0);
    sound_init();
}

// ---------------------------------------------------------------- caves

enum { END_DIED, END_EXITED };

static uint8_t play_cave(void) {
    const CaveDef *d = &caves[cave_no];
    const uint16_t tick_len = d->tick_ms * 3;  // in 1/3 ms
    const uint8_t frame_len = pal ? 60 : 50;
    const uint8_t fps = pal ? 50 : 60;
    uint16_t tick_acc = 0;
    uint8_t sec = 0;
    uint8_t latched = DIR_NONE;
    bool fire_latched = false;
    bool paused = false;
    uint8_t after = 0;  // frames since Rockford died

    cave_start(d);
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
            continue;
        }
        if ((pressed & IN_RESTART) && game.state == PS_ALIVE)
            cave_suicide();

        // A direction or the button pressed only briefly between two ticks
        // still counts in the next tick.
        uint8_t dir = joy_dir(held);
        if (dir != DIR_NONE)
            latched = dir;
        if (held & IN_BUTTON)
            fire_latched = true;

        tick_acc += frame_len;
        if (tick_acc >= tick_len && game.state != PS_TIMEOUT && game.state != PS_EXITED) {
            tick_acc -= tick_len;
            uint8_t in = dir != DIR_NONE ? dir : latched;
            if (fire_latched)
                in |= IN_FIRE;
            latched = DIR_NONE;
            fire_latched = false;
            cave_tick(in);
            sound_tick(game.sound);
            if (game.flash) {
                game.flash = false;
                flash = 2;
                video_flash(true);
                sound_exit();
            }
        }
        if (game.state == PS_ALIVE && ++sec >= fps) {
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
            status_game();
            camera(false);
            break;
        case PS_DEAD:
            status_game();
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
            // the time left is counted into the score
            if (game.time) {
                game.time--;
                game.score++;
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
    pal = !(PEEK(0xD06F) & 0x80);

    video_init();
    sound_init();
    init_tiles();

    for (;;) {
        title_screen();
        lives = LIVES;
        score = 0;
        next_life = LIFE_POINTS;
        cave_no = 0;
        while (lives) {
            uint8_t end = play_cave();
            score += game.score;
            if (end == END_EXITED)
                cave_no = (cave_no + 1) % CAVE_COUNT;
            else
                lives--;
        }
        if (score > hiscore)
            hiscore = score;
        status_center("GAME OVER");
        sound_off();
        wait_button(250);
    }
}
