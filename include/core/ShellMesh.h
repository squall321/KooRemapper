#pragma once

#include "core/Node.h"
#include "core/ShellElement.h"
#include "core/Vector3D.h"
#include <map>
#include <vector>
#include <string>
#include <utility>

namespace KooRemapper {

/**
 * Shell mesh container for QUAD4 shell elements
 *
 * Provides element adjacency via shared edges and
 * geometric queries (normals, centroids).
 */
class ShellMesh {
public:
    ShellMesh() = default;

    // Node operations
    void addNode(const Node& node) { nodes_[node.id] = node; }
    void addNode(int id, double x, double y, double z) { nodes_[id] = Node(id, x, y, z); }

    const Node* getNode(int id) const {
        auto it = nodes_.find(id);
        return (it != nodes_.end()) ? &it->second : nullptr;
    }

    bool hasNode(int id) const { return nodes_.find(id) != nodes_.end(); }
    size_t getNodeCount() const { return nodes_.size(); }
    const std::map<int, Node>& getNodes() const { return nodes_; }

    // Element operations
    void addElement(const ShellElement& elem) { elements_[elem.id] = elem; }
    void addElement(int id, int partId, const std::array<int, 4>& nodeIds) {
        elements_[id] = ShellElement(id, partId, nodeIds);
    }

    const ShellElement* getElement(int id) const {
        auto it = elements_.find(id);
        return (it != elements_.end()) ? &it->second : nullptr;
    }

    bool hasElement(int id) const { return elements_.find(id) != elements_.end(); }
    size_t getElementCount() const { return elements_.size(); }
    const std::map<int, ShellElement>& getElements() const { return elements_; }

    // Build adjacency information (must be called after adding all elements)
    void buildConnectivity();

    // Get neighbor element IDs sharing an edge with the given element
    std::vector<int> getNeighbors(int elemId) const;

    // Get the element on the other side of a shared edge
    // Returns -1 if no neighbor on that edge
    int getNeighborAcrossEdge(int elemId, int edgeIdx) const;

    // Get element normal (average of triangle normals)
    Vector3D getElementNormal(int elemId) const;

    // Get element centroid
    Vector3D getElementCentroid(int elemId) const;

    // Get element area in 3D
    double getElementArea(int elemId) const;

    // Get node-averaged normal (area-weighted average of adjacent element normals)
    Vector3D getNodeNormal(int nodeId) const;

    // Get boundary elements (elements with < 4 neighbors)
    std::vector<int> getBoundaryElements() const;

    // Validate: all element nodes exist
    bool validate(std::string& errorMessage) const;

    void clear() {
        nodes_.clear();
        elements_.clear();
        edgeToElements_.clear();
        nodeNormals_.clear();
    }

private:
    std::map<int, Node> nodes_;
    std::map<int, ShellElement> elements_;

    // Edge (sorted node pair) -> list of element IDs sharing that edge
    std::map<std::pair<int,int>, std::vector<int>> edgeToElements_;

    // Node-averaged normals (area-weighted average of adjacent element normals)
    std::map<int, Vector3D> nodeNormals_;

    // Compute node-averaged normals from element normals
    void computeNodeNormals();
};

} // namespace KooRemapper
