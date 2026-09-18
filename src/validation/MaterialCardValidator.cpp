#include "validation/MaterialCardValidator.h"
#include <sstream>
#include <algorithm>
#include <cctype>
#include <cmath>

// Knowledge graph (lat.md):
//   @lat: [[modules/validation]]

namespace KooRemapper {

MaterialCardValidator::ValidationResult MaterialCardValidator::validate(
    const std::string& materialCard) {

    ValidationResult result;
    result.isValid = true;

    if (materialCard.empty()) {
        result.addError("Material card is empty");
        return result;
    }

    // Split into lines
    std::vector<std::string> lines;
    std::istringstream iss(materialCard);
    std::string line;
    while (std::getline(iss, line)) {
        lines.push_back(line);
    }

    if (lines.empty()) {
        result.addError("Material card has no content");
        return result;
    }

    // Find keyword line
    std::string keyword;
    int keywordLineIdx = -1;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (isKeywordLine(lines[i])) {
            keyword = extractKeyword(lines[i]);
            keywordLineIdx = static_cast<int>(i);
            break;
        }
    }

    if (keyword.empty()) {
        result.addError("No valid *MAT_ keyword found");
        return result;
    }

    // MID 칸은 @MID@ 가 아니어도(10·MAT01·@CZM_MID@) 새 MID 로 바뀌므로 자리표시 유무는 검사하지 않는다

    // Validate based on keyword type.
    // 부분 문자열로 고르면 *MAT_ELASTIC_FLUID·*MAT_ELASTIC_PLASTIC_THERMAL·
    // *MAT_ELASTIC_SPRING_DISCRETE_BEAM 처럼 칸 뜻이 전혀 다른 변종까지 평범한 ELASTIC 으로 검사해
    // 합법 카드에 엉뚱한 오류를 냈다 — _TITLE 만 떼고 정확히 일치할 때만 그 검사를 쓴다.
    std::string base = keyword;
    if (base.size() > 6 && base.compare(base.size() - 6, 6, "_TITLE") == 0)
        base.erase(base.size() - 6);
    if (base == "*MAT_ELASTIC") {
        validateElastic(lines, result);
    } else if (base == "*MAT_COHESIVE_MIXED_MODE") {
        validateCohesiveMixedMode(lines, result);
    } else if (base == "*MAT_PLASTIC_KINEMATIC" || base == "*MAT_024") {
        validatePlasticKinematic(lines, result);
    } else {
        // Generic validation for unknown types
        result.addWarning("Unknown material type '" + keyword + "' - skipping detailed validation");
    }

    return result;
}

bool MaterialCardValidator::isKeywordLine(const std::string& line) const {
    std::string upper = line;
    std::transform(upper.begin(), upper.end(), upper.begin(), [](unsigned char c){ return (char)std::toupper(c); });
    return upper.find("*MAT") != std::string::npos;
}

std::string MaterialCardValidator::extractKeyword(const std::string& line) const {
    std::string upper = line;
    std::transform(upper.begin(), upper.end(), upper.begin(), [](unsigned char c){ return (char)std::toupper(c); });

    size_t start = upper.find("*MAT");
    if (start == std::string::npos) return "";

    size_t end = upper.find_first_of(" \t\r\n", start);
    if (end == std::string::npos) end = upper.length();

    return upper.substr(start, end - start);
}

void MaterialCardValidator::validateElastic(
    const std::vector<std::string>& lines, ValidationResult& result) {

    // Find first data line (non-comment, non-blank after keyword; _TITLE 은 제목 줄 다음)
    int dataLineIdx = findFirstDataLine(lines);

    if (dataLineIdx < 0) {
        result.addError("*MAT_ELASTIC: No data line found");
        return;
    }

    auto fields = parseDataLine(lines[dataLineIdx]);

    // Expected: MID RO E PR (at least 4 fields)
    if (fields.size() < 4) {
        result.addError("*MAT_ELASTIC: Expected at least 4 fields (MID, RO, E, PR), found " +
                       std::to_string(fields.size()));
        return;
    }

    // Check if MID is @MID@ (skip numeric check)
    bool midIsPlaceholder = (fields[0] == "@MID@");

    // Validate RO (density) - must be positive
    if (!midIsPlaceholder) {
        try {
            double ro = std::stod(fields[1]);
            if (ro <= 0) {
                result.addWarning("*MAT_ELASTIC: Density (RO) should be positive, got " + fields[1]);
            }
        } catch (...) {
            // Field might be @MID@ or other placeholder
            if (fields[1].find("@") == std::string::npos) {
                result.addWarning("*MAT_ELASTIC: Cannot parse density (RO): " + fields[1]);
            }
        }
    }

    // Validate E (Young's modulus) - must be positive
    try {
        double e = std::stod(fields[2]);
        if (e <= 0) {
            result.addError("*MAT_ELASTIC: Young's modulus (E) must be positive, got " + fields[2]);
        }
    } catch (...) {
        if (fields[2].find("@") == std::string::npos) {
            result.addWarning("*MAT_ELASTIC: Cannot parse Young's modulus (E): " + fields[2]);
        }
    }

    // Validate PR (Poisson's ratio) - must be in (0, 0.5)
    try {
        double pr = std::stod(fields[3]);
        if (pr <= 0 || pr >= 0.5) {
            result.addError("*MAT_ELASTIC: Poisson's ratio (PR) must be in range (0, 0.5), got " + fields[3]);
        }
    } catch (...) {
        if (fields[3].find("@") == std::string::npos) {
            result.addWarning("*MAT_ELASTIC: Cannot parse Poisson's ratio (PR): " + fields[3]);
        }
    }
}

void MaterialCardValidator::validateCohesiveMixedMode(
    const std::vector<std::string>& lines, ValidationResult& result) {

    // Find data lines (_TITLE 은 제목 줄 다음부터)
    std::vector<int> dataLineIndices;
    int firstDataIdx = findFirstDataLine(lines);
    for (size_t i = (firstDataIdx < 0 ? lines.size() : static_cast<size_t>(firstDataIdx));
         i < lines.size(); ++i) {
        if (!isCommentLine(lines[i]) && !isBlankLine(lines[i])) {
            dataLineIndices.push_back(static_cast<int>(i));
        }
    }

    if (dataLineIndices.size() < 2) {
        result.addError("*MAT_COHESIVE_MIXED_MODE: Expected at least 2 data lines (Card 1 and Card 2)");
        return;
    }

    // Card 1: MID, RO, ROFLG, INTFAIL
    auto card1 = parseDataLine(lines[dataLineIndices[0]]);
    if (card1.size() < 4) {
        result.addWarning("*MAT_COHESIVE_MIXED_MODE Card 1: Expected 4 fields, found " +
                         std::to_string(card1.size()));
    }

    // Card 2: EN, ET, GNC, GTC, XMU, T, S
    auto card2 = parseDataLine(lines[dataLineIndices[1]]);
    if (card2.size() < 7) {
        result.addWarning("*MAT_COHESIVE_MIXED_MODE Card 2: Expected 7 fields, found " +
                         std::to_string(card2.size()));
    } else {
        // Validate EN, ET (cohesive stiffness) - must be positive
        try {
            double en = std::stod(card2[0]);
            if (en <= 0) {
                result.addError("*MAT_COHESIVE_MIXED_MODE: Normal stiffness (EN) must be positive");
            }
        } catch (...) {}

        try {
            double et = std::stod(card2[1]);
            if (et <= 0) {
                result.addError("*MAT_COHESIVE_MIXED_MODE: Tangential stiffness (ET) must be positive");
            }
        } catch (...) {}
    }
}

void MaterialCardValidator::validatePlasticKinematic(
    const std::vector<std::string>& lines, ValidationResult& result) {

    // Find first data line (_TITLE 은 제목 줄 다음)
    int dataLineIdx = findFirstDataLine(lines);

    if (dataLineIdx < 0) {
        result.addError("*MAT_PLASTIC_KINEMATIC: No data line found");
        return;
    }

    auto fields = parseDataLine(lines[dataLineIdx]);

    // Expected: MID, RO, E, PR, SIGY, ETAN, ...
    if (fields.size() < 5) {
        result.addWarning("*MAT_PLASTIC_KINEMATIC: Expected at least 5 fields (MID, RO, E, PR, SIGY)");
        return;
    }

    // Validate E, PR (same as elastic)
    try {
        double e = std::stod(fields[2]);
        if (e <= 0) {
            result.addError("*MAT_PLASTIC_KINEMATIC: Young's modulus (E) must be positive");
        }
    } catch (...) {}

    try {
        double pr = std::stod(fields[3]);
        if (pr <= 0 || pr >= 0.5) {
            result.addError("*MAT_PLASTIC_KINEMATIC: Poisson's ratio (PR) must be in range (0, 0.5)");
        }
    } catch (...) {}

    // Validate SIGY (yield stress) - must be positive
    try {
        double sigy = std::stod(fields[4]);
        if (sigy <= 0) {
            result.addError("*MAT_PLASTIC_KINEMATIC: Yield stress (SIGY) must be positive");
        }
    } catch (...) {}
}

// *MAT 키워드 다음 첫 데이터 줄. *MAT_..._TITLE 은 제목 줄이 데이터 줄이 아니다 —
// 예전엔 제목을 데이터로 읽어 restack 이 받는 카드를 offset 이 거부했다.
// 다만 제목 줄을 무조건 하나 먹으면 제목이 빠진 카드(내용 줄이 하나뿐)에서는 유일한 데이터 줄이
// 사라진다. 그래서 내용 줄('$' 주석·빈 줄 제외)이 두 줄 이상일 때만 첫 줄을 제목으로 본다 —
// '제목처럼 보이는지' 로 나누면 '7075-T6 aluminum' 같은 진짜 제목에서 틀린다.
int MaterialCardValidator::findFirstDataLine(const std::vector<std::string>& lines) const {
    for (size_t i = 0; i < lines.size(); ++i) {
        if (!isKeywordLine(lines[i])) continue;
        bool isTitle = extractKeyword(lines[i]).find("_TITLE") != std::string::npos;
        std::vector<int> content;
        for (size_t j = i + 1; j < lines.size(); ++j) {
            if (isCommentLine(lines[j])) continue;
            size_t f = lines[j].find_first_not_of(" \t");
            if (f != std::string::npos && lines[j][f] == '*') break;  // 다음 키워드 = 블록 끝
            content.push_back(static_cast<int>(j));
        }
        // 블록 끝의 빈 줄은 카드 끝 개행이라 내용 줄이 아니다
        while (!content.empty() && isBlankLine(lines[content.back()])) content.pop_back();
        if (content.empty()) break;
        size_t from = (isTitle && content.size() >= 2) ? 1 : 0;
        for (size_t k = from; k < content.size(); ++k) {
            if (isBlankLine(lines[content[k]])) continue;  // 데이터 줄은 비어 있지 않다
            return content[k];
        }
        break;
    }
    return -1;
}

std::vector<std::string> MaterialCardValidator::parseDataLine(const std::string& line) const {
    std::vector<std::string> fields;

    // 자유 형식(콤마 구분) 카드도 LS-DYNA 가 받는 정상 표기다 — 공백으로만 나누면
    // '90,7.85E-09,2.10E+05,0.3' 이 한 칸으로 읽혀 칸 수가 모자라다고 잘못 짚었다.
    if (line.find(',') != std::string::npos) {
        size_t pos = 0;
        while (pos <= line.size()) {
            size_t c = line.find(',', pos);
            std::string tok = line.substr(pos, (c == std::string::npos ? line.size() : c) - pos);
            size_t b = tok.find_first_not_of(" \t\r");
            if (b != std::string::npos && tok[b] == '$') break;
            if (b != std::string::npos) {
                size_t e = tok.find_last_not_of(" \t\r");
                fields.push_back(tok.substr(b, e - b + 1));
            }
            if (c == std::string::npos) break;
            pos = c + 1;
        }
        return fields;
    }

    std::istringstream iss(line);
    std::string field;

    while (iss >> field) {
        // Skip inline comments
        if (field[0] == '$') break;
        fields.push_back(field);
    }

    // 고정폭 카드에서 MID 칸(1~10열)에 다음 값이 공백 없이 붙어 있으면('        902.3300E-09')
    // 공백 분리가 한 칸으로 읽어 필드 수가 모자란다. 10열 앞이 정수일 때만 거기서 잘라 둘로 본다.
    if (!fields.empty() && line.find(',') == std::string::npos) {
        size_t first = line.find_first_not_of(" \t");
        size_t tokEnd = (first == std::string::npos) ? std::string::npos
                                                     : line.find_first_of(" \t", first);
        if (tokEnd == std::string::npos && first != std::string::npos) tokEnd = line.size();
        if (first != std::string::npos && first < 10 && tokEnd > 10) {
            std::string head = line.substr(first, 10 - first);
            while (!head.empty() && std::isspace(static_cast<unsigned char>(head.back()))) head.pop_back();
            bool allDigit = !head.empty() &&
                std::all_of(head.begin(), head.end(),
                            [](unsigned char c) { return std::isdigit(c) != 0; });
            if (allDigit) {
                std::string rest = line.substr(10, tokEnd - 10);
                fields[0] = head;
                fields.insert(fields.begin() + 1, rest);
            }
        }
    }

    return fields;
}

bool MaterialCardValidator::isCommentLine(const std::string& line) const {
    for (char c : line) {
        if (std::isspace(static_cast<unsigned char>(c))) continue;
        return (c == '$');
    }
    return false;
}

bool MaterialCardValidator::isBlankLine(const std::string& line) const {
    return std::all_of(line.begin(), line.end(),
                      [](unsigned char c) { return std::isspace(c); });
}

} // namespace KooRemapper
