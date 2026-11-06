"""Draw need-bar style icons (1-100%) using the game's own energy colors.

Colors come from motive_Energy's commodity states in the game tuning:
  0-12.5% red, 12.5-25% orange, 25-37.5% yellow, 37.5%+ green.
"""

import os
import sys

from PIL import Image, ImageDraw

SIZE = 128
STATES = [  # (from percent, fill color, darker color)
    (0.0, (255, 0, 7), (177, 0, 5)),
    (12.5, (255, 90, 0), (178, 54, 0)),
    (25.0, (255, 222, 0), (191, 139, 0)),
    (37.5, (36, 255, 0), (1, 163, 1)),
]
BORDER = (232, 238, 244, 255)
EMPTY = (38, 46, 58, 235)


def colors_for(percent):
    fill, dark = STATES[0][1], STATES[0][2]
    for start, f, d in STATES:
        if percent >= start:
            fill, dark = f, d
    return fill, dark


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(percent):
    """Smooth red -> orange -> yellow -> green spread evenly along the bar,
    using the game's own need-bar colors."""
    stops = [(0.0, (255, 0, 7)), (100 / 3, (255, 90, 0)), (200 / 3, (255, 222, 0)), (100.0, (36, 255, 0))]
    if percent <= stops[0][0]:
        return stops[0][1]
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if percent <= p1:
            return lerp(c0, c1, (percent - p0) / (p1 - p0))
    return stops[-1][1]


def draw_bar(percent, size=SIZE):
    from PIL import ImageChops
    scale = 4  # draw big, shrink for smooth edges
    s = size * scale
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bar_w, bar_h = int(s * 0.90), int(s * 0.30)
    x0 = (s - bar_w) // 2
    y0 = (s - bar_h) // 2
    radius = bar_h // 2
    border = int(s * 0.025)
    d.rounded_rectangle([x0, y0, x0 + bar_w, y0 + bar_h], radius=radius, fill=BORDER)
    ix0, iy0 = x0 + border, y0 + border
    ix1, iy1 = x0 + bar_w - border, y0 + bar_h - border
    w, h = ix1 - ix0, iy1 - iy0
    d.rounded_rectangle([ix0, iy0, ix1, iy1], radius=radius - border, fill=EMPTY)
    fill_w = int(w * max(0.0, min(100.0, percent)) / 100.0)
    if fill_w <= 0:
        return img.resize((size, size), Image.LANCZOS)
    grad = Image.new('RGBA', (w, h))
    px = grad.load()
    for x in range(w):
        base = gradient_color(100.0 * x / max(1, w - 1))
        dark = tuple(int(c * 0.62) for c in base)
        for y in range(h):
            t = (y / max(1, h - 1)) * 0.55  # lighter top, darker bottom like the game
            c = lerp(base, dark, t)
            if y < h * 0.28:  # soft highlight along the top
                c = lerp(c, (255, 255, 255), 0.22)
            px[x, y] = c + (255,)
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius - border, fill=255)
    clip = Image.new('L', (w, h), 0)
    ImageDraw.Draw(clip).rectangle([0, 0, fill_w, h], fill=255)
    img.paste(grad, (ix0, iy0), ImageChops.multiply(mask, clip))
    return img.resize((size, size), Image.LANCZOS)


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for p in range(0, 101):
        draw_bar(p).save(os.path.join(out_dir, 'energybar_{:03d}.png'.format(p)), optimize=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'build', 'icons'))
