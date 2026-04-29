#include "remesh/TetGenRemesher.h"

// =============================================================================
// Phase B backend body. When KOOREMAPPER_BUILD_TETGEN is defined, this file
// compiles against third_party/tetgen and translates RemeshTask <-> tetgenio.
// Otherwise it ships as a stub that reports "not built" so the orchestrator
// can fall back to LocalImproveRemesher transparently.
// =============================================================================

#ifdef KOOREMAPPER_BUILD_TETGEN

// TetGen needs TETLIBRARY defined before its header is included so it
// builds as a library (no main()).
#ifndef TETLIBRARY
#define TETLIBRARY
#endif
#include "tetgen.h"

#include <algorithm>
#include <cstring>
#include <cmath>
#include <sstream>

namespace KooRemapper {
namespace remesh {

namespace {

double tetSignedVol(const Vector3D& p0, const Vector3D& p1,
                    const Vector3D& p2, const Vector3D& p3) {
    Vector3D e1 = p1 - p0;
    Vector3D e2 = p2 - p0;
    Vector3D e3 = p3 - p0;
    return e1.dot(e2.cross(e3)) / 6.0;
}

double tetScaledJac(const std::vector<PatchNode>& nodes, const PatchTet& t) {
    static const double EQ_NORM = 0.11785113019775793;  // sqrt(2)/12
    double V = tetSignedVol(nodes[t.n[0]].position, nodes[t.n[1]].position,
                             nodes[t.n[2]].position, nodes[t.n[3]].position);
    double e01 = (nodes[t.n[1]].position - nodes[t.n[0]].position).magnitude();
    double e02 = (nodes[t.n[2]].position - nodes[t.n[0]].position).magnitude();
    double e03 = (nodes[t.n[3]].position - nodes[t.n[0]].position).magnitude();
    double e12 = (nodes[t.n[2]].position - nodes[t.n[1]].position).magnitude();
    double e13 = (nodes[t.n[3]].position - nodes[t.n[1]].position).magnitude();
    double e23 = (nodes[t.n[3]].position - nodes[t.n[2]].position).magnitude();
    double maxE = std::max({e01, e02, e03, e12, e13, e23});
    if (maxE < 1e-12) return 0.0;
    return (V / (maxE * maxE * maxE)) / EQ_NORM;
}

// Free TetGen-allocated arrays inside a facet.
void freeFacet(tetgenio::facet& f) {
    if (f.polygonlist) {
        for (int i = 0; i < f.numberofpolygons; ++i) {
            delete[] f.polygonlist[i].vertexlist;
        }
        delete[] f.polygonlist;
    }
    if (f.holelist) delete[] f.holelist;
}

}  // namespace

RemeshResult TetGenRemesher::run(const RemeshTask& task) {
    RemeshResult result;
    result.nodes = task.nodes;            // initial state in case of early-out
    result.tets  = task.originalTets;

    // Initial quality (before)
    {
        double mn = std::numeric_limits<double>::max();
        for (const auto& t : task.originalTets) {
            mn = std::min(mn, tetScaledJac(task.nodes, t));
        }
        result.minJacBefore = (mn == std::numeric_limits<double>::max()) ? 0.0 : mn;
    }

    if (task.nodes.empty() || task.boundaryTris.empty()) {
        result.success = false;
        result.message = "TetGen: empty patch (no nodes or no boundary)";
        return result;
    }

    // -------------------------------------------------------------------
    // 1. Build tetgenio input.
    // -------------------------------------------------------------------
    tetgenio in;
    in.firstnumber       = 0;
    in.mesh_dim          = 3;
    in.numberofpoints    = (int)task.nodes.size();
    in.pointlist         = new REAL[3 * in.numberofpoints];
    in.pointmarkerlist   = new int[in.numberofpoints];
    for (int i = 0; i < in.numberofpoints; ++i) {
        in.pointlist[3 * i + 0] = task.nodes[i].position.x;
        in.pointlist[3 * i + 1] = task.nodes[i].position.y;
        in.pointlist[3 * i + 2] = task.nodes[i].position.z;
        // marker convention here:
        //   1 = fixed boundary node (must NOT move; will use -Y to enforce)
        //   2 = free flat-surface boundary (movable in tangent plane; treated
        //       as fixed for now, see B+ TODO below)
        //   0 = interior (not on input boundary; TetGen may relocate freely)
        in.pointmarkerlist[i] = task.nodes[i].isFixed ? 1 : 2;
    }

    // 2. Boundary facets (each PatchTri -> 1 facet with 1 polygon of 3 verts).
    in.numberoffacets   = (int)task.boundaryTris.size();
    in.facetlist        = new tetgenio::facet[in.numberoffacets];
    in.facetmarkerlist  = new int[in.numberoffacets];
    for (int f = 0; f < in.numberoffacets; ++f) {
        tetgenio::facet& fac = in.facetlist[f];
        fac.numberofpolygons = 1;
        fac.polygonlist      = new tetgenio::polygon[1];
        fac.polygonlist[0].numberofvertices = 3;
        fac.polygonlist[0].vertexlist = new int[3];
        fac.polygonlist[0].vertexlist[0] = task.boundaryTris[f].n[0];
        fac.polygonlist[0].vertexlist[1] = task.boundaryTris[f].n[1];
        fac.polygonlist[0].vertexlist[2] = task.boundaryTris[f].n[2];
        fac.numberofholes = 0;
        fac.holelist      = nullptr;
        in.facetmarkerlist[f] = 1;
    }

    // -------------------------------------------------------------------
    // 3. Configure behavior.
    //   p     : tetrahedralize a piecewise linear complex (PSLG)
    //   q<r>  : quality refinement, radius/edge ratio bound
    //   Y     : preserve boundary mesh (no Steiner on input facets)
    //         FREE flat-surface nodes lose tangential motion under -Y; this
    //         is acceptable for first integration. A future iteration may
    //         emit those facets without -Y per-facet (TetGen 1.6 supports
    //         per-facet markers we can use to relax this).
    //   B     : suppress boundary markers in output (keeps input ones)
    //   Q     : quiet
    // -------------------------------------------------------------------
    tetgenbehavior beh;
    char switches[64];
    {
        std::snprintf(switches, sizeof(switches), "pq%.2fYBQ",
                      task.tetgenQualityRatio > 0 ? task.tetgenQualityRatio : 1.4);
    }
    if (!beh.parse_commandline(switches)) {
        result.success = false;
        result.message = std::string("TetGen: failed to parse switches: ") + switches;
        return result;
    }

    // -------------------------------------------------------------------
    // 4. Call tetrahedralize. TetGen 1.6 throws std::runtime_error on
    //    failure (see tetgen.cxx). Catch and report cleanly.
    // -------------------------------------------------------------------
    // DEBUG (KOO_TETGEN_DEBUG=1): dump per-patch input size before the call
    // so we can see whether the crash happens before/after tetrahedralize.
    {
        const char* dbg = std::getenv("KOO_TETGEN_DEBUG");
        if (dbg && std::string(dbg) != "0") {
            std::fprintf(stderr,
                "[KOO_TETGEN_DEBUG] -> tetrahedralize(switches=%s, npts=%d, nfacets=%d)\n",
                switches, in.numberofpoints, in.numberoffacets);
            std::fflush(stderr);
        }
    }
    // tetgenio's destructor frees pointlist/facetlist/markerlist that we
    // allocated above (see ~tetgenio in tetgen.h). Do NOT delete them
    // manually -- that would be a double free and the process would abort.
    tetgenio out;
    try {
        tetrahedralize(&beh, &in, &out);
    } catch (int code) {
        // TetGen 1.6 throws an int exit code under TETLIBRARY (see
        // terminatetetgen() in tetgen.h). Decode common ones for clarity.
        result.success = false;
        const char* what = "unknown";
        switch (code) {
            case 1:   what = "out of memory"; break;
            case 2:   what = "internal error"; break;
            case 3:   what = "boundary self-intersection"; break;
            case 4:   what = "input feature size too small"; break;
            case 5:   what = "two boundary facets too close"; break;
            case 10:  what = "input error"; break;
            case 200: what = "boundary requires Steiner points (-YY)"; break;
        }
        std::ostringstream m;
        m << "TetGen: tetrahedralize() failed (code=" << code << ": " << what
          << "; switches: " << switches << ")";
        result.message = m.str();
        return result;
    } catch (const std::exception& ex) {
        result.success = false;
        std::ostringstream m;
        m << "TetGen: tetrahedralize() threw std::exception: " << ex.what()
          << " (switches: " << switches << ")";
        result.message = m.str();
        return result;
    } catch (...) {
        result.success = false;
        result.message = "TetGen: tetrahedralize() threw unknown exception type";
        return result;
    }

    // -------------------------------------------------------------------
    // 5. Translate output back. Under -Y the first numberofpoints input
    //    points are preserved with their indices; Steiner points are
    //    appended in [task.nodes.size(), out.numberofpoints).
    // -------------------------------------------------------------------
    result.nodes.resize((size_t)out.numberofpoints);
    for (int i = 0; i < out.numberofpoints; ++i) {
        if (i < (int)task.nodes.size()) {
            // preserve input record (isFixed flags etc) but update position
            // in case TetGen moved it (under -Y it shouldn't, but be safe).
            result.nodes[i] = task.nodes[i];
        } else {
            PatchNode pn;
            pn.isFixed       = false;
            pn.tangentNormal = Vector3D();
            pn.moveTolerance = 0.0;
            result.nodes[i]  = pn;
        }
        result.nodes[i].position = Vector3D(out.pointlist[3 * i + 0],
                                            out.pointlist[3 * i + 1],
                                            out.pointlist[3 * i + 2]);
    }

    // 6. New tets (TetGen output is corner-indexed by 0-based vertex IDs).
    //    Defensively check signed volume; flip a vertex pair if negative
    //    so LS-DYNA TET4 sign convention holds.
    result.tets.clear();
    result.tets.reserve((size_t)out.numberoftetrahedra);
    int corners = (out.numberofcorners > 0) ? out.numberofcorners : 4;
    for (int t = 0; t < out.numberoftetrahedra; ++t) {
        PatchTet pt;
        pt.n[0] = out.tetrahedronlist[corners * t + 0];
        pt.n[1] = out.tetrahedronlist[corners * t + 1];
        pt.n[2] = out.tetrahedronlist[corners * t + 2];
        pt.n[3] = out.tetrahedronlist[corners * t + 3];
        double V = tetSignedVol(result.nodes[pt.n[0]].position,
                                result.nodes[pt.n[1]].position,
                                result.nodes[pt.n[2]].position,
                                result.nodes[pt.n[3]].position);
        if (V < 0.0) std::swap(pt.n[1], pt.n[2]);
        result.tets.push_back(pt);
    }

    // 7. Final quality.
    double mn = std::numeric_limits<double>::max();
    for (const auto& t : result.tets) mn = std::min(mn, tetScaledJac(result.nodes, t));
    result.minJacAfter = (mn == std::numeric_limits<double>::max()) ? 0.0 : mn;

    result.newNodeCount = (int)result.nodes.size() - (int)task.nodes.size();
    result.success = true;

    std::ostringstream msg;
    msg << "TetGen: tets " << task.originalTets.size()
        << " -> " << result.tets.size()
        << ", new nodes=" << result.newNodeCount
        << ", scaledJac " << result.minJacBefore
        << " -> " << result.minJacAfter
        << " (switches: " << switches << ")";
    result.message = msg.str();

    // tetgenio destructors free both `in` and `out` arrays automatically.
    return result;
}

}  // namespace remesh
}  // namespace KooRemapper

#else  // KOOREMAPPER_BUILD_TETGEN not defined -- stub

#include <sstream>

namespace KooRemapper {
namespace remesh {

RemeshResult TetGenRemesher::run(const RemeshTask& task) {
    (void)task;
    RemeshResult r;
    r.success = false;
    r.message = "TetGenRemesher not built. Rebuild with "
                "-DKOOREMAPPER_BUILD_TETGEN=ON (note: TetGen is AGPL v3). "
                "Falling back to LocalImproveRemesher is the orchestrator's "
                "responsibility.";
    return r;
}

}  // namespace remesh
}  // namespace KooRemapper

#endif
