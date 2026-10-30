import hashlib
import os

from iconlib.dll_export import DLLBuilder
from iconlib.dll_import import DLLIconImporter
from iconlib.validator import IconValidator


class IconMigrator:
    def __init__(self):
        pass

    def load_dll(self, path):
        importer = DLLIconImporter(path)
        icons = importer.import_icons()
        return icons

    def compare(self, dll_a_icons, dll_b_icons):
        """
        Compare two DLL icon sets.
        Returns dict with:
            - missing_in_b
            - missing_in_a
            - changed
            - duplicates
        """
        map_a = {i["id"]: i for i in dll_a_icons}
        map_b = {i["id"]: i for i in dll_b_icons}

        missing_in_b = [map_a[i] for i in map_a if i not in map_b]
        missing_in_a = [map_b[i] for i in map_b if i not in map_a]

        changed = []
        for i in map_a:
            if i in map_b:
                if map_a[i]["ico"] != map_b[i]["ico"]:
                    changed.append((map_a[i], map_b[i]))

        # detect duplicates by hash
        val = IconValidator()
        dup = []
        seen = {}
        for i in dll_a_icons + dll_b_icons:
            h = self._hash(i["ico"])
            if h in seen:
                dup.append((seen[h], i["id"]))
            else:
                seen[h] = i["id"]

        return {
            "missing_in_b": missing_in_b,
            "missing_in_a": missing_in_a,
            "changed": changed,
            "duplicates": dup,
        }

    def migrate(self, dll_src_icons, dll_dst_path, out_path, ids_to_copy):
        """
        Copy selected icons from src DLL into new DLL.
        """
        builder = DLLBuilder()
        base_icon_id = 200
        group_id = 100

        # Add existing icons from destination DLL
        dst_importer = DLLIconImporter(dll_dst_path)
        dst_icons = dst_importer.import_icons()

        temp_files = []
        try:
            for item in dst_icons:
                temp_path = f"dst_temp_{item['id']}.ico"
                with open(temp_path, "wb") as f:
                    f.write(item["ico"])
                temp_files.append(temp_path)
                builder.add_icon(temp_path, group_id, base_icon_id)
                group_id += 1
                base_icon_id += 20

            # Add selected icons from source DLL
            for item in dll_src_icons:
                if item["id"] in ids_to_copy:
                    temp_path = f"migrate_{item['id']}.ico"
                    with open(temp_path, "wb") as f:
                        f.write(item["ico"])
                    temp_files.append(temp_path)
                    builder.add_icon(temp_path, group_id, base_icon_id)
                    group_id += 1
                    base_icon_id += 20

            builder.build(out_path)
            return out_path
        finally:
            for tf in temp_files:
                if os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except Exception:
                        pass

    def _hash(self, data):
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()
