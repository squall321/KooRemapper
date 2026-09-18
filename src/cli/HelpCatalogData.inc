// 자동 생성 — tools/help/gen_help_cpp.py (정본 tools/help/ops_help.py). 직접 고치지 말 것
static const std::vector<OpHelp> kOpHelps = {
    {"map", "메시 매핑", "평면 상세 메시를 굽힌 구조화 HEX8 참조 메시에 매핑", "매핑 bent flat 굽힘 곡면", "KooRemapper map [--single] <bent_mesh> <flat_mesh> <output>",
     {},
     {"KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper map demo_bent.k demo_flat_fine.k mapped.k"},
     {},
     {"bent 참조는 구조화 HEX8 이어야 한다. generate 가 bent/flat/flat_fine/flat_tet 세트를 만든다."}},
    {"shellmap", "메시 매핑", "굽힌 QUAD4 셸을 참조로 평면 상세 메시를 매핑", "셸매핑 shell 곡면 전개", "KooRemapper shellmap [--thickness <t>] <bent_shell> <flat_detail> <output>",
     {},
     {"KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper extract-surface demo_bent.k bent_top.k --face top", "KooRemapper shellmap bent_top.k demo_flat_fine.k shellmapped.k"},
     {},
     {"단일 곡률(원통형) 면에 적합. 이중 곡률이면 왜곡 경고가 난다."}},
    {"unfold", "메시 매핑", "굽힌 구조화 HEX8 메시를 평면으로 전개 (map 의 역)", "전개 펼치기 flat", "KooRemapper unfold <bent_mesh> <output_flat>",
     {},
     {"KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper unfold demo_bent.k unfolded.k"},
     {},
     {}},
    {"generate", "메시 생성", "시험용 곡면 메시 세트(teardrop·arc·torus…) 또는 YAML 박스 메시 생성", "생성 box 박스 teardrop arc", "KooRemapper generate [--dim-i n --dim-j n --dim-k n] <type> <output_prefix>\nKooRemapper generate box <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}},
     {"KooRemapper generate --dim-i 20 --dim-j 10 teardrop demo", "KooRemapper generate box box.yaml"},
     {},
     {"type: teardrop arc scurve helix torus twist bendtwist wave bulge taper waterdrop", "box YAML 의 mid/secid/pid/part_title 로 파트 번호·이름을 정한다. 다른 op 사례의 시작 모델로 쓴다."}},
    {"generate-var", "메시 생성", "구간별 요소 밀도가 다른 평면/곡선 메시를 YAML 로 생성", "가변밀도 variable density", "KooRemapper generate-var [--ref <flat.k>] [--no-scale] <config.yaml> <output.k>",
     {{"var.yaml", R"KRH(type: flat
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
)KRH"}},
     {"KooRemapper generate-var var.yaml var.k"},
     {},
     {"구간 이름은 고정 5개: zone1_dense_start zone2_increasing zone3_sparse zone4_decreasing zone5_dense_end", "--ref flat.k 를 주면 기준 메시 크기에 맞춰 스케일한다. 곡선형은 type: curved + centerline_points"}},
    {"battery", "메시 생성", "배터리 셀(적층·권취) 모델 + 스웰링 DR 덱 생성", "배터리 셀 pouch swelling 스웰링", "KooRemapper battery <config.yaml>",
     {},
     {"KooRemapper battery examples/battery/swell/stacked/stacked_swell.yaml"},
     {"examples/battery/swell/stacked/stacked_swell.yaml"},
     {"설정 키가 많아 저장소 예제(examples/battery/swell/stacked|wound/*.yaml)를 복사해 고쳐 쓰는 편이 안전하다.", "output 경로의 폴더가 있어야 한다.", "dynain_file 은 경로가 아니라 *INCLUDE_DYNAIN 에 그대로 찍히는 문자열이다 — 산출 덱 옆에서 솔버가 찾을 이름으로 적을 것"}},
    {"cclip", "메시 생성", "육면체 파트를 힘-변위로 보정한 C형 스프링 클립(눌린 상태 초기응력)으로 치환", "클립 spring 스프링 접점", "KooRemapper cclip <config.yaml>",
     {{"board.yaml", R"KRH(output: clip_board.k
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
)KRH"}, {"cclip.yaml", R"KRH(model: clip_board.k
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
)KRH"}},
     {"KooRemapper generate box board.yaml", "KooRemapper cclip cclip.yaml"},
     {},
     {}},
    {"convert", "메시 편집", "1차 요소를 2차 요소로 (TET10·HEX20·QUAD8·TRIA6)", "2차요소 quadratic hex20 tet10", "KooRemapper convert <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"convert.yaml", R"KRH(base_model: box.k
output: box_hex20
operations:
  - type: hex20
    elform: 23
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper convert convert.yaml"},
     {},
     {"operations[].type: tet10 | hex20 | quad8 | tria6"}},
    {"refine", "메시 편집", "요소를 변마다 1:2 또는 1:3 으로 균일 세분화", "세분화 refine 조밀", "KooRemapper refine <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"refine.yaml", R"KRH(base_model: box.k
output: box_refined
operations:
  - type: refine
    ratio: 2
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper refine refine.yaml"},
     {},
     {}},
    {"elform", "메시 편집", "*SECTION 의 ELFORM 변경 (필요하면 요소 차수도 변환)", "요소공식 section", "KooRemapper elform <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"elform.yaml", R"KRH(base_model: box.k
output: box_elform2
operations:
  - type: elform
    target_elform: 2
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper elform elform.yaml"},
     {},
     {}},
    {"disconnect", "메시 편집", "파트 경계 공유 절점을 분리 (CZM·파손 인터페이스)", "분리 czm 파손 interface", "KooRemapper disconnect <config.yaml>",
     {{"disc.yaml", R"KRH(base_model: examples/disconnect/two_hex_2part.k
output: two_hex_disc
operations:
  - type: disconnect
    mode: mefem
    target_pid: 0
    failure_strain: 0.085
)KRH"}},
     {"KooRemapper disconnect disc.yaml"},
     {"examples/disconnect/two_hex_2part.k"},
     {"입력은 절점을 공유하는 두 파트 이상 (경계면이 없으면 실패). mode: czm | mefem | full, target_pid 0 = 모든 파트 경계"}},
    {"offset", "메시 편집", "셸/표면에서 두께·방향을 지정해 솔리드 층을 돌출 (tied/CZM/contact 연결)", "돌출 두께 extrude layer", "KooRemapper offset <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"offset.yaml", R"KRH(base_model: box.k
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
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper offset offset.yaml"},
     {},
     {"connection_mode: tied(기본) | czm | contact | none (assemble 경로도 none 허용)", "material_card·czm_material_card 의 MID 칸(@MID@·@CZM_MID@·숫자·라벨)은 새 MID 로 바뀐다. 값은 10열 칸 안에 둘 것", "material_cards: 목록으로 층마다 다른 재질 (단독 offset·assemble 모두)"}},
    {"wrap", "메시 편집", "원통 파트에 와인딩 인장 초기응력(후프+반경) 부여", "와인딩 인장 hoop 압입", "KooRemapper wrap <config.yaml>",
     {{"wrap.yaml", R"KRH(model: examples/wrap/cylinder_2layer.k
output: cylinder_wrapped
material:
  E: 210000.0
  nu: 0.3
target_pid: [1, 2]
axis: z
tension: 100.0
)KRH"}},
     {"KooRemapper wrap wrap.yaml"},
     {"examples/wrap/cylinder_2layer.k"},
     {"입력은 축 방향 원통 솔리드 파트. tension 단위는 [힘/길이]"}},
    {"restack", "메시 편집", "extrude 된 솔리드를 두께·재질이 다른 층으로 다시 나눔", "적층 layer stack 두께분할", "KooRemapper restack <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"restack.yaml", R"KRH(base_model: box.k
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
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper restack restack.yaml"},
     {},
     {"element_type: solid(기본) | tshell | shell, direction: auto(기본, 자동 탐지) | x | y | z (+/- 부호도 같은 축). 모르는 값은 rc=1", "material_card 의 mid 칸은 라벨로도 쓸 수 있다 (MID001, MAT01). 층마다 새 MID 로 바뀐다. 라벨과 카드 내용이 같으면 재질을 공유하고, 라벨이 같아도 물성이 다르면 MID 를 따로 준다", "그 칸에 숫자를 적으면 그 번호를 그대로 쓴다. 이미 쓰이는 번호면 'material MID 90 is already in use -> assigned MID 91' 을 찍고 새 번호를 준다", "*MAT_…_TITLE 의 제목 줄은 그대로 두고, 같은 MID 를 가리키는 *MAT_ADD_… 카드도 함께 새 MID 로 바뀐다. 제목 줄이 없으면 [WARN] 을 내고 'Restack Layer N'(layers[].title 이 있으면 그 제목)을 채워 내보낸다. 데이터가 두 줄 이상인 카드(*MAT_RIGID·*MAT_PIECEWISE_LINEAR_PLASTICITY 등)도 마찬가지다 — 제목 자리의 줄이 '빈 칸을 뺀 모든 칸이 수이고 두 칸 이상' 이면 데이터 줄로 보고 제목이 빠진 것으로 판정한다('7075-T6 aluminum' 처럼 글자가 섞인 진짜 제목은 제목으로 남는다). 데이터 줄 자체가 없는 카드는 rc=1", "층 카드도 재질 카드 검사를 거친다 — 구조가 깨지면 rc=1, 물성 값 경고(예: PR 0.6)는 [WARN] 이고 그대로 진행한다", "카드는 10칸 고정폭 (블록 들여쓰기를 뺀 뒤 기준). 자유 형식(쉼표)도 된다. 새 SECID 는 자동", "새 층 PID 는 layers[].pid 로 층마다 못박거나 op 수준 pid_start 로 자동 발급 시작 번호를 옮길 수 있다(둘 다 없으면 예전처럼 모델 최대 PID + 1). 이미 쓰는 번호를 지정하면 조용히 바꾸지 않고 rc=1 — 'restack: layer 1 pid 2 is already used by this model - choose a free part ID'", "입력이 두 줄 포맷(*ELEMENT_SOLID (ten nodes format), 한 요소가 'eid pid' 줄 + 노드 줄)이면 지우는 요소의 노드 줄까지 함께 지우고, 새 층 요소는 표준 한 줄 포맷 *ELEMENT_SOLID 섹션을 따로 열어 쓴다 — 한 섹션에 두 포맷을 섞으면 두 줄로 읽는 쪽이 새 요소의 절반을 노드 줄로 읽는다. *ELEMENT_TSHELL 섹션의 요소도 지운다", "새 *SECTION 은 원 *SECTION 의 ELFORM 을, 새 *PART 는 원 *PART 의 HGID·TMID 를 물려받는다 (요소 종류가 같을 때만 — solid↔tshell 은 뜻이 달라 넘기지 않는다. EOSID 도 넘기지 않는다)", "대상 파트가 강체(*MAT_RIGID/*MAT_020 또는 *PART_INERTIA)면 층을 나누지 않고 rc=1 로 거절한다", "입력은 extrude 된 헥사 솔리드. 두께 방향 노드 수가 곳곳에서 같아야 하고, 아니면 not a valid extrusion 으로 멈춘다", "thickness 는 비율로 쓰인다 — 합이 실제 두께와 달라도 실제 두께에 맞춰 나눈다. 층마다 num_elements 로 두께 방향 요소 수를 준다 (첫 층이 아래쪽)", "평면 메시는 그대로 두고 두께 방향만 다시 만든다. 층마다 새 PID·SECID·MID 를 주므로 원래 *PART 는 요소 0 개인 빈 파트로 남는다", "그 죽은 PID·지워진 요소(EID)·지워진 노드(NODE)를 가리키던 자리를 훑어 옮긴다 — 체적 의미로 쓰이는 *SET_PART_LIST·*SET_PART_TITLE 은 층 PID 전부로(한 줄 8개 규칙을 지켜 줄을 늘린다), *SET_PART_COLUMN 은 딸린 칸이 있어 죽은 PID 줄을 층마다 한 줄씩으로 늘린다(딸린 칸은 그대로 복사), tied 계열 접촉(*CONTACT_*TIED*/*TIEBREAK*/*SPOTWELD*/*CONTACT_CONSTRAINT_)은 상대측 기하를 적층 축에 투영해 층이 하나로 정해질 때만 그 층으로, 그 밖의 접촉(AUTOMATIC·ERODING·SINGLE_SURFACE)은 shell 층이 섞이지 않았을 때 층 전부를 담은 새 세트로(STYP 3→2)", "한 세트를 tied 와 체적 소비자가 함께 쓰면 세트를 복제해 가른다(새 SID 를 발급). 접촉은 tied 든 아니든 층이 애매하거나 shell 층이 섞이면 옮기지 않고 이유만 보고한다(left — rc 에 들어간다)", "PID 칸이 하나뿐인 카드(*DAMPING_PART_MASS/_STIFFNESS, *DATABASE_HISTORY_PART, *MAT_ADD_THERMAL_EXPANSION, *PART_MOVE, *BOUNDARY_PRESCRIBED_MOTION_RIGID, *DEFORMABLE_TO_RIGID, *INITIAL_VELOCITY_GENERATION)는 한 칸에 층 N 개를 담을 수 없어 manual(직접 고치세요)로 남는다 — 새 PID 가 하나뿐인 merge 는 이 칸들을 옮긴다. *ELEMENT_MASS(_PART 포함)는 집중질량을 층에 나눌 수 없어 restack 에서 manual 이다", "지운 중간면 노드(NODE 축)는 *SET_NODE_LIST(_TITLE 포함) 구성원만 옮긴다 — 좌표가 똑같은 새 층 노드가 딱 하나일 때(층 두께 합·분할이 원안과 겹칠 때) 그 노드로 바꾸고, 그 밖에는 예전처럼 manual 로 보고만 한다", "*INCLUDE 가 있는 덱은 세트의 소비자를 다 볼 수 없어 세트를 펴지 않고 보고만 한다", "못 옮긴 자리가 하나라도 남으면 rc=1 이고 덱은 쓴다. 전체 목록은 덱 머리(*KEYWORD 바로 뒤)의 '$ KOOREMAPPER-PIDREF' 블록에 moved/left/manual/unknown/maybe 등급과 입력 덱 기준 줄 번호로 들어간다. maybe(화이트리스트 밖)는 rc 에 넣지 않는다", "pid_refs: strict(기본) | warn — warn 은 같은 보고를 하고 rc=0 으로 끝낸다(기존 파이프라인의 탈출구). 그 밖의 값은 rc=1 + invalid pid_refs. assemble 은 operations[] 항목 안에, 단독 restack 은 YAML 에 그대로 적는다", "strict 가 기본인 이유 — pyKooCAE 체인과 플랫폼 워커는 종료 코드로만 성공을 판정한다. rc=0 이면 콘솔 경고가 자동화에 안 보인 채 그대로 솔버까지 간다"}},
    {"update", "메시 편집", "dynain·k 파일의 *NODE 좌표로 모델 절점 좌표 덮어쓰기", "좌표갱신 dynain node", "KooRemapper update <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"sq.yaml", R"KRH(parts:
  - pid: 1
    eps_x: -0.01
    eps_y: -0.01
    eps_z: 0.0
material:
  E: 210000.0
  nu: 0.3
)KRH"}, {"update.yaml", R"KRH(model: box.k
output: box_updated.k
dynain: box_sq.k
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper squeeze box.k sq.yaml box_sq", "KooRemapper update update.yaml"},
     {},
     {}},
    {"iga", "메시 편집", "솔리드 파트를 NURBS trivariate IGA 패치로 감싸 IGA 해석용으로 변환", "nurbs isogeometric", "KooRemapper iga <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"iga.yaml", R"KRH(base_model: box.k
output: box_iga
operations:
  - type: iga
    targets:
      - target_pid: 1
        element_size: 4.0
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper iga iga.yaml"},
     {},
     {}},
    {"extract-surface", "표면·재메시", "솔리드 파트의 윗면/아랫면/전체 표면을 셸로 추출", "표면추출 surface shell 면", "KooRemapper extract-surface <solid.k> <output_shell.k> [--pid N] [--face top|bottom|all] [--output-pid N]",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper extract-surface box.k box_top.k --face top --output-pid 10"},
     {},
     {}},
    {"tetremesh", "표면·재메시", "TET4 파트의 불량 요소 패치를 국소 재메시 (localimprove | tetgen)", "사면체 품질 tet remesh", "KooRemapper tetremesh <config.yaml>",
     {{"tet.yaml", R"KRH(model: demo_flat_tet.k
output: demo_flat_tet_fixed.k
backend: localimprove
target_pids: [1]
quality:
  min_jacobian: 0.2
  max_aspect_ratio: 8.0
)KRH"}},
     {"KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper tetremesh tet.yaml"},
     {},
     {}},
    {"meshfix", "표면·재메시", "TET4 파트를 Gmsh 로 전체 재메시 (gmsh 실행 파일 필요)", "gmsh 재메시", "KooRemapper meshfix <config.yaml>",
     {{"meshfix.yaml", R"KRH(model: demo_flat_tet.k
output: remeshed.k
pid: 1
lc_target: 5.0
adaptive: true
warn_min_jac: 0.15
)KRH"}},
     {"KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper meshfix meshfix.yaml"},
     {},
     {"gmsh 탐색: KOOREMAPPER_GMSH 환경변수 → 실행 파일 옆 gmsh/·gmsh-<ver>/[bin/] → PATH → /opt/gmsh-*/bin/gmsh (SIF 는 그대로 동작)"}},
    {"cnrb2solid", "표면·재메시", "CNRB(절점 강체) 볼트를 HEX8 솔리드 원통 + tied 접촉으로 변환", "볼트 bolt cnrb 원통", "KooRemapper cnrb2solid <config.yaml>",
     {{"cnrb.yaml", R"KRH(model: examples/cnrb2solid/bolt_simple.k
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
)KRH"}},
     {"KooRemapper cnrb2solid cnrb.yaml"},
     {"examples/cnrb2solid/bolt_simple.k"},
     {"입력 모델에 원형으로 배치된 *CONSTRAINED_NODAL_RIGID_BODY 가 있어야 한다. 헤드는 head_offset_r·head_thickness·head_position"}},
    {"merge", "표면·재메시", "적층 파트들을 하나의 균질화 재질 층으로 병합 (voigt/reuss/vrh)", "병합 균질화 homogenize", "KooRemapper merge <config.yaml>",
     {{"merge.yaml", R"KRH(model: examples/merge/three_layer.k
output: three_layer_merged.k
direction: z
method: vrh
merge:
  - pids: [1, 2, 3]
    name: "Homogenized_Stack"
)KRH"}},
     {"KooRemapper merge merge.yaml"},
     {"examples/merge/three_layer.k"},
     {"입력은 z 방향으로 쌓인 솔리드 층 파트들 (각 파트에 MAT_ELASTIC 계열 재질)", "합친 파트들은 요소 0 개인 빈 파트로 남고 새 PID 하나가 생긴다 (위 사례는 PID 1,2,3 → 4)", "그 죽은 PID·지워진 요소(EID)·지워진 노드(NODE)를 가리키던 자리를 훑어 옮긴다 — 세트·접촉은 물론, PID 칸이 하나뿐인 카드(*DAMPING_PART_MASS/_STIFFNESS, *DATABASE_HISTORY_PART, *MAT_ADD_THERMAL_EXPANSION, *PART_MOVE, *BOUNDARY_PRESCRIBED_MOTION_RIGID, *DEFORMABLE_TO_RIGID, *INITIAL_VELOCITY_GENERATION)도 새 PID 로 바꾼다. 새 PID 가 여럿인 restack 은 이 칸들을 manual 로 남긴다", "두 칸이 모두 이번 merge 로 사라지는 *CONSTRAINED_RIGID_BODIES 는 합치면 자기 자신을 가리키게 되므로 옮기지 않고 보고만 한다", "*ELEMENT_MASS(_PART 포함)는 merge 에서도 옮기지 않고 manual 로 남긴다 — 변형마다 PID 칸 자리가 달라(EID·노드 ID·MASS·PID / _PART 는 PID·MASS) 잘못 짚으면 노드 ID 를 덮어쓴다. 집중질량은 직접 배분해라", "못 옮긴 자리가 하나라도 남으면 rc=1 이고 덱은 쓴다. 전체 목록은 덱 머리(*KEYWORD 바로 뒤)의 '$ KOOREMAPPER-PIDREF' 블록에 moved/left/manual/unknown/maybe 등급과 입력 덱 기준 줄 번호로 들어간다. maybe(화이트리스트 밖)는 rc 에 넣지 않는다", "pid_refs: strict(기본) | warn — warn 은 같은 보고를 하고 rc=0 으로 끝낸다. 그 밖의 값은 rc=1 + invalid pid_refs. assemble 은 operations[] 항목 안에, 단독 merge 는 YAML 에 그대로 적는다", "위 사례의 three_layer.k 는 *MAT_ADD_THERMAL_EXPANSION 2 건이 죽은 PID 를 가리켜 '옮김' 으로 보고된다 — 못 옮긴 자리가 없어 rc=0 이다"}},
    {"strip", "표면·재메시", "지정 키워드를 k 파일에서 제거 (메시 빼고 카드만 남기기 등)", "제거 키워드 remove", "KooRemapper strip <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"strip.yaml", R"KRH(model: box.k
output: box_cards_only.k
keywords:
  - "*NODE"
  - "*ELEMENT_SOLID"
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper strip strip.yaml"},
     {},
     {}},
    {"strain", "변형·초기응력", "기준·변형 메시 쌍의 요소별 변형률(6성분) CSV", "변형률 strain csv", "KooRemapper strain [--type green|...] <ref_mesh> <def_mesh> <output.csv>",
     {},
     {"KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper strain demo_flat.k demo_bent.k strain.csv"},
     {},
     {"두 메시는 절점·요소 번호가 같아야 한다."}},
    {"prestress", "변형·초기응력", "기준·변형 메시 쌍에서 Hooke 로 응력 → *INITIAL_STRESS_SOLID", "초기응력 prestress dynain", "KooRemapper prestress [--E v --nu v --strain green|...] <ref_mesh> <def_mesh> <output>",
     {},
     {"KooRemapper generate --dim-i 20 --dim-j 5 arc demo", "KooRemapper prestress --E 210000 --nu 0.3 demo_flat.k demo_bent.k demo_pre"},
     {},
     {}},
    {"squeeze", "변형·초기응력", "파트를 지정 변형률로 압축하고 역방향 초기응력 출력 (억지 끼움)", "압축 억지끼움 interference swelling", "KooRemapper squeeze <mesh.k> <config.yaml> <output_prefix>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"sq.yaml", R"KRH(parts:
  - pid: 1
    eps_x: -0.01
    eps_y: -0.01
    eps_z: 0.0
material:
  E: 210000.0
  nu: 0.3
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper squeeze box.k sq.yaml box_sq"},
     {},
     {"material 이 없으면 k 파일 재질을 쓴다 — 둘 다 없으면 실패. 등방 팽윤은 parts[].swelling", "config YAML 은 BOM 없이 저장할 것 — 이 op 만은 아직 BOM 이 붙으면 'No parts defined in squeeze config' 로 rc=1 이다(메모장은 BOM 을 붙인다)"}},
    {"formstrain", "변형·초기응력", "셸 이면각으로 성형 소성변형률 추정 → *INITIAL_STRAIN_SHELL", "성형 forming 곡률", "KooRemapper formstrain <config.yaml>",
     {{"fs.yaml", R"KRH(base_model: examples/formstrain/bent_shell.k
output: bent_formstrain
dynain_embed: true
operations:
  - type: formstrain
)KRH"}},
     {"KooRemapper formstrain fs.yaml"},
     {"examples/formstrain/bent_shell.k"},
     {"대상은 SECTION_SHELL + MAT_024(SIGY > 0) 셸 파트. 없으면 'no eligible shell parts' 로 아무것도 안 쓴다", "target_pid 를 생략하면 조건에 맞는 모든 셸 파트"}},
    {"warpage", "변형·초기응력", "측정 워피지 데이터(dat)로 셸·솔리드 파트 면외 변형", "워피지 휨 warp", "KooRemapper warpage <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"warpage.yaml", R"KRH(base_model: box.k
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
)KRH"}, {"warp.dat", R"KRH(0 0 0 0 0
0 50 100 50 0
0 0 0 0 0
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper warpage warpage.yaml"},
     {},
     {"dat 파일은 처짐값 행렬(행×열, 공백 구분). 파트 평면 bbox(또는 data_bbox)에 펼치며 열 0 = 평면 1축 최소, 행 0 = 2축 최소 (bend 의 dat 는 행 0 = 최대). 값 단위는 unit(기본 um)", "mode: prestress(기본, 초기응력만) | deform(노드 이동). outside_behavior: zero(기본) | clamp | extrapolate"}},
    {"bend", "변형·초기응력", "처짐 함수 w(x1,x2) 로 파트를 굽히고 초기응력 계산", "굽힘 bending 곡률 formula", "KooRemapper bend <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"bend.yaml", R"KRH(base_model: box.k
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
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper bend bend.yaml"},
     {},
     {"plane: xy | yz | zx (x1,x2 = X,Y | Y,Z | Z,X). L1·L2 는 파트 평면 길이", "mode: deform(노드 이동 + 역응력) | stress(응력만), source: formula | dat | dat_pair — 모두 필수 값 검사"}},
    {"indent", "변형·초기응력", "다각형·스플라인 펀치 윤곽에 필렛 압입(depth>0)/엠보싱(depth<0)", "압입 엠보싱 찍힘 dent emboss", "KooRemapper indent <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"indent.yaml", R"KRH(base_model: box.k
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
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper indent indent.yaml"},
     {},
     {}},
    {"matdb", "재료·어셈블리", "JSON 재료 DB(번들 525종)로 *MAT 카드 일괄 교체", "재질 material database 재료교체", "KooRemapper matdb <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"matdb.yaml", R"KRH(model: box.k
output: box_matdb.k
mat_type: MAT_ELASTIC
materials:
  - mid: 1
    match: "SUS304"
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper matdb matdb.yaml"},
     {},
     {"사례처럼 database 를 생략하는 편이 이식성 있다 — 작업 폴더 materials/material_db.json → 실행 파일 기준 materials/·../materials/ 순으로 번들 DB 를 찾는다 (SIF 도 /opt/kooremapper/bin + /opt/kooremapper/materials 로 이 규칙에 걸린다)", "database 를 적으면 폴더가 붙은 값은 작업 폴더 기준, 폴더 없는 홑이름은 YAML 폴더 기준이다 — 번들 이름만 주는 형태는 없으니 절대 경로나 생략을 쓸 것", "match: 파트/재질 제목 부분일치, \"*\" 는 나머지 전부. mid: 로 MID 직접 지정", "damping_preset: smartphone_drop | smartphone_drop_aggressive | quasi_static | off (모르는 값은 rc=1)"}},
    {"matswap", "재료·어셈블리", "MAT+HOURGLASS+CURVE+SECTION 번들을 파트에 통째로 교체", "재질교체 bundle rubber", "KooRemapper matswap <config.yaml>\nKooRemapper matswap <model.k> <bundle.k> <pid> <output.k>",
     {{"swap.yaml", R"KRH(model: examples/matswap/two_cubes.k
output: two_cubes_rubber.k
swaps:
  - bundle: examples/matswap/rubber.k
    pid: 1
)KRH"}},
     {"KooRemapper matswap swap.yaml"},
     {"examples/matswap/two_cubes.k", "examples/matswap/rubber.k"},
     {"번들은 *PARAMETER 로 &PID1 &MID1 &SECID1 &HGID1 &LCID1 자리표시를 쓰는 k 파일 (examples/matswap/rubber.k 형식). ID 는 충돌 없게 자동 부여", "pids: [..] / swap_all: true 도 가능. PART 카드가 PID SECID MID 3필드뿐인 모델(generate box 출력 등)도 된다"}},
    {"assemble", "재료·어셈블리", "replace·squeeze·restack·update 등 여러 파트 연산을 순차 적용하고 초기응력 누적", "조립 복합 pipeline", "KooRemapper assemble <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"asm.yaml", R"KRH(base_model: box.k
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
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper assemble asm.yaml"},
     {},
     {"operations[].type 는 각 op 이름(replace squeeze restack offset disconnect update generate ...)", "restack·merge 항목은 operations[] 안에 pid_refs: strict(기본) | warn 을 받는다 — 비운 PID 를 가리키던 자리를 못 옮기면 strict 는 rc=1(덱은 쓴다), warn 은 같은 보고에 rc=0. 자세한 것은 help restack·help merge"}},
    {"load", "하중·경계·접촉", "파트 면(방향/tied/세그먼트셋 선택)에 압력·힘 하중 + 곡선", "하중 pressure 압력 force", "KooRemapper load <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"load.yaml", R"KRH(model: box.k
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
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper load load.yaml"},
     {},
     {"mode: pressure | normal_pressure(direction 없이 노출면 전체) | force(총 힘 N 을 투영면적으로 나눠 압력화)", "select: direction(법선과 direction 사이 angle 이내 면) | tied(tied 접촉 세그먼트) | set(기존 *SET_SEGMENT, set_id 필요)"}},
    {"boundary", "하중·경계·접촉", "파트 면을 골라 SPC 구속", "구속 spc 경계조건 fixed", "KooRemapper boundary <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"bc.yaml", R"KRH(model: box.k
output: box_bc.k
boundaries:
  - part: 1
    dof: xyz
    direction: [0, 0, -1]
    select: direction
    angle: 45.0
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper boundary bc.yaml"},
     {},
     {"dof: x y z xy xyz all ...", "select: direction(법선과 direction 사이 angle 이내 면) | all(파트 노출면 전체) | set(기존 *SET_NODE, set_id 필요) — load 의 select(direction|set|tied)와 값이 다르다"}},
    {"rbe", "하중·경계·접촉", "파트 면에 RBE2(CNRB)/RBE3(INTERPOLATION) 강체 요소", "rbe2 rbe3 spider 강체요소", "KooRemapper rbe <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"rbe.yaml", R"KRH(model: box.k
output: box_rbe.k
rbe:
  - part: 1
    select: direction
    direction: [0, 0, 1]
    angle: 45.0
    type: rbe3
    mode: spider
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper rbe rbe.yaml"},
     {},
     {"mode: spider(면 전체 중심 1개) | face(면마다)", "select: direction | all(파트 노출면 전체) — boundary 와 달리 set 은 없다"}},
    {"contact", "하중·경계·접촉", "접촉 정의 분석·생성·자동감지·변환·수정·삭제를 한 YAML 로 순차 실행", "접촉 contact tied detect", "KooRemapper contact <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"contact.yaml", R"KRH(model: box.k
output: box_contact.k
contacts:
  - action: analyze
  - action: create
    type: automatic_single_surface
    slave: { pid: 1 }
    friction: 0.2
    title: Self_Contact
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper contact contact.yaml"},
     {},
     {"action: analyze | create | detect | convert | modify | remove", "create 의 type: 짧은 이름(auto automatic tied tied_thermal thermal tiebreak mortar tied_mortar single eroding forming) 또는 *CONTACT_ 뒤 전체 키워드. 아는 키워드 밖이면 막지 않고 경고 후 그대로 쓴다(다른 열거형 키와 달리 rc=1 이 아니다)", "전체 자동: action: detect, scope: all, tolerance: 0.1, auto_create: true"}},
    {"relax", "하중·경계·접촉", "초기응력 평형용 동적 이완(DR) 설정 (5단계 프리셋)", "dr dynamic relaxation 이완", "KooRemapper relax <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"relax.yaml", R"KRH(model: box.k
output: box_relaxed.k
level: 2
mode: explicit
drterm: 100.0
endtime: 1.0
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper relax relax.yaml"},
     {},
     {}},
    {"stabilize", "하중·경계·접촉", "explicit 발산 대응 안정화 조치 12 단계 누적 적용", "안정화 발산 hourglass 호글래스", "KooRemapper stabilize <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"stab.yaml", R"KRH(model: box.k
output: box_lv03.k
stabilize: explicit
level: 3
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper stabilize stab.yaml"},
     {},
     {"level 은 0~12 (0 = manual, 그 밖의 값은 rc=1)", "level 1 에너지 진단 → 3 TSSFAC → 4+ 호글래스 → 6+ 접촉 soft ... (상위가 하위 포함)"}},
    {"database", "하중·경계·접촉", "*DATABASE 출력 카드 삽입 (프리셋·개별 토글)", "출력 d3plot database glstat", "KooRemapper database <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"db.yaml", R"KRH(model: box.k
output: box_drop_db.k
preset: drop
dt: 0.0001
dt_plot: 0.005
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper database db.yaml"},
     {},
     {}},
    {"hfdamp", "하중·경계·접촉", "작은 요소 고주파 진동 억제 *DAMPING_FREQUENCY_RANGE_DEFORM", "감쇠 damping 고주파", "KooRemapper hfdamp <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"hf.yaml", R"KRH(model: box.k
output: box_hfdamp.k
dt_target: 3.0e-7
cdamp: 0.99
fhigh_ratio: 100.0
mode: global
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper hfdamp hf.yaml"},
     {},
     {"mode: global | selective (dt ≤ dt_target 파트만)"}},
    {"implicit", "솔버 설정", "explicit 덱을 implicit(정적·동적) 설정으로 변환", "암시적 static 정적", "KooRemapper implicit <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"imp.yaml", R"KRH(model: box.k
output: box_implicit.k
mode: static
level: 2
endtime: 1.0
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper implicit imp.yaml"},
     {},
     {"mode: static | dynamic, level 1(공격적)~6(보수적)"}},
    {"explicit", "솔버 설정", "implicit/DR/modal 카드를 걷어내 순수 explicit 로 되돌림", "명시적 되돌리기 revert", "KooRemapper explicit <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"imp.yaml", R"KRH(model: box.k
output: box_implicit.k
mode: static
level: 2
endtime: 1.0
)KRH"}, {"exp.yaml", R"KRH(model: box_implicit.k
output: box_explicit.k
keep_dr_curves: false
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper implicit imp.yaml", "KooRemapper explicit exp.yaml"},
     {},
     {}},
    {"modal", "솔버 설정", "고유진동수·모드 해석 설정으로 변환", "고유진동 modal eigen 주파수", "KooRemapper modal <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"modal.yaml", R"KRH(model: box.k
output: box_modal.k
nmode: 10
fmax: 2000.0
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper modal modal.yaml"},
     {},
     {}},
    {"ale", "솔버 설정", "솔리드 파트를 ALE(공기·물·폭약 등 14 프리셋)로 변환 + FSI", "유체 ale fsi 공기", "KooRemapper ale <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"ale.yaml", R"KRH(model: box.k
output: box_ale.k
ale_parts:
  - pid: 1
    material: air
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper ale ale.yaml"},
     {},
     {"fsi_pids: [..] 로 구조 파트와 커플링. 폭발은 detonation: {pid, x, y, z, lt}"}},
    {"optimize", "솔버 설정", "재질별(현재 rubber) 전역 컨트롤 카드 최적화", "고무 rubber 최적화", "KooRemapper optimize <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"opt.yaml", R"KRH(model: box.k
output: box_opt.k
optimize: rubber
pids: [1]
tssfac: 0.67
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper optimize opt.yaml"},
     {},
     {}},
    {"info", "정보·메타", "메시 정보(절점·요소·파트 수, bbox, 품질) 출력", "정보 조회 bbox 품질", "KooRemapper info <mesh_file>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper info box.k"},
     {},
     {}},
    {"modelmeta", "정보·메타", "파트별 기하 메트릭·재질·연결성(접촉 탐지 포함) JSON 추출", "메타 json connectivity 연결성", "KooRemapper modelmeta <config.yaml>",
     {{"box.yaml", R"KRH(output: box.k
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
)KRH"}, {"meta.yaml", R"KRH(model: box.k
detect: true
gap_tol: 0.2
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper modelmeta meta.yaml"},
     {},
     {}},
    {"version", "정보·메타", "버전 출력", "버전", "KooRemapper version",
     {},
     {"KooRemapper version"},
     {},
     {}},
};
