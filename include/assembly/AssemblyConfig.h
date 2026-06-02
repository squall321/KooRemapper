#pragma once

#include <vector>
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

namespace KooRemapper {

struct ReplaceOperation {
    int targetPid = 0;
    std::string detailFlat;    // flat detail mesh path
    std::string shellBent;     // bent shell reference path (QUAD4)
    std::string simpleBent;    // 3D HEX8 bent reference; auto-extract top free faces → shell
    bool prestress = false;    // compute flat→bent bending prestress

    // Pre-map mirror of the detail flat (about its bbox center). Use when
    // detail's thickness/normal is oriented opposite to what the bent shell
    // expects (e.g. cover-glass face of detail should match outer face of
    // bent but currently matches inner). HEX8 connectivity is swapped on
    // odd-parity flips to keep Jacobians positive.
    bool flipInputX = false, flipInputY = false, flipInputZ = false;

    // Post-map mirror of the result (about origin). Use when the entire
    // bent result must be mirrored about a global axis (e.g. mirror-image
    // half of an assembly). Same odd-parity HEX8 swap rule applies.
    bool flipX = false, flipY = false, flipZ = false;
};

struct SqueezeOperation {
    int targetPid = 0;
    double eps_x = 0.0;
    double eps_y = 0.0;
    double eps_z = 0.0;
};

struct RestackLayer {
    double thickness = 0.0;
    int numElements = 0;               // 0 = use parent elementSize; >0 = explicit
    std::string elementType = "";      // "" = use parent; solid | tshell | shell
    std::string title = "";            // *PART title (empty = auto "Restack Layer N")
    std::string materialCard;          // raw LS-DYNA material keyword block
    double czmNormal = -1.0;          // per-layer CZM normal failure stress (-1 = use restack default)
    double czmShear  = -1.0;          // per-layer CZM shear failure stress  (-1 = use restack default)
};

struct RestackOperation {
    int targetPid = 0;
    std::string direction = "auto";     // auto | x | y | z
    std::string elementType = "solid";  // solid | tshell | shell
    double elementSize = 0.0;          // auto numElements = max(1, round(t/elementSize)); 0=off
    std::string interfaceContact = "tied";  // tied | czm | czm_auto
    double czmNormal = 0.0;            // CZM: normal tensile stress at failure [MPa]
    double czmShear  = 0.0;            // CZM: shear stress at failure [MPa]
    double dropHeight = 0.0;           // czm_auto: drop height [mm] for VC computation
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
    int targetPid = 0;               // 0 = all, -1 = use targetPids list
    std::vector<int> targetPids;     // explicit pid list (overrides targetPid when non-empty)
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
    int targetPid = 0;               // 0 = all, -1 = use targetPids list
    std::vector<int> targetPids;     // explicit pid list (overrides targetPid when non-empty)
    double shellThickness = 0.0;
    double minCurvature = 0.0;
};

struct Tet10ConvertOperation {
    int targetPid = 0;               // 0 = all, -1 = use targetPids list
    std::vector<int> targetPids;
    int elform = 0;
    std::string convertType = "tet10";
};

struct RefineOperation {
    int targetPid = 0;               // 0 = all, -1 = use targetPids list
    std::vector<int> targetPids;
    int ratio = 2;
};

struct ElformOperation {
    int targetPid = 0;               // 0 = all, -1 = use targetPids list
    std::vector<int> targetPids;
    std::string targetElform;
};

struct DisconnectOperation {
    int targetPid = 0;           // 0 = all parts
    std::string mode = "full";   // full | czm | mefem
    int cohesivePartId = 0;      // CZM: cohesive part ID (0 = auto)
    double failureStrain = 0.0;  // MEFEM: EPPF value
};

struct IGATargetConfig {
    int targetPid = 0;
    std::vector<int> targetPids; // multi-pid shorthand; expands to multiple single-pid targets
    std::string targetName;      // wildcard pattern matching *PART titles (e.g. "*FRONT*"); applyIGA expands to all matching PIDs
    std::string excludeName;     // wildcard pattern; matches the same titles to *exclude* (e.g. "Manual_*")
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
    int targetPid = 0;               // 0 = all, -1 = use targetPids list
    std::vector<int> targetPids;
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
    std::string match;        // MAT name/tag substring, "*" = catch-all
    std::string matchPart;    // PART title pattern (supports *glob*), empty = skip
    int mid = 0;              // direct MID match (0 = use match string)
    std::string matType;      // override structural card type (empty = use global)
    int thermalOverride = -1; // -1=use global, 0=false, 1=true
};

struct MatdbOperation {
    std::string databasePath;                  // path to material_db.json (empty = default)
    std::string globalMatType = "MAT_ELASTIC"; // default structural card type
    bool globalThermal = false;                // global thermal toggle

    // ------------------------------------------------------------------
    // Optional damping rescaling (LS-DYNA explicit interpretation).
    //
    // In LS-DYNA explicit `*DAMPING_PART_MASS_SET` VALDMP (alpha) is a
    // direct node-velocity damping coefficient (F_damp = -alpha * M * v),
    // NOT a Rayleigh modal coefficient. Time constant of velocity decay
    // is 2/alpha. The DB ships alpha baked at a low reference frequency
    // (~50 Hz) so raw values are 3..63 -- inadequate for smartphone drop
    // where post-impact ringing should die in ~5..10 ms (alpha 200+).
    //
    // Two knobs:
    //   * dampingAlphaScale  : multiplier on baked alpha. Default 1.0.
    //   * dampingAlphaFloor  : minimum alpha applied to all emitted damping
    //                          cards. Default 0.0 (no floor).
    //   final_alpha = max(dampingAlphaFloor, baked_alpha * dampingAlphaScale)
    //
    // dampingApplyToAllParts: if true, emit a default DAMPING_PART_MASS_SET
    // for every PART in the model whose material was NOT in the matdb DB
    // (so no damping was added by the swap). Those unmatched parts get
    // alpha = dampingAlphaFloor and a small default beta (0.01).
    //
    // Preset shortcut (set via dampingPreset). Recognised values:
    //   "smartphone_drop"            : scale=15, floor=150, apply_all=true
    //   "smartphone_drop_aggressive" : scale=20, floor=300, apply_all=true
    //   "quasi_static"               : scale=5,  floor=50,  apply_all=false
    //   "off" / ""                   : leave defaults (no rescaling)
    // Individual fields above OVERRIDE the preset when explicitly set.
    //
    // dampingTargetFreqHz: legacy alias for dampingAlphaScale, expressed
    // as a characteristic frequency. Internally converted via
    //   scale = dampingTargetFreqHz / 50.0
    // (kept for back-compat; setting dampingAlphaScale directly is
    // preferred since the "frequency" framing is misleading for explicit.)
    double      dampingAlphaScale       = 1.0;
    double      dampingAlphaFloor       = 0.0;
    bool        dampingApplyToAllParts  = false;
    double      dampingTargetFreqHz     = 0.0;
    std::string dampingPreset;

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

struct SplitOperation {
    int targetPid = 0;               // 0 = all, -1 = use targetPids list
    std::vector<int> targetPids;
    std::string direction = "auto";  // "auto" | "x" | "y" | "z"
    int divisions = 2;               // split each element into N along extrude direction
};

struct FilletOperation {
    int targetPid = 0;               // 0 = all structured HEX8 parts, -1 = use targetPids list
    std::vector<int> targetPids;
    double radius = 1.0;
    std::vector<std::string> faces;  // "z_max", ... (legacy bbox mode) or empty = auto-detect
    double angleMin = 60.0;          // min dihedral angle (deg) to consider as sharp edge
    double angleMax = 150.0;         // max dihedral angle (deg) to consider as sharp edge
    bool fixJacobian = true;         // post-fillet: detect negative-J HEX8 → split to TET4 or remove
    int smoothIter = 3;              // Laplacian smoothing iterations for interior nodes (0=off)
};

struct HFDampOperation {
    double dtTarget    = 0.0;      // REQUIRED: target timestep
    double cdamp       = 0.99;     // fraction of critical damping
    double fhighRatio  = 100.0;    // FHIGH = FLOW * fhigh_ratio
    std::string mode   = "global"; // "global" | "selective"
    double tssfac      = 0.9;      // element dt safety factor (selective mode)
};

struct BatteryOperation {
    std::string configFile;    // path to battery YAML config (relative to assemble config)
    std::string output;        // output prefix override (empty = use battery config's output)
    int    nodeIdOffset  = 0;  // >0: explicit ID offset; 0 = auto (max of current model)
    int    elemIdOffset  = 0;  // >0: explicit element ID offset; 0 = auto
    bool   useInclude    = true;  // true = *INCLUDE the generated file; false = inline
};

struct Cnrb2SolidOperation {
    std::vector<int> targetPids;     // empty = all CNRBs
    double E               = 200000.0;
    double PR              = 0.3;
    double RHO             = 7.85e-9;
    double radiusScale     = 0.999;
    int    numCircumNodes  = 0;      // 0 = auto
    double innerRadiusRatio = 0.3;
    std::string axisDirection = "auto"; // auto|x|y|z
    double zTolerance      = 0.1;
    double rTolerance      = 0.5;
    // bolt head
    double headOffsetR     = 0.0;   // 0 = no head
    double headThickness   = 2.0;
    std::string headPosition = "auto"; // auto|top|bottom|none
};

struct MergeOperation {
    std::vector<int> pids;     // PIDs to merge (one group per operation)
    std::string name;          // name for merged part/material
    int direction = 2;         // 0=x, 1=y, 2=z
    int method = 2;            // 0=voigt, 1=reuss, 2=vrh
    int newPid = 0;            // 0 = auto (max+1), >0 = user-specified
    int newMid = 0;            // 0 = auto
    int layers = 1;            // output layers per column (1=fully merge, N=split into N)
    double tolerance = 0.0;    // node merge tolerance (0=disabled, >0=merge coincident nodes first)
};

struct StripOperation {
    std::vector<std::string> keywords;  // e.g. "*NODE", "*ELEMENT_SOLID"
};

// REQ-002: free-face extraction integrated into assemble flow.
// Same algorithm as the standalone `extract-surface` command, but emits
// shells directly into the assembled model (addedShellElements_ / addedNodes_).
struct ExtractSurfaceOperation {
    int targetPid = 0;          // 0 = all parts (source solids)
    std::string face = "all";   // top | bottom | all  (ignored when midSurface=true)
    int outputPid = 0;          // PID for the new shell part (0 = auto = ++maxPartId_)
    bool midSurface = false;    // average top↔bottom node positions → midsurface shells
};

struct AssemblyOperation {
    enum Type { REPLACE, SQUEEZE, RESTACK, BEND, INDENT, FORMSTRAIN, TET10_CONVERT, REFINE, ELFORM, DISCONNECT, IGA, WARPAGE, OFFSET, MATSWAP, MATDB, LOAD, CONTACT, BOUNDARY, RBE, WRAP, UPDATE, DATABASE, CONTROL, GENERATE, FILLET, CNRB2SOLID, HFDAMP, BATTERY, SPLIT, MERGE, STRIP, EXTRACT_SURFACE };
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
    FilletOperation fillet;
    Cnrb2SolidOperation cnrb2solid;
    HFDampOperation hfdamp;
    BatteryOperation battery;
    SplitOperation split;
    MergeOperation merge;
    StripOperation strip;
    ExtractSurfaceOperation extractSurface;
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
