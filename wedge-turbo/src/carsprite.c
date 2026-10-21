// Wedge Turbo: the player's car near as hardware sprites (see carsprite.h).
//
// Sprites of 16 colours (one per pixel, a nybble; 0 clear: the colour
// register of each is 0), 64 bits wide (16 pixels), extended height
// (CARHI_ROWS), 640 across (SPR640) and 400 down (V400). Sprite s takes
// colours s * 16 + nybble of palette 1 ($D070's sprite palette), the race
// view palette 0. Positions are the screen's: 640 across and 400 down
// from where the text area (the picture) starts, $D04C and $D04E.

#include "carsprite.h"

#include "banks.h"
#include "dma.h"
#include "hw.h"
#include "mem.h"
#include "progdata.h"
#include "sprbanks.h"
#include "video.h"

uint8_t car_sprite_image = CAR_SPRITE_OFF;
int16_t car_sprite_x, car_sprite_row;
static uint8_t shown;  // the image in chip RAM

_Static_assert(CARHI_IMAGE <= CARSPR_SIZE, "the car's sprites do not fit into CARSPR_DATA");

MENU __attribute__((noinline)) bool car_sprite_load(void) {
    if (!file_open("CARHI", PICTURE))
        return false;
    file_unpack(0, CARHI_ATTIC, CARHI_ATTIC + 18ul * CARHI_IMAGE);
    return true;
}

void car_sprite_race(void) {
    // palette 1, the sprites': per sprite nybble 1 black, 2-7 the race
    // view's colours 1-6, 8-10 the paint
    POKE(0xD070, 0x44);  // edit palette 1, the sprites' from it
    for (uint8_t s = 0; s < CARHI_SPRITES * 16; s += 16) {
        video_colour(s + 1, 0);
        for (uint8_t i = 0; i < 6; i++)
            video_colour(s + 2 + i, tab_view_colours[i]);
        for (uint8_t i = 0; i < 3; i++)
            video_colour(s + 8 + i, car_paint[i]);
    }
    POKE(0xD070, 0x04);  // edit palette 0 again
    LOW_RAM static uint8_t ptrs[2 * CARHI_SPRITES];
    for (uint8_t s = 0; s < CARHI_SPRITES; s++) {
        uint16_t p = (uint16_t)((CARSPR_DATA + (uint32_t)s * CARHI_BLOCK) >> 6);
        ptrs[2 * s] = (uint8_t)p;
        ptrs[2 * s + 1] = p >> 8;
    }
    dma_copy((uint16_t)ptrs, CARSPR_PTRS, sizeof ptrs);
    dma_flush();
    POKE(0xD06C, (uint8_t)CARSPR_PTRS);
    POKE(0xD06D, (uint8_t)(CARSPR_PTRS >> 8));
    POKE(0xD06E, 0x80 | (uint8_t)(CARSPR_PTRS >> 16));  // 16-bit pointers
    POKE(0xD054, PEEK(0xD054) | 0x10);                   // 640 across
    POKE(0xD055, 0xFF);                                  // extended height
    POKE(0xD056, CARHI_ROWS);
    POKE(0xD057, 0xFF);                                  // 64 bits wide
    POKE(0xD06B, 0xFF);                                  // 16 colours
    POKE(0xD076, 0xFF);                                  // 400 down
    POKE(0xD01B, 0);                                     // in front
    POKE(0xD017, 0);
    POKE(0xD01D, 0);
    for (uint8_t s = 0; s < CARHI_SPRITES; s++)
        POKE(0xD027 + s, 0);  // nybble 0 clear
    shown = CAR_SPRITE_OFF;
    car_sprite_image = CAR_SPRITE_OFF;
}

void car_sprite_off(void) {
    POKE(0xD015, 0);
}

void car_sprite_show(void) {
    if (car_sprite_image == CAR_SPRITE_OFF) {
        car_sprite_off();
        return;
    }
    if (car_sprite_image != shown) {
        dma_copy(CARHI_ATTIC + (uint32_t)car_sprite_image * CARHI_IMAGE, CARSPR_DATA, CARHI_IMAGE);
        dma_flush();
        shown = car_sprite_image;
    }
    uint16_t tx = PEEK(0xD04C) | (PEEK(0xD04D) & 15) << 8;
    uint16_t ty = PEEK(0xD04E) | (PEEK(0xD04F) & 15) << 8;
    uint16_t x = (uint16_t)(tx - 1 + car_sprite_x - CARHI_W / 2);
    uint16_t y = (uint16_t)(ty + 2 * (car_sprite_row + 1) - CARHI_ROWS);
    uint8_t x8 = 0, x9 = 0;
    for (uint8_t s = 0; s < CARHI_SPRITES; s++, x += 16) {
        POKE(0xD000 + 2 * s, (uint8_t)x);
        POKE(0xD001 + 2 * s, (uint8_t)y);
        if (x & 0x100)
            x8 |= (uint8_t)(1 << s);
        if (x & 0x200)
            x9 |= (uint8_t)(1 << s);
    }
    POKE(0xD010, x8);
    POKE(0xD05F, x9);
    POKE(0xD077, y & 0x100 ? 0xFF : 0);
    POKE(0xD078, y & 0x200 ? 0xFF : 0);
    POKE(0xD015, 0xFF);
}
