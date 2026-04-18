#!/usr/bin/env python3
"""
Magnet Material Library Generator for LS-DYNA
================================================
Produces magnet_ndfeb.k, magnet_smco.k, magnet_ferrite.k, magnet_thermal.k
for STRUCTURAL analysis only (no EM/magnetic simulation).

Variants:
  1. MAT_001 Linear Elastic          MID 1010xx
  2. MAT_001 + MAT_ADD_EROSION        MID 1110xx (brittle crack)
Plus thermal

Unit: mm, s, ton -> MPa, N, ton/mm^3

Data sources:
  [1] Arnold Magnetic Technologies NdFeB N-series TDS
  [2] Vacuumschmelze Vacodym NdFeB TDS
  [3] Hitachi Metals Neomax series
  [4] Shin-Etsu Rare Earth Magnet
  [5] Arnold SmCo 2:17 datasheet
"""

import json
from pathlib import Path


NDFEB_DB = [
    {
        "name": "NdFeB_N35",
        "lin_mid": 101061, "erode_mid": 111061, "tmid": 131061,
        "rho_gcc": 7.40, "E_GPa": 150.0, "nu": 0.24,
        "sigma_flex": 270.0,  # flexural strength
        "K1C": 3.5,
        "cte_ppmK": 5.0, "tc_WmK": 9.0, "cp_JkgK": 460.0,
        "BHmax_MGOe": 35, "Tmax_C": 80,
        "desc": "NdFeB N35 sintered magnet, economy grade",
        "ref": "Arnold Magnetic N35, Vacuumschmelze Vacodym 633 HR",
    },
    {
        "name": "NdFeB_N42",
        "lin_mid": 101062, "erode_mid": 111062, "tmid": 131062,
        "rho_gcc": 7.50, "E_GPa": 160.0, "nu": 0.24,
        "sigma_flex": 280.0,
        "K1C": 3.8,
        "cte_ppmK": 5.0, "tc_WmK": 9.0, "cp_JkgK": 460.0,
        "BHmax_MGOe": 42, "Tmax_C": 80,
        "desc": "NdFeB N42, standard speaker/wireless charging",
        "ref": "Arnold N42, Hitachi Metals NEOMAX-42",
    },
    {
        "name": "NdFeB_N52",
        "lin_mid": 101063, "erode_mid": 111063, "tmid": 131063,
        "rho_gcc": 7.60, "E_GPa": 170.0, "nu": 0.24,
        "sigma_flex": 290.0,
        "K1C": 4.0,
        "cte_ppmK": 5.0, "tc_WmK": 9.0, "cp_JkgK": 460.0,
        "BHmax_MGOe": 52, "Tmax_C": 65,
        "desc": "NdFeB N52 highest energy, premium (camera OIS, premium speaker)",
        "ref": "Shin-Etsu N52, Arnold N52",
    },
]

SMCO_DB = [
    {
        "name": "SmCo_2_17",
        "lin_mid": 101064, "erode_mid": 111064, "tmid": 131064,
        "rho_gcc": 8.40, "E_GPa": 150.0, "nu": 0.24,
        "sigma_flex": 150.0,
        "K1C": 3.0,
        "cte_ppmK": 9.0, "tc_WmK": 12.0, "cp_JkgK": 360.0,
        "BHmax_MGOe": 30, "Tmax_C": 350,
        "desc": "SmCo 2:17 sintered, high-temperature, corrosion resistant",
        "ref": "Arnold Recoma 26, Vacuumschmelze Vacomax 225 HR",
    },
]

FERRITE_DB = [
    {
        "name": "SrFerrite_Y30",
        "lin_mid": 101065, "erode_mid": 111065, "tmid": 131065,
        "rho_gcc": 4.90, "E_GPa": 160.0, "nu": 0.28,
        "sigma_flex": 70.0,  # ferrite is weaker
        "K1C": 1.5,
        "cte_ppmK": 13.0, "tc_WmK": 4.0, "cp_JkgK": 790.0,
        "BHmax_MGOe": 4.0, "Tmax_C": 250,
        "desc": "Strontium ferrite Y30, low-cost hard magnet (toys, appliances)",
        "ref": "TDK Ceramagnet 8, Hitachi Ferrite FB",
    },
    {
        "name": "NdFeB_Bonded",
        "lin_mid": 101066, "erode_mid": 111066, "tmid": 131066,
        "rho_gcc": 5.50, "E_GPa": 12.0, "nu": 0.35,
        "sigma_flex": 100.0,
        "K1C": 2.0,
        "cte_ppmK": 20.0, "tc_WmK": 1.5, "cp_JkgK": 1000.0,
        "BHmax_MGOe": 10, "Tmax_C": 120,
        "desc": "Injection-molded bonded NdFeB (polymer + magnetic powder)",
        "ref": "MMG Canada Bonded NdFeB, MagForce",
    },
]

ALL_MAGNET = {
    "NdFeB": NDFEB_DB,
    "SmCo": SMCO_DB,
    "Ferrite/Bonded": FERRITE_DB,
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
    lines.append("$ 2 variants per material:")
    lines.append("$   1. MAT_001 Linear           1010xx — preview")
    lines.append("$   2. MAT_001 + MAT_ADD_EROSION 1110xx — brittle crack ★")
    lines.append("$")
    lines.append("$ NOTE: Mechanical properties ONLY.")
    lines.append("$       For EM/magnetic force simulation, use *EM_MAT_PERMANENT_MAGNET.")
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
    lines.append(f"$$ E={m['E_GPa']} GPa, rho={m['rho_gcc']} g/cc, BHmax={m['BHmax_MGOe']} MGOe")
    lines.append(f"$$ Max operating temperature: {m['Tmax_C']} C")
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
    lines.append(f"$$ Brittle failure: principal stress > {m['sigma_flex']} MPa")
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
    lines.append(f"$$ [DB] PID slot holds MID={m['erode_mid']}")
    lines.append("*MAT_ADD_EROSION")
    lines.append("$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS")
    lines.append(
        f"{m['erode_mid']:10d}"
        f"       0.0       0.0       0.0       0.0       0.0"
        f"{1:10d}{1:10d}"
    )
    lines.append("$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM")
    lines.append(
        f"       0.0"
        f"{m['sigma_flex']:10.2f}"
        f"       0.0       0.0       0.0       0.0       0.0       0.0"
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
    lines.append(f"$$ CTE={m['cte_ppmK']} ppm/K, applied to both MIDs of {m['name']}")
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
    title = f"MAGNET — {group_name}: Mechanical (MAT_001 + MAT_ADD_EROSION)"
    lines = header(title, group_name)
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append(
        "$   lin     erode   tmid    Name                 E(GPa) rho   sigma  BHmax  Tmax"
    )
    lines.append("$   " + "-" * 85)
    for m in materials:
        lines.append(
            f"$   {m['lin_mid']}  {m['erode_mid']}  {m['tmid']}  "
            f"{m['name']:20s} {m['E_GPa']:5.1f}  {m['rho_gcc']:4.2f}  "
            f"{m['sigma_flex']:5.0f}  {m['BHmax_MGOe']:5.1f}  {m['Tmax_C']:3d}"
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
    lines.append("$ 2. ELASTIC + EROSION")
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
    lines.append("$ MAGNET THERMAL PROPERTIES")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> temperature K")
    lines.append("$")
    lines.append("$ !! DB CONVENTION: PID field holds MID, external tool replaces with PART IDs")
    lines.append("$")
    lines.append("*KEYWORD")

    for group, materials in ALL_MAGNET.items():
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
    for group, materials in ALL_MAGNET.items():
        db[group] = [dict(m) for m in materials]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ============================================================
# Main
# ============================================================

def main():
    script_dir = Path(__file__).parent.resolve()

    ndfeb_path = script_dir / "magnet_ndfeb.k"
    smco_path = script_dir / "magnet_smco.k"
    ferrite_path = script_dir / "magnet_ferrite.k"
    thermal_path = script_dir / "magnet_thermal.k"
    db_path = script_dir / "magnet_materials_db.json"

    write_mechanical_kfile(NDFEB_DB, ndfeb_path, "NdFeB")
    write_mechanical_kfile(SMCO_DB, smco_path, "SmCo")
    write_mechanical_kfile(FERRITE_DB, ferrite_path, "Ferrite / Bonded")
    write_thermal_kfile(thermal_path)
    write_db_json(db_path)

    total = sum(len(v) for v in ALL_MAGNET.values())
    print("=" * 65)
    print("  Magnet Material Library Generated")
    print("=" * 65)
    for group, materials in ALL_MAGNET.items():
        print(f"  {group:18s}: {len(materials):2d} materials")
    print(f"  TOTAL: {total} materials x 2 variants")
    print()
    print("  Output files:")
    for p in [ndfeb_path, smco_path, ferrite_path, thermal_path, db_path]:
        sz = p.stat().st_size if p.exists() else 0
        print(f"    {p.name:35s}  {sz:7d} bytes")
    print()
    print("=" * 85)
    for group, materials in ALL_MAGNET.items():
        for m in materials:
            print(
                f"  {m['lin_mid']}  {m['name']:22s} "
                f"E={m['E_GPa']:6.1f}  rho={m['rho_gcc']:4.2f}  "
                f"BHmax={m['BHmax_MGOe']:5.1f}  Tmax={m['Tmax_C']:3d}C"
            )


if __name__ == "__main__":
    main()
