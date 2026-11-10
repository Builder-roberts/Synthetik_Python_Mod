"""ui_widgets.py - the small Tk layer under the drawn Editor UI.

A `Panel` renders itself to a Pillow image and publishes rectangular hit
regions; a `PanelItem` shows that image on a canvas and turns mouse movement /
clicks into hover state and `Panel.on_click(key)` calls.  Everything visual
lives in Pillow; Tk is only used to put the pixels on screen and receive input.
"""
import tkinter as tk

from PIL import Image, ImageTk

import ui_style as S


class Panel:
    """Base class: subclasses implement render(hover) and on_click(key)."""

    def __init__(self, width, height):
        self.w, self.h = width, height
        self.hits = []  # [((x0, y0, x1, y1), key), ...] rebuilt by every render()

    def render(self, hover):  # -> PIL RGB image of size (w, h)
        raise NotImplementedError

    def on_click(self, key):
        pass

    def tooltip(self, key):  # -> (title, text) to show while hovering `key`, or None
        return None

    def hit_test(self, x, y):
        for (x0, y0, x1, y1), key in reversed(self.hits):  # later regions sit on top
            if x0 <= x < x1 and y0 <= y < y1:
                return key
        return None


class Tooltip:
    """A small dark hover card (title + wrapped text) that appears after the pointer rests on one spot."""
    DELAY = 350  # ms

    def __init__(self, widget):
        self.widget, self.win, self.job, self.key = widget, None, None, None
        widget.bind("<Destroy>", lambda _e: self.hide(), add="+")

    def track(self, key, info, x_root, y_root):
        """Call on every pointer move with the hovered key and its (title, text) (or None)."""
        if key == self.key and (self.win is not None or self.job is not None):
            return  # same target: leave the card where it is
        self.hide()
        if info:
            self.key = key
            self.job = self.widget.after(self.DELAY, lambda: self._show(info, x_root, y_root))

    def _show(self, info, x_root, y_root):
        self.job = None
        title, text = info
        win = self.win = tk.Toplevel(self.widget)
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        box = tk.Frame(win, bg=S.ACCENT, padx=1, pady=1)
        box.pack()
        inner = tk.Frame(box, bg=S.hexc((13, 17, 48)), padx=12, pady=8)
        inner.pack()
        tk.Label(inner, text=title.upper(), font=S.font(22), fg="#ffffff", bg=S.hexc((13, 17, 48)), anchor="w",
                 justify="left").pack(anchor="w")
        tk.Label(inner, text=text, font=S.font(16), fg=S.TEXT, bg=S.hexc((13, 17, 48)), wraplength=320,
                 justify="left").pack(anchor="w", pady=(2, 0))
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x = min(x_root + 16, win.winfo_screenwidth() - w - 4)
        y = y_root + 20
        if y + h > win.winfo_screenheight() - 4:
            y = y_root - h - 10  # flip above the pointer near the bottom edge
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

    def hide(self):
        self.key = None
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None


class PanelItem:
    """Shows a Panel as one image item on `canvas` at (x, y)."""

    def __init__(self, canvas, panel, x=0, y=0):
        self.canvas, self.panel = canvas, panel
        self.hover = None
        self.photo = None
        self.scale = 1.0  # < 1 when the window is smaller than the design size
        self.tip = Tooltip(canvas)
        self.item = canvas.create_image(x, y, anchor="nw")
        canvas.tag_bind(self.item, "<Motion>", self._motion)
        canvas.tag_bind(self.item, "<Leave>", self._leave)
        canvas.tag_bind(self.item, "<Button-1>", self._click)
        self.redraw()

    def _local(self, event):
        x0, y0 = self.canvas.coords(self.item)
        return (event.x - x0) / self.scale, (event.y - y0) / self.scale  # back to design pixels

    def _motion(self, event):
        key = self.panel.hit_test(*self._local(event))
        self.canvas.configure(cursor="hand2" if key is not None else "")
        if key != self.hover:
            self.hover = key
            self.redraw()
        self.tip.track(key, self.panel.tooltip(key) if key is not None else None, event.x_root, event.y_root)

    def _leave(self, _event):
        self.tip.hide()
        self.canvas.configure(cursor="")
        if self.hover is not None:
            self.hover = None
            self.redraw()

    def _click(self, event):
        self.tip.hide()
        key = self.panel.hit_test(*self._local(event))
        if key is not None:
            self.panel.on_click(key)

    def move_to(self, x, y):
        self.canvas.coords(self.item, x, y)

    def set_scale(self, scale):
        if abs(scale - self.scale) > 1e-6:
            self.scale = scale
            self.redraw()

    def redraw(self):
        img = self.panel.render(self.hover)
        if self.scale != 1.0:
            img = img.resize((max(1, round(img.width * self.scale)), max(1, round(img.height * self.scale))), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(img)  # keep a reference!
        self.canvas.itemconfigure(self.item, image=self.photo)


def style_entry(entry):
    """Dark, flat styling so Tk Entry widgets blend into the drawn panels."""
    entry.configure(
        bg="#15112d", fg="#f2f0e6", insertbackground="#f2f0e6", relief="flat", bd=0,
        highlightthickness=1, highlightbackground="#3a3170", highlightcolor="#8466f4",
        disabledbackground="#15112d", font=("TkDefaultFont", 11, "bold"),
    )
    return entry
