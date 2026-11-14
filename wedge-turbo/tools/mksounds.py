#!/usr/bin/env python3
"""Wedge Turbo's race sounds, made at build time: the engine and the
effects, synthesized here (no recordings).

    mksounds.py GENDIR [--wav DIR]

Writes into GENDIR:
    sounds.bin    the samples, 8-bit signed, one after the other (on the
                  disk as SOUNDS)
    sounds.c/.h   where each sample is, its loudness and loop, and per
                  effect the sample and the period it plays at

--wav DIR also writes each effect as a WAV file to listen to, and the
engine at a few rpm.

The player (src/sound.c) plays effect n as one sample at a period of the
Amiga's clock (3546895 / period samples a second); effect 8 is the engine,
a loop that sound.c plays faster with the rpm (period 0xF80C0 / rpm). The
effects: 1 crash into the scenery, 2 into a car, 3 the countdown, 4 the
start, 5 low fuel, 6 the kerb, 7 tyres screeching.
"""
import math
import os
import sys
import wave

import numpy as np

CLOCK = 3546895  # Amiga PAL: samples a second = CLOCK / period
SOUND_CHIP_SIZE = 0x5300  # src/mem.h: room for the samples in chip RAM
ENGINE_RPM = 0xF80C0  # sound.c: the engine's period = ENGINE_RPM / rpm

# The engine: one firing a revolution - a cycle of the loop is CYCLE
# samples, so at rpm r it sounds at r / 60 Hz (CLOCK * r / ENGINE_RPM / CYCLE)
CYCLE = round(CLOCK / ENGINE_RPM * 60)
CYCLES = 16


def rate(period):
    return CLOCK / period


def t_axis(seconds, period):
    return np.arange(int(seconds * rate(period))) / rate(period)


def lowpass(x, cutoff, sr, circular=False):
    """A soft low-pass in the frequency domain; circular keeps a loop's
    ends meeting"""
    n = len(x) if circular else 2 * len(x)
    spec = np.fft.rfft(x, n)
    f = np.fft.rfftfreq(n, 1 / sr)
    spec *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(spec, n)[:len(x)]


def bandpass(x, lo, hi, sr):
    return lowpass(x, hi, sr) - lowpass(x, lo, sr)


def fade(x, sr, attack=0.003, release=0.03):
    """Ramps at both ends, so nothing clicks"""
    env = np.ones(len(x))
    a, r = max(1, int(attack * sr)), max(1, int(release * sr))
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.minimum(env[-r:], np.linspace(1, 0, r))
    return x * env


def engine(rng):
    """The loop: per cycle a firing - a hard knock ringing down on the
    cycle's 3rd and 7th harmonic - with the cycles a little uneven, and a
    rasp of noise; filtered round the loop so its ends meet"""
    sr = rate(856)  # as made; sound.c plays it at any period
    n = CYCLE * CYCLES
    out = np.zeros(n)
    k = np.arange(CYCLE) / CYCLE
    for c in range(CYCLES):
        amp = 1.0 + 0.12 * rng.standard_normal() + (0.08 if c % 2 else -0.05)
        ring = (np.sin(2 * np.pi * 3 * k + 0.4) * np.exp(-k * 5.5)
                + 0.45 * np.sin(2 * np.pi * 7 * k + 1.1) * np.exp(-k * 9)
                + 0.25 * np.sin(2 * np.pi * 12 * k) * np.exp(-k * 16))
        knock = np.exp(-k * 40) * (1 - 2 * k)
        out[c * CYCLE:(c + 1) * CYCLE] = amp * (ring + 0.8 * knock)
    noise = lowpass(rng.standard_normal(n), 900, sr, circular=True)
    envelope = np.tile(np.exp(-np.arange(CYCLE) / CYCLE * 4), CYCLES)
    out += 0.35 * noise * (0.3 + envelope)
    out = lowpass(out, 1500, sr, circular=True)
    return out - out.mean()


def crash_scenery(rng, period):
    """A dull crunch: a thump dropping in pitch, a burst of dark noise and
    crackle that dies away"""
    t = t_axis(0.6, period)
    sr = rate(period)
    thump = np.sin(2 * np.pi * np.cumsum(55 + 75 * np.exp(-t / 0.08)) / sr) * np.exp(-t / 0.12)
    rumble = lowpass(rng.standard_normal(len(t)), 700, sr) * np.exp(-t / 0.2)
    crackle = np.zeros(len(t))
    for at in rng.uniform(0, 0.35, 40):
        i = int(at * sr)
        crackle[i:i + 6] += rng.uniform(-1, 1) * np.exp(-np.arange(len(crackle[i:i + 6])) / 2)
    crackle = bandpass(crackle, 400, 2000, sr) * np.exp(-t / 0.15)
    x = 1.2 * thump + 1.6 * rumble / np.abs(rumble).max() + 2.5 * crackle / max(1e-9, np.abs(crackle).max())
    return fade(x, sr, release=0.08)


def crash_car(rng, period):
    """Sheet metal: a clank of partials that do not fit together, ringing
    down at their own speeds, after a short hit of noise"""
    t = t_axis(0.4, period)
    sr = rate(period)
    x = np.zeros(len(t))
    for f, tau, a in ((212, 0.16, 1.0), (517, 0.11, 0.8), (893, 0.08, 0.6), (1340, 0.05, 0.45), (1810, 0.035, 0.3)):
        x += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.3)) * np.exp(-t / tau)
    hit = lowpass(rng.standard_normal(len(t)), 1800, sr) * np.exp(-t / 0.015)
    return fade(x + 1.5 * hit, sr, release=0.06)


def beep(period):
    """The countdown's tone (the start plays it higher): a square wave with
    its corners rounded, held, then dying away"""
    t = t_axis(0.5, period)
    sr = rate(period)
    f = 440 * period / 0x23A  # 440 Hz at the countdown's period
    x = sum(np.sin(2 * np.pi * f * h * t) / h for h in (1, 3, 5))
    env = np.where(t < 0.28, 1.0, np.exp(-(t - 0.28) / 0.07))
    return fade(x * env, sr, release=0.02)


def low_fuel(period):
    """Two short high pips"""
    t = t_axis(0.17, period)
    sr = rate(period)
    x = np.sign(np.sin(2 * np.pi * 1180 * t)) * 0.7 + 0.3 * np.sin(2 * np.pi * 2360 * t)
    x = lowpass(x, 3000, sr)
    gate = ((t < 0.065) | ((t > 0.095) & (t < 0.16))).astype(float)
    gate = lowpass(gate, 300, sr)
    return fade(x * gate, sr, release=0.005)


def kerb(rng, period):
    """The rumble strips: a quick train of knocks, fading"""
    t = t_axis(0.35, period)
    sr = rate(period)
    x = np.zeros(len(t))
    k = np.arange(int(0.03 * sr)) / sr
    knock = np.sin(2 * np.pi * 150 * k) * np.exp(-k / 0.008)
    for at in np.arange(0, 0.33, 1 / 27):
        i = int(at * sr)
        part = knock[:len(x) - i] * (1 + 0.15 * rng.standard_normal())
        x[i:i + len(part)] += part
    x += 0.25 * lowpass(rng.standard_normal(len(t)), 600, sr)
    return fade(x * np.exp(-t / 0.13), sr, release=0.04)


def screech(rng, period):
    """Tyres: a squeal that wavers, with a hiss under it; it swells, holds
    and fades"""
    t = t_axis(0.8, period)
    sr = rate(period)
    drift = lowpass(rng.standard_normal(len(t)), 4, sr)
    drift /= np.abs(drift).max()
    f = 870 + 35 * np.sin(2 * np.pi * 6.5 * t) + 60 * drift
    phase = 2 * np.pi * np.cumsum(f) / sr
    x = np.sin(phase) + 0.35 * np.sin(2 * phase + 0.7) + 0.15 * np.sin(3 * phase)
    x += 0.5 * bandpass(rng.standard_normal(len(t)), 700, 2600, sr)
    env = np.minimum(1, t / 0.1) * np.where(t > 0.62, np.exp(-(t - 0.62) / 0.06), 1)
    return fade(x * (0.7 + 0.3 * env) * env, sr, release=0.03)


def to_bytes(x, loudness):
    """8-bit, squeezed (a soft clip, as loud as the race needs it) to the
    mean loudness given (RMS, of 128)"""
    x = np.asarray(x, float)
    x = x / max(1e-9, np.abs(x).max())
    lo, hi = 0.01, 40.0
    for _ in range(40):
        drive = math.sqrt(lo * hi)
        y = np.tanh(drive * x) / math.tanh(drive) * 124
        if math.sqrt((y * y).mean()) < loudness:
            lo = drive
        else:
            hi = drive
    rms = math.sqrt((y * y).mean())
    if rms > loudness:  # loud by itself (a square wave): only softer
        y *= loudness / rms
    return np.clip(np.round(y), -128, 127).astype(np.int8)


# the effects: (name, period it plays at); the samples in this order
PERIOD_CRASH, PERIOD_BEEP, PERIOD_START, PERIOD_HIGH = 0x2C0, 0x23A, 0x1C5, 0x1C5
ENGINE_PERIOD = 856  # only for the WAV files: sound.c takes it from the rpm


def make():
    rng = np.random.default_rng(0x3ED6E)
    # name, bytes, volume (0-64), loops
    samples = [
        ('crash scenery', to_bytes(crash_scenery(rng, PERIOD_CRASH), 55), 64, False),
        ('crash car', to_bytes(crash_car(rng, PERIOD_CRASH), 60), 64, False),
        ('beep', to_bytes(beep(PERIOD_BEEP), 50), 64, False),
        ('low fuel', to_bytes(low_fuel(PERIOD_HIGH), 60), 64, False),
        ('kerb', to_bytes(kerb(rng, PERIOD_HIGH), 42), 40, False),
        ('screech', to_bytes(screech(rng, PERIOD_BEEP), 52), 64, False),
        ('engine', to_bytes(engine(rng), 55), 64, True),
    ]
    # effect -> (sample, period); 0: none, 8: the engine
    notes = [(0xFF, 0), (0, PERIOD_CRASH), (1, PERIOD_CRASH), (2, PERIOD_BEEP), (2, PERIOD_START),
             (3, PERIOD_HIGH), (4, PERIOD_HIGH), (5, PERIOD_BEEP), (6, ENGINE_PERIOD)]
    return samples, notes


# frames an effect keeps the effects from its own number on off (sound.c):
# a crash or the countdown is not cut short by the kerb or a screech
SOUND_TIMES = [0, 20, 30, 40, 40, 4, 6, 24]


def write_wav(path, x, sr, out_rate=22050):
    """x played as the audio DMA does: each sample held until the next"""
    idx = np.minimum((np.arange(int(len(x) / sr * out_rate)) * sr / out_rate).astype(int), len(x) - 1)
    pcm = (np.asarray(x, np.int16)[idx] * 200).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(out_rate)
        w.writeframes(pcm.tobytes())


def wavs(out, samples, notes):
    os.makedirs(out, exist_ok=True)
    names = ['', 'crash-scenery', 'crash-car', 'countdown', 'start', 'low-fuel', 'kerb', 'screech']
    for e in range(1, 8):
        s, period = notes[e]
        write_wav(os.path.join(out, f'{e}-{names[e]}.wav'), samples[s][1], rate(period))
    loop = samples[notes[8][0]][1]
    for rpm in (1000, 3000, 5000, 7500):
        period = max(0x7C, ENGINE_RPM // rpm)
        x = np.tile(loop, math.ceil(1.5 * rate(period) / len(loop)))[:int(1.5 * rate(period))]
        write_wav(os.path.join(out, f'8-engine-{rpm}rpm.wav'), x, rate(period))


def main():
    args = sys.argv[1:]
    if len(args) not in (1, 3) or (len(args) == 3 and args[1] != '--wav'):
        sys.exit(__doc__)
    gen = args[0]
    os.makedirs(gen, exist_ok=True)
    samples, notes = make()
    data, table = bytearray(), []
    for name, px, volume, loops in samples:
        if len(px) & 1:
            px = px[:-1]
        table.append((len(data), len(px), volume, 0, len(px) if loops else 0, name))
        data += px.tobytes()
    assert len(data) <= SOUND_CHIP_SIZE, f'the sounds take {len(data)} bytes, room for {SOUND_CHIP_SIZE}'
    with open(os.path.join(gen, 'sounds.bin'), 'wb') as f:
        f.write(data)
    with open(os.path.join(gen, 'sounds.h'), 'w') as f:
        f.write('// Generated by tools/mksounds.py - do not edit\n'
                '#pragma once\n#include <stdint.h>\n'
                '// SOUNDS (sounds.bin): the samples the effects use, 8-bit signed, one\n'
                '// after the other\n'
                f'#define SOUNDS_SIZE {len(data)}u\n'
                f'#define SOUND_EFFECTS {len(notes)}  // effect 8 is the engine\n'
                'typedef struct { uint16_t at, len; uint8_t volume; uint16_t loop_at, loop_len; } SoundSample;\n'
                'typedef struct { uint8_t sample; uint16_t period; } SoundNote;  // sample 0xFF: none\n'
                f'extern const SoundSample sound_samples[{len(table)}];\n'
                f'extern const SoundNote sound_notes[{len(notes)}];\n'
                'extern const uint8_t sound_times[8];  // frames an effect keeps lower ones off\n')
    with open(os.path.join(gen, 'sounds.c'), 'w') as f:
        f.write('// Generated by tools/mksounds.py - do not edit\n#include "sounds.h"\n\n')
        f.write('const SoundSample sound_samples[%d] = {\n%s};\n' % (len(table), ''.join(
            '    {%d, %d, %d, %d, %d},  // %s\n' % v for v in table)))
        f.write('const SoundNote sound_notes[%d] = {\n%s};\n' % (len(notes), ''.join(
            '    {0x%02X, 0x%03X},\n' % e for e in notes)))
        f.write('const uint8_t sound_times[8] = {%s};\n' % ', '.join(map(str, SOUND_TIMES)))
    print(f'mksounds: {len(table)} samples, {len(data)} bytes')
    if len(args) == 3:
        wavs(args[2], samples, notes)


if __name__ == '__main__':
    main()
