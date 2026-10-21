// Lotus Run: the pages between the races (see screens.h). Their fixed
// parts come from tools/mkpages.py; the rows given here are where its
// labels are.

#include "screens.h"

#include "dma.h"
#include "input.h"
#include "mem.h"
#include "music.h"
#include "pages.h"
#include "progdata.h"
#include "season.h"
#include "songs.h"
#include "texts.h"
#include "video.h"

// ---------------------------------------------------------------- input

#ifdef LOTUS_AUTOTEST
static const uint8_t *auto_keys;  // what the test presses next (0: fire)
#define KEY_NONE 0xFF             // in auto_keys: nothing this time
#endif

// After the next frame: the presses new since the last (bits not set the
// frame before); built with LOTUS_AUTOTEST, a press every second on its own
// (auto_keys, else fire)
MENU static uint8_t key_poll(void) {
    static uint8_t last = 0xFF;
    uint8_t f = video_frame();
    while (video_frame() == f)
        ;
#ifdef LOTUS_AUTOTEST
    static uint8_t frames;
    if (++frames < 50)
        return 0;
    frames = 0;
    if (auto_keys && *auto_keys) {
        uint8_t k = *auto_keys++;
        return k == KEY_NONE ? 0 : k;
    }
    return IN_BUTTON;
#endif
    uint8_t in = input_read();
    uint8_t pressed = in & (uint8_t)~last;
    last = in;
    return pressed;
}

// The next new press
MENU static uint8_t key(void) {
    uint8_t k;
    while (!(k = key_poll()))
        ;
    return k;
}

MENU void screen_wait_fire(void) {
    while (!(key() & IN_BUTTON))
        ;
}

// The title (shown already) until fire: its car's headlights go up and down
// (the page's animation) - a frame every TITLE_STEP frames, held at either
// end
#define TITLE_STEP 3
void screen_title(void) {
#ifdef LOTUS_AUTOTEST
    static const uint8_t keys[] = {KEY_NONE, KEY_NONE, KEY_NONE, KEY_NONE, IN_BUTTON, 0};
    auto_keys = keys;
#endif
    uint8_t last = (uint8_t)(page_frames() - 1), f = 0, wait = 50;
    int8_t step = 1;
    for (;;) {
        if (key_poll() & IN_BUTTON)
            return;
        if (last == 0xFF || --wait)
            continue;
        f = (uint8_t)(f + step);
        page_frame(f);
        wait = TITLE_STEP;
        if (f == last) {
            step = -1;
            wait = 150;
        } else if (f == 0) {
            step = 1;
            wait = 100;
        }
    }
}

// ---------------------------------------------------------------- text

static char line[PAGE_COLS + 1];

// s at col, row, padded with spaces to width
MENU static void put(uint8_t col, uint8_t row, const char *s, uint8_t width, uint8_t colour) {
    uint8_t n = 0;
    for (; *s && n < width; n++)
        line[n] = *s++;
    for (; n < width; n++)
        line[n] = ' ';
    line[n] = 0;
    page_text(col, row, line, colour);
}

// A number into buf, at least `digits` digits; returns the end
MENU static char *number(char *buf, uint16_t n, uint8_t digits) {
    char d[5];
    uint8_t k = 0;
    do {
        d[k++] = (char)('0' + n % 10);
        n /= 10;
    } while (n || k < digits);
    while (k)
        *buf++ = d[--k];
    *buf = 0;
    return buf;
}

// A time in frames (1/50 s) as M:SS.T
MENU static void time_text(char *buf, uint16_t frames) {
    uint16_t tenths = frames / 5;
    buf = number(buf, tenths / 600, 1);
    *buf++ = ':';
    buf = number(buf, (tenths % 600) / 10, 2);
    *buf++ = '.';
    number(buf, tenths % 10, 1);
}

// A place (0: first) as 1ST, 2ND, ...
MENU static void place_text(char *buf, uint8_t place) {
    static const char suffix[] = "STNDRDTH";
    uint8_t n = (uint8_t)(place + 1), s = n % 10 < 4 && (n < 10 || n > 20) && n % 10 ? n % 10 - 1 : 3;
    buf = number(buf, n, 1);
    buf[0] = suffix[2 * s];
    buf[1] = suffix[2 * s + 1];
    buf[2] = 0;
}

// ---------------------------------------------------------------- choosing

// The marker before row `rows[i]`, at col
MENU static void marks(const uint8_t *rows, uint8_t n, uint8_t at, uint8_t col) {
    for (uint8_t i = 0; i < n; i++)
        page_text(col, rows[i], i == at ? ">" : " ", TEXT_AMBER);
}

MENU uint8_t screen_level(uint8_t level) {
    static const uint8_t rows[LEVELS] = {12, 18, 24};
    page_show("PLEVEL");
    for (;;) {
        marks(rows, LEVELS, level, 2);
        uint8_t k = key();
        if (k & IN_BUTTON)
            return level;
        if ((k & IN_UP) && level)
            level--;
        if ((k & IN_DOWN) && level < LEVELS - 1)
            level++;
    }
}

// What the controls do in the race, as text rows
MENU static void controls_help(const Controls *c) {
    static const char *const help[4][3] = {
        {"FIRE + FORWARD: GEAR UP", "FIRE + BACK: GEAR DOWN", "FORWARD: GAS  BACK: BRAKE"},
        {"FORWARD: GEAR UP", "BACK: BRAKE, GEAR DOWN", "FIRE: GAS"},
        {"FORWARD: GAS", "BACK: BRAKE", "THE GEARS CHANGE THEMSELVES"},
        {"FIRE: GAS", "BACK: BRAKE", "THE GEARS CHANGE THEMSELVES"},
    };
    const char *const *h = help[c->automatic * 2 + c->fire_accel];
    for (uint8_t i = 0; i < 3; i++)
        put(2, (uint8_t)(34 + 3 * i), h[i], 36, TEXT_WHITE);
    put(2, 43, "LEFT / RIGHT: STEER", 36, TEXT_WHITE);
}

MENU void screen_controls(Controls *c) {
    static const uint8_t rows[3] = {12, 18, 24};
    uint8_t at = 2;
    page_show("PCONTROLS");
    for (;;) {
        marks(rows, 3, at, 12);
        put(14, 12, c->automatic ? "AUTOMATIC" : "MANUAL", 20, TEXT_WHITE);
        put(14, 18, c->fire_accel ? "FIRE BUTTON" : "JOYSTICK FORWARD", 20, TEXT_WHITE);
        put(14, 24, "START", 20, TEXT_AMBER);
        controls_help(c);
        uint8_t k = key();
        if ((k & IN_UP) && at)
            at--;
        if ((k & IN_DOWN) && at < 2)
            at++;
        if (k & (IN_LEFT | IN_RIGHT | IN_BUTTON)) {
            if (at == 0)
                c->automatic = !c->automatic;
            else if (at == 1)
                c->fire_accel = !c->fire_accel;
            else if (k & IN_BUTTON)
                return;
        }
    }
}

// ---------------------------------------------------------------- the radio

// Two digits of n on the display, big or small, from col on
MENU static void two_digits(uint8_t col, uint8_t row, bool big, uint8_t n) {
    uint8_t w = big ? DIGIT_BIG_W : DIGIT_SMALL_W;
    page_digit(col, row, big, n == 0xFF ? DIGIT_DASH : n / 10);
    page_digit((uint8_t)(col + w), row, big, n == 0xFF ? DIGIT_DASH : n % 10);
}

MENU uint8_t screen_radio(uint8_t track) {
#ifdef LOTUS_AUTOTEST
    static const uint8_t keys[] = {IN_RIGHT, IN_RIGHT, IN_BUTTON, 0};  // track 03
    auto_keys = keys;
#endif
    page_show("PRADIO");
    page_digits_in();
    uint8_t shown = 0xFF, second = 0xFF, frames = 0, f = video_frame();
    uint16_t seconds = 0;
    for (;;) {
        if (track != shown) {
            // the track from its start (00: none)
            if (track)
                music_start(track);
            else
                music_stop();
            two_digits(RADIO_TRACK_COL, RADIO_TRACK_ROW, true, track);
            shown = track;
            seconds = frames = 0;
            second = 0xFE;
        }
        // the time it has played, minutes and seconds (--:-- for none)
        if ((uint8_t)seconds != second) {
            second = (uint8_t)seconds;
            uint8_t m = track ? (uint8_t)(seconds / 60 % 100) : 0xFF, s = track ? (uint8_t)(seconds % 60) : 0xFF;
            two_digits(RADIO_TIME_COL, RADIO_TIME_ROW, false, m);
            two_digits(RADIO_TIME_COL + 3, RADIO_TIME_ROW, false, s);
        }
        uint8_t k = key_poll();
        uint8_t now = video_frame();
        frames = (uint8_t)(frames + (uint8_t)(now - f));
        f = now;
        if (frames >= 50) {
            frames -= 50;
            seconds++;
        }
        if (k & IN_BUTTON)
            return track;
        if (k & IN_RIGHT)
            track = (uint8_t)(track + 1 < MUSIC_SONGS ? track + 1 : 0);
        if (k & IN_LEFT)
            track = (uint8_t)(track ? track - 1 : MUSIC_SONGS - 1);
    }
}

// ---------------------------------------------------------------- the season

// Text of the course header (track.h: name, location, description,
// hazards after the colours; from the course as loaded, TRACK_ATTIC), the
// padding cut
MENU static void header_text(uint8_t at, uint8_t len, uint8_t col, uint8_t row, uint8_t colour) {
    char buf[33];
    dma_copy(TRACK_ATTIC + 2 + at, (uint16_t)buf, len);
    dma_flush();
    uint8_t n = 0;
    for (uint8_t i = 0; i < len; i++) {
        char ch = buf[i];
        buf[i] = ch == '/' ? ' ' : ch;
        if (ch != '/')
            n = (uint8_t)(i + 1);
    }
    buf[n] = 0;
    put(col, row, buf, 32, colour);
}

MENU void screen_course(uint8_t course) {
    char buf[TEXT_LEN + 1];
    page_show("PCOURSE");
    // RACE n OF m, the course's name
    char *b = line;
    *b++ = 'R', *b++ = 'A', *b++ = 'C', *b++ = 'E', *b++ = ' ';
    b = number(b, (uint16_t)(season.race + 1), 1);
    *b++ = ' ', *b++ = 'O', *b++ = 'F', *b++ = ' ';
    number(b, season.races, 1);
    page_text(30, 1, line, TEXT_GREY);
    header_text(56, 10, 2, 9, TEXT_WHITE);
    header_text(66, 32, 13, 16, TEXT_WHITE);
    number(buf, tab_laps[course], 1);
    put(13, 20, buf, 4, TEXT_WHITE);
    header_text(98, 32, 13, 24, TEXT_WHITE);
    header_text(130, 32, 13, 30, TEXT_WHITE);
    uint16_t record = season_record(course, buf);
    put(13, 36, buf, 20, TEXT_WHITE);
    time_text(buf, record);
    put(13, 39, buf, 10, TEXT_WHITE);
    screen_wait_fire();
}

// A row of the result or the championship: place, driver, a text (time),
// points; the player's in amber
MENU static void row(uint8_t r, uint8_t place, uint8_t driver, const char *time, uint16_t points) {
    char buf[TEXT_LEN + 1];
    uint8_t colour = driver == DRIVER_P1 ? TEXT_AMBER : TEXT_WHITE;
    place_text(buf, place);
    put(1, r, buf, 5, colour);
    season_name(driver, buf);
    put(6, r, buf, 20, colour);
    put(27, r, time, 7, colour);
    number(buf, points, 1);
    put(35, r, buf, 4, colour);
}

MENU void screen_result(void) {
    char buf[12];
    page_show("PRESULT");
    uint8_t r = 10;
    for (uint8_t i = 0; i < DRIVERS; i++)
        if (i < SCORING || i == season.place) {
            if (season.time[i])
                time_text(buf, season.time[i]);
            else
                buf[0] = 0;
            row(r, i, season.order[i], buf, tab_points[i]);
            r = (uint8_t)(r + 3);
        }
    if (season.record)
        page_text(1, 44, "A NEW COURSE RECORD", TEXT_RED);
    screen_wait_fire();
}

MENU void screen_standing(void) {
    page_show("PSTANDING");
    uint8_t r = 10;
    for (uint8_t i = 0; i < DRIVERS; i++) {
        uint8_t d = season.standing[i];
        if (i < SCORING || d == DRIVER_P1) {
            row(r, i, d, "", season.points[d]);
            r = (uint8_t)(r + 3);
        }
    }
    screen_wait_fire();
}

MENU void screen_season_over(bool out) {
    static const char *const level[LEVELS] = {"EASY", "MEDIUM", "HARD"};
    page_show("PSEASON");
    if (out) {
        page_text(2, 12, "YOU FINISHED OUTSIDE THE FIRST TEN:", TEXT_WHITE);
        page_text(2, 15, "THE SEASON IS OVER FOR YOU.", TEXT_WHITE);
    } else if (season.standing[0] == DRIVER_P1) {
        page_text(2, 12, "YOU WON THE CHAMPIONSHIP", TEXT_AMBER);
        page_text(2, 15, "OF THE LEVEL", TEXT_AMBER);
        page_text(15, 15, level[season.level], TEXT_AMBER);
    } else {
        page_text(2, 12, "YOU FINISHED THE SEASON,", TEXT_WHITE);
        page_text(2, 15, "BUT DID NOT WIN THE CHAMPIONSHIP.", TEXT_WHITE);
        page_text(2, 18, "KEEP TRYING...", TEXT_WHITE);
    }
    char buf[6];
    page_text(2, 24, "YOUR POINTS:", TEXT_GREY);
    number(buf, season.points[DRIVER_P1], 1);
    page_text(15, 24, buf, TEXT_WHITE);
    screen_wait_fire();
}
