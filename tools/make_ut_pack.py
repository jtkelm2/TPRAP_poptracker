"""Build the Universal Tracker map pack from the full Twilight Princess PopTracker pack.

    python tools/make_ut_pack.py <full pack dir> <output dir>

Universal Tracker only shows maps and pins; the Twilight Princess apworld supplies the logic. This keeps just what
Universal Tracker reads, with the same file paths, location names and section names as the full pack, so the
apworld's poptracker_name_mapping works with either:

  * maps/*.json, without maps that no tab in layouts/layouts_maps.json shows
  * the images those maps use
  * locations/dungeons/*.json and locations/overworld/*.json, reduced to location names, map positions and the
    sections that are Archipelago locations (those named in scripts/location_mapping.lua, and "ref"s to them).
    Pins that PopTracker hides until the player marks something (restrict_visibility_rules) are dropped:
    Universal Tracker cannot evaluate those rules. The exception are the dungeon entrance pins: the Archipelago
    game does not shuffle dungeon entrances, so each entrance keeps one pin listing all its own dungeon's checks.
  * LICENSE

Map images larger than MAX_IMAGE_SIDE are shrunk by a whole factor, and the pins on their maps scaled to match:
Universal Tracker draws the whole image as one texture, and the overworld's 8704x9984 image makes it lag. Maps in
PIN_SCALE get smaller pins than the full pack's, where pins are dense. Shrinking needs Pillow.

The output is written into <output dir>, replacing its maps/, images/ and locations/.
"""

import json
import pathlib
import re
import shutil
import sys

LOCATION_DIRS = ("locations/dungeons", "locations/overworld")
PIN_KEYS = ("map", "x", "y", "size")
MAX_IMAGE_SIDE = 2560
PIN_SCALE = {"overworld": 0.5}


def lua_codes(pack: pathlib.Path) -> list[str]:
    codes = []
    for line in (pack / "scripts/location_mapping.lua").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        m = re.match(r'\[BASE\s*\+\s*\d+\]\s*=\s*\{(.*)\}', s)
        if m and not s.startswith("--"):
            codes += [c for c in re.findall(r'"([^"]*)"', m.group(1)) if c.startswith("@")]
    return codes


def walk(nodes, parent=""):
    for node in nodes:
        path = f"{parent}/{node.get('name', '')}" if parent else node.get("name", "")
        yield node, path
        if "map_locations" not in node:
            yield from walk(node.get("children", []), path)


def layout_maps(node, out):
    if isinstance(node, list):
        for x in node:
            layout_maps(x, out)
    elif isinstance(node, dict):
        if node.get("type") == "map":
            out.update(node.get("maps", []))
        for value in node.values():
            layout_maps(value, out)
    return out


def shrink_image(src: pathlib.Path, dst: pathlib.Path) -> int:
    """Copy an image, shrunk by the smallest whole factor that fits MAX_IMAGE_SIDE. Returns the factor."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as f:
        head = f.read(24)
    width, height = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")  # PNG IHDR
    k = -(-max(width, height) // MAX_IMAGE_SIDE)
    if k <= 1:
        shutil.copyfile(src, dst)
        return 1
    from PIL import Image
    with Image.open(src) as im:
        im.resize((round(width / k), round(height / k)), Image.LANCZOS).save(dst, optimize=True)
    return k


def main() -> None:
    src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    files = sorted(p for d in LOCATION_DIRS for p in (src / d).glob("*.json"))
    docs = {p: json.loads(p.read_text(encoding="utf-8-sig")) for p in files}

    # Sections that are Archipelago locations: the ones location_mapping.lua names. Match codes ignoring case, and
    # by "location/section" alone where the lua's parent path differs from the json.
    by_code, by_leaf = {}, {}
    for doc in docs.values():
        for node, path in walk(doc):
            if "map_locations" not in node:
                continue
            for s in node.get("sections", []):
                code = f"@{path}/{s.get('name', '')}".lower()
                by_code[code] = s
                by_leaf.setdefault((node.get("name", "").strip().lower(), s.get("name", "").strip().lower()), []).append(code)
    checks = set()
    for code in lua_codes(src):
        hit = code.lower() if code.lower() in by_code else None
        if hit is None:
            parts = code.split("/")
            cands = by_leaf.get((parts[-2].strip().lower(), parts[-1].strip().lower()), [])
            if len(cands) != 1:
                sys.exit(f"cannot find {code} in the location files")
            hit = cands[0]
        checks.add(hit)

    check_sections = {id(by_code[c]) for c in checks}

    def keep_section(s):
        return s.get("name") and (id(s) in check_sections or
                                  ("ref" in s and "@" + s["ref"].lstrip("@").lower() in checks))

    # Dungeon entrance pins. At each dungeon entrance the full pack stacks every dungeon's checks, each stack hidden
    # until the player marks which dungeon that entrance leads to. The Archipelago game does not shuffle dungeon
    # entrances, so keep the stack of the entrance's own dungeon, listing all the checks of its location file.
    def norm(name):
        return name.replace("'", "").strip().lower()

    dungeon_checks = {}
    for p, doc in docs.items():
        if p.parent.name == "dungeons":
            for top in doc:
                names = dungeon_checks.setdefault(norm(top.get("name", "")), [])
                for node, _ in walk([top]):
                    for s in node.get("sections", []) if "map_locations" in node else []:
                        if id(s) in check_sections and s["name"] not in names:
                            names.append(s["name"])
    entrance_stacks = {}
    for doc in docs.values():
        for node, _ in walk(doc):
            for c in node.get("children", []):
                if ("map_locations" in c and norm(c.get("name", "")) in dungeon_checks
                        and norm(node.get("name", "")) == norm(c["name"]) + " entrance"):
                    entrance_stacks[id(c)] = dungeon_checks[norm(c["name"])]

    def strip(node):
        out = {"name": node.get("name", "")}
        if "map_locations" in node:
            stack = entrance_stacks.get(id(node))
            if stack is not None:
                pins = [scale_pin(ml, full_size=True) for ml in node["map_locations"]]
                sections = [{"name": name} for name in stack]
            else:
                pins = [scale_pin(ml) for ml in node["map_locations"] if "restrict_visibility_rules" not in ml]
                sections = [{"name": s["name"]} for s in node.get("sections", []) if keep_section(s)]
            if not pins or not sections:
                return None
            out["map_locations"], out["sections"] = pins, sections
            return out
        children = [c for c in (strip(c) for c in node.get("children", [])) if c]
        if not children:
            return None
        out["children"] = children
        return out

    for d in ("maps", "images", "locations"):
        shutil.rmtree(dst / d, ignore_errors=True)

    # Maps first: shrinking an image changes the coordinates of the pins on its maps.
    shown = layout_maps(json.loads((src / "layouts/layouts_maps.json").read_text(encoding="utf-8-sig")), set())
    image_factor, map_count = {}, 0
    coord_scale, pin_scale = {}, {}
    for p in sorted((src / "maps").glob("*.json")):
        maps = [m for m in json.loads(p.read_text(encoding="utf-8-sig")) if m["name"] in shown]
        for m in maps:
            if m["img"] not in image_factor:
                image_factor[m["img"]] = shrink_image(src / m["img"], dst / m["img"])
            k = image_factor[m["img"]]
            coord_scale[m["name"]] = 1 / k
            pin_scale[m["name"]] = PIN_SCALE.get(m["name"], 1) / k
            for key, default in (("location_size", 65), ("location_border_thickness", 8)):
                scale = pin_scale[m["name"]] if key == "location_size" else 1 / k
                if k > 1 or (key == "location_size" and m["name"] in PIN_SCALE):
                    m[key] = max(1, round(m.get(key, default) * scale))
        map_count += len(maps)
        (dst / "maps").mkdir(parents=True, exist_ok=True)
        (dst / "maps" / p.name).write_text(json.dumps(maps, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8")

    def scale_pin(ml, full_size=False):
        """full_size: scale the pin's size only as far as its map image was shrunk, ignoring PIN_SCALE."""
        pin = {k: ml[k] for k in PIN_KEYS if k in ml}
        for key in ("x", "y"):
            pin[key] = round(pin[key] * coord_scale.get(pin["map"], 1))
        if "size" in pin:
            scale = coord_scale if full_size else pin_scale
            pin["size"] = max(1, round(pin["size"] * scale.get(pin["map"], 1)))
        return pin

    kept_checks = 0
    for p, doc in docs.items():
        out = [c for c in (strip(n) for n in doc) if c]
        kept_checks += sum(len(n.get("sections", [])) for n, _ in walk(out))
        target = dst / p.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(out, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8")

    shutil.copyfile(src / "LICENSE", dst / "LICENSE")

    print(f"{len(files)} location files, {kept_checks} pin sections, {map_count} maps, {len(image_factor)} images, "
          f"shrunk: {', '.join(f'{img} by {k}' for img, k in image_factor.items() if k > 1) or 'none'}")


if __name__ == "__main__":
    main()
