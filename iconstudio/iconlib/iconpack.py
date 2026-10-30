import os
import json
import zipfile
import shutil


class IconPack:
    def __init__(self):
        pass

    def export_pack(self, library, history, out_path):
        temp_dir = out_path + "_temp"
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        icons_dir = os.path.join(temp_dir, "icons")
        os.makedirs(icons_dir)
        for e in library.entries:
            if os.path.isfile(e.path):
                ext = os.path.splitext(e.path)[1].lower()
                out_icon = os.path.join(icons_dir, f"{e.id}{ext}")
                shutil.copyfile(e.path, out_icon)
        metadata_dir = os.path.join(temp_dir, "metadata")
        os.makedirs(metadata_dir)
        tags = {str(e.id): e.tags for e in library.entries}
        with open(os.path.join(metadata_dir, "tags.json"), "w", encoding="utf-8") as f:
            json.dump(tags, f, indent=2)
        manifest = {
            "version": 1,
            "count": len(library.entries),
            "next_id": library.next_id,
            "icons": [
                {
                    "id": e.id,
                    "name": e.name,
                    "file": f"{e.id}{os.path.splitext(e.path)[1].lower()}",
                    "hash": e.hash,
                    "tags": e.tags
                }
                for e in library.entries
            ]
        }
        with open(os.path.join(metadata_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        hist_data = history.snapshots if hasattr(history, "snapshots") else []
        with open(os.path.join(metadata_dir, "history.json"), "w", encoding="utf-8") as f:
            json.dump(hist_data, f, indent=2)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    full = os.path.join(root, file)
                    rel = os.path.relpath(full, temp_dir)
                    z.write(full, rel)
        shutil.rmtree(temp_dir)
        return out_path

    def import_pack(self, pack_path, library, history):
        temp_dir = pack_path + "_temp"
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        with zipfile.ZipFile(pack_path, "r") as z:
            z.extractall(temp_dir)
        manifest_path = os.path.join(temp_dir, "metadata", "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        tags_path = os.path.join(temp_dir, "metadata", "tags.json")
        with open(tags_path, "r", encoding="utf-8") as f:
            tags = json.load(f)
        history_path_file = os.path.join(temp_dir, "metadata", "history.json")
        if os.path.isfile(history_path_file):
            with open(history_path_file, "r", encoding="utf-8") as f:
                history.snapshots = json.load(f)
        library.entries = []
        library.next_id = manifest.get("next_id", len(manifest.get("icons", [])) + 1)
        for item in manifest["icons"]:
            icon_file = os.path.join(temp_dir, "icons", item["file"])
            from iconlib.engine import IconEntry
            entry = IconEntry(
                item["id"], item.get("name", f"icon_{item['id']}"), icon_file,
                tags.get(str(item["id"]), [])
            )
            entry.hash = item.get("hash", "")
            library.entries.append(entry)
        return True
