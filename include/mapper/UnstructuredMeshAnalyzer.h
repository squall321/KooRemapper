#pragma once

#include "core/Mesh.h"
#include "core/Vector3D.h"

namespace KooRemapper {

/**
 * Analyzes an unstructured mesh for mapping purposes
 */
class UnstructuredMeshAnalyzer {
public:
    UnstructuredMeshAnalyzer();
    ~UnstructuredMeshAnalyzer() = default;

    /**
     * Analyze the mesh
     */
    void analyze(const Mesh& mesh);

    /**
     * Get bounding box
     */
    const Vector3D& getBoundingBoxMin() const { return bbMin_; }
    const Vector3D& getBoundingBoxMax() const { return bbMax_; }
    const Vector3D& getDimensions() const { return dimensions_; }

    /**
     * Normalize a coordinate to [0,1] range based on bounding box
     */
    Vector3D normalize(const Vector3D& pos) const;

    /**
     * Get scale factor to match another mesh's bounding box
     */
    Vector3D getScaleFactor(const UnstructuredMeshAnalyzer& other) const;

    /**
     * Calculate scale to match a target size
     */
    Vector3D getScaleToSize(double targetX, double targetY, double targetZ) const;

private:
    Vector3D bbMin_, bbMax_;
    Vector3D dimensions_;
    Vector3D center_;
};

} // namespace KooRemapper
