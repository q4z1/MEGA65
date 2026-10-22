/* Smaragd Dash: what the program (link.ld) and GDash's engine (gdengine.ld)
 * share, at $C000: outside $4000-$BFFF, where the engine shows while it runs.
 * Fixed here, so link-time optimisation leaves it whole and both find it.
 * The numbers are src/mem.h's; the C stack lies behind, below $D000. */

cave = 0xc000;   /* 880 cells (engine.h) */
moved = 0xc370;  /* 880 (engine.h) */
gd = 0xc6e0;     /* GdState (gdengine.h), up to 256 bytes */
file = 0xc7e0;   /* the cave being played (main.c), up to 1040 bytes, to $cbf0 */
