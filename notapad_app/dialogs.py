import tkinter as tk
from tkinter import ttk, font, messagebox
from .ui_engine import apply_windows_title_bar, AntiqueMenu
import re

APP_NAME  = "Notapad"

def _is_dark_mode(app):
    theme_key = app._theme_mode.get()
    if theme_key == "system":
        return app._get_system_theme() == "dark"
    return theme_key == "dark"

def _apply_dialog_theme(app, win, body, footer):
    t = app.current_theme
    win.configure(bg=t["bg_editor"])
    body.configure(bg=t["bg_editor"])
    footer.configure(bg=t["bg_status"])
    
    def _recurse(w, bg, fg):
        try:
            wclass = w.winfo_class()
            if wclass in ("Frame", "Label", "Checkbutton", "Radiobutton"):
                w.configure(bg=bg)
                if wclass != "Frame" and wclass != "TButton": w.configure(fg=fg)
            for child in w.winfo_children():
                _recurse(child, bg, fg)
        except: pass
    
    _recurse(body, t["bg_editor"], t["fg_editor"])
    _recurse(footer, t["bg_status"], t["fg_status"])

def _create_styled_button(parent, text, command, theme, is_primary=False, width=12):
    bg = theme["accent"] if is_primary else theme["bg_status"]
    fg = "#ffffff" if is_primary else theme["fg_status"]
    active_bg = "#185abd" if is_primary else theme["sep"]
    
    btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                    relief=tk.FLAT, activebackground=active_bg,
                    font=("Segoe UI", 9, "bold" if is_primary else "normal"),
                    width=width, pady=5)
    return btn

def open_find(app):
    if app.search_window and app.search_window.winfo_exists():
        app.search_window.lift()
        app.search_window.focus_force()
        return

    top = tk.Toplevel(app.root)
    top.title("Find")
    top.resizable(False, False)
    top.transient(app.root)
    app.search_window = top

    t = app.current_theme
    top.configure(bg=t["bg_editor"])

    body = tk.Frame(top, bg=t["bg_editor"], padx=25, pady=20)
    body.pack(fill=tk.BOTH, expand=True)
    footer = tk.Frame(top, bg=t["bg_status"], height=65, pady=12, padx=15)
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Input row
    tk.Label(body, text="Search for:", font=("Segoe UI", 10, "bold"), bg=t["bg_editor"], fg=t["fg_editor"]).grid(row=0, column=0, sticky="w", pady=(0,5))
    fv = tk.StringVar(value=app.search_last_term)
    ent = tk.Entry(body, textvariable=fv, font=("Segoe UI", 10), bg=t.get("bg_input", t["bg_gutter"]), fg=t["fg_editor"], 
                    insertbackground=t["fg_editor"], relief=tk.FLAT, bd=4, width=32)
    ent.grid(row=1, column=0, sticky="ew", pady=(0, 15))
    ent.focus(); ent.select_range(0, tk.END)

    # Options frame
    opt_f = tk.Frame(body, bg=t["bg_editor"])
    opt_f.grid(row=2, column=0, sticky="w")
    
    chk_opts = {"bg":t["bg_editor"], "fg":t["fg_editor"], "selectcolor":t["bg_status"], 
                "activebackground":t["bg_editor"], "activeforeground":t["accent"], "font":("Segoe UI", 9)}
    
    tk.Checkbutton(opt_f, text="Match case", variable=app.search_case, **chk_opts).grid(row=0, column=0, sticky="w", padx=(0,10))
    tk.Checkbutton(opt_f, text="Regex", variable=app.search_regex, **chk_opts).grid(row=0, column=1, sticky="w", padx=10)
    tk.Checkbutton(opt_f, text="Whole word", variable=app.search_whole, **chk_opts).grid(row=0, column=2, sticky="w", padx=10)

    # Status
    app.search_count_lbl = tk.Label(body, text="", font=("Segoe UI", 9, "italic"), bg=t["bg_editor"], fg=t["accent"], anchor="w")
    app.search_count_lbl.grid(row=3, column=0, sticky="w", pady=(15,0))

    def do_next():
        if fv.get():
            if fv.get() != app.search_last_term: app._do_search(fv.get())
            else:
                if app.search_dir.get() == "down": app.find_next()
                else:                              app.find_prev()

    def on_type(*_):
            if app.search_after_id: app.root.after_cancel(app.search_after_id)
            app.search_after_id = app.root.after(200, lambda: app._do_search(fv.get()))
    fv.trace_add("write", on_type)

    _create_styled_button(footer, "Cancel", top.destroy, t).pack(side=tk.RIGHT, padx=5)
    _create_styled_button(footer, "Find All", lambda: app.find_all(fv.get()), t).pack(side=tk.RIGHT, padx=5)
    _create_styled_button(footer, "Find Next", do_next, t, is_primary=True).pack(side=tk.RIGHT, padx=5)
    
    # Title Bar based on theme
    apply_windows_title_bar(top, _is_dark_mode(app))
    
    top.update_idletasks()
    app._center_window(top)
    
    ent.bind("<Return>", lambda e: do_next())
    top.bind("<Escape>", lambda e: top.destroy())

    def _cleanup():
        app.search_count_lbl = None
        app.search_window = None
        app._clear_highlights()
    top.protocol("WM_DELETE_WINDOW", lambda: (top.destroy(), _cleanup()))

def open_replace(app):
    if app.search_window and app.search_window.winfo_exists():
        app.search_window.lift()
        app.search_window.focus_force()
        return

    top = tk.Toplevel(app.root)
    top.title("Replace")
    top.resizable(False, False)
    top.transient(app.root)
    app.search_window = top
    
    t = app.current_theme
    top.configure(bg=t["bg_editor"])

    body = tk.Frame(top, bg=t["bg_editor"], padx=25, pady=20)
    body.pack(fill=tk.BOTH, expand=True)
    footer = tk.Frame(top, bg=t["bg_status"], height=65, pady=12, padx=15)
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    lbl_opts = {"bg":t["bg_editor"], "fg":t["fg_editor"], "font":("Segoe UI", 10)}
    ent_opts = {"bg":t.get("bg_input", t["bg_gutter"]), "fg":t["fg_editor"], "insertbackground":t["fg_editor"], "relief":tk.FLAT, "bd":4, "font":("Segoe UI", 10)}

    tk.Label(body, text="Find what:", anchor="w", **lbl_opts).grid(row=0, column=0, sticky="w", pady=(0,4))
    fv = tk.StringVar(value=app.search_last_term)
    fe = tk.Entry(body, textvariable=fv, width=32, **ent_opts)
    fe.grid(row=1, column=0, sticky="ew", pady=(0, 10))
    fe.focus(); fe.select_range(0, tk.END)

    tk.Label(body, text="Replace with:", anchor="w", **lbl_opts).grid(row=2, column=0, sticky="w", pady=(0,4))
    rv = tk.StringVar()
    rep_ent = tk.Entry(body, textvariable=rv, width=32, **ent_opts)
    rep_ent.grid(row=3, column=0, sticky="ew", pady=(0, 15))

    chk_opts = {"bg":t["bg_editor"], "fg":t["fg_editor"], "selectcolor":t["bg_status"], 
                "activebackground":t["bg_editor"], "activeforeground":t["accent"], "font":("Segoe UI", 9)}
    
    opt_f = tk.Frame(body, bg=t["bg_editor"])
    opt_f.grid(row=4, column=0, sticky="w")
    tk.Checkbutton(opt_f, text="Match case", variable=app.search_case, **chk_opts).grid(row=0, column=0, sticky="w", padx=(0,10))
    tk.Checkbutton(opt_f, text="Regex", variable=app.search_regex, **chk_opts).grid(row=0, column=1, sticky="w", padx=10)
    tk.Checkbutton(opt_f, text="Whole word", variable=app.search_whole, **chk_opts).grid(row=0, column=2, sticky="w", padx=10)

    app.search_count_lbl = tk.Label(body, text="", font=("Segoe UI", 9, "italic"), bg=t["bg_editor"], fg=t["accent"], anchor="w")
    app.search_count_lbl.grid(row=5, column=0, sticky="w", pady=(15,0))

    def do_find():
        if fv.get(): app._do_search(fv.get())

    def do_replace():
        if not fv.get(): return
        if not app._match_positions: app._do_search(fv.get())
        if app._match_positions:
            s, e = app._match_positions[app._match_current]
            app.text.delete(s, e)
            app.text.insert(s, rv.get())
            app._do_search(fv.get())

    def do_replace_all():
        term = fv.get()
        if not term: return
        content = app.text.get("1.0", tk.END)
        flags = 0 if app.search_case.get() else re.IGNORECASE
        pattern = term
        if app.search_whole.get() and not app.search_regex.get():
            pattern = r'\b' + re.escape(term) + r'\b'
        elif app.search_whole.get() and app.search_regex.get():
            pattern = r'\b(?:' + term + r')\b'
        elif not app.search_regex.get():
            pattern = re.escape(term)

        try:
            matches = re.findall(pattern, content, flags=flags)
            count = len(matches)
            if count == 0:
                messagebox.showinfo(APP_NAME, "No matches found.", parent=top)
                return
            new_content = re.sub(pattern, rv.get().replace("\\", "\\\\"), content, flags=flags)
            # Bracket the replacement as a single undoable unit so the undo stack
            # is preserved. One Ctrl+Z will reverse the entire Replace All.
            app.text.config(autoseparators=False)
            app.text.edit_separator()
            app.text.delete("1.0", tk.END)
            app.text.insert("1.0", new_content)
            app.text.edit_separator()
            app.text.config(autoseparators=True)
            app._clear_highlights()
            messagebox.showinfo(APP_NAME, f"{count} replacement(s) made.", parent=top)
        except Exception as e:
            app.text.config(autoseparators=True)  # always restore on error
            messagebox.showerror("Regex Error", str(e), parent=top)

    def on_type(*_):
        if app.search_after_id: app.root.after_cancel(app.search_after_id)
        app.search_after_id = app.root.after(200, lambda: app._do_search(fv.get()))

    fv.trace_add("write", on_type)

    _create_styled_button(footer, "Cancel", top.destroy, t).pack(side=tk.RIGHT, padx=5)
    _create_styled_button(footer, "Replace All", do_replace_all, t).pack(side=tk.RIGHT, padx=5)
    _create_styled_button(footer, "Replace", do_replace, t, is_primary=True).pack(side=tk.RIGHT, padx=5)
    
    apply_windows_title_bar(top, _is_dark_mode(app))
    top.update_idletasks()
    app._center_window(top)
    app._do_search(fv.get())
    
    def _cleanup():
        app.search_count_lbl = None
        app.search_window = None
        app._clear_highlights()
    top.protocol("WM_DELETE_WINDOW", lambda: (top.destroy(), _cleanup()))
    top.bind("<Escape>", lambda e: top.destroy())
    fe.bind("<Return>",  lambda e: do_find())

def goto_line(app):
    total = int(app.text.index(tk.END).split(".")[0]) - 1
    top = tk.Toplevel(app.root)
    top.title("Go To Line")
    top.resizable(False, False)
    top.transient(app.root)
    
    t = app.current_theme
    top.configure(bg=t["bg_editor"])
    body = tk.Frame(top, bg=t["bg_editor"], padx=25, pady=20)
    body.pack(fill=tk.BOTH, expand=True)
    footer = tk.Frame(top, bg=t["bg_status"], height=65, pady=12, padx=15)
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    
    tk.Label(body, text=f"Line number (1 – {total}):", font=("Segoe UI", 10), bg=t["bg_editor"], fg=t["fg_editor"]).grid(row=0, column=0, sticky="w", pady=(0, 5))
    lv = tk.StringVar(value=str(int(app.text.index(tk.INSERT).split(".")[0])))
    ent = tk.Entry(body, textvariable=lv, font=("Segoe UI", 10), bg=t.get("bg_input", t["bg_gutter"]), fg=t["fg_editor"], 
                    insertbackground=t["fg_editor"], relief=tk.FLAT, bd=4, width=24)
    ent.grid(row=1, column=0, sticky="ew")
    ent.focus(); ent.select_range(0, tk.END)

    def do_go():
        try:
            line = int(lv.get())
            if 1 <= line <= total:
                app.text.mark_set(tk.INSERT, f"{line}.0")
                app.text.see(f"{line}.0")
                app._update_status()
                top.destroy()
            else:
                messagebox.showwarning("Go To", f"Please enter a line between 1 and {total}", parent=top)
        except ValueError: pass

    _create_styled_button(footer, "Cancel", top.destroy, t).pack(side=tk.RIGHT, padx=5)
    _create_styled_button(footer, "Go To", do_go, t, is_primary=True).pack(side=tk.RIGHT, padx=5)
    
    apply_windows_title_bar(top, _is_dark_mode(app))
    top.update_idletasks()
    app._center_window(top)
    ent.bind("<Return>", lambda e: do_go())
    top.bind("<Escape>", lambda e: top.destroy())

def choose_font(app):
    top = tk.Toplevel(app.root)
    top.title("Font Selection")
    top.resizable(False, False)
    top.grab_set()
    top.transient(app.root)

    t = app.current_theme
    top.configure(bg=t["bg_editor"])

    body = tk.Frame(top, bg=t["bg_editor"], padx=25, pady=20)
    body.pack(fill=tk.BOTH, expand=True)
    footer = tk.Frame(top, bg=t["bg_status"], height=65, pady=12, padx=15)
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    tk.Label(body, text="Font family:", font=("Segoe UI", 9), bg=t["bg_editor"], fg=t["fg_editor"]).grid(row=0, column=0, sticky="w", pady=4, padx=(0,10))
    fam_var = tk.StringVar(value=app._font_family)
    fam_cb  = ttk.Combobox(body, textvariable=fam_var,
                            values=sorted(font.families()), width=26, state="readonly")
    fam_cb.grid(row=0, column=1, sticky="w", pady=4)

    tk.Label(body, text="Size:", font=("Segoe UI", 9), bg=t["bg_editor"], fg=t["fg_editor"]).grid(row=1, column=0, sticky="w", pady=4, padx=(0,10))
    size_var = tk.IntVar(value=app._font_size)
    ttk.Spinbox(body, from_=6, to=72, textvariable=size_var, width=8).grid(
        row=1, column=1, sticky="w", pady=4)

    pf = font.Font(family=fam_var.get(), size=size_var.get())
    prev = tk.Label(body,
        text="The quick brown fox jumps over the lazy dog\n0 1 2 3 4 5 6 7 8 9",
        font=pf, bg=t["bg_gutter"], fg=t["fg_editor"], padx=15, pady=15, anchor="w", justify="left")
    prev.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(15, 0))

    def refresh(*_):
        try: pf.config(family=fam_var.get(), size=int(size_var.get()))
        except: pass
    fam_cb.bind("<<ComboboxSelected>>", refresh)
    size_var.trace_add("write", refresh)

    def apply():
        app._font_family = fam_var.get()
        app._font_size   = int(size_var.get())
        app._apply_font()
        top.destroy()

    _create_styled_button(footer, "Cancel", top.destroy, t).pack(side=tk.RIGHT, padx=5)
    _create_styled_button(footer, "OK", apply, t, is_primary=True).pack(side=tk.RIGHT, padx=5)

    apply_windows_title_bar(top, _is_dark_mode(app))
    top.update_idletasks()
    app._center_window(top)
    top.bind("<Return>", lambda e: apply())
    top.bind("<Escape>", lambda e: top.destroy())

def show_appearance_submenu(app):
    items = [
        {"type":"cmd", "label":"System Default", "cmd":lambda: app.set_theme_mode("system")},
        {"type":"cmd", "label":"Arctic Glass (Light)", "cmd":lambda: app.set_theme_mode("light")},
        {"type":"cmd", "label":"Midnight Aurora (Dark)", "cmd":lambda: app.set_theme_mode("dark")}
    ]
    btn = app.menu_buttons[3] if len(app.menu_buttons) > 3 else app.menu_buttons[0]
    if app.active_antique: app.active_antique.close()
    app.active_antique = AntiqueMenu(app, btn, items)

def show_about(app):
    top = tk.Toplevel(app.root)
    top.title(f"About {APP_NAME}")
    top.resizable(False, False)
    top.transient(app.root)
    
    t = app.current_theme
    top.configure(bg=t["bg_editor"])
    body = tk.Frame(top, bg=t["bg_editor"], padx=35, pady=30)
    body.pack(fill=tk.BOTH, expand=True)
    
    tk.Label(body, text=APP_NAME, font=("Segoe UI", 24, "bold"), bg=t["bg_editor"], fg=t["accent"]).pack()
    tk.Label(body, text="v2.5.0 Modern Edition", font=("Segoe UI", 10), bg=t["bg_editor"], fg=t["fg_gutter"]).pack(pady=(0, 20))
    
    desc = "A polished Notepad clone for the modern era.\nBuilt with Antique UI Engine."
    tk.Label(body, text=desc, font=("Segoe UI", 10), bg=t["bg_editor"], fg=t["fg_editor"]).pack()
    
    _create_styled_button(body, "Close", top.destroy, t).pack(side=tk.BOTTOM, pady=15)

    apply_windows_title_bar(top, _is_dark_mode(app))
    top.update_idletasks()
    app._center_window(top)
    top.bind("<Escape>", lambda e: top.destroy())
    top.bind("<Return>", lambda e: top.destroy())
