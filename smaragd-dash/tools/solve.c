// Smaragd Dash: finds a way through the caves for the screencast build
// (SCREENCAST, see main.c). Runs on the host with GDash's engine as the game
// has it (src/gdengine.c, with the game's random numbers, which the
// screencast build starts the same as here: seed 0), so what works here
// works the same in the game, step by step.
//
// Usage: solve <gendir> <diskdir>
//   writes <gendir>/demo.h and a file per cave, <diskdir>/demoNN.bin, which
//   build.sh puts on the disk as DEMONN for the screencast build to load
//
// A cave can bring opening moves (the .moves file beside its .bd) for what
// the search cannot do: dropping boulders on purpose, pushing. They are
// played first, then the search goes on from there.
//
// The way: from the nearest few emeralds pick one, walk there (the path is
// planned again every step, round boulders, nuts and the like and away from
// creatures, over clocks), and so on until the exit (or the hidden one) is
// open, then walk out. A choice that gets Rockford
// killed or stuck is taken back and the next one tried. The caves of level 1
// are solved in order for the screencast; the first one without a solution
// ends its list. The higher levels are only checked: each cave in each of
// them is solved too, and the ones without a way through are named.
//
// A demo file holds the input of every step from the start of a cave: two
// bytes of load address (not used), then pairs of (count, input) with input
// as main.c's rules_tick takes it (DIR_* | IN_FIRE), closed by a count of 0;
// at most DEMO_MAX bytes after the load address, the game's buffer for them.
// A cave whose moves do not fit ends the list as well.

#include <stdio.h>
#include <stdlib.h>

#include "caves.h"
#include "gdengine.c"

#define MAX_TICKS  4000
#define CHOICES    3    // emeralds tried at each step
#define MAX_NODES  5000  // solved caves need up to about 1600
#define DEMO_MAX   1024  // the game's buffer for one cave's moves (the demo caves' too)

static const int16_t dir_off[4] = {-CAVE_W, 1, CAVE_W, -1};  // DIR_*

// GDash's engine as it stands, and the moves so far
typedef struct {
    GdState gd;
    uint8_t cave[CAVE_SIZE];
    uint8_t hammered[CAVE_SIZE];
    uint32_t rng;
    uint8_t c64_seed_1, c64_seed_2;
    int ticks;
} State;

static uint8_t moves[MAX_TICKS];
static int ticks;
static long nodes;
static uint16_t exit_cell;

static void save(State *s) {
    s->gd = gd;
    memcpy(s->cave, cave, CAVE_SIZE);
    memcpy(s->hammered, hammered, CAVE_SIZE);
    s->rng = rng;
    s->c64_seed_1 = c64_seed_1;
    s->c64_seed_2 = c64_seed_2;
    s->ticks = ticks;
}

static void load(const State *s) {
    gd = s->gd;
    memcpy(cave, s->cave, CAVE_SIZE);
    memcpy(hammered, s->hammered, CAVE_SIZE);
    rng = s->rng;
    c64_seed_1 = s->c64_seed_1;
    c64_seed_2 = s->c64_seed_2;
    ticks = s->ticks;
}

static uint16_t player_cell(void) {
    return gd.player_y * CAVE_W + gd.player_x;
}

// A step with input `in`, as rules_tick makes it; false if Rockford is no
// longer alive (unless he got out)
static bool tick(uint8_t in) {
    static const uint8_t mv[] = {MV_UP, MV_RIGHT, MV_DOWN, MV_LEFT, MV_STILL};
    if (ticks >= MAX_TICKS || gd.player_state == GD_PL_TIMEOUT || gd.player_state == GD_PL_EXITED)
        return false;
    gd_iterate(mv[in & 7], (in & IN_FIRE) != 0, false);
    moves[ticks++] = in;
    return gd.player_state == GD_PL_LIVING || gd.player_state == GD_PL_EXITED;
}

static bool creature(uint8_t e) {
    return (e >= O_FIREFLY_1 && e <= O_FIREFLY_4) || (e >= O_BUTTER_1 && e <= O_BUTTER_4);
}

static bool falls(uint8_t e) {
    return e == O_STONE || e == O_STONE_F || e == O_DIAMOND || e == O_DIAMOND_F || e == O_NUT || e == O_NUT_F;
}

static bool is_exit(uint8_t e) {
    return e == O_PRE_OUTBOX || e == O_OUTBOX || e == O_PRE_INVIS_OUTBOX || e == O_INVIS_OUTBOX;
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
        bool open = e == O_SPACE || e == O_DIRT || e == O_DIAMOND || e == O_CLOCK || i == player_cell() ||
                    (i == target && is_exit(e));
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
        if (gd.player_state == GD_PL_EXITED)
            return target == exit_cell;
        if (player_cell() == target)
            return true;
        uint8_t e = cave[target];
        if (target != exit_cell && e != O_DIAMOND)
            return false;  // it fell or was taken
        plan(target);
        uint16_t p = player_cell();
        int best = DIR_NONE;
        for (int d = 0; d < 4; d++) {
            int j = p + dir_off[d];
            if (cost[j] != 0xFFFF && (best == DIR_NONE || cost[j] < cost[p + dir_off[best]]))
                best = d;
        }
        if (!tick(best))  // DIR_NONE: no way now, wait
            return gd.player_state == GD_PL_EXITED && target == exit_cell;
    }
    return false;
}

static bool solve_from_here(void) {
    if (gd.player_state == GD_PL_EXITED)
        return true;
    if (++nodes > MAX_NODES)
        return false;
    uint16_t targets[CAVE_SIZE];
    uint16_t dist[CAVE_SIZE];
    int n = 0;
    if (gd.gate_open) {
        targets[n++] = exit_cell;
    } else {
        // the nearest emeralds (by the path costs from them to Rockford,
        // close enough to the other way round)
        plan(player_cell());
        for (int i = 0; i < CAVE_SIZE; i++) {
            if (cave[i] != O_DIAMOND || cost[i] == 0xFFFF)
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
                return gd.player_state == GD_PL_EXITED;
    }
    return true;
}

static bool solve(const GdCaveFile *f, const char *demo) {
    gd_start(f, 0);  // as the screencast build starts it
    ticks = 0;
    nodes = 0;
    for (int i = 0; i < CAVE_SIZE; i++)
        if (f->map[i] == O_PRE_OUTBOX || f->map[i] == O_PRE_INVIS_OUTBOX)
            exit_cell = i;
    // until Rockford stands there: hatched, and born out of the inbox
    while (gd.player_state == GD_PL_NOT_YET || (gd.player_state == GD_PL_LIVING && cave[player_cell()] != O_PLAYER))
        tick(DIR_NONE);
    if (!opening(demo)) {
        printf("solve: Rockford did not survive the opening moves\n");
        return false;
    }
    return solve_from_here();
}

// The moves of the last solved cave as (count, input) pairs, closed by 0;
// the length, or 0 if they do not fit into DEMO_MAX bytes
static int pack(uint8_t *out) {
    int len = 0;
    for (int i = 0; i < ticks;) {
        int n = 1;
        while (i + n < ticks && n < 255 && moves[i + n] == moves[i])
            n++;
        if (len + 3 > DEMO_MAX)
            return 0;
        out[len++] = n;
        out[len++] = moves[i];
        i += n;
    }
    out[len++] = 0;
    return len;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: solve <gendir> <diskdir>\n");
        return 1;
    }
    char path[1024];
    int solved = 0;
    for (; solved < CAVE_COUNT; solved++) {
        const char *name = caves[0][solved]->name;
        if (!solve(caves[0][solved], cave_demo[solved])) {
            printf("solve: no way found through cave %d (%s)\n", solved + 1, name);
            break;
        }
        uint8_t data[2 + DEMO_MAX] = {0x00, 0x20};  // load address, not used
        int len = pack(data + 2);
        if (!len) {
            printf("solve: the moves through cave %d (%s) take more than %d bytes\n",
                   solved + 1, name, DEMO_MAX);
            break;
        }
        printf("solve: cave %d (%s): %d steps, %d emeralds, %d s left\n", solved + 1, name,
               ticks, gd.diamonds_collected, gd_time_visible());
        snprintf(path, sizeof path, "%s/demo%02d.bin", argv[2], solved + 1);
        FILE *f = fopen(path, "wb");
        if (!f || fwrite(data, 1, 2 + len, f) != (size_t)(2 + len) || fclose(f)) {
            perror(path);
            return 1;
        }
    }

    // The higher levels: is there a way through, and how much time is left?
    for (int lv = 1; lv < LEVELS; lv++) {
        int ok = 0, least = -1;
        double spare = 0;
        for (int i = 0; i < CAVE_COUNT; i++) {
            const GdCaveFile *c = caves[lv][i];
            if (!solve(c, cave_demo[i])) {
                printf("solve: level %d: no way found through cave %d (%s)\n", lv + 1, i + 1,
                       c->name);
                continue;
            }
            ok++;
            // the time limit over the time the solver needed
            double f = c->time / (ticks * c->speed / 1000.0);
            if (least < 0 || f < spare) {
                least = i;
                spare = f;
            }
        }
        printf("solve: level %d: %d of %d caves solved", lv + 1, ok, CAVE_COUNT);
        if (least >= 0)
            printf(", the least time to spare in cave %d (%s): %.1f times the time needed",
                   least + 1, caves[lv][least]->name, spare);
        printf("\n");
    }

    snprintf(path, sizeof path, "%s/demo.h", argv[1]);
    FILE *h = fopen(path, "w");
    if (!h) {
        perror(path);
        return 1;
    }
    fprintf(h, "// Generated by tools/solve.c - do not edit\n#ifndef DEMO_H\n#define DEMO_H\n\n"
               "#define DEMO_CAVES %d  // caves with moves on the disk (DEMO01, ...)\n"
               "#define DEMO_MAX   %d  // bytes of moves per cave at most\n\n#endif\n",
            solved, DEMO_MAX);
    fclose(h);
    return 0;
}
