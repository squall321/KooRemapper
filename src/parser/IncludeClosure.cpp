// 주 덱의 *INCLUDE 닫힘을 매뉴얼 규칙대로 읽는 구현 — 규칙과 그 근거는 헤더에 적었다
#include "parser/IncludeClosure.h"

#include "parser/DeckScan.h"
#include "parser/ElementCardLayout.h"   // deckFieldWidth — 폭이 주 덱과 갈리는지
#include "parser/KFileReader.h"         // 주 덱과 같은 리더로 센다

#include <algorithm>
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
    bool keepLines = true;                 // false = 차례와 경로만(`readPaths`) — 파일을 흘려 읽고 줄은 담지 않는다
    Closure out;
    std::vector<std::string> searchDirs;   // `*INCLUDE_PATH` — 읽은 차례로 쌓인다
    std::set<std::string> visited;

    // ⚠ `out.files` 는 재귀에서 늘어나 재할당된다 — 줄을 **참조로 잡고 재귀를 건너면 안 된다.**
    //   줄을 복사해 돌면 큰 인클루드에서 메모리가 두 배가 되므로(이 단위를 세운 까닭 중 하나다)
    //   색인으로 매번 다시 집는다.
    const std::vector<std::string>& linesOf(size_t idx) const {
        return idx == kMain ? *mainLines : out.files[idx].lines;
    }

    // `*INCLUDE` 계열 카드 하나 — `lines[at]` 이 키워드 줄이고 그 파일에서의 줄 번호는 `base + 색인`(0-기반)이다.
    // 이름을 먼저 다 뽑고 나서 따라간다(따라가면 `out.files` 가 늘어 `lines` 가 무효가 될 수 있다).
    void card(const std::string& file, const std::vector<std::string>& lines, size_t at, size_t base,
              size_t depth, const std::string& kw) {
        const auto names = namesFrom(lines, at + 1);
        if (kw.rfind("*INCLUDE_PATH", 0) == 0) {
            // 탐색 경로 — 카드를 끌어오지 않는다. `_RELATIVE` 는 입력 파일 위치 기준이고 맨
            // `_PATH` 의 상대경로도 로컬 디렉터리 기준이라 둘 다 주 덱 폴더에 붙는다.
            for (const auto& n : names) searchDirs.push_back(deckscan::joinPath(mainDir, n.name));
            return;
        }
        if (kw != "*INCLUDE") {
            out.notFollowed.push_back({file, base + at + 1, kw, names.empty() ? "" : names[0].name});
            return;
        }
        for (const auto& n : names) {
            ++out.cards;
            const std::string p = resolvePath(n.name, mainDir, searchDirs);
            if (p.empty()) {
                out.unresolved.push_back({file, base + n.line + 1, n.name, "없다"});
                continue;
            }
            if (depth + 1 > maxDepth) { out.depthCut = true; continue; }
            const std::string k = keyOf(p);
            if (visited.count(k)) { out.cycles.push_back(p); continue; }
            std::ifstream in(p);
            if (!in.is_open()) {
                out.unresolved.push_back({file, base + n.line + 1, n.name, "열 수 없다"});
                continue;
            }
            visited.insert(k);
            File f;
            f.path = p;
            f.depth = depth + 1;
            f.from = file;
            f.fromLine = base + at + 1;
            f.afterLine = base + n.last + 1;
            if (!keepLines) {
                out.files.push_back(std::move(f));
                walkStream(in, p, depth + 1);
                continue;
            }
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
            card(file, linesOf(idx), i, 0, depth, kw);
        }
    }

    // 같은 걸음을 **흘려 읽기**로 — 파일을 담지 않고 `*INCLUDE` 계열 카드 줄만 잠깐 모아 `card` 에 넘긴다.
    // 규칙(이름 · 찾는 차례 · `*END` · 깊이 · 순환)은 `walk` 와 하나다(`card` 를 같이 쓴다).
    void walkStream(std::istream& in, const std::string& file, size_t depth) {
        std::vector<std::string> blk;    // [키워드 줄, 그 뒤 줄들…] — 다음 키워드에서 넘긴다
        std::string blkKw;
        size_t blkAt = 0, ln = 0;
        auto flush = [&]() {
            if (!blk.empty()) card(file, blk, 0, blkAt, depth, blkKw);
            blk.clear();
        };
        std::string l;
        while (std::getline(in, l)) {
            if (!l.empty() && l.back() == '\r') l.pop_back();
            if (ln == 0 && l.size() >= 3 && l.compare(0, 3, "\xEF\xBB\xBF") == 0) l.erase(0, 3);
            const std::string kw = deckscan::isDataLine(l) ? std::string() : deckscan::keywordToken(l);
            if (!kw.empty() && kw[0] == '*') {
                flush();
                if (kw == "*END") return;                   // 이 파일은 여기서 끝난다(179654)
                if (kw.rfind("*INCLUDE", 0) == 0) { blk.push_back(l); blkKw = kw; blkAt = ln; }
            } else if (!blk.empty()) {
                blk.push_back(l);                           // 이름 줄 · 주석 · 빈 줄(`namesFrom` 이 가른다)
            }
            ++ln;
        }
        flush();
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

Closure readPaths(const std::string& mainPath, size_t maxDepth) {
    Walker w;
    w.mainPath = mainPath;
    w.mainDir = deckscan::dirOf(mainPath);
    w.maxDepth = maxDepth;
    w.keepLines = false;
    w.visited.insert(keyOf(mainPath));
    std::ifstream in(mainPath);
    if (!in.is_open()) {
        w.out.unresolved.push_back({mainPath, 0, mainPath, "열 수 없다"});
        return std::move(w.out);
    }
    w.walkStream(in, mainPath, 0);
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

ReaderMax readerMax(const std::vector<std::string>& mainLines, const std::string& mainPath, const Closure& c) {
    ReaderMax r;
    const int mainFw = deckFieldWidth(mainLines);
    auto plusMinusCard = [&r](const std::vector<std::string>& lines, const std::string& file) {
        for (size_t i = 0; i < lines.size(); ++i) {
            if (deckscan::isDataLine(lines[i]) || deckscan::keywordToken(lines[i]) != "*INCLUDE") continue;
            const std::string& l = lines[i];
            const size_t a = l.find_first_not_of(" \t");
            const size_t b = l.find_first_not_of(" \t", a + 8);          // "*INCLUDE" 뒤
            if (b != std::string::npos && (l[b] == '+' || l[b] == '-'))
                r.unsure.push_back(file + ":" + std::to_string(i + 1) + " 의 `*INCLUDE " + l[b] +
                                   "` — 그 파일의 폭을 바꾼다");
        }
    };
    if (c.files.empty()) return r;
    plusMinusCard(mainLines, mainPath);
    for (const auto& f : c.files) {
        plusMinusCard(f.lines, f.path);
        const int fw = deckFieldWidth(f.lines);
        if (fw != mainFw)
            r.unsure.push_back(f.path + " — `*KEYWORD` 의 폭(" + std::to_string(fw) + ")이 주 덱(" +
                               std::to_string(mainFw) + ")과 다르다");
        try {
            KFileReader reader;
            const Mesh m = reader.readFile(f.path);
            r.node = std::max(r.node, m.getMaxNodeId());
            r.elem = std::max(r.elem, m.getMaxElementId());
            for (const auto& [pid, part] : m.parts) {
                r.part = std::max(r.part, pid);
                r.partSection = std::max(r.partSection, part.sectionId);
            }
            for (const auto& [mid, mat] : m.materials) {
                (void)mat;
                r.material = std::max(r.material, mid);
            }
        } catch (const std::exception& e) {
            r.unsure.push_back(f.path + " — 메시로 읽지 못해 노드·요소·파트·재질 번호를 세지 못했다: " + e.what());
        }
    }
    return r;
}

}  // namespace include_closure
}  // namespace KooRemapper
