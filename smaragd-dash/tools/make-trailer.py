#!/usr/bin/env python3
"""A trailer of the game from its recordings: <dir>/smaragd-dash-<VERSION>-trailer.mp4.

    tools/make-trailer.py [<dir>]       (default: build/trailer; the recordings there)
    tools/make-trailer.py <dir> --part N  (only part N and its neighbours, to look at)
    tools/make-trailer.py <dir> --thumbs  (only the thumbnails, THUMBS below)

The recordings in <dir> (mega65-cast -x 1, 704x576): title.mp4 (the normal
build left on the title: its picture and its music), caves.mp4 (the
screencast build playing the caves), tour.mp4 (tools/record-tour.sh),
editor.mp4 (tools/record-editor.sh), help.mp4 (the editor's test script
to its help pages), music.mp4 (the title again, as long as the trailer:
its music under it all; without it, title.mp4's). PARTS below says what
is taken from them.

Everything is put together picture by picture at the machine's size
(352x288, the MEGA65's pixels), so the captions, the wipes and their
sparkles are of the game's own pixels, and enlarged six times with sharp
pixels only at the end. The captions use the game's status font on a
panel that opens, lights its letters one after the other, lets a shine
run over them and closes again; spinning emeralds at its ends. The parts
go into one another with shaped wipes - an emerald, tiles turning over,
columns dropping in like boulders, the game's own covering of a cave -
with a golden rim and sparks along the edge. Under it all one track of
the title music, from the first second to the last, lower while the
game's own sounds play. The frames are streamed from the recordings and
into a lossless intermediate (body.mkv), so little is held in memory.
"""
import array
import math
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import mkgfx  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

W, H = 352, 288                 # the machine's pixels (the recordings are twice that)
Z = 6                           # enlarged
FPS = 50
RATE = 44100                    # the recordings' sound, stereo
X = 0.8                         # seconds of a wipe
BED = 0.45                      # the music's level under the game's sounds (1: alone)
GAME = 1.0                      # the game's sounds
VERSION = open(os.path.join(HERE, 'VERSION')).read().strip()

# ---- what the trailer shows --------------------------------------------------
# A part: its pieces (recording, from second, seconds, speed: 0.5 a replay
# at half speed, its sound left out; 1/200 one picture held four seconds), its captions (big line, small line,
# from, to seconds into the part; None: from just after the wipe in, to
# just before the wipe out), mute: the recording's sound left out (the
# music goes on alone).
# 'intro': the part begins covered, as a cave is, with lines on the
# cover, and is then uncovered; 'credits': the closing credits, on the cover.
# 'replay': (from, to) seconds into the part - REPLAY blinks above.
TITLE_CAP = ('SMARAGD DASH ' + VERSION, 'A BOULDER DASH STYLE GAME FOR THE MEGA65')
PARTS = [
    dict(pieces=[('title', 20.0, 19.0)], mute=True, intro=True,
         caps=[TITLE_CAP + (9.6, None)]),
    dict(pieces=[('caves', 21.0, 11.5)],
         caps=[('56 CAVES BY CLARKKENT', 'CWS BOULDER DASH 1, 2 AND 3', None, None)]),
    dict(pieces=[('caves', 34.5, 7.0), ('caves', 38.4, 2.8, 0.5)], replay=(7.0, 12.6),
         caps=[('NEW IN 1.6: ROCKFORD PUSHES', 'ARMS OUT, AS CLARKKENT DREW HIM', None, None)]),
    dict(pieces=[('caves', 164.0, 11.5)],
         caps=[('GENTLE FIRST LEVELS', 'CWS 1 AND 2: FEWER EMERALDS, MORE TIME', None, None)]),
    dict(pieces=[('caves', 132.0, 11.5)],
         caps=[('INTERMISSIONS', 'SMALL CAVES THAT STAND STILL - A LIFE TO WIN', None, None)]),
    dict(pieces=[('caves', 198.0, 11.5)],
         caps=[("PLAYED BY GDASH'S RULES", 'ITS ENGINE, RUNNING ON THE MEGA65', None, None)]),
    dict(pieces=[('caves', 280.5, 8.5), ('caves', 283.5, 2.0, 0.5)], replay=(8.5, 12.5),
         caps=[('CRUSH A BUTTERFLY ...', '... AND IT TURNS INTO EMERALDS', None, None)]),
    dict(pieces=[('caves', 318.0, 11.5)],
         caps=[('FIVE LEVELS FOR EVERY CAVE', 'THE FIFTH AS HARD AS THEY CAME', None, None)]),
    dict(pieces=[('caves', 435.5, 14.5)],
         caps=[('NEW IN 1.6: AN EXTRA LIFE', 'THE EMPTY CELLS FLICKER, AS ON THE C64', None, 6.4),
               ('SMOOTH SCROLLING', 'THE SAME PIXELS EVERY FRAME, AS IN GDASH', 6.8, None)]),
    dict(pieces=[('tour', 4.0, 11.5)],
         caps=[('EVERY ELEMENT OF GDASH', 'FOUR DEMO CAVES ON THE DISK SHOW THEM ALL', None, None)]),
    dict(pieces=[('tour', 38.0, 11.5)],
         caps=[('KEYS, DOORS AND MACHINES', 'CONVEYOR BELTS, TELEPORTERS, GROWING WALLS', None, None)]),
    dict(pieces=[('tour', 51.0, 11.5)],
         caps=[('WATER, FIRE AND EXPLOSIVES', 'BOMBS, NITRO, ROCKETS, LAVA AND GHOSTS', None, None)]),
    dict(pieces=[('help', 68.75, 0.02, 1 / 200), ('help', 70.75, 0.02, 1 / 200), ('help', 73.5, 0.02, 1 / 200)],
         mute=True,
         caps=[('HELP FOR EVERY ELEMENT', 'H ON THE TITLE: HOW TO PLAY, SEVEN PAGES', None, None)]),
    dict(pieces=[('editor', 24.0, 11.5)],
         caps=[('THE CAVE EDITOR', "ALL OF GDASH'S 95 ELEMENTS: E ON THE TITLE", None, None)]),
    dict(pieces=[('editor', 36.0, 11.5)],
         caps=[('DRAW YOUR OWN CAVES', 'FIRE PUTS, HELD IT DRAWS - U UNDOES', None, None)]),
    dict(pieces=[('editor', 52.0, 8.0), ('editor', 61.2, 0.02, 1 / 175)],
         caps=[('NAMES AND VALUES', 'TWO PAGES - EVEN HOW FAST ACID SPREADS', None, None)]),
    dict(pieces=[('editor', 62.5, 11.0)],
         caps=[('TRY IT AT ONCE', 'THEN SAVE IT: THREE GAMES OF YOUR OWN', None, None)]),
    dict(pieces=[('title', 128.5, 12.0)], mute=True,
         caps=[('SMARAGD DASH ' + VERSION + ' - OUT NOW', 'FILES.MEGA65.ORG  -  GITHUB.COM/Q4Z1/MEGA65', None, None)]),
    dict(credits=True, secs=20.0),
]
# the wipes between the parts, in turn
WIPES = ['gem', 'tiles', 'blinds', 'drop', 'clock', 'pixels', 'iris', 'tiles', 'drop', 'gem', 'blinds',
         'clock', 'tiles', 'iris', 'drop', 'pixels', 'gem']   # (into the credits: 'cover')

# the thumbnails (--thumbs), <dir>/smaragd-dash-<VERSION>-thumbnail<name>.png:
# a picture of a recording (from second) with a caption, 1280x720
THUMBS = [('', 'title', 32.0, TITLE_CAP),
          ('-pushes', 'caves', 40.96, ('NEW IN 1.6: ROCKFORD PUSHES', 'ARMS OUT, AS CLARKKENT DREW HIM')),
          ('-extra-life', 'caves', 437.5, ('NEW IN 1.6: AN EXTRA LIFE', 'THE EMPTY CELLS FLICKER, AS ON THE C64'))]

INTRO = [(('Q4Z1 (& CLAUDE AI) PRESENTS', ''), 0.6, 3.6),
         (('A GAME FOR THE MEGA65', 'DIG FOR EMERALDS - MIND THE BOULDERS'), 3.8, 7.2)]
UNCOVER = (7.4, 8.9)            # the intro's uncovering (seconds into it)
CREDITS = [('GAME', 'Q4Z1 & CLAUDE'),
           ('CAVES', 'CLARKKENT'),
           ('GRAPHICS', 'Q4Z1 & CLARKKENT'),
           ('MUSIC', 'Q4Z1 & CLAUDE'),
           ('RULES', 'GDASH'),
           ('AFTER', 'BOULDER DASH'),
           ('THANKS', 'FORUM64.DE')]
CREDITS_END = 'SEE YOU IN THE CAVES!'

# ---- colours, the font ---------------------------------------------------------
hexc = mkgfx.hexc
GOLD_ROWS = mkgfx.font_row_colours()            # the status font: 16 rows
SHADOW = mkgfx.FONT_SHADOW
GREEN = mkgfx.TITLE_RAMP                        # the big letters' ring, for a moving shine
RANKS = mkgfx.RANK_RAMPS                        # gold, silver, bronze, ice: the high score table
SEP = [c for c in mkgfx.SEP_ROWS if c]          # the status line's golden rule
WHITE = (255, 255, 255)
PALE = hexc('fff8c0')
ORANGE = hexc('ffb020')
EMBER = hexc('e06810')
SMALL = hexc('eef4ff')
# glyphs the game does not need
mkgfx.FONT5x7.update({
    "'": "00100 00100 01000 00000 00000 00000 00000",
    "&": "01100 10010 10100 01000 10101 10010 01101",
    "(": "00010 00100 01000 01000 01000 00100 00010",
    ")": "01000 00100 00010 00010 00010 00100 01000",
    "?": "01110 10001 00001 00010 00100 00000 00100",
})


def glyph_rows(ch):
    return [int(b, 2) for b in mkgfx.FONT5x7[ch].split()]


def big_text(text, rows=None):
    """text in the status font (8x16 a letter, bold, shadowed), coloured row
    by row (rows: 16 colours); RGBA, and the letters' x positions"""
    rows = rows or GOLD_ROWS
    img = Image.new('RGBA', (len(text) * 8 + 1, 17), (0, 0, 0, 0))
    px = img.load()
    for k, ch in enumerate(text):
        bits = mkgfx.font_glyph_bits(ch)
        for y in range(16):
            for x in range(8):
                if bits[y] & (0x80 >> x):
                    px[k * 8 + x, y] = rows[y] + (255,)
                elif y and x and bits[y - 1] & (0x80 >> (x - 1)) and px[k * 8 + x, y][3] == 0:
                    px[k * 8 + x, y] = SHADOW + (255,)
        # the shadow of the last column and row
        for y in range(16):
            if bits[y] & 1 and px[k * 8 + 8, y + 1][3] == 0:
                px[k * 8 + 8, y + 1] = SHADOW + (255,)
    return img


def small_text(text, colour=SMALL):
    """text in the font's thin 5x7 letters, 6 pixels a letter, a shadow"""
    img = Image.new('RGBA', (len(text) * 6 + 1, 8), (0, 0, 0, 0))
    px = img.load()
    for k, ch in enumerate(text):
        for y, v in enumerate(glyph_rows(ch)):
            for x in range(5):
                if v & (0x10 >> x):
                    px[k * 6 + x, y] = colour + (255,)
                    if px[k * 6 + x + 1, y + 1][3] == 0:
                        px[k * 6 + x + 1, y + 1] = (16, 10, 6, 255)
    return img


def tile_img(t):
    img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(16):
            if t[y][x] is not None:
                img.putpixel((x, y), tuple(t[y][x]) + (255,))
    return img


EMERALDS = [tile_img(mkgfx.draw_emerald(f)) for f in range(8)]
COVERS = [tile_img(mkgfx.draw_cover(f)).convert('RGB') for f in range(8)]


def cover_sheet(f):
    """the whole picture covered, as a cave is before it opens (the steel
    moving up, eight pictures a turn)"""
    img = Image.new('RGB', (W, H))
    c = COVERS[(f // 3) % 8]
    for y in range(0, H, 16):
        for x in range(0, W, 16):
            img.paste(c, (x, y))
    return img


def ease_out(q):
    return 1 - (1 - q) ** 3


def ease_back(q):
    s = 1.7
    q -= 1
    return 1 + q * q * ((s + 1) * q + s)


def bounce(q):
    if q < 1 / 2.75:
        return 7.5625 * q * q
    if q < 2 / 2.75:
        q -= 1.5 / 2.75
        return 7.5625 * q * q + 0.75
    if q < 2.5 / 2.75:
        q -= 2.25 / 2.75
        return 7.5625 * q * q + 0.9375
    q -= 2.625 / 2.75
    return 7.5625 * q * q + 0.984375


def clamp01(v):
    return max(0.0, min(1.0, v))


# ---- sparks -------------------------------------------------------------------

class Sparks:
    """little four-pointed stars that flash up, drift and go out"""

    def __init__(self, seed):
        self.rnd = random.Random(seed)
        self.live = []

    def add(self, x, y, life=12, dx=0.0, dy=0.0, size=None):
        self.live.append([float(x), float(y), 0, life, dx, dy,
                          size if size is not None else self.rnd.choice((1, 1, 2))])

    def draw(self, img):
        d = img.load()
        keep = []
        for s in self.live:
            x, y, age, life, dx, dy, size = s
            q = age / life
            arm = size if q < 0.6 else max(0, size - 1)
            cx, cy = int(x), int(y)
            core = WHITE if q < 0.5 else PALE
            pts = [(cx, cy, core)]
            for i in range(1, arm + 1):
                c = PALE if i == 1 else ORANGE
                pts += [(cx + i, cy, c), (cx - i, cy, c), (cx, cy + i, c), (cx, cy - i, c)]
            if q < 0.3 and size > 1:
                pts += [(cx + 1, cy + 1, PALE), (cx - 1, cy - 1, PALE), (cx + 1, cy - 1, PALE), (cx - 1, cy + 1, PALE)]
            for px, py, c in pts:
                if 0 <= px < img.width and 0 <= py < img.height:
                    d[px, py] = c if img.mode == 'RGB' else c + (255,)
            s[0] += dx
            s[1] += dy
            s[2] += 1
            if s[2] < life:
                keep.append(s)
        self.live = keep


# ---- captions -------------------------------------------------------------------

class Caption:
    """a panel with a big line and a small one; it opens, lights its
    letters one by one, a shine runs over them now and then, two emeralds
    spin at its ends, sparks twinkle round it; it closes at the end"""
    OPEN, CLOSE = 0.35, 0.3

    def __init__(self, big, small, seed, y=None, rows=None):
        self.text = big
        self.big = big_text(big, rows) if big else None
        self.n = len(big)
        self.small = small_text(small) if small else None
        tw = max(self.big.width if self.big else 0, self.small.width if self.small else 0)
        self.w = tw + 2 * 30
        self.h = 34 if self.small and self.big else 24
        self.x = (W - self.w) // 2
        self.y = H - self.h - 1 if y is None else y
        self.sparks = Sparks(seed)
        self.rnd = random.Random(seed + 1)
        bg = Image.new('RGBA', (self.w, self.h))
        d = ImageDraw.Draw(bg)
        for r in range(self.h):
            k = r / (self.h - 1)
            d.line((0, r, self.w, r), (int(30 - 18 * k), int(20 - 12 * k), int(12 - 6 * k), 228))
        for i, c in enumerate(SEP[:3]):           # the golden rules, as the status line's
            d.line((0, i, self.w, i), c + (255,))
            d.line((0, self.h - 3 + i, self.w, self.h - 3 + i), SEP[2 - i] + (255,))
        for cx, cy in ((0, 0), (self.w - 1, 0), (0, self.h - 1), (self.w - 1, self.h - 1)):
            bg.putpixel((cx, cy), (0, 0, 0, 0))   # the corners cut
        self.bg = bg

    def frame(self, t, dur):
        """the panel t seconds after it began (dur seconds on): RGBA and
        where, or None"""
        if t < 0 or t >= dur:
            return None
        f = int(t * FPS)
        img = self.bg.copy()
        tx = (self.w - (self.big.width if self.big else 0)) // 2
        ty = 4 if self.small else 4
        if self.big:
            lit = int((t - self.OPEN + 0.05) / 0.035)
            if lit > 0:
                letters = self.big.crop((0, 0, min(self.big.width, lit * 8 + 1), self.big.height))
                img.alpha_composite(letters, (tx, ty))
                # the letter just lit flashes white
                k = min(lit, self.n) - 1
                if lit <= self.n:
                    m = self.big.crop((k * 8, 0, k * 8 + 8, 16)).getchannel('A')
                    img.paste(WHITE + (255,), (tx + k * 8, ty), m)
                    self.sparks.add(tx + k * 8 + 4, ty + self.rnd.randrange(16), life=10,
                                    dy=-0.15, size=1)
                # a shine across the letters every 2.6 s
                done = self.OPEN + self.n * 0.035
                s = (t - done - 0.3) % 2.6
                if t > done + 0.3 and s < 0.7:
                    pos = s / 0.7 * (self.big.width + 30) - 15
                    band = Image.new('L', self.big.size, 0)
                    ImageDraw.Draw(band).polygon([(pos, 0), (pos + 5, 0), (pos - 3, 16), (pos - 8, 16)], 200)
                    m = ImageChops.multiply(band, self.big.getchannel('A'))
                    img.paste(WHITE + (255,), (tx, ty), m)
        if self.small:
            a = clamp01((t - self.OPEN - self.n * 0.035 - 0.1) / 0.35)
            if a > 0:
                s = self.small.copy()
                s.putalpha(s.getchannel('A').point(lambda v: int(v * a)))
                img.alpha_composite(s, ((self.w - s.width) // 2, 23 if self.big else 8))
        # the emeralds, spinning, and sparks round the panel
        em = EMERALDS[(f // 4) % 8]
        ey = (self.h - 16) // 2
        img.alpha_composite(em, (7, ey))
        img.alpha_composite(EMERALDS[(f // 4 + 4) % 8], (self.w - 23, ey))
        if f % 7 == 0:
            side = self.rnd.choice((0, 1))
            self.sparks.add((7 if side == 0 else self.w - 23) + self.rnd.randrange(16),
                            ey + self.rnd.randrange(16), life=14, size=self.rnd.choice((1, 2)))
        self.sparks.draw(img)
        # opening: from the middle outwards, a little too far and back
        if t < self.OPEN:
            q = ease_back(t / self.OPEN)
            w = max(2, int(self.w * min(q, 1.15)))
            w = min(w, self.w)
            cut = Image.new('RGBA', img.size, (0, 0, 0, 0))
            l = (self.w - w) // 2
            cut.paste(img.crop((l, 0, l + w, self.h)), (l, 0))
            img = cut
            if t < self.OPEN * 0.5:
                h = max(3, int(self.h * t / (self.OPEN * 0.5)))
                img = img.crop((0, (self.h - h) // 2, self.w, (self.h - h) // 2 + h))
                return img, (self.x, self.y + (self.h - h) // 2)
        # closing: flattened to a golden line, which goes out
        left = dur - t
        if left < self.CLOSE:
            q = left / self.CLOSE
            h = max(1, int(self.h * q * q))
            img = img.resize((self.w, h), Image.NEAREST)
            if h <= 3:
                img = Image.new('RGBA', (int(self.w * q * 2), 1), PALE + (255,))
                return img, ((W - img.width) // 2, self.y + self.h // 2)
            return img, (self.x, self.y + (self.h - h) // 2)
        return img, (self.x, self.y)


def put(frame, layer):
    if layer:
        img, at = layer
        frame.paste(img, at, img)


# ---- the wipes -------------------------------------------------------------------

def rimmed(a, b, m, sparks, p):
    """b where the mask m is set, a elsewhere; a golden rim on the edge
    and sparks flying from it"""
    out = a.copy()
    out.paste(b, (0, 0), m)
    if 0 < p < 1:
        outer = ImageChops.subtract(m.filter(ImageFilter.MaxFilter(5)), m)
        inner = ImageChops.subtract(m.filter(ImageFilter.MaxFilter(3)), m)
        out.paste(EMBER, (0, 0), outer)
        out.paste(PALE, (0, 0), inner)
        data = inner.tobytes()
        edge = [i for i in range(0, len(data), 7) if data[i]]
        for _ in range(min(6, len(edge))):
            i = sparks.rnd.choice(edge)
            sparks.add(i % W, i // W, life=sparks.rnd.randrange(8, 18),
                       dx=sparks.rnd.uniform(-0.6, 0.6), dy=sparks.rnd.uniform(-0.9, 0.2))
    sparks.draw(out)
    return out


def gem_mask(q):
    """an emerald's outline, q (0..1) of the way to filling the picture"""
    m = Image.new('L', (W, H), 0)
    s = ease_out(q) * 1.45 * max(W, H) / 2
    cx, cy = W / 2, H / 2 + s * 0.15
    ImageDraw.Draw(m).polygon([(cx - 0.55 * s, cy - 0.75 * s), (cx + 0.55 * s, cy - 0.75 * s),
                               (cx + s, cy - 0.3 * s), (cx, cy + 0.9 * s), (cx - s, cy - 0.3 * s)], 255)
    return m


class Wipe:
    def __init__(self, kind, seed):
        self.kind = kind
        self.sparks = Sparks(seed)
        rnd = random.Random(seed)
        self.order = {}
        cells = [(x, y) for y in range(0, H, 16) for x in range(0, W, 16)]
        for c in cells:
            self.order[c] = rnd.random()
        self.cols = [rnd.random() for _ in range(W // 16)]

    def __call__(self, a, b, p, f):
        k = self.kind
        if k in ('gem', 'iris', 'clock', 'blinds'):
            m = Image.new('L', (W, H), 0)
            d = ImageDraw.Draw(m)
            if k == 'gem':
                m = gem_mask(p)
            elif k == 'iris':
                r = ease_out(p) * math.hypot(W, H) / 2 + 1
                d.ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), 255)
            elif k == 'clock':
                r = math.hypot(W, H)
                d.pieslice((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), -90, -90 + 360 * p, 255)
            else:   # bars of a tile's height, one after the other, from both sides
                for i, y in enumerate(range(0, H, 16)):
                    q = clamp01(p * 1.6 - i / (H / 16) * 0.6)
                    w = ease_out(q) * W
                    if w < 1:
                        continue
                    if i % 2:
                        d.rectangle((W - w, y, W, y + 15), 255)
                    else:
                        d.rectangle((0, y, w - 1, y + 15), 255)
            return rimmed(a, b, m, self.sparks, p)
        out = Image.new('RGB', (W, H))
        if k == 'tiles':        # each tile turns over, from the top left
            out.paste(a)
            for (x, y), r in self.order.items():
                q = clamp01((p - (x / W + y / H) * 0.3 - r * 0.08) / 0.3)
                if q <= 0:
                    continue
                out.paste((0, 0, 0), (x, y, x + 16, y + 16))
                if q >= 1:
                    out.paste(b.crop((x, y, x + 16, y + 16)), (x, y))
                    continue
                src, w = (a, 1 - 2 * q) if q < 0.5 else (b, 2 * q - 1)
                w = max(1, int(16 * w))
                t = src.crop((x, y, x + 16, y + 16)).resize((w, 16), Image.NEAREST)
                if 0.35 < q < 0.65 and max(t.convert('L').getextrema()) > 40:   # (not on black)
                    t = Image.blend(t, Image.new('RGB', t.size, PALE), 0.5)
                out.paste(t, (x + (16 - w) // 2, y))
                if 0.45 < q < 0.55 and self.sparks.rnd.random() < 0.15:
                    self.sparks.add(x + 8, y + 8, life=10)
            self.sparks.draw(out)
            return out
        if k == 'drop':         # the new picture's columns fall in, bouncing like boulders
            out.paste(a)
            for c in range(W // 16):
                q = clamp01((p - (c / (W / 16)) * 0.35 - self.cols[c] * 0.12) / 0.55)
                if q <= 0:
                    continue
                y = int(-H * (1 - bounce(q)))
                out.paste(b.crop((c * 16, 0, c * 16 + 16, H)), (c * 16, y))
                if y > -16 and q < 0.98:
                    out.paste(PALE, (c * 16, y + H - 1, c * 16 + 16, y + H))
                if 0.36 < q < 0.42:
                    for _ in range(2):
                        self.sparks.add(c * 16 + self.sparks.rnd.randrange(16), H - 3, life=12,
                                        dx=self.sparks.rnd.uniform(-0.5, 0.5), dy=-0.8)
            self.sparks.draw(out)
            return out
        if k == 'pixels':       # coarser and coarser, then the new one finer and finer
            q = p * 2 if p < 0.5 else 2 - p * 2
            s = max(1, int(2 ** (q * 4.2)))
            src = a if p < 0.5 else b
            small = src.resize((max(1, W // s), max(1, H // s)), Image.BOX)
            out = small.resize((W, H), Image.NEAREST)
            return Image.blend(out, Image.new('RGB', (W, H), PALE), 0.12 * math.sin(p * math.pi))
        if k == 'cover':        # the game's own: covered cell by cell, uncovered the same way
            cov = cover_sheet(f)
            out.paste(a)
            for (x, y), r in self.order.items():
                if p < 0.5 and r < p * 2 or p >= 0.5 and r >= (p - 0.5) * 2:
                    out.paste(cov.crop((x, y, x + 16, y + 16)), (x, y))
                elif p >= 0.5:
                    out.paste(b.crop((x, y, x + 16, y + 16)), (x, y))
            return out
        raise ValueError(k)


# ---- the recordings ----------------------------------------------------------------

def ffmpeg_cmd():
    """an ffmpeg that reads and writes H.264: this one, or the host's (a
    Flatpak sandbox's may have neither)"""
    try:
        dec = subprocess.run(['ffmpeg', '-hide_banner', '-decoders'], capture_output=True, text=True).stdout
        enc = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True).stdout
        if ' h264 ' in dec and ' libx264 ' in enc:
            return ['ffmpeg']
    except OSError:
        pass
    return ['flatpak-spawn', '--host', 'ffmpeg']


FF = ffmpeg_cmd()


def frames(path, start, n):
    """n pictures from second start on, at the machine's size"""
    p = subprocess.Popen(FF + ['-v', 'error', '-ss', '%.3f' % start, '-i', path, '-frames:v', str(n),
                               '-vf', 'scale=%d:%d:flags=area' % (W, H), '-f', 'rawvideo',
                               '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    size = W * H * 3
    last = None
    for _ in range(n):
        data = p.stdout.read(size)
        if len(data) == size:
            last = Image.frombytes('RGB', (W, H), data)
        if last is None:
            last = Image.new('RGB', (W, H))
        yield last            # (the recording's last picture held, should it end)
    p.stdout.close()
    p.wait()


def sound(path, start, secs):
    """stereo 16 bit, secs long from start (silence where there is none)"""
    want = int(round(secs * FPS)) * (RATE // FPS) * 2
    r = subprocess.run(FF + ['-v', 'error', '-ss', '%.3f' % start, '-t', '%.3f' % secs, '-i', path,
                             '-vn', '-f', 's16le', '-ac', '2', '-ar', str(RATE), '-'],
                       stdout=subprocess.PIPE, check=True)
    a = array.array('h', r.stdout[:want * 2])
    a.extend([0] * (want - len(a)))
    return a


def music_start(path):
    """the second the title music begins in the title's recording"""
    a = sound(path, 0, 20)
    for i in range(0, len(a), 2):
        if abs(a[i]) > 400 or abs(a[i + 1]) > 400:
            return max(0.0, i / 2 / RATE - 0.05)
    return 0.0


# ---- the parts -----------------------------------------------------------------------

class Part:
    def __init__(self, i, spec, rec, t0):
        self.i, self.spec = i, spec
        self.pieces = []        # (path, from, seconds, speed)
        for name, a, secs, *speed in spec.get('pieces', []):
            self.pieces.append((rec[name], a, secs, speed[0] if speed else 1))
        self.secs = spec['secs'] if 'secs' in spec else sum(s / sp for _, _, s, sp in self.pieces)
        self.n = int(round(self.secs * FPS))
        last = i == len(PARTS) - 1
        self.caps = []
        for k, (big, small, a, b) in enumerate(spec.get('caps', [])):
            a = (X + 0.15 if i else 0.4) if a is None else a
            b = (self.secs - (0 if last else X) - 0.1) if b is None else b
            self.caps.append((Caption(big, small, 100 * i + k), a, b))
        self.intro = [(Caption(big, small, 50 + k, y=(H - 32) // 2), a, b)
                      for k, ((big, small), a, b) in enumerate(INTRO)] if spec.get('intro') else []
        self.sparks = Sparks(900 + i)
        if spec.get('credits'):
            self.credit_lines = []
            for k, (what, who) in enumerate(CREDITS):
                dots = 34 - len(what) - len(who)
                ramp = RANKS[min(k, 3)]
                rows = [mkgfx.ramp(ramp, max(0, r - 1) / 13) for r in range(16)]
                self.credit_lines.append(big_text(what + ' ' + '.' * (dots - 2) + ' ' + who, rows))
            self.order = random.Random(7).sample([(x, y) for y in range(0, H, 16) for x in range(0, W, 16)],
                                                 (W // 16) * (H // 16))

    def pictures(self):
        if self.spec.get('credits'):
            for f in range(self.n):
                yield None
            return
        for path, a, secs, speed in self.pieces:
            n = int(round(secs * FPS))
            for img in frames(path, a, n):
                for _ in range(int(round(1 / speed))):
                    yield img

    def game_sound(self):
        n = self.n * (RATE // FPS) * 2
        if self.spec.get('mute') or self.spec.get('credits'):
            return array.array('h', [0]) * n
        out = array.array('h')
        for path, a, secs, speed in self.pieces:
            if speed == 1:
                out.extend(sound(path, a, secs))
            else:
                out.extend(array.array('h', [0]) * (int(round(secs / speed * FPS)) * (RATE // FPS) * 2))
        out.extend([0] * (n - len(out)))
        return out[:n]

    def compose(self, k, img):
        """picture k of the part, with what is laid over it"""
        t = k / FPS
        if self.spec.get('credits'):
            return self.credits(k)
        img = img.copy()
        if self.spec.get('intro'):
            img = self.covered(img, k)
        rp = self.spec.get('replay')
        if rp and rp[0] + 0.1 <= t < rp[1] - 0.1 and (t - rp[0]) % 1.0 < 0.7:
            img.paste(big_text('REPLAY', [mkgfx.ramp(RANKS[0], r / 15) for r in range(16)]), (40, 22),
                      big_text('REPLAY'))
            ImageDraw.Draw(img).ellipse((28, 26, 35, 33), hexc('e02020'))
        for cap, a, b in self.caps:
            put(img, cap.frame(t - a, b - a))
        return img

    def covered(self, img, k):
        """the intro: the cover, lines on it, then the cell by cell uncovering"""
        t = k / FPS
        a, b = UNCOVER
        if t >= b + 0.3:
            return img
        cov = cover_sheet(k)
        if t < a:
            out = cov
        else:
            out = img.copy()
            q = (t - a) / (b - a)
            for idx, (x, y) in enumerate(self.uncover_order()):
                r = idx / len(self.uncover_order())
                if r >= q:
                    out.paste(cov.crop((x, y, x + 16, y + 16)), (x, y))
                elif r >= q - 0.03:
                    out.paste(Image.blend(img.crop((x, y, x + 16, y + 16)),
                                          Image.new('RGB', (16, 16), PALE), 0.6), (x, y))
                    if self.sparks.rnd.random() < 0.25:
                        self.sparks.add(x + 8, y + 8, life=12, size=2)
        self.sparks.draw(out)
        for cap, ca, cb in self.intro:
            put(out, cap.frame(t - ca, cb - ca))
        return out

    def uncover_order(self):
        if not hasattr(self, '_order'):
            self._order = random.Random(1).sample([(x, y) for y in range(0, H, 16) for x in range(0, W, 16)],
                                                  (W // 16) * (H // 16))
        return self._order

    def credits(self, k):
        """the credits on the cover, line by line, in the high score table's colours"""
        t = k / FPS
        img = cover_sheet(k)
        img = Image.blend(img, Image.new('RGB', (W, H)), 0.55)
        n = len(self.credit_lines)
        pw, ph = 34 * 8 + 24, 24 + (n + 2) * 20 + 8
        px, py = (W - pw) // 2, (H - ph) // 2
        # the panel grows in
        q = ease_back(clamp01((t - X) / 0.5))
        if q > 0:
            w, h = max(2, int(pw * min(q, 1.08))), max(2, int(ph * min(q, 1.08)))
            d = ImageDraw.Draw(img)
            x0, y0 = (W - w) // 2, (H - h) // 2
            for r in range(h):
                c = int(18 - 10 * r / h)
                d.line((x0, y0 + r, x0 + w - 1, y0 + r), (c + 6, c, c // 2))
            for i, c in enumerate(SEP[:3]):
                d.line((x0, y0 + i, x0 + w - 1, y0 + i), c)
                d.line((x0, y0 + h - 3 + i, x0 + w - 1, y0 + h - 3 + i), SEP[2 - i])
        if t > X + 0.5:
            # the heading in the big letters' green, its shine going round
            sh = int(t * 12)
            rows = [mkgfx.ramp(GREEN + [GREEN[0]], ((r // 2 + sh) % 8) / 8) for r in range(16)]
            head = big_text('CREDITS', rows)
            img.paste(head, ((W - head.width) // 2, py + 8), head)
            for e, at in ((EMERALDS[(k // 4) % 8], (W - head.width) // 2 - 22),
                          (EMERALDS[(k // 4 + 4) % 8], (W + head.width) // 2 + 6)):
                img.paste(e, (at, py + 8), e)
        for j, line in enumerate(self.credit_lines):
            ta = X + 1.0 + j * 0.55
            if t < ta:
                continue
            y = py + 32 + j * 20
            lit = int((t - ta) / 0.02) + 1
            part = line.crop((0, 0, min(line.width, lit * 8 + 1), line.height))
            img.paste(part, (px + 12, y), part)
            if lit <= 34:
                self.sparks.add(px + 12 + lit * 8, y + 8, life=10, size=1)
        tend = X + 1.0 + n * 0.55 + 0.6
        if t > tend:
            sh = int(t * 12)
            rows = [mkgfx.ramp(GREEN + [GREEN[0]], ((r // 2 + sh) % 8) / 8) for r in range(16)]
            end = big_text(CREDITS_END, rows)
            a = clamp01((t - tend) / 0.4)
            m = end.getchannel('A').point(lambda v: int(v * a))
            img.paste(end, ((W - end.width) // 2, py + 32 + n * 20 + 4), m)
            if k % 5 == 0:
                self.sparks.add(self.sparks.rnd.randrange(px, px + pw), py + self.sparks.rnd.randrange(ph),
                                life=16, size=2)
        self.sparks.draw(img)
        return img


# ---- putting it together ------------------------------------------------------------

def thumbnails(work, rec):
    for name, what, at, (big, small, *_) in THUMBS:
        img = next(frames(rec[what], at, 1))
        cap = Caption(big, small, 1)
        put(img, cap.frame(cap.OPEN + cap.n * 0.035 + 1.84, 100.0))  # all lit, no shine
        h = 720
        pic = img.resize((W * Z, H * Z), Image.NEAREST).resize((h * W // H, h), Image.LANCZOS)
        out = Image.new('RGB', (h * 16 // 9, h))
        out.paste(pic, ((out.width - pic.width) // 2, 0))
        path = os.path.join(work, 'smaragd-dash-%s-thumbnail%s.png' % (VERSION, name))
        out.save(path)
        print(path)


def main():
    work = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-')
                           else os.path.join(HERE, 'build', 'trailer'))
    rec = {n: os.path.join(work, n + '.mp4') for n in ('title', 'caves', 'tour', 'editor', 'help', 'music')}
    if not os.path.exists(rec['music']):    # (the title's recording, long enough for the music)
        rec['music'] = rec['title']
    if '--thumbs' in sys.argv:
        thumbnails(work, rec)
        return
    out_path = os.path.join(work, 'smaragd-dash-%s-trailer.mp4' % VERSION)
    t0 = music_start(rec['music'])
    print('title music from %.2f s' % t0)
    parts = [Part(i, s, rec, t0) for i, s in enumerate(PARTS)]
    skip = 0.0
    if '--part' in sys.argv:
        k = int(sys.argv[sys.argv.index('--part') + 1])
        skip = sum(p.secs - X for p in parts[:max(0, k - 1)])
        parts = parts[max(0, k - 1):k + 2]
        out_path = out_path.replace('.mp4', '-part%d.mp4' % k)
    xf = int(X * FPS)
    starts, t = [], 0.0
    for p in parts:
        starts.append(t)
        t += p.secs - X
    total = t + X
    music_at = t0 + skip        # (--part: where the music is there)
    for p, s in zip(parts, starts):
        for cap, a, b in p.caps:
            print('  part %2d at %6.1f s: %-34s %4.1f s on' % (p.i, s + a, cap.text, b - a))

    # the game's sounds, the parts' cross-faded into one another
    spf = RATE // FPS * 2
    game = array.array('h')
    for i, p in enumerate(parts):
        snd = p.game_sound()
        if i == 0:
            game.extend(snd)
            continue
        o = xf * spf
        tail = game[len(game) - o:]
        del game[len(game) - o:]
        game.extend(array.array('h', (int(x * (1 - k / o) + y * k / o)
                                      for k, (x, y) in enumerate(zip(tail, snd[:o])))))
        game.extend(snd[o:])
    gw = os.path.join(work, 'game.raw')
    with open(gw, 'wb') as f:
        f.write(game.tobytes())

    # the pictures, at the machine's size, into body.mkv
    body = os.path.join(work, 'body.mkv')
    enc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                            '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-', '-c:v', 'ffv1', body],
                           stdin=subprocess.PIPE)
    written = 0
    cur = parts[0].pictures()
    for i, p in enumerate(parts):
        first = xf if i else 0
        end = p.n - xf if i < len(parts) - 1 else p.n
        for k in range(first, end):
            enc.stdin.write(p.compose(k, next(cur)).tobytes())
            written += 1
        if i < len(parts) - 1:
            q = parts[i + 1]
            nxt = q.pictures()
            wipe = Wipe('cover' if q.spec.get('credits') else WIPES[(q.i - 1) % len(WIPES)], q.i)
            for k in range(xf):
                a = p.compose(end + k, next(cur))
                b = q.compose(k, next(nxt))
                enc.stdin.write(wipe(a, b, (k + 1) / (xf + 1), k).tobytes())
                written += 1
            cur = nxt
        print('  part %2d done' % p.i)
    enc.stdin.close()
    if enc.wait():
        raise RuntimeError('ffmpeg: the body')

    # the music: one track from the title's recording, from its first note
    # on; full alone, lower under the game's sounds, a wipe's time between
    lv = []
    for p, s in zip(parts, starts):
        quiet = p.spec.get('mute') or p.spec.get('credits')
        lv.append((s, 1.0 if quiet else BED))
    vol = '%.2f' % lv[0][1]
    for (ta, va), (tb, vb) in zip(lv, lv[1:]):
        if va != vb:
            vol = '(%s)+(%.2f)*clip((t-%.2f)/%.2f,0,1)' % (vol, vb - va, tb, X)
    m0 = music_at
    fc = ('[0:v]scale=%d:%d:flags=neighbor,fade=t=in:d=0.5,fade=t=out:st=%.2f:d=2.0,format=yuv420p[v];'
          % (W * Z, H * Z, total - 2.0) +
          '[1:a]volume=%s[g];' % GAME +
          "[2:a]atrim=start=%.3f,asetpts=PTS-STARTPTS,volume='%s':eval=frame[m];" % (m0, vol) +
          '[m][g]amix=inputs=2:normalize=0:duration=first,atrim=duration=%.3f,' % total +
          'afade=t=in:d=0.2,afade=t=out:st=%.2f:d=2.5[a]' % (total - 2.5))
    subprocess.run(FF + ['-v', 'error', '-y', '-i', body,
                         '-f', 's16le', '-ar', str(RATE), '-ac', '2', '-i', gw,
                         '-i', rec['music'], '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
                         '-t', '%.3f' % total, '-c:v', 'libx264', '-preset', 'slow', '-crf', '16',
                         '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out_path], check=True)
    print('%s: %.1f s (%d pictures)' % (out_path, total, written))


if __name__ == '__main__':
    main()
