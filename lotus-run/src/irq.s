; Lotus Run: the machine for the game - the KERNAL switched out (the game
; never calls it), the interrupt vectors at $FFFA-$FFFF ours. No interrupt
; is used: the vectors lead to handlers that only acknowledge.

.global irq_init

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
    lda #$FF
    sta $D019
    pla
nmi_handler:
    rti
