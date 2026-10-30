import os
import json
import wave
import colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer
from iconlib.dpi_generator import DPIGenerator


class AudioIconGenerator:
    """audio -> waveform/spectrogram -> raster -> style -> ICO."""

    STYLES = ["fluent", "monochrome", "outline", "classic"]
    MODES = ["waveform", "bars", "spectrogram", "ring"]
    SIZE_MIN = 128
    SIZE_MAX = 512
    AUDIO_EXTS = [".wav", ".mp3", ".ogg"]

    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def generate(self, source, out_dir, style="fluent", size=256, mode="waveform",
                 palette=False):
        samples, sample_rate = self._load(source)
        style = str(style).strip().lower()
        if style not in self.STYLES:
            style = "fluent"
        mode = str(mode).strip().lower()
        if mode not in self.MODES:
            mode = "waveform"
        size = int(max(self.SIZE_MIN, min(self.SIZE_MAX, int(size))))

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Step 1: audio -> waveform PNG
        waveform_path = os.path.join(out_dir, "waveform.png")
        self._render(samples, waveform_path, mode, size)

        # Step 1b: optional spectrum-derived palette -> colored glyph
        palette_data = None
        style_src = waveform_path
        if palette:
            palette_data = self._spectrum_palette(samples)
            tinted_path = os.path.join(out_dir, "tinted.png")
            self._tint(waveform_path, tinted_path, palette_data)
            style_src = tinted_path

        # Step 2: waveform -> styled PNG
        styled_path = os.path.join(out_dir, "styled.png")
        self._apply_style(style_src, styled_path, style)

        # Step 3: normalize -> multi-DPI ICO
        ico_path = os.path.join(out_dir, "audio.ico")
        IconNormalizer().normalize(styled_path, ico_path, style)

        # Step 4: optimize
        opt_path = os.path.join(out_dir, "audio_opt.ico")
        IconOptimizer().optimize_ico(ico_path, opt_path)

        # Step 5: explicit DPI set
        dpi_path = os.path.join(out_dir, "audio_dpi.ico")
        try:
            DPIGenerator().generate_dpi_set(styled_path, dpi_path)
        except Exception:
            dpi_path = None

        # Step 6: metadata
        meta_path = os.path.join(out_dir, "audio.json")
        stats = self._stats(samples, sample_rate)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "audio-icon",
                "source": str(source) if isinstance(source, str) else "samples",
                "style": style,
                "mode": mode,
                "size": size,
                "palette": palette_data,
                "audio": stats,
                "outputs": {
                    "waveform": waveform_path,
                    "png": styled_path,
                    "ico": opt_path,
                    "dpi": dpi_path,
                    "meta": meta_path,
                },
            }, f, indent=2)

        return {
            "png": styled_path,
            "waveform": waveform_path,
            "ico": opt_path,
            "dpi": dpi_path,
            "meta": meta_path,
            "mode": mode,
            "audio": stats,
            "palette": palette_data,
        }

    # --- AUDIO LOADING (path | samples | inline) ---

    def _load(self, source):
        if source is None:
            raise ValueError("Audio source is required")

        if isinstance(source, np.ndarray):
            return self._coerce_samples(source), None
        if isinstance(source, (list, tuple)):
            return self._coerce_samples(source), None

        if os.path.isfile(str(source)):
            ext = os.path.splitext(str(source))[1].lower()
            if ext in (".wav", ".wave"):
                return self._read_wav(str(source))
            return self._read_decoded(str(source))

        return self._coerce_samples(self._parse_inline(str(source))), None

    def _read_wav(self, path):
        try:
            import scipy.io.wavfile as wavfile
            rate, data = wavfile.read(path)
            arr = np.asarray(data, dtype=np.float64)
            if arr.ndim > 1:
                arr = arr.mean(axis=1)
            return arr, int(rate)
        except ImportError:
            pass

        with wave.open(path, "rb") as w:
            channels = w.getnchannels()
            width = w.getsampwidth()
            rate = w.getframerate()
            raw = w.readframes(w.getnframes())

        dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(width)
        if dtype is None:
            raise ValueError(f"Unsupported WAV sample width: {width} bytes")
        arr = np.frombuffer(raw, dtype=dtype).astype(np.float64)
        if width == 1:
            arr = arr - 128.0
        elif width == 4:
            arr = arr / 65536.0
        if channels > 1:
            arr = arr.reshape(-1, channels).mean(axis=1)
        return arr, int(rate)

    def _read_decoded(self, path):
        try:
            import soundfile as sf
            data, rate = sf.read(path, always_2d=True)
            return data.mean(axis=1), int(rate)
        except Exception:
            pass

        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(path)
            arr = np.array(seg.get_array_of_samples(), dtype=np.float64)
            if seg.channels > 1:
                arr = arr.reshape(-1, seg.channels).mean(axis=1)
            return arr, int(seg.frame_rate)
        except Exception:
            pass

        raise ValueError(
            f"Cannot decode '{os.path.basename(path)}'. "
            f"Install ffmpeg (pydub) or 'soundfile' for {', '.join(self.AUDIO_EXTS)}.")

    def _parse_inline(self, text):
        raw = [p for p in text.replace(";", " ").replace(",", " ").split() if p]
        return raw

    def _coerce_samples(self, data):
        try:
            arr = np.asarray([float(v) for v in data], dtype=np.float64)
        except (TypeError, ValueError):
            raise ValueError("Samples must be a sequence of numbers")
        if arr.size == 0:
            raise ValueError("Samples must contain at least one value")
        return arr.ravel()

    # --- AUDIO -> RASTER PNG ---

    def _render(self, samples, out_path, mode, size):
        arr = np.asarray(samples, dtype=np.float64).ravel()
        peak = float(np.max(np.abs(arr))) if arr.size else 0.0
        amp = arr / peak if peak > 1e-12 else np.zeros_like(arr)

        if mode == "spectrogram":
            img = self._spectrogram(amp, size)
        elif mode == "ring":
            img = self._ring(amp, size)
        elif mode == "bars":
            img = self._bars(amp, size)
        else:
            img = self._waveform(amp, size)

        img.save(out_path, optimize=True)
        return out_path

    def _waveform(self, amp, size):
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        mid = size // 2
        margin = max(6, size // 16)
        half = (size - margin * 2) // 2
        width = max(1, size // 256)
        n = amp.size

        for x in range(size):
            i0 = int(x * n / size)
            i1 = max(i0 + 1, int((x + 1) * n / size))
            seg = amp[i0:min(i1, n)]
            if seg.size == 0:
                continue
            lo = float(seg.min())
            hi = float(seg.max())
            y_hi = mid - int(hi * half)
            y_lo = mid - int(lo * half)
            if y_lo <= y_hi:
                y_lo = y_hi + 1
            draw.line((x, y_hi, x, y_lo), fill=(0, 0, 0, 255), width=width)
        return img

    def _bars(self, amp, size):
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        mid = size // 2
        margin = max(6, size // 16)
        half = (size - margin * 2) // 2
        n = amp.size

        for x in range(size):
            i0 = int(x * n / size)
            i1 = max(i0 + 1, int((x + 1) * n / size))
            seg = amp[i0:min(i1, n)]
            if seg.size == 0:
                continue
            energy = float(np.sqrt(np.mean(seg ** 2)))
            h = max(1, int(energy * half))
            draw.line((x, mid - h, x, mid + h), fill=(0, 0, 0, 255), width=1)
        return img

    def _ring(self, amp, size):
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        cx = cy = size / 2.0
        r = size * 0.34
        reach = size * 0.14
        n = amp.size
        width = max(1, size // 192)

        for x in range(size):
            i0 = int(x * n / size)
            i1 = max(i0 + 1, int((x + 1) * n / size))
            seg = amp[i0:min(i1, n)]
            if seg.size == 0:
                continue
            level = float(np.max(np.abs(seg)))
            ang = 2.0 * np.pi * x / size - np.pi / 2.0
            ca, sa = np.cos(ang), np.sin(ang)
            x0, y0 = cx + ca * r, cy + sa * r
            x1, y1 = cx + ca * (r + level * reach), cy + sa * (r + level * reach)
            draw.line((x0, y0, x1, y1), fill=(0, 0, 0, 255), width=width)
        return img

    def _spectrogram(self, amp, size):
        win = max(64, size // 2)
        hop = max(1, win // 4)
        if amp.size < win:
            amp = np.pad(amp, (0, win - amp.size))
        window = np.hanning(win)

        frames = []
        for start in range(0, amp.size - win + 1, hop):
            seg = amp[start:start + win] * window
            frames.append(np.abs(np.fft.rfft(seg)))
        if not frames:
            frames = [np.zeros(win // 2 + 1)]

        spec = np.array(frames).T
        spec = np.log1p(spec)
        hi = float(spec.max())
        if hi > 1e-12:
            spec = spec / hi

        gray = Image.fromarray((spec * 255.0).astype("uint8"), "L")
        gray = gray.resize((size, size), Image.LANCZOS).transpose(Image.FLIP_TOP_BOTTOM)

        arr = np.array(gray)
        rgba = np.zeros((size, size, 4), dtype="uint8")
        rgba[:, :, 3] = arr
        return Image.fromarray(rgba, "RGBA")

    # --- STYLE APPLICATION ---

    def _apply_style(self, src, dst, style):
        img = Image.open(src).convert("RGBA")

        if style == "fluent":
            img = ImageEnhance.Color(img).enhance(0.75)
            img = ImageEnhance.Brightness(img).enhance(1.1)
            img = ImageEnhance.Contrast(img).enhance(0.9)
            bloom = img.filter(ImageFilter.GaussianBlur(6))
            arr = np.array(img).copy()
            bl = np.array(bloom)
            arr[:, :, :3] = (arr[:, :, :3] * 0.85 + bl[:, :, :3] * 0.15).astype("uint8")
            Image.fromarray(arr, "RGBA").save(dst, optimize=True)
            return dst

        if style == "monochrome":
            arr = np.array(img)
            gray = np.array(img.convert("L"))
            rgba = np.zeros((gray.shape[0], gray.shape[1], 4), dtype="uint8")
            rgba[:, :, 0] = gray
            rgba[:, :, 1] = gray
            rgba[:, :, 2] = gray
            rgba[:, :, 3] = arr[:, :, 3]
            Image.fromarray(rgba, "RGBA").save(dst, optimize=True)
            return dst

        if style == "outline":
            outline = img.filter(ImageFilter.FIND_EDGES)
            arr = np.array(outline).copy()
            arr[:, :, 3] = np.array(img)[:, :, 3]
            Image.fromarray(arr, "RGBA").save(dst, optimize=True)
            return dst

        # classic
        img = ImageEnhance.Color(img).enhance(1.4)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img.save(dst, optimize=True)
        return dst

    # --- SPECTRUM PALETTE (audio -> colors) ---

    @staticmethod
    def _hsv(h, s, v, a=255):
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)),
                                      max(0.0, min(1.0, v)))
        return (int(r * 255), int(g * 255), int(b * 255), a)

    @staticmethod
    def _hex(rgb):
        return "#%02x%02x%02x" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    def _spectrum_palette(self, samples):
        arr = np.asarray(samples, dtype=np.float64).ravel()
        if arr.size < 8:
            arr = np.pad(arr, (0, 8 - arr.size))
        window = np.hanning(arr.size)
        spec = np.abs(np.fft.rfft(arr * window))
        spec[0] = 0.0
        total = float(spec.sum())
        n = spec.size

        if total <= 1e-12:
            centroid = 0.0
            bass = mid = treble = 0.0
        else:
            idx = np.arange(n, dtype=np.float64)
            centroid = float((idx * spec).sum() / total) / max(1, n - 1)
            f = idx / max(1, n - 1)
            bass = float(spec[f < 0.15].sum() / total)
            mid = float(spec[(f >= 0.15) & (f < 0.5)].sum() / total)
            treble = float(spec[f >= 0.5].sum() / total)

        energy = float(np.sqrt(np.mean(arr ** 2)))
        base_hue = (0.55 + centroid * 0.35) % 1.0
        sat = 0.45 + min(0.5, treble) * 0.5
        val = 0.55 + min(0.4, energy * 1.2)

        primary = self._hsv(base_hue, sat, val)
        accent = self._hsv(base_hue + 0.10 + bass * 0.10,
                           min(1.0, sat + 0.15), min(1.0, val + 0.10))
        surface = self._hsv(base_hue, 0.25, 0.16)
        text = self._hsv(base_hue, 0.15, 0.92)

        return {
            "primary": self._hex(primary),
            "accent": self._hex(accent),
            "surface": self._hex(surface),
            "text": self._hex(text),
            "centroid": round(centroid, 4),
            "bands": {
                "bass": round(bass, 4),
                "mid": round(mid, 4),
                "treble": round(treble, 4),
            },
            "rgb": {"primary": primary[:3], "accent": accent[:3]},
        }

    def _tint(self, src, dst, palette):
        img = Image.open(src).convert("RGBA")
        w, h = img.size
        arr = np.array(img)
        alpha = arr[:, :, 3].astype(np.float64) / 255.0
        ys = np.linspace(0.0, 1.0, h).reshape(-1, 1)
        t = np.clip(0.55 * alpha + 0.45 * ys, 0.0, 1.0)

        p = np.array(palette["rgb"]["primary"], dtype=np.float64).reshape(1, 1, 3)
        a = np.array(palette["rgb"]["accent"], dtype=np.float64).reshape(1, 1, 3)
        rgb = p * (1.0 - t[:, :, None]) + a * t[:, :, None]

        out = np.zeros((h, w, 4), dtype="uint8")
        out[:, :, :3] = rgb.astype("uint8")
        out[:, :, 3] = arr[:, :, 3]
        Image.fromarray(out, "RGBA").save(dst, optimize=True)
        return dst

    # --- STATS ---

    def _stats(self, samples, sample_rate):
        arr = np.asarray(samples, dtype=np.float64).ravel()
        peak = float(np.max(np.abs(arr))) if arr.size else 0.0
        rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
        stats = {
            "samples": int(arr.size),
            "peak": round(peak, 6),
            "rms": round(rms, 6),
        }
        if sample_rate:
            stats["sample_rate"] = int(sample_rate)
            stats["duration"] = round(arr.size / float(sample_rate), 4)
        return stats
