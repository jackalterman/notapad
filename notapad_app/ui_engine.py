import tkinter as tk
import sys
import ctypes

def apply_windows_title_bar(win, dark: bool):
    """Set Win10/11 title bar of any window to dark mode."""
    if sys.platform != "win32": return
    try:
        win.update()
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win11) or 19 (Win10)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        get_parent = ctypes.windll.user32.GetParent
        hwnd = get_parent(win.winfo_id())
        rendering_policy = ctypes.c_int(2 if dark else 0)
        set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
    except Exception:
        pass

class AntiqueMenu(tk.Frame):
    def __init__(self, parent_app, parent_btn, menu_def):
        t = parent_app.current_theme
        super().__init__(parent_app.root, bg=t["bg_status"], bd=1, highlightbackground=t["sep"], highlightthickness=1)
        self.app = parent_app
        self.parent_btn = parent_btn
        self.menu_def = menu_def
        
        self.frame = tk.Frame(self, bg=t["bg_status"], padx=1, pady=1)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.items = []
        self._build()
        
        # Position using .place() relative to root
        x = parent_btn.winfo_rootx() - parent_app.root.winfo_rootx()
        y = parent_btn.winfo_rooty() + parent_btn.winfo_height() - parent_app.root.winfo_rooty()
        self.place(x=max(0, x), y=max(0, y))
        self.tkraise()

    def _build(self):
        t = self.app.current_theme
        for item in self.menu_def:
            if item["type"] == "sep":
                s = tk.Frame(self.frame, height=1, bg=t["sep"], pady=3)
                s.pack(fill=tk.X, padx=10)
                continue
            
            f = tk.Frame(self.frame, bg=t["bg_status"], cursor="hand2")
            f.pack(fill=tk.X)
            
            # Indicator space (checkmarks/bullets)
            ind = tk.Label(f, text="", font=("Segoe UI Symbol", 9), bg=t["bg_status"], fg=t["accent"], width=3)
            ind.pack(side=tk.LEFT)
            
            # Label
            lbl = tk.Label(f, text=item["label"], font=("Segoe UI", 10), bg=t["bg_status"], fg=t["fg_status"], anchor="w", padx=10, pady=5)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Accelerator
            acc = tk.Label(f, text=item.get("acc", ""), font=("Segoe UI", 9), bg=t["bg_status"], fg=t["fg_gutter"], anchor="e", padx=10)
            acc.pack(side=tk.RIGHT)
            
            # Logic for checkmarks
            var = item.get("var")
            val = item.get("val")
            if var:
                if isinstance(var, tk.BooleanVar) and var.get():
                    ind.config(text="✔")
                elif isinstance(var, tk.StringVar) and var.get() == val:
                    ind.config(text="●")

            # Hover events
            def _enter(e, frame=f, ind=ind, lbl=lbl, acc=acc):
                frame.config(bg=t["accent"])
                for l in (ind, lbl, acc): l.config(bg=t["accent"], fg="#ffffff")
            def _leave(e, frame=f, ind=ind, lbl=lbl, acc=acc, it=item):
                frame.config(bg=t["bg_status"])
                ind.config(bg=t["bg_status"], fg=t["accent"])
                lbl.config(bg=t["bg_status"], fg=t["fg_status"])
                acc.config(bg=t["bg_status"], fg=t["fg_gutter"])
            
            f.bind("<Enter>", _enter)
            f.bind("<Leave>", _leave)
            
            # Interaction
            def _click(e, it=item):
                self.close()
                if "var" in it:
                    if isinstance(it["var"], tk.BooleanVar):
                        it["var"].set(not it["var"].get())
                    else:
                        it["var"].set(it.get("val", ""))
                if "cmd" in it:
                    it["cmd"]()
                return "break"
            
            for w in (f, ind, lbl, acc): w.bind("<Button-1>", _click)

    def close(self):
        self.app.menu_armed = False
        btn = self.parent_btn
        self.app.active_antique = None
        self.place_forget()
        self.destroy()
        if btn and btn.winfo_exists():
            btn.config(bg=self.app.current_theme["bg_status"], fg=self.app.current_theme["fg_status"])
