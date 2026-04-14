import tkinter as tk
from .config import P, THEMES

MAX_HIGHLIGHT_CHARS = 300_000


def apply_highlight(app):
    """E6 — dirty-region-aware syntax highlighter.

    Visible range: viewport_top − 20 lines to viewport_bottom + 5 lines.
    Dirty extension: if the user edited outside that window (app._dirty_line),
    the region is extended downward to the nearest 'safe' restart point
    (blank line, end-of-block-comment marker, or ±60-line cap) so that
    multi-line constructs below the viewport are kept up to date.
    """
    app._hl_after = None
    lang = app._language
    if not lang:
        return
    patterns = P.get(lang, [])
    if not patterns:
        return

    try:
        first_idx = app.text.index("@0,0")
        last_idx  = app.text.index(f"@0,{app.text.winfo_height()}")
        vp_top    = int(first_idx.split(".")[0])
        vp_bot    = int(last_idx.split(".")[0])
    except Exception:
        return

    # Base region: visible viewport with a modest upward padding.
    # 20 lines above the viewport handles most block comments that started
    # just off-screen; 5 lines below is enough for the normal typing case.
    region_start = max(1, vp_top - 20)
    region_end   = vp_bot + 5

    # E6 — dirty-line extension: expand the end of the region to cover
    # any multi-line construct that was broken by the last edit.
    dirty = getattr(app, "_dirty_line", None)
    if dirty is not None:
        # If the edit was above the viewport start, pull the region up too
        region_start = min(region_start, max(1, dirty - 2))
        safe_end = _find_safe_end(app, dirty, vp_bot)
        region_end = max(region_end, safe_end)

    try:
        start_check = app.text.index(f"{region_start}.0 linestart")
        end_check   = app.text.index(f"{region_end}.0 lineend")
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

    # E6 — clear the dirty marker now that we've incorporated it
    app._dirty_line = None


def _find_safe_end(app, dirty_line: int, viewport_bottom: int) -> int:
    """Return the line number of the nearest 'safe' re-highlight boundary
    below dirty_line.  A safe line is one where lexer state is deterministic:
    a blank line or the line that ends a block comment.  Caps at
    dirty_line + 60 (or file end), whichever comes first.

    Uses a single text.get() call to minimise Tcl round-trips.
    """
    cap = max(dirty_line + 60, viewport_bottom + 5)
    try:
        total_lines = int(app.text.index("end").split(".")[0])
        cap = min(cap, total_lines)
        # Fetch the whole range in one shot
        block = app.text.get(f"{dirty_line + 1}.0", f"{cap}.end")
        for i, line in enumerate(block.split("\n")):
            ln = dirty_line + 1 + i
            stripped = line.rstrip()
            if not stripped:                          # blank line — safe restart
                return ln
            if "*/" in stripped or "-->" in stripped: # end of block comment
                return ln + 1
    except Exception:
        pass
    return cap
