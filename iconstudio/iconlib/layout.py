import json
import os
from PIL import Image


class IconLayoutEngine:
    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def layout(self, icons, layout_type, cache, out_dir, spacing=16, padding=24):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        if layout_type == "grid":
            return self._layout_grid(icons, cache, out_dir, spacing, padding)

        if layout_type == "toolbar":
            return self._layout_toolbar(icons, cache, out_dir, spacing, padding)

        if layout_type == "ribbon":
            return self._layout_ribbon(icons, cache, out_dir, spacing, padding)

        if layout_type == "sidebar":
            return self._layout_sidebar(icons, cache, out_dir, spacing, padding)

        if layout_type == "menu":
            return self._layout_menu(icons, cache, out_dir, spacing, padding)

        raise ValueError(f"Unknown layout type: '{layout_type}'. Supported: grid, toolbar, ribbon, sidebar, menu")

    # --- GRID LAYOUT ---

    def _layout_grid(self, icons, cache, out_dir, spacing, padding):
        cols = 6
        rows = (len(icons) + cols - 1) // cols if icons else 1

        cell = 128
        w = cols * cell + (cols + 1) * spacing + padding * 2
        h = rows * cell + (rows + 1) * spacing + padding * 2

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        layout = []

        x = padding + spacing
        y = padding + spacing

        for i, id_ in enumerate(icons):
            thumb = cache.thumb128.get(id_) if cache and hasattr(cache, "thumb128") else None
            if thumb:
                img.paste(thumb, (x, y), thumb)

            layout.append({
                "id": id_,
                "x": x,
                "y": y,
                "w": 128,
                "h": 128,
            })

            x += cell + spacing
            if (i + 1) % cols == 0:
                x = padding + spacing
                y += cell + spacing

        preview = os.path.join(out_dir, "grid.png")
        img.save(preview, optimize=True)

        meta = os.path.join(out_dir, "grid.json")
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)

        return {"preview": preview, "meta": meta}

    # --- TOOLBAR LAYOUT ---

    def _layout_toolbar(self, icons, cache, out_dir, spacing, padding):
        cell = 64
        count = max(len(icons), 1)
        w = count * cell + (count + 1) * spacing + padding * 2
        h = cell + spacing * 2 + padding * 2

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        layout = []

        x = padding + spacing
        y = padding + spacing

        for id_ in icons:
            thumb = cache.thumb64.get(id_) if cache and hasattr(cache, "thumb64") else None
            if thumb:
                img.paste(thumb, (x, y), thumb)

            layout.append({
                "id": id_,
                "x": x,
                "y": y,
                "w": 64,
                "h": 64,
            })

            x += cell + spacing

        preview = os.path.join(out_dir, "toolbar.png")
        img.save(preview, optimize=True)

        meta = os.path.join(out_dir, "toolbar.json")
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)

        return {"preview": preview, "meta": meta}

    # --- RIBBON LAYOUT ---

    def _layout_ribbon(self, icons, cache, out_dir, spacing, padding):
        cell = 96
        cols = 3
        rows = (len(icons) + cols - 1) // cols if icons else 1

        w = cols * cell + (cols + 1) * spacing + padding * 2
        h = rows * cell + (rows + 1) * spacing + padding * 2

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        layout = []

        x = padding + spacing
        y = padding + spacing

        for i, id_ in enumerate(icons):
            thumb_orig = None
            if cache:
                thumb_orig = cache.thumb128.get(id_) or cache.thumb64.get(id_)
            if thumb_orig:
                thumb = thumb_orig.resize((96, 96), Image.LANCZOS)
                img.paste(thumb, (x, y), thumb)

            layout.append({
                "id": id_,
                "x": x,
                "y": y,
                "w": 96,
                "h": 96,
            })

            x += cell + spacing
            if (i + 1) % cols == 0:
                x = padding + spacing
                y += cell + spacing

        preview = os.path.join(out_dir, "ribbon.png")
        img.save(preview, optimize=True)

        meta = os.path.join(out_dir, "ribbon.json")
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)

        return {"preview": preview, "meta": meta}

    # --- SIDEBAR LAYOUT ---

    def _layout_sidebar(self, icons, cache, out_dir, spacing, padding):
        cell = 64
        count = max(len(icons), 1)
        w = cell + spacing * 2 + padding * 2
        h = count * cell + (count + 1) * spacing + padding * 2

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        layout = []

        x = padding + spacing
        y = padding + spacing

        for id_ in icons:
            thumb = cache.thumb64.get(id_) if cache and hasattr(cache, "thumb64") else None
            if thumb:
                img.paste(thumb, (x, y), thumb)

            layout.append({
                "id": id_,
                "x": x,
                "y": y,
                "w": 64,
                "h": 64,
            })

            y += cell + spacing

        preview = os.path.join(out_dir, "sidebar.png")
        img.save(preview, optimize=True)

        meta = os.path.join(out_dir, "sidebar.json")
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)

        return {"preview": preview, "meta": meta}

    # --- MENU LAYOUT ---

    def _layout_menu(self, icons, cache, out_dir, spacing, padding):
        cell = 48
        count = max(len(icons), 1)
        w = cell + spacing * 2 + padding * 2
        h = count * cell + (count + 1) * spacing + padding * 2

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        layout = []

        x = padding + spacing
        y = padding + spacing

        for id_ in icons:
            thumb_orig = cache.thumb64.get(id_) if cache and hasattr(cache, "thumb64") else None
            if thumb_orig:
                thumb = thumb_orig.resize((48, 48), Image.LANCZOS)
                img.paste(thumb, (x, y), thumb)

            layout.append({
                "id": id_,
                "x": x,
                "y": y,
                "w": 48,
                "h": 48,
            })

            y += cell + spacing

        preview = os.path.join(out_dir, "menu.png")
        img.save(preview, optimize=True)

        meta = os.path.join(out_dir, "menu.json")
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)

        return {"preview": preview, "meta": meta}
