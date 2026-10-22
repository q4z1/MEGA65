#!/usr/bin/env python3
"""Compares Smaragd Dash's GDash with GDash itself (tests/test_gdengine.sh):

  gdcompare.py <oracle> <gdplay> <levels> <steps> <file.bd or .gds>...

A .gds file (a C64 game GDash imports) goes the way a player takes it:
GDash saves it as a .bd file, which cavekit.py reads; GDash itself plays the
original.

For each cave of the files in each level (1-5, as "1,2"): the cave as
tools/cavekit.py makes it of the file and src/gdengine.c starts it must be
the one GDash's own code starts (every value, the map), and playing it for
<steps> steps with the same pseudo-random input must give the same map,
state, time, score, speed and place of the player after every step.
Caves that are random anew in every game in GDash are left out.
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import cavekit as ck  # noqa: E402


def random_in_gdash(cave, level):
    """True if GDash draws the cave anew in every game (seeds of -1)"""
    if cave.stored.v["level_rand"][level] < 0 and not cave.map:
        return True
    for kind, line in cave.objects:
        name, _, args = line.partition("=")
        a = args.split()
        if name.lower() in ("randomfill", "randomfillc64") and len(a) > 8 and \
                any(x.lstrip("-").isdigit() and int(x) < 0 for x in a[4:9]):
            return True
        if name.lower() == "maze" and len(a) > 11 and a[7 + level].lstrip("-").isdigit() and \
                int(a[7 + level]) < 0:
            return True
    return False


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout


def per_cave(out):
    caves, cur = {}, None
    for line in out.splitlines():
        if line.startswith("CAVE "):
            cur = int(line.split()[1])
            caves[cur] = []
        elif cur is not None:
            caves[cur].append(line)
    return caves


def main():
    oracle, gdplay, levels, steps = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    levels = [int(n) - 1 for n in levels.split(",")]
    tmp = tempfile.mkdtemp()
    fn = os.path.join(tmp, "cave.bin")
    total = same = skipped = 0
    bad = []
    for path in sys.argv[5:]:
        name = os.path.relpath(path)
        bd_path = path
        if not path.lower().endswith(".bd"):
            # a file GDash imports (.gds: a C64 game): as GDash saves it in
            # BDCFF for cavekit.py, and GDash itself plays the original
            bd_path = os.path.join(tmp, "imported.bd")
            if os.path.exists(bd_path):
                os.remove(bd_path)
            run([oracle, "save", path, bd_path])
            if not os.path.exists(bd_path):
                bad.append(f"{name}: GDash cannot read it")
                continue
        bd = ck.BdcffFile(bd_path)
        for level in levels:
            want_start = per_cave(run([oracle, "cave", path, str(level)]))
            want_play = per_cave(run([oracle, "play", path, str(level), steps]))
            for c in bd.caves:
                total += 1
                if random_in_gdash(c, level):
                    skipped += 1
                    continue
                try:
                    g = ck.gd_cave(bd, c, level)
                except ck.CaveError as e:
                    bad.append(f"{name} cave {c.number} level {level + 1}: {e}")
                    continue
                with open(fn, "wb") as f:
                    f.write(g.tobytes())
                # the start: what gdplay shows of it, against GDash's values
                start = dict(line.split("=", 1) for line in run([gdplay, "cave", fn]).splitlines())
                ref = dict(line.split("=", 1) for line in want_start.get(c.number, []))
                diff = [k for k in start if ref.get(k) != start[k]]
                if diff:
                    bad.append(f"{name} cave {c.number} level {level + 1}: at the start {diff[0]} "
                               f"{start[diff[0]][:40]}, GDash {ref.get(diff[0], '-')[:40]}")
                    continue
                out = run([gdplay, "play", fn, steps, str(c.number)]).splitlines()
                want = want_play.get(c.number, [])
                if out == want:
                    same += 1
                    continue
                k = next((i for i, (a, b) in enumerate(zip(out, want)) if a != b), min(len(out), len(want)))
                bad.append(f"{name} cave {c.number} level {level + 1}: step {k}: "
                           f"{out[k] if k < len(out) else '-'} | GDash {want[k] if k < len(want) else '-'}")
    print(f"{total} cave-levels: {same} as GDash plays them for {steps} steps, "
          f"{skipped} random in GDash, {len(bad)} not")
    for b in bad[:30]:
        print("  " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
