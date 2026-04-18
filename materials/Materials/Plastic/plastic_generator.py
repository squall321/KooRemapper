#!/usr/bin/env python3
"""
Plastic Material Library Generator for LS-DYNA
=================================================
Produces plastic_standard.k, plastic_reinforced.k, plastic_hiperf.k
(mechanical), plastic_thermal.k (thermal), plastic_damping.k (Rayleigh).

Each material has 5 mechanical variants:
  1. Linear elastic (MAT_001)            MID 1009xx
  2. Bilinear isotropic (MAT_024)        MID 1109xx
  3. Multilinear isotropic (MAT_024+LCSS) MID 1209xx
  4. Bilinear kinematic mixed (MAT_003)  MID 1309xx
  5. SAMP-1 advanced polymer (MAT_187)   MID 1409xx
Plus thermal (MAT_THERMAL_ISOTROPIC, TMID 1509xx)

Unit system: mm, s, ton
Data sources: Covestro, BASF, SABIC, DuPont, Solvay, Victrex TDS
              PMC 10179745, Mulliken-Boyce 2006, Kwon 2008
"""

import os
import json
import math
from pathlib import Path


# ============================================================
# Plastic Material Database
# ============================================================

STANDARD_DB = [
    {
        "name": "PC_Makrolon",
        "lin_mid": 100961, "bi_mid": 110961, "mu_mid": 120961, "kin_mid": 130961, "samp_mid": 140961, "tmid": 150961,
        "rho_gcc": 1.20, "E_GPa": 2.40, "nu": 0.37,
        "sigy_MPa": 65.0, "sigu_MPa": 68.0, "eps_f": 1.15,
        "ss_plastic": [
            (0.000, 65.0), (0.005, 66.0), (0.010, 66.5),
            (0.020, 65.5), (0.050, 62.0), (0.100, 60.0),
            (0.300, 64.0), (0.600, 68.0), (1.150, 68.0),
        ],
        "cte_ppmK": 65.0, "tc_WmK": 0.21, "cp_JkgK": 1200.0,
        "cs_C": 1.4, "cs_P": 2.5,
        "damping_zeta": 0.025,
        "desc": "Polycarbonate (Makrolon 2405), transparent, cover glass",
        "ref": "Covestro Makrolon 2405 TDS: E=2.4 GPa, sigy=65 MPa, ISO 527, eps_break=115%",
    },
    {
        "name": "ABS_Cycolac",
        "lin_mid": 100962, "bi_mid": 110962, "mu_mid": 120962, "kin_mid": 130962, "samp_mid": 140962, "tmid": 150962,
        "rho_gcc": 1.05, "E_GPa": 2.30, "nu": 0.38,
        "sigy_MPa": 42.0, "sigu_MPa": 45.0, "eps_f": 0.25,
        "ss_plastic": [
            (0.000, 42.0), (0.010, 44.0), (0.020, 45.0),
            (0.050, 44.0), (0.100, 43.0), (0.150, 44.0),
            (0.250, 45.0),
        ],
        "cte_ppmK": 90.0, "tc_WmK": 0.17, "cp_JkgK": 1300.0,
        "cs_C": 5.0, "cs_P": 3.0,
        "damping_zeta": 0.050,
        "desc": "Acrylonitrile-Butadiene-Styrene, housings",
        "ref": "SABIC Cycolac TDS, Louche 2009",
    },
    {
        "name": "PC_ABS_Cycoloy",
        "lin_mid": 100963, "bi_mid": 110963, "mu_mid": 120963, "kin_mid": 130963, "samp_mid": 140963, "tmid": 150963,
        "rho_gcc": 1.14, "E_GPa": 2.40, "nu": 0.38,
        "sigy_MPa": 55.0, "sigu_MPa": 60.0, "eps_f": 0.50,
        "ss_plastic": [
            (0.000, 55.0), (0.010, 57.0), (0.020, 58.0),
            (0.040, 57.5), (0.080, 56.0), (0.150, 55.0),
            (0.300, 58.0), (0.500, 60.0),
        ],
        "cte_ppmK": 78.0, "tc_WmK": 0.19, "cp_JkgK": 1250.0,
        "cs_C": 2.5, "cs_P": 2.8,
        "damping_zeta": 0.045,
        "desc": "PC/ABS blend (Cycoloy), smartphone midframe",
        "ref": "SABIC Cycoloy C1200HF TDS",
    },
    {
        "name": "PA6_Ultramid_B",
        "lin_mid": 100964, "bi_mid": 110964, "mu_mid": 120964, "kin_mid": 130964, "samp_mid": 140964, "tmid": 150964,
        "rho_gcc": 1.14, "E_GPa": 3.00, "nu": 0.38,
        "sigy_MPa": 90.0, "sigu_MPa": 95.0, "eps_f": 0.15,
        "ss_plastic": [
            (0.000, 90.0), (0.010, 92.0), (0.020, 93.0),
            (0.040, 92.0), (0.060, 91.0), (0.100, 93.0),
            (0.150, 95.0),
        ],
        "cte_ppmK": 100.0, "tc_WmK": 0.27, "cp_JkgK": 1700.0,
        "cs_C": 0.5, "cs_P": 5.0,
        "damping_zeta": 0.040,
        "desc": "Nylon 6 (PA6) BASF Ultramid B27, connectors, gears (dry state)",
        "ref": "BASF Ultramid B27 E 01 TDS: E=3.0 GPa, sigy=90 MPa (dry)",
    },
    {
        "name": "PA66_Zytel",
        "lin_mid": 100965, "bi_mid": 110965, "mu_mid": 120965, "kin_mid": 130965, "samp_mid": 140965, "tmid": 150965,
        "rho_gcc": 1.14, "E_GPa": 3.00, "nu": 0.38,
        "sigy_MPa": 80.0, "sigu_MPa": 85.0, "eps_f": 0.60,
        "ss_plastic": [
            (0.000, 80.0), (0.010, 82.0), (0.020, 83.0),
            (0.050, 82.0), (0.100, 81.0), (0.300, 83.0),
            (0.600, 85.0),
        ],
        "cte_ppmK": 80.0, "tc_WmK": 0.26, "cp_JkgK": 1670.0,
        "cs_C": 0.8, "cs_P": 4.5,
        "damping_zeta": 0.040,
        "desc": "Nylon 66 (Zytel 101), high-strength connectors",
        "ref": "DuPont Zytel 101 TDS",
    },
    {
        "name": "PBT_Crastin",
        "lin_mid": 100966, "bi_mid": 110966, "mu_mid": 120966, "kin_mid": 130966, "samp_mid": 140966, "tmid": 150966,
        "rho_gcc": 1.31, "E_GPa": 2.60, "nu": 0.38,
        "sigy_MPa": 60.0, "sigu_MPa": 65.0, "eps_f": 0.25,
        "ss_plastic": [
            (0.000, 60.0), (0.010, 62.0), (0.020, 63.0),
            (0.050, 62.0), (0.100, 61.0), (0.200, 64.0),
            (0.250, 65.0),
        ],
        "cte_ppmK": 75.0, "tc_WmK": 0.30, "cp_JkgK": 1450.0,
        "cs_C": 3.0, "cs_P": 3.5,
        "damping_zeta": 0.045,
        "desc": "Polybutylene Terephthalate, connectors, switches",
        "ref": "DuPont Crastin S600F20 TDS",
    },
    {
        "name": "POM_Delrin",
        "lin_mid": 100967, "bi_mid": 110967, "mu_mid": 120967, "kin_mid": 130967, "samp_mid": 140967, "tmid": 150967,
        "rho_gcc": 1.41, "E_GPa": 3.10, "nu": 0.35,
        "sigy_MPa": 72.0, "sigu_MPa": 78.0, "eps_f": 0.30,
        "ss_plastic": [
            (0.000, 72.0), (0.010, 74.0), (0.020, 76.0),
            (0.050, 75.0), (0.100, 74.0), (0.200, 76.0),
            (0.300, 78.0),
        ],
        "cte_ppmK": 110.0, "tc_WmK": 0.30, "cp_JkgK": 1470.0,
        "cs_C": 800.0, "cs_P": 2.0,
        "damping_zeta": 0.040,
        "desc": "Polyoxymethylene (Delrin), gears, slides",
        "ref": "DuPont Delrin 500P TDS",
    },
    {
        "name": "PP_Homo",
        "lin_mid": 100968, "bi_mid": 110968, "mu_mid": 120968, "kin_mid": 130968, "samp_mid": 140968, "tmid": 150968,
        "rho_gcc": 0.90, "E_GPa": 1.50, "nu": 0.42,
        "sigy_MPa": 35.0, "sigu_MPa": 40.0, "eps_f": 1.50,
        "ss_plastic": [
            (0.000, 35.0), (0.010, 36.0), (0.020, 36.5),
            (0.050, 35.5), (0.100, 34.0), (0.300, 35.0),
            (0.800, 38.0), (1.500, 40.0),
        ],
        "cte_ppmK": 150.0, "tc_WmK": 0.22, "cp_JkgK": 1920.0,
        "cs_C": 3.0, "cs_P": 3.5,
        "damping_zeta": 0.070,
        "desc": "Homopolymer Polypropylene, low-cost housings",
        "ref": "LyondellBasell Moplen TDS",
    },
]

REINFORCED_DB = [
    {
        "name": "PA66_GF30",
        "lin_mid": 100971, "bi_mid": 110971, "mu_mid": 120971, "kin_mid": 130971, "samp_mid": 140971, "tmid": 150971,
        "rho_gcc": 1.36, "E_GPa": 9.50, "nu": 0.37,
        "sigy_MPa": 180.0, "sigu_MPa": 195.0, "eps_f": 0.04,
        "ss_plastic": [
            (0.000, 180.0), (0.005, 185.0), (0.010, 190.0),
            (0.020, 193.0), (0.030, 194.0), (0.040, 195.0),
        ],
        "cte_ppmK": 25.0, "tc_WmK": 0.30, "cp_JkgK": 1400.0,
        "cs_C": 50.0, "cs_P": 2.0,
        "damping_zeta": 0.025,
        "desc": "PA66 + 30% Glass Fiber, high-strength connectors",
        "ref": "BASF Ultramid A3WG6 TDS, DuPont Zytel 70G30",
    },
    {
        "name": "PA66_GF50",
        "lin_mid": 100972, "bi_mid": 110972, "mu_mid": 120972, "kin_mid": 130972, "samp_mid": 140972, "tmid": 150972,
        "rho_gcc": 1.57, "E_GPa": 16.00, "nu": 0.36,
        "sigy_MPa": 230.0, "sigu_MPa": 250.0, "eps_f": 0.025,
        "ss_plastic": [
            (0.000, 230.0), (0.003, 238.0), (0.007, 244.0),
            (0.012, 247.0), (0.020, 249.0), (0.025, 250.0),
        ],
        "cte_ppmK": 18.0, "tc_WmK": 0.40, "cp_JkgK": 1350.0,
        "cs_C": 80.0, "cs_P": 2.0,
        "damping_zeta": 0.020,
        "desc": "PA66 + 50% Glass Fiber, structural parts",
        "ref": "BASF Ultramid A3WG10 TDS",
    },
    {
        "name": "PBT_GF30",
        "lin_mid": 100973, "bi_mid": 110973, "mu_mid": 120973, "kin_mid": 130973, "samp_mid": 140973, "tmid": 150973,
        "rho_gcc": 1.53, "E_GPa": 10.00, "nu": 0.37,
        "sigy_MPa": 130.0, "sigu_MPa": 145.0, "eps_f": 0.030,
        "ss_plastic": [
            (0.000, 130.0), (0.005, 136.0), (0.010, 140.0),
            (0.015, 142.0), (0.020, 144.0), (0.030, 145.0),
        ],
        "cte_ppmK": 30.0, "tc_WmK": 0.35, "cp_JkgK": 1350.0,
        "cs_C": 60.0, "cs_P": 2.5,
        "damping_zeta": 0.025,
        "desc": "PBT + 30% GF, electrical parts",
        "ref": "DuPont Crastin SK605 TDS",
    },
    {
        "name": "PPS_GF40",
        "lin_mid": 100974, "bi_mid": 110974, "mu_mid": 120974, "kin_mid": 130974, "samp_mid": 140974, "tmid": 150974,
        "rho_gcc": 1.66, "E_GPa": 14.00, "nu": 0.38,
        "sigy_MPa": 180.0, "sigu_MPa": 195.0, "eps_f": 0.020,
        "ss_plastic": [
            (0.000, 180.0), (0.004, 186.0), (0.008, 190.0),
            (0.012, 192.0), (0.016, 194.0), (0.020, 195.0),
        ],
        "cte_ppmK": 20.0, "tc_WmK": 0.35, "cp_JkgK": 1100.0,
        "cs_C": 150.0, "cs_P": 2.0,
        "damping_zeta": 0.020,
        "desc": "PPS + 40% GF, high-temperature structural",
        "ref": "Solvay Ryton R-4-02XT TDS",
    },
]

OPTICAL_DB = [
    {
        "name": "PMMA_Plexiglas",
        "lin_mid": 100981, "bi_mid": 110981, "mu_mid": 120981, "kin_mid": 130981, "samp_mid": 140981, "tmid": 150981,
        "rho_gcc": 1.19, "E_GPa": 3.00, "nu": 0.38,
        "sigy_MPa": 72.0, "sigu_MPa": 80.0, "eps_f": 0.05,
        "ss_plastic": [
            (0.000, 72.0), (0.005, 75.0), (0.010, 77.0),
            (0.020, 79.0), (0.030, 79.5), (0.050, 80.0),
        ],
        "cte_ppmK": 75.0, "tc_WmK": 0.19, "cp_JkgK": 1470.0,
        "cs_C": 50.0, "cs_P": 3.0,
        "damping_zeta": 0.030,
        "desc": "Polymethyl Methacrylate (Plexiglas), transparent, cheap lens",
        "ref": "Altuglas V825 TDS, Arkema Plexiglas V825-100",
    },
    {
        "name": "COP_Zeonex",
        "lin_mid": 100982, "bi_mid": 110982, "mu_mid": 120982, "kin_mid": 130982, "samp_mid": 140982, "tmid": 150982,
        "rho_gcc": 1.01, "E_GPa": 2.40, "nu": 0.37,
        "sigy_MPa": 68.0, "sigu_MPa": 72.0, "eps_f": 0.10,
        "ss_plastic": [
            (0.000, 68.0), (0.005, 69.5), (0.010, 70.5),
            (0.020, 71.5), (0.050, 72.0), (0.100, 72.0),
        ],
        "cte_ppmK": 70.0, "tc_WmK": 0.15, "cp_JkgK": 1800.0,
        "cs_C": 30.0, "cs_P": 3.0,
        "damping_zeta": 0.025,
        "desc": "Cyclic Olefin Polymer (Zeonex), smartphone camera lens (low birefringence)",
        "ref": "Zeon Zeonex E48R TDS, Japan Zeon CL",
    },
    {
        "name": "COC_TOPAS",
        "lin_mid": 100983, "bi_mid": 110983, "mu_mid": 120983, "kin_mid": 130983, "samp_mid": 140983, "tmid": 150983,
        "rho_gcc": 1.02, "E_GPa": 2.60, "nu": 0.37,
        "sigy_MPa": 63.0, "sigu_MPa": 66.0, "eps_f": 0.04,
        "ss_plastic": [
            (0.000, 63.0), (0.005, 64.5), (0.010, 65.5),
            (0.020, 66.0), (0.030, 66.0), (0.040, 66.0),
        ],
        "cte_ppmK": 60.0, "tc_WmK": 0.15, "cp_JkgK": 1750.0,
        "cs_C": 30.0, "cs_P": 3.0,
        "damping_zeta": 0.025,
        "desc": "Cyclic Olefin Copolymer (TOPAS), optical and medical",
        "ref": "TOPAS 5013 TDS, Polyplastics TOPAS",
    },
]

HIPERF_DB = [
    {
        "name": "PPS_Ryton",
        "lin_mid": 100975, "bi_mid": 110975, "mu_mid": 120975, "kin_mid": 130975, "samp_mid": 140975, "tmid": 150975,
        "rho_gcc": 1.35, "E_GPa": 3.80, "nu": 0.38,
        "sigy_MPa": 80.0, "sigu_MPa": 90.0, "eps_f": 0.02,
        "ss_plastic": [
            (0.000, 80.0), (0.005, 84.0), (0.010, 87.0),
            (0.015, 89.0), (0.020, 90.0),
        ],
        "cte_ppmK": 49.0, "tc_WmK": 0.29, "cp_JkgK": 1000.0,
        "cs_C": 100.0, "cs_P": 2.5,
        "damping_zeta": 0.025,
        "desc": "Polyphenylene Sulfide (Ryton), high-temp base resin",
        "ref": "Solvay Ryton PR06 TDS",
    },
    {
        "name": "PEEK_Victrex",
        "lin_mid": 100976, "bi_mid": 110976, "mu_mid": 120976, "kin_mid": 130976, "samp_mid": 140976, "tmid": 150976,
        "rho_gcc": 1.32, "E_GPa": 4.00, "nu": 0.39,
        "sigy_MPa": 98.0, "sigu_MPa": 115.0, "eps_f": 0.50,
        "ss_plastic": [
            (0.000, 98.0), (0.005, 103.0), (0.010, 106.0),
            (0.020, 109.0), (0.050, 108.0), (0.100, 107.0),
            (0.300, 112.0), (0.500, 115.0),
        ],
        "cte_ppmK": 47.0, "tc_WmK": 0.25, "cp_JkgK": 1340.0,
        "cs_C": 40.0, "cs_P": 2.0,
        "damping_zeta": 0.025,
        "desc": "Polyetheretherketone (PEEK), medical, aerospace",
        "ref": "Victrex PEEK 450G TDS: E=4.0 GPa, sigy=98 MPa, ISO 527",
    },
    {
        "name": "PEI_Ultem",
        "lin_mid": 100977, "bi_mid": 110977, "mu_mid": 120977, "kin_mid": 130977, "samp_mid": 140977, "tmid": 150977,
        "rho_gcc": 1.27, "E_GPa": 3.00, "nu": 0.36,
        "sigy_MPa": 105.0, "sigu_MPa": 110.0, "eps_f": 0.60,
        "ss_plastic": [
            (0.000, 105.0), (0.005, 107.0), (0.010, 109.0),
            (0.020, 110.0), (0.050, 109.0), (0.100, 108.0),
            (0.300, 109.0), (0.600, 110.0),
        ],
        "cte_ppmK": 56.0, "tc_WmK": 0.22, "cp_JkgK": 1200.0,
        "cs_C": 50.0, "cs_P": 2.5,
        "damping_zeta": 0.025,
        "desc": "Polyetherimide (Ultem 1000), high-temp electrical",
        "ref": "SABIC Ultem 1000 TDS",
    },
]

ALL_MATERIALS = {
    "Standard": STANDARD_DB,
    "Reinforced": REINFORCED_DB,
    "HighPerformance": HIPERF_DB,
    "Optical": OPTICAL_DB,
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
    lines.append("$ 5 mechanical variants per material:")
    lines.append("$   1. Linear (MAT_001)          1009xx — preview")
    lines.append("$   2. Bilinear iso (MAT_024)    1109xx — standard")
    lines.append("$   3. Multilinear iso (LCSS)    1209xx — precise")
    lines.append("$   4. Bilinear kin mixed (003)  1309xx — cyclic/Bauschinger")
    lines.append("$   5. SAMP-1 (MAT_187)          1409xx — advanced polymer")
    lines.append("$")
    lines.append("$ Cowper-Symonds strain-rate per material (literature).")
    lines.append("$")
    lines.append("$ !! ========================================================================")
    lines.append("$ !!  DATABASE CONVENTION")
    lines.append("$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID (MID),")
    lines.append("$ !!  NOT an actual Part ID. External tool must replace with real PIDs.")
    lines.append("$ !! ========================================================================")
    return lines


def write_mat001_linear(m):
    E = E_to_MPa(m["E_GPa"])
    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Linear (MID {m['lin_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Source: {m['ref']}")
    lines.append(f"$$ E={m['E_GPa']} GPa, nu={m['nu']}, rho={m['rho_gcc']} g/cc")
    lines.append("*MAT_ELASTIC_TITLE")
    lines.append(f"{m['name']} Linear")
    lines.append("$      MID        RO         E        PR")
    lines.append(
        f"{m['lin_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E:10.1f}"
        f"{m['nu']:10.4f}"
        f"       0.0       0.0       0.0"
    )
    return lines


def write_mat024_bilinear(m):
    sigy = m["sigy_MPa"]
    sigu = m["sigu_MPa"]
    eps_f = m["eps_f"]
    E = E_to_MPa(m["E_GPa"])
    eps_y = sigy / E
    etan = (sigu - sigy) / max(eps_f - eps_y, 1e-6)
    etan = max(etan, 1.0)

    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Bilinear Isotropic (MID {m['bi_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ sigy={sigy}, sigu={sigu}, eps_f={eps_f}")
    lines.append(f"$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = {etan:.1f} MPa")
    lines.append(f"$$ Cowper-Symonds: C={m['cs_C']}, P={m['cs_P']}")
    lines.append("*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE")
    lines.append(f"{m['name']} Bilinear")
    lines.append("$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL")
    lines.append(
        f"{m['bi_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E:10.1f}"
        f"{m['nu']:10.4f}"
        f"{sigy:10.2f}"
        f"{etan:10.2f}"
        f"{eps_f:10.4f}"
        f"{0.0:10.2f}"
    )
    lines.append("$        C         P      LCSS      LCSR        VP")
    lines.append(
        f"{m['cs_C']:10.1f}"
        f"{m['cs_P']:10.1f}"
        f"{0:10d}"
        f"{0:10d}"
        f"{1.0:10.1f}"
    )
    lines.append("$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8")
    lines.append("       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0")
    lines.append("$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8")
    lines.append("       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0")
    return lines


def write_define_curve(lcid, name, points):
    lines = []
    lines.append("*DEFINE_CURVE_TITLE")
    lines.append(f"{name} true stress vs plastic strain")
    lines.append("$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP")
    lines.append(
        f"{lcid:10d}"
        f"{0:10d}"
        f"{1.0:10.1f}"
        f"{1.0:10.1f}"
        f"{0.0:10.1f}"
        f"{0.0:10.1f}"
        f"{0:10d}"
    )
    for eps_p, stress in points:
        lines.append(f"{eps_p:20.10e}{stress:20.10e}")
    return lines


def write_mat024_multilinear(m):
    E = E_to_MPa(m["E_GPa"])
    lcid = m["mu_mid"]

    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Multilinear (MID {m['mu_mid']}) ---")
    lines.append(f"$$ LCSS curve: {len(m['ss_plastic'])} points, LCID={lcid}")
    lines.extend(write_define_curve(lcid, m["name"], m["ss_plastic"]))
    lines.append("$")
    lines.append("*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE")
    lines.append(f"{m['name']} Multilinear")
    lines.append("$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL")
    lines.append(
        f"{m['mu_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E:10.1f}"
        f"{m['nu']:10.4f}"
        f"{0.0:10.2f}"
        f"{0.0:10.2f}"
        f"{m['eps_f']:10.4f}"
        f"{0.0:10.2f}"
    )
    lines.append("$        C         P      LCSS      LCSR        VP")
    lines.append(
        f"{m['cs_C']:10.1f}"
        f"{m['cs_P']:10.1f}"
        f"{lcid:10d}"
        f"{0:10d}"
        f"{1.0:10.1f}"
    )
    return lines


def write_mat003_kinematic_mixed(m):
    sigy = m["sigy_MPa"]
    sigu = m["sigu_MPa"]
    eps_f = m["eps_f"]
    E = E_to_MPa(m["E_GPa"])
    eps_y = sigy / E
    etan = (sigu - sigy) / max(eps_f - eps_y, 1e-6)
    etan = max(etan, 1.0)

    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Kinematic Mixed BETA=0.5 (MID {m['kin_mid']}) ---")
    lines.append(f"$$ 50/50 isotropic/kinematic for cyclic loading")
    lines.append("*MAT_PLASTIC_KINEMATIC_TITLE")
    lines.append(f"{m['name']} Kinematic Mixed")
    lines.append("$      MID        RO         E        PR      SIGY      ETAN      BETA")
    lines.append(
        f"{m['kin_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E:10.1f}"
        f"{m['nu']:10.4f}"
        f"{sigy:10.2f}"
        f"{etan:10.2f}"
        f"{0.5:10.4f}"
    )
    lines.append("$      SRC       SRP        FS        VP")
    lines.append(
        f"{m['cs_C']:10.1f}"
        f"{m['cs_P']:10.1f}"
        f"{eps_f:10.4f}"
        f"{1.0:10.1f}"
    )
    return lines


def write_mat187_samp1(m):
    """
    Write MAT_SAMP-1 (MAT_187) simplified card.
    Note: SAMP-1 has 20+ parameters normally; we provide a basic setup
    with LCID-T (tension) and LCID-C (compression) using same curve as approximation.
    User should refine with measured data for accurate damage prediction.
    """
    E = E_to_MPa(m["E_GPa"])
    # Create two LCIDs: tension (+1000), compression (+2000)
    lcid_t = m["samp_mid"] + 10000  # e.g. 140961 -> 150961 — but this conflicts with TMID
    lcid_t = m["samp_mid"]  # reuse samp_mid as LCID (unique)
    lcid_c = m["samp_mid"] + 500000  # separate LCID for compression

    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} SAMP-1 Advanced (MID {m['samp_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ SAMP-1 polymer model with tension/compression asymmetry")
    lines.append(f"$$ Note: simplified — uses same curve for T and C (refine with measured data)")

    # Tension curve
    lines.extend(write_define_curve(lcid_t, f"{m['name']} SAMP-1 tension", m["ss_plastic"]))
    lines.append("$")
    # Compression curve (slightly higher, typical for polymers)
    comp_points = [(ep, s * 1.15) for (ep, s) in m["ss_plastic"]]
    lines.extend(write_define_curve(lcid_c, f"{m['name']} SAMP-1 compression", comp_points))
    lines.append("$")

    lines.append("*MAT_SAMP-1_TITLE")
    lines.append(f"{m['name']} SAMP-1")
    # Card 1: MID RO E NUE LCID-T NUEP LCID-C LCID-S
    lines.append("$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS")
    lines.append(
        f"{m['samp_mid']:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E:10.1f}"
        f"{m['nu']:10.4f}"
        f"{lcid_t:10d}"
        f"{0.0:10.4f}"
        f"{lcid_c:10d}"
        f"{0:10d}"
    )
    # Card 2: LCID-B NUEB LCEPS EPFAIL DEPRPT LCID-D LCID-P (simplified)
    lines.append("$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP")
    lines.append(
        f"{0:10d}"
        f"{0.0:10.4f}"
        f"{0:10d}"
        f"{m['eps_f']:10.4f}"
        f"{0.0:10.4f}"
        f"{0:10d}"
        f"{0:10d}"
    )
    # Card 3: FLAG DRATE (default)
    lines.append("$     FLAG     DRATE")
    lines.append(f"{0:10d}{0.0:10.4f}")
    return lines


def write_mat_thermal_isotropic(m):
    lines = []
    tc_out = tc_to_mWmmK(m["tc_WmK"])
    cp_out = cp_to_mm2s2K(m["cp_JkgK"])
    rho_out = rho_to_tonmm3(m["rho_gcc"])
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Thermal (TMID {m['tmid']}) ---")
    lines.append(f"$$ TC={m['tc_WmK']} W/m/K, Cp={m['cp_JkgK']} J/kg/K, CTE={m['cte_ppmK']} ppm/K")
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
    cte = cte_to_perK(m["cte_ppmK"])
    mids_labels = [
        (m["lin_mid"], "Linear"),
        (m["bi_mid"], "Bilinear"),
        (m["mu_mid"], "Multilinear"),
        (m["kin_mid"], "Kinematic"),
        (m["samp_mid"], "SAMP-1"),
    ]
    lines = []
    lines.append(f"$$ CTE={m['cte_ppmK']} ppm/K, applied to all 5 MIDs of {m['name']}")
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
    title = f"PLASTIC — {group_name}: Mechanical (MAT_001/024/003/187)"
    lines = header(title, group_name, group_desc, mid_range)
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append(
        "$   lin      bi       mu       kin      samp     Name                E(GPa)  sigy  sigu"
    )
    lines.append("$   " + "-" * 88)
    for m in materials:
        lines.append(
            f"$   {m['lin_mid']}  {m['bi_mid']}  {m['mu_mid']}  "
            f"{m['kin_mid']}  {m['samp_mid']}  {m['name']:20s}  "
            f"{m['E_GPa']:5.2f}  {m['sigy_MPa']:5.0f} {m['sigu_MPa']:5.0f}"
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
    lines.append("$ 2. BILINEAR ISOTROPIC (MAT_024)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat024_bilinear(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 3. MULTILINEAR ISOTROPIC (MAT_024 + LCSS)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat024_multilinear(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat003_kinematic_mixed(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 5. SAMP-1 ADVANCED POLYMER (MAT_187)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat187_samp1(m))
    lines.append("$")
    lines.append("*END")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_thermal_kfile(filepath):
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append("$ PLASTIC THERMAL PROPERTIES")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> temperature K")
    lines.append("$")
    lines.append("$ !! ========================================================================")
    lines.append("$ !!  DATABASE CONVENTION")
    lines.append("$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID (MID),")
    lines.append("$ !!  NOT an actual Part ID. Applied to all 5 MIDs per material.")
    lines.append("$ !! ========================================================================")
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append("$   TMID    Name                  CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)")
    lines.append("$   " + "-" * 65)
    for group, materials in ALL_MATERIALS.items():
        for m in materials:
            lines.append(
                f"$   {m['tmid']}  {m['name']:22s} "
                f"{m['cte_ppmK']:9.1f}  {m['tc_WmK']:8.3f}  {m['cp_JkgK']:8.1f}"
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
    omega_ref = 2.0 * math.pi * omega_ref_hz
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append("$ PLASTIC DAMPING LIBRARY (Rayleigh for all 5 variants)")
    lines.append("$ " + "=" * 72)
    lines.append(f"$ Reference frequency: {omega_ref_hz:.0f} Hz ({omega_ref:.1f} rad/s)")
    lines.append("$")
    lines.append("$ Damping ratios by plastic family:")
    lines.append("$   Amorphous glassy (PC, PEI):    2~3%")
    lines.append("$   Semi-crystalline (PA, POM):    3~5%")
    lines.append("$   ABS, PC/ABS (rubber phase):    4~6%")
    lines.append("$   GF-reinforced:                 2~3% (fiber reduces)")
    lines.append("$   PP (flexible):                 5~8%")
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
                ("bilinear", m["bi_mid"]),
                ("multilinear", m["mu_mid"]),
                ("kinematic", m["kin_mid"]),
                ("samp1", m["samp_mid"]),
            ]
            for label, mid in variants:
                psid = mid + 800000
                lines.append("$")
                lines.append(f"$$ --- {m['name']} ({label}, MID {mid}) ---")
                lines.append(f"$$ zeta={zeta:.4f} ({zeta*100:.2f}%) @ f_ref={omega_ref_hz:.0f} Hz")
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
    db = {}
    for group, materials in ALL_MATERIALS.items():
        db[group] = []
        for m in materials:
            entry = dict(m)
            entry["ss_plastic"] = [list(p) for p in m["ss_plastic"]]
            db[group].append(entry)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ============================================================
# Main
# ============================================================

def main():
    script_dir = Path(__file__).parent.resolve()

    std_path = script_dir / "plastic_standard.k"
    rnf_path = script_dir / "plastic_reinforced.k"
    hpf_path = script_dir / "plastic_hiperf.k"
    opt_path = script_dir / "plastic_optical.k"
    thermal_path = script_dir / "plastic_thermal.k"
    damping_path = script_dir / "plastic_damping.k"
    db_path = script_dir / "plastic_materials_db.json"

    write_mechanical_kfile(
        STANDARD_DB, std_path,
        group_name="Standard",
        group_desc="PC, ABS, PC/ABS, PA6, PA66, PBT, POM, PP",
        mid_range="100961~100968 (5 variants per material)",
    )
    write_mechanical_kfile(
        REINFORCED_DB, rnf_path,
        group_name="Reinforced",
        group_desc="PA66-GF30, PA66-GF50, PBT-GF30, PPS-GF40",
        mid_range="100971~100974 (5 variants per material)",
    )
    write_mechanical_kfile(
        HIPERF_DB, hpf_path,
        group_name="High-Performance",
        group_desc="PPS, PEEK, PEI",
        mid_range="100975~100977 (5 variants per material)",
    )
    write_mechanical_kfile(
        OPTICAL_DB, opt_path,
        group_name="Optical",
        group_desc="PMMA, COP (Zeonex), COC (TOPAS) — camera lens",
        mid_range="100981~100983 (5 variants per material)",
    )
    write_thermal_kfile(thermal_path)
    write_damping_kfile(damping_path)
    write_db_json(db_path)

    total = sum(len(v) for v in ALL_MATERIALS.values())
    print("=" * 65)
    print("  Plastic Material Library Generated")
    print("=" * 65)
    for group, materials in ALL_MATERIALS.items():
        print(f"  {group:20s}: {len(materials):2d} materials")
    print(f"  TOTAL: {total} materials x 5 mech variants = {total*5} mechanical cards")
    print(f"  + {total} thermal + {total*5} damping part sets")
    print()
    print("  Output files:")
    for p in [std_path, rnf_path, hpf_path, opt_path, thermal_path, damping_path, db_path]:
        sz = p.stat().st_size if p.exists() else 0
        print(f"    {p.name:35s}  {sz:7d} bytes")

    # Per-material summary
    print()
    print("=" * 95)
    print(f"  {'lin':>6s} {'bi':>6s} {'mu':>6s} {'kin':>6s} {'samp':>6s}  {'Name':22s} "
          f"{'E':>6s} {'sigy':>6s} {'C':>7s} {'P':>5s}")
    print("  " + "-" * 93)
    for group, materials in ALL_MATERIALS.items():
        for m in materials:
            print(
                f"  {m['lin_mid']:6d} {m['bi_mid']:6d} {m['mu_mid']:6d} "
                f"{m['kin_mid']:6d} {m['samp_mid']:6d}  "
                f"{m['name']:22s} {m['E_GPa']:6.2f} {m['sigy_MPa']:6.0f} "
                f"{m['cs_C']:7.1f} {m['cs_P']:5.2f}"
            )


if __name__ == "__main__":
    main()
