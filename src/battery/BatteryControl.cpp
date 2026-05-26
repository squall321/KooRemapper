#include "BatteryControl.h"
#include "BatteryWriter.h"
#include "BatteryIds.h"
#include <ostream>
#include <cstdio>
#include <vector>
#include <utility>
#include <cmath>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

// ─────────────────────────────────────────────────────────────
// Control cards
// ─────────────────────────────────────────────────────────────

void writeControlCards(std::ostream& out, const BatteryConfig& cfg) {
    writeComment(out, "Control Cards");
    char buf[128];

    bool isBare  = (cfg.mode == "bare" || cfg.mode == "swell");

    // *CONTROL_SOLUTION
    out << "*CONTROL_SOLUTION\n"
        << "$#  soln      nlq    isnan    lcint\n"
        << iField(0) << iField(0) << iField(0) << iField(0) << "\n";

    // *CONTROL_DYNAMIC_RELAXATION (bare mode only)
    if (isBare) {
        out << "*CONTROL_DYNAMIC_RELAXATION\n"
            << "$#  nrcyck     drtol    drfctr    drterm    tssfdr    irelal     edttl    idrflg\n";
        snprintf(buf, sizeof(buf),
                 "%10d%10.1E%10.4f%10.3f%10.4f%10d%10d%10d\n",
                 cfg.drNrcyck, cfg.drTolerance, cfg.drFactor,
                 0.0, 0.0, 0, 0, 0);
        out << buf;
    }

    // *CONTROL_TERMINATION
    out << "*CONTROL_TERMINATION\n"
        << "$#  endtim    endcyc     dtmin    endneg    endmas\n";
    double endtim = isBare ? cfg.drEndtim : cfg.terminationTime;
    snprintf(buf, sizeof(buf), "%10.4E%10d%10d%10d%10d\n",
             endtim, 0, 0, 0, 0);
    out << buf;

    // *CONTROL_TIMESTEP  DTINIT TSSFAC ISDO TSLIMT DT2MS LCTM ERODE MS1ST
    out << "*CONTROL_TIMESTEP\n"
        << "$#  dtinit    tssfac      isdo    tslimt     dt2ms      lctm     erode     ms1st\n";
    double tslimt = 0.0;
    snprintf(buf, sizeof(buf),
             "%10.3f%10.4f%10d%10.2E%10.2E%10d%10d%10d\n",
             0.0, cfg.tssfac, 0, tslimt, cfg.dt2ms, 0, 1, 0);
    out << buf;

    // *CONTROL_SHELL  WRPANG ESORT IRNXX ISTUPD THEORY BWC MITER PROJ
    out << "*CONTROL_SHELL\n"
        << "$#  wrpang     esort     irnxx    istupd    theory       bwc     miter      proj\n"
        << iField(20) << iField(1) << iField(-1) << iField(1)
        << iField(2) << iField(2) << iField(1) << iField(0) << "\n"
        // Card 2: ROTASCL INTGRD LAMSHT CSTYP6 THSHEL
        << "$# rotascl    intgrd    lamsht    cstyp6    thshel\n"
        << fldG(1.0) << iField(0) << iField(0) << iField(1) << iField(1) << "\n";

    // *CONTROL_SOLID  ESORT FMATRX NIPTETS SWLOCL PSFAIL
    out << "*CONTROL_SOLID\n"
        << "$#  esort    fmatrx   niptets    swlocl    psfail\n"
        << iField(1) << iField(0) << iField(0) << iField(0) << iField(0) << "\n";

    // *CONTROL_CONTACT  SLSFAC RWPNAL ISLCHK SHLTHK PENOPT THKCHG ORIEN ENMASS
    out << "*CONTROL_CONTACT\n"
        << "$#  slsfac    rwpnal    islchk    shlthk    penopt    thkchg     orien    enmass\n";
    snprintf(buf, sizeof(buf),
             "%10.4f%10.3f%10d%10d%10d%10d%10d%10d\n",
             0.10, 0.0, 1, 1, 1, 0, 1, 0);
    out << buf;
    // Card 2: usrstr usrfrc nsbcs interm xpene ssthk ecdt tiedprj
    out << "$# usrstr    usrfrc     nsbcs    interm     xpene     ssthk      ecdt   tiedprj\n"
        << "         0         0         0         0         4         0         0         0\n";

    // *CONTROL_ENERGY  HGEN RWEN SLNTEN RYLEN
    out << "*CONTROL_ENERGY\n"
        << "$#   hgen      rwen    slnten     rylen\n"
        << iField(2) << iField(2) << iField(2) << iField(2) << "\n";

    // *CONTROL_HOURGLASS  IHQ QH  (global default)
    out << "*CONTROL_HOURGLASS\n"
        << "$#    ihq        qh\n"
        << iField(1) << fldG(0.10) << "\n";

    // *CONTROL_BULK_VISCOSITY  Q1 Q2 TYPE
    out << "*CONTROL_BULK_VISCOSITY\n"
        << "$#       q1        q2      type\n"
        << fldG(1.5) << fldG(0.06) << iField(1) << "\n";

    // Phase 2 additional thermal control
    if (cfg.phase == 2) {
        out << "*CONTROL_SOLUTION\n"
            << "$#  soln      nlq    isnan    lcint\n"
            << iField(2) << iField(0) << iField(0) << iField(0) << "\n";

        out << "*CONTROL_THERMAL_SOLVER\n"
            << "$#  atype     ptype    solver      cgtol      gpt    eqheat     fwork     sbc\n"
            << iField(1) << iField(1) << iField(12)
            << fldG(1.0e-4) << iField(0) << fldG(1.0) << fldG(0.90) << fldG(0.0) << "\n"
            << "$#  msglvl   maxitr     abstol     reltol     omega      lcid\n"
            << iField(0) << iField(500) << fldG(1.0e-10) << fldG(1.0e-4) << fldG(1.0) << iField(0) << "\n";

        out << "*CONTROL_THERMAL_TIMESTEP\n"
            << "$#     ts       tip       its      tmin      tmax     dtemp      tscp      lcts\n"
            << iField(0) << fldG(0.5) << fldG(1.0e-5)
            << fldG(0.0) << fldG(0.0) << fldG(1.0) << fldG(0.5) << iField(0) << "\n";
    }
}

// ─────────────────────────────────────────────────────────────
// Boundary cards
// ─────────────────────────────────────────────────────────────

void writeBoundaryCards(std::ostream& out, const BatteryConfig& cfg) {
    writeComment(out, "Boundary Conditions");
    char buf[128];

    if (cfg.mode == "bare" || cfg.mode == "swell") {
        // DR modes: no impactor. Fix node 1 (innermost) XYZ for rigid-body prevention.
        out << "$ DR mode: rigid body prevention — fix node 1 XYZ\n"
            << "*BOUNDARY_SPC_NODE\n"
            << "$#    nid       cid      dofx      dofy      dofz     dofrx     dofry     dofrz\n";
        snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d\n",
                 1, 0, 1, 1, 1, 0, 0, 0);
        out << buf;

        if (cfg.mode == "bare") {
            // External pressure on pouch outer surface
            out << "$\n$ External pressure on pouch (LOAD_SEGMENT_SET)\n"
                << "*LOAD_SEGMENT_SET\n"
                << "$#    sid      lcid        sf        at        dt      ramp      stype     tmid\n";
            snprintf(buf, sizeof(buf), "%10d%10d%10.4f%10.3f%10.4E%10d%10d%10d\n",
                     SID_SEG_POUCH_LOAD, LCID_INDENT_DISP,
                     -cfg.externalPressure,
                     0.0, 0.0, 0, 0, 0);
            out << buf;
        }
        // swell: *INITIAL_STRAIN_SOLID drives deformation — no external BC needed
        return;
    }

    // Impact modes (dent / side / swelling)
    // SPC for indenter: constrain X,Y, rotations; free Z
    // DOF: 1=X, 2=Y, 3=Z, 4=RX, 5=RY, 6=RZ  (1=constrained, 0=free)
    out << "*BOUNDARY_SPC_SET\n"
        << "$#  nsid    cid     dofx     dofy     dofz     dofrx    dofry    dofrz\n";
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d\n",
             SID_NODE_INDENTER, 0, 1, 1, 0, 1, 1, 1);
    out << buf;

    // SPC for ground plate: fully fixed
    out << "*BOUNDARY_SPC_SET\n";
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d\n",
             SID_NODE_GROUND, 0, 1, 1, 1, 1, 1, 1);
    out << buf;

    // Indenter prescribed Z displacement (dent/side modes)
    if (cfg.mode == "dent" || cfg.mode == "side") {
        int dof = (cfg.mode == "dent") ? 3 : 1;  // dent=Z(3), side=-X(1)
        out << "*BOUNDARY_PRESCRIBED_MOTION_SET\n"
            << "$#  nsid     dof     vad      lcid      sf     vid     death    birth\n";
        snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10.3f%10d%10.4E%10.4f\n",
                 SID_NODE_INDENTER, dof, 2, LCID_INDENT_DISP, 1.0, 0, 1.0e28, 0.0);
        out << buf;
    }
}

// ─────────────────────────────────────────────────────────────
// Load curves
// ─────────────────────────────────────────────────────────────

void writeCurves(std::ostream& out, const BatteryConfig& cfg) {
    writeComment(out, "Load Curves");

    if (cfg.mode == "bare" || cfg.mode == "swell") {
        if (cfg.mode == "bare") {
            // Pressure ramp-up curve for LOAD_SEGMENT_SET
            double tRamp = cfg.drEndtim * 0.5;
            std::vector<std::pair<double,double>> pts = {
                {0.0,    0.0},
                {tRamp,  1.0},
                {cfg.drEndtim, 1.0}
            };
            writeDefineCurve(out, LCID_INDENT_DISP, "External_Pressure_Ramp", pts);
        }
        // Separator + Pouch curves needed for inter-layer contact
        // Slopes must not exceed Young's modulus to avoid Warning 30210:
        //   Sep E=3000: {0.0,0}→{0.033,90} slope=2727 < 3000 ✓
        //   Pouch E=69000: {0.0,0}→{0.0011,70} slope=63636 < 69000 ✓
        {
            std::vector<std::pair<double,double>> sp = {
                {0.0, 0.0}, {0.033, 90.0}, {0.10, 100.0}, {0.40, 150.0}, {0.60, 80.0}
            };
            writeDefineCurve(out, LCID_SEP_STRESS,   "Separator_Stress_Strain", sp);
        }
        {
            std::vector<std::pair<double,double>> pp = {
                {0.0, 0.0}, {0.0011, 70.0}, {0.05, 110.0}, {0.20, 140.0}
            };
            writeDefineCurve(out, LCID_POUCH_STRESS, "Pouch_Stress_Strain", pp);
        }
        return;
    }

    // Impact modes — Indenter displacement ramp + hold
    {
        double tEnd = cfg.terminationTime;
        double tRamp = cfg.rampTime;
        double disp  = cfg.displacement;
        std::vector<std::pair<double,double>> pts;
        pts.push_back({0.0,        0.0});
        pts.push_back({tRamp,      disp});
        if (cfg.hold && tEnd > tRamp * 1.1) {
            pts.push_back({tEnd, disp});  // hold at peak
        }
        writeDefineCurve(out, LCID_INDENT_DISP, "Indenter_Displacement", pts);
    }

    // Separator stress-strain (bilinear approx, PE film)
    // Slope at {0.033, 90}: 2727 < E=3000 — no Warning 30210
    {
        std::vector<std::pair<double,double>> pts = {
            {0.0,   0.0},
            {0.033, 90.0},
            {0.10,  100.0},
            {0.40,  150.0},
            {0.60,  80.0}   // after yield/fracture
        };
        writeDefineCurve(out, LCID_SEP_STRESS, "Separator_Stress_Strain", pts);
    }

    // Pouch stress-strain (Al laminate)
    // Slope at {0.0011, 70}: 63636 < E=69000 — no Warning 30210
    {
        std::vector<std::pair<double,double>> pts = {
            {0.0,    0.0},
            {0.0011, 70.0},
            {0.05,   110.0},
            {0.20,   140.0}
        };
        writeDefineCurve(out, LCID_POUCH_STRESS, "Pouch_Stress_Strain", pts);
    }
}

// ─────────────────────────────────────────────────────────────
// Database output cards
// ─────────────────────────────────────────────────────────────

void writeDatabaseCards(std::ostream& out, const BatteryConfig& cfg) {
    writeComment(out, "Database Output");
    char buf[128];

    double dt = cfg.outputInterval;

    out << "*DATABASE_BINARY_D3PLOT\n"
        << "$#      dt    lcdt      beam     npltc    psetid\n";
    snprintf(buf, sizeof(buf), "%10.4E%10d%10d%10d%10d\n", dt, 0, 0, 0, 0);
    out << buf;

    out << "*DATABASE_GLSTAT\n"
        << "$#      dt  binary    lcur    ioopt\n";
    snprintf(buf, sizeof(buf), "%10.4E%10d%10d%10d\n", dt * 0.1, 1, 0, 1);
    out << buf;

    out << "*DATABASE_MATSUM\n";
    snprintf(buf, sizeof(buf), "%10.4E%10d%10d%10d\n", dt * 0.1, 1, 0, 1);
    out << buf;

    out << "*DATABASE_RCFORC\n";
    snprintf(buf, sizeof(buf), "%10.4E%10d%10d%10d\n", dt * 0.1, 1, 0, 1);
    out << buf;

    out << "*DATABASE_EXTENT_BINARY\n"
        << "$#   neiph     neips    maxint    strflg    sigflg    epsflg    rltflg    engflg\n"
        << iField(0) << iField(0) << iField(3) << iField(1)
        << iField(1) << iField(1) << iField(1) << iField(1) << "\n"
        << "$#  cmpflg    ieverp    beamip      dcomp     shge     stssz    n3thdt   ialemat\n"
        << iField(0) << iField(0) << iField(0) << iField(1)
        << iField(1) << iField(1) << iField(1) << iField(0) << "\n";
}

} // namespace bat
