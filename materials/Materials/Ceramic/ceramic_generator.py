#!/usr/bin/env python3
"""
Ceramic Material Library Generator for LS-DYNA
=================================================
Produces ceramic_structural.k, ceramic_piezo.k, ceramic_lcp.k,
ceramic_thermal.k based on CoorsTek, Kyocera, APC, Ticona TDS.

Variants per material:
  1. MAT_001 Linear                     MID 1010xx
  2. MAT_001 + MAT_ADD_EROSION           MID 1110xx (for structural/piezo)
Plus thermal (MAT_THERMAL_ISOTROPIC, TMID 1310xx)

Unit system: mm, s, ton -> MPa, N, ton/mm^3

Data sources:
  [1] CoorsTek Al2O3/AlN TDS
  [2] Kyocera Fine Ceramics Al2O3, AlN, Si3N4, ZrO2 TDS
  [3] APC International PZT-4, PZT-5A TDS
  [4] Ticona/Celanese Vectra LCP A950, E130i TDS
  [5] ASM Engineered Materials Handbook Vol 4
"""

import json
from pathlib import Path


# ============================================================
# Ceramic Material Database
# ============================================================

STRUCTURAL_DB = [
    {
        "name": "Al2O3_96pct",
        "lin_mid": 101021, "erode_mid": 111021, "tmid": 131021,
        "rho_gcc": 3.72, "E_GPa": 300.0, "nu": 0.21,
        "sigma_flex": 300.0,  # flexural strength MPa
        "K1C": 3.5,
        "cte_ppmK": 7.1, "tc_WmK": 24.0, "cp_JkgK": 880.0,
        "desc": "Alumina 96% purity, standard substrate (HTCC), housings",
        "ref": "CoorsTek AD-96, Kyocera A-476",
    },
    {
        "name": "Al2O3_99p5pct",
        "lin_mid": 101022, "erode_mid": 111022, "tmid": 131022,
        "rho_gcc": 3.89, "E_GPa": 370.0, "nu": 0.22,
        "sigma_flex": 400.0,
        "K1C": 4.0,
        "cte_ppmK": 8.0, "tc_WmK": 32.0, "cp_JkgK": 880.0,
        "desc": "Alumina 99.5% high-purity, high-performance substrate",
        "ref": "CoorsTek AD-995, Kyocera A-479",
    },
    {
        "name": "AlN_HighK",
        "lin_mid": 101023, "erode_mid": 111023, "tmid": 131023,
        "rho_gcc": 3.26, "E_GPa": 320.0, "nu": 0.23,
        "sigma_flex": 320.0,
        "K1C": 3.0,
        "cte_ppmK": 4.5, "tc_WmK": 170.0, "cp_JkgK": 740.0,
        "desc": "Aluminum Nitride, high thermal conductivity (IGBT, LED)",
        "ref": "CoorsTek AlN-170, Kyocera Shapal-M (AlN)",
    },
    {
        "name": "ZrO2_YTZP",
        "lin_mid": 101024, "erode_mid": 111024, "tmid": 131024,
        "rho_gcc": 6.05, "E_GPa": 210.0, "nu": 0.31,
        "sigma_flex": 1200.0,  # highest flex strength among ceramics
        "K1C": 10.0,
        "cte_ppmK": 10.3, "tc_WmK": 2.0, "cp_JkgK": 420.0,
        "desc": "Yttria-stabilized Zirconia (Y-TZP), premium back cover, dental",
        "ref": "CoorsTek YZP, Kyocera Z-001, Tosoh TZ-3Y",
    },
    {
        "name": "Si3N4",
        "lin_mid": 101025, "erode_mid": 111025, "tmid": 131025,
        "rho_gcc": 3.20, "E_GPa": 310.0, "nu": 0.27,
        "sigma_flex": 800.0,
        "K1C": 7.0,
        "cte_ppmK": 3.2, "tc_WmK": 25.0, "cp_JkgK": 700.0,
        "desc": "Silicon Nitride, high reliability bearings, IC substrates",
        "ref": "CoorsTek SN, Kyocera SN-240, Ceradyne Silicon Nitride",
    },
    {
        "name": "SiC",
        "lin_mid": 101026, "erode_mid": 111026, "tmid": 131026,
        "rho_gcc": 3.10, "E_GPa": 410.0, "nu": 0.14,
        "sigma_flex": 390.0,
        "K1C": 3.5,
        "cte_ppmK": 4.0, "tc_WmK": 120.0, "cp_JkgK": 750.0,
        "desc": "Silicon Carbide, high performance semiconductor substrate",
        "ref": "CoorsTek SC-30, Saint-Gobain Hexoloy SA",
    },
]

PIEZO_DB = [
    {
        "name": "PZT_5A_soft",
        "lin_mid": 101031, "erode_mid": 111031, "tmid": 131031,
        "rho_gcc": 7.75, "E_GPa": 61.0, "nu": 0.31,
        "sigma_flex": 80.0,  # typical PZT flexural strength
        "K1C": 1.5,
        "cte_ppmK": 2.0, "tc_WmK": 1.8, "cp_JkgK": 420.0,
        "d33_pCN": 374,  # piezoelectric constant
        "desc": "PZT-5A soft piezo, sensor, hydrophone, guitar pickup",
        "ref": "APC 850, Morgan PZT-5A, CTS 3203HD",
    },
    {
        "name": "PZT_4_hard",
        "lin_mid": 101032, "erode_mid": 111032, "tmid": 131032,
        "rho_gcc": 7.50, "E_GPa": 64.0, "nu": 0.31,
        "sigma_flex": 100.0,
        "K1C": 1.5,
        "cte_ppmK": 2.0, "tc_WmK": 1.8, "cp_JkgK": 420.0,
        "d33_pCN": 289,
        "desc": "PZT-4 hard piezo, actuator, LRA motor, ultrasonic",
        "ref": "APC 840, Morgan PZT-4, CTS 3195HD",
    },
    {
        "name": "AlN_piezo_thinfilm",
        "lin_mid": 101033, "erode_mid": 111033, "tmid": 131033,
        "rho_gcc": 3.26, "E_GPa": 330.0, "nu": 0.24,
        "sigma_flex": 320.0,
        "K1C": 2.8,
        "cte_ppmK": 4.5, "tc_WmK": 140.0, "cp_JkgK": 740.0,
        "d33_pCN": 5,
        "desc": "AlN thin-film piezoelectric, MEMS, BAW filter",
        "ref": "OEM thin-film AlN piezoelectric properties",
    },
]

LCP_DB = [
    {
        "name": "LCP_Vectra_A950",
        "lin_mid": 101041, "erode_mid": 111041, "tmid": 131041,
        "rho_gcc": 1.40, "E_GPa": 10.6, "nu": 0.38,
        "sigma_flex": 145.0,  # flexural strength in flow direction
        "K1C": 5.0,
        "cte_ppmK": 5.0, "tc_WmK": 0.20, "cp_JkgK": 1090.0,
        "desc": "LCP Vectra A950, 5G mm-wave antenna substrate, low Df",
        "ref": "Celanese Ticona Vectra A950 TDS",
    },
    {
        "name": "LCP_Vectra_E130i",
        "lin_mid": 101042, "erode_mid": 111042, "tmid": 131042,
        "rho_gcc": 1.62, "E_GPa": 14.0, "nu": 0.35,
        "sigma_flex": 185.0,
        "K1C": 5.5,
        "cte_ppmK": 3.0, "tc_WmK": 0.25, "cp_JkgK": 1050.0,
        "desc": "LCP Vectra E130i reinforced, connectors, high mech",
        "ref": "Celanese Ticona Vectra E130i TDS",
    },
]

ALL_CERAMIC = {
    "Structural": STRUCTURAL_DB,
    "Piezo": PIEZO_DB,
    "LCP": LCP_DB,
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

def header(title, group_name):
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append(f"$ {title}")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> MPa, N, ton/mm^3")
    lines.append(f"$ Group: {group_name}")
    lines.append("$")
    lines.append("$ 2 mechanical variants per material:")
    lines.append("$   1. MAT_001 Linear Elastic       1010xx — preview")
    lines.append("$   2. MAT_001 + MAT_ADD_EROSION    1110xx — brittle failure ★")
    lines.append("$")
    lines.append("$ Erosion: principal stress > sigma_flex (flexural strength)")
    lines.append("$")
    lines.append("$ !! ========================================================================")
    lines.append("$ !!  DATABASE CONVENTION")
    lines.append("$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION / *MAT_ADD_EROSION holds")
    lines.append("$ !!  the MATERIAL ID (MID), NOT an actual Part ID.")
    lines.append("$ !! ========================================================================")
    return lines


def write_mat001_linear(m):
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Linear (MID {m['lin_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Source: {m['ref']}")
    lines.append(f"$$ E={m['E_GPa']} GPa, nu={m['nu']}, rho={m['rho_gcc']} g/cc, sigma_flex={m['sigma_flex']} MPa")
    if 'd33_pCN' in m:
        lines.append(f"$$ Piezoelectric d33 = {m['d33_pCN']} pC/N (not used in pure mechanical analysis)")
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
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Elastic+Erosion (MID {m['erode_mid']}) ---")
    lines.append(f"$$ Erosion: principal stress > {m['sigma_flex']} MPa")
    lines.append(f"$$ K1C={m['K1C']} MPa*sqrt(m)")
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
        f"{m['sigma_flex']:10.2f}"
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
    lines = []
    lines.append(f"$$ CTE={m['cte_ppmK']} ppm/K applied to both MIDs of {m['name']}")
    for mid, label in [(m["lin_mid"], "Linear"), (m["erode_mid"], "Elastic+Erode")]:
        lines.append(f"$$ [DB] PID slot holds MID={mid} ({label}, external tool must replace with actual PART IDs)")
        lines.append("*MAT_ADD_THERMAL_EXPANSION")
        lines.append("$      PID      LCID      MULT")
        lines.append(f"{mid:10d}{0:10d}{cte:10.3e}")
    return lines


# ============================================================
# File writers
# ============================================================

def write_mechanical_kfile(materials, filepath, group_name):
    title = f"CERAMIC — {group_name}: Mechanical (MAT_001 + MAT_ADD_EROSION)"
    lines = header(title, group_name)
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append(
        "$   lin     erode   tmid    Name                     E(GPa)  sigma(MPa)  K1C   rho"
    )
    lines.append("$   " + "-" * 83)
    for m in materials:
        lines.append(
            f"$   {m['lin_mid']}  {m['erode_mid']}  {m['tmid']}  "
            f"{m['name']:24s} {m['E_GPa']:6.1f}  {m['sigma_flex']:8.0f}   "
            f"{m['K1C']:4.2f}  {m['rho_gcc']:4.2f}"
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
    lines.append("$ CERAMIC THERMAL PROPERTIES")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> temperature K")
    lines.append("$")
    lines.append("$ !! DB CONVENTION: PID field holds MID, external tool replaces with PART IDs")
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append("$   TMID    Name                    CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)")
    lines.append("$   " + "-" * 73)
    for group, materials in ALL_CERAMIC.items():
        for m in materials:
            lines.append(
                f"$   {m['tmid']}  {m['name']:22s} "
                f"{m['cte_ppmK']:9.2f}  {m['tc_WmK']:8.2f}  {m['cp_JkgK']:9.1f}"
            )
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")

    for group, materials in ALL_CERAMIC.items():
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
    for group, materials in ALL_CERAMIC.items():
        db[group] = [dict(m) for m in materials]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ============================================================
# Main
# ============================================================

def main():
    script_dir = Path(__file__).parent.resolve()

    structural_path = script_dir / "ceramic_structural.k"
    piezo_path = script_dir / "ceramic_piezo.k"
    lcp_path = script_dir / "ceramic_lcp.k"
    thermal_path = script_dir / "ceramic_thermal.k"
    db_path = script_dir / "ceramic_materials_db.json"

    write_mechanical_kfile(STRUCTURAL_DB, structural_path, "Structural Ceramics")
    write_mechanical_kfile(PIEZO_DB, piezo_path, "Piezoelectric Ceramics")
    write_mechanical_kfile(LCP_DB, lcp_path, "Liquid Crystal Polymer")
    write_thermal_kfile(thermal_path)
    write_db_json(db_path)

    total = sum(len(v) for v in ALL_CERAMIC.values())
    print("=" * 65)
    print("  Ceramic Material Library Generated")
    print("=" * 65)
    for group, materials in ALL_CERAMIC.items():
        print(f"  {group:12s}: {len(materials):2d} materials")
    print(f"  TOTAL: {total} materials x 2 variants = {total*2} mechanical cards")
    print()
    print("  Output files:")
    for p in [structural_path, piezo_path, lcp_path, thermal_path, db_path]:
        sz = p.stat().st_size if p.exists() else 0
        print(f"    {p.name:35s}  {sz:7d} bytes")
    print()
    print("=" * 80)
    for group, materials in ALL_CERAMIC.items():
        print(f"  -- {group} --")
        for m in materials:
            print(
                f"  {m['lin_mid']}  {m['name']:26s} "
                f"E={m['E_GPa']:6.1f}  sigma={m['sigma_flex']:6.0f}  "
                f"k={m['tc_WmK']:5.1f}  rho={m['rho_gcc']:4.2f}"
            )


if __name__ == "__main__":
    main()
