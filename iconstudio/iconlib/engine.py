import os
import json
import hashlib


class IconEntry:
    def __init__(self, id_, name, path, tags=None):
        self.id = id_
        self.name = name
        self.path = path
        self.tags = tags if tags else []
        self.hash = self.compute_hash()

    def compute_hash(self):
        if not os.path.isfile(self.path):
            return ""
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()


class IconLibrary:
    def __init__(self, ai_url=None, ai_key=None):
        self.entries = []
        self.next_id = 1
        self.ai_url = ai_url or os.environ.get("ICONSTUDIO_AI_URL")
        self.ai_key = ai_key or os.environ.get("ICONSTUDIO_AI_KEY")

    def add_icon(self, path, name=None):
        if name is None:
            name = os.path.basename(path)
        entry = IconEntry(self.next_id, name, path)
        self.entries.append(entry)
        self.next_id += 1

    def remove_icon(self, id_):
        self.entries = [e for e in self.entries if e.id != id_]

    def get_entry(self, id_):
        for e in self.entries:
            if e.id == id_:
                return e
        return None

    def add_tag(self, id_, tag):
        entry = self.get_entry(id_)
        if entry and tag not in entry.tags:
            entry.tags.append(tag)

    def remove_tag(self, id_, tag):
        entry = self.get_entry(id_)
        if entry and tag in entry.tags:
            entry.tags.remove(tag)

    def search(self, text):
        text = text.lower()
        results = []
        for e in self.entries:
            if text in e.name.lower():
                results.append(e)
                continue
            for t in e.tags:
                if text in t.lower():
                    results.append(e)
                    break
        return results

    def auto_tag_style(self, id_):
        from iconlib.style_detector import IconStyleDetector
        entry = self.get_entry(id_)
        if not entry:
            return
        det = IconStyleDetector()
        style = det.detect_style(entry.path)
        self.add_tag(id_, style)
        return style

    def classify_icon(self, id_):
        from iconlib.classifier import IconClassifier
        entry = self.get_entry(id_)
        if not entry:
            return "unknown"
        clf = IconClassifier(ai_url=self.ai_url, ai_key=self.ai_key)
        cat = clf.classify(entry.path)
        self.add_tag(id_, cat)
        return cat

    def analyze_icon(self, id_):
        from iconlib.semantic import IconSemanticAnalyzer
        entry = self.get_entry(id_)
        if not entry:
            raise ValueError(f"Icon with id {id_} not found")
        sem = IconSemanticAnalyzer(ai_url=self.ai_url, ai_key=self.ai_key)
        return sem.analyze(entry.path)

    def recommend_icons(self, query, cache=None):
        from iconlib.recommender import IconRecommender
        if cache is None:
            from iconlib.cache import IconCache
            cache = IconCache()
            cache.build(self)
        rec = IconRecommender(ai_url=self.ai_url, ai_key=self.ai_key)
        return rec.recommend(query, self, cache)

    def generate_icon_set(self, prompt, categories, out_dir, style="fluent"):
        from iconlib.batch_generator import IconBatchGenerator
        gen = IconBatchGenerator(ai_url=self.ai_url, ai_key=self.ai_key)
        return gen.generate_set(prompt, categories, out_dir, style)

    def generate_ai_icon(self, prompt, out_dir):
        from iconlib.ai_generator import AIIconGenerator
        ai = AIIconGenerator(api_url=self.ai_url, api_key=self.ai_key)
        png_path, ico_path = ai.generate_icon(prompt, out_dir)
        self.add_icon(ico_path)
        return png_path, ico_path

    def map_icon_action(self, id_):
        from iconlib.ui_mapper import IconUIMapper
        entry = self.get_entry(id_)
        if not entry:
            raise ValueError(f"Icon with id {id_} not found")
        mapper = IconUIMapper(ai_url=self.ai_url, ai_key=self.ai_key)
        return mapper.map_action(entry.path)

    def add_svg(self, svg_path):
        from iconlib.svg_to_ico import SVGToICO
        conv = SVGToICO()
        ico_path = svg_path + ".ico"
        conv.svg_to_ico(svg_path, ico_path)
        self.add_icon(ico_path)
        return ico_path

    def generate_fluent3d(self, prompt, out_dir):
        from iconlib.fluent3d import Fluent3DGenerator
        gen = Fluent3DGenerator(ai_url=self.ai_url, ai_key=self.ai_key)
        return gen.generate(prompt, out_dir)

    def layout_icons(self, ids, layout_type, cache, out_dir, spacing=16, padding=24):
        from iconlib.layout import IconLayoutEngine
        if cache is None:
            from iconlib.cache import IconCache
            cache = IconCache()
            cache.build(self)
        eng = IconLayoutEngine()
        return eng.layout(ids, layout_type, cache, out_dir, spacing, padding)

    def normalize_icon(self, id_, out_path, style="fluent"):
        from iconlib.normalizer import IconNormalizer
        entry = self.get_entry(id_)
        norm = IconNormalizer()
        return norm.normalize(entry.path, out_path, style)

    def apply_preset(self, id_, preset, out_path):
        from iconlib.style_presets import IconStylePresets
        entry = self.get_entry(id_)
        sp = IconStylePresets()
        return sp.apply_preset(entry.path, out_path, preset)

    def convert_style(self, id_, out_dir, target_style="fluent"):
        from iconlib.style_convert import IconStyleConverter
        entry = self.get_entry(id_)
        conv = IconStyleConverter()
        return conv.convert(entry.path, out_dir, target_style)

    def analyze_style(self, id_):
        from iconlib.style_analysis import IconStyleAnalysis
        entry = self.get_entry(id_)
        sa = IconStyleAnalysis()
        return sa.analyze(entry.path)

    def transform_icon(self, id_, out_path, mode):
        from iconlib.transform import IconTransform
        entry = self.get_entry(id_)
        tr = IconTransform()
        return tr.transform(entry.path, out_path, mode)

    def animate_fluent3d(self, prompt, out_dir, frames=12, motion="rotate"):
        from iconlib.fluent3d_anim import Fluent3DAnimation
        anim = Fluent3DAnimation(ai_url=self.ai_url, ai_key=self.ai_key)
        return anim.animate(prompt, out_dir, frames, motion)

    def build_ui_asset(self, id_, ui_type, out_dir):
        from iconlib.ui_assets import UIAssetPipeline
        from iconlib.cache import IconCache
        cache = IconCache()
        cache.build(self)
        pipe = UIAssetPipeline(cache)
        return pipe.build(id_, ui_type, out_dir)

    def generate_theme(self, id_, out_dir, style="fluent"):
        from iconlib.theme import UIThemeGenerator
        from iconlib.cache import IconCache
        entry = self.get_entry(id_)
        if not entry:
            raise ValueError(f"Icon with id {id_} not found")
        cache = IconCache()
        cache.build(self)
        gen = UIThemeGenerator(cache)
        return gen.generate(id_, out_dir, style)

    def text_icon(self, text, out_dir, style="fluent", size=256):
        from iconlib.text_icon import TextIconGenerator
        gen = TextIconGenerator()
        return gen.generate(text, out_dir, style, size)

    def data_icon(self, data, out_dir, chart="line", style="fluent", size=256):
        from iconlib.data_icon import DataIconGenerator
        gen = DataIconGenerator()
        return gen.generate(data, out_dir, chart, style, size)

    def data_batch(self, source, out_dir, chart="line", style="fluent", size=256):
        from iconlib.data_batch import DataIconBatch
        gen = DataIconBatch()
        return gen.generate(source, out_dir, chart, style, size)

    def geo_icon(self, geo, out_dir, symbol="pin", style="fluent", size=256):
        from iconlib.geo_icon import GeoIconGenerator
        gen = GeoIconGenerator()
        return gen.generate(geo, out_dir, symbol, style, size)

    def geo_batch(self, source, out_dir, symbol="pin", style="fluent", size=256):
        from iconlib.geo_batch import GeoIconBatch
        gen = GeoIconBatch()
        return gen.generate(source, out_dir, symbol, style, size)

    def audio_icon(self, source, out_dir, style="fluent", size=256, mode="waveform",
                   palette=False):
        from iconlib.audio_icon import AudioIconGenerator
        return AudioIconGenerator().generate(source, out_dir, style, size, mode,
                                             palette=palette)

    def audio_batch(self, source, out_dir, style="fluent", size=256, mode="waveform",
                    palette=False):
        from iconlib.audio_batch import AudioIconBatch
        return AudioIconBatch().generate(source, out_dir, style, size, mode,
                                         palette=palette)

    def texture_icon(self, texture, out_dir, style="fluent", size=256, seed=None):
        from iconlib.texture_icon import TextureIconGenerator
        return TextureIconGenerator().generate(texture, out_dir, style, size, seed)

    def texture_batch(self, source, out_dir, style="fluent", size=256):
        from iconlib.texture_batch import TextureIconBatch
        return TextureIconBatch().generate(source, out_dir, style, size)

    def generate_avatar3d(self, prompt, out_dir, style="fluent3d", role=None,
                          webp=False, sprite=False):
        from iconlib.avatar3d import Fluent3DAvatar
        av = Fluent3DAvatar(ai_url=self.ai_url, ai_key=self.ai_key)
        return av.generate(prompt, out_dir, style, role=role, webp=webp, sprite=sprite)

    def avatar_batch(self, source, out_dir, style="fluent3d"):
        from iconlib.avatar_batch import Fluent3DAvatarBatch
        batch = Fluent3DAvatarBatch(ai_url=self.ai_url, ai_key=self.ai_key)
        return batch.generate(source, out_dir, style)

    def validate_icon(self, id_):
        from iconlib.validator import IconValidator
        entry = self.get_entry(id_)
        val = IconValidator()
        return val.validate(entry)

    def validate_all(self):
        from iconlib.validator import IconValidator
        val = IconValidator()
        results = {}
        for e in self.entries:
            results[e.id] = val.validate(e)
        results["duplicates"] = val.detect_duplicates(self)
        return results

    def snapshot(self, message="update"):
        from iconlib.history import IconLibraryHistory
        hist = IconLibraryHistory()
        hist.add_snapshot(self, message)

    def to_dict(self):
        return {
            "next_id": self.next_id,
            "entries": [
                {
                    "id": e.id,
                    "name": e.name,
                    "path": e.path,
                    "tags": e.tags,
                    "hash": e.hash,
                }
                for e in self.entries
            ],
        }

    def from_dict(self, data):
        self.entries = []
        self.next_id = data.get("next_id", 1)
        for item in data.get("entries", []):
            entry = IconEntry(
                item["id"],
                item["name"],
                item["path"],
                item.get("tags", [])
            )
            entry.hash = item.get("hash", "")
            self.entries.append(entry)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.from_dict(data)
