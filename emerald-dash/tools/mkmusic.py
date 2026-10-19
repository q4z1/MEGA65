#!/usr/bin/env python3
"""Emerald Dash title music: the song as text, turned into C tables for the
player in src/music.c.

Usage: mkmusic.py <outdir>

The song is written per bar of 16 rows (sixteenth notes). A note is
"name:rows" (C-4 is middle C, A-4 = 440 Hz, sharps as C#4), "-:rows" is a
rest. Six voices on two SIDs: the left one ($D420) plays lead, bass and
arpeggio chords; the right one ($D460) an echo of the lead, the bass again
and the drums.

Event bytes per voice:
  0x00-0x5F  note number, played for the current length
  0x7F       rest for the current length
  0x80+i     instrument i
  0xC0+n     length n+1 rows
  0xFF       back to the start
"""

import sys

TEMPO = 6           # frames per row: 125 beats per minute at 50 Hz
SID_CLOCK = 985248  # PAL

# ---------------------------------------------------------------- the song
# A minor; part A then part B, looped. Our own tune.

CHORDS = ["Am", "F", "C", "G", "Am", "F", "G", "E",
          "Dm", "Am", "Dm", "Am", "F", "G", "Am", "E"]

LEAD = [
    # part A
    "E-5:2 A-5:2 C-6:2 B-5:2 A-5:4 E-5:4",
    "F-5:2 A-5:2 C-6:2 A-5:2 F-5:4 C-5:4",
    "G-5:2 E-5:2 C-5:2 E-5:2 G-5:4 C-6:4",
    "B-5:4 A-5:2 G-5:2 D-5:8",
    "E-5:2 A-5:2 C-6:2 E-6:2 D-6:4 C-6:4",
    "A-5:2 C-6:2 F-6:2 E-6:2 D-6:4 C-6:4",
    "B-5:2 G-5:2 D-6:2 B-5:2 G-5:4 B-5:4",
    "G#5:4 B-5:4 D-6:4 E-6:4",
    # part B
    "F-5:4 A-5:2 D-6:6 C-6:2 A-5:2",
    "C-6:4 E-6:4 A-5:8",
    "D-6:2 F-6:2 E-6:2 D-6:2 C-6:4 A-5:4",
    "E-5:4 A-5:4 C-6:4 E-6:4",
    "F-6:4 E-6:2 C-6:2 A-5:4 C-6:4",
    "D-6:4 B-5:2 G-5:2 B-5:4 D-6:4",
    "C-6:2 B-5:2 A-5:2 E-5:2 A-5:8",
    "G#5:2 A-5:2 B-5:2 D-6:2 E-6:8",
]

# Bass: eighths jumping between root and octave; the dominant bars walk up
BASS_PATTERN = [0, 12, 0, 12, 0, 12, 0, 12]
BASS_WALK = [0, 12, 0, 12, 4, 7, 11, 12]
BASS_ROOT = {"A": "A-2", "F": "F-2", "C": "C-3", "G": "G-2", "E": "E-2", "D": "D-3"}

# Chord stabs: three rows on, one off
ARP_RHYTHM = [3, 1, 3, 1, 3, 1, 3, 1]
ARP_ROOT = {"A": "A-4", "F": "F-4", "C": "C-5", "G": "G-4", "E": "E-4", "D": "D-5"}

# Drums: K kick, S snare, H hi-hat, two rows each; the last bar has a fill
DRUMS = "KHSHKKSH"
DRUMS_FILL = "KHSHSSSS"

ECHO_DELAY = 3  # rows

# Instruments. wave: 0x10 triangle, 0x20 saw, 0x40 pulse, 0x80 noise.
# pwm: pulse width change per frame; vib: vibrato delay (frames) and depth
# (frequency >> depth); arp: 0 none, 1 minor, 2 major chord; sweep: pitch
# falls by frequency >> sweep each frame; noise: frames of noise at the start.
INSTR = {
    "lead":  dict(wave=0x40, ad=0x08, sr=0xA6, pw=0x600, pwm=20, vib=(10, 6)),
    "echo":  dict(wave=0x40, ad=0x08, sr=0x56, pw=0x900, pwm=-14, vib=(10, 6)),
    "bass":  dict(wave=0x20, ad=0x06, sr=0x51),
    "minor": dict(wave=0x40, ad=0x02, sr=0x84, pw=0x400, pwm=10, arp=1),
    "major": dict(wave=0x40, ad=0x02, sr=0x84, pw=0x400, pwm=10, arp=2),
    "kick":  dict(wave=0x10, ad=0x08, sr=0x00, sweep=3, noise=1),
    "snare": dict(wave=0x80, ad=0x09, sr=0x00),
    "hat":   dict(wave=0x80, ad=0x02, sr=0x00),
}
DRUM_NOTE = {"K": ("kick", "G-4"), "S": ("snare", "A-5"), "H": ("hat", "C-7")}

# ---------------------------------------------------------------- conversion

NAMES = ["C-", "C#", "D-", "D#", "E-", "F-", "F#", "G-", "G#", "A-", "A#", "B-"]


def note_number(name):
    return NAMES.index(name[:2]) + 12 * int(name[2])


def parse_bar(text):
    out = []
    for tok in text.split():
        n, _, rows = tok.partition(":")
        out.append((None if n == "-" else note_number(n), int(rows)))
    if sum(r for _, r in out) != 16:
        sys.exit(f"mkmusic: bar does not have 16 rows: {text}")
    return out


def voices():
    """Each voice as a list of (instrument, note or None, rows)."""
    lead = [("lead", n, r) for bar in LEAD for n, r in parse_bar(bar)]

    # echo: the lead, ECHO_DELAY rows later (the end wraps to the start)
    timeline = []
    for _, n, r in lead:
        timeline += [n] + ["tie"] * (r - 1)
    total = len(timeline)
    timeline = timeline[-ECHO_DELAY:] + timeline[:-ECHO_DELAY]
    echo, i = [], 0
    while i < total:
        n = timeline[i] if timeline[i] != "tie" else timeline_note_before(timeline, i)
        j = i + 1
        while j < total and timeline[j] == "tie":
            j += 1
        echo.append(("echo", n, j - i))
        i = j

    bass, arp, drums = [], [], []
    for b, chord in enumerate(CHORDS):
        root = chord[0]
        pattern = BASS_WALK if chord == "E" else BASS_PATTERN
        base = note_number(BASS_ROOT[root])
        bass += [("bass", base + o, 2) for o in pattern]
        inst = "minor" if chord.endswith("m") else "major"
        a = note_number(ARP_ROOT[root])
        for k, r in enumerate(ARP_RHYTHM):
            arp.append((inst, a if k % 2 == 0 else None, r))
        for d in (DRUMS_FILL if b == len(CHORDS) - 1 else DRUMS):
            inst, n = DRUM_NOTE[d]
            drums.append((inst, note_number(n), 2))
    # left SID: lead, bass, chords; right SID: echo, bass, drums
    return [lead, bass, arp, echo, list(bass), drums]


def timeline_note_before(timeline, i):
    while timeline[i] == "tie":
        i -= 1
    return timeline[i]


def encode(events, inames):
    out, inst, length = [], None, None
    for i, n, r in events:
        if i != inst:
            out.append(0x80 + inames.index(i))
            inst = i
        if r != length:
            out.append(0xC0 + r - 1)
            length = r
        out.append(0x7F if n is None else n)
    out.append(0xFF)
    return out


def freq_table():
    tab = []
    for n in range(96):
        f = 440.0 * 2 ** ((n - 57) / 12)
        tab.append(min(0xFFFF, round(f * 16777216 / SID_CLOCK)))
    return tab


def main():
    outdir = sys.argv[1]
    inames = list(INSTR)
    vs = voices()
    rows = [sum(r for _, _, r in v) for v in vs]
    if len(set(rows)) != 1:
        sys.exit(f"mkmusic: voices differ in length: {rows}")
    with open(f"{outdir}/song.h", "w") as f:
        f.write("// Generated by tools/mkmusic.py - do not edit\n#ifndef SONG_H\n#define SONG_H\n")
        f.write("#include <stdint.h>\n\n")
        f.write(f"#define SONG_TEMPO {TEMPO}\n#define SONG_VOICES {len(vs)}\n")
        f.write(f"#define SONG_INSTRUMENTS {len(inames)}\n\n")
        f.write("struct instrument {\n    uint8_t wave, ad, sr;\n    uint16_t pw;\n    int8_t pwm;\n"
                "    uint8_t vib_delay, vib_depth, arp, sweep, noise;\n};\n\n")
        f.write("extern const struct instrument song_instr[SONG_INSTRUMENTS];\n")
        f.write("extern const uint8_t *const song_voice[SONG_VOICES];\n")
        f.write("extern const uint16_t note_freq[96];\n\n#endif\n")
    with open(f"{outdir}/song.c", "w") as f:
        f.write('// Generated by tools/mkmusic.py - do not edit\n#include "song.h"\n\n')
        f.write("const struct instrument song_instr[SONG_INSTRUMENTS] = {\n")
        for name in inames:
            d = INSTR[name]
            vd, vdep = d.get("vib", (0, 0))
            f.write(f"    {{0x{d['wave']:02x}, 0x{d['ad']:02x}, 0x{d['sr']:02x}, 0x{d.get('pw', 0x800):03x}, "
                    f"{d.get('pwm', 0)}, {vd}, {vdep}, {d.get('arp', 0)}, {d.get('sweep', 0)}, "
                    f"{d.get('noise', 0)}}},  // {name}\n")
        f.write("};\n\n")
        for k, v in enumerate(vs):
            data = encode(v, inames)
            f.write(f"static const uint8_t voice{k}[{len(data)}] = {{\n")
            for i in range(0, len(data), 16):
                f.write("    " + ", ".join(f"0x{b:02x}" for b in data[i:i + 16]) + ",\n")
            f.write("};\n")
        f.write("\nconst uint8_t *const song_voice[SONG_VOICES] = {"
                + ", ".join(f"voice{k}" for k in range(len(vs))) + "};\n\n")
        tab = freq_table()
        f.write("const uint16_t note_freq[96] = {\n")
        for i in range(0, 96, 12):
            f.write("    " + ", ".join(f"0x{v:04x}" for v in tab[i:i + 12]) + ",\n")
        f.write("};\n")
    print(f"mkmusic: {len(vs)} voices, {rows[0]} rows, {rows[0] * TEMPO / 50:.1f} s per loop")


if __name__ == "__main__":
    main()
