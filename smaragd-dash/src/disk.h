// Smaragd Dash: loading files from the disk in drive 8 (the D81 that
// build.sh makes) through the KERNAL. Only before the program has switched
// off the interrupts and taken over the screen.

#ifndef DISK_H
#define DISK_H

#include <stdbool.h>
#include <stdint.h>

// Load the file `name` to bank:addr (the file's own load address is
// ignored). False if it is not there.
bool disk_load(const char *name, uint8_t bank, uint16_t addr);

#endif
