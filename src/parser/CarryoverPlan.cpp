// StepForge 이월 계획 · 변위장 · 조각 · 새 셸 섹션의 엄격한 읽기와 적용 보고 JSON — 칸 표 하나(kKeys)가 판 1 · 2 계약이다
#include "parser/CarryoverPlan.h"

#include "parser/CardCut.h"
#include "parser/DeckScan.h"
#include "parser/ElementCardLayout.h"
#include "util/StrictJson.h"
#include "util/Utf8.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <set>
#include <sstream>
#include <string_view>

namespace KooRemapper {
namespace carryover {
namespace {

using json::Value;
using VT = Value::Type;

// ★계획의 칸 — **이 표 하나**가 정본이다(사용자 결정 11-07). 줄마다 판 1 의 칸과 판 2 가 더한 칸을 함께 적는다 —
//   판 1 은 앞 두 칸(required · optional)만, 판 2 는 넷 다(그쪽 요청서 §10.2 — 「판 2 는 판 1 의 칸을 뜻 그대로 두고 칸을 더했다」).
//   뒤 두 칸만 있는 묶음은 판 2 에만 있다(판 1 계획에서는 묻지 않는다 — 그 칸을 품은 위 묶음이 판 1 에서 모르는 칸으로 거절한다).
//   required 가 없으면 거절 · optional 은 있어도 된다 · 그 밖의 칸은 그 판에서 모르는 칸이라 거절한다.
enum class K {
    Top, Deck, DeckMax, Keep, Transform, Morph, Remesh, Delete, Review, Shared, Field, FieldFailed,
    LayoutCount, LayoutShape, Fragment, FragmentFailed, Ranges, NewSection, Added, FileEntry,
    PartDeck, Include, MorphSection, ElementThickness, RefusedTransform, Summary
};
struct KeySet {
    std::vector<const char*> required, optional;
};
struct KeyRow {
    std::vector<const char*> required, optional;     // 판 1(과 판 2)
    std::vector<const char*> required2, optional2;   // 판 2 가 더한 칸
};
const std::map<K, KeyRow>& kKeys() {
    static const std::vector<const char*> kRow = {"pid", "name", "action", "why", "mapping", "members"};
    auto row = [](std::vector<const char*> extra, std::vector<const char*> opt, std::vector<const char*> opt2 = {}) {
        std::vector<const char*> req = kRow;
        req.insert(req.end(), extra.begin(), extra.end());
        return KeyRow{req, opt, {"deck"}, opt2};   // 판 2 — 처리가 무엇이든 줄마다 그 PID 의 덱 자리(§10.2)
    };
    static const std::vector<const char*> kFieldKeys = {
        "file", "nodes", "bytes", "layout", "surface_nodes", "kinds", "max_disp", "faces", "face_pairs",
        "dropped_directions", "projection_fallbacks", "solver", "check"};
    static const std::vector<const char*> kFragmentKeys = {
        "ok", "file", "pid", "secid", "mid", "new_section", "ranges", "nodes", "elements", "bytes", "mesh", "target", "check"};
    auto plus = [](std::vector<const char*> a, std::vector<const char*> b) {
        a.insert(a.end(), b.begin(), b.end());
        return a;
    };
    auto only2 = [](std::vector<const char*> req) { return KeyRow{{}, {}, req, {}}; };
    static const std::map<K, KeyRow> t = {
        {K::Top, {{"format", "version", "unit", "frame", "deck", "report_key", "cad", "floor_mm", "summary", "parts", "added",
                   "files"},
                  {"code_build"}, {}, {}}},
        // 판 2 — 덱의 자리(raw · mesh)와 `*INCLUDE` 닫힘(늘 있다 · 없으면 빈 목록)
        {K::Deck, {{"project_id", "relpath", "sha256", "max", "unread_cards"}, {}, {"deck_from", "includes"}, {}}},
        // max 의 다섯 칸은 판 1 부터 있다 — 판 2 는 뜻만 넓혔다(닫힘 전체에서 센다 · §10.2)
        {K::DeckMax, {{"node", "elem", "pid", "secid", "mid"}, {}, {}, {}}},
        {K::Keep, row({}, {"absorbed", "touches_changed"})},
        // check 는 선택 — StepForge 는 덱 겉면이나 새 CAD 짝이 없으면 그 칸을 쓰지 않는다(`carryover_build.py` build — 리뷰 11-07)
        {K::Transform, row({"transform", "translation", "rotation_deg"}, {"check", "shared_nodes"})},
        {K::Morph, row({"field"}, {"instead", "shared_nodes"})},
        {K::Remesh, row({"fragment"}, {"shared_nodes"})},
        {K::Delete, row({}, {"shared_nodes"})},
        // 판 2 — 강체가 아닌 옮김은 review 로 오고 그 4×4 를 싣는다(transform · translation · rotation_deg · check · shared_nodes 는 없다)
        {K::Review, row({}, {}, {"refused_transform"})},
        {K::Shared, {{"nodes", "with"}, {}, {}, {}}},
        // 판 2 — new_section 은 늘 있다(null 일 수 있다 · 못 지은 변위장에도) · element_thickness 는 있을 때만
        {K::Field, {kFieldKeys, {"thickness"}, {"new_section"}, {"element_thickness"}}},
        {K::FieldFailed, {{"file", "why"}, plus(kFieldKeys, {"thickness"}), {"new_section"}, {"element_thickness"}}},
        {K::LayoutCount, {{"name", "dtype", "offset", "count"}, {"unit", "codes", "shared_bit"}, {}, {}}},
        {K::LayoutShape, {{"name", "dtype", "offset", "shape"}, {"unit", "codes", "shared_bit"}, {}, {}}},
        {K::Fragment, {kFragmentKeys, {}, {}, {}}},
        // 못 지은 조각 — StepForge 의 실제 꼴은 셋이다(`carryover_build.py` fragment): {ok, why} · {ok, why(null 일 수 있다), notes} ·
        // 지었으나 확인을 못 지난 조각 {ok, 조각 칸 전부, check{why · problems}} — why 가 없을 수 있다(리뷰 11-07)
        {K::FragmentFailed, {{"ok"}, plus(kFragmentKeys, {"why", "notes"}), {}, {}}},
        {K::Ranges, {{"node", "elem"}, {}, {}, {}}},
        {K::NewSection, {{"secid", "elform", "why"}, {"nip", "t"}, {}, {}}},
        {K::Added, {{"path", "name", "action", "suggestion", "fragment", "why"}, {"pid"}, {}, {}}},
        {K::FileEntry, {{"sha256", "bytes"}, {}, {}, {}}},
        // ── 판 2 에만 있는 묶음(요청서 §10.2) ──
        {K::PartDeck, only2({"node", "node_count", "elem", "elem_count", "contiguous", "secid", "mid"})},
        {K::Include, only2({"relpath", "sha256"})},
        {K::MorphSection, only2({"secid", "thickness", "file", "why"})},
        {K::ElementThickness, only2({"elements", "why"})},
        {K::RefusedTransform, only2({"transform", "det", "scale", "orthogonality_error"})},
        {K::Summary, only2({"actions", "added", "fields", "fragments", "sections", "failed"})},
    };
    return t;
}

// 그 판의 칸 — 판 1 이면 앞 두 칸, 아니면 넷 다(모르는 판은 가장 새 판의 표로 본다 — 판 거절은 따로 말한다)
KeySet keySetOf(K k, int version) {
    const KeyRow& r = kKeys().at(k);
    if (version == 1) return KeySet{r.required, r.optional};
    KeySet s{r.required, r.optional};
    s.required.insert(s.required.end(), r.required2.begin(), r.required2.end());
    s.optional.insert(s.optional.end(), r.optional2.begin(), r.optional2.end());
    return s;
}

bool isHex64(const std::string& s) {
    if (s.size() != 64) return false;
    for (char c : s)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

// 계획이 적은 동반 파일 이름 — 계획 폴더 바로 아래의 맨 이름만 받는다(`../` · 하위 폴더 · 절대 경로 거절)
bool plainName(const std::string& n) {
    if (n.empty() || n == "." || n == "..") return false;
    for (char c : n)
        if (c == '/' || c == '\\' || c == '\0' || c == ':') return false;
    return true;
}

// 걸린 것을 모으며 읽는다 — 틀린 칸 하나가 나머지 칸을 가리지 않게 각 읽기는 false 를 돌려줄 뿐 멈추지 않는다.
class Reader {
public:
    explicit Reader(std::vector<Problem>& out) : out_(out) {}
    size_t count() const { return out_.size(); }
    // 칸 표를 고를 판 — 계획의 version 이 1 이면 1, 아니면 2(모르는 판의 거절은 따로 말한다)
    void setVersion(int v) { version_ = v == 1 ? 1 : 2; }
    int version() const { return version_; }
    void bad(long long pid, const std::string& where, const std::string& what, const char* kind = "plan_schema") {
        out_.push_back({pid, kind, where + " — " + what});
    }
    // 객체인가 · 칸이 그 판의 표대로인가(모르는 칸 · 빠진 칸을 이름으로 말한다). 객체가 아니면 false.
    bool keys(const Value& v, K k, const std::string& where, long long pid) {
        if (v.type != VT::Object) { bad(pid, where, "객체가 아니다"); return false; }
        const KeySet ks = keySetOf(k, version_);
        auto known = [&](const std::string& name) {
            for (const char* r : ks.required) if (name == r) return true;
            for (const char* o : ks.optional) if (name == o) return true;
            return false;
        };
        for (const auto& kv : v.obj)
            if (!known(kv.first))
                bad(pid, where, "모르는 칸 '" + kv.first + "' — 계획 판 " + std::to_string(version_) + " 에 없는 칸은 받지 않는다");
        for (const char* r : ks.required)
            if (!v.get(r)) bad(pid, where, "칸 '" + std::string(r) + "' 가 없다");
        return true;
    }
    bool str(const Value* v, const std::string& where, long long pid, std::string& out) {
        if (!v) return false;   // 빠진 칸은 keys 가 이미 말했다
        if (v->type != VT::String) { bad(pid, where, "문자열이 아니다"); return false; }
        out = v->s;
        return true;
    }
    bool integer(const Value* v, const std::string& where, long long pid, long long minValue, long long& out) {
        if (!v) return false;
        if (v->type != VT::Int) { bad(pid, where, "정수가 아니다"); return false; }
        if (v->i < minValue) {
            bad(pid, where, std::to_string(minValue) + " 보다 작다(" + std::to_string(v->i) + ")");
            return false;
        }
        out = v->i;
        return true;
    }
    bool number(const Value* v, const std::string& where, long long pid, double& out) {
        if (!v) return false;
        if (v->type == VT::Int) { out = static_cast<double>(v->i); return true; }
        if (v->type == VT::Real && std::isfinite(v->d)) { out = v->d; return true; }
        bad(pid, where, "수가 아니다");
        return false;
    }
    bool boolean(const Value* v, const std::string& where, long long pid, bool& out) {
        if (!v) return false;
        if (v->type != VT::Bool) { bad(pid, where, "참·거짓이 아니다"); return false; }
        out = v->b;
        return true;
    }
    // 속을 읽지 않는 칸 — 객체인지만 본다
    bool object(const Value* v, const std::string& where, long long pid) {
        if (!v) return false;
        if (v->type != VT::Object) { bad(pid, where, "객체가 아니다"); return false; }
        return true;
    }
    bool strArray(const Value* v, const std::string& where, long long pid, std::vector<std::string>& out) {
        if (!v) return false;
        if (v->type != VT::Array) { bad(pid, where, "배열이 아니다"); return false; }
        bool ok = true;
        for (size_t k = 0; k < v->arr.size(); ++k) {
            std::string s;
            if (str(&v->arr[k], where + "[" + std::to_string(k) + "]", pid, s)) out.push_back(s);
            else ok = false;
        }
        return ok;
    }
    bool intArray(const Value* v, const std::string& where, long long pid, long long minValue, std::vector<long long>& out) {
        if (!v) return false;
        if (v->type != VT::Array) { bad(pid, where, "배열이 아니다"); return false; }
        bool ok = true;
        for (size_t k = 0; k < v->arr.size(); ++k) {
            long long x = 0;
            if (integer(&v->arr[k], where + "[" + std::to_string(k) + "]", pid, minValue, x)) out.push_back(x);
            else ok = false;
        }
        return ok;
    }
    bool numArray(const Value* v, const std::string& where, long long pid, size_t n, double* out) {
        if (!v) return false;
        if (v->type != VT::Array || v->arr.size() != n) {
            bad(pid, where, "수 " + std::to_string(n) + "개의 배열이 아니다");
            return false;
        }
        bool ok = true;
        for (size_t k = 0; k < n; ++k)
            if (!number(&v->arr[k], where + "[" + std::to_string(k) + "]", pid, out[k])) ok = false;
        return ok;
    }

private:
    std::vector<Problem>& out_;
    int version_ = 1;
};

// `field.layout` — 이름 셋(node · disp · kind)이 한 번씩, 꼴은 그쪽 머리(§4) 그대로.
void readLayout(Reader& r, const Value& L, const std::string& where, long long pid, FieldHead& h) {
    if (L.type != VT::Array) { r.bad(pid, where, "배열이 아니다", "field_layout"); return; }
    const long long N = h.nodes;
    std::set<std::string> seen;
    for (size_t k = 0; k < L.arr.size(); ++k) {
        const Value& e = L.arr[k];
        const std::string w = where + "[" + std::to_string(k) + "]";
        if (e.type != VT::Object) { r.bad(pid, w, "객체가 아니다", "field_layout"); continue; }
        std::string name;
        if (!r.str(e.get("name"), w + ".name", pid, name)) {
            if (!e.get("name")) r.bad(pid, w, "칸 'name' 이 없다");
            continue;
        }
        if (name != "node" && name != "disp" && name != "kind") {
            r.bad(pid, w + ".name", "'" + name + "' — node · disp · kind 만 있다", "field_layout");
            continue;
        }
        if (!seen.insert(name).second) { r.bad(pid, w + ".name", "'" + name + "' 가 두 번", "field_layout"); continue; }
        const bool shape = (name == "disp");
        r.keys(e, shape ? K::LayoutShape : K::LayoutCount, w, pid);
        const char* wantType = name == "node" ? "<u4" : (name == "disp" ? "<f8" : "<u1");
        std::string dtype;
        if (r.str(e.get("dtype"), w + ".dtype", pid, dtype) && dtype != wantType)
            r.bad(pid, w + ".dtype", "'" + dtype + "' — " + name + " 는 " + wantType + " 여야 한다", "field_layout");
        LayoutEntry& le = name == "node" ? h.node : (name == "disp" ? h.disp : h.kind);
        long long off = 0;
        if (r.integer(e.get("offset"), w + ".offset", pid, 0, off)) {
            le.offset = off;
            if (off % 8 != 0) r.bad(pid, w + ".offset", std::to_string(off) + " — 8 의 배수가 아니다", "field_layout");
        }
        if (shape) {
            const Value* s = e.get("shape");
            if (s && (s->type != VT::Array || s->arr.size() != 2 || s->arr[0].type != VT::Int || s->arr[1].type != VT::Int ||
                      s->arr[0].i != N || s->arr[1].i != 3))
                r.bad(pid, w + ".shape", "[" + std::to_string(N) + ", 3] 이 아니다", "field_layout");
        } else {
            long long c = 0;
            if (r.integer(e.get("count"), w + ".count", pid, 0, c) && c != N)
                r.bad(pid, w + ".count", std::to_string(c) + " — 절점 수 " + std::to_string(N) + " 와 다르다", "field_layout");
        }
        if (const Value* u = e.get("unit")) {
            std::string unit;
            if (r.str(u, w + ".unit", pid, unit) && unit != "mm")
                r.bad(pid, w + ".unit", "'" + unit + "' — mm 만 받는다(환산하지 않는다)", "field_layout");
        }
        if (const Value* sb = e.get("shared_bit")) {
            long long b = 0;
            if (r.integer(sb, w + ".shared_bit", pid, 0, b)) {
                if (b != 8) r.bad(pid, w + ".shared_bit", std::to_string(b) + " — 그쪽 꼴의 넷째 비트(8)가 아니다", "field_layout");
                else le.sharedBit = b;
            }
        }
    }
    for (const char* n : {"node", "disp", "kind"})
        if (!seen.count(n)) r.bad(pid, where, "'" + std::string(n) + "' 칸이 없다", "field_layout");
    if (seen.size() != 3) return;
    // 자리 — 겹치지 않고 파일 안이며 kind 가 끝이다(파일 크기 = kind 자리 + N)
    struct Span { const char* name; long long lo, hi; };
    std::vector<Span> sp = {{"node", h.node.offset, h.node.offset + 4 * N},
                            {"disp", h.disp.offset, h.disp.offset + 24 * N},
                            {"kind", h.kind.offset, h.kind.offset + N}};
    for (size_t a = 0; a < sp.size(); ++a)
        for (size_t b = a + 1; b < sp.size(); ++b)
            if (sp[a].lo < sp[b].hi && sp[b].lo < sp[a].hi)
                r.bad(pid, where, std::string(sp[a].name) + " 와 " + sp[b].name + " 의 자리가 겹친다", "field_layout");
    if (h.kind.offset + N != h.bytes)
        r.bad(pid, where, "kind 자리 + 절점 수(" + std::to_string(h.kind.offset + N) + ")가 bytes(" + std::to_string(h.bytes) +
                              ")와 다르다", "field_layout");
}

// 판 2 — 모프 줄 field 의 새 셸 섹션(`new_section` — 늘 있다)과 요소마다 두께(`element_thickness` — 있을 때만). 꼴은 요청서 §10.2 —
// null · {secid: 정수, thickness, file: 글, why}(지었다) · {secid: null, thickness, file: null, why}(두께가 바뀌었는데 못 지었다).
void readMorphV2(Reader& r, const Value& f, const std::string& where, long long pid, FieldHead& h) {
    if (const Value* ns = f.get("new_section"); ns && !ns->isNull()) {
        const std::string w = where + ".new_section";
        if (r.keys(*ns, K::MorphSection, w, pid)) {
            MorphSection& m = h.newSection;
            m.present = true;
            const Value* sec = ns->get("secid");
            const Value* file = ns->get("file");
            const bool secNull = sec && sec->isNull(), fileNull = file && file->isNull();
            bool okSec = secNull, okFile = fileNull;
            if (sec && !secNull) okSec = r.integer(sec, w + ".secid", pid, 1, m.secid);
            if (file && !fileNull) {
                okFile = r.str(file, w + ".file", pid, m.file);
                if (okFile && !plainName(m.file)) {
                    r.bad(pid, w + ".file", "'" + m.file + "' — 계획 폴더 바로 아래의 맨 이름이 아니다", "file_name");
                    okFile = false;
                }
            }
            if (sec && file && secNull != fileNull) r.bad(pid, w, "secid 와 file 은 함께 있거나 함께 null 이다");
            m.built = sec && file && !secNull && !fileNull && okSec && okFile;
            if (r.number(ns->get("thickness"), w + ".thickness", pid, m.thickness) && !(m.thickness > 0))
                r.bad(pid, w + ".thickness", "0 보다 커야 한다");
            r.str(ns->get("why"), w + ".why", pid, m.why);
        }
    }
    if (const Value* et = f.get("element_thickness")) {
        const std::string w = where + ".element_thickness";
        if (r.keys(*et, K::ElementThickness, w, pid)) {
            h.hasElementThickness = true;
            r.integer(et->get("elements"), w + ".elements", pid, 1, h.elementThicknessCount);
            std::string why;
            r.str(et->get("why"), w + ".why", pid, why);
        }
    }
}

void readField(Reader& r, const Value& f, const std::string& where, long long pid, FieldHead& h) {
    h.present = true;
    if (f.type != VT::Object) { r.bad(pid, where, "객체가 아니다"); return; }
    const Value* file = f.get("file");
    if (file && file->isNull()) {
        r.keys(f, K::FieldFailed, where, pid);
        h.built = false;
        r.str(f.get("why"), where + ".why", pid, h.why);
        if (r.version() >= 2) readMorphV2(r, f, where, pid, h);
        return;
    }
    r.keys(f, K::Field, where, pid);
    if (r.version() >= 2) readMorphV2(r, f, where, pid, h);
    h.built = r.str(file, where + ".file", pid, h.file);
    r.integer(f.get("nodes"), where + ".nodes", pid, 0, h.nodes);
    r.integer(f.get("bytes"), where + ".bytes", pid, 0, h.bytes);
    long long tmp = 0;
    double d = 0;
    r.integer(f.get("surface_nodes"), where + ".surface_nodes", pid, 0, tmp);
    r.object(f.get("kinds"), where + ".kinds", pid);
    r.number(f.get("max_disp"), where + ".max_disp", pid, d);
    r.integer(f.get("faces"), where + ".faces", pid, 0, tmp);
    r.object(f.get("face_pairs"), where + ".face_pairs", pid);
    r.integer(f.get("dropped_directions"), where + ".dropped_directions", pid, 0, tmp);
    r.integer(f.get("projection_fallbacks"), where + ".projection_fallbacks", pid, 0, tmp);
    r.object(f.get("solver"), where + ".solver", pid);
    r.object(f.get("check"), where + ".check", pid);
    h.hasThickness = f.get("thickness") != nullptr;
    if (const Value* L = f.get("layout")) readLayout(r, *L, where + ".layout", pid, h);
}

void readRange(Reader& r, const Value* v, const std::string& where, long long pid, long long& lo, long long& hi) {
    if (!v) return;
    if (v->type != VT::Array || v->arr.size() != 2) { r.bad(pid, where, "[lo, hi] 가 아니다"); return; }
    const bool a = r.integer(&v->arr[0], where + "[0]", pid, 1, lo);
    const bool b = r.integer(&v->arr[1], where + "[1]", pid, 1, hi);
    if (a && b && lo > hi) r.bad(pid, where, "lo 가 hi 보다 크다");
}

// 못 지은 조각의 까닭 — 있는 것을 쓴다: 맨 위 why(문자열 · null) → notes.why → check.why → check.problems[]. 없으면 빈 글자
// (부르는 쪽이 「까닭을 적지 않았다」고 말한다). 꼴만 본다 — why 는 문자열 · null, notes · check 는 객체.
std::string failedReason(Reader& r, const Value& f, const std::string& where, long long pid) {
    auto text = [](const Value* v) { return v && v->type == VT::String ? v->s : std::string(); };
    const Value* why = f.get("why");
    if (why && !why->isNull() && why->type != VT::String) r.bad(pid, where + ".why", "문자열 · null 이 아니다");
    const Value* notes = f.get("notes");
    if (notes) r.object(notes, where + ".notes", pid);
    const Value* check = f.get("check");
    if (check) r.object(check, where + ".check", pid);
    if (!text(why).empty()) return text(why);
    if (notes && notes->type == VT::Object && !text(notes->get("why")).empty()) return text(notes->get("why"));
    if (check && check->type == VT::Object) {
        if (!text(check->get("why")).empty()) return text(check->get("why"));
        std::string all;
        if (const Value* ps = check->get("problems"); ps && ps->type == VT::Array)
            for (const auto& p : ps->arr)
                if (!text(&p).empty()) all += (all.empty() ? "" : " · ") + p.s;
        if (!all.empty()) return all;
    }
    return std::string();
}

// allowNull — added 줄은 조각 없이(null) 까닭만 실을 수 있다. remesh 줄은 아니다.
void readFragment(Reader& r, const Value* f, const std::string& where, long long pid, bool allowNull, FragmentHead& h) {
    if (!f) return;
    if (f->isNull()) {
        if (!allowNull) r.bad(pid, where, "null 이다 — remesh 줄은 조각 머리가 있어야 한다");
        return;
    }
    h.present = true;
    if (f->type != VT::Object) { r.bad(pid, where, "객체가 아니다"); return; }
    if (!r.boolean(f->get("ok"), where + ".ok", pid, h.ok)) {
        if (!f->get("ok")) r.bad(pid, where, "칸 'ok' 가 없다");
        return;
    }
    if (!h.ok) {
        r.keys(*f, K::FragmentFailed, where, pid);
        h.why = failedReason(r, *f, where, pid);
        return;
    }
    r.keys(*f, K::Fragment, where, pid);
    r.str(f->get("file"), where + ".file", pid, h.file);
    r.integer(f->get("pid"), where + ".pid", pid, 1, h.pid);
    r.integer(f->get("secid"), where + ".secid", pid, 1, h.secid);
    r.integer(f->get("mid"), where + ".mid", pid, 1, h.mid);
    if (const Value* ns = f->get("new_section"); ns && !ns->isNull()) {
        const std::string w = where + ".new_section";
        if (r.keys(*ns, K::NewSection, w, pid)) {
            h.newSection.present = true;
            r.integer(ns->get("secid"), w + ".secid", pid, 1, h.newSection.secid);
            r.integer(ns->get("elform"), w + ".elform", pid, 1, h.newSection.elform);
            r.str(ns->get("why"), w + ".why", pid, h.newSection.why);
            if (const Value* nip = ns->get("nip")) h.newSection.hasNip = r.integer(nip, w + ".nip", pid, 1, h.newSection.nip);
            if (const Value* t = ns->get("t")) {
                h.newSection.hasT = r.number(t, w + ".t", pid, h.newSection.t);
                if (h.newSection.hasT && !(h.newSection.t > 0)) r.bad(pid, w + ".t", "0 보다 커야 한다");
            }
        }
    }
    if (const Value* rg = f->get("ranges"); rg && r.keys(*rg, K::Ranges, where + ".ranges", pid)) {
        readRange(r, rg->get("node"), where + ".ranges.node", pid, h.nodeLo, h.nodeHi);
        readRange(r, rg->get("elem"), where + ".ranges.elem", pid, h.elemLo, h.elemHi);
    }
    r.integer(f->get("nodes"), where + ".nodes", pid, 0, h.nodes);
    r.integer(f->get("elements"), where + ".elements", pid, 0, h.elements);
    r.integer(f->get("bytes"), where + ".bytes", pid, 0, h.bytes);
    r.object(f->get("mesh"), where + ".mesh", pid);
    r.object(f->get("target"), where + ".target", pid);
    r.object(f->get("check"), where + ".check", pid);
}

bool actionOf(const std::string& s, Action& a) {
    static const std::pair<const char*, Action> t[] = {{"keep", Action::Keep},     {"transform", Action::Transform},
                                                       {"morph", Action::Morph},   {"remesh", Action::Remesh},
                                                       {"delete", Action::Delete}, {"review", Action::Review}};
    for (const auto& [n, x] : t)
        if (s == n) { a = x; return true; }
    return false;
}

// 판 2 — 줄의 덱 자리(요청서 §10.2 `parts[].deck`). 범위는 [min, max] 이거나 null, contiguous 는 참 · 거짓 · null, SECID · MID 는
// 정수이거나 null(`*PART` 가 없다). 값은 덱과 견준다(적용 쪽) — 여기서는 꼴만 본다.
void readPartDeck(Reader& r, const Value& d, const std::string& where, long long pid, PartDeck& out) {
    if (!r.keys(d, K::PartDeck, where, pid)) return;
    out.present = true;
    auto range = [&](const char* key, bool& has, long long& lo, long long& hi) {
        const Value* v = d.get(key);
        if (!v || v->isNull()) return;
        has = true;
        readRange(r, v, where + "." + key, pid, lo, hi);
    };
    auto maybeInt = [&](const char* key, bool& has, long long& v) {
        const Value* x = d.get(key);
        if (!x || x->isNull()) return;
        has = r.integer(x, where + "." + key, pid, 0, v);
    };
    range("node", out.hasNode, out.nodeLo, out.nodeHi);
    r.integer(d.get("node_count"), where + ".node_count", pid, 0, out.nodeCount);
    range("elem", out.hasElem, out.elemLo, out.elemHi);
    r.integer(d.get("elem_count"), where + ".elem_count", pid, 0, out.elemCount);
    if (const Value* c = d.get("contiguous"); c && !c->isNull()) {
        bool b = false;
        if (r.boolean(c, where + ".contiguous", pid, b)) out.contiguous = b ? 1 : 0;
    }
    maybeInt("secid", out.hasSecid, out.secid);
    maybeInt("mid", out.hasMid, out.mid);
}

void readPart(Reader& r, const Value& p, size_t k, PartRow& row) {
    std::string where = "parts[" + std::to_string(k) + "]";
    if (p.type != VT::Object) { r.bad(0, where, "객체가 아니다"); return; }
    const size_t before = r.count();
    long long pid = 0;
    if (r.integer(p.get("pid"), where + ".pid", 0, 1, pid)) where += "(PID " + std::to_string(pid) + ")";
    else if (!p.get("pid")) r.bad(0, where, "칸 'pid' 가 없다");
    row.pid = pid;
    std::string action;
    if (!r.str(p.get("action"), where + ".action", pid, action)) {
        if (!p.get("action")) r.bad(pid, where, "칸 'action' 이 없다");
        return;
    }
    row.actionText = action;
    if (!actionOf(action, row.action)) {
        r.bad(pid, where + ".action", "'" + action + "' — keep · transform · morph · remesh · delete · review 만 있다");
        return;
    }
    static const K byAction[] = {K::Keep, K::Transform, K::Morph, K::Remesh, K::Delete, K::Review};
    r.keys(p, byAction[static_cast<int>(row.action)], where, pid);
    r.str(p.get("name"), where + ".name", pid, row.name);
    r.str(p.get("why"), where + ".why", pid, row.why);
    std::string mapping;
    r.str(p.get("mapping"), where + ".mapping", pid, mapping);
    std::vector<std::string> members;
    r.strArray(p.get("members"), where + ".members", pid, members);
    switch (row.action) {
        case Action::Keep:
            if (const Value* a = p.get("absorbed")) r.strArray(a, where + ".absorbed", pid, row.absorbed);
            if (const Value* t = p.get("touches_changed")) r.intArray(t, where + ".touches_changed", pid, 1, row.touchesChanged);
            break;
        case Action::Transform: {
            r.numArray(p.get("transform"), where + ".transform", pid, 16, row.m.data());
            r.numArray(p.get("translation"), where + ".translation", pid, 3, row.translation.data());
            double deg = 0;
            r.number(p.get("rotation_deg"), where + ".rotation_deg", pid, deg);
            r.object(p.get("check"), where + ".check", pid);
            break;
        }
        case Action::Morph:
            if (const Value* f = p.get("field")) readField(r, *f, where + ".field", pid, row.field);
            row.hasInstead = p.get("instead") != nullptr;
            break;
        case Action::Remesh:
            readFragment(r, p.get("fragment"), where + ".fragment", pid, false, row.fragment);
            break;
        case Action::Review:
            // 판 2 — 강체가 아닌 옮김(요청서 §10.2 · §10.3 ④). 옮기지 않는다 — 보고에 그대로 되돌려 준다
            if (const Value* rt = p.get("refused_transform"); rt && r.keys(*rt, K::RefusedTransform, where + ".refused_transform", pid)) {
                const std::string w = where + ".refused_transform";
                bool ok = r.numArray(rt->get("transform"), w + ".transform", pid, 16, row.refusedM.data());
                ok = r.number(rt->get("det"), w + ".det", pid, row.refusedDet) && ok;
                ok = r.number(rt->get("scale"), w + ".scale", pid, row.refusedScale) && ok;
                ok = r.number(rt->get("orthogonality_error"), w + ".orthogonality_error", pid, row.refusedOrth) && ok;
                row.hasRefusedTransform = ok;
            }
            break;
        case Action::Delete:
            break;
    }
    if (const Value* s = p.get("shared_nodes")) {
        row.shared.present = true;
        if (r.keys(*s, K::Shared, where + ".shared_nodes", pid)) {
            r.intArray(s->get("nodes"), where + ".shared_nodes.nodes", pid, 1, row.shared.nodes);
            r.intArray(s->get("with"), where + ".shared_nodes.with", pid, 1, row.shared.with);
        }
    }
    if (r.version() >= 2)
        if (const Value* d = p.get("deck")) readPartDeck(r, *d, where + ".deck", pid, row.deck);
    row.valid = (r.count() == before);
}

void readAdded(Reader& r, const Value& a, size_t k, AddedRow& row) {
    const std::string where = "added[" + std::to_string(k) + "]";
    if (a.type != VT::Object) { r.bad(0, where, "객체가 아니다"); return; }
    const size_t before = r.count();
    r.keys(a, K::Added, where, 0);
    r.str(a.get("path"), where + ".path", 0, row.path);
    r.str(a.get("name"), where + ".name", 0, row.name);
    std::string action;
    if (r.str(a.get("action"), where + ".action", 0, action) && action != "add")
        r.bad(0, where + ".action", "'" + action + "' — 새 파트 줄은 add 다");
    r.object(a.get("suggestion"), where + ".suggestion", 0);
    if (const Value* p = a.get("pid")) row.hasPid = r.integer(p, where + ".pid", 0, 1, row.pid);
    readFragment(r, a.get("fragment"), where + ".fragment", row.pid, true, row.fragment);
    r.str(a.get("why"), where + ".why", 0, row.why);
    if (row.hasPid && row.fragment.present && row.fragment.ok && row.fragment.pid != row.pid)
        r.bad(row.pid, where, "pid " + std::to_string(row.pid) + " 와 fragment.pid " + std::to_string(row.fragment.pid) + " 가 다르다");
    row.valid = (r.count() == before);
}

// 판 2 의 summary(요청서 §10.2 · 그쪽 `carryover_build.build`) — {actions: {처리: 수}, added, fields, fragments, sections, failed}
struct Summary {
    bool read = false;
    std::map<std::string, long long> actions;
    long long added = 0, fields = 0, fragments = 0, sections = 0, failed = 0;
};
const char* const kActionNames[] = {"keep", "transform", "morph", "remesh", "delete", "review"};

void readSummary(Reader& r, const Value& s, Summary& sum) {
    if (!r.keys(s, K::Summary, "summary", 0)) return;
    bool ok = true;
    if (const Value* a = s.get("actions")) {
        if (a->type != VT::Object) { r.bad(0, "summary.actions", "객체가 아니다"); ok = false; }
        else
            for (const auto& [name, n] : a->obj) {
                const bool known = std::any_of(std::begin(kActionNames), std::end(kActionNames), [&](const char* x) { return name == x; });
                long long c = 0;
                if (!known) { r.bad(0, "summary.actions", "'" + name + "' — 처리 이름이 아니다"); ok = false; }
                else if (r.integer(&n, "summary.actions." + name, 0, 0, c)) sum.actions[name] = c;
                else ok = false;
            }
    }
    ok = r.integer(s.get("added"), "summary.added", 0, 0, sum.added) && ok;
    ok = r.integer(s.get("fields"), "summary.fields", 0, 0, sum.fields) && ok;
    ok = r.integer(s.get("fragments"), "summary.fragments", 0, 0, sum.fragments) && ok;
    ok = r.integer(s.get("sections"), "summary.sections", 0, 0, sum.sections) && ok;
    ok = r.integer(s.get("failed"), "summary.failed", 0, 0, sum.failed) && ok;
    sum.read = ok;
}

// 그 줄에서 못 지었거나 확인을 못 지난 재료의 수 — 그쪽 `carryover_build._failed` 와 같은 셈(조각 · 대신 지은 조각의 ok false ·
// 파일이 없거나 check.ok 가 참이 아닌 변위장 · 파일이 없는 새 셸 섹션)
long long failedOf(const Value& row) {
    auto isStr = [](const Value* x) { return x && x->type == VT::String && !x->s.empty(); };
    long long n = 0;
    for (const char* k : {"fragment", "instead"})
        if (const Value* x = row.get(k); x && x->type == VT::Object)
            if (const Value* ok = x->get("ok"); ok && ok->type == VT::Bool && !ok->b) ++n;
    if (const Value* f = row.get("field"); f && f->type == VT::Object) {
        const Value* chk = f->get("check");
        const Value* ok = chk && chk->type == VT::Object ? chk->get("ok") : nullptr;
        if (!isStr(f->get("file")) || !(ok && ok->type == VT::Bool && ok->b)) ++n;
        if (const Value* ns = f->get("new_section"); ns && ns->type == VT::Object && !isStr(ns->get("file"))) ++n;
    }
    return n;
}

// 판 2 — summary 의 actions · sections · failed 가 계획 줄과 같은가(같은 계획 안의 두 주장 — 다르면 plan_inconsistent).
// actions 는 줄의 처리를 센다(강체가 아닌 옮김은 review — §10.2 「바뀐 뜻」 ②). 나머지 칸(added · fields · fragments)은 판 1 과 뜻이
// 같아 대조하지 않는다.
void crossCheckSummary(Reader& r, const Value& root, const Plan& plan, const Summary& sum) {
    std::map<std::string, long long> rows;
    for (const auto& p : plan.parts)
        if (!p.actionText.empty()) ++rows[p.actionText];
    for (const char* name : kActionNames) {
        const long long a = sum.actions.count(name) ? sum.actions.at(name) : 0, b = rows.count(name) ? rows.at(name) : 0;
        if (a != b)
            r.bad(0, std::string("summary.actions.") + name, std::to_string(a) + " 이 계획 줄의 " + name + " 수 " + std::to_string(b) +
                                                                 " 와 다르다", "plan_inconsistent");
    }
    long long sections = 0;
    for (const auto& p : plan.parts)
        if (p.action == Action::Morph && p.field.newSection.built) ++sections;
    if (sum.sections != sections)
        r.bad(0, "summary.sections", std::to_string(sum.sections) + " 이 새 셸 섹션 파일을 실은 모프 줄 수 " + std::to_string(sections) +
                                         " 와 다르다", "plan_inconsistent");
    long long failed = 0;
    for (const char* list : {"parts", "added"})
        if (const Value* a = root.get(list); a && a->type == VT::Array)
            for (const auto& row : a->arr)
                if (row.type == VT::Object) failed += failedOf(row);
    if (sum.failed != failed)
        r.bad(0, "summary.failed", std::to_string(sum.failed) + " 이 계획 줄에서 센 못 지은 재료 수 " + std::to_string(failed) +
                                       "(조각 · 대신 지은 조각 · 변위장 · 새 셸 섹션) 와 다르다", "plan_inconsistent");
}

bool parseLL(const std::string& s, long long& v) {
    const std::string t = deckscan::trim(s);
    if (t.empty()) { v = 0; return true; }
    size_t p = (t[0] == '-' || t[0] == '+') ? 1u : 0u;
    if (p >= t.size()) return false;
    for (size_t q = p; q < t.size(); ++q)
        if (!std::isdigit(static_cast<unsigned char>(t[q]))) return false;
    try {
        v = std::stoll(t);
    } catch (...) {
        return false;
    }
    return true;
}

// 10진 수 꼴인가 — [+-]? (숫자+ (. 숫자*)? | . 숫자+) ([eE] [+-]? 숫자+)?. `strtod` 는 16진(`0x2` · `0x1.8p0`) · `inf` · `nan` 도 받아
// NIP `0x2` 를 2 로 읽었다(적대적 검토 11-08 #5) — 덱 칸은 10진만 받는다(StepForge 리더의 `int()` · `float()` 와 같은 꼴)
bool isDecimalNumber(const std::string& t) {
    const size_t n = t.size();
    size_t i = 0, digits = 0;
    if (i < n && (t[i] == '+' || t[i] == '-')) ++i;
    while (i < n && std::isdigit(static_cast<unsigned char>(t[i]))) { ++i; ++digits; }
    if (i < n && t[i] == '.') {
        ++i;
        while (i < n && std::isdigit(static_cast<unsigned char>(t[i]))) { ++i; ++digits; }
    }
    if (digits == 0) return false;
    if (i < n && (t[i] == 'e' || t[i] == 'E')) {
        ++i;
        if (i < n && (t[i] == '+' || t[i] == '-')) ++i;
        size_t ed = 0;
        while (i < n && std::isdigit(static_cast<unsigned char>(t[i]))) { ++i; ++ed; }
        if (ed == 0) return false;
    }
    return i == n;
}

bool parseReal(const std::string& s, double& v) {
    const std::string t = deckscan::trim(s);
    if (t.empty() || !isDecimalNumber(t)) return false;
    char* end = nullptr;
    v = std::strtod(t.c_str(), &end);
    return end == t.c_str() + t.size() && std::isfinite(v);
}

// 정수 칸 — 정수 글자이거나, 실수 꼴로 쓴 **정수 값**(NIP `5.000e+00`)이면 그 정수다. LS-DYNA 실행 기록이 NIP `3.000E+00` 을 3 으로
// 받는다(StepForge 권고 591d5b5 · D-681 — 그쪽 말뭉치 52 덱 · 사용자 결정 11-07 밤). 정수가 아닌 값(`2.5`) · 10진이 아닌 꼴(`0x2`)은 거절한다
bool parseIntegral(const std::string& s, long long& v) {
    if (parseLL(s, v)) return true;
    double d = 0;
    if (!parseReal(s, d) || d != std::floor(d) || std::fabs(d) > 9007199254740992.0) return false;
    v = static_cast<long long>(d);
    return true;
}

std::string padInt(long long v, int w) {
    char buf[32];
    std::snprintf(buf, sizeof(buf), "%*lld", w, v);
    return buf;
}

// 보고에 싣는 글자는 늘 바른 UTF-8 이다 — 깨진 바이트(넘친 꼴 · 서로게이트 · U+10FFFF 위 · 잘린 꼴)는 U+FFFD 로 바꾼다(RFC 3629).
// 계획(StrictJson 은 글자를 검사하지 않는다) · 덱 줄 · 경로 어디서 온 글자든 보고가 엄격한 리더에서 깨지지 않게(2026-11-07 적대적 검토 #4).
// 정본은 공용 `util::validUtf8`(extract-parts 보고와 나눈다 — 2026-11-08)
using util::validUtf8;

std::string q(const std::string& s) { return json::quote(validUtf8(s)); }

// 글자 경계에서 자른다 — 바이트 n 에서 자르면 한글(3 바이트)이 반쪽으로 남아 보고가 깨진 UTF-8 이 되었다(검토 #4)
std::string clipUtf8(const std::string& l, size_t n) {
    if (l.size() <= n) return l;
    size_t cut = n;
    while (cut > 0 && (static_cast<unsigned char>(l[cut]) & 0xC0) == 0x80) --cut;
    return l.substr(0, cut) + "…";
}

// 다시 읽으면 같은 double 이 되는 가장 짧은 꼴(15 → 16 → 17 자리) — %.15g 는 계획의 refused_transform 을 되돌려 줄 때 끝자리를
// 잃었다(1.0000000000000002 → 1 · 적대적 검토 11-07 #7). 짧게 맞는 값(0.6 · 1.01)은 예전과 같은 글자다.
std::string num(double v) {
    if (!std::isfinite(v)) return "null";
    char buf[64];
    for (int prec = 15; prec <= 17; ++prec) {
        std::snprintf(buf, sizeof(buf), "%.*g", prec, v);
        if (std::strtod(buf, nullptr) == v) break;
    }
    return buf;
}

std::string intList(const std::vector<long long>& v) {
    std::string s = "[";
    for (size_t k = 0; k < v.size(); ++k) s += (k ? ", " : "") + std::to_string(v[k]);
    return s + "]";
}

std::string problemJson(const Problem& p) {
    std::string s = "{";
    if (p.pid > 0) s += "\"pid\": " + std::to_string(p.pid) + ", ";
    return s + "\"kind\": " + q(p.kind) + ", \"detail\": " + q(p.detail) + "}";
}

}  // namespace

const char* actionName(Action a) {
    switch (a) {
        case Action::Keep: return "keep";
        case Action::Transform: return "transform";
        case Action::Morph: return "morph";
        case Action::Remesh: return "remesh";
        case Action::Delete: return "delete";
        case Action::Review: return "review";
    }
    return "?";
}

bool parsePlan(const std::string& text, Plan& out, std::vector<Problem>& problems) {
    out = Plan{};
    Value v;
    std::string jerr;
    if (!json::parse(text, v, jerr)) {
        problems.push_back({0, "plan_json", "계획 JSON 문법 — " + jerr});
        return false;
    }
    Reader r(problems);
    const size_t before = r.count();
    if (v.type != VT::Object) { r.bad(0, "계획", "객체가 아니다"); return false; }
    // 판을 먼저 본다 — 칸 표가 판마다 다르다(판 1 · 2 만 받는다 · 모르는 판은 가장 새 판의 표로 나머지를 본다)
    const Value* ver = v.get("version");
    r.setVersion(ver && ver->type == VT::Int && ver->i == 1 ? 1 : 2);
    r.keys(v, K::Top, "계획", 0);

    if (r.str(v.get("format"), "format", 0, out.format) && out.format != "stepforge-carryover-plan")
        r.bad(0, "format", "'" + out.format + "' — stepforge-carryover-plan 만 받는다", "plan_format");
    if (r.integer(v.get("version"), "version", 0, 0, out.version) && out.version != 1 && out.version != 2)
        r.bad(0, "version", std::to_string(out.version) + " — 판 1 · 2 만 받는다(칸의 뜻이 바뀐 판은 그 꼴을 받기로 한 뒤에)", "plan_format");
    const bool v2 = r.version() >= 2;
    if (r.str(v.get("unit"), "unit", 0, out.unit) && out.unit != "mm-t-s")
        r.bad(0, "unit", "'" + out.unit + "' — mm-t-s 만 받는다(환산하지 않는다)", "plan_format");
    if (r.str(v.get("frame"), "frame", 0, out.frame) && out.frame != "world")
        r.bad(0, "frame", "'" + out.frame + "' — world 만 받는다(좌표를 변환하지 않는다)", "plan_format");

    if (const Value* d = v.get("deck"); d && r.keys(*d, K::Deck, "deck", 0)) {
        r.str(d->get("project_id"), "deck.project_id", 0, out.deckProjectId);
        r.str(d->get("relpath"), "deck.relpath", 0, out.deckRelpath);
        if (r.str(d->get("sha256"), "deck.sha256", 0, out.deckSha256) && !isHex64(out.deckSha256))
            r.bad(0, "deck.sha256", "소문자 16진 64자가 아니다");
        if (const Value* m = d->get("max"); m && r.keys(*m, K::DeckMax, "deck.max", 0)) {
            r.integer(m->get("node"), "deck.max.node", 0, 0, out.maxNode);
            r.integer(m->get("elem"), "deck.max.elem", 0, 0, out.maxElem);
            r.integer(m->get("pid"), "deck.max.pid", 0, 0, out.maxPid);
            r.integer(m->get("secid"), "deck.max.secid", 0, 0, out.maxSecid);
            r.integer(m->get("mid"), "deck.max.mid", 0, 0, out.maxMid);
        }
        r.strArray(d->get("unread_cards"), "deck.unread_cards", 0, out.unreadCards);
        if (v2) {
            // 덱의 자리 — 덱을 relpath 로 찾지 않는다(부르는 쪽이 준 model 이 그 덱이고 sha256 이 지킨다) · 보고에 되돌려 줄 뿐이다
            if (r.str(d->get("deck_from"), "deck.deck_from", 0, out.deckFrom) && out.deckFrom != "raw" && out.deckFrom != "mesh")
                r.bad(0, "deck.deck_from", "'" + out.deckFrom + "' — raw · mesh 만 있다");
            if (const Value* inc = d->get("includes")) {
                if (inc->type != VT::Array) r.bad(0, "deck.includes", "배열이 아니다");
                else {
                    out.hasIncludes = true;
                    for (size_t k = 0; k < inc->arr.size(); ++k) {
                        const std::string w = "deck.includes[" + std::to_string(k) + "]";
                        IncludeEntry e;
                        if (!r.keys(inc->arr[k], K::Include, w, 0)) continue;
                        if (r.str(inc->arr[k].get("relpath"), w + ".relpath", 0, e.relpath) && e.relpath.empty())
                            r.bad(0, w + ".relpath", "비었다");
                        if (r.str(inc->arr[k].get("sha256"), w + ".sha256", 0, e.sha256) && !isHex64(e.sha256))
                            r.bad(0, w + ".sha256", "소문자 16진 64자가 아니다");
                        out.includes.push_back(e);
                    }
                }
            }
        }
    }
    r.str(v.get("report_key"), "report_key", 0, out.reportKey);
    r.object(v.get("cad"), "cad", 0);
    double floorMm = 0;
    if (r.number(v.get("floor_mm"), "floor_mm", 0, floorMm) && floorMm < 0) r.bad(0, "floor_mm", "음수다");
    // 판 1 의 summary 는 꼴만 본다. 판 2 는 칸을 보고(그쪽 요청서 §10.2) actions · sections · failed 를 계획 줄과 대조한다(아래)
    Summary sum;
    if (!v2) r.object(v.get("summary"), "summary", 0);
    else if (const Value* s = v.get("summary")) readSummary(r, *s, sum);
    if (const Value* cb = v.get("code_build")) r.str(cb, "code_build", 0, out.codeBuild);

    if (const Value* ps = v.get("parts")) {
        if (ps->type != VT::Array) r.bad(0, "parts", "배열이 아니다");
        else {
            std::set<long long> pids;
            for (size_t k = 0; k < ps->arr.size(); ++k) {
                PartRow row;
                readPart(r, ps->arr[k], k, row);
                if (row.pid > 0 && !pids.insert(row.pid).second) {
                    r.bad(row.pid, "parts[" + std::to_string(k) + "]", "PID " + std::to_string(row.pid) + " 의 줄이 두 번", "plan_rows");
                    row.valid = false;
                }
                out.parts.push_back(row);
            }
        }
    }
    if (const Value* as = v.get("added")) {
        if (as->type != VT::Array) r.bad(0, "added", "배열이 아니다");
        else
            for (size_t k = 0; k < as->arr.size(); ++k) {
                AddedRow row;
                readAdded(r, as->arr[k], k, row);
                out.added.push_back(row);
            }
    }
    if (const Value* fs = v.get("files")) {
        if (fs->type != VT::Object) r.bad(0, "files", "객체가 아니다");
        else
            for (const auto& [name, e] : fs->obj) {
                const std::string w = "files['" + name + "']";
                FileEntry fe;
                fe.name = name;
                if (!plainName(name)) r.bad(0, w, "계획 폴더 바로 아래의 맨 이름이 아니다(경로 · ../ 를 받지 않는다)", "file_name");
                if (r.keys(e, K::FileEntry, w, 0)) {
                    if (r.str(e.get("sha256"), w + ".sha256", 0, fe.sha256) && !isHex64(fe.sha256))
                        r.bad(0, w + ".sha256", "소문자 16진 64자가 아니다");
                    r.integer(e.get("bytes"), w + ".bytes", 0, 0, fe.bytes);
                }
                out.files.push_back(fe);
            }
    }
    if (v2 && sum.read) crossCheckSummary(r, v, out, sum);
    return r.count() == before;
}

bool readField(const std::string& b, const FieldHead& h, Field& out, std::string& err) {
    out = Field{};
    const long long N = h.nodes;
    if (static_cast<long long>(b.size()) != h.bytes) {
        err = "파일 크기 " + std::to_string(b.size()) + " 가 머리의 bytes " + std::to_string(h.bytes) + " 와 다르다";
        return false;
    }
    if (h.kind.offset + N != static_cast<long long>(b.size())) {
        err = "kind 자리 + 절점 수가 파일 크기와 다르다";
        return false;
    }
    auto fits = [&](long long off, long long len) { return off >= 0 && len >= 0 && off + len <= static_cast<long long>(b.size()); };
    if (!fits(h.node.offset, 4 * N) || !fits(h.disp.offset, 24 * N) || !fits(h.kind.offset, N)) {
        err = "차례의 자리가 파일 밖이다";
        return false;
    }
    auto byteAt = [&](long long off) { return static_cast<uint64_t>(static_cast<unsigned char>(b[static_cast<size_t>(off)])); };
    out.node.resize(static_cast<size_t>(N));
    out.disp.resize(static_cast<size_t>(3 * N));
    out.kind.resize(static_cast<size_t>(N));
    for (long long i = 0; i < N; ++i) {
        const long long o = h.node.offset + 4 * i;
        out.node[static_cast<size_t>(i)] =
            static_cast<uint32_t>(byteAt(o) | (byteAt(o + 1) << 8) | (byteAt(o + 2) << 16) | (byteAt(o + 3) << 24));
    }
    for (long long i = 0; i < 3 * N; ++i) {
        uint64_t u = 0;
        const long long o = h.disp.offset + 8 * i;
        for (int k = 7; k >= 0; --k) u = (u << 8) | byteAt(o + k);   // 리틀엔디언 — 호스트 바이트 순서와 무관하다
        double d = 0;
        std::memcpy(&d, &u, sizeof d);
        out.disp[static_cast<size_t>(i)] = d;
    }
    for (long long i = 0; i < N; ++i) out.kind[static_cast<size_t>(i)] = static_cast<uint8_t>(byteAt(h.kind.offset + i));

    for (long long i = 0; i < N; ++i) {
        const uint32_t n = out.node[static_cast<size_t>(i)];
        if (n == 0) { err = std::to_string(i) + "째 절점 번호가 0 이다"; return false; }
        if (i > 0 && n <= out.node[static_cast<size_t>(i - 1)]) {
            err = std::to_string(i) + "째 절점 번호 " + std::to_string(n) + " — 오름차순(중복 없음)이 아니다";
            return false;
        }
        for (int k = 0; k < 3; ++k)
            if (!std::isfinite(out.disp[static_cast<size_t>(3 * i + k)])) {
                err = "절점 " + std::to_string(n) + " 의 변위가 유한하지 않다";
                return false;
            }
        const unsigned kind = out.kind[static_cast<size_t>(i)];
        const unsigned code = kind & 7u;
        if (code > 4u || (kind & ~(7u | static_cast<unsigned>(h.kind.sharedBit))) != 0u) {
            err = "절점 " + std::to_string(n) + " 의 꼴 바이트 " + std::to_string(kind) + " — 아래 세 비트 0~4 와 나눠 쓴 절점 비트 밖이다";
            return false;
        }
    }
    return true;
}

bool scanFragment(const std::vector<std::string>& in, FragmentScan& s, std::vector<std::string>& problems) {
    s = FragmentScan{};
    s.lines.resize(in.size());
    const size_t before = problems.size();
    enum class Blk { None, Node, Solid, Shell, Part, Section };
    Blk blk = Blk::None;
    int block = -1;
    bool ended = false, sawEnd = false;
    struct Head { bool on = false; long long eid = 0, pid = 0; } head;   // 두 줄 꼴 솔리드(EID PID / 절점)
    std::vector<size_t> data;                                           // 지금 *PART · *SECTION 블록의 데이터 줄
    auto where = [](size_t i) { return "조각 " + std::to_string(i + 1) + "째 줄"; };
    auto bad = [&](size_t i, const std::string& what) { problems.push_back(where(i) + " — " + what); };

    // *PART · *SECTION 블록을 닫는다 — 빈 줄도 카드다(제목이 비었을 수 있다) · 끝의 빈 줄은 여백이다
    auto flush = [&]() {
        while (!data.empty() && deckscan::trim(in[data.back()]).empty()) data.pop_back();
        if (blk == Blk::Part) {
            if (data.size() % 2 != 0) {
                bad(data.empty() ? 0 : data.back(), "*PART 블록의 데이터 줄이 제목 · 카드 짝이 아니다");
            }
            for (size_t k = 0; k + 1 < data.size(); k += 2) {
                const std::string& card = in[data[k + 1]];
                if (card.find(',') != std::string::npos) { bad(data[k + 1], "*PART 카드가 자유 형식(콤마)이다"); continue; }
                const auto f = deckscan::fieldsFixed(card, 10);
                FragmentScan::PartCard pc;
                pc.title = deckscan::trim(in[data[k]]);
                long long v[8] = {0, 0, 0, 0, 0, 0, 0, 0};
                bool okInts = true;
                for (size_t c = 0; c < 8 && c < f.size(); ++c) {
                    if (c == 5 || c == 6) continue;   // GRAV · ADPOPT — 번호가 아니다
                    if (!parseLL(f[c], v[c])) okInts = false;
                }
                if (!okInts || f.size() < 3) { bad(data[k + 1], "*PART 카드의 PID · SECID · MID 를 읽지 못했다"); continue; }
                pc.pid = v[0];
                pc.secid = v[1];
                pc.mid = v[2];
                pc.otherIdsZero = (v[3] == 0 && v[4] == 0 && v[7] == 0);
                s.parts.push_back(pc);
            }
        } else if (blk == Blk::Section) {
            const bool shell = s.blockKw[static_cast<size_t>(block)] == "*SECTION_SHELL_TITLE";
            const size_t want = shell ? 3u : 2u;   // 제목 + Card 1 (+ 셸 Card 2 — 두께)
            if (data.size() != want) {
                bad(data.empty() ? 0 : data.front(), s.blockKw[static_cast<size_t>(block)] + " 의 데이터 줄이 " +
                                                         std::to_string(want) + " 줄(제목 · 카드)이 아니다");
            } else {
                FragmentScan::Section sec;
                sec.shell = shell;
                const std::string& c1 = in[data[1]];
                if (c1.find(',') != std::string::npos || (shell && in[data[2]].find(',') != std::string::npos)) {
                    bad(data[1], "섹션 카드가 자유 형식(콤마)이다");
                } else {
                    const auto f = deckscan::fieldsFixed(c1, 10);
                    long long icomp = 0;
                    if (f.size() < 2 || !parseLL(f[0], sec.secid) || !parseLL(f[1], sec.elform) || sec.secid <= 0 ||
                        sec.elform <= 0)
                        bad(data[1], "섹션 카드의 SECID · ELFORM 을 읽지 못했다");
                    if (shell) {
                        if (f.size() > 3 && !parseLL(f[3], sec.nip)) bad(data[1], "셸 섹션의 NIP 가 정수가 아니다");
                        if (f.size() > 6 && (!parseLL(f[6], icomp) || icomp != 0))
                            bad(data[1], "셸 섹션의 ICOMP 가 0 이 아니다 — 각도 카드가 따라오는 꼴은 계약 밖이다");
                        const auto f2 = deckscan::fieldsFixed(in[data[2]], 10);
                        if (!f2.empty() && !deckscan::trim(f2[0]).empty()) {
                            sec.t1Given = parseReal(f2[0], sec.t1);
                            if (!sec.t1Given) bad(data[2], "셸 섹션의 T1 을 읽지 못했다");
                        }
                    }
                    s.sections.push_back(sec);
                }
            }
        }
        data.clear();
    };

    for (size_t i = 0; i < in.size(); ++i) {
        const std::string& l = in[i];
        FragmentScan::Line& L = s.lines[i];
        L.block = block;
        // 제어 문자(탭 밖) — 주석 · 제목 줄은 글자 그대로 덱에 들어간다. 줄 가운데의 CR 은 다른 리더에서 줄을 끊어 살아 있는 카드가
        // 될 수 있다(리뷰 11-07 — 계획 이름의 개행이 카드를 심었다). 고치지 않고 거절한다
        if (std::any_of(l.begin(), l.end(), [](char c) {
                const unsigned char u = static_cast<unsigned char>(c);
                return (u < 0x20 && u != '\t') || u == 0x7F;
            })) {
            bad(i, "제어 문자가 든 줄 — 조각 줄은 인쇄할 수 있는 글자(와 탭)만 싣는다");
            L.kind = FragmentScan::LineKind::Skip;
            continue;
        }
        const size_t g = l.find_first_not_of(" \t");
        if (g != std::string::npos && l[g] == '*') {
            if (head.on) { bad(i, "두 줄 꼴 솔리드 카드의 절점 줄이 없다"); head.on = false; }
            flush();
            const std::string kw = deckscan::kwBare(deckscan::keywordToken(l));
            if (ended) bad(i, "*END 뒤의 키워드 " + kw);
            static const char* const kAllowed[] = {"*KEYWORD", "*END", "*NODE", "*ELEMENT_SOLID", "*ELEMENT_SHELL", "*PART",
                                                   "*SECTION_SOLID_TITLE", "*SECTION_SHELL_TITLE"};
            if (std::find_if(std::begin(kAllowed), std::end(kAllowed), [&](const char* a) { return kw == a; }) ==
                std::end(kAllowed)) {
                bad(i, "계약 밖 키워드 " + kw + " — 이월 조각은 *NODE · *ELEMENT_SOLID · *ELEMENT_SHELL · *PART · "
                                               "*SECTION_SOLID_TITLE · *SECTION_SHELL_TITLE 만 싣는다");
                blk = Blk::None;
                L.kind = FragmentScan::LineKind::Skip;
                continue;
            }
            if (keywordFieldWidth(l, 8) != 8) bad(i, "칸 폭 접미사(" + deckscan::keywordToken(l) + ") — 조각은 표준 폭이어야 한다");
            L.kind = FragmentScan::LineKind::Skip;
            if (kw == "*KEYWORD") {
                const int w = keywordCardDeckWidth(l);
                if (w != 0 && w != 8) bad(i, "*KEYWORD 의 폭이 표준(8)이 아니다 — 조각은 표준 폭이다");
                blk = Blk::None;
                continue;
            }
            if (kw == "*END") { ended = sawEnd = true; blk = Blk::None; continue; }
            ++block;
            s.blockKw.push_back(kw);
            L.block = block;
            L.kind = FragmentScan::LineKind::Keyword;
            blk = kw == "*NODE" ? Blk::Node
                : kw == "*ELEMENT_SOLID" ? Blk::Solid
                : kw == "*ELEMENT_SHELL" ? Blk::Shell
                : kw == "*PART" ? Blk::Part : Blk::Section;
            continue;
        }
        if (g != std::string::npos && l[g] == '$') { L.kind = FragmentScan::LineKind::Comment; continue; }
        if (ended || blk == Blk::None) {
            L.kind = FragmentScan::LineKind::Skip;
            if (g != std::string::npos) bad(i, ended ? "*END 뒤의 데이터 줄" : "키워드 밖의 데이터 줄");
            continue;
        }
        if (blk == Blk::Part || blk == Blk::Section) {
            L.kind = FragmentScan::LineKind::Verbatim;
            data.push_back(i);
            continue;
        }
        if (g == std::string::npos) { bad(i, "절점 · 요소 블록의 빈 줄"); L.kind = FragmentScan::LineKind::Skip; continue; }
        if (l.find(',') != std::string::npos) { bad(i, "자유 형식(콤마) 줄 — 조각은 고정폭이어야 한다"); continue; }
        if (l.find('\t') != std::string::npos) { bad(i, "탭이 든 줄 — 조각은 고정폭이어야 한다"); continue; }
        if (blk == Blk::Node) {
            // (I8, 3F16) — 그 뒤 TC · RC 칸은 계약에 없다(비어 있어야 한다)
            long long id = 0;
            FragmentScan::Node n;
            bool okLine = l.size() >= 56 && parseLL(l.substr(0, 8), id) && id > 0;
            for (int k = 0; okLine && k < 3; ++k) okLine = parseReal(l.substr(static_cast<size_t>(8 + 16 * k), 16), n.xyz[static_cast<size_t>(k)]);
            if (!okLine) { bad(i, "절점 줄(I8 · 3F16)을 읽지 못했다"); continue; }
            if (l.size() > 56 && !deckscan::trim(l.substr(56)).empty()) { bad(i, "절점 줄의 TC · RC 칸 — 계약 밖이다"); continue; }
            n.id = id;
            s.nodes.push_back(n);
            L.kind = FragmentScan::LineKind::Node;
            L.f = {id};
            continue;
        }
        auto f = deckscan::fieldsFixed(l, 8);
        while (!f.empty() && deckscan::trim(f.back()).empty()) f.pop_back();
        std::vector<long long> vals;
        bool okInts = true;
        for (const auto& x : f) {
            long long v = 0;
            if (!parseLL(x, v)) okInts = false;
            vals.push_back(v);
        }
        if (!okInts) { bad(i, "요소 카드에 정수가 아닌 칸이 있다"); continue; }
        FragmentScan::Elem e;
        if (blk == Blk::Solid) {
            if (head.on) {
                if (vals.size() != 8) { bad(i, "두 줄 꼴 솔리드의 절점 줄이 N1..N8 여덟 칸이 아니다"); head.on = false; continue; }
                L.kind = FragmentScan::LineKind::ElemNodes;
                L.f = vals;
                e.id = head.eid;
                e.pid = head.pid;
                std::copy(vals.begin(), vals.end(), e.n.begin());
                head.on = false;
            } else if (vals.size() == 2) {
                head = {true, vals[0], vals[1]};
                L.kind = FragmentScan::LineKind::ElemCard;
                L.f = vals;
                continue;
            } else if (vals.size() == 10) {
                L.kind = FragmentScan::LineKind::ElemCard;
                L.f = vals;
                e.id = vals[0];
                e.pid = vals[1];
                std::copy(vals.begin() + 2, vals.end(), e.n.begin());
            } else {
                bad(i, "솔리드 카드가 EID PID N1..N8(열 칸)이 아니다");
                continue;
            }
            for (long long n : e.n)
                if (n <= 0) { bad(i, "솔리드 요소 " + std::to_string(e.id) + " 의 절점 칸이 비었다"); break; }
        } else {
            if (vals.size() < 6 || vals.size() > 10) { bad(i, "셸 카드가 EID PID N1..N4 가 아니다"); continue; }
            for (size_t k = 6; k < vals.size(); ++k)
                if (vals[k] != 0) { bad(i, "셸 중간절점(N5-N8) — 계약 밖이다"); break; }
            L.kind = FragmentScan::LineKind::ElemCard;
            L.f = vals;
            e.id = vals[0];
            e.pid = vals[1];
            e.shell = true;
            for (size_t k = 0; k < 4; ++k) e.n[k] = vals[2 + k];
            for (size_t k = 0; k < 4; ++k)
                if (e.n[k] <= 0) { bad(i, "셸 요소 " + std::to_string(e.id) + " 의 절점 칸이 비었다"); break; }
        }
        if (e.id <= 0 || e.pid <= 0) bad(i, "요소의 EID · PID 가 양수가 아니다");
        s.elems.push_back(e);
    }
    if (head.on) bad(in.empty() ? 0 : in.size() - 1, "두 줄 꼴 솔리드 카드의 절점 줄이 없다");
    flush();
    if (!sawEnd) problems.push_back("조각 — *END 가 없다(잘린 파일일 수 있다)");
    return problems.size() == before;
}

void checkFragment(const FragmentScan& s, const FragmentHead& h, long long expectPid, std::vector<std::string>& problems) {
    auto bad = [&](const std::string& what) { problems.push_back(what); };
    if (h.pid != expectPid) bad("fragment.pid " + std::to_string(h.pid) + " 가 줄의 PID " + std::to_string(expectPid) + " 와 다르다");
    const long long wantSecid = h.newSection.present ? h.newSection.secid : h.secid;
    if (h.newSection.present && h.secid != h.newSection.secid)
        bad("fragment.secid " + std::to_string(h.secid) + " 가 new_section.secid " + std::to_string(h.newSection.secid) + " 와 다르다");
    // *PART — 정확히 하나, 그 줄의 PID · SECID · MID
    if (s.parts.size() != 1) bad("*PART 카드가 " + std::to_string(s.parts.size()) + " 장 — 정확히 한 장이어야 한다");
    for (const auto& p : s.parts) {
        if (p.pid != expectPid) bad("*PART 의 PID " + std::to_string(p.pid) + " 가 " + std::to_string(expectPid) + " 가 아니다");
        if (p.secid != wantSecid) bad("*PART 의 SECID " + std::to_string(p.secid) + " 가 " + std::to_string(wantSecid) + " 가 아니다");
        if (p.mid != h.mid) bad("*PART 의 MID " + std::to_string(p.mid) + " 가 " + std::to_string(h.mid) + " 가 아니다");
        if (!p.otherIdsZero) bad("*PART 의 EOSID · HGID · TMID 가 0 이 아니다 — 그 번호는 계약에 없다");
    }
    // 요소 — 꼴은 하나(셸이거나 솔리드)
    size_t shells = 0;
    for (const auto& e : s.elems) shells += e.shell ? 1 : 0;
    const bool mixed = shells != 0 && shells != s.elems.size();
    if (mixed) bad("셸과 솔리드가 섞였다 — 한 파트는 섹션 하나다");
    const bool shellPart = !s.elems.empty() && shells == s.elems.size();
    // 새 섹션 카드 — new_section 일 때만 정확히 하나
    if (!h.newSection.present) {
        if (!s.sections.empty()) bad("new_section 이 없는데 섹션 카드가 있다");
    } else if (s.sections.size() != 1) {
        bad("new_section 인데 섹션 카드가 " + std::to_string(s.sections.size()) + " 장 — 정확히 한 장이어야 한다");
    } else {
        const auto& sec = s.sections.front();
        if (sec.secid != h.newSection.secid) bad("섹션 카드의 SECID " + std::to_string(sec.secid) + " 가 new_section.secid 와 다르다");
        if (sec.elform != h.newSection.elform) bad("섹션 카드의 ELFORM " + std::to_string(sec.elform) + " 가 new_section.elform " +
                                                   std::to_string(h.newSection.elform) + " 와 다르다");
        if (!mixed && !s.elems.empty() && sec.shell != shellPart)
            bad(std::string("섹션 카드가 ") + (sec.shell ? "셸" : "솔리드") + " 섹션인데 요소는 " + (shellPart ? "셸" : "솔리드") + " 다");
        if (!sec.shell && (h.newSection.hasNip || h.newSection.hasT)) bad("솔리드 섹션에 new_section 의 nip · t 가 있다");
        if (sec.shell && h.newSection.hasNip && sec.nip != h.newSection.nip)
            bad("셸 섹션의 NIP " + std::to_string(sec.nip) + " 가 new_section.nip 와 다르다");
        // T1 은 상대 1e-4 안 — StepForge 는 카드에 %10.5g(유효 5자리)로 쓰고 계획에는 round(t, 9) 를 싣는다(`lsdyna_k.py` · 리뷰 11-07)
        if (sec.shell && h.newSection.hasT &&
            !(sec.t1Given && std::fabs(sec.t1 - h.newSection.t) <= 1e-4 * std::max(std::fabs(h.newSection.t), 1e-12)))
            bad("셸 섹션의 T1 " + (sec.t1Given ? num(sec.t1) : std::string("(빈 칸)")) + " 이 new_section.t " + num(h.newSection.t) +
                " 와 다르다(허용 상대 1e-4)");
    }
    // 번호 — 구간 · 수 · 중복
    std::set<long long> eids, nids;
    long long eLo = 0, eHi = 0, nLo = 0, nHi = 0;
    for (const auto& e : s.elems) {
        if (!eids.insert(e.id).second) bad("요소 " + std::to_string(e.id) + " 가 두 번");
        if (e.pid != expectPid) bad("요소 " + std::to_string(e.id) + " 의 PID " + std::to_string(e.pid) + " 가 " + std::to_string(expectPid) + " 가 아니다");
    }
    for (const auto& n : s.nodes)
        if (!nids.insert(n.id).second) bad("절점 " + std::to_string(n.id) + " 가 두 번");
    if (!eids.empty()) { eLo = *eids.begin(); eHi = *eids.rbegin(); }
    if (!nids.empty()) { nLo = *nids.begin(); nHi = *nids.rbegin(); }
    if (static_cast<long long>(s.elems.size()) != h.elements)
        bad("요소 수 " + std::to_string(s.elems.size()) + " 가 elements " + std::to_string(h.elements) + " 와 다르다");
    if (static_cast<long long>(s.nodes.size()) != h.nodes)
        bad("절점 수 " + std::to_string(s.nodes.size()) + " 가 nodes " + std::to_string(h.nodes) + " 와 다르다");
    if (eLo != h.elemLo || eHi != h.elemHi)
        bad("요소 번호 " + std::to_string(eLo) + "~" + std::to_string(eHi) + " 가 ranges.elem " + std::to_string(h.elemLo) + "~" +
            std::to_string(h.elemHi) + " 와 다르다");
    if (nLo != h.nodeLo || nHi != h.nodeHi)
        bad("절점 번호 " + std::to_string(nLo) + "~" + std::to_string(nHi) + " 가 ranges.node " + std::to_string(h.nodeLo) + "~" +
            std::to_string(h.nodeHi) + " 와 다르다");
    // 요소가 쓰는 절점이 다 있고, 안 쓰는 절점이 없다
    std::set<long long> used;
    long long missing = 0, firstMissing = 0;
    for (const auto& e : s.elems)
        for (size_t k = 0; k < (e.shell ? 4u : 8u); ++k) {
            const long long n = e.n[k];
            if (n <= 0) continue;
            used.insert(n);
            if (!nids.count(n) && missing++ == 0) firstMissing = n;
        }
    if (missing) bad("요소가 조각에 없는 절점을 가리킨다 " + std::to_string(missing) + " 곳(첫 절점 " + std::to_string(firstMissing) + ")");
    long long unused = 0, firstUnused = 0;
    for (long long n : nids)
        if (!used.count(n) && unused++ == 0) firstUnused = n;
    if (unused) bad("어느 요소도 쓰지 않는 절점 " + std::to_string(unused) + " 개(첫 절점 " + std::to_string(firstUnused) + ")");
}

std::string renderFragment(const std::vector<std::string>& lines, const FragmentScan& s, long long shiftNode, long long shiftElem,
                           int fw, bool withPart) {
    std::ostringstream o;
    for (size_t i = 0; i < lines.size() && i < s.lines.size(); ++i) {
        const auto& L = s.lines[i];
        if (L.kind == FragmentScan::LineKind::Skip) continue;
        if (!withPart && L.block >= 0 && s.blockKw[static_cast<size_t>(L.block)] == "*PART") continue;
        switch (L.kind) {
            case FragmentScan::LineKind::Keyword:
                o << s.blockKw[static_cast<size_t>(L.block)] << "\n";
                break;
            case FragmentScan::LineKind::Comment:
            case FragmentScan::LineKind::Verbatim:
                o << lines[i] << "\n";
                break;
            case FragmentScan::LineKind::Node:
                o << padInt(L.f[0] + shiftNode, fw) << lines[i].substr(8) << "\n";
                break;
            case FragmentScan::LineKind::ElemCard:
                for (size_t k = 0; k < L.f.size(); ++k) {
                    long long v = L.f[k];
                    if (k == 0) v += shiftElem;
                    else if (k >= 2 && v != 0) v += shiftNode;
                    o << padInt(v, fw);
                }
                o << "\n";
                break;
            case FragmentScan::LineKind::ElemNodes:
                for (long long v : L.f) o << padInt(v != 0 ? v + shiftNode : 0, fw);
                o << "\n";
                break;
            case FragmentScan::LineKind::Skip:
                break;
        }
    }
    return o.str();
}

bool shellSectionRows(const std::vector<std::string>& block, size_t& row1, size_t& row2, std::string& why) {
    const auto bl = cardcut::blocks(block);
    if (bl.size() != 1 || bl[0].kwLine != 0) { why = "블록이 섹션 키워드 하나로 시작하는 한 묶음이 아니다"; return false; }
    const std::string& kw = bl[0].kw;
    if (kw != "*SECTION_SHELL" && kw != "*SECTION_SHELL_TITLE") { why = kw + " — *SECTION_SHELL · *SECTION_SHELL_TITLE 이 아니다"; return false; }
    const auto& data = bl[0].data;   // 주석 밖의 줄 — 빈 줄도 카드다(끝의 빈 줄은 여백)
    const size_t title = kw == "*SECTION_SHELL_TITLE" ? 1 : 0;
    if (data.size() < title + 2) { why = "Card 1 · Card 2 가 없다(데이터 줄 " + std::to_string(data.size()) + ")"; return false; }
    row1 = data[title];
    row2 = data[title + 1];
    for (size_t r : {row1, row2})
        if (block[r].find(',') != std::string::npos || block[r].find('\t') != std::string::npos) {
            why = std::to_string(r + 1) + "째 줄 — 자유 형식(콤마 · 탭)이다(고정폭 10칸만 받는다)";
            return false;
        }
    const auto f = cardcut::cut(block[row1], 10).f;
    long long elform = 0, nip = 0, icomp = 0;
    // 정수 칸의 실수 꼴(`5.000e+00`)은 그 정수로 읽는다(`parseIntegral` — 예전엔 거절했다) · 정수가 아닌 값은 거절
    if (f.size() > 1 && !deckscan::trim(f[1]).empty() && !parseIntegral(f[1], elform)) { why = "Card 1 의 ELFORM 이 정수가 아니다"; return false; }
    if (f.size() > 3 && !parseIntegral(f[3], nip)) { why = "Card 1 의 NIP 가 정수가 아니다"; return false; }
    if (f.size() > 6 && !parseIntegral(f[6], icomp)) { why = "Card 1 의 ICOMP 가 정수가 아니다"; return false; }
    // 딸린 카드(Vol_I *SECTION_SHELL) — ICOMP 1 이면 각도 카드 ceil(NIP/8)(NIP 0 = 2 점) · ELFORM 101~105 는 사용자 정의 셸의
    // 카드 묶음(NIPP · 적분점 · 성질 카드)이 따라온다 — 그 줄 수는 그 카드의 값이 정해 여기서는 받지 않는다
    if (elform >= 101 && elform <= 105) { why = "사용자 정의 셸(ELFORM " + std::to_string(elform) + ")의 딸린 카드는 계약 밖이다"; return false; }
    if (icomp != 0 && icomp != 1) { why = "Card 1 의 ICOMP " + std::to_string(icomp) + " — 0 · 1 만 있다"; return false; }
    const long long nipEff = nip > 0 ? nip : 2;
    const size_t angles = icomp == 1 ? static_cast<size_t>((nipEff + 7) / 8) : 0;
    const size_t want = title + 2 + angles;
    if (data.size() != want) {
        why = "카드 하나가 아니다 — 데이터 줄 " + std::to_string(data.size()) + "(제목 " + std::to_string(title) + " · Card 1 · Card 2" +
              (angles ? " · 각도 카드 " + std::to_string(angles) : std::string()) + " = " + std::to_string(want) +
              ") — 한 키워드 아래 쌓인 둘째 카드일 수 있다";
        return false;
    }
    return true;
}

bool scanSectionFile(const std::vector<std::string>& in, SectionFileScan& s, std::vector<std::string>& problems) {
    s = SectionFileScan{};
    const size_t before = problems.size();
    auto bad = [&](size_t i, const std::string& what) { problems.push_back("새 섹션 " + std::to_string(i + 1) + "째 줄 — " + what); };
    // 제어 문자(탭 밖) — 주석 · 제목 줄은 글자 그대로 덱에 들어간다(조각과 같은 규칙 · 리뷰 11-07)
    for (size_t i = 0; i < in.size(); ++i)
        if (std::any_of(in[i].begin(), in[i].end(), [](char c) {
                const unsigned char u = static_cast<unsigned char>(c);
                return (u < 0x20 && u != '\t') || u == 0x7F;
            }))
            bad(i, "제어 문자가 든 줄 — 인쇄할 수 있는 글자(와 탭)만 싣는다");
    // 키워드 줄 셋 — *KEYWORD · 셸 섹션 · *END(그 차례 · 그 밖의 키워드 없음)
    std::vector<size_t> kws;
    for (size_t i = 0; i < in.size(); ++i)
        if (cardcut::isKeywordLine(in[i])) kws.push_back(i);
    auto tok = [&](size_t i) { return deckscan::keywordToken(in[i]); };
    for (size_t i = 0; i < (kws.empty() ? in.size() : kws.front()); ++i)
        if (deckscan::isDataLine(in[i])) bad(i, "*KEYWORD 앞의 데이터 줄");
    if (kws.empty() || deckscan::kwBare(tok(kws[0])) != "*KEYWORD") {
        problems.push_back("새 섹션 — 첫 키워드가 *KEYWORD 가 아니다");
        return false;
    }
    if (const int w = keywordCardDeckWidth(in[kws[0]]); w != 0 && w != 8) bad(kws[0], "*KEYWORD 의 폭이 표준(8)이 아니다");
    if (kws.size() < 2) { problems.push_back("새 섹션 — 셸 섹션 카드가 없다"); return false; }
    const size_t sk = kws[1];
    const std::string skw = tok(sk);
    if (skw != "*SECTION_SHELL" && skw != "*SECTION_SHELL_TITLE") {
        bad(sk, "키워드 " + skw + " — *SECTION_SHELL · *SECTION_SHELL_TITLE 카드 하나만 싣는다(칸 폭 접미사 없이)");
        return false;
    }
    for (size_t i = kws[0] + 1; i < sk; ++i) {
        if (deckscan::isDataLine(in[i])) bad(i, "*KEYWORD 와 섹션 카드 사이의 데이터 줄");
        else if (cardcut::isCommentLine(in[i])) s.head.push_back(in[i]);
    }
    if (kws.size() < 3) { problems.push_back("새 섹션 — *END 가 없다(잘린 파일일 수 있다)"); return false; }
    const size_t ek = kws[2];
    if (deckscan::kwBare(tok(ek)) != "*END") {
        bad(ek, "섹션 카드 뒤의 키워드 " + tok(ek) + " — 셸 섹션 카드 하나와 *END 만 싣는다");
        return false;
    }
    for (size_t k = 3; k < kws.size(); ++k) bad(kws[k], "*END 뒤의 키워드 " + tok(kws[k]));
    for (size_t i = ek + 1; i < in.size(); ++i)
        if (deckscan::isDataLine(in[i])) bad(i, "*END 뒤의 데이터 줄");
    s.block.assign(in.begin() + static_cast<long>(sk), in.begin() + static_cast<long>(ek));
    std::string why;
    if (!shellSectionRows(s.block, s.row1, s.row2, why)) {
        problems.push_back("새 섹션 — " + why);
        return false;
    }
    const auto c1 = cardcut::cut(s.block[s.row1], 10).f;
    if (c1.empty() || !parseLL(c1[0], s.secid) || s.secid <= 0) bad(sk + s.row1, "Card 1 의 SECID 를 읽지 못했다");   // ID 칸은 정수 글자만
    if (c1.size() > 1) parseIntegral(c1[1], s.elform);
    const auto c2 = cardcut::cut(s.block[s.row2], 10).f;
    for (size_t k = 0; k < 4; ++k)
        if (k >= c2.size() || !parseReal(c2[k], s.t[k])) {
            bad(sk + s.row2, "Card 2 의 T" + std::to_string(k + 1) + " 을 읽지 못했다(넷 다 적혀 있어야 한다)");
            break;
        }
    return problems.size() == before;
}

void compareSectionCards(const std::vector<std::string>& deck, const SectionFileScan& s, std::vector<std::string>& problems) {
    auto tail = [](const std::string& l, size_t n) { return l.size() > n ? l.substr(n) : std::string(); };
    auto clip = [](const std::string& l) { return "'" + clipUtf8(l, 60) + "'"; };
    if (deck.size() != s.block.size()) {
        problems.push_back("줄 수 " + std::to_string(s.block.size()) + " 가 덱의 옛 카드(" + std::to_string(deck.size()) +
                           " 줄 — 키워드 줄부터 다음 키워드 앞까지)와 다르다 — 옛 카드를 그대로 옮긴 카드가 아니다");
        return;
    }
    size_t shown = 0;
    for (size_t k = 0; k < deck.size() && shown < 3; ++k) {
        const std::string& a = deck[k];
        const std::string& b = s.block[k];
        std::string what;
        if (k == s.row1) {
            if (tail(a, 10) != tail(b, 10)) what = "(Card 1)의 SECID 밖 칸(ELFORM · SHRF · NIP · PROPT · QR/IRID · ICOMP · SETYP)이";
        } else if (k == s.row2) {
            if (tail(a, 40) != tail(b, 40)) what = "(Card 2)의 T1~T4 밖 칸(NLOC · MAREA · IDOF · EDGSET)이";
        } else if (a != b) {
            what = k == 0 ? "(키워드)이" : "이";
        }
        if (what.empty()) continue;
        ++shown;
        problems.push_back("블록 " + std::to_string(k + 1) + "째 줄" + what + " 덱의 옛 카드와 다르다 — 덱 " + clip(a) + " · 새 " + clip(b) +
                           " (SECID 와 T1~T4 만 바꿀 수 있다)");
    }
}

bool integralField(const std::string& s, long long& v) { return parseIntegral(s, v); }

bool bytesGiveLines(const std::string& bytes, const std::vector<std::string>& lines, bool include) {
    size_t k = 0;
    for (size_t p = 0; p < bytes.size();) {
        size_t e = bytes.find('\n', p);
        if (e == std::string::npos) e = bytes.size();
        std::string_view l(bytes.data() + p, e - p);
        p = e + 1;
        if (!l.empty() && l.back() == '\r') l.remove_suffix(1);
        if (include) {
            if (k == 0 && l.size() >= 3 && l.substr(0, 3) == "\xEF\xBB\xBF") l.remove_prefix(3);
            const std::string t(l);
            if (!deckscan::isDataLine(t) && deckscan::keywordToken(t) == "*END") break;   // 그 파일은 여기서 끝난다 — 뒤는 담지 않았다
        }
        if (k >= lines.size() || l != std::string_view(lines[k])) return false;
        ++k;
    }
    return k == lines.size();
}

std::string toJson(const Report& r) {
    std::ostringstream o;
    o << "{\n  \"format\": \"dynaforge-carryover-apply\",\n  \"version\": 1,\n  \"ok\": " << (r.ok ? "true" : "false") << ",\n";
    o << "  \"output_written\": " << (r.outputWritten ? "true" : "false") << ",\n";
    o << "  \"plan\": {\"sha256\": " << (r.planRead ? q(r.planSha256) : "null")
      << ", \"version\": " << (r.planParsed ? std::to_string(r.planVersion) : "null")
      << ", \"report_key\": " << (r.planParsed ? q(r.reportKey) : "null")
      << ", \"deck_from\": " << (r.deckFrom.empty() ? "null" : q(r.deckFrom)) << "},\n";
    o << "  \"deck\": {\"sha256_in\": " << (r.deckShaIn.empty() ? "null" : q(r.deckShaIn))
      << ", \"sha256_out\": " << (r.deckShaOut.empty() ? "null" : q(r.deckShaOut)) << ", \"includes\": ";
    if (!r.includesChecked) o << "null";
    else {
        o << "[";
        for (size_t k = 0; k < r.includes.size(); ++k)
            o << (k ? ", " : "") << "{\"relpath\": " << q(r.includes[k].relpath) << ", \"sha256\": " << q(r.includes[k].sha256) << "}";
        o << "]";
    }
    o << "},\n";
    auto list = [&](const char* key, const std::vector<Problem>& v) {
        o << "  \"" << key << "\": [";
        for (size_t k = 0; k < v.size(); ++k) o << (k ? ",\n    " : "\n    ") << problemJson(v[k]);
        o << (v.empty() ? "]" : "\n  ]") << ",\n";
    };
    list("problems", r.problems);
    list("warnings", r.warnings);
    if (r.shifted) o << "  \"shift\": {\"node\": " << r.shiftNode << ", \"elem\": " << r.shiftElem << "},\n";
    else o << "  \"shift\": null,\n";
    o << "  \"parts\": [";
    for (size_t k = 0; k < r.parts.size(); ++k) {
        const auto& p = r.parts[k];
        o << (k ? ",\n    " : "\n    ") << "{\"pid\": " << p.pid << ", \"action\": " << q(p.action) << ", \"result\": " << q(p.result);
        if (p.hasMove) o << ", \"nodes_moved\": " << p.nodesMoved << ", \"max_disp\": " << num(p.maxDisp);
        if (p.hasRemoved) o << ", \"removed\": {\"nodes\": " << p.removedNodes << ", \"elements\": " << p.removedElements << "}";
        if (p.hasInserted)
            o << ", \"inserted\": {\"node\": [" << p.insNodeLo << ", " << p.insNodeHi << "], \"elem\": [" << p.insElemLo << ", "
              << p.insElemHi << "]}";
        if (p.hasNewSection && p.newSectionShell)
            o << ", \"new_section\": {\"secid\": " << p.newSecid << ", \"thickness\": " << num(p.newThickness) << "}";
        else if (p.hasNewSection)
            o << ", \"new_section\": {\"secid\": " << p.newSecid << ", \"elform\": " << p.newElform << "}";
        if (p.hasRefusedTransform) {
            o << ", \"refused_transform\": {\"transform\": [";
            for (size_t m = 0; m < 16; ++m) o << (m ? ", " : "") << num(p.refusedM[m]);
            o << "], \"det\": " << num(p.refusedDet) << ", \"scale\": " << num(p.refusedScale)
              << ", \"orthogonality_error\": " << num(p.refusedOrth) << "}";
        }
        if (p.hasInverted) o << ", \"inverted_before\": " << p.invertedBefore << ", \"inverted_after\": " << p.invertedAfter;
        if (p.hasFlipped) o << ", \"flipped\": " << p.flipped;
        if (!p.absorbed.empty()) {
            o << ", \"absorbed\": [";
            for (size_t a = 0; a < p.absorbed.size(); ++a) o << (a ? ", " : "") << q(p.absorbed[a]);
            o << "]";
        }
        o << "}";
    }
    o << (r.parts.empty() ? "]" : "\n  ]") << ",\n";
    o << "  \"added\": [";
    for (size_t k = 0; k < r.added.size(); ++k) {
        const auto& a = r.added[k];
        o << (k ? ",\n    " : "\n    ") << "{\"name\": " << q(a.name);
        if (a.hasPid) o << ", \"pid\": " << a.pid;
        o << ", \"result\": " << q(a.result);
        if (!a.why.empty()) o << ", \"why\": " << q(a.why);
        o << "}";
    }
    o << (r.added.empty() ? "]" : "\n  ]") << ",\n";
    o << "  \"touches_changed\": [";
    for (size_t k = 0; k < r.touches.size(); ++k)
        o << (k ? ", " : "") << "{\"pid\": " << r.touches[k].pid << ", \"with\": " << intList(r.touches[k].with) << "}";
    o << "]\n}\n";
    return o.str();
}

}  // namespace carryover
}  // namespace KooRemapper
