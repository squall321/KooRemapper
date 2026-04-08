#pragma once
// =============================================================
// BatteryIds.h — PID / MID / SID / LCID constant assignments
// =============================================================

#include "BatteryConfig.h"
#include <string>

// ─────────────────────────────────────────────────────────────
// PID — Stacked model
// PID = 1000 + uc_index * 10 + layer_type  (UC 0-based)
// ─────────────────────────────────────────────────────────────
inline int bat_pid_stacked(int ucIdx, BatteryLayerType lt) {
    return 1000 + ucIdx * 10 + (int)lt;
}

// Special part IDs
constexpr int PID_POUCH_TOP    = 10;
constexpr int PID_POUCH_BOTTOM = 11;
constexpr int PID_POUCH_SIDE   = 12;
constexpr int PID_ELECTROLYTE  = 13;   // buffer / electrolyte fill
constexpr int PID_TAB_POS      = 20;   // positive (Al) tab
constexpr int PID_TAB_NEG      = 21;   // negative (Cu) tab
constexpr int PID_PCM_POS      = 30;   // PCM board positive side
constexpr int PID_PCM_NEG      = 31;   // PCM board negative side
constexpr int PID_INDENTER     = 100;
constexpr int PID_GROUND       = 101;

// ─────────────────────────────────────────────────────────────
// PID — Wound model (single set of layers, no UC index)
// ─────────────────────────────────────────────────────────────
constexpr int PID_W_AL  = 2001;
constexpr int PID_W_CAT = 2002;
constexpr int PID_W_SEP = 2003;
constexpr int PID_W_ANO = 2004;
constexpr int PID_W_CU  = 2005;
constexpr int PID_W_ELYTE        = 2006;  // (unused — box pouch, no elliptic ring)
constexpr int PID_W_POUCH_SIDE   = 2012;  // all 6 faces unified
constexpr int PID_W_TAB_POS      = 2020;  // Al (positive) tab
constexpr int PID_W_TAB_NEG      = 2021;  // Cu (negative) tab
constexpr int PID_W_PCM_POS      = 2030;  // PCM positive side
constexpr int PID_W_PCM_NEG      = 2031;  // PCM negative side

// ─────────────────────────────────────────────────────────────
// SECID — Section IDs (same numbering as MID for simplicity)
// ─────────────────────────────────────────────────────────────
// SHELL sections
constexpr int SID_SHELL_AL   = 1;
constexpr int SID_SHELL_SEP  = 3;
constexpr int SID_SHELL_CU   = 5;
constexpr int SID_SHELL_POUCH = 6;

// TSHELL section (electrodes + electrolyte)
constexpr int SID_SOLID_ELEC = 10;

// SOLID section (rigid: impactor, PCM, ground plate)
constexpr int SID_SOLID_RIGID = 11;
// SOLID section for merge_cc CuAl composite CC (ELFORM=2)
constexpr int SID_SOLID_CC = 12;
// SOLID section for stacked solid electrodes (configurable ELFORM)
constexpr int SID_SOLID_ELEC_STACK = 13;

// TSHELL sections (Phase 2, one per layer type)
constexpr int SID_TSHELL_AL  = 21;
constexpr int SID_TSHELL_CAT = 22;
constexpr int SID_TSHELL_SEP = 23;
constexpr int SID_TSHELL_ANO = 24;
constexpr int SID_TSHELL_CU  = 25;

// Rigid section for impactor / plate
constexpr int SID_RIGID = 50;

// ─────────────────────────────────────────────────────────────
// SECID — Wound model sections (single-sided electrode coating)
// ─────────────────────────────────────────────────────────────
constexpr int SID_W_SHELL_AL    = 1;   // reuse stacked (same thickness)
constexpr int SID_W_TSHELL_CAT  = 32;  // wound single-sided cathode TSHELL
constexpr int SID_W_SHELL_SEP   = 3;   // reuse stacked (same thickness)
constexpr int SID_W_TSHELL_ANO  = 34;  // wound single-sided anode TSHELL
constexpr int SID_W_SHELL_CU    = 5;   // reuse stacked (same thickness)
constexpr int SID_W_SHELL_ITS   = 3;   // inter-turn separator = same as SEP section
constexpr int SID_W_SOLID_ELEC  = 33;  // solid electrode section (solid_electrode=true, ELFORM=2)

// ─────────────────────────────────────────────────────────────
// MID — Material IDs
// ─────────────────────────────────────────────────────────────
constexpr int MID_AL    = 1;   // MAT_JOHNSON_COOK
constexpr int MID_CAT   = 2;   // Phase1: MAT_VISCOELASTIC  Phase2: MAT_ELASTIC
constexpr int MID_SEP   = 3;   // MAT_024 PIECEWISE_LINEAR_PLASTICITY
constexpr int MID_ANO   = 4;   // Phase1: MAT_VISCOELASTIC  Phase2: MAT_ELASTIC
constexpr int MID_CU    = 5;   // MAT_JOHNSON_COOK
constexpr int MID_POUCH = 6;   // MAT_024
constexpr int MID_RIGID = 7;   // MAT_RIGID (impactor + plate)
constexpr int MID_ELYTE = 8;   // MAT_NULL or MAT_ELASTIC (electrolyte)
constexpr int MID_CUAL  = 9;   // MAT_JOHNSON_COOK CuAl composite (merge_cc)
constexpr int MID_ELYTE_SOLID = 15;  // MAT_ELASTIC for core fill electrolyte

// Thermal MIDs (Phase 2 only) — offset +100
constexpr int TMID_AL   = 101;
constexpr int TMID_CU   = 102;
constexpr int TMID_CAT  = 113;
constexpr int TMID_ANO  = 114;
constexpr int TMID_SEP  = 105;
constexpr int TMID_POUCH= 106;

// ─────────────────────────────────────────────────────────────
// HGID — Hourglass IDs
// ─────────────────────────────────────────────────────────────
constexpr int HGID_SOLID = 1;   // IHQ=4, QH=0.05 for solids
constexpr int HGID_SHELL = 2;   // IHQ=4, QH=0.10 for shells

// ─────────────────────────────────────────────────────────────
// SID — Set IDs (NODE/PART lists)
// ─────────────────────────────────────────────────────────────
constexpr int SID_NODE_FIX_BOT  = 1;     // bottom edge fixed nodes (SPC)
constexpr int SID_NODE_INDENTER = 2;     // impactor all nodes (prescribed motion)
constexpr int SID_NODE_GROUND   = 3;     // ground plate nodes (SPC)
constexpr int SID_PART_CELL     = 102;   // all cell parts (contact MSID)
constexpr int SID_SEG_POUCH_LOAD = 503;  // pouch outer segments for bare-mode LOAD_SEGMENT_SET
constexpr int SID_SEG_AIRBAG    = 504;   // airbag segments (matches Python SID_AIRBAG_ELEC)
constexpr int SID_NODE_TOPSTACK = 1002;  // top-of-stack nodes (Phase2 BC)

// ─────────────────────────────────────────────────────────────
// CID — Contact IDs
// ─────────────────────────────────────────────────────────────
constexpr int CID_INDENT_TO_CELL = 1;
constexpr int CID_CELL_SELF      = 2;
// Tied contacts: CID_TIED_BASE + layer/uc index
constexpr int CID_TIED_BASE      = 10;

// ─────────────────────────────────────────────────────────────
// LCID — Load Curve IDs
// ─────────────────────────────────────────────────────────────
constexpr int LCID_SEP_STRESS    = 9001;  // separator stress-strain
constexpr int LCID_POUCH_STRESS  = 9002;  // pouch stress-strain
constexpr int LCID_INDENT_DISP   = 9901;  // indenter displacement vs. time
constexpr int LCID_SOC_TIME      = 9903;  // SOC vs. time (Phase 2 thermal proxy)
constexpr int LCID_SWELL_RAMP   = 9904;  // swell temperature ramp (DR)

// ─────────────────────────────────────────────────────────────
// Derived helpers
// ─────────────────────────────────────────────────────────────

// Is this PID a stacked electrode (cathode or anode)?
inline bool bat_pidIsElectrode(int pid) {
    int local = pid % 10;
    return (local == LT_CAT || local == LT_ANO) && (pid >= 1000);
}

// Unit cell index from stacked PID
inline int bat_ucFromPid(int pid) {
    return (pid - 1000) / 10;
}

// Layer type from stacked PID
inline BatteryLayerType bat_layerFromPid(int pid) {
    return static_cast<BatteryLayerType>(pid % 10);
}
