; Assembly part of the template. llvm-mos passes the first two 8-bit
; arguments in A and X.

    .text
    .global set_colors

; void set_colors(uint8_t border, uint8_t background)
set_colors:
    sta $d020           ; border colour
    stx $d021           ; background colour
    rts
