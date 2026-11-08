// 산출을 같은 폴더의 임시 파일에 쓰고 다 되면 제 이름으로 바꿔 넣는 공용 도우미(extract-parts · apply_carryover_plan)
#pragma once

#include <string>
#include <vector>

// 왜 이 파일이 있나 (2026-11-08).
//
//   extract-parts(a33af2f)와 apply_carryover_plan(0895025)이 「임시 파일에 쓰고 끝까지 지나면 바꿔 넣는다」 를 각자 사본(StagedFiles ·
//   CarryStagedFiles)으로 들고 있었다(이월 적용이 두 번째 소비자였다). 규칙을 이 한 곳에 둔다.
//
// 임시 이름 — `.kr_tmp_<호스트>_<pid>_<시작>_<n>_<이름 해시><접미사>`. 산출 이름 길이와 무관하게 50 바이트 안쪽이다(예전
//   `.<이름>.kr_tmp_<시각>_<n>` 은 30 글자를 더해 NAME_MAX 가까운 산출 · 보고 이름이 모든 처리를 마친 뒤 보고 없이 실패했다).
//   <호스트> = 호스트 이름 · pid 이름공간의 해시 8 자리, <시작> = 그 프로세스의 시작 시각(리눅스 /proc 의 starttime, 16진 — 모르면 0),
//   <이름 해시> = 대상 파일 이름의 해시 8 자리. 이름만 보고 어느 산출의 것인지 · 주인 프로세스가 누구인지 안다.
// 죽은 실행 — SIGTERM · SIGINT · SIGHUP 을 받으면 이번 실행의 임시 파일을 지우고(미리 적어 둔 경로를 unlink — 신호 안전) 그 신호로
//   끝난다(무시하라던 신호는 그대로 둔다). SIGKILL 은 잡을 수 없다 — 다음 실행이 시작할 때 같은 산출의 주인 없는 임시 파일을 지운다
//   (`sweepStale`). 예전엔 취소(SIGTERM) · 시간 초과(SIGKILL)된 잡이 1.7–32 MB 의 임시 파일을 남겼고 다시 돌려도 아무도 치우지 않았다.

namespace KooRemapper {
namespace staged_write {

// 도우미가 남기는 말 — 부르는 쪽이 콘솔에 찍는다(warn 이면 [WARN], 아니면 [INFO])
struct Note {
    bool warn = false;
    std::string text;
};

// 쓸 자리 하나를 어떻게 쓰나 — `reserve` 가 대상의 꼴로 정한다(배포 판 752fa2b 은 산출 자리에 제자리로 썼다 — 그 꼴들을 되살린다)
enum class Mode {
    // 대상 폴더의 임시 파일에 쓰고 이름 바꾸기로 바꿔 넣는다(원자적 — 보통). 대상이 심볼릭 링크면 끝까지 따라간 파일 옆에 쓰고 그 파일로
    // 바꿔 넣는다(링크는 그대로 · 매달린 링크면 링크가 가리키는 자리에 만든다). 있던 파일의 권한 비트를 잇는다. 하드 링크 · 소유자 ·
    // ACL 은 잇지 않는다 — 새 파일로 바뀌므로 다른 하드 링크 이름은 앞 내용을 그대로 가리킨다. 쓸 수 없는 파일(읽기 전용)은 거절한다
    Rename,
    // 대상 폴더에 새 파일을 만들 수 없다(읽기 전용 폴더 등) — 있는 일반 파일에 쓸 수 있으면 시스템 임시 폴더에 써 두었다가 바꿔 넣을 때
    // 그 파일에 제자리로 옮겨 쓴다. **원자적이 아니다**(옮겨 쓰는 사이에 멈추면 반쯤 쓴 파일이 남는다 — 그 말을 [WARN] 으로 남긴다)
    InPlace,
    // 대상이 일반 파일이 아니다(문자 장치 · FIFO · 소켓 — `/dev/null`) — 대상에 바로 쓴다. 임시 파일이 없고 바꿔 넣지도 지우지도 않는다
    Direct,
};

// 쓸 파일 묶음(산출 · 곁 파일 · 보고). 지우는 것은 이번 실행이 만든 임시 파일뿐이다 — 앞 파일 · 폴더 · 남의 파일은 건드리지 않는다.
// 사라질 때(실패로 돌아갈 때) 바꿔 넣지 않은 임시 파일을 지운다
class StagedFiles {
public:
    StagedFiles() = default;
    ~StagedFiles();
    StagedFiles(const StagedFiles&) = delete;
    StagedFiles& operator=(const StagedFiles&) = delete;

    // `dst` 를 쓸 자리를 잡는다 — 쓰는 쪽은 `writePath` 에 쓴다(Rename · InPlace 는 비어 있는 임시 파일, Direct 는 `dst` 그 자체).
    // `suffix` 는 임시 이름의 끝이다(덱 쓰기가 <접두>.k 를 쓰면 ".k"). 같은 `dst` 를 다시 잡으면 앞 임시 파일은 버린다.
    // 실패면 false 와 까닭(`why` — 대상이 폴더 · 쓸 수 없는 파일 · 폴더가 없다 …). InPlace 면 [WARN] 한 줄이 `takeNotes` 에 쌓인다
    bool reserve(const std::string& dst, const std::string& suffix, std::string& writePath, std::string& why);
    // 글을 쓴다(바이너리 — 개행 그대로). 자리를 잡고(reserve) 쓰기까지 한다
    bool writeText(const std::string& dst, const std::string& text, std::string& why);
    // 바꿔 넣는다. Rename — 대상이 일반 파일이 아니게 됐으면(장치 · FIFO · 폴더) 그 위로 바꿔 넣지 않는다(root 여도). 이름 바꾸기를
    // 폴더 권한이 막으면(EACCES · EPERM) 있는 일반 파일에 제자리로 옮겨 쓴다([WARN] 원자적이 아님). InPlace — 제자리로 옮겨 쓴다.
    // Direct — 할 일이 없다. 실패면 false 와 까닭(임시 파일은 남는다 — `discard` · 사라질 때 지운다)
    bool commit(const std::string& dst, std::string& why);
    // 바꿔 넣지 않은 임시 파일을 지운다 — 이번 실행이 만든 것뿐이다(Direct 의 대상은 지우지 않는다)
    void discard(const std::string& dst);
    void discardAll();
    bool has(const std::string& dst) const;
    Mode mode(const std::string& dst) const;   // 잡지 않은 자리는 Rename
    // 쌓인 말을 꺼낸다(꺼내면 비운다)
    std::vector<Note> takeNotes();

private:
    struct Item {
        std::string dst, target, tmp;
        Mode mode = Mode::Rename;
        bool existed = false;   // 잡을 때 대상이 있었다 — 바꿔 넣을 때 그 권한 비트를 잇는다
        unsigned perm = 0;
        int slot = -1;          // 신호 때 지울 경로 표의 자리
    };
    std::vector<Item> items_;
    std::vector<Note> notes_;
};

// 앞 실행이 죽으며 남긴 임시 파일을 지운다 — `dst` 의 것(같은 폴더 · 같은 대상 이름 해시)이고, 같은 호스트 · pid 이름공간에서 그 주인
// 프로세스가 없을 때만(pid 가 없거나 그 번호를 다른 프로세스가 물려받았다 — 시작 시각이 다르다). 산 프로세스의 것 · 다른 호스트의 것 ·
// 다른 산출의 것 · 옛 꼴 이름은 건드리지 않는다. 지운 수를 돌려주고 지웠으면 `notes` 에 [INFO] 한 줄
int sweepStale(const std::string& dst, std::vector<Note>* notes = nullptr);

// 시험이 이름 꼴을 잰다 — 이 프로세스(또는 준 주인)의 임시 이름 · 그 이름을 읽은 값
namespace detail {
struct Owner {
    std::string host;              // 8 자리 16진
    long pid = 0;
    unsigned long long start = 0;  // 0 = 모른다
};
Owner self();
std::string nameHash(const std::string& targetBase);
std::string tempBaseName(const Owner& o, unsigned long long n, const std::string& targetBase, const std::string& suffix);
bool parseTempName(const std::string& name, Owner& o, std::string& nameHash);
}  // namespace detail

}  // namespace staged_write
}  // namespace KooRemapper
