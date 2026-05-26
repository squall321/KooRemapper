#include "util/SpatialHash2D.h"
#include <cmath>
#include <algorithm>
#include <limits>

// Knowledge graph (lat.md):
//   @lat: [[modules/util]]

namespace KooRemapper {

void SpatialHash2D::build(const std::map<int, ShellElement>& elements,
                           const std::map<int, Vector2D>& flatPositions) {
    cells_.clear();
    elementData_.clear();

    if (elements.empty() || flatPositions.empty()) return;

    // Compute bounding box and average element size for cell sizing
    double minX = std::numeric_limits<double>::max();
    double minY = std::numeric_limits<double>::max();
    double maxX = std::numeric_limits<double>::lowest();
    double maxY = std::numeric_limits<double>::lowest();
    double totalEdgeLen = 0.0;
    int edgeCount = 0;

    for (const auto& [elemId, elem] : elements) {
        std::array<Vector2D, 4> verts;
        bool valid = true;
        for (int i = 0; i < 4; ++i) {
            auto it = flatPositions.find(elem.nodeIds[i]);
            if (it == flatPositions.end()) { valid = false; break; }
            verts[i] = it->second;

            minX = std::min(minX, it->second.x);
            minY = std::min(minY, it->second.y);
            maxX = std::max(maxX, it->second.x);
            maxY = std::max(maxY, it->second.y);
        }
        if (!valid) continue;

        // Store element data
        elementData_[elemId] = {elemId, verts};

        // Accumulate edge lengths for cell sizing
        for (int i = 0; i < 4; ++i) {
            int j = (i + 1) % 4;
            totalEdgeLen += verts[i].distanceTo(verts[j]);
            edgeCount++;
        }
    }

    if (elementData_.empty()) return;

    // Cell size = ~2x average edge length (good balance of occupancy vs. search)
    double avgEdge = totalEdgeLen / edgeCount;
    cellSize_ = avgEdge * 2.0;
    if (cellSize_ < 1e-10) cellSize_ = 1.0;

    originX_ = minX - cellSize_;
    originY_ = minY - cellSize_;

    // Insert elements into cells
    for (const auto& [elemId, data] : elementData_) {
        // Element bounding box
        double eMinX = data.vertices[0].x, eMaxX = data.vertices[0].x;
        double eMinY = data.vertices[0].y, eMaxY = data.vertices[0].y;
        for (int i = 1; i < 4; ++i) {
            eMinX = std::min(eMinX, data.vertices[i].x);
            eMaxX = std::max(eMaxX, data.vertices[i].x);
            eMinY = std::min(eMinY, data.vertices[i].y);
            eMaxY = std::max(eMaxY, data.vertices[i].y);
        }

        // Find cell range
        auto [cxMin, cyMin] = getCellIndex(eMinX, eMinY);
        auto [cxMax, cyMax] = getCellIndex(eMaxX, eMaxY);

        for (int cx = cxMin; cx <= cxMax; ++cx) {
            for (int cy = cyMin; cy <= cyMax; ++cy) {
                cells_[hashCell(cx, cy)].push_back(elemId);
            }
        }
    }
}

int SpatialHash2D::findContainingElement(double x, double y, double& xi, double& eta) const {
    auto candidates = getCandidateElements(x, y);

    for (int elemId : candidates) {
        auto it = elementData_.find(elemId);
        if (it == elementData_.end()) continue;

        if (computeLocalCoords(x, y, it->second.vertices, xi, eta)) {
            return elemId;
        }
    }

    // Not found in exact test - try with tolerance for boundary nodes
    for (int elemId : candidates) {
        auto it = elementData_.find(elemId);
        if (it == elementData_.end()) continue;

        if (isPointInQuad(x, y, it->second.vertices)) {
            // Force compute local coords even if slightly outside
            computeLocalCoords(x, y, it->second.vertices, xi, eta);
            // Clamp
            xi = std::max(-1.0, std::min(1.0, xi));
            eta = std::max(-1.0, std::min(1.0, eta));
            return elemId;
        }
    }

    return -1;
}

std::vector<int> SpatialHash2D::getCandidateElements(double x, double y) const {
    std::vector<int> result;

    // Check 3x3 neighborhood of cells for robustness
    auto [cx, cy] = getCellIndex(x, y);
    for (int dx = -1; dx <= 1; ++dx) {
        for (int dy = -1; dy <= 1; ++dy) {
            auto it = cells_.find(hashCell(cx + dx, cy + dy));
            if (it != cells_.end()) {
                for (int elemId : it->second) {
                    result.push_back(elemId);
                }
            }
        }
    }

    // Remove duplicates
    std::sort(result.begin(), result.end());
    result.erase(std::unique(result.begin(), result.end()), result.end());

    return result;
}

bool SpatialHash2D::isPointInQuad(double x, double y,
                                   const std::array<Vector2D, 4>& verts) const {
    // Cross product test: point is inside if all cross products have the same sign
    // when traversing edges CCW (or all CW)
    int positiveCount = 0;
    int negativeCount = 0;

    for (int i = 0; i < 4; ++i) {
        int j = (i + 1) % 4;
        double ex = verts[j].x - verts[i].x;
        double ey = verts[j].y - verts[i].y;
        double px = x - verts[i].x;
        double py = y - verts[i].y;
        double cross = ex * py - ey * px;

        if (cross > 1e-12) positiveCount++;
        else if (cross < -1e-12) negativeCount++;
        // cross ≈ 0 means on edge, count as inside
    }

    // Inside if all same sign (or on edge)
    return (positiveCount == 0 || negativeCount == 0);
}

bool SpatialHash2D::computeLocalCoords(double x, double y,
                                        const std::array<Vector2D, 4>& verts,
                                        double& xi, double& eta) const {
    // Newton-Raphson to solve: P = sum_i N_i(xi,eta) * v_i for (xi, eta)
    // N_0 = 0.25*(1-xi)*(1-eta), N_1 = 0.25*(1+xi)*(1-eta)
    // N_2 = 0.25*(1+xi)*(1+eta), N_3 = 0.25*(1-xi)*(1+eta)

    xi = 0.0;
    eta = 0.0;

    for (int iter = 0; iter < 20; ++iter) {
        auto N = shapeFunctions(xi, eta);

        // Current mapped position
        double fx = 0.0, fy = 0.0;
        for (int i = 0; i < 4; ++i) {
            fx += N[i] * verts[i].x;
            fy += N[i] * verts[i].y;
        }

        double dx = x - fx;
        double dy = y - fy;

        if (std::abs(dx) < 1e-12 && std::abs(dy) < 1e-12) {
            return (std::abs(xi) <= 1.0 + 1e-6 && std::abs(eta) <= 1.0 + 1e-6);
        }

        // Jacobian: J = [dF/dxi, dF/deta]
        // dN/dxi: [-0.25*(1-eta), 0.25*(1-eta), 0.25*(1+eta), -0.25*(1+eta)]
        // dN/deta: [-0.25*(1-xi), -0.25*(1+xi), 0.25*(1+xi), 0.25*(1-xi)]
        double dNdxi[4] = {
            -0.25 * (1.0 - eta),
             0.25 * (1.0 - eta),
             0.25 * (1.0 + eta),
            -0.25 * (1.0 + eta)
        };
        double dNdeta[4] = {
            -0.25 * (1.0 - xi),
            -0.25 * (1.0 + xi),
             0.25 * (1.0 + xi),
             0.25 * (1.0 - xi)
        };

        double j11 = 0.0, j12 = 0.0, j21 = 0.0, j22 = 0.0;
        for (int i = 0; i < 4; ++i) {
            j11 += dNdxi[i] * verts[i].x;
            j12 += dNdeta[i] * verts[i].x;
            j21 += dNdxi[i] * verts[i].y;
            j22 += dNdeta[i] * verts[i].y;
        }

        double det = j11 * j22 - j12 * j21;
        if (std::abs(det) < 1e-20) return false;

        double invDet = 1.0 / det;
        double dxi  = invDet * ( j22 * dx - j12 * dy);
        double deta = invDet * (-j21 * dx + j11 * dy);

        xi += dxi;
        eta += deta;

        if (std::abs(dxi) < 1e-12 && std::abs(deta) < 1e-12) {
            return (std::abs(xi) <= 1.0 + 1e-6 && std::abs(eta) <= 1.0 + 1e-6);
        }
    }

    // Check if converged within tolerance
    return (std::abs(xi) <= 1.0 + 1e-6 && std::abs(eta) <= 1.0 + 1e-6);
}

std::array<double, 4> SpatialHash2D::shapeFunctions(double xi, double eta) {
    return {
        0.25 * (1.0 - xi) * (1.0 - eta),
        0.25 * (1.0 + xi) * (1.0 - eta),
        0.25 * (1.0 + xi) * (1.0 + eta),
        0.25 * (1.0 - xi) * (1.0 + eta)
    };
}

} // namespace KooRemapper
