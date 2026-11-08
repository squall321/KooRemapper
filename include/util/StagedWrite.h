// 산출을 같은 폴더의 임시 파일에 쓰고 다 되면 제 이름으로 바꿔 넣는 공용 도우미(extract-parts · apply_carryover_plan)
#pragma once

#include <string>
#include <vector>

// 왜 이 파일이 있나 (2026-11-08).
//
//   extract-parts(a33af2f)와 apply_carryover_plan(0895025)이 「임시 파일에 쓰고 끝까지 지나면 바꿔 넣는다」 를 각자 사본(StagedFiles ·
//   CarryStagedFiles)으로 들고 있었다(이월 적용이 두 번째 소비자였다). 규칙을 이 한 곳에 둔다.

namespace KooRemapper {
namespace staged_write {

// 쓸 파일 묶음(산출 · 곁 파일 · 보고). 지우는 것은 이번 실행이 만든 임시 파일뿐이다 — 앞 파일 · 폴더 · 남의 파일은 건드리지 않는다.
// 사라질 때(실패로 돌아갈 때) 바꿔 넣지 않은 임시 파일을 지운다
class StagedFiles {
public:
    StagedFiles() = default;
    ~StagedFiles();
    StagedFiles(const StagedFiles&) = delete;
    StagedFiles& operator=(const StagedFiles&) = delete;

    // `dst` 의 임시 경로를 잡는다 — 같은 폴더(바꿔 넣기가 한 파일 시스템 안의 이름 바꾸기다) · 점으로 시작하는 이름. 쓰는 쪽은
    // `writePath` 에 쓴다. `suffix` 는 임시 이름의 끝이다(덱 쓰기가 <접두>.k 를 쓰면 ".k"). 실패면 false 와 까닭(`why`)
    bool reserve(const std::string& dst, const std::string& suffix, std::string& writePath, std::string& why);
    // 글을 임시 파일에 쓴다(바이너리 — 개행 그대로). 자리를 잡고(reserve) 쓰기까지 한다
    bool writeText(const std::string& dst, const std::string& text, std::string& why);
    // 임시 파일을 `dst` 로 바꿔 넣는다. 실패면 false 와 까닭(임시 파일은 남는다 — `discard` · 사라질 때 지운다)
    bool commit(const std::string& dst, std::string& why);
    // 바꿔 넣지 않은 임시 파일을 지운다 — 이번 실행이 만든 것뿐이다
    void discard(const std::string& dst);
    void discardAll();

private:
    struct Item {
        std::string dst, tmp;
    };
    std::vector<Item> items_;
};

}  // namespace staged_write
}  // namespace KooRemapper
