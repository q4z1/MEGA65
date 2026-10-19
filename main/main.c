// Hello world for the MEGA65: C with one routine in 45GS02 assembly
// (colors.s). Serves as a template and as a check that compiler, ROM and
// emulator work together.

#include <stdint.h>
#include <stdio.h>

// colors.s: set border and background colour (A = border, X = background)
void set_colors(uint8_t border, uint8_t background);

int main(void) {
    set_colors(6, 0);  // blue / black
    printf("\x93");    // PETSCII: clear screen
    printf("hello world!\n");
    printf("c and assembly on the mega65\n");
    return 0;
}
