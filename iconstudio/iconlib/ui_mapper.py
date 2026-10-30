import base64
import json
import numpy as np
from PIL import Image
import requests


class IconUIMapper:
    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url
        self.ai_key = ai_key

    # --- MAIN ENTRY POINT ---

    def map_action(self, path):
        img = Image.open(path).convert("RGBA")

        semantic = self._semantic_guess(img)
        visual = self._visual_features(img)

        action = self._map_semantic_to_action(semantic, visual)

        ai_action = None
        if self.ai_url:
            ai_action = self._ai_map(path)

        return {
            "semantic": semantic,
            "visual": visual,
            "action": action,
            "ai_action": ai_action,
        }

    # --- SEMANTIC GUESS ---

    def _semantic_guess(self, img):
        arr = np.array(img)
        if arr.shape[2] == 4:
            mask = arr[:, :, 3] > 10
            if np.any(mask):
                pixels = arr[mask]
            else:
                pixels = arr.reshape(-1, 4)
        else:
            pixels = arr.reshape(-1, 3)

        r = float(np.mean(pixels[:, 0]))
        g = float(np.mean(pixels[:, 1]))
        b = float(np.mean(pixels[:, 2]))

        # delete / error (red)
        if r > 180 and g < 80 and b < 80:
            return "error"

        # warning (yellow triangle / gold)
        if r > 200 and g > 180 and b < 80:
            return "warning"

        # checkmark (green)
        if g > 160 and r < 120 and b < 120:
            return "check"

        # cloud (blue/white)
        if r > 180 and g > 180 and b > 200:
            return "cloud"

        # folder (yellow/orange)
        if r > 180 and g > 150 and b < 100:
            return "folder"

        # document (mostly white)
        if np.mean(pixels[:, :3]) > 200:
            return "document"

        return "unknown"

    # --- VISUAL FEATURES ---

    def _visual_features(self, img):
        arr = np.array(img)
        if arr.shape[2] == 4:
            mask = arr[:, :, 3] > 10
            if np.any(mask):
                pixels = arr[mask][:, :3]
            else:
                pixels = arr[:, :, :3].reshape(-1, 3)
        else:
            pixels = arr[:, :, :3].reshape(-1, 3)

        brightness = float(np.mean(pixels))
        max_rgb = np.max(pixels, axis=1)
        min_rgb = np.min(pixels, axis=1)
        saturation = float(np.mean(max_rgb - min_rgb))

        return {
            "brightness": brightness,
            "saturation": saturation,
        }

    # --- SEMANTIC -> ACTION MAPPING ---

    def _map_semantic_to_action(self, semantic, visual):
        mapping = {
            "error": "delete",
            "warning": "alert",
            "check": "confirm",
            "cloud": "cloud_sync",
            "folder": "open_folder",
            "document": "open_file",
        }
        return mapping.get(semantic, "generic_action")

    # --- AI MAPPING ---

    def _ai_map(self, path):
        with open(path, "rb") as f:
            img_bytes = f.read()

        payload = {
            "image": base64.b64encode(img_bytes).decode("ascii"),
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.ai_key}",
        }

        try:
            r = requests.post(self.ai_url, headers=headers, data=json.dumps(payload), timeout=10)
            if r.status_code != 200:
                return None
            data = r.json()
            return data.get("action", None)
        except Exception:
            return None
