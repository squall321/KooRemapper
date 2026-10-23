#pragma once
#include <string>
#include <vector>
#include <array>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

// ContactDef: parsed *CONTACT_* block
struct ContactDef {
    int index = 0;
    std::string type;           // e.g. "AUTOMATIC_SURFACE_TO_SURFACE"
    std::string fullKeyword;    // e.g. "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TITLE"
    bool hasTitle = false;
    // `_ID` 접미사도 카드 앞에 줄을 **1줄 더** 둔다(cid + 제목). 이것을 안 보면 편집이
    // Card 1 자리를 한 줄 앞으로 잡아 **SSID 칸에 값을 덮어쓴다**(재현: modify friction 0.33 이
    // 슬레이브 파트 ID 칸에 들어가고 FS 는 그대로, 그런데 "Modified: FS=0.33" 이라고 보고한다).
    bool hasId = false;
    // `_ID` 카드의 CID. **새로 만드는 접촉에만** 쓴다 — 덱에서 읽은 `_ID` 카드는 `title` 에 줄
    // 전체(CID+제목)가 들어 있고 그쪽은 바이트를 보존해 되쓴다.
    int cid = 0;
    std::string title;
    // 덱에서 읽은 `_ID` 카드를 **칸대로** 가른 값 — 보고·그림용이다(되쓰기는 위 `title` 의 줄 전체를 쓴다).
    // CID 는 1~10칸, 제목은 11~80칸(Vol_II `*CONTACT` ID 카드). 예전엔 보고가 `title` 을 그대로 써서 CID 숫자가
    // 제목에 붙었다(`1ADD_to_3`). `_ID` 가 아니면 idCid=0 · idTitle 은 비어 있다.
    int idCid = 0;
    std::string idTitle;
    // `_MPP`(OPTION5) — MPP 1 카드(와 첫 칸이 `&` 인 MPP 2)가 Card 1 **앞에** 온다. 예전엔 몰라서 MPP 1 을 Card 1 로 읽었다.
    bool hasMpp = false;

    // ── 카드 자리(파서가 채운다 · 덱 줄 번호, 없으면 -1) ─────────────────────────────
    // 매뉴얼 Vol_I *CONTACT 「Cards must appear in the exact order listed below」:
    //   ID → MPP 1 → (MPP 2) → Card 1 · 2 · 3 → Card 4(형마다) → THRM → ORFR → 선택 카드 A, B, …
    // **빈 줄도 카드다**(「Optional Cards A … may be blank lines」). 편집하는 쪽(modify · optimize · stabilize)은
    // 줄을 **직접 세지 않고** 이 자리를 쓴다 — 저마다 세던 시절에 Card 4 를 Card A 로 덮어쓰고, 빈 Card B 뒤의
    // Card C 를 Card B 로 다시 썼다.
    int idLine = -1;
    std::vector<int> mppLines;
    int cardLine[3] = {-1, -1, -1};       // Card 1 · 2 · 3
    std::vector<int> card4Lines;           // Card 4 (+ 4.1a · 4.1b · 4.2b …)
    std::vector<int> thrmLines;            // THRM 1 …
    std::vector<int> orfrLines;            // ORFR 1-4
    std::vector<int> optLines;             // 선택 카드 A, B, … 차례대로
    // 선택 카드가 어디서 시작하는지 **확정했는가**. Card 4 · THRM 수를 모르는 형(TIEBREAK_USER · THERMAL_FRICTION …)이면
    // false 이고 까닭이 `layoutWhy` 에 있다 — 그때 선택 카드를 고치면 필수 카드를 덮어쓰므로 편집은 거절한다.
    bool layoutKnown = true;
    std::string layoutWhy;

    // Card 1
    int ssid=0, msid=0, sstyp=0, mstyp=0, sboxid=0, mboxid=0, spr=0, mpr=0;
    // Card 2
    double fs=0, fd=0, dc=0, vc=0, vdc=0; int penchk=0; double bt=0, dt=1.0e20;
    // Card 3
    double sfsa=1, sfsb=1, sast=0, sbst=0, sfsat=1, sfsbt=1, fsf=1, vsf=1;
    // Optional Card A
    // ⚠ 안 준 칸은 **0**(= LS-DYNA 가 형마다 정하는 기본)이다. 예전엔 MAXPAR 1.025 · DEPTH 2 · SBOPT 2 · FRCFRQ 1 ·
    //   SOFSCL 0.1 을 늘 적어 형마다 다른 기본(예 AUTOMATIC_GENERAL 의 DEPTH 3)을 덮었다. 0 은 매뉴얼 일반 규칙상 기본이다.
    bool hasCardA=false;
    int soft=0; double sofscl=0; int lcidab=0; double maxpar=0;
    int sbopt=0; int depth=0; int bsort=0; int frcfrq=0;
    // Optional Card B
    bool hasCardB=false;
    double penmax=0; int thkopt=0; int shlthk=0; int snlog=0;
    int isym=0; int i2d3d=0; double sldthk=0; double sldstf=0;
    // Optional Card C
    bool hasCardC=false;
    int igap=1; int ignore_=0; double dprfac=0; double dtstif=0;
    double edgek=0; double flangl=0; int cid_rcf=0;
    // Optional Card D
    bool hasCardD=false;
    int q2tri=0; double dtpchk=0; double sfnbr=0; double fnlscl=0;
    double dnlscl=0; int tcso=0; int tiedid=0; int shledg=0;
    // Optional Card E
    bool hasCardE=false;
    int sharec=0; int cparm8=0; int ipback=0; int srnde=0;
    double fricsf=1; int icor=0; int ftorq=0; int region=0;
    // Optional Card F
    bool hasCardF=false;
    int pstiff=0; int ignroff=0; double fstol=2.0;
    int d2binr=0; int ssftyp=0; int swtpr=0; double tetfac=0;
    // Optional Card G
    bool hasCardG=false;
    double shloff=0;
    // THRM 1 (*CONTACT_..._THERMAL): K FRAD H0 LMIN LMAX FTOSA BC_FLG ALGO
    // ⚠ 6번째 칸은 3D 접촉에서 **FTOSA**(마찰열을 SURFA 쪽에 나누는 비율, 0 = 0.5)다 — CHLM 은 `*CONTACT_2D` 에만 있다.
    //   예전엔 CHLM 으로 알고 1.0 을 넣어 마찰열을 전부 SURFA 쪽으로 보냈다. 기본은 0.
    bool hasThermal=false;
    double thK=0, thFrad=0, thH0=0, thLmin=0, thLmax=0, thFtosa=0;
    int thBcflag=0, thAlgo=0;
    // Card 4 (*CONTACT_AUTOMATIC_..._TIEBREAK): OPTION NFLS SFLS PARAM ERATEN ERATES CT2CN
    // ⚠ 매뉴얼은 OPTION · NFLS · SFLS 를 **required** 로 둔다(기본값 없음). 예전엔 생략하면 1(영구 고착 · 파손 없음)을 몰래 넣었다.
    //   만드는 쪽은 option 을 받아야만 이 카드를 쓴다(contact.cpp).
    bool hasTiebreak=false;
    int tbOption=0;
    double tbNfls=0, tbSfls=0, tbParam=0, tbEraten=0, tbErates=0, tbCt2cn=1.0;
    // Card 4 (*CONTACT_ERODING_*): ISYM EROSOP IADJ — 매뉴얼 기본 0 · 1 · 0(SMP). 예전엔 이 필수 카드를 아예 안 썼다.
    bool hasEroding=false;
    // Raw optional cards (backward compat) — 선택 카드(A…)의 원문만 든다(Card 4 · THRM · ORFR 는 들지 않는다).
    std::vector<std::string> optionalCards;
    int startLine=0, endLine=0;  // [start, end) in rawLines
};

struct SetDef {
    int id = 0;
    std::string type;           // "SEGMENT"/"NODE"/"PART"/"SHELL"/"SOLID" — **방언은 빼고** 종류만
    // 방언(`GENERATE`·`GENERATE_INCREMENT`·`GENERAL`·`ADD`·`INTERSECT`·`COLUMN`·`COLLECT`).
    // 빈 문자열이면 평범한 목록이다.
    std::string dialect;
    // 멤버의 **뜻을 확정했는가**. `_ADD`·`_INTERSECT` 는 멤버가 **세트 ID** 고 `_GENERAL` 은
    // 옵션 코드(ALL·BOX·DELETE…)라 개체 ID 가 아니다. 그때는 `ids` 를 **비워 둔다** —
    // 채워 두면 소비자(`resolvePids` 등)가 그것을 파트 ID 로 쓴다. 닫히는 쪽으로 실패한다.
    bool membersKnown = true;
    // `_GENERATE` 계열의 **범위**(beg, end, inc). 파서는 이것을 **펼치지 않는다** —
    // 매뉴얼이 "All **defined** ID's between and including B[N]BEG to B[N]END are added to the
    // set. B[N]BEG and B[N]END may simply be **limits on the ID's** and not element ID's" 라고
    // 못 박았다. 그대로 펼치면 `1 999999` 짜리 덱에서 없는 파트 백만 개를 만들어 낸다.
    // 무엇이 정의됐는지는 메시를 든 쪽이 안다 — `ct_resolveSetRanges` 가 채운다.
    std::vector<std::array<int,3>> ranges;
    // 그 범위를 **정의된 ID 로 좁혔는가**. 메시를 안 읽은 op 에서는 false 로 남는다 —
    // 그때 `ids` 가 비어 있는 것은 "멤버가 없다" 가 아니라 "아직 못 셌다" 다. 화면이 그것을
    // 구분해 말해야 한다(0건이라고 말하면 거짓이다).
    bool rangesResolved = false;
    bool hasTitle = false;
    std::string title;
    double da1=0, da2=0, da3=0, da4=0;
    std::vector<std::array<int,4>> segments;  // SET_SEGMENT only
    std::vector<int> ids;                     // NODE/PART/SHELL/SOLID
    // `_ADD`·`_INTERSECT` 의 멤버 — **세트 ID** 다(개체 ID 가 아니다). `ids` 와 섞지 않고 따로 든다.
    // `*SET_PART_ADD` 의 음수는 「앞 칸부터 그 절대값까지의 범위」다(Vol_I `*SET_PART_ADD` PSID[N]).
    // 펼치는 것은 정본 해석기(`set_members.h`) 하나만 한다 — 소비자가 이 칸을 직접 읽지 않는다.
    std::vector<int> memberSets;
    int startLine=0, endLine=0;
};

