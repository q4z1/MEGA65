// Lotus Run: where the pictures go (see sprites.h).
//
// Four things come from far to near: the scenery objects of the next 8
// segments, the opponents, the player's car and in a race of two the other
// player's car. Each time the farthest of them is placed (the scenery first
// when it is as far as a car). The arithmetic is 16-bit, overflows
// included.

#include "sprites.h"

#include "mem.h"
#include "progdata.h"
#include "race.h"
#include "tables.h"

LOW_RAM Sprite sprite_list[SPRITES_MAX];
uint8_t sprite_count;
SpriteState sprite_state;

static const RoadStep *steps;
static uint8_t steps_count;
static int16_t view_x;
static int16_t clip;

// What the overlays' rows are relative to: a 96-line view, the car at its
// bottom
#define BOTTOM(y) ((int16_t)(view_lines - 96 + (y)))

static void add(uint8_t bank, uint8_t image, int16_t x, int16_t y) {
    if (sprite_count == SPRITES_MAX)
        return;
    Sprite *s = &sprite_list[sprite_count++];
    s->bank = bank;
    s->image = image;
    s->x = x;
    s->y = y;
    s->clip = clip;
}

// by its middle (x relative to the road's centre line), bottom
// row y
static void put_centred(uint8_t bank, uint8_t image, int16_t x, int16_t y) {
    uint8_t w = sprite_width(bank, image);
    x = (int16_t)(x + 0x8C - (w >> 1));
    sprite_state.last_w = w;
    sprite_state.last_x = x;
    sprite_state.last_y = y;
    add(bank, image, x, y);
}

// by its top left corner
static void put(uint8_t bank, uint8_t image, int16_t x, int16_t y) {
    add(bank, image, x, (int16_t)(y + sprite_height(bank, image) - 1));
}

// a + (b - a) * f / 32768: a 16 x 16 multiplication, doubled, the high word
static int16_t lerp(int16_t a, int16_t b, uint16_t f) {
    int32_t p = (int32_t)(int16_t)(b - a) * f;
    return (int16_t)(a + (int16_t)((uint32_t)p << 1 >> 16));
}

// (x * scale) >> 16, as muls and swap
static int16_t mulhi(int16_t x, int16_t scale) {
    return (int16_t)(((int32_t)x * scale) >> 16);
}

#define KIND_OBJECT   -1  // the image is the size
#define KIND_CAR      0   // the image by size and angle
#define KIND_OPPONENT 63  // the same, of the opponents' cars

// something at depth step `depth` + frac / 65536, sideways at lat
// (the road's units, as the player's x); steer turns the player's car
static void place(uint8_t bank, int8_t kind, int16_t steer, uint16_t depth, int16_t lat,
                  uint16_t frac, int16_t size) {
    const RoadStep *s = &steps[depth];
    int16_t x, y;
    int16_t rel = (int16_t)((uint16_t)(lat - view_x) << 3);
    if (depth < 64) {
        // near: between this step and the next
        if (depth >= (uint16_t)(steps_count - 1))
            return;
        uint16_t f = frac >> 1;
        clip = s[0].top;
        sprite_state.dx = s[0].dx;
        x = (int16_t)(rel - lerp(s[0].x, s[1].x, f));
        y = lerp(s[0].line, s[1].line, f);
        int16_t scale = lerp((int16_t)tab_scale[depth], (int16_t)tab_scale[depth + 1], f);
        x = mulhi(x, (int16_t)(scale * 2));
    } else {
        if (depth >= steps_count)
            return;
        clip = s->top;
        sprite_state.dx = s->dx;
        x = mulhi((int16_t)(rel - s->x), (int16_t)(tab_scale[depth] * 2));
        y = s->line;
    }
    if ((uint16_t)y >= (uint16_t)BOTTOM(0x5E))
        y = BOTTOM(0x5E);
    if (kind == KIND_OBJECT) {
        put_centred(bank, (uint8_t)size, x, y);
        return;
    }
    // the car seen from the side it is on, turned by the road's direction
    // and the player's steering
    int16_t a = (int16_t)(0x90 - x) >> 2;
    if (kind == KIND_CAR)
        a = (int16_t)(a + steer);
    a = (int16_t)(a + ((int16_t)-sprite_state.dx >> 2));
    a >>= 3;
    if (a < 0)
        a = 0;
    if (a >= 8)
        a = 8;
    sprite_state.angle = (uint16_t)a;
    put_centred(bank, (uint8_t)(tab_car_image[size * 9 + a] + kind), x, y);
}

// pos - from, the segments counted round the course
static uint32_t ahead(uint32_t pos, uint32_t from) {
    uint32_t d = pos - from;
    uint32_t seg = (uint32_t)(int32_t)(int16_t)(d >> 16) + race.seg_bias;
    return (uint32_t)(uint16_t)(seg % race.segments) << 16 | (uint16_t)d;
}

// ---------------------------------------------------------------- scenery

static uint16_t obj_buf[36];  // the objects of the segments 0-8 ahead, 4 each
static uint8_t obj_i;
static int16_t obj_depth;     // -1: no more
static uint16_t obj;          // type << 8 | x
static uint16_t obj_frac;

static void next_object(void) {
    for (;;) {
        obj_depth = (int16_t)(obj_depth - 4);
        if (obj_depth < 0) {
            obj_depth = -1;
            return;
        }
        obj = obj_buf[--obj_i];
        if (obj & 0xFF00)
            return;
    }
}

// the gate over the road - two posts, a banner between
static void gate(uint16_t depth, int16_t size) {
    uint8_t bank = spr_bank_of_type[2];
    place(bank, KIND_OBJECT, 0, depth, -0x108, obj_frac, size);
    int16_t left_x = sprite_state.last_x;
    uint16_t left_w = sprite_state.last_w;
    place(bank, KIND_OBJECT, 0, depth, 0x108, obj_frac, size);
    int16_t right_x = sprite_state.last_x, bottom = sprite_state.last_y;
    if (!left_w || size < 7)
        return;
    uint8_t i = (uint8_t)(size - 7);
    int16_t top = (int16_t)(bottom - tab_gate[i]);
    int16_t inset = tab_gate[10 + i];
    clip = BOTTOM(0x5F);
    put_centred(bank, (uint8_t)(size + 10), (int16_t)(right_x - 0x8C - inset), top);
    put_centred(bank, (uint8_t)(size + 10), (int16_t)(left_x - 0x8C + left_w + inset), top);
    if (size + 20 >= 35)
        return;
    put_centred(bank, (uint8_t)(size + 20), (int16_t)(((int16_t)(left_x + left_w + right_x) >> 1) - 0x8C),
                (int16_t)(top - tab_gate[20 + i]));
}

static void object(void) {
    uint16_t depth = (uint16_t)obj_depth;
    int16_t size = tab_object_size[depth];
    if (size < 0)
        return;
    uint8_t type = (uint8_t)(obj >> 8);
    if (type == 0x82)
        gate(depth, size);
    else
        place(spr_bank_of_type[type - 0x80], KIND_OBJECT, 0, depth, (int16_t)((int8_t)obj << 4), obj_frac,
              size);
}

// ---------------------------------------------------------------- opponents

static int16_t opp_left;
static uint8_t opp_i;
static uint32_t opp_prev;
static uint32_t opp_rel;
static uint8_t opp_found;
static int16_t opp_depth;   // -1: no more
static uint16_t opp_frac;
static int16_t opp_x;
static uint8_t opp_colour;  // which of the opponents' colourings

// the next in the opponents' ring that is in sight; after the
// first one in sight the first one out of it ends them
static void next_opponent(void) {
    for (;;) {
        if (--opp_left < 0) {
            opp_depth = -1;
            return;
        }
        uint32_t pos = race.opp_pic[opp_i];
        opp_x = race.opp_pic_x[opp_i];
        opp_colour = opp_i % OPP_COLOURS;
        opp_i++;
        uint32_t d = pos - opp_prev;
        opp_prev += d;
        d += opp_rel;
        if ((int32_t)d < 0)
            d += (uint32_t)race.segments << 16;
        opp_rel = d;
        if (d >= 0x80000) {
            if (opp_found) {
                opp_depth = -1;
                return;
            }
            continue;
        }
        d <<= 4;
        opp_frac = (uint16_t)d;
        opp_depth = (int16_t)(d >> 16);
        opp_found = 1;
        return;
    }
}

static void opponent(void) {
    int16_t size = tab_car_size[opp_depth];
    if (size >= 0)
        place(opp_colour ? SPR_OPP + opp_colour - 1 : SPR_CARS, KIND_OPPONENT, 0, (uint16_t)opp_depth, opp_x,
              opp_frac, size);
}

// ---------------------------------------------------------------- the cars

typedef struct {
    int16_t depth;  // -1: not in sight
    uint16_t frac;
    int16_t x;
} Car;

static Car car, car2;

// player n's car in player 1's view
static void car_in_view(Car *c, uint8_t n) {
    const Player *p = &race.p[n];
    c->x = (int16_t)(p->x_shown >> 16);
    uint32_t d = ahead(p->pos_shown, race.p[0].pos_view);
    if (d >= 0x80000) {
        c->depth = -1;
        return;
    }
    d <<= 4;
    c->frac = (uint16_t)d;
    c->depth = (int16_t)(d >> 16);
}

// the player's car, and at the bottom of the view what goes with
// it: the brake lights when braking
static void own_car(void) {
    const Player *p = &race.p[0];
    int16_t size = tab_car_size[car.depth];
    if (size < 0)
        return;
    place(SPR_CARS, KIND_CAR, p->steer_view, (uint16_t)car.depth, car.x, car.frac, size);
    int16_t x = sprite_state.last_x;
    if (sprite_state.last_y != BOTTOM(0x5E))
        return;
    uint8_t a = (uint8_t)sprite_state.angle;
    clip = BOTTOM(0x5F);
    put(SPR_HUD, 18, (int16_t)(tab_brake[36 + a] + x), BOTTOM(0x54));
    if (p->joy & JOY_DOWN) {
        put(SPR_HUD, (uint8_t)tab_brake[a], (int16_t)(tab_brake[18 + a] + x), BOTTOM(0x4C));
        put(SPR_HUD, (uint8_t)tab_brake[9 + a], (int16_t)(tab_brake[27 + a] + x), BOTTOM(0x4C));
    }
}

// the other player's car
static void other_car(void) {
    int16_t size = tab_car_size[car2.depth];
    if (size >= 0)
        place(SPR_CARS, KIND_CAR, race.p[1].steer_view, (uint16_t)car2.depth, car2.x, car2.frac, size);
}

// ---------------------------------------------------------------- overlays

// paused, the countdown, then blinking: out of fuel, the place at
// the finish, ...
static void message(void) {
    const Player *p = &race.p[0];
    int16_t image, y = 0x20;
    if (race.paused) {
        image = 1;
    } else if (race.clock < 50) {
        int16_t t = (int16_t)(race.clock + 250);
        if (t < 0)
            return;
        image = tab_countdown[(uint16_t)t / 25];
    } else {
        if (!(race.clock & 16))
            return;
        if (!p->fuel) {
            image = 0;
        } else if (p->stopped) {
            image = (int16_t)p->place;
            if ((uint16_t)image >= 11) {
                image = 2;
            } else {
                image += 7;
                y = 0x2C;
            }
        } else if (p->timer && p->timer < 0x60) {
            image = 3;
        } else {
            return;
        }
    }
    if (image < 0)
        return;
    clip = BOTTOM(0x5F);
    put_centred(SPR_HUD, (uint8_t)image, 0, y);
}

// ----------------------------------------------------------------

void sprites_place(const RoadStep *s, uint8_t count) {
    const Player *p = &race.p[0];
    sprite_count = 0;
    if (p->in_pits_shown)
        return;
    steps = s;
    steps_count = count;
    view_x = (int16_t)(p->x_view >> 16);

    opp_found = 0;
    opp_prev = race.opp_pic[0];
    opp_rel = ahead(race.opp_pic[0], p->pos_view);
    opp_i = 0;
    opp_left = race.difficulty == 3 ? 0 : (int16_t)race.opponents;

    uint16_t seg = (uint16_t)(ahead(p->pos_view, 0) >> 16);
    for (uint8_t k = 0; k < 9; k++)
        for (uint8_t j = 0; j < 4; j++) {
            const Segment *g = &race_track->seg[seg + k];
            obj_buf[4 * k + j] = (uint16_t)(g->object[j].type << 8 | (uint8_t)g->object[j].x);
        }
    uint8_t step = (uint8_t)(p->pos_view >> 12) & 15;
    obj_depth = 0x7C + 3 - (step & 3);
    obj_i = (uint8_t)(32 + (step >> 2));
    obj_frac = (uint16_t)~(uint16_t)(p->pos_view << 4);

    next_object();
    next_opponent();
    car_in_view(&car, 0);
    if (race.two_players)
        car_in_view(&car2, 1);
    else
        car2.depth = -1;

    for (;;) {
        uint16_t o = (uint16_t)(obj_depth + 1), op = (uint16_t)(opp_depth + 1);
        uint16_t c = (uint16_t)(car.depth + 1), c2 = (uint16_t)(car2.depth + 1);
        if (!(o | op | c | c2))
            break;
        uint8_t which;  // 0 object, 1 opponent, 2 car, 3 the other car
        if (c < o) {
            if (c2 < op)
                which = op >= o ? 1 : 0;
            else
                which = c2 >= o ? 3 : 0;
        } else {
            if (c2 < op)
                which = op >= c ? 1 : 2;
            else
                which = c2 >= c ? 3 : 2;
        }
        switch (which) {
        case 0:
            object();
            next_object();
            break;
        case 1:
            opponent();
            next_opponent();
            break;
        case 2:
            own_car();
            car.depth = -1;
            break;
        default:
            other_car();
            car2.depth = -1;
            break;
        }
    }
    message();
    clip = BOTTOM(0x5F);
    put(SPR_HUD, 23, 2, 2);
}
