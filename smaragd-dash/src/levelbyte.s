; Smaragd Dash: a level's changes to the first level's cave, which come
; from the disk behind it (tools/mkcave.py) in LEVEL_BANK (src/mem.h), put
; into the cave being played (main.c's file).
;
; level_changes(level): those of level (1 for the second, in A): for each
;   level from the second a count and that many offsets in the cave (low,
;   high) and bytes. Read through the 45GS02's 32-bit pointer in
;   __rc2-__rc5; changes A, X, Y and __rc2-__rc9, which a caller does not
;   keep. Z stays 0.

.global level_changes

.section .text.level_changes,"ax",@progbits
level_changes:
    sta __rc6                   ; levels to go: the last one is level's
    lda level_changes_at        ; where they start (main.c)
    sta __rc2
    lda level_changes_at+1
    sta __rc3
    lda #3                      ; LEVEL_BANK
    sta __rc4
    stz __rc5                   ; Z is 0: the first megabyte
    lda #<file
    sta __rc7
1:  jsr next                    ; a level's count
    sta __rc9
2:  lda __rc9
    beq 3f
    dec __rc9
    jsr next                    ; the offset's low byte ...
    tay
    jsr next                    ; ... and high byte
    clc
    adc #>file
    sta __rc8
    jsr next                    ; the byte
    ldx __rc6
    dex
    bne 2b                      ; not level's
    sta (__rc7),y
    bra 2b
3:  dec __rc6
    bne 1b
    rts

next:
    lda [__rc2],z
    inw __rc2
    rts
