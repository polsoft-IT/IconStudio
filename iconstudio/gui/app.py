import os
import sys
import json
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from PIL import Image, ImageTk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iconlib.engine import IconLibrary
from iconlib.history import IconLibraryHistory

# --- Palette (single source of truth for visual consistency) ---
DARK = {
    "BG": "#1e1e2e",        # window background
    "BG_DEEP": "#181825",   # deepest surface (preview stage)
    "SURFACE": "#313244",   # cards, inputs, rows
    "SURFACE_2": "#45475a",  # borders, hover
    "STRIPE": "#2a2b3e",    # alternating row tint
    "OVERLAY": "#585b70",   # subtle text / inactive
    "TEXT": "#cdd6f4",      # primary text
    "SUBTEXT": "#a6adc8",   # secondary text
    "ACCENT": "#89b4fa",    # primary accent
    "ACCENT_2": "#74c7ec",  # accent hover
    "GREEN": "#a6e3a1",
    "YELLOW": "#f9e2af",
    "RED": "#f38ba8",
    "SHADOW": "#12121b",    # drop shadow under previews / logo
    "CHECKER_1": "#20202f",  # transparency checkerboard
    "CHECKER_2": "#1a1a27",
}

LIGHT = {
    "BG": "#eff1f5",
    "BG_DEEP": "#e6e9ef",
    "SURFACE": "#ffffff",
    "SURFACE_2": "#ccd0da",
    "STRIPE": "#f3f5f9",
    "OVERLAY": "#9ca0b0",
    "TEXT": "#4c4f69",
    "SUBTEXT": "#6c6f85",
    "ACCENT": "#1e66f5",
    "ACCENT_2": "#209fb5",
    "GREEN": "#40a02b",
    "YELLOW": "#df8e1d",
    "RED": "#d20f39",
    "SHADOW": "#c6cad4",
    "CHECKER_1": "#ffffff",
    "CHECKER_2": "#e2e6ee",
}

_PALETTE_KEYS = tuple(DARK)

# Active palette values (rebound by apply_palette()).
BG = BG_DEEP = SURFACE = SURFACE_2 = STRIPE = OVERLAY = None
TEXT = SUBTEXT = ACCENT = ACCENT_2 = GREEN = YELLOW = RED = None
SHADOW = CHECKER_1 = CHECKER_2 = None


def apply_palette(mode="light"):
    """Rebind the module-level colour constants to the chosen palette."""
    p = LIGHT if mode == "light" else DARK
    g = globals()
    for key in _PALETTE_KEYS:
        g[key] = p[key]


apply_palette("light")

FONT_UI    = ("Segoe UI", 9)
FONT_BOLD  = ("Segoe UI Semibold", 9)
FONT_TITLE = ("Segoe UI Semibold", 14)
FONT_MONO  = ("Consolas", 9)

APP_VERSION = "1.0"

PRESETS = ["fluent_light", "fluent_dark", "monochrome", "high_contrast", "pastel", "classic_xp"]
STYLES = ["fluent", "classic", "monochrome"]


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle on a Tk canvas."""
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2,
        x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return cv.create_polygon(pts, smooth=True, **kw)


class StatusBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=SURFACE, height=26, **kw)
        self.pack_propagate(False)
        self.dot = tk.Label(self, text="\u25CF", bg=SURFACE, fg=GREEN,
                            font=("Segoe UI", 10))
        self.dot.pack(side=tk.LEFT, padx=(10, 4))
        self.label = tk.Label(self, text="Ready", anchor="w", bg=SURFACE,
                              fg=SUBTEXT, font=FONT_UI)
        self.label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.right = tk.Label(self, text="", anchor="e", bg=SURFACE,
                              fg=OVERLAY, font=FONT_MONO)
        self.right.pack(side=tk.RIGHT, padx=10)

    def set(self, msg, level="info"):
        color = {"info": GREEN, "warn": YELLOW, "error": RED,
                 "busy": ACCENT}.get(level, GREEN)
        self.dot.config(fg=color)
        self.label.config(text=msg, fg=TEXT)

    def set_right(self, msg):
        self.right.config(text=msg)


class IconLibraryGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Icon Studio Manager")
        self.root.minsize(1000, 660)
        
        # Ustaw ikonę okna aplikacji
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "ilm.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.library = IconLibrary()
        self.iconstudio = self.library
        self.history = IconLibraryHistory()
        self.cache = None
        self.current_preview = None
        self._search_active = False
        self._search_results = []
        self._thumb_refs = []
        self._ph_empty = ImageTk.PhotoImage(Image.new("RGBA", (28, 28), (0, 0, 0, 0)))
        self._current_path = None
        self._preview_sizes = (128, 184, 240)
        self._preview_idx = 1
        self._mode = "light"
        self._clock_started = False

        apply_palette(self._mode)
        self._apply_theme()
        self.build_ui()
        self._tick_clock()

    def _apply_theme(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        self.root.configure(bg=BG)

        style.configure(".", background=BG, foreground=TEXT, font=FONT_UI,
                        focuscolor=ACCENT)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=SUBTEXT)
        style.configure("Accent.TLabel", background=BG, foreground=ACCENT)

        # Buttons
        style.configure("TButton", background=SURFACE, foreground=TEXT,
                        relief="flat", borderwidth=0, padding=(10, 5), font=FONT_UI)
        style.map("TButton",
                  background=[("pressed", ACCENT), ("active", SURFACE_2)],
                  foreground=[("pressed", BG)])
        style.configure("Accent.TButton", background=ACCENT, foreground=BG,
                        relief="flat", borderwidth=0, padding=(10, 5), font=FONT_BOLD)
        style.map("Accent.TButton",
                  background=[("pressed", ACCENT_2), ("active", ACCENT_2)],
                  foreground=[("pressed", BG)])

        # Inputs
        style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT,
                        insertcolor=ACCENT, bordercolor=SURFACE_2,
                        lightcolor=SURFACE_2, darkcolor=SURFACE_2,
                        relief="flat", padding=4)
        style.map("TEntry", bordercolor=[("focus", ACCENT)])

        # Group frames
        style.configure("TLabelframe", background=BG, bordercolor=SURFACE_2,
                        relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                        font=FONT_BOLD)

        # Data view
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE,
                        foreground=TEXT, bordercolor=BG, relief="flat",
                        rowheight=38, font=FONT_UI)
        style.configure("Treeview.Heading", background=SURFACE_2,
                        foreground=SUBTEXT, relief="flat",
                        font=FONT_BOLD, padding=(4, 3))
        style.map("Treeview.Heading", background=[("active", OVERLAY)])
        style.map("Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])

        # Scrollbars
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"{orient}.TScrollbar", background=SURFACE_2,
                            troughcolor=BG_DEEP, bordercolor=BG_DEEP,
                            arrowcolor=SUBTEXT, relief="flat", width=12)
            style.map(f"{orient}.TScrollbar",
                      background=[("active", OVERLAY), ("pressed", ACCENT)])

        style.configure("TSeparator", background=SURFACE_2)
        style.configure("TPanedwindow", background=BG)
        style.configure("Sash", sashthickness=6, gripcount=0)

        # Default dialog buttons follow the accent look
        for name in ("TCheckbutton", "TRadiobutton"):
            style.configure(name, background=BG, foreground=TEXT, font=FONT_UI)
            style.map(name, background=[("active", BG)], foreground=[("active", ACCENT)])

    def build_ui(self):
        self._build_menu()
        self._build_header(self.root)
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 0))
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        self._build_left(left_frame)
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        self._build_right(right_frame)
        self.status = StatusBar(self.root)
        self.status.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

    # --- Header banner ---

    def _build_header(self, parent):
        self.header_h = 58
        self.header = tk.Canvas(parent, height=self.header_h, bg=BG,
                                highlightthickness=0, bd=0)
        self.header.pack(fill=tk.X, padx=6, pady=(6, 0))
        self.header.bind("<Configure>",
                         lambda e: self._draw_header(e.width, self.header_h))

    def _draw_header(self, w, h):
        cv = self.header
        cv.delete("all")
        round_rect(cv, 1, 1, w - 1, h - 1, 14, fill=SURFACE, outline=SURFACE_2)
        
        # Wczytaj i wyświetl ikonę z pliku ilm.ico
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "ilm.ico")
        if os.path.exists(icon_path):
            try:
                icon_img = Image.open(icon_path)
                icon_img = icon_img.resize((38, 38), Image.Resampling.LANCZOS)
                self.icon_photo = ImageTk.PhotoImage(icon_img)
                cv.create_image(18, 29, image=self.icon_photo, anchor="w")
                # Przesuń tekst dalej, aby nie nakładał się na ikonę
                text_offset = 66
            except Exception:
                # Jeśli wystąpi błąd z wczytaniem ikony, użyj domyślnego prostokąta
                round_rect(cv, 12, 10, 50, 48, 10, fill=ACCENT, outline="")
                cv.create_text(31, 29, text="IS", fill=BG, font=("Segoe UI Semibold", 12))
                text_offset = 62
        else:
            # Jeśli plik ikony nie istnieje, użyj domyślnego prostokąta
            round_rect(cv, 12, 10, 50, 48, 10, fill=ACCENT, outline="")
            cv.create_text(31, 29, text="IS", fill=BG, font=("Segoe UI Semibold", 12))
            text_offset = 62
        
        cv.create_text(text_offset, 21, text="Icon Studio", anchor="w", fill=TEXT,
                       font=FONT_TITLE)
        cv.create_text(text_offset, 40,
                       text="Icon Library Manager   \u2022   Fluent3D   \u2022   DPI   \u2022   AI",
                       anchor="w", fill=SUBTEXT, font=("Segoe UI", 8))
        cv.create_text(w - 16, 29, text=time.strftime("%H:%M:%S"), anchor="e",
                       fill=OVERLAY, font=FONT_MONO, tags="clock")

    def _tick_clock(self):
        if self._clock_started:
            return
        self._clock_started = True
        self._clock_tick()

    def _clock_tick(self):
        try:
            self.header.itemconfig("clock", text=time.strftime("%H:%M:%S"))
        except Exception:
            pass
        self.root.after(1000, self._clock_tick)

    def _toggle_theme(self):
        """Switch between light and dark mode and rebuild the interface."""
        self._mode = "dark" if self._mode == "light" else "light"
        apply_palette(self._mode)
        self.root.after_idle(self._rebuild_ui)

    def _rebuild_ui(self):
        """Recreate the whole interface so every widget picks up the palette."""
        prev = self.get_selected_entry()
        sel_id = prev.id if prev else None
        for w in self.root.winfo_children():
            w.destroy()
        self._apply_theme()
        self._thumb_refs = []
        self.current_preview = None
        self.build_ui()
        self.refresh_list()
        self.show_preview(None)
        if sel_id is not None:
            for i, e in enumerate(self.library.entries):
                if e.id == sel_id:
                    self.tree.selection_set(str(i))
                    self.on_select()
                    break
        self.status.set(f"{self._mode.capitalize()} mode")

    def _build_menu(self):
        mk = dict(bg=BG, fg=TEXT,
                  activebackground=SURFACE, activeforeground=ACCENT)
        menu = tk.Menu(self.root, **mk, relief="flat", bd=0)
        self.root.config(menu=menu)

        def sub():
            return tk.Menu(menu, tearoff=0, **mk)

        fm = sub()
        menu.add_cascade(label="File", menu=fm)
        fm.add_command(label="New Library", command=self.new_library)
        fm.add_command(label="Load Library...", command=self.load_library)
        fm.add_command(label="Save Library...", command=self.save_library)
        fm.add_separator()
        fm.add_command(label="Import IconPack...", command=self.import_pack_gui)
        fm.add_command(label="Export IconPack...", command=self.export_pack_gui)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.root.destroy)

        im = sub()
        menu.add_cascade(label="Icons", menu=im)
        im.add_command(label="Add Icon...", command=self.add_icon)
        im.add_command(label="Add with DPI...", command=self.add_with_dpi)
        im.add_command(label="Import from DLL/EXE...", command=self.import_dll)
        im.add_command(label="Import SVG...", command=self.import_svg)
        im.add_separator()
        im.add_command(label="Remove Selected", command=self.remove_icon)
        im.add_separator()
        im.add_command(label="Export Library to DLL...", command=self.export_dll)

        tm = sub()
        menu.add_cascade(label="Tools", menu=tm)
        tm.add_command(label="Generate DPI Set...", command=self.generate_dpi)
        tm.add_command(label="Detect Style", command=self.detect_style)
        tm.add_command(label="Classify Icon", command=self.classify_gui)
        tm.add_command(label="Semantic Analysis...", command=self.semantic_gui)
        tm.add_command(label="Recommend Icons...", command=self.recommend_gui)
        tm.add_command(label="Generate Icon Set (AI Batch)...", command=self.generate_set_gui)
        tm.add_command(label="AI Icon Generator...", command=self.ai_icon_gui)
        tm.add_command(label="Map UI/UX Action...", command=self.map_action_gui)
        tm.add_command(label="Generate Fluent 3D Icon...", command=self.fluent3d_gui)
        tm.add_command(label="Generate Fluent 3D Avatar...", command=self.avatar3d_gui)
        tm.add_command(label="Generate Team Avatars (Batch)...", command=self.avatar_batch_gui)
        tm.add_command(label="Generate Audio Icon (Waveform)...", command=self.audio_icon_gui)
        tm.add_command(label="Generate Audio Icon Set (Batch)...", command=self.audio_batch_gui)
        tm.add_command(label="Generate Geo Icon (Map/Symbol)...", command=self.geo_icon_gui)
        tm.add_command(label="Generate Geo Icon Set (Batch)...", command=self.geo_batch_gui)
        tm.add_command(label="Generate Texture Icon (Noise/Pattern)...", command=self.texture_icon_gui)
        tm.add_command(label="Generate Texture Icon Set (Batch)...", command=self.texture_batch_gui)
        tm.add_command(label="Export UI Layout (Grid/Toolbar/Ribbon)...", command=self.layout_gui)
        tm.add_command(label="Apply Preset...", command=self.apply_preset_gui)
        tm.add_command(label="Convert Style (Classic->Fluent)...", command=self.convert_style_gui)
        tm.add_command(label="Convert Style (Fluent/Monochrome/Flat)...", command=self.convert_style_target_gui)
        tm.add_command(label="Style Analysis...", command=self.style_analysis_gui)
        tm.add_command(label="Transform Icon...", command=self.transform_gui)
        tm.add_command(label="Fluent 3D Animation...", command=self.anim_gui)
        tm.add_command(label="UI Asset...", command=self.ui_asset_gui)
        tm.add_command(label="Generate UI Theme Pack...", command=self.theme_gui)
        tm.add_command(label="Text -> Icon...", command=self.text_icon_gui)
        tm.add_command(label="Normalize...", command=self.normalize_gui)
        tm.add_command(label="Optimize...", command=self.optimize_gui)
        tm.add_separator()
        tm.add_command(label="Validate All", command=self.validate_gui)
        tm.add_command(label="Rebuild Cache", command=self.rebuild_cache_gui)

        vm = sub()
        menu.add_cascade(label="View", menu=vm)
        self._dark_var = tk.BooleanVar(value=self._mode == "dark")
        vm.add_checkbutton(label="Dark Mode", variable=self._dark_var,
                           command=self._toggle_theme)

        hm = sub()
        menu.add_cascade(label="History", menu=hm)
        hm.add_command(label="Show History...", command=self.show_history)
        hm.add_command(label="Restore Snapshot...", command=self.restore_history)
        hm.add_command(label="Compare Snapshots (Diff)...", command=self.diff_history)

        dm = sub()
        menu.add_cascade(label="DLL Migration", menu=dm)
        dm.add_command(label="Compare DLL Files...", command=self.compare_dll_gui)
        dm.add_command(label="Migrate DLL Icons...", command=self.migrate_dll_gui)

        hm2 = sub()
        menu.add_cascade(label="Help", menu=hm2)
        hm2.add_command(label="About Icon Studio...", command=self.about_gui)

    def _build_left(self, parent):
        slf = ttk.LabelFrame(parent, text="Search")
        slf.pack(fill=tk.X, padx=4, pady=(4, 2))
        si = ttk.Frame(slf)
        si.pack(fill=tk.X, padx=4, pady=4)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(si, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<Return>", lambda e: self.search_icons())
        ttk.Button(si, text="Search", command=self.search_icons).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(si, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=(2, 0))

        llf = ttk.LabelFrame(parent, text="Icons")
        llf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 2))
        li = ttk.Frame(llf)
        li.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(li, orient="vertical")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(li, columns=("id", "name", "tags"),
                                 show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("tags", text="Tags")
        self.tree.column("#0", width=38, minwidth=38, stretch=False, anchor="center")
        self.tree.column("id", width=46, minwidth=40, stretch=False, anchor="e")
        self.tree.column("name", width=168, minwidth=90, anchor="w")
        self.tree.column("tags", width=120, minwidth=60, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.tag_configure("odd", background=STRIPE)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-Button-1>", self.on_double_click)
        sb.config(command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        tlf = ttk.LabelFrame(parent, text="Tags")
        tlf.pack(fill=tk.X, padx=4, pady=(2, 2))
        self.tags_label = ttk.Label(tlf, text="(no selection)", wraplength=220,
                                    font=FONT_MONO, style="Muted.TLabel")
        self.tags_label.pack(fill=tk.X, padx=4, pady=2)
        tbf = ttk.Frame(tlf)
        tbf.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(tbf, text="+ Tag", command=self.add_tag).pack(side=tk.LEFT, padx=2)
        ttk.Button(tbf, text="- Tag", command=self.remove_tag).pack(side=tk.LEFT, padx=2)

        qa = ttk.LabelFrame(parent, text="Quick Actions")
        qa.pack(fill=tk.X, padx=4, pady=(2, 4))
        r1 = ttk.Frame(qa)
        r1.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(r1, text="Add Icon", command=self.add_icon,
                   style="Accent.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="Remove", command=self.remove_icon).pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="Semantic", command=self.semantic_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="Recommend", command=self.recommend_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="Gen Set", command=self.generate_set_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="Map Action", command=self.map_action_gui).pack(side=tk.LEFT, padx=2)
        r2 = ttk.Frame(qa)
        r2.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(r2, text="Fluent 3D", command=self.fluent3d_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="Layout", command=self.layout_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="Theme", command=self.theme_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="Data Icon", command=self.data_icon_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="Data Batch", command=self.data_batch_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="New Lib", command=self.new_library).pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="Load", command=self.load_library).pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="Save", command=self.save_library).pack(side=tk.LEFT, padx=2)
        r3 = ttk.Frame(qa)
        r3.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(r3, text="Avatar 3D", command=self.avatar3d_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3, text="Team Avatars", command=self.avatar_batch_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3, text="Audio Icon", command=self.audio_icon_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3, text="Audio Batch", command=self.audio_batch_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3, text="Geo Icon", command=self.geo_icon_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3, text="Geo Batch", command=self.geo_batch_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3, text="Texture Icon", command=self.texture_icon_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3, text="Texture Batch", command=self.texture_batch_gui).pack(side=tk.LEFT, padx=2)

    def _build_right(self, parent):
        plf = ttk.LabelFrame(parent, text="Preview")
        plf.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        pi = ttk.Frame(plf)
        pi.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(pi, width=288, height=288, bg=BG_DEEP,
                                relief="flat", bd=0, highlightthickness=0,
                                takefocus=1, cursor="hand2")
        self.canvas.pack(padx=16, pady=16)

        # Interactive zoom: wheel, keys and hover-to-focus.
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_preview_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._cycle_zoom(1))
        self.canvas.bind("<Button-5>", lambda e: self._cycle_zoom(-1))
        self.canvas.bind("<plus>", lambda e: self._cycle_zoom(1))
        self.canvas.bind("<equal>", lambda e: self._cycle_zoom(1))
        self.canvas.bind("<KP_Add>", lambda e: self._cycle_zoom(1))
        self.canvas.bind("<minus>", lambda e: self._cycle_zoom(-1))
        self.canvas.bind("<KP_Subtract>", lambda e: self._cycle_zoom(-1))

        self.show_preview(None)

        ilf = ttk.LabelFrame(parent, text="Icon Info")
        ilf.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.info_text = tk.Text(ilf, height=6, bg=SURFACE, fg=TEXT,
                                 font=FONT_MONO, relief="flat", bd=0,
                                 padx=8, pady=6, state=tk.DISABLED,
                                 highlightthickness=0, wrap="none")
        self.info_text.pack(fill=tk.X, padx=4, pady=4)

    # --- Preview stage ---

    def _draw_checkerboard(self, size=288, cell=16):
        """Transparency checkerboard behind the preview image."""
        self.canvas.delete("all")
        c1, c2 = CHECKER_1, CHECKER_2
        for y in range(0, size, cell):
            for x in range(0, size, cell):
                fill = c1 if ((x // cell + y // cell) % 2 == 0) else c2
                self.canvas.create_rectangle(x, y, x + cell, y + cell,
                                             fill=fill, outline="", tags="bg")
        self.canvas.create_rectangle(0, 0, size - 1, size - 1,
                                     outline=SURFACE_2, tags="bg")

    def _draw_picture_glyph(self, cx, cy, s=46, color=OVERLAY):
        """Font-independent framed-picture glyph for the empty state."""
        cv = self.canvas
        x1, y1, x2, y2 = cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2
        cv.create_rectangle(x1, y1, x2, y2, outline=color, width=2,
                            tags="content")
        cv.create_oval(x1 + 8, y1 + 8, x1 + 18, y1 + 18, outline=color,
                       width=2, tags="content")
        cv.create_polygon(x1 + 7, y2 - 7, x1 + s * 0.42, y1 + s * 0.40,
                          x1 + s * 0.62, y2 - 15, x1 + s * 0.80, y1 + s * 0.52,
                          x2 - 7, y2 - 7, fill=color, outline="",
                          tags="content")

    def _show_empty_state(self):
        """Placeholder shown when no icon is selected."""
        self.canvas.delete("content")
        round_rect(self.canvas, 34, 52, 254, 236, 16, fill="",
                   outline=OVERLAY, dash=(4, 3), tags="content")
        self._draw_picture_glyph(144, 122)
        self.canvas.create_text(144, 172, text="No icon selected",
                                fill=SUBTEXT, font=FONT_BOLD, tags="content")
        self.canvas.create_text(144, 192,
                                text="Pick an item from the library",
                                fill=OVERLAY, font=FONT_UI, tags="content")
        self.canvas.create_text(144, 214,
                                text="scroll / +- to zoom",
                                fill=OVERLAY, font=("Segoe UI", 8),
                                tags="content")

    def _on_preview_wheel(self, event):
        self._cycle_zoom(1 if event.delta > 0 else -1)

    def _cycle_zoom(self, step):
        """Cycle the preview between the available zoom levels."""
        if not self._current_path:
            return
        self._preview_idx = (self._preview_idx + step) % len(self._preview_sizes)
        self.show_preview(self._current_path)

    # --- Themed secondary windows ---

    def _dialog(self, title, geometry):
        """Create a consistently styled Toplevel with a header banner."""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=BG)
        win.geometry(geometry)
        win.minsize(360, 220)

        header = tk.Canvas(win, height=44, bg=BG, highlightthickness=0, bd=0)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))

        def draw(w):
            header.delete("all")
            round_rect(header, 1, 1, w - 1, 43, 12, fill=SURFACE, outline=SURFACE_2)
            round_rect(header, 10, 11, 26, 33, 6, fill=ACCENT, outline="")
            header.create_text(36, 22, text=title, anchor="w", fill=TEXT,
                               font=FONT_BOLD)

        header.bind("<Configure>", lambda e: draw(e.width))

        body = ttk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        return win, body

    def _readonly_text(self, parent, wrap="word", font=FONT_MONO):
        """Monospace, read-only text card used by report dialogs."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(frame, bg=BG_DEEP, fg=TEXT, font=font,
                      relief="flat", bd=0, padx=10, pady=8,
                      highlightthickness=0, wrap=wrap, insertbackground=ACCENT,
                      yscrollcommand=sb.set)
        txt.pack(fill=tk.BOTH, expand=True)
        sb.config(command=txt.yview)
        return txt

    def about_gui(self):
        win, body = self._dialog("About Icon Studio", "640x690")
        win.minsize(560, 520)

        big = ("Segoe UI Semibold", 17)
        tiny = ("Segoe UI", 7)

        def pill(cv, text, rx, cy, fg=ACCENT, fill=SURFACE_2, font=FONT_BOLD):
            t = cv.create_text(rx, cy, text=text, anchor="ne", fill=fg, font=font)
            x1, y1, x2, y2 = cv.bbox(t)
            r = round_rect(cv, x1 - 9, y1 - 4, x2 + 9, y2 + 4,
                           (y2 - y1 + 8) // 2, fill=fill, outline="")
            cv.tag_lower(r, t)
            return t

        # --- Hero (logo, name, tagline, version badge) ---
        hero = tk.Canvas(body, height=112, bg=BG, highlightthickness=0, bd=0)
        hero.pack(fill=tk.X, pady=(0, 10))

        def draw_hero(w):
            hero.delete("all")
            round_rect(hero, 1, 1, w - 1, 111, 16, fill=SURFACE, outline=SURFACE_2)
            hero.create_oval(w - 150, -70, w + 40, 120, fill=ACCENT,
                             outline="", stipple="gray12")
            hero.create_oval(w - 96, -34, w + 24, 86, fill=ACCENT_2,
                             outline="", stipple="gray12")
            round_rect(hero, 21, 25, 83, 87, 18, fill=SHADOW, outline="")
            round_rect(hero, 18, 22, 80, 84, 18, fill=ACCENT, outline="")
            hero.create_text(49, 53, text="IS", fill=BG,
                             font=("Segoe UI Semibold", 22))
            hero.create_text(96, 40, text="Icon Studio", anchor="w",
                             fill=TEXT, font=big)
            hero.create_text(96, 65, text="Icon Library Manager",
                             anchor="w", fill=SUBTEXT, font=FONT_UI)
            hero.create_text(96, 88,
                             text="icons \u2022 dpi \u2022 fluent 3d \u2022 ai",
                             anchor="w", fill=OVERLAY, font=FONT_MONO)
            pill(hero, f"v{APP_VERSION}", w - 16, 22)

        hero.bind("<Configure>", lambda e: draw_hero(e.width))

        # --- Feature chips ---
        chips = tk.Canvas(body, height=34, bg=BG, highlightthickness=0, bd=0)
        chips.pack(fill=tk.X, pady=(0, 10))
        features = ["Icon Library", "DLL / EXE", "DPI 16-256", "Fluent 3D",
                    "AI Batch", "UI Layout", "History"]

        def draw_chips(w):
            chips.delete("all")
            x, y = 2, 17
            for f in features:
                t = chips.create_text(x + 11, y, text=f, anchor="w",
                                      fill=ACCENT_2, font=FONT_BOLD)
                x1, y1, x2, y2 = chips.bbox(t)
                if x2 + 11 > w and x > 2:
                    chips.delete(t)
                    y += 30
                    x = 2
                    t = chips.create_text(x + 11, y, text=f, anchor="w",
                                          fill=ACCENT_2, font=FONT_BOLD)
                    x1, y1, x2, y2 = chips.bbox(t)
                r = round_rect(chips, x1 - 11, y1 - 5, x2 + 11, y2 + 5,
                               (y2 - y1 + 10) // 2, fill=SURFACE,
                               outline=SURFACE_2)
                chips.tag_lower(r, t)
                x = x2 + 11 + 8
            chips.config(height=y + 17)

        chips.bind("<Configure>", lambda e: draw_chips(e.width))

        # --- Author / contact card ---
        card = tk.Canvas(body, height=120, bg=BG, highlightthickness=0, bd=0)
        card.pack(fill=tk.X, pady=(0, 10))

        def draw_card(w):
            card.delete("all")
            round_rect(card, 1, 1, w - 1, 119, 12, fill=SURFACE, outline=SURFACE_2)
            round_rect(card, 0, 0, 5, 120, 2, fill=ACCENT, outline="")
            card.create_text(20, 15, text="AUTHOR   &   CONTACT", anchor="w",
                             fill=OVERLAY, font=tiny)
            rows = [
                ("author", "Sebastian Januchowski"),
                ("company", "polsoft.ITS\u2122"),
                ("email", "polsoft.its@mail.com"),
                ("GitHub", "https://github.com/polsoft-it"),
            ]
            y = 40
            for key, val in rows:
                card.create_text(20, y, text=key, anchor="w",
                                 fill=ACCENT, font=FONT_BOLD)
                card.create_text(98, y, text=val, anchor="w",
                                 fill=TEXT, font=FONT_MONO)
                y += 21

        card.bind("<Configure>", lambda e: draw_card(e.width))

        # --- Description ---
        txt = self._readonly_text(body, wrap="word", font=FONT_UI)
        txt.tag_configure("h", foreground=ACCENT, font=FONT_BOLD,
                          spacing1=10, spacing3=2)
        txt.tag_configure("p", foreground=TEXT, spacing3=6,
                          lmargin1=6, lmargin2=6)

        def add(text, tag="p"):
            txt.insert(tk.END, text + "\n", tag)

        add("A comprehensive icon library manager, bundled with tools to "
            "convert, analyse and generate icons and Windows DLL/EXE "
            "resources. Available both as a desktop GUI and a command-line "
            "tool (iconstudio).")

        add("Icon library", "h")
        add("\u2022  add / remove / tag icons, with thumbnails and "
            "searchable list\n"
            "\u2022  interactive preview stage with zoom and transparency "
            "checkerboard\n"
            "\u2022  save / load libraries (JSON) and portable IconPack "
            "bundles")

        add("Windows resources", "h")
        add("\u2022  import icons from DLL / EXE files\n"
            "\u2022  export the whole library to a DLL\n"
            "\u2022  compare and migrate icon resources between PE files")

        add("Processing", "h")
        add("\u2022  normalise to a full DPI set (16-256) and optimise "
            "output\n"
            "\u2022  duplicate detection and hashing of icon data")

        add("Styling and generation", "h")
        add("\u2022  style / colour analysis, style detection and "
            "classification\n"
            "\u2022  style conversion (Classic -> Fluent, Monochrome, Flat) "
            "and presets\n"
            "\u2022  text-to-icon, Fluent 3D icons with animation, UI assets\n"
            "\u2022  UI/UX action mapping, icon recommendations and AI batch "
            "icon sets\n"
            "\u2022  UI layout export (grid / toolbar / ribbon)")

        add("History", "h")
        add("\u2022  library snapshots, restore and diff between snapshots")

        txt.config(state=tk.DISABLED)

        ttk.Separator(body, orient="horizontal").pack(fill=tk.X, pady=(10, 8))

        # --- Footer (palette swatches, stack, close) ---
        footer = ttk.Frame(body)
        footer.pack(fill=tk.X)
        sw = tk.Canvas(footer, height=16, width=132, bg=BG,
                       highlightthickness=0, bd=0)
        sw.pack(side=tk.LEFT)
        for i, c in enumerate((ACCENT, ACCENT_2, GREEN, YELLOW, RED, SUBTEXT)):
            sw.create_rectangle(i * 22, 3, i * 22 + 16, 14, fill=c, outline="")
        ttk.Label(footer, text="Python  \u2022  Pillow  \u2022  Tkinter",
                  style="Muted.TLabel").pack(side=tk.LEFT, padx=12)
        ttk.Button(footer, text="Close", command=win.destroy,
                   style="Accent.TButton").pack(side=tk.RIGHT)

    def refresh_list(self):
        self._search_active = False
        self._populate_tree(self.library.entries)
        self.status.set(f"Library: {len(self.library.entries)} icons")
        self.status.set_right(f"{len(self.library.entries)} items")

    # --- Icon list helpers ---

    def _make_thumb(self, path, size=28):
        """Build a centered RGBA thumbnail for the tree list."""
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size, size), Image.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
            return ImageTk.PhotoImage(canvas)
        except Exception:
            return self._ph_empty

    def _populate_tree(self, entries):
        self.tree.delete(*self.tree.get_children())
        self._thumb_refs = []
        for i, e in enumerate(entries):
            thumb = self._make_thumb(e.path)
            self._thumb_refs.append(thumb)
            self.tree.insert("", tk.END, iid=str(i), image=thumb,
                             values=(f"{e.id:04d}", e.name, ", ".join(e.tags)),
                             tags=("odd",) if i % 2 else ())
        self._restripe()

    def _restripe(self):
        """Keep zebra stripes while leaving the selected row highlighted."""
        sel = set(self.tree.selection())
        for i, iid in enumerate(self.tree.get_children()):
            if iid in sel:
                self.tree.item(iid, tags=())
            elif i % 2:
                self.tree.item(iid, tags=("odd",))
            else:
                self.tree.item(iid, tags=())

    def get_selected_entry(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        entries = self._search_results if self._search_active else self.library.entries
        return entries[idx] if idx < len(entries) else None

    def on_select(self, event=None):
        self._restripe()
        entry = self.get_selected_entry()
        if not entry:
            return
        self.show_preview(entry.path)
        self._update_tags_label(entry)
        self._update_info(entry)

    def on_double_click(self, event=None):
        entry = self.get_selected_entry()
        if entry:
            self.status.set(f"Selected: {entry.name} | {entry.path}")

    def _update_tags_label(self, entry):
        self.tags_label.config(text=" | ".join(entry.tags) if entry.tags else "(no tags)")

    def _update_info(self, entry):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        h = entry.hash[:16] + "..." if entry.hash else "N/A"
        info = (f"ID     {entry.id}\n"
                f"Name   {entry.name}\n"
                f"Path   {entry.path}\n"
                f"Hash   {h}\n"
                f"Tags   {', '.join(entry.tags) if entry.tags else 'none'}")
        self.info_text.insert(tk.END, info)
        self.info_text.config(state=tk.DISABLED)

    def show_preview(self, path):
        """Render the preview stage (empty state when nothing is selected)."""
        self._current_path = path if path else None
        self._draw_checkerboard()
        path = self._current_path
        if not path or not os.path.isfile(path):
            self._show_empty_state()
            return
        try:
            img = Image.open(path).convert("RGBA")
            w, h = img.size
            side = self._preview_sizes[self._preview_idx]
            img = img.resize((side, side), Image.LANCZOS)
            x1 = (288 - side) / 2
            y1 = 136 - side / 2
            self.canvas.create_rectangle(x1 + 6, y1 + 6, x1 + side + 6,
                                         y1 + side + 6, fill=SHADOW,
                                         outline="", tags="content")
            self.current_preview = ImageTk.PhotoImage(img)
            self.canvas.create_image(144, 136, image=self.current_preview,
                                     tags="content")
            self.canvas.create_text(144, 272,
                                    text=f"{w} \u00D7 {h} px  \u2022  {side}px view",
                                    fill=SUBTEXT, font=FONT_MONO, tags="content")
            self.canvas.create_text(280, 10, text="\u2212 / +", anchor="ne",
                                    fill=OVERLAY, font=("Segoe UI", 8),
                                    tags="content")
        except Exception as e:
            self.canvas.create_text(144, 144, text=f"Error\n{e}",
                                    fill=RED, font=FONT_MONO, width=240,
                                    tags="content")

    def add_icon(self):
        path = filedialog.askopenfilename(
            title="Select icon file",
            filetypes=[("Icon files", "*.ico;*.png;*.bmp"), ("All files", "*.*")])
        if not path:
            return
        self.library.add_icon(path)
        self.history.add_snapshot(self.library, "add icon")
        self.refresh_list()
        self.status.set(f"Added: {os.path.basename(path)}")

    def add_with_dpi(self):
        path = filedialog.askopenfilename(
            title="Select source image",
            filetypes=[("Images", "*.png;*.jpg;*.bmp;*.ico"), ("All files", "*.*")])
        if not path:
            return
        out_path = filedialog.asksaveasfilename(
            title="Save ICO with DPI layers",
            defaultextension=".ico", filetypes=[("ICO files", "*.ico")])
        if not out_path:
            return
        try:
            from iconlib.dpi_generator import DPIGenerator
            DPIGenerator().generate_dpi_set(path, out_path)
            self.library.add_icon(out_path)
            self.history.add_snapshot(self.library, "add dpi icon")
            self.refresh_list()
            messagebox.showinfo("Done", f"DPI set saved: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def remove_icon(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        self.library.remove_icon(entry.id)
        self.history.add_snapshot(self.library, "remove icon")
        self.refresh_list()
        self.show_preview(None)
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        self.info_text.config(state=tk.DISABLED)
        self.tags_label.config(text="(no selection)")
        self.status.set("Icon removed")

    def new_library(self):
        if messagebox.askyesno("New Library", "Clear current library?"):
            self.library = IconLibrary()
            self.refresh_list()
            self.show_preview(None)
            self.status.set("New library created")

    def load_library(self):
        path = filedialog.askopenfilename(
            title="Load library",
            filetypes=[("JSON library", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.library.load(path)
            self.refresh_list()
            self.status.set(f"Loaded: {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_library(self):
        path = filedialog.asksaveasfilename(
            title="Save library",
            defaultextension=".json",
            filetypes=[("JSON library", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.library.save(path)
            self.status.set(f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def search_icons(self):
        text = self.search_var.get().strip()
        if not text:
            return
        results = self.library.search(text)
        self._search_active = True
        self._search_results = results
        self._populate_tree(results)
        self.status.set(f"Search '{text}': {len(results)} results")

    def clear_search(self):
        self.search_var.set("")
        self.refresh_list()

    def add_tag(self):
        entry = self.get_selected_entry()
        if not entry:
            return
        tag = simpledialog.askstring("Add Tag", "Enter tag:")
        if not tag:
            return
        self.library.add_tag(entry.id, tag)
        self.refresh_list()
        self._update_tags_label(entry)
        self.status.set(f"Tag added: {tag}")

    def remove_tag(self):
        entry = self.get_selected_entry()
        if not entry:
            return
        current = ", ".join(entry.tags) if entry.tags else "none"
        tag = simpledialog.askstring("Remove Tag", f"Current: {current}\nTag to remove:")
        if not tag:
            return
        self.library.remove_tag(entry.id, tag)
        self.refresh_list()
        self._update_tags_label(entry)
        self.status.set(f"Tag removed: {tag}")

    def import_dll(self):
        path = filedialog.askopenfilename(
            title="Import DLL/EXE",
            filetypes=[("DLL/EXE", "*.dll;*.exe"), ("All files", "*.*")])
        if not path:
            return
        try:
            from iconlib.dll_import import DLLIconImporter
            importer = DLLIconImporter(path)
            icons = importer.import_icons()
            save_dir = os.path.dirname(path)
            for item in icons:
                ico_path = os.path.join(save_dir, f"imported_{item['id']}.ico")
                with open(ico_path, "wb") as f:
                    f.write(item["ico"])
                self.library.add_icon(ico_path)
            self.history.add_snapshot(self.library, "import dll")
            self.refresh_list()
            messagebox.showinfo("OK", f"Imported {len(icons)} icon groups from DLL")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_dll(self):
        if not self.library.entries:
            messagebox.showwarning("Warning", "Library is empty")
            return
        path = filedialog.asksaveasfilename(
            title="Export DLL", defaultextension=".dll",
            filetypes=[("DLL", "*.dll")])
        if not path:
            return
        try:
            from iconlib.dll_export import DLLBuilder
            builder = DLLBuilder()
            gid = 100
            biid = 200
            for entry in self.library.entries:
                if os.path.isfile(entry.path) and entry.path.lower().endswith(".ico"):
                    builder.add_icon(entry.path, gid, biid)
                    gid += 1
                    biid += 20
            builder.build(path)
            messagebox.showinfo("OK", f"DLL exported: {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def import_svg(self):
        try:
            import cairosvg
        except ImportError:
            messagebox.showerror("Error", "cairosvg not installed.\nRun: pip install cairosvg")
            return
        path = filedialog.askopenfilename(
            title="Import SVG",
            filetypes=[("SVG", "*.svg"), ("All files", "*.*")])
        if not path:
            return
        out_ico = path + ".ico"
        try:
            from iconlib.svg_to_ico import SVGToICO
            SVGToICO().svg_to_ico(path, out_ico)
            self.library.add_icon(out_ico)
            self.history.add_snapshot(self.library, "import svg")
            self.refresh_list()
            messagebox.showinfo("OK", "SVG converted to ICO and added")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def generate_dpi(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        out_path = filedialog.asksaveasfilename(
            title="Save ICO with DPI", defaultextension=".ico",
            filetypes=[("ICO", "*.ico")])
        if not out_path:
            return
        try:
            from iconlib.dpi_generator import DPIGenerator
            DPIGenerator().generate_dpi_set(entry.path, out_path)
            messagebox.showinfo("OK", f"DPI set generated: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def detect_style(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        try:
            from iconlib.style_detector import IconStyleDetector
            style = IconStyleDetector().detect_style(entry.path)
            self.library.add_tag(entry.id, style)
            self.refresh_list()
            self._update_tags_label(entry)
            messagebox.showinfo("Style Detected", f"Detected style: {style}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def classify_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        try:
            from iconlib.classifier import IconClassifier
            cat = IconClassifier().classify(entry.path)
            self.library.add_tag(entry.id, cat)
            self.refresh_list()
            self._update_tags_label(entry)
            messagebox.showinfo("Category", f"Detected category: {cat}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def semantic_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return

        try:
            data = self.library.analyze_icon(entry.id)

            win, body = self._dialog(f"Semantic Analysis \u2014 {entry.name}", "760x560")
            txt = self._readonly_text(body)

            txt.insert(tk.END, "Visual\n")
            txt.insert(tk.END, json.dumps(data["visual"], indent=2) + "\n\n")

            txt.insert(tk.END, "Semantic\n")
            txt.insert(tk.END, str(data["semantic"]) + "\n\n")

            txt.insert(tk.END, "UX Context\n")
            txt.insert(tk.END, str(data["ux"]) + "\n\n")

            if data.get("ai"):
                txt.insert(tk.END, "AI Description\n")
                txt.insert(tk.END, str(data["ai"]) + "\n")

            txt.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def recommend_gui(self):
        query = simpledialog.askstring("Recommend", "Describe desired icon (e.g. 'folder', 'blue cloud', 'fluent'):")
        if not query:
            return

        if self.cache is None:
            from iconlib.cache import IconCache
            self.cache = IconCache()
            self.cache.build(self.library)

        ids = self.library.recommend_icons(query, self.cache)
        if not ids:
            messagebox.showinfo("Recommendations", f"No recommendations found for: '{query}'")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Recommendations for '{query}'")
        win.geometry("560x440")
        win.configure(bg=BG)

        lbl = ttk.Label(win, text=f"Recommended icons for: '{query}'   \u2022   {len(ids)} found",
                        font=FONT_BOLD, foreground=ACCENT)
        lbl.pack(padx=10, pady=(10, 4), anchor="w")

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        sb = ttk.Scrollbar(frame, orient="vertical")
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        lb = ttk.Treeview(frame, columns=("id", "name", "tags"),
                          show="tree headings", selectmode="browse")
        lb.heading("#0", text="")
        lb.heading("id", text="ID")
        lb.heading("name", text="Name")
        lb.heading("tags", text="Tags")
        lb.column("#0", width=34, minwidth=34, stretch=False, anchor="center")
        lb.column("id", width=48, minwidth=40, stretch=False, anchor="e")
        lb.column("name", width=200, minwidth=100, anchor="w")
        lb.column("tags", width=160, minwidth=60, anchor="w")
        lb.pack(fill=tk.BOTH, expand=True)
        sb.config(command=lb.yview)
        lb.configure(yscrollcommand=sb.set)

        rec_order = []
        rec_thumbs = []
        for id_ in ids:
            e = self.library.get_entry(id_)
            if e:
                thumb = self._make_thumb(e.path, 24)
                rec_thumbs.append(thumb)
                rec_order.append(id_)
                lb.insert("", tk.END, iid=str(len(rec_order) - 1), image=thumb,
                          values=(f"{e.id:04d}", e.name, ", ".join(e.tags)))
        lb._thumbs = rec_thumbs

        def on_select_rec(event=None):
            sel = lb.selection()
            if not sel:
                return
            target_id = rec_order[int(sel[0])]
            for idx, entry in enumerate(self.library.entries):
                if entry.id == target_id:
                    self._search_active = False
                    self.tree.selection_set(str(idx))
                    self.tree.see(str(idx))
                    self.on_select()
                    break

        lb.bind("<<TreeviewSelect>>", on_select_rec)
        lb.bind("<Double-Button-1>", lambda e: on_select_rec())

    def generate_set_gui(self):
        prompt = simpledialog.askstring("Prompt", "Describe icon set (e.g. 'Windows 11 Fluent icons'):")
        if not prompt:
            return

        cats = simpledialog.askstring("Categories", "Comma-separated categories (e.g. 'cloud, folder, sync, settings, user'):")
        if not cats:
            return

        categories = [c.strip() for c in cats.split(",") if c.strip()]
        if not categories:
            return

        out_dir = filedialog.askdirectory(title="Select output directory")
        if not out_dir:
            return

        try:
            self.status.set(f"Generating icon set ({len(categories)} icons)...")
            generated, pack_path = self.library.generate_icon_set(prompt, categories, out_dir)
            self.status.set(f"Generated {len(generated)} icons successfully.")

            do_import = messagebox.askyesno(
                "Generation Complete",
                f"Generated {len(generated)} icons.\nIconPack saved to:\n{pack_path}\n\nDo you want to add these icons to the current library?"
            )
            if do_import:
                for item in generated:
                    self.library.add_icon(item["file"], item.get("name"))
                    entry = self.library.entries[-1]
                    self.library.add_tag(entry.id, item["category"])
                self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating icon set.")

    def map_action_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return

        try:
            data = self.library.map_icon_action(entry.id)

            win, body = self._dialog("UI/UX Action Mapping", "660x500")
            txt = self._readonly_text(body)

            txt.insert(tk.END, f"Icon: {entry.name} (ID: {entry.id})\n\n")

            txt.insert(tk.END, "Semantic\n")
            txt.insert(tk.END, str(data["semantic"]) + "\n\n")

            txt.insert(tk.END, "Visual\n")
            txt.insert(tk.END, json.dumps(data["visual"], indent=2) + "\n\n")

            txt.insert(tk.END, "Mapped Action\n")
            txt.insert(tk.END, str(data["action"]) + "\n\n")

            if data.get("ai_action"):
                txt.insert(tk.END, "AI Action\n")
                txt.insert(tk.END, str(data["ai_action"]) + "\n")

            txt.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def fluent3d_gui(self):
        prompt = simpledialog.askstring("Fluent 3D", "Describe icon (e.g. 'cloud sync, glossy'):")
        if not prompt:
            return

        out_dir = filedialog.askdirectory(title="Select output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating Fluent 3D icon...")
            result = self.library.generate_fluent3d(prompt, out_dir)
            self.status.set("Fluent 3D icon generated.")
            do_add = messagebox.askyesno(
                "Fluent 3D Generated",
                f"Fluent 3D icon generated:\n{result['ico']}\n\nAdd this icon to the current library?"
            )
            if do_add:
                self.library.add_icon(result["ico"])
                self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating Fluent 3D icon.")

    def avatar3d_gui(self):
        prompt = simpledialog.askstring(
            "Avatar 3D", "Describe avatar (e.g. 'robot engineer'):")
        if not prompt:
            return

        style = simpledialog.askstring(
            "Avatar Style", "fluent3d / pastel / glossy / cartoon:", initialvalue="fluent3d")
        if not style:
            return

        role = simpledialog.askstring(
            "Avatar Role", "developer / designer / admin / (leave empty for none):")

        out_dir = filedialog.askdirectory(title="Select output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating Fluent 3D avatar...")
            result = self.library.generate_avatar3d(
                prompt, out_dir, style.strip().lower(), role=(role or None))
            self.status.set("Fluent 3D avatar generated.")
            do_add = messagebox.askyesno(
                "Avatar 3D Generated",
                f"Fluent 3D avatar generated:\n{result['ico']}\n\n"
                f"Add this avatar to the current library?"
            )
            if do_add:
                self.library.add_icon(result["ico"], name=f"avatar-{result['style']}")
                self.history.add_snapshot(self.library, "avatar 3d")
                self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating Fluent 3D avatar.")

    def avatar_batch_gui(self):
        src = filedialog.askopenfilename(
            title="Select roster file (CSV / JSON)",
            filetypes=[("Roster files", "*.csv *.json *.txt"), ("All files", "*.*")])
        if not src:
            src = simpledialog.askstring(
                "Team Avatars", "Inline roster 'Name=prompt;Name2=prompt2':")
        if not src:
            return

        style = simpledialog.askstring(
            "Avatar Style", "fluent3d / pastel / glossy / cartoon:", initialvalue="fluent3d")
        if not style:
            return

        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating team avatars...")
            result = self.library.avatar_batch(src, out_dir, style.strip().lower())
            do_add = messagebox.askyesno(
                "Team Avatars Generated",
                f"Avatars generated: {result['count']}\n"
                f"Sheet: {result['sheet']}\n\n"
                f"Add all avatars to the current library?"
            )
            if do_add:
                for item in result["avatars"]:
                    self.library.add_icon(item["ico"], name=item["name"])
                self.history.add_snapshot(self.library, "avatar batch")
                self.refresh_list()
            self.status.set(f"Team avatars generated: {result['count']}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating team avatars.")

    def audio_icon_gui(self):
        src = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[("Audio files", "*.wav *.mp3 *.ogg"), ("All files", "*.*")])
        if not src:
            return

        style = simpledialog.askstring(
            "Style", "fluent / monochrome / outline / classic:", initialvalue="fluent")
        if not style:
            return

        mode = simpledialog.askstring(
            "Mode", "waveform / bars / spectrogram / ring:", initialvalue="waveform")
        if not mode:
            return

        use_palette = messagebox.askyesno(
            "Spectrum Palette",
            "Derive the icon colors from the audio spectrum?\n"
            "(tints the glyph using frequencies of the recording)")

        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating audio icon...")
            result = self.library.audio_icon(
                src, out_dir, style.strip().lower(), mode=mode.strip().lower(),
                palette=use_palette)
            self.status.set("Audio icon generated.")
            extra = ""
            if result.get("palette"):
                extra = (f"\nPalette: {result['palette']['primary']} / "
                         f"{result['palette']['accent']}")
            do_add = messagebox.askyesno(
                "Audio Icon Generated",
                f"Audio icon generated ({result['mode']}):\n{result['ico']}{extra}\n\n"
                f"Add this icon to the current library?"
            )
            if do_add:
                self.library.add_icon(result["ico"], name=f"audio-{result['mode']}")
                self.history.add_snapshot(self.library, "audio icon")
                self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating audio icon.")

    def audio_batch_gui(self):
        src = filedialog.askdirectory(title="Select folder with audio files")
        if not src:
            src = filedialog.askopenfilename(
                title="Or select a path list (CSV / JSON / TXT)",
                filetypes=[("Path lists", "*.csv *.json *.txt"), ("All files", "*.*")])
        if not src:
            return

        style = simpledialog.askstring(
            "Style", "fluent / monochrome / outline / classic:", initialvalue="fluent")
        if not style:
            return

        mode = simpledialog.askstring(
            "Mode", "waveform / bars / spectrogram / ring:", initialvalue="waveform")
        if not mode:
            return

        use_palette = messagebox.askyesno(
            "Spectrum Palette",
            "Derive icon colors from each audio spectrum?")

        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating audio icon batch...")
            result = self.library.audio_batch(
                src, out_dir, style.strip().lower(), mode=mode.strip().lower(),
                palette=use_palette)
            do_add = messagebox.askyesno(
                "Audio Batch Generated",
                f"Icons generated: {result['count']}\n"
                f"Sheet: {result['sheet']}\n\n"
                f"Add all icons to the current library?"
            )
            if do_add:
                for item in result["icons"]:
                    self.library.add_icon(item["ico"], name=item["name"])
                self.history.add_snapshot(self.library, "audio batch")
                self.refresh_list()
            self.status.set(f"Audio batch generated: {result['count']} icons")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating audio icon batch.")

    def geo_icon_gui(self):
        raw = simpledialog.askstring(
            "Geo -> Icon",
            "Enter geo data:\n"
            "- coordinates: 'lat,lon;lat,lon' (e.g. 51.5,-0.2;51.6,-0.3)\n"
            "- a region name (e.g. London)\n"
            "- heat values: '0.2,0.5,0.9'")
        if not raw or not raw.strip():
            return

        symbol = simpledialog.askstring(
            "Symbol", "pin / marker / region / route / area / heatmap:", initialvalue="pin")
        if not symbol:
            return

        style = simpledialog.askstring(
            "Style", "fluent / monochrome / outline / classic:", initialvalue="fluent")
        if not style:
            return

        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating geo icon...")
            result = self.library.geo_icon(
                raw.strip(), out_dir, symbol.strip().lower(), style.strip().lower())
            self.status.set("Geo icon generated.")
            do_add = messagebox.askyesno(
                "Geo Icon Generated",
                f"Geo icon generated ({result['symbol']}):\n{result['ico']}\n\n"
                f"Add this icon to the current library?"
            )
            if do_add:
                self.library.add_icon(result["ico"], name=f"geo-{result['symbol']}")
                self.history.add_snapshot(self.library, "geo icon")
                self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating geo icon.")

    def geo_batch_gui(self):
        src = filedialog.askdirectory(title="Select folder with geo files")
        if not src:
            src = filedialog.askopenfilename(
                title="Or select a geo list (CSV / JSON / GEOJSON / TXT)",
                filetypes=[("Geo lists", "*.csv *.json *.geojson *.txt"),
                           ("All files", "*.*")])
        if not src:
            return

        symbol = simpledialog.askstring(
            "Default Symbol", "pin / marker / region / route / area / heatmap:",
            initialvalue="pin")
        if not symbol:
            return

        style = simpledialog.askstring(
            "Style", "fluent / monochrome / outline / classic:", initialvalue="fluent")
        if not style:
            return

        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating geo icon batch...")
            result = self.library.geo_batch(
                src, out_dir, symbol.strip().lower(), style.strip().lower())
            do_add = messagebox.askyesno(
                "Geo Batch Generated",
                f"Icons generated: {result['count']}\n"
                f"Sheet: {result['sheet']}\n\n"
                f"Add all icons to the current library?"
            )
            if do_add:
                for item in result["icons"]:
                    self.library.add_icon(item["ico"], name=item["name"])
                self.history.add_snapshot(self.library, "geo batch")
                self.refresh_list()
            self.status.set(f"Geo batch generated: {result['count']} icons")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating geo icon batch.")

    def texture_icon_gui(self):
        texture = simpledialog.askstring(
            "Texture",
            "perlin / simplex / worley / grain / metal / carbon /\n"
            "wood / marble / dots / grid / stripes / waves:",
            initialvalue="perlin")
        if not texture:
            return

        style = simpledialog.askstring(
            "Style", "fluent / monochrome / outline / classic:", initialvalue="fluent")
        if not style:
            return

        size = simpledialog.askinteger(
            "Size", "Icon size in pixels (128-512):", initialvalue=256,
            minvalue=128, maxvalue=512)
        if not size:
            return

        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating texture icon...")
            result = self.library.texture_icon(
                texture.strip().lower(), out_dir, style.strip().lower(), size)
            do_add = messagebox.askyesno(
                "Texture Icon Generated",
                f"Texture: {result['texture_name']}\n"
                f"Seed: {result['seed']}\n"
                f"ICO: {result['ico']}\n\n"
                f"Add to the current library?"
            )
            if do_add:
                self.library.add_icon(
                    result["ico"], name=f"texture-{result['texture_name']}")
                self.history.add_snapshot(self.library, "texture icon")
                self.refresh_list()
            self.status.set(f"Texture icon generated: {result['texture_name']}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating texture icon.")

    def texture_batch_gui(self):
        src = filedialog.askdirectory(title="Select folder with texture specs")
        if not src:
            src = simpledialog.askstring(
                "Textures",
                "Inline list, e.g. perlin//marble//carbon\n"
                "or a path to a .csv/.json/.txt file:",
                initialvalue="perlin//marble//carbon//wood")
        if not src:
            return

        style = simpledialog.askstring(
            "Style", "fluent / monochrome / outline / classic:", initialvalue="fluent")
        if not style:
            return

        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return

        try:
            self.status.set("Generating texture icon batch...")
            result = self.library.texture_batch(
                src.strip(), out_dir, style.strip().lower())
            do_add = messagebox.askyesno(
                "Texture Batch Generated",
                f"Icons generated: {result['count']}\n"
                f"Sheet: {result['sheet']}\n\n"
                f"Add all icons to the current library?"
            )
            if do_add:
                for item in result["icons"]:
                    self.library.add_icon(item["ico"], name=item["name"])
                self.history.add_snapshot(self.library, "texture batch")
                self.refresh_list()
            self.status.set(f"Texture batch generated: {result['count']} icons")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating texture icon batch.")

    def layout_gui(self):
        if not self.library.entries:
            messagebox.showwarning("Warning", "Library is empty. Add icons first.")
            return

        layout_type = simpledialog.askstring(
            "UI Layout",
            "Enter layout type:\n- grid (6-column 128px)\n- toolbar (horizontal 64px)\n- ribbon (3-column 96px)\n- sidebar (vertical 64px)\n- menu (vertical 48px)\n\nLayout type:",
            initialvalue="grid"
        )
        if not layout_type:
            return
        layout_type = layout_type.strip().lower()

        out_dir = filedialog.askdirectory(title="Select output directory for layout")
        if not out_dir:
            return

        try:
            if self.cache is None:
                from iconlib.cache import IconCache
                self.cache = IconCache()
                self.cache.build(self.library)

            ids = [e.id for e in self.library.entries]
            res = self.library.layout_icons(ids, layout_type, self.cache, out_dir)
            messagebox.showinfo(
                "Layout Generated",
                f"Layout '{layout_type}' generated successfully!\n\nPreview: {res['preview']}\nMetadata: {res['meta']}"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def apply_preset_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        preset = simpledialog.askstring(
            "Apply Preset",
            "Available presets:\n" + "\n".join(PRESETS) + "\n\nEnter preset name:")
        if not preset:
            return
        out_path = filedialog.asksaveasfilename(
            title="Save preset result", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("ICO", "*.ico"), ("All files", "*.*")])
        if not out_path:
            return
        try:
            from iconlib.style_presets import IconStylePresets
            IconStylePresets().apply_preset(entry.path, out_path, preset)
            messagebox.showinfo("OK", f"Preset '{preset}' applied: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def convert_style_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        out_path = filedialog.asksaveasfilename(
            title="Save converted icon", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("ICO", "*.ico"), ("All files", "*.*")])
        if not out_path:
            return
        try:
            from iconlib.style_convert import StyleConverter
            StyleConverter().classic_to_fluent(entry.path, out_path)
            messagebox.showinfo("OK", f"Style converted to Fluent: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def convert_style_target_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        target = simpledialog.askstring("Target Style", "fluent / monochrome / flat:")
        if not target:
            return
        out_dir = filedialog.askdirectory(title="Select output directory")
        if not out_dir:
            return
        try:
            from iconlib.style_convert import IconStyleConverter
            res = IconStyleConverter().convert(entry.path, out_dir, target.strip().lower())
            messagebox.showinfo(
                "OK",
                f"Style converted to {target}:\n{res['ico']}\n\n"
                f"Original style: {res['original_style']['style']}\n"
                f"New style: {res['new_style']['style']}"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def style_analysis_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        try:
            data = self.library.analyze_style(entry.id)

            win, body = self._dialog(f"Style Analysis \u2014 {entry.name}", "580x500")
            txt = self._readonly_text(body)
            txt.insert(tk.END, json.dumps(data, indent=2))
            txt.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def transform_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        mode = simpledialog.askstring(
            "Transform",
            "Mode:\nextrude / bevel / emboss / glow /\n"
            "inner_shadow / outer_shadow / highlight / metallic:")
        if not mode:
            return
        out_path = filedialog.asksaveasfilename(
            title="Save transformed icon", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("ICO", "*.ico"), ("All files", "*.*")])
        if not out_path:
            return
        try:
            self.library.transform_icon(entry.id, out_path, mode.strip().lower())
            messagebox.showinfo("OK", f"Icon transformed ({mode}): {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def anim_gui(self):
        prompt = simpledialog.askstring("Fluent 3D Animation", "Describe icon:")
        if not prompt:
            return
        frames = simpledialog.askinteger("Frames", "Number of frames:", initialvalue=12)
        if not frames:
            return
        motion = simpledialog.askstring(
            "Motion", "rotate / tilt / bounce / pulse / glow / morph:")
        if not motion:
            return
        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return
        try:
            self.status.set("Generating Fluent 3D animation...")
            result = self.library.animate_fluent3d(prompt, out_dir, frames, motion.strip().lower())
            self.status.set("Animation generated.")
            messagebox.showinfo(
                "OK",
                f"Animation generated:\nGIF:  {result['gif']}\n"
                f"WebP: {result['webp']}\nSprite: {result['sprite']}"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating animation.")

    def ui_asset_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        ui_type = simpledialog.askstring(
            "UI Type",
            "button / toggle / checkbox / radio / slider / progress /\n"
            "input / search / dropdown / toolbar / ribbon / sidebar / menu:")
        if not ui_type:
            return
        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return
        try:
            if self.cache is None:
                from iconlib.cache import IconCache
                self.cache = IconCache()
                self.cache.build(self.library)
            from iconlib.ui_assets import UIAssetPipeline
            result = UIAssetPipeline(self.cache).build(entry.id, ui_type.strip().lower(), out_dir)
            messagebox.showinfo("OK", f"UI asset generated:\n{result['preview']}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def theme_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        style = simpledialog.askstring(
            "Theme Style", "fluent / classic / monochrome:",
            initialvalue="fluent")
        if not style:
            return
        out_dir = filedialog.askdirectory(title="Output directory for theme pack")
        if not out_dir:
            return
        try:
            self.status.set("Generating UI theme...")
            if self.cache is None:
                from iconlib.cache import IconCache
                self.cache = IconCache()
                self.cache.build(self.library)
            from iconlib.theme import UIThemeGenerator
            res = UIThemeGenerator(self.cache).generate(
                entry.id, out_dir, style.strip().lower())
            self.status.set(f"Theme generated: {os.path.basename(res['pack'])}")
            messagebox.showinfo(
                "Theme Generated",
                f"Theme pack created:\n{res['pack']}\n\n"
                f"Components: {len(res['components'])}\n"
                f"Surfaces:   {len(res['surfaces'])}\n"
                f"Icon set:   {len(res['icons']['variants'])} variants\n"
                f"Icon fx:    {len(res['icons']['effects'].get('variants', {}))}\n"
                f"Layouts:    {len(res['layouts'])}\n"
                f"Typography: {len(res['typography'].get('specimens', {}))} specimens\n"
                f"Preview:    {res['preview']}\n"
                f"Tokens:     {res['tokens']['json']}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def text_icon_gui(self):
        text = simpledialog.askstring("Text", "Enter text:")
        if not text:
            return
        style = simpledialog.askstring("Style", "fluent / monochrome / outline / classic:")
        if not style:
            return
        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return
        try:
            result = self.library.text_icon(text, out_dir, style.strip().lower())
            do_add = messagebox.askyesno(
                "Text Icon Generated",
                f"Icon generated:\n{result['ico']}\n\nAdd this icon to the current library?"
            )
            if do_add:
                self.library.add_icon(result["ico"], name=text)
                self.history.add_snapshot(self.library, "text icon")
                self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def data_icon_gui(self):
        raw = simpledialog.askstring("Data -> Icon", "Comma-separated numbers (e.g. 1,2,3,4,5):")
        if not raw:
            return
        try:
            data = [float(x.strip()) for x in raw.split(",") if x.strip() != ""]
        except ValueError:
            messagebox.showerror("Error", "Data must be comma-separated numbers")
            return
        if not data:
            messagebox.showerror("Error", "Provide at least one number")
            return
        chart = simpledialog.askstring(
            "Chart", "line / bar / area / donut / sparkline:", initialvalue="line")
        if not chart:
            return
        style = simpledialog.askstring(
            "Style", "fluent / monochrome / outline / classic:", initialvalue="fluent")
        if not style:
            return
        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return
        try:
            self.status.set("Generating data icon...")
            result = self.library.data_icon(
                data, out_dir, chart.strip().lower(), style.strip().lower())
            do_add = messagebox.askyesno(
                "Data Icon Generated",
                f"Icon generated:\n{result['ico']}\n\n"
                f"Add this icon to the current library?"
            )
            if do_add:
                self.library.add_icon(result["ico"], name=f"data-{chart.strip().lower()}")
                self.history.add_snapshot(self.library, "data icon")
                self.refresh_list()
            self.status.set("Data icon generated.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def data_batch_gui(self):
        src = filedialog.askopenfilename(
            title="Select data file (CSV / JSON)",
            filetypes=[("Data files", "*.csv *.json *.txt"), ("All files", "*.*")])
        if not src:
            src = simpledialog.askstring(
                "Data Batch", "Inline spec 'name=1,2,3;name2=4,5,6':")
        if not src:
            return
        chart = simpledialog.askstring(
            "Chart", "line / bar / area / donut / sparkline:", initialvalue="line")
        if not chart:
            return
        style = simpledialog.askstring(
            "Style", "fluent / monochrome / outline / classic:", initialvalue="fluent")
        if not style:
            return
        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return
        try:
            self.status.set("Generating data batch...")
            result = self.library.data_batch(
                src, out_dir, chart.strip().lower(), style.strip().lower())
            do_add = messagebox.askyesno(
                "Data Batch Generated",
                f"Icons generated: {result['count']}\n"
                f"Sheet: {result['sheet']}\n\n"
                f"Add all icons to the current library?"
            )
            if do_add:
                for item in result["icons"]:
                    self.library.add_icon(item["ico"], name=item["name"])
                self.history.add_snapshot(self.library, "data batch")
                self.refresh_list()
            self.status.set(f"Data batch generated: {result['count']} icons")
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def ai_icon_gui(self):
        prompt = simpledialog.askstring("AI Icon", "Describe icon:")
        if not prompt:
            return
        out_dir = filedialog.askdirectory(title="Output directory")
        if not out_dir:
            return
        try:
            self.status.set("Generating AI icon...")
            from iconlib.ai_generator import AIIconGenerator
            ai = AIIconGenerator(api_url=self.library.ai_url, api_key=self.library.ai_key)
            png_path, ico_path = ai.generate_icon(prompt, out_dir)
            self.library.add_icon(ico_path)
            self.history.add_snapshot(self.library, "ai icon")
            self.refresh_list()
            self.status.set("AI icon generated.")
            messagebox.showinfo("OK", f"AI icon generated:\n{ico_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error generating AI icon.")

    def style_gui(self):
        self.style_analysis_gui()

    def normalize_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        style = simpledialog.askstring(
            "Normalize",
            "Target style:\n" + "\n".join(STYLES) + "\n\nEnter style:")
        if not style:
            return
        out_path = filedialog.asksaveasfilename(
            title="Save normalized icon", defaultextension=".ico",
            filetypes=[("ICO", "*.ico"), ("PNG", "*.png"), ("All files", "*.*")])
        if not out_path:
            return
        try:
            from iconlib.normalizer import IconNormalizer
            IconNormalizer().normalize(entry.path, out_path, style)
            messagebox.showinfo("OK", f"Icon normalized to {style}: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def optimize_gui(self):
        entry = self.get_selected_entry()
        if not entry:
            messagebox.showwarning("Warning", "No icon selected")
            return
        out_path = filedialog.asksaveasfilename(
            title="Save optimized icon", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("ICO", "*.ico"), ("All files", "*.*")])
        if not out_path:
            return
        try:
            from iconlib.optimizer import IconOptimizer
            opt = IconOptimizer()
            if entry.path.lower().endswith(".ico"):
                opt.optimize_ico(entry.path, out_path)
            else:
                opt.optimize(entry.path, out_path)
            messagebox.showinfo("OK", f"Icon optimized: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def validate_gui(self):
        try:
            from iconlib.validator import IconValidator
            val = IconValidator()
            results = {e.id: val.validate(e) for e in self.library.entries}
            duplicates = val.detect_duplicates(self.library)

            win, body = self._dialog("Validation Report", "820x580")
            txt = self._readonly_text(body, wrap="none")

            for id_, r in results.items():
                txt.insert(tk.END, f"Icon {id_}\n")
                txt.insert(tk.END, f"  Exists       {r['exists']}\n")
                txt.insert(tk.END, f"  Format       {r['format']}\n")
                txt.insert(tk.END, f"  Style        {r['style']}\n")
                txt.insert(tk.END, f"  Missing DPI  {r['dpi_missing']}\n")
                txt.insert(tk.END, f"  Invalid DPI  {r['dpi_invalid']}\n")
                txt.insert(tk.END, f"  Errors       {r['errors']}\n\n")
            txt.insert(tk.END, "Duplicates\n")
            for a, b in duplicates:
                txt.insert(tk.END, f"  {a} == {b}\n")
            txt.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def rebuild_cache_gui(self):
        try:
            from iconlib.cache import IconCache
            self.cache = IconCache()
            self.cache.build(self.library)
            messagebox.showinfo("OK", f"Cache rebuilt for {len(self.library.entries)} icons")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_history(self):
        win, body = self._dialog("History", "720x460")
        frame = ttk.Frame(body)
        frame.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tv = ttk.Treeview(frame, columns=("idx", "time", "message", "icons"),
                          show="headings", selectmode="browse")
        for col, head, w, anc in (("idx", "#", 44, "e"),
                                  ("time", "Timestamp", 150, "w"),
                                  ("message", "Message", 300, "w"),
                                  ("icons", "Icons", 70, "e")):
            tv.heading(col, text=head)
            tv.column(col, width=w, anchor=anc, stretch=(col == "message"),
                      minwidth=40)
        tv.pack(fill=tk.BOTH, expand=True)
        sb.config(command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        for i, snap in enumerate(self.history.list_snapshots()):
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(snap["timestamp"]))
            tv.insert("", tk.END, values=(i, ts, snap["message"], len(snap["entries"])))

    def restore_history(self):
        index = simpledialog.askinteger("Restore Snapshot", "Enter snapshot index:")
        if index is None:
            return
        try:
            self.history.restore_snapshot(index, self.library)
            self.refresh_list()
            messagebox.showinfo("OK", f"Snapshot {index} restored")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def diff_history(self):
        a = simpledialog.askinteger("Diff", "Snapshot A index:")
        if a is None:
            return
        b = simpledialog.askinteger("Diff", "Snapshot B index:")
        if b is None:
            return
        try:
            diff = self.history.diff(a, b)
            win, body = self._dialog(f"Diff \u2014 snapshot {a} vs {b}", "760x560")
            txt = self._readonly_text(body, wrap="none")
            txt.insert(tk.END, "ADDED\n")
            for e in diff["added"]:
                txt.insert(tk.END, f"  + {e['id']:4d}  {e['name']}\n")
            txt.insert(tk.END, "\nREMOVED\n")
            for e in diff["removed"]:
                txt.insert(tk.END, f"  - {e['id']:4d}  {e['name']}\n")
            txt.insert(tk.END, "\nCHANGED\n")
            for old, new in diff["changed"]:
                txt.insert(tk.END, f"  * {old['id']:4d}  {old['name']}  (hash changed)\n")
            txt.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def compare_dll_gui(self):
        try:
            from iconlib.migrator import IconMigrator
        except ImportError as ie:
            messagebox.showerror("Error", str(ie))
            return
        dll_a = filedialog.askopenfilename(title="Select DLL A",
                                           filetypes=[("DLL", "*.dll;*.exe")])
        if not dll_a:
            return
        dll_b = filedialog.askopenfilename(title="Select DLL B",
                                           filetypes=[("DLL", "*.dll;*.exe")])
        if not dll_b:
            return
        try:
            m = IconMigrator()
            diff = m.compare(m.load_dll(dll_a), m.load_dll(dll_b))
            win, body = self._dialog("DLL Compare", "760x560")
            txt = self._readonly_text(body, wrap="none")
            txt.insert(tk.END, f"Missing in B ({len(diff['missing_in_b'])})\n")
            for i in diff["missing_in_b"]:
                txt.insert(tk.END, f"  {i['id']}\n")
            txt.insert(tk.END, f"\nMissing in A ({len(diff['missing_in_a'])})\n")
            for i in diff["missing_in_a"]:
                txt.insert(tk.END, f"  {i['id']}\n")
            txt.insert(tk.END, f"\nChanged ({len(diff['changed'])})\n")
            for a2, b2 in diff["changed"]:
                txt.insert(tk.END, f"  {a2['id']} changed\n")
            txt.insert(tk.END, f"\nDuplicates ({len(diff['duplicates'])})\n")
            for a2, b2 in diff["duplicates"]:
                txt.insert(tk.END, f"  {a2} == {b2}\n")
            txt.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def migrate_dll_gui(self):
        try:
            from iconlib.migrator import IconMigrator
        except ImportError as ie:
            messagebox.showerror("Error", str(ie))
            return
        dll_src = filedialog.askopenfilename(title="Source DLL",
                                             filetypes=[("DLL", "*.dll;*.exe")])
        if not dll_src:
            return
        dll_dst = filedialog.askopenfilename(title="Destination DLL",
                                             filetypes=[("DLL", "*.dll;*.exe")])
        if not dll_dst:
            return
        ids_str = simpledialog.askstring("IDs to migrate",
                                         "Enter IDs comma separated (e.g. 1,2,3):")
        if not ids_str:
            return
        try:
            ids_to_copy = [int(x.strip()) for x in ids_str.split(",")]
        except ValueError:
            messagebox.showerror("Error", "Invalid IDs format")
            return
        out_path = filedialog.asksaveasfilename(
            title="Save merged DLL", defaultextension=".dll",
            filetypes=[("DLL", "*.dll")])
        if not out_path:
            return
        try:
            m = IconMigrator()
            m.migrate(m.load_dll(dll_src), dll_dst, out_path, ids_to_copy)
            messagebox.showinfo("OK", f"DLL migrated: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_pack_gui(self):
        path = filedialog.asksaveasfilename(
            title="Export IconPack", defaultextension=".iconpack",
            filetypes=[("IconPack", "*.iconpack")])
        if not path:
            return
        try:
            from iconlib.iconpack import IconPack
            IconPack().export_pack(self.library, self.history, path)
            messagebox.showinfo("OK", f"IconPack exported: {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def import_pack_gui(self):
        path = filedialog.askopenfilename(
            title="Import IconPack",
            filetypes=[("IconPack", "*.iconpack")])
        if not path:
            return
        try:
            from iconlib.iconpack import IconPack
            IconPack().import_pack(path, self.library, self.history)
            self.refresh_list()
            messagebox.showinfo("OK", "IconPack imported")
        except Exception as e:
            messagebox.showerror("Error", str(e))


def main():
    root = tk.Tk()
    IconLibraryGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()