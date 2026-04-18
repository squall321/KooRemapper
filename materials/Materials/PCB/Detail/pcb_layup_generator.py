#!/usr/bin/env python3
"""
PCB Layup to MAT_086 Equivalent Material Generator
====================================================
Converts a PCB layup definition (PPG + Cu layers with Cu ratio)
into a single LS-DYNA *MAT_ORTHOTROPIC_VISCOELASTIC (MAT_086) card.

Methodology:
  - Rule of Mixture (Voigt) for in-plane properties (XY)
  - Reuss averaging for through-thickness properties (Z)
  - PPG-dominated viscoelastic behavior (Cu is elastic)
  - Thermal expansion: VF-weighted average

Inputs:
  - PPG material library K-file (pcb_prepreg_materials.k)
  - Cu material library K-file (cu.k)
  - Layup definition YAML/JSON file

Output:
  - LS-DYNA K-file with *MAT_ORTHOTROPIC_VISCOELASTIC card
"""

import re
import os
import sys
import json
import argparse
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ============================================================
# K-file Parsers
# ============================================================

def parse_ppg_library(filepath):
    """
    Parse pcb_prepreg_materials.k and extract PPG properties.

    Returns dict: { name: {mid, ro_tonmm3, bulk_mpa, g0_mpa, gi_mpa,
                           beta, cte_xy_per_k, cte_z_per_k, tg_c, e_gpa,
                           nu, rho_gcc, desc} }

    Parsing logic:
      - Find each *MAT_VISCOELASTIC_TITLE block
      - Name = line after the keyword
      - Data row = first numeric line after the header (10 digit fields)
      - Additional metadata from $$ comments (E, nu, rho, CTE, Tg)
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    ppgs = {}
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip() == "*MAT_VISCOELASTIC_TITLE":
            # Walk backwards to collect $$ metadata
            meta = {}
            j = i - 1
            desc_lines = []
            while j >= 0 and (lines[j].startswith("$$") or lines[j].startswith("$")):
                l = lines[j]
                # Extract E, nu, rho
                m = re.search(r"E\s*=\s*([\d.]+)\s*GPa.*nu\s*=\s*([\d.]+).*rho\s*=\s*([\d.]+)", l)
                if m:
                    meta['E_gpa'] = float(m.group(1))
                    meta['nu'] = float(m.group(2))
                    meta['rho_gcc_or_kgm3'] = float(m.group(3))
                # CTE
                m = re.search(r"xy\s*=\s*([\d.]+)\s*ppm/K.*z\s*=\s*([\d.]+)\s*ppm/K", l)
                if m:
                    meta['cte_xy_ppm'] = float(m.group(1))
                    meta['cte_z_ppm'] = float(m.group(2))
                # Tg
                m = re.search(r"Tg\s*=\s*(\d+)\s*C", l)
                if m:
                    meta['tg_c'] = int(m.group(1))
                j -= 1

            # Title line
            i += 1
            if i >= len(lines):
                break
            title = lines[i].strip()

            # Find data row (skip $ comment lines)
            i += 1
            while i < len(lines) and lines[i].strip().startswith('$'):
                i += 1
            if i >= len(lines):
                break
            data_line = lines[i]

            # Parse fixed-width: MID(10) RO(10) BULK(10) G0(10) GI(10) BETA(10)
            try:
                mid = int(data_line[0:10].strip())
                ro = float(data_line[10:20].strip())
                bulk = float(data_line[20:30].strip())
                g0 = float(data_line[30:40].strip())
                gi = float(data_line[40:50].strip())
                beta = float(data_line[50:60].strip())
            except (ValueError, IndexError) as e:
                print(f"Warning: Failed to parse PPG data at line {i}: {data_line.strip()}")
                i += 1
                continue

            # Normalize rho if in kg/m^3
            rho_gcc = meta.get('rho_gcc_or_kgm3', ro * 1e9)
            if rho_gcc > 100:  # value is in kg/m^3
                rho_gcc = rho_gcc / 1000.0

            ppgs[title] = {
                'mid': mid,
                'ro_tonmm3': ro,
                'bulk_mpa': bulk,
                'g0_mpa': g0,
                'gi_mpa': gi,
                'beta': beta,
                'cte_xy_per_k': meta.get('cte_xy_ppm', 14) * 1e-6,
                'cte_z_per_k': meta.get('cte_z_ppm', 50) * 1e-6,
                'tg_c': meta.get('tg_c', 180),
                'e_gpa': meta.get('E_gpa', 22.0),
                'nu': meta.get('nu', 0.19),
                'rho_gcc': rho_gcc,
            }
        i += 1

    return ppgs


def parse_cu_library(filepath):
    """
    Parse cu.k and extract Cu properties.
    Returns dict: { name: {mid, E_mpa, nu, rho_tonmm3, sigy, etan, cte_per_k} }
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    cus = {}
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip() == "*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE":
            # Title
            i += 1
            if i >= len(lines):
                break
            title = lines[i].strip()

            # Find data row (Card 1)
            i += 1
            while i < len(lines) and lines[i].strip().startswith('$'):
                i += 1
            if i >= len(lines):
                break

            data_line = lines[i]
            try:
                mid = int(data_line[0:10].strip())
                ro = float(data_line[10:20].strip())
                e_mpa = float(data_line[20:30].strip())
                pr = float(data_line[30:40].strip())
                sigy = float(data_line[40:50].strip())
                etan = float(data_line[50:60].strip())
            except (ValueError, IndexError):
                i += 1
                continue

            cus[title] = {
                'mid': mid,
                'ro_tonmm3': ro,
                'e_mpa': e_mpa,
                'nu': pr,
                'sigy_mpa': sigy,
                'etan_mpa': etan,
                'rho_gcc': ro * 1e9,
                'cte_per_k': 16.8e-6,  # Cu standard
            }
        i += 1

    return cus


# ============================================================
# Equivalent Laminate Computation
# ============================================================

def compute_equivalent_mat086(layup, ppg_db, cu_db):
    """
    Given a layup definition, compute MAT_086 equivalent properties.

    layup = {
        "material_name": str,
        "material_id": int,
        "layers": [
            {"type": "ppg", "material": name, "thickness_um": float},
            {"type": "cu",  "material": name, "thickness_um": float, "cu_ratio": float},
            ...
        ]
    }

    Returns dict with all MAT_086 fields.
    """
    layers = layup["layers"]

    # Pre-compute each layer's effective contribution
    # For Cu layer with cu_ratio < 1: treat the non-Cu area as "resin"
    # (approximate: use the nearest PPG or a default resin value)
    # For simplicity here, Cu-only area uses Cu properties; gaps are filled by PPG.
    # We'll use a mixing approach: E_layer_inplane = η*E_cu + (1-η)*E_ppg_local

    # Find a "representative PPG" for Cu gap filling
    # Use the first PPG in the layup as the gap resin
    gap_resin = None
    for L in layers:
        if L["type"] == "ppg":
            gap_resin = ppg_db[L["material"]]
            break
    if gap_resin is None:
        raise ValueError("Layup must contain at least one PPG layer for gap resin reference")

    # Build per-layer effective properties
    layer_props = []
    for L in layers:
        t_um = L["thickness_um"]
        t_mm = t_um * 1e-3

        if L["type"] == "ppg":
            p = ppg_db[L["material"]]
            E_xy = p["e_gpa"] * 1000.0  # MPa
            # PCB PPG: assume Ez ~ 0.4*Exy (glass fiber dominated in-plane,
            # resin dominated through-thickness)
            E_z = E_xy * 0.40
            nu_xy = p["nu"]
            nu_z = 0.30
            G_xy = E_xy / (2 * (1 + nu_xy))
            G_z = E_z / (2 * (1 + nu_z))
            rho = p["rho_gcc"] * 1e-9  # ton/mm^3
            cte_xy = p["cte_xy_per_k"]
            cte_z = p["cte_z_per_k"]
            g0 = p["g0_mpa"]
            gi = p["gi_mpa"]
            beta = p["beta"]
            bulk = p["bulk_mpa"]
            is_visco = True
        else:  # cu
            c = cu_db[L["material"]]
            eta = L.get("cu_ratio", 1.0)
            # Effective layer = η*Cu + (1-η)*resin
            # Voigt in-plane (parallel)
            E_cu = c["e_mpa"]
            E_resin_xy = gap_resin["e_gpa"] * 1000.0
            E_resin_z = E_resin_xy * 0.40
            rho_cu = c["ro_tonmm3"]
            rho_resin = gap_resin["rho_gcc"] * 1e-9

            E_xy = eta * E_cu + (1 - eta) * E_resin_xy
            # Reuss through-thickness (series): 1/E_z = η/E_cu + (1-η)/E_resin_z
            E_z = 1.0 / (eta / E_cu + (1 - eta) / E_resin_z)
            nu_xy = 0.34 * eta + gap_resin["nu"] * (1 - eta)
            nu_z = 0.34 * eta + 0.30 * (1 - eta)
            G_xy = E_xy / (2 * (1 + nu_xy))
            G_z = E_z / (2 * (1 + nu_z))
            rho = eta * rho_cu + (1 - eta) * rho_resin

            # CTE: VF-weighted (Cu constrains resin in plane)
            cte_cu = c["cte_per_k"]
            cte_xy = eta * cte_cu + (1 - eta) * gap_resin["cte_xy_per_k"]
            cte_z = eta * cte_cu + (1 - eta) * gap_resin["cte_z_per_k"]

            # Viscoelastic contribution is diluted by Cu fraction
            # Pure Cu is elastic -> G0 = GI; but gap resin has full visco
            g0_resin = gap_resin["g0_mpa"]
            gi_resin = gap_resin["gi_mpa"]
            G_cu_eff = E_cu / (2 * (1 + 0.34))
            # Weighted: η*Cu_elastic + (1-η)*resin_visco
            g0 = eta * G_cu_eff + (1 - eta) * g0_resin
            gi = eta * G_cu_eff + (1 - eta) * gi_resin
            beta = gap_resin["beta"]
            bulk = eta * (E_cu / (3 * (1 - 2*0.34))) + (1 - eta) * gap_resin["bulk_mpa"]
            is_visco = (eta < 1.0)

        layer_props.append({
            't_mm': t_mm,
            'E_xy': E_xy, 'E_z': E_z,
            'nu_xy': nu_xy, 'nu_z': nu_z,
            'G_xy': G_xy, 'G_z': G_z,
            'rho': rho,
            'cte_xy': cte_xy, 'cte_z': cte_z,
            'g0': g0, 'gi': gi, 'beta': beta, 'bulk': bulk,
            'type': L["type"], 'eta': L.get("cu_ratio", 1.0) if L["type"] == "cu" else 1.0,
            'material': L["material"],
        })

    # Total thickness
    t_total = sum(lp['t_mm'] for lp in layer_props)

    # In-plane (Voigt): thickness-weighted modulus average
    E_xy_eq = sum(lp['t_mm'] * lp['E_xy'] for lp in layer_props) / t_total
    # Through-thickness (Reuss): compliance average
    inv_E_z_eq = sum(lp['t_mm'] / lp['E_z'] for lp in layer_props) / t_total
    E_z_eq = 1.0 / inv_E_z_eq

    # Poisson ratio (in-plane thickness average)
    nu_xy_eq = sum(lp['t_mm'] * lp['nu_xy'] for lp in layer_props) / t_total
    nu_z_eq = sum(lp['t_mm'] * lp['nu_z'] for lp in layer_props) / t_total

    # Shear moduli
    # G_xy_eq: thickness average (Voigt)
    G_xy_eq = sum(lp['t_mm'] * lp['G_xy'] for lp in layer_props) / t_total
    # G_z_eq: Reuss (series)
    inv_G_z_eq = sum(lp['t_mm'] / lp['G_z'] for lp in layer_props) / t_total
    G_z_eq = 1.0 / inv_G_z_eq

    # Density: volume average
    rho_eq = sum(lp['t_mm'] * lp['rho'] for lp in layer_props) / t_total

    # CTE: in-plane Schapery-like (E-weighted), z-direction thickness-weighted
    num_xy = sum(lp['t_mm'] * lp['E_xy'] * lp['cte_xy'] for lp in layer_props)
    den_xy = sum(lp['t_mm'] * lp['E_xy'] for lp in layer_props)
    cte_xy_eq = num_xy / den_xy
    cte_z_eq = sum(lp['t_mm'] * lp['cte_z'] for lp in layer_props) / t_total

    # Bulk modulus: Voigt average (dominant for compressive response)
    bulk_eq = sum(lp['t_mm'] * lp['bulk'] for lp in layer_props) / t_total

    # Viscoelastic: PPG-dominated
    # Thickness-weighted average of G0, GI, BETA using VISCOELASTIC CONTRIBUTION
    # (PPG fully contributes; Cu area partially diluted)
    ppg_thickness = sum(lp['t_mm'] for lp in layer_props if lp['type'] == 'ppg')
    cu_thickness_resin = sum(lp['t_mm'] * (1 - lp['eta']) for lp in layer_props if lp['type'] == 'cu')
    visco_mass = ppg_thickness + cu_thickness_resin

    if visco_mass > 0:
        g0_eq = sum(lp['t_mm'] * lp['g0'] for lp in layer_props) / t_total
        gi_eq = sum(lp['t_mm'] * lp['gi'] for lp in layer_props) / t_total
        # BETA: use PPG weighted average (if multiple PPG, weighted mean)
        beta_num = sum(lp['t_mm'] * lp['beta'] for lp in layer_props if lp['type'] == 'ppg')
        beta_den = sum(lp['t_mm'] for lp in layer_props if lp['type'] == 'ppg')
        beta_eq = beta_num / beta_den if beta_den > 0 else 500.0
    else:
        g0_eq = G_xy_eq  # no visco, degenerate
        gi_eq = G_xy_eq
        beta_eq = 500.0

    return {
        'material_name': layup['material_name'],
        'material_id': layup['material_id'],
        'description': layup.get('description', ''),
        't_total_mm': t_total,
        't_total_um': t_total * 1000,

        'E_a': E_xy_eq, 'E_b': E_xy_eq, 'E_c': E_z_eq,
        'nu_ba': nu_xy_eq, 'nu_ca': nu_z_eq, 'nu_cb': nu_z_eq,
        'G_ab': G_xy_eq, 'G_bc': G_z_eq, 'G_ca': G_z_eq,
        'rho': rho_eq,

        'bulk': bulk_eq,
        'g0': g0_eq, 'gi': gi_eq, 'beta': beta_eq,

        'cte_a': cte_xy_eq, 'cte_b': cte_xy_eq, 'cte_c': cte_z_eq,

        'layer_props': layer_props,
    }


# ============================================================
# MAT_086 Writer
# ============================================================

def write_mat086_kfile(eq, outpath, layup):
    """Write the MAT_086 card + MAT_ADD_THERMAL_EXPANSION to a K-file."""

    lines = []
    lines.append("$ " + "="*72)
    lines.append(f"$ PCB EQUIVALENT MATERIAL (MAT_086) — {eq['material_name']}")
    lines.append("$ " + "="*72)
    lines.append("$ Unit: mm, s, ton -> MPa, N, ton/mm^3")
    lines.append(f"$ Generated from layup: {layup.get('description', 'N/A')}")
    lines.append(f"$ Total thickness: {eq['t_total_um']:.1f} um ({eq['t_total_mm']:.4f} mm)")
    lines.append("$")
    lines.append("$ Layup composition (top -> bottom):")
    for idx, (L, lp) in enumerate(zip(layup['layers'], eq['layer_props'])):
        if L['type'] == 'cu':
            lines.append(f"$   L{idx+1}: {L['material']:35s} Cu {L['thickness_um']:6.1f} um  (eta={L['cu_ratio']:.2f})")
        else:
            lines.append(f"$   L{idx+1}: {L['material']:35s} PPG {L['thickness_um']:6.1f} um")
    lines.append("$")
    lines.append("$ Equivalent orthotropic properties:")
    lines.append(f"$   E_a = E_b (in-plane) = {eq['E_a']:10.1f} MPa = {eq['E_a']/1000:6.2f} GPa")
    lines.append(f"$   E_c     (through)   = {eq['E_c']:10.1f} MPa = {eq['E_c']/1000:6.2f} GPa")
    lines.append(f"$   nu_ba (in-plane)    = {eq['nu_ba']:.4f}")
    lines.append(f"$   nu_ca (through)     = {eq['nu_ca']:.4f}")
    lines.append(f"$   G_ab (in-plane)     = {eq['G_ab']:10.1f} MPa")
    lines.append(f"$   G_bc = G_ca         = {eq['G_bc']:10.1f} MPa")
    lines.append(f"$   rho                 = {eq['rho']:.4e} ton/mm^3 ({eq['rho']*1e9:.3f} g/cc)")
    lines.append(f"$   BULK                = {eq['bulk']:10.1f} MPa")
    lines.append(f"$   Visco G0            = {eq['g0']:10.1f} MPa")
    lines.append(f"$   Visco GI            = {eq['gi']:10.1f} MPa")
    lines.append(f"$   Visco BETA          = {eq['beta']:.1f} /s  (tau={1000.0/eq['beta']:.2f} ms)")
    lines.append(f"$   CTE_a = CTE_b       = {eq['cte_a']*1e6:6.2f} ppm/K")
    lines.append(f"$   CTE_c               = {eq['cte_c']*1e6:6.2f} ppm/K")
    lines.append("$")
    lines.append("$ Calculation methodology:")
    lines.append("$   In-plane (a,b): Rule of Mixture (Voigt) — thickness-weighted E")
    lines.append("$   Through (c):    Reuss (series) — compliance average")
    lines.append("$   CTE in-plane:   E-weighted Schapery-like average")
    lines.append("$   CTE through:    Thickness-weighted free expansion")
    lines.append("$   Cu gap filling: Non-Cu area replaced by adjacent PPG resin")
    lines.append("$ " + "="*72)
    lines.append("*KEYWORD")
    lines.append("$")

    # MAT_086 card - note: MAT_086 uses K (bulk), not the orthotropic components
    # Card format per LS-DYNA R16 manual:
    #   Card 1: MID RO EA EB (EC is derived) PRBA GAB GBC GCA (or K,G0,GI,BETA depending on variant)
    # Actually MAT_086 (ORTHOTROPIC_VISCOELASTIC) has this structure:
    #   Card 1: MID RO EA EB (empty) PRBA (empty) (empty) (empty)
    #   Card 2: GAB GBC GCA AOPT (empty) (empty) (empty) (empty)
    #   Card 3: BULK G0 GINF BETA AOPT coordinate
    #
    # Simpler and more standard: use Option 1 card layout:
    #   Card 1: MID RO EA EB (nu) GAB GBC GCA AOPT
    #   Card 2: BULK G0 GINF BETA

    mid = eq['material_id']
    lines.append(f"$$ {eq['material_name']}")
    if eq.get('description'):
        lines.append(f"$$ {eq['description']}")
    lines.append(f"*MAT_ORTHOTROPIC_VISCOELASTIC_TITLE")
    lines.append(eq['material_name'])
    lines.append(f"$      MID        RO        EA        EB      PRBA       GAB       GBC       GCA")
    lines.append(f"{mid:10d}{eq['rho']:10.3e}{eq['E_a']:10.1f}{eq['E_b']:10.1f}{eq['nu_ba']:10.4f}{eq['G_ab']:10.1f}{eq['G_bc']:10.1f}{eq['G_ca']:10.1f}")
    lines.append(f"$     AOPT         K        G0      GINF      BETA     REF")
    lines.append(f"{'0.0':>10s}{eq['bulk']:10.1f}{eq['g0']:10.1f}{eq['gi']:10.1f}{eq['beta']:10.1f}{'0.0':>10s}")
    lines.append(f"$       XP        YP        ZP        A1        A2        A3")
    lines.append(f"{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}")
    lines.append(f"$       V1        V2        V3        D1        D2        D3      BETA")
    lines.append(f"{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}")
    lines.append("$")
    lines.append("$ Orthotropic thermal expansion (separate x/y/z)")
    lines.append(f"$$ [DB] PID slot holds MID={mid} (external tool must replace with actual PART IDs)")
    lines.append("*MAT_ADD_THERMAL_EXPANSION")
    lines.append("$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ")
    lines.append(f"{mid:10d}{'0':>10s}{eq['cte_a']:10.3e}{'0':>10s}{eq['cte_b']:10.3e}{'0':>10s}{eq['cte_c']:10.3e}")
    lines.append("$")
    lines.append("*END")

    with open(outpath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")

    return outpath


# ============================================================
# MAT_002 (Orthotropic Elastic) Writer for Solid Elements
# ============================================================

def compute_rayleigh_from_visco(g0, gi, beta, target_zeta=None, omega_ref_hz=None):
    """
    Convert MAT_086 viscoelastic parameters to equivalent Rayleigh damping
    coefficients (alpha for mass-prop, beta_damp for stiffness-prop).

    Two modes:
      (1) Material-based (default):
          Uses the material's characteristic angular frequency omega_ref = BETA,
          and peak loss factor tan(delta) from the single Maxwell model.
          Produces only the intrinsic PPG damping (~0.5% typically).

      (2) Target zeta override (engineering):
          target_zeta given (e.g., 0.02 = 2%)
          omega_ref_hz given in Hz (e.g., 1000 Hz for drop impact)
          Produces Rayleigh coefficients that deliver target_zeta at omega_ref.

    Rayleigh: zeta(omega) = 0.5 * (alpha/omega + beta_d*omega)
    Split equally between mass and stiffness at omega_ref:
        alpha = zeta * omega_ref
        beta_d = zeta / omega_ref
    (each contributes zeta/2 at omega = omega_ref, sum = zeta)

    Returns dict:
        alpha_mass, beta_stiff, tan_delta, zeta, omega_ref, source
    """
    # Always compute material-based values for reporting
    if g0 > 0 and gi > 0 and beta > 0:
        tan_d_mat = (g0 - gi) / (2.0 * (g0 * gi) ** 0.5)
    else:
        tan_d_mat = 0.0
    zeta_mat = tan_d_mat / 2.0

    if target_zeta is not None and omega_ref_hz is not None:
        # Engineering override
        zeta = float(target_zeta)
        omega_ref = 2.0 * 3.141592653589793 * float(omega_ref_hz)
        source = f"target_zeta={zeta:.4f} @ {omega_ref_hz:.0f} Hz (engineering)"
    else:
        # Material-based
        zeta = zeta_mat
        omega_ref = beta if beta > 0 else 1000.0
        source = f"material tan(d)={tan_d_mat:.4f} @ BETA={beta:.1f} rad/s"

    alpha_mass = zeta * omega_ref
    beta_stiff = zeta / omega_ref if omega_ref > 0 else 0.0

    return {
        'alpha_mass': alpha_mass,
        'beta_stiff': beta_stiff,
        'tan_delta': tan_d_mat,
        'zeta': zeta,
        'zeta_material': zeta_mat,
        'omega_ref': omega_ref,
        'omega_ref_hz': omega_ref / (2.0 * 3.141592653589793),
        'source': source,
    }


def write_mat002_solid_kfile(eq, outpath, layup):
    """
    Write the SOLID version K-file with:
      - *MAT_ORTHOTROPIC_ELASTIC (MAT_002)
      - *SET_PART_LIST (placeholder for collecting PCB parts)
      - *DAMPING_PART_MASS_SET (mass-proportional Rayleigh)
      - *DAMPING_PART_STIFFNESS_SET (stiffness-proportional Rayleigh)
      - *MAT_ADD_THERMAL_EXPANSION

    Part IDs are NOT assigned here. A SET_PART_LIST is provided with a
    placeholder for the user to add actual PIDs after loading in a full model.

    Rayleigh damping source:
      - If layup has 'rayleigh_damping' block with target_zeta + omega_ref_hz,
        use engineering target override.
      - Otherwise fall back to material-based (PPG tan(delta)).
    """
    mid = eq['material_id']
    # Auto-assigned IDs derived from the material ID
    psid = mid + 800000     # part set ID (e.g., 200008 -> 1000008)

    # Check for Rayleigh damping override in layup definition
    rd = layup.get('rayleigh_damping', {}) or {}
    target_zeta = rd.get('target_zeta')
    omega_ref_hz = rd.get('omega_ref_hz')

    damp = compute_rayleigh_from_visco(
        eq['g0'], eq['gi'], eq['beta'],
        target_zeta=target_zeta,
        omega_ref_hz=omega_ref_hz,
    )
    alpha = damp['alpha_mass']
    beta_damp = damp['beta_stiff']
    tan_d = damp['tan_delta']
    zeta = damp['zeta']

    lines = []
    lines.append("$ " + "=" * 72)
    lines.append(f"$ PCB EQUIVALENT MATERIAL (MAT_002 + Rayleigh) — {eq['material_name']}")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> MPa, N, ton/mm^3")
    lines.append("$ Element type: SOLID (MAT_002 only supports elastic)")
    lines.append("$")
    lines.append(f"$ Generated from layup: {layup.get('description', 'N/A')}")
    lines.append(f"$ Total thickness: {eq['t_total_um']:.1f} um ({eq['t_total_mm']:.4f} mm)")
    lines.append("$")
    lines.append("$ Layup composition (top -> bottom):")
    for idx, L in enumerate(layup['layers']):
        if L['type'] == 'cu':
            lines.append(f"$   L{idx+1}: {L['material']:35s} Cu {L['thickness_um']:6.1f} um  (eta={L['cu_ratio']:.2f})")
        else:
            lines.append(f"$   L{idx+1}: {L['material']:35s} PPG {L['thickness_um']:6.1f} um")
    lines.append("$")
    lines.append("$ Equivalent orthotropic elastic properties:")
    lines.append(f"$   E_a = E_b (in-plane) = {eq['E_a']:10.1f} MPa = {eq['E_a']/1000:6.2f} GPa")
    lines.append(f"$   E_c     (through)    = {eq['E_c']:10.1f} MPa = {eq['E_c']/1000:6.2f} GPa")
    lines.append(f"$   nu_ba (in-plane)     = {eq['nu_ba']:.4f}")
    lines.append(f"$   nu_ca (through)      = {eq['nu_ca']:.4f}")
    lines.append(f"$   G_ab (in-plane)      = {eq['G_ab']:10.1f} MPa")
    lines.append(f"$   G_bc = G_ca          = {eq['G_bc']:10.1f} MPa")
    lines.append(f"$   rho                  = {eq['rho']:.4e} ton/mm^3 ({eq['rho']*1e9:.3f} g/cc)")
    lines.append(f"$   CTE_a = CTE_b        = {eq['cte_a']*1e6:6.2f} ppm/K")
    lines.append(f"$   CTE_c                = {eq['cte_c']*1e6:6.2f} ppm/K")
    lines.append("$")
    lines.append("$ Rayleigh damping configuration:")
    lines.append(f"$   Source               : {damp['source']}")
    lines.append(f"$   Material tan(delta)  = {tan_d:.4f}  (PPG intrinsic, reference)")
    lines.append(f"$   Material zeta        = {damp['zeta_material']:.4f}  (reference)")
    lines.append(f"$   Applied zeta         = {zeta:.4f}  ({zeta*100:.2f}%)")
    lines.append(f"$   Reference omega      = {damp['omega_ref']:.1f} rad/s ({damp['omega_ref_hz']:.1f} Hz)")
    lines.append(f"$   alpha_mass (VALDMP)  = {alpha:.4e} /s")
    lines.append(f"$   beta_stiffness       = {beta_damp:.4e} s")
    if target_zeta is None:
        lines.append("$   NOTE: Using material-based damping (intrinsic PPG loss only).")
        lines.append("$         To use engineering target zeta, add to your YAML:")
        lines.append("$           rayleigh_damping:")
        lines.append("$             target_zeta: 0.02      # 2%")
        lines.append("$             omega_ref_hz: 1000     # 1 kHz")
    lines.append("$")
    lines.append("$ =================================================================")
    lines.append("$ USAGE:")
    lines.append("$   1. INCLUDE this file in your main model")
    lines.append(f"$   2. Create or assign your PCB PART(s) with MID={mid}")
    lines.append(f"$   3. Add those PIDs to *SET_PART_LIST SID={psid} below")
    lines.append("$   4. Damping is applied automatically to all parts in the set")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")
    lines.append("$")
    lines.append("$ ----- MATERIAL (MAT_002 Orthotropic Elastic) -----")
    lines.append(f"$$ {eq['material_name']} — Solid element version")
    if eq.get('description'):
        lines.append(f"$$ {eq['description']}")
    lines.append("*MAT_ORTHOTROPIC_ELASTIC_TITLE")
    lines.append(eq['material_name'] + "_SOLID")
    # Card 1: MID RO EA EB EC PRBA PRCA PRCB
    lines.append("$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB")
    lines.append(
        f"{mid:10d}{eq['rho']:10.3e}{eq['E_a']:10.1f}{eq['E_b']:10.1f}{eq['E_c']:10.1f}"
        f"{eq['nu_ba']:10.4f}{eq['nu_ca']:10.4f}{eq['nu_cb']:10.4f}"
    )
    # Card 2: GAB GBC GCA AOPT G SIGF
    lines.append("$      GAB       GBC       GCA      AOPT         G      SIGF")
    lines.append(
        f"{eq['G_ab']:10.1f}{eq['G_bc']:10.1f}{eq['G_ca']:10.1f}"
        f"{'2.0':>10s}{'0.0':>10s}{'0.0':>10s}"
    )
    # Card 3: XP YP ZP A1 A2 A3 MACF IHIS (AOPT=2 uses vectors A and D)
    lines.append("$       XP        YP        ZP        A1        A2        A3      MACF")
    lines.append(
        f"{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}"
        f"{'1.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0':>10s}"
    )
    # Card 4: V1 V2 V3 D1 D2 D3 BETA_angle
    lines.append("$       V1        V2        V3        D1        D2        D3      BETA")
    lines.append(
        f"{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}"
        f"{'0.0':>10s}{'1.0':>10s}{'0.0':>10s}{'0.0':>10s}"
    )
    lines.append("$")
    lines.append("$ ----- ORTHOTROPIC THERMAL EXPANSION -----")
    lines.append("*MAT_ADD_THERMAL_EXPANSION")
    lines.append("$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ")
    lines.append(
        f"{mid:10d}{'0':>10s}{eq['cte_a']:10.3e}"
        f"{'0':>10s}{eq['cte_b']:10.3e}{'0':>10s}{eq['cte_c']:10.3e}"
    )
    lines.append("$")
    lines.append("$ ----- PART SET (populate with actual PCB PIDs) -----")
    lines.append(f"$$ SID={psid}: collects all solid PCB parts using this material")
    lines.append("$$ Edit the list below to include your actual PART IDs.")
    lines.append("*SET_PART_LIST_TITLE")
    lines.append(f"{eq['material_name']}_parts")
    lines.append("$      SID       DA1       DA2       DA3       DA4")
    lines.append(f"{psid:10d}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}")
    lines.append("$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8")
    lines.append("$ TODO: replace the zero below with your actual PCB PART IDs")
    lines.append(f"{'0':>10s}{'0':>10s}{'0':>10s}{'0':>10s}{'0':>10s}{'0':>10s}{'0':>10s}{'0':>10s}")
    lines.append("$")
    lines.append("$ ----- RAYLEIGH DAMPING (mass + stiffness proportional) -----")
    lines.append(f"$$ Damping source: {damp['source']}")
    lines.append(f"$$ Applied zeta={zeta:.4f} ({zeta*100:.2f}%) at f_ref={damp['omega_ref_hz']:.0f} Hz")
    lines.append(f"$$ Material ref: tan(d)={tan_d:.4f}, zeta_mat={damp['zeta_material']:.4f}")
    lines.append("*DAMPING_PART_MASS_SET")
    lines.append("$     PSID      LCID    VALDMP       STX       STY       STZ       SRX       SRY")
    lines.append(
        f"{psid:10d}{'0':>10s}{alpha:10.3e}"
        f"{'1.0':>10s}{'1.0':>10s}{'1.0':>10s}{'1.0':>10s}{'1.0':>10s}"
    )
    lines.append("$")
    lines.append("*DAMPING_PART_STIFFNESS_SET")
    lines.append("$     PSID      COEF")
    lines.append(f"{psid:10d}{beta_damp:10.3e}")
    lines.append("$")
    lines.append("*END")

    with open(outpath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")

    damp_out = dict(damp)
    damp_out['psid'] = psid
    return outpath, damp_out


# ============================================================
# Main CLI
# ============================================================

def load_layup(filepath):
    """Load layup definition from YAML or JSON."""
    ext = Path(filepath).suffix.lower()
    with open(filepath, 'r', encoding='utf-8') as f:
        if ext in ['.yaml', '.yml']:
            if not HAS_YAML:
                raise RuntimeError("PyYAML not installed; use JSON or pip install pyyaml")
            return yaml.safe_load(f)
        else:
            return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Generate MAT_086 equivalent PCB material from layup definition"
    )
    parser.add_argument("layup", help="Layup definition file (YAML or JSON)")
    parser.add_argument("--ppg-lib", default="../pcb_prepreg_materials.k",
                        help="PPG material library K-file")
    parser.add_argument("--cu-lib", default="cu.k",
                        help="Cu material library K-file")
    parser.add_argument("-o", "--output", default=None,
                        help="Output K-file path (default: {material_name}.k)")
    args = parser.parse_args()

    # Resolve paths relative to the script or layup file
    layup_path = Path(args.layup).resolve()
    script_dir = Path(__file__).parent.resolve()

    ppg_lib = Path(args.ppg_lib)
    if not ppg_lib.is_absolute():
        ppg_lib = (script_dir / ppg_lib).resolve()
    cu_lib = Path(args.cu_lib)
    if not cu_lib.is_absolute():
        cu_lib = (script_dir / cu_lib).resolve()

    print(f"Loading PPG library: {ppg_lib}")
    ppg_db = parse_ppg_library(str(ppg_lib))
    print(f"  Found {len(ppg_db)} PPG materials")

    print(f"Loading Cu library: {cu_lib}")
    cu_db = parse_cu_library(str(cu_lib))
    print(f"  Found {len(cu_db)} Cu materials")

    print(f"Loading layup: {layup_path}")
    layup = load_layup(str(layup_path))

    # Validate materials exist
    for L in layup['layers']:
        db = ppg_db if L['type'] == 'ppg' else cu_db
        if L['material'] not in db:
            print(f"\nERROR: Material '{L['material']}' not found in {L['type']} library")
            print(f"Available {L['type']} materials:")
            for name in sorted(db.keys()):
                print(f"  - {name}")
            sys.exit(1)

    print(f"\nComputing equivalent properties...")
    eq = compute_equivalent_mat086(layup, ppg_db, cu_db)

    # Output paths: two versions (shell for MAT_086, solid for MAT_002 + damping)
    if args.output:
        base = Path(args.output)
        base_stem = base.parent / base.stem
    else:
        base_stem = layup_path.parent / layup['material_name']

    outpath_shell = f"{base_stem}_shell.k"
    outpath_solid = f"{base_stem}_solid.k"

    write_mat086_kfile(eq, outpath_shell, layup)
    _, damp_info = write_mat002_solid_kfile(eq, outpath_solid, layup)

    # Summary
    print(f"\n{'='*65}")
    print(f"  PCB Equivalent — {eq['material_name']}")
    print(f"{'='*65}")
    print(f"  Total thickness:  {eq['t_total_um']:.1f} um")
    print(f"  E_a = E_b (xy):   {eq['E_a']/1000:.2f} GPa")
    print(f"  E_c (z):          {eq['E_c']/1000:.2f} GPa  (ratio xy/z = {eq['E_a']/eq['E_c']:.2f})")
    print(f"  G_ab (xy shear):  {eq['G_ab']/1000:.2f} GPa")
    print(f"  G_z (out-of-plane):{eq['G_bc']/1000:.2f} GPa")
    print(f"  rho:              {eq['rho']*1e9:.3f} g/cc")
    print(f"  BULK:             {eq['bulk']/1000:.2f} GPa")
    print(f"  G0 / GI:          {eq['g0']:.1f} / {eq['gi']:.1f} MPa  (ratio {eq['g0']/eq['gi']:.2f}x)")
    print(f"  BETA:             {eq['beta']:.1f} /s  (tau={1000.0/eq['beta']:.2f} ms)")
    print(f"  CTE_a = CTE_b:    {eq['cte_a']*1e6:.2f} ppm/K")
    print(f"  CTE_c:            {eq['cte_c']*1e6:.2f} ppm/K  (ratio z/xy = {eq['cte_c']/eq['cte_a']:.2f})")
    print()
    print(f"  Rayleigh damping (for solid version):")
    print(f"    source          = {damp_info['source']}")
    print(f"    tan(delta) mat  = {damp_info['tan_delta']:.4f}")
    print(f"    zeta applied    = {damp_info['zeta']:.4f}  ({damp_info['zeta']*100:.2f}%)")
    print(f"    omega_ref       = {damp_info['omega_ref']:.1f} rad/s ({damp_info['omega_ref_hz']:.0f} Hz)")
    print(f"    alpha (VALDMP)  = {damp_info['alpha_mass']:.3e} /s")
    print(f"    beta (stiff)    = {damp_info['beta_stiff']:.3e} s")
    print(f"    Part set SID    = {damp_info['psid']}")
    print()
    print(f"  Output SHELL (MAT_086):           {outpath_shell}")
    print(f"  Output SOLID (MAT_002 + damping): {outpath_solid}")


if __name__ == "__main__":
    main()
