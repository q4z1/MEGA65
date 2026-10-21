#!/usr/bin/env python3
"""The music for the MEGA65's four SIDs: the game's five tunes arranged
anew, then the radio's own tracks (tools/radio_tracks.py).

    mkmusic.py ORIGDIR GENDIR

The tunes come from file $E8 (the game program says where each starts):
their notes - melody, bass line, beat - are kept, the sound is new: SID
instruments instead of samples, the melody doubled and slightly detuned
over both sides with an echo going left and right, a hi-hat added to the
beat, the bass through the filter - in stereo: bass and beat in the
middle, the melody wide over both sides, the second voice on the left with
its echo on the right, the hi-hats going between the sides. The own tracks
(song 5 on) are built from their chords, beat, bass, accompaniment and
melodies in the same parts and instruments.

Writes into GENDIR:
    music.bin  on the disk as MUSIC, played by src/music.s (see there for
               the format): the instruments, the patterns, the songs
    songs.h    MUSIC's size, the number of songs
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import packers  # noqa: E402
import radio_tracks  # noqa: E402

CODE_BASE = 0xC18880
SONG_TABLE = 0xC1C59A  # where each tune lies in memory, file $E8 loaded at the first
SONGS = 5

# Amiga periods of the notes C-1 to B-3
PERIODS = [856, 808, 762, 720, 678, 640, 604, 570, 538, 508, 480, 453,
           428, 404, 381, 360, 339, 320, 302, 285, 269, 254, 240, 226,
           214, 202, 190, 180, 170, 160, 151, 143, 135, 127, 120, 113]
SPEED_CMD, VOLUME_CMD, SLIDE_CMD = 0xF, 0xC, 0xA

# The parts of the arrangement: stored ones, then the echoes, which the
# player makes from the melody and the second voice (src/music.s)
BASS, DRUMS, HATS, LEAD, SECOND, TICKS = range(6)
PARTS = 6

# The tunes' sounds: what each is in the arrangement
S_BASS, S_KICK, S_SNARE, S_TOM, S_CRASH = 13, 11, 12, 14, 7
S_SYNTH, S_BELL, S_CHORD = 2, 10, 5
DRUM_ORDER = [S_KICK, S_SNARE, S_TOM]  # who wins a row
# which channel carries the melody, per tune
LEAD_CHANNEL = [2, 0, 2, 1, 3]

# ------------------------------------------------------------ instruments
#
# 32 bytes each: attack/decay, sustain/release, pulse width (x16), its
# change per frame (signed), vibrato (delay << 4 | shift, 0 none), filter
# cutoff at the start (0: the filter is not touched) and its fall per
# frame, the echo's instrument (0xFF none), the number of steps, the step
# to loop to; from byte 16 on up to 8 steps of waveform and pitch: pitch
# 0x00-0x7F semitones up or down (7 bits, signed) from the note, 0x80 + n
# the frequency's high byte 2n.

TRI, SAW, PULSE, NOISE, GATE = 0x10, 0x20, 0x40, 0x80, 0x01


def rel(n):
    return n & 0x7F


def fix(hi):
    return 0x80 | hi >> 1


INSTRUMENTS = {}


def instrument(name, ad, sr, steps, loop=None, pw=0x80, pw_speed=0, vibrato=0,
               cutoff=0, cutoff_fall=0, echo=None):
    INSTRUMENTS[name] = dict(ad=ad, sr=sr, steps=steps, loop=len(steps) - 1 if loop is None else loop,
                             pw=pw, pw_speed=pw_speed, vibrato=vibrato, cutoff=cutoff,
                             cutoff_fall=cutoff_fall, echo=echo)


# the bass: pulse through the low pass, which closes after every note
instrument('bass', 0x08, 0xC6, [(PULSE | GATE, rel(0))], pw=0x50, pw_speed=0x18,
           cutoff=0x68, cutoff_fall=3)
# the beat: a falling triangle after a click, a pulse into noise, a falling
# triangle tuned to the note; hi-hats and the crash from the noise
instrument('kick', 0x08, 0x00, [(NOISE | GATE, fix(0xA0)), (TRI | GATE, fix(0x20)),
                                (TRI | GATE, fix(0x10)), (TRI | GATE, fix(0x0A)),
                                (TRI | GATE, fix(0x07)), (TRI | GATE, fix(0x05)),
                                (TRI | GATE, fix(0x04))])
instrument('snare', 0x09, 0x00, [(PULSE | GATE, fix(0x10)), (NOISE | GATE, fix(0xD0)),
                                 (NOISE | GATE, fix(0xB0)), (NOISE | GATE, fix(0xA0))], pw=0x80)
instrument('tom', 0x08, 0x00, [(NOISE | GATE, fix(0x60)), (TRI | GATE, rel(0)),
                               (TRI | GATE, rel(-2)), (TRI | GATE, rel(-4)),
                               (TRI | GATE, rel(-6)), (TRI | GATE, rel(-8)),
                               (TRI | GATE, rel(-10)), (TRI | GATE, rel(-12))])
instrument('hat', 0x02, 0x00, [(NOISE | GATE, fix(0xF0))])
instrument('tick', 0x01, 0x00, [(NOISE | GATE, fix(0xFE))])
instrument('open hat', 0x06, 0x00, [(NOISE | GATE, fix(0xE8))])
instrument('crash', 0x0A, 0x00, [(NOISE | GATE, fix(0xC0)), (NOISE | GATE, fix(0xA0))])
# the melody: a pulse that breathes, with vibrato; its echo thinner and
# softer
instrument('lead echo', 0x09, 0x68, [(PULSE | GATE, rel(0))], pw=0x28, pw_speed=0x10)
instrument('lead', 0x09, 0xB8, [(PULSE | GATE, rel(0))], pw=0x40, pw_speed=0x20,
           vibrato=0xC7, echo='lead echo')
# a bell: an octave up for the strike, then dying away
instrument('bell echo', 0x08, 0x00, [(TRI | GATE, rel(12)), (TRI | GATE, rel(0))])
instrument('bell', 0x0A, 0x00, [(PULSE | GATE, rel(12)), (PULSE | GATE, rel(0))], pw=0x30,
           pw_speed=0x08, echo='bell echo')
# the chord: root, fourth and sixth in turn
instrument('chord', 0x86, 0xA8, [(SAW | GATE, rel(0)), (SAW | GATE, rel(5)),
                                 (SAW | GATE, rel(9))], loop=0)
# the second voice: a pulse, plainer than the melody
instrument('riff echo', 0x08, 0x48, [(PULSE | GATE, rel(0))], pw=0x30, pw_speed=0x0C)
instrument('riff', 0x08, 0x88, [(PULSE | GATE, rel(0))], pw=0x60, pw_speed=0x14,
           echo='riff echo')

# for the own tracks (tools/radio_tracks.py): a melody on a saw and on a
# triangle; chords broken fast (arp) and slowly (pad), per kind of chord
instrument('saw lead', 0x09, 0xA8, [(SAW | GATE, rel(0))], vibrato=0xC7, echo='lead echo')
instrument('soft lead', 0x3A, 0xA9, [(TRI | GATE, rel(0))], vibrato=0x87, echo='bell echo')
CHORDS = {'': (0, 4, 7, 12), 'm': (0, 3, 7, 12), '7': (0, 4, 7, 10), 'm7': (0, 3, 7, 10),
          'maj7': (0, 4, 7, 11), 'sus': (0, 5, 7, 12)}
for kind, steps in CHORDS.items():
    instrument('arp ' + kind, 0x06, 0x97, [(PULSE | GATE, rel(s)) for s in steps], loop=0, pw=0x40,
               pw_speed=0x18)
    instrument('pad ' + kind, 0x88, 0xA9, [(SAW | GATE, rel(s)) for s in steps for _ in (0, 1)], loop=0)

NAMES = list(INSTRUMENTS)


def inst_bytes():
    out = bytearray()
    for name in NAMES:
        i = INSTRUMENTS[name]
        steps = i['steps']
        assert 1 <= len(steps) <= 8 and i['loop'] < len(steps)
        echo = 0xFF if i['echo'] is None else NAMES.index(i['echo'])
        rec = bytes([i['ad'], i['sr'], i['pw'], i['pw_speed'] & 0xFF, i['vibrato'], i['cutoff'],
                     i['cutoff_fall'], echo, len(steps), i['loop']]) + bytes(6)
        rec += b''.join(bytes(s) for s in steps)
        out += rec.ljust(32, b'\0')
    return out


# ------------------------------------------------------------ the tunes

def load_songs(orig):
    code = open(os.path.join(orig, 'code.bin'), 'rb').read()
    e8 = open(os.path.join(orig, 'E8.bin'), 'rb').read()
    at = struct.unpack_from(f'>{SONGS}I', code, SONG_TABLE - CODE_BASE)
    return [packers.unpack_bytes(e8[a - at[0]:]) for a in at]


def cells(song, p):
    """Pattern p: 64 rows of 4 cells (sound, period, command, parameter)."""
    rows = []
    for r in range(64):
        row = []
        for c in range(4):
            b = song[0x86 + p * 1024 + r * 16 + c * 4:][:4]
            row.append(((b[0] & 0xF0) | b[2] >> 4, (b[0] & 0x0F) << 8 | b[1], b[2] & 0x0F, b[3]))
        rows.append(row)
    return rows


def note_of(period):
    """Semitones from C-1."""
    return min(range(len(PERIODS)), key=lambda i: abs(PERIODS[i] - period))


def rows_of(sound, period, speed, lengths):
    """How many rows a sound plays before its sample runs out."""
    seconds = lengths[sound] * period / 3546895
    return max(1, int(seconds * 50 / speed + 0.5))


def arrange(song, n, lengths):
    """The tune's patterns as rows of parts: per row and part None, 'off' or
    (instrument, note)."""
    length = song[0]
    order = list(song[2:2 + length])
    speed = 6
    for p in order[:1]:
        for row in cells(song, p)[:1]:
            for s, per, cmd, par in row:
                if cmd == SPEED_CMD and 0 < par < 32:
                    speed = par
    patterns = {}
    for p in sorted(set(order)):
        rows = [[None] * PARTS for _ in range(64)]
        prio = [[99] * PARTS for _ in range(64)]
        owner = [None] * PARTS  # the channel whose note a part plays
        until = [None] * 4      # per channel: the row its sound runs out
        part_of = [None] * 4
        beats = 0
        for r, row in enumerate(cells(song, p)):
            for c, (s, per, cmd, par) in enumerate(row):
                ev, part, pr = None, None, 0
                if s and per:
                    t = note_of(per)
                    if s == S_BASS:
                        part, ev = BASS, ('bass', t + 12)
                    elif s in DRUM_ORDER:
                        part, pr = DRUMS, DRUM_ORDER.index(s)
                        ev = {S_KICK: ('kick', 0), S_SNARE: ('snare', 0), S_TOM: ('tom', t + 12)}[s]
                        beats += s != S_TOM
                    elif s == S_CRASH:
                        part, ev = HATS, ('crash', 0)
                        rows[r][TICKS] = ev  # on both sides
                    else:
                        part = LEAD if c == LEAD_CHANNEL[n] else SECOND
                        if s == S_BELL:
                            ev = ('bell', t + 36)
                        elif s == S_CHORD:
                            ev = ('chord', t + 24)
                        else:
                            ev = ('lead' if part == LEAD else 'riff', t + 24)
                    if pr < prio[r][part]:
                        rows[r][part], prio[r][part] = ev, pr
                        owner[part] = c
                    part_of[c] = part
                    until[c] = r + rows_of(s, per, speed, lengths) if part in (BASS, LEAD, SECOND) and s != S_CHORD else None
                    continue
                # the note ends: cut, faded out, or its sample over
                cut = (cmd == VOLUME_CMD and par == 0) or (cmd == SLIDE_CMD and par & 0x0F)
                if (cut or until[c] == r) and part_of[c] in (BASS, LEAD, SECOND):
                    part = part_of[c]
                    if owner[part] == c and rows[r][part] is None:
                        rows[r][part] = 'off'
                    until[c] = None
        # where the beat goes: the hi-hat on the off-beats on the right,
        # ticks between the beats on the left
        if beats >= 8:
            for r in range(2, 64, 4):
                if rows[r][HATS] is None:
                    rows[r][HATS] = ('open hat' if r % 16 == 14 else 'hat', 0)
            for r in range(1, 64, 2):
                if rows[r][TICKS] is None:
                    rows[r][TICKS] = ('tick', 0)
        patterns[p] = rows
    return speed, order, song[1] if song[1] < length else 0, patterns


# ------------------------------------------------------------ the own tracks

NOTE = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11,
        'Db': 1, 'Eb': 3, 'Gb': 6, 'Ab': 8, 'Bb': 10}
BASS_STEP = {'R': 0, 'O': 12, 'F': 7, '6': 9, 'S': 10}


def chord(s):
    """'F#m7' -> (6, 'm7')"""
    root = s[:2] if len(s) > 1 and s[1] in '#b' else s[:1]
    return NOTE[root], s[len(root):]


def note(s):
    """'C#5' -> 61 (C0 is 0)"""
    return int(s[-1]) * 12 + NOTE[s[:-1]]


def melody(rows, part, inst, bar, at):
    """A melody bar (\"E5:4 r:2 ...\", 16 rows) into rows from row at"""
    r = 0
    for token in bar.split():
        name, length = token.split(':')
        if name == 'r':
            rows[at + r][part] = 'off'
        else:
            rows[at + r][part] = (inst, note(name))
        r += int(length)
    assert r == 16, bar


def bar_of(rows, at, t, chords_kind, root, drums, hats, ticks, bass, second, crash):
    """Beat, bass and accompaniment of a bar over a chord"""
    for i in range(16):
        row = rows[at + i]
        d = drums[i]
        if d == 'K':
            row[DRUMS] = ('kick', 0)
        elif d == 'S':
            row[DRUMS] = ('snare', 0)
        elif d in 'Tt':
            row[DRUMS] = ('tom', 45 if d == 'T' else 38)
        if hats[i] in 'ho':
            row[HATS] = ('hat' if hats[i] == 'h' else 'open hat', 0)
        if ticks[i] == 'x':
            row[TICKS] = ('tick', 0)
        b = bass[i]
        third = 3 if chords_kind.startswith('m') else 4
        if b == '-':
            row[BASS] = 'off'
        elif b == 'T':
            row[BASS] = ('bass', 24 + root + third)
        elif b in BASS_STEP:
            row[BASS] = ('bass', 24 + root + BASS_STEP[b])
    kind = chords_kind if chords_kind in CHORDS else ''
    if second == 'arp' or second == 'pad':
        rows[at][SECOND] = (second + ' ' + kind, 36 + root)
    elif second == 'riff':
        third = 3 if chords_kind.startswith('m') else 4
        for i, step in enumerate((0, 0, third, 0, 5, 0, 7, 5)):
            rows[at + 2 * i][SECOND] = ('riff', 36 + root + step)
    elif second.startswith('stab:'):
        for i, c in enumerate(second[5:]):
            if c == 'x':
                rows[at + i][SECOND] = ('arp ' + kind, 48 + root)
            elif c == '-':
                rows[at + i][SECOND] = 'off'
    if crash:
        rows[at][HATS] = rows[at][TICKS] = ('crash', 0)


def own_track(t):
    """An own track (tools/radio_tracks.py): speed, order, restart, patterns"""
    def section(chords, bars, beat, fill, lead, crash, bass=None, second=None, hats=None, ticks=None):
        rows = [[None] * PARTS for _ in range(64)]
        for k, c in enumerate(chords):
            root, kind = chord(c)
            bar_of(rows, 16 * k, t, kind, root, fill if k == 3 and fill else beat, hats or t['hats'],
                   ticks or t['ticks'], bass or t['bass'], second or t['second'], crash and k == 0)
            if bars:
                melody(rows, LEAD, lead, bars[k], 16 * k)
        return rows

    a_chords, a_bars = t['a'][0].split(), t['a'][1]
    b_chords, b_bars = t['b'][0].split(), t['b'][1]
    b2_chords = b_chords[:3] + [t.get('b_end_chord', b_chords[3])]
    lead = t['lead']
    sections = {
        'I': section(a_chords, None, t['intro'], None, lead, False),
        'A': section(a_chords, a_bars, t['drums'], t['fill'], lead, True),
        'a': section(a_chords, a_bars[:3] + [t['a_end']], t['drums'], t['fill'], lead, False),
        'B': section(b_chords, b_bars, t['drums'], t['fill'], lead, True),
        'b': section(b2_chords, b_bars[:3] + [t['b_end']], t['drums'], t['fill'], lead, False),
        'X': section(a_chords, None, 'K.......K.......', None, lead, True, bass='R.......-.......',
                     second='pad', hats='................'),
    }
    order = list(t['order'])
    return t['speed'], order, 1, sections


# ------------------------------------------------------------ encoding

def encode(rows):
    """A pattern as the player reads it (src/music.s)."""
    out = bytearray()
    inst = [None] * PARTS
    empty = 0

    def flush():
        nonlocal empty
        while empty:
            k = min(empty, 64)
            out.append(0x80 | (k - 1))
            empty -= k

    for row in rows:
        mask = sum(1 << i for i in range(PARTS) if row[i] is not None)
        if not mask:
            empty += 1
            continue
        flush()
        out.append(mask)
        for i in range(PARTS):
            ev = row[i]
            if ev is None:
                continue
            if ev == 'off':
                out.append(0x7F)
                continue
            name, note = ev
            note = max(0, min(note, 95))
            k = NAMES.index(name)
            if inst[i] != k:
                out.append(0x60 + k)
                inst[i] = k
            out.append(note)
    flush()
    return bytes(out)


def main():
    orig, gen = sys.argv[1], sys.argv[2]
    code = open(os.path.join(orig, 'code.bin'), 'rb').read()
    # the samples' lengths in bytes, from the game's sample table
    lengths = [2 * struct.unpack_from('>H', code, 0xC191DE - CODE_BASE + 16 * i + 4)[0]
               for i in range(32)]
    assert len(NAMES) <= 31
    pattern_data, pattern_index, songs = [], {}, []
    tunes = [arrange(song, n, lengths) for n, song in enumerate(load_songs(orig))]
    tunes += [own_track(t) for t in radio_tracks.TRACKS]
    for speed, order, restart, patterns in tunes:
        mine = {}
        for p, rows in patterns.items():
            data = encode(rows)
            if data not in pattern_index:
                pattern_index[data] = len(pattern_data)
                pattern_data.append(data)
            mine[p] = pattern_index[data]
        songs.append(bytes([speed, len(order), restart] + [mine[p] for p in order]))
    assert len(pattern_data) < 256
    songs_n = len(songs)
    head = 4 + 2 * songs_n
    insts = inst_bytes()
    at_insts = head
    at_table = at_insts + len(insts)
    at = at_table + 2 * len(pattern_data)
    table = bytearray()
    for data in pattern_data:
        table += struct.pack('<H', at)
        at += len(data)
    song_at = []
    for s in songs:
        song_at.append(at)
        at += len(s)
    out = struct.pack('<HH', at_insts, at_table) + struct.pack(f'<{songs_n}H', *song_at)
    out += insts + table + b''.join(pattern_data) + b''.join(songs)
    assert len(out) == at and len(out) < 0x10000
    with open(os.path.join(gen, 'music.bin'), 'wb') as f:
        f.write(out)
    with open(os.path.join(gen, 'songs.h'), 'w') as f:
        f.write('// Generated by tools/mkmusic.py - do not edit\n#pragma once\n'
                f'#define MUSIC_SIZE {len(out)}u  // MUSIC: the songs (src/music.s)\n'
                f'#define MUSIC_SONGS {songs_n}  // 0 the title\'s, the radio\'s from 1 on\n')
    print(f'mkmusic: {len(pattern_data)} patterns, {len(out)} bytes')


if __name__ == '__main__':
    main()
