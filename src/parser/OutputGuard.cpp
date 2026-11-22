// 쓸 파일이 읽는 파일을 덮는지 묻는 공용 관문의 구현 — 까닭과 쓰는 법은 헤더에 적었다
#include "parser/OutputGuard.h"

#include "cli/ConsoleOutput.h"
#include "parser/IncludeClosure.h"

#include <filesystem>

namespace KooRemapper {
namespace output_guard {
namespace {

std::vector<std::string>& configList() {
    static std::vector<std::string> v;
    return v;
}

}  // namespace

std::vector<IncludeName> includeNamesOf(const include_closure::Closure& clo) {
    std::vector<IncludeName> names;
    for (const auto& r : clo.refs)
        names.push_back({r.name, r.what == include_closure::NameRef::What::Unresolved ? std::string() : r.path});
    for (const auto& u : clo.unresolved) names.push_back({u.name, std::string()});
    for (const auto& n : clo.notFollowed) names.push_back({n.name, n.path});
    return names;
}

void noteConfig(const std::string& path) {
    if (path.empty()) return;
    for (const auto& c : configList())
        if (include_closure::sameFile(c, path)) return;
    configList().push_back(path);
}

const std::vector<std::string>& configs() { return configList(); }

void clearConfigs() { configList().clear(); }

std::vector<Input> modelInputs(const std::string& modelPath, const std::string& role) {
    std::vector<Input> out;
    if (modelPath.empty()) return out;
    out.push_back({modelPath, role});
    const auto clo = include_closure::readPaths(modelPath);
    out.front().includeNames = includeNamesOf(clo);
    for (const auto& f : clo.files) out.push_back({f.path, role + " 의 인클루드"});
    // 이름이 가리킨 경로(깊이 상한을 넘은 것)와 따라가지 않는 변형 인클루드(`*INCLUDE_TRANSFORM` …)의 파일도 — 산출 덱이 그 카드를
    // 그대로 실으니 덮으면 산출이 가리키는 파일이 사라진다(셋째 묶음 — 실측: database · convert 가 output 을 그 파일로 주면 rc 0 으로
    // 덮었다. 흘려 읽는 셋 — extract-parts · cleanup-nodes · strip — 과 같은 목록이다)
    for (const auto& r : clo.refs)   // 따라간 이름 · 순환은 이미 `files` 에 있다
        if (r.what != include_closure::NameRef::What::Followed && r.what != include_closure::NameRef::What::Cycle && !r.path.empty())
            out.push_back({r.path, role + " 의 인클루드"});
    for (const auto& n : clo.notFollowed)
        if (!n.path.empty()) out.push_back({n.path, role + " 의 " + n.keyword + " 파일"});
    return out;
}

std::vector<Input> configAndModel(const std::string& configPath, const std::string& modelPath) {
    std::vector<Input> out;
    if (!configPath.empty()) out.push_back({configPath, "설정 YAML"});
    for (auto& in : modelInputs(modelPath)) out.push_back(std::move(in));
    return out;
}

bool findClash(const std::vector<std::string>& writes, const std::vector<Input>& reads, std::string& why) {
    std::vector<std::string> paths;
    std::vector<std::string> roles;
    for (const auto& r : reads) {
        if (r.path.empty()) continue;
        paths.push_back(r.path);
        roles.push_back(r.role);
    }
    for (const auto& c : configList()) {
        paths.push_back(c);
        roles.push_back("설정 YAML");
    }
    std::string w, r;
    if (!include_closure::clobberPair(writes, paths, w, r)) {
        // ★쓸 파일이 덱의 인클루드 이름 자리다(L-06) — 산출 폴더에서 그 이름을 먼저 찾으니 산출 덱이 자기를 끌어온다
        namespace fs = std::filesystem;
        for (const auto& wr : writes) {
            if (wr.empty() || fs::path(wr).extension() == ".dynain") continue;   // dynain 은 `*INCLUDE` 를 싣지 않는다
            const fs::path dir = fs::path(wr).parent_path();
            for (const auto& in : reads)
                for (const auto& n : in.includeNames) {
                    if (n.name.empty() || fs::path(n.name).is_absolute()) continue;
                    if (!include_closure::sameFile((dir / n.name).string(), wr)) continue;
                    // 그 이름이 원래 가리키던 파일이면 덮기다(읽는 파일과의 겹침 — 위 판정의 몫). 원래 다른 파일을 가리켰거나 못 찾은 이름이면
                    // 산출 덱의 그 카드가 산출 자신을 가리킨다
                    if (!n.path.empty() && include_closure::sameFile(n.path, wr)) continue;
                    const std::string was = n.path.empty() ? std::string("찾지 못한 이름") : "원래 " + n.path;
                    why = "쓸 파일 「" + wr + "」 이 " + in.role + " 이 끌어오는 인클루드 이름 「" + n.name + "」(" + was +
                          ") 자리다 — 산출 덱의 `*INCLUDE " + n.name + "` 를 LS-DYNA 는 덱 폴더에서 먼저 찾으므로 산출이 자기 자신을 끌어온다";
                    return true;
                }
        }
        return false;
    }
    // `clobberPair` 는 짝의 두 번째를 받은 목록의 문자열 그대로 돌려준다 — 읽는 목록에 있으면 그 몫, 없으면 쓸 파일끼리 겹친 것이다
    for (size_t i = 0; i < paths.size(); ++i) {
        if (paths[i] != r) continue;
        why = "쓸 파일 「" + w + "」 이 읽는 파일 「" + r + "」(" + roles[i] + ") 과 같은 파일이다 — 입력을 덮어쓰지 않는다";
        return true;
    }
    why = "쓸 파일 「" + w + "」 과 「" + r + "」 이 같은 파일이다 — 하나가 다른 하나를 덮는다";
    return true;
}

std::string nonRegularWhy(const std::string& path) {
    namespace fs = std::filesystem;
    std::error_code ec;
    const auto st = fs::status(path, ec);   // 링크를 따라간 끝
    if (ec || !fs::exists(st) || fs::is_regular_file(st)) return std::string();
    if (fs::is_character_file(st)) return "문자 장치";
    if (fs::is_block_file(st)) return "블록 장치";
    if (fs::is_fifo(st)) return "FIFO";
    if (fs::is_directory(st)) return "폴더";
    if (fs::is_socket(st)) return "소켓";
    return "보통 파일이 아닌 것";
}

bool refuse(const std::string& op, const std::vector<std::string>& writes, const std::vector<Input>& reads,
            const ConsoleOutput& console) {
    std::string why;
    if (!findClash(writes, reads, why)) return false;
    console.error("[" + op + "] " + why + "(아무 파일도 쓰지 않았다)");
    console.info("[" + op + "] output · report 같은 쓸 파일을 입력(설정 YAML · 모델 · 인클루드 · 다른 입력)과 다른 이름으로 주라");
    return true;
}

}  // namespace output_guard
}  // namespace KooRemapper
