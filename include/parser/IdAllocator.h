// 새 ID 를 한 길로 낸다 — 인클루드 닫힘까지 본 최대값 위로, 못 본 자리가 있으면 그렇다고 말한다
#pragma once

#include <map>
#include <string>
#include <vector>

#include "parser/IncludeClosure.h"

namespace KooRemapper {
namespace ids {

// 왜 이 단위가 있나 (2026-10-15, plan2 P1-3).
//
//   이 리포의 발행자는 저마다 "이 덱의 최대 ID + 1" 을 셌다 — 커서 규칙 7종 · 사용 자리 40곳.
//   그 분산이 이미 불법 덱을 커밋했다(`ld_findMaxSetSegmentId` 가 `_TITLE` 의 제목줄을 SID 로 읽어
//   SID 1 을 두 번 냈다). 그리고 **모두 주 덱 파일 하나만 셌다** — 인클루드에 이미 있는 번호를
//   다시 낼 수 있다. LS-DYNA 는 같은 종류의 ID 가 둘이면 키워드 단계에서 멈춘다.
//
// 이번 판에서 하는 것 — 첫 채택자(contact)가 이 길로 낸다.
//   · 번호는 **발행자가 자기 스캐너로 센** 최대값 위로 낸다. 첫 채택에서 번호가 한 글자도 바뀌지
//     않게 하려는 것이다(인클루드가 없으면 오늘과 같다). 스캐너를 하나로 모으는 것은 다음 단계다 —
//     그때는 발행자마다 차분 0 을 증명해야 한다.
//   · 인클루드 닫힘을 읽어 **그 안의 최대값도** 올린다(`include_closure`).
//   · 닫힘을 다 못 읽었으면 `blind` 에 적는다 — 그 안의 번호와 겹칠 수 있다고 **말하게** 한다.
//
// 하지 않는 것.
//   · 대역표 — 값도 소비자도 없다(P1-4 는 스코프 결정 대기). 검증할 덱이 없는 배치를 짓지 않는다.
//   · 사후 검사(`verify`) — 같은 종류 안의 ID 중복은 `info` 가 이미 본다(`ReferenceIntegrity`).
//   · 네임스페이스 입도 변경 — SET 은 **모든 종류를 한 통**으로 센다(contact 규약). 매뉴얼상 SET
//     네임스페이스는 종류별이지만 한 통이 더 보수적이고(겹칠 수 없다), 입도를 바꾸면 번호가 달라진다.

// 네임스페이스 — 지금 발행자가 쓰는 것만 둔다. 필요해질 때 더한다.
enum class Ns { Set, Contact };

inline const char* nameOf(Ns ns) { return ns == Ns::Set ? "SET" : "CONTACT"; }

// 이미 쓰인 번호와, 다 보지 못한 자리.
struct UsedIds {
    std::map<Ns, int> max;
    std::vector<std::string> blind;      // 못 본 자리 — 사람이 읽을 문장

    void raise(Ns ns, int v) {
        int& m = max[ns];
        if (v > m) m = v;
    }
    int maxOf(Ns ns) const {
        auto it = max.find(ns);
        return it == max.end() ? 0 : it->second;
    }
    bool complete() const { return blind.empty(); }

    // 닫힘을 다 읽지 못한 자리를 적는다. 그 안의 번호는 위 최대값에 **들어 있지 않다.**
    void noteClosure(const include_closure::Closure& c) {
        for (const auto& u : c.unresolved)
            blind.push_back(u.file + ":" + std::to_string(u.line) + " 의 *INCLUDE '" + u.name +
                            "' — " + u.why);
        for (const auto& n : c.notFollowed)
            blind.push_back(n.file + ":" + std::to_string(n.line) + " 의 " + n.keyword +
                            (n.name.empty() ? "" : " '" + n.name + "'") +
                            " — 따라가지 않았다(ID 오프셋 등 뜻을 확정하지 못한다)");
        if (c.depthCut) blind.push_back("인클루드 깊이 상한에 걸려 더 따라가지 않았다");
    }
};

// 한 길로 낸다 — 네임스페이스마다 본 최대값 위로 하나씩.
class IdAllocator {
public:
    explicit IdAllocator(UsedIds used) : used_(std::move(used)) {}

    int issue(Ns ns) {
        auto it = next_.find(ns);
        if (it == next_.end()) it = next_.emplace(ns, used_.maxOf(ns) + 1).first;
        return it->second++;
    }

    const UsedIds& used() const { return used_; }

private:
    UsedIds used_;
    std::map<Ns, int> next_;
};

}  // namespace ids
}  // namespace KooRemapper
