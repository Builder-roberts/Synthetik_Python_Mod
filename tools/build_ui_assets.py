"""build_ui_assets.py

One-off pipeline that turns the reference screenshots / wiki images into the
icon files used by the redesigned Editor tab (assets/ui/**).  The generated
PNGs ARE committed/shipped, so you only need to re-run this if the source
images change.

Expected layout of the source folder (--src, default ./ui_sources):
    specialist_modules.png commando_modules.png guardian_modules.png rouge_modules.png
    Loadout_section.png class_selector_section.png challenges_section.png
    cores_1.png cores_2.png artifacts.png
    classes/*.webp  Artifacts_-_SYNTHETIK_Wiki/*.webp  Gamemodes_-_SYNTHETIK_Wiki/*.webp

Outputs (all keyed by the game's object IDs, so display-name typos in
synthetik_data.py can't break the lookup):
    assets/ui/perks/<obj_perk_x>.png      white-on-transparent glyph masks (tinted at runtime)
    assets/ui/cores/<obj_perk_x>.png      full-colour class core emblems
    assets/ui/artefacts/<obj_artefact_x>.png
    assets/ui/modes/<obj_artefact_x>.png
    assets/ui/misc/*.png                  heart, stars, chevrons, refresh, random module
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import synthetik_data as d  # noqa: E402


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def runs(flags, gap=1):
    """Contiguous True-runs in a 1-D bool array, merging runs closer than `gap`."""
    out, start, last = [], None, None
    for i, flag in enumerate(flags):
        if flag:
            if start is None:
                start = i
            last = i
        elif start is not None and i - last > gap:
            out.append((start, last))
            start = None
    if start is not None:
        out.append((start, last))
    return out


def smoothstep(a, lo, hi):
    t = np.clip((a - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def to_square(img, pad=2):
    """Centre an RGBA image on a transparent square canvas."""
    side = max(img.width, img.height) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def upscale_mask(alpha01, factor=2):
    """Upscale a float alpha mask and re-sharpen its edges (glyphs are flat shapes)."""
    img = Image.fromarray((alpha01 * 255).astype("uint8"), "L")
    img = img.resize((img.width * factor, img.height * factor), Image.LANCZOS)
    a = np.asarray(img).astype(float) / 255
    return smoothstep(a, 0.30, 0.70)


def keyed_alpha(rgb, bg, fg=None, min_diff=30.0):
    """Alpha by projecting each pixel onto the (bg -> fg) colour axis."""
    rgb = rgb.astype(float)
    diff = np.sqrt(((rgb - bg) ** 2).sum(axis=-1))
    if fg is None:
        top = diff >= diff.max() * 0.8
        fg = np.median(rgb[top], axis=0)
    axis = fg - bg
    t = ((rgb - bg) * axis).sum(axis=-1) / max((axis ** 2).sum(), 1e-6)
    a = np.clip(t, 0, 1)
    a[diff < min_diff * 0.5] = 0
    return a, fg


def color_icon_from_flat_bg(crop_rgb, bg, lo=18.0, hi=60.0):
    """Cut a multi-colour icon out of a (nearly) flat background by colour distance."""
    arr = crop_rgb.astype(float)
    diff = np.sqrt(((arr - bg) ** 2).sum(axis=-1))
    alpha = smoothstep(diff, lo, hi)
    out = np.dstack([arr, alpha * 255]).astype("uint8")
    return Image.fromarray(out, "RGBA")


def trim(img, thresh=8):
    box = img.getchannel("A").point(lambda v: 255 if v > thresh else 0).getbbox()
    return img.crop(box) if box else img


# ----------------------------------------------------------------------------
# 1. class perk glyphs (4 screenshots x ~16 rows)
# ----------------------------------------------------------------------------
# (file, first data index of the class's perk block, number of perks).  The
# screenshots list perks bottom-of-range first, i.e. in REVERSE data order.
PERK_SHEETS = [
    ("specialist_modules.png", 23, 16),
    ("commando_modules.png", 47, 15),
    ("rouge_modules.png", 73, 15),
    ("guardian_modules.png", 98, 16),
]


def build_perks(src, out):
    report = {}
    for fname, first, count in PERK_SHEETS:
        rgb = np.asarray(Image.open(os.path.join(src, fname)).convert("RGB")).astype(float)
        bg_rows = rgb[:, 0:6, :].mean(axis=1, keepdims=True)         # left margin = local bg
        diff = np.sqrt(((rgb - bg_rows) ** 2).sum(axis=2))
        strong = diff > 60
        col_runs = runs(strong.any(axis=0), gap=6)
        x0, x1 = col_runs[0]                                        # first column group = icons
        row_runs = runs(strong[:, : x1 + 1].any(axis=1), gap=12)   # gap=12 keeps split glyphs whole
        assert len(row_runs) == count, f"{fname}: found {len(row_runs)} icons, expected {count}"
        ids = d.VAR_MODULES[first : first + count][::-1]            # top-to-bottom order
        for (y0, y1), obj_id in zip(row_runs, ids):
            y0, y1 = max(0, y0 - 3), min(rgb.shape[0] - 1, y1 + 3)
            crop = rgb[y0 : y1 + 1, max(0, x0 - 3) : x1 + 4, :]
            bg = bg_rows[y0 : y1 + 1].mean(axis=0)[0]
            alpha, _ = keyed_alpha(crop, bg)
            alpha = upscale_mask(alpha, 2)
            rgba = np.zeros(alpha.shape + (4,), "uint8")
            rgba[..., :3] = 255
            rgba[..., 3] = (alpha * 255).astype("uint8")
            img = to_square(trim(Image.fromarray(rgba, "RGBA")), pad=4)
            img.save(os.path.join(out, "perks", obj_id + ".png"))
            report[obj_id] = img.size
    return report


# ----------------------------------------------------------------------------
# 2. cores (7 class emblems from the wiki zip + Charge/Rank Up/Calm from screenshots)
# ----------------------------------------------------------------------------
# zip file suffix -> core object id (identified by eye: see contact sheet)
CORE_ZIP = {
    "1794213271878": "obj_perk_riotguard",    # Unyielding
    "1794213271886": "obj_perk_assassin",     # Professional
    "1794213271888": "obj_perk_assaultgunner",  # Suppression
    "1794213271889": "obj_perk_marksman",     # Spotter
    "1794213271890": "obj_perk_raider",       # Looter
    "1794213271897": "obj_perk_engineer",     # Drone Zeal
    "1794213271898": "obj_perk_demolisher",   # HE-Ammo
}


def build_cores(src, out):
    for suffix, obj_id in CORE_ZIP.items():
        path = glob.glob(os.path.join(src, "classes", f"*{suffix}.webp"))[0]
        img = trim(Image.open(path).convert("RGBA"))
        to_square(img, 2).save(os.path.join(out, "cores", obj_id + ".png"))

    # The remaining three only exist inside the blue "core picker" screenshots.
    # NOTE: cores_1.png is the Looter/HE-Ammo/Drone Zeal/Calm/Unyielding list and
    # cores_2.png is the Charge/Professional/Spotter/Rank Up/Suppression list.
    # Each row is a flat blue panel, so detect the row spans, then cut the icon
    # out of its row by colour distance to the row colour.
    for fname, row_index, obj_id in [
        ("cores_2.png", 0, "obj_perk_breacher"),      # Charge
        ("cores_2.png", 3, "obj_perk_squadleader"),   # shown in game as "Rank Up"
        ("cores_1.png", 3, "obj_perk_commando"),      # shown in game as "Calm"
    ]:
        arr = np.asarray(Image.open(os.path.join(src, fname)).convert("RGB"))
        spans = core_row_spans(arr)
        y0, y1 = spans[row_index]
        rows = arr[y0 + 3 : y1 - 2].astype(float)
        crop = rows[:, 20:86, :]
        # The row colour has a horizontal gradient, so interpolate the background per
        # row between a clean strip left of the icon and one between icon and text.
        left = rows[:, 14:19, :].mean(axis=1)[:, None, :]
        right = rows[:, 86:89, :].mean(axis=1)[:, None, :]
        t = np.linspace(0, 1, crop.shape[1])[None, :, None]
        bg = left * (1 - t) + right * t
        img = color_icon_from_flat_bg(crop, bg, lo=22, hi=60)
        to_square(trim(img), 2).save(os.path.join(out, "cores", obj_id + ".png"))


def core_row_spans(arr, row_rgb=(23, 126, 206)):
    """y-spans of the blue rows in a core-picker screenshot (sampled at a clean column)."""
    col = arr[:, 330, :].astype(int)
    near = np.abs(col - np.array(row_rgb)).sum(axis=1) < 30
    spans = runs(near, gap=2)
    assert len(spans) == 5, spans
    return spans


# ----------------------------------------------------------------------------
# 3. artefacts + modes (wiki images)
# ----------------------------------------------------------------------------
# wiki zip file suffix -> object id.  Matched against the named icons in
# artifacts.png by silhouette comparison (IoU >= 0.91 for all but Kevv/Kokova,
# which the wiki's sticky header covered in the screenshot; those two were
# identified by their visible slivers and by elimination).
ARTEFACT_ZIP = {
    "5703": "obj_artefact_shop",        # Aeon-FFD
    "5705": "obj_artefact_weaponcarry",  # Ensiferum
    "5707": "obj_artefact_strafe",      # Cario
    "5718": "obj_artefact_ultradrop",   # Kevv
    "5719": "obj_artefact_terrorlevel",  # PU-55
    "5720": "obj_artefact_healing",     # Kokova
    "5722": "obj_artefact_slowdown",    # Mael
    "5723": "obj_artefact_pistol",      # Luka
    "5726": "obj_artefact_ricochet",    # Hobb-S
    "5732": "obj_artefact_friendlyfire",  # Rhett
    "5733": "obj_artefact_elemental",   # Rynn
    "5737": "obj_artefact_itemupgrade",  # Zion
    "5738": "obj_artefact_buff",        # Savnt
}
# Not in the wiki zip -> cropped from artifacts.png: (x0, y0, x1, y1) of the icon,
# stopping above the grey description card.
ARTEFACT_CROPS = {
    "obj_artefact_powerup": (488, 835, 580, 902),  # Pure 759
    "obj_artefact_crit": (488, 1262, 580, 1329),   # Taro
}
# Gamemodes wiki images carry no names in the zip.  BEST GUESS - verify!  Edit here.
MODE_ZIP = {
    "3555": "obj_artefact_tactical",       # chip
    "3545": "obj_artefact_instagib",       # ribbon  (Hyper Adrenaline)
    "3556": "obj_artefact_madness",        # lattice
    "3557": "obj_artefact_mysterybonus",   # cubes
}


def build_artefacts_and_modes(src, out):
    for suffix, obj_id in ARTEFACT_ZIP.items():
        path = glob.glob(os.path.join(src, "Artifacts_-_SYNTHETIK_Wiki", f"*{suffix}.webp"))[0]
        to_square(trim(Image.open(path).convert("RGBA")), 2).save(os.path.join(out, "artefacts", obj_id + ".png"))
    sheet = np.asarray(Image.open(os.path.join(src, "artifacts.png")).convert("RGB"))
    for obj_id, (x0, y0, x1, y1) in ARTEFACT_CROPS.items():
        crop = sheet[y0:y1, x0:x1]
        bg = np.array([29, 34, 38], float)
        img = color_icon_from_flat_bg(crop, bg, lo=22, hi=70)
        to_square(trim(img), 2).save(os.path.join(out, "artefacts", obj_id + ".png"))
    for suffix, obj_id in MODE_ZIP.items():
        path = glob.glob(os.path.join(src, "Gamemodes_-_SYNTHETIK_Wiki", f"*{suffix}.webp"))[0]
        to_square(trim(Image.open(path).convert("RGBA")), 2).save(os.path.join(out, "modes", obj_id + ".png"))


# ----------------------------------------------------------------------------
# 4. small UI glyphs cut from the section screenshots
# ----------------------------------------------------------------------------
def build_misc(src, out):
    misc = os.path.join(out, "misc")
    classes = np.asarray(Image.open(os.path.join(src, "class_selector_section.png")).convert("RGB"))
    chall = np.asarray(Image.open(os.path.join(src, "challenges_section.png")).convert("RGB"))
    loadout = np.asarray(Image.open(os.path.join(src, "Loadout_section.png")).convert("RGB"))
    cores2 = np.asarray(Image.open(os.path.join(src, "cores_2.png")).convert("RGB"))

    # Rank chevrons (flat gold on the dark challenge rows): 6 level rows, top to bottom.
    gold = np.array([255, 190, 40], float)
    strip = chall[:, 296:332, :].astype(float)
    bg = np.array([25, 20, 50], float)
    alpha, _ = keyed_alpha(strip, bg, fg=gold, min_diff=40)
    spans = runs((alpha > 0.35).any(axis=1) & (np.arange(chall.shape[0]) < 185), gap=4)
    # The Level 20 / Level 25 chevrons are tall enough to touch: split an oversized
    # run at its thinnest row.
    split = []
    for y0, y1 in spans:
        if y1 - y0 > 36:
            rowsum = alpha[y0 : y1 + 1].sum(axis=1)
            lo, hi = int((y1 - y0) * 0.35), int((y1 - y0) * 0.65)
            cut = y0 + lo + int(np.argmin(rowsum[lo:hi]))
            split += [(y0, cut - 1), (cut + 1, y1)]
        else:
            split.append((y0, y1))
    spans = split
    assert len(spans) == 6, spans
    for i, (y0, y1) in enumerate(spans):
        a = alpha[max(0, y0 - 2) : y1 + 3]
        a = upscale_mask(a, 2)
        rgba = np.zeros(a.shape + (4,), "uint8")
        rgba[..., 0], rgba[..., 1], rgba[..., 2] = 255, 190, 40
        rgba[..., 3] = (a * 255).astype("uint8")
        to_square(trim(Image.fromarray(rgba, "RGBA")), 2).save(os.path.join(misc, f"chevron_{i}.png"))

    # Prestige + challenge stars (full colour) from the first class row.
    for name, (x0, y0, x1, y1) in {"star_prestige": (376, 126, 408, 155), "star_challenge": (376, 155, 408, 186)}.items():
        crop = classes[y0:y1, x0:x1]
        border = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
        bgc = np.median(border, axis=0)
        img = color_icon_from_flat_bg(crop, bgc, lo=18, hi=55)
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
        to_square(trim(img), 2).save(os.path.join(misc, name + ".png"))

    # Refresh icon (grey on navy) -> white mask.
    crop = classes[34:62, 366:398].astype(float)
    bgc = np.median(crop.reshape(-1, 3)[:20], axis=0)
    a, _ = keyed_alpha(crop, bgc, min_diff=40)
    a = upscale_mask(a, 3)
    rgba = np.zeros(a.shape + (4,), "uint8")
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).astype("uint8")
    to_square(trim(Image.fromarray(rgba, "RGBA")), 2).save(os.path.join(misc, "refresh.png"))

    # Power heart (white with a bolt cut-out) from the Rank Up row of the core picker.
    y0, y1 = core_row_spans(cores2)[3]
    crop = cores2[y0 + 4 : y0 + 44, 262:306].astype(float)
    left = cores2[y0 + 4 : y0 + 44, 256:260].astype(float).mean(axis=1)[:, None, :]
    bgc = left
    diff = np.sqrt(((crop - bgc) ** 2).sum(axis=-1))
    a = upscale_mask(smoothstep(diff, 40, 120), 3)
    rgba = np.zeros(a.shape + (4,), "uint8")
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).astype("uint8")
    to_square(trim(Image.fromarray(rgba, "RGBA")), 3).save(os.path.join(misc, "heart.png"))

    # Random-module cube from the last loadout row (flat purple row).
    crop = loadout[536:600, 26:92, :]
    bgc = np.median(crop[:, :3, :].reshape(-1, 3), axis=0)
    img = color_icon_from_flat_bg(crop, bgc, lo=22, hi=60)
    to_square(trim(img), 2).save(os.path.join(misc, "random_module.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(os.path.dirname(HERE), "ui_sources"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "assets", "ui"))
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    for sub in ("perks", "cores", "artefacts", "modes", "misc"):
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)
    stages = args.only.split(",") if args.only else ["perks", "cores", "artefacts", "misc"]
    if "perks" in stages:
        rep = build_perks(args.src, args.out)
        print("perks:", len(rep))
    if "cores" in stages:
        build_cores(args.src, args.out)
        print("cores done")
    if "artefacts" in stages:
        build_artefacts_and_modes(args.src, args.out)
        print("artefacts + modes done")
    if "misc" in stages:
        build_misc(args.src, args.out)
        print("misc done")
