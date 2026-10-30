import numpy as np
from PIL import Image, ImageFilter, ImageEnhance


class IconTransform:
    MODES = [
        "extrude",
        "bevel",
        "emboss",
        "glow",
        "inner_shadow",
        "outer_shadow",
        "highlight",
        "metallic",
    ]

    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def transform(self, src_path, out_path, mode="extrude"):
        img = Image.open(src_path).convert("RGBA")

        if mode == "extrude":
            out = self._extrude(img)
        elif mode == "bevel":
            out = self._bevel(img)
        elif mode == "emboss":
            out = self._emboss(img)
        elif mode == "glow":
            out = self._glow(img)
        elif mode == "inner_shadow":
            out = self._inner_shadow(img)
        elif mode == "outer_shadow":
            out = self._outer_shadow(img)
        elif mode == "highlight":
            out = self._highlight(img)
        elif mode == "metallic":
            out = self._metallic(img)
        else:
            raise Exception("Unknown transform mode")

        out.save(out_path, optimize=True)
        return out_path

    # --- EXTRUDE (pseudo-3D depth) ---

    def _extrude(self, img):
        arr = np.array(img).copy()
        shadow = img.filter(ImageFilter.GaussianBlur(8))
        sh = np.array(shadow)

        # shift shadow down-right
        extr = np.zeros_like(arr)
        extr[8:, 8:, :3] = sh[:-8, :-8, :3]
        extr[:, :, 3] = arr[:, :, 3]

        # blend
        arr[:, :, :3] = (arr[:, :, :3] * 0.85 + extr[:, :, :3] * 0.15).astype("uint8")
        return Image.fromarray(arr, "RGBA")

    # --- BEVEL (3D edges) ---

    def _bevel(self, img):
        arr = np.array(img).copy()
        blur = img.filter(ImageFilter.GaussianBlur(4))
        sharp = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

        bl = np.array(blur)
        sh = np.array(sharp)

        arr[:, :, :3] = (arr[:, :, :3] * 0.7 + bl[:, :, :3] * 0.2 + sh[:, :, :3] * 0.1).astype("uint8")
        return Image.fromarray(arr, "RGBA")

    # --- EMBOSS (relief) ---

    def _emboss(self, img):
        emb = img.filter(ImageFilter.EMBOSS)
        arr = np.array(emb).copy()
        arr[:, :, 3] = np.array(img)[:, :, 3]
        return Image.fromarray(arr, "RGBA")

    # --- GLOW (soft halo) ---

    def _glow(self, img):
        glow = img.filter(ImageFilter.GaussianBlur(12))
        arr = np.array(img).copy()
        gl = np.array(glow)

        arr[:, :, :3] = (arr[:, :, :3] * 0.8 + gl[:, :, :3] * 0.2).astype("uint8")
        return Image.fromarray(arr, "RGBA")

    # --- INNER SHADOW ---

    def _inner_shadow(self, img):
        arr = np.array(img).astype(float)
        alpha = arr[:, :, 3]
        mask = (alpha > 10).astype("uint8") * 255
        inv = Image.fromarray(mask).filter(ImageFilter.GaussianBlur(3))
        inv_arr = np.array(inv).astype(float) / 255.0

        factor = 1.0 - 0.6 * inv_arr
        arr[:, :, :3] = arr[:, :, :3] * factor[:, :, None]
        return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGBA")

    # --- OUTER SHADOW ---

    def _outer_shadow(self, img):
        pad = 8
        w, h = img.size
        alpha = img.split()[3]
        shadow = alpha.filter(ImageFilter.GaussianBlur(6))

        canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))

        sh_layer = np.zeros((h + pad * 2, w + pad * 2, 4), dtype="uint8")
        sh_alpha = (np.array(shadow).astype(float) / 255.0 * 180.0).astype("uint8")
        sh_layer[pad:pad + h, pad:pad + w, 3] = sh_alpha
        canvas = Image.alpha_composite(canvas, Image.fromarray(sh_layer, "RGBA"))

        canvas.paste(img, (pad, pad), img)
        return canvas

    # --- HIGHLIGHT (top-left light) ---

    def _highlight(self, img):
        arr = np.array(img).astype(float)
        h, w, _ = arr.shape
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(xx ** 2 + yy ** 2) / np.sqrt(float(w * w + h * h))
        light = np.clip(1.0 - d, 0.0, 1.0)

        factor = 1.0 + 0.35 * light
        arr[:, :, :3] = np.clip(arr[:, :, :3] * factor[:, :, None], 0, 255)
        return Image.fromarray(arr.astype("uint8"), "RGBA")

    # --- METALLIC (sheen + contrast) ---

    def _metallic(self, img):
        img = ImageEnhance.Contrast(img).enhance(1.35)
        img = ImageEnhance.Sharpness(img).enhance(1.6)

        arr = np.array(img).astype(float)
        h, w, _ = arr.shape
        yy, xx = np.mgrid[0:h, 0:w]
        sheen = (np.sin((xx / max(w - 1, 1)) * np.pi) * 0.5 + 0.5)

        arr[:, :, :3] = np.clip(arr[:, :, :3] * (0.85 + 0.3 * sheen[:, :, None]), 0, 255)
        return Image.fromarray(arr.astype("uint8"), "RGBA")
