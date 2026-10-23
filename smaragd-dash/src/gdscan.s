; Smaragd Dash: the passes over the cave of GDash's engine in 45GS02
; assembly - the same as scan_cells, the passes after it and find_player in
; src/gdengine.c, which the host's tests use; tests/test_gdmega65.py checks
; these against them on the MEGA65. What they know of an element comes from
; gd_class[] (GDC_* in src/gdengine.c, set by gd_start).
;
; scan_cells(ymin, ymax, w): the rows ymin-ymax, w cells each, in GDash's
;   order. A cell not scanned yet in this step whose element does something
;   adds its delay (gd_ckdelay) to gd_scan_ckdelay and goes to scan_cell (C)
;   with its x, y and element - but a boulder, emerald, ... that only
;   starts to fall with gravity (GDC_FALLS) and lies on what holds it stays
;   here: on what is not round, or on something round (GDC_ROUND) with no
;   free cell and free cell below it on either side to roll to (as
;   do_start_fall). So do a magic wall (it is only heard when it runs) and
;   a wall that grows four ways with no free cell beside it. Every cell is
;   unscanned afterwards.
; gd_cave_classes(first): the classes of all cells of the cave, or-ed; and
;   the last player in the cave (the first with first) into gd_found_x,
;   gd_found_y, as gd_find_player.
; gd_find_player(first): the last player in the cave (the first with
;   first) into gd_found_x, gd_found_y; false if there is none.
;
; Arguments and results as llvm-mos passes them: A, X, then __rc2. C code
; may change A, X, Y and __rc2-__rc19; the row pointer the scan keeps over
; scan_cell lives in __rc20-__rc21, kept for the caller too. Z is 0 whenever
; C code runs. The places of gd.w, gd.h, gd.gravity and gd.gravity_disabled
; are checked in src/gdengine.c.

.global scan_cells, gd_cave_classes, gd_find_player, gd_found_x, gd_found_y, gd_clear_scanned

row  = __rc20                   ; the row in cave[]
ptr  = __rc4                    ; a row, for the other passes

CAVE_W = 40
GD_W = gd + 2
GD_H = gd + 3
GD_GRAVITY = gd + 46
GD_GRAVITY_DISABLED = gd + 92
GD_MAGIC_WALL_STATE = gd + 116
GD_SOUND = gd + 126
MV_DOWN = 5
GD_MW_ACTIVE = 1
SND_MAGIC = $40
O_MAGIC_WALL = 17
O_EXPANDING_WALL = 46
O_EXPANDING_STEEL_WALL = 49

GDC_PLAYER = $01
GDC_FALLS = $08
GDC_SPACE = $10
GDC_SLOPED_UP = $20
GDC_ROUND = $40
GDC_IDLE = $80

.section .bss.gdscan,"aw",@nobits
sc_x:       .fill 1
sc_y:       .fill 1
sc_e:       .fill 1             ; the element
sc_sx:      .fill 1             ; the cell's byte in gd_scanned[]
sc_rowsx:   .fill 1             ; the row's first one
sc_ymax:    .fill 1
sc_w:       .fill 1
sc_bit:     .fill 1             ; the cell's bit in its byte of gd_scanned[]
sc_class:   .fill 1
sc_ck:      .fill 2             ; the row's delay
sc_save:    .fill 2             ; __rc20-__rc21 of the caller
sc_nsx:     .fill 1             ; a cell beside: its byte in gd_scanned[]
sc_nbit:    .fill 1             ; ... and its bit
cc_or:      .fill 1
cc_y:       .fill 1
fp_first:   .fill 1
fp_found:   .fill 1
gd_found_x: .fill 1
gd_found_y: .fill 1

.section .text.scan_cells,"ax",@progbits
scan_cells:
    sta sc_y
    stx sc_ymax
    lda __rc2
    sta sc_w
    lda row
    sta sc_save
    lda row+1
    sta sc_save+1

    ; the first row: row = cave + ymin * CAVE_W, sc_rowsx = ymin * CAVE_W / 8
    lda #<cave
    sta row
    lda #>cave
    sta row+1
    lda #0
    sta sc_rowsx
    ldx sc_y
    beq row_loop
first_row:
    jsr next_row
    dex
    bne first_row

row_loop:
    lda sc_ymax
    cmp sc_y
    bcc done                    ; ymax < y
    lda #0
    sta sc_ck
    sta sc_ck+1
    lda sc_rowsx
    sta sc_sx
    lda #1
    sta sc_bit
    ldy #0                      ; Y: x

    ; X: the cell's byte in gd_scanned[] (sc_sx), sc_bit its bit
cell_loop:
    lda (row), y
    tax
    lda gd_class, x
    bmi idle                    ; space, dirt, walls (GDC_IDLE)
    stx sc_e
    sta sc_class
    sty sc_x
    ldx sc_sx
    lda gd_scanned, x
    and sc_bit
    bne clear_bit               ; scanned already

    ; its delay: gd_ckdelay[e], 16 bits (e * 2 may pass 255)
    lda sc_e
    asl
    tay
    bcs ck_high
    clc
    lda gd_ckdelay, y
    adc sc_ck
    sta sc_ck
    lda gd_ckdelay+1, y
    adc sc_ck+1
    sta sc_ck+1
    bra falls
ck_high:
    clc
    lda gd_ckdelay+256, y
    adc sc_ck
    sta sc_ck
    lda gd_ckdelay+257, y
    adc sc_ck+1
    sta sc_ck+1

    ; something that starts to fall with gravity (do_start_fall): it stays
    ; where it is if gravity is off, or if gravity pulls down and below it
    ; is something scanned, or neither like space nor sloped up. Anything
    ; else goes to scan_cell.
falls:
    lda sc_class
    and #GDC_FALLS
    bne fall_check
    lda sc_e
    cmp #O_MAGIC_WALL
    beq magic
    cmp #O_EXPANDING_WALL
    beq grows
    cmp #O_EXPANDING_STEEL_WALL
    bne call

    ; a wall that grows four ways: only where a cell beside is free (not at
    ; the edges, where the cave goes round)
grows:
    ldy sc_x
    beq call
    iny
    cpy sc_w
    bcs call
    lda sc_y
    beq call
    inc a
    cmp GD_H
    bcs call
    jsr left_bits               ; left
    ldy sc_x
    dey
    jsr row_free
    bcs call
    jsr right_bits              ; right
    ldy sc_x
    iny
    jsr row_free
    bcs call
    lda sc_bit                  ; below
    sta sc_nbit
    lda sc_sx
    clc
    adc #CAVE_W / 8
    sta sc_nsx
    lda sc_x
    clc
    adc #CAVE_W
    tay
    jsr row_free
    bcs call
    lda sc_sx                   ; above
    sec
    sbc #CAVE_W / 8
    sta sc_nsx
    sec
    lda row
    sbc #CAVE_W
    sta ptr
    lda row+1
    sbc #0
    sta ptr+1
    ldy sc_x
    jsr cell_free
    bcs call
    bra stays

magic:                          ; heard while it runs
    lda GD_MAGIC_WALL_STATE
    cmp #GD_MW_ACTIVE
    bne stays
    lda GD_SOUND
    ora #SND_MAGIC
    sta GD_SOUND
    bra stays

fall_check:
    lda GD_GRAVITY_DISABLED
    bne stays
    lda GD_GRAVITY
    cmp #MV_DOWN
    bne call
    lda sc_y
    clc
    adc #1
    cmp GD_H
    bcs call                    ; below is the top row again
    lda sc_sx                   ; below's bit: in the next row of gd_scanned[]
    clc
    adc #CAVE_W / 8
    tax
    lda gd_scanned, x
    and sc_bit
    bne stays
    lda sc_x
    clc
    adc #CAVE_W
    tay
    lda (row), y
    tax
    lda gd_class, x
    tax
    and #GDC_SPACE
    bne call                    ; below is free: it falls
    txa
    and #GDC_SLOPED_UP
    beq stays                   ; nothing to roll off
    txa
    and #GDC_ROUND
    beq call                    ; sloped one way only
    ldy sc_x                    ; not at the edges, where the cave goes round
    beq call
    iny
    cpy sc_w
    bcs call

    ; round below: it rolls if a side and the cell below it are free - the
    ; left first, then the right
    jsr left_bits
    ldy sc_x
    dey
    jsr side_free
    bcs call
    jsr right_bits
    ldy sc_x
    iny
    jsr side_free
    bcc stays

call:
    lda sc_e                    ; scan_cell(x, y, e)
    sta __rc2
    lda sc_x
    ldx sc_y
    jsr scan_cell
stays:
    ldy sc_x
    ldx sc_sx

clear_bit:                      ; unscan: X, sc_bit; Y: x
    lda sc_bit
    eor #$FF
    and gd_scanned, x
    sta gd_scanned, x
    bra next_cell
idle:
    ldx sc_sx
    lda gd_scanned, x
    and sc_bit
    bne clear_bit
next_cell:
    asl sc_bit
    bne next_cell_x
    lda #1
    sta sc_bit
    inc sc_sx
next_cell_x:
    iny
    cpy sc_w
    bcc cell_loop

    ; the row's delay into gd_scan_ckdelay (32 bits)
    clc
    lda gd_scan_ckdelay
    adc sc_ck
    sta gd_scan_ckdelay
    lda gd_scan_ckdelay+1
    adc sc_ck+1
    sta gd_scan_ckdelay+1
    lda gd_scan_ckdelay+2
    adc #0
    sta gd_scan_ckdelay+2
    lda gd_scan_ckdelay+3
    adc #0
    sta gd_scan_ckdelay+3
    jsr next_row
    inc sc_y
    bra row_loop

done:
    lda sc_save
    sta row
    lda sc_save+1
    sta row+1
    rts

; The cell's bit in gd_scanned[] of x - 1 (left_bits) or x + 1
; (right_bits) into sc_nsx, sc_nbit. A and X change.
left_bits:
    ldx sc_sx
    lda sc_bit
    lsr
    bcc nbits
    lda #$80                    ; bit 7 of the byte before
    dex
    bra nbits
right_bits:
    ldx sc_sx
    lda sc_bit
    asl
    bcc nbits
    lda #1                      ; bit 0 of the byte after
    inx
nbits:
    sta sc_nbit
    stx sc_nsx
    rts

; Carry set if the cell Y of the row and the one below it are free: like
; space and not scanned (their bit sc_nbit in sc_nsx and the next row's
; byte). A, X and Y change.
side_free:
    jsr row_free
    bcc side_taken
    tya
    clc
    adc #CAVE_W
    tay
    lda sc_nsx
    clc
    adc #CAVE_W / 8
    sta sc_nsx
    ; the cell below, as row_free

; Carry set if the cell Y of the row (row_free) or of ptr (cell_free) is
; free, its bit sc_nbit in gd_scanned[sc_nsx]. A and X change.
row_free:
    lda row
    sta ptr
    lda row+1
    sta ptr+1
cell_free:
    lda (ptr), y
    tax
    lda gd_class, x
    and #GDC_SPACE
    beq side_taken
    ldx sc_nsx
    lda gd_scanned, x
    and sc_nbit
    bne side_taken
    sec
    rts
side_taken:
    clc
    rts

; row += CAVE_W, sc_rowsx += CAVE_W / 8 (A changes)
next_row:
    clc
    lda row
    adc #CAVE_W
    sta row
    bcc next_row_s
    inc row+1
next_row_s:
    clc
    lda sc_rowsx
    adc #CAVE_W / 8
    sta sc_rowsx
    rts

; ptr = cave, cc_y = 0 (A changes)
first_cave_row:
    lda #<cave
    sta ptr
    lda #>cave
    sta ptr+1
    lda #0
    sta cc_y
    rts

; ptr += CAVE_W, cc_y += 1; carry clear while cc_y < h (A changes)
next_cave_row:
    clc
    lda ptr
    adc #CAVE_W
    sta ptr
    bcc next_cave_row_y
    inc ptr+1
next_cave_row_y:
    inc cc_y
    lda cc_y
    cmp GD_H
    rts

.section .text.gd_cave_classes,"ax",@progbits
gd_cave_classes:
    sta fp_first
    jsr first_cave_row
    lda #0
    sta cc_or
    sta fp_found
cc_row:
    ldy #0
cc_cell:
    lda (ptr), y
    tax
    lda gd_class, x
    beq cc_next                 ; nothing to note
    tsb cc_or                   ; cc_or |= A
    and #GDC_PLAYER
    beq cc_next
    lda fp_first                ; the first one only?
    and fp_found
    bne cc_next
    sty gd_found_x
    lda cc_y
    sta gd_found_y
    lda #1
    sta fp_found
cc_next:
    iny
    cpy GD_W
    bcc cc_cell
    jsr next_cave_row
    bcc cc_row
    lda cc_or
    rts

; gd_clear_scanned(): all of gd_scanned[] 0
.section .text.gd_clear_scanned,"ax",@progbits
gd_clear_scanned:
    lda #0
    ldx #CAVE_SIZE / 8
cs_byte:
    sta gd_scanned-1, x
    dex
    bne cs_byte
    rts

.section .text.gd_find_player,"ax",@progbits
gd_find_player:
    sta fp_first
    lda #0
    sta fp_found
    jsr first_cave_row
fp_row:
    ldy #0
fp_cell:
    lda (ptr), y
    tax
    lda gd_class, x
    and #GDC_PLAYER
    beq fp_next
    sty gd_found_x
    lda cc_y
    sta gd_found_y
    lda #1
    sta fp_found
    lda fp_first
    bne fp_done
fp_next:
    iny
    cpy GD_W
    bcc fp_cell
    jsr next_cave_row
    bcc fp_row
fp_done:
    lda fp_found
    rts

; gd_clear_moved(): all of moved[] (CAVE_SIZE) DIR_NONE
DIR_NONE = 4
CAVE_SIZE = 880
.global gd_clear_moved
.section .text.gd_clear_moved,"ax",@progbits
gd_clear_moved:
    lda #DIR_NONE
    ldx #0
cm_pages:
    sta moved, x
    sta moved+256, x
    sta moved+512, x
    inx
    bne cm_pages
    ldx #CAVE_SIZE - 768
cm_rest:
    sta moved+767, x            ; moved[768 .. CAVE_SIZE - 1], from the end
    dex
    bne cm_rest
    rts
