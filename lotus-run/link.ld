/* Lotus Run: llvm-mos' MEGA65 PRG layout (mos-platform/mega65/lib/link.ld),
 * and two more pieces of bank 0 for variables that need no clearing
 * (WORK_RAM, LOW_RAM, HIGH_RAM in src/mem.h): .workram in the KERNAL's
 * work area, .lowram behind the DMA list, .highram behind the course under
 * the KERNAL (.workram and .highram usable once irq_init has switched it
 * out). The numbers are src/mem.h's. Besides, .menu: an overlay at
 * $E000, and .lowcode (see below). */

__basic_zp_start = 0x0002;
__basic_zp_end = 0x0090;

MEMORY {
    ram (rw) : ORIGIN = 0x2001, LENGTH = 0xafff
    workram (rw) : ORIGIN = 0x0200, LENGTH = 0x0200
    lowcode (rx) : ORIGIN = 0x0900, LENGTH = 0x0700
    lowram (rw) : ORIGIN = 0x1000, LENGTH = 0x1000
    highram (rw) : ORIGIN = 0xf100, LENGTH = 0x0efa
    menu (rx) : ORIGIN = 0xe000, LENGTH = 0x1ffa
}

SECTIONS {
    .workram (NOLOAD) : { *(.workram .workram.*) } >workram
    .lowram (NOLOAD) : { *(.lowram .lowram.*) } >lowram
    /* code that stays in bank 0 (LOW_CODE in src/mem.h): not part of the
       program file either - on the disk as LOWCODE, which main.c loads */
    .lowcode : { *(.lowcode .lowcode.*) } >lowcode
    .highram (NOLOAD) : { *(.highram .highram.*) } >highram
    /* the code of the pages between the races (MENU in src/mem.h): not part
       of the program file - build.sh writes it to the disk as MENU, main.c
       copies it here; the race's course and .highram take its place then
       (it may reach into .highram: build.sh links with --no-check-sections,
       tools/bin/mega65-mem shows the overlap) */
    .menu : { *(.menu .menu.*) } >menu
}

INCLUDE commodore.ld

INPUT(unmap-basic.o)

__stack = 0xd000;

OUTPUT_FORMAT {
    SHORT(0x2001)
    TRIM(ram)
}
