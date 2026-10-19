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
// Built with -DSCREENCAST (toolchain/tools/bin/mega65-cast), the game plays
// itself: the title runs for a while, then the caves play the moves that
// tools/solve.c found for them (DEMO01, DEMO02, ... on the disk, loaded with
// each cave), and after the last one the emulator is told to stop, which
// ends the recording.

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "disk.h"
#include "engine.h"
#include "gfx.h"
#include "hiscore.h"
#include "hw.h"
#include "input.h"
#include "levels.h"
#include "music.h"
#include "sound.h"
#include "video.h"

#ifdef SCREENCAST
#include "demo.h"
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

// What moved in the last tick slides from its old cell into the new one
// until the next tick: the rules stay in cells, only the drawing is smooth.
#define MAX_SPRITES 64              // more are drawn in their cells
static Sprite sprites[MAX_SPRITES];
static uint8_t nsprites;

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
static uint8_t start_cave, start_level;  // picked on the title
static uint32_t score;              // before the current cave
static uint32_t next_life;
static bool have_logo;              // the logo file was on the disk

// The cave being played, as loaded from the disk (CAVE01, CAVE02, ...;
// the layout is described in tools/mkcave.py)
static struct {
    uint16_t time;
    uint8_t diamonds, value, extra, amoeba, magic, speed;
    char name[24];
    uint8_t map[CAVE_SIZE];
} cave_file;
static CaveDef cave_def;
static uint8_t loaded = 0xFF, loaded_level;  // cave_no and level of cave_file
#ifdef SCREENCAST
static uint8_t demo_moves[DEMO_MAX];  // the cave's moves (DEMOnn, see tools/solve.c)
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
    nsprites = 0;
    for (uint8_t y = y0; y <= y1; y++) {
        uint16_t i = y * CAVE_W + x0;
        for (uint8_t x = x0; x <= x1; x++, i++) {
            if (any_covered && covered[i]) {
                tiles[i] = cover;
                continue;
            }
            uint8_t t = etile[cave[i]];
            if (slide && moved[i] != DIR_NONE && nsprites < MAX_SPRITES) {
                Sprite *s = &sprites[nsprites++];
                cell_pos(i, &s->x, &s->y);
                s->tile = t;
                t = T_SPACE;
            }
            tiles[i] = t;
        }
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
    uint16_t px, py;
    cell_pos(game.player, &px, &py);
    px += 8;
    py += 8;
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

// not inlined: it is called from many places, and memory is short
__attribute__((noinline)) static void put_num(uint8_t col, uint32_t v, uint8_t digits) {
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

// "CAVE 12/3": cave and level, as the original's "A/1"
static void status_intro(void) {
    status_clear();
    status_put(2, ICON(ICON_LIFE));
    put_num(4, lives, 1);
    status_print(7, "CAVE");
    uint8_t col = cave_no >= 9 ? 14 : 13;
    put_num(12, cave_no + 1, col - 12);
    status_put(col, '/');
    put_num(col + 1, level + 1, 1);
    status_print(col + 3, game.def->name);
}

// ---------------------------------------------------------------- frames

static void next_frame(void) {
    video_sync();
    update_tiles();
    video_render(tiles, cam_x, cam_y, sprites, nsprites);
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
    status_clear();
    status_print(5, what);
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

// Cave n of the level from the disk (CAVEnn-l), unless it is there already
static bool load_cave(uint8_t n) {
    if (n == loaded && level == loaded_level)
        return true;
    static char file[] = "CAVE00-0";
    static char what[] = "LOADING CAVE 00/0";
    uint8_t tens = (n + 1) / 10, ones = (n + 1) % 10;
    file[4] = '0' + tens;
    file[5] = '0' + ones;
    file[7] = '1' + level;
    char *num = what + 13;
    if (tens)
        *num++ = '0' + tens;
    *num++ = '0' + ones;
    *num++ = '/';
    *num++ = '1' + level;
    *num = 0;
    loaded = 0xFF;
    if (!load(what, file, 0, (uint16_t)&cave_file))
        return false;
#ifdef SCREENCAST
    static char demo_file[] = "DEMO00";
    demo_file[4] = file[4];
    demo_file[5] = file[5];
    if (!disk_load(demo_file, 0, (uint16_t)demo_moves))
        demo_moves[0] = 0;
#endif
    loaded = n;
    loaded_level = level;
    cave_def.name = cave_file.name;
    cave_def.map = cave_file.map;
    cave_def.time = cave_file.time;
    cave_def.diamonds_needed = cave_file.diamonds;
    cave_def.diamond_value = cave_file.value;
    cave_def.extra_value = cave_file.extra;
    cave_def.amoeba_time = cave_file.amoeba;
    cave_def.magic_time = cave_file.magic;
    cave_def.tick_ms = cave_file.speed;
    return true;
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

// One line of text under the logo, centred over the full width
static void title_line(const char *text) {
    static char line[39];
    uint8_t n = strlen(text);
    memset(line, ' ', 38);
    memcpy(line + (38 - n) / 2, text, n);
    line[38] = 0;
    video_text(1, 152, line);
}

// The status line on the title: what the game starts with, and the hi-score
static void title_status(void) {
    status_clear();
    status_print(2, "LEVEL");
    put_num(8, start_level + 1, 1);
    status_print(11, "CAVE");
    status_put(16, ' ');
    put_num(start_cave >= 9 ? 16 : 17, start_cave + 1, start_cave >= 9 ? 2 : 1);
    status_print(22, "HI-SCORE");
    put_num(31, hs_table[0].score, 6);
}

// Up and down pick the level, left and right the cave to start with
static void title_pick(void) {
    uint8_t l = start_level, c = start_cave;
    if ((pressed & IN_UP) && l < LEVELS - 1)
        l++;
    if ((pressed & IN_DOWN) && l)
        l--;
    if ((pressed & IN_RIGHT) && c + START_STEP < CAVE_COUNT)
        c += START_STEP;
    if ((pressed & IN_LEFT) && c)
        c -= START_STEP;
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
    video_text_in(HS_COL, HS_Y0 + i * 16, line, i == hs_new ? title_row : place_colours(i));
}

static void scores_page(void) {
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
        video_text(CENTRE(26), 156, "P PAUSE   RUN/STOP GIVE UP");
    }
}

static void logo_frame(uint16_t pf) {
    static const char press[] = "PRESS FIRE TO START";
    static const char blank[] = "                   ";
    if (have_logo) {
        // the line under the logo: "press fire", blinking, and in
        // between the controls
        if ((pf & 31) == 0) {
            switch ((pf >> 7) % 6) {
            case 1:
                title_line("JOYSTICK, GAMEPAD OR CURSOR KEYS");
                break;
            case 3:
                title_line("UP/DOWN: LEVEL   LEFT/RIGHT: CAVE");
                break;
            case 5:
                title_line("P PAUSE   RUN/STOP GIVE UP");
                break;
            default:
                title_line((pf & 32) ? "" : press);
            }
        }
    } else {
        if ((pf & 31) == 0)
            video_text(CENTRE(19), 112, (pf & 32) ? blank : press);
        if (pf % 3 == 0)
            video_shine(pf / 3);
    }
}

// The logo and the high score table take turns, like an arcade machine
// waiting for a player; after a game the table comes first.
static void title_screen(bool scores) {
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
    uint16_t pf = 0;  // frames on this page
    for (;;) {
        if (scores)
            scores_frame(pf);
        else
            logo_frame(pf);
        title_frame();
        title_pick();
        if (armed && (pressed & IN_BUTTON))
            break;
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
    video_palette(0);
    sound_init();
}

// ---------------------------------------------------------------- caves

enum { END_DIED, END_EXITED };

static uint8_t play_cave(void) {
    const CaveDef *d = &cave_def;
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
#ifdef SCREENCAST
            in = demo_next();
#endif
            latched = DIR_NONE;
            fire_latched = false;
            cave_tick(in);
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
    // The tiles from the disk - without the spinner, which is made of
    // them -, the title logo and the high scores (video.h)
    disk_load("SMARAGD.TILES", GFX_BANK, TILES_OFF);
    have_logo = load("LOADING", "SMARAGD.LOGO", GFX_BANK, LOGO_OFF);
    hiscore_load();

    for (bool after_game = false;; after_game = true) {
        title_screen(after_game);
        lives = LIVES;
        score = 0;
        next_life = LIFE_POINTS;
        cave_no = start_cave;
        level = start_level;
        bool have_cave = true;
        while (lives) {
#ifdef SCREENCAST
            // after the last cave with moves
            if (cave_no >= DEMO_CAVES)
                demo_end();
#endif
            if (!(have_cave = next_cave()))
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
        status_center(have_cave ? "GAME OVER" : "NO CAVES ON THE DISK");
        sound_off();
        wait_button(250);
        uint8_t rank = have_cave ? hiscore_rank(score) : HS_COUNT;
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
}
