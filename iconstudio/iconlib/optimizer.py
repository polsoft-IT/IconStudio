import os
import hashlib
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np


class IconOptimizer:
    def __init__(self):
        pass

    def optimize(self, src_path, out_path):
        img = Image.open(src_path).convert("RGBA")
        img = img.filter(ImageFilter.SMOOTH_MORE)
        img = ImageEnhance.Color(img).enhance(0.95)
        img = ImageEnhance.Contrast(img).enhance(0.95)
        img = self._clean_alpha(img)
        img = self._reduce_size(img)
        img.save(out_path, optimize=True)
        return out_path

    def _clean_alpha(self, img):
        arr = np.array(img)
        alpha = arr[:, :, 3]
        alpha[alpha < 10] = 0
        arr[:, :, 3] = alpha
        return Image.fromarray(arr, "RGBA")

    def _reduce_size(self, img):
        w, h = img.size
        if w > 512 or h > 512:
            img = img.resize((512, 512), Image.LANCZOS)
            img = img.filter(ImageFilter.SMOOTH)
        return img

    def detect_duplicates(self, library):
        seen = {}
        dup = []
        for e in library.entries:
            h = self._hash_file(e.path)
            if h in seen:
                dup.append((seen[h], e.id))
            else:
                seen[h] = e.id
        return dup

    def _hash_file(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()

    def optimize_ico(self, src_path, out_path):
        img = Image.open(src_path)
        if img.format and img.format.lower() != "ico":
            return self.optimize(src_path, out_path)
        sizes = img.info.get("sizes", [])
        valid_sizes = [s for s in sizes if s[0] <= 256]
        if not valid_sizes:
            return self.optimize(src_path, out_path)
        layers = []
        for s in valid_sizes:
            layer = img.resize((s[0], s[0]), Image.LANCZOS)
            layer = layer.filter(ImageFilter.SMOOTH_MORE)
            layers.append(layer)
        largest = max(layers, key=lambda i: i.size[0])
        largest.save(
            out_path,
            format="ICO",
            sizes=[(s[0], s[0]) for s in valid_sizes]
        )
        return out_path
