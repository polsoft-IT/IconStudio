import os
import json
import numpy as np
from PIL import Image

from iconlib.ai_generator import AIIconGenerator
from iconlib.fluent3d import Fluent3DGenerator

try:
    import imageio
except Exception:
    imageio = None


class Fluent3DAnimation:
    MOTIONS = ["rotate", "tilt", "bounce", "pulse", "glow", "morph"]

    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url
        self.ai_key = ai_key

    # --- MAIN PIPELINE ---

    def animate(self, prompt, out_dir, frames=12, motion="rotate"):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        frames = max(int(frames), 1)

        ai = AIIconGenerator(api_url=self.ai_url, api_key=self.ai_key)
        f3d = Fluent3DGenerator(ai_url=self.ai_url, ai_key=self.ai_key)

        frame_paths = []

        # Step 1: generate frames
        for i in range(frames):
            angle = int((i / frames) * 360)

            motion_prompt = (
                f"{prompt}, fluent 3d icon, {motion} {angle} degrees, "
                f"soft shadows, glossy highlights"
            )
            png_path = os.path.join(out_dir, f"frame_{i}.png")

            ai.generate_png(motion_prompt, png_path)

            # Step 2: apply Fluent 3D shading
            shaded_path = os.path.join(out_dir, f"frame_{i}_shaded.png")
            f3d._apply_3d_shading(png_path, shaded_path)

            # Step 3: normalize Fluent 3D style
            norm_path = os.path.join(out_dir, f"frame_{i}_norm.png")
            f3d._normalize_fluent3d(shaded_path, norm_path)

            frame_paths.append(norm_path)

        # Step 4: build GIF
        gif_path = os.path.join(out_dir, "animation.gif")
        frames_img = [Image.open(p).convert("RGBA") for p in frame_paths]
        frames_img[0].save(
            gif_path,
            save_all=True,
            append_images=frames_img[1:],
            duration=80,
            loop=0,
            optimize=True,
        )

        # Step 5: build WebP
        webp_path = os.path.join(out_dir, "animation.webp")
        self._write_webp(frame_paths, webp_path)

        # Step 6: sprite sheet
        sprite_path = os.path.join(out_dir, "sprite.png")
        self._sprite_sheet(frame_paths, sprite_path)

        # Step 7: timeline metadata
        meta_path = os.path.join(out_dir, "timeline.json")
        self._timeline(meta_path, frames, motion)

        return {
            "gif": gif_path,
            "webp": webp_path,
            "sprite": sprite_path,
            "timeline": meta_path,
        }

    # --- WEBP ---

    def _write_webp(self, frame_paths, out_path):
        if imageio is not None:
            try:
                imageio.mimsave(
                    out_path,
                    [np.array(Image.open(p).convert("RGBA")) for p in frame_paths],
                    format="WEBP",
                    fps=12,
                )
                return out_path
            except Exception:
                pass

        # Fallback: Pillow animated WebP
        frames_img = [Image.open(p).convert("RGBA") for p in frame_paths]
        frames_img[0].save(
            out_path,
            format="WEBP",
            save_all=True,
            append_images=frames_img[1:],
            duration=80,
            loop=0,
        )
        return out_path

    # --- SPRITE SHEET ---

    def _sprite_sheet(self, frame_paths, out_path):
        frames = [Image.open(p).convert("RGBA") for p in frame_paths]
        w, h = frames[0].size
        sheet = Image.new("RGBA", (w * len(frames), h))

        x = 0
        for f in frames:
            sheet.paste(f, (x, 0), f)
            x += w

        sheet.save(out_path, optimize=True)
        return out_path

    # --- TIMELINE METADATA ---

    def _timeline(self, out_path, frames, motion):
        data = {
            "frames": frames,
            "fps": 12,
            "loop": True,
            "motion": motion,
        }
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        return out_path
