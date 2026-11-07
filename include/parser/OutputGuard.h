// 쓸 파일(산출 · 보고 · 곁 파일)이 읽는 파일(설정 YAML · 모델 · 인클루드 닫힘 · 다른 입력)과 같은지 쓰기 전에 묻는 공용 관문
#pragma once

#include <string>
#include <vector>

namespace KooRemapper {

class ConsoleOutput;

namespace output_guard {

// 왜 이 단위가 있나 (2026-11-07).
//
//   흘려 읽는 op 셋(extract-parts · cleanup-nodes · strip)은 `include_closure::clobberPair` 로 막았지만, 나머지 op 은 쓸 파일을
//   읽는 파일과 견주지 않았다. 실측 — `update` 에 `model: main.k`(`*INCLUDE inc.k`) · `output: inc.k` 를 주면 rc 0 으로 inc.k 가
//   주 덱으로 바뀌어 **자기 자신을 끌어오고** 그 안의 `*NODE` 가 사라졌다. meshfix 는 output == model 이면 쓰기 뒤 검사가 실패할 때
//   산출을 지우며 모델을 지웠고, prestress 는 변형 메시를 다시 읽기 **전에** dynain 을 써 `prestress ref def.key def.key` 가 그 입력을
//   덮었다. op 마다 사본을 두지 않으려고 판정을 여기 한 곳에 둔다 — 같은 파일인지는 `include_closure::sameFile`(정규 경로 ·
//   심볼릭 링크 · 하드 링크), 첫 짝은 `clobberPair` 가 정한다.
//
// 쓰는 법 — op 은 산출을 하나라도 열기(잘라 비우기) **전에**, 이번 실행이 쓸 파일을 **모두**(산출 · 보고 · 곁 파일 · 임시 파일)
// `writes` 로, 읽는 파일을 `reads` 로 주고 `refuse` 를 부른다. 명령줄의 설정 YAML 은 main 이 `noteConfig` 로 한 번 적어 두므로
// 모든 관문이 저절로 본다. ModelAssembler 를 쓰는 op 은 `ModelAssembler::writeOutput` 이 같은 관문을 지난다(모델 · 인클루드 ·
// apply* 가 읽은 입력을 스스로 적는다).

// 읽는 파일 하나 — 경로와 그 몫(사람이 읽는 말 — "model" · "인클루드" · "dynain" …). 메시지에 그대로 나간다.
struct Input {
    std::string path;
    std::string role;
};

// 명령줄의 설정 파일을 적어 둔다 — main 이 op 을 부르기 전에. 이 실행의 모든 관문이 읽는 파일로 본다(빈 경로는 무시).
void noteConfig(const std::string& path);
// 적어 둔 설정 파일(시험 · 진단용)과 그 비우기(시험용).
const std::vector<std::string>& configs();
void clearConfigs();

// 모델과 그 인클루드 닫힘(`include_closure::readPaths` — 맨 `*INCLUDE` · 주 덱 폴더 기준 · `*INCLUDE_PATH`)을 읽는 파일로.
// 덱을 흘려 읽고 줄은 담지 않는다. `role` 은 모델의 몫(인클루드는 「<role> 의 인클루드」). 따라가지 않는 변형 인클루드
// (`*INCLUDE_TRANSFORM` …)가 가리키는 파일 · 깊이 상한을 넘은 이름의 파일도 든다 — 산출 덱이 그 카드를 그대로 싣는다(셋째 묶음).
std::vector<Input> modelInputs(const std::string& modelPath, const std::string& role = "model");
// 설정 파일(빈 경로면 뺀다)과 모델 · 그 인클루드 닫힘 — 대부분의 op 이 읽는 것이 이것이다.
std::vector<Input> configAndModel(const std::string& configPath, const std::string& modelPath);

// 쓸 파일(`writes` — 빈 경로는 건너뛴다)이 읽는 파일(`reads` + 적어 둔 설정)이나 다른 쓸 파일과 같은 첫 짝을 찾는다.
// 있으면 true 와 두 경로를 다 적은 문장(`why`).
bool findClash(const std::vector<std::string>& writes, const std::vector<Input>& reads, std::string& why);

// `findClash` 를 묻고 걸리면 `[<op>] …` 을 [ERROR] 로 찍고 true — 부르는 쪽은 아무것도 열지 않고 rc 1 로 끝낸다.
bool refuse(const std::string& op, const std::vector<std::string>& writes, const std::vector<Input>& reads,
            const ConsoleOutput& console);

}  // namespace output_guard
}  // namespace KooRemapper
