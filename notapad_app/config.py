import re

APP_NAME  = "Notapad"
MAX_HIGHLIGHT_CHARS = 300_000

# ─── modern design tokens ──────────────────────────────────────────────────
THEMES = {
    "light": {
        "bg_editor": "#ffffff",
        "fg_editor": "#1e1e1e",
        "bg_gutter": "#f3f3f3",
        "fg_gutter": "#999999",
        "bg_status": "#f0f0f0",
        "fg_status": "#333333",
        "sep": "#e0e0e0",
        "bg_input": "#ffffff",
        "accent": "#0078d7",
        "sel_bg": "#add6ff",
        "sel_fg": "#000000",
        "sash": "#e0e0e0",
        "syn": {
            "comment":    "#6A9955",
            "string":     "#A31515",
            "keyword":    "#0000CD",
            "builtin":    "#267F99",
            "number":     "#098658",
            "function":   "#795E26",
            "class_name": "#267F99",
            "decorator":  "#AF00DB",
            "tag":        "#800000",
            "attr":       "#0000FF",
            "key":        "#0451A5",
        }
    },
    "dark": {
        "bg_editor": "#1e1e1e",
        "fg_editor": "#cccccc",
        "bg_gutter": "#1e1e1e",
        "fg_gutter": "#858585",
        "bg_status": "#111111",
        "fg_status": "#999999",
        "sep": "#333333",
        "bg_input": "#2d2d2d",
        "accent": "#007acc",
        "sel_bg": "#264f78",
        "sel_fg": "#ffffff",
        "sash": "#2d2d2d",
        "syn": {
            "comment":    "#6A9955",
            "string":     "#ce9178",
            "keyword":    "#569cd6",
            "builtin":    "#4ec9b0",
            "number":     "#b5cea8",
            "function":   "#dcdcaa",
            "class_name": "#4ec9b0",
            "decorator":  "#dcdcaa",
            "tag":        "#569cd6",
            "attr":       "#9cdcfe",
            "key":        "#9cdcfe",
        }
    }
}

# ─── keyword lists ──────────────────────────────────────────────────────────
def _kw(*w):  return re.compile(r'\b(?:' + '|'.join(w) + r')\b')
def _kwi(*w): return re.compile(r'\b(?:' + '|'.join(w) + r')\b', re.IGNORECASE)

PY_KW  = "False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split()
PY_BI  = "abs all any bin bool bytes callable chr complex delattr dict dir divmod enumerate eval exec filter float format frozenset getattr globals hasattr hash help hex id input int isinstance issubclass iter len list locals map max memoryview min next object oct open ord pow print property range repr reversed round set setattr slice sorted staticmethod str sum super tuple type vars zip".split()
JS_KW  = "break case catch class const continue debugger default delete do else export extends finally for function if import in instanceof let new return static super switch this throw try typeof var void while with yield async await of from true false null undefined NaN Infinity".split()
TS_KW  = JS_KW + "interface type enum namespace keyof infer readonly abstract declare implements satisfies override".split()
SQL_KW = "SELECT FROM WHERE AND OR NOT INSERT INTO VALUES UPDATE SET DELETE CREATE TABLE DROP ALTER ADD PRIMARY KEY FOREIGN REFERENCES INDEX ON JOIN LEFT RIGHT INNER OUTER FULL CROSS GROUP BY ORDER HAVING DISTINCT AS UNION ALL EXISTS IN LIKE BETWEEN IS NULL COUNT SUM AVG MAX MIN LIMIT OFFSET CASE WHEN THEN ELSE END BEGIN COMMIT ROLLBACK TRANSACTION VIEW TRIGGER PROCEDURE FUNCTION DECLARE RETURNS RETURN CAST CONVERT COALESCE NULLIF ISNULL".split()
RUST_KW= "as break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while async await i8 i16 i32 i64 i128 isize u8 u16 u32 u64 u128 usize f32 f64 bool char str String Vec Option Result Some None Ok Err Box Arc Rc".split()
GO_KW  = "break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var true false nil int int8 int16 int32 int64 uint uint8 uint16 uint32 uint64 float32 float64 complex64 complex128 bool byte rune string error".split()
JAVA_KW= "abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null String System Object Integer Double List Map".split()

# ─── pattern table ──────────────────────────────────────────────────────────
P: dict[str, list] = {
"python": [
    (re.compile(r'\b\d+\.?\d*(?:[eE][+-]?\d+)?[jJ]?\b'),          "number"),
    (_kw(*PY_BI),                                                   "builtin"),
    (_kw(*PY_KW),                                                   "keyword"),
    (re.compile(r'@\w+(?:\.\w+)*'),                                 "decorator"),
    (re.compile(r'\bdef\s+(\w+)'),                                  "function",   1),
    (re.compile(r'\bclass\s+(\w+)'),                                "class_name", 1),
    (re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', re.DOTALL),"string"),
    (re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''),        "string"),
    (re.compile(r'#[^\n]*'),                                        "comment"),
],
"javascript": [
    (re.compile(r'\b\d+\.?\d*(?:[eE][+-]?\d+)?n?\b'),              "number"),
    (_kw(*JS_KW),                                                   "keyword"),
    (re.compile(r'`(?:[^`\\]|\\.)*`', re.DOTALL),                  "string"),
    (re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''),        "string"),
    (re.compile(r'//[^\n]*'),                                       "comment"),
    (re.compile(r'/\*[\s\S]*?\*/', re.DOTALL),                     "comment"),
],
"typescript": [
    (re.compile(r'\b\d+\.?\d*(?:[eE][+-]?\d+)?n?\b'),              "number"),
    (_kw(*TS_KW),                                                   "keyword"),
    (re.compile(r'`(?:[^`\\]|\\.)*`', re.DOTALL),                  "string"),
    (re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''),        "string"),
    (re.compile(r'//[^\n]*'),                                       "comment"),
    (re.compile(r'/\*[\s\S]*?\*/', re.DOTALL),                     "comment"),
    (re.compile(r'\binterface\s+(\w+)'),                           "class_name", 1),
    (re.compile(r'\btype\s+(\w+)\s*='),                            "class_name", 1),
    (re.compile(r'\benum\s+(\w+)'),                                "class_name", 1),
],
"json": [
    (re.compile(r'\b-?\d+\.?\d*(?:[eE][+-]?\d+)?\b'),              "number"),
    (re.compile(r'\b(?:true|false|null)\b'),                        "keyword"),
    (re.compile(r'"(?:[^"\\]|\\.)*"'),                              "string"),
    (re.compile(r'"(?:[^"\\]|\\.)*"(?=\s*:)'),                     "key"),
],
"xml": [
    (re.compile(r'"[^"]*"|\'[^\']*\''),                             "string"),
    (re.compile(r'\b[\w:.-]+(?=\s*=)'),                            "attr"),
    (re.compile(r'<[?!/]?\w[\w:.]*|/>|>|<\?[\w]+|\?>'),            "tag"),
    (re.compile(r'<!--[\s\S]*?-->', re.DOTALL),                    "comment"),
],
"html": [
    (re.compile(r'"[^"]*"|\'[^\']*\''),                             "string"),
    (re.compile(r'&[\w#\d]+;'),                                     "builtin"),
    (re.compile(r'\b[\w-]+(?=\s*=)'),                              "attr"),
    (re.compile(r'</?\w[\w:.]*|/>|>|<!DOCTYPE', re.IGNORECASE),    "tag"),
    (re.compile(r'<!--[\s\S]*?-->', re.DOTALL),                    "comment"),
],
"css": [
    (re.compile(r'\b\d+\.?\d*(?:px|em|rem|%|vh|vw|vmin|vmax|pt|cm|mm|s|ms|fr|deg|rad|turn)?\b'), "number"),
    (re.compile(r'#[0-9a-fA-F]{3,8}\b'),                           "number"),
    (re.compile(r'"[^"]*"|\'[^\']*\''),                             "string"),
    (re.compile(r'[\w-]+(?=\s*:(?!:))'),                           "attr"),
    (re.compile(r'[.#:][\w-]+|@[\w-]+|\b\w[\w-]*(?=\s*\{)'),      "keyword"),
    (re.compile(r'/\*[\s\S]*?\*/', re.DOTALL),                     "comment"),
],
"sql": [
    (re.compile(r'\b\d+\.?\d*\b'),                                  "number"),
    (_kwi(*SQL_KW),                                                 "keyword"),
    (re.compile(r"'(?:[^'\\]|\\.)*'"),                              "string"),
    (re.compile(r'--[^\n]*'),                                       "comment"),
    (re.compile(r'/\*[\s\S]*?\*/', re.DOTALL),                     "comment"),
],
"shell": [
    (re.compile(r'\b\d+\b'),                                        "number"),
    (re.compile(r'\b(?:if|then|else|elif|fi|for|while|until|do|done|case|esac|function|select|in|return|exit|break|continue|shift|trap|wait|exec|source|local|export|readonly|declare|unset|set|true|false)\b'), "keyword"),
    (re.compile(r'\$(?:\{[^}]*\}|\w+|[#?@*!$0-9])'),              "builtin"),
    (re.compile(r'"(?:[^"\\]|\\.)*"'),                              "string"),
    (re.compile(r"'[^']*'"),                                        "string"),
    (re.compile(r'#[^\n]*'),                                        "comment"),
],
"markdown": [
    (re.compile(r'```[\s\S]*?```|`[^`\n]+`', re.DOTALL),          "string"),
    (re.compile(r'^>{1,}\s.*$', re.MULTILINE),                     "comment"),
    (re.compile(r'\[([^\]]+)\]\([^\)]*\)'),                        "attr"),
    (re.compile(r'\*\*[^*\n]+\*\*|__[^_\n]+__'),                  "keyword"),
    (re.compile(r'(?<!\*)\*[^*\n]+\*(?!\*)|(?<!_)_[^_\n]+_(?!_)'),"builtin"),
    (re.compile(r'^#{1,6}\s.*$', re.MULTILINE),                    "function"),
    (re.compile(r'^\s*[-*+]\s|^\s*\d+\.\s', re.MULTILINE),        "number"),
],
"yaml": [
    (re.compile(r'\b-?\d+\.?\d*\b'),                                "number"),
    (re.compile(r'\b(?:true|false|null|yes|no|on|off)\b', re.I),   "keyword"),
    (re.compile(r'^[ \t]*(?:\w[\w ]*\w|\w)\s*(?=:)', re.MULTILINE),"key"),
    (re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''),        "string"),
    (re.compile(r'^---$|^\.\.\.$', re.MULTILINE),                  "decorator"),
    (re.compile(r'#[^\n]*'),                                        "comment"),
],
"toml": [
    (re.compile(r'\b-?\d+\.?\d*\b'),                                "number"),
    (re.compile(r'\b(?:true|false)\b'),                             "keyword"),
    (re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', re.DOTALL),"string"),
    (re.compile(r'"(?:[^"\\]|\\.)*"|\'[^\']*\''),                  "string"),
    (re.compile(r'^\[{1,2}[\w.\s"\']+\]{1,2}$', re.MULTILINE),    "keyword"),
    (re.compile(r'^\w[\w.-]*\s*=', re.MULTILINE),                  "key"),
    (re.compile(r'#[^\n]*'),                                        "comment"),
],
"rust": [
    (re.compile(r'\b\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?(?:_?[iu]\d{1,3}|_?f\d{2})?\b'), "number"),
    (_kw(*RUST_KW),                                                 "keyword"),
    (re.compile(r'#!\?\[[\s\S]*?\]|#\[[\s\S]*?\]'),               "decorator"),
    (re.compile(r'"(?:[^"\\]|\\.)*"'),                              "string"),
    (re.compile(r"b?'(?:[^'\\]|\\.)'"),                            "string"),
    (re.compile(r'//[^\n]*'),                                       "comment"),
    (re.compile(r'/\*[\s\S]*?\*/', re.DOTALL),                     "comment"),
],
"go": [
    (re.compile(r'\b\d+\.?\d*(?:[eE][+-]?\d+)?\b'),                "number"),
    (_kw(*GO_KW),                                                   "keyword"),
    (re.compile(r'`[^`]*`', re.DOTALL),                            "string"),
    (re.compile(r'"(?:[^"\\]|\\.)*"'),                              "string"),
    (re.compile(r"'(?:[^'\\]|\\.)'"),                              "string"),
    (re.compile(r'//[^\n]*'),                                       "comment"),
    (re.compile(r'/\*[\s\S]*?\*/', re.DOTALL),                     "comment"),
],
"java": [
    (re.compile(r'\b\d+\.?\d*[lLfFdD]?\b'),                        "number"),
    (_kw(*JAVA_KW),                                                 "keyword"),
    (re.compile(r'@\w+'),                                           "decorator"),
    (re.compile(r'\bclass\s+(\w+)'),                               "class_name", 1),
    (re.compile(r'\b[A-Z]\w*\b'),                                  "class_name"),
    (re.compile(r'"(?:[^"\\]|\\.)*"'),                              "string"),
    (re.compile(r"'(?:[^'\\]|\\.)'"),                              "string"),
    (re.compile(r'//[^\n]*'),                                       "comment"),
    (re.compile(r'/\*[\s\S]*?\*/', re.DOTALL),                     "comment"),
],
"ini": [
    (re.compile(r'"[^"]*"|\'[^\']*\''),                             "string"),
    (re.compile(r'^\w[\w\s.]*\s*[=:]', re.MULTILINE),             "key"),
    (re.compile(r'^\[[\w\s.]+\]$', re.MULTILINE),                 "keyword"),
    (re.compile(r'^[;#][^\n]*', re.MULTILINE),                     "comment"),
],
"batch": [
    (re.compile(r'\b\d+\b'),                                        "number"),
    (re.compile(r'%(?:~?\d|\w+)%|%%\w+'),                         "builtin"),
    (re.compile(r'"[^"]*"'),                                        "string"),
    (re.compile(r'(?i)\b(?:echo|set|if|else|for|do|goto|call|exit|pause|cd|dir|copy|del|ren|md|rd|cls|start|title|color|pushd|popd|shift|type|find|sort|more|choice|timeout|where|reg|sc|tasklist|taskkill|net|setlocal|endlocal|defined|not|exist|errorlevel|in)\b'), "keyword"),
    (re.compile(r'(?i)^@?rem\b[^\n]*|^::[^\n]*', re.MULTILINE),   "comment"),
],
}

EXT_LANG = {
    ".py":"python",".pyw":"python",".pyi":"python",
    ".js":"javascript",".jsx":"javascript",".mjs":"javascript",".cjs":"javascript",
    ".ts":"typescript",".tsx":"typescript",
    ".json":"json",".jsonc":"json",
    ".xml":"xml",".svg":"xml",".xaml":"xml",".xsl":"xml",".xslt":"xml",".rss":"xml",
    ".html":"html",".htm":"html",".xhtml":"html",
    ".css":"css",".scss":"css",".less":"css",
    ".sql":"sql",
    ".sh":"shell",".bash":"shell",".zsh":"shell",".fish":"shell",
    ".md":"markdown",".markdown":"markdown",
    ".yaml":"yaml",".yml":"yaml",
    ".toml":"toml",
    ".rs":"rust",
    ".go":"go",
    ".java":"java",
    ".bat":"batch",".cmd":"batch",
    ".ini":"ini",".cfg":"ini",".conf":"ini",".properties":"ini",
}

LANG_LABEL = {
    None:"Plain Text","python":"Python","javascript":"JavaScript",
    "typescript":"TypeScript",
    "json":"JSON","xml":"XML","html":"HTML","css":"CSS","sql":"SQL",
    "shell":"Shell","markdown":"Markdown","yaml":"YAML","toml":"TOML",
    "rust":"Rust","go":"Go","java":"Java","ini":"INI / Config","batch":"Batch",
}
