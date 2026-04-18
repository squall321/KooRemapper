#!/usr/bin/env python3
"""
Glass Material Library Generator for LS-DYNA
===============================================
Produces glass_cover.k, glass_sapphire.k, glass_thermal.k
based on Corning Gorilla Glass PI Sheets, AGC Dragontrail,
Goodfellow Sapphire, and Kyocera sapphire data.

Each material has 2 mechanical variants:
  1. Linear elastic (MAT_001)                    MID 1010xx
  2. Elastic + Erosion (MAT_001 + MAT_ADD_EROSION) MID 1110xx
Plus thermal (MAT_THERMAL_ISOTROPIC + ADD_THERMAL_EXPANSION, TMID 1310xx)

Unit system: mm, s, ton -> MPa, N, ton/mm^3

Data sources:
  [1] Corning Gorilla Glass 5/6/Victus PI Sheets
  [2] AGC Dragontrail TDS
  [3] Goodfellow Sapphire single crystal (AZoM 1721)
  [4] Kyocera Sapphire TDS
  [5] ASM Handbook Vol 4 (Ceramics and Glasses)
  [6] MatWeb soda-lime glass properties
"""

import json
from pathlib import Path


# ============================================================
# Glass Material Database
# ============================================================
# Each material:
#   name, lin_mid, erode_mid, tmid,
#   rho_gcc, E_GPa, nu,
#   sigma_strength_MPa (principal stress erosion threshold),
#   fracture_toughness (K1C) MPa*sqrt(m),
#   cte_ppmK, tc_WmK, cp_JkgK,
#   Tg_C (for cover glass),
#   desc, ref

COVER_GLASS_DB = [
    {
        "name": "SodaLime_Standard",
        "lin_mid": 101001, "erode_mid": 111001, "tmid": 131001,
        "rho_gcc": 2.50, "E_GPa": 72.0, "nu": 0.22,
        "sigma_strength": 45.0,  # MPa, tensile (pristine)
        "K1C": 0.75,
        "cte_ppmK": 9.0, "tc_WmK": 1.05, "cp_JkgK": 840.0,
        "Tg_C": 570,
        "desc": "Soda-lime glass (standard window/mirror)",
        "ref": "MatWeb soda-lime, ASM Vol 4",
    },
    {
        "name": "Aluminosilicate_Dragontrail",
        "lin_mid": 101002, "erode_mid": 111002, "tmid": 131002,
        "rho_gcc": 2.48, "E_GPa": 74.0, "nu": 0.22,
        "sigma_strength": 500.0,  # Strengthened surface CS
        "K1C": 0.75,
        "cte_ppmK": 8.5, "tc_WmK": 1.00, "cp_JkgK": 830.0,
        "Tg_C": 620,
        "desc": "AGC Dragontrail aluminosilicate (chemically strengthened)",
        "ref": "AGC Dragontrail TDS",
    },
    {
        "name": "GorillaGlass_3",
        "lin_mid": 101003, "erode_mid": 111003, "tmid": 131003,
        "rho_gcc": 2.45, "E_GPa": 71.5, "nu": 0.22,
        "sigma_strength": 680.0,  # CS layer
        "K1C": 0.70,
        "cte_ppmK": 7.8, "tc_WmK": 0.96, "cp_JkgK": 880.0,
        "Tg_C": 610,
        "desc": "Corning Gorilla Glass 3 (2013), NDR (Native Damage Resistance)",
        "ref": "Corning Gorilla Glass 3 PI Sheet",
    },
    {
        "name": "GorillaGlass_5",
        "lin_mid": 101004, "erode_mid": 111004, "tmid": 131004,
        "rho_gcc": 2.43, "E_GPa": 77.0, "nu": 0.21,
        "sigma_strength": 850.0,  # CS ≥850 MPa per Corning PI
        "K1C": 0.69,
        "cte_ppmK": 7.7, "tc_WmK": 0.95, "cp_JkgK": 880.0,
        "Tg_C": 609,
        "desc": "Corning Gorilla Glass 5 (2016), drop performance",
        "ref": "Corning Gorilla Glass 5 PI Sheet: E=77 GPa, nu=0.21, rho=2.43, K1C=0.69",
    },
    {
        "name": "GorillaGlass_6",
        "lin_mid": 101005, "erode_mid": 111005, "tmid": 131005,
        "rho_gcc": 2.40, "E_GPa": 77.0, "nu": 0.21,
        "sigma_strength": 850.0,
        "K1C": 0.70,
        "cte_ppmK": 7.6, "tc_WmK": 0.95, "cp_JkgK": 880.0,
        "Tg_C": 650,
        "desc": "Corning Gorilla Glass 6 (2018), improved repeated drop",
        "ref": "Corning Gorilla Glass 6 PI Sheet: E=77 GPa, nu=0.21, rho=2.40, K1C=0.70",
    },
    {
        "name": "GorillaGlass_Victus",
        "lin_mid": 101006, "erode_mid": 111006, "tmid": 131006,
        "rho_gcc": 2.44, "E_GPa": 78.0, "nu": 0.21,
        "sigma_strength": 900.0,  # Claimed >900 MPa CS
        "K1C": 0.72,
        "cte_ppmK": 7.5, "tc_WmK": 0.95, "cp_JkgK": 880.0,
        "Tg_C": 665,
        "desc": "Corning Gorilla Glass Victus (2020), flagship drop + scratch",
        "ref": "Corning Gorilla Glass Victus PI Sheet",
    },
]

SAPPHIRE_DB = [
    {
        "name": "Sapphire_Cplane",
        "lin_mid": 101011, "erode_mid": 111011, "tmid": 131011,
        "rho_gcc": 3.97, "E_GPa": 345.0, "nu": 0.29,
        "sigma_strength": 700.0,  # MOR typical
        "K1C": 2.2,
        "cte_ppmK": 5.3, "tc_WmK": 35.1, "cp_JkgK": 750.0,
        "Tg_C": 2040,  # melting point, sapphire has no Tg
        "desc": "Sapphire single crystal C-plane (0001), camera window, watch face",
        "ref": "Goodfellow Al2O3 99.9% (AZoM 1721), Kyocera sapphire TDS",
    },
    {
        "name": "Sapphire_Aplane",
        "lin_mid": 101012, "erode_mid": 111012, "tmid": 131012,
        "rho_gcc": 3.97, "E_GPa": 370.0, "nu": 0.27,
        "sigma_strength": 800.0,
        "K1C": 2.2,
        "cte_ppmK": 5.8, "tc_WmK": 35.1, "cp_JkgK": 750.0,
        "Tg_C": 2040,
        "desc": "Sapphire single crystal A-plane (1120), higher strength window",
        "ref": "Goodfellow Al2O3, Kyocera",
    },
]

ALL_GLASS = {
    "Cover": COVER_GLASS_DB,
    "Sapphire": SAPPHIRE_DB,
}


# ============================================================
# Unit conversions
# ============================================================
def rho_to_tonmm3(rho_gcc):
    return rho_gcc * 1e-9

def E_to_MPa(E_GPa):
    return E_GPa * 1000.0

def cte_to_perK(cte_ppmK):
    return cte_ppmK * 1e-6

def cp_to_mm2s2K(cp_JkgK):
    return cp_JkgK * 1e6


# ============================================================
# K-file writers
# ============================================================

def header(title):
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append(f"$ {title}")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> MPa, N, ton/mm^3")
    lines.append("$")
    lines.append("$ 2 mechanical variants per material:")
    lines.append("$   1. MAT_001 Linear Elastic       1010xx — preview")
    lines.append("$   2. MAT_001 + MAT_ADD_EROSION    1110xx — drop analysis ★")
    lines.append("$")
    lines.append("$ Erosion criterion: principal stress > sigma_strength")
    lines.append("$   sigma_strength = chemically strengthened CS (Gorilla: 680~900 MPa)")
    lines.append("$")
    lines.append("$ Thermal properties in glass_thermal.k")
    lines.append("$")
    lines.append("$ !! ========================================================================")
    lines.append("$ !!  DATABASE CONVENTION")
    lines.append("$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION / *MAT_ADD_EROSION holds")
    lines.append("$ !!  the MATERIAL ID (MID), NOT an actual Part ID.")
    lines.append("$ !!  External tool must replace with real PIDs before running LS-DYNA.")
    lines.append("$ !! ========================================================================")
    return lines


def write_mat001_linear(m):
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Linear Elastic (MID {m['lin_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Source: {m['ref']}")
    lines.append(f"$$ E={m['E_GPa']} GPa, nu={m['nu']}, rho={m['rho_gcc']} g/cc")
    lines.append(f"$$ K1C={m['K1C']} MPa*sqrt(m), sigma_strength={m['sigma_strength']} MPa")
    lines.append("*MAT_ELASTIC_TITLE")
    lines.append(f"{m['name']} Linear")
    lines.append("$      MID        RO         E        PR        DA        DB")
    lines.append(
        f"{m['lin_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E_to_MPa(m['E_GPa']):10.1f}"
        f"{m['nu']:10.4f}"
        f"       0.0       0.0"
    )
    return lines


def write_mat001_with_erosion(m):
    """MAT_001 + MAT_ADD_EROSION with principal stress criterion."""
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Elastic+Erosion (MID {m['erode_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Principal stress erosion: sigma_p_max > {m['sigma_strength']} MPa -> delete")
    lines.append("*MAT_ELASTIC_TITLE")
    lines.append(f"{m['name']} Elastic+Erode")
    lines.append("$      MID        RO         E        PR        DA        DB")
    lines.append(
        f"{m['erode_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E_to_MPa(m['E_GPa']):10.1f}"
        f"{m['nu']:10.4f}"
        f"       0.0       0.0"
    )
    lines.append("$")
    lines.append("$ Erosion: principal stress + minimum timestep criteria")
    lines.append(f"$$ [DB] PID slot holds MID={m['erode_mid']} (replace with actual PART IDs)")
    lines.append("*MAT_ADD_EROSION")
    lines.append("$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS")
    lines.append(
        f"{m['erode_mid']:10d}"
        f"       0.0"
        f"       0.0"
        f"       0.0"
        f"       0.0"
        f"       0.0"
        f"{1:10d}"
        f"{1:10d}"
    )
    lines.append("$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM")
    lines.append(
        f"       0.0"
        f"{m['sigma_strength']:10.2f}"
        f"       0.0"
        f"       0.0"
        f"       0.0"
        f"       0.0"
        f"       0.0"
        f"       0.0"
    )
    return lines


def write_mat_thermal_isotropic(m):
    lines = []
    tc_out = m["tc_WmK"]
    cp_out = cp_to_mm2s2K(m["cp_JkgK"])
    rho_out = rho_to_tonmm3(m["rho_gcc"])
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Thermal (TMID {m['tmid']}) ---")
    lines.append(f"$$ TC={m['tc_WmK']} W/m/K, Cp={m['cp_JkgK']} J/kg/K, CTE={m['cte_ppmK']} ppm/K")
    lines.append("*MAT_THERMAL_ISOTROPIC_TITLE")
    lines.append(f"{m['name']} Thermal")
    lines.append("$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT")
    lines.append(
        f"{m['tmid']:10d}"
        f"{rho_out:10.3e}"
        f"{0:10d}"
        f"{1.0:10.4f}"
        f"{0.0:10.4f}"
        f"{0.0:10.4f}"
    )
    lines.append("$       HC         TC")
    lines.append(f"{cp_out:10.3e}{tc_out:10.3e}")
    return lines


def write_thermal_expansion(m):
    cte = cte_to_perK(m["cte_ppmK"])
    mids_labels = [
        (m["lin_mid"], "Linear"),
        (m["erode_mid"], "Elastic+Erode"),
    ]
    lines = []
    lines.append(f"$$ CTE={m['cte_ppmK']} ppm/K, applied to both MIDs of {m['name']}")
    for mid, label in mids_labels:
        lines.append(f"$$ [DB] PID slot holds MID={mid} ({label}, external tool must replace with actual PART IDs)")
        lines.append("*MAT_ADD_THERMAL_EXPANSION")
        lines.append("$      PID      LCID      MULT")
        lines.append(f"{mid:10d}{0:10d}{cte:10.3e}")
    return lines


# ============================================================
# File writers
# ============================================================

def write_mechanical_kfile(materials, filepath, group_name):
    title = f"GLASS {group_name} — Mechanical (MAT_001 + MAT_ADD_EROSION)"
    lines = header(title)
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append(
        "$   lin     erode   tmid    Name                         E(GPa) rho    sigma(MPa) K1C"
    )
    lines.append("$   " + "-" * 88)
    for m in materials:
        lines.append(
            f"$   {m['lin_mid']}  {m['erode_mid']}  {m['tmid']}  "
            f"{m['name']:28s} {m['E_GPa']:6.1f}  {m['rho_gcc']:4.2f}  "
            f"{m['sigma_strength']:9.0f}  {m['K1C']:4.2f}"
        )
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 1. LINEAR ELASTIC (MAT_001)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat001_linear(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 2. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat001_with_erosion(m))
    lines.append("$")
    lines.append("*END")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_thermal_kfile(filepath):
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append("$ GLASS THERMAL PROPERTIES")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> temperature K")
    lines.append("$")
    lines.append("$ !! ========================================================================")
    lines.append("$ !!  DATABASE CONVENTION")
    lines.append("$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID (MID),")
    lines.append("$ !!  NOT an actual Part ID. Applied to both mechanical variants.")
    lines.append("$ !! ========================================================================")
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append("$   TMID    Name                        CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)")
    lines.append("$   " + "-" * 75)
    for group, materials in ALL_GLASS.items():
        for m in materials:
            lines.append(
                f"$   {m['tmid']}  {m['name']:28s} "
                f"{m['cte_ppmK']:9.2f}  {m['tc_WmK']:8.2f}  {m['cp_JkgK']:9.1f}"
            )
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")

    for group, materials in ALL_GLASS.items():
        lines.append("$")
        lines.append("$ " + "=" * 72)
        lines.append(f"$ {group} THERMAL")
        lines.append("$ " + "=" * 72)
        for m in materials:
            lines.extend(write_mat_thermal_isotropic(m))
            lines.append("$")
            lines.extend(write_thermal_expansion(m))

    lines.append("$")
    lines.append("*END")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_db_json(filepath):
    db = {}
    for group, materials in ALL_GLASS.items():
        db[group] = [dict(m) for m in materials]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ============================================================
# Main
# ============================================================

def main():
    script_dir = Path(__file__).parent.resolve()

    cover_path = script_dir / "glass_cover.k"
    sapphire_path = script_dir / "glass_sapphire.k"
    thermal_path = script_dir / "glass_thermal.k"
    db_path = script_dir / "glass_materials_db.json"

    write_mechanical_kfile(COVER_GLASS_DB, cover_path, "COVER GLASS")
    write_mechanical_kfile(SAPPHIRE_DB, sapphire_path, "SAPPHIRE")
    write_thermal_kfile(thermal_path)
    write_db_json(db_path)

    total = sum(len(v) for v in ALL_GLASS.values())
    print("=" * 65)
    print("  Glass Material Library Generated")
    print("=" * 65)
    for group, materials in ALL_GLASS.items():
        print(f"  {group:12s}: {len(materials):2d} materials")
    print(f"  TOTAL: {total} materials x 2 variants = {total*2} mechanical cards + {total} thermal")
    print()
    print("  Output files:")
    for p in [cover_path, sapphire_path, thermal_path, db_path]:
        sz = p.stat().st_size if p.exists() else 0
        print(f"    {p.name:35s}  {sz:7d} bytes")

    print()
    print("=" * 80)
    print(f"  {'lin':>6s} {'erode':>6s} {'tmid':>6s}  {'Name':28s} {'E(GPa)':>7s} {'sigma':>7s}")
    print("  " + "-" * 78)
    for group, materials in ALL_GLASS.items():
        for m in materials:
            print(
                f"  {m['lin_mid']:6d} {m['erode_mid']:6d} {m['tmid']:6d}  "
                f"{m['name']:28s} {m['E_GPa']:7.1f} {m['sigma_strength']:7.0f}"
            )


if __name__ == "__main__":
    main()
