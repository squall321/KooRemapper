#pragma once
// =============================================================
// BatteryWriter.h — K-file formatting utilities for battery
// =============================================================
// All output routines write to a std::ostream (usually ostringstream
// that feeds into the final K-file).
// Units: t/mm/s throughout (MPa, N, ton).
// =============================================================

#include <ostream>
#include <string>
#include <vector>
#include <utility>
#include <cstdio>

namespace bat {

// ── Fixed-width field helpers ──────────────────────────────────

// Right-aligned integer in width-char field
inline std::string iField(int v, int w = 10) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%*d", w, v);
    return std::string(buf);
}

// Right-aligned float in 10-char field (scientific notation)
inline std::string fField(double v, int w = 10) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%*g", w, v);
    // If it doesn't fit, use scientific
    if ((int)std::string(buf).size() > w) {
        snprintf(buf, sizeof(buf), "%*.4E", w, v);
    }
    return std::string(buf);
}

// Force scientific notation in 10-char field: e.g. "2.7000E-09"
inline std::string sciField(double v, int w = 10) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%*.4E", w, v);
    return std::string(buf);
}

// Right-aligned float in 10-char field, general notation
inline std::string fldG(double v) { return fField(v, 10); }
inline std::string fldI(int v)    { return iField(v, 10); }
inline std::string fldS(double v) { return sciField(v, 10); }

// Write comment header for a section
inline void writeComment(std::ostream& out, const std::string& text) {
    out << "$\n$ --- " << text << " ---\n$\n";
}

// Write a blank keyword separator
inline void writeSeparator(std::ostream& out) {
    out << "$\n";
}

// ── Common keyword builders ────────────────────────────────────

// *PART  (no title variant — always outputs title line)
// PID SID MID EOSID HGID GRAV ADPOPT TMID
inline void writePart(std::ostream& out,
                      const std::string& title,
                      int pid, int sid, int mid,
                      int hgid = 0, int tmid = 0) {
    out << "*PART\n"
        << title << "\n"
        << iField(pid) << iField(sid) << iField(mid)
        << iField(0)   // EOSID
        << iField(hgid)
        << iField(0)   // GRAV
        << iField(0)   // ADPOPT
        << iField(tmid) << "\n";
}

// *SECTION_SHELL
// Card 1: SID  ELFORM  SHRF  NIP  PROPT  QR/IRID  ICOMP  SETYP
// Card 2: T1   T2      T3    T4
inline void writeSectionShell(std::ostream& out,
                               int sid, int elform, double thick,
                               int nip = 5, double shrf = 0.8333) {
    out << "*SECTION_SHELL\n"
        << iField(sid) << iField(elform)
        << fldG(shrf)  << iField(nip)
        << iField(1)   << iField(0) << iField(0) << iField(1) << "\n"   // PROPT=1 QR=0 ICOMP=0 SETYP=1
        << fldG(thick) << fldG(thick) << fldG(thick) << fldG(thick) << "\n";
}

// *SECTION_SOLID  SID ELFORM AET
inline void writeSectionSolid(std::ostream& out, int sid, int elform = 1) {
    out << "*SECTION_SOLID\n"
        << iField(sid) << iField(elform) << "\n";
}

// *SECTION_TSHELL  SID ELFORM SHRF NIP
inline void writeSectionTshell(std::ostream& out,
                                int sid, int elform = 1, int nip = 3) {
    out << "*SECTION_TSHELL\n"
        << iField(sid) << iField(elform)
        << fldG(0.8333) << iField(nip) << "\n";
}

// *HOURGLASS  HGID IHQ QH
inline void writeHourglass(std::ostream& out, int hgid, int ihq, double qh) {
    out << "*HOURGLASS\n"
        << iField(hgid) << iField(ihq) << fldG(qh) << "\n";
}

// Write *NODE block header
inline void writeNodeHeader(std::ostream& out) {
    out << "*NODE\n"
        << "$#   nid               x               y               z\n";
}

// Write a single node line (free-format, 16-char fields)
inline void writeNode(std::ostream& out, int nid, double x, double y, double z) {
    char buf[128];
    snprintf(buf, sizeof(buf), "%8d%16.6f%16.6f%16.6f\n", nid, x, y, z);
    out << buf;
}

// Write *ELEMENT_SHELL header
inline void writeShellHeader(std::ostream& out) {
    out << "*ELEMENT_SHELL\n"
        << "$#   eid     pid      n1      n2      n3      n4\n";
}

// Write a single SHELL element (8-char fields)
inline void writeShell(std::ostream& out, int eid, int pid,
                        int n1, int n2, int n3, int n4) {
    char buf[128];
    snprintf(buf, sizeof(buf), "%8d%8d%8d%8d%8d%8d\n",
             eid, pid, n1, n2, n3, n4);
    out << buf;
}

// Write *ELEMENT_SOLID header
inline void writeSolidHeader(std::ostream& out) {
    out << "*ELEMENT_SOLID\n"
        << "$#   eid     pid      n1      n2      n3      n4"
           "      n5      n6      n7      n8\n";
}

// Write a single SOLID (HEX8) element
inline void writeSolid(std::ostream& out, int eid, int pid,
                        int n1, int n2, int n3, int n4,
                        int n5, int n6, int n7, int n8) {
    char buf[128];
    snprintf(buf, sizeof(buf),
             "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d\n",
             eid, pid, n1, n2, n3, n4, n5, n6, n7, n8);
    out << buf;
}

// Write *ELEMENT_TSHELL header
inline void writeTshellHeader(std::ostream& out) {
    out << "*ELEMENT_TSHELL\n"
        << "$#   eid     pid      n1      n2      n3      n4"
           "      n5      n6      n7      n8\n";
}
// TSHELL connectivity same format as SOLID
inline void writeTshell(std::ostream& out, int eid, int pid,
                         int n1, int n2, int n3, int n4,
                         int n5, int n6, int n7, int n8) {
    writeSolid(out, eid, pid, n1, n2, n3, n4, n5, n6, n7, n8);
}

// *INITIAL_STRAIN_SOLID: one element per block
// eid, then epsxx epsyy epszz epsxy epsyz epszx
inline void writeInitialStrainSolid(std::ostream& out, int eid,
                                     double exx, double eyy, double ezz,
                                     double exy = 0.0, double eyz = 0.0,
                                     double exz = 0.0) {
    out << "*INITIAL_STRAIN_SOLID\n"
        << "$#     eid\n"
        << "$#   epsxx     epsyy     epszz     epsxy     epsyz     epszx\n";
    char buf[128];
    snprintf(buf, sizeof(buf), "%10d\n", eid);
    out << buf;
    snprintf(buf, sizeof(buf), "%10.6f%10.6f%10.6f%10.6f%10.6f%10.6f\n",
             exx, eyy, ezz, exy, eyz, exz);
    out << buf;
}

// *SET_NODE_LIST_TITLE  SID, then 8 NIDs per line (0-padded)
void writeSetNodeList(std::ostream& out, int sid,
                      const std::string& title,
                      const std::vector<int>& nids);

// *SET_PART_LIST_TITLE  SID, then 8 PIDs per line
void writeSetPartList(std::ostream& out, int sid,
                      const std::string& title,
                      const std::vector<int>& pids);

// *DEFINE_CURVE_TITLE  LCID, then (time, value) pairs
void writeDefineCurve(std::ostream& out, int lcid,
                      const std::string& title,
                      const std::vector<std::pair<double,double>>& pts);

} // namespace bat
