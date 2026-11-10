# Editor tab redesign - what's in this update

Drop these into your project folder (next to `LoadoutGUI.py`), keeping the paths:

    LoadoutGUI.py          changed (Editor tab now uses editor_view; pistol slot is generic)
    synthetik_data.py      unchanged since the category-filter update
    ui_theme.py            new  - palette, Bebas Neue text rendering, Pillow drawing helpers
    ui_icons.py            new  - module catalogue, display names, icon lookup/tinting
    ui_widgets.py          new  - Panel/PanelItem (drawn panels + hover/click)
    editor_view.py         new  - Classes / Loadout / Challenges / Tools panels
    editor_pickers.py      new  - module list, core grid, pistol-slot list, power popup
    assets/ui/**           new  - icons cut from your screenshots + wiki zips, Bebas Neue (OFL)
    tools/build_ui_assets.py   optional - regenerates assets/ui from your source screenshots

Your existing `assets/items` and `assets/weapons` are used as-is (via ITEM_IMAGES / WEAPON_IMAGES).

PyInstaller: `assets/ui` lives inside `assets/`, so if you already bundle the whole
`assets` folder nothing changes. The new .py modules are picked up by import.

## Things that are best guesses - please verify
* Core names: the game's "Rank Up" and "Calm" are shown for the data names
  "Core: Squad Leader" and "Core: Commando" (swap in ui_icons.CORE_DISPLAY if reversed).
  The picker prints the data name under each so you can always see what is stored.
* Game-mode icons (Tactical / Hyper Adrenaline / Madness / Mystery Bonus) - the
  wiki zip had no names; mapping is in tools/build_ui_assets.py MODE_ZIP.
* Power badge: shown as (value - 1) x 100%, i.e. 1.0 = +0%, 1.25 = +25%.
  Your save has every perk at 0.0, which therefore reads -100%.
* Commando and Rogue have 15 perks in your data / screenshots (Specialist and Guardian 16).
* Pure 759 and Taro artefact icons were cropped from the artifacts screenshot (no wiki file).
