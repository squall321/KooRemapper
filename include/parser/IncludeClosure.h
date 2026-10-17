// 주 덱의 *INCLUDE 닫힘을 매뉴얼 규칙대로 읽는다 — 번호 발행과 참조 검사가 함께 쓰는 정본
#pragma once

#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace KooRemapper {
namespace include_closure {

// 왜 이 단위가 있나 (2026-10-15).
//
//   인클루드를 따라가는 구현이 이미 **넷**이었고 서로 달랐다.
//     · `cleanup_nodes` — 재귀·순환 감지는 있으나 상대경로를 **포함하는 파일의 폴더**로 풀고
//       못 읽은 파일을 **말없이** 넘긴다
//     · `modelmeta` — **한 단계만** 따라가고, `*INCLUDE_*` 를 전부 맨 `*INCLUDE` 처럼 읽는다
//       (`*INCLUDE_PATH` 의 디렉터리를 파일로 열고, `_TRANSFORM` 파일을 **오프셋 없이** 읽는다)
//     · `cclip` — 한 단계
//     · `IncludeScan` — 세기만 하고 읽지 않는다(그것이 그 단위의 목표였다)
//   그 사이에서 두 결함이 났다 — 번호 발행자가 인클루드에 쓰인 번호를 **다시 낼 수 있고**,
//   `info --strict` 가 인클루드 조각은 막으면서 **주 덱은 「단정 불가」로 안 본다**(실사용 study
//   덱 1,683장 실측 — 막힌 142장의 92% 가 조각, 인클루드를 가진 주 덱 83장은 한 장도 안 봤다).
//
// 따르는 규칙 — 매뉴얼 그대로(R16, Vol_I).
//   · 맨 `*INCLUDE` 는 이름 카드를 **여러 장** 받고 다음 키워드가 끝낸다            179253-179254
//   · 이름은 `␣+` 로 **세 줄까지** 잇는다(최대 236자)                                179670-179674
//   · 인클루드는 중첩된다                                                           179636-179638
//   · 인클루드 파일 안의 `*END` 는 **그 파일만** 끝낸다                               179654
//   · 찾는 순서 — **로컬 디렉터리 먼저**, 못 찾고 이름에 경로가 없으면 `*INCLUDE_PATH`
//     디렉터리. `_RELATIVE` 는 입력 파일 위치 기준                                     181591-181600
//   로컬 디렉터리 = **주 덱의 폴더**로 본다(LS-DYNA 는 덱 폴더에서 돈다). 중첩 인클루드도 하위
//   파일의 폴더가 아니라 거기서 찾는다 — 더 넓게 찾으면 LS-DYNA 가 못 찾을 덱을 괜찮다고 한다.
//
// 따라가지 않는 것 — **말한다**. 맨 `*INCLUDE` 가 아닌 인클루드 카드(`_TRANSFORM` 의 ID 오프셋
// IDNOFF·IDEOFF·IDPOFF·IDMOFF·IDSOFF…, `_BINARY`·`_NASTRAN`·`_AUTO_OFFSET`·`_STAMPED_*`…)는
// `notFollowed` 에 적는다. 오프셋을 모른 채 읽으면 번호가 **그럴듯하게 틀린다** — 가장 나쁜 꼴이다.
// (실사용 88장 · 카드 408장이 전부 맨 `*INCLUDE` 였다 — 2026-10-15.)

// 따라가지 않은 인클루드 카드.
struct NotFollowed {
    std::string file;      // 그 카드가 있던 파일
    size_t line = 0;       // 1-기반
    std::string keyword;   // 예: *INCLUDE_TRANSFORM
    std::string name;      // 카드가 가리킨 첫 이름(있으면)
};

// 찾지 못했거나 열지 못한 이름.
struct Unresolved {
    std::string file;      // 그 이름이 적힌 파일
    size_t line = 0;       // 1-기반
    std::string name;      // 적힌 그대로
    std::string why;       // "없다" · "열 수 없다"
};

// 인클루드된 파일 하나. **주 덱은 여기 없다** — 호출자가 이미 들고 있다(큰 덱에서 메모리를
// 두 배로 쓰지 않으려고).
struct File {
    std::string path;                 // 실제로 연 경로
    std::vector<std::string> lines;   // 첫 `*END` 앞까지(그 파일만 끝난다)
    size_t depth = 1;                 // 주 덱이 0, 주 덱이 직접 끌어온 파일이 1
    std::string from;                 // 끌어온 파일
    size_t fromLine = 0;              // 그 `*INCLUDE` 카드의 줄(1-기반)
    size_t afterLine = 0;             // `from` 에서 이 파일 이름의 **마지막** 줄(1-기반) — 펼칠 때 그 뒤에 넣는다
};

struct Closure {
    std::vector<File> files;                // LS-DYNA 가 읽는 차례(깊이 우선)
    std::vector<Unresolved> unresolved;
    std::vector<NotFollowed> notFollowed;
    std::vector<std::string> cycles;        // 다시 들어오려 한 경로 — 한 번만 읽는다
    bool depthCut = false;                  // 깊이 상한에 걸려 더 따라가지 않았다
    size_t cards = 0;                       // 따라간 맨 `*INCLUDE` 의 이름 수(주 덱 포함 전부)

    // 닫힘을 **다** 읽었나. 하나라도 못 봤으면 소비자는 「단정 불가」로 다뤄야 한다.
    bool complete() const { return unresolved.empty() && notFollowed.empty() && !depthCut; }
};

// 이름 카드를 모은다 — `lines[i]` 부터 다음 키워드 앞까지. `␣+` 이음은 한 이름으로 붙인다.
// `$` 주석과 빈 줄은 건너뛴다. 각 이름과 그 첫 줄(0-기반)을 돌려준다.
struct NameAt { std::string name; size_t line = 0; size_t last = 0; };   // line·last 는 0-기반(`␣+` 이음이면 last > line)
std::vector<NameAt> namesFrom(const std::vector<std::string>& lines, size_t i);

// 이름 하나를 찾는다 — 로컬 디렉터리(= `mainDir`) 먼저, 못 찾고 이름에 경로가 없을 때만 `searchDirs`
// (`*INCLUDE_PATH` 디렉터리, 적힌 차례)(Vol_I 181591). 못 찾으면 빈 문자열. 파일을 **담지 않는** 흘려
// 읽는 리더(`cleanup_nodes` — 2.32GB 덱 전제)도 이 규칙만은 같이 쓴다 — 규칙이 둘이면 갈린다.
std::string resolvePath(const std::string& name, const std::string& mainDir,
                        const std::vector<std::string>& searchDirs);

// 주 덱(`mainPath` 에서 읽은 `mainLines`)의 인클루드 닫힘을 읽는다.
Closure read(const std::string& mainPath, const std::vector<std::string>& mainLines,
             size_t maxDepth = 16);

// 같은 규칙으로 닫힘의 **차례와 경로만** 읽는다 — 주 덱과 인클루드 파일을 흘려 읽고 줄은 담지 않는다(`files[].lines` 는
// 비어 있다 — `flatten`·`readerMax` 에 넘기지 말라). 덱을 담지 않는 흘려 읽기 소비자(`cleanup_nodes` — 2.32GB 덱 전제)가
// 쓴다. 예전에는 그 소비자가 자기 재귀(8단)를 돌아 `␣+` 이음 이름을 못 읽고, **9단째 인클루드를 「읽었다」고 세면서 훑지
// 않아** 거기 요소가 쓰는 절점을 고아로 지웠다(2026-10-17 실측 — rc 0).
Closure readPaths(const std::string& mainPath, size_t maxDepth = 16);

// 닫힘을 **LS-DYNA 가 읽는 차례대로** 한 줄 벡터로 펼친다 — 각 인클루드 파일의 줄을 그 이름 줄 **바로
// 뒤에** 넣는다(중첩도 같은 규칙으로). 키워드를 훑는 소비자가 인클루드 안의 카드도 보게 하려는 것이다.
// `*INCLUDE` 카드와 이름 줄은 그대로 남긴다(줄을 지우면 소비자가 「이 덱에 인클루드가 있다」를 잃는다).
// 주 덱 줄은 전부, 인클루드 파일 줄은 그 파일의 첫 `*END` 앞까지(`read` 가 이미 그렇게 담았다).
std::vector<std::string> flatten(const std::vector<std::string>& mainLines, const std::string& mainPath,
                                 const Closure& c);

// ★닫힘을 **홀로 서는 한 덱**으로 펼친다(2026-10-17 · 고쳐 쓰는 op 의 `flatten_includes: true`). `flatten` 과 달리
// 맨 `*INCLUDE` 카드(키워드 줄 + 이름 줄 · 그 사이 주석)를 **지우고** 그 자리에 끌어온 파일의 본문을 LS-DYNA 가 읽는
// 차례로 넣는다(중첩도 같다). 인클루드 파일의 `*KEYWORD` 줄은 뺀다(폭은 주 덱이 정한다 — `readFileWithIncludes` 와 같은
// 규칙). 인클루드 파일 안의 `*END` 뒤는 이미 닫힘이 담지 않았다. 주 덱의 `*INCLUDE_PATH` 는 남긴다(가리킬 파일이 없어 무해).
// 펼칠 수 없으면 false 와 까닭 — 닫힘이 불완전하다(없는 파일 · `_TRANSFORM` 등 · 깊이) · 순환이 있다 · `*INCLUDE +`·`-`
// (그 파일의 폭을 바꾼다) · 인클루드 파일 `*KEYWORD` 의 폭이 주 덱과 다르다. 짐작해 펼치지 않는다.
bool inlined(const std::vector<std::string>& mainLines, const std::string& mainPath, const Closure& c,
             std::vector<std::string>& out, std::string& why);

// 닫힘의 인클루드 파일 가운데 그 PID 의 `*PART` 카드를 가진 첫 파일(없으면 빈 문자열) — 줄을 읽는 op 이 「대상이 인클루드
// 안에 있다 — `flatten_includes: true`」를 말하려고 쓴다(2026-10-17). `*PART` 계열 블록에서 PID·SECID 가 둘 다 양수인 줄을
// 카드 2 로 본다(리더의 `prescanPartSections` 와 같은 규칙). `read` 가 담은 줄을 본다(`readPaths` 판은 줄이 없다).
std::string partFile(const Closure& c, int pid);

// 펼친 덱을 **주 덱 옆** 임시 파일로 쓴다 — 줄을 읽는 op 이 그 경로를 그대로 읽게 하려는 것이다(상대 경로 기준인 폴더가 같다).
// 이름은 `.<줄기>.kr_flat_<시각>_<주소>.k` · 개행은 주 덱을 따른다. 소멸자가 지운다. 인클루드가 없으면 `active()` 가 거짓이고
// `path()` 는 주 덱 그대로다(파일을 쓰지 않는다). ⚠ `make` 를 부르기 전의 `path()` 는 비어 있다 — 부르는 쪽은
// `active()` 일 때만 경로를 바꿔 쓴다(2026-10-17 — 엔진 로더가 그 빈 경로를 열어 모든 op 이 멈춘 적이 있다).
class FlatDeck {
public:
    FlatDeck() = default;
    FlatDeck(const FlatDeck&) = delete;
    FlatDeck& operator=(const FlatDeck&) = delete;
    ~FlatDeck();
    // 주 덱을 읽어 닫힘을 펼친다. 펼칠 것이 없으면 true(활성 아님). 펼칠 수 없으면 false 와 까닭.
    bool make(const std::string& mainPath, std::string& why);
    bool active() const { return !tmp_.empty(); }
    const std::string& path() const { return active() ? tmp_ : main_; }
    size_t files() const { return files_; }     // 펼쳐 넣은 인클루드 파일 수
private:
    std::string main_, tmp_;
    size_t files_ = 0;
};

// 닫힘의 인클루드 파일마다 주 덱과 **같은 리더**(`KFileReader`)로 센 최대값 — 노드·요소·파트(·파트의 SECID)·재질.
// 번호 발행자가 「쪼갠 덱 = 쪼개지 않은 덱」이 되게 쓴다(주 덱은 부르는 쪽이 이미 같은 리더로 셌다).
// 노드·요소 번호를 단정할 수 없는 파일은 `unsure` 에 사람이 읽을 문장으로 적는다 —
//   · 그 파일 `*KEYWORD` 의 폭이 주 덱과 다르다(리더는 파일마다 자기 `*KEYWORD` 를 본다. LS-DYNA 는 폭을 실행줄·
//     주 덱 `*KEYWORD` 로 전체에 정하고 `*INCLUDE ±`·키워드 접미사로만 바꾼다 — Vol_I 19343-19353. 인클루드 자신의
//     `*KEYWORD` 옵션이 먹는지는 매뉴얼에 없다. 실사용 88장에서 갈린 덱 0)
//   · `*INCLUDE +`·`*INCLUDE -` 카드가 있다(그 파일의 폭을 바꾼다 — Vol_I 19350)
//   · 리더가 그 파일을 읽지 못했다
struct ReaderMax {
    int node = 0, elem = 0, part = 0, partSection = 0, material = 0;
    std::vector<std::string> unsure;
    // 인클루드 파일 안에 요소가 있는 PID → 그 첫 파일(2026-10-17) — 고쳐 쓰는 op 이 「대상이 인클루드 안에만 있다」를 알아보게
    std::map<int, std::string> elemPidFile;
};
ReaderMax readerMax(const std::vector<std::string>& mainLines, const std::string& mainPath, const Closure& c);

}  // namespace include_closure
}  // namespace KooRemapper
