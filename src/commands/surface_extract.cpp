#include "surface_extract.h"
#include "parser/KFileReader.h"
#include "core/Mesh.h"
#include "core/Element.h"
#include "core/Vector3D.h"
#include "cli/ConsoleOutput.h"

#include <algorithm>
#include <array>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/extract-surface]]

namespace {

using namespace KooRemapper;

// Detect degenerate quad → triangle (4th node duplicates 3rd, or is 0).
// LS-DYNA convention: write TRIA3 as QUAD4 with N4 = N3.
bool isTriangle(const std::array<int,4>& n) {
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

double faceCentroidZ(const std::array<int,4>& nodes, const Mesh& mesh) {
    double sum = 0.0;
    int count = 0;
    int seen[4] = {0, 0, 0, 0};
    for (int i = 0; i < 4; ++i) {
        int nid = nodes[i];
        if (nid <= 0) continue;
        // De-duplicate (for TRIA3 written as degenerate QUAD4)
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

} // anonymous namespace


int runExtractSurface(const std::string& solidFile,
                      const std::string& outputFile,
                      const ExtractSurfaceOptions& opts,
                      KooRemapper::ConsoleOutput& console) {
    // ---- 1. Read input mesh -----------------------------------------------
    KooRemapper::KFileReader reader;
    KooRemapper::Mesh mesh;
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
    // Key = sorted 4-node tuple. Value = (occurrence count, original winding,
    // owning element's centroid-Z — used by --face top/bottom filter to detect
    // outward direction robustly, regardless of LS-DYNA face-winding convention).
    using FaceKey = std::array<int,4>;
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

    // ---- 3. Collect free faces (count==1), apply directional filter -------
    std::vector<FaceKey> freeFaces;
    freeFaces.reserve(faceMap.size() / 4);  // rough lower bound
    int rejectedDir = 0;
    for (const auto& [key, val] : faceMap) {
        if (val.count != 1) continue;
        if (opts.face != "all") {
            // Outward direction is (face_centroid - element_centroid).
            // Sign of Z component robustly classifies top vs bottom.
            double dz = faceCentroidZ(val.winding, mesh) - val.elemZ;
            if (opts.face == "top"    && dz <= 0) { ++rejectedDir; continue; }
            if (opts.face == "bottom" && dz >= 0) { ++rejectedDir; continue; }
        }
        freeFaces.push_back(val.winding);
    }

    if (freeFaces.empty()) {
        console.error("No free faces found after filtering "
                      "(scanned " + std::to_string(elemsScanned) + " elements, "
                      "filter '" + opts.face + "' rejected " +
                      std::to_string(rejectedDir) + ")");
        return 1;
    }

    // ---- 4. Collect nodes actually used by emitted shells -----------------
    std::set<int> usedNodeIds;
    for (const auto& f : freeFaces) {
        for (int n : f) if (n > 0) usedNodeIds.insert(n);
    }

    // ---- 5. Write the shell .k file ---------------------------------------
    std::ofstream out(outputFile);
    if (!out.is_open()) {
        console.error("Cannot open output file: " + outputFile);
        return 1;
    }

    out << "$# KooRemapper extract-surface\n";
    out << "$# source: " << solidFile << "\n";
    out << "$# filter: pid=" << opts.filterPid
        << " face=" << opts.face
        << " output_pid=" << opts.outputPid << "\n";
    out << "*KEYWORD\n";

    // *PART (with title line)
    out << "*PART\n";
    out << "Extracted surface (PID " << opts.outputPid << ")\n";
    out << "$#     pid     secid       mid     eosid       hgid      grav    adpopt      tmid\n";
    out << std::setw(10) << opts.outputPid
        << std::setw(10) << opts.outputPid    // SECID = PID (caller can edit)
        << std::setw(10) << 1                  // MID = 1 (placeholder; caller assigns real material)
        << std::setw(10) << 0
        << std::setw(10) << 0
        << std::setw(10) << 0
        << std::setw(10) << 0
        << std::setw(10) << 0 << "\n";

    // *NODE (preserving original IDs)
    out << "*NODE\n";
    out << "$#   nid               x               y               z      tc      rc\n";
    out << std::scientific << std::setprecision(7);
    for (int nid : usedNodeIds) {
        const auto& n = mesh.nodes.at(nid);
        out << std::setw(8) << nid
            << std::setw(16) << n.position.x
            << std::setw(16) << n.position.y
            << std::setw(16) << n.position.z
            << std::setw(8) << 0
            << std::setw(8) << 0 << "\n";
    }
    out.unsetf(std::ios_base::floatfield);

    // *ELEMENT_SHELL
    out << "*ELEMENT_SHELL\n";
    out << "$#   eid     pid      n1      n2      n3      n4\n";
    int eid = 1;
    int triCount = 0, quadCount = 0;
    for (const auto& f : freeFaces) {
        int n1 = f[0], n2 = f[1], n3 = f[2], n4 = f[3];
        if (isTriangle(f)) {
            // LS-DYNA TRIA3 written as QUAD4 with N4 = N3
            n4 = n3;
            ++triCount;
        } else {
            ++quadCount;
        }
        out << std::setw(8) << eid++
            << std::setw(8) << opts.outputPid
            << std::setw(8) << n1
            << std::setw(8) << n2
            << std::setw(8) << n3
            << std::setw(8) << n4 << "\n";
    }

    out << "*END\n";
    out.close();

    console.info("Extracted " + std::to_string(quadCount + triCount) + " surface faces"
                 + (triCount > 0
                    ? " (" + std::to_string(quadCount) + " QUAD4, "
                      + std::to_string(triCount) + " TRIA3 written as degenerate QUAD4)"
                    : "")
                 + " across " + std::to_string(usedNodeIds.size()) + " nodes");
    console.info("Written: " + outputFile);
    return 0;
}
