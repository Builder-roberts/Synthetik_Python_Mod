"""LoadoutEditor.py

Synthetik Loadout Editor v3.0 - class-based rewrite of LoadoutGUI.py.

This now has the same functionality as LoadoutGUI.py, restructured into a
tabbed window (a ttk.Notebook across the whole main window):
  - "Synthetik Editor" tab: class picker, pistol + 6 module dropdowns with
    power fields and class-color coding, weapon/item token editor, submit.
  - "Weapons" / "Items" tabs: spawn-list checklists (Select All/Deselect
    All + one checkbox per weapon/item, pre-checked from the save file's
    current wdropchange/idropchange values).
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

from synthetik_data import (
    CLASS_CODES,
    ITEM_IMAGES,
    LOADOUT_SLOTS,
    OP_MODULE_POWER,
    PLACEHOLDER_IMAGE,
    SHOWN_ITEMS,
    SHOWN_MODULES,
    SHOWN_PISTOLS,
    SHOWN_WEAPONS,
    VAR_MODULES,
    VAR_PISTOLS,
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
BORDER_SELECTED = "#3ba55d"    # green border = selected
BORDER_UNSELECTED = "#3a3a3a"  # neutral/invisible-ish border = unselected
BORDER_WIDTH = 3
TILE_PADDING = 3
# Total footprint of one tile (thumbnail + caption + border + grid padding),
# used to figure out how many columns fit in the current canvas width.
TILE_TOTAL_WIDTH = THUMB_SIZE[0] + 14 + 2 * BORDER_WIDTH + 2 * TILE_PADDING

# (range_start, range_end, style_name, foreground) - which slice of
# SHOWN_MODULES belongs to which class color. Doesn't depend on any
# instance, so it lives at module level like in LoadoutGUI.py.
MODULE_COLOR_RANGES = [
    (0, 4, "Other.TCombobox", "black"),
    (4, 8, "Mode.TCombobox", "black"),
    (8, 23, "Artefact.TCombobox", "black"),
    (23, 47, "Specialist.TCombobox", "white"),
    (47, 73, "Commando.TCombobox", "white"),
    (73, 98, "Rouge.TCombobox", "white"),
    (98, 123, "Gaurdian.TCombobox", "white"),
    (123, 131, "Other.TCombobox", "black"),
]

# Slots for OptionMod1..6, in that order - see change_class()/submit_loadout().
MODULE_SLOT_CODES = list(reversed(LOADOUT_SLOTS[1:7]))


class Root(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Synthetik Loadout Editor v3.0")
        self.geometry("500x550")
        self.minsize(500, 500)

        # ---- state ------------------------------------------------------
        # safety == 0 -> save immediately. safety == 1 -> ask first.
        self.safety = 0
        self.current_token_kind = "i"          # "w" or "i"
        self.current_class = "10"
        self.loadout_items = []                # perk/item object IDs, current class's slots
        self.tokens = []                        # raw w*/i* token lines from the save
        self.class_tokens = []                  # subset of self.tokens for current class
        self.double_modules = []                # tpoints_* values, index-aligned to VAR_MODULES
        self.weapon_spawn_ids = []
        self.item_spawn_ids = []
        self.current_token_shown = SHOWN_ITEMS  # whichever of SHOWN_WEAPONS/SHOWN_ITEMS is active
        # No Token_frame UI anymore, but tokenset() still refreshes token
        # values (invisibly) from the save file so submit_loadout() keeps
        # writing back whatever bonus/plus/minus tokens were already there.
        self.token_comboboxes = []

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
        self.pistol_mod = tk.StringVar(self)
        self.option_mods = [tk.StringVar(self) for _ in range(6)]
        self.power_mods = [tk.StringVar(self) for _ in range(6)]
        self.bonus_tok = [tk.StringVar(self) for _ in range(4)]
        self.up_tok = [tk.StringVar(self) for _ in range(4)]
        self.down_tok = [tk.StringVar(self) for _ in range(4)]
        self.autopower_var = tk.StringVar(self)

        # ---- widgets -------------------------------------------------
        self._build_styles()
        self._build_notebook()
        self._build_class_buttons()
        self._build_power_frame()
        self._build_weapons_tab()
        self._build_items_tab()
        self._build_cheats_tab()
        self._build_menu()

        # ---- initial load -------------------------------------------------
        self.setsave()
        self.change_class(self.current_class)
        self.tokenset(self.current_token_kind)

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
        """Re-read every module's tpoints_ (power) value from the save file."""
        self.double_modules.clear()
        with open(self.filename, "r") as save:
            for line in save:
                if line.startswith(("tpoints_obj_perk", "tpoints_obj_artefact", "tpoints_obj_item")):
                    power_str = re.search(r'"-?\d+(\.\d+)?"', line).group()
                    power_str = re.search(r"-?\d+(\.\d+)?", power_str).group()
                    self.double_modules.append(power_str)

    @staticmethod
    def spliting(class_code):
        """'10' -> '1_0' - the save file separates class and subclass with an underscore."""
        return f"{class_code[0]}_{class_code[1]}"

    def change_class(self, subclass):
        """Load the given class's loadout (pistol, 6 modules, their power, tokens) into the UI."""
        self.current_class = subclass
        self.loadout_items.clear()
        self.tokens.clear()

        with open(self.filename, "r") as save:
            for line in save:
                if line.startswith("perkslot"):
                    for slot in LOADOUT_SLOTS:
                        if line.startswith(f"perkslot{slot}class{self.current_class}"):
                            item_id = re.search(r"obj_\w+(\d+)?_\w+", line).group()
                            self.loadout_items.append(item_id)
                elif line.startswith(("wbonus", "wplus", "wminus", "ibonus", "iplus", "iminus")):
                    self.tokens.append(line)

        self.pistol_mod.set(SHOWN_PISTOLS[VAR_PISTOLS.index(self.loadout_items[0])])

        # loadout_items[1:7] are the 6 module slots, but in reverse order
        # versus option_mods[0..5] - see LoadoutGUI.py's Testfunc() for why.
        for option_mod, power_mod, item in zip(self.option_mods, self.power_mods, reversed(self.loadout_items[1:7])):
            option_mod.set(SHOWN_MODULES[VAR_MODULES.index(item)])
            power_mod.set(self.double_modules[VAR_MODULES.index(item)])

        self.pistol_change_color()
        for option_mod, combobox in zip(self.option_mods, self.module_comboboxes):
            self.reg_change_color(option_mod, combobox)

        self.tokenset(self.current_token_kind)

    def tokenset(self, kind):
        """Populate the Bonus/Up/Down token values for the given kind ('w' or
        'i'). There's no visible UI for these anymore, but the values still
        need to be refreshed from the save file so submit_loadout() writes
        back the same tokens instead of clobbering them.
        """
        split_class = self.spliting(self.current_class)
        for token in self.tokens:
            if token.startswith(kind) and re.search(split_class, token) is not None:
                self.class_tokens.append(token)

        self.current_token_kind = kind
        self.current_token_shown = SHOWN_WEAPONS if kind == "w" else SHOWN_ITEMS
        for combobox in self.token_comboboxes:
            combobox["values"] = self.current_token_shown

        def fill_group(target_vars, prefix):
            """Fill one group of 4 token variables (bonus/plus/minus) from class_tokens."""
            for target in target_vars:
                matched = False
                for token in self.class_tokens:
                    if token.startswith(kind + prefix):
                        raw = re.search(r'"-?\d+(\.\d+)?"', token).group()
                        index = int(float(raw[1:-1]))
                        target.set(self.current_token_shown[index])
                        self.class_tokens.remove(token)
                        matched = True
                        break
                if not matched:
                    target.set("")

        fill_group(self.bonus_tok, "bonus")
        fill_group(self.up_tok, "plus")
        fill_group(self.down_tok, "minus")

    # ======================================================================
    # Save-file writing
    # ======================================================================
    def submit_loadout(self):
        """Write the current UI selections back into the save file (via the temp file)."""
        split_class = self.spliting(self.current_class)
        selected_module_ids = [VAR_MODULES[SHOWN_MODULES.index(mod.get())] for mod in self.option_mods]

        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if line.startswith(f"perkslot{LOADOUT_SLOTS[0]}class{self.current_class}"):
                    tsave.write(re.sub(r"obj_\w+(\d+)?_\w+", VAR_PISTOLS[SHOWN_PISTOLS.index(self.pistol_mod.get())], line))
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
                    for module_id, power_mod in zip(selected_module_ids, self.power_mods):
                        if line.startswith("tpoints_" + module_id):
                            tsave.write(re.sub(r'"-?\d+(\.\d+)?"', f'"{power_mod.get()}"', line))
                            break
                    else:
                        tsave.write(line)
                    continue

                if line.startswith("wunlock0"):
                    tsave.write(line)
                    if self.current_token_kind == "w":
                        self._write_token_group(tsave, split_class, "w", SHOWN_WEAPONS)
                    continue

                if self.current_token_kind == "w" and line.startswith(("wbonus", "wplus", "wminus")):
                    if re.search(split_class, line) is None:
                        tsave.write(line)
                    continue

                if line.startswith("iintel 0"):
                    tsave.write(line)
                    if self.current_token_kind == "i":
                        self._write_token_group(tsave, split_class, "i", SHOWN_ITEMS)
                    continue

                if self.current_token_kind == "i" and line.startswith(("ibonus", "iplus", "iminus")):
                    if re.search(split_class, line) is None:
                        tsave.write(line)
                    continue

                tsave.write(line)

        self.safety_window()

    def _write_token_group(self, tsave, split_class, kind, shown_list):
        """Write out the wbonus/wplus/wminus (or ibonus/iplus/iminus) lines for the
        tokens currently held (read from the save file by tokenset()).

        NOTE: the written index (__0, __1, __2...) counts only non-empty
        entries, in order - it is NOT each variable's fixed position in
        bonus_tok/up_tok/down_tok. Matches LoadoutGUI.py's behavior.
        """
        for suffix, group in (("bonus", self.bonus_tok), ("plus", self.up_tok), ("minus", self.down_tok)):
            written = 0
            for token_var in group:
                value = token_var.get()
                if not value:
                    continue
                token_index = shown_list.index(value)
                tsave.write(f'{kind}{suffix}_{split_class}__{written}="{token_index}.000000"\n')
                written += 1

    def safety_window(self):
        """Either save immediately, or ask for confirmation first, depending on self.safety."""
        if self.safety == 0:
            self.copy_to_save()
        else:
            safety_window = tk.Toplevel(self)
            safety_window.title("ALERT!")
            tk.Label(safety_window, text="Do you want to overwrite your Save File?").pack()
            tk.Button(
                safety_window,
                text="Yes",
                command=lambda: [self.copy_to_save(), safety_window.destroy()],
            ).pack()

    def copy_to_save(self):
        with open(self.filename, "w") as save, open(self.tfilename, "r") as tsave:
            for line in tsave:
                save.write(line)
        self.setsave()

    def safety_func(self):
        """Toggle whether saving asks for confirmation first."""
        self.safety = 0 if self.safety != 0 else 1

    # ======================================================================
    # Misc / cheat menu actions
    # ======================================================================
    def auto_module_edit(self, power):
        """Set every perk's tpoints_ value to a single user-supplied number."""
        if re.search(r"(-?(0|[1-9]\d*)?(\.\d+)?(?<=\d)(e-?(0|[1-9]\d*))?|0x[0-9a-f]+)", power) is None:
            messagebox.showinfo(
                "Power error",
                "Sorry, you pressed the AutoModule button without putting an "
                "integer input in! Try using only numbers this time, okay?",
            )
            return
        true_power = f'"{power}"'
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if line.startswith("tpoints_obj_perk_"):
                    tsave.write(re.sub(r'"-?\d+(\.\d+)?"', true_power, line))
                else:
                    tsave.write(line)
        self.safety_window()

    def op_module_edit(self):
        """Apply a curated 'overpowered' power value to each perk, in file order.

        FRAGILE: assumes tpoints_obj_perk_* lines appear in the save file in
        exactly the same order as OP_MODULE_POWER.
        """
        messagebox.showinfo("Ymmv", "Overpowered module power editing (your mileage may vary)")
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            i = 0
            for line in save:
                if line.startswith("tpoints_obj_perk_"):
                    tsave.write(re.sub(r'"-?\d+(\.\d+)?"', f'"{OP_MODULE_POWER[i]}"', line))
                    i += 1
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
                    if line.startswith("wdropchange147"):
                        tsave.write(re.sub(r'"-?\d+\.\d+"', '"-10.000000"', line))
                    else:
                        tsave.write(re.sub(r'"-?\d+\.\d+"', '"0.000000"', line))
                else:
                    tsave.write(line)
        self.safety_window()

    def item_spawn_reset(self):
        self._rewrite_lines_matching("idropchange", '"0.000000"')

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

    def _load_thumbnail(self, image_map, images_subdir, name):
        """Load (and cache) a fixed-size PhotoImage thumbnail for one weapon/
        item name, falling back to PLACEHOLDER_IMAGE if there's no mapped
        art or the file is missing (e.g. a handful of dev/debug items with
        no dedicated wiki art).
        """
        if not hasattr(self, "_thumb_cache"):
            self._thumb_cache = {}
        cache_key = (images_subdir, name)
        if cache_key in self._thumb_cache:
            return self._thumb_cache[cache_key]

        filename = (image_map or {}).get(name, PLACEHOLDER_IMAGE)
        path = os.path.join(ASSETS_DIR, images_subdir, filename)
        if not os.path.exists(path):
            path = os.path.join(ASSETS_DIR, images_subdir, PLACEHOLDER_IMAGE)

        try:
            source_img = Image.open(path).convert("RGBA")
        except Exception:
            source_img = Image.new("RGBA", THUMB_SIZE, (60, 60, 60, 255))

        source_img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        tile_img = Image.new("RGBA", THUMB_SIZE, (0, 0, 0, 0))
        offset = ((THUMB_SIZE[0] - source_img.width) // 2, (THUMB_SIZE[1] - source_img.height) // 2)
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

        Returns (container_frame, {name: BooleanVar}). Pack/grid the
        container into the window; read the BooleanVars back to see what's
        checked - same interface as the old checkbox version, so
        w_get_spawn/i_get_spawn/_set_all_checks don't need to change.
        """
        container = tk.Frame(parent)
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        checklist_frame = tk.Frame(canvas)

        checklist_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=checklist_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_mousewheel(event):
            canvas.yview_scroll(-1 * (event.delta // 120), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        checklist_vars = {}
        tiles = []  # [(name, tile_frame), ...] in display order, re-gridded on resize

        for name in names:
            default_checked = True if initial_checked is None else initial_checked.get(name, True)
            var = tk.BooleanVar(value=default_checked)
            checklist_vars[name] = var

            photo = self._load_thumbnail(image_map, images_subdir, name)

            tile = tk.Frame(
                checklist_frame,
                highlightthickness=BORDER_WIDTH,
                highlightbackground=BORDER_SELECTED if default_checked else BORDER_UNSELECTED,
                highlightcolor=BORDER_SELECTED if default_checked else BORDER_UNSELECTED,
                bd=0,
            )

            image_label = tk.Label(tile, image=photo, bd=0)
            image_label.image = photo  # keep a reference so it isn't garbage-collected
            image_label.pack()

            caption = tk.Label(tile, text=name, wraplength=THUMB_SIZE[0] + 14, font=("TkDefaultFont", 7), justify="center")
            caption.pack()

            def sync_border(*_args, var=var, tile=tile):
                color = BORDER_SELECTED if var.get() else BORDER_UNSELECTED
                tile.configure(highlightbackground=color, highlightcolor=color)

            var.trace_add("write", sync_border)

            def toggle(_event, var=var):
                var.set(not var.get())

            for widget in (tile, image_label, caption):
                widget.bind("<Button-1>", toggle)

            tiles.append((name, tile))

        def reflow(event=None):
            width = canvas.winfo_width()
            columns = max(1, width // TILE_TOTAL_WIDTH)
            for idx, (_name, tile) in enumerate(tiles):
                row, col = divmod(idx, columns)
                tile.grid(row=row, column=col, padx=TILE_PADDING, pady=TILE_PADDING)

        canvas.bind("<Configure>", reflow)
        # Lay out once as soon as the canvas has a real size (right after
        # the tab becomes visible / the window is drawn the first time).
        container.after(50, reflow)

        return container, checklist_vars

    @staticmethod
    def _set_all_checks(checklist_vars, value):
        for var in checklist_vars.values():
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

    def auto_weapon_spawn_edit(self):
        """Boost spawn/unlock for whichever weapons currently have a power token."""
        split_class = self.spliting(self.current_class)
        weapon_ids = []
        with open(self.filename, "r") as save:
            for line in save:
                if line.startswith("wbonus_" + split_class):
                    weapon_ids.append(re.search(r'"\d+\.', line).group()[1:-1])
        self._apply_spawn_list(
            weapon_ids, "wdropchange", "wunlock",
            "Token Error", "Sorry, would you go add a power token to the weapon(s) you want?",
        )

    def auto_item_spawn_edit(self):
        """Boost spawn chance for whichever item currently has a power token."""
        split_class = self.spliting(self.current_class)
        item_ids = []
        with open(self.filename, "r") as save:
            for line in save:
                if line.startswith("ibonus_" + split_class):
                    item_ids.append(re.search(r'"\d+\.', line).group()[1:-1])
        if not item_ids:
            messagebox.showinfo("Token Error", "Sorry, would you go add a power token for the item you want?")
            return
        with open(self.filename, "r") as save, open(self.tfilename, "w") as tsave:
            for line in save:
                if line.startswith("idropchange"):
                    for item in item_ids:
                        if line.startswith(f"idropchange {item}="):
                            tsave.write(re.sub(r'"-?\d+\.\d+"', '"10.000000"', line))
                            break
                    else:
                        tsave.write(re.sub(r'"-?\d+\.\d+"', '"-8.000000"', line))
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
    # Combobox color-coding
    # ======================================================================
    def pistol_change_color(self):
        current_pistol = self.pistol_mod.get()
        if current_pistol in (SHOWN_PISTOLS[10], SHOWN_PISTOLS[11]):
            self.gun.configure(style="Gaurdian.TCombobox", foreground="white")
        elif current_pistol in (SHOWN_PISTOLS[12], SHOWN_PISTOLS[13]):
            self.gun.configure(style="Rouge.TCombobox", foreground="white")
        elif current_pistol in (SHOWN_PISTOLS[7], SHOWN_PISTOLS[8]):
            self.gun.configure(style="Commando.TCombobox", foreground="white")
        elif current_pistol in (SHOWN_PISTOLS[5], SHOWN_PISTOLS[6]):
            self.gun.configure(style="Specialist.TCombobox", foreground="white")
        else:
            self.gun.configure(style="Other.TCombobox", foreground="black")

    def reg_change_color(self, module_var, combobox):
        current_value = module_var.get()
        try:
            module_index = SHOWN_MODULES.index(current_value)
        except ValueError:
            return
        for start, end, style_name, foreground in MODULE_COLOR_RANGES:
            if start <= module_index < end:
                combobox.configure(style=style_name, foreground=foreground)
                return

    # ======================================================================
    # Widget construction
    # ======================================================================
    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("alt")
        style.configure("Gaurdian.TCombobox", fieldbackground="blue")
        style.configure("Rouge.TCombobox", fieldbackground="darkblue")
        style.configure("Commando.TCombobox", fieldbackground="darkgreen")
        style.configure("Specialist.TCombobox", fieldbackground="red")
        style.configure("Other.TCombobox", fieldbackground="white")
        style.configure("Mode.TCombobox", fieldbackground="lightblue")
        style.configure("Artefact.TCombobox", fieldbackground="lightgreen")

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

        self.main_frame = ttk.Frame(self.editor_tab, padding=(20))
        self.main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.Button_frame = ttk.Frame(self.main_frame, borderwidth=5)
        self.Button_frame.grid(column=0, row=0, sticky="n")
        self.Power_frame = ttk.Frame(self.main_frame, borderwidth=5)
        self.Power_frame.grid(column=1, row=0, sticky="n")

        self.submit_button = tk.Button(self.editor_tab, text="SUBMIT", command=self.submit_loadout)
        self.submit_button.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_class_buttons(self):
        self.class_buttons = {}
        for label, code, color in CLASS_CODES:
            button = tk.Button(
                self.Button_frame, text=label, fg="white", bg=color,
                command=lambda c=code: self.change_class(c),
            )
            button.pack(fill=tk.X)
            self.class_buttons[code] = button

    def _build_power_frame(self):
        self.gun = ttk.Combobox(self.Power_frame, textvariable=self.pistol_mod)
        self.gun["values"] = SHOWN_PISTOLS
        self.gun.grid(row=0, column=1, columnspan=2)
        self.gun.bind("<<ComboboxSelected>>", lambda _: self.pistol_change_color())

        self.module_comboboxes = []
        for row, (option_mod, power_mod) in enumerate(zip(self.option_mods, self.power_mods), start=1):
            module_box = ttk.Combobox(self.Power_frame, textvariable=option_mod)
            module_box["values"] = SHOWN_MODULES
            module_box.grid(row=row, column=1)
            module_box.bind(
                "<<ComboboxSelected>>",
                lambda _, m=option_mod, b=module_box: self.reg_change_color(m, b),
            )
            power_box = ttk.Combobox(self.Power_frame, textvariable=power_mod)
            power_box.grid(row=row, column=2)
            self.module_comboboxes.append(module_box)

        submit_row = len(self.option_mods) + 1
        """tk.Button(self.Power_frame, text="submit", command=self.submit_loadout).grid(
            row=submit_row, column=1, columnspan=2
        )"""
        self.autopower_entry = ttk.Entry(self.Power_frame, textvariable=self.autopower_var)
        tk.Button(
            self.Power_frame, text="Auto Module Edit",
            command=lambda: self.auto_module_edit(self.autopower_var.get()),
        ).grid(row=submit_row + 1, column=1)
        self.autopower_entry.grid(row=submit_row + 1, column=2)

    def _build_weapons_tab(self):
        """Weapons tab: a checklist of every weapon, pre-checked from the
        save file's current wdropchange values (negative -> starts unchecked).
        """
        negative_weapon_ids = self._read_negative_dropchange_ids("wdropchange")
        weapon_names = SHOWN_WEAPONS[1:99]
        weapon_initial = {name: str(SHOWN_WEAPONS.index(name)) not in negative_weapon_ids for name in weapon_names}
        self._build_spawn_tab(
            self.weapons_tab, weapon_names, weapon_initial,
            confirm_text="Apply Weapon Spawn List",
            on_confirm=self.w_get_spawn,
            image_map=WEAPON_IMAGES,
            images_subdir="weapons",
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
        )

    def _build_spawn_tab(self, tab, names, initial_state, confirm_text, on_confirm, image_map=None, images_subdir=None):
        """Fill one Notebook tab with an image-tile checklist + Select All/
        Deselect All + an apply button. Click a tile to select/deselect it;
        a colored border marks the current selection. The grid reflows its
        column count to fill however wide the tab currently is."""
        tk.Label(tab, text="Click an image to select/deselect it. Green = selected.").pack(pady=(6, 0))

        button_row = tk.Frame(tab)
        button_row.pack(fill=tk.X, padx=8, pady=4)
        checklist_vars = {}
        tk.Button(button_row, text="Select All", command=lambda: self._set_all_checks(checklist_vars, True)).pack(side=tk.LEFT)
        tk.Button(button_row, text="Deselect All", command=lambda: self._set_all_checks(checklist_vars, False)).pack(side=tk.LEFT, padx=(4, 0))

        checklist_frame, checklist_vars = self._make_scrollable_checklist(
            tab, names, initial_checked=initial_state, image_map=image_map, images_subdir=images_subdir,
        )
        checklist_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        tk.Label(
            tab,
            text="You'll need to redo this periodically; the game eventually restores the original spawn list.",
        ).pack(pady=(0, 4))
        tk.Button(tab, text=confirm_text, command=lambda: on_confirm(checklist_vars)).pack(pady=(0, 8))

        return checklist_vars

    def _build_cheats_tab(self):
        """Cheats tab: everything that used to be in the Power/Misc menus,
        as plain buttons instead of menu items.
        """
        tab = self.cheats_tab
        tab.columnconfigure(0, weight=1)

        tk.Label(tab, text="Power", font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 4)
        )
        tk.Button(tab, text="OP Auto (curated overpowered perk values)", command=self.op_module_edit).grid(
            row=1, column=0, sticky="ew", padx=14, pady=2
        )
        tk.Button(tab, text="Quick 1.6x All Perk Power", command=lambda: self.auto_module_edit("1.60000")).grid(
            row=2, column=0, sticky="ew", padx=14, pady=2
        )

        tk.Label(tab, text="Misc", font=("TkDefaultFont", 11, "bold")).grid(
            row=3, column=0, sticky="w", padx=14, pady=(20, 4)
        )
        tk.Button(tab, text="Daily Run Reset", command=self.new_daily_run).grid(row=4, column=0, sticky="ew", padx=14, pady=2)
        tk.Button(tab, text="Max Data", command=self.max_data).grid(row=5, column=0, sticky="ew", padx=14, pady=2)
        tk.Button(tab, text="Undo Research", command=self.undo_research).grid(row=6, column=0, sticky="ew", padx=14, pady=2)
        tk.Button(tab, text="Cheat Code Reset", command=self.cheat_code_return).grid(row=7, column=0, sticky="ew", padx=14, pady=2)
        tk.Button(tab, text="Toggle Ask-For-Confirmation Before Saving", command=self.safety_func).grid(
            row=8, column=0, sticky="ew", padx=14, pady=2
        )
        tk.Button(tab, text="Unlock All", command=self.unlock_all).grid(row=9, column=0, sticky="ew", padx=14, pady=(2, 14))

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
#   tokenset                 -> Root.tokenset (method; no visible UI anymore,
#                                 just keeps bonus/plus/minus tokens intact
#                                 across a save)
#   SubmitLoadout             -> Root.submit_loadout
#   Safetywindow              -> Root.safety_window
#   CopytoSave                -> Root.copy_to_save
#   safetyFunc                 -> Root.safety_func
#   AutoModuleEdit             -> Root.auto_module_edit
#   OPModuleEdit               -> Root.op_module_edit
#   NewDailyRun/MaxData/CheatCodeReturn/undoresearch/itemspawnreset
#                              -> Root._rewrite_lines_matching + thin wrappers
#   UnlockAll, weaponspawnreset -> Root.unlock_all, Root.weapon_spawn_reset
#   AutoWeaponSpawnEdit/AutoItemSpawnEdit -> Root.auto_weapon_spawn_edit / auto_item_spawn_edit
#     (no longer exposed in a menu, but the methods are still here if you
#     want to wire a button back up to them)
#   WNewSpawn/WGetspawn/INewSpawn/IGetSpawn -> Root._build_weapons_tab /
#     _build_items_tab (top-level Notebook tabs, no popup) + w_get_spawn/
#     i_get_spawn (checklist-driven, pre-checked from the save file's
#     current wdropchange/idropchange values)
#   Power menu (OPauto, Quick 1.6x) and Misc menu (Daily Run Reset, Max
#   Data, Undo Research, Cheat Code Reset, Ask For Confirmation, Unlock
#   All) -> Root._build_cheats_tab (plain buttons on the "Cheats" tab;
#   the underlying methods - op_module_edit, auto_module_edit, etc. - are
#   unchanged, only how you trigger them changed)
#   Pistolchangecolor/Regchangecolor -> Root.pistol_change_color / reg_change_color
#   openSave/about/notworking -> Root.open_save / about / not_working
#   module-level globals (safety, current_class, loadout_items, tokens,
#   class_tokens, double_modules, current_token_kind, current_token_shown,
#   weapon_spawn_ids, item_spawn_ids) -> same names as self.* attributes.

