#!/usr/bin/env python3
"""Tests of tools/cavekit.py on the host:

  python3 tests/test_cavekit.py

tests/cavekit/objects.bd has every kind of object GDash draws; the maps
must be the ones GDash's own code draws (tests/cavekit/expected.txt), in
all five levels. Then the numbers of its caves, what the game cannot play,
and the ways back and forth: .bd, .cave, the disk's file layout.
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import cavekit as ck  # noqa: E402

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
    names = {v.upper(): k for k, v in ck.OTHER_CHARS.items()}
    names.update({v.upper(): k for k, v in ck.CHAR_NAME.items()})
    chars = "".join(names.get(e, e) for e in cells)
    return [chars[i:i + w] for i in range(0, len(chars), w)]


BD = os.path.join(HERE, "cavekit", "objects.bd")
bd = ck.BdcffFile(BD)

# the maps, as GDash draws them
for (level, n), rows in sorted(expected().items()):
    r = ck.Renderer(bd, bd.caves[n - 1], level - 1, {})
    got = map_chars(r.render(), r.w)
    diff = [y for y in range(len(rows)) if rows[y] != got[y]]
    check(f"level {level}, cave {n}: map as GDash draws it", not diff,
          f"row {diff[0]}: {got[diff[0]]!r} instead of {rows[diff[0]]!r}" if diff else "")

# the caves as the game plays them
_, caves = ck.read_bd(BD, 0, {})
c1, c2, c3, c4 = (c for _, _, c in caves)
check("BD1 timing: real seconds", (c1.time, c1.amoeba, c1.magic) == (180, 24, 18),
      (c1.time, c1.amoeba, c1.magic))
check("numbers of level 1", (c1.diamonds, c1.value, c1.extra) == (12, 10, 15),
      (c1.diamonds, c1.value, c1.extra))
check("BD1 speed from the CaveDelay and the cave (GDash: 166)", c1.speed == 166, c1.speed)
_, lv5 = ck.read_bd(BD, 4, {})
check("level 5: its own numbers", (lv5[0][2].time, lv5[0][2].diamonds) == (132, 16),
      (lv5[0][2].time, lv5[0][2].diamonds))
check("one diamond value: extra 0", (c2.value, c2.extra) == (5, 0), (c2.value, c2.extra))
check("PLCK speed: CaveDelay x 20 ms", c2.speed == 160, c2.speed)
check("the map codes and all creatures", c2.rows()[2][19:27] == "QoOqCbBc" and c2.rows()[1][7] == "w",
      c2.rows()[1:3])
check("amoeba threshold other than 200: noted", any("200 cells, not 88" in n for n in c2.notes), c2.notes)
check("intermission: top left, the rest steel",
      c3.rows()[11] == "W" * 40 and c3.rows()[5][19] == "X" and any("20x12" in n for n in c3.notes),
      c3.rows()[5:12])
check("milliseconds from FrameTime", c3.speed == 120, c3.speed)
check("an element the game has not: refused",
      isinstance(c4, ck.CaveError) and "HEXPANDINGWALL (26x)" in str(c4), c4)
_, sub = ck.read_bd(BD, 0, {"HEXPANDINGWALL": "w"})
check("... unless it is replaced (--as)", not isinstance(sub[3][2], ck.CaveError) and
      sub[3][2].rows()[5][5:31] == "w" * 26, sub[3][2])
for c in (c1, c2, c3):
    check(f"'{c.name}' can be played", not ck.check_cave(c), ck.check_cave(c))

# there and back
tmp = tempfile.mkdtemp()
out_bd = os.path.join(tmp, "out.bd")
ck.write_bd(out_bd, [c1, c2, c3], "test")
_, back = ck.read_bd(out_bd, 0, {})
same = all(vars(a) | {"notes": []} == vars(b) | {"notes": []} for a, (_, _, b) in zip((c1, c2, c3), back))
check(".bd written and read again: the same caves", same, [vars(b) for _, _, b in back][:1])
out_cave = os.path.join(tmp, "out.cave")
ck.write_cave_file(out_cave, c1)
again = ck.read_cave_file(out_cave)
check(".cave written and read again: the same cave", vars(again) | {"notes": []} == vars(c1) | {"notes": []},
      vars(again))
raw = ck.cave_bytes(c1)
check("the disk's file layout: 912 bytes, and back", len(raw) == 912 and
      vars(ck.cave_from_bytes(raw)) | {"notes": []} == vars(c1) | {"notes": []}, len(raw))
check("time 0: an empty slot", ck.cave_from_bytes(bytes(912)) is None)

print("all passed" if not failures else f"{failures} failed")
sys.exit(1 if failures else 0)
