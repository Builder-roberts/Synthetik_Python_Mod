"""ui_theme.py - colours, fonts and PIL drawing helpers for the Editor tab.

The redesigned Editor tab is drawn, not assembled from Tk widgets: every panel
is rendered with Pillow (using the bundled Bebas Neue font and icon PNGs) and
shown as one image on a canvas.  That gives the in-game look, identical on
every machine, with no dependence on Tk/ttk theming or on fonts being installed.
Everything here is pure Pillow - no Tk - so it can be unit-tested headlessly.
"""
import colorsys
import os
import sys
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
UI_ASSETS_DIR = os.path.join(_BASE, "assets", "ui")
FONT_FILE = os.path.join(UI_ASSETS_DIR, "fonts", "BebasNeue-Regular.ttf")

# ---------------------------------------------------------------------------
# Palette (sampled from the in-game screenshots)
# ---------------------------------------------------------------------------
WHITE = (255, 255, 255)
CREAM = (238, 236, 222)        # picker / list text
SOFT_WHITE = (232, 232, 245)
DIM_TEXT = (150, 154, 186)
DIMMER_TEXT = (84, 90, 132)
RED_DONE = (226, 58, 62)       # "completed" numbers on the challenge list

BG_TOP = (23, 27, 74)          # window backdrop gradient
BG_BOTTOM = (9, 11, 33)
CLASS_PANEL = (15, 20, 53)
CLASS_ROW = (27, 35, 74)
CLASS_ROW_HOVER = (39, 50, 100)
CHALLENGE_PANEL = (40, 31, 112)
CHALLENGE_ROW = (21, 17, 45)
CHALLENGE_ROW_HOVER = (37, 29, 82)
PICKER_BG = (13, 17, 48)
PICKER_ROW = (24, 31, 70)
PICKER_ROW_HOVER = (38, 48, 98)
BORDER = (44, 52, 104)

# Glyph colours / hues for the four class families, as used by the game for
# perk icons and for tinting the loadout panel.
FAMILIES = {
    "specialist": {"label": "Specialist", "glyph": (224, 74, 46), "hue": 0.020},
    "commando": {"label": "Commando", "glyph": (62, 178, 72), "hue": 0.345},
    "rogue": {"label": "Rogue", "glyph": (132, 98, 244), "hue": 0.700},
    "guardian": {"label": "Guardian", "glyph": (48, 128, 224), "hue": 0.575},
}
# first digit of a class code -> family (Riot Guard/Breacher = 1x, Sniper/Assassin = 2x, ...)
CLASS_FAMILY = {"1": "guardian", "2": "rogue", "3": "commando", "4": "specialist"}


def family_of_class(class_code):
    return CLASS_FAMILY[str(class_code)[0]]


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def mix(a, b, t):
    """Linear blend of two RGB tuples (t=0 -> a, t=1 -> b)."""
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


# Hand-tuned loadout-panel palettes.  Rogue is derived from the reference purple
# (panel s=.77 v=.56, rows s=.75 v=.81, header card s=.60 v=.83); the other
# three keep the same lightness relationships but are toned down, because a
# straight hue rotation of that purple is neon for green and harsh for blue/red.
_THEMES = {
    "rogue": dict(panel=(50, 33, 143), bar=(36, 23, 112), row=(101, 68, 208), card=(119, 85, 211), accent=(150, 116, 232)),
    "guardian": dict(panel=(24, 62, 138), bar=(16, 46, 106), row=(36, 116, 198), card=(74, 144, 220), accent=(98, 166, 238)),
    "commando": dict(panel=(26, 84, 52), bar=(18, 62, 38), row=(44, 142, 74), card=(78, 172, 104), accent=(100, 198, 124)),
    "specialist": dict(panel=(126, 40, 36), bar=(94, 28, 26), row=(200, 72, 52), card=(224, 104, 78), accent=(240, 124, 94)),
}


def theme_for(family):
    """Colours for the loadout panel (and accents elsewhere) of a class family."""
    base = _THEMES[family]
    return {
        "panel": base["panel"],
        "bar": base["bar"],
        "row": base["row"],
        "row_hover": mix(base["row"], WHITE, 0.14),
        "row_empty": mix(base["row"], base["panel"], 0.4),
        "card": base["card"],
        "accent": base["accent"],
        "glyph": FAMILIES[family]["glyph"],
    }


# ---------------------------------------------------------------------------
# Fonts / text
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def font(size):
    try:
        return ImageFont.truetype(FONT_FILE, int(size))
    except OSError:  # font missing: degrade to Pillow's built-in bitmap font
        return ImageFont.load_default()


def text_width(text, size):
    return font(size).getlength(text)


_text_cache = {}


def _render_text(text, size, color, max_width, min_scale=0.62):
    """-> (RGBA image, y of the middle of the capital letters inside that image)."""
    key = (text, size, color, max_width)
    cached = _text_cache.get(key)
    if cached is not None:
        return cached
    use = size
    if max_width is not None:
        while text_width(text, use) > max_width and use > size * min_scale:
            use -= 1
        if text_width(text, use) > max_width:
            while len(text) > 1 and text_width(text + "...", use) > max_width:
                text = text[:-1]
            text += "..."
    f = font(use)
    _, cap_top, _, cap_bottom = f.getbbox("H")
    _, top, right, bottom = f.getbbox(text)
    img = Image.new("RGBA", (int(right) + 2, int(max(bottom, cap_bottom)) + 3), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((0, 0), text, font=f, fill=tuple(color) + (255,))
    result = (img, (cap_top + cap_bottom) / 2.0)
    if len(_text_cache) > 4000:
        _text_cache.clear()
    _text_cache[key] = result
    return result


def text_image(text, size, color=CREAM, max_width=None):
    """Render `text` as a transparent RGBA image.  If `max_width` is given the
    text is shrunk (down to ~60%) and finally ellipsised to fit."""
    return _render_text(text, size, color, max_width)[0]


def paste_text(dst, text, x, cy, size, color=CREAM, max_width=None, anchor="l"):
    """Draw text on `dst` with the middle of its capital letters on y=`cy`.
    anchor: "l" (x = left edge), "c" (centre) or "r" (right edge).  Returns the
    drawn width."""
    img, cap_mid = _render_text(text, size, color, max_width)
    if anchor == "c":
        x = x - img.width / 2
    elif anchor == "r":
        x = x - img.width
    dst.paste(img, (int(round(x)), int(round(cy - cap_mid))), img)
    return img.width


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------
def vertical_gradient(w, h, top, bottom):
    t = Image.linear_gradient("L").resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), bottom), Image.new("RGB", (w, h), top), t)


def horizontal_gradient(w, h, left, right):
    t = Image.linear_gradient("L").rotate(90).transpose(Image.FLIP_LEFT_RIGHT).resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), right), Image.new("RGB", (w, h), left), t)


def tint(mask, color, opacity=1.0):
    """Recolour an RGBA glyph mask: keep its alpha, replace its colour."""
    out = Image.new("RGBA", mask.size, tuple(color) + (255,))
    alpha = mask.getchannel("A")
    if opacity < 1.0:
        alpha = alpha.point(lambda v: int(v * opacity))
    out.putalpha(alpha)
    return out


def fade(img, opacity):
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * opacity)))
    return out


def fit(img, max_w, max_h):
    """Scale an image to fit inside max_w x max_h keeping its aspect ratio."""
    scale = min(max_w / img.width, max_h / img.height)
    size = (max(1, int(round(img.width * scale))), max(1, int(round(img.height * scale))))
    return img.resize(size, Image.LANCZOS)


def paste_center(dst, src, cx, cy):
    dst.paste(src, (int(round(cx - src.width / 2)), int(round(cy - src.height / 2))), src)


_shape_cache = {}


def hexagon(size, fill, outline=None):
    """Antialiased flat-top... pointy-side hexagon (the purple bullets on the challenge list)."""
    key = ("hex", size, fill, outline)
    if key in _shape_cache:
        return _shape_cache[key]
    s = 6
    big = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    import math
    cx = cy = size * s / 2
    r = size * s / 2 - 1
    pts = [(cx + r * math.cos(math.radians(60 * i - 90)), cy + r * math.sin(math.radians(60 * i - 90))) for i in range(6)]
    d.polygon(pts, fill=tuple(fill) + (255,), outline=(tuple(outline) + (255,)) if outline else None)
    img = big.resize((size, size), Image.LANCZOS)
    _shape_cache[key] = img
    return img


def rect(draw, box, fill):
    draw.rectangle([box[0], box[1], box[2] - 1, box[3] - 1], fill=tuple(fill))


def frame(draw, box, color, width=1):
    x0, y0, x1, y1 = box
    for i in range(width):
        draw.rectangle([x0 + i, y0 + i, x1 - 1 - i, y1 - 1 - i], outline=tuple(color))


def backdrop(w, h):
    """The window backdrop: a deep blue gradient with a soft glow, standing in
    for the blurred city the game draws behind its menus."""
    img = vertical_gradient(w, h, BG_TOP, BG_BOTTOM)
    glow = Image.new("RGB", (w, h), (46, 52, 130))
    mask = Image.radial_gradient("L").resize((int(w * 0.9), int(h * 0.8)))
    mask = mask.point(lambda v: int((255 - v) * 0.28))
    layer = Image.new("L", (w, h), 0)
    layer.paste(mask, (int(w * 0.55), -int(h * 0.15)))
    img.paste(glow, (0, 0), layer)
    return img


def pct_text(raw):
    """'1.250000' -> '+25%' (module power is stored as a multiplier, 1.0 = +0%)."""
    try:
        pct = (float(raw) - 1.0) * 100.0
    except (TypeError, ValueError):
        return "?"
    if abs(pct - round(pct)) < 0.05:
        return f"{pct:+.0f}%"
    return f"{pct:+.1f}%"


def blit(dst, src, x, y):
    """Alpha-composite RGBA `src` onto RGBA `dst` at (x, y) (clipped, premultiplication-safe).
    Use this (not Image.paste) when the destination itself has transparency."""
    x, y = int(round(x)), int(round(y))
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + src.width, dst.width), min(y + src.height, dst.height)
    if x1 <= x0 or y1 <= y0:
        return
    piece = src.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    region = dst.crop((x0, y0, x1, y1))
    dst.paste(Image.alpha_composite(region, piece), (x0, y0))
