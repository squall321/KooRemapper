#include "surface_extract.h"
#include "parser/KFileReader.h"
#include "core/Mesh.h"
#include "core/Element.h"
#include "core/Vector3D.h"
#include "cli/ConsoleOutput.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <unordered_map>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/extract-surface]]

namespace {

using namespace KooRemapper;

using FaceKey = std::array<int,4>;

// Detect degenerate quad → triangle (4th node duplicates 3rd, or is 0).
// LS-DYNA convention: write TRIA3 as QUAD4 with N4 = N3.
bool isTriangle(const FaceKey& n) {
    return n[3] == n[2] || n[3] == 0 || n[3] == n[0];
}

// Mean Z of an element's nodes (unweighted centroid Z is enough for top/bottom
// discrimination — we only need a reference point inside the element).
double elementCentroidZ(const Element& elem, const Mesh& mesh) {
    double sum = 0.0;
    int count = 0;
    for (int nid : elem.nodeIds) {
        if (nid <= 0) continue;
        auto it = mesh.nodes.find(nid);
        if (it == mesh.nodes.end()) continue;
        sum += it->second.position.z;
        ++count;
    }
    return count > 0 ? sum / count : 0.0;
}

double faceCentroidZ(const FaceKey& nodes, const Mesh& mesh) {
    double sum = 0.0;
    int count = 0;
    int seen[4] = {0, 0, 0, 0};
    for (int i = 0; i < 4; ++i) {
        int nid = nodes[i];
        if (nid <= 0) continue;
        bool dup = false;
        for (int j = 0; j < i; ++j) if (seen[j] == nid) { dup = true; break; }
        if (dup) continue;
        seen[i] = nid;
        auto it = mesh.nodes.find(nid);
        if (it == mesh.nodes.end()) continue;
        sum += it->second.position.z;
        ++count;
    }
    return count > 0 ? sum / count : 0.0;
}

// 2D grid-based spatial hash for top↔bottom node pairing.
// Cell size is chosen so that ~3-9 nodes land in the search neighborhood;
// queryNeighbors scans the 3×3 cell window around the query point.
struct NodeHash2D {
    double cellSize = 1.0;
    std::unordered_map<long long, std::vector<int>> buckets;

    long long key(int cx, int cy) const {
        return static_cast<long long>(cx) * 1000003LL
             + static_cast<long long>(cy);
    }
    std::pair<int,int> cell(double x, double y) const {
        return {static_cast<int>(std::floor(x / cellSize)),
                static_cast<int>(std::floor(y / cellSize))};
    }
    void insert(int nid, double x, double y) {
        auto [cx, cy] = cell(x, y);
        buckets[key(cx, cy)].push_back(nid);
    }
    std::vector<int> queryNeighbors(double x, double y) const {
        std::vector<int> out;
        auto [cx, cy] = cell(x, y);
        for (int dx = -1; dx <= 1; ++dx)
        for (int dy = -1; dy <= 1; ++dy) {
            auto it = buckets.find(key(cx + dx, cy + dy));
            if (it != buckets.end())
                out.insert(out.end(), it->second.begin(), it->second.end());
        }
        return out;
    }
};

// Write a uniform `.k` file (used by both modes).
// `nodes` is iterated in map order; `shells` are emitted as *ELEMENT_SHELL
// with consecutive EIDs starting from 1.
void writeShellKFile(std::ofstream& out,
                     const std::string& sourceTag,
                     const ExtractSurfaceOptions& opts,
                     const std::map<int, Vector3D>& nodes,
                     const std::vector<FaceKey>& shells) {
    out << "$# KooRemapper extract-surface\n";
    out << "$# source: " << sourceTag << "\n";
    out << "$# filter: pid=" << opts.filterPid
        << " face=" << opts.face
        << " output_pid=" << opts.outputPid
        << " mid_surface=" << (opts.midSurface ? "yes" : "no") << "\n";
    out << "*KEYWORD\n";

    out << "*PART\n";
    out << "Extracted surface (PID " << opts.outputPid << ")\n";
    out << "$#     pid     secid       mid     eosid       hgid      grav    adpopt      tmid\n";
    out << std::setw(10) << opts.outputPid
        << std::setw(10) << opts.outputPid
        << std::setw(10) << 1
        << std::setw(10) << 0
        << std::setw(10) << 0
        << std::setw(10) << 0
        << std::setw(10) << 0
        << std::setw(10) << 0 << "\n";

    out << "*NODE\n";
    out << "$#   nid               x               y               z      tc      rc\n";
    out << std::scientific << std::setprecision(7);
    for (const auto& [nid, p] : nodes) {
        out << std::setw(8) << nid
            << std::setw(16) << p.x
            << std::setw(16) << p.y
            << std::setw(16) << p.z
            << std::setw(8) << 0
            << std::setw(8) << 0 << "\n";
    }
    out.unsetf(std::ios_base::floatfield);

    out << "*ELEMENT_SHELL\n";
    out << "$#   eid     pid      n1      n2      n3      n4\n";
    int eid = 1;
    for (const auto& f : shells) {
        int n1 = f[0], n2 = f[1], n3 = f[2], n4 = f[3];
        if (isTriangle(f)) n4 = n3;
        out << std::setw(8) << eid++
            << std::setw(8) << opts.outputPid
            << std::setw(8) << n1
            << std::setw(8) << n2
            << std::setw(8) << n3
            << std::setw(8) << n4 << "\n";
    }
    out << "*END\n";
}

} // anonymous namespace


int runExtractSurface(const std::string& solidFile,
                      const std::string& outputFile,
                      const ExtractSurfaceOptions& opts,
                      KooRemapper::ConsoleOutput& console) {
    using namespace KooRemapper;

    // ---- 1. Read input mesh -----------------------------------------------
    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(solidFile);
    } catch (const std::exception& e) {
        console.error(std::string("Failed to read ") + solidFile + ": " + e.what());
        return 1;
    }
    console.info("Loaded " + std::to_string(mesh.nodes.size()) + " nodes, " +
                 std::to_string(mesh.elements.size()) + " elements, " +
                 std::to_string(mesh.parts.size()) + " parts");

    // ---- 2. Build face-count map ------------------------------------------
    struct FaceVal { int count; FaceKey winding; double elemZ; };
    std::map<FaceKey, FaceVal> faceMap;

    int elemsScanned = 0;
    for (const auto& [eid, elem] : mesh.elements) {
        if (opts.filterPid > 0 && elem.partId != opts.filterPid) continue;
        ++elemsScanned;
        double ezc = elementCentroidZ(elem, mesh);
        for (int fi : elem.getValidFaceIndices()) {
            auto fn = elem.getFaceNodeIds(fi);
            FaceKey orig{fn[0], fn[1], fn[2], fn[3]};
            std::sort(fn.begin(), fn.end());
            FaceKey key{fn[0], fn[1], fn[2], fn[3]};
            auto it = faceMap.find(key);
            if (it == faceMap.end()) faceMap[key] = {1, orig, ezc};
            else ++it->second.count;
        }
    }

    if (elemsScanned == 0) {
        const std::string scope = (opts.filterPid > 0)
            ? "PID " + std::to_string(opts.filterPid)
            : "the input mesh";
        console.error("No solid elements found in " + scope);
        return 1;
    }

    // ---- 3. Always partition free faces into top / bottom ----------------
    std::vector<FaceKey> topFaces, bottomFaces;
    for (const auto& [key, val] : faceMap) {
        if (val.count != 1) continue;
        double dz = faceCentroidZ(val.winding, mesh) - val.elemZ;
        if (dz > 0)      topFaces.push_back(val.winding);
        else if (dz < 0) bottomFaces.push_back(val.winding);
        // dz == 0 (face exactly on element centroid plane) is a degenerate
        // corner case; treat as "side" and drop from top/bottom buckets.
    }

    // ---------------------------------------------------------------------
    // Branch A — mid-surface mode: pair top↔bottom nodes by XY, average to
    //            new mid nodes, emit shells with mid IDs.
    // ---------------------------------------------------------------------
    if (opts.midSurface) {
        if (topFaces.empty() || bottomFaces.empty()) {
            console.error("--mid-surface requires both top and bottom free faces "
                          "(found top=" + std::to_string(topFaces.size()) +
                          ", bottom=" + std::to_string(bottomFaces.size()) +
                          "). Is the part actually a layered solid?");
            return 1;
        }

        // Collect unique node IDs on each side.
        std::set<int> topNodeIds, bottomNodeIds;
        for (const auto& f : topFaces)    for (int n : f) if (n > 0) topNodeIds.insert(n);
        for (const auto& f : bottomFaces) for (int n : f) if (n > 0) bottomNodeIds.insert(n);

        // Bottom-side bbox → spatial hash cell size.
        double xMin = +1e30, xMax = -1e30, yMin = +1e30, yMax = -1e30;
        for (int nid : bottomNodeIds) {
            const auto& p = mesh.nodes.at(nid).position;
            xMin = std::min(xMin, p.x); xMax = std::max(xMax, p.x);
            yMin = std::min(yMin, p.y); yMax = std::max(yMax, p.y);
        }
        double diag = std::sqrt((xMax - xMin) * (xMax - xMin)
                              + (yMax - yMin) * (yMax - yMin));
        double cellSize = diag / std::max(1.0, std::sqrt((double)bottomNodeIds.size()));
        if (!(cellSize > 0.0)) cellSize = 1.0;  // degenerate bbox guard

        NodeHash2D hash;
        hash.cellSize = cellSize;
        for (int nid : bottomNodeIds) {
            const auto& p = mesh.nodes.at(nid).position;
            hash.insert(nid, p.x, p.y);
        }

        // Pair each top node with its closest bottom node (XY only).
        int maxOriginalNodeId = 0;
        for (const auto& [nid, _] : mesh.nodes)
            maxOriginalNodeId = std::max(maxOriginalNodeId, nid);

        std::map<int, int> topToMid;
        std::map<int, Vector3D> midPositions;
        int nextMidId = maxOriginalNodeId + 1;
        int unmatched = 0;
        double maxPairDist = 0.0;

        for (int tNid : topNodeIds) {
            const auto& tp = mesh.nodes.at(tNid).position;
            auto cands = hash.queryNeighbors(tp.x, tp.y);
            int bestB = -1;
            double bestD2 = std::numeric_limits<double>::max();
            for (int bNid : cands) {
                const auto& bp = mesh.nodes.at(bNid).position;
                double dx = tp.x - bp.x, dy = tp.y - bp.y;
                double d2 = dx * dx + dy * dy;
                if (d2 < bestD2) { bestD2 = d2; bestB = bNid; }
            }
            if (bestB < 0) { ++unmatched; continue; }

            const auto& bp = mesh.nodes.at(bestB).position;
            int midId = nextMidId++;
            topToMid[tNid] = midId;
            midPositions[midId] = {
                (tp.x + bp.x) * 0.5,
                (tp.y + bp.y) * 0.5,
                (tp.z + bp.z) * 0.5
            };
            maxPairDist = std::max(maxPairDist, std::sqrt(bestD2));
        }

        if (unmatched > 0) {
            console.warning("--mid-surface: " + std::to_string(unmatched) +
                            " top nodes had no bottom match (skipped). "
                            "Mesh may not be fully layered.");
        }

        // Build mid shells using top face winding, remapped to mid node IDs.
        std::vector<FaceKey> midShells;
        midShells.reserve(topFaces.size());
        int skippedFaces = 0;
        for (const auto& tf : topFaces) {
            FaceKey shell{0, 0, 0, 0};
            bool ok = true;
            for (int i = 0; i < 4; ++i) {
                int srcN = tf[i];
                // Handle degenerate input (TRIA3): replicate previous slot
                if (i == 3 && (srcN == tf[2] || srcN == 0 || srcN == tf[0])) {
                    shell[i] = shell[i-1];
                    continue;
                }
                auto it = topToMid.find(srcN);
                if (it == topToMid.end()) { ok = false; break; }
                shell[i] = it->second;
            }
            if (ok) midShells.push_back(shell);
            else    ++skippedFaces;
        }

        if (midShells.empty()) {
            console.error("--mid-surface: 0 paired shells produced. "
                          "Check that top/bottom node XY positions overlap.");
            return 1;
        }

        std::ofstream out(outputFile);
        if (!out.is_open()) {
            console.error("Cannot open output file: " + outputFile);
            return 1;
        }
        writeShellKFile(out, solidFile, opts, midPositions, midShells);
        out.close();

        console.info("Mid-surface: " + std::to_string(midShells.size()) + " shells, "
                     + std::to_string(midPositions.size()) + " new nodes "
                     + "(starting ID " + std::to_string(maxOriginalNodeId + 1) + "); "
                     + "max top↔bottom XY pair distance = "
                     + std::to_string(maxPairDist)
                     + (skippedFaces > 0 ? "; skipped " + std::to_string(skippedFaces) +
                                            " face(s) with unmatched corners" : ""));
        console.info("Written: " + outputFile);
        return 0;
    }

    // ---------------------------------------------------------------------
    // Branch B — top / bottom / all filter mode (default).
    // ---------------------------------------------------------------------
    std::vector<FaceKey> outFaces;
    if      (opts.face == "top")    outFaces = std::move(topFaces);
    else if (opts.face == "bottom") outFaces = std::move(bottomFaces);
    else { // "all" — also include side faces (dz == 0 case)
        for (const auto& [key, val] : faceMap)
            if (val.count == 1) outFaces.push_back(val.winding);
    }

    if (outFaces.empty()) {
        console.error("No free faces matched filter '" + opts.face +
                      "' (scanned " + std::to_string(elemsScanned) + " elements)");
        return 1;
    }

    // Collect nodes actually used by emitted shells.
    std::map<int, Vector3D> usedNodes;
    for (const auto& f : outFaces) {
        for (int n : f) {
            if (n <= 0 || usedNodes.count(n)) continue;
            usedNodes[n] = mesh.nodes.at(n).position;
        }
    }

    std::ofstream out(outputFile);
    if (!out.is_open()) {
        console.error("Cannot open output file: " + outputFile);
        return 1;
    }
    writeShellKFile(out, solidFile, opts, usedNodes, outFaces);
    out.close();

    // Stats
    int triCount = 0, quadCount = 0;
    for (const auto& f : outFaces) {
        if (isTriangle(f)) ++triCount; else ++quadCount;
    }
    console.info("Extracted " + std::to_string(quadCount + triCount) + " surface faces"
                 + (triCount > 0
                    ? " (" + std::to_string(quadCount) + " QUAD4, "
                      + std::to_string(triCount) + " TRIA3 written as degenerate QUAD4)"
                    : "")
                 + " across " + std::to_string(usedNodes.size()) + " nodes");
    console.info("Written: " + outputFile);
    return 0;
}
