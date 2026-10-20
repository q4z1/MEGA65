// Lotus Run: the panel at the right of the race view - gear, speed, rpm,
// fuel and place of player 1 - and the lap bar at its top left.
//
// The panel's picture is kept as it is shown (banks.h: panel_live); one of
// its values is brought up to date per picture, in turn, and the panel is
// drawn over the view.

#ifndef PANEL_H_INCLUDED
#define PANEL_H_INCLUDED

#include <stdint.h>

// All values from the race as it is now (at the start of a race)
void panel_reset(void);

// At the start of a picture: the value whose turn it is (panel_turn, counted
// up per picture)
extern uint8_t panel_turn;
void panel_picture(void);

// The panel into the picture (over the view, at its top right)
void panel_draw(void);

#endif
