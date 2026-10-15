#include "TestFramework.h"

#include <algorithm>
#include <vector>
#include "core/Mesh.h"
#include "core/Node.h"
#include "core/Element.h"

using namespace KooRemapper;
using namespace KooRemapper::Test;

// ============================================================
// Mesh Basic Operations Tests
// ============================================================

TEST(Mesh_AddNode) {
    Mesh mesh;
    Node n1(1, 0.0, 0.0, 0.0);
    Node n2(2, 1.0, 0.0, 0.0);

    mesh.addNode(n1);
    mesh.addNode(n2);

    ASSERT_EQ(mesh.getNodeCount(), 2);
}

TEST(Mesh_AddElement) {
    Mesh mesh;

    // Add 8 nodes for a hex element
    for (int i = 1; i <= 8; ++i) {
        mesh.addNode(Node(i, static_cast<double>(i), 0.0, 0.0));
    }

    Element elem;
    elem.id = 1;
    elem.partId = 1;
    elem.nodeIds = {1, 2, 3, 4, 5, 6, 7, 8};
    mesh.addElement(elem);

    ASSERT_EQ(mesh.getElementCount(), 1);
}

TEST(Mesh_GetNode) {
    Mesh mesh;
    Node n(42, 1.5, 2.5, 3.5);
    mesh.addNode(n);

    const Node* retrieved = mesh.getNode(42);
    ASSERT_TRUE(retrieved != nullptr);
    ASSERT_NEAR(retrieved->position.x, 1.5, 1e-10);
    ASSERT_NEAR(retrieved->position.y, 2.5, 1e-10);
    ASSERT_NEAR(retrieved->position.z, 3.5, 1e-10);
}

TEST(Mesh_GetNodeNotFound) {
    Mesh mesh;
    const Node* retrieved = mesh.getNode(999);
    ASSERT_TRUE(retrieved == nullptr);
}

TEST(Mesh_GetElement) {
    Mesh mesh;
    for (int i = 1; i <= 8; ++i) {
        mesh.addNode(Node(i, 0.0, 0.0, 0.0));
    }

    Element elem;
    elem.id = 100;
    elem.partId = 1;
    elem.nodeIds = {1, 2, 3, 4, 5, 6, 7, 8};
    mesh.addElement(elem);

    const Element* retrieved = mesh.getElement(100);
    ASSERT_TRUE(retrieved != nullptr);
    ASSERT_EQ(retrieved->id, 100);
}

TEST(Mesh_BoundingBox) {
    Mesh mesh;
    mesh.addNode(Node(1, -1.0, -2.0, -3.0));
    mesh.addNode(Node(2, 4.0, 5.0, 6.0));
    mesh.addNode(Node(3, 0.0, 0.0, 0.0));

    auto [minBound, maxBound] = mesh.getBoundingBox();

    ASSERT_NEAR(minBound.x, -1.0, 1e-10);
    ASSERT_NEAR(minBound.y, -2.0, 1e-10);
    ASSERT_NEAR(minBound.z, -3.0, 1e-10);

    ASSERT_NEAR(maxBound.x, 4.0, 1e-10);
    ASSERT_NEAR(maxBound.y, 5.0, 1e-10);
    ASSERT_NEAR(maxBound.z, 6.0, 1e-10);
}

TEST(Mesh_Name) {
    Mesh mesh;
    mesh.setName("TestMesh");
    ASSERT_EQ(mesh.getName(), "TestMesh");
}

TEST(Mesh_Clear) {
    Mesh mesh;
    mesh.addNode(Node(1, 0.0, 0.0, 0.0));
    mesh.addNode(Node(2, 1.0, 0.0, 0.0));

    ASSERT_EQ(mesh.getNodeCount(), 2);

    mesh.clear();
    ASSERT_EQ(mesh.getNodeCount(), 0);
    ASSERT_EQ(mesh.getElementCount(), 0);
}

// ============================================================
// Element Tests
// ============================================================

TEST(Element_Constructor) {
    Element elem;
    elem.id = 1;
    elem.partId = 1;
    elem.nodeIds = {1, 2, 3, 4, 5, 6, 7, 8};

    ASSERT_EQ(elem.id, 1);
    ASSERT_EQ(elem.nodeIds[0], 1);
    ASSERT_EQ(elem.nodeIds[7], 8);
}

TEST(Element_ContainsNode) {
    Element elem;
    elem.id = 1;
    elem.nodeIds = {10, 20, 30, 40, 50, 60, 70, 80};

    ASSERT_TRUE(elem.containsNode(10));
    ASSERT_TRUE(elem.containsNode(50));
    ASSERT_FALSE(elem.containsNode(100));
}

TEST(Element_GetFaceNodeIds) {
    Element elem;
    elem.id = 1;
    elem.nodeIds = {1, 2, 3, 4, 5, 6, 7, 8};

    // Face 0 (i-): local nodes **0,4,7,3** -> IDs 1,5,8,4
    //
    // ★2026-10-15 에 고쳤다. `f1b3709`("면·모서리 표를 한 곳으로")이 면 0·3·4 의 **순회
    //   방향을 뒤집었는데**(시작 꼭짓점은 그대로) 이 시험은 옛 방향을 들고 있었다 —
    //   그래서 `ctest` 가 그 커밋 이후 **계속 빨갰고 아무도 몰랐다.**
    //   뒤집은 이유는 `include/core/Element.h:61-71` 에 실측으로 적혀 있다: 시작점을 돌리면
    //   `modelmeta` 의 부피가 달라진다(`bendtwist_bent.k` 31200.37 → 31995.26, +2.55%).
    //   시작점을 두고 뒤집으면 `v0`·`v2` 대각이 보존된다.
    auto face0 = elem.getFaceNodeIds(0);
    ASSERT_EQ(face0.size(), 4u);
    ASSERT_EQ(face0[0], 1);
    ASSERT_EQ(face0[1], 5);
    ASSERT_EQ(face0[2], 8);
    ASSERT_EQ(face0[3], 4);
}

// ★글자 그대로의 순서만 보면, 다음에 또 방향을 뒤집는 사람이 "시험이 빨개졌으니 시험을
//   고치자" 로 간다. 그래서 **뒤집어도 지켜져야 하는 것**을 따로 못 박는다 —
//   ① 면의 절점 **집합**은 바뀌지 않는다 ② `v0`-`v2` **대각이 보존**된다(부피가 그것에 달려 있다).
TEST(Element_FaceInvariants_대각과_집합) {
    Element elem;
    elem.id = 1;
    elem.nodeIds = {1, 2, 3, 4, 5, 6, 7, 8};

    // i- 면의 절점 집합은 {1,4,5,8} 이다(순서와 무관).
    auto f0 = elem.getFaceNodeIds(0);
    std::vector<int> got(f0.begin(), f0.end());
    std::sort(got.begin(), got.end());
    const std::vector<int> want = {1, 4, 5, 8};
    ASSERT_TRUE(got == want);

    // 대각 v0-v2 — 뒤집어도 0번과 2번 자리는 그대로여야 한다(부피 쪼개기가 이 대각을 쓴다).
    ASSERT_EQ(f0[0], 1);
    ASSERT_EQ(f0[2], 8);

    // 마주보는 면(i+)과 절점을 하나도 공유하지 않는다 — 면 **순서** 규약(axis=fi/2)의 뿌리다.
    auto f1 = elem.getFaceNodeIds(1);
    for (int a : f0) for (int b : f1) ASSERT_NE(a, b);
}

TEST(Element_PartId) {
    Element elem;
    elem.id = 1;
    elem.partId = 42;
    ASSERT_EQ(elem.partId, 42);
}

TEST(Element_GridIndices) {
    Element elem;
    elem.id = 1;
    elem.setGridIndex(2, 3, 4);

    ASSERT_EQ(elem.i, 2);
    ASSERT_EQ(elem.j, 3);
    ASSERT_EQ(elem.k, 4);
    ASSERT_TRUE(elem.indexAssigned);
}

TEST(Element_StaticFaceInfo) {
    // Test opposite face
    ASSERT_EQ(Element::getOppositeFace(0), 1);
    ASSERT_EQ(Element::getOppositeFace(1), 0);
    ASSERT_EQ(Element::getOppositeFace(2), 3);
    ASSERT_EQ(Element::getOppositeFace(3), 2);
    ASSERT_EQ(Element::getOppositeFace(4), 5);
    ASSERT_EQ(Element::getOppositeFace(5), 4);

    // Test face axis
    ASSERT_EQ(Element::getFaceAxis(0), 0);  // i-
    ASSERT_EQ(Element::getFaceAxis(1), 0);  // i+
    ASSERT_EQ(Element::getFaceAxis(2), 1);  // j-
    ASSERT_EQ(Element::getFaceAxis(3), 1);  // j+
    ASSERT_EQ(Element::getFaceAxis(4), 2);  // k-
    ASSERT_EQ(Element::getFaceAxis(5), 2);  // k+
}

// ============================================================
// Node Tests
// ============================================================

TEST(Node_Constructor) {
    Node n(1, 1.5, 2.5, 3.5);
    ASSERT_EQ(n.id, 1);
    ASSERT_NEAR(n.position.x, 1.5, 1e-10);
    ASSERT_NEAR(n.position.y, 2.5, 1e-10);
    ASSERT_NEAR(n.position.z, 3.5, 1e-10);
}

TEST(Node_DefaultConstructor) {
    Node n;
    ASSERT_EQ(n.id, 0);
    ASSERT_NEAR(n.position.x, 0.0, 1e-10);
    ASSERT_NEAR(n.position.y, 0.0, 1e-10);
    ASSERT_NEAR(n.position.z, 0.0, 1e-10);
}
