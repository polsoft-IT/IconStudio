import base64
import json
import numpy as np
from PIL import Image
import requests


class IconRecommender:
    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url
        self.ai_key = ai_key

    # --- MAIN ENTRY POINT ---

    def recommend(self, query, library, cache):
        """
        query: text describing desired icon
        library: IconLibrary
        cache: IconCache
        """
        if cache is None or not getattr(cache, "meta", None):
            from iconlib.cache import IconCache
            cache = IconCache()
            cache.build(library)

        # Step 1: semantic match
        sem_ids = self._semantic_match(query, cache)

        # Step 2: visual similarity
        vis_ids = self._visual_similarity(query, cache)

        # Step 3: AI recommendation (optional)
        ai_ids = []
        if self.ai_url:
            ai_ids = self._ai_recommend(query, library)

        # Step 4: merge + rank
        ranked = self._rank(sem_ids, vis_ids, ai_ids)

        return ranked

    # --- SEMANTIC MATCH ---

    def _semantic_match(self, query, cache):
        q = query.lower().strip()
        words = [w for w in q.split() if len(w) > 1]
        results = set()

        # match tags
        for tag, ids in cache.index_tag.items():
            if q in tag or any(w in tag for w in words):
                results.update(ids)

        # match names
        for name, ids in cache.index_name.items():
            if q in name or any(w in name for w in words):
                results.update(ids)

        # match styles
        for style, ids in cache.index_style.items():
            if style in q or any(w in style for w in words):
                results.update(ids)

        return list(results)

    # --- VISUAL SIMILARITY ---

    def _visual_similarity(self, query, cache):
        q = query.lower()

        # heuristic: color keywords
        color_map = {
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
            "white": (255, 255, 255),
            "black": (0, 0, 0),
        }

        target_color = None
        for word, col in color_map.items():
            if word in q:
                target_color = np.array(col)
                break

        if target_color is None:
            return []

        scores = []
        for id_, meta in cache.meta.items():
            thumb = cache.thumb64.get(id_)
            if thumb is None:
                continue

            arr = np.array(thumb)
            pixels = arr[:, :, :3]
            if arr.shape[2] == 4:
                alpha = arr[:, :, 3]
                mask = alpha > 10
                if np.any(mask):
                    pixels = pixels[mask]
                else:
                    pixels = pixels.reshape(-1, 3)
            else:
                pixels = pixels.reshape(-1, 3)

            avg = np.mean(pixels, axis=0)
            dist = np.linalg.norm(avg - target_color)
            scores.append((id_, dist))

        scores.sort(key=lambda x: x[1])
        return [id_ for id_, _ in scores[:10]]

    # --- AI RECOMMENDATION ---

    def _ai_recommend(self, query, library):
        payload = {"query": query}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.ai_key}",
        }

        try:
            r = requests.post(self.ai_url, headers=headers, data=json.dumps(payload), timeout=10)
            if r.status_code != 200:
                return []

            data = r.json()
            return data.get("ids", [])
        except Exception:
            return []

    # --- RANKING ---

    def _rank(self, sem_ids, vis_ids, ai_ids):
        score = {}

        for id_ in sem_ids:
            score[id_] = score.get(id_, 0) + 3

        for id_ in vis_ids:
            score[id_] = score.get(id_, 0) + 2

        for id_ in ai_ids:
            score[id_] = score.get(id_, 0) + 5

        ranked = sorted(score.items(), key=lambda x: -x[1])
        return [id_ for id_, _ in ranked]
