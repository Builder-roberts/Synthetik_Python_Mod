"""LoadoutEditor.py

Synthetik Loadout Editor v3.0 - class-based rewrite of LoadoutGUI.py.

This now has the same functionality as LoadoutGUI.py, restructured into a
tabbed window (a ttk.Notebook across the whole main window):
  - "Synthetik Editor" tab: an in-game-style loadout screen (drawn by
    editor_view.py / editor_pickers.py): class list, pistol card + core +
    5 module rows with power badges, challenges, exact level, auto module
    edit, submit.  It is only a view: it reads/writes the Root variables below
    and the save logic here (change_class / submit_loadout) is unchanged,
    except that the pistol slot now accepts anything a module row can
    (cores, items, modules), not just pistols.
  - "Weapons" / "Items" tabs: spawn-list checklists (Select All/Deselect
    All + one checkbox per weapon/item, pre-checked from the save file's
    current wdropchange/idropchange values), with category filters (SMGs,
    Shotguns, Active items, ...) that show only the chosen categories.
    Select All/Deselect All only affect the tiles currently shown.
  - "Cheats" tab: everything that used to live in the Power/Misc menus
    (OP auto, quick 1.6x, daily-run reset, max data, undo research, cheat
    code reset, ask-for-confirmation toggle, unlock all), as plain buttons.
The File/Spawn/Help menus remain for the handful of things that don't fit
a tab (open/browse the save file, the legacy "Old Weapon/Item Spawn" and
reset actions, about/help).

Everything that was a free function + a handful of globals in LoadoutGUI.py
is now a method + `self.` attributes on Root. The logic inside each method
is the same logic (including the same FRAGILE/CHANGED notes called out in
LoadoutGUI.py) - only the "how it's wired up" changed. A name-mapping table
is at the bottom of this file if you want to compare the two side by side.
"""

import getpass
import os
import re
import sys
import tkinter as tk
from tkinter import Menu, filedialog, messagebox, ttk

from PIL import Image, ImageTk

import ui_icons as I
import ui_style as S

from editor_view import DESIGN_H, DESIGN_W, MIN_SCALE, EditorView
from synthetik_data import (
    ITEM_CATEGORIES,
    ITEM_IMAGES,
    LOADOUT_SLOTS,
    OP_MODULE_POWER_BY_ID,
    PISTOL_WEAPON_IDS,
    PISTOL_WEAPON_NAMES,
    PLACEHOLDER_IMAGE,
    SHOWN_ITEMS,
    SHOWN_MODULES,
    SHOWN_PISTOLS,
    SHOWN_WEAPONS,
    VAR_MODULES,
    VAR_PISTOLS,
    WEAPON_CATEGORIES,
    WEAPON_IMAGES,
)

# Folder this script lives in, so asset paths work regardless of cwd.
# When frozen into a PyInstaller --onefile exe, the app runs from a temp
# extraction folder referenced by sys._MEIPASS, not the exe's own location -
# so we have to special-case that, or bundled assets won't be found.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    SCRIPT_DIR = sys._MEIPASS
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")

# Thumbnail size (px) for spawn-list tiles, and border styling for the
# selected/unselected states.
THUMB_SIZE = (64, 64)
BORDER_SELECTED = S.GREEN      # green border = selected
BORDER_UNSELECTED = S.EDGE     # dim border = unselected
BORDER_WIDTH = 3
TILE_PADDING = 3
# Total footprint of one tile (thumbnail + caption + border + grid padding),
# used to figure out how many columns fit in the current canvas width.
TILE_TOTAL_WIDTH = THUMB_SIZE[0] + 14 + 2 * BORDER_WIDTH + 2 * TILE_PADDING

# Slots for OptionMod1..6, in that order - see change_class()/submit_loadout().
MODULE_SLOT_CODES = list(reversed(LOADOUT_SLOTS[1:7]))


class Root(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Synthetik Loadout Editor v3.0")
        # Sized for the Editor tab's three-panel layout; the Weapons/Items tabs reflow to fit.
        self.ui_scale = 1.0          # 1.0 at full size; the whole UI shrinks with the window (see _apply_scale)
        self._scale_hooks = []       # callables(scale) that resize the plain-Tk widgets
        self._wheel_targets = {}     # tab frame -> the canvas the mouse wheel scrolls on that tab
        self._fit_to_screen()
        # The Editor tab scales its drawing down to MIN_SCALE, so the window may shrink that far.
        self.minsize(min(int(DESIGN_W * MIN_SCALE) + 14, self._min_w_cap), min(int(DESIGN_H * MIN_SCALE) + 62, self._min_h_cap))

        # ---- state ------------------------------------------------------
        # safety == 0 -> save immediately. safety == 1 -> ask first.
        self.safety = 0
        self.current_class = "10"
        self.loadout_slots = {}                # {slot number: object ID} for the current class
        # Unsaved edits of classes you've switched away from: {class code: state dict}.
        # The current class's edits live in the tk variables below, not here.
        self.drafts = {}
        self._state_loaded = False
        self.module_power = {}                 # {object ID: tpoints_ value}, read by ID (file order varies by version)
        self.weapon_spawn_ids = []
        self.item_spawn_ids = []

        username = getpass.getuser()
        self.filename = f"C:/Users/{username}/AppData/Local/Synthetik/Save.sav"
        self.tfilename = f"C:/Users/{username}/AppData/Local/Synthetik/TEMPORARYSAVE.txt"

        if not os.path.exists(self.filename):
            messagebox.showinfo(
                "Synthetik",
                "Sorry, your save file is not where I thought it would be! "
                "Could you please find it for me?",
            )
            self.filename, self.tfilename = self.browse_files(self.filename, self.tfilename)

        # ---- tk variables -------------------------------------------------
        # The pistol slot (slot 9) takes pistols, but ALSO anything the other six
        # slots can hold (cores, items, modules...), so pistol_mod holds either a
        # SHOWN_PISTOLS name or a SHOWN_MODULES name - see _slot_name/_slot_object_id.
        self.pistol_mod = tk.StringVar(self)
        self.pistol_power = tk.StringVar(self, value="1.000000")
        self.option_mods = [tk.StringVar(self) for _ in range(6)]
        self.power_mods = [tk.StringVar(self) for _ in range(6)]
        self.autopower_var = tk.StringVar(self)
        # StringVar (not IntVar) so the entry box can be empty/mid-typing without
        # raising; use _get_subclass_lvl() to read it as an int.
        self.subclass_lvl = tk.StringVar(self, value="0")
        self.prestige_var = tk.BooleanVar(self, value=False)
        self.class_challenge_var = tk.BooleanVar(self, value=False)
        self.insanity_challenge_var = tk.BooleanVar(self, value=False)
        # Individual insanity sub-challenges: 400%(ski), Hyper(sad), Tactical(sta), Madness(sma)
        self.insanity_sub_vars = {code: tk.BooleanVar(self, value=False) for code in ("ski", "sad", "sta", "sma")}

        # ---- widgets -------------------------------------------------
        self._build_styles()
        self._build_notebook()
        self._build_editor_tab()
        self._build_weapons_tab()
        self._build_items_tab()
        self._build_cheats_tab()
        self._build_menu()

        # ---- initial load -------------------------------------------------
        self.setsave()
        self._load_class(self.current_class)
        self._center_on_screen()
        self._apply_scale(self._scale_for(self.winfo_width(), self.winfo_height()))
        self.bind("<Configure>", self._on_root_configure)
        self.bind_all("<MouseWheel>", self._on_global_wheel)

    # ======================================================================
    # Window size / position / scaling
    # ======================================================================
    @staticmethod
    def _work_area(root):
        """(x, y, w, h) of the screen area not covered by the taskbar."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                rect = wintypes.RECT()
                if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
            except Exception:
                pass
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 48  # leave room for a taskbar

    def _fit_to_screen(self):
        """Open at the design size, or smaller if the screen's usable area can't hold it
        (the title bar and window border take ~50px beyond the size we ask for)."""
        _x, _y, area_w, area_h = self._work_area(self)
        width = min(DESIGN_W + 14, max(300, area_w - 16))
        height = min(DESIGN_H + 62, max(220, area_h - 50))
        self._min_w_cap, self._min_h_cap = width, height  # never ask for a minimum bigger than the window
        self.geometry(f"{width}x{height}")

    def _center_on_screen(self):
        """Centre the whole window (title bar included) in the usable screen area."""
        self.update_idletasks()
        ax, ay, aw, ah = self._work_area(self)
        border = self.winfo_rootx() - self.winfo_x()
        title = self.winfo_rooty() - self.winfo_y()
        outer_w = self.winfo_width() + 2 * border
        outer_h = self.winfo_height() + title + border
        x = ax + max(0, (aw - outer_w) // 2)
        y = ay + max(0, (ah - outer_h) // 2)
        self.geometry(f"+{x}+{y}")

    @staticmethod
    def _scale_for(width, height):
        """Same rule the Editor tab uses: shrink with the window, never below MIN_SCALE."""
        s = min(1.0, width / (DESIGN_W + 14), height / (DESIGN_H + 62))
        return round(max(MIN_SCALE, s) * 20) / 20  # steps of 0.05 so a drag doesn't rebuild everything

    def _on_root_configure(self, event):
        if event.widget is self:
            scale = self._scale_for(event.width, event.height)
            if scale != self.ui_scale:
                self._apply_scale(scale)

    def _on_global_wheel(self, event):
        """Mouse wheel scrolls whichever tab is showing, wherever the pointer is over the main window."""
        try:
            if event.widget.winfo_toplevel() is not self:
                return  # a popup has its own wheel handling
            canvas = self._wheel_targets.get(self.nametowidget(self.notebook.select()))
            if canvas is not None and canvas.yview() != (0.0, 1.0):
                canvas.yview_scroll(-1 * (event.delta // 120), "units")
        except (tk.TclError, AttributeError, KeyError):
            pass

    def _apply_scale(self, scale):
        self.ui_scale = scale
        for hook in self._scale_hooks:
            hook(scale)

    def _track(self, widget, size, padx=None, pady=None, grid_ipadx=None):
        """Make a plain-Tk widget's font (and optionally padding) follow the UI scale."""
        def hook(scale):
            opts = {"font": S.font(max(6, round(size * scale)))}
            if padx is not None:
                opts["padx"] = max(1, round(padx * scale))
            if pady is not None:
                opts["pady"] = max(0, round(pady * scale))
            widget.configure(**opts)
            if grid_ipadx is not None:
                widget.grid_configure(ipadx=round(grid_ipadx * scale))
        self._scale_hooks.append(hook)
        hook(self.ui_scale)
        return widget

    # ======================================================================
    # File location
    # ======================================================================
    def browse_files(self, save_filename, temp_save_filename):
        """Ask the user to locate their save file if it's not where we expect."""
        filepath = save_filename.rsplit("/", 1)[0]
        new_save_filename = filedialog.askopenfilename(
            initialdir="/",
            title="Select a file",
            filetypes=(("Save files", "*.sav*"), ("All files", "*.*")),
        )
        if new_save_filename:
            save_filename = new_save_filename
            filepath = save_filename.rsplit("/", 1)[0]
            temp_save_filename = filepath + "/TEMPORARYSAVE.txt"
        return save_filename, temp_save_filename

    def open_save(self):
        os.startfile(self.filename)

    # ======================================================================
    # Save-file reading
    # ======================================================================
    def setsave(self):
        """Re-read every module's tpoints_ (power) value from the save file.

        Stored by object ID, not position: the order of the tpoints_ lines
        differs between game versions.
        """
        self.module_power.clear()
        pattern = re.compile(r'^tpoints_(obj_(?:perk|artefact|item)\w*)="(-?\d+(?:\.\d+)?)"')
        with open(self.filename, "r") as save:
            for line in save:
                match = pattern.match(line)
                if match:
                    self.module_power[match.group(1)] = match.group(2)

    @staticmethod
    def _slot_name(obj_id):
        """Display name of whatever object a loadout slot holds.  Pistols are
        only valid in the pistol slot, but every slot can hold any module.  An
        object this tool doesn't know about is kept as its raw id so it
        round-trips through submit_loadout unchanged instead of crashing."""
        if obj_id in VAR_PISTOLS:
            return SHOWN_PISTOLS[VAR_PISTOLS.index(obj_id)]
        if obj_id in VAR_MODULES:
            return SHOWN_MODULES[VAR_MODULES.index(obj_id)]
        return obj_id

    @staticmethod
    def _slot_object_id(name):
        """Inverse of _slot_name."""
        if name in SHOWN_PISTOLS:
            return VAR_PISTOLS[SHOWN_PISTOLS.index(name)]
        if name in SHOWN_MODULES:
            return VAR_MODULES[SHOWN_MODULES.index(name)]
        return name

    @staticmethod
    def _norm_power(value):
        try:
            return f"{float(value):.6f}"
        except (TypeError, ValueError):
            return value

    def _read_class_state(self, cls):
        """The class's loadout, level and challenges as the save file has them.

        Slots are looked up by number rather than by line order - newer saves
        list perkslot0..9 ascending, older ones listed them descending.  A key
        missing from the file counts as 0 / not done.
        """
        slot_pattern = re.compile(rf'^perkslot(\d+)class{cls}="([^"]*)"')
        value_pattern = re.compile(r'^(\w+)="(-?\d+(?:\.\d+)?)"')
        wanted = {f"subclasslvl{cls}", f"subclasspst{cls}", f"scl{cls}"} | {f"{c}{cls}" for c in self.insanity_sub_vars}
        slots, values = {}, {}
        with open(self.filename, "r") as save:
            for line in save:
                match = slot_pattern.match(line)
                if match:
                    slots[match.group(1)] = match.group(2)
                    continue
                match = value_pattern.match(line)
                if match and match.group(1) in wanted:
                    values[match.group(1)] = float(match.group(2))

        def power_of(obj_id):
            return self._norm_power(self.module_power.get(obj_id, "1.000000"))

        pistol_id = slots[LOADOUT_SLOTS[0]]
        module_ids = [slots[code] for code in MODULE_SLOT_CODES]
        subs = {code: values.get(f"{code}{cls}", 0.0) >= 2 for code in self.insanity_sub_vars}
        return {
            "pistol": (self._slot_name(pistol_id), power_of(pistol_id)),
            "slots": [(self._slot_name(i), power_of(i)) for i in module_ids],
            "level": str(int(values.get(f"subclasslvl{cls}", 0.0))),
            "prestige": values.get(f"subclasspst{cls}", 0.0) >= 1,
            "challenge": values.get(f"scl{cls}", 0.0) > 0 or all(subs.values()),
            "subs": subs,
        }

    def _snapshot(self):
        """The current class's state as shown in the UI (same shape as _read_class_state)."""
        subs = {code: var.get() for code, var in self.insanity_sub_vars.items()}
        return {
            "pistol": (self.pistol_mod.get(), self._norm_power(self.pistol_power.get())),
            "slots": [(m.get(), self._norm_power(p.get())) for m, p in zip(self.option_mods, self.power_mods)],
            "level": str(self._get_subclass_lvl()),
            "prestige": bool(self.prestige_var.get()),
            "challenge": bool(self.class_challenge_var.get()) or all(subs.values()),
            "subs": subs,
        }

    def _apply_state(self, state):
        self.pistol_mod.set(state["pistol"][0])
        self.pistol_power.set(state["pistol"][1])
        for (name, power), name_var, power_var in zip(state["slots"], self.option_mods, self.power_mods):
            name_var.set(name)
            power_var.set(power)
        self.subclass_lvl.set(state["level"])
        self.prestige_var.set(state["prestige"])
        self.class_challenge_var.set(state["challenge"])
        for code, var in self.insanity_sub_vars.items():
            var.set(state["subs"][code])
        self._sync_insanity_master()

    def change_class(self, subclass):
        """Switch classes.  Unsaved edits to the class you leave are kept (as a
        draft) and come back when you return to it; the refresh button discards them."""
        if subclass != self.current_class:
            self._stash_current_class()
        self._load_class(subclass)

    def _stash_current_class(self):
        if not self._state_loaded:
            return
        snapshot = self._snapshot()
        if snapshot != self._read_class_state(self.current_class):
            self.drafts[self.current_class] = snapshot
        else:
            self.drafts.pop(self.current_class, None)

    def _load_class(self, subclass):
        """Show `subclass`: its draft if it has unsaved edits, else what the save file says."""
        self.current_class = subclass
        self.loadout_slots.clear()
        state = self.drafts.pop(subclass, None) or self._read_class_state(subclass)
        self._apply_state(state)
        self._state_loaded = True
        # keep the class list's levels/stars (read for ALL classes) in step with the file
        self.editor.reload_summary()

    def reload_from_save(self):
        """The refresh button on the class list: throw away every unsaved edit and
        re-read the save file (module powers and the current class)."""
        self.drafts.clear()
        self.setsave()
        self._load_class(self.current_class)

    def _merge_file_changes_into_drafts(self, old_power, old_summary):
        """After the file was rewritten, bring other classes' drafts up to date with
        whatever really changed (a module's power, a class's level/challenges) while
        leaving the rest of their unsaved edits alone."""
        changed_power = {k for k, v in self.module_power.items() if old_power.get(k) != v}
        for cls, draft in self.drafts.items():
            if changed_power:
                new_power = lambda name, power: (
                    self._norm_power(self.module_power[self._slot_object_id(name)])
                    if self._slot_object_id(name) in changed_power else power)
                draft["pistol"] = (draft["pistol"][0], new_power(*draft["pistol"]))
                draft["slots"] = [(n, new_power(n, p)) for n, p in draft["slots"]]
            if self.editor.class_summary.get(cls) != old_summary.get(cls):
                fresh = self._read_class_state(cls)
                for key in ("level", "prestige", "challenge", "subs"):
                    draft[key] = fresh[key]

    def _load_subclass_lvl(self):
        """Re-read the current class's level/challenge widgets from the save file
        (used after the file was rewritten)."""
        state = self._read_class_state(self.current_class)
        self.subclass_lvl.set(state["level"])
        self.prestige_var.set(state["prestige"])
        self.class_challenge_var.set(state["challenge"])
        for code, var in self.insanity_sub_vars.items():
            var.set(state["subs"][code])
        self._sync_insanity_master()
        self.editor.reload_summary()

    def _get_subclass_lvl(self):
        """Current contents of the level entry as an int (blank -> 0)."""
        text = self.subclass_lvl.get().strip()
        return int(text) if text.isdigit() else 0

    # ======================================================================
    # Save-file writing
    # ======================================================================
    def submit_loadout(self):
        """Write the current UI selections back into the save file (via the temp file)."""
        selected_module_ids = [self._slot_object_id(mod.get()) for mod in self.option_mods]
        pistol_slot_id = self._slot_object_id(self.pistol_mod.get())
        # (object id, power) for every slot we write a tpoints_ value for
        power_writes = list(zip(selected_module_ids, self.power_mods)) + [(pistol_slot_id, self.pistol_power)]
        subclass_lvl_key = f"subclasslvl{self.current_class}"
        subclass_lvl = self._get_subclass_lvl()
        # single-value keys to overwrite for the current class: key -> new numeric value
        challenge_writes = {
            f"subclasspst{self.current_class}": 1 if self.prestige_var.get() else 0,
            f"scl{self.current_class}": 2 if self.insanity_challenge_var.get() else (1 if self.class_challenge_var.get() else 0),
        }
        for code, var in self.insanity_sub_vars.items():
            challenge_writes[f"{code}{self.current_class}"] = 2 if var.get() else 0

        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if line.startswith(subclass_lvl_key + "="):
                    tsave.write(re.sub(r'"-?\d+(\.\d+)?"', f'"{subclass_lvl}.000000"', line))
                    continue

                matched_challenge = False
                for key, value in challenge_writes.items():
                    if line.startswith(key + "="):
                        tsave.write(re.sub(r'"-?\d+(\.\d+)?"', f'"{value}.000000"', line))
                        matched_challenge = True
                        break
                if matched_challenge:
                    continue

                if line.startswith(f"perkslot{LOADOUT_SLOTS[0]}class{self.current_class}"):
                    tsave.write(re.sub(r"obj_\w+(\d+)?_\w+", pistol_slot_id, line))
                    continue

                matched_slot = False
                for slot_code, module_id in zip(MODULE_SLOT_CODES, selected_module_ids):
                    if line.startswith(f"perkslot{slot_code}class{self.current_class}"):
                        tsave.write(re.sub(r"obj_\w+(\d+)?_\w+", module_id, line))
                        matched_slot = True
                        break
                if matched_slot:
                    continue

                if line.startswith("tpoints_"):
                    for module_id, power_mod in power_writes:
                        if line.startswith(f"tpoints_{module_id}="):
                            tsave.write(re.sub(r'"-?\d+(\.\d+)?"', f'"{power_mod.get()}"', line))
                            break
                    else:
                        tsave.write(line)
                    continue

                tsave.write(line)

        self.safety_window()

    def safety_window(self):
        """Either save immediately, or ask for confirmation first, depending on self.safety."""
        if self.safety == 0:
            self.copy_to_save()
        else:
            safety_window = tk.Toplevel(self, bg=S.BG)
            safety_window.title("ALERT!")
            safety_window.transient(self)
            S.label(safety_window, "Do you want to overwrite your save file?", 20).pack(padx=24, pady=(18, 10))
            S.button(
                safety_window, "Yes",
                lambda: [self.copy_to_save(), safety_window.destroy()], accent=True,
            ).pack(pady=(0, 18))
            safety_window.update_idletasks()
            safety_window.geometry("+%d+%d" % (
                (safety_window.winfo_screenwidth() - safety_window.winfo_reqwidth()) // 2,
                (safety_window.winfo_screenheight() - safety_window.winfo_reqheight()) // 2))

    def copy_to_save(self):
        with open(self.filename, "w") as save, open(self.tfilename, "r") as tsave:
            for line in tsave:
                save.write(line)
        old_power = dict(self.module_power)
        old_summary = dict(self.editor.class_summary)
        self.setsave()
        # Re-sync level/challenge widgets with what is now in the file, so
        # actions like "MAX Level All Classes" show up immediately.
        self._load_subclass_lvl()
        self._sync_power_vars()
        self._merge_file_changes_into_drafts(old_power, old_summary)
        self.editor.show_submitted()

    def _sync_power_vars(self):
        """Point every shown slot's power at what the file now says for its
        object.  Without this, actions that rewrite tpoints_ (Auto Module Edit,
        OP, Quick 1.6x) would leave stale numbers on screen - and the next
        SUBMIT would write those stale numbers straight back over them.
        (After SUBMIT itself the vars already equal the file, so it's a no-op.)"""
        pairs = list(zip(self.option_mods, self.power_mods)) + [(self.pistol_mod, self.pistol_power)]
        for name_var, power_var in pairs:
            obj_id = self._slot_object_id(name_var.get())
            if obj_id in self.module_power:
                power_var.set(self.module_power[obj_id])

    def safety_func(self):
        """Toggle whether saving asks for confirmation first."""
        self.safety = 0 if self.safety != 0 else 1

    # ======================================================================
    # Misc / cheat menu actions
    # ======================================================================
    def auto_module_edit(self, power):
        """Set every module, artefact and core tpoints_ value to a single user-supplied number
        (items, pistols and game modes have no power, so they are left alone)."""
        if re.search(r"(-?(0|[1-9]\d*)?(\.\d+)?(?<=\d)(e-?(0|[1-9]\d*))?|0x[0-9a-f]+)", power) is None:
            messagebox.showinfo(
                "Power error",
                "Sorry, you pressed the AutoModule button without putting an "
                "integer input in! Try using only numbers this time, okay?",
            )
            return
        true_power = f'"{power}"'
        pattern = re.compile(r"^tpoints_(obj_(?:perk|artefact)_\w+)=")
        mode_ids = {m.obj_id for m in I.CATALOG if m.kind == "mode"}
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                match = pattern.match(line)
                if match and match.group(1) not in mode_ids:
                    tsave.write(re.sub(r'"-?\d+(\.\d+)?"', true_power, line))
                else:
                    tsave.write(line)
        self.safety_window()

    def op_module_edit(self):
        """Apply a curated 'overpowered' power value to each perk it covers (matched by perk ID)."""
        messagebox.showinfo("Ymmv", "Overpowered module power editing (your mileage may vary)")
        pattern = re.compile(r"^tpoints_(obj_perk_\w+)=")
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                match = pattern.match(line)
                if match and match.group(1) in OP_MODULE_POWER_BY_ID:
                    power = OP_MODULE_POWER_BY_ID[match.group(1)]
                    tsave.write(re.sub(r'"-?\d+(\.\d+)?"', f'"{power}"', line))
                else:
                    tsave.write(line)
        self.safety_window()

    def _rewrite_lines_matching(self, prefix, replacement):
        """Shared helper: rewrite every line starting with `prefix`, replacing its
        numeric value with `replacement`."""
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if line.startswith(prefix):
                    tsave.write(re.sub(r'"-?\d+(\.\d+)?"', replacement, line))
                else:
                    tsave.write(line)
        self.safety_window()

    def new_daily_run(self):
        self._rewrite_lines_matching("drun", '"1.000000"')

    def max_data(self):
        self._rewrite_lines_matching("currency", '"1000.000000"')

    def cheat_code_return(self):
        self._rewrite_lines_matching("statist", '"0.000000"')

    def undo_research(self):
        self._rewrite_lines_matching("resunlock", '"0.000000"')

    def unlock_all(self):
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if re.search("unlock_", line) is None:
                    tsave.write(line)
                else:
                    tsave.write(re.sub(r'"-?\d+\.\d+"', '"1.000000"', line))
        self.safety_window()

    def weapon_spawn_reset(self):
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if line.startswith("wdropchange"):
                    # wdropchange147 (Armageddon Shard) needs to stay negative,
                    # otherwise it shows up in drop pools it shouldn't.
                    # Pistols can't be picked up; keep them out of drop pools too.
                    m = re.match(r"wdropchange(\d+)=", line)
                    if line.startswith("wdropchange147") or (m and m.group(1) in PISTOL_WEAPON_IDS):
                        tsave.write(re.sub(r'"-?\d+\.\d+"', '"-10.000000"', line))
                    else:
                        tsave.write(re.sub(r'"-?\d+\.\d+"', '"0.000000"', line))
                else:
                    tsave.write(line)
        self.safety_window()

    def item_spawn_reset(self):
        self._rewrite_lines_matching("idropchange", '"0.000000"')

    def max_level_all_classes(self):
        """Set every subclass to level 25 with Prestige, Class Challenge, and
        Insanity Challenge (ski/sad/sta/sma=2, scl=2, subclasspst=1) complete."""
        class_codes = set(re.findall(r"subclasslvl(\d+)=", open(self.filename).read()))
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                for code in class_codes:
                    if line.startswith(f"subclasslvl{code}="):
                        tsave.write(re.sub(r'"-?\d+(\.\d+)?"', '"25.000000"', line))
                        break
                    if line.startswith(f"subclasspst{code}="):
                        tsave.write(re.sub(r'"-?\d+(\.\d+)?"', '"1.000000"', line))
                        break
                    if line.startswith(f"scl{code}="):
                        tsave.write(re.sub(r'"-?\d+(\.\d+)?"', '"2.000000"', line))
                        break
                    if any(line.startswith(f"{prefix}{code}=") for prefix in ("ski", "sad", "sta", "sma")):
                        tsave.write(re.sub(r'"-?\d+(\.\d+)?"', '"2.000000"', line))
                        break
                else:
                    tsave.write(line)
        self.safety_window()

    def about(self):
        messagebox.showinfo(
            "Synthetik Python Mod",
            "By: Builder_Roberts\nMade for Synthetik 1!\n"
            "With help from: Tactu, Arti, Lawro, Saper, ElectricOldMen",
        )

    def not_working(self):
        messagebox.showinfo(
            "Actual help",
            "first: try opening and closing synthetik. Make sure Synthetik is "
            "closed. That will reset the save file to what Synthetik Needs.\n"
            "Second: You may be asking,\n \"Why did I just get nothing from a crate?????\"\n"
            "The answer is slightly complex. Each set of floors before the boss has "
            "a limit on how rare an item can be on that floor. So, if you only let "
            "ultra rare legendary items spawn, you won't get diddly from a normal chest before the last set of floors.\n"
            "(This is why items and weapons have the color rarities they do on the main menu in game btw)\n"
            "There are exceptions to this; cursed and boss chests have no limit on what you can get.\n"
            "If something goes absolutely terribly wrong, contact @mason on the sythetik discord server."
        )   

    # ======================================================================
    # Weapon / item spawn-list editing
    # ======================================================================
    def _read_negative_dropchange_ids(self, prefix, id_separator=""):
        """Return the set of id strings whose current <prefix><sep><id>=... value
        in the save file is negative - i.e. weapons/items the game is
        currently suppressing. Used to pre-uncheck them in the spawn-list
        checklists, so the checklist reflects the save file's actual state
        instead of always starting fully checked.
        """
        negative_ids = set()
        pattern = re.compile(rf"^{re.escape(prefix)}{re.escape(id_separator)}(\d+)=")
        with open(self.filename, "r") as save:
            for line in save:
                match = pattern.match(line)
                if not match:
                    continue
                value_match = re.search(r'"(-?\d+(?:\.\d+)?)"', line)
                if value_match and float(value_match.group(1)) < 0:
                    negative_ids.add(match.group(1))
        return negative_ids

    def _load_thumbnail(self, image_map, images_subdir, name, scale=1.0):
        """Load (and cache) a fixed-size PhotoImage thumbnail for one weapon/
        item name, falling back to PLACEHOLDER_IMAGE if there's no mapped
        art or the file is missing (e.g. a handful of dev/debug items with
        no dedicated wiki art).
        """
        if not hasattr(self, "_thumb_cache"):
            self._thumb_cache = {}
        size = (max(8, round(THUMB_SIZE[0] * scale)), max(8, round(THUMB_SIZE[1] * scale)))
        cache_key = (images_subdir, name, size)
        if cache_key in self._thumb_cache:
            return self._thumb_cache[cache_key]

        filename = (image_map or {}).get(name, PLACEHOLDER_IMAGE)
        path = os.path.join(ASSETS_DIR, images_subdir, filename)
        if not os.path.exists(path):
            path = os.path.join(ASSETS_DIR, images_subdir, PLACEHOLDER_IMAGE)

        try:
            source_img = Image.open(path).convert("RGBA")
        except Exception:
            source_img = Image.new("RGBA", size, (60, 60, 60, 255))

        source_img.thumbnail(size, Image.LANCZOS)
        tile_img = Image.new("RGBA", size, (0, 0, 0, 0))
        offset = ((size[0] - source_img.width) // 2, (size[1] - source_img.height) // 2)
        tile_img.paste(source_img, offset, source_img)

        photo = ImageTk.PhotoImage(tile_img)
        self._thumb_cache[cache_key] = photo
        return photo

    def _make_scrollable_checklist(self, parent, names, initial_checked=None,
                                    image_map=None, images_subdir=None):
        """Build a scrollable, auto-reflowing grid of image tiles, one per
        name. Clicking a tile toggles it; a colored border marks it as
        selected (border = selected, no border = unselected). The number of
        columns adjusts to however wide the window currently is, so the
        grid fills the space nicely at any window size, including maximized/
        fullscreen.

        `initial_checked` is an optional {name: bool} dict for per-name
        starting state (names not present default to True/checked). Pass
        nothing to start everything checked.

        Returns (container_frame, {name: BooleanVar}, set_visible).
        Pack/grid the container into the window; read the BooleanVars back to
        see what's checked. `set_visible(names)` shows only the tiles whose
        name is in `names` and hides the rest (hiding a tile never changes
        its checked state) - used by the category filters.
        """
        container = tk.Frame(parent, bg=S.BG)
        canvas = tk.Canvas(container, highlightthickness=0, bg=S.PANEL)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        checklist_frame = tk.Frame(canvas, bg=S.PANEL)

        checklist_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=checklist_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self._wheel_targets[parent] = canvas

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        checklist_vars = {}
        tiles = []  # [(name, tile_frame), ...] in display order, re-gridded on resize
        visible = set(names)  # names currently shown; the rest are grid_remove()d

        for name in names:
            default_checked = True if initial_checked is None else initial_checked.get(name, True)
            var = tk.BooleanVar(value=default_checked)
            checklist_vars[name] = var

            photo = self._load_thumbnail(image_map, images_subdir, name, self.ui_scale)

            tile = tk.Frame(
                checklist_frame,
                highlightthickness=BORDER_WIDTH,
                highlightbackground=BORDER_SELECTED if default_checked else BORDER_UNSELECTED,
                highlightcolor=BORDER_SELECTED if default_checked else BORDER_UNSELECTED,
                bd=0, bg=S.ROW,
            )

            image_label = tk.Label(tile, image=photo, bd=0, bg=S.ROW)
            image_label.image = photo  # keep a reference so it isn't garbage-collected
            image_label.pack()

            caption = tk.Label(tile, text=name.upper(), fg=S.TEXT, bg=S.ROW, justify="center")
            caption.pack()

            def sync_border(*_args, var=var, tile=tile):
                color = BORDER_SELECTED if var.get() else BORDER_UNSELECTED
                tile.configure(highlightbackground=color, highlightcolor=color)

            var.trace_add("write", sync_border)

            def toggle(_event, var=var):
                var.set(not var.get())

            for widget in (tile, image_label, caption):
                widget.bind("<Button-1>", toggle)

            tiles.append((name, tile, image_label, caption))

        metrics = {}  # current border / padding / footprint, updated by rescale()

        def reflow(event=None):
            width = canvas.winfo_width()
            columns = max(1, width // metrics["total_width"])
            idx = 0
            for name, tile, _img, _cap in tiles:
                if name not in visible:
                    tile.grid_remove()
                    continue
                row, col = divmod(idx, columns)
                tile.grid(row=row, column=col, padx=metrics["pad"], pady=metrics["pad"])
                idx += 1

        def rescale(scale):
            thumb = max(8, round(THUMB_SIZE[0] * scale))
            border = max(1, round(BORDER_WIDTH * scale))
            metrics["pad"] = max(1, round(TILE_PADDING * scale))
            wrap = thumb + round(26 * scale)
            metrics["total_width"] = wrap + 2 * border + 2 * metrics["pad"]
            for name, tile, image_label, caption in tiles:
                photo = self._load_thumbnail(image_map, images_subdir, name, scale)
                image_label.configure(image=photo)
                image_label.image = photo
                caption.configure(wraplength=wrap, font=S.font(max(6, round(12 * scale))))
                tile.configure(highlightthickness=border)
            reflow()

        rescale(self.ui_scale)
        self._scale_hooks.append(rescale)

        def set_visible(names_to_show):
            visible.clear()
            visible.update(names_to_show)
            reflow()
            canvas.yview_moveto(0)  # the list just got shorter/longer; start from the top

        canvas.bind("<Configure>", reflow)
        # Lay out once as soon as the canvas has a real size (right after
        # the tab becomes visible / the window is drawn the first time).
        container.after(50, reflow)

        return container, checklist_vars, set_visible

    @staticmethod
    def _set_all_checks(checklist_vars, value, only=None):
        """Set every checkbox to `value`, or - if `only` (a collection of
        names) is given - just the ones named in it, leaving the rest alone.
        """
        for name, var in checklist_vars.items():
            if only is None or name in only:
                var.set(value)

    def _apply_spawn_list(self, id_list, dropchange_prefix, unlock_prefix, missing_error_title, missing_error_msg):
        """Boost drop chance and unlock everything named in id_list, and
        suppress everything else.

        CHANGED vs. the original AutoWeaponSpawnEdit/WGetspawn: dropped a
        fallback in the "wunlock" branch that force-unlocked a weapon
        whenever the *current line's own* value already read '"0.' - a
        check that didn't depend on which weapon was being matched and
        looked like leftover/dead logic rather than an intentional rule.
        See LoadoutGUI.py's _apply_spawn_list() for the full note.
        """
        if not id_list:
            messagebox.showinfo(missing_error_title, missing_error_msg)
            return

        remaining = list(id_list)
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if line.startswith(dropchange_prefix):
                    for wanted in id_list:
                        if line.startswith(f"{dropchange_prefix}{wanted}="):
                            tsave.write(re.sub(r'"-?\d+\.\d+"', '"10.000000"', line))
                            break
                    else:
                        tsave.write(re.sub(r'"-?\d+\.\d+"', '"-8.000000"', line))
                elif line.startswith(unlock_prefix):
                    for wanted in remaining:
                        if line.startswith(f"{unlock_prefix}{wanted}="):
                            tsave.write(re.sub(r'"-?\d+\.\d+"', '"1.000000"', line))
                            remaining.remove(wanted)
                            break
                    else:
                        tsave.write(line)
                else:
                    tsave.write(line)
        self.safety_window()

    def w_get_spawn(self, weapon_checklist):
        """weapon_checklist: {weapon name: BooleanVar} from the Weapons tab."""
        self.weapon_spawn_ids.clear()
        self.weapon_spawn_ids.extend(
            str(SHOWN_WEAPONS.index(name)) for name, checked in weapon_checklist.items() if checked.get()
        )
        self._apply_spawn_list(
            self.weapon_spawn_ids, "wdropchange", "wunlock",
            "Token Error", "No weapons were checked in that list.",
        )

    def i_get_spawn(self, item_checklist):
        """item_checklist: {item name: BooleanVar} from the Items tab."""
        self.item_spawn_ids.clear()
        self.item_spawn_ids.extend(
            str(SHOWN_ITEMS.index(name)) for name, checked in item_checklist.items() if checked.get()
        )
        if not self.item_spawn_ids:
            messagebox.showinfo("Token Error", "No items were checked in that list.")
            return
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if line.startswith("idropchange"):
                    for item in self.item_spawn_ids:
                        if line.startswith(f"idropchange {item}="):
                            tsave.write(re.sub(r'"-?\d+\.\d+"', '"10.000000"', line))
                            break
                    else:
                        tsave.write(re.sub(r'"-?\d+\.\d+"', '"-8.000000"', line))
                else:
                    tsave.write(line)
        self.safety_window()

    # ======================================================================
    # Widget construction
    # ======================================================================
    def _build_styles(self):
        S.setup_ttk(self)
        style = ttk.Style(self)

        def rescale_tabs(scale):
            style.configure("TNotebook.Tab", font=S.font(max(8, round(18 * scale))),
                            padding=(round(18 * scale), max(2, round(4 * scale))))
        self._scale_hooks.append(rescale_tabs)

    def _build_notebook(self):
        """The whole window is one Notebook: "Synthetik Editor" (class picker
        + loadout/power editing - what used to be the only thing in the
        window), "Weapons" and "Items" (the spawn-list checklists), and
        "Cheats" (everything that used to live in the Power/Misc menus).
        """
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.editor_tab = ttk.Frame(self.notebook)
        self.weapons_tab = ttk.Frame(self.notebook)
        self.items_tab = ttk.Frame(self.notebook)
        self.cheats_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_tab, text="Synthetik Editor")
        self.notebook.add(self.weapons_tab, text="Weapons")
        self.notebook.add(self.items_tab, text="Items")
        self.notebook.add(self.cheats_tab, text="Cheats")

    def _build_editor_tab(self):
        """The in-game-style loadout screen (see editor_view.py).  It reads and
        writes the variables created in __init__, so submit_loadout/change_class
        below are unchanged."""
        self.editor = EditorView(self.editor_tab, self)
        self.editor.pack(fill=tk.BOTH, expand=True)

    def _on_insanity_master_toggle(self):
        """Checking/unchecking the master 'Insanity Challenge' box sets all
        4 sub-challenge checkboxes to match, and implies Class Challenge."""
        value = self.insanity_challenge_var.get()
        for var in self.insanity_sub_vars.values():
            var.set(value)
        if value:
            self.class_challenge_var.set(True)

    def _sync_insanity_master(self):
        """Master box reflects whether all 4 sub-challenges are checked."""
        all_checked = all(v.get() for v in self.insanity_sub_vars.values())
        self.insanity_challenge_var.set(all_checked)
        if all_checked:
            self.class_challenge_var.set(True)

    def _build_weapons_tab(self):
        """Weapons tab: a checklist of every weapon, pre-checked from the
        save file's current wdropchange values (negative -> starts unchecked).
        """
        negative_weapon_ids = self._read_negative_dropchange_ids("wdropchange")
        weapon_names = [n for n in SHOWN_WEAPONS[1:99] if n not in PISTOL_WEAPON_NAMES]
        weapon_initial = {name: str(SHOWN_WEAPONS.index(name)) not in negative_weapon_ids for name in weapon_names}
        self._build_spawn_tab(
            self.weapons_tab, weapon_names, weapon_initial,
            confirm_text="Apply Weapon Spawn List",
            on_confirm=self.w_get_spawn,
            image_map=WEAPON_IMAGES,
            images_subdir="weapons",
            categories=WEAPON_CATEGORIES,
        )

    def _build_items_tab(self):
        """Items tab: a checklist of every item, pre-checked from the save
        file's current idropchange values (negative -> starts unchecked).
        """
        negative_item_ids = self._read_negative_dropchange_ids("idropchange", id_separator=" ")
        item_names = SHOWN_ITEMS[1:]
        item_initial = {name: str(SHOWN_ITEMS.index(name)) not in negative_item_ids for name in item_names}
        self._build_spawn_tab(
            self.items_tab, item_names, item_initial,
            confirm_text="Apply Item Spawn List",
            on_confirm=self.i_get_spawn,
            image_map=ITEM_IMAGES,
            images_subdir="items",
            categories=ITEM_CATEGORIES,
        )

    @staticmethod
    def _group_by_category(names, categories):
        """Work out which category filters apply to `names`.

        `categories` is an ordered {category: [names]} table (see
        WEAPON_CATEGORIES / ITEM_CATEGORIES). Returns (name_categories,
        category_order): {name: set of its categories} and the categories
        that actually contain at least one of `names`, in table order
        (so e.g. "Pistols" vanishes from the Weapons tab, where pistols are
        hidden). Any name not in the table at all goes under an automatic
        "Other" category, so it can't become impossible to show/select.
        """
        name_categories = {name: set() for name in names}
        for category, members in categories.items():
            for member in members:
                if member in name_categories:
                    name_categories[member].add(category)
        category_order = [c for c in categories if any(c in cats for cats in name_categories.values())]
        uncategorized = [name for name, cats in name_categories.items() if not cats]
        if uncategorized:
            for name in uncategorized:
                name_categories[name].add("Other")
            category_order.append("Other")
        return name_categories, category_order

    @staticmethod
    def _flow_layout(container, widgets, pad=2):
        """Lay `widgets` (children of `container`) out left to right,
        wrapping onto a new row whenever the container is too narrow, and
        size the container's height to fit - so a row of buttons reflows
        with the window instead of running off the edge.
        """
        def reflow(_event=None):
            width = container.winfo_width()
            if width <= 1:  # not laid out yet; the <Configure> event will call us again
                return
            x = y = row_height = 0
            for widget in widgets:
                w, h = widget.winfo_reqwidth(), widget.winfo_reqheight()
                if x and x + w > width:
                    x, y, row_height = 0, y + row_height + pad, 0
                widget.place(x=x, y=y)
                x += w + pad
                row_height = max(row_height, h)
            container.configure(height=max(1, y + row_height))

        container.configure(height=1)
        container.bind("<Configure>", reflow)
        return reflow

    def _build_spawn_tab(self, tab, names, initial_state, confirm_text, on_confirm,
                         image_map=None, images_subdir=None, categories=None):
        """Fill one Notebook tab with an image-tile checklist + category
        filters + Select All/Deselect All + an apply button. Click a tile to
        select/deselect it; a colored border marks the current selection.
        The grid reflows its column count to fill however wide the tab
        currently is.

        Category filters (when `categories` is given) only change what is
        SHOWN: a tile is visible if it belongs to at least one selected
        category. Select All / Deselect All act on the visible tiles only.
        Tiles hidden by the filter keep their checked state, and the apply
        button still uses every checked tile, hidden or not (the status line
        says how many selected tiles are currently hidden).
        """
        self._track(S.label(tab, "Click an image to select/deselect it. Green = selected.", 17, S.DIM), 17).pack(pady=(8, 0))

        # ---- category filter row (all categories selected = show everything)
        name_categories, category_order = ({}, [])
        category_vars = {}
        if categories:
            name_categories, category_order = self._group_by_category(names, categories)
            category_vars = {category: tk.BooleanVar(value=True) for category in category_order}

        def visible_names():
            if not categories:
                return set(names)
            selected = {category for category, var in category_vars.items() if var.get()}
            return {name for name, cats in name_categories.items() if cats & selected}

        def refresh_filter():
            set_visible(visible_names())
            update_status()

        def set_all_categories(value):
            for var in category_vars.values():
                var.set(value)
            refresh_filter()

        if category_order:
            filter_box = self._track(tk.LabelFrame(tab, text=" FILTER BY CATEGORY ", bg=S.BG, fg=S.DIM,
                                                   bd=1, relief="solid", highlightthickness=0), 15)
            filter_box.pack(fill=tk.X, padx=8, pady=(6, 0))
            flow = tk.Frame(filter_box, bg=S.BG)
            flow.pack(fill=tk.X, padx=4, pady=(0, 4))
            widgets = [
                self._track(S.button(flow, "All", lambda: set_all_categories(True), size=15, padx=8, pady=0), 15, 8, 0),
                self._track(S.button(flow, "None", lambda: set_all_categories(False), size=15, padx=8, pady=0), 15, 8, 0),
            ]
            widgets += [
                self._track(S.chip(flow, category, category_vars[category], refresh_filter), 15, 8, 1)
                for category in category_order
            ]
            reflow_chips = self._flow_layout(flow, widgets)
            # after a font change the chips' sizes change: re-wrap them once Tk has re-measured
            self._scale_hooks.append(lambda _scale: flow.after_idle(reflow_chips))

        # ---- Select All / Deselect All (visible tiles only) + status line
        button_row = tk.Frame(tab, bg=S.BG)
        button_row.pack(fill=tk.X, padx=8, pady=6)
        checklist_vars = {}
        self._track(S.button(
            button_row, "Select All",
            lambda: self._set_all_checks(checklist_vars, True, only=visible_names()), size=16, pady=1,
        ), 16, 14, 1).pack(side=tk.LEFT)
        self._track(S.button(
            button_row, "Deselect All",
            lambda: self._set_all_checks(checklist_vars, False, only=visible_names()), size=16, pady=1,
        ), 16, 14, 1).pack(side=tk.LEFT, padx=(4, 0))
        status_label = self._track(S.label(button_row, "", 16, S.DIM, anchor="e"), 16)
        status_label.pack(side=tk.RIGHT)

        def update_status(*_args):
            shown = visible_names()
            selected = [name for name, var in checklist_vars.items() if var.get()]
            hidden_selected = sum(1 for name in selected if name not in shown)
            text = f"Showing {len(shown)}/{len(names)}  \u00b7  {len(selected)} selected"
            if hidden_selected:
                text += f" ({hidden_selected} hidden)"
            status_label.configure(text=text)

        # The footer is packed to the bottom BEFORE the expanding checklist, so
        # when the window is short it's the tile grid that shrinks - the apply
        # button never gets pushed off-screen.
        self._track(S.button(tab, confirm_text, lambda: on_confirm(checklist_vars), size=22, accent=True, padx=24),
                    22, 24, 4).pack(side=tk.BOTTOM, pady=(0, 10))
        self._track(S.label(
            tab,
            "You'll need to redo this periodically; the game eventually restores the original spawn list.",
            15, S.DIMMER,
        ), 15).pack(side=tk.BOTTOM, pady=(0, 6))

        checklist_frame, checklist_vars, set_visible = self._make_scrollable_checklist(
            tab, names, initial_checked=initial_state, image_map=image_map, images_subdir=images_subdir,
        )
        checklist_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        for var in checklist_vars.values():
            var.trace_add("write", update_status)
        update_status()

        return checklist_vars

    def _build_cheats_tab(self):
        """Cheats tab: everything that used to be in the Power/Misc menus,
        as plain buttons instead of menu items.
        """
        tab = self.cheats_tab
        # A scrollable page (the list is taller than a shrunk window): canvas + scrollbar,
        # with one centred column of full-width buttons inside it.
        scrollbar = ttk.Scrollbar(tab, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(tab, highlightthickness=0, bg=S.BG, yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.configure(command=canvas.yview)
        column = tk.Frame(canvas, bg=S.BG)
        window = canvas.create_window(0, 0, window=column, anchor="n")

        def on_canvas_resize(event):
            canvas.coords(window, event.width // 2, 8)
        canvas.bind("<Configure>", on_canvas_resize)
        column.bind("<Configure>", lambda _e: canvas.configure(scrollregion=(0, 0, 1, column.winfo_reqheight() + 16)))
        self._wheel_targets[tab] = canvas
        sections = [
            ("Power", [
                ("OP Auto (curated overpowered perk values)", self.op_module_edit),
                ("Quick 1.6x All Module / Artefact / Core Power", lambda: self.auto_module_edit("1.60000")),
            ]),
            ("Misc", [
                ("Daily Run Reset", self.new_daily_run),
                ("Max Data", self.max_data),
                ("Undo Research", self.undo_research),
                ("Cheat Code Reset", self.cheat_code_return),
                ("Toggle Ask-For-Confirmation Before Saving", self.safety_func),
                ("Unlock All", self.unlock_all),
                ("MAX Level All Classes", self.max_level_all_classes),
            ]),
        ]
        row = 0
        for title, buttons in sections:
            heading = tk.Frame(column, bg=S.BG)
            heading.grid(row=row, column=0, sticky="ew", pady=(14 if row == 0 else 22, 6))
            self._track(S.label(heading, title.upper(), 26, "#ffffff"), 26).pack(side=tk.LEFT)
            tk.Frame(heading, bg=S.EDGE, height=1).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0), pady=(10, 0))
            row += 1
            for text, command in buttons:
                btn = S.button(column, text, command, size=19, pady=3)
                btn.grid(row=row, column=0, sticky="ew", pady=2, ipadx=60)
                self._track(btn, 19, pady=3, grid_ipadx=60)
                row += 1

    def _build_menu(self):
        menu_bar = Menu(self)

        file_menu = Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open", command=lambda: self.browse_files(self.filename, self.tfilename))
        file_menu.add_command(label="Show", command=self.open_save)
        file_menu.add_command(label="Exit", command=self.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        help_menu = Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=self.about)
        help_menu.add_command(label="Not working?", command=self.not_working)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menu_bar)


if __name__ == "__main__":
    root = Root()
    root.mainloop()


# --------------------------------------------------------------------------
# Name mapping: LoadoutGUI.py (free functions/globals) -> LoadoutEditor.py (methods)
# --------------------------------------------------------------------------
#   Testfunc                -> Root.change_class
#   SubmitLoadout             -> Root.submit_loadout
#   Safetywindow              -> Root.safety_window
#   CopytoSave                -> Root.copy_to_save
#   safetyFunc                 -> Root.safety_func
#   AutoModuleEdit             -> Root.auto_module_edit
#   OPModuleEdit               -> Root.op_module_edit
#   NewDailyRun/MaxData/CheatCodeReturn/undoresearch/itemspawnreset
#                              -> Root._rewrite_lines_matching + thin wrappers
#   UnlockAll, weaponspawnreset -> Root.unlock_all, Root.weapon_spawn_reset
#   (AutoWeaponSpawnEdit/AutoItemSpawnEdit/tokenset removed: newer saves have no
#     wbonus/wplus/wminus/ibonus/iplus/iminus token lines)
#   WNewSpawn/WGetspawn/INewSpawn/IGetSpawn -> Root._build_weapons_tab /
#     _build_items_tab (top-level Notebook tabs, no popup) + w_get_spawn/
#     i_get_spawn (checklist-driven, pre-checked from the save file's
#     current wdropchange/idropchange values)
#   Power menu (OPauto, Quick 1.6x) and Misc menu (Daily Run Reset, Max
#   Data, Undo Research, Cheat Code Reset, Ask For Confirmation, Unlock
#   All) -> Root._build_cheats_tab (plain buttons on the "Cheats" tab;
#   the underlying methods - op_module_edit, auto_module_edit, etc. - are
#   unchanged, only how you trigger them changed)
#   openSave/about/notworking -> Root.open_save / about / not_working
#   module-level globals (safety, current_class, weapon_spawn_ids, item_spawn_ids)
#   -> same names as self.* attributes.
