// Smaragd Dash: loading files from the disk in drive 8 (the D81 that
// build.sh makes), and writing one back, at any time: the loader reads and
// writes the sectors itself through the floppy controller, without the
// KERNAL.

#ifndef DISK_H
#define DISK_H

#include <stdbool.h>
#include <stdint.h>

// Load the file `name` to bank:addr, without the two bytes of load address
// it starts with (like LOAD with secondary address 0). False if it is not
// there or cannot be read. The file must not cross a 64K bank.
bool disk_load(const char *name, uint8_t bank, uint16_t addr);

// Write len bytes from data into the file `name` that is on the disk
// already, after its load address: the file keeps its length and its
// sectors, so it must be long enough. False if it is not there, too short,
// or the disk cannot be written.
bool disk_save(const char *name, const void *data, uint16_t len);

// The names of the partitions on the disk (1581 subdirectories: type CBM)
// but `skip`, up to max of them, their first 8 characters; how many.
// disk_load("DIR/NAME", ...) and disk_save load and write a file in one.
uint8_t disk_partitions(char (*names)[9], uint8_t max, const char *skip);

// The partition `part` renamed to `name`: its directory entry and its
// header. False if it is not there or the disk cannot be written.
bool disk_rename(const char *part, const char *name);

// Called after each sector the loader read (a spinner, for example); 0: none
extern void (*disk_busy)(void);

// After a load or save that failed: the logical sector that could not be
// read or written, and the controller's status ($D082) then; track 0 if
// the file is not on the disk
extern uint8_t disk_err_track, disk_err_sector, disk_err_status;

#endif
