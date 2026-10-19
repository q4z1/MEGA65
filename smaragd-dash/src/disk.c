// Smaragd Dash: loading files from the disk (see disk.h).

#include "disk.h"

#include <string.h>

// read by disk.s
const char *load_name;
uint8_t load_len, load_bank;
uint16_t load_addr;
uint8_t zp_save[0x8E];  // zero page $02-$8F during the load

uint8_t kernal_load(void);

bool disk_load(const char *name, uint8_t bank, uint16_t addr) {
    load_name = name;
    load_len = strlen(name);
    load_bank = bank;
    load_addr = addr;
    return kernal_load() == 0;
}
