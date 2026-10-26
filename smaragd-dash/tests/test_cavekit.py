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
import re
import shutil
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
c3.v["intermission_instantlife"] = 1  # the life at the start, none at the exit
ck.write_bd(out_bd, [c3], "test")
text = open(out_bd, encoding="latin-1").read()
check("an intermission's life at its start: written as instantlife, and no rewardlife",
      "IntermissionProperties.instantlife=true" in text and "IntermissionProperties.rewardlife=false" in text and
      ck.read_bd(out_bd, 0)[1][0][2].v["intermission_instantlife"] == 1)
c3.v["intermission_instantlife"] = 0
raw = c1.tobytes()
again = ck.GdCave.frombytes(raw)
check("the disk's file layout, and back", len(raw) == ck.GD_SIZE and again.v == c1.v and again.cells == c1.cells
      and again.name == c1.name, len(raw))
check("time 0: an empty slot", ck.GdCave.frombytes(bytes(ck.GD_SIZE)) is None)
check("names: umlauts as two letters, no accents", (ck.clean_name("Höhle 1"), ck.clean_name("A. pálya")) ==
      ("HOEHLE 1", "A. PALYA"))
cave = ck.read_cave_file(os.path.join(HERE, "cavekit", "butterflies.cave"))
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
    check("disks: a game of its own, named after the file, the caves in its slots 1-4, the rest empty",
          d.games()[0] == ck.game_name(BD) and
          [c.name for c in got[:4]] == [c.name for c in (c1, c2, c3, c4)] and not any(got[4:]),
          (d.games(), [c and c.name for c in got[:6]]))
    with contextlib.redirect_stdout(io.StringIO()):
        ck.cmd_disks([game_disk] + [BD] * 7 + ["--out", out_dir, "--cave", "1-4"])
    parts = sorted(f for f in os.listdir(out_dir) if f.startswith("objects-"))
    first, last = ck.Disk(os.path.join(out_dir, parts[0])), ck.Disk(os.path.join(out_dir, parts[-1]))
    name = ck.game_name(BD)
    check("disks: seven files, seven games, three on a disk, told apart by their names",
          parts == ["objects-1.d81", "objects-2.d81", "objects-3.d81"] and
          first.games() == [name, f"{name}-2", f"{name}-3"] and last.games()[0] == f"{name}-7" and
          sum(1 for n in last.slots() if ck.read_slot(last, n)) == 4, (parts, first.games(), last.games()))

    # the levels of a slot: OWNnn-2 ... OWNnn-5 where they differ from the first
    s1, s2 = d.slots()[:2]
    lv = ck.read_levels(d, s1)
    check("disks: all five levels of a cave, level 5 with its own numbers",
          len(lv) == 5 and lv[0].v["time"] == 150 and (lv[4].v["time"], lv[4].v["diamonds_needed"]) == (110, 16) and
          ck.own_levels(d, s1)[-1] == 5, [c.v["time"] for c in lv])
    same = [n for n in range(1, 5) if lv[n].tobytes() == lv[0].tobytes()]
    check("a level like the first has no cave of its own (its file is empty)",
          all(not ck.read_slot(d, ck.level_file(s1, n)) for n in same) and
          all(ck.read_slot(d, ck.level_file(s1, n)) for n in range(1, 5) if n not in same), same)
    with contextlib.redirect_stdout(io.StringIO()):
        ck.cmd_import([os.path.join(out_dir, "objects.d81"), BD, "--level", "5", "--cave", "1"])
    d = ck.Disk(os.path.join(out_dir, "objects.d81"))
    check("import --level 5: that level alone, the others empty",
          ck.read_slot(d, s1).v["time"] == 110 and ck.own_levels(d, s1) == [1],
          ck.own_levels(d, s1))
    ck.write_slot(d, s2, None)
    check("an empty slot: its levels empty too",
          not ck.read_levels(d, s2) and ck.own_levels(d, s2) == [1] and
          not any(ck.read_slot(d, ck.level_file(s2, n)) for n in range(1, 5)))
    with contextlib.redirect_stdout(io.StringIO()):
        ck.cmd_import([os.path.join(out_dir, "objects.d81"), BD, "--game", "3", "--slot", "20", "--cave", "2"])
    d = ck.Disk(os.path.join(out_dir, "objects.d81"))
    check("import --game 3 --slot 20: the last slot of the third game",
          ck.read_slot(d, d.slots(d.games()[2])[19]).name == c2.name and not ck.read_slot(d, d.slots()[19]))
    with contextlib.redirect_stdout(io.StringIO()):
        ck.cmd_rename([os.path.join(out_dir, "objects.d81"), "2", "my game"])
    d = ck.Disk(os.path.join(out_dir, "objects.d81"))
    check("rename: the second game, in the directory and in its partition's header",
          d.games()[1] == "MY GAME" and d.slots("MY GAME") and
          bytes(d.sector(d.files()[d.slots("MY GAME")[0]][0], 0)[4:11]) == b"MY GAME", d.games())
    try:
        ck.Disk(os.path.join(out_dir, "objects.d81")).rename("MY GAME", "A/B")
        bad = False
    except ck.CaveError:
        bad = True
    check("rename: no / in a game's name", bad)

    # a disk of an older version: its slots in its directory, no files for the levels
    sys.path.insert(0, os.path.join(HERE, "..", "..", "toolchain", "tools", "bin"))
    import mkd81
    src = ck.Disk(os.path.join(out_dir, "objects-1.d81"))
    flat = [("OWN%02d" % (i + 1), src.read(n)) for i, n in enumerate(src.slots(src.games()[0]))]
    img, _ = mkd81.build("SMARAGD 1.2", [("SMARAGD.SCORES", bytes(range(254)))] + flat)
    old = os.path.join(tmp, "old.d81")
    with open(old, "wb") as f:
        f.write(img)
    od = ck.Disk(old)
    check("an older disk: one game without a name, its slots in the directory",
          od.games() == [""] and od.slots() == [n for n, _ in flat], od.slots()[:3])
    ok = ck.write_slot(od, "OWN01", ck.read_levels(src, src.slots()[0]))
    check("an older disk: the first level only, and it says so",
          not ok and ck.read_slot(od, "OWN01").v["time"] == 150 and ck.own_levels(od, "OWN01") == [1])
    od.save()
    up = os.path.join(tmp, "up.d81")
    shutil.copyfile(game_disk, up)
    with contextlib.redirect_stdout(io.StringIO()):
        ck.cmd_upgrade([old, up])
    ud = ck.Disk(up)
    check("upgrade: the older disk's caves in the first game, its high scores along",
          [c and c.name for c in (ck.read_slot(ud, n) for n in ud.slots()[:4])] ==
          [c and c.name for c in (ck.read_slot(od, n) for n in od.slots()[:4])] and
          ud.read("SMARAGD.SCORES") == bytes(range(254)), ud.slots()[:2])
    back_bd = os.path.join(tmp, "back.bd")
    with contextlib.redirect_stdout(io.StringIO()):
        ck.cmd_export([os.path.join(out_dir, "objects-1.d81"), back_bd, "--slot", "1-4"])
    exported = ck.read_levels(ck.Disk(os.path.join(out_dir, "objects-1.d81")), src.slots()[0])
    _, back5 = ck.read_bd(back_bd, 4)
    if all(c.cells == exported[0].cells for c in exported):
        check("export: the levels' numbers in the .bd file",
              back5[0][2].v["time"] == exported[4].v["time"], back5[0][2].v["time"])
    else:
        check("export: maps that differ by level: the first level", back5[0][2].v["time"] == exported[0].v["time"])

print("all passed" if not failures else f"{failures} failed")
sys.exit(1 if failures else 0)
