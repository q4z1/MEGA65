#!/usr/bin/env python3
"""Smaragd Dash cave kit: caves between the game's disk, its .cave files
and GDash (BDCFF, .bd files). Needs nothing but Python 3.

  cavekit.py list    <disk.d81 | game.bd | game.gds | file.cave> [--game G]
  cavekit.py import  <disk.d81> <game.bd | game.gds | file.cave>... [options]
  cavekit.py disks   <disk.d81> <game.bd | game.gds | file.cave>... [--out DIR] [--name NAME] [options]
  cavekit.py export  <disk.d81> <game.bd> [--game G] [--slot N[-M]]
  cavekit.py empty   <disk.d81> [--game G] [--slot N[-M]]
  cavekit.py rename  <disk.d81> <G> <NAME>
  cavekit.py upgrade <old.d81> <new.d81>
  cavekit.py convert <game.bd | game.gds | file.cave> <out.cave | out.bd | directory>

The disk has three games of own caves: partitions (1581 subdirectories)
OWN1, OWN2, OWN3, each with 20 slots OWN01, OWN02, ... that the game's
editor saves into and plays; the editor renames them (at most 8 letters,
digits, spaces and :.!-,), and so does rename. G is a game's name or its
number (1-3); without --game a command takes the slots of all games one
after the other (slot 21 is the second game's first). A disk of an older
version has its 20 slots in its directory, a game without a name: upgrade
copies its own caves (and the high scores) onto a disk of this version.

list shows the own caves on a disk, game by game, or the caves of a file.

import puts caves into the slots of the disk, from slot 1 on (or --slot N),
over what is there. From a .bd file it takes all its caves (or --cave N or
N-M, counted from 1) in all five levels (or only in --level L, 1-5). A
cave that cannot be imported is named with the reason and left out; the
others are written.

A slot has the cave's first level in OWNnn and every other level that
differs from it in OWNnn-2 ... OWNnn-5 (empty otherwise: the game plays the
first level then). The game plays the slots one after the other, and after
the last one the next level, as GDash does. A cave from a .cave file, or
with --level, has one level; so has one the editor saves. A disk of an
older version has no files for the levels: only the first is written.

disks makes disks to play whole games from: copies of the disk (the
game's), each file a game of its own (named after the file, as
Boulder_Dash_1.bd: BD1, or --name; a game of more caves than 20 goes on in
a second one, BD1-2), three games on a disk, the other slots empty -
<name>.d81, or <name>-1.d81, <name>-2.d81, ... for more, in DIR (default:
the current directory), <name> after the first file.

A .gds file (a C64 game, as GDash imports them) is read through GDash's
own code: toolchain/tools/bin/gdash-oracle of this repository (built by
toolchain/tools/build-tools.sh), or the program $GDASH_ORACLE names, saves
it as .bd first - as GDash itself does with File / Save as.

export writes the own caves of the disk (or a game's, or --slot N-M) as a .bd file for
GDash, with their levels where only the values differ (a .bd file has one
map for all levels; where the maps differ, only the first level). empty
empties all slots of the disk (or a game's, or --slot N-M), with their levels.

convert turns a .bd file into .cave files (one per cave, into a
directory, or a single one with --cave N), for building them into the
game (caves/) - for caves with the elements of Boulder Dash 1 only -, or
a .cave file into a .bd file.

Options for import, disks, list and convert:
  --cave N[-M]      only these caves of the .bd file
  --level L         the level to take (1-5); import and disks take all
                    five without it, list and convert level 1
  --as NAME=NAME2   put the element NAME2 in place of NAME (BDCFF names or
                    map characters), e.g. --as HEXPANDINGWALL=WALL

The own caves play by GDash's rules: the game has GDash's engine for them
(src/gdengine.c) with all its elements, and takes a cave as GDash draws
and starts it - its objects (lines, rectangles, random fills with the
C64's random numbers, ...), its properties and their defaults, those of
the C64 engines (Engine=BD1, ...) included. A cave is at most 40x22 cells;
a small one (an intermission of 20x12) stands still in the middle of the
screen.

The .cave format of the game's own caves is described in tools/mkcave.py;
its map characters are the ones BDCFF uses.
"""

import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata

W, H = 40, 22
NAME_LEN = 21          # what the status line has room for
NAME_FIELD = 24        # the name's bytes in a cave file
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /:.!-,"  # the game's font
SLOT = "OWN"           # the slots on the disk: OWN01, OWN02, ...
LEVELS = 5             # BDCFF's


class CaveError(Exception):
    pass


# ---------------------------------------------------------------- the game's own caves (.cave)

# The .cave files' elements: Boulder Dash 1's and the few of GDash's that are
# close to it, by their map characters - BDCFF's (GD_CHAR), and for nut and
# clock, which have none there, the game's own
CAVE_CHARS = " .wWrdPXMaQoOqCbBc" + "xveHs"   # BD1; expanding walls, hidden exit, slime
CAVE_OWN_CHARS = {"n": "NUT", "k": "CLOCK"}
EXIT_CHARS = "XH"                              # the exit, or the hidden one


class Cave:
    """A cave of the game's own (.cave): one level, 40x22 map characters"""

    def __init__(self, name="", time=150, diamonds=10, value=10, extra=15, speed=160,
                 amoeba=0, magic=0, cells=None, clock=10, slime=7):
        self.name, self.time, self.diamonds = name, time, diamonds
        self.value, self.extra, self.speed = value, extra, speed
        self.amoeba, self.magic, self.clock, self.slime = amoeba, magic, clock, slime
        self.cells = cells or empty_map()
        self.notes = []

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
    """The name in the letters the game has, at most NAME_LEN long: German
    umlauts as two letters (HOEHLE), other letters without their accents"""
    name = name.upper()
    for a, b in (("Ä", "AE"), ("Ö", "OE"), ("Ü", "UE")):
        name = name.replace(a, b)
    name = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    name = "".join(c if c in NAME_CHARS else " " for c in name)
    return " ".join(name.split())[:NAME_LEN].rstrip()


def check_map(cells):
    """Errors of a .cave file's map (none: it can be played)"""
    errors = []
    if len(cells) != W * H:
        return [f"the map must be {W}x{H}"]
    for i, c in enumerate(cells):
        if c not in CAVE_CHARS and c not in CAVE_OWN_CHARS:
            errors.append(f"unknown map character '{c}' at {i % W},{i // W}")
        elif (i % W in (0, W - 1) or i // W in (0, H - 1)) and c not in "W" + EXIT_CHARS:
            errors.append(f"the frame must be steel (or the exit), not '{c}' at {i % W},{i // W}")
    if cells.count("P") != 1:
        errors.append("exactly one inbox (P) needed")
    if not any(c in cells for c in EXIT_CHARS):
        errors.append("an exit (X, or H hidden) is needed")
    return errors


CAVE_KEYS = ("name", "time", "diamonds", "value", "extra", "speed", "amoeba", "magic", "clock", "slime", "demo",
             "shuffle")


def parse_cave_text(path):
    """A .cave file - the game's older text format for a cave, before its
    caves were GDash's files - : its keys (strings, as written) and its map
    rows. "key = value" lines (# comments), then "map:" and 22 lines of 40
    characters (CAVE_CHARS: BDCFF's, n a nut, k a clock). The keys: name,
    time (seconds), diamonds (needed), value and extra (points per emerald
    before and after the exit opens), speed (ms per step), amoeba and magic
    (seconds), clock (seconds a clock gives, 10), slime (the C64 games' mask
    of how seldom it lets something through, 7), demo (opening moves for
    the solver); time, diamonds, speed, amoeba and magic one value or one
    per level (tools/mkcave.py scales one: time -10 %, diamonds +10 %, speed
    -5 ms a level), shuffle ("no", or a seed per higher level)."""
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
                first("amoeba", "0"), first("magic", "0"), list("".join(rows)), first("clock", "10"),
                first("slime", "7"))
    errors = check_map(cave.cells)
    if errors:
        raise CaveError(f"{path}: {errors[0]}")
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
        if cave.clock != 10:
            f.write(f"clock    = {cave.clock}\n")
        if cave.slime != 7:
            f.write(f"slime    = {cave.slime}\n")
        f.write("map:\n" + "\n".join(cave.rows()) + "\n")


# ---------------------------------------------------------------- GDash's tables

# The tables below are GDash's (https://github.com/revvv/gdash-export-CrLi,
# MIT license, Copyright (c) 2007-2018 GDash Project), written out by its own
# code: its elements, and the properties of its caves with their defaults.
#
# An element per line: its code here (GDash's order, without its "scanned"
# twins), its name in GDash's code (O_...), its name in BDCFF files, its map
# character (0: none), its flags (P_* below), the time the C64 took for it in
# microseconds (for the speed of C64 caves), what a pneumatic hammer makes of
# it (255: nothing).

GD_ELEMENTS = """\
0 SPACE SPACE 32 64 0 255
1 DIRT DIRT 46 32960 0 255
2 DIRT_SLOPED_UP_RIGHT DIRTSLOPEDUPRIGHT 0 204 0 255
3 DIRT_SLOPED_UP_LEFT DIRTSLOPEDUPLEFT 0 202 0 255
4 DIRT_SLOPED_DOWN_LEFT DIRTSLOPEDDOWNLEFT 0 210 0 255
5 DIRT_SLOPED_DOWN_RIGHT DIRTSLOPEDDOWNRIGHT 0 212 0 255
6 DIRT_BALL DIRTBALL 0 131294 120 255
7 DIRT_BALL_F DIRTBALLf 0 0 120 255
8 DIRT_LOOSE DIRTLOOSE 0 131264 60 255
9 DIRT_LOOSE_F DIRTLOOSEf 0 0 60 255
10 DIRT2 DIRT2 0 192 0 255
11 BRICK WALL 119 8254 0 0
12 BRICK_SLOPED_UP_RIGHT WALLSLOPEDUPRIGHT 0 8236 0 0
13 BRICK_SLOPED_UP_LEFT WALLSLOPEDUPLEFT 0 8234 0 0
14 BRICK_SLOPED_DOWN_LEFT WALLSLOPEDDOWNLEFT 0 8242 0 0
15 BRICK_SLOPED_DOWN_RIGHT WALLSLOPEDDOWNRIGHT 0 8244 0 0
16 BRICK_NON_SLOPED WALLNONSLOPED 0 8192 0 0
17 MAGIC_WALL MAGICWALL 77 8192 0 0
18 PRE_OUTBOX OUTBOX 88 0 0 255
19 OUTBOX OUTBOXopen 0 0 0 255
20 PRE_INVIS_OUTBOX HIDDENOUTBOX 72 0 0 255
21 INVIS_OUTBOX HIDDENOUTBOXopen 0 0 0 255
22 STEEL STEELWALL 87 2048 0 255
23 STEEL_SLOPED_UP_RIGHT STEELWALLSLOPEDUPRIGHT 0 2060 0 255
24 STEEL_SLOPED_UP_LEFT STEELWALLSLOPEDUPLEFT 0 2058 0 255
25 STEEL_SLOPED_DOWN_LEFT STEELWALLSLOPEDDOWNLEFT 0 2066 0 255
26 STEEL_SLOPED_DOWN_RIGHT STEELWALLSLOPEDDOWNRIGHT 0 2068 0 255
27 STEEL_EXPLODABLE STEELWALLDESTRUCTABLE 69 8192 0 0
28 STEEL_EATABLE STEELWALLEATABLE 0 0 0 255
29 BRICK_EATABLE WALLEATABLE 0 0 0 255
30 STONE BOULDER 114 147486 156 255
31 STONE_F BOULDERf 82 0 156 255
32 FLYING_STONE FLYINGBOULDER 0 278558 156 255
33 FLYING_STONE_F FLYINGBOULDERf 0 0 156 255
34 MEGA_STONE MEGABOULDER 0 147486 156 255
35 MEGA_STONE_F MEGABOULDERf 0 0 156 255
36 DIAMOND DIAMOND 100 131102 156 255
37 DIAMOND_F DIAMONDf 68 0 156 255
38 FLYING_DIAMOND FLYINGDIAMOND 0 262174 156 255
39 FLYING_DIAMOND_F FLYINGDIAMONDf 0 0 156 255
40 NUT NUT 0 147486 156 255
41 NUT_F NUTf 0 0 0 255
42 BLADDER_SPENDER BLADDERSPENDER 0 0 20 255
43 INBOX INBOX 80 0 0 255
44 H_EXPANDING_WALL HEXPANDINGWALL 120 40960 111 0
45 V_EXPANDING_WALL VEXPANDINGWALL 118 40960 111 0
46 EXPANDING_WALL EXPANDINGWALL 101 40960 111 0
47 H_EXPANDING_STEEL_WALL HEXPANDINGSTEELWALL 0 2048 111 255
48 V_EXPANDING_STEEL_WALL VEXPANDINGSTEELWALL 0 2048 111 255
49 EXPANDING_STEEL_WALL EXPANDINGSTEELWALL 0 2048 111 255
50 EXPANDING_WALL_SWITCH EXPANDINGWALLSWITCH 0 0 0 255
51 CREATURE_SWITCH FIREFLYBUTTERFLYSWITCH 0 0 0 255
52 BITER_SWITCH BITERSWITCH 0 0 0 255
53 REPLICATOR_SWITCH REPLICATORSWITCH 0 0 0 255
54 CONVEYOR_SWITCH CONVEYORSWITCH 0 0 0 255
55 CONVEYOR_DIR_SWITCH CONVEYORDIRECTIONSWITCH 0 0 0 255
56 ACID ACID 0 0 128 255
57 FALLING_WALL FALLINGWALL 0 8192 80 0
58 FALLING_WALL_F FALLINGWALLf 0 8192 80 0
59 BOX SOKOBANBOX 0 16384 0 255
60 TIME_PENALTY TIMEPENALTY 0 2048 0 255
61 GRAVESTONE GRAVESTONE 71 2048 0 255
62 STONE_GLUED GLUEDBOULDER 0 30 0 255
63 DIAMOND_GLUED GLUEDDIAMOND 0 30 0 255
64 DIAMOND_KEY DIAMONDRELEASEKEY 0 0 0 255
65 TRAPPED_DIAMOND TRAPPEDDIAMOND 0 2048 0 255
66 CLOCK CLOCK 0 0 0 255
67 DIRT_GLUED GLUEDDIRT 0 0 0 255
68 KEY_1 KEY1 0 0 0 255
69 KEY_2 KEY2 0 0 0 255
70 KEY_3 KEY3 0 0 0 255
71 DOOR_1 DOOR1 0 0 0 255
72 DOOR_2 DOOR2 0 0 0 255
73 DOOR_3 DOOR3 0 0 0 255
74 POT POT 0 0 0 255
75 GRAVITY_SWITCH GRAVITY_SWITCH 0 0 0 255
76 PNEUMATIC_HAMMER PNEUMATIC_HAMMER 0 0 0 255
77 TELEPORTER TELEPORTER 0 0 0 255
78 SKELETON SKELETON 0 0 0 255
79 WATER WATER 0 0 100 255
80 WATER_1 WATER1 0 0 0 255
81 WATER_2 WATER2 0 0 0 255
82 WATER_3 WATER3 0 0 0 255
83 WATER_4 WATER4 0 0 0 255
84 WATER_5 WATER5 0 0 0 255
85 WATER_6 WATER6 0 0 0 255
86 WATER_7 WATER7 0 0 0 255
87 WATER_8 WATER8 0 0 0 255
88 WATER_9 WATER9 0 0 0 255
89 WATER_10 WATER10 0 0 0 255
90 WATER_11 WATER11 0 0 0 255
91 WATER_12 WATER12 0 0 0 255
92 WATER_13 WATER13 0 0 0 255
93 WATER_14 WATER14 0 0 0 255
94 WATER_15 WATER15 0 0 0 255
95 WATER_16 WATER16 0 0 0 255
96 COW_1 COWl 0 4096 384 255
97 COW_2 COWu 0 4096 384 255
98 COW_3 COWr 0 4096 384 255
99 COW_4 COWd 0 4096 384 255
100 COW_ENCLOSED_1 COW_ENCLOSED1 0 0 120 255
101 COW_ENCLOSED_2 COW_ENCLOSED2 0 0 120 255
102 COW_ENCLOSED_3 COW_ENCLOSED3 0 0 120 255
103 COW_ENCLOSED_4 COW_ENCLOSED4 0 0 120 255
104 COW_ENCLOSED_5 COW_ENCLOSED5 0 0 120 255
105 COW_ENCLOSED_6 COW_ENCLOSED6 0 0 120 255
106 COW_ENCLOSED_7 COW_ENCLOSED7 0 0 120 255
107 WALLED_DIAMOND WALLED_DIAMOND 0 8192 0 36
108 WALLED_KEY_1 WALLED_KEY1 0 8192 0 68
109 WALLED_KEY_2 WALLED_KEY2 0 8192 0 69
110 WALLED_KEY_3 WALLED_KEY3 0 8192 0 70
111 AMOEBA AMOEBA 97 256 260 255
112 AMOEBA_2 AMOEBA2 0 33024 260 255
113 REPLICATOR REPLICATOR 0 2048 210 255
114 CONVEYOR_LEFT CONVEYORLEFT 0 2048 256 255
115 CONVEYOR_RIGHT CONVEYORRIGHT 0 2048 0 255
116 LAVA LAVA 0 2048 0 255
117 SWEET SWEET 0 0 0 255
118 VOODOO DUMMY 70 256 0 255
119 SLIME SLIME 115 0 211 255
120 BLADDER BLADDER 0 0 267 255
121 BLADDER_1 BLADDERd1 0 0 0 255
122 BLADDER_2 BLADDERd2 0 0 0 255
123 BLADDER_3 BLADDERd3 0 0 0 255
124 BLADDER_4 BLADDERd4 0 0 0 255
125 BLADDER_5 BLADDERd5 0 0 0 255
126 BLADDER_6 BLADDERd6 0 0 0 255
127 BLADDER_7 BLADDERd7 0 0 0 255
128 BLADDER_8 BLADDERd8 0 0 0 255
129 WAITING_STONE WAITINGBOULDER 0 16414 176 255
130 CHASING_STONE CHASINGBOULDER 0 16414 269 255
131 GHOST GHOST 103 0 50 255
132 FIREFLY_1 FIREFLYl 81 4608 384 255
133 FIREFLY_2 FIREFLYu 111 4608 384 255
134 FIREFLY_3 FIREFLYr 79 4608 384 255
135 FIREFLY_4 FIREFLYd 113 4608 384 255
136 ALT_FIREFLY_1 A_FIREFLYl 0 512 384 255
137 ALT_FIREFLY_2 A_FIREFLYu 0 512 384 255
138 ALT_FIREFLY_3 A_FIREFLYr 0 512 384 255
139 ALT_FIREFLY_4 A_FIREFLYd 0 512 384 255
140 BUTTER_1 BUTTERFLYl 67 512 384 255
141 BUTTER_2 BUTTERFLYu 98 512 384 255
142 BUTTER_3 BUTTERFLYr 66 512 384 255
143 BUTTER_4 BUTTERFLYd 99 512 384 255
144 ALT_BUTTER_1 A_BUTTERFLYl 0 4608 384 255
145 ALT_BUTTER_2 A_BUTTERFLYu 0 4608 384 255
146 ALT_BUTTER_3 A_BUTTERFLYr 0 4608 384 255
147 ALT_BUTTER_4 A_BUTTERFLYd 0 4608 384 255
148 STONEFLY_1 STONEFLYl 0 512 384 255
149 STONEFLY_2 STONEFLYu 0 512 384 255
150 STONEFLY_3 STONEFLYr 0 512 384 255
151 STONEFLY_4 STONEFLYd 0 512 384 255
152 BITER_1 BITERu 0 0 518 255
153 BITER_2 BITERr 0 0 518 255
154 BITER_3 BITERd 0 0 518 255
155 BITER_4 BITERl 0 0 518 255
156 DRAGONFLY_1 DRAGONFLYl 0 4608 256 255
157 DRAGONFLY_2 DRAGONFLYu 0 4608 256 255
158 DRAGONFLY_3 DRAGONFLYr 0 4608 256 255
159 DRAGONFLY_4 DRAGONFLYd 0 4608 256 255
160 PRE_PL_1 GUYBIRTH1 0 65536 0 255
161 PRE_PL_2 GUYBIRTH2 0 65536 0 255
162 PRE_PL_3 GUYBIRTH3 0 65536 0 255
163 PLAYER GUY 0 66304 32 255
164 PLAYER_BOMB GUYBOMB 0 66304 25 255
165 PLAYER_ROCKET_LAUNCHER GUYROCKETLAUNCER 0 66304 25 255
166 PLAYER_GLUED GUYGLUED 0 768 0 255
167 PLAYER_STIRRING GUYSTIRRING 0 66304 0 255
168 ROCKET_LAUNCHER ROCKET_LAUNCHER 0 0 0 255
169 ROCKET_1 ROCKETr 0 0 40 255
170 ROCKET_2 ROCKETu 0 0 40 255
171 ROCKET_3 ROCKETl 0 0 40 255
172 ROCKET_4 ROCKETd 0 0 40 255
173 BOMB BOMB 0 0 0 255
174 BOMB_TICK_1 IGNITEDBOMB1 0 1024 0 255
175 BOMB_TICK_2 IGNITEDBOMB2 0 0 0 255
176 BOMB_TICK_3 IGNITEDBOMB3 0 0 0 255
177 BOMB_TICK_4 IGNITEDBOMB4 0 0 0 255
178 BOMB_TICK_5 IGNITEDBOMB5 0 0 0 255
179 BOMB_TICK_6 IGNITEDBOMB6 0 0 0 255
180 BOMB_TICK_7 IGNITEDBOMB7 0 0 0 255
181 NITRO_PACK NITRO 0 147998 0 255
182 NITRO_PACK_F NITROf 0 512 0 255
183 NITRO_PACK_EXPLODE NITROtriggered 0 512 0 255
184 PRE_CLOCK_1 CLOCKBIRTH1 0 0 280 255
185 PRE_CLOCK_2 CLOCKBIRTH2 0 0 280 255
186 PRE_CLOCK_3 CLOCKBIRTH3 0 0 280 255
187 PRE_CLOCK_4 CLOCKBIRTH4 0 0 280 255
188 PRE_DIA_1 DIAMONDBIRTH1 0 1024 280 255
189 PRE_DIA_2 DIAMONDBIRTH2 0 0 280 255
190 PRE_DIA_3 DIAMONDBIRTH3 0 0 280 255
191 PRE_DIA_4 DIAMONDBIRTH4 0 0 280 255
192 PRE_DIA_5 DIAMONDBIRTH5 0 0 280 255
193 EXPLODE_1 EXPLOSION1 0 1024 280 255
194 EXPLODE_2 EXPLOSION2 0 0 280 255
195 EXPLODE_3 EXPLOSION3 0 0 280 255
196 EXPLODE_4 EXPLOSION4 0 0 280 255
197 EXPLODE_5 EXPLOSION5 0 0 280 255
198 PRE_STONE_1 BOULDERBIRTH1 0 0 280 255
199 PRE_STONE_2 BOULDERBIRTH2 0 0 280 255
200 PRE_STONE_3 BOULDERBIRTH3 0 0 280 255
201 PRE_STONE_4 BOULDERBIRTH4 0 0 280 255
202 PRE_STEEL_1 STEELWALLBIRTH1 0 0 280 255
203 PRE_STEEL_2 STEELWALLBIRTH2 0 0 280 255
204 PRE_STEEL_3 STEELWALLBIRTH3 0 0 280 255
205 PRE_STEEL_4 STEELWALLBIRTH4 0 0 280 255
206 GHOST_EXPL_1 GHOSTEXPLOSION1 0 0 280 255
207 GHOST_EXPL_2 GHOSTEXPLOSION2 0 0 280 255
208 GHOST_EXPL_3 GHOSTEXPLOSION3 0 0 280 255
209 GHOST_EXPL_4 GHOSTEXPLOSION4 0 0 280 255
210 BOMB_EXPL_1 BOMBEXPLOSION1 0 0 280 255
211 BOMB_EXPL_2 BOMBEXPLOSION2 0 0 280 255
212 BOMB_EXPL_3 BOMBEXPLOSION3 0 0 280 255
213 BOMB_EXPL_4 BOMBEXPLOSION4 0 0 280 255
214 NITRO_EXPL_1 NITROEXPLOSION1 0 0 280 255
215 NITRO_EXPL_2 NITROEXPLOSION2 0 0 280 255
216 NITRO_EXPL_3 NITROEXPLOSION3 0 0 280 255
217 NITRO_EXPL_4 NITROEXPLOSION4 0 0 280 255
218 AMOEBA_2_EXPL_1 AMOEBA2EXPLOSION1 0 0 280 255
219 AMOEBA_2_EXPL_2 AMOEBA2EXPLOSION2 0 0 280 255
220 AMOEBA_2_EXPL_3 AMOEBA2EXPLOSION3 0 0 280 255
221 AMOEBA_2_EXPL_4 AMOEBA2EXPLOSION4 0 0 280 255
222 NUT_CRACK_1 NUTCRACK1 0 30 280 255
223 NUT_CRACK_2 NUTCRACK2 0 30 280 255
224 NUT_CRACK_3 NUTCRACK3 0 30 280 255
225 NUT_CRACK_4 NUTCRACK4 0 30 280 255
226 PLAYER_PNEUMATIC_LEFT GUYHAMMERl 0 66304 0 255
227 PLAYER_PNEUMATIC_RIGHT GUYHAMMERr 0 66304 0 255
228 PNEUMATIC_ACTIVE_LEFT HAMMERACTIVEl 0 0 0 255
229 PNEUMATIC_ACTIVE_RIGHT HAMMERACTIVEr 0 0 0 255
230 UNKNOWN UNKNOWN 0 2048 0 255
231 NONE NONE 0 0 0 255
"""

# A property of a cave per line: GDash's name of it, its name in BDCFF files
# (-: none), its type (GD_* below), its flags (32: a part of the cave's
# size), the number of values (5: one per level), the default, then what the
# engines BD1, BD2, PLCK, 1stB, CrDr and CrLi set it to (.: they do not).

GD_PROPERTIES = """\
selectable Selectable 6 0 1 1 . . . . . .
intermission_instantlife IntermissionProperties.instantlife 6 0 1 0 1 1 1 0 0 0
intermission Intermission 6 1 1 0 . . . . . .
intermission_rewardlife IntermissionProperties.rewardlife 6 0 1 1 0 0 0 1 1 1
w Size 2 1 1 40 . . . . . .
h Size 2 1 1 22 . . . . . .
x1 Size 2 5 1 0 . . . . . .
y1 Size 2 5 1 0 . . . . . .
x2 Size 2 5 1 39 . . . . . .
y2 Size 2 5 1 21 . . . . . .
level_diamonds DiamondsRequired 3 1 5 10,10,10,10,10 . . . . . .
level_time CaveTime 3 1 5 999,999,999,999,999 . . . . . .
max_time CaveMaxTime 2 0 1 999 999 999 999 999 999 999
scheduling CaveScheduling 13 1 1 0 1 2 3 3 4 3
pal_timing PALTiming 6 0 1 0 1 1 1 1 1 1
level_speed FrameTime 3 1 5 180,160,140,120,120 . . . . . .
level_hatching_delay_frame HatchingDelay 3 0 5 21,21,21,21,21 . . . . . .
level_ckdelay CaveDelay 3 1 5 0,0,0,0,0 12,6,3,1,0 9,8,7,6,6 . . . .
level_hatching_delay_time HatchingTime 3 0 5 2,2,2,2,2 2,2,2,2,2 2,2,2,2,2 2,2,2,2,2 2,2,2,2,2 2,2,2,2,2 2,2,2,2,2
level_timevalue TimeValue 3 0 5 1,2,3,4,5 . . . . . .
diamond_value DiamondValue 2 1 1 0 . . . . . .
extra_diamond_value DiamondValue 2 1 1 0 . . . . . .
level_rand RandSeed 3 4 5 0,1,2,3,4 . . . . . .
initial_border InitialBorder 9 4 1 22 . . . . . .
initial_fill InitialFill 9 4 1 1 . . . . . .
random_fill_1 RandomFill 9 4 1 1 . . . . . .
random_fill_probability_1 RandomFill 2 4 1 0 . . . . . .
random_fill_2 RandomFill 9 4 1 1 . . . . . .
random_fill_probability_2 RandomFill 2 4 1 0 . . . . . .
random_fill_3 RandomFill 9 4 1 1 . . . . . .
random_fill_probability_3 RandomFill 2 4 1 0 . . . . . .
random_fill_4 RandomFill 9 4 1 1 . . . . . .
random_fill_probability_4 RandomFill 2 4 1 0 . . . . . .
diagonal_movements DiagonalMovement 6 0 1 0 0 0 0 . . .
active_is_first_found ActiveGuyIsFirst 6 0 1 1 0 0 0 1 1 1
snap_element SnapEffect 9 0 1 0 0 0 0 0 0 .
pushing_stone_prob PushingBoulderProb 4 0 1 250000 250000 250000 250000 250000 250000 250000
pushing_stone_prob_sweet PushingBoulderProb 4 0 1 1000000 1000000 1000000 1000000 1000000 1000000 1000000
mega_stones_pushable_with_sweet PushingMegaStonesAfterSweet 6 0 1 0 . . . . . .
infinite_rockets RocketLauncher.infinite 6 0 1 0 . . . . . .
pneumatic_hammer_frame PneumaticHammer.frames 2 0 1 5 . . . . . .
hammered_walls_reappear PneumaticHammer.wallsreappear 6 0 1 0 . . . . . .
hammered_wall_reappear_frame PneumaticHammer.wallsreappearframes 2 0 1 100 . . . . . .
level_bonus_time BonusTime 3 0 5 30,30,30,30,30 . . . . . .
voodoo_collects_diamonds DummyProperties.diamondcollector 6 0 1 0 0 0 0 1 1 1
voodoo_dies_by_stone DummyProperties.penalty 6 0 1 0 0 0 0 1 1 1
voodoo_disappear_in_explosion DummyProperties.destructable 6 0 1 1 1 1 1 1 1 1
voodoo_any_hurt_kills_player DummyProperties.alwayskillsplayer 6 0 1 0 0 0 0 0 0 0
level_penalty_time PenaltyTime 3 0 5 30,30,30,30,30 . . . . . .
amoeba_timer_started_immediately AmoebaProperties.immediately 6 0 1 1 1 0 0 0 0 0
amoeba_timer_wait_for_hatching AmoebaProperties.waitforhatching 6 0 1 0 0 0 0 1 1 1
level_amoeba_threshold AmoebaThreshold 3 32 5 200,200,200,200,200 200,200,200,200,200 200,200,200,200,200 . . . .
level_amoeba_time AmoebaTime 3 0 5 999,999,999,999,999 . . . . . .
amoeba_growth_prob AmoebaGrowthProb 4 0 1 31250 31250 31250 31250 31250 31250 31250
amoeba_fast_growth_prob AmoebaGrowthProb 4 0 1 250000 250000 250000 250000 250000 250000 250000
amoeba_too_big_effect AMOEBABOULDEReffect 10 0 1 30 . . . . . .
amoeba_enclosed_effect AMOEBADIAMONDeffect 10 0 1 36 . . . 188 188 188
level_amoeba_2_threshold Amoeba2Threshold 3 32 5 200,200,200,200,200 . . . . . .
level_amoeba_2_time Amoeba2Time 3 0 5 999,999,999,999,999 . . . . . .
amoeba_2_growth_prob Amoeba2GrowthProb 4 0 1 31250 . . . . . .
amoeba_2_fast_growth_prob Amoeba2GrowthProb 4 0 1 250000 . . . . . .
amoeba_2_explodes_by_amoeba Amoeba2Properties.explode 6 0 1 1 . . . . . .
amoeba_2_explosion_effect AMOEBA2EXPLOSIONeffect 10 0 1 0 . . . . . .
amoeba_2_too_big_effect AMOEBA2BOULDEReffect 10 0 1 30 . . . . . .
amoeba_2_enclosed_effect AMOEBA2DIAMONDeffect 10 0 1 36 . . . . . .
amoeba_2_looks_like AMOEBA2LOOKSLIKEeffect 10 0 1 112 . . . . . .
level_magic_wall_time MagicWallTime 3 0 5 999,999,999,999,999 . . . . . .
magic_timer_zero_is_infinite MagicWallProperties.zeroisinfinite 6 0 1 1 1 1 1 1 0 0
magic_timer_wait_for_hatching MagicWallProperties.waitforhatching 6 0 1 0 0 0 0 1 1 1
magic_diamond_to MagicWallProperties 9 0 1 31 . . . . . .
magic_stone_to MagicWallProperties 9 0 1 37 . . . . . .
magic_mega_stone_to MagicWallProperties.megastoneto 9 0 1 182 . . . . . .
magic_nitro_pack_to MagicWallProperties.nitropackto 9 0 1 35 . . . . . .
magic_nut_to MagicWallProperties.nutto 9 0 1 41 . . . . . .
magic_flying_stone_to MagicWallProperties.flyingstoneto 9 0 1 39 . . . . . .
magic_flying_diamond_to MagicWallProperties.flyingdiamondto 9 0 1 33 . . . . . .
magic_wall_stops_amoeba MagicWallProperties.convertamoeba 6 0 1 1 0 0 0 . . .
magic_wall_breakscan MagicWallProperties.breakscan 6 0 1 0 1 . . . . .
slime_predictable - 6 2 1 1 1 1 . 1 1 1
level_slime_permeability SlimePermeability 5 1 5 1000000,1000000,1000000,1000000,1000000 . . . . . .
level_slime_permeability_c64 SlimePermeabilityC64 3 1 5 0,0,0,0,0 . . . . . .
level_slime_seed_c64 SlimePredictableC64.seed 3 0 5 -1,-1,-1,-1,-1 . . . . . .
slime_eats_1 SlimeProperties 9 0 1 36 . . . . . .
slime_converts_1 SlimeProperties 9 0 1 37 . . . . . .
slime_eats_2 SlimeProperties 9 0 1 30 . . . . . .
slime_converts_2 SlimeProperties 9 0 1 31 . . . . . .
slime_eats_3 SlimeProperties 9 0 1 40 . . . . . .
slime_converts_3 SlimeProperties 9 0 1 41 . . . . . .
acid_eats_this AcidProperties 9 0 1 1 . . . . . .
acid_spread_ratio AcidProperties 4 0 1 31250 . . . . . .
acid_turns_to ACIDEffect 10 0 1 195 . . . . . .
biter_delay_frame BiterProperties 2 0 1 0 . . . . . .
biter_eat BiterProperties 9 0 1 36 . . . . . .
bladder_converts_by BladderProperties 9 0 1 118 . . . . . .
expanding_wall_changed ExpandingWallDirection.changed 6 0 1 0 . . . . . .
replicators_active ReplicatorActive 6 0 1 1 . . . . . .
replicator_delay_frame ReplicatorDelayFrame 2 0 1 4 . . . . . .
conveyor_belts_active ConveyorBeltActive 6 0 1 1 . . . . . .
conveyor_belts_direction_changed ConveyorBeltDirection.changed 6 0 1 0 . . . . . .
water_does_not_flow_down WaterProperties.doesnotflowdown 6 0 1 0 . . . . 1 .
nut_turns_to_when_crushed Nut.whencrushed 9 0 1 222 . . . . . .
stone_falling_effect BOULDERfallingeffect 10 0 1 31 . . . . . .
stone_bouncing_effect BOULDERbouncingeffect 10 0 1 30 . . . . . .
diamond_falling_effect DIAMONDfallingeffect 10 0 1 37 . . . . . .
diamond_bouncing_effect DIAMONDbouncingeffect 10 0 1 36 . . . . . .
firefly_explode_to FireflyExplodeTo 9 0 1 193 . . . . . .
alt_firefly_explode_to AltFireflyExplodeTo 9 0 1 193 . . . . . .
butterfly_explode_to ButterflyExplodeTo 9 0 1 188 . . . . . .
alt_butterfly_explode_to AltButterflyExplodeTo 9 0 1 188 . . . . . .
stonefly_explode_to StoneflyExplodeTo 9 0 1 198 . . . . . .
dragonfly_explode_to DragonflyExplodeTo 9 0 1 193 . . . . . .
explosion_effect EXPLOSIONEffect 10 0 1 0 . . . . . .
diamond_birth_effect DIAMONDBIRTHEffect 10 0 1 36 . . . . . .
bomb_explosion_effect BOMBEXPLOSIONeffect 10 0 1 11 . . . . . .
nitro_explosion_effect NITROEXPLOSIONeffect 10 0 1 0 . . . . . .
expanding_wall_looks_like EXPANDINGWALLLOOKSLIKEeffect 10 0 1 11 . . . . . .
dirt_looks_like DIRTLOOKSLIKEeffect 10 0 1 1 . . . 10 . .
creatures_backwards EnemyDirectionProperties.startbackwards 6 0 1 0 0 0 0 . . .
creatures_direction_auto_change_time EnemyDirectionProperties.time 2 0 1 0 0 0 0 . . .
creatures_direction_auto_change_on_start EnemyDirectionProperties.changeathatching 6 0 1 0 0 0 0 1 0 0
gravity Gravitation 12 0 1 5 . . . . . .
gravity_switch_active GravitationSwitchActive 6 0 1 0 . . . . . .
skeletons_needed_for_pot SkeletonsForPot 2 0 1 5 . . . . . .
gravity_change_time GravitationChangeDelay 2 0 1 10 . . . . . .
diamond_sound Diamond.sound 6 0 1 1 . . . . . .
stone_sound Stone.sound 6 0 1 1 . . . . . .
nut_sound Nut.sound 6 0 1 1 . . . . . .
nitro_sound NitroPack.sound 6 0 1 1 . . . . . .
expanding_wall_sound ExpandingWall.sound 6 0 1 1 . . . . . .
falling_wall_sound FallingWall.sound 6 0 1 1 . . . . . .
amoeba_sound AmoebaProperties.sound 6 0 1 1 . . . . . .
magic_wall_sound MagicWallProperties.sound 6 0 1 1 . . . . . .
slime_sound SlimeProperties.sound 6 0 1 1 . . . . . .
lava_sound LavaProperties.sound 6 0 1 1 . . . . . .
replicator_sound ReplicatorProperties.sound 6 0 1 1 . . . . . .
acid_spread_sound AcidProperties.sound 6 0 1 1 . . . . . .
biter_sound BiterProperties.sound 6 0 1 1 . . . . . .
bladder_sound BladderProperties.sound 6 0 1 1 . . . . . .
water_sound WaterProperties.sound 6 0 1 1 . . . . . .
pneumatic_hammer_sound PneumaticHammer.sound 6 0 1 1 . . . . . .
bladder_spender_sound BladderSpender.sound 6 0 1 1 . . . . . .
bladder_convert_sound BladderConvert.sound 6 0 1 1 . . . . . .
gravity_change_sound GravityChange.sound 6 0 1 1 . . . . . .
creature_direction_auto_change_sound EnemyDirectionProperties.sound 6 0 1 1 . . . . . .
skeletons_worth_diamonds SkeletonsWorthDiamonds 2 16 1 0 . . . . 1 .
lineshift BorderProperties.lineshift 6 0 1 0 1 1 1 1 1 1
wraparound_objects BorderProperties.objectwraparound 6 0 1 0 1 1 1 1 1 1
border_scan_first_and_last BorderProperties.scan 6 0 1 1 . . 0 . . .
short_explosions ShortExplosions 6 0 1 1 1 1 1 0 0 0
gravity_affects_all GravityAffectsAll 6 0 1 1 . . . . 0 .
explosion_3_effect EXPLOSION3S 10 0 1 196 . . . . . .
"""

GD_INT, GD_INT_LEVELS, GD_PROB, GD_PROB_LEVELS, GD_BOOL = 2, 3, 4, 5, 6
GD_ELEMENT, GD_EFFECT, GD_DIRECTION, GD_SCHEDULING = 9, 10, 12, 13
GD_RATIO = 32  # flag: written as a part of the cave's cells
GD_ENGINES = ("BD1", "BD2", "PLCK", "1STB", "CRDR", "CRLI")
DIRECTIONS = ("none", "up", "upright", "right", "downright", "down", "downleft", "left", "upleft")
SCHEDULINGS = ("ms", "bd1", "bd2", "plck", "crdr7", "bd1atari", "bd2ckatari")

# the flags of the elements (GDash's P_*)
P_SLOPED_LEFT, P_SLOPED_RIGHT, P_SLOPED_UP, P_SLOPED_DOWN = 1 << 1, 1 << 2, 1 << 3, 1 << 4
P_FLAGS = ("SCANNED", "SLOPED_LEFT", "SLOPED_RIGHT", "SLOPED_UP", "SLOPED_DOWN", "BLADDER_SLOPED",
           "AMOEBA_CONSUMES", "DIRT", "BLOWS_UP_FLIES", "EXPLODES_BY_HIT", "EXPLOSION_FIRST_STAGE",
           "NON_EXPLODABLE", "CCW", "CAN_BE_HAMMERED", "CAN_BE_PUSHED", "VISUAL_EFFECT", "PLAYER",
           "MOVED_BY_CONVEYOR_TOP", "MOVED_BY_CONVEYOR_BOTTOM")


class GdElement:
    def __init__(self, line):
        p = line.split()
        self.code, self.name, self.file = int(p[0]), p[1], p[2]
        self.char = chr(int(p[3])) if int(p[3]) else ""
        self.flags, self.ckdelay, self.hammered = int(p[4]), int(p[5]), int(p[6])


GD_EL = [GdElement(line) for line in GD_ELEMENTS.splitlines()]
O = {e.name: e.code for e in GD_EL}  # O["STONE"]: the code of O_STONE
# BDCFF names (GDash compares them without case), with GDash's other spellings
GD_NAME = {e.file.upper(): e.code for e in GD_EL}
GD_NAME.update({"HEXPANDING_WALL": O["H_EXPANDING_WALL"], "FALLING_DIAMOND": O["DIAMOND_F"],
                "FALLING_BOULDER": O["STONE_F"], "WALL2": O["STEEL_EXPLODABLE"],
                "BLADDERD9": O["BLADDER_8"]})
GD_NAME.update({f"EXPLOSION{i}S": O[f"EXPLODE_{i}"] for i in range(1, 6)})
GD_NAME.update({f"EXPLOSION{i}D": O[f"PRE_DIA_{i}"] for i in range(1, 6)})
# and the names of GDash's scanned twins, which stand for the element itself
GD_SCANNED_NAMES = """\
SCANN_DIRTBALL:6 SCANN_DIRTBALLf:7 SCANN_DIRTLOOSE:8 SCANN_DIRTLOOSEf:9 SCANN_BOULDER:30
SCANN_BOULDERf:31 SCANN_FLYINGBOULDER:32 SCANN_FLYINGBOULDERf:33 SCANN_MEGABOULDER:34
SCANN_MEGABOULDERf:35 SCANN_DIAMOND:36 SCANN_DIAMONDf:37 SCANN_FLYINGDIAMOND:38
SCANN_FLYINGDIAMONDf:39 SCANN_NUT:40 SCANN_NUTf:41 SCANN_HEXPANDINGWALL:44 SCANN_VEXPANDINGWALL:45
SCANN_EXPANDINGWALL:46 SCANN_HEXPANDINGSTEELWALL:47 SCANN_VEXPANDINGSTEELWALL:48
SCANN_EXPANDINGSTEELWALL:49 SCANN_ACID:56 SCANN_FALLINGWALLf:58 SCANN_COWl:96 SCANN_COWu:97
SCANN_COWr:98 SCANN_COWd:99 SCANN_AMOEBA:111 SCANN_AMOEBA2:112 SCANN_WAITINGBOULDER:129
SCANN_CHASINGBOULDER:130 SCANN_GHOST:131 SCANN_FIREFLYl:132 SCANN_FIREFLYu:133 SCANN_FIREFLYr:134
SCANN_FIREFLYd:135 SCANN_A_FIREFLYl:136 SCANN_A_FIREFLYu:137 SCANN_A_FIREFLYr:138
SCANN_A_FIREFLYd:139 SCANN_BUTTERFLYl:140 SCANN_BUTTERFLYu:141 SCANN_BUTTERFLYr:142
SCANN_BUTTERFLYd:143 SCANN_A_BUTTERFLYl:144 SCANN_A_BUTTERFLYu:145 SCANN_A_BUTTERFLYr:146
SCANN_A_BUTTERFLYd:147 SCANN_STONEFLYl:148 SCANN_STONEFLYu:149 SCANN_STONEFLYr:150
SCANN_STONEFLYd:151 SCANN_BITERu:152 SCANN_BITERr:153 SCANN_BITERd:154 SCANN_BITERl:155
SCANN_DRAGONFLYl:156 SCANN_DRAGONFLYu:157 SCANN_DRAGONFLYr:158 SCANN_DRAGONFLYd:159 SCANN_GUY:163
SCANN_GUYBOMB:164 SCANN_GUYROCKETLAUNCER:165 SCANN_ROCKETr:169 SCANN_ROCKETu:170 SCANN_ROCKETl:171
SCANN_ROCKETd:172 SCANN_NITRO:181 SCANN_NITROf:182 SCANN_NITROtriggered:183 CLOCKBIRTH0:184
DIAMONDBIRTH0:188 EXPLOSION0:193 BOULDERBIRTH0:198 STEELWALLBIRTH0:202 GHOSTEXPLOSION0:206
BOMBEXPLOSION0:210 NITROEXPLOSION0:214 AMOEBA2EXPLOSION0:218 NUTCRACK0:222
"""
GD_NAME.update({n.upper(): int(c) for n, c in (x.split(":") for x in GD_SCANNED_NAMES.split())})
GD_CHAR = {e.char: e.code for e in GD_EL if e.char}  # BDCFF's map characters


class GdProperty:
    def __init__(self, line):
        p = line.split()
        self.member, self.ident = p[0], "" if p[1] == "-" else p[1]
        self.type, self.flags, self.count = int(p[2]), int(p[3]), int(p[4])
        self.default = [int(v) for v in p[5].split(",")]
        self.engine = [None if v == "." else [int(n) for n in v.split(",")] for v in p[6:12]]


GD_PROPS = [GdProperty(line) for line in GD_PROPERTIES.splitlines()]
GD_MEMBER = {p.member: p for p in GD_PROPS}


# ---------------------------------------------------------------- BDCFF: reading

def c_int(s):
    """What C++'s >> reads as an int from s, or None"""
    m = re.match(r"\s*([+-]?\d+)", s)
    return int(m.group(1)) if m else None


def c_double(s):
    """What C++'s >> reads as a double from s, or None"""
    m = re.match(r"\s*([+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?)", s)
    return float(m.group(1)) if m else None


def gd_bool(s):
    if s == "1" or s.lower() in ("true", "on", "yes"):
        return 1
    if s == "0" or s.lower() in ("false", "off", "no"):
        return 0
    return None


class GdStored:
    """A cave's properties as GDash keeps them (CaveStored): GDash's name of
    each property, a list of its values"""

    def __init__(self):
        self.v = {p.member: list(p.default) for p in GD_PROPS}

    def copy(self):
        c = GdStored()
        c.v = {k: list(v) for k, v in self.v.items()}
        return c

    def __getitem__(self, member):
        return self.v[member][0]

    def engine(self, n):
        """GDash's defaults for engine n (C64Import::cave_set_engine_defaults)"""
        for p in GD_PROPS:
            if p.engine[n] is not None:
                self.v[p.member] = list(p.engine[n])

    def parse(self, p, s, ratio):
        """One value of property p from the string s, or None"""
        t = p.type
        if t in (GD_INT, GD_INT_LEVELS):
            if p.flags & GD_RATIO:
                d = c_double(s)
                # GDash refuses more than 1 here, but saves it (an amoeba
                # threshold bigger than the cave, as in its C64 imports)
                return int(d * ratio + 0.5) if d is not None and 0 <= d and d * ratio <= 16383 else None
            return c_int(s)
        if t in (GD_PROB, GD_PROB_LEVELS):
            d = c_double(s)
            return int(d * 1000000 + 0.5) if d is not None and 0 <= d <= 1 else None
        if t == GD_BOOL:
            return gd_bool(s)
        if t == GD_ELEMENT:
            return GD_NAME.get(s.upper())
        if t == GD_DIRECTION:
            return DIRECTIONS.index(s.lower()) if s.lower() in DIRECTIONS else None
        if t == GD_SCHEDULING:
            return SCHEDULINGS.index(s.lower()) if s.lower() in SCHEDULINGS else None
        return None

    def set(self, attrib, param, ratio):
        """A BDCFF line attrib=param as GDash reads it (struct_set_property):
        the properties of that name take the values in turn; one for each
        level takes the following ones too. True if attrib is known."""
        params = param.split(" ")
        i, found = 0, False
        for p in GD_PROPS:
            if not p.ident or p.ident.lower() != attrib.lower():
                continue
            found = True
            if p.type == GD_EFFECT:
                continue
            for j in range(p.count):
                if i >= len(params):
                    break
                v = self.parse(p, params[i], ratio)
                if v is not None:
                    self.v[p.member][j] = v
                    if p.type in (GD_INT_LEVELS, GD_PROB_LEVELS):
                        for k in range(j + 1, p.count):
                            self.v[p.member][k] = v
                    i += 1
        return found

    def tag(self, attrib, param):
        """A cave's BDCFF line (cave_process_tags_func), with GDash's special
        cases; True if known"""
        params = param.split(" ")
        a = attrib.lower()
        if a == "snapexplosions":
            b = gd_bool(param)
            if b is not None:
                self.v["snap_element"] = [O["EXPLODE_1"] if b else O["SPACE"]]
            return True
        if a == "bd1scheduling":
            if gd_bool(param) and self["scheduling"] == SCHEDULINGS.index("plck"):
                self.v["scheduling"] = [SCHEDULINGS.index("bd1")]
            return True
        if a == "engine":
            if param.upper() in GD_ENGINES:
                self.engine(GD_ENGINES.index(param.upper()))
            return True
        if a == "amoebaproperties":
            e1, e2 = (GD_NAME.get(params[i].upper()) if i < len(params) else None for i in (0, 1))
            if e1 is not None and e2 is not None:
                self.v["amoeba_too_big_effect"], self.v["amoeba_enclosed_effect"] = [e1], [e2]
            return True
        if a == "colors":
            return True
        if a == "effect":
            if len(params) == 2:
                for p in GD_PROPS:
                    if p.type == GD_EFFECT and p.ident.lower() == params[0].lower():
                        e = GD_NAME.get(params[1].upper())
                        if e is not None:
                            self.v[p.member] = [e]
                        break
                else:
                    special = {"bouncing_boulder": "stone_bouncing_effect", "explosion3s": "explosion_3_effect",
                               "starting_faling_diamond": "diamond_falling_effect", "dirt": "dirt_looks_like"}
                    e = GD_NAME.get(params[1].upper())
                    if params[0].lower() in special and e is not None:
                        self.v[special[params[0].lower()]] = [e]
                    elif params[0].lower() == "hexpanding_wall" and params[1].lower() == "steel_hexpanding_wall":
                        pass  # GDash reads it, but no element has that name
            return True
        return self.set(attrib, param, self["w"] * self["h"])


class BdcffCave:
    """A [cave] of a BDCFF file: its lines as they are"""

    def __init__(self, number):
        self.number = number
        self.lines = []    # attrib=param lines
        self.map = []      # [map] lines
        self.objects = []  # (levels, line)
        self.stored = None

    def prop(self, name, default=None):
        """A property as written (the last line of that name)"""
        v = default
        for line in self.lines:
            a, _, p = line.partition("=")
            if a.lower() == name.lower():
                v = p
        return v

    def name(self):
        return self.prop("Name", f"CAVE {self.number}")


# [game] properties that are the game's, not defaults for its caves (CaveSet)
GAME_ONLY = {"name", "description", "author", "date", "www", "difficulty", "charset", "fontset",
             "lives", "bonuslife", "story", "remark", "titlescreen", "titlescreenscroll"}


class BdcffFile:
    """A BDCFF file as GDash reads it (load_from_bdcff): every cave's
    properties (GdStored), its map or objects"""

    def __init__(self, path):
        self.path = path
        self.version = "0.32"
        self.game = []
        self.caves = []
        self.mapcodes = {}
        data = open(path, "rb").read()
        try:  # GDash writes UTF-8; older files are Latin-1
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        self.parse(text)
        self.properties()

    def parse(self, text):
        state, levels, cave = "start", None, None
        for line in text.replace("\r", "").split("\n"):
            if not line:
                continue
            if state != "map" and line.startswith(";"):
                continue
            if line.startswith("["):
                tag = line.lower()
                if tag == "[cave]":
                    cave = BdcffCave(len(self.caves) + 1)
                    self.caves.append(cave)
                    state = "cave"
                elif tag in ("[/map]", "[/objects]", "[/demo]", "[/replay]") or \
                        (tag == "[/highscore]" and state == "cavehs"):
                    state = "cave"
                elif tag in ("[/cave]", "[/mapcodes]", "[/highscore]"):
                    state = "game"
                elif tag == "[map]" and state == "cave":
                    state = "map"
                elif tag == "[objects]":
                    state, levels = "objects", None
                elif tag.startswith("[level="):
                    if state == "objects":
                        cave.objects.append(("level", line))
                elif tag == "[/level]":
                    if state == "objects":
                        cave.objects.append(("level", line))
                elif tag == "[mapcodes]":
                    state = "mapcodes"
                elif tag == "[bdcff]":
                    state = "bdcff"
                elif tag == "[game]":
                    state = "game"
                elif tag == "[highscore]":
                    state = "cavehs" if state == "cave" else "skip"
                elif tag in ("[demo]", "[replay]"):
                    state = "skip"
                continue
            if state == "map":
                cave.map.append(line)
                continue
            line = line.strip(" ")
            if state == "bdcff":
                a, _, p = line.partition("=")
                if a.lower() == "version":
                    self.version = p
            elif state == "game":
                self.game.append(line)
            elif state == "mapcodes":
                a, _, p = line.partition("=")
                if a.lower() != "length" and a and GD_NAME.get(p.upper()) is not None:
                    self.mapcodes[a[0]] = GD_NAME[p.upper()]
            elif state == "cave":
                cave.lines.append(line)
            elif state == "objects":
                cave.objects.append((None, line))

    def properties(self):
        """Every cave's properties, as GDash sets them: its defaults, the
        [game] lines (twice: GDash reads them so), then the cave's own lines,
        some of them first"""
        default = GdStored()
        lines = [line.partition("=") for line in self.game if "=" in line]
        lines = [(a, p) for a, _, p in lines if a.lower() not in GAME_ONLY and a.lower() not in ("caves", "levels")]
        for a, p in lines:
            default.tag(a, p)
        for a, p in lines:
            default.set(a, p, default["w"] * default["h"])
        for cave in self.caves:
            s = default.copy()
            todo = [line.partition("=") for line in cave.lines if "=" in line]
            todo = [[a, p] for a, _, p in todo]

            def first(name):
                for k, (a, p) in enumerate(todo):
                    if a.lower() == name.lower():
                        s.tag(a, p)
                        del todo[k]
                        return True
                return False
            for name in ("Name", "Engine", "Intermission", "Size"):
                first(name)
            if first("SlimePermeability"):
                s.v["slime_predictable"] = [0]
            if first("SlimePermeabilityC64"):
                s.v["slime_predictable"] = [1]
            if first("CaveDelay") and s["scheduling"] == 0:
                s.v["scheduling"] = [SCHEDULINGS.index("plck")]
            if first("FrameTime"):
                s.v["scheduling"] = [0]
            for a, p in todo:
                s.tag(a, p)
            cave.stored = s
        # BDCFF 0.32: intermissions without a map were 40x22 with the top
        # left 20x12 visible (GDash's hack)
        if self.version == "0.32":
            for cave in self.caves:
                s = cave.stored
                if s["intermission"] and not cave.map:
                    for k, v in (("w", 40), ("h", 22), ("x1", 0), ("y1", 0), ("x2", 19), ("y2", 11)):
                        s.v[k] = [v]
                    b = O_NAME(s["initial_border"])
                    cave.objects += [(None, f"FillRect=0 11 39 21 {b} {b}"), (None, f"FillRect=19 0 39 21 {b} {b}")]


def O_NAME(code):
    return GD_EL[code].file


class C64Random:
    """The random numbers of Boulder Dash 1 on the C64 (GDash's
    C64RandomGenerator): random fills with a RandSeed, predictable slime"""

    def __init__(self, seed=0, seed2=None):
        if seed2 is None:
            self.s1, self.s2 = seed // 256 % 256, seed % 256
        else:
            self.s1, self.s2 = seed % 256, seed2 % 256

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
    fills and mazes: g_rand_set_seed, g_rand_int_range"""

    def __init__(self, seed):
        mt = [seed & 0xFFFFFFFF]
        for i in range(1, 624):
            mt.append((1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & 0xFFFFFFFF)
        self.mt, self.i = mt, 624

    def int32(self):
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
        return y

    def range(self, begin, end):
        """g_rand_int_range(begin, end)"""
        dist = end - begin
        leftover = (0x80000000 % dist) * 2
        if leftover >= dist:
            leftover -= dist
        top = 0xFFFFFFFF - leftover
        while True:
            r = self.int32()
            if r <= top:
                return begin + r % dist

    def next(self):
        return self.range(0, 256)


def cdiv(a, b):
    """C's integer division (towards zero)"""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def cmod(a, b):
    return a - b * cdiv(a, b)


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


class Renderer:
    """Draws a BDCFF cave in one level as GDash does (create_map): the [map]
    or the random fill, then the objects. Cells hold element codes."""

    def __init__(self, bd, cave, level, subst=None):
        self.bd, self.cave, self.level, self.subst = bd, cave, level, subst or {}
        s = cave.stored
        self.w, self.h = s["w"], s["h"]
        self.lineshift, self.wrap = s["lineshift"], s["wraparound_objects"]
        self.cells = None
        self.c64 = C64Random(0, 0x1E)

    def element(self, name):
        """The code of an element name, or None (GDash leaves the object out)"""
        e = GD_NAME.get(name.upper())
        return self.subst.get(e, e)

    def get(self, x, y):
        if self.lineshift:
            x, y = lineshift(self.w, self.h, x, y)
            y = cmod(y + self.h, self.h)
        else:
            x, y = cmod(x + self.w, self.w), cmod(y + self.h, self.h)
        return self.cells[y * self.w + x]

    def put(self, x, y, e):
        if e == O["NONE"]:
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
        c, s, w, h = self.cave, self.cave.stored, self.w, self.h
        sub = lambda e: self.subst.get(e, e)
        border = sub(s["initial_border"])
        if c.map:
            codes = dict(GD_CHAR)
            codes.update(self.bd.mapcodes)
            self.cells = [border] * (w * h)
            for y, line in enumerate(c.map[:h]):
                for x, ch in enumerate(line[:w]):
                    self.cells[y * w + x] = sub(codes.get(ch, O["UNKNOWN"]))
        else:
            seed = s.v["level_rand"][self.level]
            if seed >= 0:
                rand = self.c64 = C64Random(seed)
            else:  # new in every game in GDash: here always the same
                rand = GlibRandom(self.level)
            pairs = [(sub(s[f"random_fill_{i}"]), s[f"random_fill_probability_{i}"]) for i in range(1, 5)]
            initial = sub(s["initial_fill"])
            self.cells = [initial] * (w * h)
            for y in range(1, h - 1):
                for x in range(w):
                    self.cells[y * w + x] = self.fill_element(rand.next(), initial, pairs)
            for y in range(h):
                self.cells[y * w] = self.cells[y * w + w - 1] = border
            for x in range(w):
                self.cells[x] = self.cells[(h - 1) * w + x] = border
        levels = None
        for kind, line in c.objects:
            if kind == "level":
                if line.lower() == "[/level]":
                    levels = None
                else:
                    n = [int(v) for v in re.findall(r"\d+", line.partition("=")[2])]
                    levels = set(v - 1 for v in n) if all(1 <= v <= 5 for v in n) else None
            elif levels is None or self.level in levels:
                self.draw(line)
        return self.cells

    def draw(self, line):
        kind, _, args = line.partition("=")
        kind, a = kind.lower(), args.split()
        num = lambda i: int(a[i])
        try:
            self.draw_object(kind, a, num)
        except (IndexError, ValueError, TypeError):
            pass  # GDash leaves out what it cannot read

    def draw_object(self, kind, a, num):
        el = lambda i: self.element(a[i]) if self.element(a[i]) is not None else int("not an element")
        if kind == "point":
            self.put(num(0), num(1), el(2))
        elif kind == "line":
            self.line(num(0), num(1), num(2), num(3), el(4))
        elif kind in ("rectangle", "fillrect"):
            x1, x2 = sorted((num(0), num(2)))
            y1, y2 = sorted((num(1), num(3)))
            edge = el(4)
            inside = edge
            if kind == "fillrect" and len(a) > 5 and self.element(a[5]) is not None:
                inside = el(5)
            for y in range(y1, y2 + 1):
                for x in range(x1, x2 + 1):
                    if y in (y1, y2) or x in (x1, x2):
                        self.put(x, y, edge)
                    elif kind == "fillrect":
                        self.put(x, y, inside)
        elif kind == "raster":
            x1, y1, nx, ny, dx, dy = (num(i) for i in range(6))
            e = el(6)
            x2, y2 = x1 + (nx - 1) * dx, y1 + (ny - 1) * dy
            x1, x2 = sorted((x1, x2))
            y1, y2 = sorted((y1, y2))
            for y in range(y1, y2 + 1, max(dy, 1)):
                for x in range(x1, x2 + 1, max(dx, 1)):
                    self.put(x, y, e)
        elif kind in ("add", "addbackward"):
            dx, dy, search, put = num(0), num(1), el(2), el(3)
            cells = [(x, y) for y in range(self.h) for x in range(self.w)]
            for x, y in (reversed(cells) if kind == "addbackward" else cells):
                if self.cells[y * self.w + x] == search:
                    self.put(x + dx, y + dy, put)
        elif kind in ("randomfill", "randomfillc64"):
            x1, x2 = sorted((num(0), num(2)))
            y1, y2 = sorted((num(1), num(3)))
            seeds = [num(4 + i) for i in range(5)]
            initial, rest = el(9), a[10:]
            pairs, j = [], 0
            while j < 4 and len(rest) >= 2:
                pairs.append((el(10 + 2 * j), int(rest[1])))
                rest = rest[2:]
                j += 1
            only = self.element(rest[0]) if rest else None
            if rest and only is None:
                return
            seed = seeds[self.level]
            if seed < 0:
                seed = self.level
            rand = C64Random(seed) if kind == "randomfillc64" else GlibRandom(seed)
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
            Maze(self, a).draw()

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


class Maze:
    """GDash's maze objects (CaveMaze): perfect, braid or unicursal, carved
    with GLib's random numbers from the level's seed"""

    def __init__(self, r, a):
        self.r = r
        num = lambda i: int(a[i])
        self.x1, self.x2 = sorted((num(0), num(2)))
        self.y1, self.y2 = sorted((num(1), num(3)))
        self.wall_width, self.path_width, self.horiz = num(4), num(5), num(6)
        self.seed = [num(7 + i) for i in range(5)]
        self.wall, self.path = r.element(a[12]), r.element(a[13])
        if self.wall is None or self.path is None:
            raise ValueError("not an element")
        kind = a[14].lower()
        self.kind = kind if kind in ("unicursal", "braid") else "perfect"

    def mazegen(self, maze, w, h, rand, x, y):
        maze[y][x] = True
        dirmask = 15
        while dirmask:
            d = 2 if rand.range(0, 100) < self.horiz else 0
            if d == 2 and not dirmask & 12:
                d = 0
            elif d == 0 and not dirmask & 3:
                d = 2
            d += rand.range(0, 2)
            if dirmask & (1 << d):
                dirmask &= ~(1 << d)
                if d == 0 and y >= 2 and not maze[y - 2][x]:
                    maze[y - 1][x] = True
                    self.mazegen(maze, w, h, rand, x, y - 2)
                elif d == 1 and y < h - 2 and not maze[y + 2][x]:
                    maze[y + 1][x] = True
                    self.mazegen(maze, w, h, rand, x, y + 2)
                elif d == 2 and x >= 2 and not maze[y][x - 2]:
                    maze[y][x - 1] = True
                    self.mazegen(maze, w, h, rand, x - 2, y)
                elif d == 3 and x < w - 2 and not maze[y][x + 2]:
                    maze[y][x + 1] = True
                    self.mazegen(maze, w, h, rand, x + 2, y)

    @staticmethod
    def braid(maze, w, h, rand):
        """Dead ends opened in a random direction"""
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                closed, dirs = 0, []
                if x < 1 or not maze[y][x - 1]:
                    closed += 1
                    if x > 0:
                        dirs.append((-1, 0))
                if y < 1 or not maze[y - 1][x]:
                    closed += 1
                    if y > 0:
                        dirs.append((0, -1))
                if x >= w - 1 or not maze[y][x + 1]:
                    closed += 1
                    if x < w - 1:
                        dirs.append((1, 0))
                if y >= h - 1 or not maze[y + 1][x]:
                    closed += 1
                    if y < h - 1:
                        dirs.append((0, 1))
                if closed == 3 and dirs:
                    dx, dy = dirs[rand.range(0, len(dirs))]
                    maze[y + dy][x + dx] = True

    @staticmethod
    def unicursal(maze, w, h):
        """The maze as one path along its walls: twice the size"""
        u = [[False] * (w * 2 + 1) for _ in range(h * 2 + 1)]
        for y in range(h):
            for x in range(w):
                if maze[y][x]:
                    for yy, xx in ((y * 2, x * 2), (y * 2, x * 2 + 2), (y * 2 + 2, x * 2), (y * 2 + 2, x * 2 + 2)):
                        u[yy][xx] = True
                    if x < 1 or not maze[y][x - 1]:
                        u[y * 2 + 1][x * 2] = True
                    if y < 1 or not maze[y - 1][x]:
                        u[y * 2][x * 2 + 1] = True
                    if x >= w - 1 or not maze[y][x + 1]:
                        u[y * 2 + 1][x * 2 + 2] = True
                    if y >= h - 1 or not maze[y + 1][x]:
                        u[y * 2 + 2][x * 2 + 1] = True
        return u, w * 2 - 1, h * 2 - 1

    def draw(self):
        wall, path = max(1, self.wall_width), max(1, self.path_width)
        w = (self.x2 - self.x1 + 1 + wall) // (path + wall)
        h = (self.y2 - self.y1 + 1 + wall) // (path + wall)
        if self.kind == "unicursal":
            w, h = w // 2 * 2, h // 2 * 2
        else:
            w, h = 2 * (w - 1) + 1, 2 * (h - 1) + 1
        seed = self.seed[self.r.level]
        rand = GlibRandom(seed if seed != -1 else self.r.level)  # -1: new in every game in GDash
        maze = [[False] * max(w, 0) for _ in range(max(h, 0))]
        if w >= 1 and h >= 1:
            old = sys.getrecursionlimit()
            sys.setrecursionlimit(max(old, 10000))
            self.mazegen(maze, w, h, rand, 0, 0)
            sys.setrecursionlimit(old)
        if self.kind == "braid":
            self.braid(maze, w, h, rand)
        if w >= 1 and h >= 1 and self.kind == "unicursal":
            maze, w, h = self.unicursal(maze, w, h)
        put = self.r.put
        yk = self.y1
        for y in range(h):
            for _ in range(path if y % 2 == 0 else wall):
                xk = self.x1
                for x in range(w):
                    for _ in range(path if x % 2 == 0 else wall):
                        put(xk, yk, self.path if maze[y][x] else self.wall)
                        xk += 1
                for x in range(xk, self.x2 + 1):
                    put(x, yk, self.wall)
                yk += 1
        for y in range(yk, self.y2 + 1):
            for x in range(self.x1, self.x2 + 1):
                put(x, y, self.wall)


# ---------------------------------------------------------------- the caves of GDash, as the game keeps them

# An own cave on the disk (a slot, OWNnn): what GDash's engine needs of it
# in one level - as GDash's CaveRendered has it before setup_for_game - and
# the map. src/gdengine.c plays it; mkcave.py writes this layout as C
# (build/gen/gdcave.h). All of it little-endian; time 0 is an empty slot.
GD_FIELDS = [  # name, C type, struct format
    ("time", "uint16_t", "H"), ("diamonds_needed", "int16_t", "h"), ("diamond_value", "uint16_t", "H"),
    ("extra_diamond_value", "uint16_t", "H"), ("max_time", "uint16_t", "H"), ("time_bonus", "int16_t", "h"),
    ("time_penalty", "uint8_t", "B"), ("timevalue", "uint8_t", "B"),
    ("w", "uint8_t", "B"), ("h", "uint8_t", "B"), ("x1", "uint8_t", "B"), ("y1", "uint8_t", "B"),
    ("x2", "uint8_t", "B"), ("y2", "uint8_t", "B"),
    ("magic_wall_time", "uint16_t", "H"), ("amoeba_time", "uint16_t", "H"), ("amoeba_max_count", "uint16_t", "H"),
    ("amoeba_2_time", "uint16_t", "H"), ("amoeba_2_max_count", "uint16_t", "H"),
    ("hatching_delay_time", "uint8_t", "B"), ("hatching_delay_frame", "uint8_t", "B"),
    ("speed", "uint16_t", "H"), ("ckdelay", "uint8_t", "B"), ("scheduling", "uint8_t", "B"),
    ("pneumatic_hammer_frame", "uint8_t", "B"), ("hammered_wall_reappear_frame", "uint8_t", "B"),
    ("biter_delay_frame", "uint8_t", "B"), ("replicator_delay_frame", "uint8_t", "B"),
    ("gravity_change_time", "uint8_t", "B"), ("skeletons_needed_for_pot", "uint8_t", "B"),
    ("skeletons_worth_diamonds", "uint8_t", "B"), ("slime_permeability_c64", "uint8_t", "B"),
    ("c64_seed_1", "uint8_t", "B"), ("c64_seed_2", "uint8_t", "B"), ("gravity", "uint8_t", "B"),
    ("creatures_direction_auto_change_time", "uint16_t", "H"),
]
GD_PROB_FIELDS = ["pushing_stone_prob", "pushing_stone_prob_sweet", "amoeba_growth_prob",
                  "amoeba_fast_growth_prob", "amoeba_2_growth_prob", "amoeba_2_fast_growth_prob",
                  "slime_permeability", "acid_spread_ratio"]
GD_ELEMENT_FIELDS = [
    "snap_element", "magic_diamond_to", "magic_stone_to", "magic_mega_stone_to", "magic_nitro_pack_to",
    "magic_nut_to", "magic_flying_stone_to", "magic_flying_diamond_to", "amoeba_too_big_effect",
    "amoeba_enclosed_effect", "amoeba_2_too_big_effect", "amoeba_2_enclosed_effect",
    "amoeba_2_explosion_effect", "amoeba_2_looks_like", "slime_eats_1", "slime_converts_1", "slime_eats_2",
    "slime_converts_2", "slime_eats_3", "slime_converts_3", "acid_eats_this", "acid_turns_to", "biter_eat",
    "bladder_converts_by", "nut_turns_to_when_crushed", "stone_falling_effect", "stone_bouncing_effect",
    "diamond_falling_effect", "diamond_bouncing_effect", "firefly_explode_to", "alt_firefly_explode_to",
    "butterfly_explode_to", "alt_butterfly_explode_to", "stonefly_explode_to", "dragonfly_explode_to",
    "explosion_effect", "explosion_3_effect", "diamond_birth_effect", "bomb_explosion_effect",
    "nitro_explosion_effect", "expanding_wall_looks_like", "dirt_looks_like"]
# the flags, 32 at most; the last one, intermission_instantlife: the life
# for an intermission at its start, else at its exit (rewardlife: GDash's
# engines set one of the two)
GD_FLAG_FIELDS = [
    "diagonal_movements", "active_is_first_found", "mega_stones_pushable_with_sweet", "infinite_rockets",
    "hammered_walls_reappear", "voodoo_collects_diamonds", "voodoo_dies_by_stone",
    "voodoo_disappear_in_explosion", "voodoo_any_hurt_kills_player", "amoeba_timer_started_immediately",
    "amoeba_timer_wait_for_hatching", "amoeba_2_explodes_by_amoeba", "magic_timer_zero_is_infinite",
    "magic_timer_wait_for_hatching", "magic_wall_stops_amoeba", "magic_wall_breakscan", "slime_predictable",
    "expanding_wall_changed", "replicators_active", "conveyor_belts_active",
    "conveyor_belts_direction_changed", "water_does_not_flow_down", "creatures_backwards",
    "creatures_direction_auto_change_on_start", "gravity_switch_active", "lineshift",
    "border_scan_first_and_last", "short_explosions", "gravity_affects_all", "pal_timing", "intermission",
    "intermission_instantlife"]
GD_FORMAT = "<" + "".join(f for _, _, f in GD_FIELDS) + "I" * len(GD_PROB_FIELDS) + \
    "B" * len(GD_ELEMENT_FIELDS) + "I" + f"{NAME_FIELD}s{W * H}s"
GD_SIZE = struct.calcsize(GD_FORMAT)
# a value per level (CaveStored's level_...), and what it is called in a level
GD_LEVEL = {"time": "level_time", "timevalue": "level_timevalue", "diamonds_needed": "level_diamonds",
            "magic_wall_time": "level_magic_wall_time", "slime_permeability": "level_slime_permeability",
            "slime_permeability_c64": "level_slime_permeability_c64", "time_bonus": "level_bonus_time",
            "time_penalty": "level_penalty_time", "amoeba_time": "level_amoeba_time",
            "amoeba_max_count": "level_amoeba_threshold", "amoeba_2_time": "level_amoeba_2_time",
            "amoeba_2_max_count": "level_amoeba_2_threshold", "hatching_delay_time": "level_hatching_delay_time",
            "hatching_delay_frame": "level_hatching_delay_frame", "speed": "level_speed",
            "ckdelay": "level_ckdelay"}


class GdCave:
    """A cave in one level as the game keeps and plays it with GDash's
    rules (src/gdengine.c): GDash's values (by their names in its code), its
    name, and its map, w x h element codes"""

    def __init__(self, name, values, cells):
        self.name, self.v, self.cells = name, values, cells
        self.notes = []

    def __getattr__(self, k):
        if k in ("w", "h", "time"):
            return self.v[k]
        raise AttributeError(k)

    def rows(self):
        w = self.v["w"]
        return [self.cells[y * w:(y + 1) * w] for y in range(self.v["h"])]

    def tobytes(self):
        v = dict(self.v)
        v["time"] = max(1, v["time"])  # 0 is an empty slot
        flags = sum(1 << i for i, f in enumerate(GD_FLAG_FIELDS) if v[f])
        cells = bytearray([O["STEEL"]] * (W * H))  # around a smaller cave: steel to see
        for y in range(v["h"]):
            cells[y * W:y * W + v["w"]] = bytes(self.cells[y * v["w"]:(y + 1) * v["w"]])
        lim = {"B": (0, 255), "b": (-128, 127), "H": (0, 65535), "h": (-32768, 32767)}
        fields = [min(lim[f][1], max(lim[f][0], v[n])) for n, _, f in GD_FIELDS]
        return struct.pack(GD_FORMAT, *fields, *(v[n] for n in GD_PROB_FIELDS),
                           *(v[n] for n in GD_ELEMENT_FIELDS), flags,
                           self.name.encode("ascii").ljust(NAME_FIELD, b"\0"), bytes(cells))

    @staticmethod
    def frombytes(data):
        """The cave of a slot's contents (without load address), or None for
        an empty one"""
        if len(data) < GD_SIZE or not data[0] | data[1]:
            return None
        vals = list(struct.unpack(GD_FORMAT, data[:GD_SIZE]))
        v = {}
        for (n, _, _) in GD_FIELDS:
            v[n] = vals.pop(0)
        for n in GD_PROB_FIELDS + GD_ELEMENT_FIELDS:
            v[n] = vals.pop(0)
        flags = vals.pop(0)
        for i, n in enumerate(GD_FLAG_FIELDS):
            v[n] = flags >> i & 1
        name = vals.pop(0).split(b"\0")[0].decode("ascii", "replace")
        raw = vals.pop(0)
        cells = [raw[y * W + x] for y in range(v["h"]) for x in range(v["w"])]
        return GdCave(name, v, cells)


def gd_cave(bd, cave, level, subst=None):
    """A cave of a BDCFF file in one level (0-4) as GDash's CaveRendered
    starts it; CaveError if the game cannot have it"""
    s = cave.stored
    r = Renderer(bd, cave, level, subst)
    cells = r.render()
    if s["w"] > W or s["h"] > H:
        raise CaveError(f"is {s['w']}x{s['h']} cells, the game has {W}x{H}")
    v = {}
    for f in [n for n, _, _ in GD_FIELDS] + GD_PROB_FIELDS + GD_ELEMENT_FIELDS + GD_FLAG_FIELDS:
        if f in GD_LEVEL:
            v[f] = s.v[GD_LEVEL[f]][level]
        elif f in GD_MEMBER:
            v[f] = s[f]
    # the C64 random numbers for the slime: as the map left them, or a seed
    c64 = r.c64
    seed = s.v["level_slime_seed_c64"][level]
    if seed != -1:
        c64 = C64Random(seed // 256, seed % 256)
    v["c64_seed_1"], v["c64_seed_2"] = c64.s1, c64.s2
    # the visible part, as GDash corrects it (gd_cave_correct_visible_size)
    x1, x2 = sorted((v["x1"], v["x2"]))
    y1, y2 = sorted((v["y1"], v["y2"]))
    v["x1"], v["y1"] = max(0, x1), max(0, y1)
    v["x2"], v["y2"] = min(v["w"] - 1, x2), min(v["h"] - 1, y2)
    out = GdCave(clean_name(cave.name()), v, cells)
    if (v["x2"] - v["x1"] + 1, v["y2"] - v["y1"] + 1) != (W, H):
        out.notes.append(f"{v['x2'] - v['x1'] + 1}x{v['y2'] - v['y1'] + 1} cells")
    if O["INBOX"] not in cells:
        out.notes.append("no inbox")
    return out


def read_bd(path, level, subst=None, which=None):
    """The caves of a .bd file: [(number, BdcffCave, GdCave or CaveError)]"""
    bd = BdcffFile(path)
    out = []
    for c in bd.caves:
        if which and c.number not in which:
            continue
        try:
            out.append((c.number, c, gd_cave(bd, c, level, subst)))
        except CaveError as e:
            out.append((c.number, c, e))
    return bd, out


def gd_from_cave(cave):
    """A cave of the game's own kind (.cave, Cave) with GDash's rules: those
    of Boulder Dash 1 (Engine=BD1), in milliseconds and real seconds"""
    s = GdStored()
    s.engine(GD_ENGINES.index("BD1"))
    v = {}
    for f in [n for n, _, _ in GD_FIELDS] + GD_PROB_FIELDS + GD_ELEMENT_FIELDS + GD_FLAG_FIELDS:
        if f in GD_LEVEL:
            v[f] = s.v[GD_LEVEL[f]][0]
        elif f in GD_MEMBER:
            v[f] = s[f]
    v.update(time=cave.time, diamonds_needed=cave.diamonds, diamond_value=cave.value,
             extra_diamond_value=cave.extra, speed=cave.speed, scheduling=0, pal_timing=0,
             amoeba_time=cave.amoeba, magic_wall_time=cave.magic, time_bonus=cave.clock,
             slime_predictable=1, slime_permeability_c64=cave.slime, c64_seed_1=0, c64_seed_2=0x1E)
    cells = [O[CAVE_OWN_CHARS[c]] if c in CAVE_OWN_CHARS else GD_CHAR[c] for c in cave.cells]
    return GdCave(cave.name, v, cells)


# ---------------------------------------------------------------- BDCFF: writing

def bd_value(p, x, cells):
    """A property's value as BDCFF writes it"""
    if p.type in (GD_INT, GD_INT_LEVELS):
        return f"{x / cells:.6f}" if p.flags & GD_RATIO else str(x)
    if p.type in (GD_PROB, GD_PROB_LEVELS):
        return f"{x / 1000000:.6f}"
    if p.type == GD_BOOL:
        return "true" if x else "false"
    if p.type in (GD_ELEMENT, GD_EFFECT):
        return GD_EL[x].file
    if p.type == GD_DIRECTION:
        return DIRECTIONS[x]
    if p.type == GD_SCHEDULING:
        return SCHEDULINGS[x]
    return str(x)


def write_bd(path, caves, title, levels=None, extra=None, head=""):
    """GdCaves as a BDCFF file for GDash: every property that is not GDash's
    default, the maps with BDCFF's characters (and map codes for elements
    that have none). levels: for each cave, the GdCaves of its levels (up to
    five, the last one goes on), whose values of the properties per level
    are written, one each; extra: for each cave, more lines (a dict of
    attribute and value); head: comments before it all"""
    chars = {e.code: e.char for e in GD_EL if e.char}
    codes, free = {}, (chr(i) for i in range(33, 127) if chr(i) not in "<>&[]/=\\" and chr(i) not in GD_CHAR)
    for cave in caves:
        for e in cave.cells:
            if e not in chars and e not in codes:
                codes[e] = next(free)
    out = ["[BDCFF]", "Version=0.5", "[game]", f"Name={title}", f"Caves={len(caves)}", "Levels=1"]
    if codes:
        out += ["[mapcodes]", "Length=1"] + [f"{c}={GD_EL[e].file}" for e, c in codes.items()] + ["[/mapcodes]"]
    out.append("")
    if head:
        out = [";" + line if line else ";" for line in head.splitlines()] + out
    level_of = {v: k for k, v in GD_LEVEL.items()}
    for i, cave in enumerate(caves):
        v = cave.v
        lvs = (levels[i] + [levels[i][-1]] * LEVELS)[:LEVELS] if levels and levels[i] else None
        vals = {}
        for p in GD_PROPS:
            n = level_of.get(p.member, p.member)
            if p.member in level_of and lvs:
                vals[p.member] = [c.v[n] for c in lvs][:p.count]
            else:
                vals[p.member] = [v[n]] * p.count if p.member in level_of else ([v[n]] if n in v else None)
        vals["level_slime_seed_c64"] = [v["c64_seed_1"] * 256 + v["c64_seed_2"]] * 5
        vals["intermission_rewardlife"] = [int(not v["intermission_instantlife"])]
        lines = [f"Name={cave.name}", f"Size={v['w']} {v['h']} {v['x1']} {v['y1']} {v['x2']} {v['y2']}"]
        # what says how the slime takes its random numbers, and the timing:
        # always, as GDash reads them in this order
        slime = "SlimePermeabilityC64" if v["slime_predictable"] else "SlimePermeability"
        always = {slime, "CaveScheduling", "PALTiming", "CaveTime", "DiamondsRequired", "DiamondValue"}
        done = {"Size", "SlimePermeability", "SlimePermeabilityC64"} - {slime}
        for p in GD_PROPS:
            if not p.ident or p.ident in done:
                continue
            group = [q for q in GD_PROPS if q.ident == p.ident]
            if any(vals.get(q.member) is None for q in group):
                continue
            if p.ident not in always and all(vals[q.member] == q.default for q in group):
                continue
            done.add(p.ident)
            ratio = v["w"] * v["h"]
            if p.type == GD_EFFECT:
                lines.append(f"Effect={p.ident} {GD_EL[vals[p.member][0]].file}")
            elif lvs and all(q.count == LEVELS and q.member in level_of for q in group) and \
                    any(len(set(vals[q.member])) > 1 for q in group):
                lines.append(f"{p.ident}=" + " ".join(bd_value(q, x, ratio) for q in group for x in vals[q.member]))
            else:
                lines.append(f"{p.ident}=" + " ".join(bd_value(q, vals[q.member][0], ratio) for q in group))
        lines += [f"{a}={b}" for a, b in (extra[i] if extra else {}).items()]
        out += ["[cave]"] + lines + ["", "[map]"]
        out += ["".join(chars.get(e) or codes[e] for e in row) for row in cave.rows()]
        out += ["[/map]", "[/cave]", ""]
    out += ["[/game]", "[/BDCFF]"]
    with open(path, "w", encoding="latin-1", newline="\r\n") as f:
        f.write("\n".join(out) + "\n")


# ---------------------------------------------------------------- C for the game

def write_c(gendir):
    """build/gen/gdcave.h and gdcave.c: the slots' layout and GDash's
    element table for src/gdengine.c"""
    with open(f"{gendir}/gdcave.h", "w") as f:
        f.write("// Generated by tools/mkcave.py from tools/cavekit.py - do not edit\n")
        f.write("#ifndef GDCAVE_H\n#define GDCAVE_H\n\n#include <stdint.h>\n\n")
        f.write("// GDash's elements (O_...), in its order without the scanned twins\nenum {\n")
        for e in GD_EL:
            f.write(f"    O_{e.name} = {e.code},\n")
        f.write(f"    O_COUNT = {len(GD_EL)}\n}};\n\n// their flags (GDash's P_...)\n")
        for i, n in enumerate(P_FLAGS):
            f.write(f"#define P_{n} {hex(1 << i)}ul\n")
        f.write("\n// The flags of GdCaveFile.flags\n")
        for i, n in enumerate(GD_FLAG_FIELDS):
            f.write(f"#define GDF_{n.upper()} {hex(1 << i)}ul\n")
        f.write("\n// An own cave as the disk has it (tools/cavekit.py, GD_FIELDS)\ntypedef struct {\n")
        for n, t, _ in GD_FIELDS:
            f.write(f"    {t} {n};\n")
        for n in GD_PROB_FIELDS:
            f.write(f"    uint32_t {n};  // of a million\n")
        for n in GD_ELEMENT_FIELDS:
            f.write(f"    uint8_t {n};\n")
        f.write(f"    uint32_t flags;  // GDF_*\n    char name[{NAME_FIELD}];\n")
        f.write(f"    uint8_t map[{W * H}];  // w x h codes, rows of {W}\n}} __attribute__((packed)) GdCaveFile;\n")
        f.write(f"_Static_assert(sizeof(GdCaveFile) == {GD_SIZE}, \"the layout of tools/cavekit.py\");\n\n")
        f.write("extern const uint32_t gd_flags[O_COUNT];      // P_*\n")
        f.write("extern const uint16_t gd_ckdelay[O_COUNT];    // microseconds on the C64\n")
        f.write("extern const uint8_t gd_hammered[O_COUNT];    // what a hammer makes of it, 255: nothing\n")
        f.write("extern const uint8_t gd_twin[(O_COUNT + 7) / 8];  // bits: it has a scanned twin\n\n#endif\n")
    with open(f"{gendir}/gdnew.h", "w") as f:
        # what a new cave of the editor starts with, up to its name: the
        # rules of Boulder Dash 1 in milliseconds (gd_from_cave)
        params = gd_from_cave(Cave()).tobytes()[:struct.calcsize(GD_FORMAT[:-len(f"{NAME_FIELD}s{W * H}s")])]
        f.write("// Generated by tools/mkcave.py from tools/cavekit.py - do not edit\n")
        f.write(f"#define GD_NEW_PARAMS_SIZE {len(params)}\n#define GD_NEW_PARAMS {{")
        f.write(", ".join(str(b) for b in params) + "}\n")
    with open(f"{gendir}/gdcave.c", "w") as f:
        f.write("// Generated by tools/mkcave.py from tools/cavekit.py - do not edit\n#include \"gdcave.h\"\n\n")
        for name, vals in (("const uint32_t gd_flags", [e.flags for e in GD_EL]),
                           ("const uint16_t gd_ckdelay", [e.ckdelay for e in GD_EL]),
                           ("const uint8_t gd_hammered", [e.hammered for e in GD_EL])):
            f.write(f"{name}[O_COUNT] = {{\n")
            for i in range(0, len(vals), 12):
                f.write("    " + ", ".join(str(x) for x in vals[i:i + 12]) + ",\n")
            f.write("};\n\n")
        twins = set(int(x.split(":")[1]) for x in GD_SCANNED_NAMES.split())
        bits = [sum(1 << b for b in range(8) if i * 8 + b in twins) for i in range((len(GD_EL) + 7) // 8)]
        f.write("const uint8_t gd_twin[(O_COUNT + 7) / 8] = {" + ", ".join(str(b) for b in bits) + "};\n")


def gd_speed(v, cells):
    """Milliseconds per step at the start, as GDash computes them
    (update_scheduling): for C64 caves from the CaveDelay and the cave"""
    sched, ckdelay = SCHEDULINGS[v["scheduling"]], v["ckdelay"]
    if sched == "ms":
        return v["speed"]
    cur = sum(GD_EL[e].ckdelay for e in cells)
    kinds = set(cells)
    anim = 2600 * ((O["AMOEBA"] in kinds) * 2 + any(O[f"FIREFLY_{i}"] in kinds for i in range(1, 5)) +
                   any(O[f"BUTTER_{i}"] in kinds for i in range(1, 5)))
    inter = v["intermission"]
    if sched == "bd1":
        return int((60 if inter else 88) + 3.66 * ckdelay + (cur + anim) // 1000)
    if sched == "bd1atari":
        return int((65 + 2.88 * ckdelay if inter else 74 + 3.2 * ckdelay) + cur // 1000)
    if sched == "bd2":
        return max(60 + (cur + anim) // 1000, ckdelay * 20)
    if sched == "plck":
        return max(65 + cur // 1000, ckdelay * 20)
    if sched == "bd2ckatari":
        return max(40 + cur // 1000, ckdelay * 20)
    return max(130 + cur // 1000, ckdelay * 20)  # crdr7


def game_cave(gd):
    """A GdCave as a cave of the game's own (.cave), or CaveError: only the
    elements a .cave has (CAVE_CHARS) in 40x22 cells"""
    v = gd.v
    if (v["w"], v["h"]) != (W, H):
        raise CaveError("is not 40x22 cells")
    to_char = {GD_CHAR[c]: c for c in CAVE_CHARS} | {O[n]: c for c, n in CAVE_OWN_CHARS.items()}
    other = sorted({GD_EL[e].file for e in gd.cells if e not in to_char})
    if other:
        raise CaveError("has elements of GDash only: " + ", ".join(other[:6]) + ("..." if len(other) > 6 else ""))
    factor = 1.2 if v["pal_timing"] else 1.0
    cave = Cave(gd.name, round(v["time"] * factor), max(1, min(255, v["diamonds_needed"])), v["diamond_value"],
                v["extra_diamond_value"], max(20, min(255, gd_speed(v, gd.cells))),
                min(255, round(v["amoeba_time"] * factor)), min(255, round(v["magic_wall_time"] * factor)),
                [to_char[e] for e in gd.cells], max(0, round(v["time_bonus"] * factor)),
                v["slime_permeability_c64"] if v["slime_predictable"] else 7)
    errors = check_map(cave.cells)
    if errors:
        raise CaveError(errors[0])
    return cave


# ---------------------------------------------------------------- the disk

TRACKS, SECTORS, DIR_TRACK = 80, 40, 40


CBM = 5  # a partition's type in the directory (low bits of byte 2)
GAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 :.!-,"  # a game's name, as the editor takes it
GAME_LEN = 8


class Disk:
    """A D81 image; the files are rewritten in place, as the game does. The
    own caves' slots lie in partitions, a game each (OWN1, ..., renamed in
    the editor; CAVES holds the game's caves); a disk of an older version
    has them in its directory: one game without a name"""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.img = bytearray(f.read())
        if len(self.img) != TRACKS * SECTORS * 256:
            raise CaveError(f"{path}: not a D81 disk image")

    def sector(self, t, s):
        o = ((t - 1) * SECTORS + s) * 256
        return memoryview(self.img)[o:o + 256]

    def entries(self, t=DIR_TRACK):
        """The directory from t/3 on: (name, type, track, sector, its
        sector, its offset) of each entry"""
        out, s = [], 3
        while t:
            sec = self.sector(t, s)
            for e in range(0, 256, 32):
                if sec[e + 2]:
                    name = bytes(sec[e + 5:e + 21]).rstrip(b"\xa0").decode("ascii", "replace")
                    out.append((name, sec[e + 2], sec[e + 3], sec[e + 4], (t, s), e))
            t, s = sec[0], sec[1]
        return out

    def files(self):
        """{name: (track, sector)} of the directory, a partition's files as
        DIR/NAME"""
        out = {}
        for name, typ, t, s, _, _ in self.entries():
            if typ & 7 == CBM:
                out.update((f"{name}/{n}", (tt, ss)) for n, ty, tt, ss, _, _ in self.entries(t) if ty & 7 != CBM)
            else:
                out[name] = (t, s)
        return out

    def games(self):
        """The games: the partitions but CAVES, in the directory's order;
        [""] for a disk without them"""
        return [n for n, typ, *_ in self.entries() if typ & 7 == CBM and n != "CAVES"] or [""]

    def game(self, spec):
        """A game by its name or its number (from 1)"""
        games = self.games()
        if spec.isdigit() and 1 <= int(spec) <= len(games):
            return games[int(spec) - 1]
        if spec.upper() in games:
            return spec.upper()
        raise CaveError(f"no game '{spec}' on the disk: {', '.join(games) or '(none)'}")

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
            raise CaveError(f"{name} has another length - a disk of an older version?")
        pos = 0
        for blk in self.blocks(name):
            n = 254 if blk[0] else blk[1] - 1
            blk[2:2 + n] = data[pos:pos + n]
            pos += n

    def slots(self, game=None):
        """The slots of a game (DIR/OWNnn), or of all games one after the
        other"""
        files = self.files()
        out = []
        for g in self.games() if game is None else [game]:
            pre = f"{g}/" if g else ""
            out += sorted(n for n in files if n.startswith(pre) and re.fullmatch(SLOT + r"\d\d", n[len(pre):]))
        return out

    def rename(self, game, name):
        """The game's partition renamed: its entry and its header"""
        name = name.upper()
        if not 1 <= len(name) <= GAME_LEN or any(c not in GAME_CHARS for c in name):
            raise CaveError(f"'{name}': a game's name has 1 to {GAME_LEN} of {GAME_CHARS.strip()}")
        if name != game and name in self.games() + ["CAVES"]:
            raise CaveError(f"there is a game '{name}' already")
        for n, typ, t, _, (dt, ds), e in self.entries():
            if typ & 7 == CBM and n == game:
                pad = name.encode("ascii") + b"\xa0" * (16 - len(name))
                self.sector(dt, ds)[e + 5:e + 21] = pad
                self.sector(t, 0)[4:20] = pad
                return
        raise CaveError(f"no game '{game}' on the disk")

    def has(self, name):
        return name in self.files()

    def save(self):
        with open(self.path, "wb") as f:
            f.write(self.img)


def game_name(path):
    """A game's name from its file's: the words' initials and the numbers
    (Boulder_Dash_1.bd: BD1), at most GAME_LEN characters"""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", os.path.splitext(os.path.basename(path))[0]) if w]
    name = "".join(w[0] for w in words if not w.isdigit()) + "".join(w for w in words if w.isdigit())
    return name.upper()[:GAME_LEN] or "GAME"


def level_file(slot, level):
    """The file of a slot's level (from 0): OWN01, OWN01-2, ..."""
    return slot if level == 0 else f"{slot}-{level + 1}"


def read_slot(disk, name):
    return GdCave.frombytes(disk.read(name)[2:])


def read_levels(disk, name):
    """A slot's cave in each level, as the game plays them (a level without
    a cave of its own: the first); None for an empty slot"""
    first = read_slot(disk, name)
    if not first:
        return None
    out = [first]
    for lv in range(1, LEVELS):
        f = level_file(name, lv)
        out.append((disk.has(f) and read_slot(disk, f)) or first)
    return out


def own_levels(disk, name):
    """The levels (from 1) of a slot with a cave of their own"""
    return [1] + [lv + 1 for lv in range(1, LEVELS) if disk.has(level_file(name, lv)) and
                  read_slot(disk, level_file(name, lv))]


def write_file(disk, name, cave):
    disk.rewrite(name, disk.read(name)[:2] + (cave.tobytes() if cave else bytes(GD_SIZE)))


def write_slot(disk, name, levels):
    """A cave into a slot: levels, its GdCave in each level (one or more;
    None empties the slot). The first goes into the slot's file, each other
    one that differs from it into the level's file, which is empty
    otherwise. False if the disk has no files for the levels (an older
    version) but the cave's levels differ"""
    first = levels[0] if levels else None
    write_file(disk, name, first)
    ok = True
    for lv in range(1, LEVELS):
        cave = levels[lv] if first and lv < len(levels) else None
        if cave and cave.tobytes() == first.tobytes():
            cave = None
        if disk.has(level_file(name, lv)):
            write_file(disk, level_file(name, lv), cave)
        elif cave:
            ok = False
    return ok


# ---------------------------------------------------------------- the commands

def numbers(spec, top):
    """'3' or '2-5' as a set of numbers"""
    a, _, b = spec.partition("-")
    lo, hi = int(a), int(b or a)
    if not 1 <= lo <= hi <= top:
        raise CaveError(f"'{spec}': 1-{top}")
    return set(range(lo, hi + 1))


def element_code(name):
    """An element by its BDCFF name or map character"""
    if len(name) == 1 and name in GD_CHAR:
        return GD_CHAR[name]
    if name.upper() in GD_NAME:
        return GD_NAME[name.upper()]
    raise CaveError(f"unknown element '{name}'")


def options(args):
    opts = {"cave": None, "level": None, "slot": None, "game": None, "name": None, "as": {}}
    rest = []
    while args:
        a = args.pop(0)
        if a in ("--cave", "--level", "--slot", "--game", "--name", "--as"):
            if not args:
                raise CaveError(f"{a} needs a value")
            v = args.pop(0)
            if a == "--as":
                old, _, new = v.partition("=")
                opts["as"][element_code(old)] = element_code(new)
            elif a == "--level":
                opts["level"] = int(v)
                if not 1 <= opts["level"] <= LEVELS:
                    raise CaveError(f"--level: 1-{LEVELS}")
            else:
                opts[a[2:]] = v
        else:
            rest.append(a)
    return opts, rest


def gds_to_bd(path, out):
    """A .gds file as GDash saves it as .bd, into out"""
    here = os.path.dirname(os.path.abspath(__file__))
    oracle = os.environ.get("GDASH_ORACLE") or \
        os.path.join(here, "..", "..", "toolchain", "tools", "bin", "gdash-oracle")
    if not os.access(oracle, os.X_OK):
        raise CaveError(f"{path}: a .gds file needs GDash - open it there and save it as .bd, "
                        "or build toolchain/tools/bin/gdash-oracle (toolchain/tools/build-tools.sh)")
    subprocess.run([oracle, "save", path, out], capture_output=True)
    if not os.path.exists(out):
        raise CaveError(f"{path}: GDash cannot read it")


def load_caves(path, opts, all_levels=False):
    """[(label, levels or CaveError)] of a .bd, .gds or .cave file; levels:
    the cave's GdCave in the level of --level (default 1), or with
    all_levels and no --level in each of GDash's five (a .cave file has one)"""
    if path.lower().endswith(".gds"):
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "game.bd")
            gds_to_bd(path, bd)
            return load_caves(bd, opts, all_levels)
    if path.lower().endswith(".cave"):
        try:
            return [(os.path.basename(path), [gd_from_cave(read_cave_file(path))])]
        except CaveError as e:
            return [(os.path.basename(path), e)]
    which = numbers(opts["cave"], 9999) if opts["cave"] else None
    levels = range(LEVELS) if all_levels and not opts["level"] else [(opts["level"] or 1) - 1]
    per_level = [read_bd(path, lv, opts["as"], which)[1] for lv in levels]
    out = []
    for k, (n, c, _) in enumerate(per_level[0]):
        caves = [caves[k][2] for caves in per_level]
        bad = [(lv, cave) for lv, cave in zip(levels, caves) if isinstance(cave, CaveError)]
        if bad:
            lv, e = bad[0]
            out.append((f"cave {n:2}", CaveError(f"{c.name()}: {e}" if lv == levels[0] else
                                                  f"{c.name()}: level {lv + 1}: {e}")))
        else:
            out.append((f"cave {n:2}", caves))
    return out


def level_text(opts):
    return f"level {opts['level']}" if opts["level"] else "levels 1-5"


def show(label, cave, levels=None):
    """A line for a cave (its first level, or a list of its levels; levels:
    the levels with a cave of their own)"""
    if isinstance(cave, CaveError):
        print(f"  {label}: not possible - {cave}")
        return False
    if isinstance(cave, list):
        if levels is None:
            levels = [1] + [lv + 1 for lv in range(1, len(cave)) if cave[lv].tobytes() != cave[0].tobytes()]
        cave = cave[0]
    v = cave.v
    need = v["diamonds_needed"] if v["diamonds_needed"] > 0 else "all" + \
        (f" but {-v['diamonds_needed']}" if v["diamonds_needed"] else "")
    notes = cave.notes + ([f"levels {' '.join(map(str, levels))}"] if levels and len(levels) > 1 else [])
    extra = f" ({'; '.join(notes)})" if notes else ""
    print(f"  {label}: {cave.name}, {need} in {v['time']} s{extra}")
    return True


def disk_slots(disk, opts):
    """The slots --game names (all games' without it)"""
    return disk.slots(disk.game(opts["game"]) if opts["game"] else None)


def cmd_list(args):
    opts, rest = options(args)
    path = rest[0]
    if path.lower().endswith(".d81"):
        disk = Disk(path)
        for game in [disk.game(opts["game"])] if opts["game"] else disk.games():
            if game:
                print(f"{game}:")
            for name in disk.slots(game):
                cave = read_slot(disk, name)
                if cave:
                    show(name, cave, own_levels(disk, name))
                else:
                    print(f"  {name}: (empty)")
        return
    caves = load_caves(path, opts)
    ok = sum(show(label, cave) for label, cave in caves)
    print(f"{ok} of {len(caves)} caves can be played (level {opts['level'] or 1})")


def cmd_import(args):
    opts, rest = options(args)
    disk = Disk(rest[0])
    slots = disk_slots(disk, opts)
    if not slots:
        raise CaveError(f"{rest[0]}: no slots ({SLOT}01, ...) - not a disk of Smaragd Dash with the editor?")
    first = int(opts["slot"] or 1)
    if not 1 <= first <= len(slots):
        raise CaveError(f"--slot: 1-{len(slots)}")
    todo = []
    for path in rest[1:]:
        todo += load_caves(path, opts, True)
    good = [(label, cave) for label, cave in todo if not isinstance(cave, CaveError)]
    for label, cave in todo:
        if isinstance(cave, CaveError):
            show(label, cave)
    room = len(slots) - first + 1
    if len(good) > room:
        raise CaveError(f"{len(good)} caves, but only {room} slots from {first} on (--cave, --slot or --game)")
    old = False
    for (label, cave), name in zip(good, slots[first - 1:]):
        old |= not write_slot(disk, name, cave)
        show(f"{name} <- {label}", cave, own_levels(disk, name))
    disk.save()
    print(f"{len(good)} of {len(todo)} caves written to {rest[0]} ({level_text(opts)})")
    if old:
        print(f"{rest[0]} has no files for the levels (a disk of an older version): only the first level")


def cmd_disks(args):
    opts, rest = options(args)
    out = "."
    if "--out" in rest:
        i = rest.index("--out")
        if i + 1 >= len(rest):
            raise CaveError("--out needs a directory")
        out = rest.pop(i + 1)
        rest.pop(i)
    src, files = rest[0], rest[1:]
    if not files:
        raise CaveError("disks: which caves?")
    games = Disk(src).games()
    per = len(Disk(src).slots(games[0]))
    if not per:
        raise CaveError(f"{src}: no slots ({SLOT}01, ...) - not a disk of Smaragd Dash with the editor?")
    # each file a game of its own (more caves than a game has slots: more
    # games, NAME-2, ...), as many games on a disk as it has
    units, total = [], 0
    for path in files:
        todo = load_caves(path, opts, True)
        total += len(todo)
        good = []
        for label, cave in todo:
            if isinstance(cave, CaveError):
                show(label, cave)
            else:
                good.append((label, cave))
        name = (opts["name"] or game_name(path)).upper()
        for k in range(0, len(good), per):
            units.append((name, good[k:k + per]))
    # the names told apart: NAME, NAME-2, ...
    seen = {}
    for i, (name, caves) in enumerate(units):
        seen[name] = seen.get(name, 0) + 1
        sfx = f"-{seen[name]}" if seen[name] > 1 else ""
        units[i] = (name[:GAME_LEN - len(sfx)] + sfx, caves)
    if not units:
        raise CaveError("no caves to put on a disk")
    os.makedirs(out, exist_ok=True)
    base = re.sub(r"[^A-Za-z0-9_.-]+", "-", os.path.splitext(os.path.basename(files[0]))[0])
    parts = [units[i:i + len(games)] for i in range(0, len(units), len(games))]
    old = False
    for k, part in enumerate(parts):
        path = os.path.join(out, f"{base}.d81" if len(parts) == 1 else f"{base}-{k + 1}.d81")
        shutil.copyfile(src, path)
        disk = Disk(path)
        for g, game in enumerate(games):
            name, caves = part[g] if g < len(part) else (None, [])
            slots = disk.slots(game)
            for i, slot in enumerate(slots):
                old |= not write_slot(disk, slot, caves[i][1] if i < len(caves) else None)
            if name and game:
                disk.rename(game, name)
        disk.save()
        print(f"{path}: " + "; ".join(f"{n}: {len(c)} caves - {c[0][1][0].name} ... {c[-1][1][0].name}"
                                      for n, c in part))
    caves = sum(len(c) for _, c in units)
    print(f"{caves} of {total} caves on {len(parts)} disk{'s' if len(parts) > 1 else ''} "
          f"({level_text(opts)})")
    if old:
        print(f"{src} has no files for the levels (a disk of an older version): only the first level")


def cmd_export(args):
    opts, rest = options(args)
    disk = Disk(rest[0])
    slots = disk_slots(disk, opts)
    which = numbers(opts["slot"], len(slots)) if opts["slot"] else set(range(1, len(slots) + 1))
    slot_levels = [lv for i, n in enumerate(slots) if i + 1 in which and (lv := read_levels(disk, n))]
    if not slot_levels:
        raise CaveError("no caves in these slots")
    # a .bd file has one map for a cave's levels: where they differ, the first level only
    first_only = [lv[0].name for lv in slot_levels if any(c.cells != lv[0].cells for c in lv)]
    levels = [[lv[0]] if lv[0].name in first_only else lv for lv in slot_levels]
    title = disk.game(opts["game"]) if opts["game"] else "Smaragd Dash own caves"
    write_bd(rest[1], [lv[0] for lv in slot_levels], title, levels)
    print(f"{len(slot_levels)} caves written to {rest[1]}")
    if first_only:
        print(f"only the first level (the maps of the levels differ): {', '.join(first_only)}")


def cmd_empty(args):
    opts, rest = options(args)
    disk = Disk(rest[0])
    slots = disk_slots(disk, opts)
    which = numbers(opts["slot"], len(slots)) if opts["slot"] else set(range(1, len(slots) + 1))
    for i, name in enumerate(slots):
        if i + 1 in which:
            write_slot(disk, name, None)
    disk.save()
    print(f"{len(which)} slots emptied")


def cmd_rename(args):
    opts, rest = options(args)
    disk = Disk(rest[0])
    game = disk.game(rest[1])
    if not game:
        raise CaveError(f"{rest[0]}: a disk of an older version has no games to name")
    disk.rename(game, rest[2])
    disk.save()
    print(f"{rest[0]}: {game} is {rest[2].upper()} now")


def cmd_upgrade(args):
    opts, rest = options(args)
    old, new = Disk(rest[0]), Disk(rest[1])
    src, dst = old.slots(), new.slots()
    caves = [(n, read_levels(old, n)) for n in src]
    used = [(n, lv) for n, lv in caves if lv]
    if len(caves) > len(dst) and caves[len(dst):] and any(lv for _, lv in caves[len(dst):]):
        raise CaveError(f"{rest[0]} has caves in more slots than {rest[1]} has ({len(dst)})")
    for (_, lv), name in zip(caves, dst):
        write_slot(new, name, lv)
    names = [g for g in old.games() if g]
    for g, name in zip(new.games(), names):
        if g and name != g:
            new.rename(g, name)
    if old.has("SMARAGD.SCORES") and new.has("SMARAGD.SCORES") and \
            len(old.read("SMARAGD.SCORES")) == len(new.read("SMARAGD.SCORES")):
        new.rewrite("SMARAGD.SCORES", old.read("SMARAGD.SCORES"))
    new.save()
    print(f"{rest[1]}: {len(used)} own caves of {rest[0]}, its games' names and high scores")


def cmd_convert(args):
    opts, rest = options(args)
    src, dst = rest
    if src.lower().endswith(".cave"):
        cave = gd_from_cave(read_cave_file(src))
        write_bd(dst, [cave], cave.name)
        print(f"{dst}: {cave.name}")
        return
    caves = []
    for label, gd in load_caves(src, opts):
        try:
            caves.append((label, gd if isinstance(gd, CaveError) else game_cave(gd[0])))
        except CaveError as e:
            caves.append((label, CaveError(f"{gd.name}: {e}")))
    if dst.lower().endswith(".cave"):
        good = [(label, c) for label, c in caves if not isinstance(c, CaveError)]
        if len(caves) != 1 or not good:
            for label, c in caves:
                print(f"  {label}: {c if isinstance(c, CaveError) else c.name}")
            raise CaveError("one cave to a .cave file: --cave N")
        write_cave_file(dst, good[0][1], f"from {os.path.basename(src)}, level {opts['level'] or 1}")
        print(f"{dst}: {good[0][1].name}")
        return
    os.makedirs(dst, exist_ok=True)
    n = 0
    for label, cave in caves:
        if isinstance(cave, CaveError):
            print(f"  {label}: not possible - {cave}")
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", cave.name.lower()).strip("-") or "cave"
        n += 1
        path = os.path.join(dst, f"{n:02d}-{slug}.cave")
        write_cave_file(path, cave, f"from {os.path.basename(src)}, {label}, level {opts['level'] or 1}")
        print(f"  {label}: {path}")
    print(f"{n} caves written to {dst}")


COMMANDS = {"list": (cmd_list, 1), "import": (cmd_import, 2), "disks": (cmd_disks, 2), "export": (cmd_export, 2),
            "empty": (cmd_empty, 1), "convert": (cmd_convert, 2), "rename": (cmd_rename, 3),
            "upgrade": (cmd_upgrade, 2)}


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
