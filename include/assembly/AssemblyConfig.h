#pragma once

#include <vector>
#include <string>

namespace KooRemapper {

struct ReplaceOperation {
    int targetPid = 0;
    std::string detailFlat;    // flat detail mesh path
    std::string shellBent;     // bent shell reference path (QUAD4)
    bool prestress = false;    // compute flat→bent bending prestress
};

struct SqueezeOperation {
    int targetPid = 0;
    double eps_x = 0.0;
    double eps_y = 0.0;
    double eps_z = 0.0;
};

struct RestackLayer {
    double thickness = 0.0;
    std::string materialCard;   // raw LS-DYNA material keyword block
};

struct RestackOperation {
    int targetPid = 0;
    std::string direction = "auto";     // auto | x | y | z
    std::string elementType = "solid";  // solid | tshell | shell
    std::vector<RestackLayer> layers;
};

struct IndentShapePoint {
    double x1, x2;
};

struct IndentOperation {
    int targetPid = 0;
    std::string plane = "xy";        // xy | yz | zx
    std::string direction = "-z";    // +z/-z, +x/-x, +y/-y
    double depth = 0.0;
    double r1 = 0.0;
    double r2 = 0.0;
    std::string shapeType = "polygon";  // polygon | spline
    std::vector<IndentShapePoint> points;
    double bottomRatio = 0.0;
    bool stress = false;
    double shellThickness = 0.0;  // explicit shell thickness (0 = auto from *SECTION_SHELL)
};

struct BendOperation {
    int targetPid = 0;
    std::string plane = "xy";       // xy | yz | zx
    std::string mode = "deform";    // deform | stress
    std::string source;             // dat | dat_pair | formula

    // source: dat
    std::string datFile;

    // source: dat_pair
    std::string datTop;
    std::string datBottom;

    // source: formula
    std::string expression;
};

struct FormStrainOperation {
    int targetPid = 0;           // 0 = auto-detect all eligible shell parts
    double shellThickness = 0.0; // 0 = auto from *SECTION_SHELL
    double minCurvature = 0.0;   // noise filter threshold (default=0)
};

struct Tet10ConvertOperation {
    int targetPid = 0;        // 0 = all eligible parts
    int elform = 0;           // 0 = auto (tet10→17, hex20→23, quad8→23, tria6→24)
    std::string convertType = "tet10";  // tet10, hex20, quad8, tria6
};

struct RefineOperation {
    int targetPid = 0;        // 0 = all parts
    int ratio = 2;            // 2 or 3
};

struct ElformOperation {
    int targetPid = 0;        // 0 = all parts
    std::string targetElform; // ELFORM number (as string) or alias name
};

struct DisconnectOperation {
    int targetPid = 0;           // 0 = all parts
    std::string mode = "full";   // full | czm | mefem
    int cohesivePartId = 0;      // CZM: cohesive part ID (0 = auto)
    double failureStrain = 0.0;  // MEFEM: EPPF value
};

struct IGATargetConfig {
    int targetPid = 0;
    double elementSize = 1.0;    // rr=rs=rt default voxel size
    double elementSizeR = 0.0;   // per-axis override (0 = use elementSize)
    double elementSizeS = 0.0;
    double elementSizeT = 0.0;
    double offset = -1.0;        // bbox expansion fixed value (-1 = auto = element_size per axis)
    double bboxScale = 0.0;      // uniform scale multiplier (0=disabled; e.g. 1.5 = expand 25% each side)
    double bboxScaleR = 0.0;     // per-axis scale override (0 = use bboxScale)
    double bboxScaleS = 0.0;
    double bboxScaleT = 0.0;
    int ir = 0;                  // integration rule (0=reduced, 1=full)
    int styp = 4;                // LCP stabilization type
    double tollg = 1.0e-3;       // LCP threshold
    int pr = 1; int ps = 1; int pt = 1;       // polynomial order
    int nisr = 1; int niss = 1; int nist = 1; // integration points per axis
};

struct IGAOperation {
    std::vector<IGATargetConfig> targets;
};

struct WarpageOperation {
    int targetPid = 0;
    std::string datFile;            // 필수
    std::string plane = "xy";       // xy | yz | zx
    std::string deflectionAxis = "z"; // +z | -z | +x | -x | +y | -y
    std::string unit = "um";        // um | mm | m
    double maskValue = 9999.0;
    double noiseThreshold = 1.0e-10;

    // data_bbox (선택)
    bool hasDataBbox = false;
    double dataBboxXmin = 0.0;
    double dataBboxXmax = 0.0;
    double dataBboxYmin = 0.0;
    double dataBboxYmax = 0.0;

    std::string outsideBehavior = "zero"; // zero | clamp | extrapolate

    double morphFactor = 1.0;
    std::string mode = "prestress"; // prestress | deform
    bool useFiniteStrain = true;    // true: von Kármán (대변형), false: Kirchhoff (소변형)

    // 디버깅
    bool debug = false;
    std::string debugPrefix = "debug/warp";
};

struct RegionSelection {
    // Bounding box filter
    bool useBoundingBox = false;
    double xMin = -1e10, xMax = 1e10;
    double yMin = -1e10, yMax = 1e10;
    double zMin = -1e10, zMax = 1e10;

    // Node/Element set filter
    std::vector<int> nodeIds;        // Specific node IDs
    std::vector<int> elementIds;     // Specific element IDs

    // Range specification
    int nodeIdMin = 0, nodeIdMax = 0;     // 0 = no filter
    int elementIdMin = 0, elementIdMax = 0;
};

struct OffsetOperation {
    // Source
    int sourcePid = 0;

    // Region selection (optional)
    RegionSelection region;

    // Offset parameters
    std::string offsetDirection = "+normal";  // +normal/-normal/±x/±y/±z
    double thickness = 0.0;
    std::string thicknessFormula = "";  // Optional formula: "1.0 + 0.1*x" (if set, overrides thickness)
    int numLayers = 1;
    bool useLocalNormals = false;  // true = per-node averaged normals, false = global average

    // Element type
    std::string elementType = "solid";  // solid | tshell | shell

    // Connection mode
    std::string connectionMode = "tied";  // tied | czm | contact
    int czmPartId = 0;                    // CZM part ID (0 = auto-increment)
    int czmMid = 0;                       // CZM material ID (0 = auto-increment)
    std::string czmMaterialCard;          // *MAT_COHESIVE_* keyword

    // Dual offset prestress mode
    std::string prestressMode = "";       // "" | "dual_offset"
    double innerOffset = 0.0;             // 압축된 형상 (deformed, 음수)
    double outerOffset = 0.0;             // 릴랙스 형상 (reference, 양수)

    // New part definition
    int newPid = 0;         // 0 = auto-increment
    int newSecid = 0;       // 0 = auto-increment
    std::string partTitle = "Offset Layer";

    // Material
    int newMid = 0;         // 0 = auto-increment
    std::string materialCard;  // Multi-line MAT keyword

    // Shell-specific
    double shellThickness = 0.0;  // 0 = use thickness
    double shellOffset = -1.0;    // -1 = use thickness/2 (mid-plane)
};

struct AssemblyOperation {
    enum Type { REPLACE, SQUEEZE, RESTACK, BEND, INDENT, FORMSTRAIN, TET10_CONVERT, REFINE, ELFORM, DISCONNECT, IGA, WARPAGE, OFFSET };
    Type type;
    ReplaceOperation replace;
    SqueezeOperation squeeze;
    RestackOperation restack;
    BendOperation bend;
    IndentOperation indent;
    FormStrainOperation formstrain;
    Tet10ConvertOperation tet10;
    RefineOperation refine;
    ElformOperation elform;
    DisconnectOperation disconnect;
    IGAOperation iga;
    WarpageOperation warpage;
    OffsetOperation offset;
};

struct AssemblyConfig {
    std::string baseModel;
    std::string output;
    std::vector<AssemblyOperation> operations;
    double E = 0.0;
    double nu = 0.0;
    bool dynamicRelaxation = false;
    bool dynainEmbed = false;        // true: embed *INITIAL_STRESS_SOLID inline (no separate .dynain)
    bool hasMaterial() const { return E > 0 && nu > 0 && nu < 0.5; }
};

} // namespace KooRemapper
