#include "core_ops.h"
#include "core/Platform.h"
#include <cstdio>
#include <cmath>
#include "core/Mesh.h"
#include "core/ShellMesh.h"
#include "parser/KFileReader.h"
#include "parser/KFileWriter.h"
#include "parser/DynainWriter.h"
#include "parser/ShellReader.h"
#include "mapper/MeshRemapper.h"
#include "mapper/FlatMeshGenerator.h"
#include "mapper/ShellMapper.h"
#include "mapper/ShellUnfolder.h"
#include "example/ExampleMeshGenerator.h"
#include "generator/VariableDensityConfig.h"
#include "generator/YamlConfigReader.h"
#include "generator/VariableDensityMeshGenerator.h"
#include "generator/CurvedMeshGenerator.h"
#include "analysis/StrainCalculator.h"
#include "analysis/ElementAnalyzer.h"
#include "analysis/MaterialModel.h"
#include "cli/ConsoleOutput.h"
#include "util/Timer.h"
#include "util/Validator.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <memory>
#include <limits>
#include <iomanip>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

using namespace KooRemapper;

namespace {

// =============================================================================
// bbox-align preprocessor
//
// Detail flat (CAD source) and simple_bent (target) often have small but
// non-zero bbox mismatches per axis -- e.g. detail width 44.5 vs bent k 44.897
// (0.9% drift). The mapper normalizes detail XYZ to [0,1]^3 and replays into
// bent ijk parametric coords, so any bbox ratio mismatch is silently injected
// as a uniform stretch on top of the genuine bending strain. That stretch
// shows up as an axial bias in the post-map prestress, breaking the otherwise
// symmetric ±κz bending stress distribution.
//
// This helper rescales ONE of the two meshes (per `mode`) so their bboxes line
// up before mapping. After rescaling, the only strain left in the prestress
// step is the actual bending term.
//
//   mode = "source": rescale flat (detail) so flat XYZ axes match the bent
//                    ijk neutral lengths. Detail geometry is mildly stretched
//                    by the per-axis ratios. The prestress reference must use
//                    the SAME scaled flat (caller writes a temp file).
//   mode = "target": rescale bent (target) so bent ijk neutral lengths match
//                    flat XYZ. Detail stays untouched. The prestress reference
//                    is the original flat (no temp file needed).
//   mode = "none":   no rescaling.
//
// Axis matching uses RANK by sorted length: smallest detail axis ↔ smallest
// bent axis, etc. This survives axis permutations (e.g. detail ZYX ↔ bent IJK)
// without depending on auto-axis-mapping running first.
// =============================================================================

struct BboxAlignResult {
    bool   applied = false;
    bool   rejected = false;             // drift exceeded max allowed
    std::string rejectionReason;
    std::string mode;                    // "source" / "target"
    double scale[3] = {1.0, 1.0, 1.0};   // scale applied to MODIFIED mesh's XYZ
    double maxDriftPct = 0.0;            // largest |1 - scale| in percent
    std::string axisMatch;               // "detailX↔bentK, detailY↔bentJ, detailZ↔bentI"
};

// Sort indices by ascending value; returns idx such that arr[idx[0]] <= ... <= arr[idx[2]]
void rankIndices(const double a[3], int idx[3]) {
    idx[0] = 0; idx[1] = 1; idx[2] = 2;
    auto cmp = [&](int x, int y){ return a[x] < a[y]; };
    if (cmp(idx[1], idx[0])) std::swap(idx[0], idx[1]);
    if (cmp(idx[2], idx[1])) std::swap(idx[1], idx[2]);
    if (cmp(idx[1], idx[0])) std::swap(idx[0], idx[1]);
}

void applyAffineScaleAboutCenter(Mesh& m, double sx, double sy, double sz) {
    if (sx == 1.0 && sy == 1.0 && sz == 1.0) return;
    Vector3D mn, mx;
    m.calculateBoundingBox(mn, mx);
    Vector3D c((mn.x + mx.x) * 0.5, (mn.y + mx.y) * 0.5, (mn.z + mx.z) * 0.5);
    for (auto& kv : m.nodes) {
        Vector3D& p = kv.second.position;
        p.x = c.x + (p.x - c.x) * sx;
        p.y = c.y + (p.y - c.y) * sy;
        p.z = c.z + (p.z - c.z) * sz;
        // Mirror to mappedPosition if it tracks original — matters only for
        // result writing later, but this is a pre-map mesh so the mapped
        // position is meaningless here. Leave it untouched.
    }
}

// Compute scale factors for `mode` given bent ijk neutral lengths and detail
// XYZ bbox lengths. axisMatch tags out which detail axis pairs with which
// bent axis (rank-based).
BboxAlignResult computeBboxAlign(const std::string& mode,
                                 const double bentIJK[3],
                                 const double detailXYZ[3],
                                 double maxDriftPct) {
    BboxAlignResult res;
    res.mode = mode;
    if (mode == "none" || mode.empty()) return res;

    int rb[3], rd[3];
    rankIndices(bentIJK, rb);
    rankIndices(detailXYZ, rd);
    // detailToBent[d] = bent axis paired with detail axis d (by rank).
    int detailToBent[3];
    for (int r = 0; r < 3; ++r) detailToBent[rd[r]] = rb[r];

    static const char* IJK[3] = {"i", "j", "k"};
    static const char* XYZ[3] = {"X", "Y", "Z"};
    {
        std::ostringstream am;
        for (int d = 0; d < 3; ++d) {
            if (d) am << ", ";
            am << "detail" << XYZ[d] << "↔bent" << IJK[detailToBent[d]];
        }
        res.axisMatch = am.str();
    }

    // Per-detail-axis ratio = bent_paired_length / detail_length.
    //   source mode: scale detail XYZ by this ratio (detail grows toward bent).
    //   target mode: scale bent (in detail XYZ frame) by reciprocal.
    // We always express the result as the scale APPLIED to whichever mesh is
    // being modified, indexed in that mesh's own XYZ frame.
    double sx[3];
    double maxAbsDelta = 0.0;
    for (int d = 0; d < 3; ++d) {
        double rd_len = detailXYZ[d];
        double rb_len = bentIJK[detailToBent[d]];
        if (rd_len < 1e-12 || rb_len < 1e-12) {
            res.rejected = true;
            res.rejectionReason = "degenerate axis length (one mesh is flat in some axis)";
            return res;
        }
        double ratio = rb_len / rd_len;       // detail -> bent
        if (mode == "source") {
            sx[d] = ratio;                     // grow detail toward bent
        } else {  // target
            // bent gets scaled in its own XYZ frame, but we want bent_x scale
            // to come from detail rank-paired with bent_x. That requires
            // inverting the detailToBent mapping below.
            sx[d] = 1.0;  // placeholder, fill in next loop
        }
        double drift = std::fabs(ratio - 1.0);
        if (drift > maxAbsDelta) maxAbsDelta = drift;
    }

    if (mode == "target") {
        // bentToDetail[b] = detail axis paired with bent axis b.
        int bentToDetail[3];
        for (int d = 0; d < 3; ++d) bentToDetail[detailToBent[d]] = d;
        for (int b = 0; b < 3; ++b) {
            double rd_len = detailXYZ[bentToDetail[b]];
            double rb_len = bentIJK[b];
            // Note: bent ijk lengths come from neutral arc length, but the
            // bent mesh's actual XYZ bbox length is what we'll be scaling.
            // For target rescale we still use detail/bent ratio in PARAMETRIC
            // (ijk) frame because that's what the mapper consumes -- the user
            // sees this as the fraction by which we shrink/expand the bent
            // mesh in its own physical XYZ. We approximate this as the same
            // ratio (1.0/ratio) since for moderate scales the PARAMETRIC arc
            // and the PHYSICAL extent move proportionally for slim bend
            // shapes. This is the operating point of the bbox-align feature.
            sx[b] = rd_len / rb_len;          // shrink bent toward detail
        }
    }

    // Always populate scale[] (even when rejected) so the diagnostic line
    // shows the would-be ratios. maxAbsDelta was computed in source-mode
    // form; recompute as max |1 - sx[i]| over all axes so target mode also
    // reflects what would be applied.
    double driftFromScales = 0.0;
    for (int i = 0; i < 3; ++i) {
        driftFromScales = std::max(driftFromScales, std::fabs(sx[i] - 1.0));
    }
    res.maxDriftPct = driftFromScales * 100.0;
    res.scale[0] = sx[0];
    res.scale[1] = sx[1];
    res.scale[2] = sx[2];

    if (res.maxDriftPct > maxDriftPct) {
        res.rejected = true;
        std::ostringstream rr;
        rr << "drift " << std::fixed << std::setprecision(3) << res.maxDriftPct
           << "% exceeds max " << maxDriftPct << "%";
        res.rejectionReason = rr.str();
        return res;
    }

    res.applied = (sx[0] != 1.0 || sx[1] != 1.0 || sx[2] != 1.0);
    return res;
}

}  // anonymous namespace

int runMapping(const std::string& bentFile, const std::string& flatFile,
               const std::string& outputFile, const ConsoleOutput& console,
               bool useParallel, bool forcePositive,
               bool flipX, bool flipY, bool flipZ,
               const std::string& bboxAlignMode,
               double bboxAlignMaxDriftPct,
               std::string* outScaledFlatPath,
               bool flipInputX, bool flipInputY, bool flipInputZ) {
    Timer timer;

    // Load bent mesh
    console.info("Loading bent mesh: " + bentFile);
    KFileReader reader;
    Mesh bentMesh;
    try {
        bentMesh = reader.readFile(bentFile);
    } catch (const std::exception& e) {
        console.error("Failed to load bent mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(bentMesh.getNodeCount()) + " nodes, " +
                   std::to_string(bentMesh.getElementCount()) + " elements");

    // Validate bent mesh
    auto bentValidation = Validator::validateBentMesh(bentMesh);
    if (!bentValidation.isValid) {
        for (const auto& err : bentValidation.errors) {
            console.error(err);
        }
        return 1;
    }
    for (const auto& warn : bentValidation.warnings) {
        console.warning(warn);
    }

    // Load flat mesh
    console.info("Loading flat mesh: " + flatFile);
    Mesh flatMesh;
    try {
        flatMesh = reader.readFile(flatFile);
    } catch (const std::exception& e) {
        console.error("Failed to load flat mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(flatMesh.getNodeCount()) + " nodes, " +
                   std::to_string(flatMesh.getElementCount()) + " elements");

    // Validate flat mesh
    auto flatValidation = Validator::validateFlatMesh(flatMesh);
    if (!flatValidation.isValid) {
        for (const auto& err : flatValidation.errors) {
            console.error(err);
        }
        return 1;
    }

    // -----------------------------------------------------------------
    // bbox-align preprocessor (optional)
    // -----------------------------------------------------------------
    std::string scaledFlatTmpPath;
    {
        std::string mode = bboxAlignMode;
        for (auto& c : mode) c = (char)std::tolower((unsigned char)c);
        if (mode != "none" && mode != "" && mode != "source" && mode != "target") {
            console.error("bbox_align: unknown mode '" + bboxAlignMode +
                          "' (expected: none | source | target)");
            return 1;
        }
        if (mode == "source" || mode == "target") {
            // Probe bent neutral arc lengths via a throwaway analyze.
            MeshRemapper probe;
            probe.setBentMesh(&bentMesh);
            probe.setFlatMesh(&flatMesh);
            if (!probe.analyzeBentOnly()) {
                console.error("bbox_align: bent analysis failed: " + probe.getErrorMessage());
                return 1;
            }
            double bentIJK[3] = {
                probe.getNeutralSizeI(),
                probe.getNeutralSizeJ(),
                probe.getNeutralSizeK()
            };

            Vector3D fMin0, fMax0;
            flatMesh.calculateBoundingBox(fMin0, fMax0);
            double detailXYZ[3] = {
                fMax0.x - fMin0.x,
                fMax0.y - fMin0.y,
                fMax0.z - fMin0.z
            };

            BboxAlignResult ba = computeBboxAlign(mode, bentIJK, detailXYZ,
                                                   bboxAlignMaxDriftPct);

            std::cout << "\n";
            console.header("bbox-align preprocessor");
            console.keyValue("Mode", mode);
            console.keyValue("Axis match", ba.axisMatch);
            {
                std::ostringstream s;
                s << std::fixed << std::setprecision(6)
                  << ba.scale[0] << " / " << ba.scale[1] << " / " << ba.scale[2]
                  << "  (drift " << std::setprecision(3) << ba.maxDriftPct << "%)";
                console.keyValue("Scale (X/Y/Z)", s.str());
            }

            if (ba.rejected) {
                console.error("bbox_align rejected: " + ba.rejectionReason);
                console.info("Raise bbox_align_max_drift if intentional, or fix the input "
                             "mesh sizing.");
                return 1;
            }
            if (ba.applied) {
                if (mode == "source") {
                    applyAffineScaleAboutCenter(flatMesh,
                                                ba.scale[0], ba.scale[1], ba.scale[2]);
                } else {  // target
                    applyAffineScaleAboutCenter(bentMesh,
                                                ba.scale[0], ba.scale[1], ba.scale[2]);
                }
                console.success(std::string("Applied scale to ") +
                                (mode == "source" ? "detail flat" : "bent target"));
            } else {
                console.info("Bboxes already aligned within tolerance — no scaling needed.");
            }
        }
    }

    // -----------------------------------------------------------------
    // flip-input preprocessor (optional)
    //
    // Mirror the detail flat IN PLACE before mapping, so the resulting
    // mapped mesh has its features (slits, holes, asymmetric thickness
    // patterns) on the opposite face of the bent target -- WITHOUT
    // moving the mapped mesh's global coordinates the way output flip
    // (--flip-x/y/z) would. Useful when:
    //   * detail CAD has a slit on +Z face but the model needs it on -Z
    //     face of the bent target (e.g. inner vs outer surface swap)
    //   * detail handedness needs adjusting independent of bent location
    //
    // HEX8 connectivity is also swapped on odd-parity flips so the
    // detail's Jacobian sign is preserved through the mirror; the
    // mapper's downstream sign-preservation logic then matches the
    // mirrored-detail's signs to the bent's Jacobian as usual.
    //
    // Composition with bbox_align=source: BOTH transforms write into the
    // same temp .k file (path stored in scaledFlatTmpPath -- name kept
    // for back-compat though it now means "preprocessed flat") so chain
    // prestress sees the already-mirrored-AND-scaled flat as F's
    // reference.
    //
    // Composition with output flip (--flip-x/y/z): orthogonal. flip_input
    // mirrors detail BEFORE mapping; output flip mirrors result AFTER.
    // Both can be combined; main.cpp's chain prestress wraps the second
    // step's mirror around the same flat ref.
    // -----------------------------------------------------------------
    if (flipInputX || flipInputY || flipInputZ) {
        Vector3D fMin, fMax;
        flatMesh.calculateBoundingBox(fMin, fMax);
        double cx = (fMin.x + fMax.x) * 0.5;
        double cy = (fMin.y + fMax.y) * 0.5;
        double cz = (fMin.z + fMax.z) * 0.5;
        for (auto& kv : flatMesh.nodes) {
            Vector3D& p = kv.second.position;
            if (flipInputX) p.x = 2.0 * cx - p.x;
            if (flipInputY) p.y = 2.0 * cy - p.y;
            if (flipInputZ) p.z = 2.0 * cz - p.z;
        }
        // Odd-parity mirror inverts every HEX8 Jacobian. Swap
        // bottom/top to restore positive winding so the source mesh
        // analyzer sees a clean right-handed input.
        int parity = (flipInputX ? 1 : 0) + (flipInputY ? 1 : 0) + (flipInputZ ? 1 : 0);
        if ((parity % 2) != 0) {
            for (auto& kv : flatMesh.elements) {
                Element& e = kv.second;
                if (e.type != ElementType::HEX8) continue;
                std::array<int, 8> orig = e.nodeIds;
                e.nodeIds[0] = orig[4]; e.nodeIds[1] = orig[5];
                e.nodeIds[2] = orig[6]; e.nodeIds[3] = orig[7];
                e.nodeIds[4] = orig[0]; e.nodeIds[5] = orig[1];
                e.nodeIds[6] = orig[2]; e.nodeIds[7] = orig[3];
            }
        }
        std::string axes;
        if (flipInputX) axes += "X";
        if (flipInputY) axes += "Y";
        if (flipInputZ) axes += "Z";
        console.info("Input mirror: detail flat " + axes +
                     " axis flipped before mapping" +
                     ((parity % 2) != 0 ? " (HEX8 connectivity swapped, parity restored)" : ""));
    }

    // If detail flat got pre-processed (bbox_align=source and/or
    // flip_input), persist it as a temp .k so chain prestress can use
    // the SAME pre-processed mesh as F's reference. Otherwise F would
    // compute against the un-pre-processed flat and reintroduce the
    // injected stretch / mirror as spurious residual strain.
    bool flatWasPreprocessed = (!scaledFlatTmpPath.empty()) ||
                                flipInputX || flipInputY || flipInputZ;
    if (flatWasPreprocessed) {
        // Use the existing path slot regardless of which preprocessor(s)
        // ran -- bbox_align=source may have written it already, but we
        // need to re-write to capture the additional flip_input state.
        if (scaledFlatTmpPath.empty()) {
            scaledFlatTmpPath = outputFile + ".__preproc_flat.k";
        }
        KFileWriter w;
        if (!w.writeFile(scaledFlatTmpPath, flatMesh, false)) {
            console.warning("Failed to write pre-processed flat temp: "
                            + w.getErrorMessage()
                            + " (chain prestress may report residual strain)");
            scaledFlatTmpPath.clear();
        } else if (outScaledFlatPath) {
            *outScaledFlatPath = scaledFlatTmpPath;
        }
    }

    // Perform mapping
    std::string modeStr = useParallel ? "parallel" : "single-threaded";
    console.info("Performing mesh mapping (" + modeStr + " mode)...");
    MeshRemapper remapper;
    remapper.setBentMesh(&bentMesh);
    remapper.setFlatMesh(&flatMesh);
    remapper.setForcePositive(forcePositive);
    if (forcePositive) {
        console.info("Force-positive mode: result HEX8 Jacobians will be made positive "
                     "regardless of source winding.");
    }
    remapper.setOutputFlip(flipX, flipY, flipZ);
    if (flipX || flipY || flipZ) {
        std::string axes;
        if (flipX) axes += "X";
        if (flipY) axes += "Y";
        if (flipZ) axes += "Z";
        console.info("Output mirror: " + axes +
                     " axis flipped (HEX8 connectivity swapped to preserve handedness if needed).");
    }

    // Set progress callback
    remapper.setProgressCallback([&console](int percent) {
        console.progressBar(percent);
    });

    if (!remapper.performMapping(useParallel)) {
        console.clearLine();
        console.error("Mapping failed: " + remapper.getErrorMessage());
        return 1;
    }
    console.clearLine();
    console.success("Mapping completed successfully");

    // Report auto-detected axis mapping
    int axisMap[3];
    remapper.getAxisMap(axisMap);
    auto ijkName = [](int v) -> std::string {
        return (v == 0) ? "i" : (v == 1) ? "j" : "k";
    };
    bool isIdentity = (axisMap[0] == 0 && axisMap[1] == 1 && axisMap[2] == 2);
    std::cout << "\n";
    console.header("Auto Axis Mapping (detail XYZ -> bent ijk)");

    // Source lengths used for ranking (for diagnostic clarity)
    double bentI = remapper.getNeutralSizeI();
    double bentJ = remapper.getNeutralSizeJ();
    double bentK = remapper.getNeutralSizeK();
    Vector3D fMin, fMax;
    flatMesh.calculateBoundingBox(fMin, fMax);
    double dX = fMax.x - fMin.x, dY = fMax.y - fMin.y, dZ = fMax.z - fMin.z;

    auto fmt3 = [](double a, double b, double c) {
        std::ostringstream ss;
        ss << std::fixed << std::setprecision(3)
           << a << " / " << b << " / " << c;
        return ss.str();
    };
    console.keyValue("Bent ijk lengths",  fmt3(bentI, bentJ, bentK));
    console.keyValue("Detail XYZ lengths", fmt3(dX, dY, dZ));
    console.keyValue("Detail X -> bent", ijkName(axisMap[0]));
    console.keyValue("Detail Y -> bent", ijkName(axisMap[1]));
    console.keyValue("Detail Z -> bent", ijkName(axisMap[2]));
    if (!isIdentity) {
        console.info("Detail axes were reordered to match bent ijk arc lengths.");
    }
    const std::string& topo = remapper.getTopologyDiagnostic();
    if (!topo.empty()) {
        console.info("Topology: " + topo);
    }
    {
        long long filled = remapper.getGridFilledCount();
        long long total  = remapper.getGridTotalCount();
        bool active = remapper.isGridLookupActive();
        if (total > 0) {
            double pct = 100.0 * (double)filled / (double)total;
            char buf[128];
            std::snprintf(buf, sizeof(buf),
                "%lld / %lld grid nodes (%.2f%%)  active=%s",
                filled, total, pct, active ? "yes" : "no");
            console.keyValue("Interior grid lookup", std::string(buf));
        }
    }

    // Print statistics
    const auto& stats = remapper.getStats();

    // Format helper: scientific notation for small magnitudes, fixed for
    // values in a "human" range. std::to_string truncates anything below
    // ~1e-6 to "0.000000" which is highly misleading when the actual value
    // is 1e-19 (genuine collapse) vs 1e-7 (just small but valid).
    auto fmtJac = [](double v) -> std::string {
        char buf[32];
        double a = std::fabs(v);
        if (a == 0.0) return "0";
        if (a < 1e-3 || a >= 1e7) {
            std::snprintf(buf, sizeof(buf), "%+.6e", v);
        } else {
            std::snprintf(buf, sizeof(buf), "%.6f", v);
        }
        return std::string(buf);
    };

    // Source mesh diagnostic (pre-map). Helps separate source-side bugs
    // from mapping-side bugs.
    if (stats.sourceHex8Count > 0) {
        std::cout << "\n";
        console.header("Source Mesh Diagnostic (pre-map jacFlat)");
        console.keyValue("HEX8 elements analyzed", std::to_string(stats.sourceHex8Count));
        console.keyValue("Positive jacFlat (right-handed)",
                         std::to_string(stats.sourcePosJacCount));
        if (stats.sourceNegJacCount > 0) {
            console.warning("Negative jacFlat (left-handed CW winding): " +
                            std::to_string(stats.sourceNegJacCount));
        }
        if (stats.sourceDegenerateCount > 0) {
            console.warning("Degenerate (|jacFlat| < 1e-15): " +
                            std::to_string(stats.sourceDegenerateCount));
        }
        console.keyValue("Source jacFlat range",
                         fmtJac(stats.sourceMinJac) + " to " +
                         fmtJac(stats.sourceMaxJac));
        if (stats.sourceNegJacCount > 0 && stats.sourcePosJacCount > 0) {
            console.warning("Source mesh has MIXED orientation. "
                            "Per-element correction will preserve each element's source sign. "
                            "Use --force-positive if you want all output positive.");
        }
    }

    std::cout << "\n";
    console.header("Mapping Statistics");
    console.keyValue("Nodes processed", std::to_string(stats.nodesProcessed));
    console.keyValue("Elements processed", std::to_string(stats.elementsProcessed));
    console.keyValue("Min Jacobian", fmtJac(stats.minJacobian));
    console.keyValue("Max Jacobian", fmtJac(stats.maxJacobian));
    console.keyValue("Avg Jacobian", fmtJac(stats.avgJacobian));
    if (stats.invalidElements > 0) {
        console.warning("Invalid elements (negative Jacobian): " +
                       std::to_string(stats.invalidElements));
    }
    if (stats.reorientedElements > 0) {
        console.info("Reoriented elements (connectivity swap for sign match): " +
                     std::to_string(stats.reorientedElements));
    }
    console.keyValue("Processing time", std::to_string(stats.processingTimeMs) + " ms");
    std::cout << "\n";

    // Write output (use mapped positions).
    //
    // Preserve the flat input's non-geometry cards (*PART, *SECTION_*, *MAT_*,
    // *CONTROL_*, *CONTACT_*, *BOUNDARY_*, *INCLUDE, …) so the result is a
    // self-contained LS-DYNA deck rather than a NODE+ELEMENT_SOLID stub.
    // The flat file is the canonical source for material/part definitions in
    // the standard workflow (CAD-derived geometry + material assignment); the
    // bent reference contributes only the target shape.
    console.info("Writing output: " + outputFile);
    KFileWriter writer;
    if (!writer.writeFileWithSource(outputFile, remapper.getResult(), flatFile, true)) {
        console.error("Failed to write output: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Output written successfully");

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Run shell-based mapping operation
 */
int runShellMapping(const std::string& bentShellFile, const std::string& flatFile,
                    const std::string& outputFile, double thickness,
                    const ConsoleOutput& console) {
    Timer timer;

    // Load bent shell mesh
    console.info("Loading bent shell mesh: " + bentShellFile);
    ShellReader shellReader;
    ShellMesh bentShell;
    try {
        bentShell = shellReader.readFile(bentShellFile);
    } catch (const std::exception& e) {
        console.error("Failed to load bent shell mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(bentShell.getNodeCount()) + " nodes, " +
                   std::to_string(bentShell.getElementCount()) + " shell elements");

    // Validate
    std::string validationError;
    if (!bentShell.validate(validationError)) {
        console.error("Shell mesh validation failed: " + validationError);
        return 1;
    }

    // Load flat detail mesh
    console.info("Loading flat detail mesh: " + flatFile);
    KFileReader reader;
    Mesh flatMesh;
    try {
        flatMesh = reader.readFile(flatFile);
    } catch (const std::exception& e) {
        console.error("Failed to load flat mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(flatMesh.getNodeCount()) + " nodes, " +
                   std::to_string(flatMesh.getElementCount()) + " elements");

    // Auto-detect thickness from flat mesh Z-range if not specified
    if (thickness <= 0.0) {
        auto [bbMin, bbMax] = flatMesh.getBoundingBox();
        thickness = bbMax.z - bbMin.z;
        if (thickness < 1e-15) {
            // Shell detail (no Z extent) - set thickness to 0
            thickness = 0.0;
            console.info("Detail mesh appears to be a shell (no Z extent)");
        } else {
            console.info("Auto-detected thickness from Z-range: " + std::to_string(thickness));
        }
    } else {
        console.info("Using specified thickness: " + std::to_string(thickness));
    }

    // Build shell mapper
    console.info("Unfolding shell mesh and building mapper...");
    ShellMapper mapper;
    if (!mapper.build(bentShell)) {
        console.error("Failed to build shell mapper: " + mapper.getErrorMessage());
        return 1;
    }

    // Report unfolding results
    const auto& unfolder = mapper.getUnfolder();
    std::cout << "\n";
    console.header("Shell Unfolding Results");
    console.keyValue("Flat extent X", std::to_string(unfolder.getTotalLengthX()));
    console.keyValue("Flat extent Y", std::to_string(unfolder.getTotalLengthY()));
    console.keyValue("Max distortion", std::to_string(unfolder.getMaxDistortion() * 100.0) + "%");
    console.keyValue("Avg distortion", std::to_string(unfolder.getAvgDistortion() * 100.0) + "%");

    if (unfolder.getMaxDistortion() > 0.05) {
        console.warning("High area distortion detected (>" + std::to_string(5.0) +
                       "%). Surface may not be developable.");
    }
    std::cout << "\n";

    // Perform mapping (auto-aligns flat detail BB to unfolded shell BB)
    console.info("Mapping flat mesh onto bent shell...");
    Mesh resultMesh;
    if (!mapper.mapMesh(flatMesh, resultMesh, thickness)) {
        console.error("Mapping failed: " + mapper.getErrorMessage());
        return 1;
    }

    if (mapper.isAxesSwapped()) {
        console.info("Auto-alignment: axes swapped (flat X<->Y) to match unfolded shell");
    }

    int unmapped = mapper.getUnmappedCount();
    if (unmapped > 0) {
        console.warning(std::to_string(unmapped) + " nodes could not be mapped (outside shell domain)");
    }
    console.success("Mapping completed: " + std::to_string(flatMesh.getNodeCount()) + " nodes mapped");

    // Write output — preserve flat's non-geometry cards (see runMapping for rationale).
    console.info("Writing output: " + outputFile);
    KFileWriter writer;
    if (!writer.writeFileWithSource(outputFile, resultMesh, flatFile, true)) {
        console.error("Failed to write output: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Output written successfully");

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Generate example meshes
 */
int runGenerate(const std::string& type, const std::string& outputPrefix,
                int dimI, int dimJ, int dimK, const ConsoleOutput& console) {
    console.info("Generating example meshes...");

    ExampleMeshConfig config;
    config.dimI = dimI;
    config.dimJ = dimJ;
    config.dimK = dimK;

    // Parse type
    if (type == "teardrop") {
        config.bentType = BentMeshType::TEARDROP;
    } else if (type == "arc") {
        config.bentType = BentMeshType::ARC;
    } else if (type == "scurve") {
        config.bentType = BentMeshType::S_CURVE;
    } else if (type == "helix") {
        config.bentType = BentMeshType::HELIX;
    } else if (type == "torus") {
        config.bentType = BentMeshType::TORUS;
    } else if (type == "twist") {
        config.bentType = BentMeshType::TWIST;
    } else if (type == "bendtwist") {
        config.bentType = BentMeshType::BEND_TWIST;
    } else if (type == "wave") {
        config.bentType = BentMeshType::WAVE;
    } else if (type == "bulge") {
        config.bentType = BentMeshType::BULGE;
    } else if (type == "taper") {
        config.bentType = BentMeshType::TAPER;
    } else if (type == "waterdrop") {
        config.bentType = BentMeshType::WATERDROP;
        // 폴더블 디스플레이 치수: 길이 160mm, 폭 70mm, 두께 1mm
        config.lengthI = 160.0;  // 길이 (접히는 방향)
        config.lengthJ = 70.0;   // 폭 (넓은 방향)
        config.lengthK = 1.0;    // 두께 (얇음)
        config.waterdropFoldRadius = 2.0;  // U자 반경 2mm
        config.waterdropFlatRatio = 0.45;  // 양쪽 45%씩 평평, 중간 10%가 U자
    } else {
        console.error("Unknown mesh type: " + type);
        console.info("Valid types: teardrop, arc, scurve, helix, torus, twist, bendtwist, wave, bulge, taper, waterdrop");
        return 1;
    }

    ExampleMeshGenerator generator;

    // Generate bent mesh
    std::string bentFile = outputPrefix + "_bent.k";
    console.info("Generating bent mesh (" + type + ")...");
    Mesh bentMesh = generator.generateBentMesh(config);
    console.success("Generated " + std::to_string(bentMesh.getNodeCount()) + " nodes, " +
                   std::to_string(bentMesh.getElementCount()) + " elements");

    KFileWriter writer;
    if (!writer.writeFile(bentFile, bentMesh)) {
        console.error("Failed to write bent mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Written: " + bentFile);

    // Generate flat mesh
    std::string flatFile = outputPrefix + "_flat.k";
    console.info("Generating flat mesh...");
    Mesh flatMesh = generator.generateFlatMesh(config);
    console.success("Generated " + std::to_string(flatMesh.getNodeCount()) + " nodes, " +
                   std::to_string(flatMesh.getElementCount()) + " elements");

    if (!writer.writeFile(flatFile, flatMesh)) {
        console.error("Failed to write flat mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Written: " + flatFile);

    // Generate fine flat mesh for mapping test
    std::string fineFile = outputPrefix + "_flat_fine.k";
    console.info("Generating refined flat mesh for mapping test...");
    Mesh fineMesh = generator.generateFlatUnstructuredMesh(config, 2);
    console.success("Generated " + std::to_string(fineMesh.getNodeCount()) + " nodes, " +
                   std::to_string(fineMesh.getElementCount()) + " elements");

    if (!writer.writeFile(fineFile, fineMesh)) {
        console.error("Failed to write fine mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Written: " + fineFile);

    // Generate tetrahedral flat mesh for mapping test
    std::string tetFile = outputPrefix + "_flat_tet.k";
    console.info("Generating tetrahedral flat mesh for mapping test...");
    Mesh tetMesh = generator.generateFlatTetMesh(config);
    console.success("Generated " + std::to_string(tetMesh.getNodeCount()) + " nodes, " +
                   std::to_string(tetMesh.getElementCount()) + " elements (TET4)");

    if (!writer.writeFile(tetFile, tetMesh)) {
        console.error("Failed to write tet mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Written: " + tetFile);

    std::cout << "\n";
    console.info("Example usage for mapping:");
    console.println("  KooRemapper map " + bentFile + " " + fineFile + " " +
                   outputPrefix + "_mapped.k");
    console.println("  KooRemapper map " + bentFile + " " + tetFile + " " +
                   outputPrefix + "_mapped_tet.k");

    return 0;
}

/**
 * Calculate strain between two meshes
 */
int runStrain(const std::string& refFile, const std::string& defFile,
              const std::string& outputFile, const std::string& strainType,
              const ConsoleOutput& console) {
    Timer timer;

    // Load reference mesh
    console.info("Loading reference mesh: " + refFile);
    KFileReader reader;
    Mesh refMesh;
    try {
        refMesh = reader.readFile(refFile);
    } catch (const std::exception& e) {
        console.error("Failed to load reference mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(refMesh.getNodeCount()) + " nodes, " +
                   std::to_string(refMesh.getElementCount()) + " elements");

    // Load deformed mesh
    console.info("Loading deformed mesh: " + defFile);
    Mesh defMesh;
    try {
        defMesh = reader.readFile(defFile);
    } catch (const std::exception& e) {
        console.error("Failed to load deformed mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(defMesh.getNodeCount()) + " nodes, " +
                   std::to_string(defMesh.getElementCount()) + " elements");

    // Setup strain calculator
    StrainCalculator calc;
    calc.setReferenceMesh(&refMesh);
    calc.setDeformedMesh(&defMesh);

    // Set strain type
    if (strainType == "engineering") {
        calc.setStrainType(StrainCalculator::StrainType::ENGINEERING);
    } else if (strainType == "green") {
        calc.setStrainType(StrainCalculator::StrainType::GREEN_LAGRANGE);
    } else if (strainType == "log") {
        calc.setStrainType(StrainCalculator::StrainType::LOGARITHMIC);
    }

    // Calculate strains
    console.info("Calculating strains...");
    if (!calc.calculate()) {
        console.error("Strain calculation failed: " + calc.getErrorMessage());
        return 1;
    }
    console.success("Strain calculation completed");

    // Get statistics
    const auto& stats = calc.getStatistics();
    std::cout << "\n";
    console.header("Strain Statistics");
    console.keyValue("Max Von Mises", std::to_string(stats.maxVonMises));
    console.keyValue("Avg Von Mises", std::to_string(stats.avgVonMises));
    console.keyValue("Max Volumetric", std::to_string(stats.maxVolumetric));
    console.keyValue("Min Volumetric", std::to_string(stats.minVolumetric));
    console.keyValue("Max Principal", std::to_string(stats.maxPrincipal));
    console.keyValue("Min Principal", std::to_string(stats.minPrincipal));
    std::cout << "\n";

    // Export to CSV
    console.info("Exporting results: " + outputFile);
    if (!calc.exportToCSV(outputFile)) {
        console.error("Failed to export results");
        return 1;
    }
    console.success("Results exported successfully");

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Unfold a bent mesh to generate flat mesh
 */
int runUnfold(const std::string& bentFile, const std::string& outputFile,
              const ConsoleOutput& console) {
    Timer timer;

    // Load bent mesh
    console.info("Loading bent mesh: " + bentFile);
    KFileReader reader;
    Mesh bentMesh;
    try {
        bentMesh = reader.readFile(bentFile);
    } catch (const std::exception& e) {
        console.error("Failed to load bent mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(bentMesh.getNodeCount()) + " nodes, " +
                   std::to_string(bentMesh.getElementCount()) + " elements");

    // Validate bent mesh
    auto bentValidation = Validator::validateBentMesh(bentMesh);
    if (!bentValidation.isValid) {
        for (const auto& err : bentValidation.errors) {
            console.error(err);
        }
        return 1;
    }
    for (const auto& warn : bentValidation.warnings) {
        console.warning(warn);
    }

    // Generate flat mesh
    console.info("Generating flat mesh from bent mesh...");
    FlatMeshGenerator generator;
    Mesh flatMesh = generator.generateFlatMesh(bentMesh);

    if (flatMesh.getNodeCount() == 0) {
        console.error("Failed to generate flat mesh: " + generator.getErrorMessage());
        return 1;
    }

    // Print dimensions
    std::cout << "\n";
    console.header("Unfolded Mesh Dimensions");
    console.keyValue("Grid size", std::to_string(generator.getDimI()) + " x " +
                                  std::to_string(generator.getDimJ()) + " x " +
                                  std::to_string(generator.getDimK()));
    console.keyValue("Flat length (I)", std::to_string(generator.getFlatLengthI()) + " (arc-length)");
    console.keyValue("Flat length (J)", std::to_string(generator.getFlatLengthJ()));
    console.keyValue("Flat length (K)", std::to_string(generator.getFlatLengthK()));
    std::cout << "\n";

    console.success("Generated " + std::to_string(flatMesh.getNodeCount()) + " nodes, " +
                   std::to_string(flatMesh.getElementCount()) + " elements");

    // Write output
    console.info("Writing output: " + outputFile);
    KFileWriter writer;
    if (!writer.writeFile(outputFile, flatMesh)) {
        console.error("Failed to write output: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Output written successfully");

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    std::cout << "\n";
    console.info("Usage hint:");
    console.println("  Use this flat mesh as reference for mapping a detailed flat mesh:");
    console.println("  KooRemapper map " + bentFile + " <detailed_flat.k> <output_bent.k>");

    return 0;
}

/**
 * Calculate prestress from deformed configuration
 */
int runPrestress(const std::string& refFile, const std::string& defFile,
                 const std::string& outputFile, 
                 double E, double nu,
                 StrainType strainType,
                 bool outputCSV,
                 const ConsoleOutput& console) {
    Timer timer;

    // Load reference mesh
    console.info("Loading reference mesh: " + refFile);
    KFileReader reader;
    Mesh refMesh;
    try {
        refMesh = reader.readFile(refFile);
    } catch (const std::exception& e) {
        console.error("Failed to load reference mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(refMesh.getNodeCount()) + " nodes, " +
                   std::to_string(refMesh.getElementCount()) + " elements");
    
    // Report materials found in K-file (per-part)
    const auto& parts = refMesh.getParts();
    const auto& materials = refMesh.getMaterials();

    if (!parts.empty()) {
        console.info("Part-Material mapping:");
        int missingMaterialCount = 0;
        for (const auto& [partId, part] : parts) {
            auto matIt = materials.find(part.materialId);
            if (matIt != materials.end()) {
                std::ostringstream oss;
                oss << std::scientific << std::setprecision(4);
                oss << "  Part " << partId << " -> Material " << part.materialId
                    << ": E=" << matIt->second.E << ", nu=" << std::fixed << std::setprecision(4) << matIt->second.nu;
                console.println(oss.str());
            } else {
                console.warning("  Part " + std::to_string(partId) + " -> Material " +
                              std::to_string(part.materialId) + ": NOT FOUND");
                missingMaterialCount++;
            }
        }
        if (missingMaterialCount > 0) {
            console.warning(std::to_string(missingMaterialCount) + " part(s) have missing materials - stress will be 0");
        }
    } else if (refMesh.getMaterialCount() > 0) {
        // No parts but have materials (unusual case)
        console.info("Found " + std::to_string(refMesh.getMaterialCount()) + " material(s) in K-file:");
        for (const auto& [matId, mat] : materials) {
            std::ostringstream oss;
            oss << std::scientific << std::setprecision(4);
            oss << "  Material " << matId << ": E=" << mat.E
                << ", nu=" << std::fixed << std::setprecision(4) << mat.nu;
            console.println(oss.str());
        }
    }

    // Load deformed mesh
    console.info("Loading deformed mesh: " + defFile);
    Mesh defMesh;
    try {
        defMesh = reader.readFile(defFile);
    } catch (const std::exception& e) {
        console.error("Failed to load deformed mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(defMesh.getNodeCount()) + " nodes, " +
                   std::to_string(defMesh.getElementCount()) + " elements");

    // Validate mesh pair
    std::string validationError;
    if (!ElementAnalyzer::validateMeshPair(refMesh, defMesh, validationError)) {
        console.error("Mesh pair validation failed: " + validationError);
        return 1;
    }

    // Setup analyzer
    console.info("Analyzing strain/stress...");
    ElementAnalyzer analyzer;
    analyzer.setStrainType(strainType);
    analyzer.setUsePartMaterials(true);  // Enable per-part material lookup

    // Check if we have materials from command line or K-file
    bool hasCmdLineMaterial = (E > 0 && nu > 0 && nu < 0.5);
    bool hasKFileMaterial = (refMesh.getMaterialCount() > 0);
    bool hasMaterial = hasCmdLineMaterial || hasKFileMaterial;
    
    if (hasCmdLineMaterial) {
        // Command line material overrides K-file materials completely
        MaterialModel material = MaterialModel::isotropicElastic(E, nu);
        analyzer.setMaterial(material);
        analyzer.setUsePartMaterials(false);  // Disable per-part lookup
        console.info("Using command-line material: E=" + std::to_string(E) + ", nu=" + std::to_string(nu));
        if (hasKFileMaterial) {
            console.info("(K-file materials are overridden)");
        }
    } else if (hasKFileMaterial) {
        analyzer.setUsePartMaterials(true);  // Enable per-part lookup
        console.info("Using materials from K-file (per-part)");
    } else {
        console.info("No material specified, computing strain only");
    }

    // Run analysis with progress
    MeshAnalysisResult results = analyzer.analyzeMesh(refMesh, defMesh, 
        [&console](int percent) {
            console.progressBar(percent);
        });
    console.clearLine();
    console.success("Analysis completed");

    // Print statistics
    std::cout << "\n";
    console.header("Analysis Results");
    console.keyValue("Valid elements", std::to_string(results.validElements));
    if (results.invalidElements > 0) {
        console.warning("Invalid elements: " + std::to_string(results.invalidElements));
    }
    
    console.keyValue("Strain type", 
        strainType == StrainType::ENGINEERING ? "Engineering" : "Green-Lagrange");
    console.keyValue("Min von Mises strain", std::to_string(results.minVonMisesStrain));
    console.keyValue("Max von Mises strain", std::to_string(results.maxVonMisesStrain));
    console.keyValue("Avg von Mises strain", std::to_string(results.avgVonMisesStrain));

    if (hasMaterial) {
        std::cout << "\n";
        std::ostringstream ossMin, ossMax, ossAvg;
        ossMin << std::scientific << std::setprecision(6) << results.minVonMisesStress;
        ossMax << std::scientific << std::setprecision(6) << results.maxVonMisesStress;
        ossAvg << std::scientific << std::setprecision(6) << results.avgVonMisesStress;
        console.keyValue("Min von Mises stress", ossMin.str());
        console.keyValue("Max von Mises stress", ossMax.str());
        console.keyValue("Avg von Mises stress", ossAvg.str());
    }
    std::cout << "\n";

    // Write output
    DynainWriter writer;
    writer.setLargeDeformation(strainType == StrainType::GREEN_LAGRANGE);

    if (hasMaterial) {
        console.info("Writing dynain file: " + outputFile);
        if (!writer.writeFile(outputFile, results, strainType, refFile, defFile)) {
            console.error("Failed to write dynain: " + writer.getErrorMessage());
            return 1;
        }
        console.success("Dynain file written successfully");

        // Create a copy of deformed mesh with *INCLUDE for dynain
        // The dynain contains stress-only data, meant to be used with deformed mesh
        // Output filename: same as dynain but with .k extension
        std::string meshOutputFile = outputFile;
        size_t dotPos = meshOutputFile.rfind('.');
        if (dotPos != std::string::npos) {
            meshOutputFile = meshOutputFile.substr(0, dotPos) + ".k";
        } else {
            meshOutputFile += ".k";
        }

        // Get just the dynain filename (not full path) for *INCLUDE
        std::string dynainFilename = outputFile;
        size_t slashPos = dynainFilename.find_last_of("/\\");
        if (slashPos != std::string::npos) {
            dynainFilename = dynainFilename.substr(slashPos + 1);
        }

        // Read the deformed mesh entirely INTO MEMORY first, then write the
        // augmented copy. Buffering up front (rather than streaming src->dst)
        // makes the operation safe even when meshOutputFile and defFile refer
        // to the same file -- a real hazard when the user picks `output:` and
        // `prestress.output:` with matching prefixes (e.g. foo.k + foo.dynain
        // both auto-derive foo.k). Streaming src->dst in that case truncates
        // the source on dst-open and produces a .k with only *INCLUDE/*END
        // (no mesh content), the exact symptom users hit.
        std::vector<std::string> defLines;
        {
            std::ifstream srcFile(defFile, std::ios::binary);
            if (!srcFile.is_open()) {
                console.error("Failed to read deformed mesh for copy");
                return 1;
            }
            std::string line;
            defLines.reserve(1024);
            while (std::getline(srcFile, line)) defLines.push_back(std::move(line));
        }
        if (defLines.empty()) {
            console.error("Deformed mesh file is empty: " + defFile);
            return 1;
        }

        std::ofstream dstFile(meshOutputFile, std::ios::binary);
        if (!dstFile.is_open()) {
            console.error("Failed to create mesh output file: " + meshOutputFile);
            return 1;
        }

        // Copy original content, inserting *INCLUDE before *END.
        bool endFound = false;
        for (const auto& line : defLines) {
            std::string trimmedLine = line;
            size_t start = trimmedLine.find_first_not_of(" \t");
            if (start != std::string::npos) {
                trimmedLine = trimmedLine.substr(start);
            }
            if (trimmedLine.length() >= 4 &&
                (trimmedLine[0] == '*') &&
                (trimmedLine[1] == 'E' || trimmedLine[1] == 'e') &&
                (trimmedLine[2] == 'N' || trimmedLine[2] == 'n') &&
                (trimmedLine[3] == 'D' || trimmedLine[3] == 'd')) {
                dstFile << "*INCLUDE\n";
                dstFile << dynainFilename << "\n";
                endFound = true;
            }
            dstFile << line << "\n";
        }

        if (!endFound) {
            dstFile << "*INCLUDE\n";
            dstFile << dynainFilename << "\n";
            dstFile << "*END\n";
        }

        dstFile.close();

        console.success("Deformed mesh with prestress: " + meshOutputFile);
    }

    // Write CSV if requested or if no material
    if (outputCSV || !hasMaterial) {
        std::string csvFile = outputFile;
        if (hasMaterial) {
            // Change extension to .csv
            size_t dotPos = csvFile.rfind('.');
            if (dotPos != std::string::npos) {
                csvFile = csvFile.substr(0, dotPos) + ".csv";
            } else {
                csvFile += ".csv";
            }
        }

        console.info("Writing CSV file: " + csvFile);
        if (!writer.writeStrainCSV(csvFile, results)) {
            console.error("Failed to write CSV: " + writer.getErrorMessage());
            return 1;
        }
        console.success("CSV file written successfully");
    }

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Display mesh info
 */
int runInfo(const std::string& meshFile, const ConsoleOutput& console) {
    console.info("Loading mesh: " + meshFile);

    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(meshFile);
    } catch (const std::exception& e) {
        console.error("Failed to load mesh: " + std::string(e.what()));
        return 1;
    }

    console.header("Mesh Information: " + Platform::getFilename(meshFile));

    console.keyValue("Name", mesh.getName());
    console.keyValue("Nodes", std::to_string(mesh.getNodeCount()));
    console.keyValue("Elements", std::to_string(mesh.getElementCount()));
    console.keyValue("Parts", std::to_string(mesh.getPartCount()));

    // Bounding box
    auto [minBound, maxBound] = mesh.getBoundingBox();
    console.keyValue("Min bound", minBound.toString());
    console.keyValue("Max bound", maxBound.toString());

    Vector3D size = maxBound - minBound;
    console.keyValue("Size", size.toString());

    // Validation
    std::cout << "\n";
    console.info("Running validation...");
    auto result = Validator::validateMesh(mesh);

    if (result.isValid) {
        console.success("Mesh is valid");
    } else {
        console.error("Mesh has validation errors:");
        for (const auto& err : result.errors) {
            console.println("  - " + err, ConsoleOutput::Color::RED);
        }
    }

    for (const auto& warn : result.warnings) {
        console.warning(warn);
    }

    // Element quality check
    std::cout << "\n";
    console.info("Checking element quality...");
    double minJ = std::numeric_limits<double>::max();
    double maxJ = std::numeric_limits<double>::lowest();
    int negativeCount = 0;

    for (const auto& [id, elem] : mesh.getElements()) {
        double j = Validator::calculateJacobian(mesh, elem);
        if (j < minJ) minJ = j;
        if (j > maxJ) maxJ = j;
        if (j <= 0) negativeCount++;
    }

    console.header("Element Quality");
    console.keyValue("Min Jacobian", std::to_string(minJ));
    console.keyValue("Max Jacobian", std::to_string(maxJ));
    if (negativeCount > 0) {
        console.warning("Negative Jacobian elements: " + std::to_string(negativeCount));
    } else {
        console.success("All elements have positive Jacobian");
    }

    return 0;
}

/**
 * Generate variable density mesh from YAML config
 */
int runGenerateBox(const std::string& yamlFile, ConsoleOutput& console) {
    // Parse YAML
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    {
        size_t sp = yamlFile.find_last_of("/\\");
        if (sp != std::string::npos) configDir = yamlFile.substr(0, sp);
    }

    auto trim = [](const std::string& s) -> std::string {
        size_t a = s.find_first_not_of(" \t\r\n\"'");
        size_t b = s.find_last_not_of(" \t\r\n\"'");
        return (a == std::string::npos) ? "" : s.substr(a, b - a + 1);
    };
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (p.find('/') != std::string::npos || p.find('\\') != std::string::npos)
            return p;
        return configDir.empty() ? p : configDir + "/" + p;
    };

    // Parameters with defaults
    double lx = 100.0, ly = 20.0, lz = 20.0;
    int nx = 4, ny = 4, nz = 2;
    double rho = 7.85e-9, E = 210000.0, nu = 0.3;
    int mid = 1, secid = 1, pid = 1;
    std::string partTitle = "Box";
    std::string outputPath;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = trim(ln);
        if (tr.empty() || tr[0] == '#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = trim(tr.substr(cp + 1));

        if      (key == "output")     outputPath = resolvePath(val);
        else if (key == "lx")         { try { lx = std::stod(val); } catch (...) {} }
        else if (key == "ly")         { try { ly = std::stod(val); } catch (...) {} }
        else if (key == "lz")         { try { lz = std::stod(val); } catch (...) {} }
        else if (key == "nx")         { try { nx = std::stoi(val); } catch (...) {} }
        else if (key == "ny")         { try { ny = std::stoi(val); } catch (...) {} }
        else if (key == "nz")         { try { nz = std::stoi(val); } catch (...) {} }
        else if (key == "rho")        { try { rho = std::stod(val); } catch (...) {} }
        else if (key == "E")          { try { E   = std::stod(val); } catch (...) {} }
        else if (key == "nu")         { try { nu  = std::stod(val); } catch (...) {} }
        else if (key == "mid")        { try { mid   = std::stoi(val); } catch (...) {} }
        else if (key == "secid")      { try { secid = std::stoi(val); } catch (...) {} }
        else if (key == "pid")        { try { pid   = std::stoi(val); } catch (...) {} }
        else if (key == "part_title") partTitle = val;
    }
    f.close();

    if (outputPath.empty()) { console.error("[box] output not specified"); return 1; }
    if (nx < 1 || ny < 1 || nz < 1) { console.error("[box] nx/ny/nz must be >= 1"); return 1; }

    // Ensure .k extension
    if (outputPath.size() < 2 || outputPath.substr(outputPath.size() - 2) != ".k")
        outputPath += ".k";

    int npx = nx + 1, npy = ny + 1, npz = nz + 1;
    int nodeCount = npx * npy * npz;
    int elemCount = nx * ny * nz;

    // Node index: (ix, iy, iz) → NID (1-based)
    auto nid = [&](int ix, int iy, int iz) -> int {
        return iz * (npx * npy) + iy * npx + ix + 1;
    };

    std::ofstream out(outputPath);
    if (!out.is_open()) { console.error("[box] Cannot write: " + outputPath); return 1; }

    out << "*KEYWORD\n";
    out << "$\n$ Box mesh: " << lx << "x" << ly << "x" << lz
        << " mm, " << nx << "x" << ny << "x" << nz << " elements\n$\n";

    // MAT_ELASTIC
    char buf[128];
    out << "*MAT_ELASTIC\n";
    out << "$#     mid        ro         e        pr\n";
    snprintf(buf, sizeof(buf), "%10d%10.4g%10.4g%10.4g\n", mid, rho, E, nu);
    out << buf;

    // SECTION_SOLID
    out << "*SECTION_SOLID\n";
    out << "$#   secid    elform\n";
    snprintf(buf, sizeof(buf), "%10d%10d\n", secid, 1);
    out << buf;

    // PART
    out << "*PART\n";
    out << partTitle << "\n";
    out << "$#     pid     secid       mid\n";
    snprintf(buf, sizeof(buf), "%10d%10d%10d\n", pid, secid, mid);
    out << buf;

    // NODE
    out << "*NODE\n";
    out << "$#   nid               x               y               z\n";
    for (int iz = 0; iz < npz; ++iz) {
        double z = lz * iz / nz;
        for (int iy = 0; iy < npy; ++iy) {
            double y = ly * iy / ny;
            for (int ix = 0; ix < npx; ++ix) {
                double x = lx * ix / nx;
                snprintf(buf, sizeof(buf), "%8d%16.9e%16.9e%16.9e\n",
                         nid(ix, iy, iz), x, y, z);
                out << buf;
            }
        }
    }

    // ELEMENT_SOLID (HEX8)
    out << "*ELEMENT_SOLID\n";
    out << "$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8\n";
    int eid = 1;
    for (int iz = 0; iz < nz; ++iz) {
        for (int iy = 0; iy < ny; ++iy) {
            for (int ix = 0; ix < nx; ++ix) {
                // HEX8 node ordering: bottom face (CCW from outside) then top face
                int n1 = nid(ix,   iy,   iz);
                int n2 = nid(ix+1, iy,   iz);
                int n3 = nid(ix+1, iy+1, iz);
                int n4 = nid(ix,   iy+1, iz);
                int n5 = nid(ix,   iy,   iz+1);
                int n6 = nid(ix+1, iy,   iz+1);
                int n7 = nid(ix+1, iy+1, iz+1);
                int n8 = nid(ix,   iy+1, iz+1);
                snprintf(buf, sizeof(buf),
                         "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d\n",
                         eid++, pid, n1, n2, n3, n4, n5, n6, n7, n8);
                out << buf;
            }
        }
    }

    out << "*END\n";
    out.close();

    console.success("[box] " + std::to_string(nodeCount) + " nodes, "
                    + std::to_string(elemCount) + " elements → " + outputPath);
    return 0;
}

int runGenerateVar(const std::string& configFile, const std::string& outputFile,
                   const std::string& refFile, bool noScale,
                   const ConsoleOutput& console) {
    Timer timer;
    
    // Read YAML config (extended version)
    console.info("Reading configuration: " + configFile);
    YamlConfigReader yamlReader;
    ExtendedMeshConfig extConfig;
    try {
        extConfig = yamlReader.readExtendedFile(configFile);
    } catch (const std::exception& e) {
        console.error("Failed to read config: " + std::string(e.what()));
        return 1;
    }
    
    // Determine reference dimensions
    double refLengthI = 0, refLengthJ = 0, refLengthK = 0;
    
    if (!refFile.empty()) {
        // Load from command line reference file
        console.info("Loading reference mesh: " + refFile);
        KFileReader reader;
        try {
            Mesh refMesh = reader.readFile(refFile);
            auto [minB, maxB] = refMesh.getBoundingBox();
            refLengthI = maxB.x - minB.x;
            refLengthJ = maxB.y - minB.y;
            refLengthK = maxB.z - minB.z;
            console.success("Reference dimensions: " + 
                std::to_string(refLengthI) + " x " +
                std::to_string(refLengthJ) + " x " +
                std::to_string(refLengthK));
        } catch (const std::exception& e) {
            console.error("Failed to load reference: " + std::string(e.what()));
            return 1;
        }
    } else if (!extConfig.reference.flatMeshFile.empty() && !noScale) {
        // Load from config's reference file
        console.info("Loading reference mesh: " + extConfig.reference.flatMeshFile);
        KFileReader reader;
        try {
            Mesh refMesh = reader.readFile(extConfig.reference.flatMeshFile);
            auto [minB, maxB] = refMesh.getBoundingBox();
            refLengthI = maxB.x - minB.x;
            refLengthJ = maxB.y - minB.y;
            refLengthK = maxB.z - minB.z;
            console.success("Reference dimensions: " + 
                std::to_string(refLengthI) + " x " +
                std::to_string(refLengthJ) + " x " +
                std::to_string(refLengthK));
        } catch (const std::exception& e) {
            console.error("Failed to load reference: " + std::string(e.what()));
            return 1;
        }
    } else if (extConfig.reference.hasDimensions() && !noScale) {
        // Use config's direct dimensions
        refLengthI = extConfig.reference.lengthI;
        refLengthJ = extConfig.reference.lengthJ;
        refLengthK = extConfig.reference.lengthK;
        console.info("Using config dimensions: " + 
            std::to_string(refLengthI) + " x " +
            std::to_string(refLengthJ) + " x " +
            std::to_string(refLengthK));
    }
    
    Mesh mesh;
    
    // Handle based on mesh type
    if (extConfig.isCurved()) {
        // Curved mesh generation
        console.info("Generating curved mesh from centerline...");
        
        CurvedMeshConfig& curvedConfig = extConfig.curvedConfig;
        
        // Validate
        std::string validationError;
        if (!curvedConfig.validate(validationError)) {
            console.error("Invalid configuration: " + validationError);
            return 1;
        }
        
        console.success("Configuration loaded (CURVED)");
        console.keyValue("Centerline points", std::to_string(curvedConfig.centerlinePoints.size()));
        console.keyValue("Elements along curve", std::to_string(curvedConfig.elementsAlongCurve));
        console.keyValue("Elements J (width)", std::to_string(curvedConfig.elementsWidth));
        console.keyValue("Elements K (thickness)", std::to_string(curvedConfig.elementsThickness));
        console.keyValue("Total elements", std::to_string(curvedConfig.getTotalElements()));
        
        CurvedMeshGenerator generator;
        generator.setProgressCallback([&console](int percent) {
            console.progressBar(percent);
        });
        
        try {
            if (refLengthI > 0) {
                mesh = generator.generate(curvedConfig, refLengthI, refLengthJ, refLengthK);
            } else {
                mesh = generator.generate(curvedConfig);
            }
        } catch (const std::exception& e) {
            console.clearLine();
            console.error("Generation failed: " + std::string(e.what()));
            return 1;
        }
        console.clearLine();
        console.success("Generated " + std::to_string(mesh.getNodeCount()) + " nodes, " +
                       std::to_string(mesh.getElementCount()) + " elements");
        
        // Print curved mesh statistics
        const auto& stats = generator.getStats();
        std::cout << "\n";
        console.header("Curved Mesh Statistics");
        console.keyValue("Arc length", std::to_string(stats.arcLength));
        console.keyValue("Scale factor", std::to_string(stats.scaleFactor));
        console.keyValue("Width", std::to_string(stats.width));
        console.keyValue("Thickness", std::to_string(stats.thickness));
        console.keyValue("Max curvature", std::to_string(stats.maxCurvature));
        console.keyValue("Min radius", std::to_string(stats.minRadius));
        std::cout << "\n";
    } else {
        // Flat variable density mesh generation
        VariableDensityConfig& config = extConfig.flatConfig;
        
        // Validate config
        std::string validationError;
        if (!config.validate(validationError)) {
            console.error("Invalid configuration: " + validationError);
            return 1;
        }
        
        console.success("Configuration loaded (FLAT)");
        console.keyValue("Total I elements", std::to_string(config.getTotalElementsI()));
        console.keyValue("J elements", std::to_string(config.elementsJ));
        console.keyValue("K elements", std::to_string(config.elementsK));
        console.keyValue("Total elements", std::to_string(config.getTotalElements()));
        
        if (refLengthI <= 0 && !noScale) {
            // No reference - use zone lengths as-is
            refLengthI = config.getTotalLength();
            refLengthJ = 1.0;  // Default
            refLengthK = 1.0;  // Default
            console.info("No scaling - using zone lengths directly");
        }
        
        // Generate mesh
        console.info("Generating variable density mesh...");
        VariableDensityMeshGenerator generator;
        generator.setProgressCallback([&console](int percent) {
            console.progressBar(percent);
        });
        
        try {
            mesh = generator.generate(config, refLengthI, refLengthJ, refLengthK);
        } catch (const std::exception& e) {
            console.clearLine();
            console.error("Generation failed: " + std::string(e.what()));
            return 1;
        }
        console.clearLine();
        console.success("Generated " + std::to_string(mesh.getNodeCount()) + " nodes, " +
                       std::to_string(mesh.getElementCount()) + " elements");
        
        // Print statistics
        const auto& stats = generator.getStats();
        std::cout << "\n";
        console.header("Generation Statistics");
        console.keyValue("Scale factor", std::to_string(stats.scaleFactor));
        std::cout << "\n";
        console.println("Zone lengths (after scaling):");
        console.keyValue("  Zone 1 (Dense Start)", std::to_string(stats.zone1Length) + 
            " (" + std::to_string(config.zone1_denseStart.numElements) + " elements)");
        console.keyValue("  Zone 2 (Increasing)", std::to_string(stats.zone2Length) +
            " (" + std::to_string(config.zone2_increasing.numElements) + " elements)");
        console.keyValue("  Zone 3 (Sparse)", std::to_string(stats.zone3Length) +
            " (" + std::to_string(config.zone3_sparse.numElements) + " elements)");
        console.keyValue("  Zone 4 (Decreasing)", std::to_string(stats.zone4Length) +
            " (" + std::to_string(config.zone4_decreasing.numElements) + " elements)");
        console.keyValue("  Zone 5 (Dense End)", std::to_string(stats.zone5Length) +
            " (" + std::to_string(config.zone5_denseEnd.numElements) + " elements)");
        std::cout << "\n";
        console.keyValue("Total length I", std::to_string(stats.totalLengthI));
        console.keyValue("Length J", std::to_string(stats.totalLengthJ));
        console.keyValue("Length K", std::to_string(stats.totalLengthK));
        std::cout << "\n";
        console.keyValue("Dense element size", std::to_string(stats.denseElementSize));
        console.keyValue("Sparse element size", std::to_string(stats.sparseElementSize));
        console.keyValue("Size ratio", std::to_string(stats.sizeRatio) + ":1");
        std::cout << "\n";
    }
    
    // Write output
    console.info("Writing output: " + outputFile);
    KFileWriter writer;
    if (!writer.writeFile(outputFile, mesh)) {
        console.error("Failed to write output: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Output written successfully");
    
    timer.stop();
    console.info("Total time: " + timer.elapsedString());
    
    return 0;
}
