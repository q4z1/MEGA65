#!/usr/bin/env python3
"""Smaragd Dash: the help pages, from help.txt (see the comment at its top)
into SMARAGD.HELP.

Usage: mkhelp.py <help.txt> <help.bin>

help.bin: two bytes of load address (not used), the number of pages, then
each page: its title in TITLE bytes and LINES lines of 1 + TEXT bytes, each
GDash's element whose tile goes before the line (NONE: none) and its text,
padded with 0 (main.c's help_pages shows them).
"""

import re
import sys

import cavekit as ck

TITLE, LINES, TEXT, NONE = 20, 10, 38, 0xFF  # main.c's HELP_*
NAME_W, WHAT_W = 11, 22  # an element's name (and a space) and what it does: to column 37
FONT = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ /:.!-,x+*^><_"  # mkgfx.py's font


def main():
    src, out = sys.argv[1], sys.argv[2]
    pages = []  # [title, [(element, text)]]

    def fail(n, msg):
        sys.exit(f"{src}:{n}: {msg}")

    for n, line in enumerate(open(src, encoding="utf-8"), 1):
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("="):
            title = line[1:].strip()
            if not title or len(title) > TITLE:
                fail(n, f"a title of 1 to {TITLE} characters")
            pages.append([title, []])
            continue
        if not pages:
            fail(n, "a page (= TITLE) first")
        if line.startswith("-"):
            elem, text = NONE, line[2:]
            if len(text) > TEXT:
                fail(n, f"a line of up to {TEXT} characters")
        else:
            fields = re.split(r"\s{2,}", line.strip())
            if len(fields) != 3:
                fail(n, "an element, a name and what it does, two spaces apart")
            if fields[0] not in ck.O:
                fail(n, f"no element {fields[0]}")
            if len(fields[1]) >= NAME_W or len(fields[2]) > WHAT_W:
                fail(n, f"a name of up to {NAME_W - 1} characters, what it does in up to {WHAT_W}")
            elem, text = ck.O[fields[0]], fields[1].ljust(NAME_W) + fields[2]
        if any(c not in FONT for c in text):
            fail(n, "a character the font has not")
        if len(pages[-1][1]) == LINES:  # on to a page of the same title
            pages.append([pages[-1][0], []])
        pages[-1][1].append((elem, text))
    if len(pages) > 255:
        sys.exit(f"{src}: more than 255 pages")
    data = bytearray([0x00, 0x20, len(pages)])
    for title, lines in pages:
        data += title.encode("ascii").ljust(TITLE, b"\0")
        for elem, text in lines + [(NONE, "")] * (LINES - len(lines)):
            data += bytes([elem]) + text.encode("ascii").ljust(TEXT, b"\0")
    with open(out, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
