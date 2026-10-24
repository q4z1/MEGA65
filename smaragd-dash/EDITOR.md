# The Smaragd Dash cave editor

Smaragd Dash has a cave editor built in. With it you draw your own caves on
the MEGA65, try them out at once and keep them on the game's disk, in twenty
slots. From the title screen you play them like the game's own caves.

**[Video: the editor in 1½ minutes](screenshots/cave-editor.mp4)**: it shows
everything this guide describes, from loading a cave to playing the changed
one.

Contents:

- [Your first cave, step by step](#your-first-cave-step-by-step)
- [The editor's screen](#the-editors-screen)
- [Moving, putting, drawing](#moving-putting-drawing)
- [The elements](#the-elements)
- [All elements: the page of their own](#all-elements-the-page-of-their-own)
- [Slots: loading, new caves, emptying](#slots-loading-new-caves-emptying)
- [Name and values](#name-and-values)
- [Trying a cave](#trying-a-cave)
- [Saving](#saving)
- [Playing your caves](#playing-your-caves)
- [The rules of the own caves](#the-rules-of-the-own-caves)
- [Caves on the PC: GDash and cavekit.py](#caves-on-the-pc-gdash-and-cavekitpy)
- [Messages](#messages)
- [All keys](#all-keys)

## Your first cave, step by step

This walk-through changes a cave that is already in slot 1. It is the same
walk as in the video. With an empty slot you start from a fresh cave
instead (see [Slots](#slots-loading-new-caves-emptying)).

**1. Open the editor.** Press **E** on the title screen. The editor loads
from the disk and shows the cave in slot 1, with the cursor (a light frame)
on cell 2,2.

![The editor with the cave of slot 1](screenshots/editor-cave.png)

**2. Choose an element and put it.** Press **6** for emeralds; the status
line now says EMERALD. Move the cursor with the cursor keys or the joystick
and press **fire**, **Space** or **Return** to put an emerald under the
cursor. In the video three emeralds go right of the inbox. Then **X** for
an exit, three cells further on, and **5** for two boulders above the
emeralds. All the other elements (slime, nuts, clocks, keys and doors, ...)
are on a page of their own: **E** (see
[All elements](#all-elements-the-page-of-their-own)). In the video the clock
is taken there, then the emeralds are chosen with 6.

**3. Draw a wall.** Press **3** for brick wall. Hold fire and move: every
cell the cursor passes gets a wall. A `*` after the slot number in the
status line means the cave has changes that are not saved yet.

![Emeralds, an exit, boulders and a wall put in](screenshots/editor-changed.png)

**4. Change the values.** Press **V**. Up and down choose a line, left and
right change its number. Here EMERALDS goes down from 12 to 3, so the new
exit opens once the three new emeralds are taken. On the NAME line type a
name; **Del** takes the last letter back. **Return** or **V** go back to the
cave.

![Name and values](screenshots/editor-values.png)

**5. Try it.** Press **T**. The cave plays from its start with one life and
all its rules. Rockford takes the three emeralds, the exit opens, the
boulders fall into the tunnel behind him, and he walks out. The time left is
counted into the score, then you are back in the editor where you left it.

![Trying the changed cave](screenshots/editor-try.png)

**6. Save it.** Press **S**. The cave is written into its slot on the disk;
the status line says SAVED and the `*` is gone.

![Saved](screenshots/editor-saved.png)

**7. Play it.** Run/Stop leaves the editor. The cave stays as you left it,
saved or not: E brings you back to it until the game is left (Run/Stop
twice on the title: BASIC). On the title screen move right
past the last start cave until the status line says OWN 1, then press
fire (see [Playing your caves](#playing-your-caves)).

## The editor's screen

The status line at the top shows, from left to right:

- the element chosen, as a tile and by name; for one that walks (firefly,
  butterfly, biter, cow, ...) also the direction it starts in (FIREFLY UP),
- the cursor's place, column and row (02,02; the cave is 40 x 22 cells,
  0-39 and 0-21),
- the slot, OWN 01 to OWN 20,
- a `*` while there are changes not saved.

Below it is the cave, as it is at its start, with all its elements standing
still. The view follows the cursor. For a few seconds the status line may
show a message instead (see [Messages](#messages)).

**H** or **Help** shows the help page with all keys and the twelve elements with their
keys. Any key (or fire) goes back.

![The help page](screenshots/editor-help.png)

## Moving, putting, drawing

| Key | |
| --- | --- |
| cursor keys, joystick | move the cursor one cell; held, it goes on after a moment |
| fire, Space, Return | put the chosen element under the cursor |
| fire held while moving | draw: every cell the cursor passes gets the element |
| G | choose the element the cursor is on |

Putting the element a cell already has does nothing. There is only one
inbox in a cave: putting a new one turns the old one into dirt.

## The elements

| Key | Element | |
| --- | --- | --- |
| 1 | space | empty; things fall into it |
| 2 | dirt | Rockford digs through it; it holds boulders and emeralds |
| 3 | brick wall | boulders and emeralds roll off it; explosions break it |
| 4 | steel wall | nothing breaks it; also the frame of a cave |
| 5 | boulder | falls and rolls; it kills Rockford when it lands on him |
| 6 | emerald | to collect; enough of them open the exit |
| 7 | firefly | follows walls; it explodes into empty space |
| 8 | butterfly | follows walls the other way; it explodes into emeralds |
| 9 | amoeba | grows; enclosed it turns into emeralds, too big into boulders |
| 0 | magic wall | turns falling boulders into emeralds and back, while it runs |
| I | inbox | where Rockford comes in (one per cave) |
| X | exit | opens when enough emeralds are collected |

**Fireflies and butterflies** start in a direction, as everything that
walks. Pressing **7** (or **8**) again while it is chosen, or **R** for any
of them, turns the direction on: up, right, down, left. The status line
shows it, and in the cave all of one kind look alike: with the cursor on
one, an arrow after the cursor's place in the status line (`^ > V <`) tells
where it goes.

## All elements: the page of their own

**E** opens a page with all of GDash's elements that a cave can start with,
95 of them, in five rows: the twelve above and slime, nut, clock, acid,
lava, the hidden exit and Rockford himself; the walls that grow and the
special walls; the other creatures (biters, stoneflies, dragonflies, cows,
ghosts, ...) and boulders and emeralds of all kinds; keys, doors and
things to collect; conveyor belts, switches and the sloped walls. They move
as in the cave.

![All elements: the cursor on the emerald key](screenshots/editor-elements.png)

The cursor keys or the joystick move the cursor (held, it goes on), the
status line names the element under it, and **fire** (Space, Return) takes
it and goes back to the cave, where the cursor is as it was. **E** or
**Run/Stop** go back without a new choice. Taking one that walks again turns
its direction, as R does.

In the cave some of them look like others, as in the game: the exit and the
hidden exit, the walls that grow and brick wall (or steel). The status line
tells them apart when the cursor takes them with **G**.

The elements play by GDash's rules, with the properties of the cave: a new
cave has those of Boulder Dash 1 with GDash's defaults for everything else
(how slime lets things through, what a clock gives, ...), a cave from GDash
(see [below](#caves-on-the-pc-gdash-and-cavekitpy)) brings its own. The
values page (V) changes the ones of the [Name and values](#name-and-values)
list; the others are set with GDash on the PC.

![A cave with GDash's elements in slot 3](screenshots/editor-gdash.png)

## Slots: loading, new caves, emptying

The disk has twenty slots for own caves, `OWN01` to `OWN20`. The editor
opens on slot 1 (later on the slot you had last).

| Key | |
| --- | --- |
| + | the next slot (after 20: 1) |
| - | the last slot (before 1: 20) |
| C, C again | a new cave in place of this one (not saved yet) |
| D, D again | empty the slot on the disk |

**+** and **-** load the slot from the disk. An empty slot shows a new cave:
a frame of steel wall, dirt, the inbox top left, the exit bottom right, 150
seconds, 10 emeralds needed, Boulder Dash 1's rules. That is the start for a
cave of your own. Nothing is written to the disk until you save.

![An empty slot: a new cave](screenshots/editor-new.png)

**C** makes the same new cave in the slot you are on, **D** empties the slot
on the disk (an empty slot is left out when the own caves are played). Both
want the key twice, the status line asks for it. **+** and **-** want it
twice as well when there are changes not saved: NOT SAVED - + AGAIN: NEXT
SLOT. Any other key in between cancels. **Run/Stop** loses nothing: the cave
waits for you, saved or not, until you go back to BASIC (then the title
asks: CAVE NOT SAVED - RUN/STOP AGAIN: BASIC).

## Name and values

**V** opens the page with the cave's name and values.

| Line | Range | |
| --- | --- | --- |
| NAME | up to 21 letters | A-Z, 0-9, space and `/ : . ! - ,`; shown when the cave starts |
| TIME | 1-999 | seconds to get out |
| EMERALDS | 0-255 | emeralds to collect before the exit opens; 0: all of them in the cave |
| VALUE | 0-99 | points per emerald until the exit opens |
| EXTRA | 0-99 | points per emerald after that |
| SPEED | 50-250 | milliseconds per step: smaller is faster (the game's caves: about 150) |
| AMOEBA | 0-999 | seconds the amoeba grows slowly, then it grows fast |
| MAGIC | 0-999 | seconds the magic wall runs once started; 0: it does not stop |

Up and down choose a line (it shines). Left and right change the number;
held, it runs on, and after a while in steps of ten. On the NAME line the
keys type the name and **Del** takes the last letter back. **Return**,
**V**, **Run/Stop** or fire (not on the NAME line, where Space is a space)
go back to the cave.

A cave from GDash may have the C64's timing, where the speed comes from the
cave itself. SPEED then shows the speed it starts with; once you change it,
the cave runs in milliseconds like the others.

## Trying a cave

**T** plays the cave as it is now, saved or not, with one life and all its
rules, then comes back to the editor with the cursor where it was. The
status line shows emeralds, time, lives and score as in the game.

- Rockford's way out is the exit, as in the game: the time left is counted
  into the score.
- **Run/Stop** gives up the life when he is stuck. After he is dead, fire
  (or a few seconds) brings you back; out of time, fire. **F1** comes back
  at once.
- In a cave from GDash the status line also shows for a few seconds what
  Rockford collects (keys, skeletons, ...) and where gravity pulls; hold
  **I** to see it.

A cave needs an inbox (or Rockford himself, in caves from GDash) and an exit
to be tried or saved.

## Saving

**S** writes the cave into its slot on the disk. The `*` goes and the status
line says SAVED; if the disk cannot be written, COULD NOT SAVE. The cave is
then the same in all five levels: levels of their own that a cave from
GDash brought along (see [below](#caves-on-the-pc-gdash-and-cavekitpy)) are
emptied, and so are they when **D** empties the slot.

The disk is the D81 image the game runs from. On a real MEGA65 it has to be
mounted from the SD card, as usual, and must not be write protected. In Xemu
the editor writes into the image file. Keep a copy of the image if you want
to keep your caves. A new version of the game comes on a new disk with
empty slots: take your caves along with `cavekit.py export` from the old
disk and `import` into the new one (see
[below](#caves-on-the-pc-gdash-and-cavekitpy)). Building the game with
`build.sh` keeps the slots of the old disk by itself.

## Playing your caves

On the title screen, left and right choose the cave to start with (1, 6,
11, 16, 21). Right of cave 21 come the own caves, OWN 1 to 20: left
and right choose the slot to start with, up and down the level, 1 to 5.
Fire starts them: from the slot chosen on, all slots that are not empty,
one after the other, with three lives; after the last one the first comes
again, in the next level (after level 5: level 5 again), as in GDash. The
status line shows slot and level, OWN 03/2. A cave saved in the editor is
the same in every level; one from GDash plays its own levels. The own caves
have no place in the high score table, which is for the game's caves.

![The title with the own caves chosen](screenshots/editor-title.png)

## The rules of the own caves

The own caves play by the rules of [GDash](https://github.com/revvv/gdash-export-CrLi),
the Boulder Dash construction kit for the PC: the game has its engine for
them. A new cave starts with Boulder Dash 1's rules. What is different from
the game's own 25 caves:

- What walks off an edge comes back on the other side, unless the edge is
  steel wall. Keep the steel frame of a new cave unless you want that.
- An amoeba that grows too big (200 cells) turns into boulders; one that
  cannot grow any more turns into emeralds.
- Caves from GDash bring their own rules along (C64 engines, timing,
  effects); the editor keeps them.

## Caves on the PC: GDash and cavekit.py

`tools/cavekit.py` (Python 3, nothing else needed) moves caves between the
game's disk and the PC:

```sh
tools/cavekit.py list   smaragd-dash.d81                 # what is in the slots
tools/cavekit.py export smaragd-dash.d81 my-caves.bd     # all own caves as one GDash file
tools/cavekit.py import smaragd-dash.d81 game.bd         # into the slots, from slot 1 on
tools/cavekit.py import smaragd-dash.d81 game.bd --cave 3 --slot 5
tools/cavekit.py empty  smaragd-dash.d81 --slot 3
tools/cavekit.py disks  smaragd-dash.d81 game.bd --out disks/   # a whole game on its own disks
```

- **Sharing your caves:** `export` writes them as a BDCFF file (`.bd`), the
  format of GDash. Someone else imports it into their disk with `import`,
  or opens it in GDash. A `.bd` file has one map for all levels of a cave:
  levels that differ only in their values (time, diamonds, ...) go along,
  where the maps differ (a random fill of its own) only the first level -
  `export` names those caves.
- **Caves from GDash:** GDash comes with thousands of caves of the C64 games
  and of fans. `import` takes `.bd` files; `--cave N` (or `N-M`) picks
  caves, `--slot N` the first slot. A cave comes with all five of its
  levels (the slot keeps those that differ from the first, see
  [Playing your caves](#playing-your-caves)); `--level L` (1-5) takes that
  level alone. GDash's
  `.gds` files (imported C64 games) go through GDash: open one there and
  save it (*File → Save as*), which writes a `.bd` file. In this repository
  `cavekit.py` does that by itself, with GDash's own code that
  `toolchain/tools/build-tools.sh` builds (`toolchain/tools/bin/gdash-oracle`;
  elsewhere `GDASH_ORACLE=` names the program): then all commands take
  `.gds` files as well.
- **A whole game:** `disks` makes disks to play a game from GDash on. Each
  is a copy of the game's disk with as many of the game's caves as there are
  slots (20), the rest empty: `game.d81`, or `game-1.d81`, `game-2.d81`, ...
  for a bigger game. Start one and choose OWN CAVES on the title: after the
  last cave the game goes on with the first in the next level, as the
  original does. The options of `import` work here too, e.g. `--level 3`
  for the game's third level alone. The caves of the game itself stay on
  every disk.

  ```sh
  tools/cavekit.py disks build/smaragd-dash.d81 Boulder_Dash_1.bd --out disks/
  # disks/Boulder_Dash_1.d81: 20 caves - A: INTRO ... INTERMISSION 4
  ```

  Many of GDash's caves are the caves of the original commercial games:
  keep such disks for yourself, do not pass them on.
- **Text files:** `convert` turns a `.bd` file into `.cave` text files, one
  per cave, with the map as 22 lines of 40 characters (described in
  `tools/cavekit.py`'s `parse_cave_text`), and back; `import` takes `.cave`
  files as well. So a cave can also be drawn in a text editor - or in
  GDash's own editor, as a `.bd` file, as the game's caves are.

More about this, and how exactly the caves follow GDash, is in the README,
[Own caves and GDash](README.md#own-caves-and-gdash).

## Messages

| Message | |
| --- | --- |
| THE CAVE NEEDS AN INBOX | put one (I) before trying or saving |
| THE CAVE NEEDS AN EXIT | put one (X) before trying or saving |
| SAVED | the cave is in its slot on the disk |
| COULD NOT SAVE | the disk is write protected, or it has no such slot |
| NOT SAVED - + AGAIN: NEXT SLOT | the same key again throws the changes away (also -) |
| C AGAIN: A NEW CAVE | C again makes a new cave in place of this one |
| D AGAIN: EMPTY THE SLOT | D again empties the slot on the disk |
| THE SLOT IS EMPTY | done; the editor shows a new cave |
| NOT AMONG THE ELEMENTS | G on something a cave does not start with (part of an explosion, ...) |
| NO GDASH ENGINE ON THE DISK | the disk lacks `SMARAGD.GD`: own caves cannot be played |

## All keys

| Key | |
| --- | --- |
| cursor keys, joystick | move the cursor |
| fire, Space, Return | put the element; held while moving: draw |
| 1-9, 0, I, X | choose the element (again for a firefly or butterfly: its direction) |
| G | choose the element under the cursor |
| V | name and values |
| T | try the cave |
| S | save it into its slot |
| + / - | next / last slot |
| E | all elements, on a page of their own |
| R | the next direction of what walks |
| C (twice) | a new cave |
| D (twice) | empty the slot |
| H or Help | help page |
| Run/Stop | back to the title; the cave stays as it is for the next time |
