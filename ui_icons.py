"""ui_icons.py - what each module/core/pistol looks like and what it's called.

Pure Pillow (no Tk).  Icons are looked up by game object ID (see
tools/build_ui_assets.py for how assets/ui/** is produced); item and weapon art
comes from the existing assets/items and assets/weapons folders.
"""
import os
import re
from collections import namedtuple

from PIL import Image, ImageDraw

import ui_theme as T
from ui_descriptions import DESCRIPTIONS
from synthetik_data import (
    ITEM_IMAGES,
    PLACEHOLDER_IMAGE,
    SHOWN_ITEMS,
    SHOWN_MODULES,
    SHOWN_PISTOLS,
    VAR_MODULES,
    WEAPON_IMAGES,
)

ASSETS_DIR = os.path.dirname(T.UI_ASSETS_DIR)

# ---------------------------------------------------------------------------
# Module catalogue
# ---------------------------------------------------------------------------
ModuleInfo = namedtuple("ModuleInfo", "index obj_id name display sub kind family tab")

# (family, first index in SHOWN_MODULES, count).  Perks run bottom-of-range first
# in the data, i.e. in REVERSE of the order the game lists them.
PERK_BLOCKS = [("specialist", 23, 16), ("commando", 47, 15), ("rogue", 73, 15), ("guardian", 98, 16)]

# In-game perk names, top to bottom, transcribed from the game screenshots.
# Used only for display (data names have a few typos); the save still uses obj ids.
PERK_DISPLAY_TOP_TO_BOTTOM = {
    "specialist": ["Status Extender", "Forged By Fire", "Grenadier", "Chromatic Alloy", "Weapons Deal", "Multiply",
                   "Inner Fire", "Focus", "Well Oiled", "Overdrive", "Elemental Power", "Calculated",
                   "Transmutate", "Unceasing", "Sun Rising", "Force Unleashed"],
    "commando": ["Weapon Drop", "Routine", "Charge", "Specialized Ammo", "Drone Mod", "Field Rations",
                 "Press The Attack", "On The Edge", "Pack A Punch", "Hold Breath", "Madness", "Scarred",
                 "Take Cover", "Killer", "Drill"],
    "rogue": ["Head Hunter", "Switch Position", "Evasive Maneuvers", "Backstab", "Shadow Dance", "Discipline",
              "Keeping Distance", "Perfection", "DMR Conversion", "Power Tuning", "Freeze!", "Keeping Cool",
              "Blood Borne", "Die Hard", "Against The Odds"],
    "guardian": ["I-Frame", "Warmup", "Recovery", "Into Battle", "Aegis MK5 Platinum", "Shielded",
                 "Fortify Position", "Enrage", "Weapon Mastery", "Shield Overclock", "Stimulants",
                 "Scrap Plating", "Bits And Pieces", "Berserk", "Wicked", "Push Forward"],
}

# The ten class cores (loadout slot 0).  Game name + family + which class has it by default.
CORE_DISPLAY = {
    "obj_perk_breacher": "Charge",
    "obj_perk_assassin": "Professional",
    "obj_perk_marksman": "Spotter",
    "obj_perk_squadleader": "Rank Up",     # data name "Squad Leader" - ASSUMED, see README
    "obj_perk_assaultgunner": "Suppression",
    "obj_perk_raider": "Looter",
    "obj_perk_demolisher": "HE-Ammo",
    "obj_perk_engineer": "Drone Zeal",
    "obj_perk_commando": "Calm",           # data name "Commando"   - ASSUMED, see README
    "obj_perk_riotguard": "Unyielding",
}
CORE_FAMILY = {
    "obj_perk_breacher": "guardian", "obj_perk_riotguard": "guardian",
    "obj_perk_marksman": "rogue", "obj_perk_assassin": "rogue",
    "obj_perk_raider": "commando", "obj_perk_assaultgunner": "commando",
    "obj_perk_squadleader": "commando", "obj_perk_commando": "commando",
    "obj_perk_engineer": "specialist", "obj_perk_demolisher": "specialist",
}
# Each class's own core, shown as its emblem in the class list.
CLASS_CORE = {
    "10": "obj_perk_riotguard", "11": "obj_perk_breacher",
    "20": "obj_perk_marksman", "21": "obj_perk_assassin",
    "30": "obj_perk_raider", "31": "obj_perk_assaultgunner",
    "40": "obj_perk_engineer", "41": "obj_perk_demolisher",
}
# Core-picker layout: the game shows two lists of five.
CORE_PICKER_COLUMNS = [
    ["obj_perk_breacher", "obj_perk_assassin", "obj_perk_marksman", "obj_perk_squadleader", "obj_perk_assaultgunner"],
    ["obj_perk_raider", "obj_perk_demolisher", "obj_perk_engineer", "obj_perk_commando", "obj_perk_riotguard"],
]

# Tabs offered by the module picker: id -> label
MODULE_TABS = [
    ("specialist", "Specialist"), ("commando", "Commando"), ("rogue", "Rogue"), ("guardian", "Guardian"),
    ("items", "Items"), ("artefacts", "Artefacts"), ("cores", "Cores"),
]


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def build_catalog():
    """-> list[ModuleInfo], one per entry of SHOWN_MODULES (same indices)."""
    perk_meta = {}
    for family, first, count in PERK_BLOCKS:
        ids = VAR_MODULES[first:first + count][::-1]  # top-to-bottom
        for obj_id, shown in zip(ids, PERK_DISPLAY_TOP_TO_BOTTOM[family]):
            perk_meta[obj_id] = (family, shown)

    out = []
    for index, (obj_id, name) in enumerate(zip(VAR_MODULES, SHOWN_MODULES)):
        sub = ""
        if obj_id in CORE_DISPLAY:
            kind, family = "core", CORE_FAMILY[obj_id]
            display = "Core: " + CORE_DISPLAY[obj_id]
            if _norm(name.replace("Core:", "")) != _norm(CORE_DISPLAY[obj_id]):
                sub = name  # e.g. "Core: Squad Leader" under "Core: Rank Up"
            tab = "cores"
        elif obj_id in perk_meta:
            kind = "perk"
            family, display = perk_meta[obj_id]
            tab = family
        elif obj_id == "obj_perk_randomperk":
            kind, family, display, tab = "random", None, name, "items"
        elif obj_id.startswith("obj_item"):
            kind, family, display, tab = "item", None, name, "items"
        elif name.startswith("Mode:"):
            kind, family, display, tab = "mode", None, name, "artefacts"
        else:
            kind, family, display, tab = "artefact", None, name, "artefacts"
        out.append(ModuleInfo(index, obj_id, name, display, sub, kind, family, tab))
    return out


CATALOG = build_catalog()
BY_NAME = {m.name: m for m in CATALOG}
BY_ID = {m.obj_id: m for m in CATALOG}


# Power (the heart badge) only does something for these kinds of object; pistols,
# items and game modes have no power to edit.
POWER_KINDS = {"perk", "artefact", "core"}


def has_power(name):
    """True if the object called `name` (a pistol or module name) has an editable power."""
    if name in SHOWN_PISTOLS:
        return False
    info = BY_NAME.get(name)
    return info is not None and info.kind in POWER_KINDS


def description_for(name):
    """Wiki description (tooltip text) of the module/artefact called `name`, or "" if there is none."""
    info = BY_NAME.get(name)
    return DESCRIPTIONS.get(info.obj_id, "") if info else ""


def info_for_name(name):
    """ModuleInfo for a slot's current name; objects the catalogue doesn't know
    (the save can hold anything) get a stand-in so they still draw."""
    info = BY_NAME.get(name)
    if info is None and name:
        info = ModuleInfo(-1, name, name, name, "", "unknown", None, "items")
    return info

# item/weapon names the art maps can't match by plain normalisation
ITEM_ALIASES = {"tpgrenadeflash": "Flash Grenade"}
WEAPON_ALIASES = {"tec995personal": "TEC 9.95", "deserteagle50": "Desert Eagle"}
_ITEM_NORM = {_norm(k): k for k in ITEM_IMAGES}
_WEAPON_NORM = {_norm(k): k for k in WEAPON_IMAGES}


def item_art_name(info):
    """Name under which `info` appears in ITEM_IMAGES (None if no art)."""
    key = _norm(info.name)
    if key in ITEM_ALIASES:
        return ITEM_ALIASES[key]
    if key in _ITEM_NORM:
        return _ITEM_NORM[key]
    m = re.match(r"obj_item(\d+)_", info.obj_id)  # fall back to the item number
    if m and int(m.group(1)) < len(SHOWN_ITEMS):
        return SHOWN_ITEMS[int(m.group(1))]
    return None


def weapon_art_name(name):
    key = _norm(name)
    if _norm(WEAPON_ALIASES.get(key, "")) in _WEAPON_NORM:
        return _WEAPON_NORM[_norm(WEAPON_ALIASES[key])]
    return _WEAPON_NORM.get(key)


# ---------------------------------------------------------------------------
# Icon loading
# ---------------------------------------------------------------------------
class IconSet:
    """Cached, sized and tinted icons.  All returns are RGBA PIL images."""

    def __init__(self):
        self._files = {}   # path -> PIL image (or None if missing)
        self._sized = {}   # (key...) -> PIL image

    # -- raw files ---------------------------------------------------------
    def _open(self, path):
        if path not in self._files:
            try:
                self._files[path] = Image.open(path).convert("RGBA")
            except (OSError, ValueError):
                self._files[path] = None
        return self._files[path]

    def _ui(self, sub, obj_id):
        return self._open(os.path.join(T.UI_ASSETS_DIR, sub, obj_id + ".png"))

    @staticmethod
    def _placeholder(size):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([2, 2, size - 3, size - 3], radius=size // 6, outline=(150, 154, 186, 180), width=2)
        return img

    def _cached(self, key, make):
        if key not in self._sized:
            self._sized[key] = make()
        return self._sized[key]

    # -- game art ----------------------------------------------------------
    def art(self, subdir, filename, box_w, box_h):
        """Item / weapon art from assets/<subdir>/ fitted into a box."""
        def make():
            img = self._open(os.path.join(ASSETS_DIR, subdir, filename or PLACEHOLDER_IMAGE))
            if img is None:
                img = self._open(os.path.join(ASSETS_DIR, subdir, PLACEHOLDER_IMAGE))
            if img is None:
                return self._placeholder(min(box_w, box_h))
            return T.fit(img, box_w, box_h)
        return self._cached(("art", subdir, filename, box_w, box_h), make)

    def pistol(self, shown_name, box_w, box_h):
        if not shown_name:  # nothing loaded yet
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        art_name = weapon_art_name(shown_name)
        return self.art("weapons", WEAPON_IMAGES.get(art_name) if art_name else None, box_w, box_h)

    def module(self, info, size, glyph_color=None, opacity=1.0):
        """Icon for a module in a size x size box.  Perk glyphs are tinted:
        `glyph_color` (default: their class colour), e.g. white on the loadout panel."""
        color = glyph_color
        if info.kind == "perk" and color is None:
            color = T.FAMILIES[info.family]["glyph"]

        def make():
            if info.kind == "perk":
                mask = self._ui("perks", info.obj_id)
                if mask is None:
                    return self._placeholder(size)
                return T.tint(T.fit(mask, size, size), color, opacity)
            if info.kind == "core":
                img = self._ui("cores", info.obj_id)
            elif info.kind == "artefact":
                img = self._ui("artefacts", info.obj_id)
            elif info.kind == "mode":
                img = self._ui("modes", info.obj_id)
            elif info.kind == "random":
                img = self._open(os.path.join(T.UI_ASSETS_DIR, "misc", "random_module.png"))
            elif info.kind == "unknown":
                return self._placeholder(size)
            else:
                art = item_art_name(info)
                return T.fit(self.art("items", ITEM_IMAGES.get(art) if art else None, size, size), size, size)
            if img is None:
                return self._placeholder(size)
            out = T.fit(img, size, size)
            return T.fade(out, opacity) if opacity < 1 else out
        return self._cached(("mod", info.obj_id, size, color, opacity), make)

    def class_emblem(self, class_code, size):
        return self.module(BY_ID[CLASS_CORE[class_code]], size)

    # -- small UI glyphs ---------------------------------------------------
    def misc(self, name, size, color=None, opacity=1.0):
        def make():
            img = self._open(os.path.join(T.UI_ASSETS_DIR, "misc", name + ".png"))
            if img is None:
                return self._placeholder(size)
            out = T.fit(img, size, size)
            if color is not None:
                out = T.tint(out, color, opacity)
            elif opacity < 1:
                out = T.fade(out, opacity)
            return out
        return self._cached(("misc", name, size, color, opacity), make)

    def star(self, challenge, achieved, size):
        """Prestige (5-point) / challenge (spiky) star; dimmed grey when not achieved."""
        name = "star_challenge" if challenge else "star_prestige"
        if achieved:
            return self.misc(name, size)

        def make():
            base = self.misc(name, size)
            grey = Image.new("RGBA", base.size, (92, 98, 140, 255))
            grey.putalpha(base.getchannel("A").point(lambda v: int(v * 0.55)))
            return grey
        return self._cached(("star_dim", name, size), make)

    def chevron(self, level_index, size, achieved=True):
        name = f"chevron_{level_index}"
        return self.misc(name, size, None if achieved else (88, 80, 120), 1.0 if achieved else 0.8)

    def power_badge(self, raw, color=T.WHITE, heart=22, text_size=15):
        """The heart + "+25%" badge shown beside a module whose power isn't the default.
        A neutral (+0%) badge is drawn faded so it still reads as clickable."""
        txt = T.pct_text(raw)
        try:
            neutral = abs(float(raw) - 1.0) < 1e-9
        except (TypeError, ValueError):
            neutral = False

        def make():
            h = self.misc("heart", heart, color)
            t = T.text_image(txt, text_size, color)
            w = max(h.width, t.width) + 2
            out = Image.new("RGBA", (w, h.height + t.height - 3), (0, 0, 0, 0))
            T.blit(out, h, (w - h.width) // 2, 0)
            T.blit(out, t, (w - t.width) // 2, h.height - 3)
            return T.fade(out, 0.34) if neutral else out
        return self._cached(("badge", txt, color, heart, text_size, neutral), make)
