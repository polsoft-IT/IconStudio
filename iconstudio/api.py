"""
IconStudio Plugin API
ASCII-only
"""

import os

from iconlib.engine import IconLibrary
from iconlib.dll_import import DLLIconImporter
from iconlib.dll_export import DLLBuilder
from iconlib.dpi_generator import DPIGenerator
from iconlib.svg_to_ico import SVGToICO
from iconlib.style_detector import IconStyleDetector
from iconlib.history import IconLibraryHistory
from iconlib.cache import IconCache


class IconStudio:
    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url or os.environ.get("ICONSTUDIO_AI_URL")
        self.ai_key = ai_key or os.environ.get("ICONSTUDIO_AI_KEY")
        self.library = IconLibrary(ai_url=self.ai_url, ai_key=self.ai_key)
        self.history = IconLibraryHistory()
        self.cache = IconCache()

    # --- BASIC LIBRARY OPS ---

    def load_library(self, path):
        self.library.load(path)
        self.cache.build(self.library)
        return True

    def save_library(self, path):
        self.library.save(path)
        return True

    def add_icon(self, path, name=None):
        self.library.add_icon(path, name)
        self.history.add_snapshot(self.library, "add icon")
        return True

    def remove_icon(self, id_):
        self.library.remove_icon(id_)
        self.history.add_snapshot(self.library, "remove icon")
        return True

    # --- IMPORT / EXPORT DLL ---

    def import_from_dll(self, dll_path):
        importer = DLLIconImporter(dll_path)
        icons = importer.import_icons()

        out_paths = []
        for item in icons:
            out_path = f"imported_{item['id']}.ico"
            with open(out_path, "wb") as f:
                f.write(item["ico"])
            self.library.add_icon(out_path)
            out_paths.append(out_path)

        self.history.add_snapshot(self.library, "import dll")
        return out_paths

    def export_to_dll(self, out_path):
        builder = DLLBuilder()
        base_icon_id = 200
        group_id = 100

        for entry in self.library.entries:
            if os.path.isfile(entry.path) and entry.path.lower().endswith(".ico"):
                builder.add_icon(entry.path, group_id, base_icon_id)
                group_id += 1
                base_icon_id += 20

        builder.build(out_path)
        self.history.add_snapshot(self.library, "export dll")
        return True

    # --- DPI GENERATION ---

    def generate_dpi(self, id_, out_path):
        entry = self.library.get_entry(id_)
        if not entry:
            raise ValueError(f"Icon with ID {id_} not found")
        gen = DPIGenerator()
        gen.generate_dpi_set(entry.path, out_path)
        self.history.add_snapshot(self.library, "dpi generation")
        return out_path

    # --- SVG IMPORT ---

    def import_svg(self, svg_path):
        conv = SVGToICO()
        ico_path = svg_path + ".ico"
        conv.svg_to_ico(svg_path, ico_path)
        self.library.add_icon(ico_path)
        self.history.add_snapshot(self.library, "import svg")
        return ico_path

    # --- STYLE DETECTION ---

    def detect_style(self, id_):
        entry = self.library.get_entry(id_)
        if not entry:
            raise ValueError(f"Icon with ID {id_} not found")
        det = IconStyleDetector()
        style = det.detect_style(entry.path)
        self.library.add_tag(id_, style)
        self.history.add_snapshot(self.library, "style detection")
        return style

    # --- HISTORY ---

    def list_history(self):
        return self.history.list_snapshots()

    def restore_history(self, index):
        self.history.restore_snapshot(index, self.library)
        self.history.add_snapshot(self.library, f"restore {index}")
        return True

    def diff_history(self, a, b):
        return self.history.diff(a, b)

    # --- ADVANCED / AI INTEGRATIONS ---

    def classify_icon(self, id_):
        return self.library.classify_icon(id_)

    def analyze_icon(self, id_):
        return self.library.analyze_icon(id_)

    def recommend_icons(self, query):
        if not self.cache.meta:
            self.cache.build(self.library)
        return self.library.recommend_icons(query, self.cache)

    def generate_icon_set(self, prompt, categories, out_dir, style="fluent"):
        return self.library.generate_icon_set(prompt, categories, out_dir, style)

    def map_icon_action(self, id_):
        return self.library.map_icon_action(id_)

    def generate_fluent3d(self, prompt, out_dir):
        from iconlib.fluent3d import Fluent3DGenerator
        gen = Fluent3DGenerator(ai_url=self.ai_url, ai_key=self.ai_key)
        return gen.generate(prompt, out_dir)

    def layout_icons(self, ids, layout_type, out_dir, spacing=16, padding=24):
        from iconlib.layout import IconLayoutEngine
        if not self.cache.meta:
            self.cache.build(self.library)
        eng = IconLayoutEngine()
        return eng.layout(ids, layout_type, self.cache, out_dir, spacing, padding)

    # --- STYLE ANALYSIS / TRANSFORM / ANIMATION ---

    def analyze_style(self, id_):
        return self.library.analyze_style(id_)

    def transform_icon(self, id_, out_path, mode):
        return self.library.transform_icon(id_, out_path, mode)

    def animate_fluent3d(self, prompt, out_dir, frames=12, motion="rotate"):
        return self.library.animate_fluent3d(prompt, out_dir, frames, motion)

    def build_ui_asset(self, id_, ui_type, out_dir):
        return self.library.build_ui_asset(id_, ui_type, out_dir)

    def generate_theme(self, base_id, out_dir, style="fluent"):
        from iconlib.theme import UIThemeGenerator
        if not self.cache.meta:
            self.cache.build(self.library)
        gen = UIThemeGenerator(self.cache)
        return gen.generate(base_id, out_dir, style)

    def text_icon(self, text, out_dir, style="fluent", size=256):
        return self.library.text_icon(text, out_dir, style, size)

    def data_icon(self, data, out_dir, chart="line", style="fluent", size=256, add=False, name=None):
        res = self.library.data_icon(data, out_dir, chart, style, size)
        if add:
            self.library.add_icon(res["ico"], name=name or f"data-{chart}")
            self.history.add_snapshot(self.library, "data icon")
        return res

    def data_batch(self, source, out_dir, chart="line", style="fluent", size=256, add=False):
        res = self.library.data_batch(source, out_dir, chart, style, size)
        if add:
            for item in res["icons"]:
                self.library.add_icon(item["ico"], name=item["name"])
            self.history.add_snapshot(self.library, "data batch")
        return res

    def geo_icon(self, geo, out_dir, symbol="pin", style="fluent", size=256,
                 add=False, name=None):
        res = self.library.geo_icon(geo, out_dir, symbol, style, size)
        if add:
            self.library.add_icon(res["ico"], name=name or f"geo-{res['symbol']}")
            self.history.add_snapshot(self.library, "geo icon")
        return res

    def geo_batch(self, source, out_dir, symbol="pin", style="fluent", size=256,
                  add=False):
        res = self.library.geo_batch(source, out_dir, symbol, style, size)
        if add:
            for item in res["icons"]:
                self.library.add_icon(item["ico"], name=item["name"])
            self.history.add_snapshot(self.library, "geo batch")
        return res

    def avatar3d(self, prompt, out_dir, style="fluent3d", role=None,
                 webp=False, sprite=False, add=False, name=None):
        res = self.library.generate_avatar3d(
            prompt, out_dir, style, role=role, webp=webp, sprite=sprite)
        if add:
            self.library.add_icon(res["ico"], name=name or f"avatar-{res['style']}")
            self.history.add_snapshot(self.library, "avatar 3d")
        return res

    def avatar_batch(self, source, out_dir, style="fluent3d", add=False):
        res = self.library.avatar_batch(source, out_dir, style)
        if add:
            for item in res["avatars"]:
                self.library.add_icon(item["ico"], name=item["name"])
            self.history.add_snapshot(self.library, "avatar batch")
        return res

    def audio_icon(self, source, out_dir, style="fluent", size=256, mode="waveform",
                   palette=False, add=False, name=None):
        res = self.library.audio_icon(source, out_dir, style, size, mode, palette)
        if add:
            self.library.add_icon(res["ico"], name=name or f"audio-{res['mode']}")
            self.history.add_snapshot(self.library, "audio icon")
        return res

    def audio_batch(self, source, out_dir, style="fluent", size=256, mode="waveform",
                    palette=False, add=False):
        res = self.library.audio_batch(source, out_dir, style, size, mode, palette)
        if add:
            for item in res["icons"]:
                self.library.add_icon(item["ico"], name=item["name"])
            self.history.add_snapshot(self.library, "audio batch")
        return res

    def texture_icon(self, texture, out_dir, style="fluent", size=256, seed=None,
                     add=False, name=None):
        res = self.library.texture_icon(texture, out_dir, style, size, seed)
        if add:
            self.library.add_icon(res["ico"], name=name or f"texture-{res['texture_name']}")
            self.history.add_snapshot(self.library, "texture icon")
        return res

    def texture_batch(self, source, out_dir, style="fluent", size=256, add=False):
        res = self.library.texture_batch(source, out_dir, style, size)
        if add:
            for item in res["icons"]:
                self.library.add_icon(item["ico"], name=item["name"])
            self.history.add_snapshot(self.library, "texture batch")
        return res

    def convert_style(self, id_, out_dir, target_style="fluent"):
        from iconlib.style_convert import IconStyleConverter
        entry = self.library.get_entry(id_)
        if not entry:
            raise ValueError(f"Icon with ID {id_} not found")
        conv = IconStyleConverter()
        return conv.convert(entry.path, out_dir, target_style)

