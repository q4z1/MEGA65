; Lotus Run: road_row_draw (road_rows.h) in 45GS02 assembly - one road
; line pattern drawn out in attic RAM, as road_row (road_rows.c) has it, in
; the colours of both stripe sets; road_pixels.c draws every pattern with
; it at the start. tests/check_render.c checks it against road_row.
;
; The edges come from the hardware multiplier; every run's whole pixels
; become a DMA fill per set, written straight into dma.c's list; the pixels
; it shares with other runs gather what covers them (rr_cover, in 1/64) and
; become a fill of one pixel in a mixed shade. Scratch: __rc2-__rc11, kept
; in rr_save while dma_flush (C) runs.

.include "offsets.inc"

.global road_row_draw, rr_w2, rr_v, rr_p, rr_colours, rr_colours_b, rr_dst, rr_dst_b, rr_start, rr_len

MULTINA = $D770
MULTINB = $D774
MULTOUT = $D778

tb   = __rc2                    ; rr_colours_b
ep   = __rc4                    ; the variant's road_edge
cp   = __rc6                    ; the variant's road_colour
tp   = __rc8                    ; rr_colours
jp   = __rc10                   ; where the next job goes

FILL_JOB = 16                   ; bytes of a fill job

.section .bss.road_rows_s,"aw",@nobits
rr_w2:      .fill 2             ; in: the width (scale >> 3)
rr_v:       .fill 1             ; the variant
rr_p:       .fill 1             ; the phase
rr_colours: .fill 2             ; the colour of each shade (ROAD_SHADES), set A
rr_colours_b: .fill 2           ; ... set B
rr_dst:     .fill 4             ; where the pattern goes, set A (moved on past it)
rr_dst_b:   .fill 4             ; ... set B
rr_start:   .fill 2             ; out: the pattern's start, its length
rr_len:     .fill 2
rr_runs:    .fill 1
rr_e:       .fill 2 * (ROAD_RUNS_MAX + 1)   ; the edges, in 1/64 pixel
rr_k:       .fill 1
rr_a:       .fill 2             ; the run: from a to z, shade c
rr_z:       .fill 2
rr_c:       .fill 1
rr_pa:      .fill 2             ; their pixels
rr_pz:      .fill 2
rr_t:       .fill 3
rr_cover:   .fill 4             ; the pixel being gathered: of each shade
rr_x:       .fill 1             ; the shade covering most, second most
rr_y:       .fill 1
rr_n:       .fill 2             ; pixels of a fill
rr_save:    .fill 10            ; __rc2-__rc11 while dma_flush runs

.section .text.road_rows_s,"ax",@progbits

; rr_t (24 bits, signed) / 64, rounded down, into A (low) and X (high)
div64:
    asl rr_t
    rol rr_t + 1
    rol rr_t + 2
    asl rr_t
    rol rr_t + 1
    rol rr_t + 2
    lda rr_t + 1
    ldx rr_t + 2
    rts

; The 16 bits at rr_e + Y (signed) into rr_t, 24 bits
edge_t:
    lda rr_e, y
    sta rr_t
    lda rr_e + 1, y
    sta rr_t + 1
    ldx #0
    cmp #$80
    bcc 1f
    dex
1:
    stx rr_t + 2
    rts

road_row_draw:
    ; the variant's tables
    lda #<road_edge
    sta ep
    lda #>road_edge
    sta ep + 1
    lda #<road_colour
    sta cp
    lda #>road_colour
    sta cp + 1
    ldx rr_v
    lda road_runs, x
    sta rr_runs
    txa
    beq 1f
    clc
    lda ep
    adc #ROAD_RUNS_MAX + 1
    sta ep
    bcc 2f
    inc ep + 1
2:
    clc
    lda cp
    adc #ROAD_RUNS_MAX
    sta cp
    bcc 1f
    inc cp + 1
1:
    lda rr_colours
    sta tp
    lda rr_colours + 1
    sta tp + 1
    lda rr_colours_b
    sta tb
    lda rr_colours_b + 1
    sta tb + 1

    ; edge k = c * w2 + c / 2 (rounded down) + ROAD_EDGE_BASE
    lda rr_w2
    sta MULTINB
    lda rr_w2 + 1
    sta MULTINB + 1
    lda #0
    sta MULTINB + 2
    sta MULTINB + 3
    ldy #0
    ldx #0
.Ledge:
    lda (ep), y
    sta MULTINA
    cmp #$80
    lda #0
    bcc 3f
    lda #$FF
3:
    sta MULTINA + 1
    sta MULTINA + 2
    sta MULTINA + 3
    sta rr_t + 1                ; c / 2: high byte
    lda (ep), y
    cmp #$80
    ror
    clc
    adc MULTOUT
    sta rr_t
    lda rr_t + 1
    adc MULTOUT + 1
    sta rr_t + 1
    clc
    lda rr_t
    adc #<ROAD_EDGE_BASE
    sta rr_e, x
    lda rr_t + 1
    adc #>ROAD_EDGE_BASE
    sta rr_e + 1, x
    inx
    inx
    iny
    tya
    dec
    cmp rr_runs
    bne .Ledge

    ; the start: (edge 0 - 48) / 64; the end: (last edge + 63) / 64
    ldy #0
    jsr edge_t
    sec
    lda rr_t
    sbc #48
    sta rr_t
    lda rr_t + 1
    sbc #0
    sta rr_t + 1
    lda rr_t + 2
    sbc #0
    sta rr_t + 2
    jsr div64
    sta rr_start
    stx rr_start + 1
    lda rr_runs
    asl
    tay
    jsr edge_t
    clc
    lda rr_t
    adc #63
    sta rr_t
    lda rr_t + 1
    adc #0
    sta rr_t + 1
    lda rr_t + 2
    adc #0
    sta rr_t + 2
    jsr div64
    sec
    sbc rr_start
    sta rr_len
    txa
    sbc rr_start + 1
    sta rr_len + 1

    ; the edges from the start, phase p further left: - (start * 64 + 16 * p)
    lda rr_start
    sta rr_t
    lda rr_start + 1
    ldx #6
4:
    asl rr_t
    rol
    dex
    bne 4b
    sta rr_t + 1
    lda rr_p
    asl
    asl
    asl
    asl
    clc
    adc rr_t
    sta rr_t
    bcc 5f
    inc rr_t + 1
5:
    ldx #0
6:
    sec
    lda rr_e, x
    sbc rr_t
    sta rr_e, x
    lda rr_e + 1, x
    sbc rr_t + 1
    sta rr_e + 1, x
    inx
    inx
    txa
    lsr
    dec
    cmp rr_runs
    bne 6b

    ; the runs: grass up to edge 0, run k from edge k to k + 1, grass to
    ; the end
    lda #0
    sta rr_cover
    sta rr_cover + 1
    sta rr_cover + 2
    sta rr_cover + 3
    sta rr_a
    sta rr_a + 1
    sta rr_k
.Lrun:
    ldy rr_k
    lda #0                      ; grass before edge 0 and after the last
    cpy #0
    beq 7f
    cpy rr_runs
    beq 8f
    bcs 7f
8:
    dey
    lda (cp), y
7:
    sta rr_c
    ; its end: edge k, or the pattern's end
    lda rr_k
    cmp rr_runs
    beq 9f
    bcs 10f
9:
    asl
    tax
    lda rr_e, x
    sta rr_z
    lda rr_e + 1, x
    sta rr_z + 1
    bra 11f
10:
    lda rr_len
    sta rr_z
    lda rr_len + 1
    ldx #6
12:
    asl rr_z
    rol
    dex
    bne 12b
    sta rr_z + 1
11:
    jsr run
    lda rr_z
    sta rr_a
    lda rr_z + 1
    sta rr_a + 1
    inc rr_k
    lda rr_runs
    inc
    cmp rr_k
    bcs .Lrun
    rts

; Shade rr_c from rr_a to rr_z
run:
    lda rr_a
    cmp rr_z
    bne 1f
    lda rr_a + 1
    cmp rr_z + 1
    bne 1f
    rts
1:
    ; their pixels
    lda rr_a
    sta rr_t
    lda rr_a + 1
    sta rr_t + 1
    lda #0
    sta rr_t + 2
    jsr div64
    sta rr_pa
    stx rr_pa + 1
    lda rr_z
    sta rr_t
    lda rr_z + 1
    sta rr_t + 1
    lda #0
    sta rr_t + 2
    jsr div64
    sta rr_pz
    stx rr_pz + 1
    ; within one pixel: gathered
    cmp rr_pa
    bne 2f
    cpx rr_pa + 1
    bne 2f
    ldx rr_c
    sec
    lda rr_z
    sbc rr_a
    clc
    adc rr_cover, x
    sta rr_cover, x
    rts
2:
    ; the rest of a pixel begun: gathered, and the pixel done
    lda rr_a
    and #63
    beq 3f
    eor #$FF
    sec
    adc #64                     ; 64 - (a & 63)
    ldx rr_c
    clc
    adc rr_cover, x
    sta rr_cover, x
    jsr mixed
    inc rr_pa
    bne 3f
    inc rr_pa + 1
3:
    ; whole pixels: pa .. pz - 1
    sec
    lda rr_pz
    sbc rr_pa
    sta rr_n
    lda rr_pz + 1
    sbc rr_pa + 1
    sta rr_n + 1
    ora rr_n
    beq 7f
    ldy rr_c
    jsr fill
7:
    ; a pixel begun
    lda rr_z
    and #63
    beq 8f
    ldx rr_c
    clc
    adc rr_cover, x
    sta rr_cover, x
8:
    rts

; The pixel gathered: the shade covering most (rr_x, the first of equals)
; alone, or mixed with the one covering second most (rr_y) - to the
; quarter; into the pattern, rr_cover cleared
mixed:
    ldx #0
    ldy #1
1:
    lda rr_cover, x
    cmp rr_cover, y
    bcs 2f
    tya
    tax
2:
    iny
    cpy #4
    bne 1b
    stx rr_x
    ldx #1
    lda rr_x
    beq 3f
    ldx #0
3:
    ldy #0
4:
    cpy rr_x
    beq 5f
    lda rr_cover, x
    cmp rr_cover, y
    bcs 5f
    tya
    tax
5:
    iny
    cpy #4
    bne 4b
    stx rr_y
    ; quarters of the second: (cover + 8) / 16, 0-2
    lda rr_cover, x
    clc
    adc #8
    lsr
    lsr
    lsr
    lsr
    bne 6f
    ldy rr_x                    ; none: the first alone
    bra 9f
6:
    sta rr_t                    ; quarters
    ; the pair (i, j), i < j: i ? i + j : j - 1
    lda rr_x
    cmp rr_y
    bcc 7f
    ; the first is j: 3 - quarters of j's share
    lda #3
    sec
    sbc rr_t
    sta rr_t + 1
    lda rr_y
    ldx rr_x
    bra 8f
7:
    ; the second is j: quarters - 1
    lda rr_t
    dec
    sta rr_t + 1
    lda rr_x
    ldx rr_y
8:
    ; A = i, X = j
    stx rr_t + 2
    cmp #0
    beq 10f
    clc
    adc rr_t + 2
    bra 11f
10:
    txa
    dec
11:
    sta rr_t                    ; pair
    asl
    clc
    adc rr_t                    ; 3 * pair
    adc rr_t + 1
    adc #ROAD_MIX
    tay
9:
    lda #1
    sta rr_n
    lda #0
    sta rr_n + 1
    jsr fill
    lda #0
    sta rr_cover
    sta rr_cover + 1
    sta rr_cover + 2
    sta rr_cover + 3
    rts

; rr_n pixels of shade Y, at rr_dst in set A's colour and rr_dst_b in set
; B's; both moved on
fill:
    lda (tp), y
    ldx #0
    jsr fill_job
    lda (tb), y
    ldx #4
    jsr fill_job
    ldx #0
1:
    clc
    lda rr_dst, x
    adc rr_n
    sta rr_dst, x
    lda rr_dst + 1, x
    adc rr_n + 1
    sta rr_dst + 1, x
    lda rr_dst + 2, x
    adc #0
    sta rr_dst + 2, x
    lda rr_dst + 3, x
    adc #0
    sta rr_dst + 3, x
    inx
    inx
    inx
    inx
    cpx #8
    bne 1b
    rts

; A fill job into dma.c's list: rr_n bytes of colour A at the address at
; rr_dst + X (28 bits); Y kept
fill_job:
    sta rr_t
    sty rr_t + 1
    ; room for it: dma_p + FILL_JOB <= DMA_LIST_END, or the list is run
    clc
    lda dma_p
    adc #FILL_JOB
    tay
    lda dma_p + 1
    adc #0
    cmp #>DMA_LIST_END
    bcc 2f
    bne 1f
    cpy #<DMA_LIST_END
    bcc 2f
    beq 2f
1:
    phx
    ldy #9
3:
    lda tb, y
    sta rr_save, y
    dey
    bpl 3b
    jsr dma_flush
    ldy #9
4:
    lda rr_save, y
    sta tb, y
    dey
    bpl 4b
    plx
2:
    lda dma_p
    sta jp
    lda dma_p + 1
    sta jp + 1
    ldy #0
    lda #$0A                    ; F018A jobs
    sta (jp), y
    iny
    lda #$06                    ; no transparency
    sta (jp), y
    iny
    lda #$81                    ; target megabyte
    sta (jp), y
    iny
    lda rr_dst + 3, x
    asl
    asl
    asl
    asl
    sta rr_t + 2
    lda rr_dst + 2, x
    lsr
    lsr
    lsr
    lsr
    ora rr_t + 2
    sta (jp), y
    iny
    lda #0                      ; end of options
    sta (jp), y
    iny
    lda #$07                    ; fill, chained
    sta (jp), y
    iny
    lda rr_n
    sta (jp), y
    iny
    lda rr_n + 1
    sta (jp), y
    iny
    lda rr_t                    ; the colour
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    sta (jp), y
    iny
    lda rr_dst, x
    sta (jp), y
    iny
    lda rr_dst + 1, x
    sta (jp), y
    iny
    lda rr_dst + 2, x
    and #$0F
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    sta (jp), y
    ; written: the command byte at jp + 5, the list on past it
    clc
    lda jp
    adc #5
    sta dma_last_cmd
    lda jp + 1
    adc #0
    sta dma_last_cmd + 1
    clc
    lda jp
    adc #FILL_JOB
    sta dma_p
    lda jp + 1
    adc #0
    sta dma_p + 1
    ldy rr_t + 1
    rts
