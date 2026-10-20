; Lotus Run: the renderer's inner loops in 45GS02 assembly - the same
; as their references in C (src/ref/); tests/check_render.c checks these
; against them on the MEGA65.
;
; road_draw (road_draw.h): every road line is a fill with its grass, then
; one DMA copy of its pattern, drawn out in attic RAM (ROADPIX, road_pixels.c;
; for stripe set B from ROADPIX_B on), cut to the picture. The patterns'
; index (ROADIDX, bank 1) is read through a 32-bit pointer.
;
; sprites_draw (sprites.h): every visible row of a sprite becomes a DMA copy
; from attic RAM that leaves out SPR_CLEAR.
;
; Both write their jobs straight into dma.c's list. Scratch: llvm-mos'
; caller-saved registers __rc2-__rc19; dma_flush (C) is only called where
; nothing is kept in them. Z is 0 whenever C code runs.

.include "offsets.inc"

.global road_draw, sprites_draw

MULTINA = $D770
MULTINB = $D774
MULTOUT = $D778

COL_GRASS = 12
FILL_JOB  = 16                  ; bytes of a fill job (as dma_fill_low's)
LINE_JOB  = 18                  ; bytes of a road line's copy job

jp   = __rc2                    ; where the next job goes
pat  = __rc4                    ; the line's index entry: 4-byte pointer
xx   = __rc8                    ; where the pattern starts on screen (signed)
endx = __rc10                   ; where it ends
row  = __rc12                   ; the screen row's offset in PICTURE: y * 320
x0   = __rc14                   ; the first column drawn
lp   = __rc18                   ; pointer

.section .bss.render_s,"aw",@nobits
rd_l:       .fill 1             ; the line
rd_y:       .fill 1             ; its screen row
rd_shown:   .fill 1             ; the line's stripe set (0, 4)
rd_col:     .fill 1             ; its grass colour
rd_lp:      .fill 2             ; &render_lines[rd_l]
ln_x:       .fill 2             ; the line's RoadLine
ln_scale:   .fill 2
ln_depth:   .fill 2
rd_len:     .fill 2             ; pixels to copy
rd_src:     .fill 3             ; from there (offset in ATTIC)

sd_i:       .fill 1             ; the sprite
sd_bank:    .fill 1             ; its Sprite
sd_image:   .fill 1
sd_x:       .fill 2
sd_y:       .fill 2
sd_clip:    .fill 2
sd_w:       .fill 1             ; its image's size
sd_h:       .fill 1
sd_top:     .fill 2             ; its rows top .. bottom
sd_bottom:  .fill 2
sd_yy:      .fill 2             ; the first row drawn
sd_x0:      .fill 2             ; the columns drawn x0 .. x1 - 1
sd_x1:      .fill 2
sd_len:     .fill 2
sd_rows:    .fill 1
sd_src:     .fill 4             ; the row's pixels
sd_dst:     .fill 2             ; where they go in PICTURE
sd_t:       .fill 2

.section .text.render_s,"ax",@progbits

; ---------------------------------------------------------------- the road

; A/X = A * 320 (A < 205): A * 256 + A * 64
times320:
    tax
    lsr
    lsr
    sta x0
    txa
    clc
    adc x0
    sta x0
    txa
    and #3
    asl
    asl
    asl
    asl
    asl
    asl
    ldx x0
    rts

; Room in the list for A more bytes of jobs; jp = where they go
room:
    clc
    adc dma_p
    tax
    lda dma_p + 1
    adc #0
    cmp #>DMA_LIST_END
    bcc 1f
    bne 2f
    cpx #<DMA_LIST_END
    bcc 1f
    beq 1f
2:
    jsr dma_flush
1:
    lda dma_p
    sta jp
    lda dma_p + 1
    sta jp + 1
    rts

road_draw:
    lda road_top
    sta rd_l
    clc
    adc view_y0
    sta rd_y
    ; rd_lp = render_lines + 6 * road_top
    lda road_top
    sta rd_lp
    lda #0
    sta rd_lp + 1
    asl rd_lp
    rol rd_lp + 1
    lda rd_lp
    ldx rd_lp + 1
    asl rd_lp
    rol rd_lp + 1
    clc
    adc rd_lp
    sta rd_lp
    txa
    adc rd_lp + 1
    sta rd_lp + 1
    clc
    lda rd_lp
    adc #<render_lines
    sta rd_lp
    lda rd_lp + 1
    adc #>render_lines
    sta rd_lp + 1

.Lline:
    lda rd_l
    cmp view_lines              ; at most 200 lines: the low byte
    bcc 1f
    ldz #0
    rts
1:
    ; the line
    lda rd_lp
    sta lp
    lda rd_lp + 1
    sta lp + 1
    ldy #RL_x
    lda (lp), y
    sta ln_x
    iny
    lda (lp), y
    sta ln_x + 1
    ldy #RL_scale
    lda (lp), y
    sta ln_scale
    iny
    lda (lp), y
    sta ln_scale + 1
    ldy #RL_depth
    lda (lp), y
    sta ln_depth
    iny
    lda (lp), y
    sta ln_depth + 1

    ; the stripe set: bit 10 of depth + phase; the row in its grass
    clc
    lda ln_depth
    adc road_phase
    lda ln_depth + 1
    adc road_phase + 1
    and #4
    sta rd_shown
    beq 2f
    lda #COL_SET_B
    bra 3f
2:
    lda #COL_GRASS
3:
    sta rd_col
    lda rd_y
    jsr times320
    sta row
    stx row + 1
    lda #FILL_JOB
    jsr room
    ldy #0
    lda #$0A                    ; F018A jobs
    sta (jp), y
    iny
    lda #$06                    ; no transparency
    sta (jp), y
    iny
    lda #$81                    ; target megabyte 0
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    sta (jp), y                 ; end of options
    iny
    lda #$07                    ; fill, chained
    sta (jp), y
    iny
    lda #<FB_W
    sta (jp), y
    iny
    lda #>FB_W
    sta (jp), y
    iny
    lda rd_col
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    sta (jp), y
    iny
    lda row
    sta (jp), y
    iny
    lda row + 1
    sta (jp), y
    iny
    lda #((PICTURE >> 16) & $0F)
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    sta (jp), y
    lda #5
    ldx #FILL_JOB
    jsr job_done

    ; the index entry of the pattern of width scale >> 4 and the line's
    ; variant: ROADIDX + 8 * (2 * w + (x & 1)) = ROADIDX + 16 * w + 8 * v
    lda ln_scale
    and #$F0
    sta pat
    lda ln_x
    and #1
    asl
    asl
    asl
    ora pat
    clc
    adc #<ROADIDX
    sta pat
    lda ln_scale + 1
    adc #>ROADIDX
    sta pat + 1
    lda #((ROADIDX >> 16) & $FF)
    adc #0
    sta pat + 2
    lda #0
    sta pat + 3

    ; where it lands: 159 - (scale * 2 * (x + lateral8)) >> 16 + its start
    lda ln_scale
    asl
    sta MULTINA
    lda ln_scale + 1
    rol
    sta MULTINA + 1
    lda #0
    sta MULTINA + 2
    sta MULTINA + 3
    clc
    lda ln_x
    adc road_lateral8
    sta MULTINB
    lda ln_x + 1
    adc road_lateral8 + 1
    sta MULTINB + 1
    ldx #0
    cmp #$80
    bcc 3f
    dex
3:
    stx MULTINB + 2
    stx MULTINB + 3
    sec
    lda #159
    sbc MULTOUT + 2
    sta xx
    lda #0
    sbc MULTOUT + 3
    sta xx + 1
    ldz #0
    clc
    lda xx
    adc [pat], z
    sta xx
    inz
    lda xx + 1
    adc [pat], z
    sta xx + 1
    inz
    ; its end: + length
    clc
    lda xx
    adc [pat], z
    sta endx
    inz
    lda xx + 1
    adc [pat], z
    sta endx + 1
    inz
    lda [pat], z
    sta rd_src
    inz
    lda [pat], z
    sta rd_src + 1
    inz
    lda [pat], z
    sta rd_src + 2
    ldz #0
    ; set B: the patterns in its colours
    lda rd_shown
    beq 9f
    clc
    lda rd_src + 1
    adc #((ROADPIX_B >> 8) & $FF)
    sta rd_src + 1
    lda rd_src + 2
    adc #((ROADPIX_B >> 16) & $FF)
    sta rd_src + 2
9:

    ; nothing to draw if it starts at 320 or more or ends at 0 or less
    lda xx + 1
    bmi 4f
    cmp #>FB_W
    bcc 4f
    bne .Lnext
    lda xx
    cmp #<FB_W
    bcs .Lnext
4:
    lda endx + 1
    bmi .Lnext
    ora endx
    beq .Lnext
    ; from column max(x, 0), skipping as many of its pixels
    lda xx + 1
    bpl 5f
    sec
    lda rd_src
    sbc xx
    sta rd_src
    lda rd_src + 1
    sbc xx + 1
    sta rd_src + 1
    lda rd_src + 2
    sbc #$FF
    sta rd_src + 2
    lda #0
    sta xx
    sta xx + 1
5:
    ; to column min(end, 320)
    lda endx + 1
    cmp #>FB_W
    bcc 6f
    bne 7f
    lda endx
    cmp #<FB_W
    bcc 6f
7:
    lda #<FB_W
    sta endx
    lda #>FB_W
    sta endx + 1
6:
    sec
    lda endx
    sbc xx
    sta rd_len
    lda endx + 1
    sbc xx + 1
    sta rd_len + 1

    lda rd_y
    jsr times320
    clc
    adc xx
    sta row
    txa
    adc xx + 1
    sta row + 1
    lda #LINE_JOB
    jsr room
    ldy #0
    lda #$0A                    ; F018A jobs
    sta (jp), y
    iny
    lda #$80                    ; source megabyte: attic RAM
    sta (jp), y
    iny
    lda rd_src + 2
    lsr
    lsr
    lsr
    lsr
    ora #((ATTIC >> 20) & $FF)
    sta (jp), y
    iny
    lda #$81                    ; target megabyte 0
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    lda #$06                    ; no transparency
    sta (jp), y
    iny
    lda #0                      ; end of options
    sta (jp), y
    iny
    lda #$04                    ; copy, chained
    sta (jp), y
    iny
    lda rd_len
    sta (jp), y
    iny
    lda rd_len + 1
    sta (jp), y
    iny
    lda rd_src
    sta (jp), y
    iny
    lda rd_src + 1
    sta (jp), y
    iny
    lda rd_src + 2
    and #$0F
    sta (jp), y
    iny
    lda row
    sta (jp), y
    iny
    lda row + 1
    sta (jp), y
    iny
    lda #((PICTURE >> 16) & $0F)
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    sta (jp), y
    lda #7
    ldx #LINE_JOB
    jsr job_done

.Lnext:
    inc rd_l
    inc rd_y
    clc
    lda rd_lp
    adc #ROADLINE_SIZE
    sta rd_lp
    bcc 8f
    inc rd_lp + 1
8:
    jmp .Lline

; The job at jp is written: its command byte is at jp + A, its length X
job_done:
    clc
    adc jp
    sta dma_last_cmd
    lda jp + 1
    adc #0
    sta dma_last_cmd + 1
    txa
    clc
    adc jp
    sta dma_p
    lda jp + 1
    adc #0
    sta dma_p + 1
    rts

; ---------------------------------------------------------------- sprites

COPY_JOB = 20                   ; bytes of a transparent copy job

sprites_draw:
    lda #0
    sta sd_i
.Lsprite:
    lda sd_i
    cmp sprite_count
    bcc 1f
    ldz #0
    rts
1:
    ; the Sprite
    sta lp
    lda #0
    sta lp + 1
    asl lp
    rol lp + 1
    asl lp
    rol lp + 1
    asl lp
    rol lp + 1
    clc
    lda lp
    adc #<sprite_list
    sta lp
    lda lp + 1
    adc #>sprite_list
    sta lp + 1
    ldy #SP_bank
    lda (lp), y
    sta sd_bank
    ldy #SP_image
    lda (lp), y
    sta sd_image
    ldy #SP_x
    lda (lp), y
    sta sd_x
    iny
    lda (lp), y
    sta sd_x + 1
    ldy #SP_y
    lda (lp), y
    sta sd_y
    iny
    lda (lp), y
    sta sd_y + 1
    ldy #SP_clip
    lda (lp), y
    sta sd_clip
    iny
    lda (lp), y
    sta sd_clip + 1

    ; its image: banks_pool + banks_dir[bank] + 5 * image
    lda sd_image
    sta sd_t
    lda #0
    sta sd_t + 1
    asl sd_t
    rol sd_t + 1
    asl sd_t
    rol sd_t + 1
    clc
    lda sd_t
    adc sd_image
    sta sd_t
    bcc 2f
    inc sd_t + 1
2:
    lda sd_bank
    asl
    tax
    clc
    lda banks_dir, x
    adc sd_t
    sta lp
    lda banks_dir + 1, x
    adc sd_t + 1
    sta lp + 1
    clc
    lda lp
    adc #<banks_pool
    sta lp
    lda lp + 1
    adc #>banks_pool
    sta lp + 1
    ldy #0
    lda (lp), y
    sta sd_w
    iny
    lda (lp), y
    sta sd_h
    iny
    lda (lp), y
    sta sd_src
    iny
    lda (lp), y
    sta sd_src + 1
    iny
    lda (lp), y
    sta sd_src + 2
    ; plus the bank's offset (the opponents' colourings)
    lda sd_bank
    asl
    clc
    adc sd_bank
    tax
    clc
    lda sd_src
    adc banks_offset, x
    sta sd_src
    lda sd_src + 1
    adc banks_offset + 1, x
    sta sd_src + 1
    lda sd_src + 2
    adc banks_offset + 2, x
    sta sd_src + 2
    lda #(ATTIC >> 24)
    sta sd_src + 3

    ; rows top = y - h + 1 .. bottom = y, or clip - 1 if y > clip
    ; (unsigned); from max(top, 0)
    sec
    lda sd_y
    sbc sd_h
    sta sd_top
    lda sd_y + 1
    sbc #0
    sta sd_top + 1
    inc sd_top
    bne 3f
    inc sd_top + 1
3:
    lda sd_y
    sta sd_bottom
    lda sd_y + 1
    sta sd_bottom + 1
    lda sd_clip + 1
    cmp sd_y + 1
    bcc 4f
    bne 5f
    lda sd_clip
    cmp sd_y
    bcs 5f
4:
    sec
    lda sd_clip
    sbc #1
    sta sd_bottom
    lda sd_clip + 1
    sbc #0
    sta sd_bottom + 1
5:
    lda sd_top
    sta sd_yy
    lda sd_top + 1
    sta sd_yy + 1
    bpl 6f
    lda #0
    sta sd_yy
    sta sd_yy + 1
6:
    ; columns max(x, 0) .. min(x + w, 320)
    lda sd_x
    sta sd_x0
    lda sd_x + 1
    sta sd_x0 + 1
    bpl 7f
    lda #0
    sta sd_x0
    sta sd_x0 + 1
7:
    clc
    lda sd_x
    adc sd_w
    sta sd_x1
    lda sd_x + 1
    adc #0
    sta sd_x1 + 1
    bmi 8f
    cmp #>FB_W
    bcc 8f
    bne 9f
    lda sd_x1
    cmp #<FB_W
    bcc 8f
9:
    lda #<FB_W
    sta sd_x1
    lda #>FB_W
    sta sd_x1 + 1
8:
    ; nothing to draw: no rows or no columns
    sec
    lda sd_bottom
    sbc sd_yy
    sta sd_rows
    lda sd_bottom + 1
    sbc sd_yy + 1
    bmi .Lnext_sprite
    inc sd_rows
    sec
    lda sd_x1
    sbc sd_x0
    sta sd_len
    lda sd_x1 + 1
    sbc sd_x0 + 1
    sta sd_len + 1
    bmi .Lnext_sprite
    ora sd_len
    beq .Lnext_sprite

    ; the first row's pixels: + (yy - top) * w + x0 - x
    sec
    lda sd_yy
    sbc sd_top
    sta MULTINA
    lda sd_yy + 1
    sbc sd_top + 1
    sta MULTINA + 1
    lda #0
    sta MULTINA + 2
    sta MULTINA + 3
    sta MULTINB + 1
    sta MULTINB + 2
    sta MULTINB + 3
    lda sd_w
    sta MULTINB
    clc
    lda sd_src
    adc MULTOUT
    sta sd_src
    lda sd_src + 1
    adc MULTOUT + 1
    sta sd_src + 1
    lda sd_src + 2
    adc #0
    sta sd_src + 2
    sec
    lda sd_x0
    sbc sd_x
    sta sd_t
    lda sd_x0 + 1
    sbc sd_x + 1
    sta sd_t + 1
    clc
    lda sd_src
    adc sd_t
    sta sd_src
    lda sd_src + 1
    adc sd_t + 1
    sta sd_src + 1
    lda sd_src + 2
    adc #0
    sta sd_src + 2

    ; where they go: (view_y0 + yy) * 320 + x0
    clc
    lda sd_yy
    adc view_y0
    tax
    lsr
    lsr
    sta sd_t
    txa
    clc
    adc sd_t
    sta sd_dst + 1
    txa
    and #3
    asl
    asl
    asl
    asl
    asl
    asl
    clc
    adc sd_x0
    sta sd_dst
    lda sd_dst + 1
    adc sd_x0 + 1
    sta sd_dst + 1

.Lrow:
    ; room for the job
    lda dma_p + 1
    cmp #>(DMA_LIST_END - COPY_JOB)
    bcc 10f
    bne 11f
    lda dma_p
    cmp #<(DMA_LIST_END - COPY_JOB)
    bcc 10f
11:
    jsr dma_flush
10:
    lda dma_p
    sta jp
    lda dma_p + 1
    sta jp + 1
    ldy #0
    lda #$0A                    ; F018A jobs
    sta (jp), y
    iny
    lda #$80                    ; source megabyte
    sta (jp), y
    iny
    lda sd_src + 2
    lsr
    lsr
    lsr
    lsr
    sta sd_t
    lda sd_src + 3
    asl
    asl
    asl
    asl
    ora sd_t
    sta (jp), y
    iny
    lda #$81                    ; target megabyte 0
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    lda #$07                    ; transparency on, for SPR_CLEAR
    sta (jp), y
    iny
    lda #$86
    sta (jp), y
    iny
    lda #SPR_CLEAR
    sta (jp), y
    iny
    lda #0                      ; end of options
    sta (jp), y
    iny
    lda #$04                    ; copy, chained
    sta (jp), y
    iny
    lda sd_len
    sta (jp), y
    iny
    lda sd_len + 1
    sta (jp), y
    iny
    lda sd_src
    sta (jp), y
    iny
    lda sd_src + 1
    sta (jp), y
    iny
    lda sd_src + 2
    and #$0F
    sta (jp), y
    iny
    lda sd_dst
    sta (jp), y
    iny
    lda sd_dst + 1
    sta (jp), y
    iny
    lda #((PICTURE >> 16) & $0F)
    sta (jp), y
    iny
    lda #0
    sta (jp), y
    iny
    sta (jp), y
    clc
    lda jp
    adc #9
    sta dma_last_cmd
    lda jp + 1
    adc #0
    sta dma_last_cmd + 1
    clc
    lda jp
    adc #COPY_JOB
    sta dma_p
    lda jp + 1
    adc #0
    sta dma_p + 1

    ; the next row
    clc
    lda sd_src
    adc sd_w
    sta sd_src
    bcc 12f
    inc sd_src + 1
    bne 12f
    inc sd_src + 2
12:
    clc
    lda sd_dst
    adc #<FB_W
    sta sd_dst
    lda sd_dst + 1
    adc #>FB_W
    sta sd_dst + 1
    dec sd_rows
    beq .Lnext_sprite
    jmp .Lrow

.Lnext_sprite:
    inc sd_i
    jmp .Lsprite
