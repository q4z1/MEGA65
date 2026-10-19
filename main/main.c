// Hello World fuer den MEGA65: C mit einer Routine in 45GS02-Assembler
// (colors.s). Dient als Vorlage und als Probe, dass Compiler, ROM und
// Emulator zusammenspielen.

#include <stdint.h>
#include <stdio.h>

// colors.s: Rahmen- und Hintergrundfarbe setzen (A = Rahmen, X = Hintergrund)
void set_colors(uint8_t border, uint8_t background);

int main(void) {
    set_colors(6, 0);  // blau / schwarz
    printf("\x93");    // PETSCII: Bildschirm loeschen
    printf("hello world!\n");
    printf("c und assembler auf dem mega65\n");
    return 0;
}
