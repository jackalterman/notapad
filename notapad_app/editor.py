import tkinter as tk
from .config import P, THEMES

MAX_HIGHLIGHT_CHARS = 300_000

def apply_highlight(app):
    app._hl_after = None
    lang = app._language
    if not lang:
        return
    patterns = P.get(lang, [])
    if not patterns:
        return
        
    try:
        first_idx = app.text.index("@0,0")
        last_idx = app.text.index(f"@0,{app.text.winfo_height()}")
        start_check = app.text.index(f"{first_idx} - 40 lines linestart")
        end_check = app.text.index(f"{last_idx} + 40 lines lineend")
    except Exception:
        return
        
    content = app.text.get(start_check, end_check)
    if len(content) > MAX_HIGHLIGHT_CHARS:
        return
        
    for tag in list(app.current_theme["syn"].keys()):
        app.text.tag_remove(tag, start_check, end_check)
        
    for entry in patterns:
        pat, tag = entry[0], entry[1]
        grp = entry[2] if len(entry) > 2 else 0
        try:
            for m in pat.finditer(content):
                s, e = m.start(grp), m.end(grp)
                if s != -1 and s < e:
                    app.text.tag_add(tag, f"{start_check}+{s}c", f"{start_check}+{e}c")
        except Exception:
            pass
    app.text.tag_raise("search_hi")
    app.text.tag_raise("search_cur")
