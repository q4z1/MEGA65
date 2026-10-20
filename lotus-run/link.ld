/* Lotus Run: llvm-mos' MEGA65 PRG layout (mos-platform/mega65/lib/link.ld),
 * and two more pieces of bank 0 for variables that need no clearing
 * (WORK_RAM, LOW_RAM, HIGH_RAM in src/mem.h): .workram in the KERNAL's
 * work area, .lowram behind the DMA list, .highram behind the course under
 * the KERNAL (.workram and .highram usable once irq_init has switched it
 * out). The numbers are src/mem.h's. */

__basic_zp_start = 0x0002;
__basic_zp_end = 0x0090;

MEMORY {
    ram (rw) : ORIGIN = 0x2001, LENGTH = 0xafff
    workram (rw) : ORIGIN = 0x0200, LENGTH = 0x0200
    lowram (rw) : ORIGIN = 0x1400, LENGTH = 0x0c00
    highram (rw) : ORIGIN = 0xf100, LENGTH = 0x0efa
}

SECTIONS {
    .workram (NOLOAD) : { *(.workram .workram.*) } >workram
    .lowram (NOLOAD) : { *(.lowram .lowram.*) } >lowram
    .highram (NOLOAD) : { *(.highram .highram.*) } >highram
}

INCLUDE commodore.ld

INPUT(unmap-basic.o)

__stack = 0xd000;

OUTPUT_FORMAT {
    SHORT(0x2001)
    TRIM(ram)
}
