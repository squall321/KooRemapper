#pragma once
// =============================================================
// BatteryConfig.h — Configuration structs for battery command
// =============================================================
// All physical units: t/mm/s  (stress = MPa, force = N, mass = ton)
// =============================================================

#include <string>
#include <vector>

// ── Layer type indices (used for PID calculation) ──────────────
enum BatteryLayerType {
    LT_AL   = 1,   // Al current collector (SHELL)
    LT_CAT  = 2,   // NMC cathode         (SOLID Phase1, TSHELL Phase2)
    LT_SEP  = 3,   // PE separator        (SHELL)
    LT_ANO  = 4,   // Graphite anode      (SOLID Phase1, TSHELL Phase2)
    LT_CU   = 5,   // Cu current collector (SHELL)
    LT_CUAL = 6    // Cu+Al composite CC  (SOLID, merge_cc mode only)
};

// ── Cell geometry ──────────────────────────────────────────────
struct BatteryCellGeometry {
    double cellWidth    = 66.4;   // mm (x-direction)
    double cellHeight   = 89.8;   // mm (y-direction)
    int    nUnitCells   = 11;     // number of unit cells stacked in Z
    double capacity     = 0.0;    // Ah → auto-compute nUnitCells if > 0
    double arealCap     = 3.0;    // mAh/cm² per side (used with capacity)
};

// ── Layer thicknesses ──────────────────────────────────────────
struct BatteryLayerThickness {
    double alCC       = 0.012;   // mm  Al current collector foil
    double cathode    = 0.065;   // mm  NMC half-coating (×2 = solid height 0.130)
    double separator  = 0.020;   // mm  PE separator
    double anode      = 0.070;   // mm  Graphite half-coating (×2 = solid height 0.140)
    double cuCC       = 0.008;   // mm  Cu current collector foil
    double pouch      = 0.153;   // mm  Pouch laminate (each face)
    double buffer     = 0.200;   // mm  Electrolyte buffer between pouch and jellyroll
};

// ── Material: Al / Cu current collectors (MAT_JOHNSON_COOK, MID 1/5) ──
struct BatteryMatCC {
    std::string name = "Al1050";  // written to *MAT_XXX_TITLE
    double rho    = 2.70e-9;   // ton/mm³
    double G      = 26923.0;   // shear modulus MPa
    double E      = 69000.0;   // Young's modulus MPa
    double nu     = 0.33;
    double A      = 70.0;      // JC yield stress MPa
    double B      = 110.0;
    double N      = 0.18;      // hardening exponent
    double C      = 0.014;     // strain rate
    double M      = 1.0;       // thermal softening
    double TM     = 933.0;     // melt temp K
    double TR     = 298.15;    // room temp K
    double CP     = 903.0e6;   // specific heat mJ/ton·K
    double cond   = 237.0;     // W/m·K (thermal, Phase 2)
};

// ── Material: CuAl composite CC (MID=9, merge_cc mode) ───────
// Weighted average: Cu 40% + Al 60% (by volume)
struct BatteryMatCuAl : public BatteryMatCC {
    BatteryMatCuAl() {
        rho  = 0.4*8.96e-9 + 0.6*2.70e-9;  // ~5.206e-9 ton/mm³
        E    = 0.4*110000.0 + 0.6*69000.0;  // 85400 MPa
        nu   = 0.4*0.34     + 0.6*0.33;     // 0.334
        G    = E / (2.0*(1.0+nu));
        A    = 0.4*90.0  + 0.6*70.0;        // 78 MPa
        B    = 0.4*292.0 + 0.6*110.0;       // 182.8 MPa
        N    = 0.4*0.31  + 0.6*0.18;        // 0.232
        C    = 0.4*0.025 + 0.6*0.014;       // 0.0184
        M    = 0.4*1.09  + 0.6*1.0;         // 1.036
        TM   = std::min(1357.0, 933.0);      // lower melt point (Al limited)
        TR   = 298.15;
        CP   = 0.4*385.0e6 + 0.6*903.0e6;   // 695.8e6 mJ/ton·K
        cond = 0.4*401.0   + 0.6*237.0;     // 302.6 W/m·K
    }
};

struct BatteryMatCu : public BatteryMatCC {
    BatteryMatCu() {
        name = "Cu_Foil";
        rho  = 8.96e-9;
        G    = 41791.0;
        E    = 110000.0;
        nu   = 0.34;
        A    = 90.0;
        B    = 292.0;
        N    = 0.31;
        C    = 0.025;
        M    = 1.09;
        TM   = 1357.0;
        CP   = 385.0e6;
        cond = 401.0;
    }
};

// ── Material: NMC Cathode (MID=2) ─────────────────────────────
struct BatteryMatCathode {
    std::string name  = "NMC_Cathode";
    double rho        = 2.50e-9;
    // Phase 1: MAT_VISCOELASTIC (MAT_076)
    double G0         = 307.7;     // MPa
    double Ginf       = 269.2;     // MPa
    double beta       = 1000.0;    // decay constant 1/s
    double bulk       = 666.0;     // bulk modulus MPa
    // Phase 2: MAT_ELASTIC (TSHELL constraint)
    double E_elas     = 800.0;
    double nu_elas    = 0.30;
    // Thermal (Phase 2)
    double cond       = 1.0;       // W/m·K
    double CP         = 1040.0e6;  // mJ/ton·K
    double cte        = 0.015;     // intercalation strain per unit SOC
};

// ── Material: Graphite Anode (MID=4) ──────────────────────────
struct BatteryMatAnode {
    std::string name  = "Graphite_Anode";
    double rho        = 1.60e-9;
    // Phase 1: MAT_VISCOELASTIC
    double G0         = 192.3;
    double Ginf       = 168.3;
    double beta       = 800.0;
    double bulk       = 416.0;
    // Phase 2: MAT_ELASTIC
    double E_elas     = 500.0;
    double nu_elas    = 0.25;
    // Thermal (Phase 2)
    double cond       = 5.0;
    double CP         = 700.0e6;
    double cte        = 0.035;     // intercalation strain per unit SOC
};

// ── Material: PE Separator (MID=3, MAT_024 PLP) ───────────────
struct BatteryMatSep {
    std::string name = "PE_Separator";
    double rho  = 0.90e-9;
    double E    = 3000.0;
    double nu   = 0.35;
    double cond = 0.16;
    double CP   = 1700.0e6;
};

// ── Material: Pouch (MID=6, MAT_024 PLP) ─────────────────────
struct BatteryMatPouch {
    std::string name = "Al_Pouch_Laminate";
    double rho  = 2.70e-9;
    double E    = 69000.0;
    double nu   = 0.33;
    double cond = 1.0;
    double CP   = 903.0e6;
};

// ── Material: Electrolyte (MID=8) ─────────────────────────────
struct BatteryMatElectrolyte {
    double rho          = 1.20e-9;
    double bulkStacked  = 1.0;     // MPa
    double bulkWound    = 600.0;
};

// ── Contact parameters ─────────────────────────────────────────
struct BatteryContactParams {
    int    soft        = 1;       // SOFT flag (always 1)
    double sofscl_base = 0.001;   // base for tier -1 (5mm mesh)
    double sofscl_pow  = 2.0;     // scaling power
    double sst_ext     = 0.05;    // mm  external contact shell thickness
    double sst_self    = 0.01;    // mm  self-contact shell thickness
    int    depth       = 5;
    double maxpar      = 1.025;
    double sbopt       = 2.0;
};

// ── Swelling parameters (Phase 2) ─────────────────────────────
struct BatterySwellingParams {
    bool   enabled      = false;
    double soc          = 0.8;     // state of charge snapshot (0–1)
    double graphiteCte  = 0.035;   // override mat anode cte
    double nmcCte       = 0.015;   // override mat cathode cte
    bool   seiEnabled   = false;
    double seiPreExp    = 1.5e-6;
    double seiEa        = 40000.0;
};

// ── Pouch geometry (fillet + side buffer) ─────────────────────
struct BatteryPouchParams {
    double rFillet     = 2.0;   // mm  vertical corner fillet radius
    int    nFilletSegs = 3;     // arc segments per fillet quadrant
    double bufX        = 0.5;   // mm  side electrolyte buffer in X
    double bufY        = 0.5;   // mm  side electrolyte buffer in Y
    bool   domeCap     = false; // curved top/bottom fill (flat otherwise)
};

// ── Tab geometry ───────────────────────────────────────────────
struct BatteryTabParams {
    double width      = 10.0;   // mm  X extent
    double height     = 8.0;    // mm  Y protrusion from cell edge
    double posXCenter = 17.5;   // mm  positive (Al) tab X center
    double negXCenter = 52.5;   // mm  negative (Cu) tab X center
};

// ── PCM board geometry ─────────────────────────────────────────
struct BatteryPcmParams {
    double width     = 20.0;   // mm  X extent (auto: neg_center+w/2 - pos_center+w/2)
    double height    = 3.0;    // mm  Y protrusion beyond tab tip
    double thickness = 1.0;    // mm  Z thickness
};

// ── Indenter geometry ──────────────────────────────────────────
struct BatteryIndenterParams {
    // mode=dent (flat disk punch, hits top face from above)
    double radius  = 4.0;   // mm  punch radius (Ø8mm)
    double height  = 3.0;   // mm  punch thickness in Z
    double offset  = 1.0;   // mm  initial gap between cell top and punch bottom
    double cx      = -1.0;  // mm  punch center X (-1 = auto: cell center)
    double cy      = -1.0;  // mm  punch center Y (-1 = auto: cell center)
    int    nCirc   = 16;    // circumferential segments
    int    nRadial = 3;     // radial layers

    // mode=side (cylinder or nail hits +X face along Y-axis)
    std::string type         = "cylinder"; // "cylinder" | "nail"
    double length            = 80.0;   // mm  cylinder/nail axial length (Y-dir)
    double nailTipLength     = 3.0;    // mm  cone section length
    double nailTipRadius     = 0.5;    // mm  tip radius (sharp end)
    double nailShaftRadius   = 1.5;    // mm  shaft radius
};

// ── Ground plate ───────────────────────────────────────────────
struct BatteryGroundPlate {
    double thickness = 5.0;    // mm
    double gap       = 1.0;    // mm  gap between cell bottom (z=0) and plate top
    double margin    = 10.0;   // mm  extra beyond cell edge
    int    nX        = 4;      // element count in X
    int    nY        = 4;      // element count in Y
};

// ── Batch generation ───────────────────────────────────────────
struct BatteryBatch {
    std::vector<double> tiers;       // empty → single tier from cfg.tier
    std::vector<std::string> modelTypes;  // "stacked","wound"
    std::vector<int>    phases;      // 1, 2
    // Per-phase mode overrides (parallel to phases list)
    // e.g. phase_modes: [swell, dent]  →  phase 1 uses "swell", phase 2 uses "dent"
    std::vector<std::string> phaseModes;
};

// ── Top-level config ───────────────────────────────────────────
struct BatteryConfig {
    // ── Output ──────────────────────────────────────────────
    std::string output     = "battery";   // output prefix
    std::string modelType  = "stacked";   // stacked | wound
    double      tier       = 0.0;         // -1, 0, 0.5, 1, 2
    int         phase      = 1;           // 1 | 2
    std::string mode       = "dent";      // dent | side | bare | swell

    // ── Cell ────────────────────────────────────────────────
    BatteryCellGeometry     geo;
    BatteryLayerThickness   thick;

    // ── Materials ───────────────────────────────────────────
    BatteryMatCC            matAl;
    BatteryMatCu            matCu;
    BatteryMatCuAl          matCuAl;   // merge_cc composite
    BatteryMatCathode       matCat;
    BatteryMatAnode         matAno;
    BatteryMatSep           matSep;
    BatteryMatPouch         matPouch;
    BatteryMatElectrolyte   matElyte;

    // ── Contact ─────────────────────────────────────────────
    BatteryContactParams    contact;

    // ── Loading ─────────────────────────────────────────────
    double  displacement    = -1.1;    // mm (negative = indentation)
    double  rampTime        = 0.005;   // s
    bool    hold            = true;    // maintain peak displacement
    double  plateGap        = 0.1;     // mm gap between indenter and cell top

    // ── Pouch / Tab / PCM ────────────────────────────────────
    BatteryPouchParams      pouch;
    BatteryTabParams        tabs;
    BatteryPcmParams        pcm;
    bool                    noPcm       = false;   // skip tabs + PCM
    bool                    noImpactor  = false;   // skip impactor + ground plate

    // ── Indenter / plate ─────────────────────────────────────
    BatteryIndenterParams   indenter;
    BatteryGroundPlate      plate;

    // ── Phase 2 swelling ─────────────────────────────────────
    BatterySwellingParams   swelling;

    // ── Element type modes ───────────────────────────────────
    bool  allShell       = false;  // electrodes as SHELL (no TSHELL)
    bool  solidElectrode = false;  // electrodes as ELEMENT_SOLID (Phase 3 EM)
    int   solidElform    = 1;     // wound solid electrode ELFORM (1=reduced, 2=full)
    bool  mergeCc        = false;  // Cu+Al composite CC at UC boundaries

    // ── Fixture control ──────────────────────────────────────
    bool  coreFill       = false;  // fill inner core void with electrolyte solid
    bool  noThermal      = false;  // force TMID=0 (pure mechanical)
    bool  noFixture      = false;  // skip PCM + impactor + ground + tabs

    // ── Pouch pre-tension ────────────────────────────────────
    double pouchExpandRatio = 0.0; // biaxial strain → INITIAL_STRESS_SHELL

    // ── EM RANDLES isopotential node sets ────────────────────
    bool  emRandles = false;  // write SID 201/202 (Al_CC outer / Cu_CC outer)

    // ── Airbag fill ──────────────────────────────────────────
    bool  airbagFill  = false;    // AIRBAG_LINEAR_FLUID cavity

    // ── Control ──────────────────────────────────────────────
    double terminationTime  = 0.005;   // s
    double tssfac           = 0.90;
    double dt2ms            = 0.0;

    // ── Bare mode (DR + external pressure) ───────────────────
    double externalPressure = 5.0;    // MPa  pouch face load
    double drTolerance      = 1.0e-4; // KE/IE convergence criterion
    double drEndtim         = 100.0;  // DR pseudo-time (arbitrary units)
    double drFactor         = 0.95;   // per-cycle KE damping (0.95 = 5%/cycle)
    int    drNrcyck         = 5000;   // convergence check interval
    double pouchGap         = 0.0;    // mm initial gap pouch↔jellyroll (bare)
    bool   coreVoid         = false;  // wound: leave mandrel core empty

    // ── Output ──────────────────────────────────────────────
    double outputInterval   = 2.5e-4;  // s

    // ── Phase chaining ──────────────────────────────────────
    bool        useDynain   = false;   // phase 2: *INCLUDE_DYNAIN from phase 1 output
    std::string dynainFile  = "";      // explicit dynain path (auto if empty)

    // ── Batch ───────────────────────────────────────────────
    BatteryBatch  batch;

    // ── Wound-only ──────────────────────────────────────────
    bool   woundFlat        = true;   // flat (non-conformal) vs Archimedean spiral
    double woundFlatRatio   = 0.3;    // arc x-radius = h * ratio (1.0=semicircle, 0.3=flat)
    int    woundNWinds      = 15;     // number of windings
    double woundMandrel     = 1.5;    // mandrel inner radius mm (spiral mode only)
    double woundMeshSizePath = 0.0;   // 0 = auto (meshSize * 0.8)

    // ── Auto-sizing ─────────────────────────────────────────
    double targetThickness  = 0.0;   // mm → auto-compute n_winds (wound) or n_unit_cells (stacked)

    // ── Debug / contact ─────────────────────────────────────
    double layerGapFrac     = 0.0;   // inter-winding gap = unitCell * frac (flat wound only)
};

// Helper: mesh size for a given tier
inline double batteryMeshSize(double tier) {
    if (tier <= -1.0) return 5.0;
    if (tier <   0.3) return 2.5;
    if (tier <   0.8) return 1.5;
    if (tier <   1.3) return 1.0;
    return 0.5;  // tier 2
}

// Helper: SOFSCL for a given mesh size
inline double batterySofscl(double meshSize,
                             double base = 0.001, double refSize = 5.0,
                             double power = 2.0) {
    double ratio = refSize / meshSize;
    double result = base;
    for (int i = 0; i < (int)power; ++i) result *= ratio;
    return result;
}

// Helper: output filename suffix for tier
inline std::string batteryTierSuffix(double tier) {
    if (tier <= -1.0) return "_tier-1";
    if (tier <   0.3) return "_tier0";
    if (tier <   0.8) return "_tier0_5";
    if (tier <   1.3) return "_tier1";
    return "_tier2";
}
