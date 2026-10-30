import numpy as np
from PIL import Image


class IconClassifier:
    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url
        self.ai_key = ai_key

    def classify(self, path):
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return "unknown"
        cat = self._heuristic(img)
        if cat != "unknown":
            return cat
        if self.ai_url:
            return self._ai_classify(path)
        return "unknown"

    def _heuristic(self, img):
        arr = np.array(img)
        edges = self._edges(img)
        if self._is_folder(arr):
            return "folder"
        if self._is_document(arr):
            return "document"
        if self._is_warning(arr, edges):
            return "warning"
        if self._is_error(arr):
            return "error"
        if self._is_check(arr):
            return "check"
        if self._is_cloud(arr):
            return "cloud"
        if self._is_gear(edges):
            return "settings"
        if self._is_user(arr):
            return "user"
        return "unknown"

    def _edges(self, img):
        gray = img.convert("L")
        arr = np.array(gray)
        diff_h = np.abs(arr[:, 1:].astype(int) - arr[:, :-1].astype(int))
        diff_v = np.abs(arr[1:, :].astype(int) - arr[:-1, :].astype(int))
        return np.mean(diff_h) + np.mean(diff_v)

    def _is_folder(self, arr):
        r, g, b = np.mean(arr[:, :, 0]), np.mean(arr[:, :, 1]), np.mean(arr[:, :, 2])
        return r > 180 and g > 150 and b < 100

    def _is_document(self, arr):
        return np.mean(arr[:, :, :3]) > 200

    def _is_warning(self, arr, edges):
        r, g, b = np.mean(arr[:, :, 0]), np.mean(arr[:, :, 1]), np.mean(arr[:, :, 2])
        return r > 200 and g > 180 and b < 80 and edges > 0.25

    def _is_error(self, arr):
        r, g, b = np.mean(arr[:, :, 0]), np.mean(arr[:, :, 1]), np.mean(arr[:, :, 2])
        return r > 180 and g < 80 and b < 80

    def _is_check(self, arr):
        r, g, b = np.mean(arr[:, :, 0]), np.mean(arr[:, :, 1]), np.mean(arr[:, :, 2])
        return g > 160 and r < 120 and b < 120

    def _is_cloud(self, arr):
        r, g, b = np.mean(arr[:, :, 0]), np.mean(arr[:, :, 1]), np.mean(arr[:, :, 2])
        return r > 180 and g > 180 and b > 200

    def _is_gear(self, edges):
        return edges > 0.35

    def _is_user(self, arr):
        brightness = np.mean(arr[:, :, :3])
        return brightness < 120

    def _ai_classify(self, path):
        try:
            import base64
            import json
            import requests
            with open(path, "rb") as f:
                img_bytes = f.read()
            payload = {"image": base64.b64encode(img_bytes).decode("ascii")}
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.ai_key}"
            }
            r = requests.post(self.ai_url, headers=headers, data=json.dumps(payload))
            if r.status_code != 200:
                return "unknown"
            data = r.json()
            return data.get("category", "unknown")
        except Exception:
            return "unknown"
