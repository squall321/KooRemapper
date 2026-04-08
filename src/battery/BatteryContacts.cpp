#include "BatteryContacts.h"
#include "BatteryWriter.h"
#include "BatteryIds.h"
#include <ostream>
#include <cstdio>
#include <vector>

namespace bat {

// ─────────────────────────────────────────────────────────────
// Helper: write CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID
//   SSTYP=3 (part set), MSTYP=3 (part set)
// ─────────────────────────────────────────────────────────────
static void writeA2S(std::ostream& out, int cid, const std::string& title,
                     int ssid, int msid, int sstyp, int mstyp,
                     double sofscl, double sst, double mst) {
    char buf[256];
    // Header
    out << "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID\n";
    snprintf(buf, sizeof(buf), "$ %s\n%10d\n", title.c_str(), cid);
    out << buf;

    // Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
    out << "$#      ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n";
    snprintf(buf, sizeof(buf),
             "%10d%10d%10d%10d%10d%10d%10d%10d\n",
             ssid, msid, sstyp, mstyp, 0, 0, 0, 0);
    out << buf;

    // Card 2: VDC=20 suppresses contact oscillations during DR
    out << "$#       fs        fd        dc        vc       vdc    penchk        bt        dt\n"
        << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(20.0)
        << iField(0) << fldG(0.0) << fldG(1.0e20) << "\n";

    // Card 3: SFS SFM SST MST SFST SFMT FSF VSF
    out << "$#      sfs       sfm       sst       mst      sfst      sfmt       fsf       vsf\n";
    snprintf(buf, sizeof(buf),
             "%10.3f%10.3f%10.4f%10.4f%10.3f%10.3f%10.3f%10.3f\n",
             1.0, 1.0, sst, mst, 1.0, 1.0, 1.0, 1.0);
    out << buf;

    // Card A: SOFT SOFSCL LCIDAB MAXPAR SBOPT DEPTH BSORT FRCFRQ
    out << "$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq\n";
    snprintf(buf, sizeof(buf),
             "%10d%10.4f%10d%10.4f%10.3f%10d%10d%10d\n",
             1, sofscl, 0, 1.375, 3.0, 5, 0, 1);
    out << buf;

    // Card C (optional): IGNORE BCKT LCBCKT NS2TRK INITITR PARTEFX CPARM8_
    out << "$#  ignore      bckt    lcbckt   ns2trk    initrk   partefx    cparm8\n";
    snprintf(buf, sizeof(buf),
             "%10d%10d%10d%10d%10d%10d%10d\n",
             1, 0, 0, 0, 0, 0, 0);
    out << buf;
}

// ─────────────────────────────────────────────────────────────
// Helper: write CONTACT_AUTOMATIC_SINGLE_SURFACE_ID
// ─────────────────────────────────────────────────────────────
static void writeASS(std::ostream& out, int cid, const std::string& title,
                     int ssid, int sstyp, double sofscl, double sst) {
    char buf[256];
    out << "*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID\n";
    snprintf(buf, sizeof(buf), "$ %s\n%10d\n", title.c_str(), cid);
    out << buf;

    // Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
    out << "$#      ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n";
    snprintf(buf, sizeof(buf),
             "%10d%10d%10d%10d%10d%10d%10d%10d\n",
             ssid, 0, sstyp, 0, 0, 0, 0, 0);
    out << buf;

    // Card 2: VDC=20 suppresses contact oscillations during DR
    out << "$#       fs        fd        dc        vc       vdc    penchk        bt        dt\n"
        << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(20.0)
        << iField(0) << fldG(0.0) << fldG(1.0e20) << "\n";

    // Card 3
    out << "$#      sfs       sfm       sst       mst      sfst      sfmt       fsf       vsf\n";
    snprintf(buf, sizeof(buf),
             "%10.3f%10.3f%10.4f%10.4f%10.3f%10.3f%10.3f%10.3f\n",
             1.0, 1.0, sst, sst, 1.0, 1.0, 1.0, 1.0);
    out << buf;

    // Card A: SOFT=2 (segment-based, more stable for thin elements)
    out << "$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq\n";
    snprintf(buf, sizeof(buf),
             "%10d%10.4f%10d%10.4f%10.3f%10d%10d%10d\n",
             2, sofscl, 0, 1.375, 3.0, 5, 0, 1);
    out << buf;

    // Card C: IGNORE=1 to handle initial penetrations in wound mesh
    out << "$#  ignore      bckt    lcbckt   ns2trk    initrk   partefx    cparm8\n";
    snprintf(buf, sizeof(buf),
             "%10d%10d%10d%10d%10d%10d%10d\n",
             1, 0, 0, 0, 0, 0, 0);
    out << buf;
}

// ─────────────────────────────────────────────────────────────
// Helper: CONTACT_TIED_SURFACE_TO_SURFACE_ID
//   Used to bond adjacent layers in Phase 1 (SOLID+SHELL)
//   SSID = slave part PID, MSID = master part PID (SSTYP=MSTYP=3=part)
// ─────────────────────────────────────────────────────────────
static void writeTied(std::ostream& out, int cid, const std::string& title,
                      int slavePid, int masterPid) {
    char buf[256];
    out << "*CONTACT_TIED_SURFACE_TO_SURFACE_ID\n";
    // ID card: CID only (no HEADING to avoid plabel parse issues in R16.1)
    snprintf(buf, sizeof(buf), "$ %s\n%10d\n", title.c_str(), cid);
    out << buf;

    // Card 1: SSID MSID SSTYP=3 MSTYP=3 (10-char fields)
    snprintf(buf, sizeof(buf),
             "%10d%10d%10d%10d%10d%10d%10d%10d\n",
             slavePid, masterPid, 3, 3, 0, 0, 0, 0);
    out << buf;

    // Mandatory Card 2: FS FD DC VC VDC PENCHK BT DT
    out << "$#       fs        fd        dc        vc       vdc    penchk        bt        dt\n"
        << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(0.0)
        << iField(0) << fldG(0.0) << fldG(1.0e20) << "\n";

    // Mandatory Card 3: SFS SFM SST MST SFST SFMT FSF VSF
    out << "$#      sfs       sfm       sst       mst      sfst      sfmt       fsf       vsf\n"
        << fldG(1.0) << fldG(1.0) << fldG(0.0) << fldG(0.0)
        << fldG(1.0) << fldG(1.0) << fldG(1.0) << fldG(1.0) << "\n";
}

// ─────────────────────────────────────────────────────────────
// Main entry
// ─────────────────────────────────────────────────────────────

void writeContacts(std::ostream& out, const BatteryConfig& cfg,
                   int nUnitCells,
                   const std::vector<int>& cellPids) {
    writeComment(out, "Contacts (SOFT=1)");

    double meshSize = batteryMeshSize(cfg.tier);
    double sofscl   = batterySofscl(meshSize,
                                    cfg.contact.sofscl_base,
                                    5.0,
                                    cfg.contact.sofscl_pow);

    // 1. Indenter → Cell (part 100 → part set 102)
    //    Skipped in bare/swell mode (no impactor)
    bool isBare = (cfg.mode == "bare" || cfg.mode == "swell");
    if (!isBare) {
        writeA2S(out, CID_INDENT_TO_CELL, "Indenter_to_Cell",
                 PID_INDENTER,          // slave: indenter part
                 SID_PART_CELL,         // master: all cell parts (set)
                 3,                     // SSTYP=3 (part)
                 2,                     // MSTYP=2 (part set)
                 sofscl,
                 cfg.contact.sst_ext, cfg.contact.sst_ext);
    }

    // 2. Cell self-contact (part set 102)
    writeASS(out, CID_CELL_SELF, "Cell_Self_Contact",
             SID_PART_CELL, 2, sofscl, cfg.contact.sst_self);

    // 3. TIED contacts (Phase 1: SOLID+SHELL need bonding)
    //    Phase 2: TSHELL nodes are shared → no TIED needed in jellyroll
    //    But both phases need TIED at pouch ↔ jellyroll boundary.
    if (cfg.phase == 1) {
        // Within each unit cell: Al↔Cathode, Sep↔Anode (SHELL slave, SOLID master)
        // Between unit cells: Cu(uc) ↔ Al(uc+1) — but these SHARE nodes, no TIED needed
        // (per P2 resolution: UC boundary Cu→Al shares nodes directly)
        int cid = CID_TIED_BASE;
        for (int uc = 0; uc < nUnitCells; ++uc) {
            // Sep ↔ bottom of next UC Cathode (if Sep is modeled separately)
            // In Phase 1 these are shared nodes, so no TIED needed at layer boundaries
            // We only need TIED at the buffer ↔ jellyroll interface
            (void)cid;
            (void)uc;
        }
        // Pouch bottom ↔ jellyroll bottom (Al CC of UC0)
        int alPid0 = bat_pid_stacked(0, LT_AL);
        writeTied(out, CID_TIED_BASE,     "Pouch_Bot_to_Jelly",
                  PID_POUCH_BOTTOM, alPid0);
        // Pouch top ↔ jellyroll top (Cu CC of last UC)
        int cuPidLast = bat_pid_stacked(nUnitCells - 1, LT_CU);
        writeTied(out, CID_TIED_BASE + 1, "Pouch_Top_to_Jelly",
                  PID_POUCH_TOP, cuPidLast);
    } else {
        // Phase 2: only pouch↔jellyroll TIED (TSHELL internal nodes shared)
        int alPid0 = bat_pid_stacked(0, LT_AL);
        writeTied(out, CID_TIED_BASE,     "Pouch_Bot_to_Jelly",
                  PID_POUCH_BOTTOM, alPid0);
        int cuPidLast = bat_pid_stacked(nUnitCells - 1, LT_CU);
        writeTied(out, CID_TIED_BASE + 1, "Pouch_Top_to_Jelly",
                  PID_POUCH_TOP, cuPidLast);
    }

    (void)cellPids;
}

} // namespace bat
