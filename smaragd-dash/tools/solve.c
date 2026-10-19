// Smaragd Dash: finds a way through the caves for the screencast build
// (SCREENCAST, see main.c). Runs on the host with the game's own engine, so
// what works here works the same in the game: the cave's random numbers start
// the same every time, and the frames and ticks are counted as play_cave does
// it (PAL).
//
// Usage: solve <outdir>    writes <outdir>/demo.h and demo.c
//
// A cave can bring opening moves (the demo key of its .cave file) for what
// the search cannot do: dropping boulders on purpose, pushing. They are
// played first, then the search goes on from there.
//
// The way: from the nearest few emeralds pick one, walk there (the path is
// planned again every tick, round boulders and away from creatures), and so
// on until the exit is open, then walk out. A choice that gets Rockford
// killed or stuck is taken back and the next one tried. The caves are solved
// in order; the first one without a solution ends the list.
//
// demo.c holds the input of every tick from the start of a cave: pairs of
// (count, input) with input as for cave_tick, closed by a count of 0.

#include <stdio.h>
#include <stdlib.h>

#include "caves.h"
#include "engine.c"

#define FRAME_LEN  60   // one PAL frame in 1/3 ms, as in play_cave
#define FPS        50
#define MAX_TICKS  4000
#define CHOICES    3    // emeralds tried at each step
#define MAX_NODES  20000

typedef struct {
    uint8_t cave[CAVE_SIZE];
    struct game game;
    uint16_t cave_rng;
    uint16_t tick_acc;
    uint8_t sec;
    int ticks;
} State;

static uint16_t tick_acc, tick_len;
static uint8_t sec;
static uint8_t moves[MAX_TICKS];
static int ticks;
static long nodes;
static uint16_t exit_cell;

static void save(State *s) {
    memcpy(s->cave, cave, CAVE_SIZE);
    s->game = game;
    s->cave_rng = cave_rng;
    s->tick_acc = tick_acc;
    s->sec = sec;
    s->ticks = ticks;
}

static void load(const State *s) {
    memcpy(cave, s->cave, CAVE_SIZE);
    game = s->game;
    cave_rng = s->cave_rng;
    tick_acc = s->tick_acc;
    sec = s->sec;
    ticks = s->ticks;
}

// Frames as in play_cave until the next tick, which gets `in`
static bool tick(uint8_t in) {
    if (ticks >= MAX_TICKS || game.state == PS_TIMEOUT || game.state == PS_EXITED)
        return false;
    for (;;) {
        bool ticked = false;
        tick_acc += FRAME_LEN;
        if (tick_acc >= tick_len) {
            tick_acc -= tick_len;
            cave_tick(in);
            moves[ticks++] = in;
            ticked = true;
        }
        if (game.state == PS_ALIVE && ++sec >= FPS) {
            sec = 0;
            cave_second();
        }
        if (ticked)
            return game.state == PS_ALIVE || game.state == PS_EXITED;
    }
}

static bool creature(uint8_t e) {
    return e >= E_FIREFLY && e < E_BUTTERFLY + 4;
}

static bool falls(uint8_t e) {
    return e == E_BOULDER || e == E_BOULDER_F || e == E_DIAMOND || e == E_DIAMOND_F;
}

// Path costs from every cell to `target` (Dijkstra backwards); cells within
// two steps of a creature are closed, stepping into a cell below something
// that can fall costs extra.
static uint16_t cost[CAVE_SIZE];

static void plan(uint16_t target) {
    static bool closed[CAVE_SIZE];
    memset(closed, 0, sizeof closed);
    for (int i = 0; i < CAVE_SIZE; i++) {
        uint8_t e = cave[i];
        bool open = e == E_SPACE || e == E_DIRT || e == E_DIAMOND || e == E_ROCKFORD ||
                    (i == target && (e == E_OUTBOX || e == E_OUTBOX_OPEN));
        if (!open)
            closed[i] = true;
        if (creature(e)) {
            int x = i % CAVE_W, y = i / CAVE_W;
            for (int dy = -2; dy <= 2; dy++)
                for (int dx = -2; dx <= 2; dx++)
                    if (abs(dx) + abs(dy) <= 2 && x + dx >= 0 && x + dx < CAVE_W &&
                        y + dy >= 0 && y + dy < CAVE_H)
                        closed[(y + dy) * CAVE_W + x + dx] = true;
        }
    }
    // Dijkstra with a binary heap of (cost << 16 | cell)
    static uint32_t heap[CAVE_SIZE * 4];
    int n = 0;
    for (int i = 0; i < CAVE_SIZE; i++)
        cost[i] = 0xFFFF;
    cost[target] = 0;
    heap[n++] = target;
    while (n) {
        uint32_t top = heap[0];
        uint32_t last = heap[--n];
        int k = 0;
        for (;;) {  // sift the last one down from the root
            int c = 2 * k + 1;
            if (c >= n)
                break;
            if (c + 1 < n && heap[c + 1] < heap[c])
                c++;
            if (heap[c] >= last)
                break;
            heap[k] = heap[c];
            k = c;
        }
        heap[k] = last;
        int cell = top & 0xFFFF;
        if ((top >> 16) != cost[cell])
            continue;  // outdated entry
        for (int d = 0; d < 4; d++) {
            int j = cell - dir_off[d];  // the cell from which one steps into this one
            if (j < 0 || j >= CAVE_SIZE || closed[j])
                continue;
            uint16_t c = cost[cell] + 1 + (j >= CAVE_W && falls(cave[j - CAVE_W]) ? 4 : 0);
            if (c >= cost[j])
                continue;
            cost[j] = c;
            int k = n++;  // sift up
            uint32_t v = (uint32_t)c << 16 | j;
            while (k > 0 && heap[(k - 1) / 2] > v) {
                heap[k] = heap[(k - 1) / 2];
                k = (k - 1) / 2;
            }
            heap[k] = v;
        }
    }
}

// Walks to `target` until Rockford is there (or out, for the exit)
static bool walk(uint16_t target) {
    for (int guard = 0; guard < 300; guard++) {
        if (game.state == PS_EXITED)
            return target == exit_cell;
        if (game.player == target)
            return true;
        uint8_t e = cave[target];
        if (target != exit_cell && e != E_DIAMOND)
            return false;  // it fell or was taken
        plan(target);
        uint16_t p = game.player;
        int best = DIR_NONE;
        for (int d = 0; d < 4; d++) {
            int j = p + dir_off[d];
            if (cost[j] != 0xFFFF && (best == DIR_NONE || cost[j] < cost[p + dir_off[best]]))
                best = d;
        }
        if (!tick(best))  // DIR_NONE: no way now, wait
            return game.state == PS_EXITED && target == exit_cell;
    }
    return false;
}

static bool solve_from_here(void) {
    if (game.state == PS_EXITED)
        return true;
    if (++nodes > MAX_NODES)
        return false;
    uint16_t targets[CAVE_SIZE];
    uint16_t dist[CAVE_SIZE];
    int n = 0;
    if (game.exit_open) {
        targets[n++] = exit_cell;
    } else {
        // the nearest emeralds (by the path costs from them to Rockford,
        // close enough to the other way round)
        plan(game.player);
        for (int i = 0; i < CAVE_SIZE; i++) {
            if (cave[i] != E_DIAMOND || cost[i] == 0xFFFF)
                continue;
            int k = n++;
            while (k > 0 && dist[k - 1] > cost[i]) {
                targets[k] = targets[k - 1];
                dist[k] = dist[k - 1];
                k--;
            }
            targets[k] = i;
            dist[k] = cost[i];
        }
        if (n > CHOICES)
            n = CHOICES;
    }
    State s;
    save(&s);
    for (int k = 0; k < n; k++) {
        if (walk(targets[k]) && solve_from_here())
            return true;
        load(&s);
    }
    return false;
}

// The opening moves: U R D L walk, u r d l snap, . wait, a number repeats
// what follows (see tools/mkcave.py)
static bool opening(const char *m) {
    static const char walk[] = "URDL", snap[] = "urdl";
    while (*m) {
        int n = 0;
        while (*m >= '0' && *m <= '9')
            n = n * 10 + *m++ - '0';
        char c = *m++;
        if (!c)
            break;
        if (c == ' ')
            continue;
        uint8_t in = DIR_NONE;
        if (strchr(walk, c))
            in = strchr(walk, c) - walk;
        else if (strchr(snap, c))
            in = (strchr(snap, c) - snap) | IN_FIRE;
        for (n = n ? n : 1; n--;)
            if (!tick(in))
                return game.state == PS_EXITED;
    }
    return true;
}

static bool solve(const CaveDef *d, const char *demo) {
    cave_start(d);
    tick_len = d->tick_ms * 3;
    tick_acc = 0;
    sec = 0;
    ticks = 0;
    nodes = 0;
    for (int i = 0; i < CAVE_SIZE; i++)
        if (d->map[i] == E_OUTBOX)
            exit_cell = i;
    while (game.state == PS_HATCHING)
        tick(DIR_NONE);
    if (!opening(demo)) {
        printf("solve: Rockford did not survive the opening moves\n");
        return false;
    }
    return solve_from_here();
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: solve <outdir>\n");
        return 1;
    }
    char path[1024];
    snprintf(path, sizeof path, "%s/demo.c", argv[1]);
    FILE *c = fopen(path, "w");
    if (!c) {
        perror(path);
        return 1;
    }
    fprintf(c, "// Generated by tools/solve.c - do not edit\n#include \"demo.h\"\n\n");
    int solved = 0;
    for (; solved < CAVE_COUNT; solved++) {
        if (!solve(&caves[solved], cave_demo[solved])) {
            printf("solve: no way found through cave %d (%s)\n", solved + 1, caves[solved].name);
            break;
        }
        printf("solve: cave %d (%s): %d ticks, %d emeralds, %d s left\n", solved + 1,
               caves[solved].name, ticks, game.collected, game.time);
        fprintf(c, "static const uint8_t cave%d[] = {", solved);
        for (int i = 0, col = 0; i < ticks;) {
            int n = 1;
            while (i + n < ticks && n < 255 && moves[i + n] == moves[i])
                n++;
            fprintf(c, "%s%d, %d,", col++ % 8 ? " " : "\n    ", n, moves[i]);
            i += n;
        }
        fprintf(c, "\n    0\n};\n\n");
    }
    fprintf(c, "const uint8_t *const demo_moves[DEMO_CAVES + 1] = {\n");
    for (int i = 0; i < solved; i++)
        fprintf(c, "    cave%d,\n", i);
    fprintf(c, "    0\n};\n");
    fclose(c);

    snprintf(path, sizeof path, "%s/demo.h", argv[1]);
    FILE *h = fopen(path, "w");
    if (!h) {
        perror(path);
        return 1;
    }
    fprintf(h, "// Generated by tools/solve.c - do not edit\n#ifndef DEMO_H\n#define DEMO_H\n\n"
               "#include <stdint.h>\n\n#define DEMO_CAVES %d\n"
               "// per cave: (ticks, input) pairs, closed by 0\n"
               "extern const uint8_t *const demo_moves[DEMO_CAVES + 1];\n\n#endif\n",
            solved);
    fclose(h);
    return 0;
}
