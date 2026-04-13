import json
import threading
from pathlib import Path


class SettingsManager:
    def __init__(self, app_name="notapad"):
        self.filepath = Path.home() / f".{app_name}.json"
        self.defaults = {
            "theme_mode":        "system",
            "word_wrap":         True,
            "show_line_nums":    True,
            "status_bar_visible":True,
            "font_family":       "Consolas",
            "font_size":         11,
            # E8 — window geometry
            "geometry":          None,
            # E7 — session restore
            "last_file":         None,
            "last_cursor":       "1.0",
            # E22 — tab behaviour
            "tab_size":          4,
            "use_spaces":        True,
            # E9 — recent files MRU
            "recent_files":      [],
        }
        self.config = self.load()
        self._save_timer: threading.Timer | None = None

    # ── persistence ───────────────────────────────────────────────────────────

    def load(self):
        if not self.filepath.exists():
            return self.defaults.copy()
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**self.defaults, **data}
        except Exception:
            return self.defaults.copy()

    def save(self):
        """Write config to disk. Called from the debounce timer thread."""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def save_immediate(self):
        """Cancel any pending debounced save and flush to disk right now.
        Always call this on app exit so the final state is guaranteed written."""
        if self._save_timer:
            self._save_timer.cancel()
            self._save_timer = None
        self.save()

    # ── public API ────────────────────────────────────────────────────────────

    def get(self, key):
        return self.config.get(key, self.defaults.get(key))

    def set(self, key, value):
        """Update a value. Actual disk write is debounced by 2 seconds so that
        rapid-fire calls (zoom steps, every toggle) don't hammer the filesystem."""
        self.config[key] = value
        self._schedule_save()

    # ── internals ─────────────────────────────────────────────────────────────

    def _schedule_save(self):
        if self._save_timer:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(2.0, self._fire_save)
        self._save_timer.daemon = True  # won't block process exit
        self._save_timer.start()

    def _fire_save(self):
        self._save_timer = None
        self.save()
