"""Pictures touched up by hand: where the build makes a picture of the game,
it asks here first whether there is one edited by hand to take instead -
and, exporting (WEDGE_EXPORT set to a folder), writes what it takes there as
a PNG, with what an edited one must keep to (tools/sheets.py).

Two kinds of picture:

  - indexed (the race's sprites, the backdrops, the car near): pixels that
    are colour numbers of the race's palette. Several images of a bank are
    one sheet: side by side in rows, each at the bottom of its row, CLEAR
    (or the bank's clear number) transparent. An edited sheet keeps the
    images' places and sizes, and its colours must be those of the palette
    the bank may use (its own and the race view's 0-7), exactly;
  - pictures (the pages around the race): RGB, 640 x 400; the build turns
    them into characters and palette banks as before.

The edited pictures live in art/hand/<name>.png - or, for a picture made
from the game's data, in local/hand/ (never in the repository).
"""
import json
import os
import sys

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
HAND = os.path.join(ROOT, 'art', 'hand')
LOCAL = os.path.join(ROOT, 'local', 'hand')
CLEAR = 0xFF
GAP = 2           # between a sheet's images
SHEET_W = 1024    # a sheet's rows at most this wide (an image wider has a row of its own)
META = 'sheets.json'


def export_dir():
    return os.environ.get('WEDGE_EXPORT')


def rgb(c):
    """A 12-bit colour as 8-bit RGB"""
    return ((c >> 8 & 15) * 17, (c >> 4 & 15) * 17, (c & 15) * 17)


def edited(name, from_game):
    """The file of name's edited picture, if there is one"""
    path = os.path.join(LOCAL if from_game else HAND, name + '.png')
    return path if os.path.exists(path) else None


def layout(dims):
    """Where a sheet's images go: per image (x, y) of its top left, and the
    sheet's size"""
    rows, row, x = [], [], 0
    for k, (w, h) in enumerate(dims):
        if row and x + w > SHEET_W:
            rows.append(row)
            row, x = [], 0
        row.append(k)
        x += w + GAP
    if row:
        rows.append(row)
    places, y, width = [None] * len(dims), 0, 1
    for row in rows:
        rh = max(dims[k][1] for k in row)
        x = 0
        for k in row:
            w, h = dims[k]
            places[k] = (x, y + rh - h)
            x += w + GAP
        width = max(width, x - GAP)
        y += rh + GAP
    return places, (width, max(1, y - GAP))


def _record(name, meta):
    out = export_dir()
    path = os.path.join(out, META)
    data = json.load(open(path)) if os.path.exists(path) else {}
    data[name] = meta
    with open(path, 'w') as f:
        json.dump(data, f, indent=1, sort_keys=True)


def sheet_image(ims, palette, clear=CLEAR):
    """ims (w, h, colour numbers) as one RGBA sheet"""
    places, size = layout([(w, h) for w, h, _ in ims])
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    px = img.load()
    for (w, h, data), (x0, y0) in zip(ims, places):
        for y in range(h):
            for x in range(w):
                v = data[y * w + x]
                if v != clear:
                    px[x0 + x, y0 + y] = rgb(palette[v]) + (255,)
    return img


def read_sheet(img, ims, palette, allowed, clear=CLEAR):
    """An edited sheet back as images (in ims' sizes): each pixel the
    colour number of its colour - the one the image had there if that has
    it, else the first allowed one; transparent is clear. Returns (images,
    problems)"""
    places, size = layout([(w, h) for w, h, _ in ims])
    if img.size != size:
        return None, [f'{img.size[0]}x{img.size[1]} instead of {size[0]}x{size[1]}']
    img = img.convert('RGBA')
    px = img.load()
    of_colour = {}
    for v in allowed:
        of_colour.setdefault(rgb(palette[v]), []).append(v)
    out, wrong = [], {}
    for (w, h, data), (x0, y0) in zip(ims, places):
        new = bytearray(w * h)
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x0 + x, y0 + y]
                if a < 128:
                    new[y * w + x] = clear
                    continue
                vs = of_colour.get((r, g, b))
                if not vs:
                    wrong.setdefault((r, g, b), (x0 + x, y0 + y))
                    continue
                old = data[y * w + x]
                new[y * w + x] = old if old in vs else vs[0]
        out.append((w, h, bytes(new)))
    problems = [f'colour #{r:02X}{g:02X}{b:02X} (first at {x},{y}) is not one of its palette'
                for (r, g, b), (x, y) in list(wrong.items())[:8]]
    if len(wrong) > 8:
        problems.append(f'and {len(wrong) - 8} more colours')
    return (None if wrong else out), problems


def sheet(name, ims, palette, from_game=False, clear=CLEAR, allowed=None):
    """A bank's images (w, h, colour numbers), or the edited ones instead.
    palette: colour number -> 12-bit colour (all the bank uses); allowed:
    the numbers an edit may use (default: those the images use and the race
    view's 0-7)"""
    ims = [(w, h, bytes(px)) for w, h, px in ims]
    if allowed is None:
        used = {v for _, _, px in ims for v in px} - {clear}
        allowed = sorted(used) + [v for v in range(8) if v not in used and v in palette]
    allowed = [v for v in allowed if v in palette]
    path = edited(name, from_game)
    if path:
        new, problems = read_sheet(Image.open(path), ims, palette, allowed, clear)
        if new is None:
            sys.exit(f'{os.path.relpath(path, ROOT)}: ' + '; '.join(problems))
        ims = new
    if export_dir():
        sheet_image(ims, palette, clear).save(os.path.join(export_dir(), name + '.png'))
        _record(name, {'kind': 'sheet', 'from_game': from_game, 'clear': clear,
                       'dims': [[w, h] for w, h, _ in ims], 'allowed': allowed,
                       'palette': {str(v): palette[v] for v in allowed},
                       'edited': bool(path)})
    return ims


def picture(name, img, from_game=False):
    """A page's picture (RGB), or the edited one instead"""
    path = edited(name, from_game)
    if path:
        new = Image.open(path).convert('RGB')
        if new.size != img.size:
            sys.exit(f'{os.path.relpath(path, ROOT)}: {new.size[0]}x{new.size[1]} instead of '
                     f'{img.size[0]}x{img.size[1]}')
        img = new
    if export_dir():
        img.convert('RGB').save(os.path.join(export_dir(), name + '.png'))
        _record(name, {'kind': 'picture', 'from_game': from_game, 'size': list(img.size), 'edited': bool(path)})
    return img
