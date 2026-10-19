; Smaragd Dash: load a file from the disk in drive 8 through the KERNAL,
; into any bank. Only usable before the program takes the machine over.
; Arguments in load_name, load_len, load_bank, load_addr (disk.c).

    .text
    .global kernal_load

; uint8_t kernal_load(void): 0 = loaded, 1 = error
;
; The llvm-mos start-up code switched the interrupts off and the ROM at
; $C000 (KERNAL and DOS parts live there) and BASIC out; LOAD needs the
; ROM's own configuration back. Our variables may lie under that ROM, so
; everything is passed to the KERNAL before switching. The DOS also uses
; zero page $02-$8F (BASIC's), where llvm-mos keeps its registers and
; stack pointer: that is saved and restored around the load. And it leaves
; the Z register non-zero, while llvm-mos stores zeros with STZ (which
; stores Z on the 45GS02): Z and the base page register B go back to 0.
kernal_load:
    lda load_bank
    ldx #0
    jsr $ff6b           ; SETBNK: A = bank of the data, X = bank of the name
    lda load_len
    ldx load_name
    ldy load_name+1
    jsr $ffbd           ; SETNAM
    lda #1
    ldx #8
    ldy #0              ; secondary address 0: load to X/Y, not to the file's
    jsr $ffba           ; SETLFS
    ldx #0
1:  lda $02,x
    sta zp_save,x
    inx
    cpx #$8e
    bne 1b
    ldx load_addr
    ldy load_addr+1

    lda $01
    pha
    lda $d030
    pha
    lda #$3f
    sta $01
    lda #$64
    sta $d030
    cli
    lda #0
    jsr $ffd5           ; LOAD; carry set on error
    lda #0
    rol a
    tay
    sei
    ldz #0
    lda #0
    tab
    pla
    sta $d030
    pla
    sta $01
    ldx #0
2:  lda zp_save,x
    sta $02,x
    inx
    cpx #$8e
    bne 2b
    tya
    rts
