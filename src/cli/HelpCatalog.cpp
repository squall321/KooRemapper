// help 카탈로그 검색·출력 로직 — 데이터 본체는 HelpCatalogData.inc (tools/help/gen_help_cpp.py 가 생성)
#include "cli/HelpCatalog.h"

#include <algorithm>
#include <cctype>
#include <sstream>

namespace KooRemapper {
namespace help {

#include "HelpCatalogData.inc"

const std::vector<OpHelp>& catalog() {
    return kOpHelps;
}

namespace {

std::string lower(const std::string& s) {
    std::string r = s;
    std::transform(r.begin(), r.end(), r.begin(), [](unsigned char c) { return (char)std::tolower(c); });
    return r;
}

std::vector<std::string> tokens(const std::string& s) {
    std::vector<std::string> out;
    std::istringstream is(s);
    std::string t;
    while (is >> t) out.push_back(lower(t));
    return out;
}

const char* kBar = "==============================================================================";

} // namespace

const OpHelp* find(const std::string& name) {
    std::string q = lower(name);
    for (const auto& op : kOpHelps) {
        if (q == op.name) return &op;
    }
    return nullptr;  // 별칭은 여러 op 에 걸칠 수 있어 search 로만 찾는다
}

std::vector<const OpHelp*> search(const std::string& query) {
    std::vector<std::pair<int, const OpHelp*>> scored;
    auto toks = tokens(query);
    if (toks.empty()) return {};
    for (const auto& op : kOpHelps) {
        std::string name = op.name;
        std::string alias = lower(op.aliases);
        std::string summary = lower(std::string(op.summary) + " " + op.category + " " + op.usage);
        int total = 0;
        bool all = true;
        for (const auto& t : toks) {
            int best = 0;
            if (name == t) best = 100;
            else if (name.find(t) != std::string::npos) best = 60;
            else if ((" " + alias + " ").find(" " + t + " ") != std::string::npos) best = 50;
            else if (alias.find(t) != std::string::npos) best = 40;
            else if (summary.find(t) != std::string::npos) best = 15;
            if (best == 0) { all = false; break; }
            total += best;
        }
        if (all) scored.push_back({total, &op});
    }
    std::stable_sort(scored.begin(), scored.end(),
                     [](const auto& a, const auto& b) { return a.first > b.first; });
    std::vector<const OpHelp*> out;
    for (const auto& s : scored) out.push_back(s.second);
    return out;
}

void printOverview(std::ostream& os, const std::string& version) {
    os << "KooRemapper " << version << " — LS-DYNA .k 메시·재질 변환 CLI (" << kOpHelps.size() << " op)\n\n";
    os << "사용법\n";
    os << "  KooRemapper <op> [인자]           op 대부분은 <config.yaml> 하나를 받는다\n";
    os << "  KooRemapper help <op>             상세 + 빈 폴더에서 그대로 돌아가는 사례\n";
    os << "  KooRemapper <op> --help           위와 같음\n";
    os << "  KooRemapper help <검색어...>      이름·별칭·설명 검색 (한글 가능: 초기응력, 접촉, 재질)\n";
    os << "  KooRemapper help all              전 op 상세 (LLM 이 한 번에 읽기용)\n\n";
    std::vector<std::string> cats;
    for (const auto& op : kOpHelps) {
        if (std::find(cats.begin(), cats.end(), op.category) == cats.end()) cats.push_back(op.category);
    }
    for (const auto& c : cats) {
        os << "  [" << c << "]\n";
        for (const auto& op : kOpHelps) {
            if (c != op.category) continue;
            std::string n = op.name;
            n.resize(std::max<size_t>(n.size(), 16), ' ');
            os << "    " << n << " " << op.summary << "\n";
        }
    }
    os << "\n공통 규칙\n";
    os << "  - YAML 의 model/base_model 로 입력, output 으로 출력 이름 (확장자 생략 op 는 .k 가 붙는다)\n";
    os << "  - 명령줄에 준 경로만 작업 폴더 기준. 모든 op 은 YAML 안의 상대 경로\n";
    os << "    (model/base_model/output/dat_file/dynain…)를 그 YAML 파일이 있는 폴더 기준으로 푼다 —\n";
    os << "    폴더가 붙은 상대 경로(../data/box.k)도 같고, 작업 폴더로 되돌아가지 않는다\n";
    os << "    (KooRemapper strip cfg/strip.yaml 의 output: ../data/box_stripped.k → cfg/../data/box_stripped.k)\n";
    os << "  - matdb 의 database 도 YAML 폴더 기준이다. 그 자리에 없고 폴더 없는 이름이면 번들에서 찾는다\n";
    os << "    (키를 생략하면 번들 materials/material_db.json). 폴더가 붙은 상대 경로는 번들로 넘어가지 않는다\n";
    os << "  - battery 의 dynain_file 은 경로가 아니라 *INCLUDE_DYNAIN 에 그대로 찍히는 문자열이다\n";
    os << "    (KooRemapper 는 열지 않는다 — 산출 덱 옆에서 솔버가 찾을 이름으로 적을 것)\n";
    os << "  - 남은 예외: map 의 bent/flat/output 은 아직 작업 폴더 기준이다\n";
    os << "  - 단독 op 명령은 operations 항목이 2개 이상인 YAML 을 거절하고 종료 코드 1 (assemble 로 실행할 것)\n";
    os << "  - 값 뒤 '# 주석' 은 떼어내고 값을 감싼 따옴표도 벗긴다. 따옴표 안의 '#' 는 값으로 남는다\n";
    os << "  - 실패하면 [ERROR] 줄을 찍고 종료 코드 1\n";
    os << "  - SIF 안 경로: /opt/kooremapper/bin/KooRemapper, 번들 재질 DB /opt/kooremapper/materials/material_db.json\n";
}

void printHeader(std::ostream& os, const OpHelp& op) {
    os << kBar << "\n" << op.name << " — " << op.summary << "   [" << op.category << "]\n" << kBar << "\n";
    os << "검색어: " << op.aliases << "\n\n사용법\n";
    std::istringstream is(op.usage);
    std::string line;
    while (std::getline(is, line)) os << "  " << line << "\n";
}

void printExample(std::ostream& os, const OpHelp& op) {
    if (!op.cmds.empty()) {
        os << "\n사례 — 빈 폴더에서 파일을 만들고 명령을 순서대로 실행\n";
        os << "-----8<----- 여기부터 그대로 복사 -----8<-----\n";
        for (const auto& f : op.files) {
            os << "--- 파일: " << f.name << " ---\n" << f.content;
        }
        for (const auto* c : op.cmds) os << "$ " << c << "\n";
        os << "-----8<----- 여기까지 ------------------------8<-----\n";
    }
    if (!op.needs.empty()) {
        os << "필요한 입력 (KooRemapper 저장소 예제 파일 — 같은 형식의 자기 모델로 바꿔 쓸 것)\n";
        for (const auto* n : op.needs) os << "  " << n << "\n";
    }
    if (!op.notes.empty()) {
        os << "\n주의\n";
        for (const auto* n : op.notes) os << "  - " << n << "\n";
    }
}

} // namespace help
} // namespace KooRemapper
