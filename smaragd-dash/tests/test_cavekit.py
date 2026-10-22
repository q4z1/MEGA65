#!/usr/bin/env python3
"""Tests of tools/cavekit.py on the host:

  python3 tests/test_cavekit.py

tests/cavekit/objects.bd has every kind of object GDash draws; the maps
must be the ones GDash's own code draws (tests/cavekit/expected.txt), in
all five levels. Then the values of its caves, and the ways back and
forth: .bd, .cave, the disk's file layout, and disks for a whole game
(with a built disk). (tests/test_gdengine.sh compares
with GDash itself, on all of its caves.)
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import cavekit as ck  # noqa: E402

O = ck.O
failures = 0


def check(name, ok, detail=""):
    global failures
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))
    failures += not ok


def expected():
    """{(level, cave): rows} of expected.txt"""
    out, key = {}, None
    for line in open(os.path.join(HERE, "cavekit", "expected.txt")).read().splitlines():
        if line.startswith("#"):
            continue
        if line.startswith("level "):
            p = line.split()
            key = (int(p[1]), int(p[3]))
            out[key] = []
        else:
            out[key].append(line)
    return out


def map_chars(cells, w):
    chars = "".join(ck.GD_EL[e].char or "?" for e in cells)
    return [chars[i:i + w] for i in range(0, len(chars), w)]


BD = os.path.join(HERE, "cavekit", "objects.bd")
bd = ck.BdcffFile(BD)

# the maps, as GDash draws them
for (level, n), rows in sorted(expected().items()):
    r = ck.Renderer(bd, bd.caves[n - 1], level - 1)
    got = map_chars(r.render(), r.w)
    diff = [y for y in range(len(rows)) if rows[y] != got[y]]
    check(f"level {level}, cave {n}: map as GDash draws it", not diff,
          f"row {diff[0]}: {got[diff[0]]!r} instead of {rows[diff[0]]!r}" if diff else "")

# the caves as the game keeps them: GDash's values of a level
_, caves = ck.read_bd(BD, 0)
c1, c2, c3, c4 = (c for _, _, c in caves)
v1 = c1.v
check("cave 1, level 1: its numbers", (v1["time"], v1["diamonds_needed"], v1["diamond_value"],
      v1["extra_diamond_value"]) == (150, 12, 10, 15), v1)
check("C64 timing: bd1, PAL, CaveDelay 12",
      (v1["scheduling"], v1["pal_timing"], v1["ckdelay"]) == (1, 1, 12), v1)
check("amoeba and magic wall in seconds", (v1["amoeba_time"], v1["magic_wall_time"]) == (20, 15), v1)
_, lv5 = ck.read_bd(BD, 4)
check("level 5: its own numbers", (lv5[0][2].v["time"], lv5[0][2].v["diamonds_needed"]) == (110, 16),
      lv5[0][2].v)
check("the C64 random numbers left by the fill, for the slime", (v1["c64_seed_1"], v1["c64_seed_2"]) != (0, 0x1E))
v2 = c2.v
check("one diamond value: extra 0", (v2["diamond_value"], v2["extra_diamond_value"]) == (5, 0), v2)
check("CaveDelay alone: plck", (v2["scheduling"], v2["ckdelay"]) == (3, 8), v2)
check("amoeba threshold as a part of the cave: 0.1 of 880", v2["amoeba_max_count"] == 88, v2)
check("a map: the C64's random numbers as GDash sets them", (v2["c64_seed_1"], v2["c64_seed_2"]) == (0, 0x1E))
creatures = [O[f"FIREFLY_{i}"] for i in (1, 2, 3, 4)] + [O[f"BUTTER_{i}"] for i in (1, 2, 3, 4)]
check("the map codes and all creatures", c2.cells[2 * 40 + 19:2 * 40 + 27] == creatures and
      c2.cells[1 * 40 + 7] == O["BRICK"], c2.cells[40:120])
check("intermission: 20x12 to see", (c3.v["x2"], c3.v["y2"], c3.v["intermission"]) == (19, 11, 1), c3.v)
check("FrameTime: milliseconds", (c3.v["scheduling"], c3.v["speed"]) == (0, 120), c3.v)
check("GDash's elements: an expanding wall",
      not isinstance(c4, ck.CaveError) and c4.cells[5 * 40 + 5] == O["H_EXPANDING_WALL"], c4)
_, sub = ck.read_bd(BD, 0, {O["H_EXPANDING_WALL"]: O["BRICK"]})
check("... or another one in its place (--as)", sub[3][2].cells[5 * 40 + 5] == O["BRICK"], sub[3][2])

# there and back
tmp = tempfile.mkdtemp()
out_bd = os.path.join(tmp, "out.bd")
ck.write_bd(out_bd, [c1, c2, c3, c4], "test")
_, back = ck.read_bd(out_bd, 0)
for a, (_, _, b) in zip((c1, c2, c3, c4), back):
    diff = [k for k in a.v if a.v[k] != b.v.get(k)]
    check(f"'{a.name}' written as .bd and read again: the same", not diff and a.cells == b.cells,
          [(k, a.v[k], b.v.get(k)) for k in diff][:5])
raw = c1.tobytes()
again = ck.GdCave.frombytes(raw)
check("the disk's file layout, and back", len(raw) == ck.GD_SIZE and again.v == c1.v and again.cells == c1.cells
      and again.name == c1.name, len(raw))
check("time 0: an empty slot", ck.GdCave.frombytes(bytes(ck.GD_SIZE)) is None)
cave = ck.read_cave_file(os.path.join(HERE, "..", "caves", "04-butterflies.cave"))
out_cave = os.path.join(tmp, "out.cave")
ck.write_cave_file(out_cave, cave)
check(".cave written and read again: the same", vars(ck.read_cave_file(out_cave)) == vars(cave))
gd = ck.gd_from_cave(cave)
check("a .cave with GDash's rules: Boulder Dash 1's, in milliseconds",
      (gd.v["scheduling"], gd.v["pal_timing"], gd.v["speed"], gd.v["magic_wall_stops_amoeba"]) == (0, 0, cave.speed, 0),
      gd.v)
check("... and back to a .cave", vars(ck.game_cave(gd)) | {"notes": []} == vars(cave) | {"notes": []})

# a whole game on disks: 4 caves on 1 disk, 25 copies of them on 2 (needs a built disk)
game_disk = os.path.join(HERE, "..", "build", "smaragd-dash.d81")
if os.path.exists(game_disk):
    import contextlib
    import io
    out_dir = os.path.join(tmp, "disks")
    with contextlib.redirect_stdout(io.StringIO()):
        ck.cmd_disks([game_disk, BD, "--out", out_dir])
    d = ck.Disk(os.path.join(out_dir, "objects.d81"))
    got = [ck.read_slot(d, n) for n in d.slots()]
    check("disks: the caves in slots 1-4, the others empty",
          [c.name for c in got[:4]] == [c.name for c in (c1, c2, c3, c4)] and not any(got[4:]),
          [c and c.name for c in got])
    with contextlib.redirect_stdout(io.StringIO()):
        ck.cmd_disks([game_disk] + [BD] * 7 + ["--out", out_dir, "--cave", "1-4"])
    parts = sorted(f for f in os.listdir(out_dir) if f.startswith("objects-"))
    last = ck.Disk(os.path.join(out_dir, parts[-1]))
    check("disks: 28 caves on two disks of 20 and 8",
          parts == ["objects-1.d81", "objects-2.d81"] and
          sum(1 for n in last.slots() if ck.read_slot(last, n)) == 8, parts)

print("all passed" if not failures else f"{failures} failed")
sys.exit(1 if failures else 0)
