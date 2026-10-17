// 인클루드 닫힘 리더 — 매뉴얼 규칙을 하나씩 못 박는다(규칙과 근거는 IncludeClosure.h)
//
// 왜 이 파일이 있나 (2026-10-15).
//
//   인클루드를 따라가는 구현이 넷이었고 서로 달랐다. 정본을 하나 세웠으니 **그 정본이 매뉴얼과
//   같은지**를 여기서 직접 본다. 특히 두 자리는 다른 구현들이 실제로 달랐던 곳이라 일부러
//   갈리는 꼴로 고정한다 — ① 중첩 인클루드를 **주 덱 폴더**에서 찾는다(`cleanup_nodes` 는 포함하는
//   파일의 폴더로 풀었다) ② 맨 `*INCLUDE` 가 아닌 카드는 **따라가지 않고 말한다**(`modelmeta` 는
//   `_TRANSFORM` 을 오프셋 없이 읽고 `_PATH` 의 디렉터리를 파일로 열었다).
#include "TestFramework.h"

#include "parser/IncludeClosure.h"

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

using namespace KooRemapper;

namespace {

namespace fs = std::filesystem;

// 시험마다 빈 폴더 하나. 이름에 시험 이름을 넣어 겹치지 않게 한다.
struct Scratch {
    fs::path root;
    explicit Scratch(const std::string& tag) {
        root = fs::temp_directory_path() / ("koorm_incl_" + tag);
        std::error_code ec;
        fs::remove_all(root, ec);
        fs::create_directories(root);
    }
    ~Scratch() { std::error_code ec; fs::remove_all(root, ec); }
    std::string put(const std::string& rel, const std::string& body) const {
        const fs::path p = root / rel;
        fs::create_directories(p.parent_path());
        std::ofstream(p) << body;
        return p.string();
    }
};

std::vector<std::string> splitLines(const std::string& body) {
    std::vector<std::string> out;
    size_t a = 0;
    while (a <= body.size()) {
        size_t b = body.find('\n', a);
        if (b == std::string::npos) { if (a < body.size()) out.push_back(body.substr(a)); break; }
        out.push_back(body.substr(a, b - a));
        a = b + 1;
    }
    return out;
}

include_closure::Closure readMain(const Scratch& s, const std::string& rel, const std::string& body) {
    const std::string p = s.put(rel, body);
    return include_closure::read(p, splitLines(body));
}

std::string baseOf(const std::string& p) { return fs::path(p).filename().string(); }

}  // namespace

// ── 이름 카드 ───────────────────────────────────────────────────────────────

TEST(IncludeClosure_한_카드에_이름_여러_장) {
    // Vol_I 179253 — "Include as many of this card as needed. The next keyword card terminates".
    Scratch s("multi");
    s.put("a.k", "*KEYWORD\n*END\n");
    s.put("b.k", "*KEYWORD\n*END\n");
    auto c = readMain(s, "main.k", "*KEYWORD\n*INCLUDE\na.k\n$ 주석\n\nb.k\n*END\n");
    ASSERT_EQ(c.files.size(), (size_t)2);
    ASSERT_EQ(baseOf(c.files[0].path), std::string("a.k"));
    ASSERT_EQ(baseOf(c.files[1].path), std::string("b.k"));
    ASSERT_EQ(c.cards, (size_t)2);
    ASSERT_TRUE(c.complete());
}

TEST(IncludeClosure_이름_이음_스페이스_플러스) {
    // Vol_I 179670 — 앞줄을 "␣+" 로 끝내면 다음 줄이 이어진다.
    std::vector<std::string> l = {"*INCLUDE", "very/long/fold +", "er/name.k", "*END"};
    auto n = include_closure::namesFrom(l, 1);
    ASSERT_EQ(n.size(), (size_t)1);
    ASSERT_EQ(n[0].name, std::string("very/long/folder/name.k"));
    ASSERT_EQ(n[0].line, (size_t)1);
    // 세 줄이 상한이다 — 넷째 줄은 새 이름이다.
    std::vector<std::string> l3 = {"*INCLUDE", "a +", "b +", "c +", "d.k"};
    auto n3 = include_closure::namesFrom(l3, 1);
    ASSERT_EQ(n3.size(), (size_t)2);
    ASSERT_EQ(n3[0].name, std::string("abc +"));
    ASSERT_EQ(n3[1].name, std::string("d.k"));
}

// ── 중첩 · *END · 순환 ──────────────────────────────────────────────────────

TEST(IncludeClosure_중첩은_깊이_우선_차례) {
    Scratch s("nest");
    s.put("a.k", "*KEYWORD\n*INCLUDE\nb.k\n*SET_PART\n1\n*END\n");
    s.put("b.k", "*KEYWORD\n*END\n");
    s.put("c.k", "*KEYWORD\n*END\n");
    auto c = readMain(s, "main.k", "*KEYWORD\n*INCLUDE\na.k\nc.k\n*END\n");
    ASSERT_EQ(c.files.size(), (size_t)3);
    ASSERT_EQ(baseOf(c.files[0].path), std::string("a.k"));
    ASSERT_EQ(baseOf(c.files[1].path), std::string("b.k"));   // a 안의 b 가 c 보다 먼저다
    ASSERT_EQ(baseOf(c.files[2].path), std::string("c.k"));
    ASSERT_EQ(c.files[1].depth, (size_t)2);
    ASSERT_EQ(baseOf(c.files[1].from), std::string("a.k"));
}

TEST(IncludeClosure_인클루드_파일의_END_는_그_파일만_끝낸다) {
    // Vol_I 179654 — "the command *END terminates the include file".
    Scratch s("end");
    s.put("a.k", "*KEYWORD\n*SET_PART\n7\n*END\n*SET_PART\n8\n*INCLUDE\nghost.k\n");
    auto c = readMain(s, "main.k", "*KEYWORD\n*INCLUDE\na.k\n*END\n*INCLUDE\nafter_end.k\n");
    ASSERT_EQ(c.files.size(), (size_t)1);
    bool saw8 = false;
    for (const auto& l : c.files[0].lines) if (l == "8") saw8 = true;
    ASSERT_FALSE(saw8);                        // *END 뒤 줄은 담지 않는다
    ASSERT_TRUE(c.unresolved.empty());         // *END 뒤 인클루드(ghost·after_end)는 찾지도 않는다
    ASSERT_TRUE(c.complete());
}

TEST(IncludeClosure_순환은_한_번만_읽고_말한다) {
    Scratch s("cycle");
    s.put("a.k", "*KEYWORD\n*INCLUDE\nmain.k\na.k\n*END\n");
    auto c = readMain(s, "main.k", "*KEYWORD\n*INCLUDE\na.k\n*END\n");
    ASSERT_EQ(c.files.size(), (size_t)1);
    ASSERT_EQ(c.cycles.size(), (size_t)2);     // main 으로 되돌아가기 · a 자기 자신
}

// ── 찾는 자리 ───────────────────────────────────────────────────────────────

TEST(IncludeClosure_중첩도_주_덱_폴더에서_찾는다) {
    // Vol_I 181591 — "search for files in the local directory first". 로컬 디렉터리는 주 덱 폴더다.
    // ★`sub/b.k` 에만 있는 파일은 LS-DYNA 가 못 찾는다 — 우리도 못 찾아야 한다
    //   (포함하는 파일의 폴더로 풀면 찾아 버린다 — `cleanup_nodes` 가 그랬다).
    Scratch s("local");
    s.put("sub/a.k", "*KEYWORD\n*INCLUDE\nb.k\n*END\n");
    s.put("sub/b.k", "*KEYWORD\n*END\n");
    auto c = readMain(s, "main.k", "*KEYWORD\n*INCLUDE\nsub/a.k\n*END\n");
    ASSERT_EQ(c.files.size(), (size_t)1);
    ASSERT_EQ(c.unresolved.size(), (size_t)1);
    ASSERT_EQ(c.unresolved[0].name, std::string("b.k"));
    ASSERT_FALSE(c.complete());
    // 주 덱 폴더에 있으면 찾는다.
    s.put("b.k", "*KEYWORD\n*END\n");
    auto c2 = readMain(s, "main.k", "*KEYWORD\n*INCLUDE\nsub/a.k\n*END\n");
    ASSERT_EQ(c2.files.size(), (size_t)2);
    ASSERT_TRUE(c2.complete());
}

TEST(IncludeClosure_INCLUDE_PATH_는_경로_없는_이름만) {
    // Vol_I 181591 — 못 찾고 "the filename has no path" 일 때만 탐색 경로를 본다.
    Scratch s("path");
    s.put("lib/m.k", "*KEYWORD\n*END\n");
    s.put("lib/x/y.k", "*KEYWORD\n*END\n");
    auto c = readMain(s, "main.k",
                      "*KEYWORD\n*INCLUDE_PATH_RELATIVE\nlib\n*INCLUDE\nm.k\nx/y.k\n*END\n");
    ASSERT_EQ(c.files.size(), (size_t)1);       // m.k 는 lib 에서 찾는다
    ASSERT_EQ(baseOf(c.files[0].path), std::string("m.k"));
    ASSERT_EQ(c.unresolved.size(), (size_t)1);  // x/y.k 는 경로가 있어 탐색 경로를 안 본다
    ASSERT_EQ(c.cards, (size_t)2);              // *INCLUDE_PATH 는 파일로 세지 않는다
}

TEST(IncludeClosure_없는_파일은_말한다) {
    Scratch s("missing");
    auto c = readMain(s, "main.k", "*KEYWORD\n*INCLUDE\nnope.k\n*END\n");
    ASSERT_EQ(c.files.size(), (size_t)0);
    ASSERT_EQ(c.unresolved.size(), (size_t)1);
    ASSERT_EQ(c.unresolved[0].why, std::string("없다"));
    ASSERT_EQ(c.unresolved[0].line, (size_t)3);
    ASSERT_FALSE(c.complete());
}

// ── 따라가지 않는 것 ─────────────────────────────────────────────────────────

TEST(IncludeClosure_TRANSFORM_은_따라가지_않고_말한다) {
    // 오프셋(IDNOFF…)을 모른 채 읽으면 번호가 그럴듯하게 틀린다 — 그래서 읽지 않는다.
    // `modelmeta` 는 이것을 맨 *INCLUDE 처럼 읽었다(그리고 오프셋 줄을 파일 이름으로 열려 했다).
    Scratch s("transform");
    s.put("t.k", "*KEYWORD\n*SET_PART\n5\n*END\n");
    auto c = readMain(s, "main.k",
                      "*KEYWORD\n*INCLUDE_TRANSFORM\nt.k\n100000,100000,100,100,100\n*END\n");
    ASSERT_EQ(c.files.size(), (size_t)0);
    ASSERT_EQ(c.notFollowed.size(), (size_t)1);
    ASSERT_EQ(c.notFollowed[0].keyword, std::string("*INCLUDE_TRANSFORM"));
    ASSERT_EQ(c.notFollowed[0].name, std::string("t.k"));
    ASSERT_FALSE(c.complete());
}

TEST(IncludeClosure_인클루드가_없으면_빈_닫힘이고_완전하다) {
    Scratch s("none");
    auto c = readMain(s, "main.k", "*KEYWORD\n*SET_PART\n1\n*END\n");
    ASSERT_TRUE(c.files.empty());
    ASSERT_EQ(c.cards, (size_t)0);
    ASSERT_TRUE(c.complete());
}

// ── 펼치기 — LS-DYNA 가 읽는 차례 ───────────────────────────────────────────

TEST(IncludeClosure_펼치기는_이름_줄_바로_뒤에_중첩까지) {
    Scratch s("flat");
    s.put("a.k", "*KEYWORD\n*SET_PART\nA\n*INCLUDE\nc.k\n*SET_PART\nA2\n*END\nAFTER_END\n");
    s.put("b.k", "*KEYWORD\n*SET_PART\nB\n*END\n");
    s.put("c.k", "*KEYWORD\n*SET_PART\nC\n*END\n");
    const std::string body = "*KEYWORD\n*INCLUDE\na.k\nb.k\n*SET_PART\nM\n*END\n";
    const std::string mp = s.put("main.k", body);
    const auto L = splitLines(body);
    const auto c = include_closure::read(mp, L);
    const auto f = include_closure::flatten(L, mp, c);
    const std::vector<std::string> want = {
        "*KEYWORD", "*INCLUDE",
        "a.k", "*KEYWORD", "*SET_PART", "A", "*INCLUDE",
               "c.k", "*KEYWORD", "*SET_PART", "C",          // a 안의 c 는 그 이름 줄 뒤에
               "*SET_PART", "A2",                             // a 의 *END 뒤(AFTER_END)는 없다
        "b.k", "*KEYWORD", "*SET_PART", "B",
        "*SET_PART", "M", "*END"};
    ASSERT_EQ(f.size(), want.size());
    for (size_t i = 0; i < want.size() && i < f.size(); ++i) ASSERT_EQ(f[i], want[i]);
}

TEST(IncludeClosure_펼치기는_이음_이름의_마지막_줄_뒤에) {
    Scratch s("flatcont");
    s.put("sub/long_name.k", "*KEYWORD\n*SET_PART\nX\n*END\n");
    const std::string body = "*KEYWORD\n*INCLUDE\nsub/long_ +\nname.k\n*END\n";
    const std::string mp = s.put("main.k", body);
    const auto L = splitLines(body);
    const auto c = include_closure::read(mp, L);
    ASSERT_EQ(c.files.size(), (size_t)1);
    ASSERT_EQ(c.files[0].afterLine, (size_t)4);    // 둘째 줄("name.k") 뒤
    const auto f = include_closure::flatten(L, mp, c);
    ASSERT_EQ(f[3], std::string("name.k"));
    ASSERT_EQ(f[4], std::string("*KEYWORD"));
}

TEST(IncludeClosure_못_읽은_이름은_펼치지_않고_줄을_지킨다) {
    Scratch s("flatmiss");
    const std::string body = "*KEYWORD\n*INCLUDE\nnope.k\n*SET_PART\nM\n*END\n";
    const std::string mp = s.put("main.k", body);
    const auto L = splitLines(body);
    const auto f = include_closure::flatten(L, mp, include_closure::read(mp, L));
    ASSERT_EQ(f.size(), L.size());
    for (size_t i = 0; i < L.size(); ++i) ASSERT_EQ(f[i], L[i]);
}

// ── 차례와 경로만(`readPaths`) — 흘려 읽는 소비자(cleanup-nodes)용 · 2026-10-17 ─────────────────
// 담는 판(`read`)과 **같은 규칙**이어야 한다 — 갈리면 두 소비자가 다른 파일을 본다. 예전 cleanup-nodes 의 자기 재귀는
// 9단째 인클루드를 훑지 않아 거기 요소가 쓰는 절점을 지웠다.

TEST(IncludeClosure_readPaths_는_read_와_같은_파일_같은_차례) {
    Scratch s("paths");
    s.put("a.k", "*KEYWORD\n*INCLUDE\nb.k\n*END\n*INCLUDE\nghost.k\n");
    s.put("b.k", "*KEYWORD\n*SET_PART\n1\n*END\n");
    s.put("long_name.k", "*KEYWORD\n*END\n");
    const std::string body = "*KEYWORD\n*INCLUDE\na.k\nlong_ +\nname.k\nmissing.k\n*INCLUDE_TRANSFORM\nt.k\n*END\n";
    const std::string mp = s.put("main.k", body);
    const auto c1 = include_closure::read(mp, splitLines(body));
    const auto c2 = include_closure::readPaths(mp);
    ASSERT_EQ(c2.files.size(), c1.files.size());
    for (size_t k = 0; k < c1.files.size(); ++k) {
        ASSERT_EQ(c2.files[k].path, c1.files[k].path);
        ASSERT_EQ(c2.files[k].depth, c1.files[k].depth);
        ASSERT_EQ(c2.files[k].fromLine, c1.files[k].fromLine);
        ASSERT_EQ(c2.files[k].afterLine, c1.files[k].afterLine);
        ASSERT_TRUE(c2.files[k].lines.empty());           // 줄은 담지 않는다
    }
    ASSERT_EQ(c2.unresolved.size(), c1.unresolved.size());  // missing.k (ghost.k 는 *END 뒤라 찾지도 않는다)
    ASSERT_EQ(c2.unresolved[0].line, c1.unresolved[0].line);
    ASSERT_EQ(c2.notFollowed.size(), (size_t)1);
    ASSERT_EQ(c2.notFollowed[0].line, c1.notFollowed[0].line);
    ASSERT_EQ(c2.cards, c1.cards);
}

TEST(IncludeClosure_readPaths_깊이_상한을_말한다) {
    Scratch s("pdeep");
    for (int k = 1; k <= 3; ++k)
        s.put("d" + std::to_string(k) + ".k", "*KEYWORD\n*INCLUDE\nd" + std::to_string(k + 1) + ".k\n*END\n");
    s.put("d4.k", "*KEYWORD\n*END\n");
    const std::string mp = s.put("main.k", "*KEYWORD\n*INCLUDE\nd1.k\n*END\n");
    const auto ok = include_closure::readPaths(mp, 4);
    ASSERT_EQ(ok.files.size(), (size_t)4);
    ASSERT_FALSE(ok.depthCut);
    const auto cut = include_closure::readPaths(mp, 3);
    ASSERT_EQ(cut.files.size(), (size_t)3);
    ASSERT_TRUE(cut.depthCut);
    ASSERT_FALSE(cut.complete());
}
