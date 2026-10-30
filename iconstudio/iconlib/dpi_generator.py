from PIL import Image
import os

DPI_SIZES = [16, 24, 32, 48, 64, 128, 256]


class DPIGenerator:
    def __init__(self):
        pass

    def generate_dpi_set(self, src_path, out_path):
        if not os.path.isfile(src_path):
            raise Exception("Source file not found")
        img = Image.open(src_path).convert("RGBA")
        icons = []
        for size in DPI_SIZES:
            resized = img.resize((size, size), Image.LANCZOS)
            icons.append(resized)
        icons[0].save(
            out_path,
            format="ICO",
            sizes=[(s, s) for s in DPI_SIZES]
        )
        return out_path

    def generate_temp_layers(self, src_path, out_dir):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        img = Image.open(src_path).convert("RGBA")
        paths = []
        for size in DPI_SIZES:
            resized = img.resize((size, size), Image.LANCZOS)
            p = os.path.join(out_dir, f"{size}.png")
            resized.save(p)
            paths.append(p)
        return paths
