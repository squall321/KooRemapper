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
    std::string materialCard;  // Multi-line MAT keyword (single layer or all layers)
    std::vector<std::string> materialCards;  // Per-layer materials (if specified, overrides materialCard)

    // Shell-specific
    double shellThickness = 0.0;  // 0 = use thickness
    double shellOffset = -1.0;    // -1 = use thickness/2 (mid-plane)
};

struct MatswapOperation {
    std::string bundleFile;    // path to bundle .k file
    std::vector<int> pids;    // specific PIDs (empty = swapAll)
    std::vector<int> mids;    // target by MID: swap MAT+HOURGLASS only (no SECTION)
    bool swapAll = false;     // true = swap all parts in model
};

struct MatdbMaterialRule {
    std::string match;        // name/tag substring, "*" = catch-all
    int mid = 0;              // direct MID match (0 = use match string)
    std::string matType;      // override structural card type (empty = use global)
    int thermalOverride = -1; // -1=use global, 0=false, 1=true
};

struct MatdbOperation {
    std::string databasePath;                  // path to material_db.json (empty = default)
    std::string globalMatType = "MAT_ELASTIC"; // default structural card type
    bool globalThermal = false;                // global thermal toggle
    std::vector<MatdbMaterialRule> rules;       // per-material override rules
};

struct LoadCurvePoint {
    double time = 0.0;
    double value = 0.0;
};

struct LoadCase {
    int pid = 0;                          // PID (0 = use partName)
    std::string partName;                 // part name substring match

    std::string mode = "pressure";        // force | pressure | normal_pressure
    double value = 0.0;                   // [N] for force, [MPa] for pressure
    double direction[3] = {0, 0, 0};      // load direction vector

    std::string select = "direction";     // direction | set | tied
    double angle = 45.0;                  // direction filter tolerance (degrees)
    int setId = 0;                        // set mode: existing SET_SEGMENT ID
    int contactId = 0;                    // tied mode: specific CONTACT ID (0=auto-search)

    std::vector<LoadCurvePoint> curve;    // time-value pairs (optional)
};

struct LoadOperation {
    std::vector<LoadCase> loads;
};

struct BoundaryCase {
    int pid = 0;
    std::string partName;
    std::string dof = "all";           // all|xyz|x|y|z|xy|xz|yz|custom
    int dofx=0, dofy=0, dofz=0;
    int dofrx=0, dofry=0, dofrz=0;
    std::string select = "direction";  // direction | set
    double direction[3] = {0,0,0};
    double angle = 45.0;
    int setId = 0;                     // select=set: existing SET_NODE ID
};

struct BoundaryOperation {
    std::vector<BoundaryCase> boundaries;
};

struct ContactSide {
    int pid = 0;                          // single PID
    std::vector<int> pids;                // multiple PIDs
    bool asSegment = false;               // extract surface → SET_SEGMENT
    bool facing = false;                  // facing filter
};

struct ContactAction {
    std::string action;                   // create | detect

    // create options
    std::string type = "auto";            // auto|tied|mortar|tied_mortar|single|eroding|forming
    ContactSide slave;
    ContactSide master;
    double friction = -1.0;               // -1 = not set
    std::string title;

    // detect options
    std::string scope;                    // "all" or empty
    std::vector<std::string> includeKeys; // part name include keywords
    std::vector<std::string> excludeKeys; // part name exclude keywords
    double tolerance = 0.1;
    double normalAngle = 45.0;
    bool autoCreate = false;
    std::string titlePrefix;
    std::string skipExisting;             // "tied" | "all" | ""
    bool subtractExisting = false;
};

struct ContactOperation {
    std::vector<ContactAction> actions;
};

struct RbeCase {
    int pid = 0;
    std::string partName;
    std::string select = "direction";  // direction | all
    double direction[3] = {0, 0, 0};
    double angle = 45.0;
    std::string type = "rbe3";         // rbe2 | rbe3
    std::string mode = "spider";       // spider | face
};

struct RbeOperation {
    std::vector<RbeCase> constraints;
};

struct WrapOperation {
    std::vector<int> targetPids;     // layer PIDs (inner → outer order)
    std::string axis = "z";          // winding axis: x | y | z
    double centerA = 0.0;            // center coord in 1st perpendicular axis
    double centerB = 0.0;            // center coord in 2nd perpendicular axis
    bool autoCenter = true;          // auto-detect from geometry
    double tension = 0.0;            // wrapping tension [N/mm] (force per unit width)
};

struct GenerateOperation {
    std::string shape = "box";       // box (only shape currently)
    double lx = 100.0, ly = 20.0, lz = 10.0;   // dimensions [mm]
    int    nx = 10, ny = 4, nz = 2;             // element counts
    double rho = 7.85e-9, E = 210000.0, nu = 0.3;
    int    mid = 1, secid = 1, pid = 1;
    std::string partTitle = "Box";
};

struct UpdateOperation {
    std::string dynainFile;          // dynain file with *NODE coordinates
};

struct ControlOperation {
    // *CONTROL_TERMINATION
    double endtime = 0.0;     // 0 = skip

    // *CONTROL_TIMESTEP
    double tssfac = 0.0;      // 0 = skip
    double dt2ms  = 0.0;      // 0 = skip (negative value = mass scaling on)
    bool   setDt2ms = false;

    // *CONTROL_ENERGY  (inserted if any field != 0)
    int hgen   = 0;           // 0=skip, 1=off, 2=on
    int rwen   = 0;
    int slnten = 0;
    int rylen  = 0;

    // *CONTROL_HOURGLASS  (inserted if ihq != 0)
    int    ihq = 0;           // hourglass type (1-10, 0=skip)
    double qh  = 0.1;

    // *CONTROL_BULK_VISCOSITY  (inserted if q1 or q2 != 0)
    double q1       = 0.0;
    double q2       = 0.0;
    int    bulkType = 0;      // 0 = standard
};

struct DatabaseOperation {
    std::string preset;              // all/drop/crash/static/thermal/forming/modal/minimal
    double dt = 0.001;              // ASCII output interval
    double dtPlot = 0.0;            // d3plot interval (0 = dt*10)
    double dtThdt = 0.0;            // d3thdt interval (0 = dt)
    // Individual toggles (used when preset is empty)
    std::vector<std::string> enabledAscii;
    std::vector<std::string> enabledBinary;
    bool extentBinary = false;
    int neiph = 6, strflg = 1, sigflg = 1, epsflg = 1;
};

struct AssemblyOperation {
    enum Type { REPLACE, SQUEEZE, RESTACK, BEND, INDENT, FORMSTRAIN, TET10_CONVERT, REFINE, ELFORM, DISCONNECT, IGA, WARPAGE, OFFSET, MATSWAP, MATDB, LOAD, CONTACT, BOUNDARY, RBE, WRAP, UPDATE, DATABASE, CONTROL, GENERATE };
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
    MatswapOperation matswap;
    MatdbOperation matdb;
    LoadOperation load;
    ContactOperation contact;
    BoundaryOperation boundary;
    RbeOperation rbe;
    WrapOperation wrap;
    GenerateOperation generate;
    UpdateOperation update;
    DatabaseOperation database;
    ControlOperation control;
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
