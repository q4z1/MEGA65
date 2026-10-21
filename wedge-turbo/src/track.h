// Wedge Turbo: a course in memory.

#ifndef TRACK_H
#define TRACK_H

#include <stdint.h>

#define TRACK_HEADER 162

// A segment: 12 bytes from the course file and 4 the game uses itself
typedef struct {
    int8_t curve;
    int8_t hill;
    struct {
        uint8_t type;  // scenery object $80-$AB, 0: none
        int8_t x;      // its position, * 16
    } object[4];       // one per quarter of the segment
    uint8_t flags10;
    uint8_t variant;   // bit 0: road line variant
    uint8_t spare[4];
} Segment;

typedef struct {
    uint16_t segments;  // segment count; the array has 8 more (repeated)
    uint8_t header[TRACK_HEADER];
    Segment seg[];
} Track;

_Static_assert(sizeof(Segment) == 16, "a segment is 16 bytes");

#endif
