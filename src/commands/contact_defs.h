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
    std::string title;
    // Card 1
    int ssid=0, msid=0, sstyp=0, mstyp=0, sboxid=0, mboxid=0, spr=0, mpr=0;
    // Card 2
    double fs=0, fd=0, dc=0, vc=0, vdc=0; int penchk=0; double bt=0, dt=1.0e20;
    // Card 3
    double sfsa=1, sfsb=1, sast=0, sbst=0, sfsat=1, sfsbt=1, fsf=1, vsf=1;
    // Optional Card A
    bool hasCardA=false;
    int soft=0; double sofscl=0.1; int lcidab=0; double maxpar=1.025;
    int sbopt=2; int depth=2; int bsort=0; int frcfrq=1;
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
    // THERMAL 카드 (*CONTACT_..._THERMAL): K FRAD H0 LMIN LMAX CHLM BC_FLAG ALGO
    bool hasThermal=false;
    double thK=0, thFrad=0, thH0=0, thLmin=0, thLmax=0, thChlm=1.0;
    int thBcflag=0, thAlgo=0;
    // TIEBREAK 카드 (*CONTACT_..._TIEBREAK): OPTION NFLS SFLS PARAM ERATEN ERATES CT2CN
    bool hasTiebreak=false;
    int tbOption=1;
    double tbNfls=0, tbSfls=0, tbParam=0, tbEraten=0, tbErates=0, tbCt2cn=1.0;
    // Raw optional cards (backward compat)
    std::vector<std::string> optionalCards;
    int startLine=0, endLine=0;  // [start, end) in rawLines
};

struct SetDef {
    int id = 0;
    std::string type;           // "SEGMENT"/"NODE"/"PART"/"SHELL"/"SOLID"
    bool hasTitle = false;
    std::string title;
    double da1=0, da2=0, da3=0, da4=0;
    std::vector<std::array<int,4>> segments;  // SET_SEGMENT only
    std::vector<int> ids;                     // NODE/PART/SHELL/SOLID
    int startLine=0, endLine=0;
};

