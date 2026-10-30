import argparse
import json
import os
import sys
import time

from iconlib.engine import IconLibrary
from iconlib.semantic import IconSemanticAnalyzer
from iconlib.classifier import IconClassifier
from iconlib.optimizer import IconOptimizer
from iconlib.validator import IconValidator
from iconlib.ui_mapper import IconUIMapper


DEFAULT_LIB_PATH = "library.json"


def get_library():
    lib = IconLibrary()
    if os.path.exists(DEFAULT_LIB_PATH):
        try:
            lib.load(DEFAULT_LIB_PATH)
        except Exception:
            pass
    return lib


def resolve_icon_target(lib, target):
    """Resolve target to (entry, path). Target can be an integer ID or a filepath."""
    if str(target).isdigit():
        id_ = int(target)
        entry = lib.get_entry(id_)
        if entry:
            return entry, entry.path
        raise ValueError(f"Icon with ID {id_} not found in library ({DEFAULT_LIB_PATH}).")
    if os.path.exists(target):
        return None, target
    raise ValueError(f"Target '{target}' is neither a known icon ID nor an existing file path.")


def cmd_semantic(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    analyzer = IconSemanticAnalyzer(ai_url=lib.ai_url, ai_key=lib.ai_key)
    result = analyzer.analyze(path)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=== Semantic Analysis ===")
        print(f"Target: {path}\n")
        print("Visual:")
        print(json.dumps(result["visual"], indent=2))
        print(f"\nSemantic Guess: {result['semantic']}")
        print(f"UX Context:     {result['ux']}")
        if result.get("ai"):
            print(f"AI Description: {result['ai']}")


def cmd_classify(args, lib):
    entry, path = resolve_icon_target(lib, args.target)
    clf = IconClassifier(ai_url=lib.ai_url, ai_key=lib.ai_key)
    category = clf.classify(path)
    if entry:
        lib.add_tag(entry.id, category)
        try:
            lib.save(DEFAULT_LIB_PATH)
        except Exception:
            pass
    print(f"Detected category: {category}")


def cmd_mapaction(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    mapper = IconUIMapper(ai_url=lib.ai_url, ai_key=lib.ai_key)
    result = mapper.map_action(path)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=== UI/UX Action Mapping ===")
        print(f"Target: {path}\n")
        print(f"Semantic:      {result['semantic']}")
        print(f"Mapped Action: {result['action']}")
        print("Visual Features:")
        print(json.dumps(result["visual"], indent=2))
        if result.get("ai_action"):
            print(f"AI Action:     {result['ai_action']}")


def cmd_optimize(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    out_path = args.out or path
    opt = IconOptimizer()
    if path.lower().endswith(".ico"):
        opt.optimize_ico(path, out_path)
    else:
        opt.optimize(path, out_path)
    print(f"Icon optimized -> {out_path}")


def cmd_duplicates(args, lib):
    val = IconValidator()
    dups = val.detect_duplicates(lib)
    if not dups:
        print("No duplicates detected.")
    else:
        print("Duplicates detected:")
        for group in dups:
            ids = [str(e.id) for e in group]
            print(f" - Icons ID: {', '.join(ids)} ({group[0].name})")


def cmd_list(args, lib):
    if not lib.entries:
        print("Library is empty.")
        return
    print(f"Library ({len(lib.entries)} icons):")
    for e in lib.entries:
        tags = f" [{', '.join(e.tags)}]" if e.tags else ""
        print(f"  {e.id:4d} | {e.name}{tags} -> {e.path}")


def cmd_recommend(args, lib):
    from iconlib.cache import IconCache
    cache = IconCache()
    cache.build(lib)
    ranked_ids = lib.recommend_icons(args.query, cache)

    if args.json:
        results = []
        for id_ in ranked_ids:
            e = lib.get_entry(id_)
            if e:
                results.append({"id": e.id, "name": e.name, "tags": e.tags, "path": e.path})
        print(json.dumps(results, indent=2))
    else:
        print(f"=== Recommendations for '{args.query}' ===")
        if not ranked_ids:
            print("No matching icons found.")
            return
        for rank, id_ in enumerate(ranked_ids, 1):
            e = lib.get_entry(id_)
            if e:
                tags = f" [{', '.join(e.tags)}]" if e.tags else ""
                print(f" {rank:2d}. ID {e.id:4d} | {e.name}{tags} -> {e.path}")


def cmd_genset(args, lib):
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    if not categories:
        raise ValueError("At least one category must be provided.")

    print(f"Generating icon set for prompt: '{args.prompt}'")
    print(f"Categories ({len(categories)}): {', '.join(categories)}")
    print(f"Style: {args.style} | Output: {args.out_dir}")

    generated, pack_path = lib.generate_icon_set(args.prompt, categories, args.out_dir, style=args.style)

    if args.json:
        result = {
            "prompt": args.prompt,
            "style": args.style,
            "pack": pack_path,
            "icons": [
                {
                    "name": item.get("name"),
                    "category": item.get("category"),
                    "file": item.get("file"),
                }
                for item in generated
            ],
        }
        print(json.dumps(result, indent=2))
    else:
        print("\n=== Generation Finished ===")
        print(f"Generated {len(generated)} icons:")
        for item in generated:
            print(f" - {item.get('name')}: {item.get('file')} [Category: {item.get('category')}]")
        print(f"\nIconPack created: {pack_path}")


def cmd_add(args, lib):
    if not os.path.exists(args.path):
        raise FileNotFoundError(f"File '{args.path}' not found.")
    lib.add_icon(args.path, args.name)
    lib.snapshot(f"Added icon {args.name or os.path.basename(args.path)}")
    lib.save(DEFAULT_LIB_PATH)
    new_entry = lib.entries[-1]
    print(f"Added icon ID {new_entry.id}: {new_entry.name} ({new_entry.path})")


def cmd_remove(args, lib):
    id_ = int(args.id)
    entry = lib.get_entry(id_)
    if not entry:
        raise ValueError(f"Icon with ID {id_} not found.")
    lib.remove_icon(id_)
    lib.snapshot(f"Removed icon {id_}")
    lib.save(DEFAULT_LIB_PATH)
    print(f"Removed icon ID {id_}")


def cmd_style(args, lib):
    entry, path = resolve_icon_target(lib, args.target)
    from iconlib.style_detector import IconStyleDetector
    style = IconStyleDetector().detect_style(path)
    if entry:
        lib.add_tag(entry.id, style)
        try:
            lib.save(DEFAULT_LIB_PATH)
        except Exception:
            pass
    print(f"Detected style: {style}")

    if getattr(args, "analysis", False) or getattr(args, "json", False):
        from iconlib.style_analysis import IconStyleAnalysis
        report = IconStyleAnalysis().analyze(path)
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
        else:
            print("\n=== Style Analysis Report ===")
            print(json.dumps(report, indent=2))


def cmd_transform(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    from iconlib.transform import IconTransform
    IconTransform().transform(path, args.out, args.mode)
    print(f"Transformed icon ({args.mode}) -> {args.out}")


def cmd_anim(args, lib):
    from iconlib.fluent3d_anim import Fluent3DAnimation
    print(f"Generating Fluent 3D animation for prompt: '{args.prompt}' "
          f"({args.frames} frames, motion={args.motion}) -> {args.out_dir}")
    anim = Fluent3DAnimation(ai_url=lib.ai_url, ai_key=lib.ai_key)
    res = anim.animate(args.prompt, args.out_dir, args.frames, args.motion)
    print("Animation generated:")
    print(f" - GIF:      {res['gif']}")
    print(f" - WebP:     {res['webp']}")
    print(f" - Sprite:   {res['sprite']}")
    print(f" - Timeline: {res['timeline']}")


def cmd_uiasset(args, lib):
    entry, _ = resolve_icon_target(lib, args.target)
    if not entry:
        raise ValueError("UI asset generation requires a library icon ID.")
    from iconlib.cache import IconCache
    from iconlib.ui_assets import UIAssetPipeline
    cache = IconCache()
    cache.build(lib)
    res = UIAssetPipeline(cache).build(entry.id, args.ui_type, args.out_dir)
    print(f"UI asset '{args.ui_type}' generated:")
    print(f" - Preview: {res['preview']}")
    print(f" - Meta:    {res['meta']}")


def cmd_theme(args, lib):
    entry, _ = resolve_icon_target(lib, args.target)
    if not entry:
        raise ValueError("Theme generation requires a library icon ID.")
    from iconlib.cache import IconCache
    from iconlib.theme import UIThemeGenerator
    cache = IconCache()
    cache.build(lib)
    res = UIThemeGenerator(cache).generate(entry.id, args.out_dir, args.style)

    if args.json:
        result = {
            "name": f"iconstudio-theme-{entry.id}",
            "style": args.style,
            "palette": res["palette"],
            "gradients": res["gradients"],
            "shadows": res["shadows"],
            "effects": res["effects"],
            "components": sorted(res["components"].keys()),
            "surfaces": sorted(res["surfaces"].keys()),
            "icons": sorted(res["icons"]["variants"].keys()),
            "icon_effects": sorted(res["icons"]["effects"].get("variants", {}).keys()),
            "layouts": sorted(res["layouts"].keys()),
            "typography": sorted(res["typography"].get("specimens", {}).keys()),
            "preview": res["preview"],
            "sheet": res["sheet"],
            "tokens": res["tokens"],
            "pack": res["pack"],
            "errors": res["errors"],
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"=== UI Theme generated for ID {entry.id} ({entry.name}) ===")
        print(f"Style:      {args.style}")
        print(f"Components: {len(res['components'])} ({', '.join(sorted(res['components'].keys()))})")
        print(f"Surfaces:   {len(res['surfaces'])} ({', '.join(sorted(res['surfaces'].keys()))})")
        print(f"Icon set:   {len(res['icons']['variants'])} variants "
              f"({', '.join(sorted(res['icons']['variants'].keys()))})")
        print(f"Icon fx:    {len(res['icons']['effects'].get('variants', {}))} "
              f"({', '.join(sorted(res['icons']['effects'].get('variants', {}).keys()))})")
        print(f"Layouts:    {len(res['layouts'])} ({', '.join(sorted(res['layouts'].keys()))})")
        print(f"Typography: {len(res['typography'].get('specimens', {}))} specimens")
        print("Palette:")
        for key, val in res["palette"].items():
            if key == "shadow":
                print(f"  {key:14s} rgba{tuple(val)}")
            else:
                print(f"  {key:14s} {_theme_hex(val)}")
        print(f"Preview:    {res['preview']}")
        print(f"Sprite:     {res['sheet']}")
        print(f"Tokens:     {res['tokens']['json']}")
        print(f"CSS:        {res['tokens']['css']}")
        print(f"INI:        {res['tokens']['ini']}")
        print(f"ThemePack:  {res['pack']}")
        if res["errors"]:
            print(f"Warnings:   {len(res['errors'])} component(s) skipped")


def _theme_hex(rgb):
    return "#%02x%02x%02x" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def cmd_convertstyle(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    from iconlib.style_convert import IconStyleConverter
    res = IconStyleConverter().convert(path, args.out_dir, args.target_style)
    print(f"Converted style -> {args.target_style}")
    print(f" - PNG: {res['png']}")
    print(f" - ICO: {res['ico']}")
    print(f" - Original style: {res['original_style']['style']}")
    print(f" - New style:      {res['new_style']['style']}")


def cmd_texticon(args, lib):
    from iconlib.text_icon import TextIconGenerator
    res = TextIconGenerator().generate(args.text, args.out_dir, args.style, args.size)
    print(f"Text icon '{args.text}' ({args.style}) generated:")
    print(f" - PNG: {res['png']}")
    print(f" - ICO: {res['ico']}")


def cmd_dataicon(args, lib):
    from iconlib.data_icon import DataIconGenerator
    raw = args.data.split(",")
    try:
        data = [float(x.strip()) for x in raw if x.strip() != ""]
    except ValueError:
        raise ValueError("Data must be comma-separated numbers (e.g. '1,2,3,4,5')")
    if not data:
        raise ValueError("Data must contain at least one number")
    res = DataIconGenerator().generate(data, args.out_dir, args.chart, args.style, args.size)
    print(f"Data icon generated (chart={args.chart}, style={args.style}, points={len(data)}):")
    print(f" - Chart: {res['chart']}")
    print(f" - PNG:   {res['png']}")
    print(f" - ICO:   {res['ico']}")
    if res.get("dpi"):
        print(f" - DPI:   {res['dpi']}")
    print(f" - Meta:  {res['meta']}")
    if getattr(args, "add", False):
        name = args.name or f"data-{args.chart}"
        lib.add_icon(res["ico"], name=name)
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added to library as '{name}' ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_databatch(args, lib):
    from iconlib.data_batch import DataIconBatch
    res = DataIconBatch().generate(args.source, args.out_dir, args.chart, args.style, args.size)
    print(f"Data batch generated (chart={args.chart}, style={args.style}, icons={res['count']}):")
    for i, item in enumerate(res["icons"], 1):
        print(f" [{i}] {item['name']} ({item['points']} pts) -> {item['ico']}")
    print(f" - Sheet:    {res['sheet']}")
    print(f" - Manifest: {res['manifest']}")
    if getattr(args, "add", False):
        for item in res["icons"]:
            lib.add_icon(item["ico"], name=item["name"])
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added {res['count']} icons to library ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_geoicon(args, lib):
    from iconlib.geo_icon import GeoIconGenerator
    res = GeoIconGenerator().generate(
        args.geo, args.out_dir, args.symbol, args.style, args.size)
    info = res["geo"]
    desc = f"points={info['points']}"
    if "name" in info:
        desc += f" name={info['name']}"
    print(f"Geo icon generated (symbol={res['symbol']}, style={args.style}, {desc}):")
    print(f" - Shape: {res['shape']}")
    print(f" - PNG:   {res['png']}")
    print(f" - ICO:   {res['ico']}")
    if res.get("dpi"):
        print(f" - DPI:   {res['dpi']}")
    if "center" in info:
        print(f" - Center: {info['center'][0]}, {info['center'][1]}")
    print(f" - Meta:  {res['meta']}")
    if getattr(args, "add", False):
        name = args.name or f"geo-{res['symbol']}"
        lib.add_icon(res["ico"], name=name)
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added to library as '{name}' ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_geobatch(args, lib):
    from iconlib.geo_batch import GeoIconBatch
    res = GeoIconBatch().generate(
        args.source, args.out_dir, args.symbol, args.style, args.size)
    print(f"Geo icon batch generated (symbol={args.symbol}, style={args.style}, "
          f"icons={res['count']}):")
    for i, item in enumerate(res["icons"], 1):
        info = item["geo"]
        desc = f"{item['symbol']}"
        if "name" in info:
            desc += f" name={info['name']}"
        print(f" [{i}] {item['name']} ({desc}, pts={info['points']}) -> {item['ico']}")
    print(f" - Sheet:    {res['sheet']}")
    print(f" - Manifest: {res['manifest']}")
    if getattr(args, "add", False):
        for item in res["icons"]:
            lib.add_icon(item["ico"], name=item["name"])
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added {res['count']} icons to library ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_audioicon(args, lib):
    from iconlib.audio_icon import AudioIconGenerator
    palette = getattr(args, "palette", False)
    res = AudioIconGenerator().generate(
        args.source, args.out_dir, args.style, args.size, args.mode, palette=palette)
    a = res["audio"]
    print(f"Audio icon generated (style={args.style}, mode={res['mode']}, size={args.size}):")
    print(f" - Waveform: {res['waveform']}")
    print(f" - PNG:      {res['png']}")
    print(f" - ICO:      {res['ico']}")
    if res.get("dpi"):
        print(f" - DPI:      {res['dpi']}")
    detail = f" - Samples:  {a['samples']}  peak={a['peak']}  rms={a['rms']}"
    if "duration" in a:
        detail += f"  duration={a['duration']}s"
    print(detail)
    if res.get("palette"):
        p = res["palette"]
        print(f" - Palette:  primary={p['primary']} accent={p['accent']} "
              f"centroid={p['centroid']}")
    print(f" - Meta:     {res['meta']}")
    if getattr(args, "add", False):
        lib.add_icon(res["ico"], name=f"audio-{res['mode']}")
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added audio icon to library ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_audiobatch(args, lib):
    from iconlib.audio_batch import AudioIconBatch
    palette = getattr(args, "palette", False)
    res = AudioIconBatch().generate(
        args.source, args.out_dir, args.style, args.size, args.mode, palette=palette)
    print(f"Audio icon batch generated (style={args.style}, mode={args.mode}, icons={res['count']}):")
    for i, item in enumerate(res["icons"], 1):
        a = item["audio"]
        dur = f", {a['duration']}s" if "duration" in a else ""
        print(f" [{i}] {item['name']} ({item['mode']}{dur}) -> {item['ico']}")
    print(f" - Sheet:    {res['sheet']}")
    print(f" - Manifest: {res['manifest']}")
    if palette:
        print(" - Palette:  spectrum-derived colors enabled")
    if getattr(args, "add", False):
        for item in res["icons"]:
            lib.add_icon(item["ico"], name=item["name"])
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added {res['count']} icons to library ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_textureicon(args, lib):
    from iconlib.texture_icon import TextureIconGenerator
    seed = getattr(args, "seed", None)
    res = TextureIconGenerator().generate(
        args.texture, args.out_dir, args.style, args.size, seed)
    print(f"Texture icon generated (texture={res['texture_name']}, style={args.style}, "
          f"size={args.size}, seed={res['seed']}):")
    print(f" - Texture: {res['texture']}")
    print(f" - PNG:     {res['png']}")
    print(f" - ICO:     {res['ico']}")
    if res.get("dpi"):
        print(f" - DPI:     {res['dpi']}")
    print(f" - Meta:    {res['meta']}")
    if getattr(args, "add", False):
        name = getattr(args, "name", None) or f"texture-{res['texture_name']}"
        lib.add_icon(res["ico"], name=name)
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added texture icon to library ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_texturebatch(args, lib):
    from iconlib.texture_batch import TextureIconBatch
    res = TextureIconBatch().generate(
        args.source, args.out_dir, args.style, args.size)
    print(f"Texture icon batch generated (style={args.style}, icons={res['count']}):")
    for i, item in enumerate(res["icons"], 1):
        print(f" [{i}] {item['name']} ({item['texture']}, seed={item['seed']}) -> {item['ico']}")
    print(f" - Sheet:    {res['sheet']}")
    print(f" - Manifest: {res['manifest']}")
    if getattr(args, "add", False):
        for item in res["icons"]:
            lib.add_icon(item["ico"], name=item["name"])
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added {res['count']} icons to library ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_ai(args, lib):
    prompt = " ".join(args.prompt) if isinstance(args.prompt, list) else args.prompt
    out_dir = getattr(args, "out", None) or "./ai_output"
    png_path, ico_path = lib.generate_ai_icon(prompt, out_dir)
    lib.save(DEFAULT_LIB_PATH)
    print(f"AI icon generated for prompt: '{prompt}'")
    print(f" - PNG: {png_path}")
    print(f" - ICO: {ico_path}")


def cmd_normalize(args, lib):
    entry, path = resolve_icon_target(lib, args.target)
    from iconlib.normalizer import IconNormalizer
    if entry:
        lib.normalize_icon(entry.id, args.out, args.style)
    else:
        IconNormalizer().normalize(path, args.out, args.style)
    print(f"Normalized icon ({args.style}) -> {args.out}")


def cmd_optimizeico(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    from iconlib.optimizer import IconOptimizer
    IconOptimizer().optimize_ico(path, args.out)
    print(f"ICO optimized -> {args.out}")


def cmd_buildcache(args, lib):
    from iconlib.cache import IconCache
    cache = IconCache()
    cache.build(lib)
    print(f"Cache built for {len(lib.entries)} icons "
          f"({len(cache.index_name)} names, {len(cache.index_tag)} tags, "
          f"{len(cache.index_style)} styles).")


def cmd_search(args, lib):
    from iconlib.cache import IconCache
    cache = IconCache()
    cache.build(lib)
    ids = cache.search(args.query)
    if not ids:
        print(f"No icons matching '{args.query}'.")
        return
    print(f"Search '{args.query}': {len(ids)} result(s)")
    for id_ in ids:
        e = lib.get_entry(id_)
        if e:
            tags = f" [{', '.join(e.tags)}]" if e.tags else ""
            print(f"  {e.id:4d} | {e.name}{tags} -> {e.path}")


def cmd_importdll(args, lib):
    from iconlib.dll_import import DLLIconImporter
    importer = DLLIconImporter(args.dll)
    icons = importer.import_icons()
    for item in icons:
        out_path = f"imported_{item['id']}.ico"
        with open(out_path, "wb") as f:
            f.write(item["ico"])
        lib.add_icon(out_path)
    lib.snapshot("import dll")
    lib.save(DEFAULT_LIB_PATH)
    print(f"Imported {len(icons)} icon group(s) from DLL -> {args.dll}")


def cmd_comparedll(args, lib):
    from iconlib.migrator import IconMigrator
    m = IconMigrator()
    diff = m.compare(m.load_dll(args.dll_a), m.load_dll(args.dll_b))
    print(f"=== DLL Compare: {args.dll_a} vs {args.dll_b} ===")
    print(f"Missing in B: {len(diff['missing_in_b'])}")
    for i in diff["missing_in_b"]:
        print(f"  {i['id']}")
    print(f"Missing in A: {len(diff['missing_in_a'])}")
    for i in diff["missing_in_a"]:
        print(f"  {i['id']}")
    print(f"Changed:    {len(diff['changed'])}")
    print(f"Duplicates: {len(diff['duplicates'])}")


def cmd_migratedll(args, lib):
    from iconlib.migrator import IconMigrator
    ids = [int(x.strip()) for x in args.ids.split(",") if x.strip()]
    m = IconMigrator()
    m.migrate(m.load_dll(args.src), args.dst, args.out, ids)
    print(f"Migrated {len(ids)} icon(s) -> {args.out}")


def cmd_load(args, lib):
    lib.load(args.path)
    print(f"Loaded library: {args.path} ({len(lib.entries)} icons)")


def cmd_save(args, lib):
    lib.save(args.path)
    print(f"Saved library: {args.path} ({len(lib.entries)} icons)")




def cmd_dpi(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    out_path = args.out
    from iconlib.dpi_generator import DPIGenerator
    DPIGenerator().generate_dpi_set(path, out_path)
    print(f"Generated multi-resolution DPI icon -> {out_path}")


def cmd_preset(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    from iconlib.style_presets import IconStylePresets
    IconStylePresets().apply_preset(path, args.out, args.preset)
    print(f"Applied preset '{args.preset}' -> {args.out}")


def cmd_convert(args, lib):
    _, path = resolve_icon_target(lib, args.target)
    from iconlib.style_convert import StyleConverter
    StyleConverter().classic_to_fluent(path, args.out)
    print(f"Converted style (Classic -> Fluent) -> {args.out}")


def cmd_validate(args, lib):
    from iconlib.validator import IconValidator
    val = IconValidator()
    if args.target:
        entry, _ = resolve_icon_target(lib, args.target)
        if not entry:
            raise ValueError(f"Icon ID {args.target} not found in library.")
        report = val.validate(entry)
        print(f"Validation for ID {entry.id} ({entry.name}):")
        print(json.dumps(report, indent=2))
    else:
        results = lib.validate_all()
        print("=== Library Validation ===")
        for eid, rep in results.items():
            if eid != "duplicates":
                status = "PASS" if rep.get("valid_ico") and not rep.get("issues") else "WARN"
                print(f" [{status}] ID {eid}: {rep}")
        dups = results.get("duplicates", [])
        if dups:
            print(f"\nDuplicates found: {len(dups)} groups.")
        else:
            print("\nNo duplicates detected.")


def cmd_history(args, lib):
    from iconlib.history import IconLibraryHistory
    hist = IconLibraryHistory()
    snaps = hist.list_snapshots()
    if not snaps:
        print("History is empty.")
        return
    print(f"History snapshots ({len(snaps)}):")
    for idx, s in enumerate(snaps):
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.get("timestamp", 0)))
        print(f" [{idx:2d}] {t_str} | {s.get('message', 'update')} ({len(s.get('entries', []))} icons)")


def cmd_restore(args, lib):
    from iconlib.history import IconLibraryHistory
    hist = IconLibraryHistory()
    idx = int(args.index)
    hist.restore_snapshot(idx, lib)
    lib.save(DEFAULT_LIB_PATH)
    print(f"Restored library to snapshot [{idx}]. Current icons: {len(lib.entries)}")


def cmd_diff(args, lib):
    from iconlib.history import IconLibraryHistory
    hist = IconLibraryHistory()
    diff_data = hist.diff(int(args.index_a), int(args.index_b))
    print(f"=== Diff between snapshots {args.index_a} and {args.index_b} ===")
    print(f"Added:   {len(diff_data['added'])}")
    for e in diff_data["added"]:
        print(f"  + ID {e['id']}: {e['name']}")
    print(f"Removed: {len(diff_data['removed'])}")
    for e in diff_data["removed"]:
        print(f"  - ID {e['id']}: {e['name']}")
    print(f"Changed: {len(diff_data['changed'])}")
    for a, b in diff_data["changed"]:
        print(f"  ~ ID {a['id']}: {a['name']}")


def cmd_pack(args, lib):
    from iconlib.iconpack import IconPack
    from iconlib.history import IconLibraryHistory
    hist = IconLibraryHistory()
    out_path = args.out
    IconPack().export_pack(lib, hist, out_path)
    print(f"Exported library to IconPack -> {out_path}")


def cmd_unpack(args, lib):
    from iconlib.iconpack import IconPack
    from iconlib.history import IconLibraryHistory
    hist = IconLibraryHistory()
    IconPack().import_pack(args.pack, lib, hist)
    lib.save(DEFAULT_LIB_PATH)
    print(f"Imported IconPack from {args.pack}. Current icons: {len(lib.entries)}")


def cmd_exportdll(args, lib):
    from iconlib.dll_export import DLLBuilder
    builder = DLLBuilder()
    gid = 100
    biid = 200
    count = 0
    for entry in lib.entries:
        if os.path.isfile(entry.path) and entry.path.lower().endswith(".ico"):
            builder.add_icon(entry.path, gid, biid)
            gid += 1
            biid += 20
            count += 1
    if count == 0:
        raise ValueError("No .ico files in library to export into DLL.")
    builder.build(args.out)
    print(f"Exported {count} icons to Windows PE DLL -> {args.out}")


def cmd_fluent3d(args, lib):
    from iconlib.fluent3d import Fluent3DGenerator
    print(f"Generating Fluent 3D icon for prompt: '{args.prompt}' -> {args.out_dir}")
    gen = Fluent3DGenerator(ai_url=lib.ai_url, ai_key=lib.ai_key)
    res = gen.generate(args.prompt, args.out_dir)
    print("Fluent 3D generation complete:")
    print(f" - Base:       {res['base']}")
    print(f" - Shaded:     {res['shaded']}")
    print(f" - Normalized: {res['normalized']}")
    print(f" - Optimized:  {res['ico']}")


def cmd_avatar3d(args, lib):
    from iconlib.avatar3d import Fluent3DAvatar
    print(f"Generating Fluent 3D avatar for prompt: '{args.prompt}' -> {args.out_dir}")
    av = Fluent3DAvatar(ai_url=lib.ai_url, ai_key=lib.ai_key)
    res = av.generate(args.prompt, args.out_dir, args.style,
                      role=args.role, webp=args.webp, sprite=args.sprite)
    print(f"Fluent 3D avatar generated (style={res['style']}, role={res['role']}):")
    print(f" - Base:       {res['base']}")
    print(f" - Shaded:     {res['shaded']}")
    print(f" - Normalized: {res['normalized']}")
    print(f" - PNG:        {res['png']}")
    print(f" - ICO:        {res['ico']}")
    if res.get("webp"):
        print(f" - WebP:       {res['webp']}")
    if res.get("sheet"):
        print(f" - Sheet:      {res['sheet']}")
    print(f" - Meta:       {res['meta']}")


def cmd_avatarbatch(args, lib):
    from iconlib.avatar_batch import Fluent3DAvatarBatch
    res = Fluent3DAvatarBatch(ai_url=lib.ai_url, ai_key=lib.ai_key).generate(
        args.source, args.out_dir, args.style)
    print(f"Fluent 3D avatar batch generated (style={args.style}, avatars={res['count']}):")
    for i, item in enumerate(res["avatars"], 1):
        print(f" [{i}] {item['name']} (role={item['role']}, style={item['style']}) -> {item['ico']}")
    print(f" - Sheet:    {res['sheet']}")
    print(f" - Manifest: {res['manifest']}")
    if getattr(args, "add", False):
        for item in res["avatars"]:
            lib.add_icon(item["ico"], name=item["name"])
        lib.save(DEFAULT_LIB_PATH)
        print(f" - Added {res['count']} avatars to library ({DEFAULT_LIB_PATH}).")
        print(f"   Run 'iconstudio exportdll <out.dll>' to export the library to a PE DLL.")


def cmd_layout(args, lib):
    from iconlib.cache import IconCache
    from iconlib.layout import IconLayoutEngine
    cache = IconCache()
    cache.build(lib)
    ids = [e.id for e in lib.entries]
    if not ids:
        raise ValueError("Library is empty. Add icons before generating layouts.")
    eng = IconLayoutEngine()
    res = eng.layout(ids, args.layout_type, cache, args.out_dir, spacing=args.spacing, padding=args.padding)
    print(f"Layout '{args.layout_type}' generated successfully:")
    print(f" - Preview:  {res['preview']}")
    print(f" - Metadata: {res['meta']}")


def cmd_svg(args, lib):
    from iconlib.svg_to_ico import SVGToICO
    out_ico = args.out or (args.path + ".ico")
    SVGToICO().svg_to_ico(args.path, out_ico)
    print(f"Converted SVG to ICO -> {out_ico}")


def main():
    parser = argparse.ArgumentParser(prog="iconstudio", description="IconStudio CLI & Toolset")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # genset
    p_gen = subparsers.add_parser("genset", help="Generate AI batch icon set and iconpack")
    p_gen.add_argument("prompt", help="Main prompt description")
    p_gen.add_argument("categories", help="Comma-separated category names")
    p_gen.add_argument("out_dir", help="Output directory")
    p_gen.add_argument("style", nargs="?", default="fluent", help="Style: fluent/classic/monochrome (default: fluent)")
    p_gen.add_argument("--json", action="store_true", help="Output raw JSON")

    # recommend
    p_rec = subparsers.add_parser("recommend", help="Recommend icons based on search query")
    p_rec.add_argument("query", help="Text description of desired icon")
    p_rec.add_argument("--json", action="store_true", help="Output raw JSON")

    # semantic
    p_sem = subparsers.add_parser("semantic", help="Run semantic analysis on icon ID or file")
    p_sem.add_argument("target", help="Icon ID or file path")
    p_sem.add_argument("--json", action="store_true", help="Output raw JSON")

    # mapaction
    p_map = subparsers.add_parser("mapaction", help="Map icon to UI/UX action")
    p_map.add_argument("target", help="Icon ID or file path")
    p_map.add_argument("--json", action="store_true", help="Output raw JSON")

    # classify
    p_cls = subparsers.add_parser("classify", help="Classify icon category")
    p_cls.add_argument("target", help="Icon ID or file path")

    # optimize
    p_opt = subparsers.add_parser("optimize", help="Optimize PNG or ICO file")
    p_opt.add_argument("target", help="Icon ID or file path")
    p_opt.add_argument("out", nargs="?", help="Output file path (optional)")

    # duplicates
    subparsers.add_parser("duplicates", help="Find duplicate icons in library")

    # list
    subparsers.add_parser("list", help="List icons in default library")

    # add
    p_add = subparsers.add_parser("add", help="Add icon to default library")
    p_add.add_argument("path", help="Path to icon file")
    p_add.add_argument("name", nargs="?", default=None, help="Display name (optional)")

    # remove
    p_rm = subparsers.add_parser("remove", help="Remove icon from default library")
    p_rm.add_argument("id", help="Icon ID")

    # style
    p_sty = subparsers.add_parser("style", help="Detect icon style (and optional style analysis report)")
    p_sty.add_argument("target", help="Icon ID or file path")
    p_sty.add_argument("--analysis", action="store_true", help="Print full style analysis report")
    p_sty.add_argument("--json", action="store_true", help="Output style analysis as raw JSON")

    # dpi
    p_dpi = subparsers.add_parser("dpi", help="Generate multi-resolution DPI icon")
    p_dpi.add_argument("target", help="Icon ID or file path")
    p_dpi.add_argument("out", help="Output .ico file path")

    # preset
    p_pre = subparsers.add_parser("preset", help="Apply visual style preset to icon")
    p_pre.add_argument("target", help="Icon ID or file path")
    p_pre.add_argument("preset", help="Preset name (fluent_light, fluent_dark, monochrome, high_contrast, pastel, classic_xp)")
    p_pre.add_argument("out", help="Output file path")

    # convert
    p_cnv = subparsers.add_parser("convert", help="Convert icon style (Classic -> Fluent)")
    p_cnv.add_argument("target", help="Icon ID or file path")
    p_cnv.add_argument("out", help="Output file path")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate icons in library")
    p_val.add_argument("target", nargs="?", default=None, help="Icon ID (optional, validates all if omitted)")

    # history
    subparsers.add_parser("history", help="List snapshot history")

    # restore
    p_res = subparsers.add_parser("restore", help="Restore library snapshot")
    p_res.add_argument("index", help="Snapshot index")

    # diff
    p_dif = subparsers.add_parser("diff", help="Diff two library snapshots")
    p_dif.add_argument("index_a", help="First snapshot index")
    p_dif.add_argument("index_b", help="Second snapshot index")

    # pack
    p_pck = subparsers.add_parser("pack", help="Export library to .iconpack")
    p_pck.add_argument("out", help="Output .iconpack file path")

    # unpack
    p_upk = subparsers.add_parser("unpack", help="Import .iconpack into library")
    p_upk.add_argument("pack", help="Path to .iconpack file")

    # exportdll
    p_dll = subparsers.add_parser("exportdll", help="Export library to Windows PE DLL")
    p_dll.add_argument("out", help="Output .dll file path")

    # fluent3d
    p_f3d = subparsers.add_parser("fluent3d", help="Generate Fluent 3D icon from text prompt")
    p_f3d.add_argument("prompt", help="Text prompt description")
    p_f3d.add_argument("out_dir", help="Output directory")

    # avatar3d
    p_av3 = subparsers.add_parser("avatar3d", help="Generate a Fluent 3D avatar (AI -> face -> icon)")
    p_av3.add_argument("prompt", help="Avatar prompt (e.g. 'robot engineer')")
    p_av3.add_argument("out_dir", help="Output directory")
    p_av3.add_argument("style", nargs="?", default="fluent3d",
                       help="Style: fluent3d/pastel/glossy/cartoon (default: fluent3d)")
    p_av3.add_argument("--role", nargs="?", default=None,
                       help="Role: developer/designer/admin/manager/engineer/support")
    p_av3.add_argument("--webp", action="store_true", help="Also export WebP")
    p_av3.add_argument("--sprite", action="store_true", help="Also export a DPI sprite sheet")

    # avatarbatch
    p_avb = subparsers.add_parser("avatarbatch", help="Generate a team avatar set from a roster (CSV/JSON/inline)")
    p_avb.add_argument("source", help="Path to .csv/.json OR inline spec 'Name=prompt;Name2=prompt2'")
    p_avb.add_argument("out_dir", help="Output directory")
    p_avb.add_argument("style", nargs="?", default="fluent3d",
                       help="Style: fluent3d/pastel/glossy/cartoon (default: fluent3d)")
    p_avb.add_argument("--add", action="store_true",
                       help="Add all generated avatars to the default library (enables exportdll)")

    # layout
    p_lay = subparsers.add_parser("layout", help="Generate UI icon layout (grid, toolbar, ribbon, sidebar, menu)")
    p_lay.add_argument("layout_type", choices=["grid", "toolbar", "ribbon", "sidebar", "menu"], help="Layout type")
    p_lay.add_argument("out_dir", help="Output directory for layout assets")
    p_lay.add_argument("--spacing", type=int, default=16, help="Spacing between icons (default: 16)")
    p_lay.add_argument("--padding", type=int, default=24, help="Outer padding (default: 24)")

    # svg
    p_svg = subparsers.add_parser("svg", help="Convert SVG vector to multi-resolution ICO")
    p_svg.add_argument("path", help="Path to SVG file")
    p_svg.add_argument("out", nargs="?", default=None, help="Output .ico file (optional)")

    # transform
    p_trf = subparsers.add_parser("transform", help="Apply icon transform (extrude/bevel/emboss/glow/...)")
    p_trf.add_argument("target", help="Icon ID or file path")
    p_trf.add_argument("mode", help="Mode: extrude/bevel/emboss/glow/inner_shadow/outer_shadow/highlight/metallic")
    p_trf.add_argument("out", help="Output file path")

    # anim
    p_anim = subparsers.add_parser("anim", help="Generate Fluent 3D animation (GIF/WebP/sprite)")
    p_anim.add_argument("prompt", help="Text prompt description")
    p_anim.add_argument("out_dir", help="Output directory")
    p_anim.add_argument("frames", nargs="?", type=int, default=12, help="Number of frames (default: 12)")
    p_anim.add_argument("motion", nargs="?", default="rotate",
                        help="Motion: rotate/tilt/bounce/pulse/glow/morph (default: rotate)")

    # uiasset
    p_uia = subparsers.add_parser("uiasset", help="Generate UI asset (button/toggle/menu/toolbar/...)")
    p_uia.add_argument("target", help="Icon ID")
    p_uia.add_argument("ui_type", help="UI type: button/toggle/checkbox/radio/slider/progress/input/search/dropdown/toolbar/ribbon/sidebar/menu")
    p_uia.add_argument("out_dir", help="Output directory")

    # theme
    p_thm = subparsers.add_parser("theme", help="Generate a full UI theme pack (colors/gradients/components/tokens)")
    p_thm.add_argument("target", help="Icon ID")
    p_thm.add_argument("out_dir", help="Output directory for the theme pack")
    p_thm.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/classic/monochrome (default: fluent)")
    p_thm.add_argument("--json", action="store_true", help="Output raw JSON")

    # convertstyle
    p_cst = subparsers.add_parser("convertstyle", help="Convert icon style (fluent/monochrome/flat)")
    p_cst.add_argument("target", help="Icon ID or file path")
    p_cst.add_argument("target_style", help="Target style: fluent/monochrome/flat")
    p_cst.add_argument("out_dir", help="Output directory")

    # texticon
    p_txt = subparsers.add_parser("texticon", help="Generate icon from text (text -> glyph -> icon)")
    p_txt.add_argument("text", help="Text to render (e.g. 'AI')")
    p_txt.add_argument("out_dir", help="Output directory")
    p_txt.add_argument("style", nargs="?", default="fluent", help="Style: fluent/monochrome/outline/classic")
    p_txt.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")

    # dataicon
    p_dat = subparsers.add_parser("dataicon", help="Generate icon from data (data -> chart -> icon)")
    p_dat.add_argument("data", help="Comma-separated numbers (e.g. '1,2,3,4,5')")
    p_dat.add_argument("out_dir", help="Output directory")
    p_dat.add_argument("chart", nargs="?", default="line",
                       help="Chart: line/bar/area/donut/sparkline (default: line)")
    p_dat.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/monochrome/outline/classic (default: fluent)")
    p_dat.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")
    p_dat.add_argument("--add", action="store_true",
                       help="Add the generated icon to the default library (enables exportdll)")
    p_dat.add_argument("--name", nargs="?", default=None, help="Display name when adding to the library")

    # databatch
    p_dbt = subparsers.add_parser("databatch", help="Generate an icon set from many data series (CSV/JSON/inline)")
    p_dbt.add_argument("source", help="Path to .csv/.json OR inline spec 'name=1,2,3;name2=4,5,6'")
    p_dbt.add_argument("out_dir", help="Output directory")
    p_dbt.add_argument("chart", nargs="?", default="line",
                       help="Chart: line/bar/area/donut/sparkline (default: line)")
    p_dbt.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/monochrome/outline/classic (default: fluent)")
    p_dbt.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")
    p_dbt.add_argument("--add", action="store_true",
                       help="Add all generated icons to the default library (enables exportdll)")

    # geoicon
    p_geo = subparsers.add_parser("geoicon", help="Generate an icon from geo data (geo -> symbol -> icon)")
    p_geo.add_argument("geo",
                       help="'lat,lon;lat,lon' pairs, a region name (e.g. 'London'), "
                            "or inline heat values '0.2,0.5,0.9'")
    p_geo.add_argument("out_dir", help="Output directory")
    p_geo.add_argument("symbol", nargs="?", default="pin",
                       help="Symbol: pin/marker/region/route/area/heatmap (default: pin)")
    p_geo.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/monochrome/outline/classic (default: fluent)")
    p_geo.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")
    p_geo.add_argument("--add", action="store_true",
                       help="Add the generated icon to the default library (enables exportdll)")
    p_geo.add_argument("--name", nargs="?", default=None, help="Display name when adding to the library")

    # geobatch
    p_gbt = subparsers.add_parser("geobatch", help="Generate an icon set from geo features (folder/CSV/JSON/inline)")
    p_gbt.add_argument("source",
                       help="Folder of .json/.geojson/.csv/.txt OR a path list OR inline "
                            "'name|symbol|geo|style//name2|...'")
    p_gbt.add_argument("out_dir", help="Output directory")
    p_gbt.add_argument("symbol", nargs="?", default="pin",
                       help="Default symbol: pin/marker/region/route/area/heatmap (default: pin)")
    p_gbt.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/monochrome/outline/classic (default: fluent)")
    p_gbt.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")
    p_gbt.add_argument("--add", action="store_true",
                       help="Add all generated icons to the default library (enables exportdll)")

    # audioicon
    p_aud = subparsers.add_parser("audioicon", help="Generate an icon from audio (waveform/spectrogram)")
    p_aud.add_argument("source", help="Path to .wav/.mp3/.ogg OR inline samples '0.1,0.4,-0.2,...'")
    p_aud.add_argument("out_dir", help="Output directory")
    p_aud.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/monochrome/outline/classic (default: fluent)")
    p_aud.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")
    p_aud.add_argument("--mode", nargs="?", default="waveform",
                       help="Mode: waveform/bars/spectrogram/ring (default: waveform)")
    p_aud.add_argument("--palette", action="store_true",
                       help="Derive icon colors from the audio spectrum (tint the glyph)")
    p_aud.add_argument("--add", action="store_true",
                       help="Add the generated icon to the default library (enables exportdll)")

    # audiobatch
    p_aub = subparsers.add_parser("audiobatch", help="Generate an icon set from many audio files (folder/CSV/JSON)")
    p_aub.add_argument("source", help="Folder with .wav/.mp3/.ogg OR path list (.csv/.json/.txt)")
    p_aub.add_argument("out_dir", help="Output directory")
    p_aub.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/monochrome/outline/classic (default: fluent)")
    p_aub.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")
    p_aub.add_argument("--mode", nargs="?", default="waveform",
                       help="Mode: waveform/bars/spectrogram/ring (default: waveform)")
    p_aub.add_argument("--palette", action="store_true",
                       help="Derive icon colors from each audio spectrum (tint the glyphs)")
    p_aub.add_argument("--add", action="store_true",
                       help="Add all generated icons to the default library (enables exportdll)")

    # textureicon
    p_tex = subparsers.add_parser("textureicon",
                                  help="Generate an icon from a procedural texture (noise/pattern/material)")
    p_tex.add_argument("texture",
                       help="Texture: perlin/simplex/worley/grain/metal/carbon/wood/marble/dots/grid/stripes/waves")
    p_tex.add_argument("out_dir", help="Output directory")
    p_tex.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/monochrome/outline/classic (default: fluent)")
    p_tex.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")
    p_tex.add_argument("--seed", type=int, default=None,
                       help="Deterministic noise seed (default: derived from texture name)")
    p_tex.add_argument("--name", nargs="?", default=None, help="Library name when using --add")
    p_tex.add_argument("--add", action="store_true",
                       help="Add the generated icon to the default library (enables exportdll)")

    # texturebatch
    p_txb = subparsers.add_parser("texturebatch",
                                  help="Generate an icon set from many procedural textures (folder/CSV/JSON/inline)")
    p_txb.add_argument("source", help="Folder OR list (.csv/.json/.txt) OR inline 'perlin//marble//carbon'")
    p_txb.add_argument("out_dir", help="Output directory")
    p_txb.add_argument("style", nargs="?", default="fluent",
                       help="Style: fluent/monochrome/outline/classic (default: fluent)")
    p_txb.add_argument("--size", type=int, default=256, help="Icon size in pixels (default: 256)")
    p_txb.add_argument("--add", action="store_true",
                       help="Add all generated icons to the default library (enables exportdll)")

    # ai
    p_ai = subparsers.add_parser("ai", help="Generate an AI icon from a text prompt")
    p_ai.add_argument("prompt", nargs="+", help="Prompt description (e.g. 'blue folder with cloud symbol')")
    p_ai.add_argument("--out", nargs="?", default=None, help="Output directory (default: ./ai_output)")

    # normalize
    p_nrm = subparsers.add_parser("normalize", help="Normalize icon to a target style")
    p_nrm.add_argument("target", help="Icon ID or file path")
    p_nrm.add_argument("style", help="Target style: fluent/classic/monochrome")
    p_nrm.add_argument("out", help="Output file path")

    # optimizeico
    p_oic = subparsers.add_parser("optimizeico", help="Optimize an ICO file")
    p_oic.add_argument("target", help="Icon ID or file path")
    p_oic.add_argument("out", help="Output .ico file path")

    # buildcache
    subparsers.add_parser("buildcache", help="Build the icon search cache")

    # search
    p_srch = subparsers.add_parser("search", help="Search icons via cache index")
    p_srch.add_argument("query", help="Search text")

    # importdll
    p_imp = subparsers.add_parser("importdll", help="Import icon resources from a Windows DLL")
    p_imp.add_argument("dll", help="Path to the .dll file")

    # comparedll
    p_cmp = subparsers.add_parser("comparedll", help="Compare icon resources of two DLLs")
    p_cmp.add_argument("dll_a", help="First .dll file")
    p_cmp.add_argument("dll_b", help="Second .dll file")

    # migratedll
    p_mig = subparsers.add_parser("migratedll", help="Migrate icons between two DLLs")
    p_mig.add_argument("src", help="Source .dll file")
    p_mig.add_argument("dst", help="Destination .dll file")
    p_mig.add_argument("ids", help="Comma-separated icon IDs to copy (e.g. 101,102,103)")
    p_mig.add_argument("out", help="Output .dll file path")

    # load
    p_ld = subparsers.add_parser("load", help="Load a library from a JSON file")
    p_ld.add_argument("path", help="Path to library JSON file")

    # save
    p_sv = subparsers.add_parser("save", help="Save the library to a JSON file")
    p_sv.add_argument("path", help="Path to library JSON file")

    # exportpack / importpack (aliases of pack/unpack)
    p_expk = subparsers.add_parser("exportpack", help="Export library to .iconpack (alias of pack)")
    p_expk.add_argument("out", help="Output .iconpack file path")
    p_impk = subparsers.add_parser("importpack", help="Import .iconpack into library (alias of unpack)")
    p_impk.add_argument("pack", help="Path to .iconpack file")

    # gui
    subparsers.add_parser("gui", help="Launch IconStudio GUI")

    args = parser.parse_args()

    if not args.command or args.command == "gui":
        from iconstudio.gui.app import main as gui_main
        gui_main()
        return

    lib = get_library()

    try:
        if args.command == "genset":
            cmd_genset(args, lib)
        elif args.command == "recommend":
            cmd_recommend(args, lib)
        elif args.command == "semantic":
            cmd_semantic(args, lib)
        elif args.command == "mapaction":
            cmd_mapaction(args, lib)
        elif args.command == "classify":
            cmd_classify(args, lib)
        elif args.command == "optimize":
            cmd_optimize(args, lib)
        elif args.command == "duplicates":
            cmd_duplicates(args, lib)
        elif args.command == "list":
            cmd_list(args, lib)
        elif args.command == "add":
            cmd_add(args, lib)
        elif args.command == "remove":
            cmd_remove(args, lib)
        elif args.command == "style":
            cmd_style(args, lib)
        elif args.command == "dpi":
            cmd_dpi(args, lib)
        elif args.command == "preset":
            cmd_preset(args, lib)
        elif args.command == "convert":
            cmd_convert(args, lib)
        elif args.command == "validate":
            cmd_validate(args, lib)
        elif args.command == "history":
            cmd_history(args, lib)
        elif args.command == "restore":
            cmd_restore(args, lib)
        elif args.command == "diff":
            cmd_diff(args, lib)
        elif args.command == "pack":
            cmd_pack(args, lib)
        elif args.command == "unpack":
            cmd_unpack(args, lib)
        elif args.command == "exportdll":
            cmd_exportdll(args, lib)
        elif args.command == "fluent3d":
            cmd_fluent3d(args, lib)
        elif args.command == "avatar3d":
            cmd_avatar3d(args, lib)
        elif args.command == "avatarbatch":
            cmd_avatarbatch(args, lib)
        elif args.command == "layout":
            cmd_layout(args, lib)
        elif args.command == "svg":
            cmd_svg(args, lib)
        elif args.command == "transform":
            cmd_transform(args, lib)
        elif args.command == "anim":
            cmd_anim(args, lib)
        elif args.command == "uiasset":
            cmd_uiasset(args, lib)
        elif args.command == "theme":
            cmd_theme(args, lib)
        elif args.command == "convertstyle":
            cmd_convertstyle(args, lib)
        elif args.command == "texticon":
            cmd_texticon(args, lib)
        elif args.command == "dataicon":
            cmd_dataicon(args, lib)
        elif args.command == "databatch":
            cmd_databatch(args, lib)
        elif args.command == "geoicon":
            cmd_geoicon(args, lib)
        elif args.command == "geobatch":
            cmd_geobatch(args, lib)
        elif args.command == "audioicon":
            cmd_audioicon(args, lib)
        elif args.command == "audiobatch":
            cmd_audiobatch(args, lib)
        elif args.command == "textureicon":
            cmd_textureicon(args, lib)
        elif args.command == "texturebatch":
            cmd_texturebatch(args, lib)
        elif args.command == "ai":
            cmd_ai(args, lib)
        elif args.command == "normalize":
            cmd_normalize(args, lib)
        elif args.command == "optimizeico":
            cmd_optimizeico(args, lib)
        elif args.command == "buildcache":
            cmd_buildcache(args, lib)
        elif args.command == "search":
            cmd_search(args, lib)
        elif args.command == "importdll":
            cmd_importdll(args, lib)
        elif args.command == "comparedll":
            cmd_comparedll(args, lib)
        elif args.command == "migratedll":
            cmd_migratedll(args, lib)
        elif args.command == "load":
            cmd_load(args, lib)
        elif args.command == "save":
            cmd_save(args, lib)
        elif args.command == "exportpack":
            cmd_pack(args, lib)
        elif args.command == "importpack":
            cmd_unpack(args, lib)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
