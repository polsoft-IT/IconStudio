from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import os

from iconlib.style_analysis import IconStyleAnalysis
from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer


class StyleConverter:
    def __init__(self):
        pass

    def classic_to_fluent(self, src_path, out_path):
        img = Image.open(src_path).convert("RGBA")
        img = self._remove_outline(img)
        img = ImageEnhance.Color(img).enhance(0.55)
        img = ImageEnhance.Contrast(img).enhance(0.85)
        img = ImageEnhance.Brightness(img).enhance(1.20)
        img = img.filter(ImageFilter.SMOOTH_MORE)
        img = ImageEnhance.Brightness(img).enhance(1.10)
        img = ImageEnhance.Color(img).enhance(0.75)
        img.save(out_path)
        return out_path

    def _remove_outline(self, img):
        arr = np.array(img)
        gray = np.mean(arr[:, :, :3], axis=2)
        edges_h = np.abs(np.diff(gray, axis=1))
        edges_v = np.abs(np.diff(gray, axis=0))
        edges_h = np.pad(edges_h, ((0, 0), (1, 0)), mode="constant")
        edges_v = np.pad(edges_v, ((1, 0), (0, 0)), mode="constant")
        edges = np.maximum(edges_h, edges_v)
        edges = (edges > 25).astype("uint8") * 255
        edges_img = Image.fromarray(edges).filter(ImageFilter.GaussianBlur(2))
        edges = np.array(edges_img)
        arr[:, :, :3] = (arr[:, :, :3] * (1 - edges[:, :, None] / 255.0)).astype("uint8")
        return Image.fromarray(arr.astype("uint8"), "RGBA")


class IconStyleConverter:
    """Full style converter: Classic -> Fluent, Fluent -> Monochrome, Skeuomorphic -> Flat."""

    TARGETS = ["fluent", "monochrome", "flat"]

    def __init__(self):
        self.analyzer = IconStyleAnalysis()

    # --- MAIN ENTRY POINT ---

    def convert(self, src_path, out_dir, target_style="fluent"):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        # Step 1: analyze original
        original_style = self.analyzer.analyze(src_path)

        # Step 2: load image
        img = Image.open(src_path).convert("RGBA")

        # Step 3: convert style
        if target_style == "fluent":
            out = self._to_fluent(img)
        elif target_style == "monochrome":
            out = self._to_monochrome(img)
        elif target_style == "flat":
            out = self._to_flat(img)
        else:
            raise Exception("Unknown target style")

        # Step 4: save PNG
        png_path = os.path.join(out_dir, "converted.png")
        out.save(png_path, optimize=True)

        # Step 5: normalize DPI + ICO
        norm = IconNormalizer()
        ico_path = os.path.join(out_dir, "converted.ico")
        norm.normalize(png_path, ico_path, target_style)

        # Step 6: optimize
        opt = IconOptimizer()
        opt_path = os.path.join(out_dir, "converted_opt.ico")
        opt.optimize_ico(ico_path, opt_path)

        # Step 7: analyze new style
        new_style = self.analyzer.analyze(opt_path)

        return {
            "png": png_path,
            "ico": opt_path,
            "original_style": original_style,
            "new_style": new_style,
        }

    # --- CONVERSION: CLASSIC -> FLUENT ---

    def _to_fluent(self, img):
        # pastel colors
        img = ImageEnhance.Color(img).enhance(0.75)

        # soft brightness
        img = ImageEnhance.Brightness(img).enhance(1.1)

        # soft contrast
        img = ImageEnhance.Contrast(img).enhance(0.9)

        # soft bloom
        bloom = img.filter(ImageFilter.GaussianBlur(6))
        arr = np.array(img).copy()
        bl = np.array(bloom)
        arr[:, :, :3] = (arr[:, :, :3] * 0.85 + bl[:, :, :3] * 0.15).astype("uint8")

        return Image.fromarray(arr, "RGBA")

    # --- CONVERSION: ANY -> MONOCHROME ---

    def _to_monochrome(self, img):
        gray = img.convert("L")
        arr = np.array(gray)
        rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
        rgba[:, :, 0] = arr
        rgba[:, :, 1] = arr
        rgba[:, :, 2] = arr
        rgba[:, :, 3] = np.array(img)[:, :, 3]
        return Image.fromarray(rgba, "RGBA")

    # --- CONVERSION: SKEUOMORPHIC -> FLAT ---

    def _to_flat(self, img):
        # remove shading
        flat = img.filter(ImageFilter.SMOOTH_MORE)

        # remove gradients
        flat = ImageEnhance.Color(flat).enhance(0.5)

        # increase brightness
        flat = ImageEnhance.Brightness(flat).enhance(1.2)

        # reduce contrast
        flat = ImageEnhance.Contrast(flat).enhance(0.8)

        return flat
