/* Smaragd Dash: GDash's engine (src/gdengine.c) linked on its own, as a
 * block of code and data for $4000-$BFFF that lies in bank 2 ($24000, in
 * place of the C65 ROM, which the game does not use) and is mapped there
 * only while it runs (src/gdfar.s). It shares the imaginary registers with
 * the program and has the KERNAL's zero page from $90 on for its own;
 * cave[], moved[] and gd are the program's (build.sh gives their addresses).
 * Nothing calls a start-up routine: what it needs set, gd_start sets. The
 * numbers are src/mem.h's. */

__rc0 = 0x02;
INCLUDE imag-regs.ld
INCLUDE shared.ld

MEMORY {
    zp : ORIGIN = 0x90, LENGTH = 0x70
    gd (rwx) : ORIGIN = 0x4000, LENGTH = 0x8000
}

REGION_ALIAS("c_readonly", gd)
REGION_ALIAS("c_writeable", gd)

SECTIONS {
    /* the entry points at fixed places: src/gdjump.s */
    .gdjump : { KEEP(*(.gdjump)) } >gd
    INCLUDE c.ld
}

OUTPUT_FORMAT {
    TRIM(gd)
}
