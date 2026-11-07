// 쓸 파일이 읽는 파일을 덮는지 묻는 공용 관문의 구현 — 까닭과 쓰는 법은 헤더에 적었다
#include "parser/OutputGuard.h"

#include "cli/ConsoleOutput.h"
#include "parser/IncludeClosure.h"

namespace KooRemapper {
namespace output_guard {
namespace {

std::vector<std::string>& configList() {
    static std::vector<std::string> v;
    return v;
}

}  // namespace

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
    for (const auto& f : include_closure::readPaths(modelPath).files) out.push_back({f.path, role + " 의 인클루드"});
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
    if (!include_closure::clobberPair(writes, paths, w, r)) return false;
    // `clobberPair` 는 짝의 두 번째를 받은 목록의 문자열 그대로 돌려준다 — 읽는 목록에 있으면 그 몫, 없으면 쓸 파일끼리 겹친 것이다
    for (size_t i = 0; i < paths.size(); ++i) {
        if (paths[i] != r) continue;
        why = "쓸 파일 「" + w + "」 이 읽는 파일 「" + r + "」(" + roles[i] + ") 과 같은 파일이다 — 입력을 덮어쓰지 않는다";
        return true;
    }
    why = "쓸 파일 「" + w + "」 과 「" + r + "」 이 같은 파일이다 — 하나가 다른 하나를 덮는다";
    return true;
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
