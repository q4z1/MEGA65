; Smaragd Dash: starts the DMA with a list in bank 0 (src/dma.c).
;
; dma_start(list): the list's address in __rc2-__rc3, as llvm-mos passes
;   it. In assembly so that the compiler sees a call it cannot look into:
;   every write to the list happens before it, none is dropped.
;   Changes A only. Z stays 0.

.global dma_start

.section .text.dma_start,"ax",@progbits
dma_start:
    lda #0
    sta $d702                   ; the list's bank
    sta $d704                   ; ... and megabyte
    lda __rc3
    sta $d701
    lda __rc2
    sta $d705                   ; low byte: an enhanced job, starts it
    rts
