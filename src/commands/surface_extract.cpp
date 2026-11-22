#include "parser/DeckWriter.h"
#include "parser/OutputGuard.h"   // 쓸 파일이 읽는 파일을 덮는지(2026-11-07)
#include "surface_extract.h"
#include "parser/KFileReader.h"
#include "core/Mesh.h"
#include "core/Element.h"
#include "core/Vector3D.h"
#include "cli/ConsoleOutput.h"
#include "parser/DeckScan.h"           // 파트 · 섹션 번호 훑기(칸 폭 · 키워드)
#include "parser/ElementCardLayout.h"  // deckFieldWidth · keywordFieldWidth · formatRealField
#include "parser/IdAllocator.h"        // ids::limitWhy — 새 SECID 가 정수 상한을 넘을 때
#include "parser/IncludeClosure.h"     // 인클루드 닫힘 — 이미 있는 파트 번호 · 섹션 번호

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
// fw — 솔리드 덱의 칸 폭(8 · 10 · 20). 이 파일은 그 덱에 `*INCLUDE` 로 물리므로 같은 폭으로 쓰고 머리에 밝힌다 — 예전엔 늘 표준 폭
// 맨 `*KEYWORD` 여서, LONG=Y · I10=Y 덱이 물면 LS-DYNA 가 주 덱 폭으로 읽을 수 있었다(Vol_I 「Long Format Input」 — 2026-11-22).
void writeShellKFile(std::ostream& out,
                     const std::string& sourceTag,
                     const ExtractSurfaceOptions& opts,
                     const std::map<int, Vector3D>& nodes,
                     const std::vector<FaceKey>& shells,
                     int fw, int secId, int mid) {
    const int iw = fw >= 20 ? 20 : (fw == 10 ? 10 : 8);   // 절점 · 요소 줄의 정수 칸
    const int rw = fw >= 20 ? 20 : 16;                     // 좌표 칸
    const int cw = fw >= 20 ? 20 : 10;                     // 10 칸 카드(*PART)
    out << "$# KooRemapper extract-surface\n";
    out << "$# source: " << sourceTag << "\n";
    out << "$# filter: pid=" << opts.filterPid
        << " face=" << opts.face
        << " output_pid=" << opts.outputPid
        << " mid_surface=" << (opts.midSurface ? "yes" : "no") << "\n";
    out << (fw >= 20 ? "*KEYWORD LONG=Y\n" : fw == 10 ? "*KEYWORD I10=Y\n" : "*KEYWORD\n");

    out << "*PART\n";
    out << "Extracted surface (PID " << opts.outputPid << ")\n";
    out << "$#     pid     secid       mid     eosid       hgid      grav    adpopt      tmid\n";
    out << std::setw(cw) << opts.outputPid
        << std::setw(cw) << secId
        << std::setw(cw) << mid
        << std::setw(cw) << 0
        << std::setw(cw) << 0
        << std::setw(cw) << 0
        << std::setw(cw) << 0
        << std::setw(cw) << 0 << "\n";

    // 새 셸 섹션 — ELFORM 2 · SHRF 1.0 · NIP 2(LS-DYNA 기본과 같다) · T1~T4 = --thickness (2026-11-22 사용자 결정)
    out << "*SECTION_SHELL\n";
    out << "$#   secid    elform      shrf       nip\n";
    out << std::setw(cw) << secId << std::setw(cw) << 2 << std::setw(cw) << "1.0" << std::setw(cw) << 2 << "\n";
    out << "$#      t1        t2        t3        t4\n";
    for (int k = 0; k < 4; ++k) out << formatRealField(opts.thickness, cw);
    out << "\n";

    out << "*NODE\n";
    out << "$#   nid               x               y               z      tc      rc\n";
    out << std::scientific << std::setprecision(7);
    for (const auto& [nid, p] : nodes) {
        out << std::setw(iw) << nid
            << std::setw(rw) << p.x
            << std::setw(rw) << p.y
            << std::setw(rw) << p.z
            << std::setw(iw) << 0
            << std::setw(iw) << 0 << "\n";
    }
    out.unsetf(std::ios_base::floatfield);

    out << "*ELEMENT_SHELL\n";
    out << "$#   eid     pid      n1      n2      n3      n4\n";
    int eid = 1;
    for (const auto& f : shells) {
        int n1 = f[0], n2 = f[1], n3 = f[2], n4 = f[3];
        if (isTriangle(f)) n4 = n3;
        out << std::setw(iw) << eid++
            << std::setw(iw) << opts.outputPid
            << std::setw(iw) << n1
            << std::setw(iw) << n2
            << std::setw(iw) << n3
            << std::setw(iw) << n4 << "\n";
    }
    out << "*END\n";
}

// 솔리드 덱과 그 인클루드 닫힘이 정의하는 파트 번호(`*PART` 카드 — PID · SECID 가 양수인 줄)와 가장 큰 섹션 번호(`*SECTION_*` 데이터 줄의
// 첫 칸 — 넘치게 센다: 크게 세면 새 SECID 가 더 위로 갈 뿐이다). 파일마다 제 `*KEYWORD` 폭 · 키워드 접미사로 자른다.
void scanDeckIds(const std::vector<std::string>& lines, std::set<int>& pids, long long& maxSec) {
    const int deckFw = deckFieldWidth(lines);
    std::string kw;
    int fw = 10;
    for (const auto& l : lines) {
        if (deckscan::isKeywordLine(l)) {
            kw = deckscan::kwBare(deckscan::keywordToken(l));
            fw = keywordFieldWidth(l, deckFw) >= 20 ? 20 : 10;
            continue;
        }
        if (!deckscan::isDataLine(l)) continue;
        const auto f = deckscan::cardFields(l, fw);
        if (kw == "*PART" || kw == "*PART_TITLE") {
            const int pid = deckscan::fieldInt(f, 0);
            if (pid > 0 && deckscan::fieldInt(f, 1) > 0) pids.insert(pid);
        } else if (kw.rfind("*SECTION_", 0) == 0) {
            maxSec = std::max<long long>(maxSec, deckscan::fieldInt(f, 0));
        }
    }
}

} // anonymous namespace


int runExtractSurface(const std::string& solidFile,
                      const std::string& outputFile,
                      const ExtractSurfaceOptions& opts,
                      KooRemapper::ConsoleOutput& console) {
    using namespace KooRemapper;

    // ★쓰기 관문(2026-11-07 · output_guard) — 산출이 솔리드 메시(그 인클루드까지)와 같은 파일이면 읽기 · 쓰기 전에 거절한다
    if (output_guard::refuse("extract-surface", {outputFile}, output_guard::modelInputs(solidFile, "solid"), console)) return 1;

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

    // ★새 셸 파트(2026-11-22 · 사용자 결정 「셸 섹션까지 지어 넣는다」 · 「thickness · --thickness · 새 번호면 필수」) — --output-pid 가 솔리드
    //   덱(인클루드까지)에 이미 있는 파트 번호면 멈춘다(예전엔 rc 0 으로 그 번호의 *PART 를 하나 더 썼다). 새 번호에는 *PART 와
    //   *SECTION_SHELL 을 짓는다 — 예전 *PART 는 SECID 칸에 PID 를, MID 칸에 1 을 박아 정의 안 된 섹션 · 엉뚱한 재질을 가리켰다.
    std::set<int> usedPids;
    long long maxSecId = 0;
    {
        std::vector<std::string> mainLines;
        std::ifstream f(solidFile, std::ios::binary);
        for (std::string ln; std::getline(f, ln);) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            if (mainLines.empty() && ln.size() >= 3 && ln.compare(0, 3, "\xEF\xBB\xBF") == 0) ln.erase(0, 3);
            mainLines.push_back(ln);
        }
        scanDeckIds(mainLines, usedPids, maxSecId);
        for (const auto& inc : include_closure::read(solidFile, mainLines).files) scanDeckIds(inc.lines, usedPids, maxSecId);
    }
    for (const auto& [eid, e] : mesh.elements) { (void)eid; usedPids.insert(e.partId); }
    for (const auto& [pid, p] : mesh.parts) { (void)p; usedPids.insert(pid); }
    if (opts.outputPid <= 0) {
        console.error("--output-pid 는 1 이상이다(받은 값 " + std::to_string(opts.outputPid) + ")");
        return 1;
    }
    if (usedPids.count(opts.outputPid)) {
        console.error("--output-pid " + std::to_string(opts.outputPid) + " 은 " + solidFile + "(인클루드까지)에 이미 있는 파트 번호다 — "
                      "새 번호를 주라. 새 번호에 *PART 와 *SECTION_SHELL 을 짓는다. 아무 파일도 쓰지 않았다");
        return 1;
    }
    if (!(opts.thickness > 0.0)) {
        console.error("새 셸 파트(PID " + std::to_string(opts.outputPid) + ")의 *SECTION_SHELL 두께가 없다 — --thickness T 를 주라"
                      "(T1~T4 · ELFORM 2 · NIP 2). 아무 파일도 쓰지 않았다");
        return 1;
    }
    if (maxSecId >= std::numeric_limits<int>::max()) {
        console.error("[extract-surface] " + ids::limitWhy("섹션 번호", maxSecId + 1) + " — 아무 파일도 쓰지 않았다");
        return 1;
    }
    const int newSecId = static_cast<int>(maxSecId + 1);
    // 셸을 뽑은 솔리드 파트들의 MID 하나 — 서로 다르면 멈춘다. `*PART` 가 없는 메시(`generate arc` 의 덱)는 MID 가 0 이라 0 을 그대로
    // 옮기고 알린다(기준면으로만 쓰는 덱 — 해석에 쓰려면 재질을 정한다)
    auto shellMid = [&](const std::set<int>& srcPids, int& mid) {
        std::map<int, int> midOf;
        for (int pid : srcPids) {
            const auto it = mesh.parts.find(pid);
            midOf[pid] = it == mesh.parts.end() ? 0 : std::max(0, it->second.materialId);
        }
        std::set<int> mids;
        for (const auto& [pid, m] : midOf) { (void)pid; mids.insert(m); }
        if (mids.size() != 1) {
            std::string list;
            for (const auto& [pid, m] : midOf) list += (list.empty() ? "" : " · ") + std::string("PID ") + std::to_string(pid) + " → MID " + std::to_string(m);
            console.error("셸을 뽑은 솔리드 파트들의 MID 가 서로 다르다(" + list + ") — 새 셸 파트의 MID 를 하나로 정할 수 없다. --pid 로 "
                          "한 파트만 고르라. 아무 파일도 쓰지 않았다");
            return false;
        }
        mid = *mids.begin();
        if (mid == 0)
            console.warning("셸을 뽑은 솔리드 파트에 MID 가 없다 — 새 셸 파트(PID " + std::to_string(opts.outputPid) + ")의 *PART MID 칸도 0 "
                            "이다. 해석에 쓰려면 재질을 정하라");
        return true;
    };

    // ---- 2. Build face-count map ------------------------------------------
    struct FaceVal { int count; FaceKey winding; double elemZ; int pid; };
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
            if (it == faceMap.end()) faceMap[key] = {1, orig, ezc, elem.partId};
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
    std::set<int> topPids, bottomPids, allPids;   // 그 면을 가진 솔리드 요소의 PID — 새 셸 파트의 MID 를 정한다
    for (const auto& [key, val] : faceMap) {
        if (val.count != 1) continue;
        allPids.insert(val.pid);
        double dz = faceCentroidZ(val.winding, mesh) - val.elemZ;
        if (dz > 0)      { topFaces.push_back(val.winding); topPids.insert(val.pid); }
        else if (dz < 0) { bottomFaces.push_back(val.winding); bottomPids.insert(val.pid); }
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

        int mid = 0;
        if (!shellMid(topPids, mid)) return 1;   // 가운데 면은 윗면의 감김으로 짓는다
        // 원본 솔리드 덱의 개행을 따른다
        KooRemapper::DeckWriter out_w(outputFile, KooRemapper::deck_newline::detect(solidFile));
        if (!out_w.ok()) {
            console.error("Cannot open output file: " + outputFile);
            return 1;
        }
        std::ostream& out = out_w.stream();
        writeShellKFile(out, solidFile, opts, midPositions, midShells, reader.deckFieldWidth(), newSecId, mid);
        out_w.close();

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

    int mid = 0;
    if (!shellMid(opts.face == "top" ? topPids : opts.face == "bottom" ? bottomPids : allPids, mid)) return 1;
    // 원본 솔리드 덱의 개행을 따른다
    KooRemapper::DeckWriter out_w(outputFile, KooRemapper::deck_newline::detect(solidFile));
    if (!out_w.ok()) {
        console.error("Cannot open output file: " + outputFile);
        return 1;
    }
    std::ostream& out = out_w.stream();
    writeShellKFile(out, solidFile, opts, usedNodes, outFaces, reader.deckFieldWidth(), newSecId, mid);
    out_w.close();

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
