// 구조 격자 색인기가 면 위상만으로 (i,j,k) 와 절점 순서를 정하는지 — 뒤섞인 절점 순서 · 바짝 접힌 블록 · 구멍 · 닫히지 않는 격자
#include "TestFramework.h"

#include "core/Mesh.h"
#include "grid/ConnectivityAnalyzer.h"
#include "grid/StructuredGridIndexer.h"

#include <array>
#include <cmath>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <tuple>

using namespace KooRemapper;

namespace gridtest {

// LS-DYNA 육면체의 절점 자리 c 가 (i,j,k) 마다 낮은 쪽(0)인지 높은 쪽(1)인지
const int SIDES[8][3] = {{0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0}, {0, 0, 1}, {1, 0, 1}, {1, 1, 1}, {0, 1, 1}};

int cornerOf(int a, int b, int c) {
    for (int q = 0; q < 8; ++q) {
        if (SIDES[q][0] == a && SIDES[q][1] == b && SIDES[q][2] == c) return q;
    }
    return -1;
}

// 같은 요소를 다른 절점 순서로 — 회전 셋과 거울 하나를 pick 의 비트로 겹친다(절점 집합 · 면은 그대로다)
std::array<int, 8> scramble(const std::array<int, 8>& nodes, int pick) {
    std::array<int, 8> out{};
    for (int c = 0; c < 8; ++c) {
        int a = SIDES[c][0], b = SIDES[c][1], d = SIDES[c][2];
        if (pick & 1) { int t = a; a = b; b = 1 - t; }   // k 축 둘레 90 도
        if (pick & 2) { int t = b; b = d; d = 1 - t; }   // i 축 둘레 90 도
        if (pick & 4) { int t = a; a = d; d = 1 - t; }   // j 축 둘레 90 도
        if (pick & 8) { d = 1 - d; }                     // 거울(왼손 순서)
        out[c] = nodes[cornerOf(a, b, d)];
    }
    return out;
}

using NodeId = std::function<int(int, int, int)>;
using Position = std::function<Vector3D(int, int, int)>;

// ni×nj×nk 블록을 mesh 에 더한다 — 격자점의 절점 번호와 자리는 부르는 쪽이 정한다. 요소 번호는 firstElem 부터 거꾸로 센다
void addBlock(Mesh& mesh, int ni, int nj, int nk, const NodeId& nodeId, const Position& pos,
              bool scrambled, bool preIndexed, int firstElem) {
    for (int k = 0; k <= nk; ++k) {
        for (int j = 0; j <= nj; ++j) {
            for (int i = 0; i <= ni; ++i) {
                const Vector3D p = pos(i, j, k);
                mesh.addNode(nodeId(i, j, k), p.x, p.y, p.z);
            }
        }
    }
    int eid = firstElem + ni * nj * nk - 1;
    for (int k = 0; k < nk; ++k) {
        for (int j = 0; j < nj; ++j) {
            for (int i = 0; i < ni; ++i, --eid) {
                std::array<int, 8> nodes{};
                for (int c = 0; c < 8; ++c) {
                    nodes[c] = nodeId(i + SIDES[c][0], j + SIDES[c][1], k + SIDES[c][2]);
                }
                Element elem(eid, 1, scrambled ? scramble(nodes, (eid * 7 + 3) % 16) : nodes);
                if (preIndexed) elem.setGridIndex(i, j, k);
                mesh.addElement(elem);
            }
        }
    }
}

NodeId plainIds(int ni, int nj, int base = 0) {
    return [=](int i, int j, int k) { return base + 1 + i + (ni + 1) * (j + (nj + 1) * k); };
}

Vector3D boxPosition(int i, int j, int k) { return Vector3D(i, j, k); }

// 색인과 절점 순서가 한 격자를 이루는가 — 격자점마다 절점 하나, 절점마다 격자점 하나(unfold 가 이 대응으로 평판을 짓는다)
bool oneLattice(const Mesh& mesh, size_t points) {
    std::map<std::tuple<int, int, int>, int> at;
    std::set<int> used;
    for (const auto& [id, e] : mesh.elements) {
        if (!e.indexAssigned) return false;
        for (int c = 0; c < 8; ++c) {
            auto [it, fresh] = at.emplace(std::make_tuple(e.i + SIDES[c][0], e.j + SIDES[c][1], e.k + SIDES[c][2]),
                                          e.nodeIds[c]);
            if (!fresh && it->second != e.nodeIds[c]) return false;
            used.insert(e.nodeIds[c]);
        }
    }
    return at.size() == points && used.size() == points;
}

std::map<int, std::set<int>> nodeSets(const Mesh& mesh) {
    std::map<int, std::set<int>> sets;
    for (const auto& [id, e] : mesh.elements) sets[id] = std::set<int>(e.nodeIds.begin(), e.nodeIds.end());
    return sets;
}

bool contains(const std::string& text, const char* piece) { return text.find(piece) != std::string::npos; }

} // namespace gridtest

TEST(GridIndexer_뒤섞인_절점_순서의_상자를_한_격자로_읽는다) {
    Mesh mesh;
    gridtest::addBlock(mesh, 4, 3, 2, gridtest::plainIds(4, 3), gridtest::boxPosition, true, false, 1);
    const auto before = gridtest::nodeSets(mesh);
    ConnectivityAnalyzer connectivity;
    connectivity.buildConnectivity(mesh);
    StructuredGridIndexer indexer;
    ASSERT_TRUE(indexer.assignIndices(mesh, connectivity));
    ASSERT_EQ(indexer.getDimI(), 4);
    ASSERT_EQ(indexer.getDimJ(), 3);
    ASSERT_EQ(indexer.getDimK(), 2);
    ASSERT_TRUE(indexer.reorderElementNodes(mesh));
    ASSERT_TRUE(gridtest::oneLattice(mesh, 5 * 4 * 3));
    ASSERT_TRUE(gridtest::nodeSets(mesh) == before);      // 순서만 바꾼다 — 절점을 바꿔 끼우지 않는다
}

TEST(GridIndexer_바짝_접힌_블록도_칸이_겹치지_않는다) {
    // i = 3 에서 접어 뒤쪽 절반을 앞쪽 절반 바로 위에 눕힌다. 접힌 자리의 이웃은 중심이 +z 로만 떨어져 있어(i 가 아니라 k 처럼
    // 보인다) 중심 방향으로 축을 어림하면 두 요소가 한 칸에 놓였다
    const int ni = 6, nj = 3, nk = 2;
    auto folded = [&](int i, int j, int k) {
        return i <= 3 ? Vector3D(i, j, k) : Vector3D(6 - i, j, nk + 0.05 + (nk - k));
    };
    Mesh mesh;
    gridtest::addBlock(mesh, ni, nj, nk, gridtest::plainIds(ni, nj), folded, true, false, 1);
    const auto before = gridtest::nodeSets(mesh);
    ConnectivityAnalyzer connectivity;
    connectivity.buildConnectivity(mesh);
    StructuredGridIndexer indexer;
    ASSERT_TRUE(indexer.assignIndices(mesh, connectivity));
    ASSERT_EQ(indexer.getDimI(), ni);
    ASSERT_EQ(indexer.getDimJ(), nj);
    ASSERT_EQ(indexer.getDimK(), nk);
    std::set<std::tuple<int, int, int>> slots;
    for (const auto& [id, e] : mesh.elements) slots.insert({e.i, e.j, e.k});
    ASSERT_EQ(slots.size(), mesh.elements.size());
    ASSERT_TRUE(indexer.reorderElementNodes(mesh));
    ASSERT_TRUE(gridtest::oneLattice(mesh, (ni + 1) * (nj + 1) * (nk + 1)));
    ASSERT_TRUE(gridtest::nodeSets(mesh) == before);
}

TEST(GridIndexer_면이_한_블록으로_닫히지_않으면_거절한다) {
    // 나사 꼴 — 한 바퀴(i 여덟 칸)를 돌면 한 줄 위(j + 1)의 첫 칸에 붙는다. 요소마다 이웃은 멀쩡하고 코너도 있지만, 한 요소에
    // 두 길로 닿으면 칸이 다르다. 칸이 겹치지는 않으므로 뒤의 칸 유일성 관문은 이것을 못 잡는다
    const int around = 8, rows = 3, nk = 2;
    auto screwId = [&](int i, int j, int k) {
        if (i == around) { i = 0; ++j; }
        return 1 + i + around * (j + (rows + 2) * k);
    };
    auto helix = [&](int i, int j, int k) {
        const double angle = 2.0 * 3.14159265358979323846 * i / around;
        return Vector3D((5.0 + k) * std::cos(angle), (5.0 + k) * std::sin(angle), j + static_cast<double>(i) / around);
    };
    Mesh mesh;
    gridtest::addBlock(mesh, around, rows, nk, screwId, helix, false, false, 1);
    ConnectivityAnalyzer connectivity;
    connectivity.buildConnectivity(mesh);
    StructuredGridIndexer indexer;
    ASSERT_FALSE(indexer.assignIndices(mesh, connectivity));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "do not close as one structured block"));
}

TEST(GridIndexer_떨어진_두_덩어리는_거절한다) {
    Mesh mesh;
    gridtest::addBlock(mesh, 2, 2, 2, gridtest::plainIds(2, 2), gridtest::boxPosition, false, false, 1);
    gridtest::addBlock(mesh, 2, 2, 2, gridtest::plainIds(2, 2, 100),
                       [](int i, int j, int k) { return Vector3D(i + 10.0, j, k); }, false, false, 101);
    ConnectivityAnalyzer connectivity;
    connectivity.buildConnectivity(mesh);
    StructuredGridIndexer indexer;
    ASSERT_FALSE(indexer.assignIndices(mesh, connectivity));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "was not indexed"));
}

TEST(GridIndexer_색인을_이미_가진_요소의_절점을_표준_순서로_돌린다) {
    // 색인이 격자점 좌표와 같으므로 답이 하나다 — 뒤섞기 전의 순서(LS-DYNA 표준)가 그대로 돌아와야 한다
    Mesh plain, mesh;
    gridtest::addBlock(plain, 3, 2, 2, gridtest::plainIds(3, 2), gridtest::boxPosition, false, true, 1);
    gridtest::addBlock(mesh, 3, 2, 2, gridtest::plainIds(3, 2), gridtest::boxPosition, true, true, 1);
    ConnectivityAnalyzer connectivity;
    connectivity.buildConnectivity(mesh);
    StructuredGridIndexer indexer;
    ASSERT_TRUE(indexer.assignIndices(mesh, connectivity));      // 색인이 다 있으면 걷지 않는다
    ASSERT_TRUE(indexer.reorderElementNodes(mesh));
    for (const auto& [id, e] : mesh.elements) {
        ASSERT_TRUE(e.nodeIds == plain.elements.at(id).nodeIds);
    }
}

TEST(GridIndexer_접힌_자리의_절점_순서도_면으로_읽는다) {
    // 같은 접힌 블록에 색인을 미리 준다(걷기를 건너뛴다). 접힌 자리의 요소는 이웃 중심이 가리키는 쪽과 격자 축이 어긋나, 절점을
    // 「그 절점이 놓인 쪽」 으로 어림하면 코너에 다른 절점이 앉았다 — unfold 가 그 덱을 rc 0 으로 다른 연결로 썼다
    const int ni = 6, nj = 3, nk = 2;
    auto folded = [&](int i, int j, int k) {
        return i <= 3 ? Vector3D(i, j, k) : Vector3D(6 - i, j, nk + 0.05 + (nk - k));
    };
    Mesh plain, mesh;
    gridtest::addBlock(plain, ni, nj, nk, gridtest::plainIds(ni, nj), folded, false, true, 1);
    gridtest::addBlock(mesh, ni, nj, nk, gridtest::plainIds(ni, nj), folded, true, true, 1);
    StructuredGridIndexer indexer;
    ASSERT_TRUE(indexer.reorderElementNodes(mesh));
    for (const auto& [id, e] : mesh.elements) {
        ASSERT_TRUE(e.nodeIds == plain.elements.at(id).nodeIds);
    }
}

TEST(GridIndexer_색인이_면과_어긋나면_절점_순서를_짓지_않는다) {
    Mesh mesh;
    gridtest::addBlock(mesh, 3, 2, 2, gridtest::plainIds(3, 2), gridtest::boxPosition, false, true, 1);
    // 마주 보는 두 코너의 칸을 바꾼다 — 칸은 하나씩이고 수도 맞지만 격자 이웃과 면을 나누지 않는다
    Element* first = nullptr;
    Element* last = nullptr;
    for (auto& [id, e] : mesh.elements) {
        if (e.i == 0 && e.j == 0 && e.k == 0) first = &e;
        if (e.i == 2 && e.j == 1 && e.k == 1) last = &e;
    }
    ASSERT_TRUE(first != nullptr && last != nullptr);
    first->setGridIndex(2, 1, 1);
    last->setGridIndex(0, 0, 0);
    StructuredGridIndexer indexer;
    ASSERT_FALSE(indexer.reorderElementNodes(mesh));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "share no face"));
}

TEST(GridIndexer_구멍_위의_요소는_옆_이웃에서_절점_순서를_읽는다) {
    // 두 겹 블록의 아래 겹에서 가운데 3×3 을 뺀다 — 그 위의 아홉 요소는 k 쪽으로 이웃이 없다(아래는 구멍 · 위는 겉면). 어느 면이
    // k- 인지는 옆 이웃의 k- 면을 잇는 면으로 읽는다. 한가운데 요소는 옆 이웃 넷이 다 같은 처지라 그 이웃이 정해진 뒤에 읽힌다
    auto holed = [](Mesh& mesh, bool scrambled, bool preIndexed) {
        gridtest::addBlock(mesh, 5, 3, 2, gridtest::plainIds(5, 3), gridtest::boxPosition, scrambled, preIndexed, 1);
        for (int j = 0; j < 3; ++j) {
            for (int i = 1; i <= 3; ++i) mesh.elements.erase(30 - (i + 5 * j));      // 격자 (i,j,0)
        }
    };
    Mesh plain, given, walked;
    holed(plain, false, true);
    holed(given, true, true);
    holed(walked, true, false);
    ASSERT_EQ(static_cast<int>(given.elements.size()), 21);

    StructuredGridIndexer indexer;
    ASSERT_TRUE(indexer.reorderElementNodes(given));      // 색인을 미리 준 쪽 — 답이 하나다
    for (const auto& [id, e] : given.elements) {
        ASSERT_TRUE(e.nodeIds == plain.elements.at(id).nodeIds);
    }

    const auto before = gridtest::nodeSets(walked);       // 걸어서 색인을 얻는 쪽
    ConnectivityAnalyzer connectivity;
    connectivity.buildConnectivity(walked);
    ASSERT_TRUE(indexer.assignIndices(walked, connectivity));
    ASSERT_TRUE(indexer.reorderElementNodes(walked));
    ASSERT_TRUE(gridtest::oneLattice(walked, 6 * 4 * 3 - 2 * 4));      // 구멍 안쪽 바닥의 절점 여덟은 어느 요소에도 없다
    ASSERT_TRUE(gridtest::nodeSets(walked) == before);
}

TEST(GridIndexer_한_겹_블록은_절점_순서를_짓지_않는다) {
    // 한 겹이면 어느 요소도 k 쪽 이웃이 없다 — 어느 면이 k- 인지 읽을 데가 없으므로 어림하지 않고 거절한다
    Mesh layer, strip;
    gridtest::addBlock(layer, 3, 3, 1, gridtest::plainIds(3, 3), gridtest::boxPosition, true, true, 1);
    StructuredGridIndexer indexer;
    ASSERT_FALSE(indexer.reorderElementNodes(layer));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "none beside it settles that side"));
    gridtest::addBlock(strip, 3, 1, 1, gridtest::plainIds(3, 1), gridtest::boxPosition, true, true, 1);
    ASSERT_FALSE(indexer.reorderElementNodes(strip));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "nor along"));
}

TEST(GridIndexer_시작_모서리의_두_이웃이_한_축에_놓이면_거절한다) {
    // 첫 틀만은 기하로 읽는다(시작 모서리의 세 이웃 중심 방향). 납작하게 눌려 i 이웃과 j 이웃이 한 직선의 양쪽에 놓이면 두 면 쌍이
    // 같은 축을 받는다 — 그 틀로 걷지 않고 거절한다
    Mesh mesh;
    gridtest::addBlock(mesh, 2, 2, 2, gridtest::plainIds(2, 2),
                       [](int i, int j, int k) { return Vector3D(i - j, 0.0, k); }, false, false, 1);
    ConnectivityAnalyzer connectivity;
    connectivity.buildConnectivity(mesh);
    StructuredGridIndexer indexer;
    ASSERT_FALSE(indexer.assignIndices(mesh, connectivity));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "do not lie on three different axes"));
}

TEST(GridIndexer_격자_이웃이_마주_보는_면에_있지_않으면_절점_순서를_짓지_않는다) {
    // 한 줄로 선 세 요소를 ㄱ 자로 색인한다 — 가운데 요소(번호 1 · 먼저 읽힌다)의 i+ 이웃과 j+ 이웃이 실제로는 마주 보는 두 면에
    // 붙어 있다. 이웃마다 면은 나누므로 「면을 나누지 않는다」 로는 안 잡힌다
    Mesh mesh;
    gridtest::addBlock(mesh, 3, 1, 1, gridtest::plainIds(3, 1), gridtest::boxPosition, false, false, 11);
    Element middle(1, 1, mesh.elements.at(12).nodeIds);      // 번호는 i 를 거꾸로 센다 — 13 · 12 · 11
    mesh.elements.erase(12);
    middle.setGridIndex(0, 0, 0);
    mesh.addElement(middle);
    mesh.elements.at(11).setGridIndex(1, 0, 0);
    mesh.elements.at(13).setGridIndex(0, 1, 0);
    StructuredGridIndexer indexer;
    ASSERT_FALSE(indexer.reorderElementNodes(mesh));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "three pairs of opposite faces"));
}

TEST(GridIndexer_옆_이웃끼리_열린_쪽을_달리_말하면_절점_순서를_짓지_않는다) {
    // 세 겹 블록에서 가운데 겹 전부 · 아래 겹의 i = 0 줄 · 위 겹의 i = 2 줄만 남기고, 위에 얹힌 i = 2 줄을 아래 칸(k = 0)이라고
    // 색인한다. 가운데 줄(i = 1)은 k 쪽 이웃이 없어 옆에서 읽는데, i = 0 쪽은 아랫면을 · i = 2 쪽은 윗면을 k- 라고 한다
    Mesh mesh;
    gridtest::addBlock(mesh, 3, 2, 3, gridtest::plainIds(3, 2), gridtest::boxPosition, false, true, 1);
    for (auto it = mesh.elements.begin(); it != mesh.elements.end(); ) {
        Element& e = it->second;
        if (e.k == 1 || (e.k == 0 && e.i == 0) || (e.k == 2 && e.i == 2)) {
            if (e.k == 2) e.setGridIndex(e.i, e.j, 0);
            ++it;
        } else {
            it = mesh.elements.erase(it);
        }
    }
    ASSERT_EQ(static_cast<int>(mesh.elements.size()), 10);
    StructuredGridIndexer indexer;
    ASSERT_FALSE(indexer.reorderElementNodes(mesh));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "disagree on which of its faces"));
}

TEST(GridIndexer_틈을_사이에_둔_격자_이웃은_부른_쪽이_청할_때만_받는다) {
    // 6×5×5 블록의 i = 3 면에서 안쪽 격자점 넷((3, 2..3, 2..3))의 절점을 겹친다 — i ≥ 3 쪽 요소는 새 절점을 쓴다. 그 격자점에
    // 닿는 면 아홉 쌍은 격자 이웃인데 면을 나누지 않는다(가운데 쌍은 절점을 하나도 안 나눈다). unfold 는 격자점마다 절점 하나로
    // 써서 틈을 붙이게 되니 거절하고(기본), map 은 굽은 기준을 읽기만 하니 받는다 — 받을 때도 순서는 표준 순서 하나다
    const int ni = 6, nj = 5, nk = 5;
    const auto ids = gridtest::plainIds(ni, nj);
    auto slit = [&](Mesh& mesh, bool scrambled) {
        gridtest::addBlock(mesh, ni, nj, nk, ids, gridtest::boxPosition, scrambled, true, 1);
        std::map<int, int> twin;
        int next = ids(ni, nj, nk);
        for (int j = 2; j <= 3; ++j) {
            for (int k = 2; k <= 3; ++k) {
                twin[ids(3, j, k)] = ++next;
                mesh.addNode(next, 3, j, k);
            }
        }
        for (auto& [id, e] : mesh.elements) {
            if (e.i < 3) continue;
            for (int& n : e.nodeIds) {
                auto it = twin.find(n);
                if (it != twin.end()) n = it->second;
            }
        }
    };
    Mesh plain, mesh;
    slit(plain, false);
    slit(mesh, true);
    StructuredGridIndexer indexer;
    ASSERT_FALSE(indexer.reorderElementNodes(mesh));
    ASSERT_TRUE(gridtest::contains(indexer.getErrorMessage(), "share no face"));
    ASSERT_TRUE(indexer.reorderElementNodes(mesh, true));
    for (const auto& [id, e] : mesh.elements) {
        ASSERT_TRUE(e.nodeIds == plain.elements.at(id).nodeIds);
    }
}
