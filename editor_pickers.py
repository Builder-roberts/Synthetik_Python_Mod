"""editor_pickers.py - the popup windows opened from the Editor tab.

    open_module_picker  class-coloured, tabbed, searchable list (like the game's perk lists);
                        used for the core slot and the five module rows alike
    open_pistol_picker  list of pistols with their art
    open_power_popup    edit a module's power bonus (the heart "+25%" badge)

Each returns immediately; picking something calls back into the EditorView
(which writes the root window's variables) and closes the popup.
"""
import tkinter as tk

from PIL import Image, ImageDraw

import ui_icons as I
import ui_theme as T
from synthetik_data import SHOWN_PISTOLS
from ui_widgets import Panel, PanelItem, style_entry


# ===========================================================================
# Shared popup window plumbing
# ===========================================================================
class _Popup(tk.Toplevel):
    def __init__(self, view, title):
        super().__init__(view.root)
        self.view = view
        self.title(title)
        self.configure(bg="#0d1130")
        self.resizable(False, False)
        self.transient(view.root)
        self.bind("<Escape>", lambda _e: self.destroy())

    def present(self, width, height):
        """Centre on the screen, then make the popup modal."""
        self.update_idletasks()
        width, height = max(width, self.winfo_reqwidth()), max(height, self.winfo_reqheight())
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"+{x}+{y}")
        self.update_idletasks()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass  # not viewable (e.g. headless test); fine - it just won't be modal
        self.focus_set()


def _wheel_binding(widget, callback):
    """Mouse-wheel on Windows/macOS (<MouseWheel>) and Linux (Button-4/5)."""
    widget.bind("<MouseWheel>", lambda e: callback(-1 if e.delta > 0 else 1))
    widget.bind("<Button-4>", lambda _e: callback(-1))
    widget.bind("<Button-5>", lambda _e: callback(1))


# ===========================================================================
# Tabbed list picker (modules, pistols)
# ===========================================================================
class _ListPanel(Panel):
    W, ROW_H, VIEW_ROWS = 372, 46, 10

    def __init__(self, picker, header_h):
        self.picker = picker
        self.header_h = header_h
        super().__init__(self.W, header_h + self.ROW_H * self.VIEW_ROWS)

    def render(self, hover):
        p, icons = self.picker, self.picker.view.icons
        img = Image.new("RGB", (self.w, self.h), T.PICKER_BG)
        d = ImageDraw.Draw(img)
        self.hits = []
        accent = p.accent

        # ---- header: title or tab chips --------------------------------------------
        if p.tabs:
            per_row, gap = 4, 6
            chip_w = (self.w - 24 - gap * (per_row - 1)) // per_row
            for i, (tab_id, label) in enumerate(p.tabs):
                col, row = i % per_row, i // per_row
                x, y = 12 + col * (chip_w + gap), 10 + row * 32
                box = (x, y, x + chip_w, y + 26)
                active = tab_id == p.tab and not p.query()
                glyph = T.FAMILIES[tab_id]["glyph"] if tab_id in T.FAMILIES else T.CREAM
                fill = T.mix(T.PICKER_BG, glyph, 0.55) if active else (T.PICKER_ROW_HOVER if hover == ("tab", tab_id) else T.PICKER_ROW)
                T.rect(d, box, fill)
                T.paste_text(img, label.upper(), (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, 18,
                             T.WHITE if active else (170, 174, 204), anchor="c")
                self.hits.append((box, ("tab", tab_id)))
        else:
            T.paste_text(img, p.heading.upper(), 14, 22, 26, T.WHITE)

        # ---- scrolling list (rendered separately so rows clip cleanly) ---------------
        view_h = self.ROW_H * self.VIEW_ROWS
        lst = Image.new("RGB", (self.w, view_h), T.PICKER_BG)
        entries = p.visible_entries()
        first = p.scroll // self.ROW_H
        for idx in range(first, min(len(entries), first + self.VIEW_ROWS + 2)):
            e = entries[idx]
            y = idx * self.ROW_H - p.scroll
            box = (6, y + 2, self.w - 10, y + self.ROW_H - 2)
            selected = e["key"] == p.current_key
            hot = hover == ("pick", e["key"])
            ld = ImageDraw.Draw(lst)
            fill = T.mix(T.PICKER_ROW, accent, 0.30) if selected else (T.PICKER_ROW_HOVER if hot else T.PICKER_ROW)
            ld.rectangle([box[0], box[1], box[2] - 1, box[3] - 1], fill=fill)
            if selected:
                ld.rectangle([box[0], box[1], box[0] + 3, box[3] - 1], fill=accent)
            cy = y + self.ROW_H // 2
            if e.get("icon") is not None:
                T.paste_center(lst, e["icon"], 8 + p.icon_w / 2 + 6, cy)
            tx = 8 + p.icon_w + 16
            right_pad = 62 if e.get("power") is not None and abs(float(e["power"]) - 1.0) > 1e-9 else 14
            if e.get("sub"):
                T.paste_text(lst, e["label"].upper(), tx, cy - 7, 24, T.CREAM, max_width=self.w - tx - right_pad)
                T.paste_text(lst, e["sub"], tx, cy + 12, 14, T.DIM_TEXT)
            else:
                T.paste_text(lst, e["label"].upper(), tx, cy, 25, T.CREAM, max_width=self.w - tx - right_pad)
            if right_pad == 62:
                badge = icons.power_badge(e["power"], T.WHITE, 17, 13)
                T.paste_center(lst, badge, self.w - 36, cy)
            self.hits.append(((box[0], max(box[1], 0) + self.header_h, box[2], min(box[3], view_h) + self.header_h), ("pick", e["key"])))
        if not entries:
            T.paste_text(lst, "NO MATCHES", self.w / 2, 40, 24, T.DIMMER_TEXT, anchor="c")
        # scroll indicator
        total = len(entries) * self.ROW_H
        if total > view_h:
            bar_h = max(24, int(view_h * view_h / total))
            bar_y = int((view_h - bar_h) * p.scroll / max(1, total - view_h))
            ImageDraw.Draw(lst).rectangle([self.w - 6, bar_y, self.w - 3, bar_y + bar_h], fill=(86, 92, 150))
        img.paste(lst, (0, self.header_h))

        # clip hit regions that ended up outside the viewport
        self.hits = [(b, k) for b, k in self.hits if b[3] > b[1]]
        return img

    def tooltip(self, key):
        if key[0] != "pick":
            return None
        entry = next((e for e in self.picker.entries if e["key"] == key[1]), None)
        return (entry["label"], entry["desc"]) if entry and entry.get("desc") else None

    def on_click(self, key):
        p = self.picker
        if key[0] == "tab":
            p.tab = key[1]
            if p.search_var is not None:
                p.search_var.set("")
            p.scroll = 0
            p.item.hover = None
            p.item.redraw()
        elif key[0] == "pick":
            p.choose(key[1])


class ListPicker(_Popup):
    def __init__(self, view, title, heading, entries, current_key, on_pick, tabs=None, start_tab=None,
                 icon_w=40, accent=T.CREAM):
        super().__init__(view, title)
        self.heading, self.entries, self.current_key, self.on_pick = heading, entries, current_key, on_pick
        self.tabs, self.icon_w, self.accent = tabs, icon_w, accent
        self.tab = start_tab or (tabs[0][0] if tabs else None)
        self.scroll = 0
        self.search_var = tk.StringVar(self) if tabs else None

        header_h = 112 if tabs else 44
        self.panel = _ListPanel(self, header_h)
        self.canvas = tk.Canvas(self, width=self.panel.w, height=self.panel.h, highlightthickness=0, bd=0, bg="#0d1130")
        self.canvas.pack()
        self.item = PanelItem(self.canvas, self.panel)
        _wheel_binding(self.canvas, self._on_wheel)
        _wheel_binding(self, self._on_wheel)

        if tabs:
            self.search_entry = style_entry(tk.Entry(self.canvas, textvariable=self.search_var))
            self.canvas.create_window(12, 76, window=self.search_entry, anchor="nw", width=self.panel.w - 24, height=26)
            self.search_var.trace_add("write", lambda *_: self._on_query())
            self.search_entry.focus_set()
        self.scroll_to_current()
        self.present(self.panel.w, self.panel.h)

    # ---- data ---------------------------------------------------------------
    def query(self):
        return self.search_var.get().strip().lower() if self.search_var is not None else ""

    def visible_entries(self):
        q = self.query()
        if q:
            return [e for e in self.entries
                    if q in e["label"].lower() or q in e.get("sub", "").lower() or q in e.get("desc", "").lower()]
        if self.tabs:
            return [e for e in self.entries if e["tab"] == self.tab]
        return self.entries

    def scroll_to_current(self):
        keys = [e["key"] for e in self.visible_entries()]
        if self.current_key in keys:
            idx = keys.index(self.current_key)
            self.scroll = self._clamp(idx * _ListPanel.ROW_H - _ListPanel.ROW_H * 3)
        self.item.redraw()

    def _clamp(self, value):
        total = len(self.visible_entries()) * _ListPanel.ROW_H
        return max(0, min(value, max(0, total - _ListPanel.ROW_H * _ListPanel.VIEW_ROWS)))

    def _on_wheel(self, direction):
        self.scroll = self._clamp(self.scroll + direction * _ListPanel.ROW_H * 2)
        self.item.hover = None
        self.item.redraw()

    def _on_query(self):
        self.scroll = 0
        self.item.hover = None
        self.item.redraw()

    def choose(self, key):
        entry = next(e for e in self.entries if e["key"] == key)
        self.on_pick(entry)
        self.destroy()


def _module_entries(view):
    """One picker entry per module, perks in in-game order (the data stores them bottom-up)."""
    root = view.root
    entries = []
    for info in I.CATALOG:
        entries.append({
            "key": info.name, "info": info, "name": info.name, "label": info.display, "sub": info.sub,
            "tab": info.tab, "desc": I.DESCRIPTIONS.get(info.obj_id, ""),
            "power": root.module_power.get(info.obj_id) if info.kind in I.POWER_KINDS else None,
            "icon": view.icons.module(info, 34),
        })

    def order(e):
        info = e["info"]
        if info.kind == "perk":
            return (0, -info.index)
        return (1 if info.kind != "mode" else 2, info.index)
    entries.sort(key=order)
    return entries


def open_module_picker(view, option_index):
    """Pick a module for the core slot (0) or a loadout row (1..5) - the same list for all of them."""
    root = view.root
    current = I.BY_NAME.get(root.option_mods[option_index].get())
    ListPicker(
        view, "Choose module", "", _module_entries(view), current.name if current else None,
        on_pick=lambda e: view.set_slot(option_index, e["name"]),
        tabs=I.MODULE_TABS, start_tab=current.tab if current else T.family_of_class(root.current_class),
        icon_w=36, accent=T.theme_for(view.family)["accent"],
    )


def open_pistol_picker(view):
    """The pistol slot: pistols, plus everything the module rows can hold."""
    root = view.root
    pistols = [{
        "key": "pistol:" + name, "name": name, "label": name, "tab": "pistols",
        "power": None,  # pistols have no power
        "icon": view.icons.pistol(name, 44, 30),
    } for name in SHOWN_PISTOLS]
    current_name = root.pistol_mod.get()
    is_pistol = current_name in SHOWN_PISTOLS
    current = I.BY_NAME.get(current_name)
    ListPicker(
        view, "Choose pistol-slot item", "", pistols + _module_entries(view),
        ("pistol:" + current_name) if is_pistol else (current.name if current else None),
        on_pick=lambda e: view.set_slot("pistol", e["name"]),
        tabs=[("pistols", "Pistols")] + I.MODULE_TABS,
        start_tab="pistols" if is_pistol or current is None else current.tab,
        icon_w=44, accent=T.theme_for(view.family)["accent"],
    )


# ===========================================================================
# Power editor
# ===========================================================================
def _fmt_pct(raw):
    try:
        pct = (float(raw) - 1.0) * 100.0
    except (TypeError, ValueError):
        return "0"
    text = f"{pct:.4f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


class PowerPopup(_Popup):
    def __init__(self, view, slot):
        super().__init__(view, "Module power")
        self.slot = slot
        name = view.slot_name_var(slot).get()
        self.info = I.info_for_name(name)
        self.pct = tk.StringVar(self, value=_fmt_pct(view.slot_power_var(slot).get()))
        label_fg, bg = "#d8d4ee", "#0d1130"

        heading = (name if name in SHOWN_PISTOLS else self.info.display).upper() if self.info else "MODULE"
        tk.Label(self, text=heading, bg=bg, fg="#ffffff", font=("TkDefaultFont", 12, "bold")).pack(padx=18, pady=(14, 2))
        tk.Label(self, text="Power bonus (%)", bg=bg, fg=label_fg).pack()
        self.entry = style_entry(tk.Entry(self, textvariable=self.pct, width=12, justify="center"))
        self.entry.pack(padx=18, pady=(4, 2), ipady=3)
        self.raw_label = tk.Label(self, bg=bg, fg="#8f93bd")
        self.raw_label.pack()
        buttons = tk.Frame(self, bg=bg)
        buttons.pack(pady=(12, 14))
        tk.Button(buttons, text="Apply", width=9, command=self.apply, bg="#6644d2", fg="#ffffff",
                  relief="flat", activebackground="#7d5cf0").pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="Cancel", width=9, command=self.destroy, bg="#262e62", fg="#ffffff",
                  relief="flat", activebackground="#3a4590").pack(side=tk.LEFT, padx=4)

        self.pct.trace_add("write", lambda *_: self._show_raw())
        self.entry.bind("<Return>", lambda _e: self.apply())
        self._show_raw()
        self.entry.focus_set()
        self.entry.select_range(0, tk.END)
        self.present(260, 0)

    def _parse(self):
        try:
            return 1.0 + float(self.pct.get().replace("%", "").replace("+", "").strip() or "0") / 100.0
        except ValueError:
            return None

    def _show_raw(self):
        raw = self._parse()
        self.raw_label.configure(text="" if raw is None else f"stored value: {raw:.6f}")

    def apply(self):
        raw = self._parse()
        if raw is None:
            self.entry.configure(highlightbackground="#e23a3e", highlightcolor="#e23a3e")
            return
        self.view.set_power(self.slot, f"{raw:.6f}")
        self.destroy()


def open_power_popup(view, slot):
    PowerPopup(view, slot)
