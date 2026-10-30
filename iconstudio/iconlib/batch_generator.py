import json
import os
import shutil
import zipfile

from iconlib.ai_generator import AIIconGenerator
from iconlib.classifier import IconClassifier
from iconlib.iconpack import IconPack
from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer
from iconlib.semantic import IconSemanticAnalyzer


class IconBatchGenerator:
    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url
        self.ai_key = ai_key

    def generate_set(self, prompt, categories, out_dir, style="fluent"):
        """
        Generate a full icon set:
            prompt: main description
            categories: list of semantic categories
            out_dir: output directory
            style: fluent/classic/monochrome
        """
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        ai = AIIconGenerator(api_url=self.ai_url, api_key=self.ai_key)
        norm = IconNormalizer()
        opt = IconOptimizer()
        clf = IconClassifier(ai_url=self.ai_url, ai_key=self.ai_key)
        sem = IconSemanticAnalyzer(ai_url=self.ai_url, ai_key=self.ai_key)

        generated = []

        for cat in categories:
            cat_clean = cat.strip()
            if not cat_clean:
                continue

            # Step 1: AI PNG & ICO
            png_path = os.path.join(out_dir, f"{cat_clean}.png")
            ico_path = os.path.join(out_dir, f"{cat_clean}.ico")

            ai.generate_png(f"{prompt}, {cat_clean}", png_path)
            ai.png_to_ico(png_path, ico_path)

            # Step 2: Normalize
            norm_path = os.path.join(out_dir, f"{cat_clean}_norm.ico")
            norm.normalize(ico_path, norm_path, style)

            # Step 3: Optimize
            opt_path = os.path.join(out_dir, f"{cat_clean}_opt.ico")
            opt.optimize_ico(norm_path, opt_path)

            # Step 4: Classify
            category = clf.classify(opt_path)

            # Step 5: Semantic
            semantic = sem.analyze(opt_path)

            generated.append({
                "category": category,
                "semantic": semantic,
                "file": opt_path,
                "name": cat_clean,
            })

        # Step 6: Pack into iconpack
        pack_path = os.path.join(out_dir, "generated.iconpack")
        self._pack(generated, pack_path)

        return generated, pack_path

    def _pack(self, generated, out_path):
        temp_dir = out_path + "_temp"
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)

        icons_dir = os.path.join(temp_dir, "icons")
        meta_dir = os.path.join(temp_dir, "metadata")

        os.makedirs(icons_dir, exist_ok=True)
        os.makedirs(meta_dir, exist_ok=True)

        import hashlib
        manifest = {
            "version": 1,
            "count": len(generated),
            "next_id": len(generated) + 1,
            "icons": [],
        }
        tags_data = {}

        for i, item in enumerate(generated):
            name = f"{i}.ico"
            dst = os.path.join(icons_dir, name)
            with open(item["file"], "rb") as f_in:
                data = f_in.read()
                with open(dst, "wb") as f_out:
                    f_out.write(data)

            file_hash = hashlib.sha256(data).hexdigest()

            item_tags = [item["category"]]
            if isinstance(item.get("semantic"), dict) and item["semantic"].get("semantic"):
                item_tags.append(item["semantic"]["semantic"])
            tags_data[str(i)] = list(set(item_tags))

            manifest["icons"].append({
                "id": i,
                "name": item.get("name", f"icon_{i}"),
                "file": name,
                "hash": file_hash,
                "category": item["category"],
                "semantic": item["semantic"],
                "tags": tags_data[str(i)],
            })

        with open(os.path.join(meta_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        with open(os.path.join(meta_dir, "tags.json"), "w", encoding="utf-8") as f:
            json.dump(tags_data, f, indent=2)

        with open(os.path.join(meta_dir, "history.json"), "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

        # pack into zip
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    full = os.path.join(root, file)
                    rel = os.path.relpath(full, temp_dir)
                    z.write(full, rel)

        shutil.rmtree(temp_dir)
