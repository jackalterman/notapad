import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import os, sys, re, datetime
try:
    import winreg
except ImportError:
    winreg = None

# E24 — optional drag-and-drop support via tkinterdnd2
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

# Local Modules
from notapad_app.config import APP_NAME, THEMES, EXT_LANG, LANG_LABEL
from notapad_app.ui_engine import AntiqueMenu, apply_windows_title_bar
from notapad_app.editor import apply_highlight
from notapad_app.settings import SettingsManager
from notapad_app import dialogs

class Notapad:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Untitled — {APP_NAME}")
        self.root.geometry("980x700")
        self.root.minsize(480, 320)

        # Set application icon
        if os.path.exists("notapad.ico"):
            try:
                self.root.iconbitmap("notapad.ico")
            except Exception:
                pass

        # Set nice menu / dialog font BEFORE building menus
        root.option_add("*Menu.font",     "Segoe\\ UI 10")
        root.option_add("*Dialog.font",   "Segoe\\ UI 10")
        root.option_add("*TLabel.font",   "Segoe\\ UI 9")
        root.option_add("*TButton.font",  "Segoe\\ UI 9")
        root.option_add("*TEntry.font",   "Segoe\\ UI 10")

        self.settings = SettingsManager()

        # E8 — restore window size/position from last session
        saved_geo = self.settings.get("geometry")
        if saved_geo:
            try:
                self.root.geometry(saved_geo)
            except Exception:
                pass

        self.current_file: str | None = None
        self.is_modified              = False
        self.search_window: tk.Toplevel | None = None
        
        self.status_bar_visible       = tk.BooleanVar(value=self.settings.get("status_bar_visible"))
        self.word_wrap                = tk.BooleanVar(value=self.settings.get("word_wrap"))
        self.show_line_nums           = tk.BooleanVar(value=self.settings.get("show_line_nums"))
        self._language: str | None    = None
        self._lang_var                = tk.StringVar(value="")
        self._theme_mode              = tk.StringVar(value=self.settings.get("theme_mode"))

        self._font_family = self.settings.get("font_family")
        self._font_size   = self.settings.get("font_size")
        self._zoom_level  = 0
        self._current_font = font.Font(family=self._font_family, size=self._font_size)

        self._match_positions: list[tuple[str,str]] = []
        self._match_current   = -1
        self._ln_after = None
        self._hl_after = None

        self.search_case       = tk.BooleanVar(value=False)
        self.search_regex      = tk.BooleanVar(value=False)
        self.search_whole      = tk.BooleanVar(value=False)
        self.search_dir        = tk.StringVar(value="down")
        self.search_last_term  = ""
        self.search_count_lbl  = None
        self.search_after_id   = None
        self.MAX_SEARCH_HI     = 1000

        self.menu_armed     = False
        self.active_antique = None # Current AntiqueMenu instance
        self._line_ending   = "\n" # E17 — detected on open, restored on save
        self._encoding      = "utf-8"  # E18 — detected on open, used on save
        self._file_mtime    = None     # E23 — mtime at last open/save for change detection
        self._tab_size      = self.settings.get("tab_size")    # E22
        self._use_spaces    = self.settings.get("use_spaces")  # E22
        self._word_chars_extra = self.settings.get("word_chars_extra")  # E26
        self._dirty_line    = None  # E6 — last-edited line for dirty-region highlighting
        self._loading       = False # E19 — guard against concurrent file loads
        # E2 — search result cache invalidation
        self._text_version       = 0
        self._search_cache_key   = None
        # E9 — recent files (loaded from settings; pruned on launch in main())
        self._recent_files: list[str] = list(self.settings.get("recent_files") or [])

        self._build_native_menu()
        self._build_statusbar()
        self._build_find_bar()         # E10 — inline find bar (hidden until Ctrl+F)
        self._build_reload_bar()       # E23 — file-changed-on-disk notification bar
        self._build_main_pane()
        self._build_editor()
        self._build_results_panel()
        self._setup_syntax_tags()
        self._bind_events()

        self.apply_theme()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind_all("<Button-1>", self._on_app_click, add="+")
        self._schedule_ln_update()
        self._apply_initial_settings()  # apply saved display toggles now that all widgets exist

    def _on_app_click(self, event):
        if self.active_antique:
            try:
                x, y = event.x_root, event.y_root
                cw = self.root.winfo_containing(x, y)
                if cw:
                    if cw in self.menu_buttons:
                        return
                    # We compare widget hierarchy since AntiqueMenu is now a tk.Frame child of root
                    parent = cw
                    while parent:
                        if parent == self.active_antique: return
                        parent = self.root.nametowidget(parent.winfo_parent()) if parent.winfo_parent() else None
            except Exception:
                pass
            self.active_antique.close()

    def _center_window(self, win):
        win.update_idletasks()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        ww, wh = win.winfo_width(), win.winfo_height()
        x = rx + (rw // 2) - (ww // 2)
        y = ry + (rh // 2) - (wh // 2)
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _build_main_pane(self):
        self.pane = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        self.pane.pack(fill=tk.BOTH, expand=True)

    def _get_system_theme(self) -> str:
        if sys.platform != "win32" or not winreg: return "light"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value == 1 else "dark"
        except: return "light"

    def apply_theme(self):
        mode = self._theme_mode.get()
        theme_key = self._get_system_theme() if mode == "system" else mode
        t = THEMES[theme_key]
        self.current_theme = t

        self.root.configure(bg=t["bg_status"])
        
        self.text.configure(
            bg=t["bg_editor"], fg=t["fg_editor"],
            insertbackground=t["accent"],
            selectbackground=t["sel_bg"], selectforeground=t["sel_fg"]
        )
        self.gutter.configure(bg=t["bg_gutter"])
        self.gutter_sep.configure(bg=t["sep"])
        self.editor_frame.configure(bg=t["bg_gutter"])

        self.menubar_frame.configure(bg=t["bg_status"])
        self.menubar_sep.configure(bg=t["sep"])
        for btn in self.menu_buttons:
            btn.configure(bg=t["bg_status"], fg=t["fg_status"])

        bold_tags = {"keyword", "tag"}
        for tag in THEMES["light"]["syn"].keys():
            color = t["syn"].get(tag, t["fg_editor"])
            w = "bold" if tag in bold_tags else "normal"
            self.text.tag_configure(tag, foreground=color, font=font.Font(font=self._current_font, weight=w))
        
        self.statusbar.configure(bg=t["bg_status"])
        self.status_top_sep.configure(bg=t["sep"])
        for child in self.statusbar.winfo_children():
            if isinstance(child, tk.Label): child.configure(bg=t["bg_status"], fg=t["fg_status"])
            elif isinstance(child, tk.Frame) and child.winfo_width() == 1: child.configure(bg=t["sep"])

        self.results_frame.configure(bg=t["bg_status"])
        self.results_top_bar.configure(bg=t["bg_status"])
        self.results_label.configure(bg=t["bg_status"], fg=t["fg_status"])
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background=t["bg_editor"], foreground=t["fg_editor"],
            fieldbackground=t["bg_editor"], bordercolor=t["sep"], lightcolor=t["sep"], darkcolor=t["sep"])
        style.configure("Treeview.Heading", background=t["bg_status"], foreground=t["fg_status"], relief=tk.FLAT)
        style.map("Treeview", background=[('selected', t["sel_bg"])], foreground=[('selected', t["sel_fg"])])

        self.text.tag_config("search_hi",  background="#fff176" if theme_key == "light" else "#4a4a00", foreground=t["fg_editor"])
        self.text.tag_config("search_cur", background=t["accent"], foreground="#ffffff")
        # E16 — bracket match tag: subtle underline + tinted background
        bm_bg = "#e8f4fd" if theme_key == "light" else "#1e3a4a"
        self.text.tag_config("bracket_match", background=bm_bg, underline=True)
        # E13 — passive word highlight tag: warm tint, visually distinct from search_hi
        wh_bg = "#fef3cd" if theme_key == "light" else "#3a3010"
        self.text.tag_config("word_hi", background=wh_bg)

        # E10 — theme the inline find bar
        self.find_bar.configure(bg=t["bg_status"])
        self.find_bar_sep.configure(bg=t["sep"])
        self.find_bar_inner.configure(bg=t["bg_status"])
        for child in self.find_bar_inner.winfo_children():
            cls = child.winfo_class()
            if cls == "Label":
                child.configure(bg=t["bg_status"], fg=t["fg_status"])
            elif cls == "Checkbutton":
                child.configure(bg=t["bg_status"], fg=t["fg_status"],
                                selectcolor=t["bg_gutter"],
                                activebackground=t["bg_status"],
                                activeforeground=t["accent"])
        self.find_bar_entry.configure(
            bg=t.get("bg_input", t["bg_gutter"]), fg=t["fg_editor"],
            insertbackground=t["fg_editor"])
        self.find_bar_count.configure(fg=t["accent"])  # override loop's fg_status

        if sys.platform == "win32": apply_windows_title_bar(self.root, theme_key == "dark")
        self._schedule_highlight()

    def set_theme_mode(self, mode: str):
        self._theme_mode.set(mode)
        self.settings.set("theme_mode", mode)
        self.apply_theme()

    def _apply_initial_settings(self):
        """Apply persisted display toggles that require all widgets to exist first.
        Called once at the end of __init__; also safe to call again after a theme reset."""
        # Ensure the toggle commands are executed to match the state of the BooleanVars
        # (which were initialized from the settings dictionary in __init__).
        self.toggle_wrap()
        self._toggle_line_numbers()
        self.toggle_statusbar()
        # Ensure zoom is correct from startup
        self._apply_font()

    def _build_results_panel(self):
        self.results_frame = tk.Frame(self.pane, height=190)
        self.results_frame.pack_propagate(False)

        self.results_top_bar = tk.Frame(self.results_frame)
        self.results_top_bar.pack(side=tk.TOP, fill=tk.X)
        self.results_sep = tk.Frame(self.results_top_bar, height=1)
        self.results_sep.pack(side=tk.TOP, fill=tk.X)
        
        self.results_label = tk.Label(self.results_top_bar, text="Search Results", font=("Segoe UI", 9, "bold"), padx=10)
        self.results_label.pack(side=tk.LEFT)
        
        ttk.Button(self.results_top_bar, text="\u2715", width=3, command=self.hide_results_panel).pack(side=tk.RIGHT, padx=5, pady=2)

        tree_frame = tk.Frame(self.results_frame)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.results_tree = ttk.Treeview(tree_frame, columns=("line", "text"), show="headings", height=6)
        self.results_tree.heading("line", text="Line")
        self.results_tree.heading("text", text="Content")
        self.results_tree.column("line", width=55,  minwidth=40,  stretch=False)
        self.results_tree.column("text", width=900, minwidth=200, stretch=True)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.results_tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.configure(yscrollcommand=vsb.set)

        self.results_tree.bind("<Double-1>", self._on_results_click)
        self.results_tree.bind("<Return>",   self._on_results_click)

    def show_results_panel(self):
        if not self.results_frame.winfo_ismapped():
            self.pane.add(self.results_frame, weight=0)
            self.pane.paneconfig(self.results_frame, height=190)

    def hide_results_panel(self):
        self.pane.forget(self.results_frame)

    def _on_results_click(self, event=None):
        item = self.results_tree.selection()
        if not item: return
        pos = self.results_tree.item(item[0], "tags")[0]
        self.text.mark_set(tk.INSERT, pos)
        self.text.see(pos)
        self.text.focus_set()
        self._clear_highlights()
        end = f"{pos}+{len(self.search_last_term)}c"
        self.text.tag_add("search_cur", pos, end)

    def _build_native_menu(self):
        self.menu_data = {
            "File": [
                {"type":"cmd", "label":"New",          "acc":"Ctrl+N",       "cmd":self.new_file},
                {"type":"cmd", "label":"Open…",        "acc":"Ctrl+O",       "cmd":self.open_file},
                {"type":"cmd", "label":"Recent Files ▶","acc":"",            "cmd":self._open_recent_menu},
                {"type":"cmd", "label":"Save",         "acc":"Ctrl+S",       "cmd":self.save_file},
                {"type":"cmd", "label":"Save As…",     "acc":"Ctrl+Shift+S", "cmd":self.save_as_file},
                {"type":"cmd", "label":"Close File",   "acc":"Ctrl+W",       "cmd":self.close_file},
                {"type":"sep"},
                {"type":"cmd", "label":"Exit",         "cmd":self.on_close},
            ],
            "Edit": [
                {"type":"cmd", "label":"Undo", "acc":"Ctrl+Z", "cmd":self.undo},
                {"type":"cmd", "label":"Redo", "acc":"Ctrl+Y", "cmd":self.redo},
                {"type":"sep"},
                {"type":"cmd", "label":"Cut", "acc":"Ctrl+X", "cmd":self.cut},
                {"type":"cmd", "label":"Copy", "acc":"Ctrl+C", "cmd":self.copy},
                {"type":"cmd", "label":"Paste", "acc":"Ctrl+V", "cmd":self.paste},
                {"type":"cmd", "label":"Delete", "acc":"Del", "cmd":self.delete_selection},
                {"type":"sep"},
                {"type":"cmd", "label":"Find…", "acc":"Ctrl+F", "cmd":self.open_find_bar},
                {"type":"cmd", "label":"Find Next", "acc":"F3",           "cmd":self.find_next},
                {"type":"cmd", "label":"Find All",  "acc":"Ctrl+Shift+F", "cmd":self.open_find_all},
                {"type":"cmd", "label":"Replace…", "acc":"Ctrl+H", "cmd":lambda: dialogs.open_replace(self)},
                {"type":"cmd", "label":"Go To Line…", "acc":"Ctrl+G", "cmd":lambda: dialogs.goto_line(self)},
                {"type":"sep"},
                {"type":"cmd", "label":"Select All", "acc":"Ctrl+A", "cmd":self.select_all},
                {"type":"cmd", "label":"Time / Date", "acc":"F5", "cmd":self.insert_datetime},
            ],
            "Format": [
                {"type":"check", "label":"Word Wrap",    "var":self.word_wrap,     "cmd":self.toggle_wrap},
                {"type":"check", "label":"Line Numbers", "var":self.show_line_nums,"cmd":self._toggle_line_numbers},
                {"type":"sep"},
                {"type":"cmd",   "label":"Font…",        "cmd":lambda: dialogs.choose_font(self)},
                {"type":"sep"},
                {"type":"cmd",   "label":"Tab Size: 2",  "cmd":lambda: self._set_tab_size(2)},
                {"type":"cmd",   "label":"Tab Size: 4",  "cmd":lambda: self._set_tab_size(4)},
                {"type":"cmd",   "label":"Tab Size: 8",  "cmd":lambda: self._set_tab_size(8)},
                {"type":"cmd",   "label":"Use Tab Character", "cmd":lambda: self._set_tab_size(self._tab_size, spaces=False)},
                {"type":"sep"},
                {"type":"cmd",   "label":"Word Select: Standard",          "cmd":lambda: self._set_word_chars("")},
                {"type":"cmd",   "label":"Word Select: + Hyphens",         "cmd":lambda: self._set_word_chars("-")},
                {"type":"cmd",   "label":"Word Select: + Dots",            "cmd":lambda: self._set_word_chars(".")},
                {"type":"cmd",   "label":"Word Select: + Hyphens & Dots",  "cmd":lambda: self._set_word_chars("-.")},
            ],
            "View": [
                {"type":"cmd", "label":"Zoom In", "acc":"Ctrl+=", "cmd":self.zoom_in},
                {"type":"cmd", "label":"Zoom Out", "acc":"Ctrl+-", "cmd":self.zoom_out},
                {"type":"cmd", "label":"Restore Zoom", "acc":"Ctrl+0", "cmd":self.zoom_reset},
                {"type":"sep"},
                {"type":"cmd", "label":"Appearance", "cmd":lambda: dialogs.show_appearance_submenu(self)},
                {"type":"sep"},
                {"type":"check", "label":"Status Bar", "var":self.status_bar_visible, "cmd":self.toggle_statusbar},
            ],
            "Help": [
                {"type":"cmd", "label":"About Notapad", "cmd":lambda: dialogs.show_about(self)},
            ]
        }
        self.menubar_frame = tk.Frame(self.root, height=30)
        self.menubar_frame.pack(side=tk.TOP, fill=tk.X)
        self.menubar_frame.pack_propagate(False)

        menu_labels = ["File", "Edit", "Format", "View", "Help"]
        self.menu_buttons = []
        for label in menu_labels:
            btn = tk.Label(self.menubar_frame, text=label, font=("Segoe UI", 10), padx=12, pady=2, relief=tk.FLAT)
            btn.pack(side=tk.LEFT)
            btn.bind("<Button-1>", lambda e, l=label, b=btn: self._toggle_antique_menu(e, l, b))
            btn.bind("<Enter>",    lambda e, l=label, b=btn: self._on_menu_hover(l, b))
            btn.bind("<Leave>",    lambda e, b=btn: self._on_menu_leave(b))
            self.menu_buttons.append(btn)
        
        self.menubar_sep = tk.Frame(self.root, height=1)
        self.menubar_sep.pack(side=tk.TOP, fill=tk.X)

    def _toggle_antique_menu(self, event, label, button):
        was_active = False
        if self.active_antique:
            was_active = (self.active_antique.parent_btn == button)
            self.active_antique.close()
            if was_active: return

        self.menu_armed = True
        self.active_antique = AntiqueMenu(self, button, self.menu_data[label])
        button.config(bg=self.current_theme["accent"], fg="#ffffff")

    def _on_menu_hover(self, label, button):
        if self.menu_armed and self.active_antique:
            if self.active_antique.parent_btn != button:
                self._toggle_antique_menu(None, label, button)
        else: button.config(bg=self.current_theme["accent"], fg="#ffffff")

    def _on_menu_leave(self, button):
        if self.active_antique and self.active_antique.parent_btn == button: return
        button.config(bg=self.current_theme["bg_status"], fg=self.current_theme["fg_status"])

    def _build_editor(self):
        self.editor_frame = tk.Frame(self.pane)
        self.pane.add(self.editor_frame, weight=1)

        self.gutter = tk.Canvas(self.editor_frame, width=52, highlightthickness=0)
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)

        self.gutter_sep = tk.Frame(self.editor_frame, width=1)
        self.gutter_sep.pack(side=tk.LEFT, fill=tk.Y)

        self.scrollbar_y = ttk.Scrollbar(self.editor_frame, orient=tk.VERTICAL)
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.scrollbar_x = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL)

        self.text = tk.Text(
            self.editor_frame, wrap=tk.WORD, undo=True, maxundo=-1, font=self._current_font,
            yscrollcommand=self._on_yscroll, xscrollcommand=self.scrollbar_x.set,
            relief=tk.FLAT, borderwidth=0, padx=10, pady=8
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar_y.config(command=self._on_textscroll)
        self.scrollbar_x.config(command=self.text.xview)

    def _build_statusbar(self):
        self.statusbar = tk.Frame(self.root, height=22)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.statusbar.pack_propagate(False)
        self.status_top_sep = tk.Frame(self.statusbar, height=1)
        self.status_top_sep.pack(side=tk.TOP, fill=tk.X)

        uf = ("Segoe UI", 9)
        def _sep(): tk.Frame(self.statusbar, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=3)
        def _rsep(): tk.Frame(self.statusbar, width=1).pack(side=tk.RIGHT, fill=tk.Y, pady=3)

        self.status_pos = tk.Label(self.statusbar, text="Ln 1, Col 1", font=uf, anchor=tk.W, padx=10)
        self.status_pos.pack(side=tk.LEFT)
        _sep()
        self.status_words = tk.Label(self.statusbar, text="Words: 0  Chars: 0", font=uf, anchor=tk.W, padx=10)
        self.status_words.pack(side=tk.LEFT)

        self.status_eol = tk.Label(self.statusbar, text="LF", font=uf, anchor=tk.E, padx=10)
        self.status_eol.pack(side=tk.RIGHT)
        _rsep()
        self.status_enc = tk.Label(self.statusbar, text="UTF-8", font=uf, anchor=tk.E, padx=10)
        self.status_enc.pack(side=tk.RIGHT)
        _rsep()
        self.status_zoom = tk.Label(self.statusbar, text="100%", font=uf, anchor=tk.E, padx=10)
        self.status_zoom.pack(side=tk.RIGHT)
        _rsep()
        self.status_lang = tk.Label(self.statusbar, text="Plain Text", font=uf, anchor=tk.E, padx=10)
        self.status_lang.pack(side=tk.RIGHT)
        # E14 — clicking the language label opens a language picker menu
        self.status_lang.configure(cursor="hand2")
        self.status_lang.bind("<Button-1>", self._open_language_menu)
        _rsep()

    def _build_find_bar(self):
        """E10 — Sublime-style inline find bar. Hidden until Ctrl+F."""
        uf = ("Segoe UI", 9)
        t  = {"bg_status": "#f0f0f0", "fg_status": "#333333",
               "sep": "#e0e0e0", "bg_input": "#ffffff",
               "fg_editor": "#1e1e1e", "accent": "#0078d7",
               "bg_gutter": "#f3f3f3"}  # placeholder — apply_theme overwrites immediately

        self.find_bar = tk.Frame(self.root, height=32)
        # Packed below statusbar; hidden by default — shown on open_find_bar()
        self.find_bar_sep   = tk.Frame(self.find_bar, height=1, bg=t["sep"])
        self.find_bar_sep.pack(side=tk.TOP, fill=tk.X)
        self.find_bar_inner = tk.Frame(self.find_bar, bg=t["bg_status"])
        self.find_bar_inner.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        tk.Label(self.find_bar_inner, text="Find:", font=uf,
                 bg=t["bg_status"], fg=t["fg_status"]).pack(side=tk.LEFT, padx=(0, 4))

        self._find_bar_var = tk.StringVar()
        self.find_bar_entry = tk.Entry(
            self.find_bar_inner, textvariable=self._find_bar_var,
            font=("Segoe UI", 10), relief=tk.FLAT, bd=3, width=28,
            bg=t["bg_input"], fg=t["fg_editor"], insertbackground=t["fg_editor"])
        self.find_bar_entry.pack(side=tk.LEFT, padx=(0, 6))

        self.find_bar_count = tk.Label(self.find_bar_inner, text="", font=uf,
                                       bg=t["bg_status"], fg=t["accent"], width=16, anchor="w")
        self.find_bar_count.pack(side=tk.LEFT, padx=(0, 8))

        # Nav buttons
        btn_cfg = dict(font=uf, relief=tk.FLAT, padx=6, pady=1,
                       bg=t["bg_status"], fg=t["fg_status"],
                       activebackground=t["sep"], cursor="hand2")
        tk.Button(self.find_bar_inner, text="▲", command=self.find_prev, **btn_cfg).pack(side=tk.LEFT, padx=1)
        tk.Button(self.find_bar_inner, text="▼", command=self.find_next, **btn_cfg).pack(side=tk.LEFT, padx=1)

        # Options
        chk_cfg = dict(font=uf, bg=t["bg_status"], fg=t["fg_status"],
                       selectcolor=t["bg_gutter"],
                       activebackground=t["bg_status"], activeforeground=t["accent"],
                       relief=tk.FLAT, bd=0)
        tk.Checkbutton(self.find_bar_inner, text="Aa", variable=self.search_case,
                       command=self._on_find_bar_type, **chk_cfg).pack(side=tk.LEFT, padx=4)
        tk.Checkbutton(self.find_bar_inner, text=".*", variable=self.search_regex,
                       command=self._on_find_bar_type, **chk_cfg).pack(side=tk.LEFT, padx=4)
        tk.Checkbutton(self.find_bar_inner, text="\\b", variable=self.search_whole,
                       command=self._on_find_bar_type, **chk_cfg).pack(side=tk.LEFT, padx=4)

        # Close button
        tk.Button(self.find_bar_inner, text="✕", command=self.close_find_bar,
                  **btn_cfg).pack(side=tk.RIGHT, padx=(4, 0))
        # Find All button — populates the results panel below the editor
        tk.Button(self.find_bar_inner, text="Find All",
                  command=lambda: self.find_all(self._find_bar_var.get()),
                  **btn_cfg).pack(side=tk.RIGHT, padx=(4, 0))

        # Wire up live search
        self._find_bar_var.trace_add("write", lambda *_: self._on_find_bar_type())
        self.find_bar_entry.bind("<Return>",  lambda e: self.find_next())
        self.find_bar_entry.bind("<Shift-Return>", lambda e: self.find_prev())
        self.find_bar_entry.bind("<Escape>",  lambda e: self.close_find_bar())

        # Point the shared search_count_lbl at the bar's label
        self.search_count_lbl = self.find_bar_count

    def open_find_bar(self):
        """Show the inline find bar, populate with any current selection, focus entry."""
        # Pack between statusbar and the main pane — "above status bar"
        if not self.find_bar.winfo_ismapped():
            self.find_bar.pack(side=tk.BOTTOM, fill=tk.X, before=self.pane)
        # Pre-fill with selected text if short enough
        try:
            sel = self.text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if sel and "\n" not in sel and len(sel) <= 200:
                self._find_bar_var.set(sel)
        except tk.TclError:
            pass
        self.find_bar_entry.focus_set()
        self.find_bar_entry.select_range(0, tk.END)
        if self._find_bar_var.get():
            self._do_search(self._find_bar_var.get())

    def close_find_bar(self):
        """Hide the inline find bar and return focus to the editor."""
        if self.find_bar.winfo_ismapped():
            self.find_bar.pack_forget()
        self._clear_highlights()
        self._clear_word_highlight()    # E13
        self._match_positions = []
        self._match_current   = -1
        self.text.focus_set()

    def open_find_all(self):
        """Open the find bar (if needed) and immediately populate results."""
        self.open_find_bar()
        term = self._find_bar_var.get()
        if term:
            self.find_all(term)

    def _on_find_bar_type(self):
        """Debounced live search triggered by every keystroke in the find bar."""
        if self.search_after_id:
            self.root.after_cancel(self.search_after_id)
        self.search_after_id = self.root.after(
            200, lambda: self._do_search(self._find_bar_var.get()))

    # ── E23 — file-changed-on-disk notification bar ───────────────────────────

    def _build_reload_bar(self):
        """Build the non-blocking reload notification bar. Hidden until needed."""
        t = {"bg_status": "#f0f0f0", "fg_status": "#333333",
             "sep": "#e0e0e0", "accent": "#0078d7"}  # placeholder; apply_theme overwrites
        uf = ("Segoe UI", 9)

        self._reload_bar = tk.Frame(self.root, height=28)
        self._reload_bar_sep = tk.Frame(self._reload_bar, height=1, bg=t["sep"])
        self._reload_bar_sep.pack(side=tk.TOP, fill=tk.X)
        self._reload_bar_inner = tk.Frame(self._reload_bar, bg=t["bg_status"])
        self._reload_bar_inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        self._reload_bar_lbl = tk.Label(
            self._reload_bar_inner,
            text="File changed on disk.",
            font=uf, bg=t["bg_status"], fg=t["fg_status"], anchor="w")
        self._reload_bar_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_cfg = dict(font=uf, relief=tk.FLAT, padx=8, pady=1,
                       bg=t["bg_status"], fg=t["fg_status"],
                       activebackground=t["sep"], cursor="hand2")
        tk.Button(self._reload_bar_inner, text="Reload",
                  command=self._reload_from_disk, **btn_cfg).pack(side=tk.LEFT, padx=4)
        tk.Button(self._reload_bar_inner, text="Dismiss",
                  command=self._dismiss_reload_bar, **btn_cfg).pack(side=tk.LEFT, padx=(0, 4))

    def _check_file_changed(self, event=None):
        """E23 — called on <FocusIn>; shows reload bar if mtime has changed."""
        if not self.current_file or self._file_mtime is None:
            return
        # Ignore focus events from child widgets (dialogs restoring focus)
        if event and event.widget is not self.root:
            return
        try:
            current_mtime = os.path.getmtime(self.current_file)
        except Exception:
            return
        if current_mtime != self._file_mtime:
            self._file_mtime = current_mtime   # update so we don't keep prompting
            self._show_reload_bar()

    def _show_reload_bar(self):
        if not self._reload_bar.winfo_ismapped():
            # Pack above the find bar / pane (below statusbar)
            self._reload_bar.pack(side=tk.BOTTOM, fill=tk.X, before=self.pane)
        t = self.current_theme
        self._reload_bar.configure(bg=t["bg_status"])
        self._reload_bar_sep.configure(bg=t["sep"])
        self._reload_bar_inner.configure(bg=t["bg_status"])
        for child in self._reload_bar_inner.winfo_children():
            child.configure(bg=t["bg_status"])
            if isinstance(child, tk.Label):
                child.configure(fg=t["fg_status"])
            elif isinstance(child, tk.Button):
                child.configure(fg=t["fg_status"], activebackground=t["sep"])

    def _reload_from_disk(self):
        """Re-read the file from disk, preserving cursor position."""
        self._dismiss_reload_bar()
        if not self.current_file or not os.path.isfile(self.current_file):
            return
        cursor = self.text.index(tk.INSERT)
        self.is_modified = False          # suppress "save changes?" dialog
        self.open_file(self.current_file)
        try:
            self.text.mark_set(tk.INSERT, cursor)
            self.text.see(cursor)
        except Exception:
            pass

    def _dismiss_reload_bar(self):
        if self._reload_bar.winfo_ismapped():
            self._reload_bar.pack_forget()

    # ── E24 — drag-and-drop ────────────────────────────────────────────────────

    def _on_drop(self, event):
        """Handle a file drop. Strips Tcl list braces and opens the first path."""
        raw = event.data or ""
        # tkinterdnd2 returns paths wrapped in braces on Windows: {C:/path/to/file}
        raw = raw.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        # Multiple files arrive space-separated; take only the first
        path = raw.split("} {")[0].strip("{}").strip()
        if path and os.path.isfile(path):
            self.open_file(path)
        return event.action if hasattr(event, "action") else None

    def _setup_syntax_tags(self): pass

    def _bind_events(self):
        t, r = self.text, self.root

        t.bind("<Control-z>",     lambda e: (self.undo(),         "break")[1])
        t.bind("<Control-y>",     lambda e: (self.redo(),         "break")[1])
        t.bind("<Control-Z>",     lambda e: (self.redo(),         "break")[1])
        t.bind("<Control-a>",     lambda e: (self.select_all(),   "break")[1])
        t.bind("<Control-n>",     lambda e: (self.new_file(),     "break")[1])
        t.bind("<Control-o>",     lambda e: (self.open_file(),    "break")[1])
        t.bind("<Control-s>",     lambda e: (self.save_file(),    "break")[1])
        t.bind("<Control-S>",     lambda e: (self.save_as_file(), "break")[1])
        t.bind("<Control-w>",     lambda e: (self.close_file(),   "break")[1])
        t.bind("<Control-f>",     lambda e: (self.open_find_bar(),          "break")[1])
        t.bind("<Control-h>",     lambda e: (dialogs.open_replace(self), "break")[1])
        t.bind("<Control-g>",     lambda e: (dialogs.goto_line(self),    "break")[1])
        t.bind("<F3>",            lambda e: (self.find_next(),    "break")[1])
        t.bind("<F5>",            lambda e: (self.insert_datetime(),"break")[1])
        t.bind("<Control-equal>", lambda e: (self.zoom_in(),      "break")[1])
        t.bind("<Control-minus>", lambda e: (self.zoom_out(),     "break")[1])
        t.bind("<Control-0>",     lambda e: (self.zoom_reset(),   "break")[1])

        r.bind("<Control-n>",     lambda e: self.new_file())
        r.bind("<Control-o>",     lambda e: self.open_file())
        r.bind("<Control-s>",     lambda e: self.save_file())
        r.bind("<Control-S>",     lambda e: self.save_as_file())
        r.bind("<Control-w>",     lambda e: self.close_file())
        r.bind("<F3>",            lambda e: self.find_next())
        r.bind("<Control-f>",     lambda e: self.open_find_bar())
        t.bind("<Control-F>",     lambda e: (self.open_find_all(), "break")[1])
        r.bind("<Control-F>",     lambda e: self.open_find_all())
        r.bind("<Control-h>",     lambda e: dialogs.open_replace(self))
        r.bind("<Control-g>",     lambda e: dialogs.goto_line(self))

        t.bind("<Return>",        self._auto_indent)   # E21 — auto-indent
        t.bind("<Tab>",           self._handle_tab)       # E22 — smart tab
        t.bind("<Shift-Tab>",     self._handle_shift_tab) # E22 — dedent
        t.bind("<Double-Button-1>", self._handle_double_click)  # E26 — custom word boundaries
        # E2 — invalidate search cache when content changes
        t.bind("<<Modified>>",    self._on_text_modified)

        t.bind("<KeyRelease>",    self._on_key)
        t.bind("<ButtonRelease>", self._update_status)
        t.bind("<Configure>",     lambda e: (self._schedule_ln_update(), self._schedule_highlight()))
        t.bind("<Control-MouseWheel>", self._on_wheel_zoom)

        # E23 — detect external file changes when the window regains focus
        r.bind("<FocusIn>", self._check_file_changed)
        # E24 — drag-and-drop (only wired when tkinterdnd2 is available)
        if _DND_AVAILABLE:
            try:
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _on_wheel_zoom(self, event):
        if event.delta > 0: self.zoom_in()
        else:               self.zoom_out()
        return "break"

    def _on_yscroll(self, *args):
        self.scrollbar_y.set(*args)
        self._schedule_ln_update()
        self._schedule_highlight()

    def _on_textscroll(self, *args):
        self.text.yview(*args)
        self._schedule_ln_update()
        self._schedule_highlight()

    def _schedule_ln_update(self):
        if self._ln_after: self.root.after_cancel(self._ln_after)
        self._ln_after = self.root.after_idle(self._redraw_gutter)

    def _redraw_gutter(self):
        self._ln_after = None
        if not self.show_line_nums.get(): return
        
        # Ensure latest layout measurements before drawing
        self.root.update_idletasks()
        
        # E3 — skip gutter redraws for very large files
        try:
            if int(self.text.count("1.0", "end", "chars")[0] or 0) > 300_000:
                return
        except Exception:
            pass
        c = self.gutter
        c.delete("all")
        w = c.winfo_width()
        h = self.text.winfo_height()
        
        if w <= 1 or h <= 1:
            # Layout not yet ready; reschedule for a later tick
            self._schedule_ln_update()
            return

        # E4 — single pixel-probe pass using @0,y stepping.
        # Instead of iterating logical line numbers and calling dlineinfo() per line
        # (one Tcl round-trip each), we step through the viewport by line-height pixels.
        # text.index("@0,y") maps pixel → character index in one call; text.bbox("@0,y")
        # gives the exact pixel row bounds.  For each *unique* logical line we encounter
        # we draw the number once (at its first visible visual row).  This handles
        # word-wrap correctly and reduces Tcl round-trips to O(visible visual rows).
        try:
            lh = max(self._current_font.metrics("linespace"), 4)
        except Exception:
            lh = 16

        fill   = self.current_theme["fg_gutter"]
        drawn  = set()   # logical line numbers already drawn
        y      = 0
        while y <= h:
            try:
                idx = self.text.index(f"@10,{y}")
                ln  = int(idx.split(".")[0])
            except Exception:
                break
            if ln not in drawn:
                try:
                    bb = self.text.bbox(f"@10,{y}")
                    if bb:
                        _, row_y, _, row_h = bb
                        c.create_text(w // 2, row_y + row_h // 2, anchor="center",
                                      text=str(ln), fill=fill,
                                      font=self._current_font)
                        drawn.add(ln)
                except Exception:
                    pass
            y += lh

    def _on_key(self, event=None):
        if not self.is_modified:
            self.is_modified = True
            self._update_title()
        self._update_status()
        self._schedule_ln_update()
        self._schedule_highlight()
        self._schedule_bracket_match()  # E16
        self._clear_word_highlight()    # E13 — clear immediately on keystroke
        # E6 — record the edited line so apply_highlight() can extend its region
        try:
            self._dirty_line = int(self.text.index(tk.INSERT).split(".")[0])
        except Exception:
            pass

    def _update_status(self, event=None):
        try:
            row, col = self.text.index(tk.INSERT).split(".")
            self.status_pos.config(text=f"Ln {row}, Col {int(col)+1}")
            content = self.text.get("1.0", tk.END)
            self.status_words.config(text=f"Words: {len(content.split())}  Chars: {len(content)-1}")
        except Exception: pass
        self._schedule_bracket_match()  # E16 — also fire on click/cursor move
        self._schedule_word_highlight() # E13 — idle word highlight on cursor move

    def _update_title(self):
        base  = os.path.basename(self.current_file) if self.current_file else "Untitled"
        dirty = " \u2022" if self.is_modified else ""
        self.root.title(f"{base}{dirty} — {APP_NAME}")

    def _apply_font(self):
        eff_size = max(6, self._font_size + self._zoom_level)
        self._current_font.config(family=self._font_family, size=eff_size)
        self.text.config(font=self._current_font)
        bold_tags = {"keyword", "tag"}
        for tag in THEMES["light"]["syn"].keys():
            w = "bold" if tag in bold_tags else "normal"
            self.text.tag_configure(tag, font=font.Font(font=self._current_font, weight=w))
        
        pct = round(eff_size / self._font_size * 100)
        self.status_zoom.config(text=f"{pct}%")
        # PERSISTENCE: Save the base font settings. 
        # Since zooming only modifies self._zoom_level, self._font_size remains 
        # at its base value and will be restored as 100% on next launch.
        self.settings.set("font_family", self._font_family)
        self.settings.set("font_size",   self._font_size)
        self._schedule_ln_update()

    def _schedule_highlight(self):
        if self._hl_after:
            self.root.after_cancel(self._hl_after)
        # E3 — skip highlighting entirely for large files
        try:
            char_count = int(self.text.count("1.0", "end", "chars")[0] or 0)
        except Exception:
            char_count = 0
        if char_count > 300_000:
            lang_label = LANG_LABEL.get(self._language, "Plain Text")
            self.status_lang.config(text=f"⚡ {lang_label} — large file")
            return
        # Restore normal label in case we were over threshold before
        self.status_lang.config(text=LANG_LABEL.get(self._language, "Plain Text"))
        self._hl_after = self.root.after(120, lambda: apply_highlight(self))

    def set_language(self, lang: str | None):
        self._language = lang
        self._lang_var.set(lang or "")
        self.status_lang.config(text=LANG_LABEL.get(lang, "Plain Text"))
        if not lang:
            for tag in self.current_theme["syn"].keys():
                self.text.tag_remove(tag, "1.0", tk.END)
        else: self._schedule_highlight()

    def _open_language_menu(self, event=None):
        """E14 — show an AntiqueMenu of all languages from LANG_LABEL for manual override."""
        items = [{"type": "cmd", "label": "Plain Text", "cmd": lambda: self.set_language(None)}]
        items.append({"type": "sep"})
        for lang, label in LANG_LABEL.items():
            if lang is None:
                continue
            items.append({"type": "cmd", "label": label, "cmd": lambda l=lang: self.set_language(l)})
        if self.active_antique:
            self.active_antique.close()
        menu = AntiqueMenu(self, self.status_lang, items)
        self.active_antique = menu
        # AntiqueMenu always places below its anchor. For a status-bar label that's at
        # the bottom of the window we need to reposition above it instead.
        menu.update_idletasks()
        mh = menu.winfo_reqheight()
        x  = self.status_lang.winfo_rootx() - self.root.winfo_rootx()
        y  = self.status_lang.winfo_rooty() - self.root.winfo_rooty() - mh
        menu.place(x=max(0, x), y=max(0, y))
        return "break"  # prevent _on_app_click (bind_all) from immediately closing the menu

    def _detect_and_set_language(self, path: str):
        ext  = os.path.splitext(path)[1].lower()
        self.set_language(EXT_LANG.get(ext))

    def _confirm_discard(self) -> bool:
        if not self.is_modified: return True
        name   = os.path.basename(self.current_file) if self.current_file else "Untitled"
        result = messagebox.askyesnocancel(APP_NAME, f"Save changes to {name}?")
        if result is True: return self.save_file()
        return False if result is None else True

    def new_file(self):
        if not self._confirm_discard(): return
        self.text.delete("1.0", tk.END)
        self.current_file   = None
        self.is_modified    = False
        self._line_ending   = "\n"          # E17
        self._encoding      = "utf-8"       # E18
        self._file_mtime    = None          # E23
        self.status_eol.config(text="LF")   # E17
        self.status_enc.config(text="UTF-8") # E18
        self.set_language(None)
        self._update_title()
        self._update_status()
        self._schedule_ln_update()

    def close_file(self):
        """B6 — close the current file and return to an Untitled blank state."""
        if not self._confirm_discard(): return
        self.text.delete("1.0", tk.END)
        self.current_file   = None
        self.is_modified    = False
        self._line_ending   = "\n"
        self._encoding      = "utf-8"
        self._file_mtime    = None
        self.status_eol.config(text="LF")
        self.status_enc.config(text="UTF-8")
        self.set_language(None)
        self._update_title()
        self._update_status()
        self._schedule_ln_update()

    def open_file(self, path: str | None = None):
        if not self._confirm_discard(): return
        if not path:
            path = filedialog.askopenfilename(
                filetypes=[("Text / Code files", "*.txt *.py *.js *.ts *.json *.xml *.html *.htm *.css *.sql *.sh *.bash *.md *.yaml *.yml *.toml *.rs *.go *.java *.bat *.cmd *.ini *.cfg *.conf"), ("All Files", "*.*")])
        if not path: return
        try:
            with open(path, "rb") as f:
                raw = f.read()

            # E17 — detect line endings before decoding
            if b"\r\n" in raw:
                self._line_ending = "\r\n"
                eol_label = "CRLF"
            elif b"\r" in raw:
                self._line_ending = "\r"
                eol_label = "CR"
            else:
                self._line_ending = "\n"
                eol_label = "LF"

            # E18 — detect encoding: try UTF-8, then chardet, then latin-1
            enc = "utf-8"
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    import chardet
                    result = chardet.detect(raw)
                    enc = (result.get("encoding") or "latin-1").lower()
                except ImportError:
                    enc = "latin-1"
            self._encoding = enc
            content = raw.decode(enc, errors="replace")

            # Normalise to \n for tk.Text; save_file() restores original ending
            if self._line_ending != "\n":
                content = content.replace("\r\n", "\n").replace("\r", "\n")

            self.text.delete("1.0", tk.END)

            # E19 — chunked progressive loading for large files (> 5 MB raw bytes)
            _LARGE_FILE_BYTES = 5 * 1024 * 1024
            if len(raw) > _LARGE_FILE_BYTES:
                self._load_large_file_chunked(content, path, eol_label, enc)
                return

            self.text.insert("1.0", content)
            self.text.mark_set(tk.INSERT, "1.0")
            self.current_file = path
            self.is_modified  = False
            self.status_eol.config(text=eol_label)
            self.status_enc.config(text=enc.upper().replace("-", ""))  # E18
            # E23 — record mtime so we can detect external changes later
            try:
                self._file_mtime = os.path.getmtime(path)
            except Exception:
                self._file_mtime = None
            self._update_title()
            self._update_status()
            self._schedule_ln_update()
            self._detect_and_set_language(path)
            self._push_recent(path)          # E9
        except Exception as exc: messagebox.showerror(APP_NAME, f"Could not open file:\n{exc}")

    def _load_large_file_chunked(self, content: str, path: str,
                                  eol_label: str, enc: str):
        """E19 — insert a large file in 50k-char chunks via after_idle() so the
        UI thread is never blocked for more than a few milliseconds at a time.
        Progress is shown in the status bar as 'Loading… N%'.
        Auto-disables syntax highlighting (file will exceed E3's 300k-char guard anyway).
        """
        _CHUNK = 50_000  # characters per idle tick

        # Split on line boundaries so we never cut in the middle of a line
        chunks: list[str] = []
        remaining = content
        while remaining:
            if len(remaining) <= _CHUNK:
                chunks.append(remaining)
                break
            cut = remaining.rfind("\n", 0, _CHUNK)
            if cut == -1:
                cut = _CHUNK
            chunks.append(remaining[:cut + 1])
            remaining = remaining[cut + 1:]

        total = len(chunks)
        self._loading = True
        self.status_pos.config(text="Loading…")
        self.status_words.config(text="0%")

        def _insert(i: int):
            if not self._loading:
                return  # aborted by a new open_file() call
            if i >= total:
                # ── finalization ─────────────────────────────────────────────
                self._loading = False
                self.text.mark_set(tk.INSERT, "1.0")
                self.current_file = path
                self.is_modified  = False
                self.status_eol.config(text=eol_label)
                self.status_enc.config(text=enc.upper().replace("-", ""))
                try:
                    self._file_mtime = os.path.getmtime(path)
                except Exception:
                    self._file_mtime = None
                self._update_title()
                self._update_status()
                self._schedule_ln_update()
                self._detect_and_set_language(path)
                self._push_recent(path)
                return

            self.text.insert(tk.END, chunks[i])
            pct = int((i + 1) / total * 100)
            self.status_words.config(text=f"{pct}%")
            self.root.after_idle(lambda: _insert(i + 1))

        self.root.after_idle(lambda: _insert(0))

    def save_file(self) -> bool:
        if not self.current_file: return self.save_as_file()
        try:
            content = self.text.get("1.0", tk.END).rstrip("\n")
            # E17 — restore the original line ending detected on open
            if self._line_ending != "\n":
                content = content.replace("\n", self._line_ending)
            # E18 — write in the detected (or default) encoding
            with open(self.current_file, "wb") as f:
                f.write(content.encode(self._encoding, errors="replace"))
            self.is_modified = False
            self._update_title()
            # E23 — update mtime reference after save
            try:
                self._file_mtime = os.path.getmtime(self.current_file)
            except Exception:
                self._file_mtime = None
            return True
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not save file:\n{exc}")
            return False

    def save_as_file(self) -> bool:
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if not path: return False
        self.current_file = path
        result = self.save_file()
        if result:
            self._detect_and_set_language(path)
            self._push_recent(path)          # E9
        return result

    def undo(self):
        try: self.text.edit_undo()
        except: pass
    def redo(self):
        try: self.text.edit_redo()
        except: pass
    def cut(self): self.text.event_generate("<<Cut>>")
    def copy(self): self.text.event_generate("<<Copy>>")
    def paste(self):
        self.text.event_generate("<<Paste>>")
        self._on_key()
    def delete_selection(self):
        try: self.text.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except: pass
    def select_all(self):
        self.text.tag_add(tk.SEL, "1.0", tk.END)
        self.text.mark_set(tk.INSERT, "1.0")
        self.text.see(tk.INSERT)
    def insert_datetime(self): self.text.insert(tk.INSERT, datetime.datetime.now().strftime("%I:%M %p %m/%d/%Y"))

    def _clear_highlights(self):
        self.text.tag_remove("search_hi", "1.0", tk.END)
        self.text.tag_remove("search_cur", "1.0", tk.END)

    def _do_search(self, term: str):
        self._clear_highlights()
        if not term:
            self._update_match_label()
            return

        case  = self.search_case.get()
        regex = self.search_regex.get()
        whole = self.search_whole.get()

        # E2 — skip full buffer scan if term + flags + text are unchanged
        cache_key = (term, case, regex, whole, self._text_version)
        if cache_key == self._search_cache_key and self._match_positions:
            # Re-apply highlights (cleared above) then bail
            for i, (pos, end) in enumerate(self._match_positions):
                if i >= self.MAX_SEARCH_HI: break
                self.text.tag_add("search_hi", pos, end)
            self._highlight_current()
            self._update_match_label()
            return

        search_term = term
        is_regex    = regex

        if whole:
            if not is_regex:
                search_term = r'\b' + re.escape(term) + r'\b'
                is_regex = True
            else:
                search_term = r'\b(?:' + term + r')\b'

        self.search_last_term = term
        idx, count_var, matches = "1.0", tk.IntVar(), []

        try:
            while True:
                pos = self.text.search(search_term, idx, tk.END, nocase=not case, regexp=is_regex, count=count_var)
                if not pos: break
                cnt = count_var.get()
                if cnt <= 0: break
                end = f"{pos}+{cnt}c"
                matches.append((pos, end))
                idx = end
                if self.text.compare(idx, "==", tk.END) or len(matches) > 10000: break
        except Exception: pass

        self._match_positions  = matches
        self._search_cache_key = cache_key   # E2 — store for next call

        for i, (pos, end) in enumerate(self._match_positions):
            if i >= self.MAX_SEARCH_HI: break
            self.text.tag_add("search_hi", pos, end)

        if self._match_positions:
            curr = self.text.index(tk.INSERT)
            self._match_current = 0
            for i, (s, e) in enumerate(self._match_positions):
                if self.text.compare(s, ">=", curr):
                    self._match_current = i
                    break
            self._highlight_current()
        self._update_match_label()

    def find_all(self, term):
        if not term: return
        self._do_search(term)
        if not self._match_positions: return
        self.results_tree.delete(*self.results_tree.get_children())
        self.show_results_panel()
        self.root.update_idletasks() # Force GUI to render the panel
        for pos, end in self._match_positions[:5000]:
            line_idx = pos.split(".")[0]
            line_text = self.text.get(f"{line_idx}.0", f"{line_idx}.end").strip()
            if len(line_text) > 120: line_text = line_text[:117] + "..."
            self.results_tree.insert("", tk.END, values=(line_idx, line_text), tags=(pos,))

    def _update_match_label(self):
        if not self.search_count_lbl: return
        if not self._match_positions:
            self.search_count_lbl.config(text="No matches", foreground="red") if self.search_last_term else self.search_count_lbl.config(text="")
        else:
            self.search_count_lbl.config(text=f"Match {self._match_current + 1} of {len(self._match_positions)}", fg=self.current_theme["accent"])

    def _highlight_current(self):
        self.text.tag_remove("search_cur", "1.0", tk.END)
        if 0 <= self._match_current < len(self._match_positions):
            s, e = self._match_positions[self._match_current]
            self.text.tag_add("search_cur", s, e)
            self.text.see(s)
            self.text.mark_set(tk.INSERT, s)

    def find_next(self):
        if not self._match_positions:
            self.open_find_bar()
            return
        wrapped = (self._match_current == len(self._match_positions) - 1)
        self._match_current = (self._match_current + 1) % len(self._match_positions)
        self._highlight_current()
        if wrapped:
            self._flash_wrap_indicator()
        else:
            self._update_match_label()

    def find_prev(self):
        if not self._match_positions:
            self.open_find_bar()
            return
        wrapped = (self._match_current == 0)
        self._match_current = (self._match_current - 1) % len(self._match_positions)
        self._highlight_current()
        if wrapped:
            self._flash_wrap_indicator()
        else:
            self._update_match_label()

    def _flash_wrap_indicator(self):
        """Briefly show '↩ Wrapped' in the search count label then restore it."""
        if not self.search_count_lbl:
            return
        self.search_count_lbl.config(text="↩ Wrapped", fg=self.current_theme["accent"])
        self.root.after(1200, self._update_match_label)

    def _auto_indent(self, event):
        """E21 — on Enter, replicate the leading whitespace of the current line."""
        line = self.text.get("insert linestart", "insert")
        indent = len(line) - len(line.lstrip())
        self.text.insert("insert", "\n" + line[:indent])
        self._on_key()
        return "break"  # suppress tk.Text default newline insertion

    # ── E22 — smart tab / dedent ───────────────────────────────────────────────

    def _handle_tab(self, event):
        """Insert spaces to the next tab stop (or a literal tab if use_spaces=False)."""
        if self._use_spaces:
            col = int(self.text.index(tk.INSERT).split(".")[1])
            spaces = self._tab_size - (col % self._tab_size)
            self.text.insert(tk.INSERT, " " * spaces)
        else:
            self.text.insert(tk.INSERT, "\t")
        self._on_key()
        return "break"

    def _handle_shift_tab(self, event):
        """Remove up to tab_size leading spaces from the current line."""
        line_start = self.text.index("insert linestart")
        line_text  = self.text.get(line_start, "insert linestart + 1 line")
        strip_count = 0
        for ch in line_text[:self._tab_size]:
            if ch == " ":
                strip_count += 1
            else:
                break
        if strip_count:
            self.text.delete(line_start, f"{line_start}+{strip_count}c")
            self._on_key()
        return "break"

    def _set_tab_size(self, size: int, spaces: bool = True):
        """Update tab size/mode and persist to settings."""
        self._tab_size   = size
        self._use_spaces = spaces
        self.settings.set("tab_size",   size)
        self.settings.set("use_spaces", spaces)

    # ── E26 — adjustable double-click word boundaries ─────────────────────────

    def _handle_double_click(self, event):
        """E26 — select the word under the click using the configurable word-char set.
        Returns 'break' to suppress Tk's default selection only when we successfully
        selected a word; falls through to default for non-word characters."""
        try:
            idx      = self.text.index(f"@{event.x},{event.y}")
            line, col = map(int, idx.split("."))
            line_text = self.text.get(f"{line}.0", f"{line}.end")
        except Exception:
            return  # let default handle it

        extra = re.escape(self._word_chars_extra)
        pat   = re.compile(r"[a-zA-Z0-9_" + extra + r"]")

        if col >= len(line_text) or not pat.match(line_text[col]):
            return  # clicked on non-word char — let default selection happen

        # Walk left to find word start
        start = col
        while start > 0 and pat.match(line_text[start - 1]):
            start -= 1
        # Walk right to find word end
        end = col
        while end < len(line_text) and pat.match(line_text[end]):
            end += 1

        self.text.tag_remove(tk.SEL, "1.0", tk.END)
        self.text.tag_add(tk.SEL, f"{line}.{start}", f"{line}.{end}")
        self.text.mark_set(tk.INSERT, f"{line}.{end}")
        self.text.see(tk.INSERT)
        # Trigger word highlight for the freshly selected word (E25)
        self._schedule_word_highlight()
        return "break"

    def _set_word_chars(self, extra: str):
        """E26 — update the extra word characters used for double-click selection."""
        self._word_chars_extra = extra
        self.settings.set("word_chars_extra", extra)

    # ── E2 — search cache invalidation ────────────────────────────────────────

    def _on_text_modified(self, event=None):
        """Increment version counter so _do_search() knows to rescan."""
        self._text_version += 1
        self.text.edit_modified(False)  # reset flag so event fires again next edit

    # ── E16 — bracket matching ────────────────────────────────────────────────

    def _schedule_bracket_match(self):
        if hasattr(self, "_bm_after") and self._bm_after:
            self.root.after_cancel(self._bm_after)
        self._bm_after = self.root.after(80, self._do_bracket_match)

    def _do_bracket_match(self):
        self._bm_after = None
        self.text.tag_remove("bracket_match", "1.0", tk.END)

        OPEN  = "([{"
        CLOSE = ")]}"
        PAIRS = dict(zip(OPEN, CLOSE))
        RPAIRS = dict(zip(CLOSE, OPEN))

        # Check the character at INSERT and the one just before it
        cur  = self.text.index(tk.INSERT)
        candidates = []
        try:
            ch_at   = self.text.get(cur)
            ch_before = self.text.get(f"{cur}-1c") if self.text.compare(cur, ">", "1.0") else ""
            if ch_at in OPEN or ch_at in CLOSE:
                candidates.append((cur, ch_at))
            elif ch_before in OPEN or ch_before in CLOSE:
                candidates.append((f"{cur}-1c", ch_before))
        except Exception:
            return

        if not candidates:
            return

        pos, ch = candidates[0]
        pos = self.text.index(pos)  # normalise

        try:
            if ch in OPEN:
                # Search forward for matching closer
                target = PAIRS[ch]
                depth  = 1
                idx    = self.text.index(f"{pos}+1c")
                while self.text.compare(idx, "<", tk.END):
                    c = self.text.get(idx)
                    if c == ch:     depth += 1
                    elif c == target:
                        depth -= 1
                        if depth == 0:
                            self.text.tag_add("bracket_match", pos, f"{pos}+1c")
                            self.text.tag_add("bracket_match", idx, f"{idx}+1c")
                            return
                    idx = self.text.index(f"{idx}+1c")
            else:
                # Search backward for matching opener
                target = RPAIRS[ch]
                depth  = 1
                idx    = self.text.index(f"{pos}-1c")
                while self.text.compare(idx, ">=", "1.0"):
                    c = self.text.get(idx)
                    if c == ch:     depth += 1
                    elif c == target:
                        depth -= 1
                        if depth == 0:
                            self.text.tag_add("bracket_match", pos, f"{pos}+1c")
                            self.text.tag_add("bracket_match", idx, f"{idx}+1c")
                            return
                    idx = self.text.index(f"{idx}-1c")
        except Exception:
            pass

    # ── E9 — recent files ─────────────────────────────────────────────────────

    def _push_recent(self, path: str):
        """Prepend path to the MRU list, deduplicate, cap at 10, persist."""
        recents = [p for p in self._recent_files if p != path]
        recents.insert(0, path)
        self._recent_files = recents[:10]
        self.settings.set("recent_files", self._recent_files)

    def _open_recent_menu(self):
        """Show an AntiqueMenu of recent files below the File menu button."""
        file_btn = self.menu_buttons[0]  # "File" is always index 0
        if self.active_antique:
            self.active_antique.close()
        if not self._recent_files:
            items = [{"type": "cmd", "label": "No recent files", "cmd": lambda: None}]
        else:
            items = []
            for path in self._recent_files:
                label = os.path.basename(path)
                # Show full path as the accelerator column
                items.append({
                    "type": "cmd",
                    "label": label,
                    "acc": path if len(path) <= 55 else "…" + path[-52:],
                    "cmd": lambda p=path: self.open_file(p),
                })
            # B6 — allow clearing the MRU list from within the submenu
            items.append({"type": "sep"})
            items.append({
                "type": "cmd",
                "label": "Clear Recent Files",
                "cmd": self._clear_recent_files,
            })
        self.active_antique = AntiqueMenu(self, file_btn, items)
        self.menu_armed = True

    def _clear_recent_files(self):
        """B6 — wipe the MRU list and persist the empty state."""
        self._recent_files = []
        self.settings.set("recent_files", [])
        if self.active_antique:
            self.active_antique.close()

    # ── E13 — passive word highlight ──────────────────────────────────────────

    def _schedule_word_highlight(self):
        if hasattr(self, "_wh_after") and self._wh_after:
            self.root.after_cancel(self._wh_after)
        self._wh_after = self.root.after(400, self._do_word_highlight)

    def _clear_word_highlight(self):
        if hasattr(self, "_wh_after") and self._wh_after:
            self.root.after_cancel(self._wh_after)
            self._wh_after = None
        self.text.tag_remove("word_hi", "1.0", tk.END)

    def _do_word_highlight(self):
        self._wh_after = None
        self.text.tag_remove("word_hi", "1.0", tk.END)

        # ── E25 / E13 — determine the word / phrase to highlight ──────────────
        # Priority: active selection (E25) → word under cursor (E13)
        word           = None
        use_whole_word = True

        try:
            sel_start = self.text.index(tk.SEL_FIRST)
            sel_end   = self.text.index(tk.SEL_LAST)
            selected  = self.text.get(sel_start, sel_end)
            # E25: only highlight if selection is non-trivial, single-line, ≤200 chars
            if selected and "\n" not in selected and 2 <= len(selected) <= 200:
                word = selected
                # Whole-word matching only when the selection is a pure identifier
                use_whole_word = bool(re.match(r"^\w+$", word))
        except tk.TclError:
            pass  # no selection — fall through to E13

        if word is None:
            # E13 — cursor mode: highlight the word the cursor is resting on
            try:
                word_start = self.text.index("insert wordstart")
                word_end   = self.text.index("insert wordend")
                word = self.text.get(word_start, word_end).strip()
            except Exception:
                return
            if len(word) < 2 or not re.match(r"^\w+$", word):
                return
            use_whole_word = True

        # ── viewport-scoped search (±20 lines) ────────────────────────────────
        try:
            first      = self.text.index("@0,0")
            last       = self.text.index(f"@0,{self.text.winfo_height()}")
            scan_start = self.text.index(f"{first} - 20 lines linestart")
            scan_end   = self.text.index(f"{last} + 20 lines lineend")
        except Exception:
            return

        pattern   = (r"\b" + re.escape(word) + r"\b") if use_whole_word else re.escape(word)
        count_var = tk.IntVar()
        idx       = scan_start
        hits      = 0
        try:
            while True:
                pos = self.text.search(pattern, idx, scan_end,
                                       regexp=True, nocase=False, count=count_var)
                if not pos:
                    break
                cnt = count_var.get()
                if cnt <= 0:
                    break
                end = f"{pos}+{cnt}c"
                self.text.tag_add("word_hi", pos, end)
                idx = end
                hits += 1
                if hits > 500:
                    break
        except Exception:
            pass

    # ── toggle_wrap lives here ─────────────────────────────────────────────────

    def toggle_wrap(self):
        # We unmanage the horizontal scrollbar if wrap is ON.
        # If wrap is OFF, we pack it at the bottom.
        if self.word_wrap.get():
            self.text.config(wrap=tk.WORD)
            if self.scrollbar_x.winfo_ismapped():
                self.scrollbar_x.pack_forget()
        else:
            self.text.config(wrap=tk.NONE)
            # Pack at the very bottom of the window, above status bar but below the pane
            if not self.scrollbar_x.winfo_ismapped():
                self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X, before=self.pane)
        
        self.settings.set("word_wrap", self.word_wrap.get())
        self._schedule_ln_update()

    def _toggle_line_numbers(self):
        """Toggle the gutter and separator visibility by re-packing the editor frame.
        We unpack ALL children and repack them in a guaranteed order to avoid
        incorrect overlap or layout calculation race conditions."""
        # Unpack all to ensure clean slate in the editor_frame
        self.gutter.pack_forget()
        self.gutter_sep.pack_forget()
        self.scrollbar_y.pack_forget()
        self.text.pack_forget()

        if self.show_line_nums.get():
            self.gutter.pack(side=tk.LEFT, fill=tk.Y)
            self.gutter_sep.pack(side=tk.LEFT, fill=tk.Y)
        
        # Always pack text and scrollbar back
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Force layout update so the redraw logic sees valid dimensions immediately
        self.root.update_idletasks()
        
        self.settings.set("show_line_nums", self.show_line_nums.get())
        self._schedule_ln_update()

    def zoom_in(self):
        self._zoom_level = min(self._zoom_level + 1, 60)
        self._apply_font()

    def zoom_out(self):
        self._zoom_level = max(self._zoom_level - 1, -self._font_size + 6)
        self._apply_font()

    def zoom_reset(self):
        self._zoom_level = 0
        self._apply_font()

    def toggle_statusbar(self):
        if self.status_bar_visible.get():
            self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        else:
            self.statusbar.pack_forget()
        self.settings.set("status_bar_visible", self.status_bar_visible.get())

    def on_close(self):
        if self._confirm_discard():
            # E8 / E7 — persist geometry and session state before the window dies.
            # Use save_immediate() so the debounce timer doesn't get orphaned.
            self.settings.set("geometry",    self.root.wm_geometry())
            self.settings.set("last_file",   self.current_file)
            self.settings.set("last_cursor", self.text.index(tk.INSERT))
            self.settings.save_immediate()
            self.root.destroy()

def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception: pass

    # E24 — use TkinterDnD root when available so <Drop> events work
    if _DND_AVAILABLE:
        try:
            root = TkinterDnD.Tk()
        except Exception:
            root = tk.Tk()
    else:
        root = tk.Tk()
    app  = Notapad(root)

    # E9 — prune recent files list of any paths that no longer exist on disk
    pruned = [p for p in app._recent_files if os.path.isfile(p)]
    if pruned != app._recent_files:
        app._recent_files = pruned
        app.settings.set("recent_files", pruned)

    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        # Explicit CLI argument wins — open that file
        app.open_file(sys.argv[1])
    else:
        # E7 — restore last session file and cursor position
        last_file   = app.settings.get("last_file")
        last_cursor = app.settings.get("last_cursor") or "1.0"
        if last_file and os.path.isfile(last_file):
            app.open_file(last_file)
            try:
                app.text.mark_set(tk.INSERT, last_cursor)
                app.text.see(last_cursor)
                app._update_status()
            except Exception:
                pass

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
