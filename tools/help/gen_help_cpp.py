# ops_help.py 정본으로 src/cli/HelpCatalogData.inc (C++ 카탈로그 데이터)를 생성
"""
사용: python3 tools/help/gen_help_cpp.py        → src/cli/HelpCatalogData.inc 갱신
      python3 tools/help/gen_help_cpp.py --check → 생성 결과가 커밋본과 다르면 종료 코드 1
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from ops_help import OPS  # noqa: E402

OUT = os.path.join(ROOT, "src", "cli", "HelpCatalogData.inc")


def raw(s):
    assert ")KRH\"" not in s
    return 'R"KRH(' + s + ')KRH"'


def cstr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def render():
    lines = ["// 자동 생성 — tools/help/gen_help_cpp.py (정본 tools/help/ops_help.py). 직접 고치지 말 것",
             "static const std::vector<OpHelp> kOpHelps = {"]
    for o in OPS:
        files = ", ".join("{" + cstr(n) + ", " + raw(c) + "}" for n, c in o["files"].items())
        cmds = ", ".join(cstr(c) for c in o["cmds"])
        needs = ", ".join(cstr(c) for c in o["needs"])
        notes = ", ".join(cstr(c) for c in o["notes"])
        lines.append("    {" + ", ".join([cstr(o["name"]), cstr(o["category"]), cstr(o["summary"]),
                                           cstr(o["aliases"]), cstr(o["usage"])]) + ",")
        lines.append("     {" + files + "},")
        lines.append("     {" + cmds + "},")
        lines.append("     {" + needs + "},")
        lines.append("     {" + notes + "}},")
    lines.append("};")
    return "\n".join(lines) + "\n"


def main():
    text = render()
    if "--check" in sys.argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if cur != text:
            print("HelpCatalogData.inc 가 ops_help.py 와 다르다 — gen_help_cpp.py 를 다시 돌릴 것")
            sys.exit(1)
        print("HelpCatalogData.inc 최신")
        return
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"생성: {OUT} ({len(OPS)} op)")


if __name__ == "__main__":
    main()
