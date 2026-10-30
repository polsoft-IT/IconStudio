import os
import hashlib
from PIL import Image
import numpy as np

DPI_REQUIRED = [16, 32, 48, 64, 128, 256]


class IconValidator:
    def __init__(self):
        pass

    def validate(self, entry):
        results = {
            "exists": False,
            "format": "unknown",
            "dpi_missing": [],
            "dpi_invalid": [],
            "hash": entry.hash,
            "duplicate": False,
            "style": "unknown",
            "errors": []
        }
        if not os.path.isfile(entry.path):
            results["errors"].append("file_not_found")
            return results
        results["exists"] = True
        try:
            img = Image.open(entry.path)
            fmt = img.format
            results["format"] = fmt.lower() if fmt else "unknown"
        except Exception:
            results["errors"].append("invalid_format")
            return results
        if results["format"] == "ico":
            try:
                sizes = img.info.get("sizes", [])
                sizes_list = [s[0] for s in sizes]
                for req in DPI_REQUIRED:
                    if req not in sizes_list:
                        results["dpi_missing"].append(req)
                for s in sizes_list:
                    if s <= 0 or s > 1024:
                        results["dpi_invalid"].append(s)
            except Exception:
                results["errors"].append("ico_parse_error")
        else:
            if img.width < 256 or img.height < 256:
                results["dpi_invalid"].append(f"{img.width}x{img.height}")
        results["style"] = self.detect_style(img)
        return results

    def detect_style(self, img):
        try:
            arr = np.array(img.convert("RGBA"))
            pixels = arr.reshape(-1, 4)
            pixels = pixels[pixels[:, 3] > 10]
            if len(pixels) == 0:
                return "unknown"
            brightness = np.mean(pixels[:, :3])
            max_rgb = np.max(pixels[:, :3], axis=1)
            min_rgb = np.min(pixels[:, :3], axis=1)
            saturation = np.mean(max_rgb - min_rgb)
            unique_colors = len(np.unique(pixels[:, :3], axis=0))
            if unique_colors < 8 and saturation < 20:
                return "monochrome"
            if brightness > 150 and saturation < 60:
                return "fluent"
            return "classic"
        except Exception:
            return "unknown"

    def detect_duplicates(self, library):
        duplicates = []
        seen = {}
        for e in library.entries:
            if e.hash in seen:
                duplicates.append((seen[e.hash], e.id))
            else:
                seen[e.hash] = e.id
        return duplicates
