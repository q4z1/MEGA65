#!/usr/bin/env python3
"""The mechanics of GDash's engine, element by element, against GDash itself:

  python3 tests/test_mechanics.py [--coverage] [--uncovered] [scenario...]

A scenario is a small cave (GDash's .bd) with moves that make one mechanic
happen - a key opening its door, a bladder rising through a wall, slime
letting a boulder through, ... -, and say what must come of it ("=" lines,
see tools/democave.py): tests/mechanics/*.bd with their .moves, and the
demo caves (demo/). Without names, all of them; a name is a file's name
without .bd, or a part of it.

Each scenario is played three ways:
  - by src/gdengine.c on the host with GDash's random numbers (GD_EXACT):
    the moves (a * after one adapts to what the cave does), and what they
    say must be so;
  - by GDash's own code (toolchain/tools/bin/gdash-oracle moves) with the
    same input, step for step: the map, the player's state, emeralds, time,
    score, speed, where he is, his keys, sweet, hammer, diamond key and
    skeletons, gravity, the exit, amoeba and magic wall, and the cave's
    switches must be the same after every step;
  - by src/gdengine.c with the game's random numbers, as the MEGA65 plays
    it (tests/test_gdmega65.py checks that the MEGA65 plays as the host):
    what the moves say must be so there too.

--coverage builds the engine with gcov and tells how much of src/gdengine.c
the scenarios run; --uncovered also lists what they never reach, by
function.
"""

import glob
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import democave as dc  # noqa: E402

ORACLE = os.path.join(ROOT, "..", "toolchain", "tools", "bin", "gdash-oracle")


def scenarios(names):
    found = sorted(glob.glob(os.path.join(HERE, "mechanics", "*.bd"))) + \
        sorted(glob.glob(os.path.join(ROOT, "demo", "*.bd")))
    found = [f for f in found if os.path.exists(f[:-3] + ".moves")]
    if names:
        found = [f for f in found if any(n in os.path.basename(f)[:-3] for n in names)]
    return found


def oracle_input(inputs):
    """democave's inputs as characters for the oracle's moves"""
    out = ""
    for inp in inputs:
        c = "URDL."[inp & 7]
        if inp & dc.IN_FIRE:
            c = "," if c == "." else c.lower()
        out += "X" if inp & dc.IN_SUICIDE else c
    return out


def run(paths, variant, cflags):
    exact = dc.library(variant, cflags)
    game = dc.library("game")
    tmp = tempfile.mkdtemp()
    failed = 0
    for bd in paths:
        name = os.path.relpath(bd[:-3], ROOT)
        moves = bd[:-3] + ".moves"
        problems = []
        p, out, bad = dc.play(bd, moves, lib=exact, quiet=True)
        problems += [f"with GDash's random numbers: {b}" for b in bad]
        fn = os.path.join(tmp, "inputs")
        with open(fn, "w") as f:
            f.write(oracle_input(p.inputs))
        want = subprocess.run([ORACLE, "moves", bd, "0", "1", fn], capture_output=True,
                              text=True).stdout.splitlines()
        k = next((i for i, (a, b) in enumerate(zip(p.lines, want)) if a != b), None)
        if k is None and len(want) != len(p.lines):
            k = min(len(want), len(p.lines))
        if k is not None:
            ours, theirs = (p.lines[k] if k < len(p.lines) else "-"), (want[k] if k < len(want) else "-")
            diff = [f"{a} | GDash {b}" for a, b in zip(ours.split(), theirs.split()) if a != b]
            problems.append(f"step {k} not as in GDash: {', '.join(diff) or ours + ' | GDash ' + theirs}")
        _, game_out, game_bad = dc.play(bd, moves, lib=game, quiet=True)
        problems += [f"with the game's random numbers: {b}" for b in game_bad]
        state = dc.STATES[p.st()[0]]
        print(("ok   " if not problems else "FAIL ") + f"{name}: {len(p.inputs)} steps as in GDash, "
              f"{'out' if out else state}" + ("" if game_out == out else
                                               f" (with the game's random numbers {'out' if game_out else 'not out'})"))
        for pr in problems[:8]:
            print("       " + pr)
        failed += bool(problems)
    return failed


def coverage(paths, uncovered):
    """The scenarios in a child (gcov writes its counts when a process ends), then gcov"""
    gen = os.path.join(dc.GEN, "coverage")
    for f in glob.glob(os.path.join(gen, "*.gcda")):
        os.remove(f)
    child = subprocess.run([sys.executable, __file__, "--variant-coverage"] + paths)
    gcno = glob.glob(os.path.join(gen, "*gdengine.gcno"))
    out = subprocess.run(["gcov", "-b", "-c", "-f", "-o", gcno[0], os.path.join(ROOT, "src", "gdengine.c")],
                         capture_output=True, text=True, cwd=gen).stdout
    summary = out.split("File '")[-1].splitlines()
    print("src/gdengine.c: " + ", ".join(s.strip() for s in summary[1:5]))
    funcs = re.findall(r"Function '(\w+)'\nLines executed:([\d.]+)% of (\d+)", out)
    never = [f for f, pct, _ in funcs if float(pct) == 0]
    if never:
        print("never called: " + ", ".join(never))
    if uncovered:
        lines = open(os.path.join(gen, "gdengine.c.gcov")).read().splitlines()
        func = None
        for line in lines:
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            src = parts[2]
            m = re.match(r"^(?:static\s+)?[\w\s\*]+?\b(\w+)\(.*\)\s*\{", src)
            if m and not src.startswith(" "):
                func = m.group(1)
            if parts[0].strip() == "#####":
                print(f"  {func}:{parts[1].strip()}: {src.strip()}")
    return child.returncode


def main():
    args = sys.argv[1:]
    if not os.path.exists(ORACLE):
        sys.exit(f"no {ORACLE}: toolchain/tools/build-tools.sh")
    if args[:1] == ["--variant-coverage"]:
        return 1 if run(args[1:], "coverage", ("-DGD_EXACT", "--coverage", "-O0")) else 0
    cov = "--coverage" in args or "--uncovered" in args
    paths = scenarios([a for a in args if not a.startswith("--")])
    if not paths:
        sys.exit("no such scenario")
    if cov:
        return coverage(paths, "--uncovered" in args)
    failed = run(paths, "exact", ("-DGD_EXACT",))
    print(f"{len(paths)} scenarios: " + ("all as GDash plays them and as their moves say" if not failed else
                                         f"{failed} not"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
