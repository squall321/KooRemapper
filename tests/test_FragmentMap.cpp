// StepForge 조각 계약 — SHA-256 · 엄격 JSON · 대응표 칸 집합 · coord_sha(저쪽 식) · 조각 대조를 못 박는다
//
// 왜 이 파일이 있나 (2026-10-16).
//
//   저쪽(StepForge)이 조각 내보내기를 지었고 대응표 칸 집합을 확정했다(BOUNDARY-DYNAFORGE §3-3). 우리 삽입은
//   그것을 **계약 그대로** 읽어야 한다 — 모르는 칸은 거절하고, `coord_sha` 는 저쪽과 **같은 값**이어야 검증
//   관문이 된다. 기댓값 해시는 저쪽 식(`f"{v:16.9e}"` · 사전순 · sha256 앞 16자)을 파이썬으로 돌려 얻었다.
#include "TestFramework.h"
#include "parser/FragmentMap.h"
#include "util/Sha256.h"
#include "util/StrictJson.h"

#include <filesystem>
#include <fstream>
#include <string>

using namespace KooRemapper;

namespace {
namespace fs = std::filesystem;

struct FragScratch {
    fs::path root;
    explicit FragScratch(const std::string& tag) {
        root = fs::temp_directory_path() / ("koorm_frag_" + tag);
        std::error_code ec;
        fs::remove_all(root, ec);
        fs::create_directories(root);
    }
    ~FragScratch() { std::error_code ec; fs::remove_all(root, ec); }
    std::string put(const std::string& name, const std::string& body) const {
        const fs::path p = root / name;
        std::ofstream(p, std::ios::binary) << body;
        return p.string();
    }
};

bool has(const std::vector<std::string>& v, const std::string& needle) {
    for (const auto& s : v) if (s.find(needle) != std::string::npos) return true;
    return false;
}

const char* kFragment =
    "*KEYWORD\n"
    "$# StepForge — test — 조각 abc\n"
    "$# 단위 mm-t-s (밀도 t/mm³, 예 강철 7.85e-9)\n"
    "*NODE\n"
    "       1 0.000000000e+00 0.000000000e+00 0.000000000e+00\n"
    "       2 1.000000000e+00 0.000000000e+00 0.000000000e+00\n"
    "       3 1.000000000e+00 1.000000000e+00 0.000000000e+00\n"
    "       4 0.000000000e+00 1.000000000e+00 0.000000000e+00\n"
    "       5 0.000000000e+00 0.000000000e+00 1.000000000e+00\n"
    "       6 1.000000000e+00 0.000000000e+00 1.000000000e+00\n"
    "       7 1.000000000e+00 1.000000000e+00 1.000000000e+00\n"
    "       8 0.000000000e+00 1.000000000e+00 1.000000000e+00\n"
    "       9-3.000000000e+01-1.500000000e+01 2.000000000e+01\n"
    "      10-2.000000000e+01-1.500000000e+01 2.000000000e+01\n"
    "      11-2.000000000e+01-5.000000000e+00 2.000000000e+01\n"
    "      12-3.000000000e+01-5.000000000e+00 2.000000000e+01\n"
    "*ELEMENT_SOLID\n"
    "       1       1       1       2       3       4       5       6       7       8\n"
    "*ELEMENT_SHELL\n"
    "       2       2       9      10      11      12\n"
    "*PART\ncube\n         1         1         1\n"
    "*PART\nplate\n         2         2         2\n"
    "*SECTION_SOLID_TITLE\ncube\n         1         1\n"
    "*SECTION_SHELL_TITLE\nplate\n         2         2       1.0         2\n       0.3       0.3       0.3       0.3\n"
    "*MAT_ELASTIC_TITLE\ncube\n         1    7.85E-9  210000.0       0.3\n"
    "*MAT_ELASTIC_TITLE\nplate\n         2    7.85E-9  210000.0       0.3\n"
    "*END\n";

std::string mapJson(const std::string& sha1, const std::string& sha2, const std::string& nodeRange = "[1, 12]",
                    const std::string& extraTop = "") {
    return "{\"unit\": \"mm-t-s\", \"frame\": \"world\", " + extraTop +
           "\"ranges\": {\"node\": " + nodeRange + ", \"elem\": [1, 2], \"pid\": [1, 2], \"sid\": null},"
           " \"parts\": ["
           "{\"path\": \"/ASM/CUBE\", \"name\": \"cube\", \"pid\": 1, \"node_start\": 1, \"node_count\": 8,"
           " \"elem_start\": 1, \"elem_count\": 1, \"coord_sha\": \"" + sha1 + "\"},"
           "{\"path\": \"/ASM/PLATE\", \"name\": \"plate\", \"pid\": 2, \"node_start\": 9, \"node_count\": 4,"
           " \"elem_start\": 2, \"elem_count\": 1, \"coord_sha\": \"" + sha2 + "\"}]}";
}

std::string cubeSha() {
    return fragment::coordSha({{0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0}, {0, 0, 1}, {1, 0, 1}, {1, 1, 1}, {0, 1, 1}});
}
std::string plateSha() {
    return fragment::coordSha({{-30, -15, 20}, {-20, -15, 20}, {-20, -5, 20}, {-30, -5, 20}});
}

}  // namespace

TEST(Sha256_표준_벡터) {
    ASSERT_EQ(util::sha256Hex(""), std::string("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"));
    ASSERT_EQ(util::sha256Hex("abc"), std::string("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));
    ASSERT_EQ(util::sha256Hex("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
              std::string("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"));
    // 꼬리가 한 블록·두 블록으로 갈리는 경계(55·56·64바이트)와 긴 입력
    ASSERT_EQ(util::sha256Hex(std::string(55, 'a')), std::string("9f4390f8d30c2dd92ec9f095b65e2b9ae9b0a925a5258e241c9f1e910f734318"));
    ASSERT_EQ(util::sha256Hex(std::string(56, 'a')), std::string("b35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde7090ef7970686ec6738a"));
    ASSERT_EQ(util::sha256Hex(std::string(64, 'a')), std::string("ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb"));
    ASSERT_EQ(util::sha256Hex(std::string(1000000, 'a')),
              std::string("cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"));
}

TEST(coordSha_저쪽_식과_같은_값) {
    // 기댓값 — 저쪽 `core/remesh_impact.coord_sha` 의 식을 파이썬으로 그대로 돌려 얻었다
    ASSERT_EQ(fragment::coordSha({{0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0}, {0, 0, 1}, {1, 0, 1}, {1, 1, 1}, {0, 1, 1}}),
              std::string("73a2372c4df4836c"));
    // 음수 · 음의 0 · 세 자리 지수(16칸을 넘는다 — 파이썬과 C 가 같은 규칙으로 넓힌다)
    ASSERT_EQ(fragment::coordSha({{-30.0, -15.0, 20.0}, {1.5e-7, -0.0, 123456.789}, {9.87654321e10, -1e-300, 0.1}}),
              std::string("17d54cdc8e4bf4f0"));
    ASSERT_EQ(fragment::coordSha({{0.1, 0.2, 0.3}}), std::string("91242175d3c42b1a"));
    // 번호·순서와 무관하다
    ASSERT_EQ(fragment::coordSha({{0, 1, 1}, {1, 1, 1}, {0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0}, {0, 0, 1}, {1, 0, 1}}),
              std::string("73a2372c4df4836c"));
}

TEST(StrictJson_읽는다_유니코드_이스케이프) {
    json::Value v;
    std::string err;
    ASSERT_TRUE(json::parse("{\"a\": [1, -2, 3.5e2, true, null], \"k\": \"\\uD55C \\uD83D\\uDE00 \\n\"}", v, err));
    ASSERT_EQ(v.get("a")->arr.size(), (size_t)5);
    ASSERT_EQ(v.get("a")->arr[1].i, -2LL);
    ASSERT_TRUE(v.get("a")->arr[2].type == json::Value::Type::Real);
    ASSERT_EQ(v.get("k")->s, std::string("\xED\x95\x9C \xF0\x9F\x98\x80 \n"));   // 한 · 😀 · 줄바꿈
    ASSERT_TRUE(json::parse("9999999999", v, err));                               // 10자리 sid — int64
    ASSERT_EQ(v.i, 9999999999LL);
}

TEST(StrictJson_거절하는_꼴) {
    json::Value v;
    std::string err;
    for (const char* bad : {"1 2", "{\"a\": 1, \"a\": 2}", "01", "+1", ".5", "1.", "[1,]", "{\"a\" 1}",
                            "\"\\uDC00\"", "\"\\uD83D\"", "\"a\tb\"", "\"\\q\"", "tru", "[1] x",
                            "99999999999999999999"}) {
        err.clear();
        ASSERT_FALSE(json::parse(bad, v, err));
        ASSERT_FALSE(err.empty());
    }
}

TEST(대응표_계약_칸_그대로_읽는다) {
    fragment::Map m;
    std::string err;
    ASSERT_TRUE(fragment::parseMap(mapJson(cubeSha(), plateSha()), m, err));
    ASSERT_EQ(m.unit, std::string("mm-t-s"));
    ASSERT_EQ(m.frame, std::string("world"));
    ASSERT_TRUE(m.node.used && m.node.lo == 1 && m.node.hi == 12);
    ASSERT_FALSE(m.sid.used);                                   // null 을 받는다(저쪽 새 질문 4)
    ASSERT_EQ(m.parts.size(), (size_t)2);
    ASSERT_EQ(m.parts[1].nodeStart, 9LL);
}

TEST(대응표_모르는_칸_빠진_칸_꼴_밖은_거절) {
    fragment::Map m;
    std::string err;
    ASSERT_FALSE(fragment::parseMap(mapJson(cubeSha(), plateSha(), "[1, 12]", "\"extra\": 1, "), m, err));
    ASSERT_TRUE(err.find("모르는 칸 'extra'") != std::string::npos);
    ASSERT_FALSE(fragment::parseMap("{\"unit\": \"mm-t-s\", \"frame\": \"world\", \"parts\": []}", m, err));
    ASSERT_TRUE(err.find("'ranges'") != std::string::npos);
    ASSERT_FALSE(fragment::parseMap(mapJson("XYZ", plateSha()), m, err));               // coord_sha 꼴
    ASSERT_FALSE(fragment::parseMap(mapJson(cubeSha(), plateSha(), "[12, 1]"), m, err));  // lo > hi
    ASSERT_FALSE(fragment::parseMap(mapJson(cubeSha(), plateSha(), "[1]"), m, err));
}

TEST(조각_대조_맞으면_조용하다) {
    FragScratch d("ok");
    const auto k = d.put("f.k", kFragment);
    fragment::Map m;
    std::string err;
    ASSERT_TRUE(fragment::parseMap(mapJson(cubeSha(), plateSha()), m, err));
    const auto bad = fragment::check(m, k);
    ASSERT_TRUE(bad.empty());
}

TEST(조각_대조_좌표_구간_파트_세트를_말한다) {
    FragScratch d("bad");
    fragment::Map m;
    std::string err;
    ASSERT_TRUE(fragment::parseMap(mapJson(cubeSha(), plateSha()), m, err));
    // ① 절점 하나를 옮겼다 → 그 파트의 coord_sha 가 다르다
    std::string moved = kFragment;
    moved.replace(moved.find("       3 1.000000000e+00"), 24, "       3 1.500000000e+00");
    ASSERT_TRUE(has(fragment::check(m, d.put("moved.k", moved)), "PID 1(cube) — coord_sha"));
    // ② ranges 가 실제 최소·최대와 다르다
    fragment::Map m2;
    ASSERT_TRUE(fragment::parseMap(mapJson(cubeSha(), plateSha(), "[1, 13]"), m2, err));
    ASSERT_TRUE(has(fragment::check(m2, d.put("ok.k", kFragment)), "절점 실제 [1, 12]"));
    // ③ 대응표에 없는 파트가 조각에 있다
    std::string extra = kFragment;
    extra.insert(extra.find("*END"), "*PART\nghost\n         3         1         1\n");
    ASSERT_TRUE(has(fragment::check(m, d.put("extra.k", extra)), "조각의 PID 3"));
    // ④ sid 가 null 인데 *SET_* 가 있다
    std::string withSet = kFragment;
    withSet.insert(withSet.find("*END"), "*SET_PART_LIST\n         5\n         1\n");
    ASSERT_TRUE(has(fragment::check(m, d.put("set.k", withSet)), "SID"));
}
