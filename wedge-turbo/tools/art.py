"""Wedge Turbo's own drawings for the screens (tools/mkpages.py): the car
from the side and from the front, as smooth shapes, drawn four times as
large and scaled down for clean edges."""
import math

from PIL import Image, ImageDraw, ImageFilter

SS = 4  # supersampling


def bezier(points, n=24):
    """Points along a chain of cubic Bezier segments: p0 c1 c2 p1 c1 c2 p2 ..."""
    out = []
    for i in range(0, len(points) - 3, 3):
        p0, c1, c2, p1 = points[i:i + 4]
        for k in range(n):
            t = k / n
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
            out.append((a * p0[0] + b * c1[0] + c * c2[0] + d * p1[0], a * p0[1] + b * c1[1] + c * c2[1] + d * p1[1]))
    out.append(points[-1])
    return out


# The car from the side, facing right, in units of a 1000-long car: y down,
# the ground at 262. A wedge of the late eighties: a
# high tail, the buttress rising slowly to a short roof, the windscreen
# running into a long bonnet, the nose low.
BODY = [(18, 214),
        (8, 190), (20, 150), (24, 120),            # the rear bumper
        (24, 100), (24, 64), (34, 50),             # the tail
        (90, 50), (150, 50), (190, 42),            # the deck
        (240, 30), (300, 20), (366, 14),           # the buttress up to the roof
        (430, 12), (490, 12), (520, 15),           # the roof
        (575, 30), (630, 60), (690, 76),           # the windscreen
        (790, 100), (890, 125), (950, 150),        # the bonnet
        (978, 156), (984, 190), (968, 204),        # the nose
        (990, 210), (940, 220), (860, 222),        # the spoiler under the nose
        (600, 222), (300, 222), (120, 222),        # the sill
        (60, 224), (30, 222), (18, 214)]
GLASS = [(286, 52),
         (300, 40), (330, 26), (360, 22),
         (420, 20), (490, 20), (520, 22),
         (566, 38), (606, 58), (632, 72),
         (520, 72), (380, 62), (286, 52)]
SPOILER = [(26, 46), (104, 46)]
WHEELS = [(176, 206, 55), (755, 207, 55)]
GROUND = 262


def _mask(size, polys, ellipses=()):
    m = Image.new('L', size, 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon(p, fill=255)
    for e in ellipses:
        d.ellipse(e, fill=255)
    return m


def _vgradient(size, y0, y1, top, bottom):
    g = Image.new('RGBA', size)
    d = ImageDraw.Draw(g)
    for y in range(size[1]):
        t = min(1, max(0, (y - y0) / max(1, y1 - y0)))
        d.line([(0, y), (size[0], y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    return g


def side_view(width, paint=((214, 40, 50), (160, 14, 24), (86, 6, 12)), trim=(18, 18, 22)):
    """The car from the side, width pixels long, on a transparent ground:
    the paint as a gradient from its top colour over its middle to its
    bottom one"""
    s = width * SS / 1000
    size = (width * SS, int(280 * s))
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def pts(ps):
        return [(x * s, y * s) for x, y in ps]

    def ell(cx, cy, r):
        return [((cx - r) * s, (cy - r) * s), ((cx + r) * s, (cy + r) * s)]
    top, mid, low = paint
    # a soft shadow on the ground
    sh = Image.new('RGBA', size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([(50 * s, 248 * s), (970 * s, 276 * s)], fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(10 * s))
    im.alpha_composite(sh)
    # the paint: a gradient in the body's shape, the arches cut out
    body = _mask(size, [pts(bezier(BODY))])
    arches = _mask(size, [], [ell(cx, cy, r + 12) for cx, cy, r in WHEELS])
    body = Image.composite(Image.new('L', size, 0), body, arches)
    grad = _vgradient(size, 10 * s, 225 * s, top, low)
    mid_band = _vgradient(size, 60 * s, 150 * s, top, mid)
    grad.paste(mid_band.crop((0, 0, size[0], int(150 * s))), (0, 0))
    im.paste(grad, (0, 0), body)
    d = ImageDraw.Draw(im)
    # the sills: a darker skirt below the wedge line
    skirt = _mask(size, [pts([(28, 180), (982, 186), (968, 204), (930, 214), (880, 220), (840, 222),
                              (34, 220), (26, 190)])])
    skirt = Image.composite(Image.new('L', size, 0), skirt, arches)
    im.paste(_vgradient(size, 172 * s, 220 * s, mid, low), (0, 0), skirt)
    d = ImageDraw.Draw(im)
    # light: the shoulder line, a reflection along the side
    d.line(pts([(30, 104), (500, 116), (976, 156)]), fill=(255, 190, 190), width=int(3 * s))
    hl = _mask(size, [pts([(700, 92), (840, 112), (920, 136), (780, 114)]), pts([(70, 60), (230, 56), (250, 66), (90, 70)]),
                      pts([(250, 128), (420, 132), (420, 136), (250, 132)])])
    im.paste(Image.new('RGBA', size, (255, 236, 236, 255)), (0, 0), hl.point(lambda v: v * 0.85))
    hl2 = _mask(size, [pts([(600, 100), (700, 104), (860, 126), (700, 112)]), pts([(60, 74), (240, 70), (250, 84), (80, 88)])])
    im.paste(Image.new('RGBA', size, (240, 120, 120, 255)), (0, 0), hl2.point(lambda v: v * 0.6))
    d = ImageDraw.Draw(im)
    refl = _mask(size, [pts([(120, 152), (700, 160), (700, 168), (120, 162)])])
    im.paste(Image.new('RGBA', size, (250, 110, 110, 255)), (0, 0), refl.point(lambda v: v * 0.55))
    d = ImageDraw.Draw(im)
    # the arches: the opening dark inside, a lip around it
    for cx, cy, r in WHEELS:
        d.arc(ell(cx, cy, r + 8), 180, 360, fill=(250, 150, 150), width=int(2 * s))
        d.pieslice(ell(cx, cy, r + 6), 180, 360, fill=(8, 8, 10))
    # the wheels: a thin tyre, five spokes over the brake disc, five bolts
    for cx, cy, r in WHEELS:
        d.ellipse(ell(cx, cy, r), fill=(18, 18, 20))
        rr = r * 0.82
        d.ellipse(ell(cx, cy, rr), fill=(44, 46, 52))
        d.ellipse(ell(cx, cy, rr * 0.78), fill=(92, 94, 100))           # the disc behind
        for k in range(5):
            a = k * 2 * math.pi / 5 - math.pi / 2
            spoke = [(cx + math.cos(a - 0.16) * rr * 0.26, cy + math.sin(a - 0.16) * rr * 0.26),
                     (cx + math.cos(a - 0.30) * rr * 0.96, cy + math.sin(a - 0.30) * rr * 0.96),
                     (cx + math.cos(a + 0.30) * rr * 0.96, cy + math.sin(a + 0.30) * rr * 0.96),
                     (cx + math.cos(a + 0.16) * rr * 0.26, cy + math.sin(a + 0.16) * rr * 0.26)]
            d.polygon(pts(spoke), fill=(200, 204, 212))
            d.line(pts([spoke[0], spoke[1]]), fill=(244, 246, 250), width=int(2 * s))
        d.ellipse(ell(cx, cy, rr), outline=(226, 228, 234), width=int(3 * s))
        d.ellipse(ell(cx, cy, rr * 0.28), fill=(176, 178, 186))
        for k in range(5):
            a = k * 2 * math.pi / 5 - math.pi / 2 + math.pi / 5
            bx, by = cx + math.cos(a) * rr * 0.17, cy + math.sin(a) * rr * 0.17
            d.ellipse(ell(bx, by, rr * 0.04), fill=(40, 40, 46))
    # glass: trim around it, a gradient, two reflections; the B-pillar
    d.polygon(pts(bezier([(278, 54), (292, 38), (326, 22), (358, 18), (420, 16), (492, 16), (524, 18),
                          (570, 36), (612, 58), (642, 76), (520, 76), (380, 66), (278, 54)])), fill=trim)
    glass = _mask(size, [pts(bezier(GLASS))])
    im.paste(_vgradient(size, 20 * s, 72 * s, (84, 94, 116), (22, 26, 34)), (0, 0), glass)
    d = ImageDraw.Draw(im)
    for x0, w in ((440, 40), (500, 14)):
        d.polygon(pts([(x0, 22), (x0 + w, 22), (x0 + w - 48, 68), (x0 - 48, 66)]), fill=(128, 140, 164))
    d.line(pts([(380, 20), (372, 66)]), fill=trim, width=int(7 * s))
    d.ellipse(pts([(592, 56), (626, 72)]), fill=trim)                                 # the mirror
    d.line(pts([(604, 72), (614, 80)]), fill=trim, width=int(4 * s))
    # the door: its edges, the handle; the crease along it; the badge
    d.line(pts([(372, 66), (366, 140), (368, 210)]), fill=(96, 6, 12), width=int(3 * s))
    d.line(pts([(628, 72), (636, 140), (642, 206)]), fill=(96, 6, 12), width=int(3 * s))
    d.rounded_rectangle(pts([(410, 124), (444, 132)]), radius=int(3 * s), fill=(84, 6, 12))
    d.line(pts([(250, 138), (700, 142)]), fill=(150, 14, 24), width=int(2 * s))
    d.line(pts([(250, 141), (700, 145)]), fill=(250, 120, 120), width=int(1 * s))
    d.line(pts([(296, 120), (334, 120)]), fill=(200, 202, 210), width=int(2 * s))
    # the bonnet: the pop-up lights' edge; the nose: intake, indicator
    d.line(pts([(735, 92), (850, 114)]), fill=(150, 14, 24), width=int(2 * s))
    d.line(pts([(850, 114), (856, 124)]), fill=(150, 14, 24), width=int(2 * s))
    d.polygon(pts([(900, 186), (980, 186), (972, 198), (906, 196)]), fill=trim)
    d.rounded_rectangle(pts([(948, 160), (980, 170)]), radius=int(2 * s), fill=(255, 176, 48))
    # the tail: its lights, the bumper
    d.rectangle(pts([(25, 78), (36, 112)]), fill=(255, 46, 36))
    d.rectangle(pts([(25, 114), (36, 122)]), fill=(255, 176, 48))
    d.line(pts([(26, 176), (92, 178)]), fill=trim, width=int(4 * s))
    # the rear wing on the tail: a post, an end plate, its top lit
    d.line(pts([(62, 40), (64, 52)]), fill=trim, width=int(6 * s))
    d.polygon(pts([(22, 36), (106, 38), (110, 46), (24, 48)]), fill=mid)
    d.line(pts([(24, 37), (104, 39)]), fill=(255, 170, 170), width=int(2 * s))
    d.polygon(pts([(18, 30), (34, 30), (34, 52), (18, 52)]), fill=low)
    return im.resize((width, size[1] // SS), Image.LANCZOS)


if __name__ == '__main__':
    import sys
    img = Image.new('RGB', (900, 280), (16, 18, 24))
    car = side_view(820)
    img.paste(car, (40, 20), car)
    img.save(sys.argv[1])
