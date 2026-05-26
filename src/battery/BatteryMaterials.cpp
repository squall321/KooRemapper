#include "BatteryMaterials.h"
#include "BatteryWriter.h"
#include "BatteryIds.h"
#include <ostream>
#include <cstdio>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

// ─────────────────────────────────────────────────────────────
// Sections
// ─────────────────────────────────────────────────────────────

void writeSections_Phase1(std::ostream& out,
                           const BatteryConfig& cfg) {
    const auto& t = cfg.thick;
    writeComment(out, "Sections");

    // SHELL: Al CC  (ELFORM=2, zero-mass shell)
    writeSectionShell(out, SID_SHELL_AL, 2, t.alCC, 5, 0.8333);
    // SHELL: Separator (ELFORM=16 fully integrated)
    writeSectionShell(out, SID_SHELL_SEP, 16, t.separator, 5, 0.8333);
    // SHELL: Cu CC
    writeSectionShell(out, SID_SHELL_CU, 2, t.cuCC, 5, 0.8333);
    // SHELL: Pouch
    writeSectionShell(out, SID_SHELL_POUCH, 2, t.pouch, 5, 0.8333);

    // TSHELL: Electrodes + Electrolyte (ELFORM=1, NIP=3)
    writeSectionTshell(out, SID_SOLID_ELEC, 1, 3);

    // SOLID: Rigid parts (impactor, PCM, ground plate) ELFORM=1
    writeSectionSolid(out, SID_SOLID_RIGID, 1);
    // SOLID: CuAl composite CC (merge_cc mode, ELFORM=2 fully-integrated)
    writeSectionSolid(out, SID_SOLID_CC, 2);
    // SOLID: Stacked solid electrodes (configurable ELFORM via solid_elform)
    if (cfg.solidElectrode)
        writeSectionSolid(out, SID_SOLID_ELEC_STACK, cfg.solidElform);

    // RIGID section shell (kept for backward-compat, not used)
    writeSectionShell(out, SID_RIGID, 2, 5.0, 5, 0.8333);

    // Hourglass for shells and solids
    writeHourglass(out, HGID_SOLID, 6, 0.10);  // Belytschko-Bindeman (SOLID/TSHELL)
    writeHourglass(out, HGID_SHELL, 4, 0.10);  // Flanagan-Belytschko (SHELL)
}

void writeSections_Wound(std::ostream& out, const BatteryConfig& cfg) {
    const auto& t = cfg.thick;
    writeComment(out, "Sections (Wound)");

    // CC shells — same thickness as stacked, shared SECID
    writeSectionShell(out, SID_SHELL_AL,   2,  t.alCC,     5, 0.8333);
    writeSectionShell(out, SID_SHELL_SEP,  16, t.separator,5, 0.8333);
    writeSectionShell(out, SID_SHELL_CU,   2,  t.cuCC,     5, 0.8333);
    writeSectionShell(out, SID_SHELL_POUCH,2,  t.pouch,    5, 0.8333);

    if (cfg.solidElectrode) {
        // solid_elform: 1=reduced integration (stable, high AR), 2=fully integrated (accurate)
        writeSectionSolid(out, SID_W_SOLID_ELEC, cfg.solidElform);
    } else {
        // Wound electrode TSHELL — single-sided coating
        writeSectionTshell(out, SID_W_TSHELL_CAT, 1, 3);   // NMC cathode
        writeSectionTshell(out, SID_W_TSHELL_ANO, 1, 3);   // Graphite anode
    }

    // Rigid (impactor, ground plate)
    writeSectionSolid(out, SID_SOLID_RIGID, 1);
    writeSectionShell(out, SID_RIGID, 2, 5.0, 5, 0.8333);

    writeHourglass(out, HGID_SOLID, 6, 0.10);
    writeHourglass(out, HGID_SHELL, 4, 0.10);
}

// ─────────────────────────────────────────────────────────────
// MAT_JOHNSON_COOK (MAT_015)
// Fields: MID RO G E PR DTF VP RATEOP  (Card 1)
//         A B N C M TM TR EPSO          (Card 2)
//         CP PC SPALL IT D1 D2 D3 D4    (Card 3)
//         D5 EPS1 EPS2                   (Card 4)
// ─────────────────────────────────────────────────────────────
static void writeJohnsonCook(std::ostream& out, int mid,
                              const BatteryMatCC& m, const char* name = "") {
    char buf[256];
    out << "*MAT_JOHNSON_COOK_TITLE\n" << name << "\n"
        << "$#   mid        ro         g         e        pr       dtf        vp    rateop\n";
    snprintf(buf, sizeof(buf),
             "%10d%10s%10.1f%10.1f%10.4f%10d%10d%10d\n",
             mid, sciField(m.rho).c_str(), m.G, m.E, m.nu, 0, 0, 0);
    out << buf;

    out << "$#       a         b         n         c         m        tm        tr      epso\n";
    snprintf(buf, sizeof(buf),
             "%10.1f%10.1f%10.4f%10.4f%10.3f%10.2f%10.4f%10.3f\n",
             m.A, m.B, m.N, m.C, m.M, m.TM, m.TR, 1.0);
    out << buf;

    out << "$#       cp        pc     spall        it        d1        d2        d3        d4\n";
    snprintf(buf, sizeof(buf),
             "%10s%10.1f%10.1f%10.1f%10.1f%10.1f%10.1f%10.1f\n",
             sciField(m.CP).c_str(), 0.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0);
    out << buf;

    out << "$#       d5      eps1      eps2\n"
        << fldG(0.0) << fldG(0.0) << fldG(0.0) << "\n";
}

// ─────────────────────────────────────────────────────────────
// MAT_VISCOELASTIC (MAT_076)
// Fields: MID RO BULK G0 GINF BETA
// ─────────────────────────────────────────────────────────────
static void writeViscoelastic(std::ostream& out, int mid, double rho,
                               double bulk, double G0, double Ginf,
                               double beta, const char* name = "") {
    char buf[128];
    out << "*MAT_VISCOELASTIC_TITLE\n" << name << "\n"
        << "$#   mid        ro      bulk        g0      ginf      beta\n";
    snprintf(buf, sizeof(buf),
             "%10d%10s%10.1f%10.1f%10.1f%10.1f\n",
             mid, sciField(rho).c_str(), bulk, G0, Ginf, beta);
    out << buf;
}

// ─────────────────────────────────────────────────────────────
// MAT_ELASTIC (MAT_001)
// Fields: MID RO E PR DA DB K
// ─────────────────────────────────────────────────────────────
static void writeElastic(std::ostream& out, int mid, double rho,
                          double E, double nu, const char* name = "") {
    char buf[128];
    out << "*MAT_ELASTIC_TITLE\n" << name << "\n"
        << "$#   mid        ro         e        pr\n";
    snprintf(buf, sizeof(buf),
             "%10d%10s%10.1f%10.4f\n",
             mid, sciField(rho).c_str(), E, nu);
    out << buf;
}

// ─────────────────────────────────────────────────────────────
// MAT_PIECEWISE_LINEAR_PLASTICITY (MAT_024) — used for Sep/Pouch
// Simple elastic-perfectly-plastic approximation (no LCSS)
// Fields: MID RO E PR SIGY ETAN FAIL TDEL  (Card 1)
//         C P LCSS LCSR VP               (Card 2)
// ─────────────────────────────────────────────────────────────
static void writePLP(std::ostream& out, int mid, double rho,
                     double E, double nu, double sigy,
                     int lcss = 0, const char* name = "") {
    char buf[128];
    out << "*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE\n" << name << "\n"
        << "$#   mid        ro         e        pr      sigy      etan      fail      tdel\n";
    snprintf(buf, sizeof(buf),
             "%10d%10s%10.1f%10.4f%10.1f%10.1f%10.3f%10.3f\n",
             mid, sciField(rho).c_str(), E, nu, sigy, 0.0, 0.0, 0.0);
    out << buf;
    out << "$#       c         p      lcss      lcsr        vp\n"
        << fldG(0.0) << fldG(0.0) << iField(lcss) << iField(0) << iField(0) << "\n";
    if (lcss > 0) {
        // Cards 3 & 4 (EPS1-8, ES1-8): values ignored when LCSS>0, but
        // LS-DYNA R16 still reads them — write explicit blank cards
        out << "$#    eps1      eps2      eps3      eps4      eps5      eps6      eps7      eps8\n"
            << iField(0) << iField(0) << iField(0) << iField(0)
            << iField(0) << iField(0) << iField(0) << iField(0) << "\n"
            << "$#     es1       es2       es3       es4       es5       es6       es7       es8\n"
            << iField(0) << iField(0) << iField(0) << iField(0)
            << iField(0) << iField(0) << iField(0) << iField(0) << "\n";
    }
}

// ─────────────────────────────────────────────────────────────
// MAT_RIGID (MAT_020)
// Fields: MID RO E PR N COUPLE M ALIAS
// ─────────────────────────────────────────────────────────────
static void writeRigid(std::ostream& out, int mid, double rho, double E, double nu,
                       const char* name = "") {
    char buf[128];
    out << "*MAT_RIGID_TITLE\n" << name << "\n"
        << "$#   mid        ro         e        pr         n    couple         m     alias\n";
    snprintf(buf, sizeof(buf),
             "%10d%10s%10.1f%10.4f%10d%10d%10d%10s\n",
             mid, sciField(rho).c_str(), E, nu, 0, 0, 0, "");
    out << buf;
    // Card 2: constraint (CMO=0 free, CON1=0, CON2=0)
    out << "$#     cmo      con1      con2\n"
        << iField(0) << iField(0) << iField(0) << "\n";
    // Card 3: local coordinate system — must be included but may be blank
    out << "$#      a1        a2        a3        v1        v2        v3\n"
        << iField(0) << iField(0) << iField(0)
        << iField(0) << iField(0) << iField(0) << "\n";
}

// ─────────────────────────────────────────────────────────────
// MAT_NULL (MAT_009) — electrolyte buffer
// Fields: MID RO PC MU TEROD CEROD YM PR
// ─────────────────────────────────────────────────────────────
static void writeNull(std::ostream& out, int mid, double rho,
                      const char* name = "") {
    char buf[128];
    out << "*MAT_NULL_TITLE\n" << name << "\n"
        << "$#   mid        ro\n";
    snprintf(buf, sizeof(buf), "%10d%10s\n", mid, sciField(rho).c_str());
    out << buf;
}

// ─────────────────────────────────────────────────────────────
// MAT_THERMAL_ISOTROPIC (Phase 2)
// Fields: TMID TRO TGRLC TGMULT TLAT HLAT  (Card 1)
//         HC TC                              (Card 2)
// ─────────────────────────────────────────────────────────────
static void writeThermalIso(std::ostream& out, int tmid, double rho,
                             double cp, double k, const char* name = "") {
    char buf[128];
    out << "*MAT_THERMAL_ISOTROPIC_TITLE\n" << name << "\n"
        << "$#  tmid       tro     tgrlc    tgmult      tlat      hlat\n";
    snprintf(buf, sizeof(buf),
             "%10d%10s%10.1f%10.3f%10.1f%10.1f\n",
             tmid, sciField(rho).c_str(), 0.0, 1.0, 0.0, 0.0);
    out << buf;
    out << "$#       hc        tc\n";
    snprintf(buf, sizeof(buf), "%10s%10.4f\n", sciField(cp).c_str(), k);
    out << buf;
}

// ─────────────────────────────────────────────────────────────
// Public entry: writeMaterials
// ─────────────────────────────────────────────────────────────

void writeMaterials(std::ostream& out, const BatteryConfig& cfg) {
    writeComment(out, "Materials");

    const auto& a = cfg.matAl;
    const BatteryMatCu& cu = cfg.matCu;

    // ── Al CC — MAT_015 Johnson-Cook ──────────────────────────
    writeJohnsonCook(out, MID_AL, a, a.name.c_str());
    writeJohnsonCook(out, MID_CU, cu, cu.name.c_str());
    if (cfg.mergeCc)
        writeJohnsonCook(out, MID_CUAL, cfg.matCuAl, "CuAl_CC_Composite");

    // ── Electrodes ────────────────────────────────────────────
    // Phase 1 impact: viscoelastic (rate-dependent)
    // Phase 1 swell / Phase 2: elastic (DR needs time-independent material)
    if (cfg.phase == 1 && cfg.mode != "swell") {
        writeViscoelastic(out, MID_CAT, cfg.matCat.rho,
                          cfg.matCat.bulk, cfg.matCat.G0,
                          cfg.matCat.Ginf, cfg.matCat.beta, cfg.matCat.name.c_str());
        writeViscoelastic(out, MID_ANO, cfg.matAno.rho,
                          cfg.matAno.bulk, cfg.matAno.G0,
                          cfg.matAno.Ginf, cfg.matAno.beta, cfg.matAno.name.c_str());
    } else {
        writeElastic(out, MID_CAT, cfg.matCat.rho,
                     cfg.matCat.E_elas, cfg.matCat.nu_elas, cfg.matCat.name.c_str());
        writeElastic(out, MID_ANO, cfg.matAno.rho,
                     cfg.matAno.E_elas, cfg.matAno.nu_elas, cfg.matAno.name.c_str());
        // Record original viscoelastic properties as comments
        char vbuf[512];
        snprintf(vbuf, sizeof(vbuf),
            "$\n"
            "$ Original viscoelastic (MAT_076) properties for reference:\n"
            "$   Cathode: bulk=%.1f  G0=%.1f  Ginf=%.1f  beta=%.1f\n"
            "$   Anode:   bulk=%.1f  G0=%.1f  Ginf=%.1f  beta=%.1f\n"
            "$\n",
            cfg.matCat.bulk, cfg.matCat.G0, cfg.matCat.Ginf, cfg.matCat.beta,
            cfg.matAno.bulk, cfg.matAno.G0, cfg.matAno.Ginf, cfg.matAno.beta);
        out << vbuf;
    }

    // ── Separator — MAT_024 ───────────────────────────────────
    writePLP(out, MID_SEP, cfg.matSep.rho,
             cfg.matSep.E, cfg.matSep.nu, 100.0, LCID_SEP_STRESS, cfg.matSep.name.c_str());

    // ── Pouch — MAT_024 ───────────────────────────────────────
    writePLP(out, MID_POUCH, cfg.matPouch.rho,
             cfg.matPouch.E, cfg.matPouch.nu, 140.0, LCID_POUCH_STRESS, cfg.matPouch.name.c_str());

    // ── Rigid — MAT_020 (impactor + ground) ───────────────────
    writeRigid(out, MID_RIGID, 7.85e-9, 210000.0, 0.30, "Rigid_Steel");

    // ── Electrolyte ─────────────────────────────────────────────
    if (cfg.airbagFill) {
        writeNull(out, MID_ELYTE, cfg.matElyte.rho, "Electrolyte");
    }
    // Core fill needs MAT_ELASTIC (solid elements, not airbag)
    // Bulk ~2200 MPa, nu~0.45 → E = 3K(1-2nu) = 660 MPa
    writeElastic(out, MID_ELYTE_SOLID, cfg.matElyte.rho,
                 cfg.matElyte.bulkStacked * 3.0 * (1.0 - 2.0 * 0.45),
                 0.45, "Electrolyte_Solid");

    // ── Phase 2: Thermal materials ────────────────────────────
    if (cfg.phase == 2) {
        writeComment(out, "Thermal Materials (Phase 2)");
        writeThermalIso(out, TMID_AL,    a.rho,            a.CP,            a.cond,            (a.name+"_Thermal").c_str());
        writeThermalIso(out, TMID_CU,    cu.rho,           cu.CP,           cu.cond,           (cu.name+"_Thermal").c_str());
        writeThermalIso(out, TMID_CAT,   cfg.matCat.rho,   cfg.matCat.CP,   cfg.matCat.cond,   (cfg.matCat.name+"_Thermal").c_str());
        writeThermalIso(out, TMID_ANO,   cfg.matAno.rho,   cfg.matAno.CP,   cfg.matAno.cond,   (cfg.matAno.name+"_Thermal").c_str());
        writeThermalIso(out, TMID_SEP,   cfg.matSep.rho,   cfg.matSep.CP,   cfg.matSep.cond,   (cfg.matSep.name+"_Thermal").c_str());
        writeThermalIso(out, TMID_POUCH, cfg.matPouch.rho, cfg.matPouch.CP, cfg.matPouch.cond, (cfg.matPouch.name+"_Thermal").c_str());
    }
}

} // namespace bat
