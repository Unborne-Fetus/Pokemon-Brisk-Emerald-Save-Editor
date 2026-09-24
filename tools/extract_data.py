#!/usr/bin/env python3
"""
Brisk Dex data extractor for pokeemerald-expansion based projects
(built for Pokemon Brisk Emerald, but should work on any expansion fork
 that hasn't renamed the standard constants/data files).

Run this against your actual repo checkout -- it never talks to the network,
it just reads your source files and writes out:

  brisk-dex-data.json   -- species (name/types/abilities), moves, abilities, items
  brisk-dex-icons/      -- one <species_id>.png per species, copied from your
                           graphics/pokemon/<name>/icon.png source art

Usage:
    python3 extract_data.py /path/to/your/pokeemerald-expansion/checkout

Then in Brisk Dex: "Load species/move data" -> brisk-dex-data.json
                    "Load icon folder"       -> the brisk-dex-icons folder
"""
import json
import os
import re
import shutil
import sys

TYPE_NAMES = {
    "NONE": None, "NORMAL": "Normal", "FIGHTING": "Fighting", "FLYING": "Flying",
    "POISON": "Poison", "GROUND": "Ground", "ROCK": "Rock", "BUG": "Bug",
    "GHOST": "Ghost", "STEEL": "Steel", "MYSTERY": None, "FIRE": "Fire",
    "WATER": "Water", "GRASS": "Grass", "ELECTRIC": "Electric", "PSYCHIC": "Psychic",
    "ICE": "Ice", "DRAGON": "Dragon", "DARK": "Dark", "FAIRY": "Fairy",
}

def read(path):
    if not os.path.isfile(path):
        return None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def read_dir_concat(path):
    """Some expansion versions split a table across a folder of .h files."""
    if not os.path.isdir(path):
        return ""
    out = []
    for root, _, files in os.walk(path):
        for fn in sorted(files):
            if fn.endswith('.h') or fn.endswith('.inc'):
                out.append(read(os.path.join(root, fn)) or "")
    return "\n".join(out)

def find_source(repo, *candidates):
    """Try a list of relative paths (files or directories); return concatenated text."""
    combined = ""
    for rel in candidates:
        full = os.path.join(repo, rel)
        if os.path.isdir(full):
            combined += read_dir_concat(full)
        else:
            content = read(full)
            if content:
                combined += content
    return combined

def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', '', text)
    return text

def parse_defines(text, prefix):
    """#define SPECIES_BULBASAUR 1  ->  {'BULBASAUR': 1}"""
    out = {}
    pattern = re.compile(r'#define\s+' + re.escape(prefix) + r'([A-Za-z0-9_]+)\s+(\d+)\b')
    for m in pattern.finditer(text or ""):
        out[m.group(1)] = int(m.group(2))
    return out

def parse_enums(text, prefix):
    """
    enum { SPECIES_NONE, SPECIES_BULBASAUR, SPECIES_IVYSAUR = 50, ... };
    Sequentially numbers entries starting at 0 (or the prior explicit value + 1),
    restarting at each separate enum block (matching C semantics).
    """
    out = {}
    text = strip_comments(text or "")
    for enum_m in re.finditer(r'\benum\b[^{]*\{', text):
        start = enum_m.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == '{': depth += 1
            elif text[i] == '}': depth -= 1
            i += 1
        block = text[start:i-1]
        counter = 0
        for raw in block.split(','):
            token = raw.strip()
            if not token:
                continue
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(.+))?$', token)
            if not m:
                continue
            name, value_expr = m.group(1), m.group(2)
            if value_expr:
                ve = value_expr.strip()
                if re.match(r'^\d+$', ve):
                    counter = int(ve)
                elif re.match(r'^0[xX][0-9a-fA-F]+$', ve):
                    counter = int(ve, 16)
                # else: unparseable expression (macro/arithmetic) -- keep counting from
                # wherever we were; good enough for entries that follow it sequentially.
            if name.startswith(prefix):
                out[name[len(prefix):]] = counter
            counter += 1
    return out

def parse_constants(text, prefix):
    """Merge #define-style and enum-style constant declarations."""
    out = {}
    out.update(parse_enums(text, prefix))
    out.update(parse_defines(text, prefix))  # #define (if any) takes priority when both exist
    return out

def extract_blocks(text, prefix):
    """
    Find  [SPECIES_FOO] = { ... },   style table entries and return
    {'FOO': '<contents between the braces>'}. Handles nested braces.
    """
    out = {}
    marker = re.compile(r'\[\s*' + re.escape(prefix) + r'([A-Za-z0-9_]+)\s*\]\s*=\s*\{')
    for m in marker.finditer(text):
        name = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == '{': depth += 1
            elif text[i] == '}': depth -= 1
            i += 1
        out[name] = text[start:i-1]
    return out

def extract_string_field(block, *field_names):
    for field in field_names:
        m = re.search(re.escape(field) + r'\s*=\s*(?:_|COMPOUND_STRING)\(\s*"((?:[^"\\]|\\.)*)"\s*\)', block)
        if m:
            return m.group(1).replace('\\"', '"')
    return None

def extract_types(block):
    # accepts ".types = { TYPE_X, TYPE_Y }" or ".types = ANY_MACRO_NAME(TYPE_X, TYPE_Y)"
    m = re.search(r'\.types\s*=\s*(?:[A-Za-z_]\w*\s*\(|\{)\s*TYPE_([A-Za-z0-9_]+)\s*(?:,\s*TYPE_([A-Za-z0-9_]+))?', block)
    if not m:
        return []
    types = []
    for g in m.groups():
        if g and g in TYPE_NAMES and TYPE_NAMES[g]:
            types.append(TYPE_NAMES[g])
    return types

def extract_abilities(block):
    ids = []
    # form 1: ".abilities = { ABILITY_X, ... }"  or  ".abilities = ANY_MACRO(ABILITY_X, ...)"
    m = re.search(r'\.abilities\s*=\s*(?:[A-Za-z_]\w*\s*\(|\{)([^}\)]*)[\}\)]', block)
    if m:
        for part in m.group(1).split(','):
            am = re.match(r'\s*ABILITY_([A-Za-z0-9_]+)', part)
            if am and am.group(1) != 'NONE':
                ids.append(am.group(1))
        if ids:
            return ids
    # form 2: ".abilities[0] = ABILITY_X, .abilities[1] = ABILITY_Y, .abilities[2] = ABILITY_Z"
    for m in re.finditer(r'\.abilities\s*\[\s*\d+\s*\]\s*=\s*ABILITY_([A-Za-z0-9_]+)', block):
        if m.group(1) != 'NONE':
            ids.append(m.group(1))
    if ids:
        return ids
    # form 3: separate named fields, e.g. ".ability1 = ABILITY_X, .ability2 = ABILITY_Y, .abilityHidden = ABILITY_Z"
    for field in ('ability1', 'ability2', 'abilityHidden', 'ability3'):
        m = re.search(r'\.' + field + r'\s*=\s*ABILITY_([A-Za-z0-9_]+)', block)
        if m and m.group(1) != 'NONE':
            ids.append(m.group(1))
    return ids

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_data.py /path/to/repo")
        sys.exit(1)
    repo = sys.argv[1]
    if not os.path.isdir(repo):
        print("Not a directory:", repo)
        sys.exit(1)

    print("Reading constants...")
    species_const_text = find_source(repo, "include/constants/species.h")
    moves_const_text = find_source(repo, "include/constants/moves.h")
    abilities_const_text = find_source(repo, "include/constants/abilities.h")
    items_const_text = find_source(repo, "include/constants/items.h")

    species_ids = parse_constants(species_const_text, "SPECIES_")
    move_ids = parse_constants(moves_const_text, "MOVE_")
    ability_ids = parse_constants(abilities_const_text, "ABILITY_")
    item_ids = parse_constants(items_const_text, "ITEM_")

    print("  species constants:", len(species_ids))
    print("  move constants:", len(move_ids))
    print("  ability constants:", len(ability_ids))
    print("  item constants:", len(item_ids))

    print("Reading data tables (this can take a moment)...")
    species_text = find_source(repo, "src/data/pokemon/species_info.h", "src/data/pokemon/species_info")
    moves_text = find_source(repo, "src/data/moves_info.h", "src/data/moves_info")
    abilities_text = find_source(repo, "src/data/abilities.h", "src/data/abilities")
    items_text = find_source(repo, "src/data/items.h", "src/data/items")

    species_blocks = extract_blocks(species_text, "SPECIES_")
    move_blocks = extract_blocks(moves_text, "MOVE_")
    ability_blocks = extract_blocks(abilities_text, "ABILITY_")
    item_blocks = extract_blocks(items_text, "ITEM_")

    print("  species table entries found:", len(species_blocks))
    print("  move table entries found:", len(move_blocks))
    print("  ability table entries found:", len(ability_blocks))
    print("  item table entries found:", len(item_blocks))

    out_species = {}
    unresolved_species = 0
    with_types = 0
    with_abilities = 0
    first_block_sample = None
    for name, sid in species_ids.items():
        if sid == 0:
            continue
        block = species_blocks.get(name)
        if block is None:
            unresolved_species += 1
            continue
        if first_block_sample is None:
            first_block_sample = (name, block)
        display_name = extract_string_field(block, '.speciesName') or name.replace('_', ' ').title()
        types = extract_types(block)
        ability_names_raw = extract_abilities(block)
        ability_names = []
        for a in ability_names_raw:
            ab_block = ability_blocks.get(a)
            ab_name = extract_string_field(ab_block, '.name') if ab_block else None
            ability_names.append(ab_name or a.replace('_', ' ').title())
        if types: with_types += 1
        if ability_names: with_abilities += 1
        out_species[str(sid)] = {
            "name": display_name,
            "types": types,
            "abilities": ability_names,
            "constant": name
        }

    out_moves = {}
    for name, mid in move_ids.items():
        if mid == 0:
            continue
        block = move_blocks.get(name)
        move_name = extract_string_field(block, '.name') if block else None
        out_moves[str(mid)] = move_name or name.replace('_', ' ').title()

    out_abilities = {}
    for name, aid in ability_ids.items():
        if aid == 0:
            continue
        block = ability_blocks.get(name)
        ab_name = extract_string_field(block, '.name') if block else None
        out_abilities[str(aid)] = ab_name or name.replace('_', ' ').title()

    out_items = {}
    for name, iid in item_ids.items():
        if iid == 0:
            continue
        block = item_blocks.get(name)
        item_name = extract_string_field(block, '.name') if block else None
        out_items[str(iid)] = item_name or name.replace('_', ' ').title()

    data = {"species": out_species, "moves": out_moves, "abilities": out_abilities, "items": out_items}
    with open("brisk-dex-data.json", "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    print()
    print("Wrote brisk-dex-data.json:")
    print("  species:", len(out_species), "  (unresolved constants with no matching table entry:", unresolved_species, ")")
    print("  species with types resolved:", with_types, "/", len(out_species))
    print("  species with abilities resolved:", with_abilities, "/", len(out_species))
    print("  moves:", len(out_moves))
    print("  abilities:", len(out_abilities))
    print("  items:", len(out_items))

    if first_block_sample and (with_types < len(out_species) * 0.5 or with_abilities < len(out_species) * 0.5):
        with open("debug_sample_species_block.txt", "w", encoding='utf-8') as f:
            f.write("Species: " + first_block_sample[0] + "\n\n" + first_block_sample[1][:2000])
        print()
        print("  Types or abilities are resolving for less than half of species --")
        print("  wrote a raw sample block to debug_sample_species_block.txt.")
        print("  Paste its contents back and I can fix the pattern directly.")

    # ---- icons ----
    gfx_dir = os.path.join(repo, "graphics", "pokemon")
    icons_out = "brisk-dex-icons"
    if os.path.isdir(gfx_dir):
        os.makedirs(icons_out, exist_ok=True)
        found = 0
        by_folder = {}
        for entry in os.listdir(gfx_dir):
            by_folder[entry.lower().replace('_', '').replace('-', '')] = entry

        for name, sid in species_ids.items():
            if sid == 0 or str(sid) not in out_species:
                continue
            key = name.lower().replace('_', '')
            folder = by_folder.get(key)
            if not folder:
                continue
            icon_path = os.path.join(gfx_dir, folder, "icon.png")
            if os.path.isfile(icon_path):
                shutil.copyfile(icon_path, os.path.join(icons_out, str(sid) + ".png"))
                found += 1
        print()
        print("Copied", found, "icon PNGs into ./" + icons_out + "/ (named by species id)")
        if found == 0:
            print("  No icons matched automatically -- check that graphics/pokemon/<name>/icon.png exists")
            print("  and that <name> corresponds to the SPECIES_ constant (case-insensitive, underscores ignored).")
    else:
        print()
        print("No graphics/pokemon folder found at", gfx_dir, "-- skipping icon export.")

    print()
    print("Done. Load brisk-dex-data.json and the brisk-dex-icons folder into Brisk Dex.")

if __name__ == "__main__":
    main()
