#!/usr/bin/env python3
"""Smaragd Dash: the demo caves (demo/*.bd, GDash's files) and their moves
(demo/*.moves), played on the host with GDash's engine as the game has it
(src/gdengine.c with the game's random numbers, started as the screencast
build starts it: seed 0), step by step as on the MEGA65.

  democave.py play <cave.bd | disk.d81> <moves> [--every N] [--cave N]
      plays the moves and tells how it ends; the map wherever the moves say
      "!" (and every N steps); the cave as for solve
  democave.py pack <cave.bd> <moves> <out.bin>
      the moves as the screencast build loads them (tools/record-tour.sh)
  democave.py solve <cave.bd | disk.d81> <out.bin> [--cave N] [--moves FILE]
      a way through the cave (of a .bd file: its N-th, of a disk: slot N,
      level 1) found by tools/solve.c (build/solve, made by build.sh),
      from where the moves of FILE end (if given): what the search cannot
      find by itself - dropping boulders on purpose, say - FILE shows it
      the way (tools/record-solutions.sh)

The moves: U R D L walk, u r d l the same with fire (snap; place a bomb,
fire a rocket, use the hammer), . wait a step, X give up (Run/Stop:
GDash's suicide), a number repeats what
follows, a * after a move repeats it until Rockford gets there (pushing
works only now and then), @x,y walks to that cell the shortest way through
space, dirt and emeralds (waiting while there is none); # starts a comment,
! shows the map there. They
start when Rockford stands in the cave; the steps before (hatching, being
born out of the inbox) are added. A line that starts with = says what must
be so at that point (Play.check), e.g. "= key1=1 @12,5=DIAMOND st=out".
A line that starts with % gives tools/solve.c's search (solve) its
settings, e.g. "% beam=6000 cell=8" (its SOLVE_BEAM, SOLVE_CELL, ...).

A demo file holds the input of every step from the start of the cave, as
tools/solve.c writes them: two bytes of load address (not used), then
pairs of (count, input) with input as main.c's rules_tick takes it
(DIR_* | IN_FIRE), closed by a count of 0.
"""

import ctypes
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import cavekit as ck  # noqa: E402

GEN = os.path.join(ROOT, "build", "democave")
DIR_NONE, IN_FIRE, IN_SUICIDE = 4, 8, 16
STATES = ["not born", "living", "out of time", "dead", "out"]


def library(variant="", cflags=()):
    """The engine as a shared library, made anew when a source changed;
    a variant (its own directory in build/democave) with other cflags:
    GD_EXACT for GDash's random numbers, --coverage (tests/test_mechanics.py)"""
    gen = os.path.join(GEN, variant)
    lib_path = os.path.join(gen, "democave.so")
    os.makedirs(gen, exist_ok=True)
    srcs = [os.path.join(ROOT, "src", f) for f in ("gdengine.c", "gdengine.h", "engine.h")] + \
        [os.path.join(HERE, f) for f in ("democave_lib.c", "cavekit.py")]
    if not os.path.exists(lib_path) or os.path.getmtime(lib_path) < max(os.path.getmtime(f) for f in srcs):
        ck.write_c(gen)
        cc = subprocess.run(["cc", "-shared", "-fPIC", "-O2", "-w", *cflags, "-I" + os.path.join(ROOT, "src"),
                             "-I" + gen, "-o", lib_path, os.path.join(HERE, "democave_lib.c"),
                             os.path.join(ROOT, "src", "gdengine.c"), os.path.join(gen, "gdcave.c")],
                            capture_output=True, text=True, cwd=gen)
        if cc.returncode:
            sys.exit(cc.stderr)
    lib = ctypes.CDLL(lib_path)
    lib.dc_cave.restype = ctypes.POINTER(ctypes.c_uint8 * (ck.W * ck.H))
    lib.dc_sound.restype = ctypes.c_ulong
    return lib


def read_moves(path):
    """[(input, show the map before it, until Rockford moves, what must be so
    before it)] of a moves file; input None: the end"""
    out, show, expect = [], False, []
    for line in open(path).read().splitlines():
        line = line.split("#")[0].strip()
        if line.startswith("%"):
            continue
        if line.startswith("="):
            expect += [tuple(w.split("=", 1)) for w in line[1:].split()]
            continue
        for gx, gy, n, c, until in re.findall(r"@(\d+),(\d+)|(\d*)([URDLurdl.!X])(\*?)", line):
            if gx:
                out.append((("goto", int(gx), int(gy)), show, False, expect))
                show, expect = False, []
                continue
            if c == "!":
                show = True
                continue
            if c == ".":
                inp = DIR_NONE
            elif c == "X":
                inp = DIR_NONE | IN_SUICIDE
            elif c in "URDL":
                inp = "URDL".index(c)
            else:
                inp = "urdl".index(c) | IN_FIRE
            for _ in range(int(n or 1)):
                out.append((inp, show, bool(until), expect))
                show, expect = False, []
    out.append((None, show, False, expect))
    return out


# What a "=" line of the moves can ask for: a value of dc_line, by its name
# there (st, dia: the emeralds collected, keys, ...) or one of these, an
# element anywhere (has=NAME, no=NAME) or in a cell (@x,y=NAME; NAME* for
# any whose name starts so), or a sound heard since the last "=" line
# (heard=PICKUP: src/engine.h's SND_PICKUP)
EXPECT_STATES = {"born": 0, "living": 1, "timeout": 2, "dead": 3, "out": 4}
EXPECT_VALUES = {
    "amoeba": ["sleeping", "awake", "toobig", "enclosed"], "amoeba2": ["sleeping", "awake", "toobig", "enclosed"],
    "magic": ["dormant", "active", "expired"],
    "grav": {"still": "0", "up": "1", "right": "3", "down": "5", "left": "7"},
}
SWITCHES = ["backwards", "expwall", "replicators", "conveyors", "convdir", "gravswitch"]
SOUNDS = {m[0]: int(m[1], 16) for m in re.findall(r"#define SND_(\w+) +0x([0-9A-Fa-f]+)",
                                                   open(os.path.join(ROOT, "src", "engine.h")).read())}


def read_cave(path, cave=1):
    """The cave of a .bd file (the N-th) or a disk (slot N, level 1)"""
    if path.lower().endswith(".d81"):
        found = ck.read_slot(ck.Disk(path), f"{ck.SLOT}{cave:02d}")
        if not found:
            sys.exit(f"{path}: slot {cave} is empty")
        return found
    _, caves = ck.read_bd(path, 0)
    if len(caves) < cave or isinstance(caves[cave - 1][2], ck.CaveError):
        sys.exit(f"{path}: {caves[cave - 1][2] if len(caves) >= cave else 'no cave ' + str(cave)}")
    return caves[cave - 1][2]


class Play:
    def __init__(self, bd_path, lib=None, cave=1):
        """bd_path: a .bd file or a disk (read_cave), or a GdCave"""
        self.cave = bd_path if isinstance(bd_path, ck.GdCave) else read_cave(bd_path, cave)
        self.raw = ctypes.create_string_buffer(self.cave.tobytes())
        self.lib = lib or library()
        self.lib.dc_start(self.raw, 0)
        self.inputs = []
        self.lines = []  # dc_line after each step, if the library has it
        self.heard = 0   # the sounds since the last check (SND_*)
        self.state = (ctypes.c_int * 15)()
        self.buf = ctypes.create_string_buffer(256)

    def st(self):
        self.lib.dc_state(self.state)
        return list(self.state)

    def step(self, inp):
        self.lib.dc_step(inp & 7, inp & IN_FIRE, inp & IN_SUICIDE)
        self.lib.dc_line(len(self.inputs), self.buf, len(self.buf))
        self.lines.append(self.buf.value.decode())
        self.heard |= self.lib.dc_sound()
        self.inputs.append(inp)

    def values(self):
        """dc_line's values by name, of the last step"""
        self.lib.dc_line(len(self.inputs), self.buf, len(self.buf))
        words = self.buf.value.decode().split()[2:]
        v = dict(w.split("=") for w in words)
        v["dia"], v["needed"] = v["dia"].split("/")
        v["key1"], v["key2"], v["key3"] = v.pop("keys").split(",")
        v["amoeba"], v["amoeba2"] = v["amoeba"].split(",")
        v.update(zip(SWITCHES, v.pop("sw")))
        return v

    def check(self, expect):
        """What of expect ([(name, value)]) is not so, as text"""
        v, cells, bad = self.values(), self.lib.dc_cave().contents, []
        for name, want in expect:
            if name.startswith("@"):
                x, y = (int(n) for n in name[1:].split(","))
                got = ck.GD_EL[cells[y * ck.W + x]].name
            elif name == "heard":
                got = "yes" if self.heard & SOUNDS[want] else "no"
                sound, want = want, "yes"
            elif name in ("has", "no"):
                there = {ck.GD_EL[cells[y * ck.W + x]].name
                         for y in range(self.cave.v["h"]) for x in range(self.cave.v["w"])}
                found = any(n.startswith(want[:-1]) for n in there) if want.endswith("*") else want in there
                got, want = ("yes" if found else "no"), ("yes" if name == "has" else "no")
            elif name == "st":
                got, want = v["st"], str(EXPECT_STATES[want])
            elif name in EXPECT_VALUES:
                names = EXPECT_VALUES[name]
                got, want = v[name], names[want] if isinstance(names, dict) else str(names.index(want))
            else:
                got = v[name]
            if got != want and not (want.endswith("*") and got.startswith(want[:-1])):
                bad.append(f"step {len(self.inputs)}: {name} {got}, not {want}" if name != "heard" else
                           f"step {len(self.inputs)}: not heard: {sound}")
        if expect:
            self.heard = 0
        return bad

    def born(self):
        """Steps until Rockford stands in the cave (or is dead already)"""
        while True:
            s = self.st()
            cells = self.lib.dc_cave().contents
            if s[0] == 1 and cells[s[2] * ck.W + s[1]] == ck.O["PLAYER"] or s[0] > 1:
                return
            if len(self.inputs) > 500:
                sys.exit("Rockford is not born")
            self.step(DIR_NONE)

    def walk(self, x, y):
        """Steps to cell x, y (@x,y in the moves): each one the first of a
        shortest way through space, dirt and emeralds; what went wrong"""
        through = {ck.O["SPACE"], ck.O["DIRT"], ck.O["DIAMOND"]}
        waited = 0
        for _ in range(400):
            s = self.st()
            if s[0] != 1 or (s[1], s[2]) == (x, y):
                break
            cells = self.lib.dc_cave().contents
            # breadth first from the target, so that every cell knows its way
            dist = {(x, y): 0}
            todo = [(x, y)]
            for cx, cy in todo:
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) not in dist and 0 <= nx < ck.W and 0 <= ny < ck.H and \
                            cells[ny * ck.W + nx] in through:
                        dist[(nx, ny)] = dist[(cx, cy)] + 1
                        todo.append((nx, ny))
            best = None
            for d, (dx, dy) in enumerate(((0, -1), (1, 0), (0, 1), (-1, 0))):
                k = dist.get((s[1] + dx, s[2] + dy))
                if k is not None and (best is None or k < best[0]):
                    best = (k, d)
            if best is None:
                waited += 1
                if waited > 50:
                    return [f"step {len(self.inputs)}: no way to {x},{y}"]
                self.step(DIR_NONE)
            else:
                self.step(best[1])
        s = self.st()
        return [] if (s[1], s[2]) == (x, y) or s[0] == 4 else [f"step {len(self.inputs)}: not at {x},{y}"]

    def show(self, note=""):
        s = self.st()
        cells = list(self.lib.dc_cave().contents)
        native = {ck.GD_EL[e].char for e in cells}
        legend = {}
        spare = iter(c for c in "abcefghijklmnopstuvxyzABDEFGHIJKLNRSTUVYZ0123456789$%&*+-=?" if c not in native)
        rows = []
        for y in range(self.cave.v["h"]):
            row = ""
            for x in range(self.cave.v["w"]):
                e = cells[y * ck.W + x]
                if (x, y) == (s[1], s[2]):
                    row += "@"
                    continue
                c = ck.GD_EL[e].char
                if not c or c in "@":
                    name = ck.GD_EL[e].name
                    if name not in legend:
                        legend[name] = next(spare, "?")
                    c = legend[name]
                row += c
            rows.append(row)
        print(f"-- step {len(self.inputs)} {note}")
        print("\n".join(rows))
        if legend:
            print("   " + ", ".join(f"{c}={n}" for n, c in legend.items()))
        print(f"   {STATES[s[0]]} at {s[1]},{s[2]}; {s[3]}/{s[4]} emeralds{', exit open' if s[5] else ''}, "
              f"{s[6]} s; keys {s[8]} {s[9]} {s[10]}, sweet {s[11]}, hammer {s[12]}")


def play(bd_path, moves_path, every=0, lib=None, cave=1, quiet=False, after=10):
    """The moves played; (Play, out, what was not as the moves say);
    after: the steps that are waited for what happens next"""
    p = Play(bd_path, lib, cave)
    p.born()
    bad = []
    for inp, show, until, expect in read_moves(moves_path):
        if show and not quiet:
            p.show()
        bad += p.check(expect)
        if inp is None:
            break
        if isinstance(inp, tuple):
            bad += p.walk(inp[1], inp[2])
            continue
        at = p.st()[1:3]
        for _ in range(100 if until else 1):
            if until and p.st()[0] != 1:  # the cave goes on after Rockford, as in GDash
                break
            p.step(inp)
            if every and not quiet and len(p.inputs) % every == 0:
                p.show()
            if p.st()[1:3] != at:
                break
    for _ in range(after):  # what happens next
        if p.st()[0] != 1:
            break
        p.step(DIR_NONE)
    s = p.st()
    if not quiet:
        print(f"{STATES[s[0]]} after {len(p.inputs)} steps: {s[3]}/{s[4]} emeralds, {s[6]} s left")
        for b in bad:
            print("  not as the moves say: " + b)
    return p, s[0] == 4, bad


def pack(inputs):
    if any(inp & IN_SUICIDE for inp in inputs):
        sys.exit("democave: a demo file has no X")
    out = bytearray([0x00, 0x20])
    i = 0
    while i < len(inputs):
        n = 1
        while i + n < len(inputs) and n < 255 and inputs[i + n] == inputs[i]:
            n += 1
        out += bytes([n, inputs[i]])
        i += n
    out.append(0)
    return bytes(out)


def solve(path, out_path, cave=1, moves_path=None):
    """tools/solve.c's way through the cave, from where the moves end"""
    solver = os.path.join(ROOT, "build", "solve")
    if not os.path.exists(solver):
        sys.exit("democave: no build/solve - ./build.sh makes it")
    first = []
    if moves_path:
        p, _, bad = play(path, moves_path, cave=cave, quiet=True, after=0)
        if bad or p.st()[0] not in (1, 4):
            sys.exit(f"democave: {moves_path}: " + ("; ".join(bad) or "Rockford does not survive the moves"))
        first = p.inputs
    gen = os.path.join(GEN, "solve", os.path.basename(out_path))  # one each: several run at once
    os.makedirs(gen, exist_ok=True)
    with open(os.path.join(gen, "cave.bin"), "wb") as f:
        f.write(read_cave(path, cave).tobytes())
    with open(os.path.join(gen, "opening.bin"), "wb") as f:
        f.write(bytes(first))
    env = dict(os.environ)
    for line in open(moves_path).read().splitlines() if moves_path else []:
        if line.startswith("%"):
            env.update(("SOLVE_" + k.upper(), v) for k, v in (w.split("=") for w in line[1:].split()))
    run = subprocess.run([solver, "--own", os.path.join(gen, "cave.bin"), os.path.join(gen, "opening.bin"),
                          out_path], capture_output=True, text=True, env=env)
    print(run.stdout.strip())
    return run.returncode == 0


def main():
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "play":
        every = int(args[args.index("--every") + 1]) if "--every" in args else 0
        cave = int(args[args.index("--cave") + 1]) if "--cave" in args else 1
        _, ok, bad = play(args[1], args[2], every, cave=cave)
        return 0 if ok and not bad else 1
    if len(args) == 4 and args[0] == "pack":
        p, ok, bad = play(args[1], args[2])
        if not ok or bad:
            sys.exit("democave: Rockford does not get out" if not ok else "democave: not as the moves say")
        with open(args[3], "wb") as f:
            f.write(pack(p.inputs))
        print(f"{args[3]}: {len(p.inputs)} steps")
        return 0
    if len(args) >= 3 and args[0] == "solve":
        cave = int(args[args.index("--cave") + 1]) if "--cave" in args else 1
        moves = args[args.index("--moves") + 1] if "--moves" in args else None
        return 0 if solve(args[1], args[2], cave, moves) else 1
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
