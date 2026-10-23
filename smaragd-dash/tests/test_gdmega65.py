#!/usr/bin/env python3
"""GDash's engine as the MEGA65 runs it - src/gdengine.c as llvm-mos
compiles it, with what is written in assembler - against src/gdengine.c on
the host, which tests/test_gdengine.sh compares with GDash itself:

  python3 tests/test_gdmega65.py [--steps N] [game.bd | .gds | .cave]...

Without files: eight games of GDash's collection (toolchain/tools/src/gdash,
about 200 caves, a few minutes) with most of its elements,
tests/cavekit/objects.bd, and the scenarios of tests/test_mechanics.py
(tests/mechanics/, demo/), which make every mechanic happen.

The caves of the files (level 1), twenty at a time, go into the slots of a
disk of the game built with -DGDCHECK; Xemu plays each for N steps (200)
with the input tests/gdplay.c gives it - a .bd with a .moves beside it
(a scenario) with those moves, as tools/democave.py plays them with the
game's random numbers, in the slot's file CHECKnn - and writes a digest of
every step (src/gddigest.h) into bank 4, which it dumps on exit.
tests/gdplay.c, built with the game's random numbers, must give the same
digests. If Xemu does not get through twenty caves (it hangs), it plays
them one by one and names the caves it hangs in.
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
import democave as dc  # noqa: E402

XEMU = os.path.join(ROOT, "..", "toolchain", "tools", "bin", "xmega65")
GDASH_CAVES = os.path.join(ROOT, "..", "toolchain", "tools", "src", "gdash", "caves")
DEFAULT = ["First_Star_Software/Boulder_Dash_1.bd", "First_Star_Software/Boulder_Dash_2.bd", "Sendy/Crli_Caves.bd",
           "Dustin/Boulder_Dash_-_The_New_Elements.bd", "Marek_Roth/Crazy_Dream/Crazy_Dream_8.bd",
           "Thomas_Mauritz/Emerald_Dash_1.bd", "Olaf_Roth/Cool_Dash/Cool_Dash_02.gds", "Olaf_Roth/Bilder_Dash.gds"]
BANK = 4  # main.c's GDCHECK_BANK
TIMEOUT = 300  # seconds for twenty caves; they take some 15


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)


def packed(inputs):
    """The input of a scenario as a CHECKnn file (main.c's gd_check): its
    load address, (count, input) pairs, 0"""
    out = bytearray(2)
    i = 0
    while i < len(inputs):
        n = 1
        while i + n < len(inputs) and n < 255 and inputs[i + n] == inputs[i]:
            n += 1
        out += bytes([n, inputs[i]])
        i += n
    return bytes(out) + bytes(1)


def main():
    args = sys.argv[1:]
    steps = 200
    if args[:1] == ["--steps"]:
        steps = int(args[1])
        args = args[2:]
    if not args:
        args = [os.path.join(GDASH_CAVES, f) for f in DEFAULT] + [os.path.join(HERE, "cavekit", "objects.bd")] + \
            sorted(os.path.join(HERE, "mechanics", f) for f in os.listdir(os.path.join(HERE, "mechanics"))
                   if f.endswith(".bd")) + \
            sorted(os.path.join(ROOT, "demo", f) for f in os.listdir(os.path.join(ROOT, "demo")) if f.endswith(".bd"))

    caves = []  # (label, cave, CHECKnn file or None)
    game_lib = None
    for path in args:
        moves = path[:-3] + ".moves"
        if path.endswith(".bd") and os.path.exists(moves):
            game_lib = game_lib or dc.library("game")
            p, _, _ = dc.play(path, moves, lib=game_lib, quiet=True)
            caves.append((os.path.relpath(path), p.cave, packed(p.inputs)))
            steps = max(steps, len(p.inputs))
            continue
        for label, cave in ck.load_caves(path, {"cave": None, "level": 1, "as": {}}):
            if not isinstance(cave, ck.CaveError):
                caves.append((f"{os.path.relpath(path)} {label.strip()}", cave[0], None))
    build = run(["./build.sh"], env=dict(os.environ, SMARAGD_CFLAGS=f"-DGDCHECK -DGDCHECK_STEPS={steps}"))
    if build.returncode:
        sys.exit(build.stdout[-2000:] + build.stderr[-2000:])
    gdplay = os.path.join(ROOT, "build", "gdplay-mega65")
    cc = run(["cc", "-O2", "-Wall", "-Wno-array-bounds", "-Isrc", "-Ibuild/gen", "-o", gdplay,
              "tests/gdplay.c", "src/gdengine.c", "build/gen/gdcave.c"])
    if cc.returncode:
        sys.exit(cc.stderr)

    tmp = tempfile.mkdtemp()
    disk_path = os.path.join(tmp, "check.d81")
    total = bad = 0

    def play(chunk, timeout):
        """Xemu plays the caves of chunk, in slots 1, 2, ...: its memory, or None if it hangs"""
        shutil.copyfile(os.path.join(ROOT, "build", "smaragd-dash.d81"), disk_path)
        disk = ck.Disk(disk_path)
        for i, name in enumerate(disk.slots()):
            ck.write_slot(disk, name, [chunk[i][1]] if i < len(chunk) else None)
            moves = chunk[i][2] if i < len(chunk) else None
            size = len(disk.read(f"CHECK{i + 1:02d}"))
            if moves and len(moves) > size:
                sys.exit(f"{chunk[i][0]}: its moves take {len(moves)} bytes, CHECKnn {size}")
            disk.rewrite(f"CHECK{i + 1:02d}", (moves or bytes(2)).ljust(size, b"\0"))
        disk.save()
        dump = os.path.join(tmp, "mem.bin")
        if os.path.exists(dump):
            os.remove(dump)
        subprocess.run(["timeout", str(timeout), XEMU, "-headless", "-sleepless", "-testing", "-besure",
                        "-8", disk_path, "-autoload", "-dumpmem", dump],
                       capture_output=True, env=dict(os.environ, SDL_AUDIODRIVER="dummy"))
        return open(dump, "rb").read() if os.path.exists(dump) else None

    def compare(label, cave, moves, mem, slot):
        """True if the digests Xemu left for the cave in slot are the host's"""
        at = BANK * 0x10000 + slot * steps * 4
        got = [int.from_bytes(mem[at + 4 * t:at + 4 * t + 4], "little") for t in range(steps)]
        fn = os.path.join(tmp, "cave.bin")
        with open(fn, "wb") as f:
            f.write(cave.tobytes())
        cmd = [gdplay, "check", fn, str(steps), str(slot + 1)]
        if moves:
            with open(fn + ".moves", "wb") as f:
                f.write(moves)
            cmd.append(fn + ".moves")
        want = [int(x, 16) for x in run(cmd).stdout.split()]
        if got == want:
            return True
        k = next(t for t in range(steps) if t >= len(want) or got[t] != want[t])
        print(f"  {label}: step {k} differs")
        return False

    try:
        for part in range(0, len(caves), 20):
            chunk = caves[part:part + 20]
            mem = play(chunk, TIMEOUT)
            if mem is None:
                # one by one, each in the slot it had (its input depends on the slot)
                print(f"  Xemu hangs in caves {part + 1}-{part + len(chunk)}; one by one:", flush=True)
            for i, (label, cave, moves) in enumerate(chunk):
                total += 1
                one = mem
                if mem is None:
                    one = play([(None, None, None)] * i + [(label, cave, moves)], TIMEOUT // 4)
                    if one is None:
                        bad += 1
                        print(f"  {label}: Xemu hangs")
                        continue
                if not compare(label, cave, moves, one, i):
                    bad += 1
            print(f"{min(part + 20, len(caves))} of {len(caves)} caves", flush=True)
    finally:
        shutil.rmtree(tmp)
        run(["./build.sh"])
    print(f"{total} caves, {steps} steps: {total - bad} as on the host, {bad} not")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
