/* Smaragd Dash: llvm-mos' MEGA65 PRG layout (mos-platform/mega65/lib/link.ld),
 * up to $BFFF, and besides:
 *   .editor   the cave editor's code, an overlay in the RAM under the KERNAL
 *             at $E000 (main.c switches the KERNAL out at the start), not
 *             part of the program file: build.sh writes it to the disk as
 *             SMARAGD.EDIT, which main.c loads when the editor is opened
 *   .lowcode  the calls into GDash's engine (src/gdfar.s) at $1F80, behind
 *             the DMA list: on the disk as SMARAGD.LOW, loaded at the start
 * What it shares with GDash's engine lies at $C000 (shared.ld), the C stack
 * behind it. The numbers are src/mem.h's. */

__basic_zp_start = 0x0002;
__basic_zp_end = 0x0090;

MEMORY {
    ram (rw) : ORIGIN = 0x2001, LENGTH = 0x9fff
    lowcode (rx) : ORIGIN = 0x1f80, LENGTH = 0x80
    editor (rx) : ORIGIN = 0xe000, LENGTH = 0x1ffa
}

SECTIONS {
    .editor : { *(.editor .editor.*) } >editor
    .lowcode : { *(.lowcode .lowcode.*) } >lowcode
}

INCLUDE commodore.ld
INCLUDE shared.ld

INPUT(unmap-basic.o)

__stack = 0xd000;
/* the C stack grows down from __stack into what lies below: room for it */
ASSERT(__heap_start + 0x200 <= __stack, "less than 512 bytes left for the C stack")

OUTPUT_FORMAT {
    SHORT(0x2001)
    TRIM(ram)
}
