#include "example/ExampleMeshGenerator.h"
#include <cmath>
#include <algorithm>

namespace KooRemapper {

namespace {
    constexpr double PI = 3.14159265358979323846;
    constexpr double DEG_TO_RAD = PI / 180.0;
    constexpr double EPSILON = 1e-10;
}

ExampleMeshGenerator::ExampleMeshGenerator()
    : customCenterline_(nullptr), customCrossSection_(nullptr)
{}

Mesh ExampleMeshGenerator::generateFlatMesh(const ExampleMeshConfig& config) {
    Mesh mesh;
    mesh.setName("flat_structured_mesh");
    double dy = config.lengthJ / config.dimJ;
    double dz = config.lengthK / config.dimK;
    int nodeId = config.startNodeId;
    int elemId = config.startElementId;

    for (int k = 0; k <= config.dimK; ++k) {
        for (int j = 0; j <= config.dimJ; ++j) {
            for (int i = 0; i <= config.dimI; ++i) {
                double t = static_cast<double>(i) / config.dimI;
                double x;

                // For WATERDROP, flat mesh X = cumulative arc-length along centerline
                // This matches the bent mesh edge interpolator's arc-length basis
                if (config.bentType == BentMeshType::WATERDROP) {
                    // Compute arc-length by integrating the centerline
                    // Use same t-remap as bent mesh, then compute actual arc-length
                    double flatRatio = config.waterdropFlatRatio;
                    double foldAngle = config.waterdropFoldAngle * DEG_TO_RAD;
                    double R = config.waterdropFoldRadius;
                    double flatLength = flatRatio * config.lengthI;
                    double arcLength = R * foldAngle;
                    double totalLength = 2.0 * flatLength + arcLength;

                    double targetCurveRatio = 0.5;
                    double targetFlatRatio = (1.0 - targetCurveRatio) / 2.0;

                    double s;
                    if (t <= targetFlatRatio) {
                        double localT = t / targetFlatRatio;
                        s = localT * flatLength;
                    } else if (t >= 1.0 - targetFlatRatio) {
                        double localT = (t - (1.0 - targetFlatRatio)) / targetFlatRatio;
                        s = flatLength + arcLength + localT * flatLength;
                    } else {
                        double localT = (t - targetFlatRatio) / targetCurveRatio;
                        s = flatLength + localT * arcLength;
                    }
                    // Scale s to match bent mesh edge arc-length (accounting for thickness)
                    // Bent edge is slightly longer due to k offset
                    x = s;
                } else {
                    x = t * config.lengthI;
                }

                double y = j * dy - config.lengthJ / 2.0;
                double z = k * dz - config.lengthK / 2.0;
                mesh.addNode(Node(nodeId++, x, y, z));
            }
        }
    }

    int nodesPerRow = config.dimI + 1;
    int nodesPerSlice = nodesPerRow * (config.dimJ + 1);

    for (int k = 0; k < config.dimK; ++k) {
        for (int j = 0; j < config.dimJ; ++j) {
            for (int i = 0; i < config.dimI; ++i) {
                int base = config.startNodeId + i + j * nodesPerRow + k * nodesPerSlice;
                std::array<int, 8> nodes = {
                    base, base + 1, base + 1 + nodesPerRow, base + nodesPerRow,
                    base + nodesPerSlice, base + 1 + nodesPerSlice,
                    base + 1 + nodesPerRow + nodesPerSlice, base + nodesPerRow + nodesPerSlice
                };
                Element elem(elemId++, config.partId, nodes);
                elem.i = i; elem.j = j; elem.k = k;
                elem.indexAssigned = true;
                mesh.addElement(elem);
            }
        }
    }

    Part part;
    part.id = config.partId;
    part.name = "flat_part";
    mesh.addPart(part);
    return mesh;
}

Mesh ExampleMeshGenerator::generateBentMesh(const ExampleMeshConfig& config) {
    Mesh mesh;
    mesh.setName("bent_structured_mesh");
    int nodeId = config.startNodeId;
    int elemId = config.startElementId;

    for (int k = 0; k <= config.dimK; ++k) {
        for (int j = 0; j <= config.dimJ; ++j) {
            for (int i = 0; i <= config.dimI; ++i) {
                Vector3D pos = computeBentPosition(i, j, k, config);
                mesh.addNode(Node(nodeId++, pos));
            }
        }
    }

    int nodesPerRow = config.dimI + 1;
    int nodesPerSlice = nodesPerRow * (config.dimJ + 1);

    for (int k = 0; k < config.dimK; ++k) {
        for (int j = 0; j < config.dimJ; ++j) {
            for (int i = 0; i < config.dimI; ++i) {
                int base = config.startNodeId + i + j * nodesPerRow + k * nodesPerSlice;
                std::array<int, 8> nodes = {
                    base, base + 1, base + 1 + nodesPerRow, base + nodesPerRow,
                    base + nodesPerSlice, base + 1 + nodesPerSlice,
                    base + 1 + nodesPerRow + nodesPerSlice, base + nodesPerRow + nodesPerSlice
                };
                Element elem(elemId++, config.partId, nodes);
                elem.i = i; elem.j = j; elem.k = k;
                elem.indexAssigned = true;
                mesh.addElement(elem);
            }
        }
    }

    Part part;
    part.id = config.partId;
    part.name = "bent_part";
    mesh.addPart(part);
    return mesh;
}

Mesh ExampleMeshGenerator::generateFlatUnstructuredMesh(const ExampleMeshConfig& config, int refineFactor) {
    ExampleMeshConfig refinedConfig = config;
    refinedConfig.dimI *= refineFactor;
    refinedConfig.dimJ *= refineFactor;
    refinedConfig.dimK *= refineFactor;
    Mesh mesh = generateFlatMesh(refinedConfig);
    mesh.setName("flat_unstructured_mesh");
    return mesh;
}

Mesh ExampleMeshGenerator::generateFlatTetMesh(const ExampleMeshConfig& config) {
    // First generate the hex mesh
    Mesh hexMesh = generateFlatMesh(config);

    Mesh tetMesh;
    tetMesh.setName("flat_tet_mesh");

    // Copy all nodes from hex mesh
    for (const auto& [nodeId, node] : hexMesh.getNodes()) {
        tetMesh.addNode(node);
    }

    // Convert each hex element to 5 tetrahedra
    // Standard decomposition maintaining positive volume
    int tetElemId = config.startElementId;

    for (const auto& [hexId, hex] : hexMesh.getElements()) {
        // Hex node indices (0-7)
        const auto& n = hex.nodeIds;

        // Split hex into 5 tets using the standard decomposition
        // This decomposition ensures consistent orientation across adjacent hexes
        // Tet 1: 0-1-3-4
        // Tet 2: 1-2-3-6
        // Tet 3: 1-4-5-6
        // Tet 4: 3-4-6-7
        // Tet 5: 1-3-4-6 (central tet connecting the others)

        std::array<std::array<int, 4>, 5> tetNodes = {{
            {n[0], n[1], n[3], n[4]},
            {n[1], n[2], n[3], n[6]},
            {n[1], n[4], n[5], n[6]},
            {n[3], n[4], n[6], n[7]},
            {n[1], n[3], n[4], n[6]}
        }};

        for (int t = 0; t < 5; ++t) {
            Element tet;
            tet.id = tetElemId++;
            tet.partId = config.partId;
            tet.type = ElementType::TET4;
            // Store in first 4 positions, rest are 0
            for (int i = 0; i < 4; ++i) {
                tet.nodeIds[i] = tetNodes[t][i];
            }
            for (int i = 4; i < 8; ++i) {
                tet.nodeIds[i] = 0;
            }
            tetMesh.addElement(tet);
        }
    }

    // Copy part info
    Part part;
    part.id = config.partId;
    part.name = "tet_part";
    tetMesh.addPart(part);

    return tetMesh;
}

Vector3D ExampleMeshGenerator::computeBentPosition(int i, int j, int k, const ExampleMeshConfig& config) {
    double t = static_cast<double>(i) / config.dimI;
    double localJ = static_cast<double>(j) / config.dimJ - 0.5;
    double localK = static_cast<double>(k) / config.dimK - 0.5;

    Vector3D center = getCenterlinePoint(t, config);
    auto [scaleJ, scaleK] = getCrossSectionScale(t, config);

    // WATERDROP: U-fold in XZ plane
    // Width direction (Y) is always fixed, thickness direction rotates with the fold
    if (config.bentType == BentMeshType::WATERDROP) {
        // Get tangent from centerline
        Vector3D tangent = getTangent(t, config);

        // Width direction is always Y (perpendicular to fold plane XZ)
        Vector3D widthDir(0, 1, 0);

        // Thickness direction is perpendicular to both tangent and width
        // This rotates with the fold while keeping width fixed
        Vector3D thicknessDir = tangent.cross(widthDir);
        if (thicknessDir.magnitude() > EPSILON) {
            thicknessDir.normalize();
        } else {
            thicknessDir = Vector3D(0, 0, 1);  // fallback
        }

        double offsetJ = localJ * config.lengthJ * scaleJ;
        double offsetK = localK * config.lengthK * scaleK;

        return center + widthDir * offsetJ + thicknessDir * offsetK;
    }

    // ARC, TORUS, BEND_TWIST: curves in XY plane
    // Flat mesh: X=i direction, Y=j direction (width), Z=k direction (thickness)
    // Bent mesh: tangent=i direction, Z=j direction (width, perpendicular to bend plane),
    //            in-plane normal=k direction (thickness, rotates with bend)
    if (config.bentType == BentMeshType::ARC ||
        config.bentType == BentMeshType::TORUS ||
        config.bentType == BentMeshType::BEND_TWIST) {
        Vector3D tangent = getTangent(t, config);

        // Width direction (J) is always Z (perpendicular to the XY bend plane)
        Vector3D widthDir(0, 0, 1);

        // Thickness direction (K) is perpendicular to tangent in XY plane
        // Use tangent x Z to get the in-plane normal pointing outward from arc center
        Vector3D thicknessDir = tangent.cross(widthDir);
        if (thicknessDir.magnitude() > EPSILON) {
            thicknessDir.normalize();
        } else {
            thicknessDir = Vector3D(0, 1, 0);  // fallback
        }

        double twistAngle = getTwistAngle(t, config);
        if (std::abs(twistAngle) > EPSILON) {
            double cosT = std::cos(twistAngle);
            double sinT = std::sin(twistAngle);
            double newLocalJ = localJ * cosT - localK * sinT;
            double newLocalK = localJ * sinT + localK * cosT;
            localJ = newLocalJ;
            localK = newLocalK;
        }

        double offsetJ = localJ * config.lengthJ * scaleJ;
        double offsetK = localK * config.lengthK * scaleK;
        return center + widthDir * offsetJ + thicknessDir * offsetK;
    }

    Vector3D tangent, normal, binormal;
    getFrenetFrame(t, config, tangent, normal, binormal);

    double twistAngle = getTwistAngle(t, config);
    if (std::abs(twistAngle) > EPSILON) {
        double cosT = std::cos(twistAngle);
        double sinT = std::sin(twistAngle);
        double newLocalJ = localJ * cosT - localK * sinT;
        double newLocalK = localJ * sinT + localK * cosT;
        localJ = newLocalJ;
        localK = newLocalK;
    }

    double offsetJ = localJ * config.lengthJ * scaleJ;
    double offsetK = localK * config.lengthK * scaleK;
    return center + binormal * offsetJ + normal * offsetK;
}

Vector3D ExampleMeshGenerator::getCenterlinePoint(double t, const ExampleMeshConfig& config) {
    switch (config.bentType) {
        case BentMeshType::TEARDROP: return teardropCenterline(t, config);
        case BentMeshType::ARC: return arcCenterline(t, config);
        case BentMeshType::S_CURVE: return sCurveCenterline(t, config);
        case BentMeshType::HELIX: return helixCenterline(t, config);
        case BentMeshType::TORUS: return torusCenterline(t, config);
        case BentMeshType::TWIST: return twistCenterline(t, config);
        case BentMeshType::BEND_TWIST: return bendTwistCenterline(t, config);
        case BentMeshType::WAVE: return waveCenterline(t, config);
        case BentMeshType::WATERDROP: return waterdropCenterline(t, config);
        case BentMeshType::BULGE:
        case BentMeshType::TAPER: return Vector3D(t * config.lengthI, 0, 0);
        case BentMeshType::CUSTOM:
            if (customCenterline_) return customCenterline_(t);
            [[fallthrough]];
        default: return Vector3D(t * config.lengthI, 0, 0);
    }
}

std::pair<double, double> ExampleMeshGenerator::getCrossSectionScale(double t, const ExampleMeshConfig& config) {
    switch (config.bentType) {
        case BentMeshType::TEARDROP: return teardropCrossSection(t, config);
        case BentMeshType::BULGE: return bulgeCrossSection(t, config);
        case BentMeshType::TAPER: return taperCrossSection(t, config);
        case BentMeshType::CUSTOM:
            if (customCrossSection_) return customCrossSection_(t);
            [[fallthrough]];
        default: return defaultCrossSection(t, config);
    }
}

Vector3D ExampleMeshGenerator::teardropCenterline(double t, const ExampleMeshConfig& config) {
    double length = config.teardropLength;
    double x = t * length;
    double bulge = 0.0;
    if (t > 0.0 && t < 1.0) {
        double peakT = 0.35;
        if (t < peakT) bulge = std::sin((t / peakT) * PI / 2);
        else bulge = std::cos(((t - peakT) / (1.0 - peakT)) * PI / 2);
        bulge *= config.teardropRadius * 0.3;
    }
    return Vector3D(x, bulge, 0);
}

Vector3D ExampleMeshGenerator::arcCenterline(double t, const ExampleMeshConfig& config) {
    double angleRad = config.arcAngle * DEG_TO_RAD;
    double theta = t * angleRad;
    return Vector3D(config.arcRadius * std::sin(theta), config.arcRadius * (1.0 - std::cos(theta)), 0);
}

Vector3D ExampleMeshGenerator::sCurveCenterline(double t, const ExampleMeshConfig& config) {
    return Vector3D(t * config.lengthI, config.sCurveAmplitude * std::sin(t * 2 * PI * config.sCurveFrequency), 0);
}

Vector3D ExampleMeshGenerator::helixCenterline(double t, const ExampleMeshConfig& config) {
    double angle = t * 2 * PI * (config.lengthI / config.helixPitch);
    return Vector3D(t * config.lengthI, config.helixRadius * std::cos(angle), config.helixRadius * std::sin(angle));
}

Vector3D ExampleMeshGenerator::torusCenterline(double t, const ExampleMeshConfig& config) {
    double theta = t * config.torusAngle * DEG_TO_RAD;
    return Vector3D(config.torusRadius * std::sin(theta), config.torusRadius * (1.0 - std::cos(theta)), 0);
}

Vector3D ExampleMeshGenerator::twistCenterline(double t, const ExampleMeshConfig& config) {
    return Vector3D(t * config.lengthI, 0, 0);
}

Vector3D ExampleMeshGenerator::bendTwistCenterline(double t, const ExampleMeshConfig& config) {
    double theta = t * config.arcAngle * DEG_TO_RAD;
    return Vector3D(config.arcRadius * std::sin(theta), config.arcRadius * (1.0 - std::cos(theta)), 0);
}

Vector3D ExampleMeshGenerator::waveCenterline(double t, const ExampleMeshConfig& config) {
    double phase = t * 2 * PI * config.waveFrequency;
    return Vector3D(t * config.lengthI, config.waveAmplitude * std::sin(phase), config.waveAmplitude * std::sin(phase + PI / 2));
}

Vector3D ExampleMeshGenerator::waterdropCenterline(double t, const ExampleMeshConfig& config) {
    // True U-fold geometry in XZ plane
    // With element concentration at the curved section
    double flatRatio = config.waterdropFlatRatio;
    double foldAngle = config.waterdropFoldAngle * DEG_TO_RAD;
    double R = config.waterdropFoldRadius;

    double flatLength = flatRatio * config.lengthI;
    double arcLength = R * foldAngle;
    double totalLength = 2.0 * flatLength + arcLength;

    // Remap t to concentrate elements at the curve
    // t1, t2 are the parameter boundaries for the curve section
    double t1 = flatLength / totalLength;
    double t2 = (flatLength + arcLength) / totalLength;
    double curveRatio = t2 - t1;  // fraction of t for curve

    // We want to use more of the t range for the curve
    // Target: curve gets 50% of elements (instead of ~10%)
    double targetCurveRatio = 0.5;
    double targetFlatRatio = (1.0 - targetCurveRatio) / 2.0;  // 25% each flat

    double s;
    if (t <= targetFlatRatio) {
        // First flat section: compress t range
        double localT = t / targetFlatRatio;  // 0 to 1
        s = localT * flatLength;
    } else if (t >= 1.0 - targetFlatRatio) {
        // Second flat section: compress t range
        double localT = (t - (1.0 - targetFlatRatio)) / targetFlatRatio;  // 0 to 1
        s = flatLength + arcLength + localT * flatLength;
    } else {
        // Curve section: expand t range
        double localT = (t - targetFlatRatio) / targetCurveRatio;  // 0 to 1
        s = flatLength + localT * arcLength;
    }

    double x, z;
    if (s <= flatLength) {
        x = s;
        z = 0.0;
    } else if (s >= flatLength + arcLength) {
        double localS = s - flatLength - arcLength;
        x = flatLength - localS;
        z = 2.0 * R;
    } else {
        double arcS = s - flatLength;
        double theta = arcS / R;
        x = flatLength + R * std::sin(theta);
        z = R - R * std::cos(theta);
    }

    return Vector3D(x, 0, z);
}

double ExampleMeshGenerator::getTwistAngle(double t, const ExampleMeshConfig& config) {
    if (config.bentType == BentMeshType::TWIST || config.bentType == BentMeshType::BEND_TWIST)
        return t * config.twistAngle * DEG_TO_RAD;
    return 0.0;
}

Vector3D ExampleMeshGenerator::getTangent(double t, const ExampleMeshConfig& config) {
    double dt = 0.001;
    Vector3D p1 = getCenterlinePoint(std::max(0.0, t - dt), config);
    Vector3D p2 = getCenterlinePoint(std::min(1.0, t + dt), config);
    Vector3D tangent = p2 - p1;
    return (tangent.magnitude() > EPSILON) ? tangent.normalized() : Vector3D(1, 0, 0);
}

void ExampleMeshGenerator::getFrenetFrame(double t, const ExampleMeshConfig& config,
                                          Vector3D& tangent, Vector3D& normal, Vector3D& binormal) {
    tangent = getTangent(t, config);
    double dt = 0.001;
    Vector3D tan1 = getTangent(std::max(0.0, t - dt), config);
    Vector3D tan2 = getTangent(std::min(1.0, t + dt), config);
    Vector3D curvature = tan2 - tan1;

    if (curvature.magnitude() > EPSILON) {
        normal = curvature.normalized();
        normal = normal - tangent * normal.dot(tangent);
        if (normal.magnitude() > EPSILON) normal.normalize();
        else normal = (std::abs(tangent.x) < 0.9) ? Vector3D(1,0,0).cross(tangent).normalized() : Vector3D(0,1,0).cross(tangent).normalized();
    } else {
        normal = (std::abs(tangent.x) < 0.9) ? Vector3D(1,0,0).cross(tangent).normalized() : Vector3D(0,1,0).cross(tangent).normalized();
    }

    // For arc-like shapes bending in XY plane (ARC, TORUS, BEND_TWIST),
    // ensure binormal points in +Z direction for proper right-hand orientation
    // This ensures positive Jacobian in the generated mesh
    binormal = tangent.cross(normal);
    if (binormal.magnitude() > EPSILON) {
        binormal.normalize();
        // Check if we need to flip the orientation for arc-type geometries
        // Arc curves in XY plane should have binormal pointing in +Z
        if (config.bentType == BentMeshType::ARC ||
            config.bentType == BentMeshType::TORUS ||
            config.bentType == BentMeshType::BEND_TWIST) {
            if (binormal.z < 0) {
                binormal = binormal * (-1.0);
                normal = normal * (-1.0);
            }
        }
    }
}

std::pair<double, double> ExampleMeshGenerator::teardropCrossSection(double t, const ExampleMeshConfig& config) {
    double scale = 1.0;
    if (t <= 0.1) scale = 1.0;
    else if (t <= 0.4) {
        double maxScale = 1.0 + (config.teardropRadius / config.lengthJ);
        scale = 1.0 + (maxScale - 1.0) * std::sin(((t - 0.1) / 0.3) * PI / 2);
    } else if (t <= 0.7) {
        double maxScale = 1.0 + (config.teardropRadius / config.lengthJ);
        scale = maxScale * (1.0 - 0.2 * ((t - 0.4) / 0.3));
    } else {
        double startScale = (1.0 + (config.teardropRadius / config.lengthJ)) * 0.8;
        scale = std::max(0.1, startScale * (1.0 - ((t - 0.7) / 0.3) * 0.9));
    }
    return {scale, scale};
}

std::pair<double, double> ExampleMeshGenerator::defaultCrossSection(double, const ExampleMeshConfig&) {
    return {1.0, 1.0};
}

std::pair<double, double> ExampleMeshGenerator::bulgeCrossSection(double t, const ExampleMeshConfig& config) {
    double dist = std::abs(t - config.bulgePosition);
    double halfWidth = config.bulgeWidth / 2.0;
    double scale = 1.0;
    if (dist < halfWidth) {
        scale = 1.0 + (config.bulgeFactor - 1.0) * (1.0 + std::cos((dist / halfWidth) * PI)) / 2.0;
    }
    return {scale, scale};
}

std::pair<double, double> ExampleMeshGenerator::taperCrossSection(double t, const ExampleMeshConfig& config) {
    double scale = 1.0 + (config.taperRatio - 1.0) * t;
    return {scale, scale};
}

} // namespace KooRemapper
