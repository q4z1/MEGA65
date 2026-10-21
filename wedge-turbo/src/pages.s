; Wedge Turbo: a frame of the page's animation (pages.h) - its rows of screen
; RAM and of colour RAM, copied by DMA from the page's file in attic RAM,
; where page_show (pages.c) found them. In LOW_CODE (mem.h): there is room.

.include "offsets.inc"

.global page_frames, page_frame

COLOUR_RAM = $FF80000

.section .lowram.pages_s,"aw",@nobits   ; set before use: LOW_RAM (mem.h)
src:        .fill 4

.section .lowcode.pages_s,"ax",@progbits

; page_frames(): how many frames the page has (0: none)
page_frames:
    lda anim_frames
    rts

; Copies len (anim_len) bytes from src to rc4-rc7 + anim_at
copy:
    lda anim_len
    sta __rc8
    lda anim_len + 1
    sta __rc9
    lda src + 2
    sta __rc2
    lda src + 3
    sta __rc3
    clc
    lda __rc4
    adc anim_at
    sta __rc4
    lda __rc5
    adc anim_at + 1
    sta __rc5
    lda __rc6
    adc #0
    sta __rc6
    lda src
    ldx src + 1
    jmp dma_copy

; src += anim_len
next:
    clc
    lda src
    adc anim_len
    sta src
    lda src + 1
    adc anim_len + 1
    sta src + 1
    bcc 1f
    inc src + 2
    bne 1f
    inc src + 3
1:  rts

; page_frame(f): frame f (A) shown
page_frame:
    tay
    ldx #3
1:  lda anim_src, x
    sta src, x
    dex
    bpl 1b
2:  cpy #0                      ; on to frame f: two blocks of anim_len each
    beq 3f
    jsr next
    jsr next
    dey
    bra 2b
3:  lda #<PAGE_SCREEN
    sta __rc4
    lda #>PAGE_SCREEN
    sta __rc5
    lda #(PAGE_SCREEN >> 16)
    sta __rc6
    stz __rc7
    jsr copy
    jsr next
    lda #<COLOUR_RAM
    sta __rc4
    lda #>COLOUR_RAM
    sta __rc5
    lda #((COLOUR_RAM >> 16) & $FF)
    sta __rc6
    lda #(COLOUR_RAM >> 24)
    sta __rc7
    jsr copy
    jmp dma_flush
