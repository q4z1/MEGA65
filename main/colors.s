; Assembler-Teil der Vorlage. llvm-mos uebergibt die ersten beiden
; 8-Bit-Argumente in A und X.

    .text
    .global set_colors

; void set_colors(uint8_t border, uint8_t background)
set_colors:
    sta $d020           ; Rahmenfarbe
    stx $d021           ; Hintergrundfarbe
    rts
