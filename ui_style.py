"""ui_style.py - dark, in-game styling for the plain Tk widgets on the Weapons / Items /
Cheats tabs (and the dialogs), so they match the drawn Editor tab.

Colours come from ui_theme's palette; text uses Bebas Neue when it can be loaded
(Windows: registered privately for this process), else Tk's default font.
"""
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import ui_theme as T


def hexc(color):
    return "#%02x%02x%02x" % tuple(color)


BG = hexc(T.BG_BOTTOM)             # window / tab background
PANEL = hexc(T.CLASS_PANEL)        # boxes
ROW = hexc(T.CLASS_ROW)            # buttons, tabs
ROW_HOVER = hexc(T.CLASS_ROW_HOVER)
ACCENT = "#6644d2"                 # purple used for the loadout/submit highlights
ACCENT_HOVER = "#7d5cf0"
GREEN = "#3ba55d"                  # "selected" colour on the spawn-list tiles
EDGE = hexc(T.BORDER)
TEXT = hexc(T.CREAM)
DIM = hexc(T.DIM_TEXT)
DIMMER = hexc(T.DIMMER_TEXT)

_family = None


def _load_font():
    """Register Bebas Neue and return its family name, or None if unavailable."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.gdi32.AddFontResourceExW(T.FONT_FILE, 0x10, 0)  # FR_PRIVATE
        except Exception:
            return None
    return "Bebas Neue" if "Bebas Neue" in tkfont.families() else None


def font(size, bold=False):
    """Tk font tuple.  `size` is a Bebas Neue size; the fallback font is sized down to match."""
    global _family
    if _family is None:
        _family = _load_font() or ""
    if _family:
        return (_family, size)
    return ("TkDefaultFont", max(7, round(size * 0.62)), "bold" if bold else "normal")


def label(parent, text="", size=16, color=TEXT, **kw):
    kw.setdefault("bg", BG)
    return tk.Label(parent, text=text, font=font(size), fg=color, **kw)


def button(parent, text, command, size=18, accent=False, padx=14, pady=4, **kw):
    """Flat dark button with a hover colour."""
    base, hot = (ACCENT, ACCENT_HOVER) if accent else (ROW, ROW_HOVER)
    b = tk.Button(parent, text=text.upper(), command=command, font=font(size), fg="#ffffff", bg=base,
                  activebackground=hot, activeforeground="#ffffff", relief="flat", bd=0,
                  highlightthickness=1, highlightbackground=EDGE, highlightcolor=EDGE,
                  padx=padx, pady=pady, cursor="hand2", **kw)
    b.bind("<Enter>", lambda _e: b.configure(bg=hot))
    b.bind("<Leave>", lambda _e: b.configure(bg=base))
    return b


def chip(parent, text, variable, command, size=15):
    """Category toggle: dim when off, accent when on."""
    return tk.Checkbutton(parent, text=text.upper(), variable=variable, command=command, font=font(size),
                          indicatoron=False, bg=ROW, fg=DIM, selectcolor=ACCENT, activebackground=ROW_HOVER,
                          activeforeground="#ffffff", relief="flat", bd=0, highlightthickness=1,
                          highlightbackground=EDGE, padx=8, pady=1, cursor="hand2")


def setup_ttk(root):
    """Dark Notebook tabs, frames and scrollbars."""
    root.configure(bg=BG)
    s = ttk.Style(root)
    s.theme_use("alt")
    s.configure("TFrame", background=BG)
    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(8, 6, 8, 0))
    s.configure("TNotebook.Tab", background=ROW, foreground=DIM, font=font(18), padding=(18, 4), borderwidth=0)
    s.map("TNotebook.Tab", background=[("selected", ACCENT), ("active", ROW_HOVER)],
          foreground=[("selected", "#ffffff"), ("active", "#ffffff")])
    s.configure("Vertical.TScrollbar", background=ROW_HOVER, troughcolor=PANEL, bordercolor=PANEL,
                arrowcolor=DIM, lightcolor=ROW_HOVER, darkcolor=ROW_HOVER, gripcount=0)
    s.map("Vertical.TScrollbar", background=[("active", ACCENT)])
