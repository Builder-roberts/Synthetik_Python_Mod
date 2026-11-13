"""jukebox_view.py - the "Jukebox" tab.

Left:   every .ogg in the game folder, grouped by where it plays (jukebox / final boss / combat / ...).
Right:  the selected track (cover art + player) and a list of YOUR tracks (or the game's Master originals).

Drag your track (or an original) onto a game track to replace it - the file is copied over the game file
under the game file's exact name.  Drag one game track onto another to swap the two.  Every change can be
undone with UNDO, and RESTORE puts the Master original back.
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

import jukebox_core as C
import ui_style as S
import ui_theme as T
from jukebox_audio import Player

LIGHT = "#b79cff"        # "something of yours is in this slot"
RED = "#e23a3e"
AMBER = "#e0a030"
DROP = "#2f7d4a"         # drop-target highlight
ART_BASE = 150


# ---------------------------------------------------------------------------
# Small widgets
# ---------------------------------------------------------------------------
class Worker:
    """Run a function in a thread; its progress/result callbacks happen on the Tk thread."""

    def __init__(self, widget):
        self.widget, self.q, self.active, self.polling = widget, queue.Queue(), 0, False

    def run(self, fn, done, progress=None):
        self.active += 1

        def target():
            try:
                result = fn(lambda *a: self.q.put(("progress", progress, a)))
                self.q.put(("done", done, (result, None)))
            except Exception as exc:  # reported to the UI thread
                self.q.put(("done", done, (None, exc)))
        threading.Thread(target=target, daemon=True).start()
        if not self.polling:
            self.polling = True
            self.widget.after(50, self._poll)

    def _poll(self):
        try:
            while True:
                kind, callback, payload = self.q.get_nowait()
                if kind == "progress":
                    if callback:
                        callback(*payload)
                else:
                    self.active -= 1
                    callback(*payload)
        except queue.Empty:
            pass
        except tk.TclError:
            return
        if self.active > 0:
            self.widget.after(50, self._poll)
        else:
            self.polling = False


class ScrollList(tk.Frame):
    """A vertically scrolling column of rows."""

    def __init__(self, parent):
        super().__init__(parent, bg=S.PANEL, highlightthickness=1, highlightbackground=S.EDGE)
        self.canvas = tk.Canvas(self, bg=S.PANEL, highlightthickness=0, bd=0, yscrollincrement=18)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=S.PANEL)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def refill(self, build):
        top = self.canvas.yview()[0]
        for child in self.inner.winfo_children():
            child.destroy()
        build()
        self.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(top)


class SliderBar(tk.Canvas):
    """A flat 0..1 slider (seek bar / volume).  command(value, final) is called while dragging and on release."""

    def __init__(self, parent, command, height=14, value=0.0, **kw):
        super().__init__(parent, height=height, bg=S.PANEL, highlightthickness=0, bd=0, cursor="hand2", **kw)
        self.command, self.value, self.dragging = command, value, False
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<ButtonPress-1>", lambda e: self._moved(e, False))
        self.bind("<B1-Motion>", lambda e: self._moved(e, False))
        self.bind("<ButtonRelease-1>", lambda e: self._moved(e, True))

    def set(self, value):
        if not self.dragging:
            self.value = min(1.0, max(0.0, value))
            self._draw()

    def _moved(self, event, final):
        self.dragging = not final
        width = max(1, self.winfo_width())
        self.value = min(1.0, max(0.0, event.x / width))
        self._draw()
        self.command(self.value, final)

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        mid, t = h // 2, max(2, h // 5)
        self.create_rectangle(0, mid - t, w, mid + t, fill=S.ROW, outline="")
        x = int(self.value * w)
        self.create_rectangle(0, mid - t, x, mid + t, fill=S.ACCENT, outline="")
        r = max(3, h // 2 - 1)
        self.create_oval(min(max(x, r), w - r) - r, mid - r, min(max(x, r), w - r) + r, mid + r, fill="#ffffff", outline="")


class WheelRouter:
    """Stands in for a canvas in Root._wheel_targets: scrolls whichever list the pointer is over."""

    def __init__(self, view):
        self.view = view

    def yview(self):
        return (0.0, 0.5)  # "scrollable"

    def yview_scroll(self, amount, what):
        try:
            w = self.view.winfo_containing(*self.view.winfo_pointerxy())
        except (tk.TclError, KeyError):
            return
        lists = [lst for lst in (getattr(self.view, "slot_list", None), getattr(self.view, "lib_list", None)) if lst]
        while w is not None:
            for lst in lists:
                if w is lst:
                    lst.canvas.yview_scroll(amount * 2, what)
                    return
            w = getattr(w, "master", None)


def _elide(text, limit):
    return text if len(text) <= limit else text[:limit - 1] + "..."


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------
class JukeboxView(tk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, bg=S.BG)
        self.root = root
        self.scale = 1.0
        self.worker = Worker(self)
        self.player = None
        self.lib = None
        self.game_dir = None
        self.slots, self.slot_by_rel, self.holders = [], {}, {}
        self.user_names = []
        self.sel = None                 # ("slot", rel) / ("user", name) / ("master", rel)
        self.lib_mode = "user"          # which list the right-hand column shows
        self.collapsed = {"sfx": True}
        self.history = []               # undo records, newest last
        self.busy = False
        self.mode = "setup"
        self.rows = {}                  # payload -> row frame (for repainting)
        self._art_cache = {}
        self._loaded_path = None
        self._drag = None
        self._rebuild_job = None
        self._filter_job = None
        self._started = False
        self.search_var = tk.StringVar(self)
        self.search_var.trace_add("write", lambda *_a: self._schedule_filter())
        self.status_var = tk.StringVar(self)
        self.setup_lib_dir = None
        self.slot_list = self.lib_list = None

        root._wheel_targets[parent] = WheelRouter(self)
        root._scale_hooks.append(self.apply_scale)
        root.notebook.bind("<<NotebookTabChanged>>", self._tab_changed, add="+")
        self._build_setup()

    # ---- sizing helpers -------------------------------------------------
    def f(self, size):
        return S.font(max(6, round(size * self.scale)))

    def px(self, n):
        return max(1, round(n * self.scale))

    def apply_scale(self, scale):
        if abs(scale - self.scale) < 1e-6:
            return
        self.scale = scale
        if self._started:
            if self._rebuild_job:
                self.after_cancel(self._rebuild_job)
            self._rebuild_job = self.after(150, self._rebuild)

    def _rebuild(self):
        self._rebuild_job = None
        if self._drag and self._drag.get("active"):
            self._rebuild_job = self.after(300, self._rebuild)
            return
        self._art_cache.clear()
        if self.mode == "main":
            self._build_main()
            self._fill_all()
        else:
            self._build_setup()

    def _clear(self):
        for child in self.winfo_children():
            child.destroy()
        self.rows.clear()
        self.slot_list = self.lib_list = None

    # ---- start-up ---------------------------------------------------------
    def _tab_changed(self, _event):
        try:
            if self.root.notebook.select() == str(self.master):
                self._ensure_started()
        except tk.TclError:
            pass

    def _ensure_started(self):
        if self._started:
            return
        self._started = True
        self.player = Player()
        prefs = C.load_prefs()
        self.player_open = prefs.get("player_open", True)
        self._init_audio()
        self.game_dir = prefs.get("game_dir") if prefs.get("game_dir") and os.path.isdir(prefs["game_dir"]) else C.find_game_dir()
        lib_dir = prefs.get("library_dir")
        if lib_dir and os.path.isdir(lib_dir) and self.game_dir:
            self.lib = C.Library(lib_dir)
            self._build_main()
            self._refresh()
        else:
            self.setup_lib_dir = lib_dir if lib_dir and os.path.isdir(os.path.dirname(lib_dir)) else None
            self._build_setup()
        self._tick()

    # ---- audio set-up -------------------------------------------------------
    def _init_audio(self):
        """Start the player; if pygame is missing, download it automatically (once) and retry."""
        if self.player.init():
            return
        if not self.player.can_install or self.busy_audio:
            return
        self.busy_audio = True
        self._say("Setting up audio playback (one-time download)...")

        def done(result, err):
            self.busy_audio = False
            message = str(err) if err else result
            if not message and self.player.init():
                self._say("Audio ready.")
            else:
                self.player.can_install = False
                if message:
                    self.player.error = message
                self._say("Audio playback isn't available - see the player panel.", True)
            self._loaded_path = None
            self._update_info()
        self.worker.run(lambda _r: self.player.install_backend(), done)

    busy_audio = False

    def _audio_problem(self):
        """Called when the user asks for playback but the player isn't ready: retry, and say why."""
        if self.busy_audio:
            self._say("Still setting up audio - one moment...")
            return
        self.player.can_install = not getattr(sys, "frozen", False)
        self._init_audio()
        if not self.player.ok and not self.busy_audio:
            self._say(_elide(self.player.error or "Audio isn't available.", 90), True)
        elif self.player.ok:
            self._loaded_path = None
            self._update_info()
    def _build_setup(self):
        self.mode = "setup"
        self._clear()
        box = tk.Frame(self, bg=S.PANEL, highlightthickness=1, highlightbackground=S.EDGE)
        box.place(relx=0.5, rely=0.46, anchor="center")
        pad = self.px(26)
        inner = tk.Frame(box, bg=S.PANEL)
        inner.pack(padx=pad, pady=pad)
        tk.Label(inner, text="SET UP YOUR JUKEBOX", bg=S.PANEL, fg="#ffffff", font=self.f(34), anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w")
        tk.Label(inner, bg=S.PANEL, fg=S.DIM, font=self.f(15), justify="left", anchor="w", wraplength=self.px(620),
                 text=("Pick a folder for your library. Inside it I'll create  Master  (untouched copies of every .ogg "
                       "in the game folder, so you can always get the originals back) and  User_tracks  (your own tracks, "
                       "converted to .ogg).")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 14))

        def path_row(r, title, value, command, empty):
            tk.Label(inner, text=title, bg=S.PANEL, fg=S.TEXT, font=self.f(17), anchor="w").grid(
                row=r * 2, column=0, columnspan=2, sticky="w")
            shown = value or empty
            tk.Label(inner, text=_elide(shown, 64), bg=S.ROW, fg=S.TEXT if value else AMBER, font=self.f(15), anchor="w",
                     padx=8, pady=4, width=1).grid(row=r * 2 + 1, column=0, sticky="ew", pady=(2, 10), ipadx=self.px(190))
            S.button(inner, "Change" if value else "Choose...", command, size=16, pady=2).grid(
                row=r * 2 + 1, column=1, sticky="e", padx=(8, 0), pady=(2, 10))

        path_row(1, "1.  SYNTHETIK GAME FOLDER", self.game_dir, self._choose_game_dir, "Not found - choose it")
        path_row(2, "2.  LIBRARY FOLDER (Master and User_tracks go in here)", self.setup_lib_dir, self._choose_setup_lib, "Not chosen yet")
        ready = bool(self.game_dir and self.setup_lib_dir)
        self.setup_go = S.button(inner, "Create Master copy and start", self._setup_go, size=20, accent=True, pady=6)
        self.setup_go.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(4, 6))
        self.setup_go.configure(disabledforeground=S.DIMMER)
        if not ready:
            self.setup_go.configure(state="disabled")
        self.setup_msg = tk.Label(inner, text="", bg=S.PANEL, fg=LIGHT, font=self.f(14), anchor="w")
        self.setup_msg.grid(row=7, column=0, columnspan=2, sticky="w")
        inner.columnconfigure(0, weight=1)
        self.pack(fill="both", expand=True)

    def _choose_game_dir(self):
        folder = filedialog.askdirectory(title="Select your Synthetik game folder", initialdir=self.game_dir or "C:/")
        if folder:
            self.game_dir = os.path.normpath(folder)
            if not C.scan_ogg(self.game_dir):
                messagebox.showwarning("Jukebox", "No .ogg files were found in that folder (or its sub-folders). "
                                                  "Make sure it's the Synthetik install folder.")
            self._build_setup()

    def _choose_setup_lib(self):
        folder = filedialog.askdirectory(title="Choose where your Jukebox library should live")
        if folder:
            self.setup_lib_dir = os.path.normpath(folder)
            self._build_setup()

    def _setup_go(self):
        if not (self.game_dir and self.setup_lib_dir) or self.busy:
            return
        try:
            self.lib = C.Library(self.setup_lib_dir)
        except OSError as exc:
            messagebox.showerror("Jukebox", f"Couldn't create the library folders there:\n{exc}")
            return
        C.update_prefs(game_dir=self.game_dir, library_dir=self.setup_lib_dir)
        self.setup_go.configure(state="disabled")
        self.busy = True

        def progress(i, n, rel):
            self.setup_msg.configure(text=f"Copying originals to Master...  {i}/{n}   {_elide(rel, 40)}")

        def job(report):
            total, copied = self.lib.build_master(self.game_dir, report)
            return total, copied, self.lib.analyze(self.game_dir)

        def done(result, err):
            self.busy = False
            if err:
                self.setup_msg.configure(text=f"Failed: {err}", fg=RED)
                self.setup_go.configure(state="normal")
                return
            total, copied, holders = result
            self.holders = holders
            self._build_main()
            self._reload_lists()
            self._fill_all()
            self._say(f"Master copy ready: {copied} new file(s) copied, {total} game track(s) found.")
        self.worker.run(job, done, progress)

    # ---- main screen -------------------------------------------------------
    def _build_main(self):
        self.mode = "main"
        self._clear()
        bar = tk.Frame(self, bg=S.BG)
        bar.pack(fill="x", padx=self.px(8), pady=(self.px(8), self.px(4)))
        self.btn_add = S.button(bar, "Add tracks...", self._add_tracks, size=17, accent=True, padx=10, pady=2)
        self.btn_add.pack(side="left")
        self.btn_undo = S.button(bar, "Undo", self._undo, size=17, padx=10, pady=2)
        self.btn_undo.pack(side="left", padx=(6, 0))
        S.button(bar, "Restore all originals", self._restore_all, size=17, padx=10, pady=2).pack(side="left", padx=(6, 0))
        S.button(bar, "Rescan", self._refresh, size=17, padx=10, pady=2).pack(side="left", padx=(6, 0))
        S.button(bar, "Synthetik cover...", self._set_default_cover, size=17, padx=10, pady=2).pack(side="left", padx=(6, 0))
        search = tk.Entry(bar, textvariable=self.search_var, width=18, font=self.f(15), bg=S.PANEL, fg=S.TEXT,
                          insertbackground=S.TEXT, relief="flat", highlightthickness=1, highlightbackground=S.EDGE,
                          highlightcolor=S.ACCENT)
        search.pack(side="right", ipady=self.px(3))
        S.label(bar, "SEARCH", 15, S.DIM).pack(side="right", padx=(0, 6))
        self.btn_undo.configure(disabledforeground=S.DIMMER)
        self._update_undo_button()

        foot = tk.Frame(self, bg=S.BG)
        foot.pack(side="bottom", fill="x", padx=self.px(8), pady=(self.px(2), self.px(6)))
        self.status_lbl = tk.Label(foot, textvariable=self.status_var, bg=S.BG, fg=S.DIM, font=self.f(14), anchor="w")
        self.status_lbl.pack(side="left", fill="x", expand=True)
        for title, value, command in (("GAME", self.game_dir, self._change_game_dir),
                                      ("LIBRARY", self.lib.base if self.lib else "", self._change_library)):
            link = tk.Label(foot, text=f"{title}: {_elide(os.path.normpath(value) if value else '-', 34)}  (change)",
                            bg=S.BG, fg=S.DIMMER, font=self.f(13), cursor="hand2")
            link.pack(side="right", padx=(10, 0))
            link.bind("<Button-1>", lambda _e, c=command: c())

        body = tk.Frame(self, bg=S.BG)
        body.pack(fill="both", expand=True, padx=self.px(8))
        body.columnconfigure(0, weight=11, uniform="c")
        body.columnconfigure(1, weight=10, uniform="c")
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=S.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(4)))
        head = tk.Frame(left, bg=S.BG)
        head.pack(fill="x")
        S.label(head, "GAME TRACKS", 20, "#ffffff").pack(side="left")
        S.label(head, "drag onto another to swap", 13, S.DIMMER).pack(side="right")
        self.slot_list = ScrollList(left)
        self.slot_list.pack(fill="both", expand=True, pady=(2, 0))

        right = tk.Frame(body, bg=S.BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(self.px(4), 0))
        self._build_info(right)
        head = tk.Frame(right, bg=S.BG)
        head.pack(fill="x", pady=(self.px(6), 0))
        self.seg = {}
        for mode, text in (("user", "MY TRACKS"), ("master", "ORIGINALS")):
            lbl = tk.Label(head, text=text, font=self.f(17), padx=self.px(10), pady=self.px(1), cursor="hand2")
            lbl.pack(side="left", padx=(0, 4))
            lbl.bind("<Button-1>", lambda _e, m=mode: self._set_lib_mode(m))
            self.seg[mode] = lbl
        self.lib_hint = S.label(head, "drag onto a game track to replace it", 13, S.DIMMER)
        self.lib_hint.pack(side="right")
        self.lib_list = ScrollList(right)
        self.lib_list.pack(fill="both", expand=True, pady=(2, 0))
        self._paint_seg()
        self.pack(fill="both", expand=True)

    def _build_info(self, parent):
        head = tk.Frame(parent, bg=S.BG, cursor="hand2")
        head.pack(fill="x")
        self.player_head = head
        self.chev = tk.Canvas(head, width=self.px(16), height=self.px(16), bg=S.BG, highlightthickness=0)
        self.chev.pack(side="left", padx=(self.px(2), self.px(6)))
        title = tk.Label(head, text="PLAYER", bg=S.BG, fg="#ffffff", font=self.f(20), cursor="hand2")
        title.pack(side="left")
        self.mini = tk.Frame(head, bg=S.BG)
        self.mini_btn = S.button(self.mini, "Play", self._toggle_play, size=15, accent=True, padx=8, pady=0)
        self.mini_btn.pack(side="right")
        self.mini_lbl = tk.Label(self.mini, text="", bg=S.BG, fg=S.DIM, font=self.f(14))
        self.mini_lbl.pack(side="right", padx=(0, 8))
        for w in (head, self.chev, title):
            w.bind("<Button-1>", lambda _e: self._toggle_player_panel())
        box = tk.Frame(parent, bg=S.PANEL, highlightthickness=1, highlightbackground=S.EDGE)
        self.info_box = box
        if self.player_open:
            box.pack(fill="x")
        self._paint_chevron()
        art = self.px(ART_BASE)
        self.art_img = self._art_image(None, art)
        self.art_lbl = tk.Label(box, bg=S.PANEL, bd=0, image=self.art_img)
        self.art_lbl.grid(row=0, column=0, rowspan=2, padx=self.px(8), pady=self.px(8), sticky="n")
        right = tk.Frame(box, bg=S.PANEL)
        right.grid(row=0, column=1, sticky="nsew", pady=(self.px(6), 0), padx=(0, self.px(8)))
        box.columnconfigure(1, weight=1)
        self.info_title = tk.Label(right, text="", bg=S.PANEL, fg="#ffffff", font=self.f(26), anchor="w")
        self.info_title.pack(fill="x")
        self.info_sub = tk.Label(right, text="", bg=S.PANEL, fg=S.DIM, font=self.f(13), anchor="w")
        self.info_sub.pack(fill="x")
        self.info_status = tk.Label(right, text="", bg=S.PANEL, fg=LIGHT, font=self.f(15), anchor="w")
        self.info_status.pack(fill="x", pady=(self.px(2), 0))
        self.info_meta = tk.Label(right, text="", bg=S.PANEL, fg=S.DIM, font=self.f(13), anchor="w", justify="left",
                                  wraplength=self.px(250))
        self.info_meta.pack(fill="x")

        ctl = tk.Frame(right, bg=S.PANEL)
        ctl.pack(fill="x", pady=(self.px(6), 0))
        self.play_btn = S.button(ctl, "Play", self._toggle_play, size=16, accent=True, padx=10, pady=1)
        self.play_btn.pack(side="left")
        S.button(ctl, "Stop", self._stop, size=16, padx=10, pady=1).pack(side="left", padx=(4, 0))
        self.time_lbl = tk.Label(ctl, text="0:00 / 0:00", bg=S.PANEL, fg=S.DIM, font=self.f(14))
        self.time_lbl.pack(side="right")
        self.vol = SliderBar(ctl, lambda v, _f: self.player and self.player.set_volume(v), height=self.px(14),
                             value=self.player.volume if self.player else 0.8, width=self.px(54))
        self.vol.pack(side="right", padx=(0, self.px(10)))
        tk.Label(ctl, text="VOL", bg=S.PANEL, fg=S.DIMMER, font=self.f(13)).pack(side="right", padx=(0, 4))
        self.seek = SliderBar(right, self._on_seek, height=self.px(16))
        self.seek.pack(fill="x", pady=(self.px(6), 0))

        acts = tk.Frame(box, bg=S.PANEL)
        acts.grid(row=1, column=1, sticky="ew", padx=(0, self.px(8)), pady=(0, self.px(8)))
        self.act_art = S.button(acts, "Set art...", self._set_art, size=15, padx=6, pady=0)
        self.act_art.pack(side="left")
        self.act_clear = S.button(acts, "Reset art", self._clear_art, size=15, padx=6, pady=0)
        self.act_clear.pack(side="left", padx=(4, 0))
        self.act_main = S.button(acts, "Restore original", self._act_main, size=15, padx=6, pady=0)
        self.act_main.pack(side="right")
        for btn in (self.act_clear, self.act_main):
            btn.configure(disabledforeground=S.DIMMER)

    player_open = True

    def _paint_chevron(self):
        self.chev.delete("all")
        pts = [2, 4, 14, 4, 8, 12] if self.player_open else [4, 2, 12, 8, 4, 14]
        self.chev.create_polygon([self.px(p) for p in pts], fill=S.DIM, outline="")
        if self.player_open:
            self.mini.pack_forget()
        else:
            self.mini.pack(side="right", fill="x")

    def _toggle_player_panel(self):
        """Close / reopen the player.  Closing only hides it - whatever is playing keeps playing,
        and a small play/pause button stays in the header."""
        self.player_open = not self.player_open
        if self.player_open:
            self.info_box.pack(fill="x", after=self.player_head)
        else:
            self.info_box.pack_forget()
        self._paint_chevron()
        C.update_prefs(player_open=self.player_open)
        self._sync_transport()
        self._update_info()

    def _say(self, text, error=False):
        self.status_var.set(text)
        if hasattr(self, "status_lbl"):
            try:
                self.status_lbl.configure(fg=RED if error else S.DIM)
            except tk.TclError:
                pass

    # ---- data ----------------------------------------------------------------
    def _reload_lists(self):
        self.slots = self.lib.slots(self.game_dir)
        self.slot_by_rel = {s.rel: s for s in self.slots}
        self.user_names = self.lib.user_tracks()
        if self.sel:
            kind, ident = self.sel
            if (kind == "user" and ident not in self.user_names) or (kind != "user" and ident not in self.slot_by_rel):
                self.sel = None

    def _refresh(self):
        """Rescan the game folder (new files go into Master) and re-check what each slot holds."""
        if not self.lib or self.busy:
            return
        self.busy = True
        self._say("Scanning the game folder...")

        def job(_report):
            total, copied = self.lib.build_master(self.game_dir)
            return total, copied, self.lib.analyze(self.game_dir)

        def done(result, err):
            self.busy = False
            if err:
                self._say(f"Scan failed: {err}", True)
                return
            total, copied, self.holders = result
            self._reload_lists()
            self._fill_all()
            self._say(f"{total} game track(s)" + (f" - {copied} new one(s) copied into Master." if copied else "."))
        self.worker.run(job, done)

    def _reanalyze(self, message=None):
        def job(_report):
            return self.lib.analyze(self.game_dir)

        def done(result, err):
            if not err:
                self.holders = result
            self._reload_lists()
            self._fill_all()
            if message:
                self._say(message)
        self.worker.run(job, done)

    # ---- filling the lists -----------------------------------------------------
    def _fill_all(self):
        if self.mode != "main" or not self.slot_list:
            return
        self.rows.clear()
        self.slot_list.refill(self._build_slot_rows)
        self.lib_list.refill(self._build_lib_rows)
        self._update_info()
        self._update_undo_button()

    def _match(self, *texts):
        term = self.search_var.get().strip().lower()
        return not term or any(term in t.lower() for t in texts)

    def _schedule_filter(self):
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(200, self._fill_all)

    def _holder_text(self, slot):
        holder = self.holders.get(slot.rel)
        if not slot.exists:
            return "MISSING", RED
        if holder == ("master", slot.rel):
            return "ORIGINAL", S.DIM
        if holder and holder[0] == "master":
            return _elide("ORIGINAL: " + C.display_name(holder[1]), 30).upper(), LIGHT
        if holder:
            return _elide("YOURS: " + holder[1], 30).upper(), LIGHT
        return "UNKNOWN FILE", AMBER

    def _build_slot_rows(self):
        parent = self.slot_list.inner
        searching = bool(self.search_var.get().strip())
        for key, title, blurb in C.CATEGORIES:
            members = [s for s in self.slots if s.category == key and self._match(s.name, s.rel)]
            if not members:
                continue
            collapsed = self.collapsed.get(key, False) and not searching
            head = tk.Frame(parent, bg=S.PANEL, cursor="hand2")
            head.pack(fill="x", padx=self.px(6), pady=(self.px(8), self.px(2)))
            icon = tk.Canvas(head, width=self.px(14), height=self.px(14), bg=S.PANEL, highlightthickness=0)
            pts = [2, 3, 12, 3, 7, 11] if not collapsed else [3, 2, 11, 7, 3, 12]
            icon.create_polygon([self.px(p) for p in pts], fill=S.DIM, outline="")
            icon.pack(side="left", padx=(self.px(2), self.px(6)))
            tk.Label(head, text=f"{title.upper()}  ({len(members)})", bg=S.PANEL, fg="#ffffff", font=self.f(18)).pack(side="left")
            tk.Label(head, text=blurb, bg=S.PANEL, fg=S.DIMMER, font=self.f(13)).pack(side="right")
            for w in [head] + head.winfo_children():
                w.bind("<Button-1>", lambda _e, k=key: self._toggle_group(k))
            if collapsed:
                continue
            for slot in members:
                text, color = self._holder_text(slot)
                name = slot.name if key != "sfx" else C.stem_of(slot.rel)
                self._make_row(parent, ("slot", slot.rel), name, text, color, drop_rel=slot.rel)

    def _toggle_group(self, key):
        self.collapsed[key] = not self.collapsed.get(key, False)
        self.slot_list.refill(self._build_slot_rows)

    def _build_lib_rows(self):
        parent = self.lib_list.inner
        shown = 0
        if self.lib_mode == "user":
            for name in self.user_names:
                if self._match(name):
                    shown += 1
                    info = C.ogg_info(self.lib.user_path(name))
                    self._make_row(parent, ("user", name), name, C.fmt_time(info["duration"]) if info else "", S.DIM)
            if not self.user_names:
                tk.Label(parent, bg=S.PANEL, fg=S.DIM, font=self.f(16), justify="center", pady=self.px(24),
                         text="No tracks yet.\n\nClick ADD TRACKS to bring in mp3, wav, flac, m4a, ogg...\n"
                              "They're converted to .ogg and kept in User_tracks.").pack(fill="x")
        else:
            order = {key: i for i, (key, _t, _b) in enumerate(C.CATEGORIES)}
            for slot in sorted(self.slots, key=lambda s: (order.get(s.category, 99), s.name.lower())):
                if os.path.exists(slot.master_path) and self._match(slot.name, slot.rel) and (
                        slot.category != "sfx" or self.search_var.get().strip()):
                    shown += 1
                    self._make_row(parent, ("master", slot.rel), slot.name, C.CATEGORY_TITLES[slot.category].upper(), S.DIMMER)
        if shown == 0 and self.search_var.get().strip():
            tk.Label(parent, text="Nothing matches.", bg=S.PANEL, fg=S.DIM, font=self.f(15), pady=self.px(12)).pack()

    def _set_lib_mode(self, mode):
        self.lib_mode = mode
        self._paint_seg()
        self.lib_list.refill(self._build_lib_rows)
        self.lib_hint.configure(text="drag onto a game track to replace it")

    def _paint_seg(self):
        for mode, lbl in self.seg.items():
            on = mode == self.lib_mode
            lbl.configure(bg=S.ACCENT if on else S.ROW, fg="#ffffff" if on else S.DIM)

    # ---- rows, selection, drag and drop ---------------------------------------------
    def _make_row(self, parent, payload, title, right_text, right_color, drop_rel=None):
        row = tk.Frame(parent, bg=S.ROW, cursor="hand2")
        row.pack(fill="x", padx=self.px(6), pady=self.px(1))
        row.payload, row.hover, row.drop_hot = payload, False, False
        if drop_rel:
            row.drop_rel = drop_rel
        play = tk.Canvas(row, width=self.px(22), height=self.px(22), bg=S.ROW, highlightthickness=0)
        play.create_polygon([self.px(p) for p in (7, 5, 7, 17, 17, 11)], fill=LIGHT, outline="")
        play.pack(side="left", padx=(self.px(4), 0))
        play.bind("<ButtonPress-1>", lambda _e, p=payload: self._play_row(p), add="+")
        name = tk.Label(row, text=title, bg=S.ROW, fg="#ffffff", font=self.f(17), anchor="w", pady=self.px(2))
        name.pack(side="left", fill="x", expand=True, padx=(self.px(4), 0))
        tk.Label(row, text=right_text, bg=S.ROW, fg=right_color, font=self.f(13)).pack(side="right", padx=self.px(8))
        self.rows[payload] = row
        for w in [row] + row.winfo_children():
            if w is not play:
                w.bind("<ButtonPress-1>", lambda e, r=row: self._press(e, r))
                w.bind("<Double-Button-1>", lambda _e, p=payload: self._play_row(p))
            w.bind("<B1-Motion>", self._motion)
            w.bind("<ButtonRelease-1>", self._release)
            w.bind("<Enter>", lambda _e, r=row: self._hover(r, True))
            w.bind("<Leave>", lambda _e, r=row: self.after(15, self._check_leave, r))
            w.bind("<Button-3>", lambda e, r=row: self._context(e, r))
        self._paint(row)
        return row

    def _paint(self, row):
        try:
            if row.drop_hot:
                bg = DROP
            elif row.payload == self.sel:
                bg = S.ACCENT
            elif row.hover:
                bg = S.ROW_HOVER
            else:
                bg = S.ROW
            row.configure(bg=bg)
            for child in row.winfo_children():
                child.configure(bg=bg)
        except tk.TclError:
            pass

    def _hover(self, row, state):
        row.hover = state
        self._paint(row)

    def _check_leave(self, row):
        try:
            w = self.winfo_containing(*self.winfo_pointerxy())
        except (tk.TclError, KeyError):
            w = None
        while w is not None:
            if w is row:
                return
            w = getattr(w, "master", None)
        self._hover(row, False)

    def _select(self, payload):
        old = self.rows.get(self.sel)
        self.sel = payload
        if old is not None:
            self._paint(old)
        if payload in self.rows:
            self._paint(self.rows[payload])
        self._update_info()

    def _press(self, event, row):
        self._drag = {"row": row, "payload": row.payload, "x": event.x_root, "y": event.y_root,
                      "active": False, "ghost": None, "target": None}
        self._select(row.payload)

    def _motion(self, event):
        drag = self._drag
        if not drag:
            return
        if not drag["active"]:
            if abs(event.x_root - drag["x"]) + abs(event.y_root - drag["y"]) < 8:
                return
            drag["active"] = True
            ghost = tk.Toplevel(self)
            ghost.overrideredirect(True)
            try:
                ghost.attributes("-topmost", True)
                ghost.attributes("-alpha", 0.88)
            except tk.TclError:
                pass
            label = drag["row"].winfo_children()[1].cget("text")
            tk.Label(ghost, text="  " + label + "  ", bg=S.ACCENT, fg="#ffffff", font=self.f(18), padx=6, pady=3,
                     highlightthickness=1, highlightbackground="#ffffff").pack()
            drag["ghost"] = ghost
        drag["ghost"].geometry(f"+{event.x_root + 14}+{event.y_root + 10}")
        target = self._row_at(event.x_root, event.y_root)
        if target is not drag["target"]:
            if drag["target"] is not None:
                drag["target"].drop_hot = False
                self._paint(drag["target"])
            drag["target"] = target
            if target is not None and target.payload != drag["payload"]:
                target.drop_hot = True
                self._paint(target)
        self._autoscroll(event.x_root, event.y_root)

    def _row_at(self, x, y):
        try:
            w = self.winfo_containing(x, y)
        except (tk.TclError, KeyError):
            return None
        while w is not None:
            if hasattr(w, "drop_rel"):
                return w
            w = getattr(w, "master", None)
        return None

    def _autoscroll(self, x, y):
        lst = self.slot_list
        canvas = lst.canvas
        left, top = canvas.winfo_rootx(), canvas.winfo_rooty()
        if left <= x <= left + canvas.winfo_width():
            if top - 10 <= y < top + 28:
                canvas.yview_scroll(-1, "units")
            elif top + canvas.winfo_height() - 28 < y <= top + canvas.winfo_height() + 10:
                canvas.yview_scroll(1, "units")

    def _release(self, _event):
        drag, self._drag = self._drag, None
        if not drag or not drag["active"]:
            return
        if drag["ghost"] is not None:
            drag["ghost"].destroy()
        target = drag["target"]
        if target is not None:
            target.drop_hot = False
            self._paint(target)
            if target.payload != drag["payload"]:
                self._perform_drop(drag["payload"], target.drop_rel)

    def _context(self, event, row):
        self._select(row.payload)
        kind, ident = row.payload
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Play", command=lambda: self._play_row(row.payload))
        if kind == "slot":
            menu.add_command(label="Restore original", command=self._restore_selected)
            move = tk.Menu(menu, tearoff=0)
            for key, title, _b in C.CATEGORIES:
                move.add_command(label=title, command=lambda k=key, r=ident: self._move_category(r, k))
            menu.add_cascade(label="Move to", menu=move)
        elif kind == "user":
            menu.add_command(label="Remove from my tracks...", command=self._remove_user_track)
        menu.tk_popup(event.x_root, event.y_root)

    def _move_category(self, rel, key):
        self.lib.set_category(rel, key)
        self._reload_lists()
        self.slot_list.refill(self._build_slot_rows)

    # ---- changing game files ------------------------------------------------------
    def _perform_drop(self, payload, target_rel):
        kind, ident = payload
        target = self.slot_by_rel[target_rel]
        if kind == "slot":
            other = self.slot_by_rel[ident]
            if not (other.exists and target.exists):
                self._say("Can't swap with a track that's missing from the game folder - restore it first.", True)
                return
            self._run_changes([(other.game_path, target.game_path), (target.game_path, other.game_path)],
                              f"Swapped {other.name} and {target.name}", [other, target])
            return
        src = self.lib.user_path(ident) if kind == "user" else self.slot_by_rel[ident].master_path
        label = ident if kind == "user" else self.slot_by_rel[ident].name
        self._run_changes([(target.game_path, src)], f"{target.name} now plays {label}", [target])

    def _run_changes(self, changes, label, affected):
        if self.busy:
            return
        try:
            for slot in affected:
                self.lib.ensure_master(slot)
            record = self.lib.apply_changes(changes, label)
        except PermissionError:
            messagebox.showerror("Jukebox", "Windows wouldn't let me write to the game folder.\n\n"
                                            "Close Synthetik if it's running, or run this program as administrator "
                                            "(right-click -> Run as administrator).")
            return
        except OSError as exc:
            messagebox.showerror("Jukebox", f"Couldn't write the file:\n{exc}")
            return
        self.history.append(record)
        for old in self.history[:-10]:
            self.lib.discard(old)
        self.history = self.history[-10:]
        self._loaded_path = None
        self._reanalyze(label + ".")

    def _undo(self):
        if not self.history or self.busy:
            return
        record = self.history.pop()
        try:
            self.lib.undo(record)
        except OSError as exc:
            messagebox.showerror("Jukebox", f"Couldn't undo:\n{exc}")
            return
        self._loaded_path = None
        self._reanalyze(f"Undid: {record['label']}")

    def _update_undo_button(self):
        if hasattr(self, "btn_undo"):
            try:
                self.btn_undo.configure(state="normal" if self.history else "disabled")
            except tk.TclError:
                pass

    def _restore_selected(self):
        if not self.sel or self.sel[0] != "slot":
            return
        slot = self.slot_by_rel[self.sel[1]]
        if not os.path.exists(slot.master_path):
            self._say("No Master copy of that track exists.", True)
            return
        self._run_changes([(slot.game_path, slot.master_path)], f"Restored {slot.name}", [slot])

    def _restore_all(self):
        todo = [s for s in self.slots if os.path.exists(s.master_path) and self.holders.get(s.rel) != ("master", s.rel)]
        if not todo:
            self._say("Everything already matches the originals.")
            return
        if not messagebox.askyesno("Restore all", f"Put the original Master files back into {len(todo)} game track slot(s)?"):
            return
        self._run_changes([(s.game_path, s.master_path) for s in todo], f"Restored {len(todo)} original(s)", [])

    def _remove_user_track(self):
        if not self.sel or self.sel[0] != "user":
            return
        name = self.sel[1]
        if not messagebox.askyesno("Remove track", f"Delete '{name}' from your tracks?\n\n"
                                                    "Game slots currently using it keep playing it."):
            return
        self.player and self.player.stop()
        self.lib.delete_user_track(name)
        self.sel, self._loaded_path = None, None
        self._reload_lists()
        self._fill_all()
        self._say(f"Removed {name}.")

    # ---- adding tracks ------------------------------------------------------------
    def _add_tracks(self):
        if self.busy:
            return
        exts = " ".join("*" + e for e in C.AUDIO_EXTS)
        files = filedialog.askopenfilenames(title="Add tracks", filetypes=(("Audio files", exts), ("All files", "*.*")))
        if not files:
            return
        self.busy = True
        self._say(f"Converting 1/{len(files)}...")

        def job(report):
            added, errors = [], []
            for i, path in enumerate(files, 1):
                report(i, len(files), os.path.basename(path))
                try:
                    added.append(self.lib.import_track(path))
                except Exception as exc:
                    errors.append((os.path.basename(path), str(exc)))
            return added, errors

        def progress(i, n, name):
            self._say(f"Converting {i}/{n}: {_elide(name, 50)}")

        def done(result, err):
            self.busy = False
            if err:
                messagebox.showerror("Jukebox", str(err))
                return
            added, errors = result
            self.lib_mode = "user"
            self._paint_seg()
            self._reload_lists()
            if added:
                self.sel = ("user", added[0])
            self._fill_all()
            self._say(f"Added {len(added)} track(s). Drag one onto a game track to use it." if added else "Nothing was added.")
            if errors:
                messagebox.showerror("Jukebox", "Couldn't convert:\n\n" + "\n\n".join(f"{n}\n{e}" for n, e in errors[:4]))
        self.worker.run(job, done, progress)

    # ---- changing folders ------------------------------------------------------------
    def _change_game_dir(self):
        folder = filedialog.askdirectory(title="Select your Synthetik game folder", initialdir=self.game_dir or "C:/")
        if not folder:
            return
        self.game_dir = os.path.normpath(folder)
        C.update_prefs(game_dir=self.game_dir, library_dir=self.lib.base)
        self._build_main()
        self._refresh()

    def _change_library(self):
        folder = filedialog.askdirectory(title="Choose where your Jukebox library should live", initialdir=self.lib.base)
        if not folder or os.path.normpath(folder) == os.path.normpath(self.lib.base):
            return
        self.setup_lib_dir = os.path.normpath(folder)
        C.update_prefs(game_dir=self.game_dir, library_dir=self.setup_lib_dir)
        self.player and self.player.stop()
        self.sel, self._loaded_path, self.history = None, None, []
        self._build_setup()
        self._setup_go()

    # ---- art ---------------------------------------------------------------------------
    def _describe(self):
        """What the info panel should show for the selection."""
        if not self.sel:
            return None
        kind, ident = self.sel
        if kind == "user":
            path = self.lib.user_path(ident)
            return dict(title=ident, sub=f"User_tracks/{ident}.ogg", path=path, art_key=f"user:{ident}",
                        status="YOUR TRACK", detail="Not in the game yet - drag it onto a game track.",
                        main="Remove", can_art=True)
        slot = self.slot_by_rel.get(ident)
        if slot is None:
            return None
        if kind == "master":
            return dict(title=slot.name, sub=f"Master/{slot.rel}", path=slot.master_path, art_key=f"master:{slot.rel}",
                        status="GAME ORIGINAL", detail=C.CATEGORY_TITLES[slot.category], main=None, can_art=True)
        holder = self.holders.get(slot.rel)
        art_key = f"{holder[0]}:{holder[1]}" if holder else f"slot:{slot.rel}"
        text, _c = self._holder_text(slot)
        return dict(title=slot.name, sub=slot.rel, path=slot.game_path if slot.exists else None, art_key=art_key,
                    status=("PLAYING IN GAME: " + text.title()) if slot.exists else "MISSING FROM GAME FOLDER",
                    detail=C.CATEGORY_TITLES[slot.category], main="Restore original", can_art=True)

    def _art_image(self, path, size):
        try:
            key = (path, os.path.getmtime(path) if path else 0, size)
        except OSError:
            key = (None, 0, size)
        if key not in self._art_cache:
            img = None
            if path:
                try:
                    img = ImageOps.fit(Image.open(path).convert("RGB"), (size, size), Image.LANCZOS)
                except Exception:
                    img = None
            if img is None:
                img = Image.new("RGB", (size, size), T.CLASS_ROW)
                draw = ImageDraw.Draw(img)
                draw.rectangle([0, 0, size - 1, size - 1], outline=T.BORDER, width=2)
                try:
                    fnt = ImageFont.truetype(T.FONT_FILE, max(10, size // 7))
                except OSError:
                    fnt = ImageFont.load_default()
                draw.text((size / 2, size / 2), "NO ART", font=fnt, fill=T.DIM_TEXT, anchor="mm")
            self._art_cache[key] = ImageTk.PhotoImage(img)
        return self._art_cache[key]

    def _set_art(self):
        info = self._describe()
        if not info:
            return
        path = filedialog.askopenfilename(title="Choose cover art", filetypes=(("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All files", "*.*")))
        if path:
            try:
                self.lib.set_art(info["art_key"], path)
            except Exception as exc:
                messagebox.showerror("Jukebox", f"Couldn't use that image:\n{exc}")
                return
            self._update_info()

    def _clear_art(self):
        info = self._describe()
        if info:
            self.lib.clear_art(info["art_key"])
            self._update_info()

    def _set_default_cover(self):
        path = filedialog.askopenfilename(title="Choose the default Synthetik cover", filetypes=(("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All files", "*.*")))
        if path:
            try:
                self.lib.set_default_cover(path)
            except Exception as exc:
                messagebox.showerror("Jukebox", f"Couldn't use that image:\n{exc}")
                return
            self._art_cache.clear()
            self._update_info()
            self._say("Default Synthetik cover replaced.")

    def _act_main(self):
        if self.sel and self.sel[0] == "slot":
            self._restore_selected()
        elif self.sel and self.sel[0] == "user":
            self._remove_user_track()

    # ---- info panel + player ---------------------------------------------------------------
    def _update_info(self, force=False):
        if self.mode != "main" or not hasattr(self, "info_title"):
            return
        info = self._describe()
        size = self.px(ART_BASE)
        if not info:
            self.mini_lbl.configure(text="")
            self.info_title.configure(text="Select a track")
            self.info_sub.configure(text="")
            self.info_status.configure(text="")
            self.info_meta.configure(text="Click a track to see its art and listen to it.\n"
                                          "Drag tracks to swap them or replace them." +
                                          ("" if not self.player or self.player.ok else "\n\n" + self._audio_note()))
            self.art_img = self._art_image(None, size)
            self.art_lbl.configure(image=self.art_img)
            self.act_main.configure(state="disabled", text="RESTORE ORIGINAL")
            if self.player:
                self.player.stop()
            self._loaded_path = None
            return
        self.mini_lbl.configure(text=_elide(info["title"], 24))
        self.info_title.configure(text=_elide(info["title"], 22))
        self.info_sub.configure(text=info["sub"])
        self.info_status.configure(text=info["status"], fg=RED if "MISSING" in info["status"] else LIGHT)
        meta = C.ogg_info(info["path"]) if info["path"] and os.path.exists(info["path"]) else None
        parts = [info["detail"]]
        if meta:
            parts = [f"{C.fmt_time(meta['duration'])}  -  {meta['rate'] / 1000:g} kHz  -  "
                     f"{'stereo' if meta['channels'] == 2 else 'mono' if meta['channels'] == 1 else str(meta['channels']) + ' ch'}  -  "
                     f"{meta['size'] / 1048576:.1f} MB"]
        if self.player and not self.player.ok:
            parts.append(self._audio_note())
        self.info_meta.configure(text="\n".join(parts))
        self.art_img = self._art_image(self.lib.art_path(info["art_key"]), size)
        self.art_lbl.configure(image=self.art_img)
        self.act_clear.configure(state="normal" if self.lib.has_art_override(info["art_key"]) else "disabled")
        if info["main"]:
            self.act_main.configure(text=info["main"].upper(), state="normal")
        else:
            self.act_main.configure(text="RESTORE ORIGINAL", state="disabled")
        path = info["path"] if info["path"] and os.path.exists(info["path"]) else None
        if self.player and self.player.ok and (force or path != self._loaded_path or self._loaded_key != self.sel):
            self.player.stop()
            if path:
                self.player.load(path, meta["duration"] if meta else 0.0)
            self._loaded_path = path
        self._loaded_key = self.sel
        self._sync_transport()

    _loaded_key = None

    def _audio_note(self):
        if self.busy_audio:
            return "Setting up audio playback..."
        return "Audio unavailable: " + _elide(self.player.error or "unknown error", 120) + "  (press PLAY to retry)"

    def _play_row(self, payload):
        self._select(payload)
        self._start_play()

    def _start_play(self):
        if not self.player or not self.player.ok:
            self._audio_problem()
            return
        if not self._loaded_path:
            return
        self.player.play(0.0)
        self._sync_transport()

    def _toggle_play(self):
        if not self.player or not self.player.ok:
            self._audio_problem()
            return
        if self.player.current:
            self.player.toggle()
            self._sync_transport()

    def _stop(self):
        if self.player:
            self.player.stop()
            self._sync_transport()

    def _on_seek(self, value, final):
        if not self.player or not self.player.ok or not self.player.current or self.player.duration <= 0:
            return
        self.time_lbl.configure(text=f"{C.fmt_time(value * self.player.duration)} / {C.fmt_time(self.player.duration)}")
        if final:
            if self.player.state == "stopped":
                self.player.play(value * self.player.duration)
            else:
                self.player.seek(value * self.player.duration)
            self._sync_transport()

    def _sync_transport(self):
        try:
            player = self.player
            label = "PAUSE" if player and player.state == "playing" else "PLAY"
            self.play_btn.configure(text=label)
            self.mini_btn.configure(text=label)
            duration = player.duration if player else 0.0
            pos = player.position() if player else 0.0
            self.time_lbl.configure(text=f"{C.fmt_time(pos)} / {C.fmt_time(duration)}")
            self.seek.set(pos / duration if duration > 0 else 0.0)
        except (tk.TclError, AttributeError):
            pass

    def _tick(self):
        try:
            if self.player and self.mode == "main":
                self.player.poll()
                if self.player.state != "stopped" and not self.seek.dragging:
                    self._sync_transport()
                elif self.player.state == "stopped" and self.play_btn.cget("text") != "PLAY":
                    self._sync_transport()
        except (tk.TclError, AttributeError):
            pass
        self.after(200, self._tick)
