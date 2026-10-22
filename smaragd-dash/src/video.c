// Smaragd Dash: the screen (see video.h).

#include "video.h"

#include "dma.h"
#include "engine.h"
#include "gfx.h"
#include "hw.h"
#include "mem.h"

// The memory is mem.h's: framebuffers, status line and screens in banks 4
// and 5, the tiles and the logo in bank 1, the DMA list in bank 0.
#define COLS        40
#define ROWS        25
#define LINESTEP    (COLS * 2)
#define STATUS_ROWS 3           // status line (2) and separator (1)
#define FB_COL      (22 * 64u)  // bytes per framebuffer column (22 characters)
_Static_assert(COLS * FB_COL == FB_SIZE, "a framebuffer is not as mem.h has it");

static uint16_t text_x;        // TEXTXPOS for the status line
static uint16_t text_y;        // first raster line of the text area
static uint16_t bottom;        // first raster line of the bottom border
static uint8_t back;           // framebuffer being drawn: 0 = A, 1 = B
static uint8_t shown_fx;       // fine scroll of the framebuffer on screen
static uint8_t drawn_fx;       // fine scroll of the one just drawn

// ---------------------------------------------------------------- setup

static void set_palette(void) {
    POKE(0xD070, 0x00);  // edit and use palette 0
    for (uint8_t i = 0; i < PAL_COUNT; i++) {
        POKE(0xD100 + i, pal_r[i]);
        POKE(0xD200 + i, pal_g[i]);
        POKE(0xD300 + i, pal_b[i]);
    }
    POKE(0xD070, 0x40);  // edit palette 1: the title screen's
    for (uint16_t i = 0; i < 256; i++) {
        POKE(0xD100 + i, pal1_r[i]);
        POKE(0xD200 + i, pal1_g[i]);
        POKE(0xD300 + i, pal1_b[i]);
    }
    POKE(0xD070, 0x00);
    POKE(0xD030, PEEK(0xD030) | 0x04);  // colours 0-15 from palette RAM too
}

void video_palette(uint8_t n) {
    POKE(0xD070, n << 4);  // palette for text; palette 0 stays mapped
}

// Screen RAM: rows 0-2 point to the status characters, rows 3-24 to a
// framebuffer; both stored column by column.
static void build_screen(uint16_t screen, uint8_t fb_bank) {
    static uint8_t row[LINESTEP];
    uint16_t fb_char = (uint16_t)fb_bank << 10;  // bank * 64K / 64
    const uint16_t st_char = ((uint32_t)STATUS_BANK << 10) + STATUS_OFF / 64;
    for (uint8_t r = 0; r < ROWS; r++) {
        for (uint8_t c = 0; c < COLS; c++) {
            uint16_t ch = r < STATUS_ROWS ? st_char + c * STATUS_ROWS + r : fb_char + c * 22 + (r - STATUS_ROWS);
            row[c * 2] = (uint8_t)ch;
            row[c * 2 + 1] = ch >> 8;
        }
        dma_begin(0, 0);
        dma_copy((uint16_t)row, 0, screen + r * LINESTEP, SCREEN_BANK, LINESTEP);
        dma_run();
    }
}

static uint8_t status_code[COLS];

void video_init(void) {
    // 40x25 characters at the standard position: let the "hot" VIC-II
    // registers set up the VIC-IV, then take over.
    POKE(0xD031, (PEEK(0xD031) & ~0xA8) | 0x40);  // no H640/V400/attributes; fast
    POKE(0xD016, 0xC8);
    POKE(0xD011, 0x1B);
    text_x = PEEK(0xD04C) | ((PEEK(0xD04D) & 0x0F) << 8);
    text_y = PEEK(0xD04E) | ((PEEK(0xD04F) & 0x0F) << 8);
    bottom = PEEK(0xD04A) | ((PEEK(0xD04B) & 0x0F) << 8);
    POKE(0xD05D, PEEK(0xD05D) & 0x7F);  // hot registers off

    // Side borders one character wider: hides the scrolled-in column
    uint16_t side = (PEEK(0xD05C) | ((PEEK(0xD05D) & 0x3F) << 8)) + 16;
    POKE(0xD05C, (uint8_t)side);
    POKE(0xD05D, (PEEK(0xD05D) & 0xC0) | (side >> 8));

    POKE(0xD020, 0);
    POKE(0xD021, 0);
    POKE(0xD015, 0);                    // no sprites
    POKE(0xD054, PEEK(0xD054) | 0x47);  // 16-bit chars, full colour for all, fast
    POKE(0xD058, LINESTEP);
    POKE(0xD059, 0);
    POKE(0xD05E, COLS);
    POKE(0xD064, 0);                    // colour RAM from its start
    POKE(0xD065, 0);
    set_palette();

    // Colour RAM all 0 (no attributes): its first 2K at $D800
    POKE(0xD030, PEEK(0xD030) | 0x01);
    for (uint16_t i = 0; i < ROWS * LINESTEP; i++)
        POKE(0xD800 + i, 0);
    POKE(0xD030, PEEK(0xD030) & ~0x01);

    // Framebuffers and status black, separator line drawn; the tiles
    // black until they are loaded (or if they are not on the disk)
    dma_begin(0, 0);
    dma_fill(0, 0x0000, FB_BANK_A, 0);           // 0 = 64K
    dma_fill(0, 0x0000, FB_BANK_B, 0);
    dma_fill(0, TILES_OFF, GFX_BANK, TILE_COUNT * 256);
    for (uint8_t c = 0; c < COLS; c++)
        dma_copy((uint16_t)sep_gfx, 0, STATUS_OFF + c * (STATUS_ROWS * 64) + 128, STATUS_BANK, 64);
    dma_run();
    for (uint8_t c = 0; c < COLS; c++)
        status_code[c] = ' ';

    build_screen(SCREEN_A, FB_BANK_A);
    build_screen(SCREEN_B, FB_BANK_B);
    POKE(0xD060, (uint8_t)SCREEN_A);
    POKE(0xD061, SCREEN_A >> 8);
    POKE(0xD062, SCREEN_BANK);
    POKE(0xD063, 0);
    back = 1;
}

// ---------------------------------------------------------------- frame

static uint16_t raster(void) {
    uint8_t lo, hi;
    do {
        hi = PEEK(0xD053);
        lo = PEEK(0xD052);
    } while (hi != PEEK(0xD053));
    return ((hi & 7) << 8) | lo;
}

static void wait_raster(uint16_t from, uint16_t to) {
    uint16_t r;
    do
        r = raster();
    while (r < from || r >= to);
}

static void set_text_x(uint16_t x) {
    POKE(0xD04C, (uint8_t)x);
    POKE(0xD04D, (PEEK(0xD04D) & 0xF0) | (x >> 8));
}

void video_sync(void) {
    // Separator row: 2 rows of 16 raster lines below the top of the text.
    // Each of its pixel rows is a single colour, so shifting it is invisible.
    wait_raster(text_y + 34, text_y + 46);
    set_text_x(text_x - 2 * shown_fx);
}

void video_show(void) {
    wait_raster(bottom + 2, bottom + 40);
    uint16_t scr = back ? SCREEN_B : SCREEN_A;
    POKE(0xD060, (uint8_t)scr);
    POKE(0xD061, scr >> 8);
    set_text_x(text_x);
    shown_fx = drawn_fx;
    back ^= 1;
}

// One copy job in the list at p (see dma_job), written inline: this runs
// about 480 times a frame.
#define JOB(p, src, dst, bank, len)    \
    do {                               \
        uint16_t s_ = (src);           \
        uint16_t d_ = (dst);           \
        uint16_t l_ = (len);           \
        (p)[0] = 4;                    \
        (p)[1] = (uint8_t)l_;          \
        (p)[2] = l_ >> 8;              \
        (p)[3] = (uint8_t)s_;          \
        (p)[4] = s_ >> 8;              \
        (p)[5] = GFX_BANK;             \
        (p)[6] = (uint8_t)d_;          \
        (p)[7] = d_ >> 8;              \
        (p)[8] = (bank);               \
        (p)[9] = 0;                    \
        (p)[10] = 0;                   \
        (p)[11] = 0;                   \
        (p) += 12;                     \
    } while (0)

// A sprite job (see dma_job): its own options first, then the job. DMA
// transparency for pixel value 0, the skip rate for source and target.
#define SPRITE_JOB 19

#define SJOB(p, step, src, dst, bank, len) \
    do {                                   \
        uint16_t s_ = (src);               \
        uint16_t d_ = (dst);               \
        (p)[0] = 0x07;                     \
        (p)[1] = 0x86;                     \
        (p)[2] = 0x00;                     \
        (p)[3] = 0x83;                     \
        (p)[4] = (step);                   \
        (p)[5] = 0x85;                     \
        (p)[6] = (step);                   \
        (p)[7] = 0x00;                     \
        (p)[8] = 4;                        \
        (p)[9] = (len);                    \
        (p)[10] = 0;                       \
        (p)[11] = (uint8_t)s_;             \
        (p)[12] = s_ >> 8;                 \
        (p)[13] = GFX_BANK;                \
        (p)[14] = (uint8_t)d_;             \
        (p)[15] = d_ >> 8;                 \
        (p)[16] = (bank);                  \
        (p)[17] = 0;                       \
        (p)[18] = 0;                       \
        (p) += SPRITE_JOB;                 \
    } while (0)

// The sprites go into a list of their own, after the cells are drawn: the
// options are set by every job, so it does not matter whether the DMA keeps
// them from one chained job to the next. A full list is run and started
// again.
static uint8_t *sprite_list(void) {
    uint8_t *p = DMA_LIST;
    p[0] = 0x0A;
    p[1] = 0x80;
    p[2] = 0x00;
    p[3] = 0x81;
    p[4] = 0x00;
    return p + 5;
}

static uint8_t *sprite_run(uint8_t *p) {
    if (p != DMA_LIST + 5) {
        dma_last = p - SPRITE_JOB + 8;
        dma_run();
    }
    return sprite_list();
}

// A sprite at pixel column x of the framebuffer (any), its rows r0 to
// r0 + rows - 1 at pixel row y + r0 of the view. On a character column it
// is two copies of a tile half; otherwise one copy per pixel column, from
// one byte in 8 of the tile to one in 8 of the framebuffer column.
static uint8_t *sprite_jobs(uint8_t *p, int16_t x, uint16_t src, uint16_t dst, uint8_t rows, uint8_t bank) {
    if (!(x & 7)) {
        for (uint8_t h = 0; h < 2; h++, x += 8, src += 128)
            if (x >= 0 && x < COLS * 8)
                SJOB(p, 1, src, dst + (x >> 3) * FB_COL, bank, rows * 8);
        return p;
    }
    for (uint8_t k = 0; k < 16; k++, x++, src++) {
        if (k == 8)
            src += 128 - 8;
        if (x >= 0 && x < COLS * 8)
            SJOB(p, 8, src, dst + (x >> 3) * FB_COL + (x & 7), bank, rows);
    }
    return p;
}

static void draw_sprites(const Sprite *s, uint8_t n, uint16_t cam_x, uint16_t cam_y, uint8_t bank) {
    const uint16_t left = (cam_x & ~7) - 8;  // cave pixel column of FB column 0
    uint8_t *p = sprite_list();
    for (; n; n--, s++) {
        int16_t x = (int16_t)(s->x - left);
        int16_t y = (int16_t)(s->y - cam_y);
        if (x <= -16 || x >= COLS * 8 || y <= -16 || y >= VIEW_H)
            continue;
        uint8_t r0 = y < 0 ? (uint8_t)-y : 0;
        uint8_t rows = 16 - r0;
        if (y + 16 > VIEW_H)
            rows -= y + 16 - VIEW_H;
        if (p > DMA_LIST + DMA_JOBS * 12 - 16 * SPRITE_JOB)
            p = sprite_run(p);
        p = sprite_jobs(p, x, TILES_OFF + (s->tile << 8) + r0 * 8, (y + r0) * 8, rows, bank);
    }
    sprite_run(p);
}

void video_render(const uint8_t *tiles, uint16_t cam_x, uint16_t cam_y, const Sprite *sprites, uint8_t n) {
    const uint8_t bank = back ? FB_BANK_B : FB_BANK_A;
    int8_t wc = (int8_t)(cam_x >> 3) - 1;  // cave character column of FB column 0
    const uint8_t yo = cam_y & 15;          // pixel rows of the top tiles above the view
    const uint8_t first = 16 - yo;
    const uint8_t *top = tiles + (cam_y >> 4) * CAVE_W;
    const uint16_t space = TILES_OFF + T_SPACE * 256;
    uint16_t dcol = 0;
    uint8_t *p;

    drawn_fx = cam_x & 7;
    dma_begin(0, 0);
    p = dma_p;
    for (uint8_t c = 0; c < COLS; c++, wc++, dcol += FB_COL) {
        const uint8_t *tp = top + (wc >> 1);
        uint16_t gfx = TILES_OFF + ((wc & 1) ? 128 : 0);
        bool outside = wc < 0 || wc >= CAVE_W * 2;
        uint16_t d = dcol + first * 8;
        uint8_t y = first;
        JOB(p, outside ? space : gfx + (*tp << 8) + yo * 8, dcol, bank, first * 8);
        for (tp += CAVE_W; y + 16 <= VIEW_H; y += 16, d += 128, tp += CAVE_W)
            JOB(p, outside ? space : gfx + (*tp << 8), d, bank, 128);
        if (y < VIEW_H)
            JOB(p, outside ? space : gfx + (*tp << 8), d, bank, (VIEW_H - y) * 8);
    }
    dma_last = p - 12;
    dma_run();
    if (n)
        draw_sprites(sprites, n, cam_x, cam_y, bank);
}

void video_flash(bool on) {
    uint8_t v = on ? 0xFF : 0x00;
    POKE(0xD100, v);
    POKE(0xD200, v);
    POKE(0xD300, v);
}

// ---------------------------------------------------------------- status

static uint8_t font_index(uint8_t ch) {
    uint8_t gi = 0;
    while (font_chars[gi] && font_chars[gi] != ch)
        gi++;
    if (!font_chars[gi])  // unknown character: space
        for (gi = 0; font_chars[gi] != ' '; gi++)
            ;
    return gi;
}

static uint8_t glyph[512];

// Colour a character of the font into glyph[] (8x16, rows of 8 bytes), with
// the palette entry rows[r] for pixel row r, and return where its pixels
// are: glyph[] or, for an icon, the icon itself.
static uint16_t make_glyph(uint8_t ch, const uint8_t *rows) {
    if (ch >= 0x80)
        return (uint16_t)icon_gfx + (ch & 0x7F) * 128;
    const uint8_t *b = font_bits + font_index(ch) * 16;
    uint8_t *g = glyph;
    uint8_t prev = 0;
    for (uint8_t r = 0; r < 16; r++) {
        uint8_t bits = b[r];
        uint8_t col_r = rows[r];
        for (uint8_t m = 0x80; m; m >>= 1)
            *g++ = (bits & m) ? col_r : (prev & m) ? FONT_SHADOW : 0;
        prev = bits >> 1;  // shadow: one pixel right and down
    }
    return (uint16_t)glyph;
}

void status_put(uint8_t col, uint8_t ch) {
    if (col >= COLS || status_code[col] == ch)
        return;
    status_code[col] = ch;
    uint16_t src = make_glyph(ch, font_row);
    dma_begin(0, 0);
    dma_copy(src, 0, STATUS_OFF + col * (STATUS_ROWS * 64), STATUS_BANK, 128);
    dma_run();
}

void status_tile(uint8_t col, uint8_t tile) {
    status_code[col] = status_code[col + 1] = 0xFF;  // no character
    uint16_t src = TILES_OFF + (tile << 8);
    uint16_t dst = STATUS_OFF + col * (STATUS_ROWS * 64);
    dma_begin(0, 0);
    dma_copy(src, GFX_BANK, dst, STATUS_BANK, 128);
    dma_copy(src + 128, GFX_BANK, dst + STATUS_ROWS * 64, STATUS_BANK, 128);
    dma_run();
}

uint8_t status_code_at(uint8_t col) {
    return status_code[col];
}

void status_print(uint8_t col, const char *text) {
    while (*text)
        status_put(col++, (uint8_t)*text++);
}

// ---------------------------------------------------------------- title

void video_clear(void) {
    dma_begin(0, 0);
    dma_fill(0, 0x0000, FB_BANK_A, COLS * FB_COL);
    dma_fill(0, 0x0000, FB_BANK_B, COLS * FB_COL);
    dma_run();
    drawn_fx = shown_fx = 0;
}

// Copy len bytes from sbank:src into both framebuffers at column col,
// pixel row y
static void to_both(uint16_t src, uint8_t sbank, uint8_t col, uint8_t y, uint16_t len) {
    uint16_t dst = col * FB_COL + y * 8;
    dma_begin(0, 0);
    dma_copy(src, sbank, dst, FB_BANK_A, len);
    dma_copy(src, sbank, dst, FB_BANK_B, len);
    dma_run();
}

void video_logo(uint8_t col, uint8_t y) {
    uint16_t src = LOGO_OFF;  // LOAD skipped the file's load address
    dma_begin(0, 0);
    for (uint8_t c = 0; c < LOGO_W / 8; c++, src += LOGO_H * 8) {
        uint16_t dst = (col + c) * FB_COL + y * 8;
        dma_copy(src, GFX_BANK, dst, FB_BANK_A, LOGO_H * 8);
        dma_copy(src, GFX_BANK, dst, FB_BANK_B, LOGO_H * 8);
    }
    dma_run();
}

void video_text_in(uint8_t col, uint8_t y, const char *text, const uint8_t *rows) {
    for (; *text; text++, col++)
        to_both(make_glyph((uint8_t)*text, rows), 0, col, y, 128);
}

void video_text(uint8_t col, uint8_t y, const char *text) {
    video_text_in(col, y, text, font_row);
}

void video_tile(uint8_t col, uint8_t y, uint8_t tile) {
    uint16_t src = TILES_OFF + (tile << 8);
    to_both(src, GFX_BANK, col, y, 128);
    to_both(src + 128, GFX_BANK, col + 1, y, 128);
}

void video_blank(uint8_t col, uint8_t y, uint8_t cols, uint8_t h) {
    dma_begin(0, 0);
    for (uint16_t dst = col * FB_COL + y * 8; cols--; dst += FB_COL) {
        dma_fill(0, dst, FB_BANK_A, h * 8);
        dma_fill(0, dst, FB_BANK_B, h * 8);
    }
    dma_run();
}

// Twice the size: 16x32 pixels per character in the shining title colours,
// drawn as two strips of 8x32.
void video_big_text(uint8_t col, uint8_t y, const char *text) {
    for (; *text; text++, col += 2) {
        const uint8_t *b = font_bits + font_index((uint8_t)*text) * 16;
        uint8_t *g = glyph;
        // x counts from a start fixed per strip: a loop bound of
        // half * 8 + 8 was miscompiled (its counter never went up)
        for (uint8_t x0 = 0; x0 < 16; x0 += 8)
            for (uint8_t r = 0; r < 32; r++)
                for (uint8_t i = 0; i < 8; i++) {
                    uint8_t x = x0 + i;
                    uint8_t on = b[r >> 1] & (0x80 >> (x >> 1));
                    uint8_t sh = r >= 2 && x >= 2 && (b[(r - 2) >> 1] & (0x80 >> ((x - 2) >> 1)));
                    *g++ = on ? title_row[r >> 1] : sh ? FONT_SHADOW : 0;
                }
        to_both((uint16_t)glyph, 0, col, y, 256);
        to_both((uint16_t)glyph + 256, 0, col + 1, y, 256);
    }
}

void video_shine(uint8_t phase) {
    for (uint8_t i = 0; i < 16; i++) {
        uint8_t from = title_row[(i + phase) & 15];
        uint8_t to = title_row[i];
        POKE(0xD100 + to, pal_r[from]);
        POKE(0xD200 + to, pal_g[from]);
        POKE(0xD300 + to, pal_b[from]);
    }
}
