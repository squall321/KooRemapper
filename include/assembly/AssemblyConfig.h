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

struct AssemblyOperation {
    enum Type { REPLACE, SQUEEZE, RESTACK, BEND, INDENT, FORMSTRAIN, TET10_CONVERT, REFINE, ELFORM, DISCONNECT };
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
