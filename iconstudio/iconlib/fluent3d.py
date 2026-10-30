import os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from iconlib.ai_generator import AIIconGenerator
from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer


class Fluent3DGenerator:
    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url
        self.ai_key = ai_key

    # --- MAIN PIPELINE ---

    def generate(self, prompt, out_dir):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Step 1: AI base render
        base_png = os.path.join(out_dir, "base.png")
        ai = AIIconGenerator(api_url=self.ai_url, api_key=self.ai_key)
        ai.generate_png(f"{prompt}, fluent 3d icon, soft shadows, glossy highlights", base_png)

        # Step 2: apply 3D shading
        shaded_png = os.path.join(out_dir, "shaded.png")
        self._apply_3d_shading(base_png, shaded_png)

        # Step 3: normalize to Fluent 3D spec
        norm_png = os.path.join(out_dir, "norm.png")
        self._normalize_fluent3d(shaded_png, norm_png)

        # Step 4: DPI + ICO
        norm = IconNormalizer()
        ico_path = os.path.join(out_dir, "fluent3d.ico")
        norm.normalize(norm_png, ico_path, "fluent")

        # Step 5: optimize
        opt = IconOptimizer()
        opt_path = os.path.join(out_dir, "fluent3d_opt.ico")
        opt.optimize_ico(ico_path, opt_path)

        return {
            "base": base_png,
            "shaded": shaded_png,
            "normalized": norm_png,
            "ico": opt_path,
        }

    # --- 3D SHADING ---

    def _apply_3d_shading(self, src, dst):
        img = Image.open(src).convert("RGBA")

        # soft shadow
        shadow = img.filter(ImageFilter.GaussianBlur(12))

        # blend shadow
        arr = np.array(img).copy()
        sh = np.array(shadow)
        arr[:, :, :3] = (arr[:, :, :3] * 0.85 + sh[:, :, :3] * 0.15).astype("uint8")

        # glossy highlight
        gloss = img.filter(ImageFilter.GaussianBlur(4))
        gloss_arr = np.array(gloss)
        arr[:, :, :3] = (arr[:, :, :3] * 0.9 + gloss_arr[:, :, :3] * 0.1).astype("uint8")

        # ambient occlusion (AO)
        ao = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
        ao_arr = np.array(ao)
        arr[:, :, :3] = (arr[:, :, :3] * 0.95 + ao_arr[:, :, :3] * 0.05).astype("uint8")

        Image.fromarray(arr, "RGBA").save(dst, optimize=True)

    # --- FLUENT 3D NORMALIZATION ---

    def _normalize_fluent3d(self, src, dst):
        img = Image.open(src).convert("RGBA")

        # pastel colors
        img = ImageEnhance.Color(img).enhance(0.75)

        # soft contrast
        img = ImageEnhance.Contrast(img).enhance(0.9)

        # soft brightness
        img = ImageEnhance.Brightness(img).enhance(1.1)

        # bloom
        bloom = img.filter(ImageFilter.GaussianBlur(6))
        arr = np.array(img).copy()
        bl = np.array(bloom)
        arr[:, :, :3] = (arr[:, :, :3] * 0.85 + bl[:, :, :3] * 0.15).astype("uint8")

        Image.fromarray(arr, "RGBA").save(dst, optimize=True)
