// Smaragd Dash: the high score table (see hiscore.h).
//
// The file holds four bytes "SDH1" and the table as it is in memory (9
// bytes per entry, the score little-endian). On the disk it is one sector
// long, its two bytes of load address and 252 more; what is not the table
// stays 0. A file without the four bytes - as build.sh makes it - gives
// the default table, which the first entry then writes.

#include "hiscore.h"

#include <string.h>

#include "disk.h"

#define FILE_NAME "SMARAGD.SCORES"
#define FILE_SIZE 252  // see build.sh

HiScore hs_table[HS_COUNT];

static union {
    struct {
        char magic[4];
        HiScore table[HS_COUNT];
    } s;
    uint8_t raw[FILE_SIZE];
} file;

static const char magic[4] = {'S', 'D', 'H', '1'};

static const HiScore defaults[HS_COUNT] = {
    {{'R', 'O', 'C'}, 15, 0, 5000},
    {{'G', 'E', 'M'}, 12, 0, 4000},
    {{'D', 'I', 'G'}, 10, 0, 3000},
    {{'O', 'R', 'E'}, 8, 0, 2500},
    {{'F', 'L', 'Y'}, 6, 0, 2000},
    {{'B', 'U', 'G'}, 4, 0, 1500},
    {{'R', 'U', 'N'}, 3, 0, 1000},
    {{'A', 'X', 'E'}, 1, 0, 500},
};

void hiscore_load(void) {
    if (disk_load(FILE_NAME, 0, (uint16_t)&file) && !memcmp(file.s.magic, magic, 4))
        memcpy(hs_table, file.s.table, sizeof hs_table);
    else
        memcpy(hs_table, defaults, sizeof hs_table);
}

bool hiscore_save(void) {
    memset(&file, 0, sizeof file);
    memcpy(file.s.magic, magic, 4);
    memcpy(file.s.table, hs_table, sizeof hs_table);
    return disk_save(FILE_NAME, &file, sizeof file);
}

uint8_t hiscore_rank(uint32_t score) {
    uint8_t r = 0;
    while (r < HS_COUNT && score <= hs_table[r].score)
        r++;
    return r;
}

HiScore *hiscore_insert(uint8_t rank) {
    memmove(&hs_table[rank + 1], &hs_table[rank], (HS_COUNT - 1 - rank) * sizeof(HiScore));
    return &hs_table[rank];
}
