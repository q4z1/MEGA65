; Smaragd Dash: text in 45GS02 assembly, smaller than llvm-mos makes it
; (and the big letters' loops were miscompiled twice in C).
;
; big_glyph(shadow, bits, out): a big letter (video_big_text, src/video.c)
;   from the 16 rows of its 8x16 glyph (bits), twice as wide and high, into
;   out: 512 bytes, the left and then the right 8 pixels of its 32 rows.
;   A pixel that is set gets the row's colour (title_row[row / 2]), one
;   that is not but has a set one 2 pixels up and left gets the shadow
;   colour, the others 0.
; to_digits(out, v, n): the last n digits of v (32 bits) at out, without
;   division: each power of ten is taken away as often as it goes.
;
; As llvm-mos passes them: shadow in A, bits in __rc2-__rc3, out in
; __rc4-__rc5; out in __rc2-__rc3, v in A, X, __rc4, __rc5, n in __rc6.
; They change X, Y and __rc4-__rc8, which a caller does not keep. Z stays 0.

.global big_glyph, to_digits

.section .bss.text_s,"aw",@nobits
bg_sh:  .fill 1                 ; the shadow's colour
bg_b:   .fill 16                ; the glyph's rows
bg_r:   .fill 1                 ; the big letter's row, 0-31
bg_x0:  .fill 1                 ; the strip's first pixel: 0 or 8
td_v:   .fill 4
td_t:   .fill 3

.section .rodata.text_s,"a",@progbits
maskx:                          ; the glyph's bit of big pixel x (0-15)
    .byte $80, $80, $40, $40, $20, $20, $10, $10, $08, $08, $04, $04, $02, $02, $01, $01
pow_0:                          ; 10 to the power 0-6, byte by byte (the
                                ; fourth is 0)
    .byte $01, $0a, $64, $e8, $10, $a0, $40
pow_1:
    .byte $00, $00, $00, $03, $27, $86, $42
pow_2:
    .byte $00, $00, $00, $00, $00, $01, $0f

.section .text.big_glyph,"ax",@progbits
big_glyph:
    sta bg_sh
    ldy #15
1:  lda (__rc2),y
    sta bg_b,y
    dey
    bpl 1b
    lda #0
    sta bg_x0
strip:
    ldy #0                      ; where in out: 32 rows of 8 pixels
    sty bg_r
row:
    lda bg_r
    lsr
    tax
    lda bg_b,x
    sta __rc6                   ; the row's bits
    lda title_row,x
    sta __rc8                   ; its colour
    lda #0
    ldx bg_r
    cpx #2
    bcc 2f
    lda bg_r                    ; the bits 2 rows up, one bit (2 pixels) right
    sec
    sbc #2
    lsr
    tax
    lda bg_b,x
    lsr
2:  sta __rc7
    ldx bg_x0
pixel:
    lda maskx,x
    and __rc6
    beq 3f
    lda __rc8
    bra 4f
3:  lda maskx,x
    and __rc7
    beq 4f                      ; 0
    lda bg_sh
4:  sta (__rc4),y
    iny
    inx
    txa
    and #7
    bne pixel
    inc bg_r
    lda bg_r
    cmp #32
    bne row
    lda bg_x0                   ; the right strip, 256 bytes on
    bne 5f
    inc __rc5
    lda #8
    sta bg_x0
    bra strip
5:  rts

.section .text.to_digits,"ax",@progbits
to_digits:
    sta td_v
    stx td_v+1
    lda __rc4
    sta td_v+2
    lda __rc5
    sta td_v+3
    ldy __rc6
    jsr take_away               ; what is above the n digits goes
1:  dey
    bmi 2f
    jsr take_away
    txa
    ora #$30                    ; '0'
    sta (__rc2),z
    inw __rc2
    bra 1b
2:  rts

; td_v less 10 to the power Y as often as it goes: that often in X
take_away:
    ldx #0
1:  sec
    lda td_v
    sbc pow_0,y
    sta td_t
    lda td_v+1
    sbc pow_1,y
    sta td_t+1
    lda td_v+2
    sbc pow_2,y
    sta td_t+2
    lda td_v+3
    sbc #0
    bcc 2f
    sta td_v+3
    lda td_t+2
    sta td_v+2
    lda td_t+1
    sta td_v+1
    lda td_t
    sta td_v
    inx
    bra 1b
2:  rts
