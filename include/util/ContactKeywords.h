// 단독 contact 와 assemble 의 contact create 가 같은 *CONTACT 키워드 집합을 보도록 목록을 한곳에 모은다
#pragma once

#include <string>

namespace KooRemapper {

// KooRemapper 가 내는 카드 구성(카드 1·2·3 + 선택 THERMAL/TIEBREAK)과 맞는 *CONTACT 키워드.
// LS-DYNA 의 접촉 키워드는 이보다 훨씬 많고 판마다 늘어나므로 이 목록은 '허용값 검증' 이 아니라
// '오타 경고' 의 기준이다 — 목록에 없는 값도 대문자로 그대로 내보낸다. examples/contact/README.md 이
// 약속한 통과 규칙이고, KooRemapper 자신이 cclip 에서 쓰는 AUTOMATIC_NODES_TO_SURFACE 처럼
// 목록을 좁히면 바로 막히는 키워드가 있다.
inline bool ctKnownContactKeyword(const std::string& kw) {
    static const char* kKnown[] = {
        "SURFACE_TO_SURFACE",
        "ONE_WAY_SURFACE_TO_SURFACE",
        "NODES_TO_SURFACE",
        "SINGLE_SURFACE",
        "AUTOMATIC_SURFACE_TO_SURFACE",
        "AUTOMATIC_SURFACE_TO_SURFACE_MORTAR",
        "AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK",
        "AUTOMATIC_ONE_WAY_SURFACE_TO_SURFACE",
        "AUTOMATIC_SINGLE_SURFACE",
        "AUTOMATIC_SINGLE_SURFACE_MORTAR",
        "AUTOMATIC_NODES_TO_SURFACE",
        "AUTOMATIC_GENERAL",
        "TIED_SURFACE_TO_SURFACE",
        "TIED_SURFACE_TO_SURFACE_OFFSET",
        "TIED_SURFACE_TO_SURFACE_FAILURE",
        "TIED_SURFACE_TO_SURFACE_MORTAR",
        "TIED_SURFACE_TO_SURFACE_THERMAL",
        "TIED_NODES_TO_SURFACE",
        "TIED_NODES_TO_SURFACE_OFFSET",
        "TIED_SHELL_EDGE_TO_SURFACE",
        "TIED_SHELL_EDGE_TO_SURFACE_OFFSET",
        "ERODING_SURFACE_TO_SURFACE",
        "ERODING_SINGLE_SURFACE",
        "ERODING_NODES_TO_SURFACE",
        "FORMING_SURFACE_TO_SURFACE",
        "FORMING_ONE_WAY_SURFACE_TO_SURFACE",
        "FORMING_NODES_TO_SURFACE"
    };
    for (const char* k : kKnown) if (kw == k) return true;
    return false;
}

// 목록에 없는 값을 쓸 때의 경고 — 막지는 않고 그대로 쓴다고 알린다(단독 contact·assemble 공용).
inline std::string ctUnknownContactKeywordWarning(const std::string& given, const std::string& keyword) {
    return "[contact] create: type '" + given + "' is not a known contact keyword — "
           "writing *CONTACT_" + keyword + " as-is (LS-DYNA will reject it if the keyword does not exist). "
           "Short names: auto, automatic, tied, tied_thermal, thermal, tiebreak, mortar, tied_mortar, "
           "single, eroding, forming";
}

}  // namespace KooRemapper
