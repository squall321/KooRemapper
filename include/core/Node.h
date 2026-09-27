#pragma once

#include "core/Vector3D.h"

// Knowledge graph (lat.md):
//   @lat: [[modules/core]]

namespace KooRemapper {

/**
 * Node class representing a point in the mesh
 */
class Node {
public:
    int id;                     // Node ID (from k-file)
    Vector3D position;          // Original position
    Vector3D mappedPosition;    // Mapped position (after transformation)
    bool isMapped;              // Flag indicating if node has been mapped
    // `*NODE` 카드의 TC/RC(이동·회전 자유도 구속). 리더가 예전에는 이 두 칸을 **버렸다** —
    // `KFileWriter` 로 나가는 op(map·shellmap·unfold·squeeze·tetremesh·generate·flip)이
    // 전 자유도 구속을 준 노드를 **구속 없는 노드로** 바꿔 내보내고 rc=0 으로 성공을 보고했다.
    // 0 이 기본이고, 쓰는 쪽은 **둘 중 하나가 0 이 아닐 때만** 칸을 낸다 — 그래서 구속이 없는
    // 덱의 출력 바이트는 그대로다.
    int tc = 0;
    int rc = 0;

    // Constructors
    Node() : id(0), position(), mappedPosition(), isMapped(false) {}

    Node(int id, const Vector3D& pos)
        : id(id), position(pos), mappedPosition(pos), isMapped(false) {}

    Node(int id, double x, double y, double z)
        : id(id), position(x, y, z), mappedPosition(x, y, z), isMapped(false) {}

    // Copy constructor and assignment
    Node(const Node& other) = default;
    Node& operator=(const Node& other) = default;

    // Move constructor and assignment
    Node(Node&& other) noexcept = default;
    Node& operator=(Node&& other) noexcept = default;

    // Getters for convenience
    double x() const { return position.x; }
    double y() const { return position.y; }
    double z() const { return position.z; }

    // Get the current effective position (mapped if available, otherwise original)
    const Vector3D& getEffectivePosition() const {
        return isMapped ? mappedPosition : position;
    }

    // Set mapped position
    void setMappedPosition(const Vector3D& pos) {
        mappedPosition = pos;
        isMapped = true;
    }

    // Reset mapping
    void resetMapping() {
        mappedPosition = position;
        isMapped = false;
    }

    // Distance to another node
    double distanceTo(const Node& other) const {
        return position.distanceTo(other.position);
    }

    // Comparison operators (by ID)
    bool operator==(const Node& other) const {
        return id == other.id;
    }

    bool operator!=(const Node& other) const {
        return id != other.id;
    }

    bool operator<(const Node& other) const {
        return id < other.id;
    }
};

} // namespace KooRemapper
