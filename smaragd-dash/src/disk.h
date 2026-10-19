// Smaragd Dash: loading files from the disk in drive 8 (the D81 that
// build.sh makes), at any time: the loader reads the sectors itself through
// the floppy controller, without the KERNAL.

#ifndef DISK_H
#define DISK_H

#include <stdbool.h>
#include <stdint.h>

// Load the file `name` to bank:addr, without the two bytes of load address
// it starts with (like LOAD with secondary address 0). False if it is not
// there or cannot be read. The file must not cross a 64K bank.
bool disk_load(const char *name, uint8_t bank, uint16_t addr);

// Called after each sector the loader read (a spinner, for example); 0: none
extern void (*disk_busy)(void);

#endif
