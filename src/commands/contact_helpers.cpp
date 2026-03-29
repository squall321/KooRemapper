#include "contact_helpers.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"
#include "core/Mesh.h"
#include "core/Vector3D.h"
#include <string>
#include <vector>
#include <map>
#include <set>
#include <array>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <unordered_map>

using namespace KooRemapper;

std::vector<ContactDef> ct_parseContacts(const std::vector<std::string>& lines) {
    std::vector<ContactDef> result;
    int idx = 0;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = kw_upper(tr);
        if (up.rfind("*CONTACT_", 0) != 0) continue;
        // Skip *CONTACT comment lines
        if (up.size() >= 2 && up[1] == '$') continue;

        ContactDef c;
        c.startLine = i;
        c.fullKeyword = tr;
        c.index = idx++;

        // Extract type: remove "*CONTACT_" prefix, then strip _TITLE/_ID suffix
        std::string typeStr = up.substr(9);  // after "*CONTACT_"
        c.hasTitle = false;
        // Check _TITLE suffix
        {
            size_t pos = typeStr.rfind("_TITLE");
            if (pos != std::string::npos && pos == typeStr.size() - 6) {
                c.hasTitle = true;
                typeStr = typeStr.substr(0, pos);
            }
        }
        // Check _ID suffix (used in some variants)
        bool hasId = false;
        {
            size_t pos = typeStr.rfind("_ID");
            if (pos != std::string::npos && pos == typeStr.size() - 3) {
                hasId = true;
                typeStr = typeStr.substr(0, pos);
            }
        }
        c.type = typeStr;

        // Collect data lines until next keyword
        int j = i + 1;
        std::vector<std::string> dataLines;
        while (j < (int)lines.size()) {
            std::string jt = kw_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*' && jt[0] != '$') {
                // Check it's really a keyword, not $*comment
                if (jt.size() >= 2 && jt[1] != '$') break;
            }
            dataLines.push_back(lines[j]);
            ++j;
        }
        c.endLine = j;

        // Parse data lines (skip comments/empty)
        int cardNum = 0;
        // If _TITLE or _ID: first non-comment is title/CID line
        bool needTitle = c.hasTitle || hasId;

        for (const auto& dl : dataLines) {
            std::string dtr = kw_trim(dl);
            if (dtr.empty() || dtr[0] == '$') continue;

            if (needTitle) {
                if (hasId) {
                    // CID + title on same line
                    auto toks = kw_tok10(dl);
                    if (!toks.empty()) c.title = dtr;  // store full line as title
                } else {
                    c.title = dtr;
                }
                needTitle = false;
                continue;
            }

            auto toks = kw_tok10(dl);
            if (cardNum == 0) {
                // Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
                if (toks.size() >= 1) try { c.ssid   = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.msid   = std::stoi(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.sstyp  = std::stoi(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.mstyp  = std::stoi(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.sboxid = std::stoi(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.mboxid = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.spr    = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.mpr    = std::stoi(toks[7]); } catch(...){}
            } else if (cardNum == 1) {
                // Card 2: FS FD DC VC VDC PENCHK BT DT
                if (toks.size() >= 1) try { c.fs     = std::stod(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.fd     = std::stod(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.dc     = std::stod(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.vc     = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.vdc    = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.penchk = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.bt     = std::stod(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.dt     = std::stod(toks[7]); } catch(...){}
            } else if (cardNum == 2) {
                // Card 3: SFSA SFSB SAST SBST SFSAT SFSBT FSF VSF
                if (toks.size() >= 1) try { c.sfsa   = std::stod(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.sfsb   = std::stod(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.sast   = std::stod(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.sbst   = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.sfsat  = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.sfsbt  = std::stod(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.fsf    = std::stod(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.vsf    = std::stod(toks[7]); } catch(...){}
            } else if (cardNum == 3) {
                // Card A: SOFT SOFSCL LCIDAB MAXPAR SBOPT DEPTH BSORT FRCFRQ
                c.hasCardA = true;
                if (toks.size() >= 1) try { c.soft    = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.sofscl  = std::stod(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.lcidab  = std::stoi(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.maxpar  = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.sbopt   = std::stoi(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.depth   = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.bsort   = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.frcfrq  = std::stoi(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 4) {
                // Card B: PENMAX THKOPT SHLTHK SNLOG ISYM I2D3D SLDTHK SLDSTF
                c.hasCardB = true;
                if (toks.size() >= 1) try { c.penmax  = std::stod(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.thkopt  = std::stoi(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.shlthk  = std::stoi(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.snlog   = std::stoi(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.isym    = std::stoi(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.i2d3d   = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.sldthk  = std::stod(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.sldstf  = std::stod(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 5) {
                // Card C: IGAP IGNORE DPRFAC DTSTIF EDGEK FLANGL CID_RCF
                c.hasCardC = true;
                if (toks.size() >= 1) try { c.igap    = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.ignore_ = std::stoi(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.dprfac  = std::stod(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.dtstif  = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.edgek   = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.flangl  = std::stod(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.cid_rcf = std::stoi(toks[6]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 6) {
                // Card D: Q2TRI DTPCHK SFNBR FNLSCL DNLSCL TCSO TIEDID SHLEDG
                c.hasCardD = true;
                if (toks.size() >= 1) try { c.q2tri   = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.dtpchk  = std::stod(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.sfnbr   = std::stod(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.fnlscl  = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.dnlscl  = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.tcso    = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.tiedid  = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.shledg  = std::stoi(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 7) {
                // Card E: SHAREC CPARM8 IPBACK SRNDE FRICSF ICOR FTORQ REGION
                c.hasCardE = true;
                if (toks.size() >= 1) try { c.sharec  = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.cparm8  = std::stoi(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.ipback  = std::stoi(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.srnde   = std::stoi(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.fricsf  = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.icor    = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.ftorq   = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.region  = std::stoi(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 8) {
                // Card F: PSTIFF IGNROFF (blank) FSTOL 2DBINR SSFTYP SWTPR TETFAC
                c.hasCardF = true;
                if (toks.size() >= 1) try { c.pstiff  = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.ignroff = std::stoi(toks[1]); } catch(...){}
                // field 3 is blank
                if (toks.size() >= 4) try { c.fstol   = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.d2binr  = std::stoi(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.ssftyp  = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.swtpr   = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.tetfac  = std::stod(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 9) {
                // Card G: (blank) SHLOFF (rest blank)
                c.hasCardG = true;
                // field 1 is blank
                if (toks.size() >= 2) try { c.shloff  = std::stod(toks[1]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else {
                // Beyond Card G — store raw
                c.optionalCards.push_back(dl);
            }
            cardNum++;
        }
        result.push_back(c);
        i = j - 1;  // advance outer loop
    }
    return result;
}

// Parse all *SET_* blocks from rawLines
std::vector<SetDef> ct_parseSets(const std::vector<std::string>& lines) {
    std::vector<SetDef> result;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = kw_upper(tr);
        if (up.rfind("*SET_", 0) != 0) continue;

        SetDef s;
        s.startLine = i;

        // Determine set type and title
        std::string rest = up.substr(5);  // after "*SET_"
        s.hasTitle = (rest.find("_TITLE") != std::string::npos);
        if (s.hasTitle) {
            size_t pos = rest.find("_TITLE");
            rest = rest.substr(0, pos);
        }
        // Also strip _LIST suffix (e.g., *SET_NODE_LIST)
        {
            size_t pos = rest.find("_LIST");
            if (pos != std::string::npos) rest = rest.substr(0, pos);
        }
        s.type = rest;  // "SEGMENT", "NODE", "PART", "SHELL", "SOLID"

        // Collect data lines
        int j = i + 1;
        while (j < (int)lines.size()) {
            std::string jt = kw_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*' && !(jt.size() >= 2 && jt[1] == '$')) break;
            ++j;
        }
        s.endLine = j;

        // Parse data
        bool titleRead = !s.hasTitle;
        bool headerRead = false;

        for (int k = i + 1; k < j; ++k) {
            std::string dtr = kw_trim(lines[k]);
            if (dtr.empty() || dtr[0] == '$') continue;

            if (!titleRead) {
                s.title = dtr;
                titleRead = true;
                continue;
            }

            auto toks = kw_tok10(lines[k]);

            if (!headerRead) {
                // Header line: SID [DA1 DA2 DA3 DA4] [SOLVER]
                if (!toks.empty()) try { s.id = std::stoi(toks[0]); } catch(...){}
                if (s.type == "SEGMENT") {
                    if (toks.size() >= 2) try { s.da1 = std::stod(toks[1]); } catch(...){}
                    if (toks.size() >= 3) try { s.da2 = std::stod(toks[2]); } catch(...){}
                    if (toks.size() >= 4) try { s.da3 = std::stod(toks[3]); } catch(...){}
                    if (toks.size() >= 5) try { s.da4 = std::stod(toks[4]); } catch(...){}
                }
                headerRead = true;
                continue;
            }

            // Data lines
            if (s.type == "SEGMENT") {
                // N1 N2 N3 N4 [A1 A2 A3 A4]
                std::array<int,4> seg = {0,0,0,0};
                for (int f = 0; f < 4 && f < (int)toks.size(); ++f) {
                    try { seg[f] = std::stoi(toks[f]); } catch(...){}
                }
                if (seg[0] != 0) s.segments.push_back(seg);
            } else {
                // Up to 8 IDs per line
                for (const auto& t : toks) {
                    if (t.empty()) continue;
                    try {
                        int v = std::stoi(t);
                        if (v != 0) s.ids.push_back(v);
                    } catch(...){}
                }
            }
        }
        result.push_back(s);
        i = j - 1;
    }
    return result;
}

// Find max Set ID across all SET_* keywords
int ct_findMaxSetId(const std::vector<SetDef>& sets) {
    int maxId = 0;
    for (const auto& s : sets) if (s.id > maxId) maxId = s.id;
    return maxId;
}

// Extract outer surface from solid/shell elements of given PID
// Reuses extractSourceSurface() algorithm
std::vector<std::array<int,4>> ct_extractSurface(
        const KooRemapper::Mesh& mesh, int pid) {
    using namespace KooRemapper;

    // Check for shell elements first
    // (KFileReader stores shells differently — check element types)
    std::vector<std::array<int,4>> faces;

    // Build face count map: sorted key → (count, original winding)
    std::map<std::array<int,4>, std::pair<int, std::array<int,4>>> faceMap;

    bool foundSolid = false;
    for (const auto& [eid, elem] : mesh.getElements()) {
        if (elem.partId != pid) continue;
        foundSolid = true;

        // TET4 detection
        bool isTet = (elem.nodeIds[4] == elem.nodeIds[7] &&
                      elem.nodeIds[4] == elem.nodeIds[6] &&
                      elem.nodeIds[4] == elem.nodeIds[5]);
        int numFaces = isTet ? 4 : 6;

        for (int fi = 0; fi < numFaces; ++fi) {
            auto fn = elem.getFaceNodeIds(fi);
            std::array<int,4> winding = {fn[0], fn[1], fn[2], fn[3]};

            std::array<int,4> key = winding;
            std::sort(key.begin(), key.end());

            auto it = faceMap.find(key);
            if (it == faceMap.end()) {
                faceMap[key] = {1, winding};
            } else {
                it->second.first++;
            }
        }
    }

    if (!foundSolid) {
        // Try shell elements (QUAD4) — TODO: if shells are parsed into elements map
        // For now just return empty; shell handling can be added later
        return faces;
    }

    for (const auto& [key, val] : faceMap) {
        if (val.first == 1) {
            faces.push_back(val.second);
        }
    }
    return faces;
}

// ============================================================
// Module B: Core Detection — Spatial Hash Grid Algorithm
// ============================================================

// ---- B-1. Data structures ----

struct ct_FaceInfo {
    std::array<int, 4> nodeIds;
    Vector3D verts[4];       // cached vertex positions
    Vector3D centroid;
    Vector3D normal;         // unit normal (direction NOT guaranteed outward)
    double area;
    double radius;           // max distance from centroid to any vertex
    int nVerts;              // 3 (tri) or 4 (quad)
    int pid;                 // owning part ID
    int sourceIndex;         // index in original faces vector
};

struct ct_CellKey {
    int ix, iy, iz;
    bool operator==(const ct_CellKey& o) const {
        return ix == o.ix && iy == o.iy && iz == o.iz;
    }
};

struct ct_CellKeyHash {
    size_t operator()(const ct_CellKey& k) const {
        size_t h = size_t(k.ix) * 73856093ULL;
        h ^= size_t(k.iy) * 19349663ULL;
        h ^= size_t(k.iz) * 83492791ULL;
        return h;
    }
};


static ct_CellKey ct_cellKey(const Vector3D& pos, double cellSize) {
    return { (int)std::floor(pos.x / cellSize),
             (int)std::floor(pos.y / cellSize),
             (int)std::floor(pos.z / cellSize) };
}

static std::vector<ct_FaceInfo> ct_buildFaceInfo(
        const std::vector<std::array<int,4>>& faces,
        const KooRemapper::Mesh& mesh,
        int pid) {
    using namespace KooRemapper;
    std::vector<ct_FaceInfo> info;
    info.reserve(faces.size());
    for (int idx = 0; idx < (int)faces.size(); ++idx) {
        ct_FaceInfo fi;
        fi.nodeIds = faces[idx];
        fi.pid = pid;
        fi.sourceIndex = idx;

        // Detect triangle (TET4 degenerate quad)
        bool isTri = (faces[idx][3] == faces[idx][2] ||
                      faces[idx][3] == 0);
        fi.nVerts = isTri ? 3 : 4;

        // Cache vertex positions
        bool valid = true;
        for (int k = 0; k < fi.nVerts; ++k) {
            const auto* nd = mesh.getNode(faces[idx][k]);
            if (!nd) { valid = false; break; }
            fi.verts[k] = nd->position;
        }
        if (!valid) continue;
        if (isTri) fi.verts[3] = fi.verts[2]; // fill 4th slot

        // Centroid
        fi.centroid = Vector3D(0, 0, 0);
        for (int k = 0; k < fi.nVerts; ++k) fi.centroid = fi.centroid + fi.verts[k];
        fi.centroid = fi.centroid * (1.0 / fi.nVerts);

        // Normal
        Vector3D n;
        if (isTri) {
            Vector3D v1 = fi.verts[1] - fi.verts[0];
            Vector3D v2 = fi.verts[2] - fi.verts[0];
            n = v1.cross(v2);
        } else {
            Vector3D d1 = fi.verts[2] - fi.verts[0];
            Vector3D d2 = fi.verts[3] - fi.verts[1];
            n = d1.cross(d2);
        }
        fi.area = n.magnitude() * 0.5;
        if (fi.area < 1e-20) continue; // skip degenerate face
        fi.normal = n.normalized();

        // Radius: max distance from centroid to any vertex
        fi.radius = 0;
        for (int k = 0; k < fi.nVerts; ++k) {
            double r = fi.verts[k].distanceTo(fi.centroid);
            if (r > fi.radius) fi.radius = r;
        }

        info.push_back(fi);
    }
    return info;
}

static double ct_averageFaceSize(const std::vector<ct_FaceInfo>& faces) {
    if (faces.empty()) return 1.0;
    double sum = 0;
    for (const auto& f : faces) sum += std::sqrt(f.area);
    return sum / faces.size();
}

// Insert face into all grid cells its AABB overlaps
static void ct_insertFaceToGrid(
        std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash>& grid,
        const ct_FaceInfo& fi, int idx, double cellSize) {
    // Compute AABB of face vertices
    double minX = fi.verts[0].x, maxX = fi.verts[0].x;
    double minY = fi.verts[0].y, maxY = fi.verts[0].y;
    double minZ = fi.verts[0].z, maxZ = fi.verts[0].z;
    for (int k = 1; k < fi.nVerts; ++k) {
        if (fi.verts[k].x < minX) minX = fi.verts[k].x;
        if (fi.verts[k].x > maxX) maxX = fi.verts[k].x;
        if (fi.verts[k].y < minY) minY = fi.verts[k].y;
        if (fi.verts[k].y > maxY) maxY = fi.verts[k].y;
        if (fi.verts[k].z < minZ) minZ = fi.verts[k].z;
        if (fi.verts[k].z > maxZ) maxZ = fi.verts[k].z;
    }
    int ixMin = (int)std::floor(minX / cellSize);
    int ixMax = (int)std::floor(maxX / cellSize);
    int iyMin = (int)std::floor(minY / cellSize);
    int iyMax = (int)std::floor(maxY / cellSize);
    int izMin = (int)std::floor(minZ / cellSize);
    int izMax = (int)std::floor(maxZ / cellSize);
    for (int ix = ixMin; ix <= ixMax; ++ix)
        for (int iy = iyMin; iy <= iyMax; ++iy)
            for (int iz = izMin; iz <= izMax; ++iz)
                grid[{ix, iy, iz}].push_back(idx);
}

// ---- B-4. Narrow phase check (4-stage) ----

static bool ct_narrowPhaseCheck(
        const ct_FaceInfo& fA, const ct_FaceInfo& fB,
        double gapTol, double cosThresh, double& gapOut) {

    // Stage 1: centroid distance pre-filter
    double centDist = fA.centroid.distanceTo(fB.centroid);
    if (centDist > fA.radius + fB.radius + gapTol) return false;

    // Stage 2: normal parallelism (direction-agnostic via |dot|)
    double absDot = std::abs(fA.normal.dot(fB.normal));
    if (absDot < cosThresh) return false;

    // Stage 3: vertex-to-plane projection (bilateral)
    // Check A's vertices against B's plane, and vice versa
    double minGap = std::numeric_limits<double>::max();

    // A → B plane
    for (int k = 0; k < fA.nVerts; ++k) {
        Vector3D diff = fA.verts[k] - fB.centroid;
        double gap_k = std::abs(diff.dot(fB.normal));
        // Check projected point is within face B's extent
        Vector3D projPt = fA.verts[k] - fB.normal * diff.dot(fB.normal);
        double projDist = projPt.distanceTo(fB.centroid);
        if (projDist < fB.radius + gapTol) {
            if (gap_k < minGap) minGap = gap_k;
        }
    }
    // B → A plane
    for (int k = 0; k < fB.nVerts; ++k) {
        Vector3D diff = fB.verts[k] - fA.centroid;
        double gap_k = std::abs(diff.dot(fA.normal));
        Vector3D projPt = fB.verts[k] - fA.normal * diff.dot(fA.normal);
        double projDist = projPt.distanceTo(fA.centroid);
        if (projDist < fA.radius + gapTol) {
            if (gap_k < minGap) minGap = gap_k;
        }
    }

    if (minGap > gapTol) return false;
    gapOut = minGap;
    return true;
}

// ---- B-5. Single pair detection ----

std::vector<ct_ContactPair> ct_detectContacting(
        const std::vector<std::array<int,4>>& facesA,
        const std::vector<std::array<int,4>>& facesB,
        const KooRemapper::Mesh& mesh,
        int pidA, int pidB,
        double gapTolerance,
        double normalAngleDeg) {

    auto infoA = ct_buildFaceInfo(facesA, mesh, pidA);
    auto infoB = ct_buildFaceInfo(facesB, mesh, pidB);
    if (infoA.empty() || infoB.empty()) return {};

    double avgSize = (ct_averageFaceSize(infoA) + ct_averageFaceSize(infoB)) * 0.5;
    double cellSize = std::max(avgSize, gapTolerance * 2.0);
    cellSize = std::max(cellSize, 1e-10);
    double cosThresh = std::cos(normalAngleDeg * 3.14159265358979323846 / 180.0);

    // Build grid from B (master)
    std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash> grid;
    for (int j = 0; j < (int)infoB.size(); ++j)
        ct_insertFaceToGrid(grid, infoB[j], j, cellSize);

    // Query with A (slave) — collect candidates with dedup
    std::set<std::pair<int,int>> candidates;
    for (int i = 0; i < (int)infoA.size(); ++i) {
        // AABB cell range for slave face
        double minX = infoA[i].verts[0].x, maxX = minX;
        double minY = infoA[i].verts[0].y, maxY = minY;
        double minZ = infoA[i].verts[0].z, maxZ = minZ;
        for (int k = 1; k < infoA[i].nVerts; ++k) {
            if (infoA[i].verts[k].x < minX) minX = infoA[i].verts[k].x;
            if (infoA[i].verts[k].x > maxX) maxX = infoA[i].verts[k].x;
            if (infoA[i].verts[k].y < minY) minY = infoA[i].verts[k].y;
            if (infoA[i].verts[k].y > maxY) maxY = infoA[i].verts[k].y;
            if (infoA[i].verts[k].z < minZ) minZ = infoA[i].verts[k].z;
            if (infoA[i].verts[k].z > maxZ) maxZ = infoA[i].verts[k].z;
        }
        // Expand by 1 cell margin for tolerance
        int ixMin = (int)std::floor(minX / cellSize) - 1;
        int ixMax = (int)std::floor(maxX / cellSize) + 1;
        int iyMin = (int)std::floor(minY / cellSize) - 1;
        int iyMax = (int)std::floor(maxY / cellSize) + 1;
        int izMin = (int)std::floor(minZ / cellSize) - 1;
        int izMax = (int)std::floor(maxZ / cellSize) + 1;
        for (int ix = ixMin; ix <= ixMax; ++ix)
            for (int iy = iyMin; iy <= iyMax; ++iy)
                for (int iz = izMin; iz <= izMax; ++iz) {
                    auto it = grid.find({ix, iy, iz});
                    if (it == grid.end()) continue;
                    for (int j : it->second)
                        candidates.insert({i, j});
                }
    }

    // Narrow phase
    // faceA/faceB stored as sourceIndex (original index in facesA/facesB),
    // NOT the infoA/infoB index — callers use these to index back into facesA/facesB.
    std::vector<ct_ContactPair> results;
    for (const auto& [i, j] : candidates) {
        double gap;
        if (ct_narrowPhaseCheck(infoA[i], infoB[j], gapTolerance, cosThresh, gap)) {
            results.push_back({pidA, pidB, infoA[i].sourceIndex, infoB[j].sourceIndex, gap});
        }
    }
    return results;
}

// ---- B-6. All-pairs detection (Global Grid) ----

std::vector<ct_PairResult> ct_detectAllPairs(
        const std::map<int, std::vector<std::array<int,4>>>& surfacesByPid,
        const std::vector<int>& targetPids,
        const std::vector<int>& counterPids,
        const KooRemapper::Mesh& mesh,
        double gapTolerance,
        double normalAngleDeg) {

    // Build face info for all PIDs, tagged with PID
    std::vector<ct_FaceInfo> allFaces;
    // Track per-PID ranges: pid → (startIdx, count)
    std::map<int, std::pair<int,int>> pidRange;

    std::set<int> counterSet(counterPids.begin(), counterPids.end());
    std::set<int> targetSet(targetPids.begin(), targetPids.end());
    // Collect all unique PIDs needed
    std::set<int> allPids;
    allPids.insert(targetPids.begin(), targetPids.end());
    allPids.insert(counterPids.begin(), counterPids.end());

    for (int pid : allPids) {
        auto it = surfacesByPid.find(pid);
        if (it == surfacesByPid.end()) continue;
        int startIdx = (int)allFaces.size();
        auto fi = ct_buildFaceInfo(it->second, mesh, pid);
        allFaces.insert(allFaces.end(), fi.begin(), fi.end());
        pidRange[pid] = {startIdx, (int)fi.size()};
    }
    if (allFaces.empty()) return {};

    double avgSize = ct_averageFaceSize(allFaces);
    double cellSize = std::max(avgSize, gapTolerance * 2.0);
    cellSize = std::max(cellSize, 1e-10);
    double cosThresh = std::cos(normalAngleDeg * 3.14159265358979323846 / 180.0);

    // Insert counter faces into grid
    std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash> grid;
    for (int pid : counterPids) {
        auto it = pidRange.find(pid);
        if (it == pidRange.end()) continue;
        int start = it->second.first;
        int count = it->second.second;
        for (int i = start; i < start + count; ++i)
            ct_insertFaceToGrid(grid, allFaces[i], i, cellSize);
    }

    // Query with target faces — collect candidates with dedup
    std::set<std::pair<int,int>> candidates;
    for (int pid : targetPids) {
        auto it = pidRange.find(pid);
        if (it == pidRange.end()) continue;
        int start = it->second.first;
        int count = it->second.second;
        for (int i = start; i < start + count; ++i) {
            const auto& fi = allFaces[i];
            double minX = fi.verts[0].x, maxX = minX;
            double minY = fi.verts[0].y, maxY = minY;
            double minZ = fi.verts[0].z, maxZ = minZ;
            for (int k = 1; k < fi.nVerts; ++k) {
                if (fi.verts[k].x < minX) minX = fi.verts[k].x;
                if (fi.verts[k].x > maxX) maxX = fi.verts[k].x;
                if (fi.verts[k].y < minY) minY = fi.verts[k].y;
                if (fi.verts[k].y > maxY) maxY = fi.verts[k].y;
                if (fi.verts[k].z < minZ) minZ = fi.verts[k].z;
                if (fi.verts[k].z > maxZ) maxZ = fi.verts[k].z;
            }
            int ixMin = (int)std::floor(minX / cellSize) - 1;
            int ixMax = (int)std::floor(maxX / cellSize) + 1;
            int iyMin = (int)std::floor(minY / cellSize) - 1;
            int iyMax = (int)std::floor(maxY / cellSize) + 1;
            int izMin = (int)std::floor(minZ / cellSize) - 1;
            int izMax = (int)std::floor(maxZ / cellSize) + 1;
            for (int ix = ixMin; ix <= ixMax; ++ix)
                for (int iy = iyMin; iy <= iyMax; ++iy)
                    for (int iz = izMin; iz <= izMax; ++iz) {
                        auto git = grid.find({ix, iy, iz});
                        if (git == grid.end()) continue;
                        for (int j : git->second) {
                            if (allFaces[j].pid == fi.pid) continue; // skip same PID
                            // Canonical ordering: smaller PID first
                            int a = std::min(i, j), b = std::max(i, j);
                            candidates.insert({a, b});
                        }
                    }
        }
    }

    // Narrow phase + group by PID pair
    std::map<std::pair<int,int>, std::vector<ct_ContactPair>> grouped;
    for (const auto& [a, b] : candidates) {
        double gap;
        if (ct_narrowPhaseCheck(allFaces[a], allFaces[b],
                                gapTolerance, cosThresh, gap)) {
            int pA = std::min(allFaces[a].pid, allFaces[b].pid);
            int pB = std::max(allFaces[a].pid, allFaces[b].pid);
            grouped[{pA, pB}].push_back({pA, pB, a, b, gap});
        }
    }

    // Build results
    std::vector<ct_PairResult> results;
    for (auto& [pidPair, pairs] : grouped) {
        ct_PairResult pr;
        pr.pidA = pidPair.first;
        pr.pidB = pidPair.second;
        pr.pairCount = (int)pairs.size();
        pr.gapMin = std::numeric_limits<double>::max();
        pr.gapMax = 0;
        double gapSum = 0;
        std::set<int> usedA, usedB;
        for (const auto& cp : pairs) {
            if (cp.gap < pr.gapMin) pr.gapMin = cp.gap;
            if (cp.gap > pr.gapMax) pr.gapMax = cp.gap;
            gapSum += cp.gap;
            // Determine which face belongs to which PID
            int idxA = (allFaces[cp.faceA].pid == pr.pidA) ? cp.faceA : cp.faceB;
            int idxB = (allFaces[cp.faceB].pid == pr.pidB) ? cp.faceB : cp.faceA;
            usedA.insert(idxA);
            usedB.insert(idxB);
        }
        pr.gapAvg = pairs.empty() ? 0 : gapSum / pairs.size();
        for (int idx : usedA) pr.contactFacesA.push_back(allFaces[idx].nodeIds);
        for (int idx : usedB) pr.contactFacesB.push_back(allFaces[idx].nodeIds);
        results.push_back(pr);
    }
    return results;
}

// ---- B-7. Merge faces from multiple PIDs (remove internal shared faces) ----

std::vector<std::array<int,4>> ct_mergeFaces(
        const std::vector<std::vector<std::array<int,4>>>& perPidFaces) {
    // Dedup: sorted key → (count, original winding)
    std::map<std::array<int,4>, std::pair<int, std::array<int,4>>> faceMap;
    for (const auto& faces : perPidFaces) {
        for (const auto& f : faces) {
            std::array<int,4> key = f;
            std::sort(key.begin(), key.end());
            auto it = faceMap.find(key);
            if (it == faceMap.end()) {
                faceMap[key] = {1, f};
            } else {
                it->second.first++;
            }
        }
    }
    std::vector<std::array<int,4>> result;
    for (const auto& [key, val] : faceMap) {
        if (val.first == 1) result.push_back(val.second);
    }
    return result;
}

// ============================================================
// Module A: Part Selection (include/exclude/all filtering)
// ============================================================

static bool ct_matchPartName(const std::string& partName,
                              const std::vector<std::string>& keywords) {
    if (keywords.empty()) return false;
    std::string upper = partName;
    std::transform(upper.begin(), upper.end(), upper.begin(),
                   [](unsigned char c) { return (char)std::toupper(c); });
    for (const auto& kw : keywords) {
        std::string kwUp = kw;
        std::transform(kwUp.begin(), kwUp.end(), kwUp.begin(),
                       [](unsigned char c) { return (char)std::toupper(c); });
        if (upper.find(kwUp) != std::string::npos) return true;
    }
    return false;
}


ct_PartSelection ct_selectParts(
        const KooRemapper::Mesh& mesh,
        const std::string& scope,
        const std::vector<std::string>& includeKeys,
        const std::vector<std::string>& excludeKeys) {
    using namespace KooRemapper;
    ct_PartSelection sel;

    // Collect all PIDs, filtering by exclude
    std::vector<std::pair<int, std::string>> allParts;
    for (const auto& [pid, part] : mesh.getParts()) {
        if (!excludeKeys.empty() && ct_matchPartName(part.name, excludeKeys))
            continue;
        allParts.push_back({pid, part.name});
    }

    if (scope == "all") {
        // All non-excluded parts are both target and counter
        for (const auto& [pid, name] : allParts) {
            sel.targetPids.push_back(pid);
            sel.counterPids.push_back(pid);
        }
    } else if (!includeKeys.empty()) {
        // Include-matched parts are targets, rest are counters
        for (const auto& [pid, name] : allParts) {
            if (ct_matchPartName(name, includeKeys)) {
                sel.targetPids.push_back(pid);
            }
            // All non-excluded parts are potential counters
            sel.counterPids.push_back(pid);
        }
    }
    // If neither scope nor include → empty (caller uses explicit PID mode)
    return sel;
}

std::map<int, std::vector<std::array<int,4>>> ct_extractAllSurfaces(
        const KooRemapper::Mesh& mesh,
        const std::vector<int>& pids) {
    std::map<int, std::vector<std::array<int,4>>> result;
    for (int pid : pids) {
        auto faces = ct_extractSurface(mesh, pid);
        if (!faces.empty()) result[pid] = std::move(faces);
    }
    return result;
}

// ============================================================
// Module C: Contact Type Presets
// ============================================================


ct_ContactPreset ct_getPreset(const std::string& contactType) {
    std::string t = contactType;
    std::transform(t.begin(), t.end(), t.begin(),
                   [](unsigned char c) { return (char)std::tolower(c); });

    if (t == "auto" || t == "automatic" || t.empty())
        return {"AUTOMATIC_SURFACE_TO_SURFACE", true};
    if (t == "tied")
        return {"TIED_SURFACE_TO_SURFACE", true};
    if (t == "mortar")
        return {"AUTOMATIC_SURFACE_TO_SURFACE_MORTAR", true};
    if (t == "tied_mortar")
        return {"TIED_SURFACE_TO_SURFACE_MORTAR", true};
    if (t == "single")
        return {"AUTOMATIC_SINGLE_SURFACE", false};
    if (t == "eroding")
        return {"ERODING_SURFACE_TO_SURFACE", true};
    if (t == "forming")
        return {"FORMING_SURFACE_TO_SURFACE", true};

    // Custom: use as-is (uppercase)
    std::string upper = contactType;
    std::transform(upper.begin(), upper.end(), upper.begin(),
                   [](unsigned char c) { return (char)std::toupper(c); });
    return {upper, true};
}

// ---- Skip/Subtract helpers ----

// Check if a PID pair has an existing contact
// mode: "tied" → only TIED contacts, "all" → any contact
bool ct_pairHasExisting(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const std::string& mode) {
    for (const auto& ct : contacts) {
        // Check if contact type matches mode
        bool typeMatch = false;
        if (mode == "all") {
            typeMatch = true;
        } else if (mode == "tied") {
            std::string up = ct.type;
            std::transform(up.begin(), up.end(), up.begin(),
                [](unsigned char c) { return (char)std::toupper(c); });
            typeMatch = (up.find("TIED") != std::string::npos);
        } else {
            continue;
        }
        if (!typeMatch) continue;

        // Resolve PIDs from contact sides
        auto resolvePids = [&](int sid, int styp) -> std::vector<int> {
            if (styp == 3) return {sid};
            if (styp == 2) {
                for (const auto& s : sets)
                    if (s.type == "PART" && s.id == sid) return s.ids;
            }
            // SSTYP=0 (segment): can't directly resolve to PID — skip
            return {};
        };

        auto sPids = resolvePids(ct.ssid, ct.sstyp);
        auto mPids = resolvePids(ct.msid, ct.mstyp);
        std::set<int> sSet(sPids.begin(), sPids.end());
        std::set<int> mSet(mPids.begin(), mPids.end());

        // Check both orderings: (A in slave, B in master) or (A in master, B in slave)
        if ((sSet.count(pidA) && mSet.count(pidB)) ||
            (sSet.count(pidB) && mSet.count(pidA))) {
            return true;
        }
    }
    return false;
}

// Get existing tied segments for a PID pair from existing contacts
// Returns {slaveFaces, masterFaces} — empty if not found or not segment-based
std::pair<std::vector<std::array<int,4>>, std::vector<std::array<int,4>>>
ct_getExistingTiedSegments(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const Mesh& mesh, double tol, double nAngle) {
    std::pair<std::vector<std::array<int,4>>, std::vector<std::array<int,4>>> result;

    for (const auto& ct : contacts) {
        // Only TIED contacts
        std::string up = ct.type;
        std::transform(up.begin(), up.end(), up.begin(),
            [](unsigned char c) { return (char)std::toupper(c); });
        if (up.find("TIED") == std::string::npos) continue;

        // Resolve PIDs
        auto resolvePids = [&](int sid, int styp) -> std::vector<int> {
            if (styp == 3) return {sid};
            if (styp == 2) {
                for (const auto& s : sets)
                    if (s.type == "PART" && s.id == sid) return s.ids;
            }
            return {};
        };

        auto sPids = resolvePids(ct.ssid, ct.sstyp);
        auto mPids = resolvePids(ct.msid, ct.mstyp);
        std::set<int> sSet(sPids.begin(), sPids.end());
        std::set<int> mSet(mPids.begin(), mPids.end());

        bool matchForward = (sSet.count(pidA) && mSet.count(pidB));
        bool matchReverse = (sSet.count(pidB) && mSet.count(pidA));
        if (!matchForward && !matchReverse) continue;

        // Found matching tied contact. Get segments.
        if (ct.sstyp == 0 && ct.mstyp == 0) {
            // Already segment-based: read from SetDef
            for (const auto& s : sets) {
                if (s.type == "SEGMENT" && s.id == ct.ssid)
                    result.first = s.segments;
                if (s.type == "SEGMENT" && s.id == ct.msid)
                    result.second = s.segments;
            }
        } else {
            // Part-based: use detect to find tied segments
            auto facesA = ct_extractSurface(mesh, pidA);
            auto facesB = ct_extractSurface(mesh, pidB);
            if (!facesA.empty() && !facesB.empty()) {
                auto pairs = ct_detectContacting(facesA, facesB, mesh, pidA, pidB, tol, nAngle);
                std::set<int> aIdx, bIdx;
                for (const auto& p : pairs) { aIdx.insert(p.faceA); bIdx.insert(p.faceB); }
                for (int i : aIdx) result.first.push_back(facesA[i]);
                for (int i : bIdx) result.second.push_back(facesB[i]);
            }
        }
        if (matchReverse) std::swap(result.first, result.second);
        break;
    }
    return result;
}

// Subtract tiedFaces from allFaces. Returns faces in allFaces that are NOT in tiedFaces.
// Comparison by sorted node IDs.
std::vector<std::array<int,4>> ct_subtractFaces(
        const std::vector<std::array<int,4>>& allFaces,
        const std::vector<std::array<int,4>>& tiedFaces) {
    // Build set of tied face keys (sorted node IDs)
    std::set<std::array<int,4>> tiedSet;
    for (const auto& f : tiedFaces) {
        auto key = f;
        std::sort(key.begin(), key.end());
        tiedSet.insert(key);
    }
    std::vector<std::array<int,4>> result;
    for (const auto& f : allFaces) {
        auto key = f;
        std::sort(key.begin(), key.end());
        if (!tiedSet.count(key)) result.push_back(f);
    }
    return result;
}

// ---- Generation helpers ----

std::string ct_generateSetSegment(int setId,
        const std::vector<std::array<int,4>>& faces,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_SEGMENT\n";
    } else {
        ss << "*SET_SEGMENT_TITLE\n" << title << "\n";
    }
    ss << "$#     sid       da1       da2       da3       da4\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d  0.000000  0.000000  0.000000  0.000000", setId);
    ss << buf << "\n";
    ss << "$#      n1        n2        n3        n4\n";
    for (const auto& f : faces) {
        snprintf(buf, sizeof(buf), "%10d%10d%10d%10d", f[0], f[1], f[2], f[3]);
        ss << buf << "\n";
    }
    return ss.str();
}

std::string ct_generateSetPart(int setId,
        const std::vector<int>& pids,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_PART_LIST\n";
    } else {
        ss << "*SET_PART_LIST_TITLE\n" << title << "\n";
    }
    ss << "$#     sid\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d", setId);
    ss << buf << "\n";
    ss << "$#    pid1      pid2      pid3      pid4      pid5      pid6      pid7      pid8\n";
    for (size_t i = 0; i < pids.size(); ++i) {
        snprintf(buf, sizeof(buf), "%10d", pids[i]);
        ss << buf;
        if ((i + 1) % 8 == 0 || i + 1 == pids.size()) ss << "\n";
    }
    return ss.str();
}

std::string ct_generateSetNode(int setId,
        const std::vector<int>& nids,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_NODE_LIST\n";
    } else {
        ss << "*SET_NODE_LIST_TITLE\n" << title << "\n";
    }
    ss << "$#     sid\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d", setId);
    ss << buf << "\n";
    ss << "$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8\n";
    for (size_t i = 0; i < nids.size(); ++i) {
        snprintf(buf, sizeof(buf), "%10d", nids[i]);
        ss << buf;
        if ((i + 1) % 8 == 0 || i + 1 == nids.size()) ss << "\n";
    }
    return ss.str();
}

// Format helpers for Optional Cards A~G
static std::string ct_formatCardA(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10.2f%10d%10.4f%10d%10d%10d%10d",
             d.soft, d.sofscl, d.lcidab, d.maxpar, d.sbopt, d.depth, d.bsort, d.frcfrq);
    return "$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq\n" + std::string(buf);
}
static std::string ct_formatCardB(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10.4f%10d%10d%10d%10d%10d%10.4f%10.4f",
             d.penmax, d.thkopt, d.shlthk, d.snlog, d.isym, d.i2d3d, d.sldthk, d.sldstf);
    return "$#  penmax    thkopt    shlthk     snlog      isym     i2d3d    sldthk    sldstf\n" + std::string(buf);
}
static std::string ct_formatCardC(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10d%10.4f%10.4f%10.4f%10.4f%10d%10s",
             d.igap, d.ignore_, d.dprfac, d.dtstif, d.edgek, d.flangl, d.cid_rcf, "");
    return "$#    igap    ignore    dprfac    dtstif     edgek    flangl   cid_rcf\n" + std::string(buf);
}
static std::string ct_formatCardD(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10.4f%10.4f%10.4f%10.4f%10d%10d%10d",
             d.q2tri, d.dtpchk, d.sfnbr, d.fnlscl, d.dnlscl, d.tcso, d.tiedid, d.shledg);
    return "$#   q2tri    dtpchk     sfnbr    fnlscl    dnlscl      tcso    tiedid    shledg\n" + std::string(buf);
}
static std::string ct_formatCardE(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10.4f%10d%10d%10d",
             d.sharec, d.cparm8, d.ipback, d.srnde, d.fricsf, d.icor, d.ftorq, d.region);
    return "$#  sharec    cparm8    ipback     srnde    fricsf      icor     ftorq    region\n" + std::string(buf);
}
static std::string ct_formatCardF(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10d%10s%10.4f%10d%10d%10d%10.4f",
             d.pstiff, d.ignroff, "", d.fstol, d.d2binr, d.ssftyp, d.swtpr, d.tetfac);
    return "$#  pstiff   ignroff              fstol    2dbinr    ssftyp     swtpr    tetfac\n" + std::string(buf);
}
static std::string ct_formatCardG(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10s%10.4f%10s%10s%10s%10s%10s%10s",
             "", d.shloff, "", "", "", "", "", "");
    return "$#            shloff\n" + std::string(buf);
}

// Append optional cards A~G to stream (ensures card ordering: A before B, etc.)
static void ct_appendOptionalCards(std::ostringstream& ss, const ContactDef& d) {
    // Determine highest card needed
    int maxCard = 0;
    if (d.hasCardG) maxCard = 7;
    else if (d.hasCardF) maxCard = 6;
    else if (d.hasCardE) maxCard = 5;
    else if (d.hasCardD) maxCard = 4;
    else if (d.hasCardC) maxCard = 3;
    else if (d.hasCardB) maxCard = 2;
    else if (d.hasCardA) maxCard = 1;

    // Emit all cards up to maxCard (LS-DYNA sequential dependency)
    if (maxCard >= 1) ss << ct_formatCardA(d) << "\n";
    if (maxCard >= 2) ss << ct_formatCardB(d) << "\n";
    if (maxCard >= 3) ss << ct_formatCardC(d) << "\n";
    if (maxCard >= 4) ss << ct_formatCardD(d) << "\n";
    if (maxCard >= 5) ss << ct_formatCardE(d) << "\n";
    if (maxCard >= 6) ss << ct_formatCardF(d) << "\n";
    if (maxCard >= 7) ss << ct_formatCardG(d) << "\n";
}

std::string ct_generateContact(const ContactDef& d) {
    std::ostringstream ss;
    std::string kw = "*CONTACT_" + kw_upper(d.type);
    if (!d.title.empty()) kw += "_TITLE";
    ss << kw << "\n";
    if (!d.title.empty()) ss << d.title << "\n";

    char buf[90];
    // Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d",
             d.ssid, d.msid, d.sstyp, d.mstyp, d.sboxid, d.mboxid, d.spr, d.mpr);
    ss << "$#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n";
    ss << buf << "\n";

    // Card 2: FS FD DC VC VDC PENCHK BT DT
    snprintf(buf, sizeof(buf), "%10.2f%10.2f%10.2f%10.2f%10.2f%10d%10.2f%10.3E",
             d.fs, d.fd, d.dc, d.vc, d.vdc, d.penchk, d.bt, d.dt);
    ss << "$#      fs        fd        dc        vc       vdc    penchk        bt        dt\n";
    ss << buf << "\n";

    // Card 3: SFSA SFSB SAST SBST SFSAT SFSBT FSF VSF
    snprintf(buf, sizeof(buf), "%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f",
             d.sfsa, d.sfsb, d.sast, d.sbst, d.sfsat, d.sfsbt, d.fsf, d.vsf);
    ss << "$#    sfsa      sfsb      sast      sbst     sfsat     sfsbt       fsf       vsf\n";
    ss << buf << "\n";

    // Optional Cards A~G
    ct_appendOptionalCards(ss, d);

    return ss.str();
}

// Modify an existing contact's Card 1 fields in-place
void ct_modifyContactCard1(std::vector<std::string>& lines,
        const ContactDef& c,
        int newSsid, int newMsid, int newSstyp, int newMstyp) {
    // Find Card 1 data line in [startLine, endLine)
    bool titleSkipped = !c.hasTitle;
    int cardNum = 0;
    for (int i = c.startLine + 1; i < c.endLine; ++i) {
        std::string dtr = kw_trim(lines[i]);
        if (dtr.empty() || dtr[0] == '$') continue;
        if (!titleSkipped) { titleSkipped = true; continue; }
        if (cardNum == 0) {
            // This is Card 1 — modify in place
            std::string line = lines[i];
            if (newSsid  >= 0) line = kw_setField(line, 0, 10, std::to_string(newSsid));
            if (newMsid  >= 0) line = kw_setField(line, 10, 10, std::to_string(newMsid));
            if (newSstyp >= 0) line = kw_setField(line, 20, 10, std::to_string(newSstyp));
            if (newMstyp >= 0) line = kw_setField(line, 30, 10, std::to_string(newMstyp));
            lines[i] = line;
            return;
        }
        cardNum++;
    }
}

// Modify Card 2 FS field
void ct_modifyContactFs(std::vector<std::string>& lines,
        const ContactDef& c, double newFs) {
    bool titleSkipped = !c.hasTitle;
    int cardNum = 0;
    for (int i = c.startLine + 1; i < c.endLine; ++i) {
        std::string dtr = kw_trim(lines[i]);
        if (dtr.empty() || dtr[0] == '$') continue;
        if (!titleSkipped) { titleSkipped = true; continue; }
        if (cardNum == 1) {
            // Card 2 — modify FS at [0, 10)
            char buf[20]; snprintf(buf, sizeof(buf), "%10.2f", newFs);
            lines[i] = kw_setField(lines[i], 0, 10, std::string(buf));
            return;
        }
        cardNum++;
    }
}

// Replace all optional cards (Card A~G) in existing contact
// Finds Card 3 position, removes everything after it until endLine, inserts new cards
void ct_modifyOptionalCards(std::vector<std::string>& lines,
        ContactDef& ct, const ContactDef& newVals) {
    // Find position after Card 3
    bool titleSkipped = !ct.hasTitle;
    int cardNum = 0;
    int card3Line = -1;
    for (int i = ct.startLine + 1; i < ct.endLine; ++i) {
        std::string dtr = kw_trim(lines[i]);
        if (dtr.empty() || dtr[0] == '$') continue;
        if (!titleSkipped) { titleSkipped = true; continue; }
        if (cardNum == 2) { card3Line = i; break; }
        cardNum++;
    }
    if (card3Line < 0) return;

    // Find range of optional cards: from card3Line+1 to endLine
    // Skip any comment lines that follow Card 3 data line
    int optStart = card3Line + 1;
    int optEnd = ct.endLine;

    // Remove old optional card lines (including their comment lines)
    if (optEnd > optStart) {
        lines.erase(lines.begin() + optStart, lines.begin() + optEnd);
    }

    // Generate new optional cards
    std::ostringstream ss;
    ct_appendOptionalCards(ss, newVals);
    std::string newCards = ss.str();

    // Insert new lines
    std::vector<std::string> newLines;
    if (!newCards.empty()) {
        std::istringstream is(newCards);
        std::string ln;
        while (std::getline(is, ln)) newLines.push_back(ln);
    }

    if (!newLines.empty()) {
        lines.insert(lines.begin() + optStart, newLines.begin(), newLines.end());
    }

    // Update endLine
    int delta = (int)newLines.size() - (optEnd - optStart);
    ct.endLine += delta;

    // Update parsed fields
    ct.hasCardA = newVals.hasCardA; ct.soft = newVals.soft; ct.sofscl = newVals.sofscl;
    ct.lcidab = newVals.lcidab; ct.maxpar = newVals.maxpar; ct.sbopt = newVals.sbopt;
    ct.depth = newVals.depth; ct.bsort = newVals.bsort; ct.frcfrq = newVals.frcfrq;
    ct.hasCardB = newVals.hasCardB; ct.penmax = newVals.penmax; ct.thkopt = newVals.thkopt;
    ct.shlthk = newVals.shlthk; ct.snlog = newVals.snlog; ct.isym = newVals.isym;
    ct.i2d3d = newVals.i2d3d; ct.sldthk = newVals.sldthk; ct.sldstf = newVals.sldstf;
    ct.hasCardC = newVals.hasCardC; ct.igap = newVals.igap; ct.ignore_ = newVals.ignore_;
    ct.dprfac = newVals.dprfac; ct.dtstif = newVals.dtstif; ct.edgek = newVals.edgek;
    ct.flangl = newVals.flangl; ct.cid_rcf = newVals.cid_rcf;
    ct.hasCardD = newVals.hasCardD; ct.hasCardE = newVals.hasCardE;
    ct.hasCardF = newVals.hasCardF; ct.hasCardG = newVals.hasCardG;
}

// Remove a block [startLine, endLine) from lines
void ct_removeBlock(std::vector<std::string>& lines, int startLine, int endLine) {
    if (startLine >= 0 && endLine > startLine && endLine <= (int)lines.size()) {
        lines.erase(lines.begin() + startLine, lines.begin() + endLine);
    }
}

// SSTYP description
std::string ct_stypName(int styp) {
    switch(styp) {
        case 0: return "Segment Set";
        case 1: return "Shell Set";
        case 2: return "Part Set";
        case 3: return "Part ID";
        case 4: return "Node Set";
        case 5: return "All Parts";
        case 6: return "Exempt Parts";
        default: return "Unknown(" + std::to_string(styp) + ")";
    }
}

// Analyze and print contact report
void ct_analyze(const std::vector<ContactDef>& contacts,
                       const std::vector<SetDef>& sets,
                       const KooRemapper::Mesh& mesh,
                       ConsoleOutput& console) {
    // Contacts
    console.println("\n--- Contacts (" + std::to_string(contacts.size()) + ") ---");
    if (contacts.empty()) {
        console.println("  No contacts found.");
    }
    for (const auto& c : contacts) {
        console.println("  [" + std::to_string(c.index) + "] " + c.fullKeyword);
        if (!c.title.empty()) console.println("      Title: " + c.title);

        // Slave info
        std::string slaveInfo = "      Slave:  ";
        if (c.sstyp == 3) slaveInfo += "PID " + std::to_string(c.ssid);
        else if (c.sstyp == 0) slaveInfo += "SET_SEGMENT " + std::to_string(c.ssid);
        else if (c.sstyp == 2) slaveInfo += "SET_PART " + std::to_string(c.ssid);
        else if (c.sstyp == 4) slaveInfo += "SET_NODE " + std::to_string(c.ssid);
        else if (c.sstyp == 5) slaveInfo += "All Parts";
        else slaveInfo += "ID=" + std::to_string(c.ssid);
        slaveInfo += " (SSTYP=" + std::to_string(c.sstyp) + ", " + ct_stypName(c.sstyp) + ")";

        // Resolve set members
        if (c.sstyp == 2 || c.sstyp == 0) {
            for (const auto& s : sets) {
                if (s.id == c.ssid) {
                    if (s.type == "PART" && !s.ids.empty()) {
                        slaveInfo += " -> [";
                        for (size_t k = 0; k < s.ids.size(); ++k) {
                            if (k) slaveInfo += ", ";
                            slaveInfo += std::to_string(s.ids[k]);
                        }
                        slaveInfo += "]";
                    } else if (s.type == "SEGMENT") {
                        slaveInfo += " -> " + std::to_string(s.segments.size()) + " segments";
                    }
                    break;
                }
            }
        }
        console.println(slaveInfo);

        // Master info
        std::string masterInfo = "      Master: ";
        if (c.mstyp == 3) masterInfo += "PID " + std::to_string(c.msid);
        else if (c.mstyp == 0) masterInfo += "SET_SEGMENT " + std::to_string(c.msid);
        else if (c.mstyp == 2) masterInfo += "SET_PART " + std::to_string(c.msid);
        else if (c.mstyp == 4) masterInfo += "SET_NODE " + std::to_string(c.msid);
        else if (c.msid == 0 && c.mstyp == 0) masterInfo += "(none)";
        else masterInfo += "ID=" + std::to_string(c.msid);
        if (c.msid != 0 || c.mstyp != 0)
            masterInfo += " (MSTYP=" + std::to_string(c.mstyp) + ", " + ct_stypName(c.mstyp) + ")";

        if (c.mstyp == 2 || c.mstyp == 0) {
            for (const auto& s : sets) {
                if (s.id == c.msid) {
                    if (s.type == "PART" && !s.ids.empty()) {
                        masterInfo += " -> [";
                        for (size_t k = 0; k < s.ids.size(); ++k) {
                            if (k) masterInfo += ", ";
                            masterInfo += std::to_string(s.ids[k]);
                        }
                        masterInfo += "]";
                    } else if (s.type == "SEGMENT") {
                        masterInfo += " -> " + std::to_string(s.segments.size()) + " segments";
                    }
                    break;
                }
            }
        }
        console.println(masterInfo);

        // Friction & Card 2 options
        char fbuf[120];
        snprintf(fbuf, sizeof(fbuf), "      FS=%.2f  FD=%.2f", c.fs, c.fd);
        std::string optLine(fbuf);
        if (c.dc != 0) { snprintf(fbuf, sizeof(fbuf), "  DC=%.2f", c.dc); optLine += fbuf; }
        if (c.vc != 0) { snprintf(fbuf, sizeof(fbuf), "  VC=%.2f", c.vc); optLine += fbuf; }
        if (c.penchk != 0) optLine += "  PENCHK=" + std::to_string(c.penchk);
        console.println(optLine);

        // Card A
        if (c.hasCardA) {
            std::string ca = "      Card A: SOFT=" + std::to_string(c.soft);
            if (c.sofscl != 0.1) { snprintf(fbuf, sizeof(fbuf), "  SOFSCL=%.2f", c.sofscl); ca += fbuf; }
            if (c.depth != 2) ca += "  DEPTH=" + std::to_string(c.depth);
            if (c.sbopt != 2) ca += "  SBOPT=" + std::to_string(c.sbopt);
            if (c.bsort != 0) ca += "  BSORT=" + std::to_string(c.bsort);
            if (c.frcfrq != 1) ca += "  FRCFRQ=" + std::to_string(c.frcfrq);
            if (c.lcidab != 0) ca += "  LCIDAB=" + std::to_string(c.lcidab);
            if (c.maxpar != 1.025) { snprintf(fbuf, sizeof(fbuf), "  MAXPAR=%.4f", c.maxpar); ca += fbuf; }
            console.println(ca);
        }
        // Card B
        if (c.hasCardB) {
            std::string cb = "      Card B:";
            if (c.penmax != 0) { snprintf(fbuf, sizeof(fbuf), " PENMAX=%.4f", c.penmax); cb += fbuf; }
            if (c.thkopt != 0) cb += " THKOPT=" + std::to_string(c.thkopt);
            if (c.shlthk != 0) cb += " SHLTHK=" + std::to_string(c.shlthk);
            if (c.snlog != 0) cb += " SNLOG=" + std::to_string(c.snlog);
            if (c.isym != 0) cb += " ISYM=" + std::to_string(c.isym);
            if (c.i2d3d != 0) cb += " I2D3D=" + std::to_string(c.i2d3d);
            if (c.sldthk != 0) { snprintf(fbuf, sizeof(fbuf), " SLDTHK=%.4f", c.sldthk); cb += fbuf; }
            if (c.sldstf != 0) { snprintf(fbuf, sizeof(fbuf), " SLDSTF=%.4f", c.sldstf); cb += fbuf; }
            console.println(cb);
        }
        // Card C
        if (c.hasCardC) {
            std::string cc = "      Card C:";
            if (c.igap != 1) cc += " IGAP=" + std::to_string(c.igap);
            if (c.ignore_ != 0) cc += " IGNORE=" + std::to_string(c.ignore_);
            if (c.dprfac != 0) { snprintf(fbuf, sizeof(fbuf), " DPRFAC=%.4f", c.dprfac); cc += fbuf; }
            if (c.dtstif != 0) { snprintf(fbuf, sizeof(fbuf), " DTSTIF=%.4f", c.dtstif); cc += fbuf; }
            if (c.edgek != 0) { snprintf(fbuf, sizeof(fbuf), " EDGEK=%.4f", c.edgek); cc += fbuf; }
            if (c.flangl != 0) { snprintf(fbuf, sizeof(fbuf), " FLANGL=%.4f", c.flangl); cc += fbuf; }
            if (c.cid_rcf != 0) cc += " CID_RCF=" + std::to_string(c.cid_rcf);
            console.println(cc);
        }
        // Card D
        if (c.hasCardD) {
            std::string cd = "      Card D:";
            if (c.q2tri != 0) cd += " Q2TRI=" + std::to_string(c.q2tri);
            if (c.shledg != 0) cd += " SHLEDG=" + std::to_string(c.shledg);
            if (c.tcso != 0) cd += " TCSO=" + std::to_string(c.tcso);
            if (c.tiedid != 0) cd += " TIEDID=" + std::to_string(c.tiedid);
            console.println(cd);
        }
        // Card E
        if (c.hasCardE) {
            std::string ce = "      Card E:";
            if (c.sharec != 0) ce += " SHAREC=" + std::to_string(c.sharec);
            if (c.cparm8 != 0) ce += " CPARM8=" + std::to_string(c.cparm8);
            if (c.ipback != 0) ce += " IPBACK=" + std::to_string(c.ipback);
            if (c.fricsf != 1.0) { snprintf(fbuf, sizeof(fbuf), " FRICSF=%.4f", c.fricsf); ce += fbuf; }
            if (c.icor != 0) ce += " ICOR=" + std::to_string(c.icor);
            if (c.region != 0) ce += " REGION=" + std::to_string(c.region);
            console.println(ce);
        }
        // Card F
        if (c.hasCardF) {
            std::string cf = "      Card F:";
            if (c.pstiff != 0) cf += " PSTIFF=" + std::to_string(c.pstiff);
            if (c.ignroff != 0) cf += " IGNROFF=" + std::to_string(c.ignroff);
            if (c.fstol != 2.0) { snprintf(fbuf, sizeof(fbuf), " FSTOL=%.4f", c.fstol); cf += fbuf; }
            console.println(cf);
        }
        // Card G
        if (c.hasCardG) {
            snprintf(fbuf, sizeof(fbuf), "      Card G: SHLOFF=%.4f", c.shloff);
            console.println(std::string(fbuf));
        }
        console.println("");
    }

    // Sets
    console.println("--- Sets (" + std::to_string(sets.size()) + ") ---");
    if (sets.empty()) {
        console.println("  No sets found.");
    }
    for (const auto& s : sets) {
        std::string info = "  SET_" + s.type + " " + std::to_string(s.id) + ": ";
        if (s.type == "SEGMENT") {
            info += std::to_string(s.segments.size()) + " segments";
        } else {
            info += std::to_string(s.ids.size()) + " entries";
            if (s.ids.size() <= 10) {
                info += " [";
                for (size_t k = 0; k < s.ids.size(); ++k) {
                    if (k) info += ", ";
                    info += std::to_string(s.ids[k]);
                }
                info += "]";
            }
        }
        if (!s.title.empty()) info += " \"" + s.title + "\"";
        console.println(info);
    }

    // Coverage analysis
    console.println("\n--- Coverage ---");
    std::map<int, std::vector<std::string>> pidContacts;
    for (const auto& [pid, part] : mesh.getParts()) {
        pidContacts[pid];  // ensure entry exists
    }
    for (const auto& c : contacts) {
        auto addCoverage = [&](int id, int styp, const std::string& role) {
            if (styp == 3) {
                // Direct PID
                pidContacts[id].push_back(role + "[" + std::to_string(c.index) + "]");
            } else if (styp == 2) {
                // Part set — resolve
                for (const auto& s : sets) {
                    if (s.id == id && (s.type == "PART")) {
                        for (int pid : s.ids) {
                            pidContacts[pid].push_back(role + "[" + std::to_string(c.index) + "]");
                        }
                    }
                }
            } else if (styp == 5) {
                // All parts
                for (auto& [pid, v] : pidContacts) {
                    v.push_back(role + "[" + std::to_string(c.index) + "]");
                }
            }
        };
        addCoverage(c.ssid, c.sstyp, "slave");
        addCoverage(c.msid, c.mstyp, "master");
    };

    for (const auto& [pid, roles] : pidContacts) {
        std::string line = "  PID " + std::to_string(pid) + ": ";
        if (roles.empty()) {
            line += "no contact (!)";
        } else {
            for (size_t k = 0; k < roles.size(); ++k) {
                if (k) line += ", ";
                line += roles[k];
            }
        }
        console.println(line);
    }
    console.println("");
}
