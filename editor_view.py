"""editor_view.py - the in-game-style "Synthetik Editor" tab.

Four drawn panels on one canvas, mirroring the game's loadout screen:

    CLASSES          LOADOUT (pistol card, core, 5 module rows)     CHALLENGES
    (8 classes)                                                      TOOLS (level, insanity,
                                                                           auto module, SUBMIT)

This is only a *view*.  All state still lives in the Root window's existing
variables (pistol_mod, option_mods, power_mods, subclass_lvl, prestige_var, ...)
and all save-file logic is untouched (submit_loadout / change_class); the
panels read those variables to draw themselves, and write to them when you
click something.  Variable changes (from anywhere) trigger a redraw.
"""
import re
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

import editor_pickers
import ui_icons as I
import ui_theme as T
from synthetik_data import CLASS_CODES, SHOWN_PISTOLS
from ui_widgets import Panel, PanelItem, style_entry

# ---- layout (design pixels; the whole composition is centred in the tab) ----
MARGIN, GAP = 24, 16
CLASS_W, LOAD_W, CHAL_W = 330, 300, 300
PANEL_H = 494
CHAL_H = 246
TOOLS_H = PANEL_H - CHAL_H - GAP
DESIGN_W = MARGIN * 2 + CLASS_W + LOAD_W + CHAL_W + GAP * 2
DESIGN_H = MARGIN * 2 + PANEL_H
MIN_SCALE = 0.5  # the composition shrinks to this fraction of its design size as the window gets smaller

# "Changes Submitted" toast timing (seconds)
TOAST_IN, TOAST_HOLD, TOAST_OUT = 0.25, 1.3, 0.6

LEVEL_ROWS = [("Baseline", 0), ("Level 5", 5), ("Level 10", 10), ("Level 15", 15), ("Level 20", 20), ("Level 25", 25)]
INSANITY_CHIPS = [("ski", "400%"), ("sad", "Hyper"), ("sta", "Tactical"), ("sma", "Madness")]
MODULE_ROWS = [1, 2, 3, 4, 5]  # option_mods indexes shown as loadout rows; index 0 is the core


# ===========================================================================
# Classes panel
# ===========================================================================
class ClassPanel(Panel):
    ROW_Y0, ROW_PITCH, ROW_H = 62, 52, 46

    def __init__(self, view):
        super().__init__(CLASS_W, PANEL_H)
        self.view = view

    def render(self, hover):
        v, icons = self.view, self.view.icons
        img = Image.new("RGB", (self.w, self.h), T.CLASS_PANEL)
        d = ImageDraw.Draw(img)
        T.frame(d, (0, 0, self.w, self.h), T.BORDER)
        T.paste_text(img, "CLASSES", 18, 31, 27, T.WHITE)

        hot = hover == ("refresh",)
        T.paste_center(img, icons.misc("refresh", 22, T.WHITE if hot else (146, 152, 188)), self.w - 30, 31)
        self.hits = [((self.w - 50, 12, self.w - 10, 50), ("refresh",))]

        for i, (label, code, _color) in enumerate(CLASS_CODES):
            y = self.ROW_Y0 + i * self.ROW_PITCH
            box = (10, y, self.w - 10, y + self.ROW_H)
            selected = code == v.root.current_class
            level, prestige, challenge = v.class_info(code)
            th = T.theme_for(T.family_of_class(code))
            if selected:
                img.paste(T.horizontal_gradient(box[2] - box[0], self.ROW_H, th["row"], T.mix(th["row"], th["panel"], 0.45)), (box[0], y))
            else:
                T.rect(d, box, T.CLASS_ROW_HOVER if hover == ("class", code) else T.CLASS_ROW)

            cy = y + self.ROW_H // 2
            T.paste_center(img, icons.class_emblem(code, 40), 37, cy)
            name_color = T.WHITE if selected else (178, 181, 206)
            width = T.paste_text(img, label.upper(), 68, cy, 28, name_color)
            level_color = T.mix(th["row"], T.WHITE, 0.55) if selected else T.DIMMER_TEXT
            T.paste_text(img, str(level), 68 + width + 8, cy, 28, level_color)

            sx = self.w - 36
            T.paste_center(img, icons.star(False, prestige >= 1, 18), sx, cy - 11)
            T.paste_center(img, icons.star(True, challenge >= 2, 19), sx, cy + 11)
            self.hits.append((box, ("class", code)))
        return img

    def on_click(self, key):
        if key[0] == "class":
            self.view.root.change_class(key[1])
        elif key[0] == "refresh":
            self.view.root.reload_from_save()


# ===========================================================================
# Loadout panel
# ===========================================================================
class LoadoutPanel(Panel):
    CARD = (8, 8, LOAD_W - 8, 140)
    BAR = (8, 148, LOAD_W - 8, 180)
    ROW_Y0, ROW_PITCH, ROW_H = 188, 60, 52

    def __init__(self, view):
        super().__init__(LOAD_W, PANEL_H)
        self.view = view

    def render(self, hover):
        v, icons, root = self.view, self.view.icons, self.view.root
        th = T.theme_for(v.family)
        img = Image.new("RGB", (self.w, self.h), th["panel"])
        d = ImageDraw.Draw(img)
        self.hits = []

        # ---- header card: class + level, pistol art, core strip ------------------
        x0, y0, x1, y1 = self.CARD
        img.paste(T.vertical_gradient(x1 - x0, y1 - y0, T.mix(th["card"], T.WHITE, 0.10), th["card"]), (x0, y0))
        # The pistol slot holds a pistol - or anything else a loadout row can hold.
        slot_name = root.pistol_mod.get()
        art_box = (x0 + 70, y0 + 32, x1 - 54, y0 + 100)
        if hover == ("pistol",):
            T.rect(d, art_box, T.mix(th["card"], T.WHITE, 0.14))
        label = v.class_label.upper()
        width = T.paste_text(img, label, x0 + 14, y0 + 24, 33, T.WHITE)
        T.paste_text(img, str(v.level), x0 + 14 + width + 9, y0 + 24, 33, T.mix(th["card"], T.WHITE, 0.50))
        # the art is drawn over the title, like the game's overlapping gun
        art_cx, art_w = (art_box[0] + art_box[2]) / 2, art_box[2] - art_box[0] - 4
        if slot_name in SHOWN_PISTOLS:
            art, caption = icons.pistol(slot_name, art_w, 46), slot_name
        else:
            slot_info = I.info_for_name(slot_name)
            art = icons.module(slot_info, 46, T.WHITE if slot_info and slot_info.kind == "perk" else None) if slot_info else None
            caption = slot_info.display if slot_info else ""
        if art is not None:
            T.paste_center(img, art, art_cx, y0 + 54)
        T.paste_text(img, caption.upper(), art_cx, y0 + 88, 17, T.mix(th["card"], T.WHITE, 0.9), max_width=art_w, anchor="c")
        self.hits.append((art_box, ("pistol",)))
        if I.has_power(slot_name):  # pistols have no power; a module/core/artefact here does
            pbadge = icons.power_badge(root.pistol_power.get(), T.WHITE, 20, 14)
            T.paste_center(img, pbadge, x1 - 28, y0 + 56)
            self.hits.append(((x1 - 52, y0 + 34, x1 - 4, y0 + 82), ("power", "pistol")))

        strip_cy = y1 - 24
        core_name = root.option_mods[0].get()
        core = I.info_for_name(core_name)
        core_has_power = I.has_power(core_name)
        core_box = (x0 + 6, y1 - 46, x0 + 6 + 46, y1 - 2)
        if hover == ("core",):
            d.ellipse(list(core_box), fill=T.mix(th["card"], T.WHITE, 0.16))
        if core is None:
            T.paste_text(img, "EMPTY", x0 + 60, strip_cy, 20, T.mix(th["card"], T.WHITE, 0.6))
        else:
            glyph = T.WHITE if core.kind == "perk" else None
            T.paste_center(img, icons.module(core, 40, glyph), (core_box[0] + core_box[2]) / 2, strip_cy)
            T.paste_text(img, core.display.upper(), x0 + 60, strip_cy, 20, T.mix(th["card"], T.WHITE, 0.9),
                         max_width=x1 - x0 - 60 - (56 if core_has_power else 12))
        self.hits.append(((core_box[0], core_box[1], x1 - (52 if core_has_power else 4), core_box[3]), ("core",)))
        if core_has_power:
            badge = icons.power_badge(root.power_mods[0].get(), T.WHITE, 18, 14)
            bx0 = x1 - 12 - badge.width
            T.paste_center(img, badge, bx0 + badge.width / 2, strip_cy)
            self.hits.append(((bx0 - 6, y1 - 46, x1 - 4, y1 - 2), ("power", 0)))

        # ---- "LOADOUT" bar -----------------------------------------------------
        T.rect(d, self.BAR, th["bar"])
        T.paste_text(img, "LOADOUT", self.BAR[0] + 14, (self.BAR[1] + self.BAR[3]) // 2, 24, T.WHITE)

        # ---- module rows ---------------------------------------------------------
        for row, option_index in enumerate(MODULE_ROWS):
            y = self.ROW_Y0 + row * self.ROW_PITCH
            box = (8, y, self.w - 8, y + self.ROW_H)
            hot = hover in (("row", option_index),)
            T.rect(d, box, th["row_hover"] if hot else th["row"])
            row_name = root.option_mods[option_index].get()
            info = I.info_for_name(row_name)
            row_has_power = I.has_power(row_name)
            cy = y + self.ROW_H // 2
            if info is None:
                T.paste_text(img, "EMPTY", 78, cy, 24, T.mix(th["row"], T.WHITE, 0.45))
            else:
                glyph = T.WHITE if info.kind == "perk" else None
                icon = icons.module(info, 38 if info.kind == "perk" else 46, glyph)
                T.paste_center(img, icon, 8 + 36, cy)
                T.paste_text(img, info.display.upper(), 78, cy, 27, T.WHITE,
                             max_width=self.w - 8 - 78 - (62 if row_has_power else 14))
            self.hits.append((box, ("row", option_index)))
            if row_has_power:  # items and game modes have no power to show
                badge = icons.power_badge(root.power_mods[option_index].get(), T.WHITE, 21, 15)
                bx0 = self.w - 14 - badge.width
                T.paste_center(img, badge, bx0 + badge.width / 2, cy)
                self.hits.append(((bx0 - 6, y + 2, self.w - 9, y + self.ROW_H - 2), ("power", option_index)))
        return img

    def tooltip(self, key):
        """Hovering a module/artefact (or its power badge) shows its wiki description."""
        root = self.view.root
        if key[0] == "pistol" or key[:2] == ("power", "pistol"):
            name = root.pistol_mod.get()
        elif key[0] == "core":
            name = root.option_mods[0].get()
        elif key[0] in ("row", "power"):
            name = root.option_mods[key[1]].get()
        else:
            return None
        text = I.description_for(name)
        info = I.BY_NAME.get(name)
        return (info.display, text) if text and info else None

    def on_click(self, key):
        v = self.view
        if key[0] == "pistol":
            v.pick_pistol()
        elif key[0] == "core":
            v.pick_module(0)  # the core slot takes anything a module row does (not pistols)
        elif key[0] == "row":
            v.pick_module(key[1])
        elif key[0] == "power":
            v.edit_power(key[1])


# ===========================================================================
# Challenges panel
# ===========================================================================
class ChallengePanel(Panel):
    ROW_Y0, ROW_PITCH, ROW_H = 8, 29, 26

    def __init__(self, view):
        super().__init__(CHAL_W, CHAL_H)
        self.view = view

    def render(self, hover):
        v, icons = self.view, self.view.icons
        img = Image.new("RGB", (self.w, self.h), T.CHALLENGE_PANEL)
        d = ImageDraw.Draw(img)
        self.hits = []
        level = v.level
        prestige = v.root.prestige_var.get()
        challenge = v.challenge_count()

        rows = [(label, ("level", n)) for label, n in LEVEL_ROWS] + [("Prestige", ("prestige",)), ("Challenge", ("challenge",))]
        for i, (label, key) in enumerate(rows):
            y = self.ROW_Y0 + i * self.ROW_PITCH
            box = (10, y, self.w - 10, y + self.ROW_H)
            T.rect(d, box, T.CHALLENGE_ROW_HOVER if hover == key else T.CHALLENGE_ROW)
            cy = y + self.ROW_H // 2
            if key[0] == "level":
                achieved = level >= key[1]
            elif key[0] == "prestige":
                achieved = bool(prestige)
            else:
                achieved = challenge >= 2
            bullet = T.hexagon(16, (102, 68, 210) if (achieved or key[0] != "level") else (60, 48, 128))
            img.paste(bullet, (20, cy - 8), bullet)
            text_color = T.WHITE if (key[0] != "level" or achieved) else (132, 128, 170)
            T.paste_text(img, label, 46, cy, 22, text_color)

            rx = self.w - 36
            if key[0] == "level":
                index = [n for _l, n in LEVEL_ROWS].index(key[1])
                T.paste_center(img, icons.chevron(index, 21 if index < 4 else 27, achieved), rx, cy)
            else:
                if key[0] == "prestige":
                    number, done = ("1" if prestige else "0"), bool(prestige)
                else:
                    number, done = f"{challenge}/2", challenge >= 2
                T.paste_center(img, icons.star(key[0] == "challenge", done, 22), rx + 4, cy)
                T.paste_text(img, number, rx - 16, cy, 23, T.RED_DONE if done else T.WHITE, anchor="r")
            self.hits.append((box, key))
        return img

    def on_click(self, key):
        v, root = self.view, self.view.root
        if key[0] == "level":
            root.subclass_lvl.set(str(key[1]))
        elif key[0] == "prestige":
            root.prestige_var.set(not root.prestige_var.get())
        elif key[0] == "challenge":
            v.cycle_challenge()


# ===========================================================================
# Tools panel: exact level, insanity challenges, auto module edit, SUBMIT
# ===========================================================================
class ToolsPanel(Panel):
    LEVEL_ENTRY = (104, 9, 72, 26)        # x, y, w, h (within the panel)
    AUTO_ENTRY = (14, 124, 150, 28)
    CHIP_W, CHIP_GAP, CHIP_X, CHIP_Y, CHIP_H = 63, 6, 15, 66, 28
    APPLY_BOX = (172, 124, CHAL_W - 14, 152)
    SUBMIT_BOX = (12, TOOLS_H - 58, CHAL_W - 12, TOOLS_H - 12)

    def __init__(self, view):
        super().__init__(CHAL_W, TOOLS_H)
        self.view = view

    def render(self, hover):
        v, root = self.view, self.view.root
        th = T.theme_for(v.family)
        img = Image.new("RGB", (self.w, self.h), T.CLASS_PANEL)
        d = ImageDraw.Draw(img)
        T.frame(d, (0, 0, self.w, self.h), T.BORDER)
        self.hits = []

        T.paste_text(img, "EXACT LEVEL", 16, 22, 20, T.DIM_TEXT)
        T.paste_text(img, "INSANITY CHALLENGES", 16, 53, 20, T.DIM_TEXT)
        for i, (code, label) in enumerate(INSANITY_CHIPS):
            x = self.CHIP_X + i * (self.CHIP_W + self.CHIP_GAP)
            box = (x, self.CHIP_Y, x + self.CHIP_W, self.CHIP_Y + self.CHIP_H)
            on = root.insanity_sub_vars[code].get()
            hot = hover == ("chip", code)
            fill = th["row_hover"] if (on and hot) else th["row"] if on else T.CLASS_ROW_HOVER if hot else T.CLASS_ROW
            T.rect(d, box, fill)
            T.paste_text(img, label.upper(), (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, 19,
                         T.WHITE if on else (160, 164, 196), anchor="c")
            self.hits.append((box, ("chip", code)))

        T.paste_text(img, "AUTO MODULE EDIT", 16, 111, 20, T.DIM_TEXT)
        box = self.APPLY_BOX
        T.rect(d, box, T.CLASS_ROW_HOVER if hover == ("apply",) else T.CLASS_ROW)
        T.frame(d, box, T.BORDER)
        T.paste_text(img, "APPLY", (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, 20, T.WHITE, anchor="c")
        self.hits.append((box, ("apply",)))
        T.paste_text(img, "Sets every module, artefact and core power", 16, 166, 15, T.DIMMER_TEXT)

        box = self.SUBMIT_BOX
        T.rect(d, box, th["row_hover"] if hover == ("submit",) else th["row"])
        T.frame(d, box, T.mix(th["row"], T.WHITE, 0.35))
        T.paste_text(img, "SUBMIT", (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, 34, T.WHITE, anchor="c")
        self.hits.append((box, ("submit",)))
        return img

    def on_click(self, key):
        root = self.view.root
        if key[0] == "chip":
            var = root.insanity_sub_vars[key[1]]
            var.set(not var.get())
            root._sync_insanity_master()
        elif key[0] == "apply":
            root.auto_module_edit(root.autopower_var.get())
        elif key[0] == "submit":
            root.submit_loadout()


# ===========================================================================
# The tab itself
# ===========================================================================
class EditorView(tk.Canvas):
    def __init__(self, parent, root):
        super().__init__(parent, highlightthickness=0, bd=0, bg="#0b0d22")
        self.root = root
        self.icons = I.IconSet()
        self.class_summary = {}        # code -> (level, prestige, scl), read from the save file
        self._pending = False
        self._size = (0, 0)
        self.scale = 1.0
        self._toast_start = None
        self._toast_job = None
        self._toast_photo = None
        self._toast_base = None

        self.backdrop_item = self.create_image(0, 0, anchor="nw")
        self._backdrop_photo = None

        self.panels = {
            "classes": ClassPanel(self), "loadout": LoadoutPanel(self),
            "challenges": ChallengePanel(self), "tools": ToolsPanel(self),
        }
        self.items = {name: PanelItem(self, panel) for name, panel in self.panels.items()}
        self.toast_item = self.create_image(0, 0, anchor="nw", state="hidden")
        # clicks that land on the toast still reach the SUBMIT button underneath it
        self.tag_bind(self.toast_item, "<Button-1>", self.items["tools"]._click)

        # Tk entries that sit on top of the tools panel
        digits_only = (self.register(lambda proposed: proposed == "" or proposed.isdigit()), "%P")
        self.level_entry = style_entry(tk.Entry(self, textvariable=root.subclass_lvl, width=6,
                                                validate="key", validatecommand=digits_only))
        self.auto_entry = style_entry(tk.Entry(self, textvariable=root.autopower_var, width=14))
        self.level_window = self.create_window(0, 0, window=self.level_entry, anchor="nw")
        self.auto_window = self.create_window(0, 0, window=self.auto_entry, anchor="nw")

        self._watch_variables()
        self.bind("<Configure>", self._on_configure)
        self.reload_summary()

    # ---- state the panels read -------------------------------------------------
    @property
    def family(self):
        return T.family_of_class(self.root.current_class)

    @property
    def class_label(self):
        return next(label for label, code, _c in CLASS_CODES if code == self.root.current_class)

    @property
    def level(self):
        return self.root._get_subclass_lvl()

    def challenge_count(self):
        """0/1/2 - mirrors what submit_loadout writes to scl<class>."""
        root = self.root
        if root.insanity_challenge_var.get():
            return 2
        return 1 if root.class_challenge_var.get() else 0

    def class_info(self, code):
        """(level, prestige 0/1, challenge 0/2) for the class list.  The selected
        class uses the live (possibly unsaved) values, the rest come from the file."""
        if code == self.root.current_class:
            return self.level, int(self.root.prestige_var.get()), self.challenge_count()
        draft = self.root.drafts.get(code)
        if draft is not None:
            challenge = 2 if all(draft["subs"].values()) else (1 if draft["challenge"] else 0)
            return int(draft["level"] or 0), int(draft["prestige"]), challenge
        return self.class_summary.get(code, (0, 0, 0))

    def reload_summary(self):
        """Re-read level / prestige / challenge for every class from the save file."""
        summary = {code: [0, 0, 0] for _label, code, _c in CLASS_CODES}
        pattern = re.compile(r'^(subclasslvl|subclasspst|scl)(\d+)="(-?\d+(?:\.\d+)?)"')
        slot = {"subclasslvl": 0, "subclasspst": 1, "scl": 2}
        try:
            with open(self.root.filename, "r") as save:
                for line in save:
                    match = pattern.match(line)
                    if match and match.group(2) in summary:
                        summary[match.group(2)][slot[match.group(1)]] = int(float(match.group(3)))
        except OSError:
            pass
        self.class_summary = {code: tuple(vals) for code, vals in summary.items()}
        self.request_refresh()

    # ---- actions ---------------------------------------------------------------
    def cycle_challenge(self):
        """Challenge row: 0 -> class challenge -> + insanity (all four) -> none."""
        root = self.root
        count = self.challenge_count()
        if count == 0:
            root.class_challenge_var.set(True)
        elif count == 1:
            root.insanity_challenge_var.set(True)
            root._on_insanity_master_toggle()
        else:
            root.insanity_challenge_var.set(False)
            root._on_insanity_master_toggle()
            root.class_challenge_var.set(False)

    # A "slot" below is 0..5 (an index into root.option_mods: the core and the five
    # rows) or "pistol" (the pistol slot, which can hold anything a row can).
    def slot_name_var(self, slot):
        return self.root.pistol_mod if slot == "pistol" else self.root.option_mods[slot]

    def slot_power_var(self, slot):
        return self.root.pistol_power if slot == "pistol" else self.root.power_mods[slot]

    def set_power(self, slot, raw):
        self.slot_power_var(slot).set(raw)

    def set_slot(self, slot, name):
        """Put the object called `name` (a pistol or module name) in a slot.
        Power belongs to the object, so the slot's power switches to that
        object's saved value."""
        self.slot_name_var(slot).set(name)
        self.slot_power_var(slot).set(self.root.module_power.get(self.root._slot_object_id(name), "1.000000"))

    def set_module(self, option_index, info):
        self.set_slot(option_index, info.name)

    def pick_pistol(self):
        editor_pickers.open_pistol_picker(self)

    def pick_module(self, option_index):
        editor_pickers.open_module_picker(self, option_index)

    def edit_power(self, slot):
        editor_pickers.open_power_popup(self, slot)

    # ---- redraw plumbing ---------------------------------------------------------
    def _watch_variables(self):
        root = self.root
        variables = [root.pistol_mod, root.pistol_power, root.subclass_lvl, root.prestige_var, root.class_challenge_var,
                     root.insanity_challenge_var, *root.option_mods, *root.power_mods, *root.insanity_sub_vars.values()]
        for var in variables:
            var.trace_add("write", lambda *_: self.request_refresh())

    def request_refresh(self):
        """Coalesce bursts of variable changes (change_class sets ~15) into one redraw."""
        if not self._pending:
            self._pending = True
            self.after_idle(self.refresh)

    def refresh(self):
        self._pending = False
        for item in self.items.values():
            item.redraw()

    def _on_configure(self, event):
        size = (event.width, event.height)
        if size != self._size and event.width > 1:
            self._size = size
            self._backdrop_photo = None
            from PIL import ImageTk
            self._backdrop_photo = ImageTk.PhotoImage(T.backdrop(*size))
            self.itemconfigure(self.backdrop_item, image=self._backdrop_photo)
        self._layout()

    def _layout(self):
        w, h = self._size
        s = max(MIN_SCALE, min(1.0, w / DESIGN_W, h / DESIGN_H))
        if abs(s - self.scale) > 1e-6:
            self.scale = s
            self._toast_base = None
            entry_font = ("TkDefaultFont", max(6, round(11 * s)), "bold")
            self.level_entry.configure(font=entry_font)
            self.auto_entry.configure(font=entry_font)
        for item in self.items.values():
            item.set_scale(s)
        # centre the (scaled) composition in the tab
        ox = max(0, (w - DESIGN_W * s) / 2) + MARGIN * s
        oy = max(0, (h - DESIGN_H * s) / 2) + MARGIN * s
        x_load = ox + (CLASS_W + GAP) * s
        x_right = x_load + (LOAD_W + GAP) * s
        y_tools = oy + (CHAL_H + GAP) * s
        self.items["classes"].move_to(ox, oy)
        self.items["loadout"].move_to(x_load, oy)
        self.items["challenges"].move_to(x_right, oy)
        self.items["tools"].move_to(x_right, y_tools)
        for window, (lx, ly, lw, lh) in ((self.level_window, ToolsPanel.LEVEL_ENTRY), (self.auto_window, ToolsPanel.AUTO_ENTRY)):
            self.coords(window, x_right + lx * s, y_tools + ly * s)
            self.itemconfigure(window, width=round(lw * s), height=round(lh * s))
        sx0, sy0, _sx1, _sy1 = ToolsPanel.SUBMIT_BOX
        self.coords(self.toast_item, x_right + sx0 * s, y_tools + sy0 * s)
        for name in ("classes", "loadout", "challenges", "tools"):
            self.tag_raise(self.items[name].item)
        self.tag_raise(self.level_window)
        self.tag_raise(self.auto_window)
        self.tag_raise(self.toast_item)

    # ---- "Changes Submitted" toast ---------------------------------------------------
    def show_submitted(self):
        """Fade a 'Changes Submitted' message in over the SUBMIT button, hold it, fade it out."""
        if self._toast_job is not None:
            self.after_cancel(self._toast_job)
        self._toast_start = time.monotonic()
        self.itemconfigure(self.toast_item, state="normal")
        self.tag_raise(self.toast_item)
        self._toast_tick()

    def _toast_opacity(self, t):
        if t < TOAST_IN:
            return t / TOAST_IN
        if t < TOAST_IN + TOAST_HOLD:
            return 1.0
        return max(0.0, 1.0 - (t - TOAST_IN - TOAST_HOLD) / TOAST_OUT)

    def _toast_tick(self):
        t = time.monotonic() - self._toast_start
        if t >= TOAST_IN + TOAST_HOLD + TOAST_OUT:
            self.itemconfigure(self.toast_item, state="hidden")
            self._toast_job = None
            return
        if self._toast_base is None:
            self._toast_base = self._build_toast_base()
        base, mask = self._toast_base
        frame = base.copy()
        opacity = self._toast_opacity(t)
        frame.putalpha(mask.point(lambda v: int(v * opacity)))
        self._toast_photo = ImageTk.PhotoImage(frame)  # keep a reference!
        self.itemconfigure(self.toast_item, image=self._toast_photo)
        self._toast_job = self.after(30, self._toast_tick)

    def _build_toast_base(self):
        """-> (RGB image, alpha mask) of the toast, already scaled to the current layout."""
        x0, y0, x1, y1 = ToolsPanel.SUBMIT_BOX
        w, h = x1 - x0, y1 - y0
        img = Image.new("RGB", (w, h), (46, 150, 84))
        d = ImageDraw.Draw(img)
        T.frame(d, (0, 0, w, h), (120, 214, 150), 2)
        text_w = T.text_width("CHANGES SUBMITTED", 28)
        tx = (w - text_w) / 2 + 12
        T.paste_text(img, "CHANGES SUBMITTED", tx, h / 2, 28, T.WHITE)
        cx, cy = tx - 22, h / 2  # check mark
        d.line([(cx - 8, cy), (cx - 2, cy + 7), (cx + 9, cy - 8)], fill=T.WHITE, width=4)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=4, fill=255)
        size = (max(1, round(w * self.scale)), max(1, round(h * self.scale)))
        if size != (w, h):
            img, mask = img.resize(size, Image.LANCZOS), mask.resize(size, Image.LANCZOS)
        return img, mask
