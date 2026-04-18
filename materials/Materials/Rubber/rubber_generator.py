#!/usr/bin/env python3
"""
Rubber Material Library Generator for LS-DYNA
================================================
Produces rubber_natural.k, rubber_synthetic.k, rubber_hiperf.k, rubber_tpe.k
(mechanical), rubber_thermal.k (thermal), rubber_damping.k (Rayleigh damping).

Each material has 3 mechanical variants:
  - Linear elastic (MAT_001)     — MID 1009xx / 1009xx / 1009xx
  - Mooney-Rivlin (MAT_027)       — MID 1109xx
  - Ogden+Prony (MAT_077_O)       — MID 1309xx
Plus thermal (MAT_THERMAL_ISOTROPIC, TMID 1209xx)

Unit system: mm, s, ton
  rho: ton/mm^3      = g/cc * 1e-9
  E, sigma, Mu: MPa
  Cp: mm^2/s^2/K     = J/kg/K * 1e6
  TC: mW/mm/K        = W/m/K

Data sources:
  - ASTM D2000 rubber classification
  - Rubber Technology (Morton 1987, 3rd ed)
  - Ogden (1972) large deformation isotropic elasticity
  - Arruda & Boyce (1993) 8-chain data
  - Shin-Etsu Silicone TDS (VMQ)
  - DuPont Viton TDS (FKM)
  - BASF Elastollan TDS (TPU)
  - MatWeb elastomer properties
"""

import os
import json
import math
from pathlib import Path


# ============================================================
# Rubber Material Database
# ============================================================
# Each material has:
#   name, lin_mid, mr_mid, ogden_mid, tmid, temper,
#   rho_gcc, hardness_shoreA,
#   E_MPa (linear equivalent), nu,
#   C10_MPa, C01_MPa (Mooney-Rivlin),
#   mu1, alpha1, mu2, alpha2, mu3, alpha3 (Ogden 3-term),
#   prony: list of (g_i, beta_i) — normalized shear decay,
#   cte_ppmK, tc_WmK, cp_JkgK,
#   damping_zeta,
#   desc, ref
#
# Relationships:
#   G_inst ≈ C10 + C01 (small strain shear modulus)
#   E_inst ≈ 3G ≈ 3*(C10 + C01)  (incompressible)
#   Mooney-Rivlin: W = C10*(I1-3) + C01*(I2-3)
#   Typical split: C01/C10 ≈ 0.25~0.5

NATURAL_DB = [
    {
        "name": "NR_SoftSuperior",
        "lin_mid": 100901, "mr_mid": 110901, "ogden_mid": 130901, "tmid": 120901,
        "temper": "Shore A 40",
        "rho_gcc": 0.92, "hardness_A": 40,
        "E_MPa": 1.6, "nu": 0.499,
        "C10": 0.267, "C01": 0.067,
        "ogden": [(0.63, 1.30), (0.0012, 5.00), (-0.01, -2.00)],
        "prony": [(0.20, 100.0), (0.15, 1000.0)],
        "cte_ppmK": 220.0, "tc_WmK": 0.14, "cp_JkgK": 1900.0,
        "damping_zeta": 0.05,
        "desc": "Natural Rubber, soft Shore A 40, vibration mount",
        "ref": "Treloar 1975, Morton Rubber Technology 3rd ed, ASTM D2000 AA",
    },
    {
        "name": "NR_Standard",
        "lin_mid": 100902, "mr_mid": 110902, "ogden_mid": 130902, "tmid": 120902,
        "temper": "Shore A 60",
        "rho_gcc": 0.93, "hardness_A": 60,
        "E_MPa": 3.6, "nu": 0.499,
        "C10": 0.60, "C01": 0.15,
        "ogden": [(1.50, 1.30), (0.0020, 5.00), (-0.02, -2.00)],
        "prony": [(0.15, 100.0), (0.10, 1000.0)],
        "cte_ppmK": 220.0, "tc_WmK": 0.14, "cp_JkgK": 1900.0,
        "damping_zeta": 0.04,
        "desc": "Natural Rubber Shore A 60, general purpose gasket",
        "ref": "ASTM D2000 AA, Arruda-Boyce 1993",
    },
    {
        "name": "SBR_TireTread",
        "lin_mid": 100903, "mr_mid": 110903, "ogden_mid": 130903, "tmid": 120903,
        "temper": "Shore A 65",
        "rho_gcc": 0.94, "hardness_A": 65,
        "E_MPa": 4.3, "nu": 0.499,
        "C10": 0.70, "C01": 0.20,
        "ogden": [(1.80, 1.30), (0.0025, 5.00), (-0.025, -2.00)],
        "prony": [(0.25, 100.0), (0.18, 1000.0)],
        "cte_ppmK": 225.0, "tc_WmK": 0.20, "cp_JkgK": 1880.0,
        "damping_zeta": 0.05,
        "desc": "Styrene-Butadiene tire tread compound",
        "ref": "Rubber Technology (Morton 1987), ASTM D2000 BA",
    },
    {
        "name": "BR_Butadiene",
        "lin_mid": 100904, "mr_mid": 110904, "ogden_mid": 130904, "tmid": 120904,
        "temper": "Shore A 55",
        "rho_gcc": 0.93, "hardness_A": 55,
        "E_MPa": 2.8, "nu": 0.499,
        "C10": 0.48, "C01": 0.12,
        "ogden": [(1.20, 1.30), (0.0015, 5.00), (-0.015, -2.00)],
        "prony": [(0.18, 100.0), (0.12, 1000.0)],
        "cte_ppmK": 220.0, "tc_WmK": 0.22, "cp_JkgK": 1900.0,
        "damping_zeta": 0.04,
        "desc": "Butadiene Rubber, tire sidewall, abrasion resistant",
        "ref": "ASTM D2000 BA, Morton 1987",
    },
    {
        "name": "IIR_Butyl",
        "lin_mid": 100905, "mr_mid": 110905, "ogden_mid": 130905, "tmid": 120905,
        "temper": "Shore A 55",
        "rho_gcc": 0.92, "hardness_A": 55,
        "E_MPa": 2.7, "nu": 0.499,
        "C10": 0.45, "C01": 0.12,
        "ogden": [(1.20, 1.30), (0.0018, 5.00), (-0.018, -2.00)],
        "prony": [(0.40, 50.0), (0.30, 500.0), (0.20, 5000.0)],
        "cte_ppmK": 195.0, "tc_WmK": 0.13, "cp_JkgK": 1960.0,
        "damping_zeta": 0.20,
        "desc": "Butyl rubber (IIR), excellent gas impermeability, damping",
        "ref": "ASTM D2000 AA, ExxonMobil Butyl TDS",
    },
    {
        "name": "CR_Neoprene",
        "lin_mid": 100906, "mr_mid": 110906, "ogden_mid": 130906, "tmid": 120906,
        "temper": "Shore A 60",
        "rho_gcc": 1.23, "hardness_A": 60,
        "E_MPa": 3.6, "nu": 0.499,
        "C10": 0.60, "C01": 0.15,
        "ogden": [(1.50, 1.30), (0.0020, 5.00), (-0.020, -2.00)],
        "prony": [(0.20, 100.0), (0.15, 1000.0)],
        "cte_ppmK": 200.0, "tc_WmK": 0.19, "cp_JkgK": 1700.0,
        "damping_zeta": 0.05,
        "desc": "Chloroprene (Neoprene), oil-resistant, wetsuit, cable",
        "ref": "DuPont Neoprene TDS, ASTM D2000 BC",
    },
    {
        "name": "NBR_Nitrile",
        "lin_mid": 100907, "mr_mid": 110907, "ogden_mid": 130907, "tmid": 120907,
        "temper": "Shore A 70",
        "rho_gcc": 1.00, "hardness_A": 70,
        "E_MPa": 5.6, "nu": 0.499,
        "C10": 0.93, "C01": 0.20,
        "ogden": [(2.20, 1.30), (0.0030, 5.00), (-0.030, -2.00)],
        "prony": [(0.22, 100.0), (0.15, 1000.0)],
        "cte_ppmK": 230.0, "tc_WmK": 0.25, "cp_JkgK": 1900.0,
        "damping_zeta": 0.06,
        "desc": "Nitrile (Buna-N), excellent fuel/oil resistance",
        "ref": "ASTM D2000 BG, Arlanxeo Perbunan TDS",
    },
    {
        "name": "EPDM_Standard",
        "lin_mid": 100908, "mr_mid": 110908, "ogden_mid": 130908, "tmid": 120908,
        "temper": "Shore A 65",
        "rho_gcc": 0.86, "hardness_A": 65,
        "E_MPa": 4.3, "nu": 0.499,
        "C10": 0.72, "C01": 0.17,
        "ogden": [(1.80, 1.30), (0.0025, 5.00), (-0.025, -2.00)],
        "prony": [(0.15, 100.0), (0.10, 1000.0)],
        "cte_ppmK": 200.0, "tc_WmK": 0.36, "cp_JkgK": 2000.0,
        "damping_zeta": 0.04,
        "desc": "Ethylene-Propylene-Diene, weather/ozone resistant",
        "ref": "ASTM D2000 CA, ISO 4097, Dow Nordel TDS",
    },
]

HIPERF_DB = [
    {
        "name": "VMQ_Silicone_Std",
        "lin_mid": 100911, "mr_mid": 110911, "ogden_mid": 130911, "tmid": 120911,
        "temper": "Shore A 50",
        "rho_gcc": 1.15, "hardness_A": 50,
        "E_MPa": 2.2, "nu": 0.499,
        "C10": 0.37, "C01": 0.09,
        "ogden": [(0.90, 1.30), (0.0012, 5.00), (-0.012, -2.00)],
        "prony": [(0.08, 100.0), (0.05, 1000.0)],
        "cte_ppmK": 310.0, "tc_WmK": 0.22, "cp_JkgK": 1300.0,
        "damping_zeta": 0.025,
        "desc": "Silicone VMQ Shore A 50, -55~250°C, low damping",
        "ref": "Shin-Etsu KE-961-U TDS, ASTM D2000 FC/FE",
    },
    {
        "name": "VMQ_Silicone_Firm",
        "lin_mid": 100912, "mr_mid": 110912, "ogden_mid": 130912, "tmid": 120912,
        "temper": "Shore A 70",
        "rho_gcc": 1.20, "hardness_A": 70,
        "E_MPa": 5.6, "nu": 0.499,
        "C10": 0.93, "C01": 0.20,
        "ogden": [(2.20, 1.30), (0.0030, 5.00), (-0.030, -2.00)],
        "prony": [(0.08, 100.0), (0.05, 1000.0)],
        "cte_ppmK": 300.0, "tc_WmK": 0.24, "cp_JkgK": 1300.0,
        "damping_zeta": 0.025,
        "desc": "Silicone VMQ Shore A 70, firmer gasket/keypad",
        "ref": "Dow 3-6749, Shin-Etsu KE-951-U",
    },
    {
        "name": "FKM_Viton",
        "lin_mid": 100913, "mr_mid": 110913, "ogden_mid": 130913, "tmid": 120913,
        "temper": "Shore A 75",
        "rho_gcc": 1.85, "hardness_A": 75,
        "E_MPa": 6.8, "nu": 0.499,
        "C10": 1.13, "C01": 0.25,
        "ogden": [(2.80, 1.30), (0.0035, 5.00), (-0.035, -2.00)],
        "prony": [(0.15, 100.0), (0.10, 1000.0)],
        "cte_ppmK": 160.0, "tc_WmK": 0.25, "cp_JkgK": 1700.0,
        "damping_zeta": 0.035,
        "desc": "Fluoroelastomer (Viton A/B), extreme oil/heat",
        "ref": "DuPont Viton A/B TDS, ASTM D2000 HK",
    },
    {
        "name": "FFKM_Kalrez",
        "lin_mid": 100914, "mr_mid": 110914, "ogden_mid": 130914, "tmid": 120914,
        "temper": "Shore A 75",
        "rho_gcc": 2.00, "hardness_A": 75,
        "E_MPa": 7.0, "nu": 0.499,
        "C10": 1.17, "C01": 0.25,
        "ogden": [(2.90, 1.30), (0.0036, 5.00), (-0.036, -2.00)],
        "prony": [(0.15, 100.0), (0.10, 1000.0)],
        "cte_ppmK": 150.0, "tc_WmK": 0.25, "cp_JkgK": 1700.0,
        "damping_zeta": 0.035,
        "desc": "Perfluoroelastomer (Kalrez), semiconductor, chemical",
        "ref": "DuPont Kalrez 4079 TDS",
    },
]

TPE_DB = [
    {
        "name": "TPU_Hard_85A",
        "lin_mid": 100921, "mr_mid": 110921, "ogden_mid": 130921, "tmid": 120921,
        "temper": "Shore A 85",
        "rho_gcc": 1.20, "hardness_A": 85,
        "E_MPa": 15.0, "nu": 0.499,
        "C10": 2.50, "C01": 0.50,
        "ogden": [(5.00, 1.30), (0.0080, 5.00), (-0.080, -2.00)],
        "prony": [(0.25, 100.0), (0.15, 1000.0)],
        "cte_ppmK": 170.0, "tc_WmK": 0.19, "cp_JkgK": 1800.0,
        "damping_zeta": 0.07,
        "desc": "Thermoplastic Polyurethane Shore A 85, phone cases",
        "ref": "BASF Elastollan 1185A TDS, Lubrizol ISOPLAST",
    },
    {
        "name": "TPE_S_SBS",
        "lin_mid": 100922, "mr_mid": 110922, "ogden_mid": 130922, "tmid": 120922,
        "temper": "Shore A 65",
        "rho_gcc": 0.93, "hardness_A": 65,
        "E_MPa": 4.3, "nu": 0.490,
        "C10": 0.72, "C01": 0.15,
        "ogden": [(1.80, 1.30), (0.0025, 5.00), (-0.025, -2.00)],
        "prony": [(0.30, 100.0), (0.20, 1000.0)],
        "cte_ppmK": 180.0, "tc_WmK": 0.14, "cp_JkgK": 1900.0,
        "damping_zeta": 0.06,
        "desc": "Styrenic TPE (SBS), grip, overmolding",
        "ref": "Kraton G1650 TDS, Shell TPE",
    },
]

ALL_MATERIALS = {
    "Natural": NATURAL_DB,
    "HighPerformance": HIPERF_DB,
    "TPE": TPE_DB,
}


# ============================================================
# Unit conversions
# ============================================================
def rho_to_tonmm3(rho_gcc):
    return rho_gcc * 1e-9

def cte_to_perK(cte_ppmK):
    return cte_ppmK * 1e-6

def tc_to_mWmmK(tc_WmK):
    return tc_WmK

def cp_to_mm2s2K(cp_JkgK):
    return cp_JkgK * 1e6


# ============================================================
# K-file writers
# ============================================================

def header(title, group_name, group_desc, mid_range):
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append(f"$ {title}")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> MPa, N, ton/mm^3")
    lines.append(f"$ Group: {group_name} — {group_desc}")
    lines.append(f"$ MID: {mid_range}")
    lines.append("$")
    lines.append("$ Hybrid strategy (3 variants per material):")
    lines.append("$   Linear elastic (MAT_001)    MID 1009xx — low strain preview")
    lines.append("$   Mooney-Rivlin (MAT_027)     MID 1109xx — standard hyperelastic")
    lines.append("$   Ogden+Prony (MAT_077_O)     MID 1309xx — dynamic with damping")
    lines.append("$")
    lines.append("$ Thermal properties (TC, Cp, CTE) in rubber_thermal.k")
    lines.append("$ Rayleigh damping for MAT_001/MAT_027 in rubber_damping.k")
    lines.append("$ (MAT_077_O has built-in Prony viscoelasticity)")
    lines.append("$")
    lines.append("$ !! ========================================================================")
    lines.append("$ !!  DATABASE CONVENTION — IMPORTANT")
    lines.append("$ !!")
    lines.append("$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID (MID),")
    lines.append("$ !!  NOT an actual Part ID. External tool must replace with real PIDs.")
    lines.append("$ !! ========================================================================")
    return lines


def write_mat001_linear(m):
    """Write a MAT_001 linear elastic card."""
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Linear (MID {m['lin_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Hardness: {m['temper']}, Source: {m['ref']}")
    lines.append(f"$$ E={m['E_MPa']} MPa (linear approximation for small strain ≤10%)")
    lines.append("*MAT_ELASTIC_TITLE")
    lines.append(f"{m['name']} Linear")
    lines.append("$      MID        RO         E        PR        DA        DB  NOT_USED")
    lines.append(
        f"{m['lin_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{m['E_MPa']:10.4f}"
        f"{m['nu']:10.4f}"
        f"       0.0       0.0       0.0"
    )
    return lines


def write_mat027_mooney_rivlin(m):
    """Write a MAT_027 Mooney-Rivlin card."""
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Mooney-Rivlin (MID {m['mr_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Hardness: {m['temper']}, Source: {m['ref']}")
    lines.append(f"$$ C10={m['C10']} MPa, C01={m['C01']} MPa")
    lines.append(f"$$ W = C10*(I1-3) + C01*(I2-3)")
    lines.append("*MAT_MOONEY-RIVLIN_RUBBER_TITLE")
    lines.append(f"{m['name']} Mooney-Rivlin")
    lines.append("$      MID        RO         A         B        PR       REF       SGL       SW")
    lines.append(
        f"{m['mr_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{m['C10']:10.4f}"
        f"{m['C01']:10.4f}"
        f"{m['nu']:10.4f}"
        f"       0.0       0.0       0.0"
    )
    lines.append("$                  LCID (optional uniaxial test data)")
    lines.append("                     0")
    return lines


def write_mat077_ogden(m):
    """Write a MAT_077_O Ogden + Prony viscoelastic card."""
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Ogden Viscoelastic (MID {m['ogden_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Hardness: {m['temper']}, Source: {m['ref']}")
    lines.append(f"$$ Ogden 3-term + {len(m['prony'])} Prony terms")
    n_ogden = len([x for x in m['ogden'] if abs(x[0]) > 1e-12])
    n_prony = len(m['prony'])
    lines.append("*MAT_HYPERELASTIC_RUBBER_TITLE")
    lines.append(f"{m['name']} Ogden Viscoelastic")
    # Card 1: MID RO PR N NV G SIGF REF
    lines.append("$      MID        RO        PR         N        NV         G      SIGF       REF")
    lines.append(
        f"{m['ogden_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{m['nu']:10.4f}"
        f"{n_ogden:10d}"
        f"{n_prony:10d}"
        f"       0.0       0.0       0.0"
    )
    # Card 2: SGL SW ST LCID DATA LCID2 (simplified — leave blank)
    lines.append("$      SGL        SW        ST      LCID      DATA     LCID2")
    lines.append("       0.0       0.0       0.0         0         0         0")
    # Card 3: MU1 ALPHA1 MU2 ALPHA2 MU3 ALPHA3 MU4 ALPHA4 (up to 8 pairs)
    lines.append("$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4")
    mu_alpha = list(m['ogden'])
    while len(mu_alpha) < 4:
        mu_alpha.append((0.0, 0.0))
    fields = []
    for mu, alpha in mu_alpha[:4]:
        fields.append(f"{mu:10.4f}")
        fields.append(f"{alpha:10.4f}")
    lines.append("".join(fields))
    # Card 5/onward: Prony series (G_i, BETA_i) — up to 6 pairs
    for gi, beta in m['prony']:
        lines.append(f"{gi:10.4f}{beta:10.2f}")
    # Fill remaining Prony rows with zeros (MAT_077_O expects 6 rows after Ogden section)
    n_remaining = 6 - len(m['prony'])
    for _ in range(max(0, n_remaining)):
        lines.append(f"{0.0:10.4f}{0.0:10.2f}")
    return lines


def write_mat_thermal_isotropic(m):
    """Write a *MAT_THERMAL_ISOTROPIC card."""
    lines = []
    tc_out = tc_to_mWmmK(m["tc_WmK"])
    cp_out = cp_to_mm2s2K(m["cp_JkgK"])
    rho_out = rho_to_tonmm3(m["rho_gcc"])
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Thermal (TMID {m['tmid']}) ---")
    lines.append(f"$$ TC={m['tc_WmK']} W/m/K, Cp={m['cp_JkgK']} J/kg/K, rho={m['rho_gcc']} g/cc")
    lines.append("*MAT_THERMAL_ISOTROPIC_TITLE")
    lines.append(f"{m['name']} Thermal")
    lines.append("$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT")
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
    """Write *MAT_ADD_THERMAL_EXPANSION for all 3 mechanical MIDs."""
    cte = cte_to_perK(m["cte_ppmK"])
    mids_labels = [
        (m["lin_mid"], "Linear"),
        (m["mr_mid"], "Mooney-Rivlin"),
        (m["ogden_mid"], "Ogden+Visco"),
    ]
    lines = []
    lines.append(f"$$ CTE={m['cte_ppmK']} ppm/K, applied to all 3 MIDs of {m['name']}")
    for mid, label in mids_labels:
        lines.append(f"$$ [DB] PID slot holds MID={mid} ({label}, external tool must replace with actual PART IDs)")
        lines.append("*MAT_ADD_THERMAL_EXPANSION")
        lines.append("$      PID      LCID      MULT")
        lines.append(f"{mid:10d}{0:10d}{cte:10.3e}")
    return lines


# ============================================================
# File writers
# ============================================================

def write_mechanical_kfile(materials, filepath, group_name, group_desc, mid_range):
    """Write a K-file with all mechanical variants."""
    title = f"RUBBER — {group_name}: Mechanical (MAT_001 + MAT_027 + MAT_077_O)"
    lines = header(title, group_name, group_desc, mid_range)
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append(
        "$   lin_mid  mr_mid  og_mid  Name                       ShoreA  E(MPa) C10   C01   rho"
    )
    lines.append("$   " + "-" * 88)
    for m in materials:
        lines.append(
            f"$   {m['lin_mid']}   {m['mr_mid']}  {m['ogden_mid']}  "
            f"{m['name']:25s}  {m['hardness_A']:5d}   "
            f"{m['E_MPa']:5.2f}  {m['C10']:5.3f} {m['C01']:5.3f}  {m['rho_gcc']:4.2f}"
        )
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 1. LINEAR ELASTIC (MAT_001, for low-strain preview)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat001_linear(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 2. MOONEY-RIVLIN HYPERELASTIC (MAT_027, standard)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat027_mooney_rivlin(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 3. OGDEN HYPERELASTIC + PRONY VISCOELASTIC (MAT_077_O)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat077_ogden(m))
    lines.append("$")
    lines.append("*END")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_thermal_kfile(filepath):
    """Write combined thermal K-file for all rubber materials."""
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append("$ RUBBER THERMAL PROPERTIES")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> temperature K")
    lines.append("$   TC (thermal conductivity) : mW/mm/K  (= W/m/K)")
    lines.append("$   Cp (specific heat)        : mm^2/s^2/K (= J/kg/K * 1e6)")
    lines.append("$   CTE                       : 1/K  (= ppm/K * 1e-6)")
    lines.append("$")
    lines.append("$ !! ========================================================================")
    lines.append("$ !!  DATABASE CONVENTION — IMPORTANT")
    lines.append("$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID,")
    lines.append("$ !!  NOT an actual Part ID. External tool must replace with real PIDs.")
    lines.append("$ !!  CTE is applied to all 3 MIDs (linear/Mooney-Rivlin/Ogden+Visco).")
    lines.append("$ !! ========================================================================")
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append("$   TMID    Name                      CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)")
    lines.append("$   " + "-" * 70)
    for group, materials in ALL_MATERIALS.items():
        for m in materials:
            lines.append(
                f"$   {m['tmid']}  {m['name']:25s} "
                f"{m['cte_ppmK']:9.1f}  {m['tc_WmK']:8.3f}  {m['cp_JkgK']:9.1f}"
            )
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")

    for group, materials in ALL_MATERIALS.items():
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


def write_damping_kfile(filepath, omega_ref_hz=1000.0):
    """
    Write Rayleigh damping for MAT_001 and MAT_027 variants.
    (MAT_077_O has built-in Prony viscoelasticity, but we still provide
    structural damping for mass/stiffness if needed.)
    """
    omega_ref = 2.0 * math.pi * omega_ref_hz

    lines = []
    lines.append("$ " + "=" * 72)
    lines.append("$ RUBBER DAMPING LIBRARY (Rayleigh for MAT_001 / MAT_027 / MAT_077_O)")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton")
    lines.append(f"$ Reference frequency: {omega_ref_hz:.0f} Hz ({omega_ref:.1f} rad/s)")
    lines.append("$")
    lines.append("$ Note: MAT_077_O (Ogden+Prony) already has viscoelastic damping built in.")
    lines.append("$       Additional Rayleigh is OPTIONAL — include only if needed for")
    lines.append("$       global structural damping beyond material Prony.")
    lines.append("$")
    lines.append("$ Damping ratios by rubber family:")
    lines.append("$   NR/SBR/BR:           3~5%  (general)")
    lines.append("$   IIR (Butyl):         20%   (extreme damping for isolation)")
    lines.append("$   NBR/CR/EPDM:         4~6%")
    lines.append("$   VMQ (Silicone):      2~3%  (lowest)")
    lines.append("$   FKM/FFKM:            3~4%")
    lines.append("$   TPU/TPE:             6~8%")
    lines.append("$")
    lines.append("$ Part Set SID = MID + 800000")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")

    for group, materials in ALL_MATERIALS.items():
        lines.append("$")
        lines.append("$ " + "=" * 72)
        lines.append(f"$ {group} DAMPING")
        lines.append("$ " + "=" * 72)
        for m in materials:
            zeta = m["damping_zeta"]
            alpha = zeta * omega_ref
            beta = zeta / omega_ref

            variants = [
                ("linear", m["lin_mid"]),
                ("mooney", m["mr_mid"]),
                ("ogden", m["ogden_mid"]),
            ]
            for label, mid in variants:
                psid = mid + 800000
                lines.append("$")
                lines.append(f"$$ --- {m['name']} ({label}, MID {mid}) ---")
                lines.append(f"$$ zeta={zeta:.4f} ({zeta*100:.2f}%) @ f_ref={omega_ref_hz:.0f} Hz")
                lines.append(f"$$ alpha={alpha:.3e} /s, beta={beta:.3e} s")
                lines.append("*SET_PART_LIST_TITLE")
                lines.append(f"{m['name']}_{label}_parts")
                lines.append("$      SID       DA1       DA2       DA3       DA4")
                lines.append(f"{psid:10d}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}")
                lines.append("$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8")
                lines.append("$ TODO: replace zeros with actual PART IDs")
                lines.append(f"{'0':>10s}{'0':>10s}{'0':>10s}{'0':>10s}"
                             f"{'0':>10s}{'0':>10s}{'0':>10s}{'0':>10s}")
                lines.append("*DAMPING_PART_MASS_SET")
                lines.append("$     PSID      LCID    VALDMP       STX       STY       STZ       SRX       SRY")
                lines.append(
                    f"{psid:10d}{'0':>10s}{alpha:10.3e}"
                    f"{'1.0':>10s}{'1.0':>10s}{'1.0':>10s}{'1.0':>10s}{'1.0':>10s}"
                )
                lines.append("*DAMPING_PART_STIFFNESS_SET")
                lines.append("$     PSID      COEF")
                lines.append(f"{psid:10d}{beta:10.3e}")

    lines.append("$")
    lines.append("*END")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_db_json(filepath):
    """Save parsed DB as JSON."""
    db = {}
    for group, materials in ALL_MATERIALS.items():
        db[group] = []
        for m in materials:
            entry = dict(m)
            entry["ogden"] = [list(p) for p in m["ogden"]]
            entry["prony"] = [list(p) for p in m["prony"]]
            db[group].append(entry)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ============================================================
# Main
# ============================================================

def main():
    script_dir = Path(__file__).parent.resolve()

    # Write separate K-files for each group
    natural_syn_path = script_dir / "rubber_natural_synthetic.k"
    hiperf_path = script_dir / "rubber_hiperf.k"
    tpe_path = script_dir / "rubber_tpe.k"
    thermal_path = script_dir / "rubber_thermal.k"
    damping_path = script_dir / "rubber_damping.k"
    db_path = script_dir / "rubber_materials_db.json"

    write_mechanical_kfile(
        NATURAL_DB, natural_syn_path,
        group_name="Natural & Synthetic",
        group_desc="NR, SBR, BR, IIR, CR, NBR, EPDM",
        mid_range="100901~100908 (lin), 110901~110908 (MR), 130901~130908 (Ogden)",
    )
    write_mechanical_kfile(
        HIPERF_DB, hiperf_path,
        group_name="High-Performance",
        group_desc="VMQ Silicone, FKM Viton, FFKM Kalrez",
        mid_range="100911~100914 (lin), 110911~110914 (MR), 130911~130914 (Ogden)",
    )
    write_mechanical_kfile(
        TPE_DB, tpe_path,
        group_name="Thermoplastic Elastomer",
        group_desc="TPU, TPE-S (SBS/SIS)",
        mid_range="100921~100922 (lin), 110921~110922 (MR), 130921~130922 (Ogden)",
    )
    write_thermal_kfile(thermal_path)
    write_damping_kfile(damping_path)
    write_db_json(db_path)

    total = sum(len(v) for v in ALL_MATERIALS.values())
    print("=" * 65)
    print("  Rubber Material Library Generated")
    print("=" * 65)
    for group, materials in ALL_MATERIALS.items():
        print(f"  {group:25s}: {len(materials):2d} materials")
    print(f"  TOTAL: {total} materials x 3 mech variants = {total*3} mechanical cards")
    print(f"  + {total} thermal + {total*3} damping part sets")
    print()
    print("  Output files:")
    for p in [natural_syn_path, hiperf_path, tpe_path,
              thermal_path, damping_path, db_path]:
        sz = p.stat().st_size if p.exists() else 0
        print(f"    {p.name:35s}  {sz:7d} bytes")

    # Per-material summary
    print()
    print("=" * 85)
    print(f"  {'lin_mid':>7s} {'mr_mid':>7s} {'og_mid':>7s}  {'Name':25s} "
          f"{'ShoreA':>6s} {'E(MPa)':>7s} {'C10':>6s} {'zeta':>5s}")
    print("  " + "-" * 83)
    for group, materials in ALL_MATERIALS.items():
        for m in materials:
            print(
                f"  {m['lin_mid']:7d} {m['mr_mid']:7d} {m['ogden_mid']:7d}  "
                f"{m['name']:25s} {m['hardness_A']:6d} {m['E_MPa']:7.2f} "
                f"{m['C10']:6.3f} {m['damping_zeta']:5.3f}"
            )


if __name__ == "__main__":
    main()
