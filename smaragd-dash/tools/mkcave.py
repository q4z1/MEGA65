#!/usr/bin/env python3
"""Smaragd Dash caves: turns the caves of the game - GDash's files (.bd,
BDCFF), a game of caves each - into the files the game loads from the disk,
and into C for the tools on the host.

Usage: mkcave.py <outdir> <gendir> <game.bd>...   (in the order they are played)

The game plays the caves of the files one after the other, each in GDash's
LEVELS levels, as GDash draws and starts them (tools/cavekit.py's gd_cave):
its objects, random fills and values of each level. A level the same as
the cave's first gets no file of its own; the game plays the first's.

The moves the screencast and the solver (tools/solve.c) start a cave with -
for what the solver cannot find by itself: dropping boulders on purpose,
pushing - are in a .moves file beside its .bd, named after the file and the
cave's number in it (caves/CWS_Boulder-03.moves; as tools/democave.py has
them: U R D L walk, u r d l snap, . wait one tick, a number repeats what
follows, # a comment).

Writes <outdir>/caveNN-L.bin for each cave and level it has a file for (NN
from 01, in the given order, L from 1), which build.sh puts on the disk as
CAVENN-L, <outdir>/caves.c and caves.h with all of them for tools/solve.c,
<outdir>/ownNN.bin, the empty slots for the own caves (OWNNN on the disk,
OWN_SLOTS of them; their layout is tools/cavekit.py's GdCaveFile), and
ownNN-L.bin for their other levels (OWNNN-L, L from 2 to LEVELS: GDash's
levels; a cave whose level L is not its first level has it there),
<gendir>/levels.h with the number of caves, levels and slots and the levels
each cave has a file for, for the game, and <gendir>/gdcave.h, gdcave.c and
gdnew.h for GDash's engine (src/gdengine.c) and the editor. A cave file is a
PRG: two bytes of load address (not used, the game gives its own), then the
cave as GDash's engine plays it - the own caves' layout (GdCaveFile,
tools/cavekit.py's GD_FIELDS).

The game loads cave after cave up to the last; then it goes on with the
first cave of the next level (and stays in the last level).
"""

import os
import re
import sys

import cavekit as ck
from cavekit import GD_SIZE, CaveError, write_c

NAME_LEN = 21  # "CAVE 12/3 " before it in the status line
LEVELS = ck.LEVELS  # GDash's
OWN_SLOTS = 20  # the editor's slots on the disk: as many caves as Boulder Dash 1
START_STEP = 5  # the title offers every fifth cave to start with - an intermission's next one


def fail(path, msg):
    sys.exit(f"{path}: {msg}")


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
    """The caves of a game as GDash's file (.bd): for each its name, its
    opening moves and its file in each level"""
    try:
        bd = ck.BdcffFile(path)
    except (CaveError, OSError) as e:
        fail(path, str(e))
    out = []
    for i, cave in enumerate(bd.caves):
        where = f"{path}, cave {i + 1}"
        try:
            gds = [ck.gd_cave(bd, cave, lv) for lv in range(LEVELS)]
        except CaveError as e:
            fail(where, str(e))
        name = gds[0].name
        if not name or len(name) > NAME_LEN:
            fail(where, f"a name of 1 to {NAME_LEN} characters is needed")
        demo = read_moves(f"{os.path.splitext(path)[0]}-{i + 1:02d}.moves")
        files = [gd.tobytes() for gd in gds]
        assert all(len(data) == GD_SIZE for data in files)
        out.append((name, demo, files, gds[0].v["intermission"]))
    return out


def main():
    outdir, gendir, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
    caves = [cave for p in paths for cave in load_bd(p)]
    if len(caves) > 99:
        sys.exit("mkcave: more than 99 caves (CAVE01 ... CAVE99)")
    files = [data for _, _, data, _ in caves]  # [cave][level]
    # the caves to start with: every START_STEP-th, or the first after it
    # that is not an intermission (none if there is none before the next)
    starts = [next(i for i in range(k, min(k + START_STEP, len(caves))) if not caves[i][3])
              for k in range(0, len(caves), START_STEP)
              if any(not c[3] for c in caves[k:k + START_STEP])]
    # the levels each cave has a file of its own for: bit L for level L + 1
    have = [sum(1 << lv for lv, data in enumerate(cave) if lv == 0 or data != cave[0]) for cave in files]
    for i, cave in enumerate(files):
        for lv, data in enumerate(cave):
            if have[i] >> lv & 1:
                with open(f"{outdir}/cave{i + 1:02d}-{lv + 1}.bin", "wb") as f:
                    f.write(bytes([0x00, 0x20]) + data)  # load address: not used
    for n in range(1, OWN_SLOTS + 1):
        for lv in range(1, LEVELS + 1):
            with open(f"{outdir}/own{n:02d}{f'-{lv}' if lv > 1 else ''}.bin", "wb") as f:
                f.write(bytes(2 + GD_SIZE))  # time 0: empty
    write_c(gendir)  # the own caves' layout and GDash's elements, for src/gdengine.c
    with open(f"{gendir}/levels.h", "w") as f:
        f.write("// Generated by tools/mkcave.py - do not edit\n#ifndef LEVELS_H\n#define LEVELS_H\n\n")
        f.write(f"#define CAVE_COUNT {len(caves)}  // caves on the disk (CAVE01-1, ...)\n")
        f.write(f"#define LEVELS     {LEVELS}  // levels of each, GDash's\n")
        f.write(f"#define OWN_SLOTS  {OWN_SLOTS}  // the editor's slots (OWN01, ...)\n")
        f.write(f"#define OWN_LEVELS {LEVELS}  // their levels (OWN01-2, ...)\n")
        f.write("// the levels each cave has a file for (bit L: CAVENN-(L+1)); the\n"
                "// others play the first level's\n")
        f.write(f"#define START_COUNT {len(starts)}  // the caves to start with (from 0)\n")
        f.write("#define CAVE_STARTS {" + ", ".join(str(n) for n in starts) + "}\n")
        f.write("#define CAVE_LEVELS { \\\n")
        for i in range(0, len(have), 16):
            f.write("    " + ", ".join(f"0x{h:02x}" for h in have[i:i + 16]) + ", \\\n")
        f.write("}\n\n#endif\n")
    with open(f"{outdir}/caves.h", "w") as f:
        f.write("// Generated by tools/mkcave.py - do not edit\n#ifndef CAVES_H\n#define CAVES_H\n")
        f.write('#include "gdcave.h"\n\n')
        f.write(f"#define CAVE_COUNT {len(caves)}\n#define LEVELS     {LEVELS}\n")
        f.write("// a level the same as the first is the first's file\n")
        f.write("extern const GdCaveFile *const caves[LEVELS][CAVE_COUNT];\n")
        f.write("extern const char *const cave_demo[CAVE_COUNT];  // opening moves\n\n#endif\n")
    with open(f"{outdir}/caves.c", "w") as f:
        f.write('// Generated by tools/mkcave.py - do not edit\n#include "caves.h"\n\n')
        for i, cave in enumerate(files):
            for lv, data in enumerate(cave):
                if have[i] >> lv & 1:
                    f.write(f"static const uint8_t file{i}_{lv}[{GD_SIZE}] = {{\n")
                    for o in range(0, GD_SIZE, 20):
                        f.write("    " + ", ".join(str(b) for b in data[o:o + 20]) + ",\n")
                    f.write("};\n\n")
        f.write("const GdCaveFile *const caves[LEVELS][CAVE_COUNT] = {\n")
        for lv in range(LEVELS):
            f.write("    {" + ", ".join(f"(const GdCaveFile *)file{i}_{lv if have[i] >> lv & 1 else 0}"
                                        for i in range(len(files))) + "},\n")
        f.write("};\n\nconst char *const cave_demo[CAVE_COUNT] = {\n")
        for _, demo, _, _ in caves:
            f.write(f'    "{demo}",\n')
        f.write("};\n")
    print(f"mkcave: {len(caves)} cave(s) in {LEVELS} levels, {sum(bin(h).count('1') for h in have)} files")


if __name__ == "__main__":
    main()
