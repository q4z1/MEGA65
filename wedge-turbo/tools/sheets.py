#!/usr/bin/env python3
"""Every picture of the game out into one folder, and back in by file name.

    tools/sheets.py export DIR
    tools/sheets.py import DIR [--dry-run]

The folder then holds, as the game has them now:

    cars-player.png      the player's car: its 63 images (17 sizes, the
                         angles each size has), side by side in rows
    cars-opponent.png    the opponents' car the same way, in its first
                         colouring (the race paints it five other ways)
    car-near.png         the player's car near, twice as fine (the
                         hardware sprites): angles 0-8
    scenery-NN.png       scenery type NN (hex): its 17 sizes and more
    hud.png              messages, countdown, places
    backdrop-N.png       the backdrop behind course theme N, 960 x 32, in
                         the colours of the theme's first course
    page-NAME.png        the pages around the race, 640 x 400 (the title's
    page-title-K.png     six frames, its headlights rising)

Each sheet's images keep their places and sizes; between them and around
them it is transparent. A sheet's colours are the race's: an edited sheet
may use only the colours its images use and the race view's 0-7, exactly
(sheets.json in the folder lists them per sheet). The pages are free in
their colours; the build fits them into characters and palette banks and
says when a page has too many.

Import looks at the folder's PNG files by name and takes only what changed
and is valid, with the reason when it is not; a name that is no picture of
the game is left alone. What it takes goes to art/hand/<name>.png - or, for
a picture made from the game's data, to
local/hand/, which is never in the repository. The build then takes it
instead of what it makes (tools/hand.py); delete the file to have the
picture made again. Run ./build.sh afterwards. --dry-run only reports what
would happen.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hand  # noqa: E402

TOOLS = os.path.dirname(os.path.abspath(__file__))


def export(out):
    """The game's pictures into out (with sheets.json), as the build makes them"""
    os.makedirs(out, exist_ok=True)
    meta = os.path.join(out, hand.META)
    if os.path.exists(meta):
        os.remove(meta)
    env = dict(os.environ, WEDGE_EXPORT=os.path.abspath(out))
    with tempfile.TemporaryDirectory() as gen:
        for cmd in (['mksprites.py', gen], ['mkpages.py', gen]):
            r = subprocess.run([sys.executable, os.path.join(TOOLS, cmd[0])] + cmd[1:], env=env,
                               stdout=subprocess.DEVNULL)
            if r.returncode:
                sys.exit(f'{cmd[0]} failed')
    return json.load(open(meta))


def plain(img):
    """A picture to compare: RGBA, transparent all alike"""
    b = img.convert('RGBA').tobytes()
    return [b[i:i + 4] if b[i + 3] >= 128 else b'\0\0\0\0' for i in range(0, len(b), 4)]


def check(name, meta, img):
    """What is wrong with an edited picture (empty: nothing)"""
    if meta['kind'] == 'picture':
        size = tuple(meta['size'])
        return [] if img.size == size else [f'{img.size[0]}x{img.size[1]} instead of {size[0]}x{size[1]}']
    palette = {int(v): c for v, c in meta['palette'].items()}
    ims = [(w, h, bytes(w * h)) for w, h in meta['dims']]
    new, problems = hand.read_sheet(img, ims, palette, meta['allowed'], meta['clear'])
    return problems if new is None else []


def import_(folder, dry_run):
    with tempfile.TemporaryDirectory() as now:
        metas = export(now)
        taken = 0
        for f in sorted(os.listdir(folder)):
            name, ext = os.path.splitext(f)
            if ext.lower() != '.png':
                continue
            if name not in metas:
                print(f'{f}: no picture of the game, left alone')
                continue
            meta = metas[name]
            img = Image.open(os.path.join(folder, f))
            if img.size == Image.open(os.path.join(now, f)).size and \
                    plain(img) == plain(Image.open(os.path.join(now, f))):
                continue
            problems = check(name, meta, img)
            if problems:
                print(f'{f}: refused - ' + '; '.join(problems))
                continue
            dest = os.path.join(hand.LOCAL if meta['from_game'] else hand.HAND, f)
            print(f'{f}: {"would go" if dry_run else "goes"} to {os.path.relpath(dest, hand.ROOT)}'
                  + (' (from the game\'s data: not for the repository)' if meta['from_game'] else ''))
            if not dry_run:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if meta['kind'] == 'picture':
                    img.convert('RGB').save(dest)
                else:
                    img.convert('RGBA').save(dest)
            taken += 1
        print(f'{taken} picture(s) {"to take" if dry_run else "taken"}' + ('' if dry_run or not taken else
                                                                          ' - now ./build.sh'))


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('export')
    e.add_argument('dir')
    i = sub.add_parser('import')
    i.add_argument('dir')
    i.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    if a.cmd == 'export':
        metas = export(a.dir)
        edited = [n for n, m in metas.items() if m['edited']]
        print(f'{len(metas)} pictures in {a.dir}' + (f', edited by hand: {", ".join(sorted(edited))}' if edited else ''))
    else:
        import_(a.dir, a.dry_run)


if __name__ == '__main__':
    main()
