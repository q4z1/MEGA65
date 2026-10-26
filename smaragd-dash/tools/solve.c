// Smaragd Dash: finds a way through the caves for the screencast build
// (SCREENCAST, see main.c). Runs on the host with GDash's engine as the game
// has it (src/gdengine.c, with the game's random numbers, which the
// screencast build starts the same as here: seed 0), so what works here
// works the same in the game, step by step.
//
// Usage: solve <gendir> <diskdir> [--levels]
//   writes <gendir>/demo.h and a file per cave, <diskdir>/demoNN.bin, which
//   build.sh puts on the disk as DEMONN for the screencast build to load;
//   with --levels it checks the higher levels too
//        solve --own <cave> <opening> <out.bin>
//   an own cave (a slot's contents without load address, tools/cavekit.py)
//   from the input of its first steps on (<opening>: a byte per step from
//   the start of the cave, as tools/democave.py plays them; empty: from
//   where Rockford stands): its moves as a demo file (tools/democave.py
//   solve, tools/record-solutions.sh); the way above first, then a beam
//   search (beam_search)
//
// A cave can bring opening moves (a .moves file, see tools/mkcave.py) for what
// the search cannot do: dropping boulders on purpose, pushing. They are
// played first, then the search goes on from there.
//
// The way: from the nearest few emeralds pick one, walk there (the path is
// planned again every step, round boulders, nuts and the like and away from
// creatures, over clocks), and so on until the exit (or the hidden one) is
// open, then walk out. A choice that gets Rockford
// killed or stuck is taken back and the next one tried. The caves of level 1
// are solved for the screencast, which plays the ones with a solution. The higher levels are only checked (--levels): each cave
// in each of them that differs from its first level is solved too, and the
// ones without a way through are named.
//
// A demo file holds the input of every step from the start of a cave: two
// bytes of load address (not used), then pairs of (count, input) with input
// as main.c's rules_tick takes it (DIR_* | IN_FIRE), closed by a count of 0;
// at most DEMO_MAX bytes after the load address, the game's buffer for them.
// A cave whose moves do not fit is left out as well.

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

static void start(const GdCaveFile *f) {
    gd_start(f, 0);  // as the screencast build starts it
    ticks = 0;
    nodes = 0;
    for (int i = 0; i < CAVE_SIZE; i++)
        if (f->map[i] == O_PRE_OUTBOX || f->map[i] == O_PRE_INVIS_OUTBOX)
            exit_cell = i;
}

// Until Rockford stands there: hatched, and born out of the inbox
static void born(void) {
    while (gd.player_state == GD_PL_NOT_YET || (gd.player_state == GD_PL_LIVING && cave[player_cell()] != O_PLAYER))
        tick(DIR_NONE);
}

static bool solve(const GdCaveFile *f, const char *demo) {
    start(f);
    born();
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

static bool write_demo(const char *path) {
    uint8_t data[2 + DEMO_MAX] = {0x00, 0x20};  // load address, not used
    int len = pack(data + 2);
    if (!len)
        return false;
    FILE *f = fopen(path, "wb");
    if (!f || fwrite(data, 1, 2 + len, f) != (size_t)(2 + len) || fclose(f)) {
        perror(path);
        exit(1);
    }
    return true;
}

// The beam search for the own caves, when the way above finds none: every
// step, each of the best beam_w states so far tries every input, and the
// best of what comes out go on - by the emeralds collected, then by how far
// the nearest one is (or the open exit), at most beam_cell states with
// Rockford in the same cell, the same cave twice only once. The engine
// decides what works: pushing, digging under boulders, dodging creatures.
// Its settings from the environment (a moves file's "%" line, see
// tools/democave.py): SOLVE_BEAM and SOLVE_CELL for beam_w and beam_cell,
// SOLVE_HEUR for the flags of heur, SOLVE_TIERS for room for the states
// with fewer emeralds.
static int beam_w = 1500, beam_cell = 3;
static int heur;  // 1: boulders and walls priced as below, 2: the way to the
                  // exit kept open, 4: the amoeba shut in

typedef struct {
    State s;
    int node;   // in the tree of inputs: the way here
    uint8_t in;
    long score;
    uint32_t tie;  // among equal scores: changes with every step, so that
                   // the same states do not win every time (a push wants
                   // tries with ever new random numbers)
} Cand;

static int32_t *tree_parent;
static uint8_t *tree_in;
static int tree_n;

// How far Rockford is from the nearest cell that `want` takes: digging
// through costs 1, a boulder or a creature 8 (it may be pushed, fall or move
// away), a brick or magic wall 10 (it may be blown up); steel and the like
// never. With heur & 1: a boulder 4 if it can be pushed on or fall, else
// 15, a wall 40.
static int distance(bool (*want)(int)) {
    static uint16_t d[CAVE_SIZE];
    static uint16_t queue[41][CAVE_SIZE];
    static int qn[41];
    for (int i = 0; i < CAVE_SIZE; i++)
        d[i] = 0xFFFF;
    memset(qn, 0, sizeof qn);
    int p = player_cell();
    d[p] = 0;
    queue[0][qn[0]++] = p;
    // a bucket queue: the costs of a step are at most 40 apart
    for (int base = 0; base < 4000; base++) {
        int b = base % 41;
        for (int k = 0; k < qn[b]; k++) {
            int c = queue[b][k];
            if (d[c] != base)
                continue;
            if (want(c))
                return base;
            for (int dir = 0; dir < 4; dir++) {
                int j = c + dir_off[dir];
                if (j < 0 || j >= CAVE_SIZE)
                    continue;
                uint8_t e = cave[j];
                int w;
                if (e == O_SPACE || e == O_DIRT || e == O_DIAMOND || e == O_DIAMOND_F || e == O_CLOCK ||
                    is_exit(e) || want(j))
                    w = 1;
                else if (creature(e))
                    w = 8;
                else if (falls(e) && (heur & 1))
                    // a boulder that can be pushed on or fall away, or not
                    w = (dir & 1) && cave[j + dir_off[dir]] == O_SPACE ? 4 :
                        cave[j + CAVE_W] == O_SPACE ? 4 : 15;
                else if (falls(e))
                    w = 8;
                else if (e == O_BRICK || e == O_MAGIC_WALL)
                    w = heur & 1 ? 40 : 10;
                else
                    continue;
                if ((unsigned)(base + w) < d[j]) {
                    d[j] = base + w;
                    int nb = (base + w) % 41;
                    queue[nb][qn[nb]++] = j;
                }
            }
        }
        qn[b] = 0;
    }
    return 4000;
}

static bool want_diamond(int c) {
    return cave[c] == O_DIAMOND || cave[c] == O_DIAMOND_F;
}

static bool want_exit(int c) {
    return cave[c] == O_OUTBOX || cave[c] == O_INVIS_OUTBOX;
}

// The exit open first, then the emeralds collected, then those there are
// still to collect (up to the number needed: a creature blown up into
// emeralds, boulders turned by a magic wall count), then the nearest one
static bool want_closed_exit(int c) {
    return is_exit(cave[c]);
}

static long beam_score(void) {
    if (gd.gate_open)
        return 10000000L - distance(want_exit);
    int there = 0;
    for (int i = 0; i < CAVE_SIZE; i++)
        there += want_diamond(i);
    int missing = gd.diamonds_needed - gd.diamonds_collected;
    long score = gd.diamonds_collected * 10000L + (there < missing ? there : missing) * 2000L - distance(want_diamond);
    if (heur & 2)  // the way out kept open
        score -= distance(want_closed_exit) / 4;
    if ((heur & 4) && there < missing) {
        // an amoeba with less room to grow, towards one shut in, which
        // turns into emeralds
        int room = 0;
        for (int i = CAVE_W; i < CAVE_SIZE - CAVE_W; i++)
            if (cave[i] == O_SPACE || cave[i] == O_DIRT)
                room += cave[i - 1] == O_AMOEBA || cave[i + 1] == O_AMOEBA || cave[i - CAVE_W] == O_AMOEBA ||
                        cave[i + CAVE_W] == O_AMOEBA;
        score -= room * 300L;
    }
    return score;
}

static uint32_t state_hash(void) {
    uint32_t h = 2166136261u;
    for (int i = 0; i < CAVE_SIZE; i++)
        h = (h ^ cave[i]) * 16777619u;
    h = (h ^ player_cell()) * 16777619u;
    h = (h ^ gd.diamonds_collected) * 16777619u;
    return h ^ rng;  // a push that failed is not the same as waiting: it takes a random number
}

static int by_score(const void *a, const void *b) {
    const Cand *p = a, *q = b;
    if (p->score != q->score)
        return p->score < q->score ? 1 : -1;
    return p->tie < q->tie ? -1 : p->tie > q->tie;
}

// The way to tree node n into moves[], ticks
static void tree_moves(int n) {
    int len = 0;
    for (int k = n; k > 0; k = tree_parent[k])
        len++;
    ticks = len;
    for (int k = n; k > 0; k = tree_parent[k])
        moves[--len] = tree_in[k];
}

// A state's cave for SOLVE_DEBUG=2
static void show(const State *s) {
    for (int y = 0; y < s->gd.h; y++) {
        for (int x = 0; x < s->gd.w; x++) {
            uint8_t e = s->cave[y * CAVE_W + x];
            char c = e == O_SPACE ? ' ' : e == O_DIRT ? '.' : e == O_STEEL ? 'W' : e == O_BRICK ? 'w' :
                     falls(e) && e != O_DIAMOND && e != O_DIAMOND_F ? 'r' : e == O_DIAMOND || e == O_DIAMOND_F ? 'd' :
                     creature(e) ? 'Q' : is_exit(e) ? 'X' : e == O_PLAYER ? '@' : e == O_MAGIC_WALL ? 'M' :
                     e == O_AMOEBA ? 'a' : '?';
            if (x == s->gd.player_x && y == s->gd.player_y)
                c = '@';
            fputc(c, stderr);
        }
        fputc('\n', stderr);
    }
}

static bool beam_search(void) {
    static Cand *beam, *next;
    static uint8_t *taken;
    static uint32_t seen[1 << 16];
    static uint8_t per_cell[CAVE_SIZE];
    if (getenv("SOLVE_BEAM"))
        beam_w = atoi(getenv("SOLVE_BEAM"));
    if (getenv("SOLVE_CELL"))
        beam_cell = atoi(getenv("SOLVE_CELL"));
    if (getenv("SOLVE_HEUR"))
        heur = atoi(getenv("SOLVE_HEUR"));
    bool tiers = getenv("SOLVE_TIERS") != NULL;
    long beam_nodes = (long)MAX_TICKS * beam_w;
    if (!beam) {
        beam = malloc(sizeof(Cand) * beam_w);
        next = malloc(sizeof(Cand) * beam_w * 9);
        taken = malloc(beam_w * 9);
        tree_parent = malloc(sizeof(int32_t) * beam_nodes);
        tree_in = malloc(beam_nodes);
        if (!beam || !next || !tree_parent || !tree_in) {
            fprintf(stderr, "solve: out of memory\n");
            exit(1);
        }
    }
    // the root: what has been played so far
    int start_ticks = ticks;
    static uint8_t first[MAX_TICKS];
    memcpy(first, moves, ticks);
    tree_n = 1;
    tree_parent[0] = -1;
    int nb = 1;
    save(&beam[0].s);
    beam[0].node = 0;
    for (int depth = start_ticks; depth < MAX_TICKS; depth++) {
        int nn = 0;
        memset(seen, 0, sizeof seen);
        for (int b = 0; b < nb; b++) {
            load(&beam[b].s);
            bool living = gd.player_state == GD_PL_LIVING;
            uint16_t p = player_cell();
            for (int in = 0; in < 9; in++) {
                if (in != DIR_NONE && !living)
                    continue;
                uint8_t input = in < 5 ? in : (in - 5) | IN_FIRE;
                if (in)
                    load(&beam[b].s);
                if (in > DIR_NONE) {  // snapping: only an emerald or dirt beside
                    uint8_t e = cave[p + dir_off[in - 5]];
                    if (e != O_DIAMOND && e != O_DIRT)
                        continue;
                }
                bool alive = tick(input);
                if (gd.player_state == GD_PL_EXITED) {
                    tree_moves(beam[b].node);
                    moves[ticks++] = input;
                    memmove(moves + start_ticks, moves, ticks);
                    memcpy(moves, first, start_ticks);
                    ticks += start_ticks;
                    return true;
                }
                if (!alive)
                    continue;
                uint32_t h = state_hash();
                uint32_t *slot = &seen[h & 0xFFFF];
                if (*slot == (h | 1))
                    continue;
                *slot = h | 1;
                Cand *c = &next[nn++];
                save(&c->s);
                c->node = beam[b].node;  // the parent until it goes on
                c->in = input;
                c->score = beam_score();
                c->tie = (h ^ (uint32_t)depth * 2654435761u) * 2246822519u;
            }
        }
        if (!nn)
            return false;
        qsort(next, nn, sizeof(Cand), by_score);
        memset(taken, 0, nn);
        memset(per_cell, 0, sizeof per_cell);
        nb = 0;
        // with SOLVE_TIERS: the states with the most emeralds get half the
        // beam, those with one less a quarter, ... (so that a way that
        // gets Rockford stuck after the last emerald is not the only one
        // left), what is left over goes by the score
        for (int pass = tiers ? 0 : 1; pass < 2; pass++) {
            int tier = -1, rank = -1, in_tier = 0;
            for (int k = 0; k < nn && nb < beam_w; k++) {
                if (taken[k])
                    continue;
                if (!pass) {
                    int t = next[k].s.gd.diamonds_collected + next[k].s.gd.gate_open;
                    if (t != tier)
                        tier = t, rank++, in_tier = 0;
                    int cap = rank < 30 ? beam_w >> (rank + 1) : 0;
                    if (in_tier >= (cap > 32 ? cap : 32))
                        continue;
                }
                int cell = next[k].s.gd.player_y * CAVE_W + next[k].s.gd.player_x;
                if (per_cell[cell] >= beam_cell)
                    continue;
                per_cell[cell]++;
                in_tier++;
                taken[k] = 1;
                if (tree_n >= beam_nodes) {
                    fprintf(stderr, "solve: the beam search ran out of room\n");
                    return false;
                }
                tree_parent[tree_n] = next[k].node;
                tree_in[tree_n] = next[k].in;
                next[k].node = tree_n++;
                beam[nb++] = next[k];
            }
        }
        if (getenv("SOLVE_DEBUG") && depth % 50 == 0) {
            fprintf(stderr, "step %d: %d states, best %ld (%d emeralds)\n", depth, nb, beam[0].score,
                    beam[0].s.gd.diamonds_collected);
            if (atoi(getenv("SOLVE_DEBUG")) > 1)
                show(&beam[0].s);
        }
    }
    return false;
}

// An own cave from a file, from the input of its first steps on
static int solve_own(const char *cave_path, const char *opening_path, const char *out) {
    static GdCaveFile f;
    static uint8_t first[MAX_TICKS];
    FILE *c = fopen(cave_path, "rb"), *o = fopen(opening_path, "rb");
    if (!c || fread(&f, 1, sizeof f, c) != sizeof f || !o) {
        fprintf(stderr, "solve: cannot read %s or %s\n", cave_path, opening_path);
        return 1;
    }
    size_t n = fread(first, 1, sizeof first, o);
    fclose(c);
    fclose(o);
    start(&f);
    if (!n)
        born();
    for (size_t i = 0; i < n; i++)
        if (!tick(first[i]) && gd.player_state != GD_PL_EXITED && gd.player_state != GD_PL_NOT_YET) {
            printf("solve: Rockford did not survive the opening moves\n");
            return 1;
        }
    State s;
    save(&s);
    if (!solve_from_here() && (load(&s), !beam_search())) {
        printf("solve: no way found through %s\n", f.name);
        return 1;
    }
    if (!write_demo(out)) {
        printf("solve: the moves through %s take more than %d bytes\n", f.name, DEMO_MAX);
        return 1;
    }
    printf("solve: %s: %d steps, %d emeralds, %d s left\n", f.name, ticks, gd.diamonds_collected,
           gd_time_visible());
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 5 && !strcmp(argv[1], "--own"))
        return solve_own(argv[2], argv[3], argv[4]);
    if (argc != 3 && !(argc == 4 && !strcmp(argv[3], "--levels"))) {
        fprintf(stderr, "usage: solve <gendir> <diskdir> [--levels]\n"
                        "       solve --own <cave> <opening> <out.bin>\n");
        return 1;
    }
    char path[1024];
    int solved = 0, list[CAVE_COUNT];
    for (int i = 0; i < CAVE_COUNT; i++) {
        const char *name = caves[0][i]->name;
        if (!solve(caves[0][i], cave_demo[i])) {
            printf("solve: no way found through cave %d (%s)\n", i + 1, name);
            continue;
        }
        snprintf(path, sizeof path, "%s/demo%02d.bin", argv[2], i + 1);
        if (!write_demo(path)) {
            printf("solve: the moves through cave %d (%s) take more than %d bytes\n", i + 1, name, DEMO_MAX);
            continue;
        }
        list[solved++] = i + 1;
        printf("solve: cave %d (%s): %d steps, %d emeralds, %d s left\n", i + 1, name,
               ticks, gd.diamonds_collected, gd_time_visible());
    }

    // The higher levels: is there a way through, and how much time is left?
    for (int lv = 1; lv < (argc == 4 ? LEVELS : 1); lv++) {
        int ok = 0, tried = 0, least = -1;
        double spare = 0;
        for (int i = 0; i < CAVE_COUNT; i++) {
            const GdCaveFile *c = caves[lv][i];
            if (c == caves[0][i])
                continue;  // the first level's
            tried++;
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
        printf("solve: level %d: %d of %d caves solved", lv + 1, ok, tried);
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
               "#define DEMO_CAVES %d  // caves with moves on the disk (DEMOnn, nn their number)\n"
               "#define DEMO_MAX   %d  // bytes of moves per cave at most\n"
               "#define DEMO_LIST  {",
            solved, DEMO_MAX);
    for (int i = 0; i < solved; i++)
        fprintf(h, "%s%d", i ? ", " : "", list[i]);
    fprintf(h, "%s}  // their numbers, from 1\n\n#endif\n", solved ? "" : "0");
    fclose(h);
    return 0;
}
