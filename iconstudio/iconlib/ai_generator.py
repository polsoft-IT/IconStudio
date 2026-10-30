import base64
import json
import os
import requests
from PIL import Image, ImageDraw

DPI_SIZES = [16, 24, 32, 48, 64, 128, 256]


class AIIconGenerator:
    def __init__(self, api_url=None, api_key=None):
        self.api_url = api_url or os.environ.get("ICONSTUDIO_AI_URL")
        self.api_key = api_key or os.environ.get("ICONSTUDIO_AI_KEY")

    def generate_png(self, prompt, out_path):
        """Generate PNG from text prompt using external AI backend, or fallback if offline."""
        if self.api_url:
            payload = {"prompt": prompt, "size": 512}
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            try:
                r = requests.post(self.api_url, headers=headers, data=json.dumps(payload), timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    img_bytes = base64.b64decode(data["image"])
                    with open(out_path, "wb") as f:
                        f.write(img_bytes)
                    return out_path
            except Exception:
                pass

        # Fallback procedural generator (offline / no API configured)
        self._generate_procedural_png(prompt, out_path)
        return out_path

    def _generate_procedural_png(self, prompt, out_path):
        p = prompt.lower()
        size = 512
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Determine theme color based on prompt
        if "folder" in p:
            fill_color = (245, 176, 65, 255)
            accent = (220, 150, 40, 255)
            shape = "folder"
        elif "cloud" in p:
            fill_color = (93, 173, 226, 255)
            accent = (52, 152, 219, 255)
            shape = "cloud"
        elif "sync" in p:
            fill_color = (82, 190, 128, 255)
            accent = (46, 170, 100, 255)
            shape = "sync"
        elif "settings" in p or "gear" in p:
            fill_color = (127, 140, 141, 255)
            accent = (100, 110, 115, 255)
            shape = "settings"
        elif "user" in p or "person" in p:
            fill_color = (175, 122, 197, 255)
            accent = (150, 100, 180, 255)
            shape = "user"
        elif "error" in p or "alert" in p:
            fill_color = (231, 76, 60, 255)
            accent = (192, 57, 43, 255)
            shape = "error"
        else:
            fill_color = (52, 152, 219, 255)
            accent = (41, 128, 185, 255)
            shape = "box"

        pad = 64
        # Draw background base
        draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=80, fill=fill_color, outline=accent, width=8)

        # Draw inner glyph
        mid_x, mid_y = size // 2, size // 2
        if shape == "folder":
            draw.rectangle([mid_x - 120, mid_y - 60, mid_x + 120, mid_y + 80], fill=(255, 255, 255, 220))
            draw.polygon([(mid_x - 120, mid_y - 60), (mid_x - 40, mid_y - 60), (mid_x - 10, mid_y - 30), (mid_x - 120, mid_y - 30)], fill=(255, 255, 255, 240))
        elif shape == "cloud":
            draw.ellipse([mid_x - 100, mid_y - 40, mid_x + 40, mid_y + 80], fill=(255, 255, 255, 220))
            draw.ellipse([mid_x - 40, mid_y - 90, mid_x + 100, mid_y + 60], fill=(255, 255, 255, 220))
            draw.rectangle([mid_x - 80, mid_y, mid_x + 80, mid_y + 80], fill=(255, 255, 255, 220))
        elif shape == "user":
            draw.ellipse([mid_x - 50, mid_y - 100, mid_x + 50, mid_y], fill=(255, 255, 255, 230))
            draw.chord([mid_x - 100, mid_y + 20, mid_x + 100, mid_y + 140], start=180, end=0, fill=(255, 255, 255, 230))
        else:
            draw.ellipse([mid_x - 60, mid_y - 60, mid_x + 60, mid_y + 60], fill=(255, 255, 255, 220))

        img.save(out_path, format="PNG")
        return out_path

    def png_to_ico(self, png_path, ico_path):
        img = Image.open(png_path).convert("RGBA")
        icons = []
        for size in DPI_SIZES:
            resized = img.resize((size, size), Image.LANCZOS)
            icons.append(resized)

        icons[0].save(
            ico_path,
            format="ICO",
            sizes=[(s, s) for s in DPI_SIZES],
        )
        return ico_path

    def generate_icon(self, prompt, out_dir):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        png_path = os.path.join(out_dir, "ai_icon.png")
        ico_path = os.path.join(out_dir, "ai_icon.ico")

        self.generate_png(prompt, png_path)
        self.png_to_ico(png_path, ico_path)

        return png_path, ico_path
