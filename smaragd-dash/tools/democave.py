#!/usr/bin/env python3
"""Smaragd Dash: the demo caves (demo/*.bd, GDash's files) and their moves
(demo/*.moves), played on the host with GDash's engine as the game has it
(src/gdengine.c with the game's random numbers, started as the screencast
build starts it: seed 0), step by step as on the MEGA65.

  democave.py play <cave.bd> <moves> [--every N]
      plays the moves and tells how it ends; the map wherever the moves say
      "!" (and every N steps)
  democave.py pack <cave.bd> <moves> <out.bin>
      the moves as the screencast build loads them (tools/record-tour.sh)

The moves: U R D L walk, u r d l the same with fire (snap; place a bomb,
fire a rocket, use the hammer), . wait a step, a number repeats what
follows, a * after a move repeats it until Rockford gets there (pushing
works only now and then); # starts a comment, ! shows the map there. They
start when Rockford stands in the cave; the steps before (hatching, being
born out of the inbox) are added.

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
LIB = os.path.join(GEN, "democave.so")
DIR_NONE, IN_FIRE = 4, 8
STATES = ["not born", "living", "out of time", "dead", "out"]


def library():
    """The engine as a shared library, made anew when a source changed"""
    os.makedirs(GEN, exist_ok=True)
    srcs = [os.path.join(ROOT, "src", f) for f in ("gdengine.c", "gdengine.h", "engine.h")] + \
        [os.path.join(HERE, f) for f in ("democave_lib.c", "cavekit.py")]
    if not os.path.exists(LIB) or os.path.getmtime(LIB) < max(os.path.getmtime(f) for f in srcs):
        ck.write_c(GEN)
        cc = subprocess.run(["cc", "-shared", "-fPIC", "-O2", "-w", "-I" + os.path.join(ROOT, "src"), "-I" + GEN,
                             "-o", LIB, os.path.join(HERE, "democave_lib.c"),
                             os.path.join(ROOT, "src", "gdengine.c"), os.path.join(GEN, "gdcave.c")],
                            capture_output=True, text=True)
        if cc.returncode:
            sys.exit(cc.stderr)
    lib = ctypes.CDLL(LIB)
    lib.dc_cave.restype = ctypes.POINTER(ctypes.c_uint8 * (ck.W * ck.H))
    return lib


def read_moves(path):
    """[(input, show the map before it, until Rockford moves)] of a moves file"""
    text = re.sub(r"#[^\n]*", "", open(path).read())
    out, show = [], False
    for n, c, until in re.findall(r"(\d*)([URDLurdl.!])(\*?)", text):
        if c == "!":
            show = True
            continue
        if c == ".":
            inp = DIR_NONE
        elif c in "URDL":
            inp = "URDL".index(c)
        else:
            inp = "urdl".index(c) | IN_FIRE
        for _ in range(int(n or 1)):
            out.append((inp, show, bool(until)))
            show = False
    if show:
        out.append((None, True, False))
    return out


class Play:
    def __init__(self, bd_path):
        _, caves = ck.read_bd(bd_path, 0)
        if not caves or isinstance(caves[0][2], ck.CaveError):
            sys.exit(f"{bd_path}: {caves[0][2] if caves else 'no cave'}")
        self.cave = caves[0][2]
        self.raw = ctypes.create_string_buffer(self.cave.tobytes())
        self.lib = library()
        self.lib.dc_start(self.raw, 0)
        self.inputs = []
        self.state = (ctypes.c_int * 15)()

    def st(self):
        self.lib.dc_state(self.state)
        return list(self.state)

    def step(self, inp):
        self.lib.dc_step(inp & 7, inp & IN_FIRE)
        self.inputs.append(inp)

    def born(self):
        """Steps until Rockford stands in the cave"""
        while True:
            s = self.st()
            cells = self.lib.dc_cave().contents
            if s[0] == 1 and cells[s[2] * ck.W + s[1]] == ck.O["PLAYER"]:
                return
            if s[0] not in (0, 1) or len(self.inputs) > 500:
                sys.exit("Rockford is not born")
            self.step(DIR_NONE)

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


def play(bd_path, moves_path, every=0):
    p = Play(bd_path)
    p.born()
    for inp, show, until in read_moves(moves_path):
        if show:
            p.show()
        if inp is None:
            break
        at = p.st()[1:3]
        for _ in range(100 if until else 1):
            if p.st()[0] != 1:
                break
            p.step(inp)
            if every and len(p.inputs) % every == 0:
                p.show()
            if p.st()[1:3] != at:
                break
    for _ in range(10):  # what happens next
        if p.st()[0] != 1:
            break
        p.step(DIR_NONE)
    s = p.st()
    print(f"{STATES[s[0]]} after {len(p.inputs)} steps: {s[3]}/{s[4]} emeralds, {s[6]} s left")
    return p, s[0] == 4


def pack(inputs):
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


def main():
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "play":
        every = int(args[args.index("--every") + 1]) if "--every" in args else 0
        _, ok = play(args[1], args[2], every)
        return 0 if ok else 1
    if len(args) == 4 and args[0] == "pack":
        p, ok = play(args[1], args[2])
        if not ok:
            sys.exit("democave: Rockford does not get out")
        with open(args[3], "wb") as f:
            f.write(pack(p.inputs))
        print(f"{args[3]}: {len(p.inputs)} steps")
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
