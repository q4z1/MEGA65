#!/usr/bin/env python3
"""GDash's engine as the MEGA65 runs it - src/gdengine.c as llvm-mos
compiles it, with what is written in assembler - against src/gdengine.c on
the host, which tests/test_gdengine.sh compares with GDash itself:

  python3 tests/test_gdmega65.py [--steps N] [game.bd | .gds | .cave]...

Without files: eight games of GDash's collection (toolchain/tools/src/gdash,
about 200 caves, a few minutes) with most of its elements, and
tests/cavekit/objects.bd.

The caves of the files (level 1), twenty at a time, go into the slots of a
disk of the game built with -DGDCHECK; Xemu plays each for N steps (200)
with the input tests/gdplay.c gives it and writes a digest of every step
(src/gddigest.h) into bank 4, which it dumps on exit. tests/gdplay.c, built
with the game's random numbers, must give the same digests.
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
GDASH_CAVES = os.path.join(ROOT, "..", "toolchain", "tools", "src", "gdash", "caves")
DEFAULT = ["First_Star_Software/Boulder_Dash_1.bd", "First_Star_Software/Boulder_Dash_2.bd", "Sendy/Crli_Caves.bd",
           "Dustin/Boulder_Dash_-_The_New_Elements.bd", "Marek_Roth/Crazy_Dream/Crazy_Dream_8.bd",
           "Thomas_Mauritz/Emerald_Dash_1.bd", "Olaf_Roth/Cool_Dash/Cool_Dash_02.gds", "Olaf_Roth/Bilder_Dash.gds"]
BANK = 4  # main.c's GDCHECK_BANK


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)


def main():
    args = sys.argv[1:]
    steps = 200
    if args[:1] == ["--steps"]:
        steps = int(args[1])
        args = args[2:]
    if not args:
        args = [os.path.join(GDASH_CAVES, f) for f in DEFAULT] + [os.path.join(HERE, "cavekit", "objects.bd")]
    build = run(["./build.sh"], env=dict(os.environ, SMARAGD_CFLAGS=f"-DGDCHECK -DGDCHECK_STEPS={steps}"))
    if build.returncode:
        sys.exit(build.stdout[-2000:] + build.stderr[-2000:])
    gdplay = os.path.join(ROOT, "build", "gdplay-mega65")
    cc = run(["cc", "-O2", "-Wall", "-Wno-array-bounds", "-Isrc", "-Ibuild/gen", "-o", gdplay,
              "tests/gdplay.c", "src/gdengine.c", "src/engine.c", "build/gen/gdcave.c"])
    if cc.returncode:
        sys.exit(cc.stderr)

    caves = []
    for path in args:
        for label, cave in ck.load_caves(path, {"cave": None, "level": 1, "as": {}}):
            if not isinstance(cave, ck.CaveError):
                caves.append((f"{os.path.relpath(path)} {label.strip()}", cave))
    tmp = tempfile.mkdtemp()
    disk_path = os.path.join(tmp, "check.d81")
    total = bad = 0
    try:
        for part in range(0, len(caves), 20):
            chunk = caves[part:part + 20]
            shutil.copyfile(os.path.join(ROOT, "build", "smaragd-dash.d81"), disk_path)
            disk = ck.Disk(disk_path)
            slots = disk.slots()
            for i, name in enumerate(slots):
                ck.write_slot(disk, name, chunk[i][1] if i < len(chunk) else None)
            disk.save()
            dump = os.path.join(tmp, "mem.bin")
            if os.path.exists(dump):
                os.remove(dump)
            subprocess.run(["timeout", "900", XEMU, "-headless", "-sleepless", "-testing", "-besure",
                            "-8", disk_path, "-autoload", "-dumpmem", dump],
                           capture_output=True, env=dict(os.environ, SDL_AUDIODRIVER="dummy"))
            if not os.path.exists(dump):
                sys.exit("Xemu wrote no memory dump")
            mem = open(dump, "rb").read()
            for i, (label, cave) in enumerate(chunk):
                total += 1
                at = BANK * 0x10000 + i * steps * 4
                got = [int.from_bytes(mem[at + 4 * t:at + 4 * t + 4], "little") for t in range(steps)]
                fn = os.path.join(tmp, "cave.bin")
                with open(fn, "wb") as f:
                    f.write(cave.tobytes())
                want = [int(x, 16) for x in run([gdplay, "check", fn, str(steps), str(i + 1)]).stdout.split()]
                if got != want:
                    bad += 1
                    k = next(t for t in range(steps) if t >= len(want) or got[t] != want[t])
                    print(f"  {label}: step {k} differs")
            print(f"{min(part + 20, len(caves))} of {len(caves)} caves", flush=True)
    finally:
        shutil.rmtree(tmp)
        run(["./build.sh"])
    print(f"{total} caves, {steps} steps: {total - bad} as on the host, {bad} not")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
