// linkage-fit 이 적은 군별 변환을 큰 덱에 찍는 op — 조용히 빠지는 절점이 하나도 없어야 한다.
#include "applyfold.h"

#include "assembly/ModelAssembler.h"
#include "cli/ConsoleOutput.h"
#include "core/Mesh.h"
#include "core/Vector3D.h"
#include "parser/KFileReader.h"
#include "util/YamlComment.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <vector>

using KooRemapper::ConsoleOutput;
using KooRemapper::KFileReader;
using KooRemapper::Mesh;
using KooRemapper::Vector3D;
using KooRemapper::yamlStripComment;

namespace {

struct Group {
    std::set<int> parts;
    double angle = 0.0;
    Vector3D axis{0, 0, 1};
    Vector3D pivot{0, 0, 0};
    double slide = 0.0;
    int lineNo = 0;
};

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
}

std::string num(const char* f, double v) {
    char b[64];
    std::snprintf(b, sizeof(b), f, v);
    return std::string(b);
}

// "[1, 2, 3]" → {1,2,3}
bool parseIntList(const std::string& v, std::set<int>& out) {
    std::string s = trim(v);
    if (s.size() < 2 || s.front() != '[' || s.back() != ']') return false;
    s = s.substr(1, s.size() - 2);
    std::string tok;
    for (char ch : s + ",") {
        if (ch == ',') {
            const std::string t = trim(tok);
            if (!t.empty()) {
                try { out.insert(std::stoi(t)); } catch (const std::exception&) { return false; }
            }
            tok.clear();
        } else {
            tok.push_back(ch);
        }
    }
    return !out.empty();
}

// "[1.0, 2.0, 3.0]" → Vector3D
bool parseVec3(const std::string& v, Vector3D& out) {
    std::string s = trim(v);
    if (s.size() < 2 || s.front() != '[' || s.back() != ']') return false;
    s = s.substr(1, s.size() - 2);
    std::vector<double> xs;
    std::string tok;
    for (char ch : s + ",") {
        if (ch == ',') {
            const std::string t = trim(tok);
            if (!t.empty()) {
                try { xs.push_back(std::stod(t)); } catch (const std::exception&) { return false; }
            }
            tok.clear();
        } else {
            tok.push_back(ch);
        }
    }
    if (xs.size() != 3) return false;
    out = Vector3D(xs[0], xs[1], xs[2]);
    return true;
}

bool readGroups(const std::string& path, std::vector<Group>& groups, ConsoleOutput& console) {
    std::ifstream f(path);
    if (!f.is_open()) { console.error("Cannot open groups file: " + path); return false; }
    KooRemapper::yamlSkipBOM(f);
    std::string ln;
    int lineNo = 0;
    bool inGroups = false;
    while (std::getline(f, ln)) {
        lineNo++;
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        const std::string t = trim(yamlStripComment(ln));
        if (t.empty()) continue;
        if (t == "groups:") { inGroups = true; continue; }
        if (!inGroups) continue;

        std::string body = t;
        const bool isItem = (body.rfind("- ", 0) == 0);
        if (isItem) {
            groups.push_back(Group());
            groups.back().lineNo = lineNo;
            body = trim(body.substr(2));
        }
        if (groups.empty()) continue;
        const size_t cp = body.find(':');
        if (cp == std::string::npos) continue;
        const std::string key = trim(body.substr(0, cp));
        const std::string val = trim(body.substr(cp + 1));
        Group& g = groups.back();
        if (key == "parts") {
            if (!parseIntList(val, g.parts)) {
                console.error(path + ":" + std::to_string(lineNo) + " parts 를 읽을 수 없다: " + val);
                return false;
            }
        } else if (key == "angle") {
            try { g.angle = std::stod(val); } catch (const std::exception&) {
                console.error(path + ":" + std::to_string(lineNo) + " angle 을 읽을 수 없다"); return false; }
        } else if (key == "slide") {
            try { g.slide = std::stod(val); } catch (const std::exception&) {
                console.error(path + ":" + std::to_string(lineNo) + " slide 를 읽을 수 없다"); return false; }
        } else if (key == "axis") {
            if (!parseVec3(val, g.axis)) {
                console.error(path + ":" + std::to_string(lineNo) + " axis 를 읽을 수 없다: " + val);
                return false;
            }
        } else if (key == "pivot") {
            if (!parseVec3(val, g.pivot)) {
                console.error(path + ":" + std::to_string(lineNo) + " pivot 을 읽을 수 없다: " + val);
                return false;
            }
        }
        // translation·rms_residual 은 보고용이라 읽지 않는다
    }
    if (groups.empty()) { console.error("groups: 항목이 없다: " + path); return false; }
    for (const Group& g : groups) {
        if (g.parts.empty()) {
            console.error(path + ":" + std::to_string(g.lineNo) + " parts 가 비었다");
            return false;
        }
    }
    return true;
}

}  // namespace

int runApplyFold(const std::string& yamlFile, ConsoleOutput& console) {
    std::string model, groupsFile, output;
    {
        std::ifstream f(yamlFile);
        if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
        KooRemapper::yamlSkipBOM(f);
        std::string ln;
        while (std::getline(f, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            const std::string t = trim(ln);
            if (t.empty() || t[0] == '#') continue;
            const size_t cp = t.find(':');
            if (cp == std::string::npos) continue;
            const std::string key = trim(t.substr(0, cp));
            const std::string val = trim(yamlStripComment(t.substr(cp + 1)));
            if (val.empty()) continue;
            if      (key == "model")  model = val;
            else if (key == "groups") groupsFile = val;
            else if (key == "output") output = val;
            else console.warning("모르는 키는 무시한다: " + key);
        }
    }
    if (model.empty())      { console.error("model: 이 필요하다"); return 1; }
    if (groupsFile.empty()) { console.error("groups: (linkage-fit 산출 yaml)이 필요하다"); return 1; }
    if (output.empty())     { console.error("output: 이 필요하다"); return 1; }

    std::vector<Group> groups;
    if (!readGroups(groupsFile, groups, console)) return 1;

    console.header("Apply fold (per-group rigid transforms)");
    console.keyValue("Model", model);
    console.keyValue("Groups file", groupsFile);
    console.keyValue("Groups", std::to_string(groups.size()));

    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(model);
    } catch (const std::exception& e) {
        console.error("Failed to load model: " + std::string(e.what()));
        return 1;
    }

    // 파트별 절점 — 절점에는 파트가 없으니 요소에서 모은다
    std::map<int, std::set<int>> partNodes;
    for (const auto& [eid, e] : mesh.elements) {
        (void)eid;
        for (int nid : e.nodeIds)
            if (nid > 0) partNodes[e.partId].insert(nid);
    }

    // ★ 안전장치 ① — yaml 이 가리키는 파트가 덱에 **다 있나**
    std::vector<int> missingParts;
    for (const Group& g : groups)
        for (int pid : g.parts)
            if (partNodes.find(pid) == partNodes.end()) missingParts.push_back(pid);
    if (!missingParts.empty()) {
        std::string s;
        for (int pid : missingParts) s += (s.empty() ? "" : ", ") + std::to_string(pid);
        console.error("groups 가 가리키는 파트가 덱에 없다: " + s);
        console.info("  변환을 조용히 버리지 않는다 — 덱과 groups 가 맞는지 보라.");
        return 1;
    }

    // ★ 안전장치 ② — 두 군이 **같은 절점**을 나눠 가지면 접힘이 정의되지 않는다
    std::map<int, int> nodeGroup;   // nid -> group index
    long long shared = 0;
    for (size_t gi = 0; gi < groups.size(); ++gi) {
        for (int pid : groups[gi].parts) {
            for (int nid : partNodes[pid]) {
                auto it = nodeGroup.find(nid);
                if (it != nodeGroup.end() && it->second != (int)gi) shared++;
                else nodeGroup[nid] = (int)gi;
            }
        }
    }
    if (shared > 0) {
        console.error("두 군이 같은 절점 " + std::to_string(shared) +
                      "개를 나눠 가진다 — 어느 변환을 찍어야 할지 정의되지 않는다.");
        console.info("  그 파트들은 절점으로 붙어 있다. `disconnect` 로 떼고 다시 하라.");
        return 1;
    }

    auto [b0min, b0max] = mesh.getBoundingBox();

    KooRemapper::ModelAssembler asm_;
    if (!asm_.loadBaseModel(model)) { console.error(asm_.getErrorMessage()); return 1; }

    console.println("");
    console.println("  group   parts                 angle[deg]       slide     nodes moved");
    long long totalMoved = 0;
    for (size_t gi = 0; gi < groups.size(); ++gi) {
        const Group& g = groups[gi];
        long long moved = 0;
        if (!asm_.applyRigidTransform(g.parts, g.axis, g.angle, g.pivot, g.slide, &moved)) {
            console.error(asm_.getErrorMessage());
            return 1;
        }
        // ★ 안전장치 ③ — 그 군의 절점을 **전부** 옮겼나
        long long expect = 0;
        {
            std::set<int> u;
            for (int pid : g.parts) u.insert(partNodes[pid].begin(), partNodes[pid].end());
            expect = (long long)u.size();
        }
        std::string parts;
        for (int pid : g.parts) parts += (parts.empty() ? "" : ",") + std::to_string(pid);
        if (parts.size() > 20) parts = parts.substr(0, 17) + "...";
        char row[256];
        std::snprintf(row, sizeof(row), "%7zu   %-20s %12.6f %11.4g %15lld",
                      gi + 1, parts.c_str(), g.angle, g.slide, moved);
        console.println(row);
        if (moved != expect) {
            console.error("군 " + std::to_string(gi + 1) + ": 절점 " + std::to_string(expect) +
                          "개 중 " + std::to_string(moved) + "개만 옮겼다 — " +
                          std::to_string(expect - moved) + "개가 빠졌다.");
            return 1;
        }
        totalMoved += moved;
    }
    console.println("");

    if (!asm_.writeOutput(output)) { console.error(asm_.getErrorMessage()); return 1; }
    for (const auto& m : asm_.infoMessages) console.info(m);

    const std::string outDeck = output + ".k";
    Mesh after;
    try {
        after = reader.readFile(outDeck);
    } catch (const std::exception& e) {
        console.error("산출 덱을 되읽을 수 없다: " + std::string(e.what()));
        return 1;
    }

    // ★ 안전장치 ④ — 되읽어 절점 수가 같나. 하나라도 사라지면 실패다.
    if (after.getNodeCount() != mesh.getNodeCount()) {
        console.error("되읽은 절점 수가 다르다: " + std::to_string(mesh.getNodeCount()) +
                      " → " + std::to_string(after.getNodeCount()));
        return 1;
    }
    // 되읽은 좌표가 **요구한 변환과 같은가.** "움직였나" 로 보면 안 된다 — 회전축 위의 절점은
    // 제대로 변환해도 제자리에 남는다(45도 힌지 예제에서 축 위 절점 2개가 그렇다). 그래서
    // 기대 좌표를 다시 계산해 대조한다. 이것이 더 센 검사이기도 하다.
    const double modelSize = (b0max - b0min).magnitude();
    const double tol = 1e-6 * std::max(1.0, modelSize);
    double worstDev = 0.0;
    long long offTransform = 0, movedButShouldNot = 0;
    for (const auto& [nid, n] : mesh.nodes) {
        auto it = after.nodes.find(nid);
        if (it == after.nodes.end()) continue;
        auto gi = nodeGroup.find(nid);
        if (gi == nodeGroup.end()) {
            if ((it->second.position - n.position).magnitude() > tol) movedButShouldNot++;
            continue;
        }
        const Group& g = groups[gi->second];
        const double am = g.axis.magnitude();
        const Vector3D u = (am > 1e-12) ? g.axis * (1.0 / am) : Vector3D(0, 0, 1);
        const double t = g.angle * M_PI / 180.0;
        const double c = std::cos(t), sn = std::sin(t);
        const Vector3D v = n.position - g.pivot;
        const Vector3D want = v * c + u.cross(v) * sn + u * (u.dot(v) * (1.0 - c)) + g.pivot + u * g.slide;
        const double dev = (it->second.position - want).magnitude();
        worstDev = std::max(worstDev, dev);
        if (dev > tol) offTransform++;
    }
    console.keyValue("Nodes", std::to_string(mesh.getNodeCount()));
    console.keyValue("Nodes in a group", std::to_string((long long)nodeGroup.size()));
    console.keyValue("Nodes moved", std::to_string(totalMoved));
    console.keyValue("Max transform deviation", num("%.6g", worstDev) +
                     " (tol " + num("%.3g", tol) + ")");
    console.keyValue("Off-transform nodes", std::to_string(offTransform));
    console.keyValue("Moved but should not", std::to_string(movedButShouldNot));
    if (offTransform > 0 || movedButShouldNot > 0) {
        console.error("되읽은 좌표가 요구한 변환과 다르다 — 산출물을 믿지 말라.");
        return 1;
    }

    auto [b1min, b1max] = after.getBoundingBox();
    console.keyValue("bbox before", b0min.toString() + " .. " + b0max.toString());
    console.keyValue("bbox after", b1min.toString() + " .. " + b1max.toString());

    // 바이트 크기 — 고정폭이라 좌표만 바뀌면 크기가 같아야 한다
    std::ifstream fa(model, std::ios::binary | std::ios::ate);
    std::ifstream fb(outDeck, std::ios::binary | std::ios::ate);
    if (fa.is_open() && fb.is_open()) {
        const long long sa = (long long)fa.tellg(), sb = (long long)fb.tellg();
        console.keyValue("Byte size", std::to_string(sa) + " → " + std::to_string(sb));
        if (sa != sb)
            console.warning("바이트 크기가 달라졌다(" + num("%+lld", (double)(sb - sa)) +
                            ") — 좌표가 칸 폭을 넘었을 수 있다. 큰 좌표를 확인하라.");
    }

    console.success("Apply fold output: " + outDeck);
    return 0;
}
