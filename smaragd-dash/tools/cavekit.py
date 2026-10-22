#!/usr/bin/env python3
"""Smaragd Dash cave kit: caves between the game's disk, its .cave files
and GDash (BDCFF, .bd files). Needs nothing but Python 3.

  cavekit.py list    <disk.d81 | game.bd | file.cave>
  cavekit.py import  <disk.d81> <game.bd | file.cave>... [options]
  cavekit.py export  <disk.d81> <game.bd> [--slot N[-M]]
  cavekit.py empty   <disk.d81> [--slot N[-M]]
  cavekit.py convert <game.bd | file.cave> <out.cave | out.bd | directory>

list shows the own caves on a disk (the slots OWN01, OWN02, ... that the
game's editor saves into and plays), or the caves of a file and whether
they can be imported.

import puts caves into the slots of the disk, from slot 1 on (or --slot N),
over what is there. From a .bd file it takes all its caves (or --cave N or
N-M, counted from 1) in level 1 (or --level L, 1-5). A cave that cannot be
imported is named with the reason and left out; the others are written.

export writes the own caves of the disk (or --slot N-M) as a .bd file for
GDash.

empty empties all slots of the disk (or --slot N-M).

convert turns a .bd file into .cave files (one per cave, into a
directory, or a single one with --cave N), for building them into the
game (caves/), or a .cave file into a .bd file.

Options for import, list and convert:
  --cave N[-M]      only these caves of the .bd file
  --level L         the level to take (1-5), default 1
  --as NAME=C       turn the GDash element NAME (or map character) into the
                    map character C, e.g. --as HEXPANDINGWALL=w

What the game has: the elements of Boulder Dash 1 (steel and brick wall,
dirt, boulders, emeralds, magic wall, amoeba, fireflies, butterflies, inbox
and exit) in a cave of 40x22 cells with a steel frame. A smaller cave
(an intermission) goes into the top left corner, the rest is steel. GDash's
timing is converted: the time with PAL timing in real seconds (x 1.2), the
speed of C64 caves (CaveDelay) into milliseconds as GDash computes them.
Objects are drawn as GDash draws them (lines, rectangles, random fills,
...), except mazes: save such a file flat first (gdash in.bd --save-flat
out.bd -q, from github.com/revvv/gdash-export-CrLi).

The .cave format is described in tools/mkcave.py; its map characters are
the ones BDCFF uses.
"""

import os
import re
import sys

W, H = 40, 22
NAME_LEN = 21          # what the status line has room for
NAME_FIELD = 24        # bytes 8-31 of a cave file
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /:.!-,"  # the game's font
SLOT = "OWN"           # the slots on the disk: OWN01, OWN02, ...
LEVELS = 5             # BDCFF's

# The engine's codes (src/engine.h; mkcave.py checks them against it)
CODES = {"E_SPACE": 0, "E_DIRT": 1, "E_BRICK": 2, "E_STEEL": 3, "E_BOULDER": 4,
         "E_DIAMOND": 6, "E_INBOX": 9, "E_OUTBOX": 10, "E_MAGIC": 12, "E_AMOEBA": 13,
         "E_FIREFLY": 14, "E_BUTTERFLY": 18,
         "DIR_UP": 0, "DIR_RIGHT": 1, "DIR_DOWN": 2, "DIR_LEFT": 3}

# The elements of the game: map character (BDCFF's), GDash's name, the
# engine's code, and the C64 time it took per cell in microseconds (GDash's
# "ckdelay", for the speed of C64 caves)
ELEMENTS = [
    (" ", "SPACE", "E_SPACE", 0),
    (".", "DIRT", "E_DIRT", 0),
    ("w", "WALL", "E_BRICK", 0),
    ("W", "STEELWALL", "E_STEEL", 0),
    ("r", "BOULDER", "E_BOULDER", 156),
    ("d", "DIAMOND", "E_DIAMOND", 156),
    ("P", "INBOX", "E_INBOX", 0),
    ("X", "OUTBOX", "E_OUTBOX", 0),
    ("M", "MAGICWALL", "E_MAGIC", 0),
    ("a", "AMOEBA", "E_AMOEBA", 260),
    ("Q", "FIREFLYl", "E_FIREFLY + DIR_LEFT", 384),
    ("o", "FIREFLYu", "E_FIREFLY + DIR_UP", 384),
    ("O", "FIREFLYr", "E_FIREFLY + DIR_RIGHT", 384),
    ("q", "FIREFLYd", "E_FIREFLY + DIR_DOWN", 384),
    ("C", "BUTTERFLYl", "E_BUTTERFLY + DIR_LEFT", 384),
    ("b", "BUTTERFLYu", "E_BUTTERFLY + DIR_UP", 384),
    ("B", "BUTTERFLYr", "E_BUTTERFLY + DIR_RIGHT", 384),
    ("c", "BUTTERFLYd", "E_BUTTERFLY + DIR_DOWN", 384),
]
CHAR_EXPR = {c: expr for c, _, expr, _ in ELEMENTS}
CHAR_CODE = {c: eval(expr, {}, CODES) for c, expr in CHAR_EXPR.items()}
CODE_CHAR = {v: c for c, v in CHAR_CODE.items()}
CHAR_NAME = {c: name for c, name, _, _ in ELEMENTS}
CKDELAY = {c: d for c, _, _, d in ELEMENTS}

# GDash's names (upper case: it compares them so) for what the game has
NAME_CHAR = {name.upper(): c for c, name, _, _ in ELEMENTS}
# Other states of the same things: falling, open, hidden, the player
NAME_CHAR.update({"DIRT2": ".", "BOULDERF": "r", "FALLING_BOULDER": "r", "DIAMONDF": "d",
                  "FALLING_DIAMOND": "d", "OUTBOXOPEN": "X", "HIDDENOUTBOX": "X",
                  "HIDDENOUTBOXOPEN": "X", "GUY": "P", "GUYBIRTH1": "P", "GUYBIRTH2": "P",
                  "GUYBIRTH3": "P"})
# GDash's map characters for elements the game does not have
OTHER_CHARS = {"E": "STEELWALLDESTRUCTABLE", "x": "HEXPANDINGWALL", "v": "VEXPANDINGWALL",
               "e": "EXPANDINGWALL", "G": "GRAVESTONE", "F": "DUMMY", "s": "SLIME", "g": "GHOST",
               "R": "BOULDERf", "D": "DIAMONDf", "H": "HIDDENOUTBOX"}


class CaveError(Exception):
    pass


# ---------------------------------------------------------------- caves

class Cave:
    """A cave as the game plays it: one level, 40x22 map characters"""

    def __init__(self, name="", time=150, diamonds=10, value=10, extra=15, speed=160,
                 amoeba=0, magic=0, cells=None):
        self.name, self.time, self.diamonds = name, time, diamonds
        self.value, self.extra, self.speed = value, extra, speed
        self.amoeba, self.magic = amoeba, magic
        self.cells = cells or empty_map()
        self.notes = []  # what was changed on the way, for the user

    def rows(self):
        return ["".join(self.cells[y * W:(y + 1) * W]) for y in range(H)]


def empty_map():
    """Steel frame, dirt, inbox at the top left, exit at the bottom right
    (the editor's new cave)"""
    cells = ["W" if x in (0, W - 1) or y in (0, H - 1) else "." for y in range(H) for x in range(W)]
    cells[2 * W + 2] = "P"
    cells[(H - 3) * W + W - 1] = "X"
    return cells


def clean_name(name):
    """The name in the letters the game has, at most NAME_LEN long"""
    name = "".join(c if c in NAME_CHARS else " " for c in name.upper())
    return " ".join(name.split())[:NAME_LEN].rstrip()


def check_map(cells):
    """Errors of a map the game cannot play (none: it can)"""
    errors = []
    if len(cells) != W * H:
        return [f"the map must be {W}x{H}"]
    for i, c in enumerate(cells):
        if c not in CHAR_CODE:
            errors.append(f"unknown map character '{c}' at {i % W},{i // W}")
        elif (i % W in (0, W - 1) or i // W in (0, H - 1)) and c not in "WX":
            errors.append(f"the frame must be steel (or the exit), not '{c}' at {i % W},{i // W}")
    if cells.count("P") != 1:
        errors.append("exactly one inbox (P) needed")
    if "X" not in cells:
        errors.append("an exit (X) is needed")
    return errors


def check_cave(cave):
    """Errors of the cave's numbers and map"""
    errors = check_map(cave.cells)
    for key, lo, hi in (("time", 1, 999), ("diamonds", 0, 255), ("value", 0, 255), ("extra", 0, 255),
                        ("speed", 20, 255), ("amoeba", 0, 255), ("magic", 0, 255)):
        if not lo <= getattr(cave, key) <= hi:
            errors.append(f"{key} must be {lo}-{hi}, not {getattr(cave, key)}")
    if len(cave.name) > NAME_LEN or any(c not in NAME_CHARS for c in cave.name):
        errors.append(f"the name must be at most {NAME_LEN} of {NAME_CHARS.strip()}")
    return errors


# The file the game loads (src/main.c, cave_file): after two bytes of load
# address the time (2 bytes), diamonds, value, extra, amoeba, magic, speed,
# the name (24 bytes, closed by 0) and the map as E_* codes.

def cave_bytes(cave):
    errors = check_cave(cave)
    if errors:
        raise CaveError("; ".join(errors))
    head = bytes([cave.time & 255, cave.time >> 8, cave.diamonds, cave.value, cave.extra,
                  cave.amoeba, cave.magic, cave.speed])
    return head + cave.name.encode("ascii").ljust(NAME_FIELD, b"\0") + bytes(CHAR_CODE[c] for c in cave.cells)


def cave_from_bytes(data):
    """The cave of a file's contents (without load address), or None for
    an empty slot"""
    time = data[0] | data[1] << 8
    if not time:
        return None
    name = data[8:8 + NAME_FIELD].split(b"\0")[0].decode("ascii", "replace")
    cells = [CODE_CHAR.get(b, "?") for b in data[32:32 + W * H]]
    return Cave(name, time, data[2], data[3], data[4], data[7], data[5], data[6], cells)


# ---------------------------------------------------------------- .cave files

CAVE_KEYS = ("name", "time", "diamonds", "value", "extra", "speed", "amoeba", "magic", "demo", "shuffle")


def parse_cave_text(path):
    """A .cave file: its keys (strings, as written) and its map rows"""
    keys, rows, in_map = {}, [], False
    for line in open(path, encoding="utf-8").read().splitlines():
        if in_map:
            if line.strip():
                rows.append(line)
            continue
        if not line.strip() or line.startswith("#"):
            continue
        if line.strip() == "map:":
            in_map = True
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k not in CAVE_KEYS:
            raise CaveError(f"{path}: unknown key '{k}'")
        keys[k] = v.strip()
    if len(rows) != H or any(len(r) != W for r in rows):
        raise CaveError(f"{path}: the map must be {H} lines of {W} characters")
    return keys, rows


def read_cave_file(path):
    """A .cave file as a Cave in its first level"""
    keys, rows = parse_cave_text(path)
    first = lambda k, d: int(keys.get(k, d).split()[0])
    cave = Cave(clean_name(keys.get("name", "")), first("time", "150"), first("diamonds", "10"),
                first("value", "10"), first("extra", "15"), first("speed", "160"),
                first("amoeba", "0"), first("magic", "0"), list("".join(rows)))
    return cave


def write_cave_file(path, cave, source=""):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Smaragd Dash cave: see tools/mkcave.py for the format.\n")
        if source:
            f.write(f"# {source}\n")
        f.write(f"name     = {cave.name}\ntime     = {cave.time}\ndiamonds = {cave.diamonds}\n"
                f"value    = {cave.value}\nextra    = {cave.extra}\nspeed    = {cave.speed}\n")
        if cave.amoeba:
            f.write(f"amoeba   = {cave.amoeba}\n")
        if cave.magic:
            f.write(f"magic    = {cave.magic}\n")
        f.write("map:\n" + "\n".join(cave.rows()) + "\n")


# ---------------------------------------------------------------- BDCFF: reading

class C64Random:
    """The random numbers of Boulder Dash 1 on the C64 (GDash's
    C64RandomGenerator): random fills with a RandSeed"""

    def __init__(self, seed):
        self.s1, self.s2 = seed // 256 % 256, seed % 256

    def next(self):
        t1 = (self.s1 & 1) << 7
        t2 = (self.s2 >> 1) & 0x7F
        r = self.s2 + ((self.s2 & 1) << 7)
        carry = r >> 8
        r = (r & 0xFF) + carry + 0x13
        carry = r >> 8
        self.s2 = r & 0xFF
        r = self.s1 + carry + t1
        carry = r >> 8
        r = (r & 0xFF) + carry + t2
        self.s1 = r & 0xFF
        return self.s1


class GlibRandom:
    """GLib's g_rand (Mersenne Twister) as GDash uses it for its own random
    fills: g_rand_set_seed, then g_rand_int_range(0, 256)"""

    def __init__(self, seed):
        mt = [seed & 0xFFFFFFFF]
        for i in range(1, 624):
            mt.append((1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & 0xFFFFFFFF)
        self.mt, self.i = mt, 624

    def next(self):
        mt = self.mt
        if self.i >= 624:
            for k in range(624):
                y = (mt[k] & 0x80000000) | (mt[(k + 1) % 624] & 0x7FFFFFFF)
                mt[k] = mt[(k + 397) % 624] ^ (y >> 1) ^ (0x9908B0DF if y & 1 else 0)
            self.i = 0
        y = mt[self.i]
        self.i += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y % 256


def cdiv(a, b):
    """C's integer division (towards zero)"""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def cmod(a, b):
    return a - b * cdiv(a, b)


SCHEDULING = ("ms", "bd1", "bd2", "plck", "crdr7", "bd1atari", "bd2ckatari")
# The Engine tag: its timing and CaveDelay per level. All of them (C64
# engines) have PAL timing and draw objects round the edge, line-shifted.
ENGINES = {
    "BD1": ("bd1", (12, 6, 3, 1, 0)), "BD2": ("bd2", (9, 8, 7, 6, 6)), "PLCK": ("plck", None),
    "1STB": ("plck", None), "CRDR": ("crdr7", None), "CRLI": ("plck", None)}


class BdcffCave:
    """A [cave] of a BDCFF file, with the properties of its [game] as
    defaults"""

    def __init__(self, number):
        self.number = number
        self.props = {}    # upper-case name: value string
        self.map = []      # [map] lines
        self.objects = []  # (levels, line)

    def prop(self, name, default=None):
        return self.props.get(name.upper(), default)

    def name(self):
        return self.prop("Name", f"CAVE {self.number}")


# [game] properties that are the game's, not defaults for its caves
GAME_ONLY = {"NAME", "DESCRIPTION", "AUTHOR", "DATE", "WWW", "DIFFICULTY", "STORY", "REMARK",
             "CHARSET", "FONTSET", "LIVES", "MAXIMUMLIVES", "BONUSLIFE", "TITLESCREEN",
             "TITLESCREENSCROLL", "LEVELS", "CAVES"}


class BdcffFile:
    def __init__(self, path):
        self.path = path
        self.version = "0.32"
        self.game = {}
        self.caves = []
        self.mapcodes = {}
        self.parse(open(path, encoding="latin-1").read())

    def parse(self, text):
        state, levels, cave = "start", None, None
        for line in text.replace("\r", "").split("\n"):
            if not line:
                continue
            if state != "map" and line.startswith(";"):
                continue
            if line.startswith("["):
                tag = line.strip().lower()
                if tag == "[cave]":
                    cave = BdcffCave(len(self.caves) + 1)
                    cave.props.update((k, v) for k, v in self.game.items() if k not in GAME_ONLY)
                    self.caves.append(cave)
                    state = "cave"
                elif tag in ("[/cave]", "[/map]", "[/objects]", "[/demo]", "[/replay]", "[/highscore]"):
                    state = "cave" if tag != "[/cave]" else "game"
                elif tag == "[map]":
                    state = "map"
                elif tag == "[objects]":
                    state, levels = "objects", None
                elif tag.startswith("[level="):
                    levels = {int(n) - 1 for n in re.findall(r"\d+", tag) if 1 <= int(n) <= LEVELS}
                elif tag == "[/level]":
                    levels = None
                elif tag == "[mapcodes]":
                    state = "mapcodes"
                elif tag == "[/mapcodes]":
                    state = "game"
                elif tag == "[bdcff]":
                    state = "bdcff"
                elif tag == "[game]":
                    state = "game"
                elif tag in ("[demo]", "[replay]", "[highscore]"):
                    state = "skip"
                continue
            if state == "map":
                cave.map.append(line)
                continue
            line = line.rstrip()
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if state == "bdcff" and key.lower() == "version":
                self.version = value
            elif state == "game":
                self.game[key.upper()] = value
            elif state == "mapcodes" and len(key) == 1:
                self.mapcodes[key] = value
            elif state == "cave":
                cave.props[key.upper()] = value
            elif state == "objects":
                cave.objects.append((levels, line))


class Renderer:
    """Draws a BDCFF cave in one level as GDash does: the [map] or the
    random fill, then the objects. Cells hold GDash element names (upper
    case)."""

    def __init__(self, bd, cave, level, subst):
        self.bd, self.cave, self.level, self.subst = bd, cave, level, subst
        size = [int(n) for n in cave.prop("Size", "40 22").split()]
        self.w, self.h = size[0], size[1]
        self.view = size[2:6] if len(size) >= 6 else [0, 0, self.w - 1, self.h - 1]
        c64 = (cave.prop("Engine") or "").upper() in ENGINES
        self.lineshift = self.flag("BorderProperties.lineshift", c64)
        self.wrap = self.flag("BorderProperties.objectwraparound", c64)
        self.cells = None

    def flag(self, name, default):
        v = self.cave.prop(name)
        return default if v is None else v.lower() == "true"

    def element(self, name):
        name = name.upper()
        if name in self.subst:
            return self.subst[name]
        return name

    def per_level(self, name, default):
        """A property with a value per level: the one of this level (BDCFF
        repeats the last one given)"""
        v = self.cave.prop(name)
        if v is None:
            return default
        vals = v.split()
        return vals[min(self.level, len(vals) - 1)]

    def get(self, x, y):
        if self.lineshift:
            x, y = lineshift(self.w, self.h, x, y)
            y = cmod(y + self.h, self.h)
        else:
            x, y = cmod(x + self.w, self.w), cmod(y + self.h, self.h)
        return self.cells[y * self.w + x]

    def put(self, x, y, e):
        if e == "NONE":
            return
        if self.wrap:
            if self.lineshift:
                x, y = lineshift(self.w, self.h, x, y)
            else:
                x, y = cmod(x + self.w, self.w), cmod(y + self.h, self.h)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.cells[y * self.w + x] = e

    @staticmethod
    def fill_element(randm, initial, pairs):
        """What a random fill puts for the random number randm: the last
        of the (element, probability) pairs it is below"""
        e = initial
        for elem, prob in pairs:
            if randm < prob:
                e = elem
        return e

    def render(self):
        c, w, h = self.cave, self.w, self.h
        border = self.element(c.prop("InitialBorder", "STEELWALL"))
        if c.map:
            codes = dict(OTHER_CHARS)
            codes.update(CHAR_NAME)
            codes.update(self.bd.mapcodes)
            self.cells = [border] * (w * h)
            for y, line in enumerate(c.map[:h]):
                for x, ch in enumerate(line[:w]):
                    self.cells[y * w + x] = self.element(codes.get(ch, f"'{ch}'"))
        else:
            seed = int(self.per_level("RandSeed", str(self.level)))
            rand = C64Random(seed) if seed >= 0 else GlibRandom(self.level)
            fill = c.prop("RandomFill", "").split()
            pairs = [(self.element(fill[i]), int(fill[i + 1])) for i in range(0, len(fill) - 1, 2)]
            initial = self.element(c.prop("InitialFill", "DIRT"))
            self.cells = [initial] * (w * h)
            for y in range(1, h - 1):
                for x in range(w):
                    self.cells[y * w + x] = self.fill_element(rand.next(), initial, pairs)
            for y in range(h):
                self.cells[y * w] = self.cells[y * w + w - 1] = border
            for x in range(w):
                self.cells[x] = self.cells[(h - 1) * w + x] = border
        for levels, line in c.objects:
            if levels is None or self.level in levels:
                self.draw(line)
        # BDCFF 0.32: intermissions without a size were 40x22 with the top
        # left 20x12 visible (GDash's hack)
        if self.bd.version == "0.32" and self.flag("Intermission", False) and not c.map:
            self.view = [0, 0, 19, 11]
            for x0, y0 in ((0, 11), (19, 0)):
                for y in range(y0, h):
                    for x in range(x0, w):
                        self.put(x, y, border)
        return self.cells

    def draw(self, line):
        kind, _, args = line.partition("=")
        kind, a = kind.strip().lower(), args.split()
        num = lambda i: int(a[i])
        el = lambda i: self.element(a[i])
        if kind == "point":
            self.put(num(0), num(1), el(2))
        elif kind == "line":
            self.line(num(0), num(1), num(2), num(3), el(4))
        elif kind in ("rectangle", "fillrect"):
            x1, x2 = sorted((num(0), num(2)))
            y1, y2 = sorted((num(1), num(3)))
            edge = el(4)
            inside = el(5) if kind == "fillrect" and len(a) > 5 else edge
            for y in range(y1, y2 + 1):
                for x in range(x1, x2 + 1):
                    if y in (y1, y2) or x in (x1, x2):
                        self.put(x, y, edge)
                    elif kind == "fillrect":
                        self.put(x, y, inside)
        elif kind == "raster":
            x1, y1, nx, ny, dx, dy = (num(i) for i in range(6))
            x2, y2 = x1 + (nx - 1) * dx, y1 + (ny - 1) * dy
            x1, x2 = sorted((x1, x2))
            y1, y2 = sorted((y1, y2))
            for y in range(y1, y2 + 1, max(dy, 1)):
                for x in range(x1, x2 + 1, max(dx, 1)):
                    self.put(x, y, el(6))
        elif kind in ("add", "addbackward"):
            dx, dy, search, put = num(0), num(1), el(2), el(3)
            cells = [(x, y) for y in range(self.h) for x in range(self.w)]
            for x, y in (reversed(cells) if kind == "addbackward" else cells):
                if self.cells[y * self.w + x] == search:
                    self.put(x + dx, y + dy, put)
        elif kind in ("randomfill", "randomfillc64"):
            x1, x2 = sorted((num(0), num(2)))
            y1, y2 = sorted((num(1), num(3)))
            seed = int(a[4 + self.level])
            if seed < 0:
                seed = self.level
            rand = C64Random(seed) if kind == "randomfillc64" else GlibRandom(seed)
            initial, rest = el(9), a[10:]
            pairs = [(self.element(rest[i]), int(rest[i + 1])) for i in range(0, len(rest) - 1, 2)][:4]
            only = self.element(rest[-1]) if len(rest) % 2 else None
            for y in range(y1, y2 + 1):
                for x in range(x1, x2 + 1):
                    e = self.fill_element(rand.next(), initial, pairs)
                    if only is None or self.get(x, y) == only:
                        self.put(x, y, e)
        elif kind == "floodfill":
            fill, search = el(2), el(3)
            if fill != search:
                self.flood(num(0), num(1), lambda e: e == search, fill)
        elif kind == "boundaryfill":
            fill, edge = el(2), el(3)
            self.flood(num(0), num(1), lambda e: e != edge, fill)
        elif kind == "copypaste":
            x1, x2 = sorted((num(0), num(2)))
            y1, y2 = sorted((num(1), num(3)))
            dx, dy = num(4), num(5)
            mirror = len(a) > 6 and a[6].lower() == "mirror"
            flip = len(a) > 7 and a[7].lower() == "flip"
            w, h = x2 - x1 + 1, y2 - y1 + 1
            clip = [[self.get(x1 + x, y1 + y) for x in range(w)] for y in range(h)]
            for y in range(h):
                for x in range(w):
                    self.put(dx + (w - 1 - x if mirror else x), dy + (h - 1 - y if flip else y), clip[y][x])
        elif kind == "maze":
            raise CaveError("has a maze, which only GDash draws: save the file flat first "
                            "(gdash in.bd --save-flat out.bd -q)")
        else:
            raise CaveError(f"unknown object '{kind}'")

    def line(self, x1, y1, x2, y2, e):
        steep = abs(y2 - y1) > abs(x2 - x1)
        if steep:
            x1, y1, x2, y2 = y1, x1, y2, x2
        if x1 > x2:
            x1, x2, y1, y2 = x2, x1, y2, y1
        dx, dy, err, y = x2 - x1, abs(y2 - y1), 0, y1
        step = 1 if y1 < y2 else -1
        for x in range(x1, x2 + 1):
            self.put(*((y, x) if steep else (x, y)), e)
            err += dy
            if err * 2 >= dx:
                y += step
                err -= dx

    def flood(self, x, y, take, fill):
        """GDash's flood and boundary fills (4 neighbours), without recursion"""
        done, todo = set(), [(x, y)]
        while todo:
            x, y = todo.pop()
            if not (0 <= x < self.w and 0 <= y < self.h) or (x, y) in done:
                continue
            if not take(self.cells[y * self.w + x]):
                continue
            done.add((x, y))
            todo += [(x - 1, y), (x, y - 1), (x + 1, y), (x, y + 1)]
        for x, y in done:
            self.put(x, y, fill)


def lineshift(w, h, x, y):
    """GDash's lineshift_wrap_coords_only_x: off the right edge into the
    next row, as on the C64"""
    if x < 0:
        y -= cdiv(-x, w) + 1
        x = cmod(x, w) + w
    elif x >= w:
        y += cdiv(x, w)
        x = cmod(x, w)
    return x, y


def bdcff_cave(bd, cave, level, subst):
    """A cave of a BDCFF file in one level (0-4) as the game plays it;
    CaveError if it cannot"""
    r = Renderer(bd, cave, level, subst)
    cells = r.render()
    x1, y1, x2, y2 = r.view
    vw, vh = x2 - x1 + 1, y2 - y1 + 1
    if vw > W or vh > H:
        raise CaveError(f"is {vw}x{vh} cells, the game has {W}x{H}")
    out = Cave(clean_name(cave.name()))
    notes = out.notes
    if (vw, vh) != (W, H):
        notes.append(f"{vw}x{vh} cells, in the top left corner")
    names = ["STEELWALL"] * (W * H)
    for y in range(vh):
        for x in range(vw):
            names[y * W + x] = cells[(y1 + y) * r.w + x1 + x]
    missing = {}
    chars = []
    for n in names:
        c = n if n in CHAR_CODE else NAME_CHAR.get(n)
        if c is None:
            missing[n] = missing.get(n, 0) + 1
            c = "?"
        chars.append(c)
    if missing:
        what = ", ".join(f"{n} ({k}x)" for n, k in sorted(missing.items(), key=lambda t: -t[1]))
        raise CaveError(f"has what the game does not: {what}")
    edge = [i for i in range(W * H) if (i % W in (0, W - 1) or i // W in (0, H - 1)) and chars[i] not in "WX"]
    if any(chars[i] == "P" for i in edge):
        raise CaveError("has its inbox on the edge (GDash wraps such caves round, the game cannot)")
    for i in edge:
        chars[i] = "W"
    if edge:
        notes.append(f"{len(edge)} cells of the edge made steel")
    inboxes = [i for i, c in enumerate(chars) if c == "P"]
    if not inboxes:
        raise CaveError("has no inbox")
    if len(inboxes) > 1:
        keep = inboxes[0] if r.flag("ActiveGuyIsFirst", True) else inboxes[-1]
        for i in inboxes:
            if i != keep:
                chars[i] = " "
        notes.append(f"{len(inboxes) - 1} more inbox(es) left out: one player only")
    if "X" not in chars:
        raise CaveError("has no exit")
    out.cells = chars

    # the numbers
    num = lambda name, default: int(float(r.per_level(name, default)))
    pal = r.flag("PALTiming", ENGINES.get((cave.prop("Engine") or "").upper()) is not None)
    factor = 1.2 if pal else 1.0
    out.time = max(1, min(999, round(num("CaveTime", "999") * factor)))
    need = num("DiamondsRequired", "10")
    if need <= 0:
        need += chars.count("d")
    out.diamonds = max(1, min(255, need))
    dv = (cave.prop("DiamondValue") or "0 0").split()
    out.value = min(255, int(dv[0]))
    out.extra = min(255, int(dv[1])) if len(dv) > 1 else 0
    out.speed = cave_speed(r, cave, cells)
    for key, prop in (("amoeba", "AmoebaTime"), ("magic", "MagicWallTime")):
        v = round(num(prop, "999") * factor)
        elem = "a" if key == "amoeba" else "M"
        if v > 255:
            if elem in chars:
                notes.append(f"{prop} {v} s cut to 255 s")
            v = 255
        setattr(out, key, v)
    if "a" in chars:
        t = cave.prop("AmoebaThreshold")
        if t is not None and float(t.split()[min(level, len(t.split()) - 1)]) <= 1:
            # a part of the cave's cells, as GDash reads it
            cells_max = int(float(t.split()[min(level, len(t.split()) - 1)]) * r.w * r.h + 0.5)
            if cells_max != 200:
                notes.append(f"the amoeba turns to boulders at 200 cells, not {cells_max}")
    for prop, ok in (("DiagonalMovement", "false"), ("Gravitation", "down"),
                     ("PushingBoulderProb", "0.25"), ("AmoebaGrowthProb", "0.03125 0.25")):
        v = cave.prop(prop)
        if v is not None and v.lower() != ok and [float(n) for n in re.findall(r"[\d.]+", v)] != \
                [float(n) for n in re.findall(r"[\d.]+", ok)]:
            notes.append(f"{prop}={v} is played as {ok}")
    return out


def cave_speed(r, cave, cells):
    """Milliseconds per cave tick, as GDash computes them (for C64 caves
    from the CaveDelay and what the whole cave holds, cells as drawn)"""
    engine = ENGINES.get((cave.prop("Engine") or "").upper())
    sched = engine[0] if engine else "ms"
    delays = engine[1] if engine and engine[1] else (0,) * LEVELS
    if cave.prop("CaveDelay") is not None and sched == "ms":
        sched = "plck"
    if cave.prop("FrameTime") is not None:
        sched = "ms"
    if cave.prop("CaveScheduling") is not None:
        sched = cave.prop("CaveScheduling").lower()
    if sched not in SCHEDULING:
        sched = "ms"
    if sched == "ms":
        ms = int(r.per_level("FrameTime", str((180, 160, 140, 120, 120)[r.level])))
    else:
        ckdelay = int(r.per_level("CaveDelay", str(delays[r.level])))
        chars = [c if c in CHAR_CODE else NAME_CHAR.get(c, "") for c in cells]
        cur = sum(CKDELAY.get(c, 0) for c in chars)
        anim = 2600 * (("a" in chars) * 2 + any(c in "QoOq" for c in chars) + any(c in "CbBc" for c in chars))
        inter = r.flag("Intermission", False)
        # GDash's ints and doubles: (cur + anim) / 1000 is an int division
        if sched == "bd1":
            ms = (60 if inter else 88) + 3.66 * ckdelay + (cur + anim) // 1000
        elif sched == "bd1atari":
            ms = (65 + 2.88 * ckdelay if inter else 74 + 3.2 * ckdelay) + cur // 1000
        elif sched == "bd2":
            ms = max(60 + (cur + anim) // 1000, ckdelay * 20)
        elif sched == "plck":
            ms = max(65 + cur // 1000, ckdelay * 20)
        elif sched == "bd2ckatari":
            ms = max(40 + cur // 1000, ckdelay * 20)
        else:  # crdr7
            ms = max(130 + cur // 1000, ckdelay * 20)
    return max(20, min(255, int(ms)))


def read_bd(path, level, subst, which=None):
    """The caves of a .bd file: [(number, BdcffCave, Cave or CaveError)]"""
    bd = BdcffFile(path)
    out = []
    for c in bd.caves:
        if which and c.number not in which:
            continue
        try:
            out.append((c.number, c, bdcff_cave(bd, c, level, subst)))
        except (CaveError, ValueError, IndexError) as e:
            out.append((c.number, c, e if isinstance(e, CaveError) else CaveError(f"cannot be read: {e}")))
    return bd, out


# ---------------------------------------------------------------- BDCFF: writing

def write_bd(path, caves, title):
    """caves as a BDCFF file for GDash, with the rules of Boulder Dash 1
    (Engine=BD1) in the game's timing: real seconds, milliseconds per tick"""
    out = ["[BDCFF]", "Version=0.5", "[game]", f"Name={title}", f"Caves={len(caves)}", "Levels=1", ""]
    for cave in caves:
        out += ["[cave]", f"Name={cave.name}", "Engine=BD1", "Intermission=false", "Size=40 22",
                f"CaveTime={cave.time}", f"DiamondsRequired={cave.diamonds}",
                f"DiamondValue={cave.value} {cave.extra}", "CaveScheduling=ms", "PALTiming=false",
                f"FrameTime={cave.speed}", f"AmoebaTime={cave.amoeba}", f"MagicWallTime={cave.magic}",
                "", "[map]"] + cave.rows() + ["[/map]", "[/cave]", ""]
    out += ["[/game]", "[/BDCFF]"]
    with open(path, "w", encoding="latin-1", newline="\r\n") as f:
        f.write("\n".join(out) + "\n")


# ---------------------------------------------------------------- the disk

TRACKS, SECTORS, DIR_TRACK = 80, 40, 40


class Disk:
    """A D81 image; the files are rewritten in place, as the game does"""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.img = bytearray(f.read())
        if len(self.img) != TRACKS * SECTORS * 256:
            raise CaveError(f"{path}: not a D81 disk image")

    def sector(self, t, s):
        o = ((t - 1) * SECTORS + s) * 256
        return memoryview(self.img)[o:o + 256]

    def files(self):
        """{name: (track, sector)} of the directory"""
        out, t, s = {}, DIR_TRACK, 3
        while t:
            sec = self.sector(t, s)
            for e in range(0, 256, 32):
                if sec[e + 2]:
                    name = bytes(sec[e + 5:e + 21]).rstrip(b"\xa0").decode("ascii", "replace")
                    out[name] = (sec[e + 3], sec[e + 4])
            t, s = sec[0], sec[1]
        return out

    def blocks(self, name):
        t, s = self.files()[name]
        while t:
            blk = self.sector(t, s)
            yield blk
            t, s = blk[0], blk[1]

    def read(self, name):
        data = b""
        for blk in self.blocks(name):
            data += bytes(blk[2:] if blk[0] else blk[2:blk[1] + 1])
        return data

    def rewrite(self, name, data):
        """The file's contents in place: it keeps its length"""
        if len(data) != len(self.read(name)):
            raise CaveError(f"{name} has another length")
        pos = 0
        for blk in self.blocks(name):
            n = 254 if blk[0] else blk[1] - 1
            blk[2:2 + n] = data[pos:pos + n]
            pos += n

    def slots(self):
        return sorted(n for n in self.files() if re.fullmatch(SLOT + r"\d\d", n))

    def save(self):
        with open(self.path, "wb") as f:
            f.write(self.img)


def read_slot(disk, name):
    return cave_from_bytes(disk.read(name)[2:])


def write_slot(disk, name, cave):
    old = disk.read(name)
    data = old[:2] + (cave_bytes(cave) if cave else bytes(32 + W * H))
    disk.rewrite(name, data)


# ---------------------------------------------------------------- the commands

def numbers(spec, top):
    """'3' or '2-5' as a set of numbers"""
    a, _, b = spec.partition("-")
    lo, hi = int(a), int(b or a)
    if not 1 <= lo <= hi <= top:
        raise CaveError(f"'{spec}': 1-{top}")
    return set(range(lo, hi + 1))


def options(args):
    opts = {"cave": None, "level": 1, "slot": None, "as": {}}
    rest = []
    while args:
        a = args.pop(0)
        if a in ("--cave", "--level", "--slot", "--as"):
            if not args:
                raise CaveError(f"{a} needs a value")
            v = args.pop(0)
            if a == "--as":
                name, _, ch = v.partition("=")
                if ch not in CHAR_CODE:
                    raise CaveError(f"--as {v}: the character must be one of '{''.join(CHAR_CODE)}'")
                opts["as"][name if len(name) == 1 else name.upper()] = ch
            elif a == "--level":
                opts["level"] = int(v)
                if not 1 <= opts["level"] <= LEVELS:
                    raise CaveError(f"--level: 1-{LEVELS}")
            else:
                opts[a[2:]] = v
        else:
            rest.append(a)
    return opts, rest


def subst_names(opts):
    """--as for map characters and names: both as element names"""
    out = {}
    for k, ch in opts["as"].items():
        out[OTHER_CHARS.get(k, CHAR_NAME.get(k, f"'{k}'")).upper() if len(k) == 1 else k] = ch
        if len(k) == 1:
            out[f"'{k}'"] = ch
    return out


def load_caves(path, opts):
    """[(label, Cave or CaveError)] of a .bd or .cave file"""
    if path.lower().endswith(".cave"):
        try:
            cave = read_cave_file(path)
            errors = check_cave(cave)
            return [(os.path.basename(path), CaveError("; ".join(errors)) if errors else cave)]
        except CaveError as e:
            return [(os.path.basename(path), e)]
    which = numbers(opts["cave"], 9999) if opts["cave"] else None
    _, caves = read_bd(path, opts["level"] - 1, subst_names(opts), which)
    return [(f"cave {n:2}", CaveError(f"{c.name()}: {cave}") if isinstance(cave, CaveError) else cave)
            for n, c, cave in caves]


def show(label, cave):
    if isinstance(cave, CaveError):
        print(f"  {label}: not possible - {cave}")
        return False
    extra = f" ({'; '.join(cave.notes)})" if cave.notes else ""
    print(f"  {label}: {cave.name}, {cave.diamonds} in {cave.time} s, {cave.speed} ms{extra}")
    return True


def cmd_list(args):
    opts, rest = options(args)
    path = rest[0]
    if path.lower().endswith(".d81"):
        disk = Disk(path)
        for name in disk.slots():
            cave = read_slot(disk, name)
            print(f"  {name}: " + (f"{cave.name}, {cave.diamonds} in {cave.time} s" if cave else "(empty)"))
        return
    caves = load_caves(path, opts)
    ok = sum(show(label, cave) for label, cave in caves)
    print(f"{ok} of {len(caves)} caves can be played (level {opts['level']})")


def cmd_import(args):
    opts, rest = options(args)
    disk = Disk(rest[0])
    slots = disk.slots()
    if not slots:
        raise CaveError(f"{rest[0]}: no slots ({SLOT}01, ...) - not a disk of Smaragd Dash with the editor?")
    first = int(opts["slot"] or 1)
    if not 1 <= first <= len(slots):
        raise CaveError(f"--slot: 1-{len(slots)}")
    todo = []
    for path in rest[1:]:
        todo += load_caves(path, opts)
    good = [(label, cave) for label, cave in todo if not isinstance(cave, CaveError)]
    for label, cave in todo:
        if isinstance(cave, CaveError):
            show(label, cave)
    room = len(slots) - first + 1
    if len(good) > room:
        raise CaveError(f"{len(good)} caves, but only {room} slots from {first} on (--cave or --slot)")
    for (label, cave), name in zip(good, slots[first - 1:]):
        write_slot(disk, name, cave)
        show(f"{name} <- {label}", cave)
    disk.save()
    print(f"{len(good)} of {len(todo)} caves written to {rest[0]}")


def cmd_export(args):
    opts, rest = options(args)
    disk = Disk(rest[0])
    slots = disk.slots()
    which = numbers(opts["slot"], len(slots)) if opts["slot"] else set(range(1, len(slots) + 1))
    caves = [c for i, n in enumerate(slots) if i + 1 in which and (c := read_slot(disk, n))]
    if not caves:
        raise CaveError("no caves in these slots")
    write_bd(rest[1], caves, "Smaragd Dash own caves")
    print(f"{len(caves)} caves written to {rest[1]}")


def cmd_empty(args):
    opts, rest = options(args)
    disk = Disk(rest[0])
    slots = disk.slots()
    which = numbers(opts["slot"], len(slots)) if opts["slot"] else set(range(1, len(slots) + 1))
    for i, name in enumerate(slots):
        if i + 1 in which:
            write_slot(disk, name, None)
    disk.save()
    print(f"{len(which)} slots emptied")


def cmd_convert(args):
    opts, rest = options(args)
    src, dst = rest
    if src.lower().endswith(".cave"):
        cave = read_cave_file(src)
        write_bd(dst, [cave], cave.name)
        print(f"{dst}: {cave.name}")
        return
    caves = load_caves(src, opts)
    if dst.lower().endswith(".cave"):
        good = [(label, c) for label, c in caves if not isinstance(c, CaveError)]
        if len(caves) != 1 or not good:
            for label, c in caves:
                show(label, c)
            raise CaveError("one cave to a .cave file: --cave N")
        write_cave_file(dst, good[0][1], f"from {os.path.basename(src)}, level {opts['level']}")
        show(dst, good[0][1])
        return
    os.makedirs(dst, exist_ok=True)
    n = 0
    for label, cave in caves:
        if show(label, cave):
            slug = re.sub(r"[^a-z0-9]+", "-", cave.name.lower()).strip("-") or "cave"
            n += 1
            write_cave_file(os.path.join(dst, f"{n:02d}-{slug}.cave"), cave,
                            f"from {os.path.basename(src)}, cave {label.split()[0]}, level {opts['level']}")
    print(f"{n} caves written to {dst}")


COMMANDS = {"list": (cmd_list, 1), "import": (cmd_import, 2), "export": (cmd_export, 2),
            "empty": (cmd_empty, 1), "convert": (cmd_convert, 2)}


def main():
    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        sys.exit(__doc__)
    fn, need = COMMANDS[args[0]]
    try:
        if len(options(list(args[1:]))[1]) < need:
            sys.exit(__doc__)
        fn(args[1:])
    except (CaveError, OSError, ValueError) as e:
        sys.exit(f"cavekit: {e}")


if __name__ == "__main__":
    main()
