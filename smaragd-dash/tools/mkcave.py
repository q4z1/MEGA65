#!/usr/bin/env python3
"""Smaragd Dash caves: turns the .cave text files into the files the game
loads from the disk, and into C for the tools on the host.

Usage: mkcave.py <outdir> <gendir> <file.cave>...   (in the order they are played)

Every cave comes in LEVELS levels, as in Boulder Dash 1: level 1 is the cave
as drawn, the higher ones give less time, ask for more emeralds, tick a
little faster and shuffle the cave's fill (see shuffle()).

Writes <outdir>/caveNN-L.bin for each cave and level (NN from 01, in the
given order, L from 1), which build.sh puts on the disk as CAVENN-L,
<outdir>/caves.c and caves.h with all of them for tools/solve.c,
<outdir>/ownNN.bin, the empty slots for the own caves (OWNNN on the disk,
OWN_SLOTS of them; their layout is tools/cavekit.py's GdCaveFile),
<gendir>/levels.h with the number of caves, levels and slots for the game,
and <gendir>/gdcave.h, gdcave.c and gdnew.h for GDash's engine
(src/gdengine.c) and the editor. A cave file is a PRG: two bytes of
load address (not used, the game gives its own), then

  0-1   time in seconds      5  amoeba
  2     diamonds needed      6  magic
  3     value                7  speed
  4     extra                8-31   name, closed by 0
  32-911  the map, 40x22 cells as E_* codes (src/engine.h)

The game loads cave after cave until there is no next file; then it goes on
with the first cave of the next level (and stays in the last level).

A .cave file has "key = value" lines, then "map:" and 22 lines of 40
characters. Lines starting with # are comments.

  name      shown in the status line (A-Z, 0-9, space, a few signs)
  time      seconds
  diamonds  diamonds needed to open the exit
  value     points per diamond until then
  extra     points per diamond after that
  speed     length of a cave tick in milliseconds (original: about 140)
  amoeba    seconds of slow amoeba growth (default 0)
  magic     seconds the magic wall stays active (default 0)
  demo      moves the screencast starts the cave with, for what
            tools/solve.c cannot find by itself (dropping boulders on
            purpose, pushing): U R D L walk, u r d l snap, . wait one
            tick, a number repeats what follows; spaces are ignored.
            The solver starts every level of the cave with them.
  shuffle   "no": the higher levels keep the map as drawn (where the
            fill is the idea); or a seed per higher level (default:
            from the name), to try another shuffle

time, diamonds, speed, amoeba and magic take one value, or one per level.
With one value the higher levels get, from level 1 on:
  time      100 90 80 70 %   (in steps of 5 seconds)
  diamonds  100 110 120 130 %
  speed     -0 -5 -10 -15 ms
amoeba and magic stay the same.

Map characters, the ones of BDCFF (GDash's files; tools/cavekit.py
converts between the two):
  W steel wall    w brick wall    . dirt      (space) empty
  r boulder       d diamond       P inbox     X outbox (in a wall)
  a amoeba        M magic wall
  fireflies starting to the left Q, up o, right O, down q
  butterflies starting to the left C, up b, right B, down c
"""

import re
import sys
import zlib

from cavekit import CHAR_EXPR, CODES, GD_SIZE, CaveError, check_map, parse_cave_text, write_c

W, H = 40, 22
NAME_LEN = 21  # "CAVE 12/3 " before it in the status line
NAME_FIELD = 24  # bytes 8-31 of the file, cave_file.name in src/main.c
LEVELS = 4
OWN_SLOTS = 20  # the editor's slots on the disk: as many caves as Boulder Dash 1
SCALED = ("time", "diamonds", "speed", "amoeba", "magic")
FILL = ".rd "  # what the random fill of a cave is made of
ELEM = CHAR_EXPR  # map character: E_* code, as C
KEYS = {"name": None, "time": None, "diamonds": None, "value": None,
        "extra": None, "speed": None, "amoeba": "0", "magic": "0",
        "demo": "", "shuffle": ""}


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


def elements():
    """E_* codes from src/engine.h, for the cave files"""
    src = open(f"{sys.path[0]}/../src/engine.h", encoding="utf-8").read()
    body = src[src.index("enum {\n    E_SPACE"):]
    body = body[:body.index("};")]
    codes, n = {}, 0
    for name, expr in re.findall(r"^\s+(E_\w+)(?:\s*=\s*([^,]+))?,", body, re.M):
        if expr:
            n = eval(expr.split("//")[0], {}, codes)
        codes[name] = n
        n += 1
    codes.update({f"DIR_{d}": i for i, d in enumerate(("UP", "RIGHT", "DOWN", "LEFT"))})
    for name, v in CODES.items():
        if codes[name] != v:
            sys.exit(f"mkcave: {name} is {codes[name]} in src/engine.h, {v} in tools/cavekit.py")
    return codes


def cave_file(keys, flat, codes):
    num = [int(keys[k]) for k in ("time", "diamonds", "value", "extra", "amoeba", "magic", "speed")]
    if not 0 < num[0] < 1000 or any(not 0 <= v < 256 for v in num[1:]):
        raise ValueError("numbers out of range")
    head = bytes([0x00, 0x20, num[0] & 255, num[0] >> 8] + num[1:])
    name = keys["name"].encode("ascii").ljust(NAME_FIELD, b"\0")
    cells = bytes(eval(ELEM[c], {}, codes) for c in flat)
    data = head + name + cells
    assert len(data) == 2 + 32 + W * H, "the file layout does not match the docstring"
    return data


def main():
    outdir, gendir, files = sys.argv[1], sys.argv[2], sys.argv[3:]
    caves = [load(p) for p in files]
    levels = [variants(k, flat) for k, flat in caves]  # [cave][level]
    codes = elements()
    for i, cave in enumerate(levels):
        for lv, (k, flat) in enumerate(cave):
            with open(f"{outdir}/cave{i + 1:02d}-{lv + 1}.bin", "wb") as f:
                f.write(cave_file(k, flat, codes))
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
        f.write('#include "engine.h"\n\n')
        f.write(f"#define CAVE_COUNT {len(caves)}\n#define LEVELS     {LEVELS}\n")
        f.write("extern const CaveDef caves[LEVELS][CAVE_COUNT];\n")
        f.write("extern const char *const cave_demo[CAVE_COUNT];  // opening moves\n\n#endif\n")
    with open(f"{outdir}/caves.c", "w") as f:
        f.write('// Generated by tools/mkcave.py - do not edit\n#include "caves.h"\n\n')
        for i, cave in enumerate(levels):
            for lv, (_, flat) in enumerate(cave):
                f.write(f"static const uint8_t map{i}_{lv}[CAVE_SIZE] = {{\n")
                for y in range(H):
                    f.write("    " + ", ".join(ELEM[c] for c in flat[y * W:(y + 1) * W]) + ",\n")
                f.write("};\n\n")
        f.write("const CaveDef caves[LEVELS][CAVE_COUNT] = {\n")
        for lv in range(LEVELS):
            f.write("    {\n")
            for i, cave in enumerate(levels):
                k = cave[lv][0]
                f.write(f'        {{"{k["name"]}", map{i}_{lv}, {k["time"]}, {k["diamonds"]}, '
                        f'{k["value"]}, {k["extra"]}, {k["amoeba"]}, {k["magic"]}, {k["speed"]}}},\n')
            f.write("    },\n")
        f.write("};\n\nconst char *const cave_demo[CAVE_COUNT] = {\n")
        for k, _ in caves:
            f.write(f'    "{k["demo"]}",\n')
        f.write("};\n")
    print(f"mkcave: {len(caves)} cave(s) in {LEVELS} levels")


if __name__ == "__main__":
    main()
