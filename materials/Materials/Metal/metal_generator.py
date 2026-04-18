#!/usr/bin/env python3
"""
Metal Material Library Generator for LS-DYNA
==============================================
Produces sus.k / al.k / ti.k (mechanical) and metal_thermal.k (thermal)
from an embedded material database.

Output files:
  sus.k            — SUS grades, bilinear + multi-linear LCSS (MAT_024)
  al.k             — Al grades, bilinear + multi-linear LCSS (MAT_024)
  ti.k             — Ti grades, bilinear + multi-linear LCSS (MAT_024)
  metal_thermal.k  — *MAT_THERMAL_ISOTROPIC + *MAT_ADD_THERMAL_EXPANSION
  metal_materials_db.json — parsed database

Unit system: mm, s, ton
  rho: ton/mm^3      = g/cc * 1e-9
  E, sigma: MPa      = N/mm^2
  Cp: mm^2/s^2/K     = J/kg/K * 1e6
  TC: mW/mm/K        = W/m/K * 1.0
  CTE: 1/K           = ppm/K * 1e-6

Data sources:
  - ASM Handbook Vol 2 (Nonferrous Alloys)
  - MatWeb material database
  - Kaiser/Alcoa aluminum TDS
  - POSCO/Kobelco stainless catalog
  - Timet titanium TDS
  - ASTM B209/B265/A240, JIS G 4304
"""

import os
import json
from pathlib import Path

# ============================================================
# Cowper-Symonds strain-rate constants per material family
# ============================================================
# Source summary:
#   Cowper-Symonds (1957):        mild steel     C=40,   P=5
#   Jones 1989:                    Al solid-sol   C=6500, P=4
#                                  SUS 304         C=100,  P=10
#                                  CP Ti           C=120,  P=9
#   Bodner-Partom (1975):          Al precipit.   ~rate-insensitive
#   Hsu & Jones (2004):            SUS 316L        C=50,   P=5
#   Meyer & Kleponis (2001):       Ti-6Al-4V      C=255,  P=2
#
# Key principle:
#   FCC solid-solution Al (1xxx,3xxx,5xxx): significant rate-sensitivity  → C=6500
#   FCC precipitation Al (2xxx,6xxx,7xxx):  near rate-insensitive         → C large
#   Die cast Al-Si:                        intermediate                  → C~1500
#   FCC austenitic SUS (201,301,304,316):  moderate rate sensitivity     → C=100
#   Low-C 316L:                            slightly higher                → C=50
#   BCC martensitic/ferritic SUS:          mild-steel-like               → C=40, P=5
#   Precipitation martensitic (17-4PH):    low rate-sensitivity          → C=3200, P=5
#   CP Titanium (Gr1/2/4):                 HCP, moderate                  → C=120, P=9
#   Ti-6Al-4V alpha-beta:                  different mechanism           → C=255, P=2
#
# For rate-insensitive materials, set C very large so sigma scaling ~ 1
# (sigma_dyn/sigma_y = 1 + (rate/C)^(1/P) -> 1 when C >> rate)
CS_AL_SOLID_SOL = {"C": 6500.0, "P": 4.0}       # Jones 1989
CS_AL_PRECIP = {"C": 1288000.0, "P": 4.0}       # Bodner-Partom 1975 (near-insensitive)
CS_AL_DIECAST = {"C": 1500.0, "P": 4.0}         # Intermediate (ADC12, A380)
CS_SUS_AUSTENITIC = {"C": 100.0, "P": 10.0}     # Jones 1989 (304, 316)
CS_SUS_316L = {"C": 50.0, "P": 5.0}             # Hsu & Jones 2004
CS_SUS_BCC = {"C": 40.0, "P": 5.0}              # Mild-steel-like (410, 420, 430)
CS_SUS_PH = {"C": 3200.0, "P": 5.0}             # 17-4PH, low sensitivity
CS_TI_CP = {"C": 120.0, "P": 9.0}               # Jones 1989
CS_TI_64 = {"C": 255.0, "P": 2.0}               # Meyer & Kleponis 2001

# Additional families
CS_MG = {"C": 4800.0, "P": 4.0}                 # Mg alloys (HCP, Jones 1989 analogue)
CS_STEEL_MILD = {"C": 40.0, "P": 5.0}           # Cowper-Symonds 1957 original
CS_STEEL_MEDIUM = {"C": 802.0, "P": 3.585}      # S45C / 0.45%C (Hsu 2004)
CS_BRASS = {"C": 1400.0, "P": 5.0}              # Cu-Zn alloys
CS_BRONZE = {"C": 1800.0, "P": 5.0}             # Cu-Sn alloys
CS_INCONEL = {"C": 17200.0, "P": 3.0}           # Ni-base superalloys (rate-insensitive)

# Default fallback
CS_ALUMINUM = CS_AL_SOLID_SOL
CS_STAINLESS = CS_SUS_AUSTENITIC
CS_TITANIUM = CS_TI_CP

# ============================================================
# Material Database
# ============================================================
# Format per material:
#   name, bi_mid, multi_mid, tmid, group, temper,
#   rho_gcc, E_GPa, nu, sigy_MPa, sigu_MPa, eps_f (uniform elong),
#   stress_strain_plastic: list of (eps_p, stress_MPa) pairs,
#   cte_ppmK, tc_WmK, cp_JkgK,
#   cs: Cowper-Symonds dict,
#   desc: description, ref: source

SUS_DB = [
    {
        "name": "SUS201_annealed",
        "bi_mid": 100501, "multi_mid": 110501, "tmid": 120501,
        "temper": "Annealed",
        "rho_gcc": 7.80, "E_GPa": 200.0, "nu": 0.30,
        "sigy_MPa": 260.0, "sigu_MPa": 655.0, "eps_f": 0.40,
        "ss_plastic": [
            (0.000, 260.0), (0.020, 340.0), (0.050, 420.0),
            (0.100, 510.0), (0.200, 600.0), (0.300, 640.0),
            (0.400, 655.0),
        ],
        "cte_ppmK": 16.9, "tc_WmK": 16.2, "cp_JkgK": 500.0,
        "cs": CS_SUS_AUSTENITIC,
        "damping_zeta": 0.005,
        "desc": "Low-Ni austenitic, economic grade",
        "ref": "ASTM A666, AISI 201, MatWeb",
    },
    {
        "name": "SUS301_annealed",
        "bi_mid": 100502, "multi_mid": 110502, "tmid": 120502,
        "temper": "Annealed",
        "rho_gcc": 7.88, "E_GPa": 193.0, "nu": 0.30,
        "sigy_MPa": 275.0, "sigu_MPa": 690.0, "eps_f": 0.40,
        "ss_plastic": [
            (0.000, 275.0), (0.020, 360.0), (0.050, 445.0),
            (0.100, 535.0), (0.200, 625.0), (0.300, 675.0),
            (0.400, 690.0),
        ],
        "cte_ppmK": 16.9, "tc_WmK": 16.2, "cp_JkgK": 500.0,
        "cs": CS_SUS_AUSTENITIC,
        "damping_zeta": 0.005,
        "desc": "High-strength spring austenitic",
        "ref": "AISI 301, ASM Handbook",
    },
    {
        "name": "SUS304_annealed",
        "bi_mid": 100503, "multi_mid": 110503, "tmid": 120503,
        "temper": "Annealed",
        "rho_gcc": 8.00, "E_GPa": 193.0, "nu": 0.29,
        "sigy_MPa": 215.0, "sigu_MPa": 505.0, "eps_f": 0.40,
        "ss_plastic": [
            (0.000, 215.0), (0.020, 280.0), (0.050, 340.0),
            (0.100, 400.0), (0.200, 460.0), (0.300, 490.0),
            (0.400, 505.0),
        ],
        "cte_ppmK": 17.3, "tc_WmK": 16.2, "cp_JkgK": 500.0,
        "cs": CS_SUS_AUSTENITIC,
        "damping_zeta": 0.005,
        "desc": "Most common austenitic stainless steel",
        "ref": "AISI 304, ASTM A240, MatWeb",
    },
    {
        "name": "SUS304L_annealed",
        "bi_mid": 100504, "multi_mid": 110504, "tmid": 120504,
        "temper": "Annealed",
        "rho_gcc": 8.00, "E_GPa": 193.0, "nu": 0.29,
        "sigy_MPa": 205.0, "sigu_MPa": 485.0, "eps_f": 0.40,
        "ss_plastic": [
            (0.000, 205.0), (0.020, 265.0), (0.050, 325.0),
            (0.100, 380.0), (0.200, 440.0), (0.300, 470.0),
            (0.400, 485.0),
        ],
        "cte_ppmK": 17.3, "tc_WmK": 16.2, "cp_JkgK": 500.0,
        "cs": CS_SUS_AUSTENITIC,
        "damping_zeta": 0.005,
        "desc": "Low-carbon 304, weld-friendly",
        "ref": "AISI 304L, ASTM A240",
    },
    {
        "name": "SUS316_annealed",
        "bi_mid": 100505, "multi_mid": 110505, "tmid": 120505,
        "temper": "Annealed",
        "rho_gcc": 8.00, "E_GPa": 193.0, "nu": 0.30,
        "sigy_MPa": 240.0, "sigu_MPa": 550.0, "eps_f": 0.40,
        "ss_plastic": [
            (0.000, 240.0), (0.020, 310.0), (0.050, 375.0),
            (0.100, 440.0), (0.200, 510.0), (0.300, 540.0),
            (0.400, 550.0),
        ],
        "cte_ppmK": 16.0, "tc_WmK": 15.9, "cp_JkgK": 500.0,
        "cs": CS_SUS_AUSTENITIC,
        "damping_zeta": 0.005,
        "desc": "Mo-bearing austenitic, corrosion resistant",
        "ref": "AISI 316, ASTM A240",
    },
    {
        "name": "SUS316L_annealed",
        "bi_mid": 100506, "multi_mid": 110506, "tmid": 120506,
        "temper": "Annealed",
        "rho_gcc": 8.00, "E_GPa": 193.0, "nu": 0.30,
        "sigy_MPa": 220.0, "sigu_MPa": 520.0, "eps_f": 0.40,
        "ss_plastic": [
            (0.000, 220.0), (0.020, 285.0), (0.050, 345.0),
            (0.100, 410.0), (0.200, 475.0), (0.300, 510.0),
            (0.400, 520.0),
        ],
        "cte_ppmK": 16.0, "tc_WmK": 15.9, "cp_JkgK": 500.0,
        "cs": CS_SUS_316L,
        "damping_zeta": 0.005,
        "desc": "Low-carbon 316, medical/weld",
        "ref": "AISI 316L, ASTM A240, Hsu&Jones 2004 (CS)",
    },
    {
        "name": "SUS410_annealed",
        "bi_mid": 100507, "multi_mid": 110507, "tmid": 120507,
        "temper": "Annealed",
        "rho_gcc": 7.74, "E_GPa": 200.0, "nu": 0.30,
        "sigy_MPa": 275.0, "sigu_MPa": 485.0, "eps_f": 0.22,
        "ss_plastic": [
            (0.000, 275.0), (0.020, 350.0), (0.050, 410.0),
            (0.100, 450.0), (0.150, 475.0), (0.220, 485.0),
        ],
        "cte_ppmK": 10.4, "tc_WmK": 24.9, "cp_JkgK": 460.0,
        "cs": CS_SUS_BCC,
        "damping_zeta": 0.003,
        "desc": "Martensitic, hardenable",
        "ref": "AISI 410, ASTM A240",
    },
    {
        "name": "SUS420_annealed",
        "bi_mid": 100508, "multi_mid": 110508, "tmid": 120508,
        "temper": "Annealed",
        "rho_gcc": 7.75, "E_GPa": 200.0, "nu": 0.29,
        "sigy_MPa": 345.0, "sigu_MPa": 655.0, "eps_f": 0.20,
        "ss_plastic": [
            (0.000, 345.0), (0.020, 440.0), (0.050, 520.0),
            (0.100, 585.0), (0.150, 630.0), (0.200, 655.0),
        ],
        "cte_ppmK": 10.3, "tc_WmK": 24.9, "cp_JkgK": 460.0,
        "cs": CS_SUS_BCC,
        "damping_zeta": 0.003,
        "desc": "High-C martensitic, knife/mold",
        "ref": "AISI 420, ASM Handbook",
    },
    {
        "name": "SUS430_annealed",
        "bi_mid": 100509, "multi_mid": 110509, "tmid": 120509,
        "temper": "Annealed",
        "rho_gcc": 7.70, "E_GPa": 200.0, "nu": 0.30,
        "sigy_MPa": 205.0, "sigu_MPa": 450.0, "eps_f": 0.22,
        "ss_plastic": [
            (0.000, 205.0), (0.020, 275.0), (0.050, 340.0),
            (0.100, 395.0), (0.150, 430.0), (0.220, 450.0),
        ],
        "cte_ppmK": 10.4, "tc_WmK": 26.1, "cp_JkgK": 460.0,
        "cs": CS_SUS_BCC,
        "damping_zeta": 0.004,
        "desc": "Ferritic, magnetic",
        "ref": "AISI 430, ASTM A240",
    },
    {
        "name": "SUS_17-4PH_H900",
        "bi_mid": 100510, "multi_mid": 110510, "tmid": 120510,
        "temper": "H900 (aged)",
        "rho_gcc": 7.80, "E_GPa": 196.0, "nu": 0.272,
        "sigy_MPa": 1170.0, "sigu_MPa": 1310.0, "eps_f": 0.14,
        "ss_plastic": [
            (0.000, 1170.0), (0.010, 1220.0), (0.020, 1250.0),
            (0.050, 1285.0), (0.100, 1305.0), (0.140, 1310.0),
        ],
        "cte_ppmK": 10.8, "tc_WmK": 17.9, "cp_JkgK": 460.0,
        "cs": CS_SUS_PH,
        "damping_zeta": 0.003,
        "desc": "Precipitation hardening, high strength",
        "ref": "AMS 5643, ASM Handbook",
    },
]

AL_DB = [
    {
        "name": "Al1050-O",
        "bi_mid": 100521, "multi_mid": 110521, "tmid": 120521,
        "temper": "O (annealed)",
        "rho_gcc": 2.705, "E_GPa": 69.0, "nu": 0.33,
        "sigy_MPa": 28.0, "sigu_MPa": 76.0, "eps_f": 0.36,
        "ss_plastic": [
            (0.000, 28.0), (0.020, 40.0), (0.050, 52.0),
            (0.100, 62.0), (0.200, 72.0), (0.360, 76.0),
        ],
        "cte_ppmK": 23.6, "tc_WmK": 229.0, "cp_JkgK": 900.0,
        "cs": CS_AL_SOLID_SOL,
        "damping_zeta": 0.008,
        "desc": "Pure Al annealed, reflector grade",
        "ref": "Al Association, MatWeb",
    },
    {
        "name": "Al1100-O",
        "bi_mid": 100522, "multi_mid": 110522, "tmid": 120522,
        "temper": "O (annealed)",
        "rho_gcc": 2.71, "E_GPa": 69.0, "nu": 0.33,
        "sigy_MPa": 34.0, "sigu_MPa": 90.0, "eps_f": 0.35,
        "ss_plastic": [
            (0.000, 34.0), (0.020, 48.0), (0.050, 62.0),
            (0.100, 73.0), (0.200, 84.0), (0.350, 90.0),
        ],
        "cte_ppmK": 23.6, "tc_WmK": 222.0, "cp_JkgK": 904.0,
        "cs": CS_AL_SOLID_SOL,
        "damping_zeta": 0.008,
        "desc": "Commercial pure Al, foil and sheet",
        "ref": "ASTM B209, Al Assoc",
    },
    {
        "name": "Al2024-T3",
        "bi_mid": 100523, "multi_mid": 110523, "tmid": 120523,
        "temper": "T3",
        "rho_gcc": 2.78, "E_GPa": 73.1, "nu": 0.33,
        "sigy_MPa": 345.0, "sigu_MPa": 483.0, "eps_f": 0.18,
        "ss_plastic": [
            (0.000, 345.0), (0.005, 385.0), (0.010, 410.0),
            (0.020, 435.0), (0.050, 465.0), (0.100, 478.0),
            (0.180, 483.0),
        ],
        "cte_ppmK": 23.2, "tc_WmK": 121.0, "cp_JkgK": 875.0,
        "cs": CS_AL_PRECIP,
        "damping_zeta": 0.003,
        "desc": "Al-Cu aerospace alloy",
        "ref": "ASTM B209, MIL-HDBK-5; Bodner-Partom (rate-insensitive)",
    },
    {
        "name": "Al3003-H14",
        "bi_mid": 100524, "multi_mid": 110524, "tmid": 120524,
        "temper": "H14 (half-hard)",
        "rho_gcc": 2.73, "E_GPa": 68.9, "nu": 0.33,
        "sigy_MPa": 145.0, "sigu_MPa": 150.0, "eps_f": 0.10,
        "ss_plastic": [
            (0.000, 145.0), (0.010, 148.0), (0.030, 149.0),
            (0.050, 150.0), (0.080, 150.0), (0.100, 150.0),
        ],
        "cte_ppmK": 23.2, "tc_WmK": 159.0, "cp_JkgK": 893.0,
        "cs": CS_AL_SOLID_SOL,
        "damping_zeta": 0.006,
        "desc": "Al-Mn, roofing and radiator",
        "ref": "ASTM B209",
    },
    {
        "name": "Al5052-H32",
        "bi_mid": 100525, "multi_mid": 110525, "tmid": 120525,
        "temper": "H32 (strain-hardened)",
        "rho_gcc": 2.68, "E_GPa": 70.3, "nu": 0.33,
        "sigy_MPa": 193.0, "sigu_MPa": 228.0, "eps_f": 0.12,
        "ss_plastic": [
            (0.000, 193.0), (0.010, 205.0), (0.020, 213.0),
            (0.050, 222.0), (0.080, 226.0), (0.120, 228.0),
        ],
        "cte_ppmK": 23.8, "tc_WmK": 138.0, "cp_JkgK": 880.0,
        "cs": CS_AL_SOLID_SOL,
        "damping_zeta": 0.008,
        "desc": "Al-Mg marine grade",
        "ref": "ASTM B209",
    },
    {
        "name": "Al5083-H116",
        "bi_mid": 100526, "multi_mid": 110526, "tmid": 120526,
        "temper": "H116",
        "rho_gcc": 2.66, "E_GPa": 70.3, "nu": 0.33,
        "sigy_MPa": 215.0, "sigu_MPa": 305.0, "eps_f": 0.16,
        "ss_plastic": [
            (0.000, 215.0), (0.005, 240.0), (0.010, 258.0),
            (0.020, 275.0), (0.050, 293.0), (0.100, 303.0),
            (0.160, 305.0),
        ],
        "cte_ppmK": 23.8, "tc_WmK": 117.0, "cp_JkgK": 900.0,
        "cs": CS_AL_SOLID_SOL,
        "damping_zeta": 0.008,
        "desc": "High-strength Al-Mg, LNG tanks",
        "ref": "ASTM B928",
    },
    {
        "name": "Al6061-T6",
        "bi_mid": 100535, "multi_mid": 110535, "tmid": 120535,
        "temper": "T6",
        "rho_gcc": 2.70, "E_GPa": 68.9, "nu": 0.33,
        "sigy_MPa": 276.0, "sigu_MPa": 310.0, "eps_f": 0.12,
        "ss_plastic": [
            (0.000, 276.0), (0.005, 289.0), (0.010, 296.0),
            (0.020, 302.0), (0.050, 308.0), (0.100, 310.0),
            (0.120, 310.0),
        ],
        "cte_ppmK": 23.4, "tc_WmK": 167.0, "cp_JkgK": 896.0,
        "cs": CS_AL_PRECIP,
        "damping_zeta": 0.003,
        "desc": "Al-Mg-Si general structural (most common)",
        "ref": "ASTM B209, MIL-HDBK-5; precipitation hardened rate-insensitive",
    },
    {
        "name": "Al6063-T5",
        "bi_mid": 100536, "multi_mid": 110536, "tmid": 120536,
        "temper": "T5",
        "rho_gcc": 2.70, "E_GPa": 68.9, "nu": 0.33,
        "sigy_MPa": 145.0, "sigu_MPa": 186.0, "eps_f": 0.12,
        "ss_plastic": [
            (0.000, 145.0), (0.005, 158.0), (0.010, 168.0),
            (0.020, 176.0), (0.050, 183.0), (0.100, 186.0),
            (0.120, 186.0),
        ],
        "cte_ppmK": 23.4, "tc_WmK": 201.0, "cp_JkgK": 900.0,
        "cs": CS_AL_PRECIP,
        "damping_zeta": 0.003,
        "desc": "Extrusion alloy, windows/frames",
        "ref": "ASTM B221",
    },
    {
        "name": "Al6063-T6",
        "bi_mid": 100537, "multi_mid": 110537, "tmid": 120537,
        "temper": "T6",
        "rho_gcc": 2.70, "E_GPa": 68.9, "nu": 0.33,
        "sigy_MPa": 214.0, "sigu_MPa": 241.0, "eps_f": 0.12,
        "ss_plastic": [
            (0.000, 214.0), (0.005, 225.0), (0.010, 232.0),
            (0.020, 237.0), (0.050, 240.0), (0.100, 241.0),
            (0.120, 241.0),
        ],
        "cte_ppmK": 23.4, "tc_WmK": 201.0, "cp_JkgK": 900.0,
        "cs": CS_AL_PRECIP,
        "damping_zeta": 0.003,
        "desc": "T6 heat-treated 6063 extrusion",
        "ref": "ASTM B221",
    },
    {
        "name": "Al7050-T7451",
        "bi_mid": 100538, "multi_mid": 110538, "tmid": 120538,
        "temper": "T7451",
        "rho_gcc": 2.83, "E_GPa": 71.7, "nu": 0.33,
        "sigy_MPa": 469.0, "sigu_MPa": 524.0, "eps_f": 0.11,
        "ss_plastic": [
            (0.000, 469.0), (0.005, 492.0), (0.010, 505.0),
            (0.020, 515.0), (0.050, 521.0), (0.100, 524.0),
            (0.110, 524.0),
        ],
        "cte_ppmK": 23.5, "tc_WmK": 157.0, "cp_JkgK": 860.0,
        "cs": CS_AL_PRECIP,
        "damping_zeta": 0.003,
        "desc": "Al-Zn aerospace, stress-corrosion resistant",
        "ref": "ASTM B209, MIL-HDBK-5",
    },
    {
        "name": "Al7075-T6",
        "bi_mid": 100539, "multi_mid": 110539, "tmid": 120539,
        "temper": "T6",
        "rho_gcc": 2.81, "E_GPa": 71.7, "nu": 0.33,
        "sigy_MPa": 503.0, "sigu_MPa": 572.0, "eps_f": 0.11,
        "ss_plastic": [
            (0.000, 503.0), (0.005, 528.0), (0.010, 543.0),
            (0.020, 555.0), (0.050, 567.0), (0.100, 572.0),
            (0.110, 572.0),
        ],
        "cte_ppmK": 23.6, "tc_WmK": 130.0, "cp_JkgK": 960.0,
        "cs": CS_AL_PRECIP,
        "damping_zeta": 0.003,
        "desc": "Highest-strength Al-Zn aerospace",
        "ref": "ASTM B209, MIL-HDBK-5",
    },
    {
        "name": "ADC12_diecast",
        "bi_mid": 100540, "multi_mid": 110540, "tmid": 120540,
        "temper": "As-cast",
        "rho_gcc": 2.70, "E_GPa": 71.0, "nu": 0.33,
        "sigy_MPa": 150.0, "sigu_MPa": 310.0, "eps_f": 0.025,
        "ss_plastic": [
            (0.000, 150.0), (0.005, 220.0), (0.010, 260.0),
            (0.015, 285.0), (0.020, 300.0), (0.025, 310.0),
        ],
        "cte_ppmK": 21.0, "tc_WmK": 96.0, "cp_JkgK": 963.0,
        "cs": CS_AL_DIECAST,
        "damping_zeta": 0.015,
        "desc": "Die-cast Al-Si-Cu (smartphone frames)",
        "ref": "JIS H 5302, Nadca handbook; porosity raises damping",
    },
]

TI_DB = [
    {
        "name": "Ti_Grade1",
        "bi_mid": 100561, "multi_mid": 110561, "tmid": 120561,
        "temper": "Annealed",
        "rho_gcc": 4.51, "E_GPa": 105.0, "nu": 0.34,
        "sigy_MPa": 170.0, "sigu_MPa": 240.0, "eps_f": 0.24,
        "ss_plastic": [
            (0.000, 170.0), (0.010, 195.0), (0.030, 215.0),
            (0.060, 228.0), (0.120, 236.0), (0.240, 240.0),
        ],
        "cte_ppmK": 8.6, "tc_WmK": 16.4, "cp_JkgK": 523.0,
        "cs": CS_TI_CP,
        "damping_zeta": 0.005,
        "desc": "CP Ti, softest, medical",
        "ref": "ASTM B265 Grade 1",
    },
    {
        "name": "Ti_Grade2",
        "bi_mid": 100562, "multi_mid": 110562, "tmid": 120562,
        "temper": "Annealed",
        "rho_gcc": 4.51, "E_GPa": 105.0, "nu": 0.34,
        "sigy_MPa": 275.0, "sigu_MPa": 345.0, "eps_f": 0.20,
        "ss_plastic": [
            (0.000, 275.0), (0.010, 300.0), (0.030, 320.0),
            (0.060, 335.0), (0.120, 342.0), (0.200, 345.0),
        ],
        "cte_ppmK": 8.6, "tc_WmK": 16.4, "cp_JkgK": 523.0,
        "cs": CS_TI_CP,
        "damping_zeta": 0.005,
        "desc": "CP Ti, most common commercial grade",
        "ref": "ASTM B265 Grade 2",
    },
    {
        "name": "Ti_Grade4",
        "bi_mid": 100563, "multi_mid": 110563, "tmid": 120563,
        "temper": "Annealed",
        "rho_gcc": 4.51, "E_GPa": 105.0, "nu": 0.34,
        "sigy_MPa": 480.0, "sigu_MPa": 550.0, "eps_f": 0.15,
        "ss_plastic": [
            (0.000, 480.0), (0.010, 505.0), (0.030, 525.0),
            (0.060, 540.0), (0.100, 547.0), (0.150, 550.0),
        ],
        "cte_ppmK": 8.6, "tc_WmK": 16.4, "cp_JkgK": 523.0,
        "cs": CS_TI_CP,
        "damping_zeta": 0.005,
        "desc": "High-strength CP Ti",
        "ref": "ASTM B265 Grade 4",
    },
    {
        "name": "Ti6Al4V_Grade5",
        "bi_mid": 100564, "multi_mid": 110564, "tmid": 120564,
        "temper": "Annealed",
        "rho_gcc": 4.43, "E_GPa": 113.8, "nu": 0.342,
        "sigy_MPa": 880.0, "sigu_MPa": 950.0, "eps_f": 0.14,
        "ss_plastic": [
            (0.000, 880.0), (0.005, 905.0), (0.010, 920.0),
            (0.020, 935.0), (0.050, 945.0), (0.100, 950.0),
            (0.140, 950.0),
        ],
        "cte_ppmK": 8.6, "tc_WmK": 6.7, "cp_JkgK": 526.3,
        "cs": CS_TI_64,
        "damping_zeta": 0.003,
        "desc": "Ti-6Al-4V workhorse alpha-beta alloy",
        "ref": "ASTM B265 Grade 5, MIL-HDBK-5; Meyer&Kleponis 2001 (CS)",
    },
    {
        "name": "Ti6Al4V_Grade5_ELI",
        "bi_mid": 100565, "multi_mid": 110565, "tmid": 120565,
        "temper": "Annealed ELI",
        "rho_gcc": 4.43, "E_GPa": 113.8, "nu": 0.342,
        "sigy_MPa": 795.0, "sigu_MPa": 860.0, "eps_f": 0.14,
        "ss_plastic": [
            (0.000, 795.0), (0.005, 820.0), (0.010, 835.0),
            (0.020, 848.0), (0.050, 857.0), (0.100, 860.0),
            (0.140, 860.0),
        ],
        "cte_ppmK": 8.6, "tc_WmK": 6.7, "cp_JkgK": 526.3,
        "cs": CS_TI_64,
        "damping_zeta": 0.003,
        "desc": "Extra-Low Interstitial Ti-6Al-4V, medical implant",
        "ref": "ASTM F136, ASTM B348 Gr 23",
    },
    {
        "name": "Ti3Al2.5V_Grade9",
        "bi_mid": 100566, "multi_mid": 110566, "tmid": 120566,
        "temper": "Annealed",
        "rho_gcc": 4.48, "E_GPa": 100.0, "nu": 0.30,
        "sigy_MPa": 485.0, "sigu_MPa": 620.0, "eps_f": 0.15,
        "ss_plastic": [
            (0.000, 485.0), (0.010, 540.0), (0.020, 575.0),
            (0.050, 605.0), (0.100, 618.0), (0.150, 620.0),
        ],
        "cte_ppmK": 9.4, "tc_WmK": 8.3, "cp_JkgK": 540.0,
        "cs": CS_TI_CP,
        "damping_zeta": 0.004,
        "desc": "Ti-3Al-2.5V, bicycle/tubing grade",
        "ref": "ASTM B338 Grade 9",
    },
]

MG_DB = [
    {
        "name": "Mg_AZ31B_H24",
        "bi_mid": 100581, "multi_mid": 110581, "tmid": 120581,
        "temper": "H24",
        "rho_gcc": 1.77, "E_GPa": 45.0, "nu": 0.35,
        "sigy_MPa": 220.0, "sigu_MPa": 290.0, "eps_f": 0.15,
        "ss_plastic": [
            (0.000, 220.0), (0.010, 240.0), (0.020, 255.0),
            (0.050, 275.0), (0.100, 285.0), (0.150, 290.0),
        ],
        "cte_ppmK": 26.0, "tc_WmK": 96.0, "cp_JkgK": 1024.0,
        "cs": CS_MG,
        "damping_zeta": 0.010,
        "desc": "Wrought Mg-Al-Zn, most common sheet grade (smartphone midframe)",
        "ref": "ASTM B90 AZ31B-H24, ASM Handbook Vol 2",
    },
    {
        "name": "Mg_AZ91D_diecast",
        "bi_mid": 100582, "multi_mid": 110582, "tmid": 120582,
        "temper": "As-cast",
        "rho_gcc": 1.81, "E_GPa": 45.0, "nu": 0.35,
        "sigy_MPa": 160.0, "sigu_MPa": 230.0, "eps_f": 0.03,
        "ss_plastic": [
            (0.000, 160.0), (0.005, 185.0), (0.010, 200.0),
            (0.015, 215.0), (0.020, 223.0), (0.030, 230.0),
        ],
        "cte_ppmK": 26.0, "tc_WmK": 72.0, "cp_JkgK": 1020.0,
        "cs": CS_MG,
        "damping_zeta": 0.015,
        "desc": "Die-cast Mg-Al-Zn, laptop/phone housings",
        "ref": "ASTM B94 AZ91D, NADCA standards",
    },
    {
        "name": "Mg_ZK60A_T5",
        "bi_mid": 100583, "multi_mid": 110583, "tmid": 120583,
        "temper": "T5 (aged)",
        "rho_gcc": 1.83, "E_GPa": 45.0, "nu": 0.35,
        "sigy_MPa": 255.0, "sigu_MPa": 325.0, "eps_f": 0.11,
        "ss_plastic": [
            (0.000, 255.0), (0.005, 275.0), (0.010, 290.0),
            (0.030, 310.0), (0.060, 320.0), (0.110, 325.0),
        ],
        "cte_ppmK": 26.0, "tc_WmK": 117.0, "cp_JkgK": 1004.0,
        "cs": CS_MG,
        "damping_zeta": 0.010,
        "desc": "Extruded Mg-Zn-Zr high-strength (aerospace/bike frame)",
        "ref": "ASTM B107 ZK60A-T5",
    },
]

STEEL_DB = [
    {
        "name": "SPCC_mild_steel",
        "bi_mid": 100591, "multi_mid": 110591, "tmid": 120591,
        "temper": "Cold rolled",
        "rho_gcc": 7.85, "E_GPa": 210.0, "nu": 0.30,
        "sigy_MPa": 195.0, "sigu_MPa": 350.0, "eps_f": 0.37,
        "ss_plastic": [
            (0.000, 195.0), (0.020, 240.0), (0.050, 275.0),
            (0.100, 310.0), (0.200, 335.0), (0.300, 345.0),
            (0.370, 350.0),
        ],
        "cte_ppmK": 12.0, "tc_WmK": 52.0, "cp_JkgK": 465.0,
        "cs": CS_STEEL_MILD,
        "damping_zeta": 0.003,
        "desc": "Cold-rolled mild steel sheet (brackets, housings)",
        "ref": "JIS G 3141 SPCC, ASTM A1008",
    },
    {
        "name": "S45C_medium_carbon",
        "bi_mid": 100592, "multi_mid": 110592, "tmid": 120592,
        "temper": "Normalized",
        "rho_gcc": 7.85, "E_GPa": 205.0, "nu": 0.29,
        "sigy_MPa": 343.0, "sigu_MPa": 569.0, "eps_f": 0.20,
        "ss_plastic": [
            (0.000, 343.0), (0.010, 410.0), (0.020, 450.0),
            (0.050, 500.0), (0.100, 540.0), (0.150, 560.0),
            (0.200, 569.0),
        ],
        "cte_ppmK": 11.0, "tc_WmK": 49.8, "cp_JkgK": 486.0,
        "cs": CS_STEEL_MEDIUM,
        "damping_zeta": 0.003,
        "desc": "0.45%C medium carbon steel (shafts, fasteners)",
        "ref": "JIS G 4051 S45C, AISI 1045",
    },
    {
        "name": "SCM440_alloy_steel",
        "bi_mid": 100593, "multi_mid": 110593, "tmid": 120593,
        "temper": "Q&T (HB 285)",
        "rho_gcc": 7.85, "E_GPa": 205.0, "nu": 0.29,
        "sigy_MPa": 835.0, "sigu_MPa": 980.0, "eps_f": 0.12,
        "ss_plastic": [
            (0.000, 835.0), (0.005, 875.0), (0.010, 905.0),
            (0.020, 935.0), (0.050, 965.0), (0.100, 978.0),
            (0.120, 980.0),
        ],
        "cte_ppmK": 12.3, "tc_WmK": 42.6, "cp_JkgK": 477.0,
        "cs": CS_STEEL_MEDIUM,
        "damping_zeta": 0.003,
        "desc": "Cr-Mo alloy steel Q&T (high-strength bolts, gears)",
        "ref": "JIS G 4053 SCM440, AISI 4140",
    },
]

BRASS_DB = [
    {
        "name": "C26000_Cartridge_Brass",
        "bi_mid": 100601, "multi_mid": 110601, "tmid": 120601,
        "temper": "1/2 Hard",
        "rho_gcc": 8.53, "E_GPa": 110.0, "nu": 0.375,
        "sigy_MPa": 310.0, "sigu_MPa": 425.0, "eps_f": 0.23,
        "ss_plastic": [
            (0.000, 310.0), (0.010, 345.0), (0.020, 370.0),
            (0.050, 395.0), (0.100, 410.0), (0.150, 420.0),
            (0.230, 425.0),
        ],
        "cte_ppmK": 19.9, "tc_WmK": 120.0, "cp_JkgK": 375.0,
        "cs": CS_BRASS,
        "damping_zeta": 0.004,
        "desc": "70/30 Cu-Zn cartridge brass (connector shells)",
        "ref": "ASTM B36 / UNS C26000, Copper Development Assoc",
    },
    {
        "name": "C36000_FreeCutting_Brass",
        "bi_mid": 100602, "multi_mid": 110602, "tmid": 120602,
        "temper": "Half hard",
        "rho_gcc": 8.50, "E_GPa": 97.0, "nu": 0.31,
        "sigy_MPa": 310.0, "sigu_MPa": 400.0, "eps_f": 0.18,
        "ss_plastic": [
            (0.000, 310.0), (0.010, 340.0), (0.020, 360.0),
            (0.050, 380.0), (0.100, 392.0), (0.180, 400.0),
        ],
        "cte_ppmK": 20.5, "tc_WmK": 115.0, "cp_JkgK": 380.0,
        "cs": CS_BRASS,
        "damping_zeta": 0.004,
        "desc": "Free-cutting leaded brass (precision machined parts)",
        "ref": "ASTM B16 / UNS C36000",
    },
    {
        "name": "C51000_Phosphor_Bronze",
        "bi_mid": 100603, "multi_mid": 110603, "tmid": 120603,
        "temper": "Spring temper",
        "rho_gcc": 8.86, "E_GPa": 110.0, "nu": 0.34,
        "sigy_MPa": 590.0, "sigu_MPa": 655.0, "eps_f": 0.08,
        "ss_plastic": [
            (0.000, 590.0), (0.005, 615.0), (0.010, 630.0),
            (0.020, 642.0), (0.050, 650.0), (0.080, 655.0),
        ],
        "cte_ppmK": 17.8, "tc_WmK": 69.0, "cp_JkgK": 380.0,
        "cs": CS_BRONZE,
        "damping_zeta": 0.005,
        "desc": "5% Sn phosphor bronze spring material (contacts, bearings)",
        "ref": "ASTM B103 / UNS C51000",
    },
]

TUNGSTEN_DB = [
    {
        "name": "Tungsten_99pct",
        "bi_mid": 100621, "multi_mid": 110621, "tmid": 120621,
        "temper": "Sintered 99%",
        "rho_gcc": 19.30, "E_GPa": 411.0, "nu": 0.28,
        "sigy_MPa": 750.0, "sigu_MPa": 980.0, "eps_f": 0.03,
        "ss_plastic": [
            (0.000, 750.0), (0.005, 820.0), (0.010, 870.0),
            (0.015, 920.0), (0.020, 960.0), (0.030, 980.0),
        ],
        "cte_ppmK": 4.5, "tc_WmK": 174.0, "cp_JkgK": 134.0,
        "cs": CS_STEEL_MILD,
        "damping_zeta": 0.002,
        "desc": "Tungsten 99% pure sintered (haptic motor counterweight, densest)",
        "ref": "Plansee Tungsten TDS, ASM Handbook Vol 2",
    },
]

INCONEL_DB = [
    {
        "name": "Inconel_625_annealed",
        "bi_mid": 100611, "multi_mid": 110611, "tmid": 120611,
        "temper": "Annealed",
        "rho_gcc": 8.44, "E_GPa": 207.5, "nu": 0.312,
        "sigy_MPa": 415.0, "sigu_MPa": 827.0, "eps_f": 0.30,
        "ss_plastic": [
            (0.000, 415.0), (0.010, 510.0), (0.020, 585.0),
            (0.050, 685.0), (0.100, 760.0), (0.200, 810.0),
            (0.300, 827.0),
        ],
        "cte_ppmK": 12.8, "tc_WmK": 9.8, "cp_JkgK": 410.0,
        "cs": CS_INCONEL,
        "damping_zeta": 0.003,
        "desc": "Ni-Cr-Mo solid-solution superalloy (aerospace, marine)",
        "ref": "ASTM B443 / UNS N06625, Special Metals TDS",
    },
    {
        "name": "Inconel_718_aged",
        "bi_mid": 100612, "multi_mid": 110612, "tmid": 120612,
        "temper": "Solution + aged",
        "rho_gcc": 8.19, "E_GPa": 205.0, "nu": 0.294,
        "sigy_MPa": 1035.0, "sigu_MPa": 1240.0, "eps_f": 0.12,
        "ss_plastic": [
            (0.000, 1035.0), (0.005, 1105.0), (0.010, 1150.0),
            (0.020, 1185.0), (0.050, 1215.0), (0.100, 1235.0),
            (0.120, 1240.0),
        ],
        "cte_ppmK": 13.0, "tc_WmK": 11.4, "cp_JkgK": 435.0,
        "cs": CS_INCONEL,
        "damping_zeta": 0.003,
        "desc": "Ni-Cr precipitation-hardenable (turbine, rocket)",
        "ref": "ASTM B637 / UNS N07718, Special Metals TDS",
    },
]

ALL_MATERIALS = {
    "SUS": SUS_DB,
    "Al": AL_DB,
    "Ti": TI_DB,
    "Mg": MG_DB,
    "Steel": STEEL_DB,
    "Brass": BRASS_DB,
    "Inconel": INCONEL_DB,
    "Tungsten": TUNGSTEN_DB,
}

# ============================================================
# Auto-derive kinematic hardening MIDs from bilinear MID
# ============================================================
# Bilinear isotropic (MAT_024):   100501~100580
# Multilinear isotropic (MAT_024+LCSS): 110501~110580
# Thermal (TMID):                  120501~120580
# Bilinear kinematic pure  (MAT_003, BETA=0):   130501~130580
# Bilinear kinematic mixed (MAT_003, BETA=0.5): 140501~140580
def _augment_kinematic_mids():
    for group, materials in ALL_MATERIALS.items():
        for m in materials:
            m["kin_pure_mid"] = m["bi_mid"] + 30000    # 130xxx
            m["kin_mixed_mid"] = m["bi_mid"] + 40000   # 140xxx

_augment_kinematic_mids()

# ============================================================
# Unit conversions
# ============================================================
# Input: g/cc, GPa, MPa, ppm/K, W/m/K, J/kg/K
# Output: ton/mm^3, MPa (E and stress), 1/K, mW/mm/K, mm^2/s^2/K

def rho_to_tonmm3(rho_gcc):
    return rho_gcc * 1e-9

def E_to_MPa(E_GPa):
    return E_GPa * 1000.0

def cte_to_perK(cte_ppmK):
    return cte_ppmK * 1e-6

def tc_to_mWmmK(tc_WmK):
    # W/(m·K) = (1000 mW) / (1000 mm · K) = mW/(mm·K)
    return tc_WmK

def cp_to_mm2s2K(cp_JkgK):
    # J/(kg·K) = (1e6 g·mm^2/s^2) / (1e-3 ton · K) = 1e9 mm^2/s^2/ton/K
    # LS-DYNA uses specific heat per unit mass with density in ton/mm^3
    # [Cp] = [mm^2 / s^2 / K]  (energy per mass per temperature)
    # 1 J/kg/K = 1 (kg·m^2/s^2) / (kg·K) = 1 m^2/s^2/K = 1e6 mm^2/s^2/K
    return cp_JkgK * 1e6


# ============================================================
# K-file writers
# ============================================================

def fmt_10(v):
    """Format a float/int into a 10-character fixed-width field."""
    if isinstance(v, int):
        return f"{v:10d}"
    if isinstance(v, str):
        return f"{v:>10s}"
    # Float: choose best representation
    if v == 0.0:
        return "       0.0"
    a = abs(v)
    if 0.001 <= a < 1e5:
        return f"{v:10.4f}"
    return f"{v:10.3e}"


def header(title, group_name, group_desc, mid_range):
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append(f"$ {title}")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> MPa, N, ton/mm^3")
    lines.append(f"$ Group: {group_name} — {group_desc}")
    lines.append(f"$ MID: {mid_range}")
    lines.append("$ Model: *MAT_PIECEWISE_LINEAR_PLASTICITY (MAT_024)")
    lines.append("$")
    lines.append("$ Hybrid strategy:")
    lines.append("$   Bilinear    MID 1005xx (fast, SIGY+ETAN)")
    lines.append("$   Multilinear MID 1105xx (precise, LCSS=MID)")
    lines.append("$")
    lines.append("$ Cowper-Symonds strain-rate (Jones, Structural Impact):")
    lines.append("$   Aluminum: C=6500  P=4")
    lines.append("$   Stainless:C=100   P=10")
    lines.append("$   Titanium: C=120   P=9")
    lines.append("$")
    lines.append("$ Thermal properties (TC, Cp, CTE) in metal_thermal.k")
    lines.append("$ " + "=" * 72)
    return lines


def write_mat024_bilinear(m):
    """Write a bilinear MAT_024 card."""
    sigy = m["sigy_MPa"]
    sigu = m["sigu_MPa"]
    eps_f = m["eps_f"]
    E = E_to_MPa(m["E_GPa"])
    eps_y = sigy / E
    eps_plastic_at_failure = max(eps_f - eps_y, 1e-6)
    etan = (sigu - sigy) / eps_plastic_at_failure
    etan = max(etan, 1.0)  # avoid negative

    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Bilinear (MID {m['bi_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Temper: {m['temper']}")
    lines.append(f"$$ Source: {m['ref']}")
    lines.append(f"$$ rho={m['rho_gcc']} g/cc, E={m['E_GPa']} GPa, nu={m['nu']}")
    lines.append(f"$$ sigy={sigy} MPa, sigu={sigu} MPa, eps_f={eps_f}")
    lines.append(f"$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = {etan:.1f} MPa")
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
        f"{m['cs']['C']:10.1f}"
        f"{m['cs']['P']:10.1f}"
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
    """Write a *DEFINE_CURVE for stress-plastic strain."""
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
    """Write a multi-linear MAT_024 with LCSS."""
    E = E_to_MPa(m["E_GPa"])
    lcid = m["multi_mid"]  # LCID == multi_mid

    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} Multilinear (MID {m['multi_mid']}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Temper: {m['temper']}")
    lines.append(f"$$ Source: {m['ref']}")
    lines.append(f"$$ LCSS curve: {len(m['ss_plastic'])} points, LCID={lcid}")
    lines.extend(write_define_curve(lcid, m["name"], m["ss_plastic"]))
    lines.append("$")
    lines.append("*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE")
    lines.append(f"{m['name']} Multilinear")
    lines.append("$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL")
    lines.append(
        f"{m['multi_mid']:10d}"
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
        f"{m['cs']['C']:10.1f}"
        f"{m['cs']['P']:10.1f}"
        f"{lcid:10d}"
        f"{0:10d}"
        f"{1.0:10.1f}"
    )
    return lines


def write_mat003_kinematic(m, beta, mid, label):
    """
    Write a *MAT_PLASTIC_KINEMATIC card (MAT_003).

    BETA parameter:
      0.0 = pure kinematic hardening
      1.0 = pure isotropic hardening
      0.5 = 50/50 mixed hardening

    Same SIGY, ETAN, FAIL as bilinear isotropic (MAT_024) so direct comparable.

    Card format (LS-DYNA R16):
      Card 1: MID RO E PR SIGY ETAN BETA
      Card 2: SRC SRP FS VP
    """
    sigy = m["sigy_MPa"]
    sigu = m["sigu_MPa"]
    eps_f = m["eps_f"]
    E = E_to_MPa(m["E_GPa"])
    eps_y = sigy / E
    eps_plastic_at_failure = max(eps_f - eps_y, 1e-6)
    etan = (sigu - sigy) / eps_plastic_at_failure
    etan = max(etan, 1.0)

    lines = []
    lines.append("$")
    lines.append(f"$$ --- {m['name']} {label} (MID {mid}) ---")
    lines.append(f"$$ {m['desc']}")
    lines.append(f"$$ Temper: {m['temper']}")
    lines.append(f"$$ Source: {m['ref']}")
    lines.append(f"$$ Hardening: BETA={beta}  (0=pure kinematic, 1=isotropic)")
    lines.append(f"$$ sigy={sigy} MPa, ETAN={etan:.1f} MPa, eps_f={eps_f}")
    lines.append(f"$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)")
    lines.append("*MAT_PLASTIC_KINEMATIC_TITLE")
    lines.append(f"{m['name']} {label}")
    lines.append("$      MID        RO         E        PR      SIGY      ETAN      BETA")
    lines.append(
        f"{mid:10d}"
        f"{rho_to_tonmm3(m['rho_gcc']):10.3e}"
        f"{E:10.1f}"
        f"{m['nu']:10.4f}"
        f"{sigy:10.2f}"
        f"{etan:10.2f}"
        f"{beta:10.4f}"
    )
    lines.append("$      SRC       SRP        FS        VP")
    lines.append(
        f"{m['cs']['C']:10.1f}"
        f"{m['cs']['P']:10.1f}"
        f"{eps_f:10.4f}"
        f"{1.0:10.1f}"
    )
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
    lines.append(f"$$ Converted: TC={tc_out:.4e} mW/mm/K, Cp={cp_out:.4e} mm^2/s^2/K")
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
    """Write *MAT_ADD_THERMAL_EXPANSION for all four MIDs (bi iso, multi iso, kin pure, kin mixed).

    DB CONVENTION: The first field of *MAT_ADD_THERMAL_EXPANSION is officially
    a PART ID in LS-DYNA. However, for library/database purposes we store the
    MATERIAL ID (MID) in that field as a placeholder. An external post-processor
    should scan the user's main model, find all PARTs that reference a given MID,
    and generate one *MAT_ADD_THERMAL_EXPANSION card per PART ID.

    This allows the DB to be self-contained without knowing actual part numbering.
    """
    cte = cte_to_perK(m["cte_ppmK"])
    mids = [m["bi_mid"], m["multi_mid"], m["kin_pure_mid"], m["kin_mixed_mid"]]
    variant_labels = ["bi_iso", "multi_iso", "kin_pure", "kin_mixed"]
    lines = []
    lines.append(f"$$ CTE={m['cte_ppmK']} ppm/K, applied to all 4 MIDs of {m['name']}")
    lines.append(f"$$   bi_iso={m['bi_mid']}, multi_iso={m['multi_mid']}, "
                 f"kin_pure={m['kin_pure_mid']}, kin_mixed={m['kin_mixed_mid']}")
    lines.append(f"$$ NOTE: The value in the PID field is the MATERIAL ID (MID).")
    lines.append(f"$$ An external tool must replace this with actual PART IDs")
    lines.append(f"$$ that reference each MID before running LS-DYNA.")
    for mid, vlabel in zip(mids, variant_labels):
        lines.append(f"$$ [DB] {m['name']} {vlabel} -- PID slot holds MID={mid}")
        lines.append("*MAT_ADD_THERMAL_EXPANSION")
        lines.append("$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ")
        lines.append(f"{mid:10d}{0:10d}{cte:10.3e}")
    return lines


# ============================================================
# File writers
# ============================================================

def write_mechanical_kfile(materials, filepath, group_name, group_desc, mid_range):
    """Write a K-file containing all 4 hardening variants per material."""
    title = f"{group_name} METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)"
    lines = header(title, group_name, group_desc, mid_range)
    lines.append("$")
    lines.append("$ 4 hardening variants per material:")
    lines.append("$   1. Bilinear isotropic  (MAT_024, SIGY+ETAN)            1005xx")
    lines.append("$   2. Multilinear isotropic (MAT_024 + LCSS curve)         1105xx")
    lines.append("$   3. Bilinear kinematic pure  (MAT_003, BETA=0.0)         1305xx")
    lines.append("$   4. Bilinear kinematic mixed (MAT_003, BETA=0.5)         1405xx")
    lines.append("$")
    lines.append("$ Use isotropic for monotonic drop impact,")
    lines.append("$ kinematic/mixed for cyclic or reverse loading (Bauschinger effect).")
    lines.append("$")
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append(
        "$   bi_iso  multi_iso  kin_pure  kin_mix   Name                    sigy   sigu"
    )
    lines.append("$   " + "-" * 80)
    for m in materials:
        lines.append(
            f"$   {m['bi_mid']}  {m['multi_mid']}     "
            f"{m['kin_pure_mid']}    {m['kin_mixed_mid']}   "
            f"{m['name']:22s}  "
            f"{m['sigy_MPa']:5.0f}  {m['sigu_MPa']:5.0f}"
        )
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat024_bilinear(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat024_multilinear(m))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)")
    lines.append("$    For Bauschinger effect / reverse cyclic loading")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat003_kinematic(m, beta=0.0,
                                             mid=m["kin_pure_mid"],
                                             label="Kinematic Pure"))
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)")
    lines.append("$    50/50 isotropic-kinematic, realistic for metals")
    lines.append("$ " + "=" * 72)
    for m in materials:
        lines.extend(write_mat003_kinematic(m, beta=0.5,
                                             mid=m["kin_mixed_mid"],
                                             label="Kinematic Mixed"))
    lines.append("$")
    lines.append("*END")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_thermal_kfile(filepath):
    """Write a combined thermal K-file with all materials."""
    lines = []
    lines.append("$ " + "=" * 72)
    lines.append("$ METAL THERMAL PROPERTIES")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton -> temperature K")
    lines.append("$   TC (thermal conductivity) : mW/mm/K  (= W/m/K)")
    lines.append("$   Cp (specific heat)        : mm^2/s^2/K (= J/kg/K * 1e6)")
    lines.append("$   CTE                       : 1/K  (= ppm/K * 1e-6)")
    lines.append("$")
    lines.append("$ *MAT_THERMAL_ISOTROPIC for coupled thermal-mechanical analysis")
    lines.append("$   Reference the TMID in your *PART card.")
    lines.append("$ *MAT_ADD_THERMAL_EXPANSION for thermal strain")
    lines.append("$   Paired with 4 structural MIDs: bi_iso, multi_iso, kin_pure, kin_mixed.")
    lines.append("$")
    lines.append("$ " + "!" * 72)
    lines.append("$ !!  DATABASE CONVENTION — IMPORTANT                                  !!")
    lines.append("$ !!                                                                     !!")
    lines.append("$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds the MATERIAL ID  !!")
    lines.append("$ !!  (MID), NOT an actual Part ID. This is a library convention:        !!")
    lines.append("$ !!                                                                     !!")
    lines.append("$ !!    1. All CTE cards in this file are template placeholders.         !!")
    lines.append("$ !!    2. Before running LS-DYNA, an external tool must:                !!")
    lines.append("$ !!       - Scan user's main model for *PART cards                      !!")
    lines.append("$ !!       - Find all PIDs that reference each MID from this library     !!")
    lines.append("$ !!       - Generate one *MAT_ADD_THERMAL_EXPANSION per actual PID       !!")
    lines.append("$ !!    3. Running this file as-is will cause LS-DYNA to complain that   !!")
    lines.append("$ !!       PID (e.g. 100535) does not exist.                             !!")
    lines.append("$ !!                                                                     !!")
    lines.append("$ !!  The *MAT_THERMAL_ISOTROPIC cards themselves are standalone and     !!")
    lines.append("$ !!  used directly via TMID field in *PART — no replacement needed.     !!")
    lines.append("$ " + "!" * 72)
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("$ SUMMARY TABLE")
    lines.append("$")
    lines.append(
        "$   TMID    Name                     CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)"
    )
    lines.append("$   " + "-" * 70)
    for group_name, materials in ALL_MATERIALS.items():
        for m in materials:
            lines.append(
                f"$   {m['tmid']}  {m['name']:25s} "
                f"{m['cte_ppmK']:8.2f}  {m['tc_WmK']:8.2f}  {m['cp_JkgK']:8.1f}"
            )
    lines.append("$")
    lines.append("$ " + "=" * 72)
    lines.append("*KEYWORD")

    for group_name, materials in ALL_MATERIALS.items():
        lines.append("$")
        lines.append("$ " + "=" * 72)
        lines.append(f"$ {group_name} THERMAL")
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
    Write a K-file with *SET_PART_LIST + *DAMPING_PART_MASS_SET + *DAMPING_PART_STIFFNESS_SET
    for every material, using its damping_zeta field.

    For each material:
      - Part set SID = bi_mid + 800000 (bilinear parts)
      - Part set SID = multi_mid + 800000 (multilinear parts)
    User fills in actual PIDs after loading in full model.

    Rayleigh split equally:
      alpha = zeta * omega_ref
      beta  = zeta / omega_ref
    """
    import math

    omega_ref = 2.0 * math.pi * omega_ref_hz

    lines = []
    lines.append("$ " + "=" * 72)
    lines.append("$ METAL DAMPING LIBRARY (Rayleigh for MAT_024 solids)")
    lines.append("$ " + "=" * 72)
    lines.append("$ Unit: mm, s, ton")
    lines.append(f"$ Reference frequency: {omega_ref_hz:.0f} Hz ({omega_ref:.1f} rad/s)")
    lines.append("$")
    lines.append("$ Damping ratios (zeta) by material family:")
    lines.append("$   SUS austenitic (201,301,304,316):   0.5%  (FCC, solid-sol)")
    lines.append("$   SUS martensitic/PH (410,420,17-4PH):0.3%  (rate-insensitive BCC)")
    lines.append("$   SUS ferritic (430):                 0.4%")
    lines.append("$   Al solid-sol (1xxx,3xxx,5xxx):      0.6~0.8% (Mg content)")
    lines.append("$   Al precipitation (2xxx,6xxx,7xxx):  0.3%     (heat treated)")
    lines.append("$   ADC12 die cast:                     1.5%     (porosity/defects)")
    lines.append("$   Ti CP (Gr1/2/4):                    0.5%")
    lines.append("$   Ti-6Al-4V (Gr5,Gr5 ELI):            0.3%     (two-phase)")
    lines.append("$   Ti-3Al-2.5V (Gr9):                  0.4%")
    lines.append("$")
    lines.append("$ Rayleigh coefficients:")
    lines.append("$   alpha (mass)      = zeta * omega_ref")
    lines.append("$   beta  (stiffness) = zeta / omega_ref")
    lines.append("$")
    lines.append("$ USAGE:")
    lines.append("$   1. INCLUDE this file in your main model")
    lines.append("$   2. Each material has a *SET_PART_LIST placeholder with empty PID list")
    lines.append("$      Part Set SID = MID + 800000")
    lines.append("$      Example: Al6061-T6 bi  -> MID 100535 -> SID 900535")
    lines.append("$               Al6061-T6 mu  -> MID 110535 -> SID 910535")
    lines.append("$   3. Fill in the actual PART IDs for each material you use")
    lines.append("$   4. Damping auto-applied via DAMPING_PART_MASS_SET + STIFFNESS_SET")
    lines.append("$ " + "=" * 72)
    lines.append("$")
    lines.append("$ SUMMARY TABLE (4 variants per material)")
    lines.append("$")
    lines.append(
        "$   MID      Variant  Name                    zeta  alpha(/s)  beta(s)"
    )
    lines.append("$   " + "-" * 73)
    for group, materials in ALL_MATERIALS.items():
        for m in materials:
            zeta = m["damping_zeta"]
            alpha = zeta * omega_ref
            beta = zeta / omega_ref
            variants = [
                ("bi_iso", m["bi_mid"]),
                ("mu_iso", m["multi_mid"]),
                ("kin_pure", m["kin_pure_mid"]),
                ("kin_mix", m["kin_mixed_mid"]),
            ]
            for label, mid in variants:
                lines.append(
                    f"$   {mid}  {label:8s} {m['name']:22s}  {zeta:.4f}  {alpha:.3e}  {beta:.3e}"
                )
    lines.append("$")
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

            # 4 variants per material
            variants = [
                ("bi_iso", m["bi_mid"]),
                ("mu_iso", m["multi_mid"]),
                ("kin_pure", m["kin_pure_mid"]),
                ("kin_mix", m["kin_mixed_mid"]),
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
                lines.append("$ TODO: replace zeros below with actual PART IDs using this material")
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


def write_materials_db_json(filepath):
    """Write the parsed material database to JSON."""
    db = {}
    for group, materials in ALL_MATERIALS.items():
        db[group] = []
        for m in materials:
            entry = dict(m)
            # Serialize tuples
            entry["ss_plastic"] = [list(p) for p in m["ss_plastic"]]
            db[group].append(entry)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ============================================================
# Main
# ============================================================

def main():
    script_dir = Path(__file__).parent.resolve()

    sus_path = script_dir / "sus.k"
    al_path = script_dir / "al.k"
    ti_path = script_dir / "ti.k"
    mg_path = script_dir / "mg.k"
    steel_path = script_dir / "steel.k"
    brass_path = script_dir / "brass.k"
    inconel_path = script_dir / "inconel.k"
    tungsten_path = script_dir / "tungsten.k"
    thermal_path = script_dir / "metal_thermal.k"
    damping_path = script_dir / "metal_damping.k"
    db_path = script_dir / "metal_materials_db.json"

    write_mechanical_kfile(
        SUS_DB, sus_path,
        group_name="SUS",
        group_desc="Stainless Steel Alloys",
        mid_range="100501~100520 (bi), 110501~110520 (multi)",
    )
    write_mechanical_kfile(
        AL_DB, al_path,
        group_name="AL",
        group_desc="Aluminum Alloys",
        mid_range="100521~100560 (bi), 110521~110560 (multi)",
    )
    write_mechanical_kfile(
        TI_DB, ti_path,
        group_name="TI",
        group_desc="Titanium Alloys",
        mid_range="100561~100580 (bi), 110561~110580 (multi)",
    )
    write_mechanical_kfile(
        MG_DB, mg_path,
        group_name="MG",
        group_desc="Magnesium Alloys (smartphone frames)",
        mid_range="100581~100590 (bi), 110581~110590 (multi)",
    )
    write_mechanical_kfile(
        STEEL_DB, steel_path,
        group_name="STEEL",
        group_desc="Carbon/Alloy Steel (brackets, fasteners)",
        mid_range="100591~100600 (bi), 110591~110600 (multi)",
    )
    write_mechanical_kfile(
        BRASS_DB, brass_path,
        group_name="BRASS",
        group_desc="Brass & Bronze (connectors, springs)",
        mid_range="100601~100610 (bi), 110601~110610 (multi)",
    )
    write_mechanical_kfile(
        INCONEL_DB, inconel_path,
        group_name="INCONEL",
        group_desc="Ni-base Superalloys (high temperature)",
        mid_range="100611~100620 (bi), 110611~110620 (multi)",
    )
    write_mechanical_kfile(
        TUNGSTEN_DB, tungsten_path,
        group_name="TUNGSTEN",
        group_desc="Tungsten (haptic motor counterweight, highest density)",
        mid_range="100621 (bi), 110621 (multi)",
    )
    write_thermal_kfile(thermal_path)
    write_damping_kfile(damping_path, omega_ref_hz=1000.0)
    write_materials_db_json(db_path)

    # Summary
    total = sum(len(v) for v in ALL_MATERIALS.values())
    print("=" * 65)
    print("  Metal Material Library Generated")
    print("=" * 65)
    for group, materials in ALL_MATERIALS.items():
        print(f"  {group:5s}: {len(materials):2d} materials")
    print(f"  TOTAL: {total} materials x 4 mech variants = {total*4} mechanical cards")
    print(f"  + {total} thermal + {total*4} damping part sets")
    print()
    print("  Output files:")
    for p in [sus_path, al_path, ti_path, mg_path, steel_path, brass_path,
              inconel_path, tungsten_path, thermal_path, damping_path, db_path]:
        sz = p.stat().st_size if p.exists() else 0
        print(f"    {p.name:35s}  {sz:7d} bytes")

    # Per-material summary
    print()
    print("=" * 98)
    print(f"  {'bi_iso':>7s} {'mu_iso':>7s} {'kin_pure':>8s} {'kin_mix':>8s} {'TMID':>7s}  "
          f"{'Name':22s} {'sigy':>6s} {'sigu':>6s} {'zeta':>5s}")
    print("  " + "-" * 96)
    for group, materials in ALL_MATERIALS.items():
        for m in materials:
            print(
                f"  {m['bi_mid']:7d} {m['multi_mid']:7d} {m['kin_pure_mid']:8d} "
                f"{m['kin_mixed_mid']:8d} {m['tmid']:7d}  "
                f"{m['name']:22s} {m['sigy_MPa']:6.0f} {m['sigu_MPa']:6.0f} "
                f"{m['damping_zeta']:5.3f}"
            )


if __name__ == "__main__":
    main()
