import json
import time
import os


class IconLibraryHistory:
    def __init__(self, history_path="history.json"):
        self.history_path = history_path
        self.snapshots = []
        self.load()

    def load(self):
        if os.path.isfile(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    self.snapshots = json.load(f)
            except Exception:
                self.snapshots = []
        else:
            self.snapshots = []

    def save(self):
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.snapshots, f, indent=2)

    def add_snapshot(self, library, message="update"):
        snap = {
            "timestamp": time.time(),
            "message": message,
            "next_id": library.next_id,
            "entries": [
                {
                    "id": e.id,
                    "name": e.name,
                    "path": e.path,
                    "tags": e.tags,
                    "hash": e.hash,
                }
                for e in library.entries
            ],
        }
        self.snapshots.append(snap)
        try:
            self.save()
        except Exception:
            pass

    def list_snapshots(self):
        return self.snapshots

    def restore_snapshot(self, index, library):
        if index < 0 or index >= len(self.snapshots):
            raise Exception("Invalid snapshot index")
        snap = self.snapshots[index]
        library.entries = []
        library.next_id = snap["next_id"]
        for item in snap["entries"]:
            from iconlib.engine import IconEntry
            entry = IconEntry(
                item["id"], item["name"], item["path"],
                item.get("tags", [])
            )
            entry.hash = item.get("hash", "")
            library.entries.append(entry)

    def diff(self, index_a, index_b):
        if index_a < 0 or index_a >= len(self.snapshots):
            raise Exception("Invalid snapshot A")
        if index_b < 0 or index_b >= len(self.snapshots):
            raise Exception("Invalid snapshot B")
        a = self.snapshots[index_a]
        b = self.snapshots[index_b]
        map_a = {e["id"]: e for e in a["entries"]}
        map_b = {e["id"]: e for e in b["entries"]}
        added = [map_b[i] for i in map_b if i not in map_a]
        removed = [map_a[i] for i in map_a if i not in map_b]
        changed = []
        for i in map_a:
            if i in map_b:
                if map_a[i]["hash"] != map_b[i]["hash"]:
                    changed.append((map_a[i], map_b[i]))
        return {"added": added, "removed": removed, "changed": changed}
