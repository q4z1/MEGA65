#!/usr/bin/env python3
"""Smaragd Dash caves: turns the .cave text files into the files the game
loads from the disk, and into C for the tools on the host.

Usage: mkcave.py <outdir> <file.cave>...   (in the order they are played)

Writes <outdir>/caveNN.bin for each cave (NN from 01, in the given order),
which build.sh puts on the disk as CAVENN, and <outdir>/caves.c and caves.h
with all caves for tools/solve.c. A cave file is a PRG: two bytes of load
address (not used, the game gives its own), then

  0-1   time in seconds      5  amoeba
  2     diamonds needed      6  magic
  3     value                7  speed
  4     extra                8-31   name, closed by 0
  32-911  the map, 40x22 cells as E_* codes (src/engine.h)

The game loads cave after cave until there is no next file; then it starts
again with CAVE01.

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
            tick, a number repeats what follows; spaces are ignored

Map characters:
  W steel wall    w brick wall    . dirt      (space) empty
  r boulder       d diamond       P inbox     X outbox (in a wall)
  q firefly (starts moving left)  B butterfly (starts moving down)
  a amoeba        m magic wall
"""

import re
import sys

W, H = 40, 22
NAME_LEN = 23
ELEM = {
    "W": "E_STEEL", "w": "E_BRICK", ".": "E_DIRT", " ": "E_SPACE",
    "r": "E_BOULDER", "d": "E_DIAMOND", "P": "E_INBOX", "X": "E_OUTBOX",
    "q": "E_FIREFLY + DIR_LEFT", "B": "E_BUTTERFLY + DIR_DOWN",
    "a": "E_AMOEBA", "m": "E_MAGIC",
}
KEYS = {"name": None, "time": None, "diamonds": None, "value": None,
        "extra": None, "speed": None, "amoeba": "0", "magic": "0",
        "demo": ""}


def fail(path, msg):
    sys.exit(f"{path}: {msg}")


def load(path):
    keys, rows, in_map = dict(KEYS), [], False
    for line in open(path, encoding="utf-8").read().splitlines():
        if in_map:
            if line.strip():
                rows.append(line)
            continue
        if not line.strip() or line.startswith("#"):
            continue
        if line.strip() == "map:":
            in_map = True
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k not in KEYS:
            fail(path, f"unknown key '{k}'")
        keys[k] = v.strip()
    for k, v in keys.items():
        if v is None:
            fail(path, f"'{k}' missing")
    if re.search(r"[^0-9URDLurdl. ]", keys["demo"]):
        fail(path, "demo: only U R D L u r d l . digits and spaces")
    keys["name"] = keys["name"].upper().replace("\\", "").replace('"', "")
    if len(keys["name"]) > NAME_LEN:
        fail(path, f"the name is longer than {NAME_LEN} characters")
    if len(rows) != H or any(len(r) != W for r in rows):
        fail(path, f"map must be {H} lines of {W} characters")
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch not in ELEM:
                fail(path, f"unknown map character '{ch}' at {x},{y}")
            edge = x in (0, W - 1) or y in (0, H - 1)
            if edge and ch not in "WX":
                fail(path, f"the frame must be steel (or the outbox), not '{ch}' at {x},{y}")
    flat = "".join(rows)
    if flat.count("P") != 1:
        fail(path, "exactly one inbox (P) needed")
    if flat.count("X") < 1:
        fail(path, "an outbox (X) is needed")
    return keys, flat


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
    return codes


def cave_file(keys, flat, codes):
    num = [int(keys[k]) for k in ("time", "diamonds", "value", "extra", "amoeba", "magic", "speed")]
    if not 0 < num[0] < 1000 or any(not 0 <= v < 256 for v in num[1:]):
        raise ValueError("numbers out of range")
    head = bytes([0x00, 0x20, num[0] & 255, num[0] >> 8] + num[1:])
    name = keys["name"].encode("ascii").ljust(NAME_LEN + 1, b"\0")
    cells = bytes(eval(ELEM[c], {}, codes) for c in flat)
    return head + name + cells


def main():
    outdir, files = sys.argv[1], sys.argv[2:]
    caves = [load(p) for p in files]
    codes = elements()
    for i, (k, flat) in enumerate(caves):
        with open(f"{outdir}/cave{i + 1:02d}.bin", "wb") as f:
            f.write(cave_file(k, flat, codes))
    with open(f"{outdir}/caves.h", "w") as f:
        f.write("// Generated by tools/mkcave.py - do not edit\n#ifndef CAVES_H\n#define CAVES_H\n")
        f.write('#include "engine.h"\n\n')
        f.write(f"#define CAVE_COUNT {len(caves)}\nextern const CaveDef caves[CAVE_COUNT];\n")
        f.write("extern const char *const cave_demo[CAVE_COUNT];  // opening moves\n\n#endif\n")
    with open(f"{outdir}/caves.c", "w") as f:
        f.write('// Generated by tools/mkcave.py - do not edit\n#include "caves.h"\n\n')
        for i, (_, flat) in enumerate(caves):
            f.write(f"static const uint8_t map{i}[CAVE_SIZE] = {{\n")
            for y in range(H):
                f.write("    " + ", ".join(ELEM[c] for c in flat[y * W:(y + 1) * W]) + ",\n")
            f.write("};\n\n")
        f.write("const CaveDef caves[CAVE_COUNT] = {\n")
        for i, (k, _) in enumerate(caves):
            f.write(f'    {{"{k["name"]}", map{i}, {k["time"]}, {k["diamonds"]}, {k["value"]}, '
                    f'{k["extra"]}, {k["amoeba"]}, {k["magic"]}, {k["speed"]}}},\n')
        f.write("};\n\nconst char *const cave_demo[CAVE_COUNT] = {\n")
        for k, _ in caves:
            f.write(f'    "{k["demo"]}",\n')
        f.write("};\n")
    print(f"mkcave: {len(caves)} cave(s)")


if __name__ == "__main__":
    main()
