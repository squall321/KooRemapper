#pragma once

#include "core/Mesh.h"
#include "core/ShellMesh.h"
#include "mapper/ShellUnfolder.h"
#include "util/SpatialHash2D.h"
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/mapper]]

namespace KooRemapper {

/**
 * Shell-based mesh mapper
 *
 * Maps a flat detail mesh onto a bent shell surface.
 * Workflow:
 *   1. Unfold bent shell to flat 2D
 *   2. For each flat detail node, find containing flat shell element
 *   3. Compute local coordinates (xi, eta) in the flat element
 *   4. Interpolate bent position using same (xi, eta) on bent element
 *   5. Add thickness offset along shell normal
 */
class ShellMapper {
public:
    ShellMapper() = default;

    /**
     * Build mapping from bent shell mesh
     * @param bentShell Bent shell mesh (connectivity must be built)
     * @return true on success
     */
    bool build(const ShellMesh& bentShell);

    /**
     * Map a flat detail mesh to bent configuration
     * Auto-aligns flat detail bounding box to unfolded shell bounding box.
     * @param flatDetail Flat detail mesh (solid or shell)
     * @param resultMesh Output: mapped mesh
     * @param thickness Shell thickness for z-offset mapping
     * @return true on success
     */
    bool mapMesh(const Mesh& flatDetail, Mesh& resultMesh, double thickness) const;

    /**
     * Map a single flat point to bent position (uses alignment transform)
     * @param flatPoint Flat point (x, y in shell plane, z = thickness direction)
     * @param thickness Shell thickness
     * @return Bent 3D position
     */
    Vector3D mapPoint(const Vector3D& flatPoint, double thickness) const;

    // Whether axes were swapped during alignment
    bool isAxesSwapped() const { return axesSwapped_; }

    // Access unfolder results
    const ShellUnfolder& getUnfolder() const { return unfolder_; }

    // Diagnostics
    double getMaxDistortion() const { return unfolder_.getMaxDistortion(); }
    int getUnmappedCount() const { return unmappedCount_; }
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    const ShellMesh* bentShell_ = nullptr;
    ShellUnfolder unfolder_;
    SpatialHash2D spatialHash_;
    mutable std::string errorMessage_;
    mutable int unmappedCount_ = 0;

    // Alignment transform: flat detail XY → unfolded shell XY
    mutable bool alignmentComputed_ = false;
    mutable bool axesSwapped_ = false;     // true if flat X↔Y need swapping
    mutable double scaleX_ = 1.0, scaleY_ = 1.0;
    mutable double offsetX_ = 0.0, offsetY_ = 0.0;
    mutable double flatMinX_ = 0.0, flatMinY_ = 0.0;
    mutable double flatMaxX_ = 0.0, flatMaxY_ = 0.0;

    // Compute alignment transform from flat detail BB to unfolded shell BB
    void computeAlignment(const Mesh& flatDetail) const;

    // Transform flat detail (x,y) to unfolded shell coordinates
    void transformToUnfolded(double flatX, double flatY,
                             double& unfoldX, double& unfoldY) const;

    // Interpolate position on bent shell surface at (xi, eta)
    Vector3D interpolateOnBentSurface(int elemId, double xi, double eta) const;

    // Compute shell normal at (xi, eta) on element
    Vector3D computeNormal(int elemId, double xi, double eta) const;

    // QUAD4 shape functions
    static std::array<double, 4> shapeFunctions(double xi, double eta);
    static std::array<double, 4> shapeFunctionDerivsXi(double xi, double eta);
    static std::array<double, 4> shapeFunctionDerivsEta(double xi, double eta);
};

} // namespace KooRemapper
