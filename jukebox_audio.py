"""jukebox_audio.py - listening to tracks inside the Jukebox tab (pygame.mixer.music).

No manual install needed:
  * a frozen (PyInstaller) build simply bundles pygame;
  * when running from source and pygame isn't importable by *this* Python, the app downloads pygame-ce
    into its own private folder (<LOCALAPPDATA>/SynthetikLoadoutEditor/libs) the first time you open the
    Jukebox, using the same interpreter that is running the editor (so it can't end up in the wrong Python).
If audio still can't start, `Player.error` holds the real reason and the tab shows it.

Playback always runs from a private temp copy of the file, so previewing a track never keeps the game's
own .ogg (or your Master / User_tracks files) locked while you're replacing it.
"""
import atexit
import os
import shutil
import subprocess
import sys
import tempfile

import jukebox_core as C

PACKAGE = "pygame-ce"


def libs_dir():
    path = os.path.join(C._app_data_dir(), "libs")
    return path


def _add_libs_to_path():
    """Make the private libs folder importable.  Never done in a frozen (PyInstaller) build: the exe
    bundles its own pygame, and a leftover libs folder (e.g. pygame-ce downloaded earlier by a source
    run, possibly for a different Python version) would shadow it and break `import pygame.base`."""
    if getattr(sys, "frozen", False):
        return
    path = libs_dir()
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


class Player:
    def __init__(self):
        self.ok = False
        self.error = ""
        self.can_install = False   # True when the failure is "pygame missing" and we may download it
        self.pg = None
        self.tmpdir = None
        self.counter = 0
        self.current = None       # temp file currently loaded
        self.duration = 0.0
        self.offset = 0.0         # where the last play() started from (seconds)
        self.state = "stopped"    # stopped / playing / paused
        self.volume = 0.8
        atexit.register(self.close)

    # ---- start-up -----------------------------------------------------------
    def init(self):
        """Import pygame and open the audio device.  Returns True when ready (otherwise see .error)."""
        if self.ok:
            return True
        self.error, self.can_install = "", False
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            import pygame                      # the bundled / normally installed pygame always wins
        except Exception:
            _add_libs_to_path()                # source runs only: fall back to the downloaded copy
            for name in [m for m in sys.modules if m == "pygame" or m.startswith("pygame.")]:
                sys.modules.pop(name, None)    # drop any half-imported pygame before retrying
            try:
                import pygame
            except Exception as exc:
                self.error = f"pygame couldn't be loaded ({exc})"
                self.can_install = not getattr(sys, "frozen", False)
                return False
        last = ""
        drivers = [None] + (["directsound", "winmm", "wasapi"] if sys.platform == "win32" else [])
        for driver in drivers:
            try:
                if driver:
                    os.environ["SDL_AUDIODRIVER"] = driver
                try:
                    pygame.mixer.quit()
                except Exception:
                    pass
                pygame.mixer.init()
                break
            except Exception as exc:
                last = str(exc)
        else:
            self.error = f"No audio device could be opened ({last})"
            return False
        self.pg = pygame
        self.tmpdir = tempfile.mkdtemp(prefix="synth_jukebox_")
        pygame.mixer.music.set_volume(self.volume)
        self.ok = True
        return True

    def install_backend(self):
        """Download pygame-ce into the private libs folder.  Blocking - run it in a thread.
        Returns '' on success or an error message."""
        target = libs_dir()
        os.makedirs(target, exist_ok=True)
        flags = 0x08000000 if os.name == "nt" else 0
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--target", target, "--disable-pip-version-check",
               "--no-warn-script-location", "--only-binary", ":all:", PACKAGE]
        result = subprocess.run(cmd, capture_output=True, creationflags=flags)
        if result.returncode != 0 and b"No module named pip" in result.stderr:
            subprocess.run([sys.executable, "-m", "ensurepip", "--default-pip"], capture_output=True, creationflags=flags)
            result = subprocess.run(cmd, capture_output=True, creationflags=flags)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout).decode("utf-8", "ignore").strip().splitlines()[-3:]
            return "Couldn't download the audio component: " + " ".join(tail)
        return ""

    # ---- loading / transport ---------------------------------------------
    def load(self, src, duration=0.0):
        """Get `src` ready (stopped at 0:00).  Returns False if it can't be loaded."""
        if not self.ok:
            return False
        self.stop()
        self._release()
        try:
            self.counter += 1
            tmp = os.path.join(self.tmpdir, f"preview_{self.counter}.ogg")
            shutil.copyfile(src, tmp)
            self.pg.mixer.music.load(tmp)
        except Exception as exc:
            self.error = str(exc)
            self.current = None
            return False
        self.current, self.duration, self.offset = tmp, duration, 0.0
        return True

    def _release(self):
        if self.current:
            try:
                self.pg.mixer.music.unload()
            except Exception:
                pass
            try:
                os.remove(self.current)
            except OSError:
                pass
            self.current = None

    def play(self, start=0.0):
        if not (self.ok and self.current):
            return
        try:
            self.pg.mixer.music.play(start=max(0.0, start))
            self.pg.mixer.music.set_volume(self.volume)
            self.offset, self.state = max(0.0, start), "playing"
        except Exception as exc:
            self.error = str(exc)

    def toggle(self):
        """Play from the start / pause / resume."""
        if not (self.ok and self.current):
            return
        if self.state == "playing":
            self.pg.mixer.music.pause()
            self.state = "paused"
        elif self.state == "paused":
            self.pg.mixer.music.unpause()
            self.state = "playing"
        else:
            self.play(0.0)

    def stop(self):
        if self.ok and self.state != "stopped":
            try:
                self.pg.mixer.music.stop()
            except Exception:
                pass
        self.state, self.offset = "stopped", 0.0

    def seek(self, seconds):
        if not (self.ok and self.current):
            return
        was_paused = self.state == "paused"
        self.play(seconds)
        if was_paused:
            self.pg.mixer.music.pause()
            self.state = "paused"

    def set_volume(self, value):
        self.volume = min(1.0, max(0.0, value))
        if self.ok:
            self.pg.mixer.music.set_volume(self.volume)

    # ---- state -------------------------------------------------------------
    def position(self):
        if not self.ok or self.state == "stopped":
            return self.offset if self.state == "stopped" else 0.0
        return self.offset + max(0, self.pg.mixer.music.get_pos()) / 1000.0

    def poll(self):
        """Call regularly; flips to 'stopped' when the track ends.  True if the state changed."""
        if self.ok and self.state == "playing" and not self.pg.mixer.music.get_busy():
            self.state, self.offset = "stopped", 0.0
            return True
        return False

    def close(self):
        if not self.ok:
            return
        try:
            self.pg.mixer.music.stop()
            self._release()
            self.pg.mixer.quit()
        except Exception:
            pass
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        self.ok = False
