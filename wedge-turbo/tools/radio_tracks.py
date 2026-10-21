"""The radio's own tracks (05 on), composed for Wedge Turbo, for
tools/mkmusic.py to build.

A track is a few sections of four bars of 16 rows: its chords, a beat, a
bass line, an accompaniment and the melody. From them mkmusic.py makes the
intro (beat, bass, accompaniment), A and B with the melody - A2 and B2 with
their own last bar - and a break; `order` strings them together (I, A, a,
B, b, X), the song going back to its second section at the end.

    speed     frames per row
    lead      the melody's instrument
    a, b      chords (four, one a bar) and the melody's bars; a_end, b_end
              the last bar of A2, B2 (b_end_chord: a chord of its own)
    drums     a bar of the beat: K kick, S snare, T, t toms high and low
    fill      its last bar in A and B
    intro     the beat of the intro
    hats      the hi-hat on the right: h closed, o open
    ticks     the ticks on the left: x
    bass      a bar of the bass line, per row: R root, T third, F fifth,
              6 sixth, S seventh (minor), O octave, - off
    second    the accompaniment: arp (the chord broken fast), pad (slowly),
              riff (root, third, fourth, fifth in eighths), or stab:...
              (x the chord, - off, per row)

A melody bar is notes and rests with their length in rows: "E5:4 r:2 ...".
"""

TRACKS = [
    # 05 - synthwave at night
    dict(name='NIGHT DRIVE', speed=6, lead='lead', order='IAaBbXAb',
         a=('Am F C G', ['E5:6 D5:2 C5:4 B4:2 C5:2', 'A4:8 r:4 C5:2 D5:2',
                          'E5:6 G5:2 E5:4 D5:2 C5:2', 'D5:12 r:4']),
         a_end='D5:6 E5:2 B4:8',
         b=('F G Em Am', ['A5:4 G5:2 F5:2 E5:4 C5:4', 'D5:4 E5:2 F5:2 G5:4 D5:4',
                          'E5:6 D5:2 B4:4 G4:4', 'A4:12 r:4']),
         b_end='A4:4 C5:4 E5:8',
         drums='K...S...K...S...', fill='K...S...S.S.TTtt', intro='K.......K.......',
         hats='..h...h...h...h.', ticks='x.x.x.x.x.x.x.x.', bass='R.R.O.R.R.R.O.R.', second='arp'),
    # 06 - Eurobeat: octaves bouncing, stabs on the off-beat
    dict(name='TURBO BOOST', speed=5, lead='saw lead', order='IAaBbAaX',
         a=('Dm Bb C A', ['D5:2 F5:2 A5:2 F5:2 D6:4 C6:2 A5:2', 'A#5:4 A5:2 F5:2 D5:4 F5:4',
                          'C5:2 E5:2 G5:2 E5:2 C6:4 A#5:2 G5:2', 'A5:6 G5:2 E5:2 C#5:2 A4:4']),
         a_end='A5:4 C#6:4 E6:4 r:4',
         b=('Gm Dm Bb A', ['G5:8 A5:4 A#5:4', 'A5:8 F5:4 D5:4', 'F5:6 E5:2 D5:4 F5:4', 'E5:12 r:4']),
         b_end='C#5:4 E5:4 A5:8',
         drums='K...S...K...S...', fill='K...S...K.S.S.SS', intro='K...K...K...K...',
         hats='..o...o...o...o.', ticks='x.x.x.x.x.x.x.x.', bass='R.O.R.O.R.O.R.O.',
         second='stab:..x-..x-..x-..x-'),
    # 07 - funk by the sea
    dict(name='COASTLINE', speed=6, lead='bell', order='IAaBbXBb',
         a=('Em7 Am7 D G', ['B4:3 D5:3 E5:2 G5:4 E5:2 D5:2', 'C5:3 E5:3 A5:2 G5:4 E5:4',
                            'F#5:3 A5:3 F#5:2 E5:2 D5:2 E5:4', 'D5:8 B4:4 r:4']),
         a_end='D5:3 G5:3 B5:2 A5:8',
         b=('C D Bm Em', ['G5:4 E5:4 C5:4 E5:4', 'F#5:4 A5:4 D6:4 C6:2 A5:2',
                          'B5:6 A5:2 F#5:4 D5:4', 'E5:12 r:4']),
         b_end='E5:4 G5:4 B5:8',
         drums='K.K...S..KK...S.', fill='K.K...S..K..TTtt', intro='K.K.......K.....',
         hats='h.h.h.h.h.h.h.h.', ticks='...x...x...x...x', bass='R..R..O.F.R-S.O.',
         second='stab:..x-..x-..x-..x-'),
    # 08 - a guitar riff, all out
    dict(name='FINAL LAP', speed=5, lead='lead', order='IAaBbAbX',
         a=('Em Em C D', ['B4:4 E5:4 G5:4 F#5:2 E5:2', 'D5:4 E5:4 B4:8',
                          'C5:4 E5:4 G5:4 A5:2 G5:2', 'F#5:8 D5:4 A4:4']),
         a_end='F#5:4 A5:4 B5:8',
         b=('G D Em C', ['G5:6 F#5:2 G5:4 B5:4', 'A5:8 F#5:4 D5:4', 'G5:6 F#5:2 E5:4 B4:4',
                         'C5:6 D5:2 E5:8']),
         b_end='D#5:8 F#5:4 B5:4', b_end_chord='B',
         drums='K...S.K.K...S...', fill='K...S.K.S.S.TTtt', intro='K.......K.K.....',
         hats='h.h.h.h.h.h.h.h.', ticks='................', bass='R.R.R.R.R.R.R.R.', second='riff'),
    # 09 - electro, the arpeggio does the work
    dict(name='NEON GRID', speed=5, lead='saw lead', order='IAaBbXab',
         a=('Cm Ab Eb Bb', ['G5:2 r:2 G5:2 D#5:2 C5:4 D#5:4', 'F5:2 r:2 F5:2 D#5:2 C5:8',
                            'D#5:2 r:2 D#5:2 G5:2 A#5:4 G5:4', 'F5:12 r:4']),
         a_end='F5:4 D5:4 A#4:8',
         b=('Fm Cm Ab G', ['C6:8 G#5:4 F5:4', 'G5:8 D#5:4 C5:4', 'G#5:6 G5:2 F5:4 D#5:4',
                           'B4:4 D5:4 G5:8']),
         b_end='G5:4 F5:4 D5:4 B4:4',
         drums='K..K..S.K..K..S.', fill='K..K..S.K.S.S.SS', intro='K..K....K..K....',
         hats='h.hhh.hhh.hhh.hh', ticks='................', bass='R..R..O.R..R..O.', second='arp'),
    # 10 - Phrygian heat, toms and a tresillo
    dict(name='DESERT HEAT', speed=6, lead='lead', order='IAaBbXAb',
         a=('Em F Em F', ['E5:2 F5:2 G5:2 F5:2 E5:4 B4:4', 'C5:2 D5:2 E5:2 F5:2 A5:4 G5:4',
                          'F5:2 E5:2 D5:2 E5:2 B4:8', 'A4:4 C5:4 F5:4 E5:4']),
         a_end='F5:8 E5:8',
         b=('G F Em Em', ['G5:6 A5:2 B5:4 G5:4', 'A5:6 G5:2 F5:4 C5:4', 'E5:4 F5:2 G5:2 F5:4 E5:4',
                          'E5:12 r:4']),
         b_end='B4:4 E5:4 G5:4 B5:4',
         drums='K.....S.K.K...S.', fill='K.....S.TTttTTtt', intro='K.....T.K.K...t.',
         hats='..h...h...h...h.', ticks='x..x..x..x..x...', bass='R..R..R.R..R..F.', second='pad'),
    # 11 - slow, in the rain
    dict(name='RAIN CIRCUIT', speed=7, lead='soft lead', order='IAaBbAbX',
         a=('F#m D A E', ['C#5:8 B4:4 A4:4', 'F#4:8 A4:4 B4:4', 'C#5:6 E5:2 D5:4 C#5:4', 'B4:12 r:4']),
         a_end='B4:6 C#5:2 G#4:8',
         b=('Bm F#m D E', ['D5:8 C#5:4 B4:4', 'C#5:8 A4:4 F#4:4', 'A4:6 B4:2 C#5:4 D5:4',
                           'E5:12 r:4']),
         b_end='E5:4 D5:4 C#5:4 B4:4',
         drums='K.......S.......', fill='K.......S...TTtt', intro='K...............',
         hats='h...h...h...h...', ticks='.......x.......x', bass='R.......F...R...', second='pad'),
    # 12 - a boogie in the pits
    dict(name='PIT STOP', speed=5, lead='lead', order='IAaBbAbX',
         a=('A A D A', ['E5:2 G5:2 A5:4 G5:2 E5:2 C#5:4', 'A4:4 C5:2 C#5:2 E5:8',
                        'F#5:2 A5:2 F#5:2 D5:2 C5:4 A4:4', 'C#5:8 r:8']),
         a_end='E5:4 C#5:4 A4:8',
         b=('E D A E', ['B5:4 G#5:4 E5:4 D5:4', 'A5:4 F#5:4 D5:8', 'C#6:4 A5:4 E5:4 C#5:4',
                        'B4:4 D5:4 E5:4 G#5:4']),
         b_end='B5:12 r:4',
         drums='K...S..KK...S...', fill='K...S..KS.S.TTtt', intro='K...S...K...S...',
         hats='h.h.h.h.h.h.h.h.', ticks='..x...x...x...x.', bass='R.T.F.6.S.6.F.T.',
         second='stab:x-..x-..x-..x-..'),
    # 13 - four to the floor, fast
    dict(name='OVERDRIVE', speed=4, lead='saw lead', order='IAABbXab',
         a=('Fm Fm Db Eb', ['C6:2 r:2 C6:2 r:2 G#5:2 r:2 F5:4', 'C6:2 r:2 C6:2 r:2 D#6:4 C6:4',
                            'C#6:2 r:2 C#6:2 r:2 A#5:2 r:2 G#5:4', 'G5:8 A#5:4 G5:4']),
         a_end='D#6:8 G5:8',
         b=('Bbm Fm Db C', ['F5:8 C#5:4 A#4:4', 'C5:8 G#4:4 F4:4', 'G#4:4 C#5:4 F5:4 G#5:4',
                            'G5:4 E5:4 C5:8']),
         b_end='E5:4 G5:4 C6:8',
         drums='K...K...K...K...', fill='K...K...K.K.KKKK', intro='K...K...K...K...',
         hats='..o...o...o...o.', ticks='x.x.x.x.x.x.x.x.', bass='..R...R...R...R.', second='arp'),
    # 14 - up the mountain, in D major
    dict(name='ALPINE PASS', speed=6, lead='lead', order='IAaBbAbX',
         a=('D A Bm G', ['F#5:4 E5:2 D5:2 A5:8', 'E5:4 F#5:2 G5:2 A5:4 C#5:4',
                         'D5:4 F#5:4 B5:4 A5:4', 'G5:12 r:4']),
         a_end='G5:4 B5:4 D6:8',
         b=('G A F#m Bm', ['B5:6 A5:2 G5:4 D5:4', 'C#6:6 B5:2 A5:4 E5:4', 'A5:4 F#5:4 C#5:4 F#5:4',
                           'D5:8 B4:8']),
         b_end='D6:12 r:4', b_end_chord='D',
         drums='K...S...K.K.S...', fill='K...S...K.K.TTtt', intro='K.......K.K.....',
         hats='..h...h...h...h.', ticks='x...x...x...x...', bass='R.R.R.R.O.O.R.R.', second='arp'),
    # 15 - a dark groove underground
    dict(name='MIDNIGHT TUNNEL', speed=6, lead='bell', order='IAaBbXAb',
         a=('Gm Gm Eb D', ['D5:4 r:2 A#4:2 C5:4 D5:4', 'G5:4 F5:2 D5:2 A#4:8',
                           'D#5:4 r:2 G5:2 F5:4 D#5:4', 'D5:4 F#4:4 A4:8']),
         a_end='A4:4 C5:4 D5:4 F#5:4',
         b=('Cm Gm Eb D', ['G5:6 D#5:2 C5:8', 'A#5:6 G5:2 D5:8', 'G5:4 A#5:4 G5:4 D#5:4',
                           'F#5:12 r:4']),
         b_end='A5:4 F#5:4 D5:8',
         drums='K..K..S...K...S.', fill='K..K..S...K.TTtt', intro='K..K......K.....',
         hats='h.h.h.h.h.h.h.h.', ticks='......x.......x.', bass='R.RO..R.R.RF..S.',
         second='stab:x-......x-......'),
    # 16 - the podium
    dict(name='VICTORY LANE', speed=5, lead='saw lead', order='IAaBbAbX',
         a=('Bb F Gm Eb', ['F5:2 A#5:2 D6:4 C6:2 A#5:2 F5:4', 'A5:4 C6:4 F5:8',
                           'G5:2 A#5:2 D6:4 C6:4 A#5:4', 'G5:8 D#5:4 F5:4']),
         a_end='G5:4 A#5:4 D#6:8',
         b=('Eb F Dm Gm', ['D#5:4 G5:4 A#5:8', 'C6:4 A5:4 F5:8', 'D6:6 C6:2 A5:4 F5:4', 'G5:12 r:4']),
         b_end='C6:4 A5:4 F6:8', b_end_chord='F',
         drums='K...S...K...S.KK', fill='K...S...K.S.SSSS', intro='K.......K.......',
         hats='h.h.h.h.h.h.h.h.', ticks='....x.......x...', bass='R...O...R.F.O...',
         second='stab:x-x-....x-x-....'),
]
