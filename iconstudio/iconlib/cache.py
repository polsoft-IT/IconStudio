import os
from PIL import Image
import numpy as np


class IconCache:
    def __init__(self):
        self.meta = {}
        self.thumb64 = {}
        self.thumb128 = {}
        self.full = {}
        self.index_name = {}
        self.index_tag = {}
        self.index_style = {}
        self.index_hash = {}
        self.index_dpi = {}

    def build(self, library):
        from iconlib.style_detector import IconStyleDetector
        det = IconStyleDetector()
        self.meta = {}
        self.thumb64 = {}
        self.thumb128 = {}
        self.index_name = {}
        self.index_tag = {}
        self.index_style = {}
        self.index_hash = {}
        self.index_dpi = {}
        for e in library.entries:
            meta = {
                "id": e.id,
                "name": e.name.lower(),
                "tags": [t.lower() for t in e.tags],
                "path": e.path,
                "hash": e.hash,
            }
            self.meta[e.id] = meta
            try:
                img = Image.open(e.path).convert("RGBA")
                style = det.detect_style(e.path)
            except Exception:
                img = None
                style = "unknown"
            meta["style"] = style
            if img:
                try:
                    self.thumb64[e.id] = img.resize((64, 64), Image.LANCZOS)
                    self.thumb128[e.id] = img.resize((128, 128), Image.LANCZOS)
                except Exception:
                    pass
            self.index_name.setdefault(meta["name"], []).append(e.id)
            for t in meta["tags"]:
                self.index_tag.setdefault(t, []).append(e.id)
            self.index_style.setdefault(style, []).append(e.id)
            self.index_hash[e.hash] = e.id
            dpi = self._detect_dpi(e.path)
            for d in dpi:
                self.index_dpi.setdefault(d, []).append(e.id)

    def get_full(self, id_):
        if id_ in self.full:
            return self.full[id_]
        path = self.meta[id_]["path"]
        img = Image.open(path).convert("RGBA")
        self.full[id_] = img
        return img

    def _detect_dpi(self, path):
        try:
            img = Image.open(path)
            if img.format and img.format.lower() == "ico":
                sizes = img.info.get("sizes", [])
                return [s[0] for s in sizes]
            else:
                return [img.width]
        except Exception:
            return []

    def search(self, text):
        text = text.lower()
        results = set()
        for name, ids in self.index_name.items():
            if text in name:
                results.update(ids)
        for tag, ids in self.index_tag.items():
            if text in tag:
                results.update(ids)
        if text in self.index_style:
            results.update(self.index_style[text])
        return list(results)

    def find_duplicates(self):
        dup = []
        seen = {}
        for id_, meta in self.meta.items():
            h = meta["hash"]
            if h in seen:
                dup.append((seen[h], id_))
            else:
                seen[h] = id_
        return dup
