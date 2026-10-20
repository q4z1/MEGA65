// Lotus Run: the sprites into the picture, in C - the reference of
// render.s's sprites_draw (see sprites.h), and what the host tests draw
// with.

#include "banks.h"
#include "fb.h"
#include "road.h"
#include "sprites.h"

void sprites_draw(void) {
    for (uint8_t i = 0; i < sprite_count; i++) {
        const Sprite *s = &sprite_list[i];
        uint8_t w = sprite_width(s->bank, s->image), h = sprite_height(s->bank, s->image);
        int16_t top = (int16_t)(s->y - h + 1), bottom = s->y;
        if ((uint16_t)bottom > (uint16_t)s->clip)
            bottom = (int16_t)(s->clip - 1);
        int16_t y = top < 0 ? 0 : top;
        int16_t x0 = s->x < 0 ? 0 : s->x, x1 = (int16_t)(s->x + w);
        if (x1 > FB_W)
            x1 = FB_W;
        if (y > bottom || x0 >= x1)
            continue;
        uint32_t src = sprite_pixels(s->bank, s->image) + (uint16_t)((y - top) * w + (x0 - s->x));
        for (; y <= bottom; y++, src += w)
            fb_sprite_row((uint8_t)(view_y0 + y), (uint16_t)x0, src, (uint16_t)(x1 - x0));
    }
}
