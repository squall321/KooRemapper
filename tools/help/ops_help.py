# KooRemapper help 카탈로그 정본 — op 요약·용법·자체완결 사례 (C++ HelpCatalog.cpp 는 여기서 생성)
"""
사례 규약 (help 출력 그대로 LLM 이 따라 할 수 있게)
  files: {파일이름: 내용}  — 작업 폴더에 그대로 쓴다
  cmds : ["KooRemapper ..."] — 순서대로 실행 (앞 명령 산출물을 뒤 명령이 쓴다)
  outputs: 실행 후 반드시 생겨야 하는 파일 (검증 전용, 출력하지 않음)
  invariants: {산출물: {"bbox": [dx, dy, dz], "elements": n, "keywords": ["*MAT_ELASTIC"]}} — 산출물이
              만족해야 할 값 (검증 전용, 출력하지 않음). rc=0 만으로는 못 잡는 '돌지만 틀린' 사례를 막는다
  needs  : 사례 폴더에 미리 있어야 하는 저장소 파일 (검증 전용). 있으면 help 에 입력 조건으로 안내

tools/help/run_help_examples.py 가 빌드된 바이너리의 `help <op>` 출력을 파싱해 실제로 돌려 본다.
"""

BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 10
ny: 5
nz: 2
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""

BOX_CMD = "KooRemapper generate box box.yaml"

OPS = []


def op(name, category, summary, aliases, usage, files=None, cmds=None, outputs=None, needs=None, notes=None,
       invariants=None):
    OPS.append(dict(name=name, category=category, summary=summary, aliases=aliases, usage=usage,
                    files=files or {}, cmds=cmds or [], outputs=outputs or [], needs=needs or [],
                    notes=notes or [], invariants=invariants or {}))


def boxed(files):
    d = {"box.yaml": BOX}
    d.update(files)
    return d


# ── 메시 매핑 ──
op("map", "메시 매핑", "평면 상세 메시를 굽힌 구조화 HEX8 참조 메시에 매핑", "매핑 bent flat 굽힘 곡면",
   "KooRemapper map [--single] <bent_mesh> <flat_mesh> <output>",
   cmds=["KooRemapper generate --dim-i 20 --dim-j 5 arc demo",
         "KooRemapper map demo_bent.k demo_flat_fine.k mapped.k"],
   outputs=["mapped.k"],
   notes=["bent 참조는 구조화 HEX8 이어야 한다. generate 가 bent/flat/flat_fine/flat_tet 세트를 만든다."])
op("shellmap", "메시 매핑", "굽힌 QUAD4 셸을 참조로 평면 상세 메시를 매핑", "셸매핑 shell 곡면 전개",
   "KooRemapper shellmap [--thickness <t>] <bent_shell> <flat_detail> <output>",
   cmds=["KooRemapper generate --dim-i 20 --dim-j 5 arc demo",
         "KooRemapper extract-surface demo_bent.k bent_top.k --face top",
         "KooRemapper shellmap bent_top.k demo_flat_fine.k shellmapped.k"],
   outputs=["shellmapped.k"],
   notes=["단일 곡률(원통형) 면에 적합. 이중 곡률이면 왜곡 경고가 난다."])
op("unfold", "메시 매핑", "굽힌 구조화 HEX8 메시를 평면으로 전개 (map 의 역)", "전개 펼치기 flat",
   "KooRemapper unfold <bent_mesh> <output_flat>",
   cmds=["KooRemapper generate --dim-i 20 --dim-j 5 arc demo",
         "KooRemapper unfold demo_bent.k unfolded.k"],
   outputs=["unfolded.k"])

# ── 메시 생성 ──
op("generate", "메시 생성", "시험용 곡면 메시 세트(teardrop·arc·torus…) 또는 YAML 박스 메시 생성", "생성 box 박스 teardrop arc",
   "KooRemapper generate [--dim-i n --dim-j n --dim-k n] <type> <output_prefix>\n"
   "KooRemapper generate box <config.yaml>",
   files={"box.yaml": BOX},
   cmds=["KooRemapper generate --dim-i 20 --dim-j 10 teardrop demo",
         BOX_CMD],
   outputs=["demo_bent.k", "demo_flat.k", "box.k"],
   notes=["type: teardrop arc scurve helix torus twist bendtwist wave bulge taper waterdrop",
          "box YAML 의 mid/secid/pid/part_title 로 파트 번호·이름을 정한다. 다른 op 사례의 시작 모델로 쓴다."])
op("generate-var", "메시 생성", "구간별 요소 밀도가 다른 평면/곡선 메시를 YAML 로 생성", "가변밀도 variable density",
   "KooRemapper generate-var [--ref <flat.k>] [--no-scale] <config.yaml> <output.k>",
   files={"var.yaml": """type: flat
reference:
  dimensions:
    length_i: 100.0
    length_j: 10.0
    length_k: 2.0
elements_j: 5
elements_k: 2
variable_density:
  zone1_dense_start:
    length: 10.0
    num_elements: 10
  zone2_increasing:
    length: 20.0
    num_elements: 8
  zone3_sparse:
    length: 40.0
    num_elements: 8
  zone4_decreasing:
    length: 20.0
    num_elements: 8
  zone5_dense_end:
    length: 10.0
    num_elements: 10
"""},
   cmds=["KooRemapper generate-var var.yaml var.k"],
   outputs=["var.k"],
   invariants={"var.k": {"bbox": [100.0, 10.0, 2.0]}},
   notes=["구간 이름은 고정 5개: zone1_dense_start zone2_increasing zone3_sparse zone4_decreasing zone5_dense_end",
          "--ref flat.k 를 주면 기준 메시 크기에 맞춰 스케일한다. 곡선형은 type: curved + centerline_points"])
op("battery", "메시 생성", "배터리 셀(적층·권취) 모델 + 스웰링 DR 덱 생성", "배터리 셀 pouch swelling 스웰링",
   "KooRemapper battery <config.yaml>",
   needs=["examples/battery/swell/stacked/stacked_swell.yaml"],
   cmds=["KooRemapper battery examples/battery/swell/stacked/stacked_swell.yaml"],
   outputs=["examples/battery/swell/stacked/battery_stacked_swell_tier0_phase1.k"],
   notes=["설정 키가 많아 저장소 예제(examples/battery/swell/stacked|wound/*.yaml)를 복사해 고쳐 쓰는 편이 안전하다.",
          "output 경로의 폴더가 있어야 한다.",
          "dynain_file 은 경로가 아니라 *INCLUDE_DYNAIN 에 그대로 찍히는 문자열이다 — 산출 덱 옆에서 솔버가 찾을 이름으로 적을 것"])
op("cclip", "메시 생성", "육면체 파트를 힘-변위로 보정한 C형 스프링 클립(눌린 상태 초기응력)으로 치환", "클립 spring 스프링 접점",
   "KooRemapper cclip <config.yaml>",
   files={"board.yaml": """output: clip_board.k
lx: 3.0
ly: 1.5
lz: 0.5
nx: 6
ny: 3
nz: 1
rho: 8.36e-9
E: 131000.0
nu: 0.3
mid: 2
secid: 2
pid: 2
part_title: CCLIP_ANT_01
""", "cclip.yaml": """model: clip_board.k
output: clip_board_cclip
mode: analytic
attach: none
stress_output: embed
free_output: true
calibration:
  point: {deflection: 0.15, force: 1.2}
  tolerance: 0.05
clips:
  - pid: 2
    overtravel: 0.15
"""},
   cmds=["KooRemapper generate box board.yaml", "KooRemapper cclip cclip.yaml"],
   outputs=["clip_board_cclip.k"])

# ── 메시 편집 ──
op("convert", "메시 편집", "1차 요소를 2차 요소로 (TET10·HEX20·QUAD8·TRIA6)", "2차요소 quadratic hex20 tet10",
   "KooRemapper convert <config.yaml>",
   files=boxed({"convert.yaml": """base_model: box.k
output: box_hex20
operations:
  - type: hex20
    elform: 23
"""}),
   cmds=[BOX_CMD, "KooRemapper convert convert.yaml"], outputs=["box_hex20.k"],
   notes=["operations[].type: tet10 | hex20 | quad8 | tria6"])
op("refine", "메시 편집", "요소를 변마다 1:2 또는 1:3 으로 균일 세분화", "세분화 refine 조밀",
   "KooRemapper refine <config.yaml>",
   files=boxed({"refine.yaml": """base_model: box.k
output: box_refined
operations:
  - type: refine
    ratio: 2
"""}),
   cmds=[BOX_CMD, "KooRemapper refine refine.yaml"], outputs=["box_refined.k"])
op("elform", "메시 편집", "*SECTION 의 ELFORM 변경 (필요하면 요소 차수도 변환)", "요소공식 section",
   "KooRemapper elform <config.yaml>",
   files=boxed({"elform.yaml": """base_model: box.k
output: box_elform2
operations:
  - type: elform
    target_elform: 2
"""}),
   cmds=[BOX_CMD, "KooRemapper elform elform.yaml"], outputs=["box_elform2.k"])
op("disconnect", "메시 편집", "파트 경계 공유 절점을 분리 (CZM·파손 인터페이스)", "분리 czm 파손 interface",
   "KooRemapper disconnect <config.yaml>",
   needs=["examples/disconnect/two_hex_2part.k"],
   files={"disc.yaml": """base_model: examples/disconnect/two_hex_2part.k
output: two_hex_disc
operations:
  - type: disconnect
    mode: mefem
    target_pid: 0
    failure_strain: 0.085
"""},
   cmds=["KooRemapper disconnect disc.yaml"], outputs=["two_hex_disc.k"],
   notes=["입력은 절점을 공유하는 두 파트 이상 (경계면이 없으면 실패). mode: czm | mefem | full, target_pid 0 = 모든 파트 경계"])
op("offset", "메시 편집", "셸/표면에서 두께·방향을 지정해 솔리드 층을 돌출 (tied/CZM/contact 연결)", "돌출 두께 extrude layer",
   "KooRemapper offset <config.yaml>",
   files=boxed({"offset.yaml": """base_model: box.k
output: box_offset
operations:
  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 2
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
"""}),
   cmds=[BOX_CMD, "KooRemapper offset offset.yaml"], outputs=["box_offset.k"],
   invariants={"box_offset.k": {"bbox": [20.0, 10.0, 3.0]}},
   notes=["connection_mode: tied(기본) | czm | contact | none (assemble 경로도 none 허용)",
          "material_card·czm_material_card 의 MID 칸(@MID@·@CZM_MID@·숫자·라벨)은 새 MID 로 바뀐다. 값은 10열 칸 안에 둘 것",
          "material_cards: 목록으로 층마다 다른 재질 (단독 offset·assemble 모두)"])
op("wrap", "메시 편집", "원통 파트에 와인딩 인장 초기응력(후프+반경) 부여", "와인딩 인장 hoop 압입",
   "KooRemapper wrap <config.yaml>",
   needs=["examples/wrap/cylinder_2layer.k"],
   files={"wrap.yaml": """model: examples/wrap/cylinder_2layer.k
output: cylinder_wrapped
material:
  E: 210000.0
  nu: 0.3
target_pid: [1, 2]
axis: z
tension: 100.0
"""},
   cmds=["KooRemapper wrap wrap.yaml"], outputs=["cylinder_wrapped.k"],
   notes=["입력은 축 방향 원통 솔리드 파트. tension 단위는 [힘/길이]"])
op("restack", "메시 편집", "extrude 된 솔리드를 두께·재질이 다른 층으로 다시 나눔", "적층 layer stack 두께분할",
   "KooRemapper restack <config.yaml>",
   files=boxed({"restack.yaml": """base_model: box.k
output: box_stack
operations:
  - type: restack
    target_pid: 1
    direction: z
    element_type: solid
    layers:
      - thickness: 0.5
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
              MID001  7.85E-09  2.10E+05       0.3
      - thickness: 0.2
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
              MID002  1.20E-09  3.00E+03      0.45
"""}),
   cmds=[BOX_CMD, "KooRemapper restack restack.yaml"], outputs=["box_stack.k"],
   invariants={"box_stack.k": {"bbox": [20.0, 10.0, 2.0], "elements": 100}},
   notes=["element_type: solid(기본) | tshell | shell, direction: auto(기본, 자동 탐지) | x | y | z (+/- 부호도 같은 축). 모르는 값은 rc=1",
          "material_card 의 mid 칸은 라벨로도 쓸 수 있다 (MID001, MAT01). 층마다 새 MID 로 바뀐다. 라벨과 카드 내용이 같으면 재질을 공유하고, 라벨이 같아도 물성이 다르면 MID 를 따로 준다",
          "그 칸에 숫자를 적으면 그 번호를 그대로 쓴다. 이미 쓰이는 번호면 'material MID 90 is already in use -> assigned MID 91' 을 찍고 새 번호를 준다",
          "*MAT_…_TITLE 의 제목 줄은 그대로 두고, 같은 MID 를 가리키는 *MAT_ADD_… 카드도 함께 새 MID 로 바뀐다. 제목 줄이 없으면 [WARN] 을 내고 'Restack Layer N'(layers[].title 이 있으면 그 제목)을 채워 내보낸다. 데이터가 두 줄 이상인 카드(*MAT_RIGID·*MAT_PIECEWISE_LINEAR_PLASTICITY 등)도 마찬가지다 — 제목 자리의 줄이 '빈 칸을 뺀 모든 칸이 수이고 두 칸 이상' 이면 데이터 줄로 보고 제목이 빠진 것으로 판정한다('7075-T6 aluminum' 처럼 글자가 섞인 진짜 제목은 제목으로 남는다). 데이터 줄 자체가 없는 카드는 rc=1",
          "층 카드도 재질 카드 검사를 거친다 — 구조가 깨지면 rc=1, 물성 값 경고(예: PR 0.6)는 [WARN] 이고 그대로 진행한다",
          "카드는 10칸 고정폭 (블록 들여쓰기를 뺀 뒤 기준). 자유 형식(쉼표)도 된다. 새 SECID 는 자동",
          "새 층 PID 는 layers[].pid 로 층마다 못박거나 op 수준 pid_start 로 자동 발급 시작 번호를 옮길 수 있다(둘 다 없으면 예전처럼 모델 최대 PID + 1). 이미 쓰는 번호를 지정하면 조용히 바꾸지 않고 rc=1 — 'restack: layer 1 pid 2 is already used by this model - choose a free part ID'",
          "입력이 두 줄 포맷(*ELEMENT_SOLID (ten nodes format), 한 요소가 'eid pid' 줄 + 노드 줄)이면 지우는 요소의 노드 줄까지 함께 지우고, 새 층 요소는 표준 한 줄 포맷 *ELEMENT_SOLID 섹션을 따로 열어 쓴다 — 한 섹션에 두 포맷을 섞으면 두 줄로 읽는 쪽이 새 요소의 절반을 노드 줄로 읽는다. *ELEMENT_TSHELL 섹션의 요소도 지운다",
          "새 *SECTION 은 원 *SECTION 의 ELFORM 을, 새 *PART 는 원 *PART 의 HGID·TMID 를 물려받는다 (요소 종류가 같을 때만 — solid↔tshell 은 뜻이 달라 넘기지 않는다. EOSID 도 넘기지 않는다)",
          "대상 파트가 강체(*MAT_RIGID/*MAT_020 또는 *PART_INERTIA)면 층을 나누지 않고 rc=1 로 거절한다",
          "입력은 extrude 된 헥사 솔리드. 두께 방향 노드 수가 곳곳에서 같아야 하고, 아니면 not a valid extrusion 으로 멈춘다",
          "thickness 는 비율로 쓰인다 — 합이 실제 두께와 달라도 실제 두께에 맞춰 나눈다. 층마다 num_elements 로 두께 방향 요소 수를 준다 (첫 층이 아래쪽)",
          "평면 메시는 그대로 두고 두께 방향만 다시 만든다. 층마다 새 PID·SECID·MID 를 주므로 원래 *PART 는 요소 0 개인 빈 파트로 남는다",
          "그 죽은 PID·지워진 요소(EID)·지워진 노드(NODE)를 가리키던 자리를 훑어 옮긴다 — 체적 의미로 쓰이는 *SET_PART_LIST·*SET_PART_TITLE 은 층 PID 전부로(한 줄 8개 규칙을 지켜 줄을 늘린다), *SET_PART_COLUMN 은 딸린 칸이 있어 죽은 PID 줄을 층마다 한 줄씩으로 늘린다(딸린 칸은 그대로 복사), tied 계열 접촉(*CONTACT_*TIED*/*TIEBREAK*/*SPOTWELD*/*CONTACT_CONSTRAINT_)은 상대측 기하를 적층 축에 투영해 층이 하나로 정해질 때만 그 층으로, 그 밖의 접촉(AUTOMATIC·ERODING·SINGLE_SURFACE)은 shell 층이 섞이지 않았을 때 층 전부를 담은 새 세트로(STYP 3→2)",
          "한 세트를 tied 와 체적 소비자가 함께 쓰면 세트를 복제해 가른다(새 SID 를 발급). 접촉은 tied 든 아니든 층이 애매하거나 shell 층이 섞이면 옮기지 않고 이유만 보고한다(left — rc 에 들어간다)",
          "PID 칸이 하나뿐인 카드(*DAMPING_PART_MASS/_STIFFNESS, *DATABASE_HISTORY_PART, *MAT_ADD_THERMAL_EXPANSION, *PART_MOVE, *BOUNDARY_PRESCRIBED_MOTION_RIGID, *DEFORMABLE_TO_RIGID, *INITIAL_VELOCITY_GENERATION)는 한 칸에 층 N 개를 담을 수 없어 manual(직접 고치세요)로 남는다 — 새 PID 가 하나뿐인 merge 는 이 칸들을 옮긴다. *ELEMENT_MASS(_PART 포함)는 집중질량을 층에 나눌 수 없어 restack 에서 manual 이다",
          "지운 중간면 노드(NODE 축)는 먼저 옮긴다 — 좌표가 똑같은 새 층 노드가 딱 하나일 때(층 두께 합·분할이 원안과 겹칠 때) *SET_NODE_LIST 구성원을 그 노드로 바꾼다",
          "옮길 곳이 없는 참조는 실제로 치운다 — *SET_NODE/_LIST/_LIST_SMOOTH 는 죽은 구성원을 빼고 남은 것만 다시 채우고, *SET_NODE_COLUMN·*SET_SEGMENT·*BOUNDARY_SPC_NODE·*LOAD_NODE_POINT·*INITIAL_VELOCITY_NODE·*CONSTRAINED_EXTRA_NODES_NODE·*ELEMENT_MASS 는 그 줄을 지우고, *DATABASE_HISTORY_NODE 는 목록에서 뺀다. 무엇을 몇 개 치웠는지 [정리] 로 찍는다",
          "*SET_NODE_*_GENERATE 범위는 고치지 않는다 — 매뉴얼이 '정의된 ID 만 들어가고 번호 구멍은 문제가 아니다' 를 명시한다(Vol_I 234577-234581). 범위가 통째로 지워져 빈 세트가 되면 [WARN] 으로 알린다. *SET_NODE_ADD 는 구성원이 노드 세트 ID 라 건드리지 않는다",
          "*CONSTRAINED_NODAL_RIGID_BODY 의 PNODE, *DEFINE_COORDINATE_NODES, *ELEMENT_BEAM/_DISCRETE/_SEATBELT 는 빼면 모델이 달라져 manual 로 보고만 한다(strict 면 rc=1)",
          "요소 카드 줄 수는 어림짐작이 아니라 매뉴얼 표로 정한다 — 키워드 옵션(H20·T15·P21·H27·P40·H64·ORTHO·DOF·THICKNESS·BETA·MCID·OFFSET), 그다음 *SECTION_SOLID ELFORM 23-29, 마지막으로 줄 구조 순이다. *ELEMENT_SHELL_THICKNESS 계열은 두께 카드(중간절점이 있으면 셋째 카드까지)를 한 카드로 묶어 함께 지운다",
          "고차 정식 파트(ELFORM 23-29)는 rc=1 로 거절한다 — 이 도구는 요소마다 8 절점 모서리만 담아 중간 절점을 다시 만들 수 없다. 덱의 요소 카드 수와 리더가 읽은 수가 다를 때도 rc=1 이다(*ELEMENT_SOLID_ORTHO 처럼 읽지 않는 변형)",
          "COMPOSITE 계열(*ELEMENT_SHELL_COMPOSITE·*ELEMENT_TSHELL_COMPOSITE)은 적층점 수에 따라 카드 줄 수가 달라 손대지 않고 그대로 내보낸다. 그 섹션의 요소를 지워야 하면 덱을 쓰지 않고 rc=1",
          "끝나면 파트별 요소 수를 'PID x: a → b (삭제/신규)' 와 합계로 찍고, 출력 덱을 다시 읽어 기대 수와 맞는지 스스로 확인한다 — 이번 op 가 건드리지 않은 파트와 합계까지 본다. 어긋나면 파일을 쓰지 않고 rc=1 이다(무증상 결함을 잡는 마지막 관문)",
          "*INCLUDE 가 있는 덱은 세트의 소비자를 다 볼 수 없어 세트를 펴지 않고 보고만 한다",
          "못 옮긴 자리가 하나라도 남으면 rc=1 이고 덱은 쓴다. 전체 목록은 덱 머리(*KEYWORD 바로 뒤)의 '$ KOOREMAPPER-PIDREF' 블록에 moved/left/manual/unknown/maybe 등급과 입력 덱 기준 줄 번호로 들어간다. maybe(화이트리스트 밖)는 rc 에 넣지 않는다",
          "pid_refs: strict(기본) | warn — warn 은 같은 보고를 하고 rc=0 으로 끝낸다(기존 파이프라인의 탈출구). 그 밖의 값은 rc=1 + invalid pid_refs. assemble 은 operations[] 항목 안에, 단독 restack 은 YAML 에 그대로 적는다",
          "strict 가 기본인 이유 — pyKooCAE 체인과 플랫폼 워커는 종료 코드로만 성공을 판정한다. rc=0 이면 콘솔 경고가 자동화에 안 보인 채 그대로 솔버까지 간다"])
op("update", "메시 편집", "dynain·k 파일의 *NODE 좌표로 모델 절점 좌표 덮어쓰기", "좌표갱신 dynain node",
   "KooRemapper update <config.yaml>",
   files=boxed({"sq.yaml": """parts:
  - pid: 1
    eps_x: -0.01
    eps_y: -0.01
    eps_z: 0.0
material:
  E: 210000.0
  nu: 0.3
""", "update.yaml": """model: box.k
output: box_updated.k
dynain: box_sq.k
"""}),
   cmds=[BOX_CMD, "KooRemapper squeeze box.k sq.yaml box_sq", "KooRemapper update update.yaml"],
   outputs=["box_updated.k"])
op("iga", "메시 편집", "솔리드 파트를 NURBS trivariate IGA 패치로 감싸 IGA 해석용으로 변환", "nurbs isogeometric",
   "KooRemapper iga <config.yaml>",
   files=boxed({"iga.yaml": """base_model: box.k
output: box_iga
operations:
  - type: iga
    targets:
      - target_pid: 1
        element_size: 4.0
"""}),
   cmds=[BOX_CMD, "KooRemapper iga iga.yaml"], outputs=["box_iga.k"])

# ── 표면·재메시 ──
op("extract-surface", "표면·재메시", "솔리드 파트의 윗면/아랫면/전체 표면을 셸로 추출", "표면추출 surface shell 면",
   "KooRemapper extract-surface <solid.k> <output_shell.k> [--pid N] [--face top|bottom|all] [--output-pid N]",
   files={"box.yaml": BOX},
   cmds=[BOX_CMD, "KooRemapper extract-surface box.k box_top.k --face top --output-pid 10"],
   outputs=["box_top.k"])
op("tetremesh", "표면·재메시", "TET4 파트의 불량 요소 패치를 국소 재메시 (localimprove | tetgen)", "사면체 품질 tet remesh",
   "KooRemapper tetremesh <config.yaml>",
   files={"tet.yaml": """model: demo_flat_tet.k
output: demo_flat_tet_fixed.k
backend: localimprove
target_pids: [1]
quality:
  min_jacobian: 0.2
  max_aspect_ratio: 8.0
"""},
   cmds=["KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper tetremesh tet.yaml"],
   outputs=["demo_flat_tet_fixed.k"])
op("meshfix", "표면·재메시", "TET4 파트를 Gmsh 로 전체 재메시 (gmsh 실행 파일 필요)", "gmsh 재메시",
   "KooRemapper meshfix <config.yaml>",
   files={"meshfix.yaml": """model: demo_flat_tet.k
output: remeshed.k
pid: 1
lc_target: 5.0
adaptive: true
warn_min_jac: 0.15
"""},
   cmds=["KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper meshfix meshfix.yaml"],
   outputs=["remeshed.k"],
   notes=["gmsh 탐색: KOOREMAPPER_GMSH 환경변수 → 실행 파일 옆 gmsh/·gmsh-<ver>/[bin/] → PATH → /opt/gmsh-*/bin/gmsh (SIF 는 그대로 동작)"])
op("cnrb2solid", "표면·재메시", "CNRB(절점 강체) 볼트를 HEX8 솔리드 원통 + tied 접촉으로 변환", "볼트 bolt cnrb 원통",
   "KooRemapper cnrb2solid <config.yaml>",
   needs=["examples/cnrb2solid/bolt_simple.k"],
   files={"cnrb.yaml": """model: examples/cnrb2solid/bolt_simple.k
output: bolt_simple_solid.k
E: 200000.0
PR: 0.3
RHO: 7.85e-9
radius_scale: 0.999
num_circum_nodes: 8
inner_radius_ratio: 0.3
axis_direction: auto
z_tolerance: 0.1
r_tolerance: 0.5
"""},
   cmds=["KooRemapper cnrb2solid cnrb.yaml"], outputs=["bolt_simple_solid.k"],
   notes=["입력 모델에 원형으로 배치된 *CONSTRAINED_NODAL_RIGID_BODY 가 있어야 한다. 헤드는 head_offset_r·head_thickness·head_position"])
op("merge", "표면·재메시", "적층 파트들을 하나의 균질화 재질 층으로 병합 (voigt/reuss/vrh)", "병합 균질화 homogenize",
   "KooRemapper merge <config.yaml>",
   needs=["examples/merge/three_layer.k"],
   files={"merge.yaml": """model: examples/merge/three_layer.k
output: three_layer_merged.k
direction: z
method: vrh
merge:
  - pids: [1, 2, 3]
    name: "Homogenized_Stack"
"""},
   cmds=["KooRemapper merge merge.yaml"], outputs=["three_layer_merged.k"],
   notes=["입력은 z 방향으로 쌓인 솔리드 층 파트들 (각 파트에 MAT_ELASTIC 계열 재질)",
          "합친 파트들은 요소 0 개인 빈 파트로 남고 새 PID 하나가 생긴다 (위 사례는 PID 1,2,3 → 4)",
          "그 죽은 PID·지워진 요소(EID)·지워진 노드(NODE)를 가리키던 자리를 훑어 옮긴다 — 세트·접촉은 물론, PID 칸이 하나뿐인 카드(*DAMPING_PART_MASS/_STIFFNESS, *DATABASE_HISTORY_PART, *MAT_ADD_THERMAL_EXPANSION, *PART_MOVE, *BOUNDARY_PRESCRIBED_MOTION_RIGID, *DEFORMABLE_TO_RIGID, *INITIAL_VELOCITY_GENERATION)도 새 PID 로 바꾼다. 새 PID 가 여럿인 restack 은 이 칸들을 manual 로 남긴다",
          "두 칸이 모두 이번 merge 로 사라지는 *CONSTRAINED_RIGID_BODIES 는 합치면 자기 자신을 가리키게 되므로 옮기지 않고 보고만 한다",
          "*ELEMENT_MASS(_PART 포함)는 merge 에서도 옮기지 않고 manual 로 남긴다 — 변형마다 PID 칸 자리가 달라(EID·노드 ID·MASS·PID / _PART 는 PID·MASS) 잘못 짚으면 노드 ID 를 덮어쓴다. 집중질량은 직접 배분해라",
          "못 옮긴 자리가 하나라도 남으면 rc=1 이고 덱은 쓴다. 전체 목록은 덱 머리(*KEYWORD 바로 뒤)의 '$ KOOREMAPPER-PIDREF' 블록에 moved/left/manual/unknown/maybe 등급과 입력 덱 기준 줄 번호로 들어간다. maybe(화이트리스트 밖)는 rc 에 넣지 않는다",
          "pid_refs: strict(기본) | warn — warn 은 같은 보고를 하고 rc=0 으로 끝낸다. 그 밖의 값은 rc=1 + invalid pid_refs. assemble 은 operations[] 항목 안에, 단독 merge 는 YAML 에 그대로 적는다",
          "위 사례의 three_layer.k 는 *MAT_ADD_THERMAL_EXPANSION 2 건이 죽은 PID 를 가리켜 '옮김' 으로 보고된다 — 못 옮긴 자리가 없어 rc=0 이다"])
op("strip", "표면·재메시", "지정 키워드를 k 파일에서 제거 (메시 빼고 카드만 남기기 등)", "제거 키워드 remove",
   "KooRemapper strip <config.yaml>",
   files=boxed({"strip.yaml": """model: box.k
output: box_cards_only.k
keywords:
  - "*NODE"
  - "*ELEMENT_SOLID"
"""}),
   cmds=[BOX_CMD, "KooRemapper strip strip.yaml"], outputs=["box_cards_only.k"])

# ── 변형·초기응력 ──
op("strain", "변형·초기응력", "기준·변형 메시 쌍의 요소별 변형률(6성분) CSV", "변형률 strain csv",
   "KooRemapper strain [--type green|...] <ref_mesh> <def_mesh> <output.csv>",
   cmds=["KooRemapper generate --dim-i 20 --dim-j 5 arc demo",
         "KooRemapper strain demo_flat.k demo_bent.k strain.csv"],
   outputs=["strain.csv"], notes=["두 메시는 절점·요소 번호가 같아야 한다."])
op("prestress", "변형·초기응력", "기준·변형 메시 쌍에서 Hooke 로 응력 → *INITIAL_STRESS_SOLID", "초기응력 prestress dynain",
   "KooRemapper prestress [--E v --nu v --strain green|...] <ref_mesh> <def_mesh> <output>",
   cmds=["KooRemapper generate --dim-i 20 --dim-j 5 arc demo",
         "KooRemapper prestress --E 210000 --nu 0.3 demo_flat.k demo_bent.k demo_pre"],
   outputs=["demo_pre.k"])
op("squeeze", "변형·초기응력", "파트를 지정 변형률로 압축하고 역방향 초기응력 출력 (억지 끼움)", "압축 억지끼움 interference swelling",
   "KooRemapper squeeze <mesh.k> <config.yaml> <output_prefix>",
   files=boxed({"sq.yaml": """parts:
  - pid: 1
    eps_x: -0.01
    eps_y: -0.01
    eps_z: 0.0
material:
  E: 210000.0
  nu: 0.3
"""}),
   cmds=[BOX_CMD, "KooRemapper squeeze box.k sq.yaml box_sq"], outputs=["box_sq.k", "box_sq.dynain"],
   invariants={"box_sq.k": {"bbox": [19.8, 9.9, 2.0]},
               "box_sq.dynain": {"keywords": ["*INITIAL_STRESS_SOLID"]}},
   notes=["material 이 없으면 k 파일 재질을 쓴다 — 둘 다 없으면 실패. 등방 팽윤은 parts[].swelling",
          "config YAML 은 BOM 없이 저장할 것 — 이 op 만은 아직 BOM 이 붙으면 "
          "'No parts defined in squeeze config' 로 rc=1 이다(메모장은 BOM 을 붙인다)"])
op("formstrain", "변형·초기응력", "셸 이면각으로 성형 소성변형률 추정 → *INITIAL_STRAIN_SHELL", "성형 forming 곡률",
   "KooRemapper formstrain <config.yaml>",
   needs=["examples/formstrain/bent_shell.k"],
   files={"fs.yaml": """base_model: examples/formstrain/bent_shell.k
output: bent_formstrain
dynain_embed: true
operations:
  - type: formstrain
"""},
   cmds=["KooRemapper formstrain fs.yaml"],
   outputs=["bent_formstrain.dynain"],
   notes=["대상은 SECTION_SHELL + MAT_024(SIGY > 0) 셸 파트. 없으면 'no eligible shell parts' 로 아무것도 안 쓴다",
          "target_pid 를 생략하면 조건에 맞는 모든 셸 파트"])
op("warpage", "변형·초기응력", "측정 워피지 데이터(dat)로 셸·솔리드 파트 면외 변형", "워피지 휨 warp",
   "KooRemapper warpage <config.yaml>",
   files=boxed({"warpage.yaml": """base_model: box.k
output: box_warp
material:
  E: 210000
  nu: 0.3
operations:
  - type: warpage
    target_pid: 1
    dat_file: warp.dat
    plane: xy
    deflection_axis: +z
    unit: um
    mode: deform
""", "warp.dat": """0 0 0 0 0
0 50 100 50 0
0 0 0 0 0
"""}),
   cmds=[BOX_CMD, "KooRemapper warpage warpage.yaml"], outputs=["box_warp.k"],
   notes=["dat 파일은 처짐값 행렬(행×열, 공백 구분). 파트 평면 bbox(또는 data_bbox)에 펼치며 열 0 = 평면 1축 최소, "
          "행 0 = 2축 최소 (bend 의 dat 는 행 0 = 최대). 값 단위는 unit(기본 um)",
          "mode: prestress(기본, 초기응력만) | deform(노드 이동). outside_behavior: zero(기본) | clamp | extrapolate"])
op("bend", "변형·초기응력", "처짐 함수 w(x1,x2) 로 파트를 굽히고 초기응력 계산", "굽힘 bending 곡률 formula",
   "KooRemapper bend <config.yaml>",
   files=boxed({"bend.yaml": """base_model: box.k
output: box_bent
material:
  E: 210000
  nu: 0.3
dynain_embed: true
operations:
  - type: bend
    target_pid: 1
    plane: xy
    mode: deform
    source: formula
    expression: "0.5 * sin(pi*x1/L1) * sin(pi*x2/L2)"
"""}),
   cmds=[BOX_CMD, "KooRemapper bend bend.yaml"], outputs=["box_bent.k"],
   notes=["plane: xy | yz | zx (x1,x2 = X,Y | Y,Z | Z,X). L1·L2 는 파트 평면 길이",
          "mode: deform(노드 이동 + 역응력) | stress(응력만), source: formula | dat | dat_pair — 모두 필수 값 검사"])
op("indent", "변형·초기응력", "다각형·스플라인 펀치 윤곽에 필렛 압입(depth>0)/엠보싱(depth<0)", "압입 엠보싱 찍힘 dent emboss",
   "KooRemapper indent <config.yaml>",
   files=boxed({"indent.yaml": """base_model: box.k
output: box_indent
operations:
  - type: indent
    target_pid: 1
    plane: xy
    direction: -z
    depth: 0.5
    r1: 0.5
    r2: 1.0
    bottom_ratio: 0.0
    stress: false
    shape:
      type: polygon
      points:
        - [6, 3]
        - [12, 3]
        - [12, 7]
        - [6, 7]
"""}),
   cmds=[BOX_CMD, "KooRemapper indent indent.yaml"], outputs=["box_indent.k"])

# ── 재료·어셈블리 ──
op("matdb", "재료·어셈블리", "JSON 재료 DB(번들 525종)로 *MAT 카드 일괄 교체", "재질 material database 재료교체",
   "KooRemapper matdb <config.yaml>",
   files=boxed({"matdb.yaml": """model: box.k
output: box_matdb.k
mat_type: MAT_ELASTIC
materials:
  - mid: 1
    match: "SUS304"
"""}),
   cmds=[BOX_CMD, "KooRemapper matdb matdb.yaml"], outputs=["box_matdb.k"],
   notes=["사례처럼 database 를 생략하는 편이 이식성 있다 — 작업 폴더 materials/material_db.json → 실행 파일 기준 materials/·../materials/ 순으로 번들 DB 를 찾는다 (SIF 도 /opt/kooremapper/bin + /opt/kooremapper/materials 로 이 규칙에 걸린다)",
          "database 를 적으면 폴더가 붙은 값은 작업 폴더 기준, 폴더 없는 홑이름은 YAML 폴더 기준이다 — 번들 이름만 주는 형태는 없으니 절대 경로나 생략을 쓸 것",
          "match: 파트/재질 제목 부분일치, \"*\" 는 나머지 전부. mid: 로 MID 직접 지정",
          "damping_preset: smartphone_drop | smartphone_drop_aggressive | quasi_static | off (모르는 값은 rc=1)"])
op("matswap", "재료·어셈블리", "MAT+HOURGLASS+CURVE+SECTION 번들을 파트에 통째로 교체", "재질교체 bundle rubber",
   "KooRemapper matswap <config.yaml>\nKooRemapper matswap <model.k> <bundle.k> <pid> <output.k>",
   needs=["examples/matswap/two_cubes.k", "examples/matswap/rubber.k"],
   files={"swap.yaml": """model: examples/matswap/two_cubes.k
output: two_cubes_rubber.k
swaps:
  - bundle: examples/matswap/rubber.k
    pid: 1
"""},
   cmds=["KooRemapper matswap swap.yaml"], outputs=["two_cubes_rubber.k"],
   notes=["번들은 *PARAMETER 로 &PID1 &MID1 &SECID1 &HGID1 &LCID1 자리표시를 쓰는 k 파일 (examples/matswap/rubber.k 형식). ID 는 충돌 없게 자동 부여",
          "pids: [..] / swap_all: true 도 가능. PART 카드가 PID SECID MID 3필드뿐인 모델(generate box 출력 등)도 된다"])
op("assemble", "재료·어셈블리", "replace·squeeze·restack·update 등 여러 파트 연산을 순차 적용하고 초기응력 누적", "조립 복합 pipeline",
   "KooRemapper assemble <config.yaml>",
   files=boxed({"asm.yaml": """base_model: box.k
output: box_assembled
operations:
  - type: squeeze
    target_pid: 1
    eps_x: 0.0
    eps_y: -0.01
    eps_z: 0.0
material:
  E: 210000.0
  nu: 0.3
"""}),
   cmds=[BOX_CMD, "KooRemapper assemble asm.yaml"], outputs=["box_assembled.k"],
   notes=["operations[].type 는 각 op 이름(replace squeeze restack offset disconnect update generate ...)",
          "restack·merge 항목은 operations[] 안에 pid_refs: strict(기본) | warn 을 받는다 — 비운 PID 를 가리키던 자리를 못 옮기면 strict 는 rc=1(덱은 쓴다), warn 은 같은 보고에 rc=0. 자세한 것은 help restack·help merge"])

# ── 하중·경계·접촉 ──
op("load", "하중·경계·접촉", "파트 면(방향/tied/세그먼트셋 선택)에 압력·힘 하중 + 곡선", "하중 pressure 압력 force",
   "KooRemapper load <config.yaml>",
   files=boxed({"load.yaml": """model: box.k
output: box_loaded.k
loads:
  - part: 1
    mode: pressure
    value: 1.0
    direction: [0, 0, 1]
    select: direction
    angle: 45.0
    curve:
      - [0.0, 0.0]
      - [0.001, 1.0]
      - [0.01, 1.0]
"""}),
   cmds=[BOX_CMD, "KooRemapper load load.yaml"], outputs=["box_loaded.k"],
   invariants={"box_loaded.k": {"keywords": ["*LOAD_SEGMENT_SET", "*DEFINE_CURVE"]}},
   notes=["mode: pressure | normal_pressure(direction 없이 노출면 전체) | force(총 힘 N 을 투영면적으로 나눠 압력화)",
          "select: direction(법선과 direction 사이 angle 이내 면) | tied(tied 접촉 세그먼트) | set(기존 *SET_SEGMENT, set_id 필요)"])
op("boundary", "하중·경계·접촉", "파트 면을 골라 SPC 구속", "구속 spc 경계조건 fixed",
   "KooRemapper boundary <config.yaml>",
   files=boxed({"bc.yaml": """model: box.k
output: box_bc.k
boundaries:
  - part: 1
    dof: xyz
    direction: [0, 0, -1]
    select: direction
    angle: 45.0
"""}),
   cmds=[BOX_CMD, "KooRemapper boundary bc.yaml"], outputs=["box_bc.k"],
   invariants={"box_bc.k": {"keywords": ["*BOUNDARY_SPC_SET", "*SET_NODE"]}},
   notes=["dof: x y z xy xyz all ...",
          "select: direction(법선과 direction 사이 angle 이내 면) | all(파트 노출면 전체) | set(기존 *SET_NODE, set_id 필요) "
          "— load 의 select(direction|set|tied)와 값이 다르다"])
op("rbe", "하중·경계·접촉", "파트 면에 RBE2(CNRB)/RBE3(INTERPOLATION) 강체 요소", "rbe2 rbe3 spider 강체요소",
   "KooRemapper rbe <config.yaml>",
   files=boxed({"rbe.yaml": """model: box.k
output: box_rbe.k
rbe:
  - part: 1
    select: direction
    direction: [0, 0, 1]
    angle: 45.0
    type: rbe3
    mode: spider
"""}),
   cmds=[BOX_CMD, "KooRemapper rbe rbe.yaml"], outputs=["box_rbe.k"],
   notes=["mode: spider(면 전체 중심 1개) | face(면마다)",
          "select: direction | all(파트 노출면 전체) — boundary 와 달리 set 은 없다"])
op("cnrb2spring", "하중·경계·접촉", "CNRB 체결점을 두 강체 + 유격 discrete beam 조인트로 분할",
   "볼트 유격 gap clearance 나사 체결 스프링 discrete beam 측면낙하",
   "KooRemapper cnrb2spring <config.yaml>",
   needs=["examples/cnrb2spring/two_plate_bolt.k"],
   files={"spring.yaml": """model: examples/cnrb2spring/two_plate_bolt.k
output: two_plate_bolt_spring.k
axis: z
gap: 0.1
k_engage: 1.0e5
k_axial: 1.0e7
k_rot: 1.0e7
curve_range: 1.0
target_pids: [1201]
node_id_start: 90000001
elem_id_start: 9900001
card_id_start: 990001
pid_refs: strict
"""},
   cmds=["KooRemapper cnrb2spring spring.yaml"], outputs=["two_plate_bolt_spring.k"],
   invariants={"two_plate_bolt_spring.k": {"keywords": ["*ELEMENT_BEAM", "*SECTION_BEAM",
                                                        "*MAT_NONLINEAR_ELASTIC_DISCRETE_BEAM",
                                                        "*DEFINE_COORDINATE_SYSTEM", "*DEFINE_CURVE"]}},
   notes=["CNRB 하나를 Side A/B 두 강체로 쪼개고 같은 자리에 둔 팬텀 노드 2개를 제로길이 discrete beam"
          "(*SECTION_BEAM ELFORM=6 + *MAT_NONLINEAR_ELASTIC_DISCRETE_BEAM) 하나로 잇는다."
          " 원 CNRB 와 그 *SET_NODE_LIST 는 통째로 지운다.",
          "축 분리는 *DEFINE_COORDINATE_SYSTEM 이 세운다 — 로컬 r=axis(k_axial), s·t=전단(±gap 유격)."
          " 제로길이라 상대변위가 아무리 커져도 r/s/t 가 섞이지 않는다.",
          "axis 는 필수다(auto 없음). 두 파트 간격의 최대 성분과 다르면 [WARN] 만 내고 계속한다.",
          "k_rot 은 회전 3자유도 강성이다(기본 1.0e7 N*mm/rad). 0 으로 두면 회전을 풀지만 원 CNRB 와 달라진다.",
          "gap·k_engage·k_axial·k_rot 는 실측이 아닌 가정값이다 — 기본값을 쓰면 콘솔에 그 사실을 알린다.",
          "새 ID 는 고정 번호대(노드 9000만·요소 990만·카드 99만)다. 원본과 겹치면 조용히 밀지 않고 rc=1 이다.",
          "CNRB 가 잇는 두 파트는 요소 연결성으로 판정한다. 세트 안의 '*NODE 에 없는 ID' 는 제외하고 몇 개인지 알린다."])
op("contact", "하중·경계·접촉", "접촉 정의 분석·생성·자동감지·변환·수정·삭제를 한 YAML 로 순차 실행", "접촉 contact tied detect",
   "KooRemapper contact <config.yaml>",
   files=boxed({"contact.yaml": """model: box.k
output: box_contact.k
contacts:
  - action: analyze
  - action: create
    type: automatic_single_surface
    slave: { pid: 1 }
    friction: 0.2
    title: Self_Contact
"""}),
   cmds=[BOX_CMD, "KooRemapper contact contact.yaml"], outputs=["box_contact.k"],
   notes=["action: analyze | create | detect | convert | modify | remove",
          "create 의 type: 짧은 이름(auto automatic tied tied_thermal thermal tiebreak mortar tied_mortar single eroding forming) "
          "또는 *CONTACT_ 뒤 전체 키워드. 아는 키워드 밖이면 막지 않고 경고 후 그대로 쓴다(다른 열거형 키와 달리 rc=1 이 아니다)",
          "전체 자동: action: detect, scope: all, tolerance: 0.1, auto_create: true"])
op("relax", "하중·경계·접촉", "초기응력 평형용 동적 이완(DR) 설정 (5단계 프리셋)", "dr dynamic relaxation 이완",
   "KooRemapper relax <config.yaml>",
   files=boxed({"relax.yaml": """model: box.k
output: box_relaxed.k
level: 2
mode: explicit
drterm: 100.0
endtime: 1.0
"""}),
   cmds=[BOX_CMD, "KooRemapper relax relax.yaml"], outputs=["box_relaxed.k"])
op("stabilize", "하중·경계·접촉", "explicit 발산 대응 안정화 조치 12 단계 누적 적용", "안정화 발산 hourglass 호글래스",
   "KooRemapper stabilize <config.yaml>",
   files=boxed({"stab.yaml": """model: box.k
output: box_lv03.k
stabilize: explicit
level: 3
"""}),
   cmds=[BOX_CMD, "KooRemapper stabilize stab.yaml"], outputs=["box_lv03.k"],
   notes=["level 은 0~12 (0 = manual, 그 밖의 값은 rc=1)",
          "level 1 에너지 진단 → 3 TSSFAC → 4+ 호글래스 → 6+ 접촉 soft ... (상위가 하위 포함)"])
op("database", "하중·경계·접촉", "*DATABASE 출력 카드 삽입 (프리셋·개별 토글)", "출력 d3plot database glstat",
   "KooRemapper database <config.yaml>",
   files=boxed({"db.yaml": """model: box.k
output: box_drop_db.k
preset: drop
dt: 0.0001
dt_plot: 0.005
"""}),
   cmds=[BOX_CMD, "KooRemapper database db.yaml"], outputs=["box_drop_db.k"])
op("hfdamp", "하중·경계·접촉", "작은 요소 고주파 진동 억제 *DAMPING_FREQUENCY_RANGE_DEFORM", "감쇠 damping 고주파",
   "KooRemapper hfdamp <config.yaml>",
   files=boxed({"hf.yaml": """model: box.k
output: box_hfdamp.k
dt_target: 3.0e-7
cdamp: 0.99
fhigh_ratio: 100.0
mode: global
"""}),
   cmds=[BOX_CMD, "KooRemapper hfdamp hf.yaml"], outputs=["box_hfdamp.k"],
   notes=["mode: global | selective (dt ≤ dt_target 파트만)"])

# ── 솔버 설정 ──
op("implicit", "솔버 설정", "explicit 덱을 implicit(정적·동적) 설정으로 변환", "암시적 static 정적",
   "KooRemapper implicit <config.yaml>",
   files=boxed({"imp.yaml": """model: box.k
output: box_implicit.k
mode: static
level: 2
endtime: 1.0
"""}),
   cmds=[BOX_CMD, "KooRemapper implicit imp.yaml"], outputs=["box_implicit.k"],
   notes=["mode: static | dynamic, level 1(공격적)~6(보수적)"])
op("explicit", "솔버 설정", "implicit/DR/modal 카드를 걷어내 순수 explicit 로 되돌림", "명시적 되돌리기 revert",
   "KooRemapper explicit <config.yaml>",
   files=boxed({"imp.yaml": """model: box.k
output: box_implicit.k
mode: static
level: 2
endtime: 1.0
""", "exp.yaml": """model: box_implicit.k
output: box_explicit.k
keep_dr_curves: false
"""}),
   cmds=[BOX_CMD, "KooRemapper implicit imp.yaml", "KooRemapper explicit exp.yaml"], outputs=["box_explicit.k"])
op("modal", "솔버 설정", "고유진동수·모드 해석 설정으로 변환", "고유진동 modal eigen 주파수",
   "KooRemapper modal <config.yaml>",
   files=boxed({"modal.yaml": """model: box.k
output: box_modal.k
nmode: 10
fmax: 2000.0
"""}),
   cmds=[BOX_CMD, "KooRemapper modal modal.yaml"], outputs=["box_modal.k"])
op("ale", "솔버 설정", "솔리드 파트를 ALE(공기·물·폭약 등 14 프리셋)로 변환 + FSI", "유체 ale fsi 공기",
   "KooRemapper ale <config.yaml>",
   files=boxed({"ale.yaml": """model: box.k
output: box_ale.k
ale_parts:
  - pid: 1
    material: air
"""}),
   cmds=[BOX_CMD, "KooRemapper ale ale.yaml"], outputs=["box_ale.k"],
   notes=["fsi_pids: [..] 로 구조 파트와 커플링. 폭발은 detonation: {pid, x, y, z, lt}"])
op("optimize", "솔버 설정", "재질별(현재 rubber) 전역 컨트롤 카드 최적화", "고무 rubber 최적화",
   "KooRemapper optimize <config.yaml>",
   files=boxed({"opt.yaml": """model: box.k
output: box_opt.k
optimize: rubber
pids: [1]
tssfac: 0.67
"""}),
   cmds=[BOX_CMD, "KooRemapper optimize opt.yaml"], outputs=["box_opt.k"])

# ── 정보 ──
op("info", "정보·메타", "메시 정보(절점·요소·파트 수, bbox, 품질) 출력", "정보 조회 bbox 품질",
   "KooRemapper info <mesh_file>",
   files={"box.yaml": BOX}, cmds=[BOX_CMD, "KooRemapper info box.k"], outputs=[])
op("modelmeta", "정보·메타", "파트별 기하 메트릭·재질·연결성(접촉 탐지 포함) JSON 추출", "메타 json connectivity 연결성",
   "KooRemapper modelmeta <config.yaml>",
   files=boxed({"meta.yaml": """model: box.k
detect: true
gap_tol: 0.2
"""}),
   cmds=[BOX_CMD, "KooRemapper modelmeta meta.yaml"], outputs=["box_modelmeta.json"])
op("version", "정보·메타", "버전 출력", "버전", "KooRemapper version", cmds=["KooRemapper version"])
