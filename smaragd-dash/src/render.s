; Smaragd Dash: the DMA jobs of a frame's playfield in 45GS02 assembly - the
; same jobs as the C loop in video_render (src/video.c, built with
; -DRENDER_C), byte for byte; tests/test_render.sh compares the screencasts
; of both, frame by frame.
;
; render_columns(): for each of the 40 columns of 8 pixels, the copies of
; its tiles from the top of the view down: the first tile from its row
; rd_yo8 / 8 on (rd_first8 bytes), rd_nfull whole tiles (128 bytes), and the
; top of one more (rd_last8 bytes, if not 0). A column outside the cave
; gets the empty tile. The jobs go from rd_p on (dma.c's list); rd_p is
; where the next would go afterwards. src/video.c sets the rd_* values.
;
; Scratch: __rc2-__rc5, which a C caller does not keep. Z stays 0.

.global render_columns
.global rd_p, rd_top, rd_wc, rd_yo8, rd_first8, rd_nfull, rd_last8, rd_bank, rd_gfx_bank, rd_space

COLS = 40
CAVE_W = 40
FB_COL = 22 * 64                ; bytes per framebuffer column

p  = __rc2                      ; where the job goes
tp = __rc4                      ; the tile in tiles[]

.section .bss.render_s,"aw",@nobits
rd_p:        .fill 2
rd_top:      .fill 2            ; tiles[] at the top row of the view
rd_wc:       .fill 1            ; the cave's character column of column 0 (signed)
rd_yo8:      .fill 1            ; the top tile's first row * 8
rd_first8:   .fill 1            ; its bytes
rd_nfull:    .fill 1
rd_last8:    .fill 1
rd_bank:     .fill 1            ; the framebuffer's
rd_gfx_bank: .fill 1            ; the tiles'
rd_space:    .fill 1            ; the empty tile
rc_col:      .fill 1
rc_wc:       .fill 1
rc_out:      .fill 1            ; not 0: the column is outside the cave
rc_par:      .fill 1            ; 0 or 128: the tile's left or right half
rc_k:        .fill 1
rc_dcol:     .fill 2
jd:          .fill 2            ; the job's target
jl:          .fill 1            ; and length

.section .text.render_columns,"ax",@progbits
render_columns:
    lda rd_p
    sta p
    lda rd_p+1
    sta p+1
    lda rd_wc
    sta rc_wc
    lda #0
    sta rc_dcol
    sta rc_dcol+1
    lda #COLS
    sta rc_col

col_loop:
    lda rc_wc
    bmi col_outside             ; wc < 0
    cmp #CAVE_W * 2
    bcs col_outside             ; wc >= CAVE_W * 2
    lsr                         ; tp = rd_top + wc / 2, the half from wc's bit 0
    clc
    adc rd_top
    sta tp
    lda rd_top+1
    adc #0
    sta tp+1
    lda rc_wc
    lsr
    lda #0
    ror
    sta rc_par
    lda #0
    sta rc_out
    bra col_jobs
col_outside:
    lda #1
    sta rc_out

col_jobs:
    ; the top tile: from its row yo on, to the column's top
    lda rc_dcol
    sta jd
    lda rc_dcol+1
    sta jd+1
    lda rd_first8
    sta jl
    lda rc_out
    bne first_out
    ldy #0
    lda (tp), y
    tax
    lda rc_par
    clc
    adc rd_yo8
    bra first_job
first_out:
    ldx rd_space
    lda #0
first_job:
    jsr job
    lda rd_first8               ; the next one's target: below it
    clc
    adc rc_dcol
    sta jd
    lda rc_dcol+1
    adc #0
    sta jd+1

    ; the whole tiles
    lda #128
    sta jl
    lda rd_nfull
    sta rc_k
    beq last_tile
full_tile:
    jsr tile_job
    lda jd
    clc
    adc #128
    sta jd
    bcc full_next
    inc jd+1
full_next:
    dec rc_k
    bne full_tile

    ; the top of one more
last_tile:
    lda rd_last8
    beq col_next
    sta jl
    jsr tile_job

col_next:
    clc
    lda rc_dcol
    adc #<FB_COL
    sta rc_dcol
    lda rc_dcol+1
    adc #>FB_COL
    sta rc_dcol+1
    inc rc_wc
    dec rc_col
    bne col_loop

    lda p
    sta rd_p
    lda p+1
    sta rd_p+1
    rts

; the job of the tile one row down (tp += CAVE_W), whole from its top
tile_job:
    lda rc_out
    bne tile_out
    clc
    lda tp
    adc #CAVE_W
    sta tp
    bcc tile_in
    inc tp+1
tile_in:
    ldy #0
    lda (tp), y
    tax
    lda rc_par
    bra job
tile_out:
    ldx rd_space
    lda #0

; a copy job at p (12 bytes, as video.c's JOB): from tile X, byte A on,
; jl bytes, to jd in the framebuffer; p += 12
job:
    ldy #3
    sta (p), y                  ; source: A, X, the tiles' bank
    iny
    txa
    sta (p), y
    iny
    lda rd_gfx_bank
    sta (p), y
    iny
    lda jd                      ; target
    sta (p), y
    iny
    lda jd+1
    sta (p), y
    iny
    lda rd_bank
    sta (p), y
    lda #0                      ; the end of the next job's options
    iny
    sta (p), y
    iny
    sta (p), y
    iny
    sta (p), y
    ldy #2                      ; length
    sta (p), y
    dey
    lda jl
    sta (p), y
    dey
    lda #4                      ; copy, chained
    sta (p), y
    clc
    lda p
    adc #12
    sta p
    bcc job_done
    inc p+1
job_done:
    rts
