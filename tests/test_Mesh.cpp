#include "TestFramework.h"
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

    // Face 0 (i-): local nodes 0,3,7,4 -> IDs 1,4,8,5
    auto face0 = elem.getFaceNodeIds(0);
    ASSERT_EQ(face0.size(), 4u);
    ASSERT_EQ(face0[0], 1);
    ASSERT_EQ(face0[1], 4);
    ASSERT_EQ(face0[2], 8);
    ASSERT_EQ(face0[3], 5);
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
