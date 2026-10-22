; Smaragd Dash: the cell access of GDash's engine in 45GS02 assembly - the
; same as cell() and get() in src/gdengine.c, which the host's tests use;
; tests/test_gdmega65.py checks these against them on the MEGA65. They are
; called all over the engine (get() at more than a hundred places).
;
; cell(x, y): the index of x, y in cave[] (y * CAVE_W + x), wrapped round
;   the cave as GDash does: perfectly, or line-shifted as on the C64 (off
;   the right edge into the next row).
; get(x, y): the element there, with SCAN (0x100) if it is scanned in this
;   step (its bit in gd_scanned[]).
; store(x, y, e): e there - unless lava, not scanned, is there, which takes
;   what comes into it -, scanned if e has a scanned twin (gd_twin[]).
; has_flag(x, y, dir, f): whether the element next to x, y in direction dir
;   (gd_dx[], gd_dy[]) has one of the properties f (P_*): gd_flags[], or for
;   a scanned one P_SCANNED and what flags_of() adds to it.
;
; x in A, y in X (signed), e and dir in __rc2, f in __rc3-__rc6; the result
; in A (low) and X (high), as llvm-mos passes them. They change Y and
; __rc4-__rc11, which a caller does not keep.
; Z stays 0. The places of gd.w, gd.h and gd.flags are checked in
; src/gdengine.c.

.global cell, get, store, has_flag

CAVE_W = 40
CAVE_H = 22
GD_W = gd + 2
GD_H = gd + 3
GD_FLAGS_3 = gd + 7             ; bits 24-31 of gd.flags
LINESHIFT = $02                 ; GDF_LINESHIFT >> 24
O_LAVA = 116
O_H_EXPANDING_STEEL_WALL = 47
O_EXPANDING_STEEL_WALL = 49     ; 47-49: the three
O_PLAYER = 163

.section .bss.gdcell,"aw",@nobits
c_x: .fill 1
c_y: .fill 1
c_e: .fill 1
hf_f: .fill 4                   ; has_flag's f

.section .rodata.gdcell,"a",@progbits
row_lo:                         ; y * CAVE_W
    .irp y, 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21
    .byte <(\y * CAVE_W)
    .endr
row_hi:
    .irp y, 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21
    .byte >(\y * CAVE_W)
    .endr
srow:                           ; y * CAVE_W / 8: the row's first byte in gd_scanned[]
    .irp y, 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21
    .byte \y * CAVE_W / 8
    .endr
bits:
    .byte 1, 2, 4, 8, 16, 32, 64, 128

.section .text.gdcell,"ax",@progbits

cell:
    jsr wrap
    lda c_x
    clc
    adc row_lo, y
    ldx row_hi, y
    bcc cell_done
    inx
cell_done:
    rts

get:
    jsr wrap
    lda row_lo, y               ; the row in cave[]
    clc
    adc #<cave
    sta __rc4
    lda row_hi, y
    adc #>cave
    sta __rc5
    lda srow, y                 ; the byte of gd_scanned[]: srow[y] + x / 8
    sta c_e
    lda c_x
    lsr
    lsr
    lsr
    clc
    adc c_e
    tax
    lda c_x
    and #7
    tay
    lda bits, y
    and gd_scanned, x
    tax                         ; 0, or not 0: scanned
    ldy c_x
    lda (__rc4), y
    cpx #0
    beq get_done
    ldx #1                      ; SCAN >> 8
get_done:
    rts

store:
    jsr wrap
    lda row_lo, y               ; the row in cave[]
    clc
    adc #<cave
    sta __rc4
    lda row_hi, y
    adc #>cave
    sta __rc5
    lda srow, y                 ; X: the byte of gd_scanned[]
    sta c_e
    lda c_x
    lsr
    lsr
    lsr
    clc
    adc c_e
    tax
    lda c_x
    and #7
    tay
    lda bits, y
    sta c_e                     ; the cell's bit
    ldy c_x
    lda (__rc4), y
    cmp #O_LAVA
    bne store_it
    lda gd_scanned, x
    and c_e
    beq store_done              ; lava takes it
store_it:
    lda __rc2
    sta (__rc4), y
    lsr                         ; scanned if it has a twin: gd_twin[e / 8], bit e & 7
    lsr
    lsr
    tay
    lda gd_twin, y
    sta __rc6
    lda __rc2
    and #7
    tay
    lda bits, y
    and __rc6
    beq store_unscanned
    lda gd_scanned, x
    ora c_e
    sta gd_scanned, x
store_done:
    rts
store_unscanned:
    lda c_e
    eor #$FF
    and gd_scanned, x
    sta gd_scanned, x
    rts

has_flag:
    ldy __rc3                   ; f, before get changes __rc4-__rc5
    sty hf_f
    ldy __rc4
    sty hf_f+1
    ldy __rc5
    sty hf_f+2
    ldy __rc6
    sty hf_f+3
    ldy __rc2
    clc
    adc gd_dx, y
    sta c_e
    txa
    clc
    adc gd_dy, y
    tax
    lda c_e
    jsr get
    cpx #0
    bne hf_scanned
    sta __rc4                   ; gd_flags + e * 4
    lda #0
    asl __rc4
    rol
    asl __rc4
    rol
    sta __rc5
    clc
    lda __rc4
    adc #<gd_flags
    sta __rc4
    lda __rc5
    adc #>gd_flags
    sta __rc5
    ldy #3
hf_bytes:
    lda (__rc4), y
    and hf_f, y
    bne hf_true
    dey
    bpl hf_bytes
    lda #0
    rts
hf_true:
    lda #1
    rts

; a scanned element: P_SCANNED (bit 0), with P_NON_EXPLODABLE (bit 11)
; for the expanding steel walls or P_BLOWS_UP_FLIES (bit 8) for the player
hf_scanned:
    tay
    lda hf_f
    and #$01
    bne hf_true
    cpy #O_PLAYER
    beq hf_player
    cpy #O_H_EXPANDING_STEEL_WALL
    bcc hf_false
    cpy #O_EXPANDING_STEEL_WALL + 1
    bcs hf_false
    lda hf_f+1
    and #$08
    bne hf_true
hf_false:
    lda #0
    rts
hf_player:
    lda hf_f+1
    and #$01
    bne hf_true
    lda #0
    rts

; x, y (A, X) into the cave: c_x, c_y; Y = c_y
wrap:
    sta c_x
    stx c_y
    cmp GD_W
    bcs wrap_x                  ; x < 0 (as unsigned: >= 128) or x >= w
wrap_y:
    lda c_y
    cmp GD_H
    bcs wrap_y_out
wrap_done:
    ldy c_y
    rts
wrap_x:
    lda c_x
    bmi wrap_x_neg
    sec
    sbc GD_W
    sta c_x
    lda GD_FLAGS_3
    and #LINESHIFT
    beq wrap_y
    inc c_y
    bra wrap_y
wrap_x_neg:
    clc
    adc GD_W
    sta c_x
    lda GD_FLAGS_3
    and #LINESHIFT
    beq wrap_y
    dec c_y
    bra wrap_y
wrap_y_out:
    lda c_y
    bmi wrap_y_neg
    sec
    sbc GD_H
    sta c_y
    bra wrap_done
wrap_y_neg:
    clc
    adc GD_H
    sta c_y
    bra wrap_done
