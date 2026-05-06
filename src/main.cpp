#include "core/Platform.h"
#ifdef _WIN32
#  define WIN32_LEAN_AND_MEAN
#  define NOMINMAX
#  include <windows.h>
// windows.h defines ERROR, BOOL, etc. as macros — undefine to avoid conflicts
#  ifdef ERROR
#    undef ERROR
#  endif
#  ifdef BOOL
#    undef BOOL
#  endif
#endif
#include "core/Mesh.h"
#include "core/ShellMesh.h"
#include "parser/KFileReader.h"
#include "parser/KFileWriter.h"
#include "parser/DynainWriter.h"
#include "parser/ShellReader.h"
#include "mapper/MeshRemapper.h"
#include "mapper/FlatMeshGenerator.h"
#include "mapper/ShellMapper.h"
#include "example/ExampleMeshGenerator.h"
#include "generator/VariableDensityConfig.h"
#include "generator/YamlConfigReader.h"
#include "generator/VariableDensityMeshGenerator.h"
#include "generator/CurvedMeshGenerator.h"
#include "analysis/StrainCalculator.h"
#include "analysis/ElementAnalyzer.h"
#include "analysis/MaterialModel.h"
#include "cli/ArgumentParser.h"
#include "cli/ConsoleOutput.h"
#include "squeeze/SqueezeConfig.h"
#include "squeeze/SqueezeConfigReader.h"
#include "assembly/AssemblyConfig.h"
#include "assembly/AssemblyConfigReader.h"
#include "assembly/ModelAssembler.h"
#include "util/Logger.h"
#include "util/Timer.h"
#include "util/Validator.h"
#include "commands/kw_util.h"
#include "commands/modal.h"
#include "commands/relax.h"
#include "commands/implicit.h"
#include "commands/database.h"
#include "commands/matdb.h"
#include "commands/contact_defs.h"
#include "commands/contact_helpers.h"
#include "commands/stabilize.h"
#include "commands/ale.h"
#include "commands/optimize.h"
#include "commands/matswap.h"
#include "commands/contact.h"
#include "commands/load_boundary.h"
#include "commands/standalone_ops.h"
#include "commands/core_ops.h"
#include "commands/squeeze_assemble.h"
#include "commands/cnrb2solid.h"
#include "commands/hfdamp.h"
#include "commands/battery.h"
#include "commands/strip.h"
#include "commands/merge.h"
#include "commands/tetremesh.h"
#include "commands/meshfix.h"

#include <iostream>
#include <fstream>
#include <cctype>
#include <cstdio>
#include <system_error>
#include <memory>
#include <limits>
#include <climits>
#include <sstream>
#include <iomanip>
#include <set>
#include <unordered_map>

using namespace KooRemapper;

// Version info
constexpr const char* VERSION = "1.8.0";

/**
 * Display program banner
 */
void printBanner(const ConsoleOutput& console) {
    console.separator('=', 60);
    console.println("  KooRemapper - Mesh Mapping Tool for LS-DYNA", ConsoleOutput::Color::BRIGHT_CYAN);
    console.println("  Version " + std::string(VERSION), ConsoleOutput::Color::CYAN);
    console.separator('=', 60);
    std::cout << "\n";
}

/**
 * Apply the same mirror+swap that MeshRemapper::applyOutputFlip does, but to
 * an arbitrary k-file on disk. Produces a transformed copy at outFile.
 *
 * Why this exists: the map -> prestress YAML chain uses the FLAT mesh as
 * prestress reference and the MAPPED mesh as deformed configuration. When
 * any flip is active, the mapped mesh has odd-parity HEX8 connectivity
 * swapped (n[0..3] <-> n[4..7]) to keep positive Jacobians, so its element-
 * local node order no longer matches the original FLAT reference. Computing
 * F = dx_def/dx_ref then dereferences mismatched physical points and
 * yields garbage strain. The fix: apply the SAME flip+swap to the flat
 * mesh before handing it to runPrestress; both ref and def are then
 * mirrored consistently and strain becomes reflection-invariant
 * (E' = R E R^T, von Mises identical).
 */
static int applyMeshFlipFile(const std::string& inFile,
                              const std::string& outFile,
                              bool fx, bool fy, bool fz,
                              const ConsoleOutput& console) {
    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(inFile);
    } catch (const std::exception& e) {
        console.error(std::string("flip-helper: cannot load ") + inFile + ": " + e.what());
        return 1;
    }
    // negate node coords on selected axes
    for (auto& kv : mesh.nodes) {
        Vector3D p = kv.second.position;
        if (fx) p.x = -p.x;
        if (fy) p.y = -p.y;
        if (fz) p.z = -p.z;
        kv.second.position = p;
        kv.second.setMappedPosition(p);
    }
    // odd-parity flip count flips local handedness; restore by swapping
    // bottom/top face of every HEX8 (matches MeshRemapper::applyOutputFlip).
    int parity = (int)fx + (int)fy + (int)fz;
    if (parity % 2 == 1) {
        for (auto& kv : mesh.elements) {
            Element& e = kv.second;
            if (e.type != ElementType::HEX8) continue;
            std::array<int, 8> orig = e.nodeIds;
            e.nodeIds[0] = orig[4]; e.nodeIds[1] = orig[5];
            e.nodeIds[2] = orig[6]; e.nodeIds[3] = orig[7];
            e.nodeIds[4] = orig[0]; e.nodeIds[5] = orig[1];
            e.nodeIds[6] = orig[2]; e.nodeIds[7] = orig[3];
        }
    }
    KFileWriter writer;
    if (!writer.writeFile(outFile, mesh, /*useMappedPositions=*/false)) {
        console.error(std::string("flip-helper: cannot write ") + outFile +
                      ": " + writer.getErrorMessage());
        return 1;
    }
    return 0;
}


int main(int argc, char* argv[]) {
#ifdef _WIN32
    // Set console output to UTF-8 so Korean/Unicode help text renders correctly
    SetConsoleOutputCP(65001);
    SetConsoleCP(65001);
#endif
    ConsoleOutput console;

    // Check for subcommand
    if (argc < 2) {
        printBanner(console);
        console.println("Usage: KooRemapper <command> [options]");
        std::cout << "\n";
        console.println("Commands:");
        console.println("  map         Map a flat mesh onto a bent reference mesh (HEX8)");
        console.println("  shellmap    Map a flat mesh using a bent shell reference (QUAD4)");
        console.println("  unfold      Generate flat mesh from a bent structured mesh");
        console.println("  generate    Generate example meshes for testing");
        console.println("  generate-var Generate variable density mesh from YAML config");
        console.println("  strain      Calculate strain between two meshes");
        console.println("  prestress   Calculate prestress from deformed configuration");
        console.println("  squeeze     Compress parts for interference fit modeling");
        console.println("  assemble    Assemble model with part replace/squeeze operations");
        console.println("  matswap     Swap material bundle for a part (with HOURGLASS/CURVE/SECTION)");
        console.println("  matdb       Replace materials from JSON database (structural + thermal)");
        console.println("  implicit    Convert explicit K-file to implicit solver settings");
        console.println("  modal       Convert explicit K-file to modal (natural frequency) analysis");
        console.println("  ale         Convert parts to ALE (fluid/gas/explosive) with material presets");
        console.println("  contact     Analyze, create, modify, convert contact definitions");
        console.println("  cnrb2solid  Convert CNRB rigid bolts to solid HEX8 cylinder meshes");
        console.println("  hfdamp      Insert high-frequency damping (*DAMPING_FREQUENCY_RANGE_DEFORM)");
        console.println("  battery     Generate battery cell K-file (stacked/wound, Phase 1+2)");
        console.println("  info        Display information about a mesh file");
        console.println("  help        Show help for a command");
        console.println("  version     Show version information");
        std::cout << "\n";
        console.println("Use 'KooRemapper help <command>' for more information.");
        return 1;
    }

    std::string command = argv[1];

    // Version command
    if (command == "version" || command == "--version" || command == "-v") {
        console.println("KooRemapper version " + std::string(VERSION));
        return 0;
    }

    // Help command
    if (command == "help" || command == "--help" || command == "-h") {
        if (argc > 2) {
            std::string helpCmd = argv[2];
            if (helpCmd == "map") {
                console.println("Usage: KooRemapper map [--single] <bent_mesh> <flat_mesh> <output>");
                std::cout << "\n";
                console.println("Map a flat unstructured mesh onto a bent structured mesh.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  bent_mesh   The bent structured reference mesh (k-file)");
                console.println("  flat_mesh   The flat mesh to be mapped (k-file)");
                console.println("  output      Output file path for the mapped mesh");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --single, -s  Use single-threaded mode (default: parallel)");
                std::cout << "\n";
                console.println("By default, parallel processing is used for faster mapping.");
                console.println("Use --single for debugging or when OpenMP is not available.");
            } else if (helpCmd == "generate") {
                console.println("Usage: KooRemapper generate [options] <type> <output_prefix>");
                console.println("       KooRemapper generate box <config.yaml>");
                std::cout << "\n";
                console.println("Generate example meshes for testing.");
                std::cout << "\n";
                console.println("Sub-commands:");
                console.println("  box <config.yaml>  Generate a box (rectangular solid) mesh from YAML");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  type           Mesh type:");
                console.println("                   teardrop, arc, scurve, helix");
                console.println("                   torus, twist, bendtwist, wave, bulge, taper");
                console.println("                   waterdrop (foldable display)");
                console.println("  output_prefix  Prefix for output files");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --dim-i <n>    Number of elements in I direction (default: 10)");
                console.println("  --dim-j <n>    Number of elements in J direction (default: 5)");
                console.println("  --dim-k <n>    Number of elements in K direction (default: 5)");
                std::cout << "\n";
                console.println("Box YAML parameters:");
                console.println("  output: box.k      # output file path");
                console.println("  lx: 100.0          # length X [mm]");
                console.println("  ly: 20.0           # length Y [mm]");
                console.println("  lz: 5.0            # length Z [mm]");
                console.println("  nx: 10             # elements in X");
                console.println("  ny: 4              # elements in Y");
                console.println("  nz: 1              # elements in Z");
                console.println("  rho: 7.85e-9       # density [t/mm3]");
                console.println("  E: 210000.0        # Young's modulus [MPa]");
                console.println("  nu: 0.3            # Poisson's ratio");
                console.println("  mid: 1             # material ID");
                console.println("  secid: 1           # section ID");
                console.println("  pid: 1             # part ID");
                console.println("  part_title: Box    # part title");
            } else if (helpCmd == "strain") {
                console.println("Usage: KooRemapper strain [options] <ref_mesh> <def_mesh> <output.csv>");
                std::cout << "\n";
                console.println("Calculate strain tensor between reference and deformed meshes.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  ref_mesh   Reference (undeformed) mesh (k-file)");
                console.println("  def_mesh   Deformed mesh (k-file)");
                console.println("  output     Output CSV file for strain data");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --type <t>  Strain type: engineering (default), green, log");
            } else if (helpCmd == "info") {
                console.println("Usage: KooRemapper info <mesh_file>");
                std::cout << "\n";
                console.println("Display information about a mesh file.");
            } else if (helpCmd == "unfold") {
                console.println("Usage: KooRemapper unfold <bent_mesh> <output_flat>");
                std::cout << "\n";
                console.println("Generate a flat (unfolded) mesh from a bent structured mesh.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  bent_mesh    The bent structured mesh (k-file)");
                console.println("  output_flat  Output file path for the flat mesh");
                std::cout << "\n";
                console.println("Description:");
                console.println("  This command analyzes a bent structured HEX8 mesh and");
                console.println("  generates a corresponding flat mesh by:");
                console.println("  1. Computing arc-length along the centerline for X dimension");
                console.println("  2. Preserving cross-section size for Y and Z dimensions");
                std::cout << "\n";
                console.println("  The generated flat mesh can be used as a reference for mapping");
                console.println("  detailed flat meshes back to the bent shape.");
            } else if (helpCmd == "prestress") {
                console.println("Usage: KooRemapper prestress [options] <ref_mesh> <def_mesh> <output>");
                std::cout << "\n";
                console.println("Calculate prestress from reference and deformed mesh configurations.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  ref_mesh   Reference (undeformed) mesh (k-file)");
                console.println("  def_mesh   Deformed mesh (k-file, same topology)");
                console.println("  output     Output file (dynain format or CSV)");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --E <value>      Young's modulus (overrides K-file materials)");
                console.println("  --nu <value>     Poisson's ratio (overrides K-file materials)");
                console.println("  --strain <type>  Strain type: engineering, green (default)");
                console.println("  --csv            Also output strain/stress CSV file");
                std::cout << "\n";
                console.println("Material Properties:");
                console.println("  The tool automatically reads *PART and *MAT_ELASTIC cards from");
                console.println("  the reference K-file. Each element uses its part's material.");
                console.println("  If --E and --nu are specified, they override K-file materials.");
                std::cout << "\n";
                console.println("Description:");
                console.println("  Computes strain tensor from mesh deformation.");
                console.println("  If materials are available (from K-file or command line),");
                console.println("  computes stress using Hooke's law and outputs *INITIAL_STRESS_SOLID");
                console.println("  cards in dynain format.");
            } else if (helpCmd == "generate-var") {
                console.println("Usage: KooRemapper generate-var [options] <config.yaml> <output.k>");
                std::cout << "\n";
                console.println("Generate mesh from YAML configuration (flat or curved).");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  config.yaml  YAML configuration file");
                console.println("  output.k     Output K-file");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --ref <file>   Reference flat mesh for scaling");
                console.println("  --no-scale     Don't scale to reference (use YAML lengths as-is)");
                std::cout << "\n";
                console.println("YAML Format (Flat Variable Density):");
                console.println("  type: flat  # Optional, default is flat");
                console.println("  reference:");
                console.println("    flat_mesh: \"ref_flat.k\"  # Reference for auto-scaling");
                console.println("  elements_j: 50");
                console.println("  elements_k: 10");
                console.println("  variable_density:");
                console.println("    zone1_dense_start:");
                console.println("      length: 10.0");
                console.println("      num_elements: 50");
                console.println("    ...");
                std::cout << "\n";
                console.println("YAML Format (Curved from Centerline):");
                console.println("  type: curved");
                console.println("  reference:");
                console.println("    flat_mesh: \"ref_flat.k\"  # For scaling (optional)");
                console.println("  centerline_points:");
                console.println("    - [0, 0]");
                console.println("    - [50, 0]");
                console.println("    - [100, 50]");
                console.println("    - [150, 50]");
                console.println("  interpolation: catmull_rom  # linear, catmull_rom, bspline");
                console.println("  cross_section:  # Only if no reference");
                console.println("    width: 10.0");
                console.println("    thickness: 2.0");
                console.println("  elements_along_curve: 100");
                console.println("  elements_j: 20");
                console.println("  elements_k: 5");
            } else if (helpCmd == "shellmap") {
                console.println("Usage: KooRemapper shellmap [options] <bent_shell> <flat_detail> <output>");
                std::cout << "\n";
                console.println("Map a flat detail mesh onto a bent QUAD4 shell reference mesh.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  bent_shell   Bent shell reference mesh (QUAD4 elements, k-file)");
                console.println("  flat_detail  Flat detail mesh to be mapped (solid or shell, k-file)");
                console.println("  output       Output file path for the mapped mesh");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --thickness <t>  Shell thickness for Z-offset mapping");
                console.println("                   Default: auto-detect from flat mesh Z-range");
                std::cout << "\n";
                console.println("Description:");
                console.println("  Unlike 'map' (which requires a structured HEX8 reference),");
                console.println("  'shellmap' uses an unstructured QUAD4 shell as reference.");
                console.println("  The shell is unfolded to a flat plane (edge-length preserving),");
                console.println("  then flat detail nodes are mapped onto the bent shell surface.");
                std::cout << "\n";
                console.println("  Best for: developable surfaces (single curvature, e.g. cylinders).");
                console.println("  Non-developable surfaces will show a distortion warning.");
            } else if (helpCmd == "squeeze") {
                console.println("Usage: KooRemapper squeeze <mesh.k> <config.yaml> <output_prefix>");
                std::cout << "\n";
                console.println("Compress parts for interference fit modeling.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  mesh.k         Input mesh with multiple parts (k-file)");
                console.println("  config.yaml    YAML config specifying per-part strain conditions");
                console.println("  output_prefix  Output prefix (generates .k and _dynain.dat)");
                std::cout << "\n";
                console.println("Output:");
                console.println("  <prefix>.k          Compressed mesh with *INCLUDE dynain");
                console.println("  <prefix>_dynain.dat  Reverse prestress (*INITIAL_STRESS_SOLID)");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  parts:");
                console.println("    - pid: 1");
                console.println("      eps_x: 0.0");
                console.println("      eps_y: 0.0");
                console.println("      eps_z: -0.02      # 2% compression in Z");
                console.println("    - pid: 3");
                console.println("      eps_x: -0.01");
                console.println("      eps_y: -0.01");
                console.println("  material:              # Optional (overrides K-file)");
                console.println("    E: 210000.0");
                console.println("    nu: 0.3");
                std::cout << "\n";
                console.println("Description:");
                console.println("  For each specified part:");
                console.println("  1. Computes bounding box center (neutral plane)");
                console.println("  2. Compresses nodes by specified strain relative to center");
                console.println("  3. Generates reverse (tensile) prestress via Hooke's law");
                console.println("  Use with LS-DYNA dynamic relaxation to model interference fits.");
            } else if (helpCmd == "assemble") {
                console.println("Usage: KooRemapper assemble <config.yaml>");
                std::cout << "\n";
                console.println("Assemble a full model with sequential part operations.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  config.yaml  YAML config specifying base model, operations, and material");
                std::cout << "\n";
                console.println("Output:");
                console.println("  <output>.k          Assembled model (all keywords preserved)");
                console.println("  <output>.dynain     Accumulated prestress (*INITIAL_STRESS_SOLID)");
                std::cout << "\n";
                console.println("YAML Top-level Keys:");
                console.println("  base_model: model.k          # Input K-file");
                console.println("  output: result               # Output prefix (no extension)");
                console.println("  dynamic_relaxation: true     # Insert *CONTROL_DYNAMIC_RELAXATION");
                console.println("  dynain_embed: true           # Embed dynain inline (no .dynain file)");
                console.println("  material:");
                console.println("    E: 210000.0                # Global Young's modulus");
                console.println("    nu: 0.3                    # Global Poisson's ratio");
                std::cout << "\n";
                console.println("Operation Types:");
                std::cout << "\n";
                console.println("  replace      Replace part with mapped detail mesh");
                console.println("    target_pid: 3              # Part to replace");
                console.println("    detail_flat: detail.k      # Flat detail mesh");
                console.println("    shell_bent:  ref.k         # Bent QUAD4 shell reference");
                console.println("    prestress: true            # Compute bending prestress");
                std::cout << "\n";
                console.println("  squeeze      Interference fit - compress part nodes");
                console.println("    target_pid: 5");
                console.println("    eps_x: -0.02  eps_y: 0.0  eps_z: 0.0");
                std::cout << "\n";
                console.println("  restack      Extrude/restack layers (solid rebuild)");
                console.println("    source_pid: 2              # Source part to extrude from");
                console.println("    layers:                    # Layer stack definition");
                console.println("      - pid: 10  thickness: 0.3  secid: 1  mid: 1  hgid: 1");
                console.println("      - pid: 11  thickness: 0.5  secid: 2  mid: 2  hgid: 1");
                std::cout << "\n";
                console.println("  bend         Apply bending deformation + prestress");
                console.println("    target_pid: 3");
                console.println("    deflection_file: bend.dat  # Grid deflection data (CSV)");
                console.println("    plane: xy                  # Bending plane (xy/xz/yz)");
                console.println("    thickness: 0.5");
                std::cout << "\n";
                console.println("  indent       Apply indentation/embossing deformation + prestress");
                console.println("    target_pid: 3");
                console.println("    depth: 0.5                 # Indent depth (negative = emboss)");
                console.println("    r1: 2.0  r2: 1.0           # Fillet radii");
                console.println("    center_x: 50.0  center_y: 30.0");
                console.println("    direction: z               # Indent axis (x/y/z)");
                console.println("    thickness: 0.5");
                std::cout << "\n";
                console.println("  formstrain   Compute plastic strain from shell dihedral angles");
                console.println("    target_pid: 3");
                console.println("    shell_thickness: 0.5");
                std::cout << "\n";
                console.println("  refine       Mesh refinement (1:2 or 1:3 subdivision)");
                console.println("    target_pid: 3");
                console.println("    ratio: 2                   # 2 or 3");
                std::cout << "\n";
                console.println("  elform       Change element formulation (ELFORM)");
                console.println("    target_pid: 3");
                console.println("    target_elform: hex20       # tet4/hex8/hex20/tet10/quad8/tria6");
                std::cout << "\n";
                console.println("  disconnect   Decohere conformal mesh (full/czm/mefem)");
                console.println("    target_pid: 3");
                console.println("    mode: czm                  # full / czm / mefem");
                console.println("    cohesive_part_id: 99       # CZM/MEFEM: new cohesive part ID");
                console.println("    failure_strain: 0.1        # CZM: failure strain");
                std::cout << "\n";
                console.println("  iga          Embed FE part in IGA (NURBS) trivariate box");
                console.println("    targets:");
                console.println("      - target_pid: 3");
                console.println("        element_size: 0.6      # NURBS box voxel size");
                console.println("        pr: 1  ps: 1  pt: 1    # Polynomial order");
                console.println("        ir: 0                  # Integration: 0=reduced, 1=full");
                std::cout << "\n";
                console.println("  offset       Extrude surface elements to solid layer(s)");
                console.println("    source_pid: 3");
                console.println("    thickness: 1.0");
                console.println("    offset_direction: +normal  # +normal/-normal/both/+x/-x/+y/-y/+z/-z");
                console.println("    num_layers: 1");
                console.println("    connection_mode: tied      # tied / czm / contact");
                console.println("    use_local_normals: true    # Per-node normal averaging");
                console.println("    swap_all: false            # Region filter: bbox/node_id/element_id");
                std::cout << "\n";
                console.println("  warpage      Apply warpage (out-of-plane deflection) to shell");
                console.println("    dat_file: warp.dat         # Warpage measurement data");
                console.println("    plane: xy                  # Shell plane");
                console.println("    deflection_axis: z");
                console.println("    target_pid: 3");
                std::cout << "\n";
                console.println("  matswap      Replace material bundle (MAT+HG+CURVE+SECTION)");
                console.println("    bundle: rubber.k           # Bundle file with *PARAMETER block");
                console.println("    pid: 1                     # Single PID");
                console.println("    pids: [1, 2, 3]            # Multiple PIDs");
                console.println("    swap_all: true             # All parts in model");
                std::cout << "\n";
                console.println("Examples: see examples/ directory");
                console.println("  examples/offset/   examples/iga/   examples/matswap/");
                console.println("  examples/disconnect/   examples/formstrain/");
            } else if (helpCmd == "matswap") {
                console.println("Usage: KooRemapper matswap <config.yaml>");
                console.println("       KooRemapper matswap <model.k> <bundle.k> <pid> <output.k>");
                std::cout << "\n";
                console.println("Replace material bundle for one or more parts.");
                console.println("Replaces MAT + HOURGLASS + DEFINE_CURVE + SECTION as a complete unit.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: model.k");
                console.println("  output: result.k");
                console.println("  swaps:");
                console.println("    - bundle: rubber.k         # Bundle file (with *PARAMETER block)");
                console.println("      pid: 1                   # Single PID");
                console.println("    - bundle: foam.k");
                console.println("      pids: [2, 3, 5]          # Multiple PIDs");
                console.println("    - bundle: rubber.k");
                console.println("      swap_all: true           # All parts in model");
                std::cout << "\n";
                console.println("Bundle File Format (*.k with *PARAMETER):");
                console.println("  *PARAMETER");
                console.println("  I HGID1            1I LCID1            1");
                console.println("  I MID1             1I SECID1           1");
                console.println("  I PID1             1");
                console.println("  *HOURGLASS_TITLE");
                console.println("  ...   &HGID1 ...");
                console.println("  *DEFINE_CURVE_TITLE");
                console.println("  ...   &LCID1 ...");
                console.println("  *MAT_...");
                console.println("  ... &MID1 ... &LCID1 ...");
                console.println("  *SECTION_SOLID_TITLE");
                console.println("  ...   &SECID1 ...");
                console.println("  *PART");
                console.println("  ...   &PID1   &SECID1   &MID1   ...   &HGID1 ...");
                console.println("  *END");
                std::cout << "\n";
                console.println("Parameter name prefix convention:");
                console.println("  HGID*  -> Hourglass ID  (always new ID = model max + 1)");
                console.println("  LCID*  -> Curve ID      (always new ID = model max + 1)");
                console.println("  SECID* -> Section ID    (always new ID = model max + 1)");
                console.println("  MID*   -> Material ID   (reuse orphan ID if possible)");
                console.println("  PID*   -> Part ID       (skipped - PART card not inserted)");
                std::cout << "\n";
                console.println("Note: Output file has no *PARAMETER block (resolved to numbers).");
                console.println("      Orphaned old MAT/SECTION/HOURGLASS cards are auto-removed.");
                console.println("      Shared cards (used by non-target parts) are preserved.");
                std::cout << "\n";
                console.println("Examples: see examples/matswap/");
            } else if (helpCmd == "relax") {
                console.println("Usage: KooRemapper relax <config.yaml>");
                std::cout << "\n";
                console.println("Set up Dynamic Relaxation for initial stress equilibrium.");
                console.println("Inserts *CONTROL_DYNAMIC_RELAXATION with 5-level preset system.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: wrapped_model.k");
                console.println("  output: relaxed_model.k");
                console.println("  level: 2               # 1(fast)~5(max conservative), default=2");
                console.println("  mode: explicit         # explicit(IDRFLG=1) | implicit(IDRFLG=5), default=explicit");
                console.println("  drterm: 100.0          # DR termination time (0=convergence only)");
                console.println("  endtime: 1.0           # Post-DR analysis endtime (optional)");
                console.println("");
                console.println("  # Overrides (level defaults used if omitted):");
                console.println("  nrcyck:                # Convergence check interval");
                console.println("  drtol:                 # Convergence tolerance");
                console.println("  drfctr:                # Velocity damping factor");
                console.println("  tssfdr:                # DR timestep scale factor");
                console.println("  irelal:                # Auto control (0=off, 1=Papadrakakis)");
                console.println("  edttl:                 # Auto control convergence tolerance");
                console.println("");
                console.println("  d3drlf: true           # DATABASE_BINARY_D3DRLF output (default: true)");
                console.println("  fix_shell_elform: false");
                console.println("  strip: false           # true: only REMOVE DR keywords (no insertion)");
                std::cout << "\n";
                console.println("Level Presets:");
                console.println("  Lv  Name   NRCYCK  DRTOL    DRFCTR   TSSFDR  IRELAL  EDTTL");
                console.println("  --  -----  ------  -------  -------  ------  ------  ------");
                console.println("   1  빠름     500    0.010    0.990    0.95    0       0.04");
                console.println("   2  표준     250    0.001    0.995    0.90    0       0.04");
                console.println("   3  안정     100    0.001    0.998    0.80    0       0.04");
                console.println("   4  보수      50    0.0001   0.999    0.67    1       0.01");
                console.println("   5  최대      25    0.00001  0.999    0.50    1       0.001");
                std::cout << "\n";
                console.println("Examples: see examples/wrap/relax_test.yaml");

            } else if (helpCmd == "explicit") {
                console.println("Usage: KooRemapper explicit <config.yaml>");
                std::cout << "\n";
                console.println("Revert a K-file to pure explicit by stripping implicit/DR/modal keywords.");
                console.println("Removes *CONTROL_IMPLICIT_*, *CONTROL_DYNAMIC_RELAXATION, *DATABASE_BINARY_D3DRLF,");
                console.println("and SIDR=1 load curves.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: implicit_model.k");
                console.println("  output: explicit_model.k");
                console.println("  keep_dr_curves: false    # true: keep SIDR=1 DEFINE_CURVEs (default: remove)");
                std::cout << "\n";
                console.println("Note: implicit/modal/relax commands also support 'strip: true' for");
                console.println("removing only their specific keywords without adding new ones.");

            } else if (helpCmd == "implicit") {
                console.println("Usage: KooRemapper implicit <config.yaml>");
                std::cout << "\n";
                console.println("Convert an explicit LS-DYNA K-file to implicit solver settings.");
                console.println("Removes explicit-only cards and inserts CONTROL_IMPLICIT_* blocks.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: explicit.k");
                console.println("  output: implicit.k");
                console.println("  mode: static           # static(IMASS=0) | dynamic(IMASS=1), default=static");
                console.println("  level: 2               # 1(aggressive)~7(max stability), default=2");
                console.println("  endtime: 1.0           # optional: update *CONTROL_TERMINATION + DT base");
                console.println("");
                console.println("  # Fine-grained overrides (level defaults used if omitted):");
                console.println("  dctol:                 # Displacement convergence tolerance");
                console.println("  ectol:                 # Energy convergence tolerance");
                console.println("  dt0:                   # Initial timestep");
                console.println("  dtmax:                 # Maximum timestep");
                console.println("  nsolvr:                # Nonlinear solver (12=BFGS, -2=BFGS+line search)");
                console.println("  kfail:                 # Step cuts before stiffness reform (0=none)");
                console.println("  rctol:                 # Residual force tolerance (1e10=disabled default)");
                console.println("  lsolvr:                # Linear solver (7=default sparse, 30=MUMPS)");
                console.println("  stab: false            # *CONTROL_IMPLICIT_STABILIZATION on/off override");
                console.println("  stab_scale: 1.0        # Stabilization SCALE factor (smaller=more stabilization)");
                console.println("  arc_length: false      # Arc-length method on/off (auto-sets NSOLVR=7 if needed)");
                console.println("");
                console.println("  # Cleanup options:");
                console.println("  fix_shell_elform: false  # true: ELFORM=16->2 auto-fix (default: warn only)");
                console.println("  keep_dr_curves: false    # true: keep SIDR=1 DEFINE_CURVEs (default: remove)");
                console.println("  strip: false             # true: only REMOVE *CONTROL_IMPLICIT_* (no insertion)");
                std::cout << "\n";
                console.println("Level Spectrum --- Table 1: Nonlinear solver & convergence tolerances");
                console.println("  Lv  Name           NSOLVR  ILIM  MXREF  ITOPT  KFAIL   DCTOL   ECTOL   LSTOL   RCTOL");
                console.println("  --  -------------  ------  ----  -----  -----  -----  ------  ------  ------  ------");
                console.println("   1  공격적           12     11    10     11      0    0.0050  0.0500  0.90    (off)");
                console.println("   2  표준             12     11    15     11      0    0.0010  0.0100  0.90    (off)");
                console.println("   3  안정             12     15    20     11      0    0.0010  0.0100  0.95    (off)");
                console.println("   4  수렴우선         -2     20    25     11      3    0.0010  0.0100  0.95    (off)");
                console.println("   5  강건             -2     25    30     15      5    0.0010  0.0050  0.99    (off)");
                console.println("   6  고강건           -2     30    40     15      8    0.0005  0.0020  0.99    0.1");
                console.println("   7  최대안정         -2     40    50     20     15    0.0001  0.0010  0.99    0.01");
                console.println("   8  좌굴/스냅스루     7*     40    50     20     15    0.0001  0.0010  0.99    0.01");
                console.println("  * NSOLVR=7 (Full Newton): arc-length requires NSOLVR in [6..9]");
                console.println("  ILIM=ILIMIT, MXREF=MAXREF, ITOPT=ITEOPT, RCTOL off = 1E+10 (disabled)");
                std::cout << "\n";
                console.println("Level Spectrum --- Table 2: Time stepping & activated features");
                console.println("  Lv  DT0         DTMAX       DTMIN         LSOLVR        STAB    ARC-LEN");
                console.println("  --  ----------  ----------  ------------  ------------  ------  -------");
                console.println("   1  T/100       T/20        -T/1000       7 (default)   off     off");
                console.println("   2  T/500       T/100       -T/10000      7 (default)   off     off");
                console.println("   3  T/1000      T/200       -T/10000      7 (default)   off     off");
                console.println("   4  T/2000      T/500       -T/100000     7 (default)   off     off");
                console.println("   5  T/5000      T/1000      -T/100000     7 (default)   ON      off");
                console.println("   6  T/10000     T/2000      -T/100000     30 (MUMPS)    ON      off");
                console.println("   7  T/50000     T/10000     -T/1000000    30 (MUMPS)    ON      off");
                console.println("   8  T/50000     T/10000     -T/1000000    30 (MUMPS)    ON      ON(Crisfield)");
                std::cout << "\n";
                console.println("Feature notes:");
                console.println("  KFAIL     : reform tangent stiffness after N consecutive step bisections");
                console.println("  LSTOL     : line search convergence tolerance (NSOLVR=-2 only)");
                console.println("  RCTOL     : residual force norm tolerance (off=1e10; try 0.1 to activate)");
                console.println("  STAB(IAS) : *CONTROL_IMPLICIT_STABILIZATION IAS=1 - artificial stiffness");
                console.println("              prevents singular K from rigid body modes / springback unloading");
                console.println("  MUMPS(30) : *CONTROL_IMPLICIT_SOLVER LSOLVR=30 - parallel direct solver");
                console.println("              more robust for ill-conditioned/contact-heavy stiffness matrices");
                console.println("  ARC-LEN   : *CONTROL_IMPLICIT_SOLUTION Card3 - Crisfield arc-length method");
                console.println("              ARCCTL=0(generalized), ARCMTH=1(Crisfield), ARCDMP=2(off)");
                console.println("              use when load-displacement path has negative slope (snap-through)");
                std::cout << "\n";
                console.println("Removed cards:");
                console.println("  *CONTROL_DYNAMIC_RELAXATION  (always)");
                console.println("  *CONTROL_BULK_VISCOSITY       (always)");
                console.println("  *DATABASE_BINARY_D3DRLF       (always)");
                console.println("  *DEFINE_CURVE with SIDR=1     (unless keep_dr_curves: true)");
                std::cout << "\n";
                console.println("Inserted cards (always):");
                console.println("  *CONTROL_IMPLICIT_GENERAL / DYNAMICS / SOLUTION / AUTO");
                console.println("Inserted cards (level 5+):");
                console.println("  *CONTROL_IMPLICIT_STABILIZATION");
                console.println("Inserted cards (level 6+):");
                console.println("  *CONTROL_IMPLICIT_SOLVER (MUMPS)");
                console.println("Inserted cards (level 8 / arc_length:true):");
                console.println("  *CONTROL_IMPLICIT_SOLUTION Card 3 (arc-length parameters)");
                std::cout << "\n";
                console.println("Mode: static vs dynamic");
                console.println("  static   IMASS=0, GAMMA=0.5, BETA=0.25  (quasi-static loading)");
                console.println("  dynamic  IMASS=1, GAMMA=0.6, BETA=0.30  (structural dynamics, num. damping)");
            } else if (helpCmd == "modal") {
                console.println("Usage: KooRemapper modal <config.yaml>");
                std::cout << "\n";
                console.println("Convert an explicit LS-DYNA K-file for natural frequency (modal) analysis.");
                console.println("Removes explicit-only cards and inserts *CONTROL_IMPLICIT_EIGENVALUE.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: explicit.k          # Input explicit K-file");
                console.println("  output: modal.k            # Output file");
                console.println("");
                console.println("  # Key parameters (all have defaults):");
                console.println("  nmode:  10                 # Number of modes to extract (default: 10)");
                console.println("  fmin:   0.0                # Lower frequency bound Hz (default: 0 = no limit)");
                console.println("  fmax:   2000.0             # Upper frequency bound Hz (default: 0 = no limit)");
                console.println("");
                console.println("  # Advanced (optional):");
                console.println("  center: 0.0                # Frequency shift center Hz (default: 0.0)");
                console.println("  eigmth: 2                  # Eigensolver method (see below)");
                console.println("  solver: 7                  # Linear solver (7=default sparse, 30=MUMPS)");
                console.println("  fix_shell_elform: false    # true: ELFORM=16->2 auto-fix (default: warn)");
                console.println("  keep_dr_curves:  false     # true: keep SIDR=1 DEFINE_CURVEs (default: remove)");
                console.println("  strip: false               # true: only REMOVE modal keywords (no insertion)");
                std::cout << "\n";
                console.println("Eigenvalue method (eigmth):");
                console.println("  2   Block Shift Lanczos   -- general purpose (default)");
                console.println("  101 MCMS                  -- NVH, thousands of modes");
                console.println("  102 LOBPCG                -- large models, iterative");
                console.println("  103 Fast Lanczos          -- MPP parallel");
                std::cout << "\n";
                console.println("Frequency limits:");
                console.println("  fmin=0 (default) -> LFLAG=0 (no lower bound, searches from -inf)");
                console.println("  fmin>0           -> LFLAG=1, LFTEND=fmin Hz");
                console.println("  fmax=0 (default) -> RFLAG=0 (no upper bound)");
                console.println("  fmax>0           -> RFLAG=1, RHTEND=fmax Hz");
                std::cout << "\n";
                console.println("Output files (automatic, no DATABASE card needed):");
                console.println("  eigout   ASCII frequency list (natural frequencies in Hz)");
                console.println("  d3eigv   Binary mode shapes (view in LS-PrePost)");
                std::cout << "\n";
                console.println("Removed cards:");
                console.println("  *CONTROL_DYNAMIC_RELAXATION  (always)");
                console.println("  *CONTROL_BULK_VISCOSITY       (always)");
                console.println("  *DATABASE_BINARY_D3DRLF       (always)");
                console.println("  *DEFINE_CURVE with SIDR=1     (unless keep_dr_curves: true)");
                std::cout << "\n";
                console.println("Inserted cards:");
                console.println("  *CONTROL_IMPLICIT_GENERAL   (IMFLAG=1, DT0=1.0, IMFORM=2, IGS=2)");
                console.println("  *CONTROL_IMPLICIT_EIGENVALUE (NEIG, LFLAG/RFLAG, EIGMTH)");
                console.println("  *CONTROL_IMPLICIT_SOLUTION  (NSOLVR=12, standard tolerances)");
                console.println("  *CONTROL_IMPLICIT_SOLVER    (only when solver: 30)");
                std::cout << "\n";
                console.println("Examples: see examples/modal/");
            } else if (helpCmd == "ale") {
                console.println("Usage: KooRemapper ale <config.yaml>");
                std::cout << "\n";
                console.println("Convert parts to ALE (Arbitrary Lagrangian-Eulerian) with material presets.");
                console.println("Changes ELFORM, inserts CONTROL_ALE, AMMG, material cards, and FSI coupling.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model:   explicit.k");
                console.println("  output:  ale.k");
                console.println("");
                console.println("  ale_parts:                  # Parts to convert (required)");
                console.println("    - pid: 3");
                console.println("      material: air           # Preset name or custom .k bundle path");
                console.println("    - pid: 4");
                console.println("      material: water");
                console.println("");
                console.println("  fsi_pids: [1, 2]            # Lagrangian parts for FSI coupling (optional)");
                console.println("  elform: 11                  # ALE ELFORM (11=multi-mat, 12=single, default: 11)");
                console.println("");
                console.println("  # *CONTROL_ALE options (optional):");
                console.println("  dct:  1       # Advection logic (1=default, -1=improved)");
                console.println("  nadv: 1       # Advection cycles (default: 1)");
                console.println("  meth: 2       # Advection method (2=Van Leer, default)");
                console.println("");
                console.println("  # FSI options (*CONSTRAINED_LAGRANGE_IN_SOLID, optional):");
                console.println("  ctype: 2      # Coupling type (2=accel+vel, default)");
                console.println("  pfac:  0.1    # Penalty factor");
                console.println("");
                console.println("  # Detonation point (for he/c4 presets, optional):");
                console.println("  detonation:");
                console.println("    pid: 5");
                console.println("    x: 100.0");
                console.println("    y: 50.0");
                console.println("    z: 0.0");
                console.println("    lt: 0.0     # Detonation time");
                std::cout << "\n";
                console.println("Material presets (unit: t/mm/s -> MPa):");
                console.println("  Gas (MAT_NULL + EOS_LINEAR_POLYNOMIAL):");
                console.println("    air        rho=1.293e-12  gamma=1.40");
                console.println("    nitrogen   rho=1.165e-12  gamma=1.40");
                console.println("    argon      rho=1.661e-12  gamma=1.67");
                console.println("  Liquid (MAT_NULL + EOS_GRUNEISEN):");
                console.println("    water       rho=1.00e-9   C=1484   S1=1.979");
                console.println("    electrolyte rho=1.18e-9   C=1200   S1=1.58   (battery)");
                console.println("    gasoline    rho=7.50e-10  C=1250   S1=1.60   (fuel tank)");
                console.println("    oil         rho=8.70e-10  C=1350   S1=1.80   (hydraulic)");
                console.println("    coolant     rho=1.08e-9   C=1600   S1=1.85   (50% EG)");
                console.println("    resin       rho=1.15e-9   C=1700   S1=1.70   MU=1e-5 (epoxy)");
                console.println("    tim         rho=2.80e-9   C=1800   S1=1.60   MU=5e-4 (gap filler)");
                console.println("    silicone    rho=1.05e-9   C=1050   S1=1.50   MU=1e-4 (gel/oil)");
                console.println("  Explosive (MAT_HIGH_EXPLOSIVE_BURN + EOS_JWL):");
                console.println("    tnt        rho=1.63e-9  D=6.93e6  PCJ=21000");
                console.println("    c4         rho=1.60e-9  D=8.19e6  PCJ=28000");
                console.println("  Special:");
                console.println("    vacuum     MAT_VACUUM (rho~1e-18, void filler)");
                std::cout << "\n";
                console.println("Auto-inserted cards:");
                console.println("  *SECTION_SOLID     ELFORM modified (or new section if shared)");
                console.println("  *MAT_* + *EOS_*    Per-part material replacement");
                console.println("  *HOURGLASS         IHQ=3 Flanagan-Belytschko for ALE");
                console.println("  *CONTROL_ALE       Advection control");
                console.println("  *ALE_MULTI-MATERIAL_GROUP    Material group definition");
                console.println("  *ALE_REFERENCE_SYSTEM_GROUP  Mesh smoothing (PRTYPE=4)");
                console.println("  *CONSTRAINED_LAGRANGE_IN_SOLID  FSI coupling (if fsi_pids)");
                console.println("  *INITIAL_DETONATION             Detonation point (if he/c4)");
                std::cout << "\n";
                console.println("Examples: see examples/ale/");
            } else if (helpCmd == "optimize") {
                console.println("Usage: KooRemapper optimize <config.yaml>");
                std::cout << "\n";
                console.println("Apply material-specific global card optimization.");
                console.println("Can also be used with 'optimize: rubber' inside matswap YAML.");
                std::cout << "\n";
                console.println("Standalone YAML Format:");
                console.println("  model: model.k");
                console.println("  output: optimized.k");
                console.println("  optimize: rubber              # optimization mode");
                console.println("  pids: [3, 5]                  # target PIDs (for contact scope)");
                console.println("  tssfac: 0.67                  # optional, default 0.67");
                std::cout << "\n";
                console.println("Matswap Integration:");
                console.println("  model: model.k");
                console.println("  output: result.k");
                console.println("  swaps:");
                console.println("    - bundle: rubber.k");
                console.println("      pid: 3");
                console.println("  optimize: rubber              # applied after matswap");
                console.println("  tssfac: 0.67                  # optional");
                std::cout << "\n";
                console.println("Rubber Mode Actions:");
                console.println("  Forced modify + notice:");
                console.println("    *CONTROL_ACCURACY    INN=4 (invariant node numbering)");
                console.println("    *CONTROL_ENERGY      HGEN=2,RWEN=2,SLNTEN=2,RYLEN=2");
                console.println("    *CONTROL_TIMESTEP    TSSFAC (default 0.67)");
                console.println("    *CONTACT_*           SOFT=0, SBOPT=2.0 (for target PIDs)");
                std::cout << "\n";
                console.println("  Warning only:");
                console.println("    *CONTROL_TIMESTEP         DT2MS != 0 warning");
                console.println("    *CONTROL_BULK_VISCOSITY   Q1/Q2 deviation warning");
            } else if (helpCmd == "stabilize") {
                console.println("Usage: KooRemapper stabilize <config.yaml>");
                std::cout << "\n";
                console.println("Apply explicit solver stabilization measures (12-level cumulative system).");
                console.println("Each level includes all measures from lower levels.");
                std::cout << "\n";
                console.println("YAML Format (level preset):");
                console.println("  model:     model.k");
                console.println("  output:    stabilized.k");
                console.println("  stabilize: explicit");
                console.println("  level:     6           # preset level 1-12");
                std::cout << "\n";
                console.println("YAML Format (manual — set specific options):");
                console.println("  model:     model.k");
                console.println("  output:    stabilized.k");
                console.println("  stabilize: explicit");
                console.println("  tssfac:    0.80        # *CONTROL_TIMESTEP TSSFAC");
                console.println("  ihq:       4           # *CONTROL_HOURGLASS type");
                console.println("  soft:      1           # *CONTACT_* Card A SOFT");
                std::cout << "\n";
                console.println("Level Presets:");
                console.println("  Lv 1  Energy diagnostics: HGEN=RWEN=SLNTEN=RYLEN=2");
                console.println("  Lv 2  Accuracy: OSU=1, INN=4, ESORT=1 (solid+shell)");
                console.println("  Lv 3  Time step 1: TSSFAC=0.80");
                console.println("  Lv 4  Hourglass stiffness: IHQ=4, QH=0.10");
                console.println("  Lv 5  Shell stabilization: BWC=1, MITER=2, IRNXX=-2, WRPANG=10");
                console.println("          (auto-skipped if no *ELEMENT_SHELL in model)");
                console.println("  Lv 6  Contact stage 1: ORIEN=2, SHLTHK=1, XPENE=2, ISLCHK=2");
                console.println("          per-contact: SOFT=1, SBOPT=2, DEPTH=3");
                console.println("  Lv 7  Time step 2: TSSFAC=0.67 + BULK Q1=1.5, Q2=0.06 (forced)");
                console.println("  Lv 8  Contact stage 2 (pinball): SOFT=2, SBOPT=3, DEPTH=5");
                console.println("          SHLTHK=2, NSBCS=5, ENMASS=1, IGNORE=1, MAXPAR=1.15");
                console.println("  Lv 9  Best hourglass: IHQ=6 (Belytschko-Bindeman), QH=1.0");
                console.println("  Lv10  Time step 3: TSSFAC=0.60, NSBCS=2");
                console.println("  Lv11  Erosion: ERODE=11, ENMASS=2, NSBCS=1, TSSFAC=0.55");
                console.println("          (requires confirm_erosion: true or interactive y/N prompt)");
                console.println("  Lv12  Maximum conservative: TSSFAC=0.50, Q1=2.0, Q2=0.10");
                std::cout << "\n";
                console.println("All YAML options (manual mode):");
                console.println("  tssfac esort_solid esort_shell osu inn ihq qh");
                console.println("  bwc miter irnxx wrpang");
                console.println("  orien shlthk xpene islchk enmass nsbcs");
                console.println("  soft sbopt depth maxpar ignore");
                console.println("  bulk_q1 bulk_q2 erode confirm_erosion");
                console.println("  hgen rwen slnten rylen");
                std::cout << "\n";
                console.println("Examples: see examples/explicit/");
            } else if (helpCmd == "contact") {
                console.println("Usage: KooRemapper contact <config.yaml>");
                std::cout << "\n";
                console.println("Analyze, create, modify, convert, remove, or detect contact definitions.");
                console.println("Manages *CONTACT_*, *SET_SEGMENT, *SET_PART, *SET_NODE keywords.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model:  model.k");
                console.println("  output: model_contact.k      # optional for analyze-only");
                console.println("");
                console.println("  contacts:");
                console.println("    # Analyze (report only, no modification)");
                console.println("    - action: analyze");
                console.println("");
                console.println("    # Create: part ID direct (SSTYP=3)");
                console.println("    - action: create");
                console.println("      type: automatic_surface_to_surface");
                console.println("      slave:  { pid: 1 }");
                console.println("      master: { pid: 2 }");
                console.println("      friction: 0.3");
                console.println("      soft: 2");
                console.println("      title: Case_to_Board");
                console.println("");
                console.println("    # Create: multiple PIDs -> auto SET_PART (SSTYP=2)");
                console.println("    - action: create");
                console.println("      type: automatic_surface_to_surface");
                console.println("      slave:  { pids: [1, 2, 3] }");
                console.println("      master: { pids: [4, 5] }");
                console.println("");
                console.println("    # Create: extract surface segments (SSTYP=0)");
                console.println("    - action: create");
                console.println("      type: automatic_surface_to_surface");
                console.println("      slave:  { pid: 1, as_segment: true }");
                console.println("      master: { pid: 2, as_segment: true }");
                console.println("");
                console.println("    # Create: single surface self-contact");
                console.println("    - action: create");
                console.println("      type: automatic_single_surface");
                console.println("      slave:  { pids: [1, 2, 3, 4] }");
                console.println("      soft: 2");
                console.println("");
                console.println("    # Convert: part -> segment (extract outer surface)");
                console.println("    - action: convert");
                console.println("      contact_index: 0          # from analyze report");
                console.println("      slave_to: segment");
                console.println("      master_to: segment");
                console.println("");
                console.println("    # Modify: change friction / SOFT");
                console.println("    - action: modify");
                console.println("      contact_index: 0");
                console.println("      friction: 0.5");
                console.println("      soft: 2");
                console.println("");
                console.println("    # Remove a contact definition");
                console.println("    - action: remove");
                console.println("      contact_index: 0");
                console.println("");
                console.println("    # Detect: auto-find contacting segments between two PIDs");
                console.println("    - action: detect");
                console.println("      slave:  { pid: 1 }");
                console.println("      master: { pid: 2 }");
                console.println("      tolerance: 0.1");
                console.println("      auto_create: true");
                console.println("      contact_type: auto         # auto/tied/mortar/tied_mortar/single/eroding/forming");
                console.println("");
                console.println("    # Detect: all parts (scope: all)");
                console.println("    - action: detect");
                console.println("      scope: all");
                console.println("      exclude: [rigid, null]");
                console.println("      tolerance: 0.1");
                console.println("      auto_create: true");
                console.println("");
                console.println("    # Detect: keyword-based part selection");
                console.println("    - action: detect");
                console.println("      include: [bolt, plate]");
                console.println("      exclude: [rigid]");
                console.println("      tolerance: 0.05");
                console.println("      auto_create: true");
                console.println("      contact_type: tied");
                std::cout << "\n";
                console.println("SSTYP/MSTYP values:");
                console.println("  0  Segment set (*SET_SEGMENT)");
                console.println("  1  Shell element set (*SET_SHELL)");
                console.println("  2  Part set (*SET_PART)");
                console.println("  3  Part ID (direct)");
                console.println("  4  Node set (*SET_NODE)");
                console.println("  5  All parts (entire model)");
                std::cout << "\n";
                console.println("Workflow:");
                console.println("  1. Run with 'analyze' action to see contacts and indices");
                console.println("  2. Use contact_index from report for convert/modify/remove");
                console.println("  3. Multiple actions processed in order");
            } else if (helpCmd == "database") {
                console.println("Usage: KooRemapper database <config.yaml>");
                std::cout << "\n";
                console.println("Insert *DATABASE_* output control keywords into a K-file.");
                console.println("Uses presets for common analysis types or individual keyword toggles.");
                console.println("Existing keywords are detected and skipped automatically.");
                std::cout << "\n";
                console.println("YAML Format (preset):");
                console.println("  model:  model.k");
                console.println("  output: model_db.k");
                console.println("  preset: all            # all/drop/crash/static/thermal/forming/modal/minimal");
                console.println("  dt:     0.001          # global ASCII output interval (default 0.001)");
                console.println("  dt_plot: 0.01          # D3PLOT interval (default 0.01)");
                std::cout << "\n";
                console.println("YAML Format (custom):");
                console.println("  model:  model.k");
                console.println("  output: model_db.k");
                console.println("  ascii:");
                console.println("    glstat: true");
                console.println("    matsum: true");
                console.println("    nodout: true");
                console.println("    rcforc: true");
                console.println("  binary:");
                console.println("    d3plot: true");
                console.println("    d3thdt: true");
                console.println("  extent:");
                console.println("    neiph: 6             # extra integration point history vars");
                console.println("    strflg: 1            # strain tensor output");
                console.println("    sigflg: 1            # stress tensor output");
                console.println("    epsflg: 1            # effective plastic strain output");
                std::cout << "\n";
                console.println("Presets:");
                console.println("  all      All 20 ASCII + D3PLOT/D3THDT/D3DUMP (comprehensive)");
                console.println("  drop     glstat matsum rcforc nodout elout sleout jntforc d3plot");
                console.println("  crash    glstat matsum rcforc sleout spcforc rwforc abstat d3plot d3thdt");
                console.println("  static   glstat matsum nodout elout spcforc bndout d3plot");
                console.println("  thermal  glstat matsum nodout elout tprint d3plot d3thdt");
                console.println("  forming  glstat matsum rcforc sleout rwforc swforc d3plot");
                console.println("  modal    glstat matsum nodout elout d3plot");
                console.println("  minimal  glstat matsum d3plot");
                std::cout << "\n";
                console.println("ASCII keywords: glstat matsum nodout elout rcforc sleout spcforc");
                console.println("  nodfor rwforc secforc jntforc bndout abstat swforc ssstat");
                console.println("  deforc disbout ncforc tprint massout");
                console.println("Binary keywords: d3plot d3thdt d3dump runrsf intfor d3drlf");
            } else if (helpCmd == "update") {
                console.println("Usage: KooRemapper update <config.yaml>");
                std::cout << "\n";
                console.println("Update node coordinates from a dynain or K-file.");
                console.println("Reads *NODE block from the source file and overwrites matching");
                console.println("node positions in the model. Unmatched nodes are left unchanged.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model:  original.k");
                console.println("  output: updated.k");
                console.println("  dynain: dr_result.dynain   # Any file with *NODE block");
                std::cout << "\n";
                console.println("Assemble operation:");
                console.println("  - type: update");
                console.println("    dynain: dr_result.dynain");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  - Only nodes present in both model and dynain are updated");
                console.println("  - Nodes in dynain but not in model are silently skipped");
                console.println("  - Works with any file containing *NODE (dynain, K-file, etc.)");
                console.println("  - Can be chained with other assemble operations");
            } else if (helpCmd == "iga") {
                console.println("Usage: KooRemapper iga <config.yaml>");
                std::cout << "\n";
                console.println("Embed FE parts in IGA (Isogeometric Analysis) NURBS trivariate box.");
                console.println("Generates *IGA_DEV_VOLUME_XYZ patch wrapping each target FE part.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: model.k");
                console.println("  output: result");
                console.println("  operations:");
                console.println("    - type: iga");
                console.println("      targets:");
                console.println("        - target_pid: 1        # Single part");
                console.println("          element_size: 4.0    # NURBS box resolution");
                console.println("          ir: 0                # Integration type (0=Gauss)");
                console.println("          pr: 2                # Polynomial degree r (min 1)");
                console.println("          ps: 2                # Polynomial degree s");
                console.println("          pt: 1                # Polynomial degree t");
                console.println("          bbox_scale: 1.4      # Bounding box expansion factor");
                console.println("        - target_pids: [2, 3]  # Multiple parts same settings");
                console.println("          element_size: 3.0");
                std::cout << "\n";
                console.println("Output:");
                console.println("  <output>.k             Main file with *INCLUDE for each IGA part");
                console.println("  <output>_iga_p<N>.k    Per-part IGA keyword file");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  - Control points per direction = max(2, pr+1)");
                console.println("  - IGA and FE parts use separate MID (LS-DYNA requirement)");
                console.println("  - Requires LS-DYNA R12 or later");
                console.println("  - See examples/iga/iga_guide.md for full documentation");
            } else if (helpCmd == "matdb") {
                console.println("Usage: KooRemapper matdb <config.yaml>");
                std::cout << "\n";
                console.println("Replace *MAT cards from a JSON material database.");
                console.println("Supports structural and thermal material insertion.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: model.k");
                console.println("  output: result.k");
                console.println("  database: materials/material_db.json");
                console.println("  mat_type: MAT_ELASTIC       # Default structural card type");
                console.println("  thermal: false               # Insert thermal cards by default");
                console.println("  materials:");
                console.println("    - match: \"steel\"          # Match by title substring");
                console.println("      mat_type: MAT_024        # Override per-material");
                console.println("      thermal: true");
                console.println("    - mid: 3                   # Match by MID directly");
                console.println("      match: \"rubber\"");
                console.println("    - match: \"*\"              # Catch-all auto-match");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  - DB path: materials/material_db.json (relative to exe)");
                console.println("  - Match: title->name/tag substring, case-insensitive");
                console.println("  - Thermal inserts: *MAT_THERMAL_ISOTROPIC + *MAT_ADD_THERMAL_EXPANSION");
            } else if (helpCmd == "load") {
                console.println("Usage: KooRemapper load <config.yaml>");
                std::cout << "\n";
                console.println("Apply loads (force/pressure/gravity) to parts from YAML config.");
                console.println("Inserts *LOAD_*, *DEFINE_CURVE, *SET_* keywords.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: mesh.k");
                console.println("  output: mesh_loaded.k");
                console.println("  loads:");
                console.println("    - part: 1");
                console.println("      mode: pressure          # pressure | force | gravity");
                console.println("      value: 1.0              # Load magnitude");
                console.println("      direction: [0, 0, 1]    # Load direction vector");
                console.println("      select: direction        # direction | tied | all");
                console.println("      angle: 45.0             # Face selection angle tolerance");
                console.println("      curve:                   # Optional time-load curve");
                console.println("        - [0.0, 0.0]");
                console.println("        - [0.001, 1.0]");
                console.println("        - [0.01, 1.0]");
                std::cout << "\n";
                console.println("Select modes:");
                console.println("  direction  Face normals within angle of direction vector");
                console.println("  tied       Faces participating in tied contact");
                console.println("  all        All exposed faces of the part");
            } else if (helpCmd == "boundary") {
                console.println("Usage: KooRemapper boundary <config.yaml>");
                std::cout << "\n";
                console.println("Apply boundary conditions (SPC/rigid wall) from YAML config.");
                console.println("Inserts *BOUNDARY_SPC_NODE, *RIGIDWALL_PLANAR keywords.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: mesh.k");
                console.println("  output: mesh_bc.k");
                console.println("  boundaries:");
                console.println("    - part: 9");
                console.println("      dof: all                 # all | x | y | z | xy | xz | yz");
                console.println("      direction: [0, 0, -1]    # Face selection direction");
                console.println("      select: direction         # direction | all");
                console.println("      angle: 45.0              # Face selection angle tolerance");
                std::cout << "\n";
                console.println("DOF options:");
                console.println("  all  Fix all 6 DOF (tx,ty,tz,rx,ry,rz)");
                console.println("  x/y/z  Fix single translational DOF");
                console.println("  xy/xz/yz  Fix two translational DOFs");
            } else if (helpCmd == "rbe") {
                console.println("Usage: KooRemapper rbe <config.yaml>");
                std::cout << "\n";
                console.println("Create RBE2/RBE3 rigid body element constraints from YAML config.");
                console.println("Inserts *CONSTRAINED_NODAL_RIGID_BODY or *CONSTRAINED_INTERPOLATION.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: mesh.k");
                console.println("  output: mesh_rbe.k");
                console.println("  rbe:");
                console.println("    - part: 9");
                console.println("      select: direction        # direction | all");
                console.println("      direction: [0, 0, -1]");
                console.println("      angle: 45.0");
                console.println("      type: rbe3               # rbe2 | rbe3");
                console.println("      mode: spider             # spider (one centroid master node)");
                std::cout << "\n";
                console.println("Types:");
                console.println("  rbe2  Rigid: slave nodes move exactly with master");
                console.println("  rbe3  Interpolation: master motion is weighted average of slaves");
            } else if (helpCmd == "restack") {
                console.println("Usage: KooRemapper restack <config.yaml>");
                std::cout << "\n";
                console.println("Extrude shell surface into stacked solid layers.");
                console.println("Used in assemble pipeline for multi-layer solid stacks.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: shell.k");
                console.println("  output: solid_stack");
                console.println("  operations:");
                console.println("    - type: restack");
                console.println("      target_pid: 1            # Source shell part ID");
                console.println("      direction: +z            # Extrusion direction");
                console.println("      element_type: solid      # solid | tshell");
                console.println("      layers:");
                console.println("        - thickness: 0.5");
                console.println("          material_card: |");
                console.println("            *MAT_ELASTIC");
                console.println("            $#  mid   ro    e   pr");
                console.println("                 10  2.0 1000 0.35");
                console.println("        - thickness: 0.2");
                console.println("          material_card: |");
                console.println("            *MAT_ELASTIC");
                console.println("            ...");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  - Each layer gets a new PID/MID automatically");
                console.println("  - disconnect op can follow restack for CZM/Peri separation");
                console.println("  - See examples/assemble_display/restack_guide.md for full docs");
            } else if (helpCmd == "bend") {
                console.println("Usage: KooRemapper bend <config.yaml>");
                std::cout << "\n";
                console.println("Apply bending deformation and optional prestress to a part.");
                console.println("Supports formula-based or dat-file curvature input.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: flat.k");
                console.println("  output: bent");
                console.println("  operations:");
                console.println("    - type: bend");
                console.println("      target_pid: 1");
                console.println("      plane: xz               # Bending plane: xy | xz | yz");
                console.println("      mode: formula            # formula | dat");
                console.println("      expression: \"0.001*x1\" # Deflection w(x1) formula");
                console.println("      # dat mode:");
                console.println("      # source: dat_file");
                console.println("      # dat_file: warpage.dat");
                console.println("      # dat_top: top");
                console.println("      # dat_bottom: bottom");
                std::cout << "\n";
                console.println("Formula variables:");
                console.println("  x1, x2  Coordinates relative to bounding box min");
                console.println("  L1, L2  Bounding box dimensions");
                console.println("  pi      3.14159...");
            } else if (helpCmd == "indent") {
                console.println("Usage: KooRemapper indent <config.yaml>");
                std::cout << "\n";
                console.println("Apply indentation or embossing deformation and prestress.");
                console.println("Supports circular and polygon punch shapes.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: flat.k");
                console.println("  output: indented");
                console.println("  operations:");
                console.println("    - type: indent");
                console.println("      target_pid: 1");
                console.println("      plane: xy                # Indentation plane");
                console.println("      direction: -z            # Punch direction");
                console.println("      depth: 0.5              # Indent depth (negative = emboss)");
                console.println("      r1: 2.0                  # Punch radius");
                console.println("      r2: 0.5                  # Fillet radius");
                console.println("      stress: true             # Compute prestress");
                console.println("      shape:");
                console.println("        type: circle           # circle | polygon");
                console.println("        # polygon points:");
                console.println("        # points: [[0,0],[5,0],[5,5],[0,5]]");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  depth < 0  Emboss (pull outward)");
                console.println("  r1  Flat bottom radius, r2  Fillet blend radius");
                console.println("  shell_thickness  Required for shell element stress");
            } else if (helpCmd == "formstrain") {
                console.println("Usage: KooRemapper formstrain <config.yaml>");
                std::cout << "\n";
                console.println("Compute plastic strain from shell mesh dihedral angles.");
                console.println("Uses curvature kappa=theta/L to estimate forming EPS.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: bent_shell.k");
                console.println("  output: formstrain_result");
                console.println("  dynain_embed: true          # Embed *INITIAL_STRAIN_SHELL in output");
                console.println("  operations:");
                console.println("    - type: formstrain");
                console.println("      target_pid: 1            # Omit to auto-detect all shell parts");
                console.println("      shell_thickness: 0.3     # Override thickness (optional)");
                console.println("      min_curvature: 0.001     # Ignore flat regions below threshold");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  - Requires bent shell mesh with *ELEMENT_SHELL");
                console.println("  - Reads material sigy from *MAT_024 for EPS scaling");
                console.println("  - EPS merge: max() across overlapping operations (not sum)");
            } else if (helpCmd == "convert") {
                console.println("Usage: KooRemapper convert <config.yaml>");
                std::cout << "\n";
                console.println("Convert element type to quadratic (TET10/HEX20/QUAD8/TRIA6).");
                console.println("Adds mid-side nodes to existing linear elements.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: model.k");
                console.println("  output: result");
                console.println("  operations:");
                console.println("    - type: hex20               # hex20 | tet10 | quad8 | tria6");
                console.println("      target_pid: 1             # Omit to convert all parts");
                console.println("      elform: 23                # Target ELFORM (optional)");
                std::cout << "\n";
                console.println("Supported conversions:");
                console.println("  tet10   TET4  -> TET10 (quadratic tetrahedron)");
                console.println("  hex20   HEX8  -> HEX20 (quadratic hexahedron)");
                console.println("  quad8   QUAD4 -> QUAD8 (quadratic shell)");
                console.println("  tria6   TRIA3 -> TRIA6 (quadratic triangle)");
            } else if (helpCmd == "refine") {
                console.println("Usage: KooRemapper refine <config.yaml>");
                std::cout << "\n";
                console.println("Mesh refinement by subdivision (1:2 or 1:3 split).");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: model.k");
                console.println("  output: refined");
                console.println("  operations:");
                console.println("    - type: refine");
                console.println("      target_pid: 1             # Omit to refine all parts");
                console.println("      ratio: 2                  # 2 = 1:2 split, 3 = 1:3 split");
                std::cout << "\n";
                console.println("Supported element types:");
                console.println("  HEX8   ratio 2 -> 8 hexes, ratio 3 -> 27 hexes");
                console.println("  QUAD4  ratio 2 -> 4 quads, ratio 3 -> 9 quads");
                console.println("  TRIA3  ratio 2 -> 4 triangles");
                console.println("  TET4   ratio 2 -> 8 tetrahedra");
            } else if (helpCmd == "elform") {
                console.println("Usage: KooRemapper elform <config.yaml>");
                std::cout << "\n";
                console.println("Change element formulation (ELFORM) in *SECTION_* cards.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: model.k");
                console.println("  output: result");
                console.println("  operations:");
                console.println("    - type: elform");
                console.println("      target_pid: 1             # Omit to change all matching parts");
                console.println("      target_elform: 23         # Target ELFORM value");
                std::cout << "\n";
                console.println("Common ELFORM values (solid):");
                console.println("  1   1-point reduced integration (default HEX8)");
                console.println("  2   Full integration (2x2x2)");
                console.println(" 10   1-point tetrahedron");
                console.println(" 13   1-point nodal pressure tetrahedron");
                console.println(" 16   5-point tet (improved)");
                console.println(" 23   HEX20 quadratic");
                std::cout << "\n";
                console.println("Common ELFORM values (shell):");
                console.println("  2   Belytschko-Tsay (default)");
                console.println(" 16   Fully integrated (reduced membrane hourglass)");
            } else if (helpCmd == "disconnect") {
                console.println("Usage: KooRemapper disconnect <config.yaml>");
                std::cout << "\n";
                console.println("Decohere conformal mesh interface for fracture modeling.");
                console.println("Splits shared nodes at part boundaries.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: model.k");
                console.println("  output: result");
                console.println("  operations:");
                console.println("    - type: disconnect");
                console.println("      mode: czm                 # czm | full | mefem");
                console.println("      target_pid: 1             # Interface part (czm/mefem) or 0=all");
                console.println("      cohesive_part_id: 99      # CZM cohesive part ID (czm mode)");
                console.println("      failure_strain: 0.5       # CZM failure strain");
                std::cout << "\n";
                console.println("Modes:");
                console.println("  full    Split all shared nodes -> independent parts");
                console.println("  czm     Insert cohesive zone elements at interface");
                console.println("  mefem   Insert MEFEM (mesh-free) peridynamic elements");
            } else if (helpCmd == "warpage") {
                console.println("Usage: KooRemapper warpage <config.yaml>");
                std::cout << "\n";
                console.println("Apply warpage deflection field to shell or solid parts.");
                console.println("Reads measured warpage data (CSV/dat) and deforms mesh.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: flat.k");
                console.println("  output: warped");
                console.println("  operations:");
                console.println("    - type: warpage");
                console.println("      target_pid: 1");
                console.println("      source: dat_file          # dat_file | formula");
                console.println("      dat_file: warpage.dat     # Measured deflection data");
                console.println("      dat_top: top              # Column name for top surface");
                console.println("      dat_bottom: bottom        # Column name for bottom surface");
                console.println("      x_min: 0.0               # Data bounding box (optional)");
                console.println("      x_max: 100.0");
                console.println("      y_min: 0.0");
                console.println("      y_max: 100.0");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  - dat file: tab/space delimited with x, y, z columns");
                console.println("  - Bilinear interpolation used for intermediate node positions");
            } else if (helpCmd == "offset") {
                console.println("Usage: KooRemapper offset <config.yaml>");
                std::cout << "\n";
                console.println("Extrude surface elements to solid HEX8 layer(s).");
                console.println("Supports tied, CZM, and contact connection modes.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  base_model: model.k");
                console.println("  output: result");
                console.println("  operations:");
                console.println("    - type: offset");
                console.println("      source_pid: 1             # Source surface part");
                console.println("      element_type: solid       # solid | tshell | shell");
                console.println("      thickness: 1.0            # Offset distance");
                console.println("      num_layers: 1             # Number of layers");
                console.println("      offset_direction: +z      # +x|-x|+y|-y|+z|-z|+normal|-normal");
                console.println("      connection_mode: tied     # tied | czm | contact | none");
                console.println("      new_pid: 10               # New part ID");
                console.println("      use_local_normals: false  # Per-node averaged normals");
                console.println("      thickness_formula: \"1.0+0.01*x\"  # Variable thickness");
                console.println("      material_card: |          # Inline material definition");
                console.println("        *MAT_ELASTIC");
                console.println("        $#  mid   ro     e    pr");
                console.println("             @MID@  2.0  1000  0.35");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  - @MID@ is auto-replaced with assigned material ID");
                console.println("  - use_local_normals improves quality on curved surfaces");
                console.println("  - region: bbox/nodeId/elementId filters source surface");
                console.println("  - See examples/offset/README.md for full examples");
            } else if (helpCmd == "wrap") {
                console.println("Usage: KooRemapper wrap <config.yaml>");
                std::cout << "\n";
                console.println("Apply winding tension prestress (hoop + radial stress).");
                console.println("Models wire/fiber winding or press-fit cylindrical tension.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: cylinder.k");
                console.println("  output: cylinder_wrapped");
                console.println("  target_pid: [1, 2]           # One or more part IDs");
                console.println("  axis: z                      # Winding axis: x | y | z");
                console.println("  tension: 100.0               # Winding tension [force/length]");
                console.println("  center: [0.0, 0.0]           # Axis center (optional, auto-detect)");
                console.println("  material:");
                console.println("    E: 210000.0");
                console.println("    nu: 0.3");
                std::cout << "\n";
                console.println("Notes:");
                console.println("  - Generates hoop (circumferential) + radial prestress dynain");
                console.println("  - Use with 'relax' command or dynamic_relaxation: true for");
                console.println("    equilibration before main analysis");
            } else {
                console.error("Unknown command: " + helpCmd);
                return 1;
            }
        } else {
            printBanner(console);
            console.println("Usage: KooRemapper <command> [options]");
            std::cout << "\n";
            console.println("Commands:");
            console.println("  map          Map a flat mesh onto a bent reference mesh (HEX8)");
            console.println("  shellmap     Map a flat mesh using a bent shell reference (QUAD4)");
            console.println("  unfold       Generate flat mesh from a bent structured mesh");
            console.println("  generate     Generate example meshes for testing");
            console.println("  generate-var Generate variable density mesh from YAML config");
            console.println("  strain       Calculate strain between two meshes");
            console.println("  prestress    Calculate prestress from deformed configuration");
            console.println("  squeeze      Compress parts for interference fit modeling");
            console.println("  assemble     Assemble model with sequential part operations");
            console.println("  matswap      Replace material bundle (MAT+HG+CURVE+SECTION) for parts");
            console.println("  matdb        Replace materials from JSON DB (structural + thermal)");
            console.println("  load         Apply loads (force/pressure/gravity) from YAML config");
            console.println("  boundary     Apply boundary conditions (SPC/rigid wall) from YAML config");
            console.println("  rbe          Create RBE constraints (RBE2/RBE3) from YAML config");
            console.println("  relax        Set up Dynamic Relaxation for initial stress equilibrium");
            console.println("  explicit     Revert to pure explicit (strip implicit/DR/modal keywords)");
            console.println("  implicit     Convert explicit K-file to implicit solver settings");
            console.println("  modal        Convert explicit K-file to modal (natural frequency) analysis");
            console.println("  ale          Convert parts to ALE with material presets");
            console.println("  contact      Analyze, create, modify, convert contact definitions");
            console.println("  optimize     Apply material-specific global card optimization");
            console.println("  stabilize    Apply explicit solver stabilization (12-level system)");
            console.println("  database     Insert DATABASE output control keywords");
            console.println("  restack      Extrude/restack layers from shell surface");
            console.println("  bend         Apply bending deformation + prestress");
            console.println("  indent       Apply indentation/embossing deformation + prestress");
            console.println("  formstrain   Compute plastic strain from shell dihedral angles");
            console.println("  convert      Convert element type (tet10/hex20/quad8/tria6)");
            console.println("  refine       Mesh refinement (1:2 or 1:3 subdivision)");
            console.println("  elform       Change element formulation (ELFORM)");
            console.println("  disconnect   Decohere conformal mesh (full/czm/mefem)");
            console.println("  iga          Embed FE part in IGA (NURBS) trivariate box");
            console.println("  warpage      Apply warpage deflection to shell/solid parts");
            console.println("  offset       Extrude surface elements to solid layer(s)");
            console.println("  wrap         Apply winding tension prestress (hoop + radial)");
            console.println("  update       Update node coordinates from dynain/k-file");
            console.println("  info         Display information about a mesh file");
            console.println("  help         Show help for a command");
            console.println("  version      Show version information");
            std::cout << "\n";
            console.println("Use 'KooRemapper help <command>' for details.");
            console.println("  Key commands: help assemble  help implicit  help modal  help ale  help contact");
        }
        return 0;
    }

    // Map command
    if (command == "map") {
        // Parse options
        bool useParallel = true;  // Default: parallel mode
        bool forcePositive = false;
        bool flipX = false, flipY = false, flipZ = false;
        bool flipInX = false, flipInY = false, flipInZ = false;
        std::string bboxAlignMode = "none";   // none | source | target
        double bboxAlignMaxDrift = 2.0;       // percent
        bool sawBboxAlignCli = false;
        bool sawBboxDriftCli = false;
        std::vector<std::string> positionalArgs;

        for (int i = 2; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--single" || arg == "-s") {
                useParallel = false;
            } else if (arg == "--force-positive" || arg == "--fp") {
                forcePositive = true;
            } else if (arg == "--flip-x") {
                flipX = true;
            } else if (arg == "--flip-y") {
                flipY = true;
            } else if (arg == "--flip-z") {
                flipZ = true;
            } else if (arg == "--flip-input-x") {
                flipInX = true;
            } else if (arg == "--flip-input-y") {
                flipInY = true;
            } else if (arg == "--flip-input-z") {
                flipInZ = true;
            } else if (arg == "--bbox-align" && i + 1 < argc) {
                bboxAlignMode = argv[++i];
                sawBboxAlignCli = true;
            } else if (arg == "--bbox-align-max-drift" && i + 1 < argc) {
                try { bboxAlignMaxDrift = std::stod(argv[++i]); sawBboxDriftCli = true; }
                catch (...) {
                    console.error("Invalid value for --bbox-align-max-drift");
                    return 1;
                }
            } else if (arg[0] != '-') {
                positionalArgs.push_back(arg);
            }
        }

        // YAML mode: single positional arg ending in .yaml/.yml replaces the
        // 3-positional + flag form. All options (including bent/flat/output
        // paths and flip flags) come from the YAML. CLI flags act as
        // overrides (CLI takes precedence over YAML).
        auto endsWith = [](const std::string& s, const std::string& suf) {
            return s.size() >= suf.size() &&
                   s.compare(s.size() - suf.size(), suf.size(), suf) == 0;
        };
        bool yamlMode = (positionalArgs.size() == 1 &&
                         (endsWith(positionalArgs[0], ".yaml") ||
                          endsWith(positionalArgs[0], ".yml")));

        std::string bentPath, flatPath, outputPath;

        // Optional prestress chaining state populated by YAML reader.
        bool   pre_enabled = false;
        std::string pre_output;
        std::string pre_strainType = "green";  // green | engineering | log
        double pre_E = 0.0;
        double pre_nu = 0.0;
        bool   pre_csv = false;

        if (yamlMode) {
            // Minimal flat YAML reader for the map config schema.
            //   bent: <path>
            //   flat: <path>
            //   output: <path>
            //   parallel: true|false       (optional, default true)
            //   force_positive: true|false (optional, default false)
            //   flip_x: true|false         (optional, default false)
            //   flip_y: true|false         (optional, default false)
            //   flip_z: true|false         (optional, default false)
            //
            //   prestress:                 (optional; when present + enabled,
            //     enabled: true             generates a dynain from the mapped
            //     output: detail_stress.dynain
            //     strain_type: green       # green | engineering | log
            //     E:  210000.0             # MPa, optional (omit -> strain only)
            //     nu: 0.3                  # optional
            //     csv: false               # optional, write CSV instead of dynain
            //   )
            // Comments start with '#'. Unknown keys are ignored with a warning.
            std::ifstream yf(positionalArgs[0]);
            if (!yf.is_open()) {
                console.error("Cannot open YAML config: " + positionalArgs[0]);
                return 1;
            }
            auto trim = [](std::string s) {
                size_t a = s.find_first_not_of(" \t\r\n");
                size_t b = s.find_last_not_of(" \t\r\n");
                if (a == std::string::npos) return std::string();
                return s.substr(a, b - a + 1);
            };
            auto stripQuotes = [](std::string s) {
                if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') ||
                                      (s.front() == '\'' && s.back() == '\''))) {
                    return s.substr(1, s.size() - 2);
                }
                return s;
            };
            auto parseBool = [](const std::string& v) {
                std::string t = v;
                for (auto& c : t) c = (char)std::tolower((unsigned char)c);
                return t == "true" || t == "yes" || t == "on" || t == "1";
            };
            // Track which keys were set in YAML so CLI flags can override.
            bool yamlForce = false, yamlFlipX = false, yamlFlipY = false, yamlFlipZ = false;
            bool yamlFlipInX = false, yamlFlipInY = false, yamlFlipInZ = false;
            bool yamlParallel = useParallel;
            bool sawForce = false, sawFlipX = false, sawFlipY = false, sawFlipZ = false, sawParallel = false;
            bool sawFlipInX = false, sawFlipInY = false, sawFlipInZ = false;
            std::string yamlBboxAlign;
            double yamlBboxDrift = 2.0;
            bool sawBboxAlignYaml = false, sawBboxDriftYaml = false;

            std::string line;
            std::string section;       // "" or "prestress"
            int sectionIndent = -1;    // tracks the prestress block's indent
            while (std::getline(yf, line)) {
                size_t hash = line.find('#');
                if (hash != std::string::npos) line = line.substr(0, hash);
                if (line.find_first_not_of(" \t\r\n") == std::string::npos) continue;
                int indent = 0;
                while (indent < (int)line.size() &&
                       (line[indent] == ' ' || line[indent] == '\t')) ++indent;
                std::string body = trim(line);
                size_t colon = body.find(':');
                if (colon == std::string::npos) continue;
                std::string key = trim(body.substr(0, colon));
                std::string val = stripQuotes(trim(body.substr(colon + 1)));

                // Section bookkeeping
                if (indent == 0) {
                    section.clear();
                    sectionIndent = -1;
                    if (val.empty() && key == "prestress") {
                        section = "prestress";
                        sectionIndent = 0;
                        pre_enabled = true;  // presence of section enables it by default
                        continue;
                    }
                } else if (sectionIndent < 0 || indent <= sectionIndent) {
                    section.clear();
                }

                if (section == "prestress") {
                    if      (key == "enabled")     pre_enabled = parseBool(val);
                    else if (key == "output")      pre_output = val;
                    else if (key == "strain_type") pre_strainType = val;
                    else if (key == "E")        { try { pre_E = std::stod(val); } catch(...) {} }
                    else if (key == "nu")       { try { pre_nu = std::stod(val); } catch(...) {} }
                    else if (key == "csv")         pre_csv = parseBool(val);
                    continue;
                }

                if      (key == "bent")           bentPath = val;
                else if (key == "flat")           flatPath = val;
                else if (key == "output")         outputPath = val;
                else if (key == "parallel")     { yamlParallel = parseBool(val); sawParallel = true; }
                else if (key == "force_positive"){ yamlForce = parseBool(val); sawForce = true; }
                else if (key == "flip_x")       { yamlFlipX = parseBool(val); sawFlipX = true; }
                else if (key == "flip_y")       { yamlFlipY = parseBool(val); sawFlipY = true; }
                else if (key == "flip_z")       { yamlFlipZ = parseBool(val); sawFlipZ = true; }
                else if (key == "flip_input_x") { yamlFlipInX = parseBool(val); sawFlipInX = true; }
                else if (key == "flip_input_y") { yamlFlipInY = parseBool(val); sawFlipInY = true; }
                else if (key == "flip_input_z") { yamlFlipInZ = parseBool(val); sawFlipInZ = true; }
                else if (key == "bbox_align")   { yamlBboxAlign = val; sawBboxAlignYaml = true; }
                else if (key == "bbox_align_max_drift") {
                    try { yamlBboxDrift = std::stod(val); sawBboxDriftYaml = true; }
                    catch(...) { console.warning("Invalid bbox_align_max_drift: " + val); }
                }
                else if (key == "prestress")    { /* handled above as section */ }
                else {
                    console.warning("Unknown YAML key in map config: " + key);
                }
            }
            if (bentPath.empty() || flatPath.empty() || outputPath.empty()) {
                console.error("YAML config missing required keys (bent, flat, output)");
                return 1;
            }
            // CLI flags override YAML values when explicitly passed.
            if (sawParallel && useParallel) useParallel = yamlParallel;  // CLI --single sets useParallel=false; respect that
            if (sawForce  && !forcePositive) forcePositive = yamlForce;
            if (sawFlipX  && !flipX)         flipX         = yamlFlipX;
            if (sawFlipY  && !flipY)         flipY         = yamlFlipY;
            if (sawFlipZ  && !flipZ)         flipZ         = yamlFlipZ;
            if (sawFlipInX && !flipInX)      flipInX       = yamlFlipInX;
            if (sawFlipInY && !flipInY)      flipInY       = yamlFlipInY;
            if (sawFlipInZ && !flipInZ)      flipInZ       = yamlFlipInZ;
            if (sawBboxAlignYaml && !sawBboxAlignCli) bboxAlignMode = yamlBboxAlign;
            if (sawBboxDriftYaml && !sawBboxDriftCli) bboxAlignMaxDrift = yamlBboxDrift;
        } else {
            if (positionalArgs.size() < 3) {
                console.error("Usage: KooRemapper map [--single] [--force-positive] "
                              "[--flip-x|y|z] <bent_mesh> <flat_mesh> <output>");
                console.println("       KooRemapper map <config.yaml>");
                console.println("Options:");
                console.println("  --single, -s         Use single-threaded mode (default: parallel)");
                console.println("  --force-positive,    Force every mapped HEX8 Jacobian positive by");
                console.println("    --fp               swapping connectivity (overrides source sign).");
                console.println("                       Use when source mesh has unreliable HEX winding.");
                console.println("  --flip-x             Mirror output along global X (negate node X).");
                console.println("  --flip-y             Mirror output along global Y.");
                console.println("  --flip-z             Mirror output along global Z. Combine multiple");
                console.println("                       (e.g. --flip-x --flip-z) to compose reflections.");
                console.println("                       HEX8 connectivity is swapped automatically when");
                console.println("                       odd-parity flips would otherwise invert Jacobian.");
                console.println("  --flip-input-x|y|z   PRE-map detail flat mirror. Mirrors detail BEFORE");
                console.println("                       mapping so its features land on the OPPOSITE face");
                console.println("                       of the bent target while keeping the result's");
                console.println("                       global coordinates unchanged. Use for slit/hole");
                console.println("                       face swap independent of bent location.");
                console.println("  --bbox-align <mode>  Auto-rescale to remove uniform stretch in mapping.");
                console.println("                       mode = source: rescale detail flat to bent ijk lengths");
                console.println("                              target: rescale bent to detail XYZ lengths");
                console.println("                              none  : default, no rescaling");
                console.println("                       Eliminates axial-bias bending stress asymmetry caused");
                console.println("                       by detail/target bbox mismatch.");
                console.println("  --bbox-align-max-drift <pct>");
                console.println("                       Reject scaling if any axis ratio drifts beyond this");
                console.println("                       percent. Default 2.0%. Safety guard for big mismatches.");
                console.println("YAML config (alternative to positional args):");
                console.println("  bent: <bent.k>");
                console.println("  flat: <flat.k>");
                console.println("  output: <out.k>");
                console.println("  parallel: true            # optional");
                console.println("  force_positive: false     # optional");
                console.println("  flip_x: false             # optional, output mirror");
                console.println("  flip_y: false             # optional");
                console.println("  flip_z: true              # optional");
                console.println("  flip_input_x: false       # optional, PRE-map detail flat mirror");
                console.println("  flip_input_y: false       # (slit/hole face swap; result coords unchanged)");
                console.println("  flip_input_z: true        # ");
                console.println("  bbox_align: source        # optional: source|target|none");
                console.println("  bbox_align_max_drift: 2.0 # optional, percent (reject above)");
                console.println("  prestress:                # optional, chain prestress after map");
                console.println("    enabled: true");
                console.println("    output: detail_stress.dynain");
                console.println("    strain_type: green      # green | engineering | log");
                console.println("    E:  210000.0            # MPa, optional (omit = strain only)");
                console.println("    nu: 0.3                 # optional");
                console.println("    csv: false              # optional");
                console.println("Diagnostics:");
                console.println("  Set KOO_MAP_DEBUG=1 to print orientation correction internals.");
                return 1;
            }
            bentPath = positionalArgs[0];
            flatPath = positionalArgs[1];
            outputPath = positionalArgs[2];
        }

        printBanner(console);
        std::string scaledFlatPath;  // populated by runMapping when flat is preprocessed
        int mapRc = runMapping(bentPath, flatPath, outputPath,
                               console, useParallel, forcePositive, flipX, flipY, flipZ,
                               bboxAlignMode, bboxAlignMaxDrift, &scaledFlatPath,
                               flipInX, flipInY, flipInZ);
        if (mapRc != 0) return mapRc;

        // Optional prestress chaining: configured only via YAML (CLI form
        // does not accept it). After mapping, treat the original FLAT mesh
        // as the reference and the just-written MAPPED file as the deformed
        // configuration, computing strain/stress per the chosen option.
        if (yamlMode && pre_enabled) {
            if (pre_output.empty()) {
                console.error("Prestress section requested but 'output:' "
                              "(dynain/csv path) not set");
                return 1;
            }
            StrainType strainType = StrainType::GREEN_LAGRANGE;
            std::string st = pre_strainType;
            for (auto& c : st) c = (char)std::tolower((unsigned char)c);
            if      (st == "engineering") strainType = StrainType::ENGINEERING;
            else if (st == "log" || st == "logarithmic" || st == "true")
                                          strainType = StrainType::LOGARITHMIC;

            // Reference selection priority:
            //   1. bbox_align=source: use the bbox-scaled flat written by
            //      runMapping (otherwise the un-scaled flat would inject
            //      the same uniform stretch we just removed back as residual
            //      stress in F = ∂x_def/∂X_ref).
            //   2. flip_x/y/z: apply the same flip to the flat reference so
            //      element-local node orderings match between ref and def.
            //      Both 1 and 2 may apply; flip is composed on top of the
            //      scaled flat in that case.
            //   3. Otherwise: use the original flat as-is.
            std::string refFileForPrestress = flatPath;
            std::string tempRefPath;
            bool ownsScaledFlat = !scaledFlatPath.empty();   // we own its lifetime
            if (ownsScaledFlat) {
                refFileForPrestress = scaledFlatPath;
            }
            bool needFlipRef = (flipX || flipY || flipZ);
            if (needFlipRef) {
                tempRefPath = outputPath + ".__flipped_ref.k";
                std::cout << "\n";
                console.info("Generating flip-aligned reference for prestress: "
                             + tempRefPath);
                int frc = applyMeshFlipFile(refFileForPrestress, tempRefPath,
                                             flipX, flipY, flipZ, console);
                if (frc != 0) return frc;
                refFileForPrestress = tempRefPath;
            }

            std::cout << "\n";
            console.header("Chained Prestress");
            console.info("Reference (flat): " + refFileForPrestress);
            console.info("Deformed (mapped): " + outputPath);
            console.info("Output: " + pre_output);
            int prc = runPrestress(refFileForPrestress, outputPath, pre_output,
                                    pre_E, pre_nu, strainType, pre_csv, console);

            // Clean up temp ref(s) regardless of prestress success.
            if (!tempRefPath.empty()) std::remove(tempRefPath.c_str());
            if (ownsScaledFlat)      std::remove(scaledFlatPath.c_str());
            return prc;
        }
        // No prestress chain — scaled flat tmp (if any) is no longer needed.
        if (!scaledFlatPath.empty()) std::remove(scaledFlatPath.c_str());
        return 0;
    }

    // Shell-based mapping command
    if (command == "shellmap") {
        double thickness = -1.0;  // Auto-detect
        std::vector<std::string> positionalArgs;

        for (int i = 2; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--thickness" && i + 1 < argc) {
                try {
                    thickness = std::stod(argv[++i]);
                } catch (...) {
                    console.error("Invalid thickness value");
                    return 1;
                }
            } else if (arg[0] != '-') {
                positionalArgs.push_back(arg);
            }
        }

        if (positionalArgs.size() < 3) {
            console.error("Usage: KooRemapper shellmap [--thickness <t>] <bent_shell> <flat_detail> <output>");
            return 1;
        }
        printBanner(console);
        return runShellMapping(positionalArgs[0], positionalArgs[1], positionalArgs[2],
                              thickness, console);
    }

    // Unfold command
    if (command == "unfold") {
        if (argc < 4) {
            console.error("Usage: KooRemapper unfold <bent_mesh> <output_flat>");
            return 1;
        }
        printBanner(console);
        return runUnfold(argv[2], argv[3], console);
    }

    // Generate command
    if (command == "generate") {
        // Sub-command: generate box <yaml>
        if (argc >= 3 && std::string(argv[2]) == "box") {
            if (argc < 4) {
                console.error("Usage: KooRemapper generate box <config.yaml>");
                return 1;
            }
            printBanner(console);
            return runGenerateBox(argv[3], console);
        }

        ArgumentParser parser("KooRemapper generate", "Generate example meshes");
        parser.addPositional("type", "Mesh type: teardrop, arc, scurve, helix");
        parser.addPositional("output_prefix", "Prefix for output files");
        parser.addOption("", "dim-i", "Elements in I direction", "10");
        parser.addOption("", "dim-j", "Elements in J direction", "5");
        parser.addOption("", "dim-k", "Elements in K direction", "5");

        // Repack arguments for parser
        int subArgc = argc - 1;
        char** subArgv = argv + 1;

        if (!parser.parse(subArgc, subArgv)) {
            console.error(parser.getError());
            return 1;
        }

        std::string type = parser.getPositional("type");
        std::string prefix = parser.getPositional("output_prefix");

        if (type.empty() || prefix.empty()) {
            console.error("Usage: KooRemapper generate [options] <type> <output_prefix>");
            console.info("Types: teardrop, arc, scurve, helix");
            return 1;
        }

        int dimI = parser.getInt("dim-i").value_or(10);
        int dimJ = parser.getInt("dim-j").value_or(5);
        int dimK = parser.getInt("dim-k").value_or(5);

        printBanner(console);
        return runGenerate(type, prefix, dimI, dimJ, dimK, console);
    }

    // Generate-var command
    if (command == "generate-var") {
        ArgumentParser parser("KooRemapper generate-var", "Generate variable density mesh");
        parser.addPositional("config", "YAML configuration file");
        parser.addPositional("output", "Output K-file");
        parser.addOption("", "ref", "Reference flat mesh for scaling", "");
        parser.addFlag("", "no-scale", "Don't scale to reference");

        int subArgc = argc - 1;
        char** subArgv = argv + 1;

        if (!parser.parse(subArgc, subArgv)) {
            console.error(parser.getError());
            return 1;
        }

        std::string configFile = parser.getPositional("config");
        std::string outputFile = parser.getPositional("output");
        std::string refFile = parser.getOption("ref");
        bool noScale = parser.hasFlag("no-scale");

        if (configFile.empty() || outputFile.empty()) {
            console.error("Usage: KooRemapper generate-var [options] <config.yaml> <output.k>");
            return 1;
        }

        printBanner(console);
        return runGenerateVar(configFile, outputFile, refFile, noScale, console);
    }

    // Strain command
    if (command == "strain") {
        ArgumentParser parser("KooRemapper strain", "Calculate strain between meshes");
        parser.addPositional("ref_mesh", "Reference mesh (k-file)");
        parser.addPositional("def_mesh", "Deformed mesh (k-file)");
        parser.addPositional("output", "Output CSV file");
        parser.addOption("", "type", "Strain type: engineering, green, log", "engineering");

        int subArgc = argc - 1;
        char** subArgv = argv + 1;

        if (!parser.parse(subArgc, subArgv)) {
            console.error(parser.getError());
            return 1;
        }

        std::string refFile = parser.getPositional("ref_mesh");
        std::string defFile = parser.getPositional("def_mesh");
        std::string output = parser.getPositional("output");
        std::string strainType = parser.getOption("type");
        if (strainType.empty()) strainType = "engineering";

        if (refFile.empty() || defFile.empty() || output.empty()) {
            console.error("Usage: KooRemapper strain [options] <ref_mesh> <def_mesh> <output.csv>");
            return 1;
        }

        printBanner(console);
        return runStrain(refFile, defFile, output, strainType, console);
    }

    // Prestress command
    if (command == "prestress") {
        ArgumentParser parser("KooRemapper prestress", "Calculate prestress");
        parser.addPositional("ref_mesh", "Reference mesh (k-file)");
        parser.addPositional("def_mesh", "Deformed mesh (k-file)");
        parser.addPositional("output", "Output file (dynain or csv)");
        parser.addOption("", "E", "Young's modulus", "0");
        parser.addOption("", "nu", "Poisson's ratio", "0");
        parser.addOption("", "strain", "Strain type: engineering, green, log", "green");
        parser.addFlag("", "csv", "Output CSV file");

        int subArgc = argc - 1;
        char** subArgv = argv + 1;

        if (!parser.parse(subArgc, subArgv)) {
            console.error(parser.getError());
            return 1;
        }

        std::string refFile = parser.getPositional("ref_mesh");
        std::string defFile = parser.getPositional("def_mesh");
        std::string output = parser.getPositional("output");

        if (refFile.empty() || defFile.empty() || output.empty()) {
            console.error("Usage: KooRemapper prestress [options] <ref_mesh> <def_mesh> <output>");
            return 1;
        }

        double E = parser.getDouble("E").value_or(0.0);
        double nu = parser.getDouble("nu").value_or(0.0);
        std::string strainTypeStr = parser.getOption("strain");
        bool outputCSV = parser.hasFlag("csv");

        StrainType strainType = StrainType::GREEN_LAGRANGE;
        if (strainTypeStr == "engineering") {
            strainType = StrainType::ENGINEERING;
        } else if (strainTypeStr == "log") {
            strainType = StrainType::LOGARITHMIC;
        }

        printBanner(console);
        return runPrestress(refFile, defFile, output, E, nu, strainType, outputCSV, console);
    }

    // Squeeze command
    if (command == "squeeze") {
        std::vector<std::string> positionalArgs;

        for (int i = 2; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg[0] != '-') {
                positionalArgs.push_back(arg);
            }
        }

        if (positionalArgs.size() < 3) {
            console.error("Usage: KooRemapper squeeze <mesh.k> <config.yaml> <output_prefix>");
            return 1;
        }
        printBanner(console);
        return runSqueeze(positionalArgs[0], positionalArgs[1], positionalArgs[2], console);
    }

    // Assemble command
    if (command == "assemble") {
        if (argc < 3) {
            console.error("Usage: KooRemapper assemble <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runAssemble(argv[2], console);
    }

    // Matswap command
    if (command == "matswap") {
        // YAML mode: single argument ending in .yaml/.yml
        if (argc == 3) {
            std::string arg = argv[2];
            if (arg.size() >= 5 &&
                (arg.substr(arg.size()-5) == ".yaml" || arg.substr(arg.size()-4) == ".yml")) {
                printBanner(console);
                return runMatswapYaml(arg, console);
            }
        }
        // Legacy positional mode
        if (argc < 6) {
            console.error("Usage (YAML):    KooRemapper matswap <config.yaml>");
            console.error("Usage (legacy):  KooRemapper matswap <model.k> <bundle.k> <target_pid> <output.k>");
            console.println("  config.yaml: YAML with model/output/swaps (supports multiple PIDs, swap_all)");
            return 1;
        }
        std::string modelFile  = argv[2];
        std::string bundleFile = argv[3];
        int targetPid = std::stoi(argv[4]);
        std::string outputFile = argv[5];
        printBanner(console);
        return runMatswap(modelFile, bundleFile, targetPid, outputFile, console);
    }

    // Matdb command
    if (command == "matdb") {
        if (argc < 3) {
            console.error("Usage: KooRemapper matdb <config.yaml>");
            console.error("       KooRemapper matdb list [database.json]");
            console.println("  Material database-driven swap: replace structural materials from JSON DB");
            console.println("  Options: mat_type (MAT_ELASTIC/MAT_024/MAT_RIGID), thermal (true/false)");
            return 1;
        }
        std::string subcmd(argv[2]);
        if (subcmd == "list") {
            printBanner(console);
            std::string dbPath = (argc >= 4) ? argv[3] : "materials/material_db.json";
            return runMatdbList(dbPath, console);
        }
        printBanner(console);
        return runMatdb(argv[2], console);
    }

    // Load command
    if (command == "load") {
        if (argc < 3) {
            console.error("Usage: KooRemapper load <config.yaml>");
            console.println("  Apply segment-based loads (pressure/force) to model");
            console.println("  Modes: force, pressure, normal_pressure");
            console.println("  Select: direction, set, tied");
            return 1;
        }
        printBanner(console);
        return runLoad(argv[2], console);
    }

    // Boundary command
    if (command == "boundary") {
        if (argc < 3) {
            console.error("Usage: KooRemapper boundary <config.yaml>");
            console.println("  Apply nodal SPC boundary conditions");
            console.println("  DOF: all, xyz, x, y, z, xy, xz, yz, custom");
            console.println("  Select: direction, set");
            return 1;
        }
        printBanner(console);
        return runBoundary(argv[2], console);
    }

    // RBE command
    if (command == "rbe") {
        if (argc < 3) {
            console.error("Usage: KooRemapper rbe <config.yaml>");
            console.println("  Create RBE constraints (CNRB/CONSTRAINED_INTERPOLATION)");
            console.println("  Type: rbe2 (rigid), rbe3 (interpolation)");
            console.println("  Mode: spider (one centroid), face (per-face centroid)");
            return 1;
        }
        printBanner(console);
        return runRbe(argv[2], console);
    }

    // Relax command (Dynamic Relaxation)
    if (command == "relax") {
        if (argc < 3) {
            console.error("Usage: KooRemapper relax <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runRelax(argv[2], console);
    }

    // Explicit command (revert to pure explicit)
    if (command == "explicit") {
        if (argc < 3) {
            console.error("Usage: KooRemapper explicit <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runExplicit(argv[2], console);
    }

    // Implicit command
    if (command == "implicit") {
        if (argc < 3) {
            console.error("Usage: KooRemapper implicit <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runImplicit(argv[2], console);
    }

    // Modal command
    if (command == "modal") {
        if (argc < 3) {
            console.error("Usage: KooRemapper modal <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runModal(argv[2], console);
    }

    // ALE command
    if (command == "ale") {
        if (argc < 3) {
            console.error("Usage: KooRemapper ale <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runAle(argv[2], console);
    }

    // Contact command
    if (command == "contact") {
        if (argc < 3) {
            console.error("Usage: KooRemapper contact <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runContact(argv[2], console);
    }

    // Optimize command
    if (command == "optimize") {
        if (argc < 3) {
            console.error("Usage: KooRemapper optimize <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runOptimize(argv[2], console);
    }

    // Stabilize command
    if (command == "stabilize") {
        if (argc < 3) {
            console.error("Usage: KooRemapper stabilize <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runStabilize(argv[2], console);
    }

    // Database command
    if (command == "database") {
        if (argc < 3) {
            console.error("Usage: KooRemapper database <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runDatabase(argv[2], console);
    }

    // TET local remesh command
    if (command == "tetremesh") {
        if (argc < 3) {
            console.error("Usage: KooRemapper tetremesh <config.yaml>");
            console.println("");
            console.println("YAML schema:");
            console.println("  model:        input.k");
            console.println("  output:       output.k");
            console.println("  backend:      localimprove | tetgen   # default localimprove");
            console.println("  fallback:     localimprove | tetgen   # optional, used when");
            console.println("                                        # primary backend fails per patch");
            console.println("  report_only:  false                   # true = scan + report only");
            console.println("  target_pids:  [1, 2, 3]               # optional; empty = all parts");
            console.println("");
            console.println("  quality:");
            console.println("    # SCALED JACOBIAN: 1.0 = perfect equilateral tet, 0 = degenerate,");
            console.println("    # <0 = inverted. Suggested thresholds:");
            console.println("    #   <0.1   very poor    0.2~0.5  acceptable    >0.7  excellent");
            console.println("    min_jacobian:     0.2");
            console.println("    max_aspect_ratio: 8.0");
            console.println("");
            console.println("  patch:");
            console.println("    ring_expand:           2");
            console.println("    surface_flatness_deg:  5.0");
            console.println("    surface_move_tolerance: 0.0   # >0 = flat-surface tangential motion");
            console.println("    preserve_multi_material: true");
            console.println("");
            console.println("  improve:                  # Phase A backend tuning");
            console.println("    laplacian_iters: 5");
            console.println("    max_outer_iters: 3");
            console.println("    allow_subdivide: true");
            console.println("");
            console.println("  tetgen:                   # Phase B backend tuning");
            console.println("    quality_ratio:    1.4   # TetGen -q radius/edge ratio");
            console.println("    min_dihedral_deg: 10.0");
            console.println("");
            console.println("Backends:");
            console.println("  localimprove   smoothing + 2-3 face-edge swap + subdivide.");
            console.println("                 No external lib. Always available.");
            console.println("  tetgen         constrained Delaunay tetrahedralization via");
            console.println("                 third_party/tetgen. Build flag KOOREMAPPER_BUILD_TETGEN");
            console.println("                 must be ON (TetGen is AGPL v3).");
            return 1;
        }
        printBanner(console);
        return runTetRemesh(argv[2], console);
    }

    // MeshFix command — whole-part TET4 remesh via Gmsh subprocess
    if (command == "meshfix") {
        if (argc < 3) {
            console.error("Usage: KooRemapper meshfix <config.yaml>");
            console.println("");
            console.println("Requires dist/gmsh/gmsh.exe (or dist/gmsh-<ver>/gmsh.exe).");
            console.println("");
            console.println("YAML schema:");
            console.println("  model:          input.k");
            console.println("  output:         output.k");
            console.println("  pid:            3                 # part to remesh");
            console.println("");
            console.println("  lc_target:      1.0               # target avg element size");
            console.println("  lc_min:         0.3               # min size (or auto from min_dt)");
            console.println("  lc_max:         2.0               # max size (default: lc_target*2)");
            console.println("");
            console.println("  # min_dt-based lc_min (alternative to lc_min):");
            console.println("  min_dt:         1.0e-4            # LS-DYNA explicit dt lower bound");
            console.println("  density:        7.85e-9           # rho (t/mm^3)");
            console.println("  E:              210000.0          # MPa");
            console.println("  nu:             0.3");
            console.println("");
            console.println("  min_layers_thin: 2               # layers through thin dimension");
            console.println("  adaptive:       false            # bbox-corner attractor size field");
            console.println("                                   # (false is safe default; true adds");
            console.println("                                   #  Distance/Threshold fields around");
            console.println("                                   #  bbox corners; may slow HXT on");
            console.println("                                   #  complex surfaces)");
            console.println("  attractor_ratio: 0.4            # edge < lc_target*ratio -> attractor");
            console.println("  decay_factor:   8.0             # size ramp distance = lc_min*factor");
            console.println("");
            console.println("  boundary_nodes: free             # free | fixed | snap");
            console.println("  snap_tolerance: 0.001");
            console.println("");
            console.println("  algorithm:      hxt              # hxt | frontal3d | del3d");
            console.println("  optimize_netgen: true");
            console.println("  warn_min_jac:   0.15");
            console.println("");
            console.println("  refine_surface: 0                # 0=off; 1-3 = conforming feature");
            console.println("                                   # bisection on boundary STL edges");
            console.println("                                   # with dihedral > 40 deg");
            console.println("");
            console.println("  # Post-remesh patch polish (experimental):");
            console.println("  polish:         false            # enable local bad-element re-mesh");
            console.println("  polish_jac:     0.10             # polish elements below this Jac");
            console.println("  polish_max_iter: 2               # max polish iterations");
            return 1;
        }
        printBanner(console);
        return runMeshFix(argv[2], console);
    }

    // Info command
    if (command == "info") {
        if (argc < 3) {
            console.error("Usage: KooRemapper info <mesh_file>");
            return 1;
        }
        printBanner(console);
        return runInfo(argv[2], console);
    }

    // Restack command
    if (command == "restack") {
        if (argc < 3) {
            console.error("Usage: KooRemapper restack <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runRestack(argv[2], console);
    }

    // Bend command
    if (command == "bend") {
        if (argc < 3) {
            console.error("Usage: KooRemapper bend <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runBend(argv[2], console);
    }

    // Indent command
    if (command == "indent") {
        if (argc < 3) {
            console.error("Usage: KooRemapper indent <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runIndent(argv[2], console);
    }

    // Formstrain command
    if (command == "formstrain") {
        if (argc < 3) {
            console.error("Usage: KooRemapper formstrain <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runFormstrain(argv[2], console);
    }

    // Convert command (tet10/hex20/quad8/tria6)
    if (command == "convert") {
        if (argc < 3) {
            console.error("Usage: KooRemapper convert <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runConvert(argv[2], console);
    }

    // Refine command
    if (command == "refine") {
        if (argc < 3) {
            console.error("Usage: KooRemapper refine <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runRefine(argv[2], console);
    }

    // Elform command
    if (command == "elform") {
        if (argc < 3) {
            console.error("Usage: KooRemapper elform <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runElform(argv[2], console);
    }

    // Disconnect command
    if (command == "disconnect") {
        if (argc < 3) {
            console.error("Usage: KooRemapper disconnect <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runDisconnect(argv[2], console);
    }

    // IGA command
    if (command == "iga") {
        if (argc < 3) {
            console.error("Usage: KooRemapper iga <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runIga(argv[2], console);
    }

    // Warpage command
    if (command == "warpage") {
        if (argc < 3) {
            console.error("Usage: KooRemapper warpage <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runWarpage(argv[2], console);
    }

    // Offset command
    if (command == "offset") {
        if (argc < 3) {
            console.error("Usage: KooRemapper offset <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runOffset(argv[2], console);
    }

    // Wrap command
    if (command == "wrap") {
        if (argc < 3) {
            console.error("Usage: KooRemapper wrap <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runWrap(argv[2], console);
    }

    // Update command
    if (command == "update") {
        if (argc < 3) {
            console.error("Usage: KooRemapper update <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runUpdate(argv[2], console);
    }

    // Cnrb2Solid command
    if (command == "cnrb2solid") {
        if (argc < 3) {
            console.error("Usage: KooRemapper cnrb2solid <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runCnrb2Solid(argv[2], console);
    }

    // HFDamp command
    if (command == "hfdamp") {
        if (argc < 3) {
            console.error("Usage: KooRemapper hfdamp <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runHFDamp(argv[2], console);
    }

    // Battery command
    if (command == "battery") {
        if (argc < 3) {
            console.error("Usage: KooRemapper battery <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runBattery(argv[2], console);
    }

    // Merge command
    if (command == "merge") {
        if (argc < 3) {
            console.error("Usage: KooRemapper merge <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runMerge(argv[2], console);
    }

    // Strip command
    if (command == "strip") {
        if (argc < 3) {
            console.error("Usage: KooRemapper strip <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runStrip(argv[2], console);
    }

    // Unknown command
    console.error("Unknown command: " + command);
    console.info("Use 'KooRemapper help' for a list of commands.");
    return 1;
}
