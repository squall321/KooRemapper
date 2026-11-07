// 쓸 파일이 읽는 파일(설정 YAML · 모델 · 인클루드 닫힘 · 다른 입력)을 덮는지 묻는 공용 관문(OutputGuard.h)을 못 박는 단위 시험
//
// 왜 이 파일이 있나 (2026-11-07).
//
//   op 마다 「output == model」 을 문자열로 견주거나 아예 견주지 않았다 — `update` 의 output 이 모델의 인클루드면 rc 0 으로 그
//   인클루드가 주 덱으로 바뀌었다. 판정을 한 곳(`output_guard`)에 모았으니 그 판정이 철자 · 심볼릭 링크 · 하드 링크 · 인클루드 ·
//   설정을 다 보는지, 그리고 **다른 폴더의 같은 이름 · 상관없는 기존 파일은 거절하지 않는지**를 여기서 직접 본다.
#include "TestFramework.h"

#include "parser/OutputGuard.h"

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

using namespace KooRemapper;

namespace {

namespace fs = std::filesystem;

// 시험마다 빈 폴더 하나(같은 번역 단위의 다른 시험과 이름이 겹치지 않게 OgScratch).
struct OgScratch {
    fs::path root;
    explicit OgScratch(const std::string& tag) {
        root = fs::temp_directory_path() / ("koorm_ogd_" + tag);
        std::error_code ec;
        fs::remove_all(root, ec);
        fs::create_directories(root);
    }
    ~OgScratch() { std::error_code ec; fs::remove_all(root, ec); output_guard::clearConfigs(); }
    std::string put(const std::string& rel, const std::string& body) const {
        const fs::path p = root / rel;
        fs::create_directories(p.parent_path());
        std::ofstream(p) << body;
        return p.string();
    }
    std::string at(const std::string& rel) const { return (root / rel).string(); }
};

}  // namespace

TEST(OutputGuard_modelInputs_는_모델과_중첩_인클루드를_몫과_함께_낸다) {
    OgScratch s("inputs");
    const std::string m = s.put("d/main.k", "*KEYWORD\n*INCLUDE\na.k\n*END\n");
    s.put("d/a.k", "*KEYWORD\n*INCLUDE\nb.k\n*END\n");
    s.put("d/b.k", "*KEYWORD\n*NODE\n*END\n");
    const auto in = output_guard::modelInputs(m);
    ASSERT_EQ(in.size(), (size_t)3);
    ASSERT_EQ(in[0].path, m);
    ASSERT_EQ(in[0].role, std::string("model"));
    ASSERT_EQ(fs::path(in[1].path).filename().string(), std::string("a.k"));
    ASSERT_EQ(fs::path(in[2].path).filename().string(), std::string("b.k"));   // 중첩도 주 덱 폴더에서 찾는다
    ASSERT_EQ(in[2].role, std::string("model 의 인클루드"));
    ASSERT_TRUE(output_guard::modelInputs("").empty());
}

TEST(OutputGuard_modelInputs_는_따라가지_않는_변형_인클루드의_파일도_낸다) {
    // 산출 덱은 `*INCLUDE_TRANSFORM` 카드를 그대로 싣는다 — 그 파일을 덮으면 산출이 가리키는 파일이 사라진다(셋째 묶음 — database ·
    // convert 가 output 을 그 파일로 주면 rc 0 으로 덮었다). 깊이 상한을 넘은 이름의 파일도 읽는 파일로 본다
    OgScratch s("variants");
    const std::string m = s.put("d/main.k", "*KEYWORD\n*INCLUDE_TRANSFORM\nt.k\n0,0,0,0,0,0,0\n0,0,0,0,0,0,0\n1.0,1.0,1.0,1.0\n0\n*END\n");
    s.put("d/t.k", "*KEYWORD\n*NODE\n*END\n");
    const auto in = output_guard::modelInputs(m);
    ASSERT_EQ(in.size(), (size_t)2);
    ASSERT_EQ(fs::path(in[1].path).filename().string(), std::string("t.k"));
    ASSERT_EQ(in[1].role, std::string("model 의 *INCLUDE_TRANSFORM 파일"));
    std::string why;
    ASSERT_TRUE(output_guard::findClash({s.at("d/t.k")}, in, why));
}

TEST(OutputGuard_findClash_는_모델_인클루드_철자_링크를_잡고_두_경로를_적는다) {
    OgScratch s("clash");
    const std::string m = s.put("d/main.k", "*KEYWORD\n*INCLUDE\ninc.k\n*END\n");
    const std::string inc = s.put("d/inc.k", "*KEYWORD\n*NODE\n*END\n");
    const auto reads = output_guard::modelInputs(m);
    std::string why;
    // 모델 그대로 · `../` 철자 · 인클루드
    ASSERT_TRUE(output_guard::findClash({m}, reads, why));
    ASSERT_TRUE(why.find(m) != std::string::npos);
    ASSERT_TRUE(why.find("(model)") != std::string::npos);
    const std::string dotdot = (s.root / "d" / ".." / "d" / "inc.k").string();
    ASSERT_TRUE(output_guard::findClash({dotdot}, reads, why));
    ASSERT_TRUE(why.find(dotdot) != std::string::npos && why.find(inc) != std::string::npos);
    ASSERT_TRUE(why.find("인클루드") != std::string::npos);
    // 하드 링크 · 심볼릭 링크(가리키는 파일) · 심볼릭 링크로 들어간 폴더 안의 아직 없는 이름이 아니라 모델 자리
    fs::create_hard_link(inc, s.at("d/hard.k"));
    ASSERT_TRUE(output_guard::findClash({s.at("d/hard.k")}, reads, why));
    fs::create_symlink(m, s.at("d/sym.k"));
    ASSERT_TRUE(output_guard::findClash({s.at("d/sym.k")}, reads, why));
    fs::create_directory_symlink(s.root / "d", s.at("dl"));
    ASSERT_TRUE(output_guard::findClash({s.at("dl/main.k")}, reads, why));
    // 거절하지 않는 것 — 다른 폴더의 같은 이름 · 상관없는 기존 파일 · 아직 없는 새 이름 · 빈 경로
    s.put("other/main.k", "*KEYWORD\n*END\n");
    ASSERT_FALSE(output_guard::findClash({s.at("other/main.k")}, reads, why));
    ASSERT_FALSE(output_guard::findClash({s.at("other/inc.k")}, reads, why));
    const std::string unrelated = s.put("d/old_result.k", "*KEYWORD\n*END\n");
    ASSERT_FALSE(output_guard::findClash({unrelated, s.at("d/new.k"), std::string()}, reads, why));
}

TEST(OutputGuard_findClash_는_쓸_파일끼리_겹친_것과_다른_입력과_설정을_잡는다) {
    OgScratch s("writes");
    const std::string m = s.put("d/main.k", "*KEYWORD\n*END\n");
    const std::string dyn = s.put("d/dyn.k", "*KEYWORD\n*END\n");
    std::vector<output_guard::Input> reads = output_guard::modelInputs(m);
    reads.push_back({dyn, "dynain"});
    std::string why;
    ASSERT_TRUE(output_guard::findClash({s.at("d/out.k"), dyn}, reads, why));
    ASSERT_TRUE(why.find("(dynain)") != std::string::npos);
    // 쓸 파일끼리 — 아직 없는 같은 이름(철자만 다르다)
    ASSERT_TRUE(output_guard::findClash({s.at("d/o.k"), (s.root / "d" / "." / "o.k").string()}, reads, why));
    ASSERT_TRUE(why.find("하나가 다른 하나를 덮는다") != std::string::npos);
    // 설정은 main 이 적어 둔 것을 모든 관문이 본다
    const std::string cfg = s.put("d/c.yaml", "model: main.k\n");
    ASSERT_FALSE(output_guard::findClash({cfg}, reads, why));
    output_guard::noteConfig(cfg);
    output_guard::noteConfig((s.root / "d" / "." / "c.yaml").string());   // 같은 파일은 한 번만 적는다
    ASSERT_EQ(output_guard::configs().size(), (size_t)1);
    ASSERT_TRUE(output_guard::findClash({cfg}, reads, why));
    ASSERT_TRUE(why.find("설정 YAML") != std::string::npos);
    output_guard::clearConfigs();
    ASSERT_FALSE(output_guard::findClash({cfg}, reads, why));
}
