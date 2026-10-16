// 주 덱의 *INCLUDE 닫힘을 매뉴얼 규칙대로 읽는 구현 — 규칙과 그 근거는 헤더에 적었다
#include "parser/IncludeClosure.h"

#include "parser/DeckScan.h"

#include <filesystem>
#include <fstream>
#include <set>
#include <system_error>

namespace KooRemapper {
namespace include_closure {
namespace {

namespace fs = std::filesystem;

std::string trimBoth(const std::string& s) {
    const size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    const size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

bool hasPathPart(const std::string& name) {
    return name.find('/') != std::string::npos || name.find('\\') != std::string::npos;
}

bool isFile(const std::string& p) {
    std::error_code ec;
    return fs::is_regular_file(p, ec);
}

// 순환 감지용 열쇠. 실제 파일이면 정규 경로, 아니면 적힌 그대로.
std::string keyOf(const std::string& p) {
    std::error_code ec;
    const auto c = fs::weakly_canonical(p, ec);
    return ec ? p : c.string();
}


struct Walker {
    static constexpr size_t kMain = static_cast<size_t>(-1);
    std::string mainPath;
    std::string mainDir;
    const std::vector<std::string>* mainLines = nullptr;
    size_t maxDepth = 16;
    Closure out;
    std::vector<std::string> searchDirs;   // `*INCLUDE_PATH` — 읽은 차례로 쌓인다
    std::set<std::string> visited;

    // ⚠ `out.files` 는 재귀에서 늘어나 재할당된다 — 줄을 **참조로 잡고 재귀를 건너면 안 된다.**
    //   줄을 복사해 돌면 큰 인클루드에서 메모리가 두 배가 되므로(이 단위를 세운 까닭 중 하나다)
    //   색인으로 매번 다시 집는다.
    const std::vector<std::string>& linesOf(size_t idx) const {
        return idx == kMain ? *mainLines : out.files[idx].lines;
    }

    // 첫 `*END` 앞까지 훑으며 인클루드를 따라간다(깊이 우선 — LS-DYNA 가 읽는 차례).
    void walk(size_t idx, size_t depth) {
        const std::string file = idx == kMain ? mainPath : out.files[idx].path;
        for (size_t i = 0; i < linesOf(idx).size(); ++i) {
            const std::string kw = [&] {
                const std::string& l = linesOf(idx)[i];
                return deckscan::isDataLine(l) ? std::string() : deckscan::keywordToken(l);
            }();
            if (kw.empty() || kw[0] != '*') continue;
            if (kw == "*END") return;                       // 이 파일은 여기서 끝난다(179654)
            if (kw.rfind("*INCLUDE", 0) != 0) continue;

            const auto names = namesFrom(linesOf(idx), i + 1);
            if (kw.rfind("*INCLUDE_PATH", 0) == 0) {
                // 탐색 경로 — 카드를 끌어오지 않는다. `_RELATIVE` 는 입력 파일 위치 기준이고 맨
                // `_PATH` 의 상대경로도 로컬 디렉터리 기준이라 둘 다 주 덱 폴더에 붙는다.
                for (const auto& n : names) searchDirs.push_back(deckscan::joinPath(mainDir, n.name));
                continue;
            }
            if (kw != "*INCLUDE") {
                out.notFollowed.push_back({file, i + 1, kw, names.empty() ? "" : names[0].name});
                continue;
            }
            for (const auto& n : names) {
                ++out.cards;
                const std::string p = resolvePath(n.name, mainDir, searchDirs);
                if (p.empty()) {
                    out.unresolved.push_back({file, n.line + 1, n.name, "없다"});
                    continue;
                }
                if (depth + 1 > maxDepth) { out.depthCut = true; continue; }
                const std::string k = keyOf(p);
                if (visited.count(k)) { out.cycles.push_back(p); continue; }
                std::ifstream in(p);
                if (!in.is_open()) {
                    out.unresolved.push_back({file, n.line + 1, n.name, "열 수 없다"});
                    continue;
                }
                visited.insert(k);
                File f;
                f.path = p;
                f.depth = depth + 1;
                f.from = file;
                f.fromLine = i + 1;
                f.afterLine = n.last + 1;
                std::string l;
                while (std::getline(in, l)) {
                    if (!l.empty() && l.back() == '\r') l.pop_back();
                    if (!deckscan::isDataLine(l) && deckscan::keywordToken(l) == "*END") break;
                    f.lines.push_back(std::move(l));
                }
                out.files.push_back(std::move(f));
                walk(out.files.size() - 1, depth + 1);
            }
        }
    }
};

}  // namespace

// Vol_I 181591 — 로컬 디렉터리(= 주 덱 폴더) 먼저. 못 찾고 이름에 경로가 없을 때만
// `*INCLUDE_PATH` 디렉터리를 적힌 차례로 본다.
std::string resolvePath(const std::string& name, const std::string& mainDir,
                        const std::vector<std::string>& searchDirs) {
    const std::string local = deckscan::joinPath(mainDir, name);
    if (isFile(local)) return local;
    if (hasPathPart(name)) return "";
    for (const auto& d : searchDirs) {
        const std::string c = deckscan::joinPath(d, name);
        if (isFile(c)) return c;
    }
    return "";
}

std::vector<NameAt> namesFrom(const std::vector<std::string>& lines, size_t i) {
    std::vector<NameAt> out;
    while (i < lines.size()) {
        const std::string t = trimBoth(lines[i]);
        if (!t.empty() && t[0] == '*') break;               // 다음 키워드가 끝낸다(179253)
        if (t.empty() || t[0] == '$') { ++i; continue; }
        NameAt n;
        n.line = i;
        std::string part = t;
        // `␣+` 로 끝나면 다음 줄이 이어진다 — 세 줄까지(Vol_I 179670: 78 + 78 + 80 = 236자).
        for (int k = 1; k < 3 && part.size() >= 2 && part.compare(part.size() - 2, 2, " +") == 0
                        && i + 1 < lines.size(); ++k) {
            const std::string next = trimBoth(lines[i + 1]);
            if (!next.empty() && next[0] == '*') break;
            n.name += part.substr(0, part.size() - 2);
            part = next;
            ++i;
        }
        n.name += part;
        n.last = i;
        out.push_back(std::move(n));
        ++i;
    }
    return out;
}

Closure read(const std::string& mainPath, const std::vector<std::string>& mainLines,
             size_t maxDepth) {
    Walker w;
    w.mainPath = mainPath;
    w.mainDir = deckscan::dirOf(mainPath);
    w.mainLines = &mainLines;
    w.maxDepth = maxDepth;
    w.visited.insert(keyOf(mainPath));
    w.walk(Walker::kMain, 0);
    return std::move(w.out);
}

namespace {

void spliceInto(std::vector<std::string>& out, const std::vector<std::string>& lines,
                const std::string& path, const Closure& c, size_t depth) {
    // 이 파일에서 끌어온 파일들 — 이름의 마지막 줄 뒤에 넣는다.
    std::vector<const File*> kids;
    for (const auto& f : c.files)
        if (f.depth == depth + 1 && f.from == path) kids.push_back(&f);
    size_t k = 0;
    for (size_t i = 0; i < lines.size(); ++i) {
        out.push_back(lines[i]);
        while (k < kids.size() && kids[k]->afterLine == i + 1) {
            spliceInto(out, kids[k]->lines, kids[k]->path, c, depth + 1);
            ++k;
        }
    }
}

}  // namespace

std::vector<std::string> flatten(const std::vector<std::string>& mainLines, const std::string& mainPath,
                                 const Closure& c) {
    std::vector<std::string> out;
    out.reserve(mainLines.size());
    spliceInto(out, mainLines, mainPath, c, 0);
    return out;
}

}  // namespace include_closure
}  // namespace KooRemapper
