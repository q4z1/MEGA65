; Lotus Run: the raster interrupt - the colours that change down the
; screen.
;
; From raster line irq_line[i] on, palette entries 12-15 get the colours of
; entry i (irq_r/g/b, four each). The table being shown is the active one;
; the renderer fills the next one (irq_next_*), and video_show copies it
; over while the beam is in the lower border (video.c). The entries are
; sorted by line; the last one is followed by the first again, in the next
; frame.
;
; The KERNAL is switched out for this: the game never calls it, and the
; interrupt vector at $FFFE is then ours.

IRQ_ENTRIES = 64

.global irq_init, irq_restart, irq_count
.global irq_line_lo, irq_line_hi, irq_colours

.section .bss.irq,"aw",@nobits
irq_index:   .fill 1
irq_count:   .fill 1
; per entry: raster line (low byte; bit 8 as $80), then R G B of colour
; 12, 13, 14 and 15: each field an array of IRQ_ENTRIES (irq.h)
irq_line_lo: .fill IRQ_ENTRIES
irq_line_hi: .fill IRQ_ENTRIES
irq_colours: .fill 12 * IRQ_ENTRIES

.section .text.irq,"ax",@progbits

; Switches the KERNAL out, installs the handler; the table must hold at
; least one entry (irq_count > 0)
irq_init:
    sei
    ; no mapping in the upper 32K (the C65 KERNAL is mapped there), then
    ; RAM under $E000 through the CPU port
    lda #0
    ldx #0
    ldy #0
    ldz #0
    map
    eom
    lda #$35
    sta $01
    lda #<irq_handler
    sta $FFFE
    lda #>irq_handler
    sta $FFFF
    lda #<nmi_handler
    sta $FFFA
    lda #>nmi_handler
    sta $FFFB
    lda #$7F            ; no CIA interrupts
    sta $DC0D
    sta $DD0D
    lda $DC0D
    lda $DD0D
    lda #0
    sta irq_index
    lda irq_line_lo
    sta $D012
    lda $D011
    and #$7F
    ora irq_line_hi
    sta $D011
    lda #$FF            ; acknowledge whatever is pending
    sta $D019
    lda #$01            ; raster interrupt on
    sta $D01A
    ldz #0              ; llvm-mos keeps Z at 0
    cli
    rts

; From the table's first entry on (interrupts off)
irq_restart:
    lda #0
    sta irq_index
    lda irq_line_lo
    sta $D012
    lda $D011
    and #$7F
    ora irq_line_hi
    sta $D011
    rts

irq_handler:
    pha
    phx
    phy
    ldy irq_index
    lda irq_colours + 0 * IRQ_ENTRIES, y
    sta $D10C
    lda irq_colours + 1 * IRQ_ENTRIES, y
    sta $D20C
    lda irq_colours + 2 * IRQ_ENTRIES, y
    sta $D30C
    lda irq_colours + 3 * IRQ_ENTRIES, y
    sta $D10D
    lda irq_colours + 4 * IRQ_ENTRIES, y
    sta $D20D
    lda irq_colours + 5 * IRQ_ENTRIES, y
    sta $D30D
    lda irq_colours + 6 * IRQ_ENTRIES, y
    sta $D10E
    lda irq_colours + 7 * IRQ_ENTRIES, y
    sta $D20E
    lda irq_colours + 8 * IRQ_ENTRIES, y
    sta $D30E
    lda irq_colours + 9 * IRQ_ENTRIES, y
    sta $D10F
    lda irq_colours + 10 * IRQ_ENTRIES, y
    sta $D20F
    lda irq_colours + 11 * IRQ_ENTRIES, y
    sta $D30F
    iny
    cpy irq_count
    bcc 1f
    ldy #0
1:
    sty irq_index
    lda irq_line_lo, y
    sta $D012
    lda $D011
    and #$7F
    ora irq_line_hi, y
    sta $D011
    lda #$01
    sta $D019
    ply
    plx
    pla
nmi_handler:
    rti
