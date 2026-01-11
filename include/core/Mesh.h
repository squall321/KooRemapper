#pragma once

#include "core/Node.h"
#include "core/Element.h"
#include "core/Vector3D.h"
#include <map>
#include <vector>
#include <string>
#include <utility>

namespace KooRemapper {

/**
 * Part definition
 */
struct Part {
    int id;
    std::string name;

    Part() : id(0) {}
    Part(int id, const std::string& name = "") : id(id), name(name) {}
};

/**
 * Mesh statistics structure
 */
struct MeshStats {
    int nodeCount;
    int elementCount;
    Vector3D boundingBoxMin;
    Vector3D boundingBoxMax;
    Vector3D dimensions;        // boundingBoxMax - boundingBoxMin
    Vector3D centroid;          // Center of bounding box

    // Grid dimensions (for structured meshes)
    int dimI, dimJ, dimK;
    bool isStructured;

    MeshStats()
        : nodeCount(0), elementCount(0)
        , dimI(0), dimJ(0), dimK(0)
        , isStructured(false) {}
};

/**
 * Mesh class containing nodes and elements
 */
class Mesh {
public:
    std::map<int, Node> nodes;          // Node ID -> Node
    std::map<int, Element> elements;    // Element ID -> Element
    std::map<int, Part> parts;          // Part ID -> Part
    std::string name_;                  // Mesh name

    // Grid dimensions (for structured meshes)
    int dimI, dimJ, dimK;
    bool gridDimensionsSet;

    // Constructors
    Mesh() : dimI(0), dimJ(0), dimK(0), gridDimensionsSet(false) {}

    // Copy and move
    Mesh(const Mesh& other) = default;
    Mesh& operator=(const Mesh& other) = default;
    Mesh(Mesh&& other) noexcept = default;
    Mesh& operator=(Mesh&& other) noexcept = default;

    // Node operations
    void addNode(const Node& node) {
        nodes[node.id] = node;
    }

    void addNode(int id, double x, double y, double z) {
        nodes[id] = Node(id, x, y, z);
    }

    Node* getNode(int id) {
        auto it = nodes.find(id);
        return (it != nodes.end()) ? &it->second : nullptr;
    }

    const Node* getNode(int id) const {
        auto it = nodes.find(id);
        return (it != nodes.end()) ? &it->second : nullptr;
    }

    bool hasNode(int id) const {
        return nodes.find(id) != nodes.end();
    }

    // Element operations
    void addElement(const Element& elem) {
        elements[elem.id] = elem;
    }

    void addElement(int id, int partId, const std::array<int, 8>& nodeIds) {
        elements[id] = Element(id, partId, nodeIds);
    }

    Element* getElement(int id) {
        auto it = elements.find(id);
        return (it != elements.end()) ? &it->second : nullptr;
    }

    const Element* getElement(int id) const {
        auto it = elements.find(id);
        return (it != elements.end()) ? &it->second : nullptr;
    }

    bool hasElement(int id) const {
        return elements.find(id) != elements.end();
    }

    // Get element by grid index
    Element* getElementByIndex(int i, int j, int k) {
        for (auto& [id, elem] : elements) {
            if (elem.indexAssigned && elem.i == i && elem.j == j && elem.k == k) {
                return &elem;
            }
        }
        return nullptr;
    }

    const Element* getElementByIndex(int i, int j, int k) const {
        for (const auto& [id, elem] : elements) {
            if (elem.indexAssigned && elem.i == i && elem.j == j && elem.k == k) {
                return &elem;
            }
        }
        return nullptr;
    }

    // Count operations
    size_t getNodeCount() const { return nodes.size(); }
    size_t getElementCount() const { return elements.size(); }
    size_t getPartCount() const { return parts.size(); }

    // Accessors for collections
    const std::map<int, Node>& getNodes() const { return nodes; }
    const std::map<int, Element>& getElements() const { return elements; }
    const std::map<int, Part>& getParts() const { return parts; }

    // Name operations
    void setName(const std::string& name) { name_ = name; }
    const std::string& getName() const { return name_; }

    // Part operations
    void addPart(const Part& part) { parts[part.id] = part; }
    void addPart(int id, const std::string& name = "") { parts[id] = Part(id, name); }

    // Get bounding box as pair
    std::pair<Vector3D, Vector3D> getBoundingBox() const {
        Vector3D minP, maxP;
        calculateBoundingBox(minP, maxP);
        return {minP, maxP};
    }

    // Set grid dimensions
    void setGridDimensions(int i, int j, int k) {
        dimI = i;
        dimJ = j;
        dimK = k;
        gridDimensionsSet = true;
    }

    // Calculate bounding box
    void calculateBoundingBox(Vector3D& minPoint, Vector3D& maxPoint) const {
        if (nodes.empty()) {
            minPoint = Vector3D(0, 0, 0);
            maxPoint = Vector3D(0, 0, 0);
            return;
        }

        bool first = true;
        for (const auto& [id, node] : nodes) {
            if (first) {
                minPoint = node.position;
                maxPoint = node.position;
                first = false;
            } else {
                minPoint.x = std::min(minPoint.x, node.position.x);
                minPoint.y = std::min(minPoint.y, node.position.y);
                minPoint.z = std::min(minPoint.z, node.position.z);
                maxPoint.x = std::max(maxPoint.x, node.position.x);
                maxPoint.y = std::max(maxPoint.y, node.position.y);
                maxPoint.z = std::max(maxPoint.z, node.position.z);
            }
        }
    }

    // Get mesh statistics
    MeshStats getStats() const {
        MeshStats stats;
        stats.nodeCount = static_cast<int>(nodes.size());
        stats.elementCount = static_cast<int>(elements.size());

        calculateBoundingBox(stats.boundingBoxMin, stats.boundingBoxMax);
        stats.dimensions = stats.boundingBoxMax - stats.boundingBoxMin;
        stats.centroid = (stats.boundingBoxMin + stats.boundingBoxMax) * 0.5;

        stats.dimI = dimI;
        stats.dimJ = dimJ;
        stats.dimK = dimK;
        stats.isStructured = gridDimensionsSet;

        return stats;
    }

    // Clear all data
    void clear() {
        nodes.clear();
        elements.clear();
        parts.clear();
        name_.clear();
        dimI = dimJ = dimK = 0;
        gridDimensionsSet = false;
    }

    // Get all nodes of an element as vector
    std::vector<const Node*> getElementNodes(const Element& elem) const {
        std::vector<const Node*> result;
        result.reserve(Element::NUM_NODES);
        for (int i = 0; i < Element::NUM_NODES; ++i) {
            const Node* node = getNode(elem.nodeIds[i]);
            if (node) {
                result.push_back(node);
            }
        }
        return result;
    }

    // Calculate element centroid
    Vector3D getElementCentroid(const Element& elem) const {
        Vector3D centroid(0, 0, 0);
        int count = 0;
        for (int i = 0; i < Element::NUM_NODES; ++i) {
            const Node* node = getNode(elem.nodeIds[i]);
            if (node) {
                centroid += node->position;
                ++count;
            }
        }
        if (count > 0) {
            centroid /= static_cast<double>(count);
        }
        return centroid;
    }

    // Validate mesh integrity
    bool validate(std::string& errorMessage) const {
        // Check that all element nodes exist
        for (const auto& [elemId, elem] : elements) {
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                if (!hasNode(elem.nodeIds[i])) {
                    errorMessage = "Element " + std::to_string(elemId) +
                                 " references non-existent node " +
                                 std::to_string(elem.nodeIds[i]);
                    return false;
                }
            }
        }
        return true;
    }
};

} // namespace KooRemapper
