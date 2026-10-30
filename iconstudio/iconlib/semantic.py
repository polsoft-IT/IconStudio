import base64
import json
import numpy as np
from PIL import Image
import requests


class IconSemanticAnalyzer:
    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url
        self.ai_key = ai_key

    # --- MAIN ENTRY POINT ---

    def analyze(self, path):
        img = Image.open(path).convert("RGBA")

        visual = self._visual_description(img)
        semantic = self._semantic_guess(img)
        ux = self._ux_context(semantic)

        ai_desc = None
        if self.ai_url:
            ai_desc = self._ai_description(path)

        return {
            "visual": visual,
            "semantic": semantic,
            "ux": ux,
            "ai": ai_desc
        }

    # --- VISUAL DESCRIPTION ---

    def _visual_description(self, img):
        arr = np.array(img)
        pixels = arr.reshape(-1, 4)
        pixels = pixels[pixels[:, 3] > 10]

        if len(pixels) == 0:
            pixels = arr.reshape(-1, 4)

        brightness = float(np.mean(pixels[:, :3]))
        max_rgb = np.max(pixels[:, :3], axis=1)
        min_rgb = np.min(pixels[:, :3], axis=1)
        saturation = float(np.mean(max_rgb - min_rgb))

        r = float(np.mean(pixels[:, 0]))
        g = float(np.mean(pixels[:, 1]))
        b = float(np.mean(pixels[:, 2]))

        return {
            "brightness": brightness,
            "saturation": saturation,
            "dominant_color": [r, g, b],
            "shape": self._detect_shape(arr),
            "style": self._detect_style(arr)
        }

    # --- SHAPE DETECTION ---

    def _detect_shape(self, arr):
        h, w, _ = arr.shape

        # detect circle-like shape
        center = arr[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4, :]
        if np.mean(center[:, :, 3]) > 200:
            return "circle"

        # detect rectangle-like shape
        if np.mean(arr[:, :, 3]) > 150:
            return "rectangle"

        return "complex"

    # --- STYLE DETECTION ---

    def _detect_style(self, arr):
        brightness = float(np.mean(arr[:, :, :3]))
        max_rgb = np.max(arr[:, :, :3], axis=2)
        min_rgb = np.min(arr[:, :, :3], axis=2)
        saturation = float(np.mean(max_rgb - min_rgb))
        rgb_flat = arr[:, :, :3].reshape(-1, 3)
        unique_colors = len(np.unique(rgb_flat, axis=0))

        if unique_colors < 8 and saturation < 20:
            return "monochrome"

        if brightness > 150 and saturation < 60:
            return "fluent"

        return "classic"

    # --- SEMANTIC GUESS (HEURISTIC) ---

    def _semantic_guess(self, img):
        arr = np.array(img)

        r, g, b = np.mean(arr[:, :, 0]), np.mean(arr[:, :, 1]), np.mean(arr[:, :, 2])

        # folder
        if r > 180 and g > 150 and b < 100:
            return "folder"

        # document
        if np.mean(arr[:, :, :3]) > 200:
            return "document"

        # error
        if r > 180 and g < 80 and b < 80:
            return "error"

        # warning
        if r > 200 and g > 180 and b < 80:
            return "warning"

        # checkmark
        if g > 160 and r < 120 and b < 120:
            return "check"

        # cloud
        if r > 180 and g > 180 and b > 200:
            return "cloud"

        return "unknown"

    # --- UX CONTEXT ---

    def _ux_context(self, semantic):
        mapping = {
            "folder": "Used for navigation, file grouping, storage, and directory representation.",
            "document": "Represents files, text, notes, or content.",
            "error": "Used for critical alerts, failures, and blocking actions.",
            "warning": "Used for caution, risk, or attention-required actions.",
            "check": "Used for confirmation, success, completion, or approval.",
            "cloud": "Used for online storage, sync, network services, or remote access."
        }
        return mapping.get(semantic, "General-purpose icon with no specific UX context.")

    # --- AI DESCRIPTION ---

    def _ai_description(self, path):
        with open(path, "rb") as f:
            img_bytes = f.read()

        payload = {
            "image": base64.b64encode(img_bytes).decode("ascii")
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.ai_key}"
        }

        try:
            r = requests.post(self.ai_url, headers=headers, data=json.dumps(payload), timeout=10)
            if r.status_code != 200:
                return None
            data = r.json()
            return data.get("description", None)
        except Exception:
            return None
