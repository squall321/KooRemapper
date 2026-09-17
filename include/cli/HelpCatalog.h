// op 별 한글 요약·용법·자체완결 사례 카탈로그와 help 검색·출력 (데이터는 tools/help/ops_help.py 에서 생성)
#pragma once

#include <ostream>
#include <string>
#include <vector>

namespace KooRemapper {
namespace help {

struct HelpFile {
    const char* name;
    const char* content;
};

struct OpHelp {
    const char* name;
    const char* category;
    const char* summary;
    const char* aliases;   // 공백 구분 검색어
    const char* usage;     // 여러 줄이면 \n
    std::vector<HelpFile> files;
    std::vector<const char*> cmds;
    std::vector<const char*> needs;
    std::vector<const char*> notes;
};

const std::vector<OpHelp>& catalog();

// op 이름 완전일치 (대소문자 무시). 없으면 nullptr
const OpHelp* find(const std::string& name);

// 모든 검색어가 이름·별칭·요약·분류 어딘가에 들어있는 op (점수 내림차순)
std::vector<const OpHelp*> search(const std::string& query);

// 전체 op 목록 (분류별) + help 사용법
void printOverview(std::ostream& os, const std::string& version);

// 상세 머리 (이름·요약·분류·용법)
void printHeader(std::ostream& os, const OpHelp& op);

// 사례 블록 + 필요한 입력 + 주의
void printExample(std::ostream& os, const OpHelp& op);

} // namespace help
} // namespace KooRemapper
