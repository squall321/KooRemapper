#!/usr/bin/env python3
"""
Display Stack Material Library Generator for LS-DYNA
=======================================================
Produces display_oled.k, display_lcd.k, display_thermal.k based on
homogenized (Voigt/Reuss averaged) stack properties.

Variants per material:
  1. Linear Elastic (MAT_001)                    MID 1010xx
  2. Orthotropic Elastic (MAT_002)               MID 1110xx
  3. Elastic + Erosion (MAT_001 + MAT_ADD_EROSION) MID 1210xx
Plus thermal (MAT_THERMAL_ISOTROPIC, TMID 1310xx)

Unit system: mm, s, ton -> MPa, N, ton/mm^3

Method:
  - Voigt (in-plane):    E_xy = Σ(t_i × E_i) / Σ(t_i)
  - Reuss (through):     1/E_z = Σ(t_i / E_i) / Σ(t_i)
  - Density:             ρ = Σ(t_i × ρ_i) / Σ(t_i)

Data sources:
  [1] Samsung Display OLED stack publications
  [2] LG Display OLED/LCD technical papers
  [3] BOE/JDI/CSOT datasheets
  [4] PMC PubMed foldable OLED mechanical characterization
"""

import json
from pathlib import Path


# ============================================================
# Display Stack Database (homogenized)
# ============================================================
# Each material gives equivalent single-layer properties

DISPLAY_DB = [
    {
        "name": "Display_RigidOLED",
        "lin_mid": 101051, "ortho_mid": 111051, "erode_mid": 121051, "tmid": 131051,
        "rho_gcc": 2.10,  # glass-dominated
        "E_GPa_inplane": 60.0,   # Voigt avg: cover glass 77, interlayers 2-5, substrate 60
        "E_GPa_through": 30.0,   # Reuss avg: lower due to polymer layers
        "nu_inplane": 0.25,
        "nu_through": 0.30,
        "G_GPa_inplane": 24.0,
        "G_GPa_through": 12.0,
        "sigma_strength": 400.0,  # limited by weakest layer (glass in tension)
        "cte_ppmK": 15.0,        # glass 8 + polymer 60 avg
        "tc_WmK": 0.8,           # thermal avg
        "cp_JkgK": 900.0,
        "thickness_mm": 1.2,
        "desc": "Rigid OLED stack equivalent (Gorilla + OCA + OLED + glass substrate)",
        "ref": "Samsung Display / LG Display OLED stack public data; Voigt avg",
    },
    {
        "name": "Display_FlexibleOLED",
        "lin_mid": 101052, "ortho_mid": 111052, "erode_mid": 121052, "tmid": 131052,
        "rho_gcc": 1.50,  # polymer-dominated
        "E_GPa_inplane": 35.0,
        "E_GPa_through": 8.0,
        "nu_inplane": 0.30,
        "nu_through": 0.35,
        "G_GPa_inplane": 13.5,
        "G_GPa_through": 3.0,
        "sigma_strength": 300.0,
        "cte_ppmK": 30.0,  # polymer dominated
        "tc_WmK": 0.3,
        "cp_JkgK": 1200.0,
        "thickness_mm": 0.4,
        "desc": "Flexible OLED (edge curved), polymer on PI substrate",
        "ref": "Samsung Edge display, LG Flexible OLED",
    },
    {
        "name": "Display_FoldableOLED_UTG",
        "lin_mid": 101053, "ortho_mid": 111053, "erode_mid": 121053, "tmid": 131053,
        "rho_gcc": 1.80,  # UTG + PI mix
        "E_GPa_inplane": 40.0,  # thin glass dominates
        "E_GPa_through": 10.0,
        "nu_inplane": 0.28,
        "nu_through": 0.32,
        "G_GPa_inplane": 15.6,
        "G_GPa_through": 3.8,
        "sigma_strength": 500.0,  # UTG gives high strength
        "cte_ppmK": 25.0,
        "tc_WmK": 0.5,
        "cp_JkgK": 1100.0,
        "thickness_mm": 0.6,
        "desc": "Foldable OLED with UTG (Ultra-Thin Glass), Galaxy Fold/Flip",
        "ref": "Samsung UTG 30um + OLED + PI substrate",
    },
    {
        "name": "Display_FoldableOLED_CPI",
        "lin_mid": 101054, "ortho_mid": 111054, "erode_mid": 121054, "tmid": 131054,
        "rho_gcc": 1.40,  # all polymer
        "E_GPa_inplane": 10.0,  # CPI window dominates (no glass)
        "E_GPa_through": 3.0,
        "nu_inplane": 0.35,
        "nu_through": 0.40,
        "G_GPa_inplane": 3.7,
        "G_GPa_through": 1.1,
        "sigma_strength": 200.0,
        "cte_ppmK": 45.0,  # CPI has high CTE
        "tc_WmK": 0.25,
        "cp_JkgK": 1300.0,
        "thickness_mm": 0.3,
        "desc": "Foldable OLED with CPI (Colorless Polyimide) window, early foldable",
        "ref": "Galaxy Fold 1, SKC CPI",
    },
    {
        "name": "Display_LCD_IPS",
        "lin_mid": 101055, "ortho_mid": 111055, "erode_mid": 121055, "tmid": 131055,
        "rho_gcc": 1.80,  # glass + BLU mix
        "E_GPa_inplane": 25.0,  # averaged with BLU
        "E_GPa_through": 8.0,
        "nu_inplane": 0.28,
        "nu_through": 0.32,
        "G_GPa_inplane": 9.8,
        "G_GPa_through": 3.0,
        "sigma_strength": 200.0,
        "cte_ppmK": 25.0,
        "tc_WmK": 0.5,
        "cp_JkgK": 1000.0,
        "thickness_mm": 2.0,
        "desc": "LCD IPS module (Cover glass + polarizer + LC cell + BLU)",
        "ref": "JDI / BOE LCD IPS module specs",
    },
    {
        "name": "Display_MicroLED",
        "lin_mid": 101056, "ortho_mid": 111056, "erode_mid": 121056, "tmid": 131056,
        "rho_gcc": 2.30,  # sapphire substrate + cover glass
        "E_GPa_inplane": 70.0,  # heavily sapphire/glass
        "E_GPa_through": 40.0,
        "nu_inplane": 0.24,
        "nu_through": 0.28,
        "G_GPa_inplane": 28.0,
        "G_GPa_through": 15.0,
        "sigma_strength": 450.0,
        "cte_ppmK": 10.0,  # glass + sapphire
        "tc_WmK": 5.0,  # sapphire boosts thermal
        "cp_JkgK": 800.0,
        "thickness_mm": 0.8,
        "desc": "Micro-LED display (reference, sapphire substrate + cover glass)",
        "ref": "Samsung The Wall, Sony Crystal LED technical papers",
    },
]

ALL_DISPLAY = {"Display": DISPLAY_DB}


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
    lines.append("$ 3 mechanical variants per material:")
    lines.append("$   1. MAT_001 Linear (isotropic)       1010xx — simplest")
    lines.append("$   2. MAT_002 Orthotropic              1110xx — in-plane vs through-plane")
    lines.append("$   3. MAT_001 + MAT_ADD_EROSION         1210xx — crack simulation ★")
    lines.append("$")
    lines.append("$ Each material is HOMOGENIZED single layer representing")
    lines.append("$ the entire display stack (cover glass + OCA + OLED/LCD + substrate).")
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
    lines.append(f"$$ --- {m['name']} Linear Isotropic (MID {m['lin_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Homogenized: E={m['E_GPa_inplane']} GPa (in-plane), rho={m['rho_gcc']} g/cc")
    lines.append(f"$$ Stack thickness: {m['thickness_mm']} mm")
    lines.append(f"$$ Source: {m['ref']}")
    lines.append("*MAT_ELASTIC_TITLE")
    lines.append(f"{m['name']} Linear")
    lines.append("$      MID        RO         E        PR        DA        DB")
    lines.append(
        f"{m['lin_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E_to_MPa(m['E_GPa_inplane']):10.1f}"
        f"{m['nu_inplane']:10.4f}"
        f"       0.0       0.0"
    )
    return lines


def write_mat002_orthotropic(m):
    """Orthotropic transversely isotropic: in-plane (a,b) vs through (c)."""
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Orthotropic (MID {m['ortho_mid']}) ---")
    lines.append(f"$$ E_inplane={m['E_GPa_inplane']}, E_through={m['E_GPa_through']} GPa")
    lines.append(f"$$ G_inplane={m['G_GPa_inplane']}, G_through={m['G_GPa_through']} GPa")
    lines.append("*MAT_ORTHOTROPIC_ELASTIC_TITLE")
    lines.append(f"{m['name']} Orthotropic")
    # Card 1: MID RO EA EB EC PRBA PRCA PRCB
    lines.append("$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB")
    lines.append(
        f"{m['ortho_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E_to_MPa(m['E_GPa_inplane']):10.1f}"
        f"{E_to_MPa(m['E_GPa_inplane']):10.1f}"
        f"{E_to_MPa(m['E_GPa_through']):10.1f}"
        f"{m['nu_inplane']:10.4f}"
        f"{m['nu_through']:10.4f}"
        f"{m['nu_through']:10.4f}"
    )
    # Card 2: GAB GBC GCA AOPT
    lines.append("$      GAB       GBC       GCA      AOPT         G      SIGF")
    lines.append(
        f"{E_to_MPa(m['G_GPa_inplane']):10.1f}"
        f"{E_to_MPa(m['G_GPa_through']):10.1f}"
        f"{E_to_MPa(m['G_GPa_through']):10.1f}"
        f"{'2.0':>10s}{'0.0':>10s}{'0.0':>10s}"
    )
    # Card 3: XP YP ZP A1 A2 A3 MACF
    lines.append("$       XP        YP        ZP        A1        A2        A3      MACF")
    lines.append("       0.0       0.0       0.0       1.0       0.0       0.0         0")
    # Card 4: V1 V2 V3 D1 D2 D3 BETA
    lines.append("$       V1        V2        V3        D1        D2        D3      BETA")
    lines.append("       0.0       0.0       0.0       0.0       1.0       0.0       0.0")
    return lines


def write_mat001_with_erosion(m):
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Elastic+Erosion (MID {m['erode_mid']}) ---")
    lines.append(f"$$ Erosion: principal stress > {m['sigma_strength']} MPa (cover glass fracture)")
    lines.append("*MAT_ELASTIC_TITLE")
    lines.append(f"{m['name']} Elastic+Erode")
    lines.append("$      MID        RO         E        PR        DA        DB")
    lines.append(
        f"{m['erode_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E_to_MPa(m['E_GPa_inplane']):10.1f}"
        f"{m['nu_inplane']:10.4f}"
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
        f"{m['sigma_strength']:10.2f}"
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
    lines.append(f"$$ CTE={m['cte_ppmK']} ppm/K, applied to all 3 MIDs of {m['name']}")
    for mid, label in [(m["lin_mid"], "Linear"), (m["ortho_mid"], "Orthotropic"), (m["erode_mid"], "Elastic+Erode")]:
        lines.append(f"$$ [DB] PID slot holds MID={mid} ({label}, external tool must replace with actual PART IDs)")
        lines.append("*MAT_ADD_THERMAL_EXPANSION")
        lines.append("$      PID      LCID      MULT")
        lines.append(f"{mid:10d}{0:10d}{cte:10.3e}")
    return lines


# ============================================================
# File writers
# ============================================================

def write_mechanical_kfile(materials, filepath, group_name):
    title = f"DISPLAY — {group_name}: Homogenized stack mechanical"
    lines = header(title)
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append(
        "$   lin     ortho   erode   tmid    Name                    E_xy  E_z  t(mm) rho"
    )
    lines.append("$   " + "-" * 88)
    for m in materials:
        lines.append(
            f"$   {m['lin_mid']}  {m['ortho_mid']}  {m['erode_mid']}  {m['tmid']}  "
            f"{m['name']:22s} {m['E_GPa_inplane']:5.1f} {m['E_GPa_through']:4.1f}  "
            f"{m['thickness_mm']:4.1f} {m['rho_gcc']:4.2f}"
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
    lines.append("$ 2. ORTHOTROPIC ELASTIC (MAT_002)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat002_orthotropic(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 3. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)")
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
    lines.append("$ DISPLAY THERMAL PROPERTIES")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> temperature K")
    lines.append("$")
    lines.append("$ !! DB CONVENTION: PID field holds MID, external tool replaces with PART IDs")
    lines.append("$")
    lines.append("*KEYWORD")
    for group, materials in ALL_DISPLAY.items():
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
    for group, materials in ALL_DISPLAY.items():
        db[group] = [dict(m) for m in materials]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ============================================================
# Main
# ============================================================

def main():
    script_dir = Path(__file__).parent.resolve()

    oled_path = script_dir / "display_oled.k"
    lcd_path = script_dir / "display_lcd.k"
    thermal_path = script_dir / "display_thermal.k"
    db_path = script_dir / "display_materials_db.json"

    # Split by type
    oled_materials = [m for m in DISPLAY_DB if "OLED" in m["name"] or "MicroLED" in m["name"]]
    lcd_materials = [m for m in DISPLAY_DB if "LCD" in m["name"]]

    write_mechanical_kfile(oled_materials, oled_path, "OLED Stacks")
    write_mechanical_kfile(lcd_materials, lcd_path, "LCD Modules")
    write_thermal_kfile(thermal_path)
    write_db_json(db_path)

    total = len(DISPLAY_DB)
    print("=" * 65)
    print("  Display Material Library Generated")
    print("=" * 65)
    print(f"  TOTAL: {total} display stacks x 3 variants = {total*3} mechanical cards")
    print()
    print("  Output files:")
    for p in [oled_path, lcd_path, thermal_path, db_path]:
        sz = p.stat().st_size if p.exists() else 0
        print(f"    {p.name:35s}  {sz:7d} bytes")
    print()
    print("=" * 85)
    for m in DISPLAY_DB:
        print(
            f"  {m['lin_mid']}  {m['name']:26s} "
            f"E_xy={m['E_GPa_inplane']:5.1f} E_z={m['E_GPa_through']:5.1f}  "
            f"t={m['thickness_mm']:4.1f}  rho={m['rho_gcc']:4.2f}"
        )


if __name__ == "__main__":
    main()
