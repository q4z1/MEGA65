; Lotus Run: the machine for the game - the KERNAL switched out (the game
; never calls it), the interrupt vectors at $FFFA-$FFFF ours. No interrupt
; is on at first: the vectors lead to handlers that acknowledge, and call
; irq_frame (an assembly routine, which may use the KERNAL's zero page from
; $90 on) - music.c turns on a timer interrupt for the music.

.global irq_init, irq_frame

.section .data.irq,"aw",@progbits
irq_frame:  .word irq_nothing

.section .text.irq,"ax",@progbits

irq_init:
    sei
    ; no mapping in the upper 32K (the C65 KERNAL is mapped there), then
    ; RAM under $E000 through the CPU port
    lda #0
    ldx #0
    ldy #0
    ldz #0
    map
    eom
    lda #$35
    sta $01
    lda #<irq_handler
    sta $FFFE
    lda #>irq_handler
    sta $FFFF
    lda #<nmi_handler
    sta $FFFA
    lda #>nmi_handler
    sta $FFFB
    lda #$7F            ; no CIA interrupts
    sta $DC0D
    sta $DD0D
    lda $DC0D
    lda $DD0D
    lda #0              ; no VIC interrupts
    sta $D01A
    lda #$FF            ; acknowledge whatever is pending
    sta $D019
    ldz #0              ; llvm-mos keeps Z at 0
    cli
    rts

irq_handler:
    pha
    phx
    phy
    phz
    lda $D030           ; the I/O as it should be: without the colour RAM
    pha                 ; at $D800-$DFFF (video.c turns it on for a while),
    and #$FE            ; which hides CIA 1
    sta $D030
    lda $DC0D           ; acknowledge CIA 1 and the VIC
    lda #$FF
    sta $D019
    jsr irq_call
    pla
    sta $D030
    plz
    ply
    plx
    pla
nmi_handler:
    rti

irq_call:
    jmp (irq_frame)
irq_nothing:
    rts
