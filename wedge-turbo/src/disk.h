// Wedge Turbo: loading files from the disk in drive 8 (the D81 that
// build.sh makes), and writing one back, at any time: the loader reads and
// writes the sectors itself through the floppy controller, without the
// KERNAL.

#ifndef DISK_H
#define DISK_H

#include <stdbool.h>
#include <stdint.h>

// Load the file `name` to addr (28 bits), without the two bytes of load
// address it starts with (like LOAD with secondary address 0). False if it
// is not there or cannot be read.
bool disk_load(const char *name, uint32_t addr);

// Write len bytes from data into the file `name` that is on the disk
// already, after its load address: the file keeps its length and its
// sectors, so it must be long enough. False if it is not there, too short,
// or the disk cannot be written.
bool disk_save(const char *name, const void *data, uint16_t len);

// Called after each sector the loader read (a spinner, for example); 0: none
extern void (*disk_busy)(void);

#endif
