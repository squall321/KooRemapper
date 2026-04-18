#!/usr/bin/env python3
"""
Build material_db.json from ALL .k files in materials/ + name_mapping.yaml.

Usage:
    python scripts/build_material_db.py [materials_dir]

Reads:
    materials/*.k              (all k-files, auto-classified by keyword)
    materials/name_mapping.yaml

Writes:
    materials/material_db.json

Files named test_* are excluded.
"""

import json
import sys
import re
from pathlib import Path
from datetime import date


# ═══════════════════════════════════════════════════════════════
# K-file parser: extract MAT blocks
# ═══════════════════════════════════════════════════════════════

def read_int_field(line, col, width=10):
    """Read integer from fixed-width field in raw (non-stripped) line."""
    if len(line) < col + width:
        s = line[col:] if col < len(line) else ""
    else:
        s = line[col:col + width]
    s = s.strip()
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        # Might be float like "7.9000E-09" — not an int field
        return 0


def read_float_field(line, col, width=10):
    """Read float from fixed-width field."""
    if len(line) < col + width:
        s = line[col:] if col < len(line) else ""
    else:
        s = line[col:col + width]
    s = s.strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_k_file(path):
    """Parse a .k file → list of (mid, mat_type, title, card_text, data_line)"""
    lines = Path(path).read_text(errors='replace').splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        t = raw.strip()

        # Detect *MAT_ keyword (not *MAT_ADD except *MAT_ADD_THERMAL_EXPANSION)
        is_mat = t.startswith('*MAT_') and not t.startswith('*MAT_ADD')
        is_cte = t.startswith('*MAT_ADD_THERMAL')
        is_thermal = t.startswith('*MAT_THERMAL')

        if is_mat or is_cte or is_thermal:
            keyword = t
            has_title = '_TITLE' in t.upper()
            card_lines = [raw.rstrip()]
            i += 1
            title = ""
            title_done = not has_title
            mid = None
            first_data = None

            while i < len(lines):
                raw2 = lines[i]
                t2 = raw2.strip()

                # Break on next keyword (* but not $ comment)
                if t2.startswith('*') and not t2.startswith('$'):
                    break

                card_lines.append(raw2.rstrip())

                # Skip $ comments
                if t2.startswith('$') or not t2:
                    i += 1
                    continue

                # Non-comment, non-empty line
                if not title_done:
                    title = t2
                    title_done = True
                elif mid is None:
                    # First data line → MID in col 0-9
                    mid = read_int_field(raw2, 0, 10)
                    first_data = raw2.rstrip()

                i += 1

            if mid is not None and mid > 0:
                # Normalize mat_type: remove _TITLE suffix
                mat_type = keyword.replace('_TITLE', '').replace('*', '')
                card_text = '\n'.join(card_lines)
                blocks.append({
                    'mid': mid,
                    'mat_type': mat_type,
                    'title': title,
                    'card_text': card_text,
                    'data_line': first_data or "",
                })
        else:
            i += 1

    return blocks


def parse_mechanical(mat_type, data_line):
    """Extract mechanical properties from first data line."""
    props = {}
    if not data_line:
        return props

    if mat_type in ('MAT_ELASTIC',):
        # MID RHO E PR DA DB K
        props['RHO'] = read_float_field(data_line, 10, 10)
        props['E'] = read_float_field(data_line, 20, 10)
        props['PR'] = read_float_field(data_line, 30, 10)

    elif mat_type in ('MAT_RIGID',):
        # MID RO E PR N COUPLE M ALIAS
        props['RHO'] = read_float_field(data_line, 10, 10)
        props['E'] = read_float_field(data_line, 20, 10)
        props['PR'] = read_float_field(data_line, 30, 10)

    elif mat_type in ('MAT_PIECEWISE_LINEAR_PLASTICITY',):
        # MID RO E PR SIGY ETAN FAIL TDEL
        props['RHO'] = read_float_field(data_line, 10, 10)
        props['E'] = read_float_field(data_line, 20, 10)
        props['PR'] = read_float_field(data_line, 30, 10)
        props['SIGY'] = read_float_field(data_line, 40, 10)

    elif 'MOONEY' in mat_type.upper():
        # MID RO PR A B V REF
        props['RHO'] = read_float_field(data_line, 10, 10)
        props['PR'] = read_float_field(data_line, 20, 10)
        a = read_float_field(data_line, 30, 10)
        b = read_float_field(data_line, 40, 10)
        props['A'] = a
        props['B'] = b
        props['E'] = 6.0 * (a + b)  # linear approximation

    elif mat_type in ('MAT_VISCOELASTIC',):
        # MID RO BULK G0 GI BETA
        props['RHO'] = read_float_field(data_line, 10, 10)
        props['BULK'] = read_float_field(data_line, 20, 10)
        props['G0'] = read_float_field(data_line, 30, 10)
        props['GI'] = read_float_field(data_line, 40, 10)
        props['BETA'] = read_float_field(data_line, 50, 10)
        # E from instantaneous shear modulus
        if props['G0'] > 0 and props['BULK'] > 0:
            props['E'] = 9.0 * props['BULK'] * props['G0'] / (3.0 * props['BULK'] + props['G0'])
            props['PR'] = (3.0 * props['BULK'] - 2.0 * props['G0']) / (6.0 * props['BULK'] + 2.0 * props['G0'])

    # SI reference values
    if 'RHO' in props and props['RHO'] > 0:
        props['rho_g_cm3'] = round(props['RHO'] * 1e9, 4)
    if 'E' in props and props['E'] > 0:
        props['E_GPa'] = round(props['E'] / 1000.0, 4)

    return props


def parse_thermal(data_line):
    """Extract thermal properties from MAT_THERMAL_ISOTROPIC data line."""
    # TMID TRO TGRLC TGMULT (card 1)
    # HC TC (card 2) — but in our k-file, card 2 is the next data line
    # We parse from the card text instead
    return {}


def parse_thermal_card(card_text):
    """Extract HC, TC from MAT_THERMAL_ISOTROPIC card text."""
    lines = card_text.split('\n')
    has_title = any('_TITLE' in l.upper() for l in lines if l.strip().startswith('*'))
    data_lines = [l for l in lines if l.strip() and not l.strip().startswith('$') and not l.strip().startswith('*')]
    # With _TITLE: data_lines = [title, TMID_line, HC_line]
    # Without:     data_lines = [TMID_line, HC_line]
    hc_idx = 2 if has_title else 1
    if len(data_lines) > hc_idx:
        hc = read_float_field(data_lines[hc_idx], 0, 10)
        tc = read_float_field(data_lines[hc_idx], 10, 10)
        return {
            'HC': hc,
            'TC': tc,
            'Cp_SI': round(hc / 1e6, 2) if hc > 0 else 0,
            'k_SI': round(tc, 4) if tc > 0 else 0,
        }
    return {}


def parse_cte_card(card_text):
    """Extract ALPHA from MAT_ADD_THERMAL_EXPANSION card text."""
    lines = card_text.split('\n')
    data_lines = [l for l in lines if l.strip() and not l.strip().startswith('$') and not l.strip().startswith('*')]
    if data_lines:
        # PID LCID MULT
        mult = read_float_field(data_lines[0], 20, 10)
        return {
            'ALPHA': mult,
            'ALPHA_ppm_K': round(mult * 1e6, 2) if mult > 0 else 0,
        }
    return {}


# ═══════════════════════════════════════════════════════════════
# Damping parser: *_damping.k files
#   Pattern per MID:
#     $$ --- Name (variant, MID XXXXXX) ---
#     $$ zeta=... alpha=... beta=...
#     *SET_PART_LIST_TITLE  →  SID = MID + 800000
#     *DAMPING_PART_MASS_SET  →  alpha (VALDMP)
#     *DAMPING_PART_STIFFNESS_SET  →  beta (COEF)
# ═══════════════════════════════════════════════════════════════

def parse_damping_file(path):
    """Parse a *_damping.k file → dict { MID: {zeta, alpha, beta, card_text} }"""
    text = Path(path).read_text(errors='replace')
    lines = text.splitlines()
    result = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detect $$ --- ... MID XXXXXX ---
        if line.startswith('$$') and 'MID' in line:
            m = re.search(r'MID\s+(\d+)', line)
            if m:
                mid = int(m.group(1))
                # Read zeta from line i+1, alpha/beta from line i+2
                zeta, alpha, beta = 0.0, 0.0, 0.0
                for offset in [1, 2]:
                    if i + offset < len(lines):
                        cl = lines[i + offset].strip()
                        if not cl.startswith('$$'):
                            break
                        zm = re.search(r'zeta=([\d.Ee+-]+)', cl)
                        am = re.search(r'alpha=([\d.Ee+-]+)', cl)
                        bm = re.search(r'beta=([\d.Ee+-]+)', cl)
                        if zm: zeta = float(zm.group(1))
                        if am: alpha = float(am.group(1))
                        if bm: beta = float(bm.group(1))

                # Collect the full card block (SET_PART_LIST + DAMPING_*)
                block_start = i
                i += 1
                # Skip to *SET_PART_LIST
                while i < len(lines) and not lines[i].strip().startswith('*SET_PART_LIST'):
                    i += 1
                card_start = i
                # Collect until next $$ --- or EOF
                while i < len(lines):
                    l = lines[i].strip()
                    if l.startswith('$$') and 'MID' in l:
                        break
                    if l.startswith('$ ===='):
                        break
                    i += 1
                card_text = '\n'.join(lines[card_start:i])

                # Fallback: extract alpha/beta from card text if not in comments
                if alpha == 0 or beta == 0:
                    for cl in card_text.split('\n'):
                        cl_s = cl.strip()
                        if cl_s.startswith('$') or cl_s.startswith('*') or not cl_s:
                            continue
                        # *DAMPING_PART_MASS_SET data: PSID LCID VALDMP(alpha)
                        valdmp = read_float_field(cl, 20, 10)
                        if valdmp > 0 and alpha == 0:
                            alpha = valdmp
                        # *DAMPING_PART_STIFFNESS_SET data: PSID COEF(beta)
                        coef = read_float_field(cl, 10, 10)
                        if coef > 0 and coef < 1.0 and beta == 0:
                            beta = coef

                if alpha > 0 or beta > 0:
                    result[mid] = {
                        'zeta': zeta,
                        'alpha': alpha,
                        'beta': beta,
                        'card_text': card_text.rstrip(),
                    }
                continue
        i += 1

    return result


# ═══════════════════════════════════════════════════════════════
# YAML parser (simple, no dependency)
# ═══════════════════════════════════════════════════════════════

def parse_name_mapping(path):
    """Parse name_mapping.yaml → dict {MID: {original, tag, note, category}}"""
    text = Path(path).read_text(errors='replace')
    result = {}
    current_cat = ""

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Category header (e.g. "metals:")
        if not line.startswith(' ') and stripped.endswith(':'):
            current_cat = stripped[:-1]
            continue

        # Key-value in list item1
        if '- MID:' in stripped:
            mid = int(stripped.split('MID:')[1].strip())
            result[mid] = {'category': current_cat}
        elif ':' in stripped and current_cat:
            key, val = stripped.split(':', 1)
            key = key.strip().lstrip('- ')
            val = val.strip().strip('"')
            if result:
                last_mid = max(result.keys())
                if key in ('original', 'tag', 'note'):
                    result[last_mid][key] = val

    return result


# ═══════════════════════════════════════════════════════════════
# Main: build material_db.json
# ═══════════════════════════════════════════════════════════════

def build_db(mat_dir):
    mat_dir = Path(mat_dir)

    # 1. Parse ALL .k files in materials/ (auto-classify by keyword)
    cards = {}      # MID → { mat_type → card_text }
    mech = {}       # MID → mechanical props (from primary type)
    titles = {}     # MID → title (from primary)
    primary = {}    # MID → primary mat_type
    thermal_cards = {}
    thermal_props = {}
    cte_cards_map = {}
    cte_props = {}
    dir_category = {}  # MID → category inferred from source directory (Materials/<Cat>/...)

    # (a) top-level curated k-files (legacy mat_*.k bundles)
    top_files = sorted(mat_dir.glob('*.k'))
    top_files = [f for f in top_files if not f.name.startswith('test_')]

    # (b) full library under materials/Materials/**/*.k
    lib_root = mat_dir / 'Materials'
    lib_files = []
    if lib_root.exists():
        lib_files = sorted(lib_root.rglob('*.k'))
        lib_files = [f for f in lib_files
                     if not f.name.startswith('test_')
                     and 'example' not in str(f).lower()]

    # (c) damping files: *_damping.k
    damping_files = sorted(lib_root.rglob('*_damping.k')) if lib_root.exists() else []
    # Also check top-level
    damping_files += sorted(mat_dir.glob('*_damping.k'))

    # Exclude damping files from structural parsing (they don't have *MAT_ cards)
    damping_names = {f.resolve() for f in damping_files}
    k_files = [f for f in (top_files + lib_files) if f.resolve() not in damping_names]
    print(f"  Found {len(top_files)} top-level + {len(lib_files)} library k-files"
          f" ({len(damping_files)} damping files)")

    # Parse damping files
    damping_data = {}  # MID → {zeta, alpha, beta, card_text}
    for df in damping_files:
        parsed = parse_damping_file(df)
        damping_data.update(parsed)
        display = str(df.relative_to(mat_dir)) if df.is_relative_to(mat_dir) else df.name
        if parsed:
            print(f"  {display}: {len(parsed)} damping entries")

    for fpath in k_files:
        blocks = parse_k_file(fpath)
        if not blocks:
            continue

        # Infer category from directory name when file lives under Materials/<Cat>/...
        src_cat = ''
        try:
            rel = fpath.relative_to(lib_root) if lib_root.exists() else None
        except ValueError:
            rel = None
        if rel is not None and len(rel.parts) >= 2:
            src_cat = rel.parts[0].lower()  # e.g. "Metal" → "metal"

        n_struct, n_thermal, n_cte = 0, 0, 0
        for b in blocks:
            mid = b['mid']
            mt = b['mat_type']

            if mt.startswith('MAT_THERMAL'):
                # *MAT_THERMAL_ISOTROPIC etc.
                thermal_cards[mid] = b['card_text']
                thermal_props[mid] = parse_thermal_card(b['card_text'])
                n_thermal += 1
            elif mt.startswith('MAT_ADD_THERMAL'):
                # *MAT_ADD_THERMAL_EXPANSION
                cte_cards_map[mid] = b['card_text']
                cte_props[mid] = parse_cte_card(b['card_text'])
                n_cte += 1
            else:
                # Structural MAT card — library wins over top-level on conflict
                if mid not in cards:
                    cards[mid] = {}
                cards[mid][mt] = b['card_text']

                if mid not in primary:
                    primary[mid] = mt
                    titles[mid] = b['title']
                    mech[mid] = parse_mechanical(mt, b['data_line'])
                elif mt == primary[mid]:
                    mech[mid] = parse_mechanical(mt, b['data_line'])
                    if b['title']:
                        titles[mid] = b['title']
                n_struct += 1

            if src_cat:
                dir_category[mid] = src_cat

        display_name = str(fpath.relative_to(mat_dir)) if fpath.is_relative_to(mat_dir) else fpath.name
        parts = []
        if n_struct:  parts.append(f"{n_struct} struct")
        if n_thermal: parts.append(f"{n_thermal} thermal")
        if n_cte:     parts.append(f"{n_cte} CTE")
        if parts:
            print(f"  {display_name}: {', '.join(parts)}")

    # 2. Parse name mapping
    mapping = {}
    yaml_path = mat_dir / 'name_mapping.yaml'
    if yaml_path.exists():
        mapping = parse_name_mapping(yaml_path)
        print(f"  name_mapping.yaml: {len(mapping)} entries")

    # 3. Build materials dict
    #    Only MIDs that have a structural card become first-class entries.
    #    Library thermal/CTE cards use shared TMID (e.g. 120501) that is a
    #    template for all structural variants sharing the suffix (100501,
    #    110501, …), so they must not become orphan materials in the DB.
    struct_mids = sorted(cards.keys())
    orphan_thermal = sorted(set(thermal_cards.keys()) - set(struct_mids))
    orphan_cte = sorted(set(cte_cards_map.keys()) - set(struct_mids))
    all_mids = struct_mids
    print(f"\n  Total unique structural MIDs: {len(all_mids)}")
    if orphan_thermal:
        print(f"  Shared thermal TMIDs (template cards, not first-class): {len(orphan_thermal)}")
    if orphan_cte:
        print(f"  Shared CTE template MIDs: {len(orphan_cte)}")

    materials = {}
    category_index = {}

    for mid in all_mids:
        meta = mapping.get(mid, {})
        mat_type = primary.get(mid, "MAT_ELASTIC")

        # Category: dir_category (library) > name_mapping.yaml > 'unknown'
        cat_map = {
            'metals': 'metal', 'polymers': 'polymer', 'glass': 'glass',
            'composites': 'composite', 'rubber': 'rubber', 'tapes': 'tape',
            'plastic': 'polymer',
        }
        if mid in dir_category:
            category = cat_map.get(dir_category[mid], dir_category[mid])
        else:
            raw_cat = meta.get('category', '')
            category = cat_map.get(raw_cat, raw_cat or 'unknown')

        # Thermal combined
        th = thermal_props.get(mid, {})
        ct = cte_props.get(mid, {})
        thermal = {**th, **ct}

        mat_type_id_map = {
            'MAT_ELASTIC': 1, 'MAT_RIGID': 20,
            'MAT_PIECEWISE_LINEAR_PLASTICITY': 24,
            'MAT_MOONEY-RIVLIN_RUBBER': 27, 'MAT_VISCOELASTIC': 6,
        }

        # Auto-generate missing variants
        card_set = dict(cards.get(mid, {}))
        m = mech.get(mid, {})
        name = meta.get('original', titles.get(mid, ''))

        # Any type with known E/RHO/PR → auto-generate MAT_RIGID
        if 'MAT_RIGID' not in card_set and m.get('E', 0) > 0:
            rho = m.get('RHO', 0)
            E = m.get('E', 0)
            pr = m.get('PR', 0)
            card_set['MAT_RIGID'] = (
                f"*MAT_RIGID_TITLE\n{name}\n"
                f"$      MID       RHO         E        PR"
                f"         N     COUPLE         M     ALIAS\n"
                f"{mid:10d}{rho:10.4E}{E:10.1f}{pr:10.4f}"
                f"{'':10s}{'':10s}{'':10s}{'':10s}\n"
                f"$      CMO      CON1      CON2\n"
                f"{'1.0':>10s}{'7':>10s}{'7':>10s}\n"
                f"$  A1  A2  A3  V1  V2  V3\n"
                f"{'':10s}{'':10s}{'':10s}{'':10s}{'':10s}{'':10s}"
            )

        # MAT_ELASTIC (metal) → auto-generate MAT_024
        if ('MAT_ELASTIC' in card_set and category == 'metal'
                and 'MAT_PIECEWISE_LINEAR_PLASTICITY' not in card_set):
            rho = m.get('RHO', 0)
            E = m.get('E', 0)
            pr = m.get('PR', 0)
            sigy = m.get('SIGY', E * 0.002)  # estimate 0.2% yield
            card_set['MAT_PIECEWISE_LINEAR_PLASTICITY'] = (
                f"*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE\n{name}\n"
                f"$      MID       RHO         E        PR"
                f"      SIGY      ETAN      FAIL      TDEL\n"
                f"{mid:10d}{rho:10.4E}{E:10.1f}{pr:10.4f}"
                f"{sigy:10.1f}{'':10s}{'':10s}{'':10s}"
            )

        # MAT_VISCOELASTIC → instantaneous (G0) and longterm (GI) elastic variants
        if mat_type == 'MAT_VISCOELASTIC' and m.get('BULK', 0) > 0:
            rho = m.get('RHO', 0)
            bulk = m.get('BULK', 0)
            for suffix, G_key in [('instantaneous', 'G0'), ('longterm', 'GI')]:
                G = m.get(G_key, 0)
                if G > 0:
                    E_v = 9.0 * bulk * G / (3.0 * bulk + G)
                    pr_v = (3.0 * bulk - 2.0 * G) / (6.0 * bulk + 2.0 * G)
                    vname = f'MAT_ELASTIC_{suffix}'
                    card_set[vname] = (
                        f"*MAT_ELASTIC_TITLE\n{name}_{suffix}\n"
                        f"$      MID       RHO         E        PR"
                        f"        DA        DB         K\n"
                        f"{mid:10d}{rho:10.4E}{E_v:10.1f}{pr_v:10.4f}"
                        f"{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}"
                    )

        # Any type without MAT_ELASTIC → auto-generate from E/PR
        if 'MAT_ELASTIC' not in card_set and m.get('E', 0) > 0:
            rho = m.get('RHO', 0)
            E = m.get('E', 0)
            pr = m.get('PR', 0)
            card_set['MAT_ELASTIC'] = (
                f"*MAT_ELASTIC_TITLE\n{name}\n"
                f"$      MID       RHO         E        PR"
                f"        DA        DB         K\n"
                f"{mid:10d}{rho:10.4E}{E:10.1f}{pr:10.4f}"
                f"{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}"
            )

        # Damping data
        damp = damping_data.get(mid, {})
        damping_info = {}
        damp_card = ''
        if damp:
            damping_info = {
                'zeta': damp['zeta'],
                'alpha': damp['alpha'],
                'beta': damp['beta'],
            }
            damp_card = damp.get('card_text', '')

        entry = {
            'name': name,
            'tag': meta.get('tag', ''),
            'description': meta.get('note', ''),
            'category': category,
            'mat_type': mat_type,
            'mat_type_id': mat_type_id_map.get(mat_type, 0),
            'mechanical': m,
            'thermal': thermal,
            'damping': damping_info,
            'cards_structural': card_set,
            'card_thermal': thermal_cards.get(mid, ''),
            'card_thermal_expansion': cte_cards_map.get(mid, ''),
            'card_damping': damp_card,
        }
        materials[str(mid)] = entry

        # Category index
        if category not in category_index:
            category_index[category] = []
        category_index[category].append(mid)

    # 4. Build final DB
    db = {
        '_meta': {
            'description': 'LS-DYNA Material Database - Mechanical + Thermal',
            'unit_system': 't / mm / s / K  → MPa',
            'unit_notes': {
                'density_RHO': 't/mm³  (multiply g/cm³ × 1e-9)',
                'youngs_modulus_E': 'MPa',
                'poissons_ratio_PR': 'dimensionless',
                'yield_stress_SIGY': 'MPa',
                'specific_heat_HC': 'mJ/(t·K)  (multiply J/(kg·K) × 1e6)',
                'thermal_conductivity_TC': 'mW/(mm·K)  (numerically same as W/(m·K))',
                'specific_heat_Cp_SI': 'J/(kg·K)',
                'thermal_conductivity_k_SI': 'W/(m·K)',
            },
            'card_note': 'card_structural contains the EXACT original LS-DYNA keyword text',
            'created': str(date.today()),
            'generator': 'scripts/build_material_db.py',
        },
        'materials': materials,
        'category_index': category_index,
    }

    # 5. Write
    out_path = mat_dir / 'material_db.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

    print(f"\n  Written: {out_path}")
    print(f"  Materials: {len(materials)}")
    for cat, mids in sorted(category_index.items()):
        print(f"    {cat}: {len(mids)} ({mids})")


if __name__ == '__main__':
    mat_dir = sys.argv[1] if len(sys.argv) > 1 else 'materials'
    print(f"Building material_db.json from: {mat_dir}/")
    build_db(mat_dir)
