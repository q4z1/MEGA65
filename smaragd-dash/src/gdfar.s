; Smaragd Dash: calls into GDash's engine, which lies in bank 2 and shows at
; $4000-$BFFF only while it runs (src/mem.h, gdengine.ld): MAP it in, call
; it, MAP it out again. This lies outside that, in link.ld's .lowcode, which
; main.c loads to $1F80 (SMARAGD.LOW). The arguments stay as they came (A,
; X, Y and the imaginary registers), and so does what it returns (A, X).

.global gd_start, gd_iterate, gd_time_visible

.section .lowcode,"ax",@progbits

gd_start:
    jsr map_in
    jsr $4000
    jmp map_out

gd_iterate:
    jsr map_in
    jsr $4003
    jmp map_out

gd_time_visible:
    jsr map_in
    jsr $4006
map_out:
    pha
    phx
    phy
    lda #0
    tax
    tay
    taz
    map
    eom
    ply
    plx
    pla
    rts

; $4000-$7FFF (blocks 2 and 3) and $8000-$BFFF (4 and 5) from $24000
map_in:
    pha
    phx
    phy
    lda #$00
    ldx #$C2
    ldy #$00
    ldz #$32
    map
    eom
    ldz #0
    ply
    plx
    pla
    rts
