; Smaragd Dash: covering and uncovering the cave in 45GS02 assembly - the
; same as cover_cells_c in src/main.c, which tests/test_asm.sh compares it
; with (-DASM_CHECK).
;
; cover_cells(on, per_row, bits): in each row of the cave per_row random
; cells (rnd() * CAVE_W / 256) covered (on) or uncovered (0) - a bit per
; cell in bits, cell i in bit i & 7 of byte i / 8. on in A, per_row in X,
; bits in __rc2-__rc3, as llvm-mos passes them. It calls rnd() and
; changes A, X, Y and __rc2-__rc3. Z stays 0.

.global cover_cells

CAVE_W = 40
CAVE_H = 22

ptr = __rc2

.section .bss.cover_s,"aw",@nobits
cc_on:   .fill 1
cc_per:  .fill 1
cc_bits: .fill 2
cc_row:  .fill 2                ; the row's first cell
cc_y:    .fill 1                ; rows left
cc_k:    .fill 1                ; cells left in the row
cc_t:    .fill 2
cc_m:    .fill 1                ; the cell's bit

.section .rodata.cover_s,"a",@progbits
bit_of:
    .byte 1, 2, 4, 8, 16, 32, 64, 128

.section .text.cover_s,"ax",@progbits
cover_cells:
    sta cc_on
    stx cc_per
    lda __rc2
    sta cc_bits
    lda __rc3
    sta cc_bits+1
    stz cc_row
    stz cc_row+1
    lda #CAVE_H
    sta cc_y
1:  lda cc_per
    sta cc_k
2:  jsr rnd                     ; the column: rnd * 40 / 256 = rnd * 5 / 32
    sta cc_t
    stz cc_t+1
    asl
    rol cc_t+1
    asl
    rol cc_t+1
    clc
    adc cc_t
    sta cc_t
    bcc 3f
    inc cc_t+1
3:  lsr
    lsr
    lsr
    lsr
    lsr
    sta cc_m
    lda cc_t+1
    asl
    asl
    asl
    ora cc_m
    clc                         ; the cell
    adc cc_row
    sta cc_t
    lda cc_row+1
    adc #0
    sta cc_t+1
    lda cc_t                    ; its bit
    and #7
    tax
    lda bit_of,x
    sta cc_m
    ldx #3                      ; its byte
4:  lsr cc_t+1
    ror cc_t
    dex
    bne 4b
    clc
    lda cc_bits
    adc cc_t
    sta ptr
    lda cc_bits+1
    adc cc_t+1
    sta ptr+1
    lda cc_on
    beq 5f
    lda (ptr),z
    ora cc_m
    bra 6f
5:  lda cc_m
    eor #$FF
    and (ptr),z
6:  sta (ptr),z
    dec cc_k
    bne 2b
    clc                         ; the next row
    lda cc_row
    adc #CAVE_W
    sta cc_row
    bcc 7f
    inc cc_row+1
7:  dec cc_y
    bne 1b
    rts
