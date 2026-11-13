"""jukebox_core.py - the logic under the Jukebox tab (no Tk in here, so it can be tested headlessly).

Folder layout the player chooses (any folder, anywhere):

    <library>/Master/        untouched copies of every .ogg found in the game folder (same sub-folders)
    <library>/User_tracks/   the player's own tracks, converted to .ogg
    <library>/Art/           cover images (default Synthetik cover + per-track overrides)
    <library>/jukebox_library.json   small bookkeeping file (art links, category overrides, hashes)

The game folder itself is only ever written by `Library.apply_changes`, which copies a file over a
game track *under the game track's exact file name* (atomic: temp file + os.replace) and keeps a
backup of whatever it overwrote so the last few operations can be undone.
"""
import base64
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

from PIL import Image

DEFAULT_GAME_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Synthetik"
AUDIO_EXTS = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".wma", ".opus", ".ogg", ".oga", ".aiff", ".aif", ".mp4", ".webm")

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _BASE = sys._MEIPASS
    _EXE_DIR = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _EXE_DIR = _BASE
BUNDLED_COVER = os.path.join(_BASE, "assets", "ui", "jukebox", "cover.jpg")


# ---------------------------------------------------------------------------
# Where things are remembered / found
# ---------------------------------------------------------------------------
def _app_data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, "SynthetikLoadoutEditor")
    os.makedirs(path, exist_ok=True)
    return path


def load_prefs():
    try:
        with open(os.path.join(_app_data_dir(), "jukebox_prefs.json"), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_prefs(prefs):
    try:
        with open(os.path.join(_app_data_dir(), "jukebox_prefs.json"), "w", encoding="utf-8") as fh:
            json.dump(prefs, fh, indent=2)
    except OSError:
        pass


def update_prefs(**changes):
    prefs = load_prefs()
    prefs.update(changes)
    save_prefs(prefs)


def _steam_roots():
    roots = [os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Steam")]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            roots.append(winreg.QueryValueEx(key, "SteamPath")[0])
    except Exception:
        pass
    libraries = []
    for root in roots:
        libraries.append(root)
        try:
            with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), "r", encoding="utf-8", errors="ignore") as fh:
                for match in re.finditer(r'"path"\s+"([^"]+)"', fh.read()):
                    libraries.append(match.group(1).replace("\\\\", "\\"))
        except OSError:
            pass
    seen, result = set(), []
    for lib in libraries:
        key = os.path.normcase(os.path.normpath(lib))
        if key not in seen:
            seen.add(key)
            result.append(lib)
    return result


def find_game_dir():
    """The Synthetik install folder if we can find it (default path first, then every Steam library)."""
    if os.path.isdir(DEFAULT_GAME_DIR):
        return DEFAULT_GAME_DIR
    for lib in _steam_roots():
        common = os.path.join(lib, "steamapps", "common")
        try:
            names = os.listdir(common)
        except OSError:
            continue
        exact = [n for n in names if n.lower() == "synthetik"]
        fuzzy = [n for n in names if n.lower().startswith("synthetik")]
        for name in exact + fuzzy:
            return os.path.join(common, name)
    return None


# ---------------------------------------------------------------------------
# Naming and categories ("where it plays in the game")
# ---------------------------------------------------------------------------
# (key, title, blurb).  Order = order on screen.
CATEGORIES = [
    ("jukebox", "Jukebox songs", "The in-game jukebox"),
    ("finalboss", "Final boss songs", "The final boss fight"),
    ("combat", "During combat", "Played while fighting"),
    ("boss", "Boss fights", "Sorted by file name"),
    ("menu", "Menus & hub", "Sorted by file name"),
    ("ambient", "Ambient", "Sorted by file name"),
    ("other", "Other music", "Not sorted yet - right-click a track to move it"),
    ("sfx", "Other sounds", "Not music - sound effects and the like"),
]
CATEGORY_TITLES = {key: title for key, title, _ in CATEGORIES}

# Names that are known for sure.  Everything else is sorted by guessing from the file name
# (and the player can move any track with right-click -> Move to).
KNOWN = {
    "music_psy_eternallord": ("jukebox", "Eternal Lord"),
    "music_psy_hypernoma": ("jukebox", "Hypernoma"),
    "music_psy_supremers": ("jukebox", "Supremers"),
    "music_cyberpunk_combat1": ("finalboss", "Cyberpunk Combat 1"),
    "music_cyberpunk_combat2": ("finalboss", "Cyberpunk Combat 2"),
}
for _n in range(1, 6):
    KNOWN[f"music_electro_hendrik_combat_{_n}"] = ("combat", f"Hendrik Combat {_n}")


def stem_of(rel):
    return os.path.splitext(rel.replace("\\", "/").rsplit("/", 1)[-1])[0]


def guess_category(rel):
    stem = stem_of(rel).lower()
    if stem in KNOWN:
        return KNOWN[stem][0]
    if stem.startswith("music_psy"):
        return "jukebox"
    if "boss" in stem and "final" in stem:
        return "finalboss"
    if "combat" in stem:
        return "boss" if "boss" in stem else "combat"
    if "boss" in stem:
        return "boss"
    if not stem.startswith("music"):
        return "sfx"
    if any(w in stem for w in ("menu", "title", "hub", "lobby", "shop", "base", "intro", "credits", "loadout", "select")):
        return "menu"
    if any(w in stem for w in ("ambient", "calm", "explor", "idle", "peace")):
        return "ambient"
    return "other"


def display_name(rel):
    stem = stem_of(rel)
    if stem.lower() in KNOWN:
        return KNOWN[stem.lower()][1]
    words = [w for w in re.split(r"[_\s]+", stem) if w]
    if words and words[0].lower() == "music":
        words = words[1:]
    return " ".join(w.capitalize() if not w.isdigit() else w for w in words) or stem


def sanitize_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "track"


# ---------------------------------------------------------------------------
# Small file helpers
# ---------------------------------------------------------------------------
_HASH_CACHE = {}


def file_sha1(path):
    st = os.stat(path)
    key = (path, st.st_size, st.st_mtime_ns)
    cached = _HASH_CACHE.get(key)
    if cached:
        return cached
    sha = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    _HASH_CACHE[key] = sha.hexdigest()
    return _HASH_CACHE[key]


def ogg_info(path):
    """{'duration', 'rate', 'channels', 'size'} for an Ogg Vorbis file, read straight from the headers
    (no audio libraries needed).  None if the file isn't Ogg Vorbis."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            head = fh.read(8192)
            i = head.find(b"\x01vorbis")
            if i < 0:
                return None
            channels = head[i + 11]
            rate = struct.unpack("<I", head[i + 12:i + 16])[0]
            fh.seek(max(0, size - 65536))
            tail = fh.read()
        j = tail.rfind(b"OggS")
        duration = 0.0
        if j >= 0 and rate:
            granule = struct.unpack("<q", tail[j + 6:j + 14])[0]
            duration = max(0.0, granule / rate)
        return {"duration": duration, "rate": rate, "channels": channels, "size": size}
    except (OSError, struct.error, IndexError):
        return None


def fmt_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _atomic_copy(src, dst):
    tmp = dst + ".jbtmp"
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def _rel_to_path(base, rel):
    return os.path.join(base, *rel.split("/"))


def scan_ogg(folder):
    """Every .ogg under `folder`, as '/'-separated paths relative to it."""
    found = []
    for dirpath, _dirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(".ogg"):
                full = os.path.join(dirpath, name)
                found.append(os.path.relpath(full, folder).replace(os.sep, "/"))
    return sorted(found, key=str.lower)


# ---------------------------------------------------------------------------
# Converting other formats to .ogg
# ---------------------------------------------------------------------------
class ConversionError(Exception):
    pass


_FFMPEG = {}


def find_ffmpeg():
    if "path" in _FFMPEG:
        return _FFMPEG["path"]
    found = shutil.which("ffmpeg")
    if not found:
        exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        for folder in (_EXE_DIR, _BASE, os.path.join(_EXE_DIR, "tools"), os.path.join(_EXE_DIR, "ffmpeg"),
                       os.path.join(_EXE_DIR, "ffmpeg", "bin")):
            candidate = os.path.join(folder, exe)
            if os.path.isfile(candidate):
                found = candidate
                break
    if not found:
        try:
            import imageio_ffmpeg
            found = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            found = None
    _FFMPEG["path"] = found
    return found


def _run(cmd):
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    return subprocess.run(cmd, capture_output=True, creationflags=flags)


NO_CONVERTER_MSG = (
    "Converting this file to .ogg needs ffmpeg, and none was found.\n\n"
    "Easiest fix: run   pip install imageio-ffmpeg   (or put ffmpeg.exe next to this program), "
    "then try again.\n\n.ogg (Vorbis) files can be added without it."
)


def convert_to_ogg(src, dst):
    """Make `dst` an Ogg Vorbis file from `src` (mp3, wav, flac, m4a, ...)."""
    if src.lower().endswith((".ogg", ".oga")) and ogg_info(src):
        _atomic_copy(src, dst)  # already Vorbis: keep it bit-for-bit
        return
    tmp = dst + ".jbtmp"
    ffmpeg = find_ffmpeg()
    try:
        if ffmpeg:
            base = [ffmpeg, "-y", "-v", "error", "-i", src, "-vn", "-map_metadata", "-1"]
            result = _run(base + ["-c:a", "libvorbis", "-q:a", "6", "-f", "ogg", tmp])
            if result.returncode != 0:  # builds without libvorbis: ffmpeg's native (experimental) encoder
                result = _run(base + ["-c:a", "vorbis", "-strict", "-2", "-ac", "2", "-f", "ogg", tmp])
            if result.returncode != 0:
                raise ConversionError(result.stderr.decode("utf-8", "ignore").strip()[-400:] or "ffmpeg failed")
        else:
            try:
                import soundfile as sf  # libsndfile can write Vorbis (and read mp3 in recent versions)
                data, rate = sf.read(src)
                sf.write(tmp, data, rate, format="OGG", subtype="VORBIS")
            except ImportError:
                raise ConversionError(NO_CONVERTER_MSG)
            except Exception as exc:
                raise ConversionError(f"Could not convert: {exc}")
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def extract_art(src):
    """A PIL image for the cover embedded in `src` (or sitting next to it), else None."""
    data = None
    try:
        import mutagen
        audio = mutagen.File(src)
        if audio is not None:
            pics = getattr(audio, "pictures", None)
            if pics:
                data = pics[0].data
            tags = getattr(audio, "tags", None)
            if not data and tags is not None:
                if hasattr(tags, "getall"):
                    apic = tags.getall("APIC")
                    if apic:
                        data = apic[0].data
                if not data:
                    try:
                        covr = tags.get("covr")
                        if covr:
                            data = bytes(covr[0])
                    except Exception:
                        pass
                if not data:
                    try:
                        from mutagen.flac import Picture
                        block = tags.get("metadata_block_picture")
                        if block:
                            data = Picture(base64.b64decode(block[0])).data
                    except Exception:
                        pass
    except Exception:
        data = None
    if not data:
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            fd, out = tempfile.mkstemp(suffix=".jpg", prefix="jbart_")
            os.close(fd)
            try:
                if _run([ffmpeg, "-y", "-v", "error", "-i", src, "-an", "-frames:v", "1", out]).returncode == 0 \
                        and os.path.isfile(out):
                    with open(out, "rb") as fh:
                        data = fh.read()
            except Exception:
                pass
            finally:
                if os.path.exists(out):
                    try:
                        os.remove(out)
                    except OSError:
                        pass
    if data:
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            return img
        except Exception:
            pass
    folder, stem = os.path.split(src)
    stem = os.path.splitext(stem)[0].lower()
    try:
        names = {n.lower(): n for n in os.listdir(folder or ".")}
    except OSError:
        return None
    for base in (stem, "cover", "folder", "front", "album", "albumart"):
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            if base + ext in names:
                try:
                    img = Image.open(os.path.join(folder, names[base + ext]))
                    img.load()
                    return img
                except Exception:
                    pass
    return None


# ---------------------------------------------------------------------------
# The library
# ---------------------------------------------------------------------------
@dataclass
class Slot:
    rel: str            # 'music_psy_eternallord.ogg' (relative to the game folder, '/' separated)
    game_path: str
    master_path: str
    category: str
    name: str
    exists: bool        # is the file currently in the game folder?


class Library:
    def __init__(self, base):
        self.base = os.path.abspath(base)
        self.master_dir = os.path.join(self.base, "Master")
        self.user_dir = os.path.join(self.base, "User_tracks")
        self.art_dir = os.path.join(self.base, "Art")
        self.undo_dir = os.path.join(self.base, ".undo")
        self.meta_file = os.path.join(self.base, "jukebox_library.json")
        self.meta = {"category_overrides": {}, "art": {}}
        for folder in (self.master_dir, self.user_dir, self.art_dir):
            os.makedirs(folder, exist_ok=True)
        try:
            with open(self.meta_file, "r", encoding="utf-8") as fh:
                self.meta.update(json.load(fh))
        except (OSError, ValueError):
            pass
        shutil.rmtree(self.undo_dir, ignore_errors=True)  # undo history only lives for one session
        cover = os.path.join(self.art_dir, "cover.jpg")
        if not os.path.exists(cover) and os.path.exists(BUNDLED_COVER):
            try:
                shutil.copyfile(BUNDLED_COVER, cover)
            except OSError:
                pass

    def save(self):
        try:
            with open(self.meta_file, "w", encoding="utf-8") as fh:
                json.dump(self.meta, fh, indent=2)
        except OSError:
            pass

    # ---- master copy ----------------------------------------------------
    def build_master(self, game_dir, report=None):
        """Copy every game .ogg that isn't in Master yet.  Existing Master files are NEVER overwritten,
        so the Master copy stays the true original even if the game folder is later modified."""
        rels = scan_ogg(game_dir)
        copied = 0
        for i, rel in enumerate(rels, 1):
            dst = _rel_to_path(self.master_dir, rel)
            if not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(_rel_to_path(game_dir, rel), dst)
                copied += 1
            if report:
                report(i, len(rels), rel)
        return len(rels), copied

    # ---- tracks ---------------------------------------------------------
    def slots(self, game_dir):
        rels = set(scan_ogg(game_dir)) | set(scan_ogg(self.master_dir))
        overrides = self.meta.get("category_overrides", {})
        result = []
        for rel in sorted(rels, key=str.lower):
            game_path = _rel_to_path(game_dir, rel)
            result.append(Slot(rel, game_path, _rel_to_path(self.master_dir, rel),
                               overrides.get(rel) if overrides.get(rel) in CATEGORY_TITLES else guess_category(rel),
                               display_name(rel), os.path.exists(game_path)))
        return result

    def ensure_master(self, slot):
        """Make sure the slot's original is safely in Master before the game file gets touched."""
        if slot.exists and not os.path.exists(slot.master_path):
            os.makedirs(os.path.dirname(slot.master_path), exist_ok=True)
            shutil.copy2(slot.game_path, slot.master_path)

    def user_tracks(self):
        try:
            return sorted((os.path.splitext(n)[0] for n in os.listdir(self.user_dir) if n.lower().endswith(".ogg")),
                          key=str.lower)
        except OSError:
            return []

    def user_path(self, name):
        return os.path.join(self.user_dir, name + ".ogg")

    def set_category(self, rel, category):
        self.meta.setdefault("category_overrides", {})
        if category == guess_category(rel):
            self.meta["category_overrides"].pop(rel, None)
        else:
            self.meta["category_overrides"][rel] = category
        self.save()

    def analyze(self, game_dir):
        """{slot rel: holder} where holder is ('master', rel) / ('user', name) / None (= something unknown),
        found by comparing file hashes.  Run in a worker thread."""
        index = {}
        for rel in scan_ogg(self.master_dir):
            index.setdefault(file_sha1(_rel_to_path(self.master_dir, rel)), []).append(("master", rel))
        for name in self.user_tracks():
            index.setdefault(file_sha1(self.user_path(name)), []).append(("user", name))
        holders = {}
        for slot in self.slots(game_dir):
            if not slot.exists:
                holders[slot.rel] = None
                continue
            candidates = index.get(file_sha1(slot.game_path), [])
            own = ("master", slot.rel)
            holders[slot.rel] = own if own in candidates else (candidates[0] if candidates else None)
        return holders

    def import_track(self, src):
        """Convert `src` into User_tracks (+ pick up its cover art).  Returns the track's name."""
        base = sanitize_name(os.path.splitext(os.path.basename(src))[0])
        name, n = base, 2
        while os.path.exists(self.user_path(name)):
            name = f"{base} ({n})"
            n += 1
        convert_to_ogg(src, self.user_path(name))
        art = extract_art(src)
        if art is not None:
            self._save_art(f"user:{name}", art)
        return name

    def delete_user_track(self, name):
        for key in (f"user:{name}",):
            self.clear_art(key)
        try:
            os.remove(self.user_path(name))
        except OSError:
            pass

    # ---- art ------------------------------------------------------------
    def _save_art(self, key, image):
        fname = re.sub(r"[^A-Za-z0-9_.-]+", "_", key) + "_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:6] + ".jpg"
        img = image.convert("RGB")
        img.thumbnail((800, 800))
        img.save(os.path.join(self.art_dir, fname), "JPEG", quality=90)
        self.meta.setdefault("art", {})[key] = "Art/" + fname
        self.save()

    def set_art(self, key, image_path):
        img = Image.open(image_path)
        img.load()
        self._save_art(key, img)

    def set_default_cover(self, image_path):
        img = Image.open(image_path)
        img.load()
        img = img.convert("RGB")
        img.thumbnail((800, 800))
        img.save(os.path.join(self.art_dir, "cover.jpg"), "JPEG", quality=90)

    def clear_art(self, key):
        rel = self.meta.get("art", {}).pop(key, None)
        if rel:
            try:
                os.remove(os.path.join(self.base, *rel.split("/")))
            except OSError:
                pass
            self.save()

    def has_art_override(self, key):
        return key in self.meta.get("art", {})

    def art_path(self, key):
        """The image to show for `key` ('master:<rel>', 'user:<name>' or 'slot:<rel>'), or None.
        Original game tracks fall back to the default Synthetik cover."""
        rel = self.meta.get("art", {}).get(key)
        if rel:
            path = os.path.join(self.base, *rel.split("/"))
            if os.path.exists(path):
                return path
        if key.startswith("master:"):
            for path in (os.path.join(self.art_dir, "cover.jpg"), BUNDLED_COVER):
                if os.path.exists(path):
                    return path
        return None

    # ---- changing game files (with undo) ----------------------------------
    def apply_changes(self, changes, label):
        """changes = [(destination file, source file), ...].  Every destination is backed up first; sources
        that are themselves destinations (a swap) are read from their backups.  Returns an undo record."""
        op_id = int(time.time() * 1000)
        os.makedirs(self.undo_dir, exist_ok=True)
        backups, restore = {}, []
        for i, (dest, _src) in enumerate(changes):
            if os.path.exists(dest):
                backup = os.path.join(self.undo_dir, f"{op_id}_{i}.ogg")
                shutil.copyfile(dest, backup)
                backups[_norm(dest)] = backup
                restore.append((dest, backup))
            else:
                restore.append((dest, None))
        done = []
        try:
            for dest, src in changes:
                _atomic_copy(backups.get(_norm(src), src), dest)
                done.append(dest)
        except Exception:
            for dest, backup in restore:
                if dest in done and backup:
                    try:
                        _atomic_copy(backup, dest)
                    except OSError:
                        pass
            raise
        return {"label": label, "restore": restore}

    def undo(self, op):
        for dest, backup in op["restore"]:
            if backup and os.path.exists(backup):
                _atomic_copy(backup, dest)
            elif not backup and os.path.exists(dest):
                os.remove(dest)
        self.discard(op)

    def discard(self, op):
        for _dest, backup in op["restore"]:
            if backup:
                try:
                    os.remove(backup)
                except OSError:
                    pass
