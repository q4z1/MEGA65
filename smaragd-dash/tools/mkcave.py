#!/usr/bin/env python3
"""Smaragd Dash caves: turns the caves of the game - GDash's files (.bd,
BDCFF), one cave each - into the files the game loads from the disk, and
into C for the tools on the host.

Usage: mkcave.py <outdir> <gendir> <file.bd>...   (in the order they are played)

Every cave comes in LEVELS levels, as in Boulder Dash 1. Its .bd file gives
the values of each level as GDash has them (CaveTime=150 135 120 105 105,
DiamondsRequired, FrameTime: milliseconds per step, ...; a fifth level,
which the game does not have, repeats the fourth), so GDash plays and edits
them as the game does. Level 1 is the map as drawn; the higher ones shuffle
the cave's fill (shuffle()) - what GDash cannot, it plays every level with
the map as drawn. Without RandSeed in the file each level is shuffled from
the cave's name; with it, from its value of that level, and a level with
level 1's value keeps the map (RandSeed=0 0 0 0 0: no shuffling at all).
GDash takes RandSeed for a random fill, which these caves do not have.

The moves the screencast and the solver (tools/solve.c) start every level
of a cave with - for what the solver cannot find by itself: dropping
boulders on purpose, pushing - are in a .moves file beside its .bd (as
tools/democave.py has them: U R D L walk, u r d l snap, . wait one tick, a
number repeats what follows, # a comment).

The caves of the game have Boulder Dash 1's elements and a few of GDash's
close to them: the clock (BonusTime: its seconds), the nut, expanding
walls, slime (SlimePermeabilityC64: how seldom it lets something through)
and the hidden exit; their rules are Boulder Dash 1's, in milliseconds.
mkcave.py also still reads the game's older text files (.cave, see
tools/cavekit.py's parse_cave_text), which tools/cavekit.py converts to .bd.

Writes <outdir>/caveNN-L.bin for each cave and level (NN from 01, in the
given order, L from 1), which build.sh puts on the disk as CAVENN-L,
<outdir>/caves.c and caves.h with all of them for tools/solve.c,
<outdir>/ownNN.bin, the empty slots for the own caves (OWNNN on the disk,
OWN_SLOTS of them; their layout is tools/cavekit.py's GdCaveFile),
<gendir>/levels.h with the number of caves, levels and slots for the game,
and <gendir>/gdcave.h, gdcave.c and gdnew.h for GDash's engine
(src/gdengine.c) and the editor. A cave file is a PRG: two bytes of
load address (not used, the game gives its own), then the cave as GDash's
engine plays it - the own caves' layout (GdCaveFile, tools/cavekit.py's
GD_FIELDS).

The game loads cave after cave until there is no next file; then it goes on
with the first cave of the next level (and stays in the last level).
"""

import re
import sys
import zlib

import cavekit as ck
from cavekit import GD_SIZE, Cave, CaveError, check_map, gd_from_cave, parse_cave_text, write_c

W, H = 40, 22
NAME_LEN = 21  # "CAVE 12/3 " before it in the status line
LEVELS = 4
OWN_SLOTS = 20  # the editor's slots on the disk: as many caves as Boulder Dash 1
SCALED = ("time", "diamonds", "speed", "amoeba", "magic")
FILL = ".rd "  # what the random fill of a cave is made of
KEYS = {"name": None, "time": None, "diamonds": None, "value": None,
        "extra": None, "speed": None, "amoeba": "0", "magic": "0",
        "clock": "10", "slime": "7", "demo": "", "shuffle": ""}


def fail(path, msg):
    sys.exit(f"{path}: {msg}")


def load(path):
    keys = dict(KEYS)
    try:
        given, rows = parse_cave_text(path)
    except CaveError as e:
        sys.exit(str(e))
    keys.update(given)
    for k, v in keys.items():
        if v is None:
            fail(path, f"'{k}' missing")
    for k in SCALED:
        v = [int(n) for n in keys[k].split()]
        if len(v) == 1:
            v = [level_value(k, v[0], lv) for lv in range(LEVELS)]
        if len(v) != LEVELS:
            fail(path, f"'{k}' needs one value or {LEVELS}")
        keys[k] = v
    sh = keys["shuffle"].split()
    if sh == ["no"]:
        keys["shuffle"] = None
    elif not sh:
        keys["shuffle"] = [zlib.crc32(f"{keys['name']}/{lv}".encode()) for lv in range(1, LEVELS)]
    elif len(sh) == LEVELS - 1 and all(n.isdigit() for n in sh):
        keys["shuffle"] = [int(n) for n in sh]
    else:
        fail(path, f"shuffle: 'no' or {LEVELS - 1} seeds")
    if re.search(r"[^0-9URDLurdl. ]", keys["demo"]):
        fail(path, "demo: only U R D L u r d l . digits and spaces")
    keys["name"] = keys["name"].upper().replace("\\", "").replace('"', "")
    if len(keys["name"]) > NAME_LEN:
        fail(path, f"the name is longer than {NAME_LEN} characters")
    flat = "".join(rows)
    errors = check_map(list(flat))
    if errors:
        fail(path, errors[0])
    return keys, flat


def level_value(key, v, level):
    if key == "time":
        return max(5, round(v * (10 - level) / 50) * 5)
    if key == "diamonds":
        return round(v * (10 + level) / 10)
    if key == "speed":
        return v - 5 * level
    return v


def demo_path(flat, demo):
    """The cells Rockford walks through in the opening moves (as if
    nothing were in his way)"""
    p = flat.index("P")
    path = {p}
    for n, c in re.findall(r"(\d*)([URDL])", demo):
        for _ in range(int(n or 1)):
            p += {"U": -W, "R": 1, "D": W, "L": -1}[c]
            path.add(p)
    return path


def shuffle(flat, seed, demo):
    """The map of a higher level, as Boulder Dash 1 fills each level of a
    cave from its own seed: the dirt, boulders and emeralds of the fill
    swap places with others close by (up to three cells to the side, one
    up or down), so each part of the cave keeps its mix. Holes stay, and so
    does everything next to something that is not fill - walls, creatures,
    the exit, rooms and their doors -, around the inbox and along the way
    of the opening moves (demo), which then still work."""
    cells = list(flat)
    path = demo_path(flat, demo)

    def free(i):
        if cells[i] == " " or cells[i] not in FILL:
            return False
        x, y = i % W, i // W
        for dy in (-2, -1, 0, 1, 2):
            for dx in (-2, -1, 0, 1, 2):
                xx, yy = x + dx, y + dy
                if not (0 <= xx < W and 0 <= yy < H):
                    continue
                c = cells[yy * W + xx]
                if (abs(dx) <= 1 and abs(dy) <= 1 and yy * W + xx in path) or c == "P" or (abs(dx) <= 1 and abs(dy) <= 1 and c not in FILL):
                    return False
        return True

    movable = [free(i) for i in range(W * H)]
    rng = seed & 0xFFFFFFFF
    for i in range(W * H):
        if not movable[i]:
            continue
        near = [j for dy in (-W, 0, W) for dx in range(-3, 4)
                if 0 <= (j := i + dy + dx) < W * H and abs(j % W - i % W) <= 3 and movable[j]]
        rng = (rng * 1103515245 + 12345) & 0xFFFFFFFF
        j = near[(rng >> 16) % len(near)]
        cells[i], cells[j] = cells[j], cells[i]
    return "".join(cells)


def variants(keys, flat):
    """The cave in each level: (keys with single values, map)"""
    out = []
    for lv in range(LEVELS):
        k = dict(keys)
        for key in SCALED:
            k[key] = keys[key][lv]
        out.append((k, shuffle(flat, keys["shuffle"][lv - 1], keys["demo"]) if lv and keys["shuffle"] else flat))
    return out


def gd_cave(keys, flat):
    """The cave in a level as GDash's engine plays it (tools/cavekit.py's
    layout, GdCaveFile): Boulder Dash 1's rules, in milliseconds"""
    cave = Cave(keys["name"], int(keys["time"]), int(keys["diamonds"]), int(keys["value"]), int(keys["extra"]),
                int(keys["speed"]), int(keys["amoeba"]), int(keys["magic"]), list(flat), int(keys["clock"]),
                int(keys["slime"]))
    data = gd_from_cave(cave).tobytes()
    assert len(data) == GD_SIZE
    return data


def read_moves(path):
    """The opening moves of a .moves file (its comments, # to the end of a
    line, and lines that start with = left out), or none"""
    try:
        text = open(path).read()
    except FileNotFoundError:
        return ""
    lines = [line.split("#")[0].strip() for line in text.splitlines()]
    moves = " ".join(line for line in lines if line and not line.startswith("="))
    if re.search(r"[^0-9URDLurdl. ]", moves):
        fail(path, "only U R D L u r d l . digits and spaces")
    return moves


def load_bd(path):
    """A cave of the game as GDash's file (.bd): its name, its opening moves
    (the .moves file beside it) and its file in each level. The values of
    each level are the file's; the map is the one drawn, and in the higher
    levels its fill is shuffled (shuffle()) as RandSeed says: without it
    from the name, with it each level from its own value, unless that is
    level 1's (then the map stays)."""
    try:
        bd = ck.BdcffFile(path)
    except (CaveError, OSError) as e:
        fail(path, str(e))
    if len(bd.caves) != 1:
        fail(path, "one cave to a file")
    cave = bd.caves[0]
    demo = read_moves(path[:-3] + ".moves")
    try:
        gds = [ck.gd_cave(bd, cave, lv) for lv in range(LEVELS)]
    except CaveError as e:
        fail(path, str(e))
    name = gds[0].name
    if not name or len(name) > NAME_LEN:
        fail(path, f"a name of 1 to {NAME_LEN} characters is needed")
    if (gds[0].v["w"], gds[0].v["h"]) != (W, H):
        fail(path, f"the cave must be {W}x{H} cells")
    seeds = cave.stored.v["level_rand"]
    to_char = {ck.GD_CHAR[c]: c for c in ck.CAVE_CHARS} | {ck.O[n]: c for c, n in ck.CAVE_OWN_CHARS.items()}
    to_code = {c: e for e, c in to_char.items()}
    files = []
    for lv, gd in enumerate(gds):
        if lv:
            if cave.prop("RandSeed") is None:
                seed = zlib.crc32(f"{name}/{lv}".encode())
            else:
                seed = None if seeds[lv] == seeds[0] else seeds[lv]
            if seed is not None:
                flat = "".join(to_char.get(e, chr(0x100 + e)) for e in gd.cells)
                gd.cells = [to_code.get(c, ord(c) - 0x100) for c in shuffle(flat, seed, demo)]
        data = gd.tobytes()
        assert len(data) == GD_SIZE
        files.append(data)
    return name, demo, files


def load_any(path):
    """A cave of the game, .bd or .cave: (name, opening moves, file per level)"""
    if path.lower().endswith(".bd"):
        return load_bd(path)
    keys, flat = load(path)
    return keys["name"], keys["demo"], [gd_cave(k, f) for k, f in variants(keys, flat)]


def main():
    outdir, gendir, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
    caves = [load_any(p) for p in paths]
    files = [data for _, _, data in caves]  # [cave][level]
    for i, cave in enumerate(files):
        for lv, data in enumerate(cave):
            with open(f"{outdir}/cave{i + 1:02d}-{lv + 1}.bin", "wb") as f:
                f.write(bytes([0x00, 0x20]) + data)  # load address: not used
    for n in range(1, OWN_SLOTS + 1):
        with open(f"{outdir}/own{n:02d}.bin", "wb") as f:
            f.write(bytes(2 + GD_SIZE))  # time 0: empty
    write_c(gendir)  # the own caves' layout and GDash's elements, for src/gdengine.c
    with open(f"{gendir}/levels.h", "w") as f:
        f.write("// Generated by tools/mkcave.py - do not edit\n#ifndef LEVELS_H\n#define LEVELS_H\n\n")
        f.write(f"#define CAVE_COUNT {len(caves)}  // caves on the disk (CAVE01-1, ...)\n")
        f.write(f"#define LEVELS     {LEVELS}  // levels of each\n")
        f.write(f"#define OWN_SLOTS  {OWN_SLOTS}  // the editor's slots (OWN01, ...)\n\n#endif\n")
    with open(f"{outdir}/caves.h", "w") as f:
        f.write("// Generated by tools/mkcave.py - do not edit\n#ifndef CAVES_H\n#define CAVES_H\n")
        f.write('#include "gdcave.h"\n\n')
        f.write(f"#define CAVE_COUNT {len(caves)}\n#define LEVELS     {LEVELS}\n")
        f.write("extern const GdCaveFile *const caves[LEVELS][CAVE_COUNT];\n")
        f.write("extern const char *const cave_demo[CAVE_COUNT];  // opening moves\n\n#endif\n")
    with open(f"{outdir}/caves.c", "w") as f:
        f.write('// Generated by tools/mkcave.py - do not edit\n#include "caves.h"\n\n')
        for i, cave in enumerate(files):
            for lv, data in enumerate(cave):
                f.write(f"static const uint8_t file{i}_{lv}[{GD_SIZE}] = {{\n")
                for o in range(0, GD_SIZE, 20):
                    f.write("    " + ", ".join(str(b) for b in data[o:o + 20]) + ",\n")
                f.write("};\n\n")
        f.write("const GdCaveFile *const caves[LEVELS][CAVE_COUNT] = {\n")
        for lv in range(LEVELS):
            f.write("    {" + ", ".join(f"(const GdCaveFile *)file{i}_{lv}" for i in range(len(files))) + "},\n")
        f.write("};\n\nconst char *const cave_demo[CAVE_COUNT] = {\n")
        for _, demo, _ in caves:
            f.write(f'    "{demo}",\n')
        f.write("};\n")
    print(f"mkcave: {len(caves)} cave(s) in {LEVELS} levels")


if __name__ == "__main__":
    main()
