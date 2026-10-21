#!/usr/bin/env python3
"""Wedge Turbo's courses: 48 of our own, laid out at build time.

    mkcourses.py ORIGDIR GENDIR

Each course is made from a seed and its place in the order, which raises
the difficulty a little from one course to the next: longer, with more and
sharper bends, more and steeper hills, more hazards, faster opponents. What
it looks like comes from a theme - one of the game's backdrops with the
scenery that goes with it (the objects the game's own courses show with
that backdrop, where they stand) - and a time of day that colours sky,
backdrop and road. The rules the game's engine needs are kept: the start
with its gate, the pits, warning signs before bends, the bends adding up
to one whole turn and the hills to none over a lap.

Writes into GENDIR:
    trackNN.bin  the courses 00-2F (on the disk as TRACKNN), as the game keeps
                 them in memory: 16 bytes per segment, the first 8 segments
                 repeated at the end; header as tracks.h describes
    tracks.h     the largest course file, the number of courses
    courses.c/.h per course its laps, its opponents' bonus, its record time;
                 the first course of each level
"""
import collections
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ORIG_COURSES = 32
COURSES = 48
LEVELS = (12, 16, 20)  # races: easy, medium, hard - one after the other
assert sum(LEVELS) == COURSES

HEADER = 162
MAX_SEGMENTS = 253  # (the course buffer, src/mem.h: TRACK_BUF_SIZE - 164) / 16 - 8
NAME, LOCATION, TRACK_TEXT, HAZARD_TEXT = 56, 66, 98, 130

GATE, PIT_SIGN, PIT_WALL = 0x82, 0x83, 0x86
SIGN_RIGHT, SIGN_LEFT = 0x80, 0x81
ROCKS, BARRIER, BARRIER_RIGHT, BARRIER_LEFT, OIL, WATER = 0x9A, 0x9F, 0xA0, 0xA1, 0xA2, 0xA3
HAZARDS = {ROCKS, BARRIER, BARRIER_RIGHT, BARRIER_LEFT, OIL, WATER}
# kinds of our own (tools/mkscenery.py): wind turbines and solar fields,
# where the land is open (the backdrops' themes, mkbackdrops.py), in groups
# (one per so many segments, so many in a group, segments between them),
# how far from the road (its edge is at 16, the signs at 18, most trees
# at 16-24): a little further than the trees, near enough to be seen large
TURBINE, SOLAR = 0x8D, 0x8E
OPEN_LAND = {TURBINE: ({0, 4, 7, 8, 9}, 40, (3, 5), (2, 3), (22, 28)),
             SOLAR: ({0, 2, 3, 6, 7, 9}, 35, (6, 10), (1, 1), (20, 24))}
NOT_SCENERY = {SIGN_RIGHT, SIGN_LEFT, GATE, PIT_SIGN, PIT_WALL} | HAZARDS


# ------------------------------------------------------------ places

# per theme (the backdrop): places, name (10) and where (32)
PLACES = {
    0: [('FRANCE', 'col de braus, alpes-maritimes'), ('TUNISIA', 'douz, edge of the sahara'),
        ('CROATIA', 'split, dalmatian coast'), ('CYPRUS', 'troodos mountains'), ('MALTA', 'mellieha ridge')],
    1: [('ESTONIA', 'parnu forest'), ('LATVIA', 'sigulda'), ('POLAND', 'mazury lakes'),
        ('BELARUS', 'braslaw lakes'), ('DENMARK', 'silkeborg')],
    2: [('TANZANIA', 'serengeti plains'), ('NAMIBIA', 'sossusvlei'), ('BOTSWANA', 'maun, okavango'),
        ('PARAGUAY', 'gran chaco'), ('ZAMBIA', 'kafue flats')],
    3: [('BOLIVIA', 'salar de uyuni'), ('CHILE', 'atacama'), ('COLOMBIA', 'bogota highlands'),
        ('VENEZUELA', 'merida, the andes'), ('BOLIVIA', 'la paz, the altiplano')],
    4: [('SVALBARD', 'longyearbyen'), ('YUKON', 'whitehorse'), ('LAPLAND', 'kittila'),
        ('SIBERIA', 'yakutsk'), ('FAROES', 'torshavn')],
    5: [('VIETNAM', 'da lat highlands'), ('LAOS', 'luang prabang'), ('BHUTAN', 'paro valley'),
        ('TAIWAN', 'taroko gorge'), ('KOREA', 'jeju island')],
    6: [('SAN MARINO', 'monte titano'), ('SINGAPORE', 'marina bay'), ('HONG KONG', 'tai mo shan'),
        ('SLOVENIA', 'lake bled'), ('MONACO', 'la turbie')],
    7: [('IRELAND', 'connemara'), ('AUSTRIA', 'salzkammergut'), ('BELGIUM', 'the ardennes'),
        ('NETHERLAND', 'zandvoort dunes'), ('HUNGARY', 'lake balaton')],
    8: [('CZECHIA', 'bohemian hills'), ('SLOVAKIA', 'tatra foothills'), ('ROMANIA', 'transfagarasan'),
        ('BULGARIA', 'rila mountains'), ('SERBIA', 'zlatibor')],
    9: [('NEVADA', 'great basin highway'), ('UTAH', 'monument valley'), ('WYOMING', 'thunder basin'),
        ('NEW MEXICO', 'roswell'), ('OKLAHOMA', 'along route 66')],
}

# the themes in turn, so that course after course looks different
THEME_ORDER = [7, 0, 2, 6, 1, 9, 4, 5, 3, 8]


# ------------------------------------------------------------ colours

def rgb(c):
    return c >> 8 & 15, c >> 4 & 15, c & 15


def pack(r, g, b):
    def lim(v):
        return max(0, min(15, round(v)))
    return lim(r) << 8 | lim(g) << 4 | lim(b)


def scaled(c, k, tint=(1, 1, 1)):
    r, g, b = rgb(c)
    return pack(r * k * tint[0], g * k * tint[1], b * k * tint[2])


def grey(c, amount):
    r, g, b = rgb(c)
    m = (r + g + b) / 3
    return pack(r + (m - r) * amount, g + (m - g) * amount, b + (m - b) * amount)


def gradient(top, bottom):
    t, b = rgb(top), rgb(bottom)
    return [pack(*(t[i] + (b[i] - t[i]) * k / 15 for i in range(3))) for k in range(16)]


# times of day: (sky from top to horizon, backdrop and road changed so)
TIMES = {
    'day': None,
    'morning': (0x58E, 0xFDB, lambda c: scaled(c, 1.0, (1.05, 1.0, 0.95))),
    'dusk': (0x214, 0xF84, lambda c: scaled(c, 0.75, (1.15, 0.9, 0.95))),
    'night': (0x002, 0x125, lambda c: scaled(c, 0.5, (0.85, 0.9, 1.2))),
    'overcast': (0x778, 0xBBC, lambda c: grey(scaled(c, 0.9), 0.4)),
}


def colours(base, time, rng):
    """The header's colour words 1-27 (backdrop, stripes A and B, sky)"""
    words = list(base)
    if TIMES[time] is None:
        # the sky of the day a little warmer or cooler than the theme's
        shift = rng.choice([(1, 0, 0), (0, 0, 1), (0, 1, 0), (0, 0, 0)])
        words[11:27] = [pack(*(v + s for v, s in zip(rgb(c), shift))) for c in words[11:27]]
        return words
    top, horizon, change = TIMES[time]
    words[0:11] = [change(c) for c in words[0:11]]
    if time == 'night':
        # the kerb and the lane stay visible (words: backdrop 0-2, then per
        # stripe set grass, kerb, road, lane)
        for i in (4, 6, 8, 10):
            words[i] = scaled(base[i], 0.8)
    words[11:27] = gradient(top, horizon)
    return words


# ------------------------------------------------------------ the game's courses

def load_orig(orig):
    """The game's courses: header, segments (curve, hill, objects)"""
    out = []
    for t in range(ORIG_COURSES):
        d = open(os.path.join(orig, f'{t:02X}.bin'), 'rb').read()
        n = struct.unpack_from('>H', d, 0)[0]
        segs = [d[164 + 12 * i:176 + 12 * i] for i in range(n)]
        out.append((d[2:164], segs))
    return out


def themes(courses):
    """Per backdrop: its colours (of its first course), its scenery types
    with how often and where (x) they stand"""
    th = {}
    for header, segs in courses:
        back = header[1]
        t = th.setdefault(back, {'colours': struct.unpack_from('>27H', header, 2),
                                 'types': collections.Counter(), 'x': collections.defaultdict(list)})
        for s in segs:
            for k in range(4):
                ty = s[2 + 2 * k]
                if ty and ty not in NOT_SCENERY:
                    t['types'][ty] += 1
                    t['x'][ty].append(struct.unpack('b', s[3 + 2 * k:4 + 2 * k])[0])
    return th


# ------------------------------------------------------------ sprite memory

def bank_sizes(gen):
    """Per sprite bank: images, pixels; and the bank of each object type"""
    sizes = {}
    for f in os.listdir(gen):
        if f.startswith('spr') and f.endswith('.bin'):
            d = open(os.path.join(gen, f), 'rb').read()
            n = d[0]
            sizes[int(f[3:5], 16)] = (n, sum(d[1 + 2 * i] * d[2 + 2 * i] for i in range(n)))
    src = open(os.path.join(gen, 'sprbanks.c')).read()
    body = src[src.index('spr_bank_of_type'):].split('{')[1].split('}')[0]
    of_type = [int(v, 16) for v in body.replace('\n', ' ').split(',') if v.strip()]
    return sizes, of_type


def memory(types, sizes, of_type):
    """What a course's scenery takes: directory bytes, pixels"""
    banks = {of_type[t - 0x80] for t in types | {SIGN_RIGHT, SIGN_LEFT, GATE, PIT_SIGN, PIT_WALL}} - {0xFF}
    return sum(1 + 5 * sizes[b][0] for b in banks), sum(sizes[b][1] for b in banks)


# ------------------------------------------------------------ laying out

def layout(rng, d, length):
    """The bends and hills: per segment (curve, hill). The bends add up to a
    whole turn (+-128), the hills to nothing"""
    turn = rng.choice((-1, 1))
    curves = [0] * 24  # the start: gate, pits
    while len(curves) < length - 30:
        lo, hi = round(10 - 6 * d), round(22 - 10 * d)
        curves += [0] * rng.randint(lo, hi)
        # a bend: sharper and more often against the course's turn later on
        sev = rng.choices([2, 3, 4, 5, 6], weights=[5 - 4 * d, 4, 2 + d, 0.5 + 3.5 * d, 0.2 + 3.3 * d])[0]
        # the side: so that the bends keep on the way to the whole turn
        due = turn * 128 * len(curves) / length - sum(curves)
        side = 1 if rng.random() < 0.5 + 0.4 * max(-1, min(1, due / 48)) else -1
        n = rng.randint(4, 10 if sev < 5 else 7)
        curves += [side * sev] * n
        if rng.random() < 0.15 + 0.35 * d:
            # an S-bend, or late on a chicane
            n2 = rng.randint(2, 4) if d > 0.5 and rng.random() < 0.5 else rng.randint(4, 8)
            curves += [-side * rng.choice([3, 4, 5, 6] if d > 0.4 else [2, 3, 4])] * n2
    # what is left of the whole turn: new bends on straights along the
    # course, or bends a little sharper
    curves += [0] * 12
    rest = turn * 128 - sum(curves)
    while rest:
        sign = 1 if rest > 0 else -1
        runs, i = [], 26
        while i < len(curves) - 10:
            if curves[i] == 0:
                j = i
                while j < len(curves) - 10 and curves[j] == 0:
                    j += 1
                if j - i >= 8:
                    runs.append((i, j - i))
                i = j
            else:
                i += 1
        if runs and abs(rest) >= 8 and rng.random() < 0.8:
            at, n = rng.choice(runs)
            sev = min(abs(rest), rng.choice([2, 3, 4, 5] if d > 0.3 else [2, 3, 4]))
            k = max(1, min(n - 4, abs(rest) // sev, rng.randint(4, 9)))
            for j in range(at + 2, at + 2 + k):
                curves[j] = sign * sev
            rest -= sign * sev * k
        else:
            bends = [i for i, c in enumerate(curves) if c * sign > 0 and abs(c) < 6]
            if not bends:
                curves[len(curves) - 12] = sign
                rest -= sign
                continue
            i = rng.choice(bends)
            curves[i] += sign
            rest -= sign
    curves += [0] * 0
    hills = [0] * len(curves)
    # hills: rises and dips, each adding up to nothing
    i = 30
    while i < len(hills) - 20:
        if rng.random() < 0.2 + 0.5 * d:
            h = rng.randint(1, 1 + round(3 * d))
            n = rng.choice((2, 2, 3, 4))
            gap = rng.randint(0, 6)
            shape = rng.choice(([h, -h], [-h, h], [h, -2 * h, h] if 2 * h <= 6 and d > 0.4 else [h, -h]))
            at = i
            for v in shape:
                for _ in range(n):
                    if at < len(hills) - 10:
                        hills[at] = v
                    at += 1
                at += gap if v == shape[0] else 0
            i = at + rng.randint(6, 20)
        else:
            i += rng.randint(6, 16)
    # what got cut at the end, taken out again
    s = sum(hills)
    j = len(hills) - 10
    while s:
        step = max(-3, min(3, -s))
        hills[j] += step
        s += step
        j -= 1
    return list(zip(curves, hills))


def course(n, th, rng, d, sizes, of_type, budget):
    theme = THEME_ORDER[n % len(THEME_ORDER)]
    place, where = PLACES[theme][(n // len(THEME_ORDER)) % len(PLACES[theme])]
    t = th[theme]
    if n < 4:
        time = 'day'
    else:
        time = rng.choices(list(TIMES), weights=[5, 1.5, 1.5, 0.6 + 2 * d, 1.2])[0]
    length = rng.randint(110, 150) + round(60 * d)
    segs = layout(rng, d, length)
    while len(segs) > MAX_SEGMENTS - 10:  # the last turn took too long: again
        segs = layout(rng, d, length)
    n_segs = len(segs)
    assert n_segs <= MAX_SEGMENTS, (n, n_segs)
    objects = [[(0, 0)] * 4 for _ in range(n_segs)]
    pit = [0] * n_segs

    # the start: gate, pit signs, the pit lane with its wall
    objects[0][0] = (GATE, 0)
    for i in range(4, 8):
        objects[i][0] = objects[i][2] = (PIT_SIGN, 18)
    for i in range(8, 16):
        pit[i] = 1
    for i in range(9, 20):
        if i != 12:
            objects[i][0] = (PIT_WALL, -20)

    # warning signs before and into bends
    i = 24
    while i < n_segs:
        c = segs[i][0]
        if c and (i == 0 or segs[i - 1][0] != c):
            run = 1
            while i + run < n_segs and segs[i + run][0] == c:
                run += 1
            if abs(c) >= 3:
                sign = (SIGN_RIGHT, 18) if c > 0 else (SIGN_LEFT, -18)
                for j in range(max(20, i - 2), min(n_segs, i + min(run, 6))):
                    objects[j][0] = objects[j][2] = sign
                    if abs(c) >= 5 and j < i:
                        objects[j][1] = objects[j][3] = sign
            i += run
        else:
            i += 1

    # the hazards it has, more of them later on
    kinds = []
    if d > 0.15:
        kinds = rng.sample(['oil', 'water', 'rocks', 'roadworks'], k=min(4, 1 + round(rng.random() * 3 * d)))
    hazard_types = {'oil': {OIL}, 'water': {WATER}, 'rocks': {ROCKS},
                    'roadworks': {BARRIER, BARRIER_RIGHT, BARRIER_LEFT}}
    need = set().union(*(hazard_types[k] for k in kinds)) if kinds else set()

    # the scenery: a few of the theme's types, the most common more often -
    # as long as the sprites fit
    pool = [ty for ty, _ in t['types'].most_common()]
    picks = rng.randint(3, 5)
    # first wind turbines and solar fields where the land is open, then
    # the theme's own kinds in what room is left (room for its commonest
    # kind at least)
    extra = []
    for ty, (themes_of, _, _, _, _) in OPEN_LAND.items():
        m = memory(need | set(extra) | {ty, pool[0]}, sizes, of_type)
        if theme in themes_of and m[0] <= budget[0] and m[1] <= budget[1]:
            extra.append(ty)
    chosen = []
    for ty in rng.sample(pool[:8], min(len(pool[:8]), picks)):
        m = memory(need | set(extra) | set(chosen) | {ty}, sizes, of_type)
        if m[0] <= budget[0] and m[1] <= budget[1]:
            chosen.append(ty)
    if not chosen:  # the hazards' sprites left no room: fewer hazards
        kinds, need = [], set()
        chosen = [pool[0]]
    weights = [t['types'][ty] for ty in chosen]
    density = 0.3 + 0.2 * rng.random()
    for i in range(22, n_segs):
        for q in range(4):
            if objects[i][q][0] or rng.random() >= density:
                continue
            ty = rng.choices(chosen, weights=weights)[0]
            objects[i][q] = (ty, rng.choice(t['x'][ty]))
    # wind turbines, solar fields: further out, in groups on one side, on
    # straights where there are (no bend signs in front of them), else
    # where the bends are gentlest
    def straight(i, n):
        return max(abs(segs[j][0]) for j in range(i - 2, i + n))
    places = range(30, n_segs - 14)
    open_road = [i for i in places if straight(i, 10) <= 2]
    if len(open_road) < 8:
        open_road = sorted(places, key=lambda i: straight(i, 10))[:max(8, len(places) // 4)]
    for ty in extra:
        _, every, (fewest, most), (step0, step1), (near, far) = OPEN_LAND[ty]
        for _ in range(max(1, (n_segs - 40) // every) if open_road else 0):
            i, side = rng.choice(open_road), rng.choice((-1, 1))
            for k in range(rng.randint(fewest, most)):
                # a free place, or one of the theme's own kinds makes room
                free = [q for q in range(4) if not objects[i][q][0]] or \
                    [q for q in range(4) if objects[i][q][0] in chosen]
                if free:
                    objects[i][rng.choice(free)] = (ty, side * rng.randint(near, far))
                i += rng.randint(step0, step1)

    # the hazards on straights
    placed = set()
    count = round(d * 7 * rng.uniform(0.6, 1.2))
    straights = [i for i in range(40, n_segs - 20) if all(abs(segs[j][0]) <= 2 for j in range(i, i + 10))]
    for _ in range(count if kinds else 0):
        if not straights:
            break
        at = rng.choice(straights)
        kind = rng.choice(kinds)
        if kind == 'oil':
            side = rng.choice((-1, 1))
            for j in range(at, at + 2):
                objects[j][rng.randrange(4)] = (OIL, side * rng.choice((8, 10, 12)))
        elif kind == 'water':
            for j in range(at, at + 3):
                objects[j][rng.randrange(4)] = (WATER, rng.choice((-32, -20, 20, 32, -8, 8)))
        elif kind == 'rocks':
            side = rng.choice((-1, 1))
            for j in range(at, at + 3):
                objects[j][rng.randrange(4)] = (ROCKS, side * rng.choice((18, 18, 2)))
        else:
            # a lane closed, the barrier first
            closed = rng.choice((BARRIER_RIGHT, BARRIER_LEFT))
            sign = 1 if closed == BARRIER_RIGHT else -1
            objects[at][0] = (BARRIER, sign * 8)
            for j in range(at + 1, at + rng.randint(5, 9)):
                objects[j][0] = objects[j][2] = (closed, sign * rng.choice((6, 8, 10, 12)))
        placed.add(kind)

    types = {o[0] for row in objects for o in row if o[0]}
    mem = memory(types, sizes, of_type)
    assert mem[0] <= budget[0] and mem[1] <= budget[1], (n, mem, budget)

    # how it reads
    curv = sum(abs(c) for c, _ in segs) / n_segs
    hill = sum(abs(h) for _, h in segs) / n_segs
    track = ('fast and gentle' if curv < 1.3 else 'some sharp bends' if curv < 1.9 else
             'winding, sharp bends')
    if max(abs(h) for _, h in segs) >= 4:
        track += ', steep hills'
    elif hill > 0.25:
        track += ', hills'
    if time == 'night':
        track = 'night, ' + track
    for long, short in (('some sharp', 'sharp'), ('winding, sharp bends', 'winding'),
                        ('fast and gentle', 'fast'), ('steep hills', 'hills')):
        if len(track) > 32:
            track = track.replace(long, short)
    hz = [k for k in ('oil', 'water', 'rocks', 'roadworks') if k in placed]
    hazards = 'no hazards' if not hz else ', '.join(hz) + ' on the road'
    if len(hazards) > 32:
        hazards = ', '.join(hz)
    assert len(track) <= 32 and len(hazards) <= 32, (track, hazards)
    laps = max(3, min(8, round((560 + 560 * d + rng.randint(-60, 60)) / n_segs)))
    bonus = round(85 + 45 * d + rng.randint(-4, 4))
    record = round(n_segs * laps * (11.9 + 1.03 * curv + 1.1 * hill + 0.15 * len(placed)))

    header = bytearray(HEADER)
    header[0], header[1] = 0, theme
    struct.pack_into('>27H', header, 2, *colours(t['colours'], time, rng))
    for at, size, text in ((NAME, 10, place), (LOCATION, 32, where), (TRACK_TEXT, 32, track),
                           (HAZARD_TEXT, 32, hazards)):
        text = text[:size].upper() if at == NAME else text[:size]
        header[at:at + size] = text.encode('latin1').ljust(size, b'/')
    body = bytearray()
    for (c, h), row, p in zip(segs, objects, pit):
        body += struct.pack('bb', c, h)
        for ty, x in row:
            body += struct.pack('Bb', ty, x)
        body += bytes([0, p]) + bytes(4)
    body += body[:8 * 16]
    return struct.pack('<H', n_segs) + bytes(header) + bytes(body), laps, bonus, record


def main():
    orig, gen = sys.argv[1], sys.argv[2]
    origs = load_orig(orig)
    th = themes(origs)
    sizes, of_type = bank_sizes(gen)
    # no more sprite memory than the game's busiest course takes
    budget = [0, 0]
    for _, segs in origs:
        types = {s[2 + 2 * k] for s in segs for k in range(4) if s[2 + 2 * k]}
        m = memory(types, sizes, of_type)
        budget = [max(budget[0], m[0]), max(budget[1], m[1])]
    largest, laps, bonus, record = 0, [], [], []
    for n in range(COURSES):
        rng = random.Random(0x4C52 + 977 * n)
        data, l, b, r = course(n, th, rng, n / (COURSES - 1), sizes, of_type, budget)
        largest = max(largest, len(data))
        laps.append(l)
        bonus.append(b)
        record.append(r)
        with open(os.path.join(gen, f'track{n:02X}.bin'), 'wb') as f:
            f.write(data)
    first = [0]
    for k in LEVELS:
        first.append(first[-1] + k)

    def array(name, ctype, values):
        return f'const {ctype} {name}[{len(values)}] = {{' + ', '.join(str(v) for v in values) + '};\n'

    with open(os.path.join(gen, 'tracks.h'), 'w') as f:
        f.write('// Generated by tools/mkcourses.py - do not edit\n#pragma once\n'
                f'#define TRACK_SIZE {largest}  // the largest course file\n'
                f'#define COURSES {COURSES}\n')
    with open(os.path.join(gen, 'courses.h'), 'w') as f:
        f.write('// Generated by tools/mkcourses.py - do not edit\n#pragma once\n#include <stdint.h>\n'
                '#include "tracks.h"\n'
                'extern const uint8_t course_laps[COURSES];\n'
                'extern const uint8_t course_bonus[COURSES];  // the opponents\' speed\n'
                'extern const uint16_t course_time[COURSES];  // the record to beat (frames)\n'
                'extern const uint8_t course_first[4];  // per level its first course, then the end\n')
    with open(os.path.join(gen, 'courses.c'), 'w') as f:
        f.write('// Generated by tools/mkcourses.py - do not edit\n#include "courses.h"\n\n')
        f.write(array('course_laps', 'uint8_t', laps))
        f.write(array('course_bonus', 'uint8_t', bonus))
        f.write(array('course_time', 'uint16_t', record))
        f.write(array('course_first', 'uint8_t', first))
    print(f'mkcourses: {COURSES} courses, the largest {largest} bytes')


if __name__ == '__main__':
    main()
