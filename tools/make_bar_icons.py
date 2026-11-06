"""Draw need-bar style icons (like the game's Needs panel) for every 5% step.

Run with any Python that has Pillow:  python3 tools/make_bar_icons.py
Writes assets/bar_000.png/.dds ... assets/bar_100.png/.dds (128x128, transparent).

Colours follow the game's own energy states: green above 37.5%, yellow
25-37.5%, orange 12.5-25%, red below 12.5%.
"""

import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets')
SIZE = 128
SCALE = 4  # draw big, then shrink for smooth edges

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

COLOURS = [  # (min %, bright, dark-unfilled, rim)
    (37.5, (92, 214, 60), (40, 120, 34), (30, 95, 25)),
    (25.0, (238, 200, 40), (150, 118, 22), (118, 90, 14)),
    (12.5, (245, 140, 35), (150, 78, 18), (120, 60, 12)),
    (0.0, (226, 52, 40), (130, 26, 20), (100, 18, 14)),
]


def colours_for(pct):
    for minimum, bright, dark, rim in COLOURS:
        if pct >= minimum:
            return bright, dark, rim
    return COLOURS[-1][1:]


def lighten(c, amount):
    return tuple(min(255, int(v + (255 - v) * amount)) for v in c)


def draw_icon(pct):
    s = SIZE * SCALE
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bright, dark, rim = colours_for(pct)

    # bar geometry
    bar_h = int(s * 0.34)
    top = (s - bar_h) // 2
    left = int(s * 0.22)
    right = s - int(s * 0.04)
    radius = bar_h // 2

    # rim + unfilled part
    d.rounded_rectangle([left - 6, top - 6, right + 6, top + bar_h + 6], radius + 6, fill=rim)
    d.rounded_rectangle([left, top, right, top + bar_h], radius, fill=dark)

    # filled part: measured from the badge's right edge so low values stay visible
    badge_edge = int(s * 0.21) + int(s * 0.19)
    fill_right = badge_edge + int((right - badge_edge) * pct / 100.0)
    if pct > 0:
        fill_right = max(fill_right, badge_edge + radius // 2)
        d.rounded_rectangle([left, top, fill_right, top + bar_h], radius, fill=bright)
        # gloss on the top half
        gloss = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gloss)
        gd.rounded_rectangle([left + 10, top + 8, fill_right - 10, top + bar_h // 2],
                             radius // 2, fill=lighten(bright, 0.45) + (150,))
        img.alpha_composite(gloss)

    # round badge on the left with "Zz", like the Energy need icon
    cx, cy, r = int(s * 0.21), s // 2, int(s * 0.19)
    d.ellipse([cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8], fill=rim)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=lighten(bright, 0.15))
    d.ellipse([cx - r + 14, cy - r + 10, cx + r - 14, cy - 4], fill=lighten(bright, 0.5))
    try:
        big = ImageFont.truetype(FONT, int(r * 1.15))
        small = ImageFont.truetype(FONT, int(r * 0.75))
    except OSError:
        big = small = ImageFont.load_default()
    d.text((cx - r * 0.62, cy - r * 0.62), 'Z', font=big, fill=(255, 255, 255), stroke_width=6, stroke_fill=rim)
    d.text((cx + r * 0.12, cy - r * 0.05), 'z', font=small, fill=(255, 255, 255), stroke_width=5, stroke_fill=rim)

    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    return img


def draw_gradient_icon(pct):
    """The approved design: a need bar whose fill blends red -> orange ->
    yellow -> green, spread evenly along the bar (see make_icons.py)."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from make_icons import draw_bar
    return draw_bar(pct, SIZE)


def main():
    draw_icon = draw_gradient_icon  # noqa: F811 - use the approved gradient design
    os.makedirs(OUT, exist_ok=True)
    for pct in range(0, 101, 5):
        icon = draw_icon(pct)
        icon.save(os.path.join(OUT, 'bar_{:03d}.png'.format(pct)), optimize=True)
        # The game's menus load icons from DDS image resources (type 00B2D882)
        # with the same ID, so a DXT5 copy is packed too.
        icon.save(os.path.join(OUT, 'bar_{:03d}.dds'.format(pct)), format='DDS', pixel_format='DXT5')
    # contact sheet for checking
    sheet = Image.new('RGBA', (SIZE * 7, SIZE * 3), (40, 60, 110, 255))
    for i, pct in enumerate(range(0, 101, 5)):
        sheet.alpha_composite(draw_gradient_icon(pct), ((i % 7) * SIZE, (i // 7) * SIZE))
    sheet.save(os.path.join(ROOT, 'assets_preview.png'))
    print('wrote', len(os.listdir(OUT)), 'icons')


if __name__ == '__main__':
    main()
