#!/usr/bin/env python3
"""The game's flow in Xemu, from the title to the high score table:

  python3 tests/test_flow.py

The game built with -DFLOWTEST takes its keys and joystick from a script
(flow_script in src/main.c) that waits for what happens - the title, Rockford
alive, out of time, the name entry - rather than for a number of frames, and
at its checkpoints writes what the game knows into memory (main.c's
flow_check, after the status line), which Xemu dumps at the end. The disk has caves of its own in
place of some of the game's: caves 52-56 of level 1 are a step from an
emerald and the exit (each emerald 100 points), cave 1 is a box Rockford
cannot leave, with 10 seconds - in level 2 too, which has no file of its
own for it -, and three are intermissions: cave 51 such a box, cave 52 one
with a life at its exit, cave 53 one with a life at its start.

The script: on the title, cave 51 is picked (right ten times) and played;
its time runs out, which costs no life, and cave 52 comes; Rockford gets
out of caves 52-56 - two lives for the intermissions, one for 500 points;
after the last cave of level 1 comes cave 1 of level 2. There the game is
paused (the time stands) and goes on, the time runs out (fire: a life
less), Rockford gives up three times (Run/Stop) - game over. The score gets
into the table, the name is typed (ZQX), the table is written to the disk
and shown first on the title, which then runs for a minute (logo and table
in turn, as the high score page hung in version 1.0). Then the own caves,
started in level 3: slot 1 has a cave of its own in level 3 (30 seconds),
the other levels play the first (20 seconds) and the other slots are empty -
after the exit comes slot 1 again in level 4. F1 ends that game.

What the checkpoints and the disk's SMARAGD.SCORES must show is below. The
normal build is made again at the end.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import cavekit as ck  # noqa: E402

XEMU = os.path.join(ROOT, "..", "toolchain", "tools", "bin", "xmega65")
FLOW_AT = 0x4FA00              # main.c's FLOW_AT, in bank 4
SCREENS = {1: "title", 2: "cave", 3: "name"}
PS_ALIVE, PS_TIMEOUT = 1, 3    # src/engine.h
HS_COUNT = 8

EXIT_CAVE = """name = FLOW EXIT
time = 20
diamonds = 1
value = 100
extra = 100
speed = 160
map:
""" + "\n".join(["W" * 40, "W" * 40, "WWP dXW" + "W" * 33] + ["W" * 40] * 19)

BOX_CAVE = """name = FLOW BOX
time = 10
diamonds = 1
value = 10
extra = 10
speed = 160
map:
""" + "\n".join(["W" * 40, "W" * 40, "WWPWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWXWW"] + ["W" * 40] * 19)


def write_cave(text, tmp):
    path = os.path.join(tmp, "c.cave")
    with open(path, "w") as f:
        f.write(text + "\n")
    return path


def cave_file(text, tmp, inter=False, instant=False):
    g = ck.gd_from_cave(ck.read_cave_file(write_cave(text, tmp)))
    g.v.update(intermission=int(inter), intermission_instantlife=int(instant))
    return g.tobytes()


def records(mem):
    """The checkpoints flow_check wrote: (number, values)"""
    at = FLOW_AT
    out = []
    for i in range(mem[at]):
        r = mem[at + 16 + 16 * i:at + 32 + 16 * i]
        out.append(dict(stop=r[0], timed_out=r[1], screen=SCREENS.get(r[2], r[2]), lives=r[3], cave=r[4],
                        level=r[5], state=r[6], hs_new=r[7], start_cave=r[8], start_level=r[9],
                        time=r[10] | r[11] << 8, score=int.from_bytes(r[12:16], "little")))
    return out


def main():
    build = subprocess.run(["./build.sh"], cwd=ROOT, capture_output=True, text=True,
                           env=dict(os.environ, SMARAGD_CFLAGS="-DFLOWTEST"))
    if build.returncode:
        sys.exit(build.stdout[-2000:] + build.stderr[-2000:])
    tmp = tempfile.mkdtemp()
    failures = []
    try:
        disk_path = os.path.join(tmp, "flow.d81")
        shutil.copyfile(os.path.join(ROOT, "build", "smaragd-dash.d81"), disk_path)
        disk = ck.Disk(disk_path)
        exit_cave, box_cave = cave_file(EXIT_CAVE, tmp), cave_file(BOX_CAVE, tmp)
        ours = {51: cave_file(BOX_CAVE, tmp, True), 52: cave_file(EXIT_CAVE, tmp, True),
                53: cave_file(EXIT_CAVE, tmp, True, True)}
        for n in range(51, 57):
            disk.rewrite(f"CAVES/CAVE{n}-1", disk.read(f"CAVES/CAVE{n}-1")[:2] + ours.get(n, exit_cave))
        disk.rewrite("CAVES/CAVE01-1", disk.read("CAVES/CAVE01-1")[:2] + box_cave)
        disk.rewrite("SMARAGD.SCORES", bytes(len(disk.read("SMARAGD.SCORES"))))  # the default table
        own = ck.gd_from_cave(ck.read_cave_file(write_cave(EXIT_CAVE, tmp)))
        own3 = ck.gd_from_cave(ck.read_cave_file(write_cave(EXIT_CAVE.replace("time = 20", "time = 30"), tmp)))
        for name in disk.slots():
            ck.write_slot(disk, name, None)
        ck.write_slot(disk, disk.slots()[0], [own, own, own3])
        disk.save()
        dump = os.path.join(tmp, "mem.bin")
        subprocess.run(["timeout", "900", XEMU, "-headless", "-sleepless", "-testing", "-besure",
                        "-8", disk_path, "-autoload", "-dumpmem", dump],
                       capture_output=True, env=dict(os.environ, SDL_AUDIODRIVER="dummy"))
        if not os.path.exists(dump):
            sys.exit("Xemu wrote no memory dump")
        rec = records(open(dump, "rb").read())
        for r in rec:
            print(f"  {r['stop']:2} {r['screen']:5} lives {r['lives']} cave {r['cave'] + 1}/{r['level'] + 1} "
                  f"state {r['state']} time {r['time']:3} score {r['score']:5} start {r['start_cave'] + 1}"
                  f"/{r['start_level'] + 1} new {r['hs_new']}" + ("  TIMED OUT" if r["timed_out"] else ""))
        by = {r["stop"]: r for r in rec if r["stop"]}

        def check(name, ok):
            print(("ok   " if ok else "FAIL ") + name)
            if not ok:
                failures.append(name)

        def at(n, **want):
            r = by.get(n)
            return r is not None and not r["timed_out"] and all(r[k] == v for k, v in want.items())

        check("no wait timed out", not any(r["timed_out"] for r in rec))
        check("the title comes up", at(1, screen="title"))
        check("right ten times picks cave 51", at(2, start_cave=50, start_level=0))
        check("the intermission Rockford does not get out of costs no life, the next cave comes",
              at(3, cave=50, lives=3) and at(4, screen="cave", cave=51, lives=3))
        check("a life at an intermission's exit, or at its start", at(5, cave=52, lives=5))
        check("Rockford gets through caves 52-56, one after the other",
              all(at(4 + i, screen="cave", cave=51 + i, level=0, state=PS_ALIVE) for i in range(5)))
        check("an extra life at 500 points", at(9, lives=6) and by[9]["score"] >= 500)
        check("after the last cave of level 1: cave 1 of level 2, from the first level's file",
              at(9, cave=0, level=1) and by[9]["time"] <= 10)
        check("paused, the time stands still", at(10) and at(11) and by[10]["time"] == by[11]["time"])
        check("and goes on after the pause", at(12) and by[12]["time"] < by[11]["time"])
        check("out of time", at(13, state=PS_TIMEOUT))
        check("fire after the time ran out: a life less, the cave again", at(14, lives=5, cave=0, level=1,
                                                                            state=PS_ALIVE))
        check("Run/Stop: a life less", at(15, lives=4, state=PS_ALIVE))
        check("and again", at(16, lives=3, state=PS_ALIVE))
        rank = by[17]["hs_new"] if 17 in by else HS_COUNT
        check("game over: the score gets into the table", at(17, screen="name") and rank < HS_COUNT)
        check("then the title, the table first", at(18, screen="title", hs_new=rank))
        check("the title runs on for a minute", at(19, screen="title"))
        check("own caves in level 3: slot 1 from its file of level 3",
              at(20, screen="cave", cave=0, level=2, state=PS_ALIVE) and by[20]["time"] > 20)
        check("after the last slot the next level, the first level's file where it has none",
              at(21, screen="cave", cave=0, level=3, state=PS_ALIVE) and by[21]["time"] <= 20)
        check("the script got to its end", 22 in by)

        raw = ck.Disk(disk_path).read("SMARAGD.SCORES")[2:]
        table = [(raw[4 + 9 * i:7 + 9 * i].decode("latin-1"), int.from_bytes(raw[9 + 9 * i:13 + 9 * i], "little"))
                 for i in range(HS_COUNT)]
        final = by[17]["score"] if 17 in by else -1
        check("the table on the disk has ZQX with the score", raw[:4] == b"SDH1" and rank < HS_COUNT and
              table[rank] == ("ZQX", final))
    finally:
        shutil.rmtree(tmp)
        subprocess.run(["./build.sh"], cwd=ROOT, capture_output=True)
    print("all passed" if not failures else f"{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
