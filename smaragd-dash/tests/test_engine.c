// Host tests for the cave engine: cc -I../src test_engine.c ../src/engine.c
//
// Each test builds a small cave from text (the rest is steel), runs some
// ticks and compares the result with the expected picture.
//   W steel  w brick  . dirt  (space)  r boulder  d diamond  P inbox
//   X outbox  R Rockford  q firefly (left)  B butterfly (down)  a amoeba
//   m magic wall  * explosion (any stage)

#include <stdio.h>
#include <string.h>

#include "engine.h"

static uint8_t map[CAVE_SIZE];
static CaveDef def = {"test", map, 100, 2, 10, 15, 30, 30, 140};
static int failures;

static uint8_t from_char(char c) {
    switch (c) {
    case 'w': return E_BRICK;
    case '.': return E_DIRT;
    case ' ': return E_SPACE;
    case 'r': return E_BOULDER;
    case 'd': return E_DIAMOND;
    case 'P': return E_INBOX;
    case 'X': return E_OUTBOX;
    case 'R': return E_ROCKFORD;
    case 'q': return E_FIREFLY + DIR_LEFT;
    case 'B': return E_BUTTERFLY + DIR_DOWN;
    case 'a': return E_AMOEBA;
    case 'm': return E_MAGIC;
    default: return E_STEEL;
    }
}

static char to_char(uint8_t e) {
    switch (e) {
    case E_BRICK: return 'w';
    case E_DIRT: return '.';
    case E_SPACE: return ' ';
    case E_BOULDER: case E_BOULDER_F: return 'r';
    case E_DIAMOND: case E_DIAMOND_F: return 'd';
    case E_INBOX: return 'P';
    case E_OUTBOX: case E_OUTBOX_OPEN: return 'X';
    case E_ROCKFORD: return 'R';
    case E_AMOEBA: return 'a';
    case E_MAGIC: return 'm';
    }
    if (e >= E_FIREFLY && e < E_FIREFLY + 4) return 'q';
    if (e >= E_BUTTERFLY && e < E_BUTTERFLY + 4) return 'B';
    if (e >= E_EXPLODE && e < E_BIRTH) return '*';
    return 'W';
}

// rows: the cave's rows starting at (1,1), inside the steel frame
static void setup(const char *const *rows, int n) {
    memset(map, E_STEEL, sizeof map);
    for (int y = 0; y < n; y++)
        for (int x = 0; rows[y][x]; x++)
            map[(y + 1) * CAVE_W + x + 1] = from_char(rows[y][x]);
    cave_start(&def);
    game.state = PS_ALIVE;  // tests start with Rockford alive
    game.hatch_ticks = 0;
}

static void check(const char *name, const char *const *rows, int n) {
    int bad = 0;
    for (int y = 0; y < n; y++)
        for (int x = 0; rows[y][x]; x++)
            if (to_char(cave[(y + 1) * CAVE_W + x + 1]) != rows[y][x])
                bad = 1;
    if (!bad) {
        printf("ok   %s\n", name);
        return;
    }
    failures++;
    printf("FAIL %s\n", name);
    for (int y = 0; y < n; y++) {
        printf("  |");
        for (int x = 0; rows[y][x]; x++)
            putchar(to_char(cave[(y + 1) * CAVE_W + x + 1]));
        printf("|   expected |%s|\n", rows[y]);
    }
}

static void ticks(int n, uint8_t input) {
    while (n--)
        cave_tick(input);
}

#define SETUP(...) do { static const char *const r[] = {__VA_ARGS__}; setup(r, sizeof r / sizeof *r); } while (0)
#define CHECK(name, ...) do { static const char *const r[] = {__VA_ARGS__}; check(name, r, sizeof r / sizeof *r); } while (0)
#define EXPECT(name, cond) do { if (cond) printf("ok   %s\n", name); else { failures++; printf("FAIL %s\n", name); } } while (0)

int main(void) {
    SETUP("r", " ", " ", ".");
    ticks(1, DIR_NONE);
    CHECK("boulder starts falling at once", " ", "r", " ", ".");
    ticks(2, DIR_NONE);
    CHECK("boulder lands on dirt", " ", " ", "r", ".");

    SETUP("  ", "r ", "r ", "ww");
    ticks(1, DIR_NONE);
    CHECK("boulder on boulder moves aside first", "  ", " r", "r ", "ww");
    ticks(1, DIR_NONE);
    CHECK("boulder rolls off boulder to the right", "  ", "  ", "rr", "ww");

    SETUP("  ", " r", " r", "ww");
    ticks(2, DIR_NONE);
    CHECK("boulder rolls off boulder to the left", "  ", "  ", "rr", "ww");

    SETUP("r", "w");
    ticks(3, DIR_NONE);
    CHECK("no room: boulder stays on the wall", "r", "w");

    SETUP("r ", ". ");
    ticks(3, DIR_NONE);
    CHECK("dirt is not round", "r ", ". ");

    SETUP("r", ".", "R");
    ticks(1, DIR_NONE);
    CHECK("resting boulder over dirt stays", "r", ".", "R");

    SETUP("r", "R", ".");
    ticks(1, DIR_DOWN);
    ticks(1, DIR_NONE);
    CHECK("walking down under a boulder: it follows", " ", "r", "R");
    ticks(1, DIR_NONE);
    EXPECT("... and kills Rockford", game.state == PS_DEAD);

    SETUP("r", "R", " ");
    ticks(1, DIR_LEFT);  // blocked by steel
    CHECK("Rockford under a resting boulder is safe", "r", "R", " ");

    SETUP("R.d ");
    ticks(1, DIR_RIGHT);
    CHECK("Rockford digs", " Rd ");
    ticks(1, DIR_RIGHT);
    CHECK("Rockford collects", "  R ");
    EXPECT("... diamond counted", game.collected == 1 && game.score == 10);

    SETUP("R.d");
    ticks(1, DIR_RIGHT | IN_FIRE);
    CHECK("snapping takes dirt without moving", "R d");

    SETUP("Rr ");
    for (int i = 0; i < 40 && cave[CAVE_W + 3] != E_BOULDER; i++)
        ticks(1, DIR_RIGHT);
    CHECK("Rockford pushes a boulder (sometimes)", " Rr");

    SETUP("Rrr ");
    ticks(40, DIR_RIGHT);
    CHECK("two boulders cannot be pushed", "Rrr ");

    SETUP("     ", " www ", " w w ", " www ", "q    ");
    ticks(1, DIR_NONE);
    CHECK("firefly facing left in a corner turns right (up) on the spot", "     ", " www ", " w w ", " www ", "q    ");
    ticks(1, DIR_NONE);
    CHECK("... then moves up", "     ", " www ", " w w ", "qwww ", "     ");

    SETUP("www", "  q");
    ticks(1, DIR_NONE);
    CHECK("firefly goes straight on", "www", " q ");

    SETUP(" R", " q");
    ticks(1, DIR_NONE);
    CHECK("firefly next to Rockford explodes", "**", "**");
    EXPECT("... and Rockford is dead", game.state == PS_DEAD);
    ticks(5, DIR_NONE);
    CHECK("explosion leaves space", "  ", "  ");

    SETUP("r ", "  ", "B ", "ww");
    ticks(1, DIR_NONE);
    CHECK("butterfly facing down, blocked: turns left on the spot", "  ", "r ", "B ", "ww");
    ticks(1, DIR_NONE);
    CHECK("falling boulder hits butterfly", "  ", "**", "**", "**");
    ticks(5, DIR_NONE);
    CHECK("butterfly leaves diamonds", "  ", "dd", "dd", "dd");

    SETUP("r", "m", " ", "w");
    map[CAVE_W + 1] = E_BOULDER_F;
    cave_start(&def);
    game.state = PS_ALIVE;
    ticks(1, DIR_NONE);
    CHECK("magic wall turns boulder into diamond", " ", "m", "d", "w");
    EXPECT("... and wakes up", game.magic_state == MW_ACTIVE);

    def.amoeba_time = 0;
    SETUP("w w", "wa ", "www");
    for (int i = 0; i < 300; i++)
        ticks(1, DIR_NONE);
    CHECK("enclosed amoeba turns into diamonds", "wdw", "wdd", "www");

    SETUP("wRw", "w w", "wXw");
    game.collected = 1;
    def.diamonds_needed = 2;
    map[CAVE_W * 2 + 2] = E_DIAMOND;
    cave[CAVE_W * 2 + 2] = E_DIAMOND;
    ticks(1, DIR_DOWN);
    EXPECT("exit opens with the last diamond", game.exit_open && game.flash);
    ticks(1, DIR_DOWN);
    EXPECT("Rockford enters the exit", game.state == PS_EXITED);

    // The moves of a tick, for drawing them (moved[])
#define AT(x, y) moved[((y) + 1) * CAVE_W + (x) + 1]
    SETUP("r  ", "   ", " R ");
    ticks(1, DIR_RIGHT);
    EXPECT("moves: boulder falls, Rockford walks",
           AT(0, 1) == DIR_DOWN && AT(2, 2) == DIR_RIGHT && AT(0, 0) == DIR_NONE && AT(1, 2) == DIR_NONE);
    ticks(1, DIR_NONE);
    EXPECT("moves: only those of the last tick", AT(2, 2) == DIR_NONE && AT(0, 2) == DIR_DOWN);
    ticks(1, DIR_NONE);
    EXPECT("moves: a landed boulder did not move", AT(0, 2) == DIR_NONE);

    SETUP(" q ", "   ");
    ticks(1, DIR_NONE);
    EXPECT("moves: firefly turns left and moves", AT(1, 1) == DIR_DOWN);

    SETUP("r", "R", " ");
    ticks(1, DIR_NONE);
    ticks(1, DIR_DOWN);
    ticks(1, DIR_NONE);
    EXPECT("moves: the boulder follows", AT(0, 1) == DIR_DOWN);
    ticks(1, DIR_NONE);
    EXPECT("moves: none where it exploded",
           game.state == PS_DEAD && AT(0, 1) == DIR_NONE && AT(0, 2) == DIR_NONE);
#undef AT

    printf(failures ? "\n%d FAILED\n" : "\nall passed\n", failures);
    return failures != 0;
}
