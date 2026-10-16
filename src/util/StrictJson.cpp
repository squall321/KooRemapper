// 엄격한 JSON 리더 구현 — 재귀 하강, 문법(RFC 8259) 밖은 거절한다
#include "util/StrictJson.h"

#include <cerrno>
#include <cstdlib>

namespace KooRemapper {
namespace json {

const Value* Value::get(const std::string& key) const {
    if (type != Type::Object) return nullptr;
    for (const auto& kv : obj)
        if (kv.first == key) return &kv.second;
    return nullptr;
}

namespace {

constexpr int kMaxDepth = 64;

struct Reader {
    const std::string& s;
    size_t p = 0;
    std::string err;

    bool fail(const std::string& what) {
        if (err.empty()) err = std::to_string(p) + "째 바이트: " + what;
        return false;
    }
    void ws() {
        while (p < s.size() && (s[p] == ' ' || s[p] == '\t' || s[p] == '\n' || s[p] == '\r')) ++p;
    }
    bool literal(const char* word, Value& v, Value::Type t, bool b) {
        const std::string w(word);
        if (s.compare(p, w.size(), w) != 0) return fail("알 수 없는 낱말");
        p += w.size();
        v.type = t;
        v.b = b;
        return true;
    }
    static void utf8(std::string& out, unsigned cp) {
        if (cp < 0x80) {
            out += (char)cp;
        } else if (cp < 0x800) {
            out += (char)(0xC0 | (cp >> 6));
            out += (char)(0x80 | (cp & 0x3F));
        } else if (cp < 0x10000) {
            out += (char)(0xE0 | (cp >> 12));
            out += (char)(0x80 | ((cp >> 6) & 0x3F));
            out += (char)(0x80 | (cp & 0x3F));
        } else {
            out += (char)(0xF0 | (cp >> 18));
            out += (char)(0x80 | ((cp >> 12) & 0x3F));
            out += (char)(0x80 | ((cp >> 6) & 0x3F));
            out += (char)(0x80 | (cp & 0x3F));
        }
    }
    bool hex4(unsigned& u) {
        if (p + 4 > s.size()) return fail("\\u 뒤 16진 넷이 모자라다");
        u = 0;
        for (int k = 0; k < 4; ++k) {
            const char c = s[p++];
            u <<= 4;
            if (c >= '0' && c <= '9') u |= (unsigned)(c - '0');
            else if (c >= 'a' && c <= 'f') u |= (unsigned)(c - 'a' + 10);
            else if (c >= 'A' && c <= 'F') u |= (unsigned)(c - 'A' + 10);
            else return fail("\\u 뒤가 16진이 아니다");
        }
        return true;
    }
    bool string(std::string& out) {
        ++p;   // 여는 "
        while (true) {
            if (p >= s.size()) return fail("닫히지 않은 문자열");
            const unsigned char c = (unsigned char)s[p];
            if (c == '"') { ++p; return true; }
            if (c < 0x20) return fail("문자열 안의 제어 문자");
            if (c != '\\') { out += (char)c; ++p; continue; }
            ++p;
            if (p >= s.size()) return fail("이스케이프가 끝났다");
            const char e = s[p++];
            switch (e) {
                case '"': out += '"'; break;
                case '\\': out += '\\'; break;
                case '/': out += '/'; break;
                case 'b': out += '\b'; break;
                case 'f': out += '\f'; break;
                case 'n': out += '\n'; break;
                case 'r': out += '\r'; break;
                case 't': out += '\t'; break;
                case 'u': {
                    unsigned u = 0;
                    if (!hex4(u)) return false;
                    if (u >= 0xDC00 && u <= 0xDFFF) return fail("짝 없는 아래 서로게이트");
                    if (u >= 0xD800 && u <= 0xDBFF) {
                        if (s.compare(p, 2, "\\u") != 0) return fail("위 서로게이트 뒤에 짝이 없다");
                        p += 2;
                        unsigned lo = 0;
                        if (!hex4(lo)) return false;
                        if (lo < 0xDC00 || lo > 0xDFFF) return fail("서로게이트 짝이 맞지 않는다");
                        u = 0x10000 + ((u - 0xD800) << 10) + (lo - 0xDC00);
                    }
                    utf8(out, u);
                    break;
                }
                default: return fail("모르는 이스케이프");
            }
        }
    }
    bool number(Value& v) {
        const size_t start = p;
        if (s[p] == '-') ++p;
        if (p >= s.size()) return fail("수가 끝났다");
        if (s[p] == '0') {
            ++p;
        } else if (s[p] >= '1' && s[p] <= '9') {
            while (p < s.size() && s[p] >= '0' && s[p] <= '9') ++p;
        } else {
            return fail("수의 꼴이 아니다");
        }
        bool real = false;
        if (p < s.size() && s[p] == '.') {
            real = true;
            ++p;
            if (p >= s.size() || s[p] < '0' || s[p] > '9') return fail("소수점 뒤에 숫자가 없다");
            while (p < s.size() && s[p] >= '0' && s[p] <= '9') ++p;
        }
        if (p < s.size() && (s[p] == 'e' || s[p] == 'E')) {
            real = true;
            ++p;
            if (p < s.size() && (s[p] == '+' || s[p] == '-')) ++p;
            if (p >= s.size() || s[p] < '0' || s[p] > '9') return fail("지수에 숫자가 없다");
            while (p < s.size() && s[p] >= '0' && s[p] <= '9') ++p;
        }
        const std::string tok = s.substr(start, p - start);
        errno = 0;
        if (real) {
            v.type = Value::Type::Real;
            v.d = std::strtod(tok.c_str(), nullptr);
        } else {
            v.type = Value::Type::Int;
            v.i = std::strtoll(tok.c_str(), nullptr, 10);
            if (errno == ERANGE) return fail("int64 를 넘는 정수");
        }
        return true;
    }
    bool value(Value& v, int depth) {
        if (depth > kMaxDepth) return fail("깊이 64 를 넘는다");
        ws();
        if (p >= s.size()) return fail("값이 없다");
        const char c = s[p];
        if (c == '{') {
            v.type = Value::Type::Object;
            ++p;
            ws();
            if (p < s.size() && s[p] == '}') { ++p; return true; }
            while (true) {
                ws();
                if (p >= s.size() || s[p] != '"') return fail("객체의 키는 문자열이어야 한다");
                std::string key;
                if (!string(key)) return false;
                for (const auto& kv : v.obj)
                    if (kv.first == key) return fail("같은 키가 두 번 — " + key);
                ws();
                if (p >= s.size() || s[p] != ':') return fail("키 뒤에 ':' 가 없다");
                ++p;
                Value child;
                if (!value(child, depth + 1)) return false;
                v.obj.emplace_back(key, std::move(child));
                ws();
                if (p < s.size() && s[p] == ',') { ++p; continue; }
                if (p < s.size() && s[p] == '}') { ++p; return true; }
                return fail("객체에 ',' 나 '}' 가 와야 한다");
            }
        }
        if (c == '[') {
            v.type = Value::Type::Array;
            ++p;
            ws();
            if (p < s.size() && s[p] == ']') { ++p; return true; }
            while (true) {
                Value child;
                if (!value(child, depth + 1)) return false;
                v.arr.push_back(std::move(child));
                ws();
                if (p < s.size() && s[p] == ',') { ++p; continue; }
                if (p < s.size() && s[p] == ']') { ++p; return true; }
                return fail("배열에 ',' 나 ']' 가 와야 한다");
            }
        }
        if (c == '"') { v.type = Value::Type::String; return string(v.s); }
        if (c == 't') return literal("true", v, Value::Type::Bool, true);
        if (c == 'f') return literal("false", v, Value::Type::Bool, false);
        if (c == 'n') return literal("null", v, Value::Type::Null, false);
        if (c == '-' || (c >= '0' && c <= '9')) return number(v);
        return fail("값이 아니다");
    }
};

}  // namespace

bool parse(const std::string& text, Value& out, std::string& err) {
    Reader r{text};
    out = Value{};
    if (!r.value(out, 0)) { err = r.err; return false; }
    r.ws();
    if (r.p != text.size()) { r.fail("값 뒤에 다른 글이 있다"); err = r.err; return false; }
    return true;
}

}  // namespace json
}  // namespace KooRemapper
