#pragma once

#include <map>

#include "core/Mesh.h"
#include <string>
#include <fstream>
#include <vector>
#include <functional>

// Knowledge graph (lat.md):
//   @lat: [[modules/parser]]

namespace KooRemapper {

/**
 * Parser for LS-DYNA keyword (.k) files
 *
 * Supports:
 *   - *NODE
 *   - *ELEMENT_SOLID / *ELEMENT_TSHELL / *ELEMENT_SHELL
 *   - *PART (with material ID mapping)
 *   - *MAT_ELASTIC (001)
 *   - *MAT_PIECEWISE_LINEAR_PLASTICITY (024)
 *   - *MAT_RIGID (020)
 *   - *MAT_VISCOELASTIC (006) - uses gi (long-time shear modulus)
 *   - *END
 */
class KFileReader {
public:
    using ProgressCallback = std::function<void(int percent)>;

    KFileReader();
    ~KFileReader() = default;

    /**
     * Read a k-file and return the mesh
     * @param filename Path to the k-file
     * @return Parsed mesh
     * @throws std::runtime_error on parse errors
     */
    Mesh readFile(const std::string& filename);

    // 인클루드 닫힘까지 읽는다 — **분석 전용**(info · modelmeta · 그림 셋). 덱을 고쳐 쓰는 op 은 주 덱만 읽는
    // `readFile` 을 쓴다(인클루드 안의 카드를 고쳐 쓸 길이 없다). 닫힘은 정본(`include_closure`)으로 LS-DYNA 가 읽는
    // 차례대로 펼치고, 펼친 줄을 임시 파일에 써 **같은 파서로** 읽는다(파서를 둘로 두지 않는다).
    //   · 인클루드가 없으면 `readFile` 과 똑같다.
    //   · 정수 칸 폭은 주 덱 `*KEYWORD` 가 정한다 — 인클루드 파일 안의 `*KEYWORD` 줄은 뺀다(LS-DYNA 규칙 · 실사용 88장에서
    //     갈린 덱 0). `*INCLUDE +`·`*INCLUDE -`(그 파일의 폭을 바꾼다)가 있으면 펼치지 않고 주 덱만 읽는다.
    // `note` 에는 사람이 읽을 한 줄(무엇을 읽었나 · 왜 주 덱만 읽었나)을, `complete` 에는 닫힘을 다 읽었는지를 돌려준다.
    Mesh readFileWithIncludes(const std::string& filename, std::string* note = nullptr, bool* complete = nullptr);

    /**
     * Set progress callback
     */
    void setProgressCallback(ProgressCallback callback) {
        progressCallback_ = callback;
    }

    /**
     * Get last error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

    /**
     * Get number of lines processed
     */
    int getLinesProcessed() const { return linesProcessed_; }

private:
    Mesh mesh_;
    std::string errorMessage_;
    std::string currentKeyword_;
    // 지금 섹션의 키워드 줄 원문 — 칸 폭 접미사('%','+','-')가 여기에만 남는다.
    // currentKeyword_ 는 extractKeyword 가 접미사를 떼어 버려 폭 판정에 쓸 수 없다.
    std::string currentKeywordLine_;
    int currentLine_;
    int linesProcessed_;
    long fileSize_;
    bool i10_ = false;  // i10=y flag: use 10-char integer fields
    int  deckFw_ = 8;   // *KEYWORD 가 정한 덱 기본 정수 칸 폭(8/10/20) — Vol_I 19305-19360
    // 지금 섹션의 정수 칸 폭. 키워드 접미사가 덱 기본값을 덮어쓴다(19342-19360).
    int sectionFieldWidth() const;
    // PID → 그 파트 요소의 절점 수(고차 정식일 때만 채운다). *PART 의 SECID 를 풀어
    // *SECTION_SOLID 의 ELFORM 23-29 를 본다(Vol_I 228671-228677). 요소 줄만 보고는
    // 카드가 몇 줄인지 알 수 없어서, 요소를 읽기 전에 미리 훑어 둔다.
    std::map<int, int> pidHighOrderNodes_;
    // 2차 솔리드 하나 — 코너를 위상 표 자리에, 전체 절점을 `Mesh::solidAllNodes` 에 담는다(정의의 주석 참조).
    void addSecondOrderSolid(int eid, int pid, const std::vector<int>& all);
    // *PART·*SECTION_SOLID 만 훑어 pidHighOrderNodes_ 를 채운다(요소를 읽기 전에 한 번).
    void prescanPartSections(std::ifstream& file);
    ProgressCallback progressCallback_;
    std::vector<std::pair<int, std::string>> unsupportedMaterials_;  // (MID, keyword)

    // Parse methods
    bool parseFile(std::ifstream& file);
    bool parseNodeSection(std::ifstream& file);
    bool parseElementSolidSection(std::ifstream& file);
    bool parseElementShellSection(std::ifstream& file);
    bool parsePartSection(std::ifstream& file);
    bool parseMatElasticSection(std::ifstream& file);
    bool parseMatPlasticSection(std::ifstream& file);
    bool parseMatRigidSection(std::ifstream& file);
    bool parseMatViscoelasticSection(std::ifstream& file);
    bool parseMatMooneyRivlinSection(std::ifstream& file);
    bool parseSectionShellSection(std::ifstream& file);
    void skipToNextKeyword(std::ifstream& file);
    void skipDataLines(std::ifstream& file, int count);
    bool isMaterialKeyword(const std::string& keyword) const;
    bool isSupportedMaterial(const std::string& keyword) const;

    // Helper methods
    bool isKeywordLine(const std::string& line) const;
    bool isCommentLine(const std::string& line) const;
    std::string extractKeyword(const std::string& line) const;
    std::vector<std::string> tokenize(const std::string& line) const;
    std::vector<std::string> tokenizeFixed(const std::string& line, int fieldWidth = 10) const;
    std::string trim(const std::string& str) const;

    // Fixed-format parsing (LS-DYNA uses fixed column widths)
    double parseDouble(const std::string& str) const;
    int parseInt(const std::string& str) const;

    // Report progress
    void reportProgress(std::streampos currentPos);
};

} // namespace KooRemapper
