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
     {"KooRemapper generate-var --no-scale var.yaml var.k"},
     {},
     {"구간 이름은 고정 5개: zone1_dense_start zone2_increasing zone3_sparse zone4_decreasing zone5_dense_end", "--ref flat.k 를 주면 기준 메시 크기에 맞춰 스케일한다. 곡선형은 type: curved + centerline_points"}},
    {"battery", "메시 생성", "배터리 셀(적층·권취) 모델 + 스웰링 DR 덱 생성", "배터리 셀 pouch swelling 스웰링", "KooRemapper battery <config.yaml>",
     {},
     {"KooRemapper battery examples/battery/swell/stacked/stacked_swell.yaml"},
     {"examples/battery/swell/stacked/stacked_swell.yaml"},
     {"설정 키가 많아 저장소 예제(examples/battery/swell/stacked|wound/*.yaml)를 복사해 고쳐 쓰는 편이 안전하다.", "output 경로의 폴더가 있어야 한다."}},
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
     {"connection_mode: tied(기본) | czm | contact | none", "YAML 값 뒤에 # 주석을 붙이지 말 것 (element_type: solid  # ... 는 값으로 읽혀 실패한다)"}},
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
    {"restack", "메시 편집", "셸/면을 두께·재질이 다른 솔리드 층 스택으로 돌출", "적층 layer stack", "KooRemapper restack <config.yaml>",
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
     {"material_card 의 mid 칸은 라벨이다 (MID001, MAT01, 11 모두 가능). 층마다 새 MID 로 바뀐다. 라벨과 카드 내용이 같으면 재질을 공유하고, 라벨이 같아도 물성이 다르면 MID 를 따로 준다", "*MAT_…_TITLE 의 제목 줄은 그대로 두고, 같은 MID 를 가리키는 *MAT_ADD_… 카드도 함께 새 MID 로 바뀐다", "카드는 10칸 고정폭 (블록 들여쓰기를 뺀 뒤 기준). 자유 형식(쉼표)도 된다. 새 PID·SECID 는 자동"}},
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
     {"입력은 z 방향으로 쌓인 솔리드 층 파트들 (각 파트에 MAT_ELASTIC 계열 재질)"}},
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
     {"material 이 없으면 k 파일 재질을 쓴다 — 둘 다 없으면 실패. 등방 팽윤은 parts[].swelling"}},
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
     {},
     {},
     {},
     {"dat 파일은 x y z 열 (탭/공백). 스키마는 `KooRemapper help warpage` 의 YAML Config Format", "실행 검증된 자체완결 사례가 아직 없다 — 측정 데이터로 직접 확인할 것"}},
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
     {"plane: xy | xz | yz. L1·L2 는 파트 평면 길이"}},
    {"indent", "변형·초기응력", "원·다각형 펀치 영역에 필렛 압입(depth>0)/엠보싱(depth<0)", "압입 엠보싱 찍힘 dent emboss", "KooRemapper indent <config.yaml>",
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
database: /opt/kooremapper/materials/material_db.json
mat_type: MAT_ELASTIC
materials:
  - mid: 1
    match: "SUS304"
)KRH"}},
     {"KooRemapper generate box box.yaml", "KooRemapper matdb matdb.yaml"},
     {},
     {"database 를 생략하면 작업 폴더 materials/material_db.json → 실행 파일 기준 materials/·../materials/ 순으로 번들 DB 를 찾는다 (SIF: /opt/kooremapper/materials/material_db.json)", "match: 파트/재질 제목 부분일치, \"*\" 는 나머지 전부. mid: 로 MID 직접 지정"}},
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
     {"operations[].type 는 각 op 이름(replace squeeze restack offset disconnect update generate ...)"}},
    {"load", "하중·경계·접촉", "파트 면(방향/tied 선택)에 압력·힘·중력 하중 + 곡선", "하중 pressure 압력 force", "KooRemapper load <config.yaml>",
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
     {"select: direction(법선과 direction 사이 angle 이내 면) | tied"}},
    {"boundary", "하중·경계·접촉", "파트 면을 골라 SPC 구속 또는 강체벽", "구속 spc 경계조건 fixed", "KooRemapper boundary <config.yaml>",
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
     {"dof: x y z xy xyz all ..."}},
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
     {"mode: spider(면 전체 중심 1개) | face(면마다)"}},
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
     {"action: analyze | create | detect | convert | modify | remove", "전체 자동: action: detect, scope: all, tolerance: 0.1, auto_create: true"}},
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
     {"level 1 에너지 진단 → 3 TSSFAC → 4+ 호글래스 → 6+ 접촉 soft ... (상위가 하위 포함)"}},
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
