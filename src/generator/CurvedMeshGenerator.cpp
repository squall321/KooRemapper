#include "generator/CurvedMeshGenerator.h"
#include <cmath>
#include <stdexcept>
#include <limits>

namespace KooRemapper {

CurvedMeshGenerator::CurvedMeshGenerator()
    : progressCallback_(nullptr)
{}

Mesh CurvedMeshGenerator::generate(const CurvedMeshConfig& config) {
    // No reference - use config values directly
    return generate(config, 0, config.width, config.thickness);
}

Mesh CurvedMeshGenerator::generate(
    const CurvedMeshConfig& config,
    double refArcLength, double refWidth, double refThickness)
{
    // Validate config
    std::string error;
    if (!config.validate(error)) {
        errorMessage_ = error;
        throw std::runtime_error(error);
    }
    
    reportProgress(5);
    
    // Setup curve interpolator
    curve_.setControlPoints(config.centerlinePoints);
    curve_.setInterpolationType(config.interpolation);
    
    double originalArcLength = curve_.getArcLength();
    
    // Determine scale factor and dimensions
    double scaleFactor = 1.0;
    double width = config.width;
    double thickness = config.thickness;
    
    if (refArcLength > 0) {
        // Scale curve to match reference arc length
        scaleFactor = refArcLength / originalArcLength;
        curve_.scale(scaleFactor);
    }
    
    if (refWidth > 0) {
        width = refWidth;
    }
    if (refThickness > 0) {
        thickness = refThickness;
    }
    
    reportProgress(10);
    
    // Analyze curve
    analyzeCurve();
    
    // Store stats
    stats_.arcLength = curve_.getArcLength();
    stats_.scaleFactor = scaleFactor;
    stats_.width = width;
    stats_.thickness = thickness;
    stats_.totalElements = config.getTotalElements();
    
    reportProgress(15);
    
    // Generate mesh
    Mesh mesh;
    
    int ni = config.elementsAlongCurve + 1;  // Nodes along curve
    int nj = config.elementsWidth + 1;        // Nodes in width direction
    int nk = config.elementsThickness + 1;    // Nodes in thickness direction
    
    // Precompute positions along curve (arc length parameterized)
    std::vector<Vector2D> curvePositions(ni);
    std::vector<Vector2D> curveTangents(ni);
    std::vector<Vector2D> curveNormals(ni);
    
    for (int i = 0; i < ni; ++i) {
        double s = (static_cast<double>(i) / (ni - 1)) * stats_.arcLength;
        curvePositions[i] = curve_.evaluateAtArcLength(s);
        curveTangents[i] = curve_.evaluateTangentAtArcLength(s).normalized();
        curveNormals[i] = curveTangents[i].perpendicular();
    }
    
    reportProgress(20);
    
    // Create nodes
    // Standard structured grid ordering: K -> J -> I (outer to inner)
    // This matches the expected ordering for the mapper
    // Coordinate system at each curve point:
    // - X: curve position X + normal * thickness offset
    // - Y: width direction (out of plane)
    // - Z: curve position Y + normal * thickness offset (curve Y becomes Z)
    
    int nodeId = 1;
    for (int k = 0; k < nk; ++k) {
        // Thickness offset (centered)
        double thicknessRatio = static_cast<double>(k) / (nk - 1) - 0.5;
        double thicknessOffset = thicknessRatio * thickness;
        
        for (int j = 0; j < nj; ++j) {
            // Width offset (centered)
            double widthRatio = static_cast<double>(j) / (nj - 1) - 0.5;
            double y = widthRatio * width;
            
            for (int i = 0; i < ni; ++i) {
                const Vector2D& pos = curvePositions[i];
                const Vector2D& normal = curveNormals[i];
                
                // Position along normal direction
                double x = pos.x + normal.x * thicknessOffset;
                double z = pos.y + normal.y * thicknessOffset;
                
                mesh.addNode(nodeId++, x, y, z);
            }
        }
        
        if (progressCallback_ && k % 2 == 0) {
            int progress = 20 + (50 * k / nk);
            reportProgress(progress);
        }
    }
    
    reportProgress(70);
    
    // Create elements
    // Node numbering: node(i,j,k) = 1 + i + j*ni + k*ni*nj
    int elemId = 1;
    for (int k = 0; k < config.elementsThickness; ++k) {
        for (int j = 0; j < config.elementsWidth; ++j) {
            for (int i = 0; i < config.elementsAlongCurve; ++i) {
                // HEX8 node indices (LS-DYNA convention)
                // Face at i: nodes n1-n4
                // Face at i+1: nodes n5-n8
                
                auto nodeIndex = [ni, nj](int ii, int jj, int kk) {
                    return 1 + ii + jj * ni + kk * ni * nj;
                };
                
                // HEX8 node ordering (same as ExampleMeshGenerator):
                // n1-n4: face at i=current, n5-n8: face at i=next
                // Within each face: counter-clockwise when viewed from outside
                int n1 = nodeIndex(i, j, k);         // (i, j, k)
                int n2 = nodeIndex(i + 1, j, k);     // (i+1, j, k)
                int n3 = nodeIndex(i + 1, j + 1, k); // (i+1, j+1, k)
                int n4 = nodeIndex(i, j + 1, k);     // (i, j+1, k)
                int n5 = nodeIndex(i, j, k + 1);     // (i, j, k+1)
                int n6 = nodeIndex(i + 1, j, k + 1); // (i+1, j, k+1)
                int n7 = nodeIndex(i + 1, j + 1, k + 1); // (i+1, j+1, k+1)
                int n8 = nodeIndex(i, j + 1, k + 1); // (i, j+1, k+1)
                
                std::array<int, 8> nodeIds = {n1, n2, n3, n4, n5, n6, n7, n8};
                Element elem(elemId++, 1, nodeIds);
                // Set grid indices explicitly for StructuredGridIndexer
                elem.i = i;
                elem.j = j;
                elem.k = k;
                elem.indexAssigned = true;
                mesh.addElement(elem);
            }
        }
        
        if (progressCallback_) {
            int progress = 70 + (25 * k / config.elementsThickness);
            reportProgress(progress);
        }
    }
    
    stats_.totalNodes = static_cast<int>(mesh.getNodeCount());
    
    // Set grid dimensions
    mesh.setGridDimensions(config.elementsAlongCurve, 
                           config.elementsWidth, 
                           config.elementsThickness);
    
    // Add part
    Part part;
    part.id = 1;
    part.name = "curved_mesh_part";
    mesh.addPart(part);
    
    reportProgress(100);
    
    return mesh;
}

double CurvedMeshGenerator::computeCurvature(double t) const {
    // Curvature = |x'y'' - y'x''| / (x'^2 + y'^2)^(3/2)
    // For simplicity, use numerical differentiation
    
    const double h = 0.001;
    double t0 = std::max(0.0, t - h);
    double t1 = std::min(1.0, t + h);
    
    Vector2D p0 = curve_.evaluate(t0);
    Vector2D p1 = curve_.evaluate(t);
    Vector2D p2 = curve_.evaluate(t1);
    
    // First derivative (central difference)
    Vector2D dp = (p2 - p0) / (t1 - t0);
    
    // Second derivative
    Vector2D d2p = (p2 - p1 * 2 + p0) / ((t1 - t) * (t - t0));
    
    // Curvature formula
    double cross = dp.x * d2p.y - dp.y * d2p.x;
    double lenCubed = std::pow(dp.lengthSquared(), 1.5);
    
    if (lenCubed < 1e-10) return 0;
    
    return std::abs(cross) / lenCubed;
}

void CurvedMeshGenerator::analyzeCurve() {
    stats_.maxCurvature = 0;
    stats_.curvatureAtMax = 0;
    stats_.minRadius = std::numeric_limits<double>::max();
    
    const int samples = 100;
    for (int i = 0; i <= samples; ++i) {
        double t = static_cast<double>(i) / samples;
        double curvature = computeCurvature(t);
        
        if (curvature > stats_.maxCurvature) {
            stats_.maxCurvature = curvature;
            stats_.curvatureAtMax = t;
        }
    }
    
    if (stats_.maxCurvature > 1e-10) {
        stats_.minRadius = 1.0 / stats_.maxCurvature;
    }
}

void CurvedMeshGenerator::reportProgress(int percent) {
    if (progressCallback_) {
        progressCallback_(percent);
    }
}

} // namespace KooRemapper
