#include "commands/tetremesh.h"
#include "core/Mesh.h"
#include "parser/KFileReader.h"
#include "parser/KFileWriter.h"
#include "remesh/PatchExtractor.h"
#include "remesh/RemeshOrchestrator.h"
#include "remesh/LocalImproveRemesher.h"
#include "remesh/TetGenRemesher.h"
#include "cli/ConsoleOutput.h"
#include "util/Timer.h"
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

namespace {

// Minimal flat YAML reader for the tetremesh config.
//   model: <input.k>
//   output: <output.k>
//   backend: localimprove | tetgen           (default: localimprove)
//   target_pids: [1, 2, 3]                   (optional; empty = all)
//   quality:
//     min_jacobian: 0.2
//     max_aspect_ratio: 8.0
//   patch:
//     ring_expand: 2
//     surface_flatness_deg: 5.0
//     surface_move_tolerance: 0.1
//     preserve_multi_material: true
//   improve:
//     laplacian_iters: 5
//     max_outer_iters: 3
//     allow_subdivide: true
//   tetgen:
//     quality_ratio: 1.4
//     min_dihedral_deg: 10.0

struct Cfg {
    std::string model;
    std::string output;
    std::string backend = "localimprove";   // "localimprove" | "tetgen"
    std::string fallback = "";              // "" | "localimprove" | "tetgen"
    bool reportOnly = false;                // scan + report quality, no modify

    // ---- selection ----
    std::string selectionMode = "bad_quality";   // "bad_quality" | "explicit_ids"
    std::vector<int> selectedElementIds;         // EXPLICIT_IDS seed set
    std::string ringMode = "node";               // "node" | "face"
    std::vector<int> targetPids;

    double minJacobian   = 0.20;            // scaled Jac (1.0 = perfect tet)
    double maxAspectRatio = 8.0;

    int    ringExpand           = 2;
    double surfaceFlatnessDeg   = 5.0;
    double surfaceMoveTolerance = 0.0;
    bool   preserveMultiMaterial = true;

    int    laplacianIters = 5;
    int    maxOuterIters  = 3;
    bool   allowSubdivide = true;

    double tetgenQualityRatio = 1.4;
    double tetgenMinDihedral  = 10.0;

    // ---- iterative driver ----
    bool   iterate              = false;    // wrap orchestrator.run() in
                                            // a loop until target hit
    int    iterMax              = 10;
    double iterTarget           = 0.30;     // min scaledJac target
    double iterConvergenceTol   = 0.01;     // early-stop if no improvement
    bool   iterKeepBest         = true;
};

std::string trim(std::string s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    size_t b = s.find_last_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    return s.substr(a, b - a + 1);
}
std::string stripQuotes(std::string s) {
    if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') ||
                          (s.front() == '\'' && s.back() == '\''))) {
        return s.substr(1, s.size() - 2);
    }
    return s;
}
bool parseBool(const std::string& v) {
    std::string t = v;
    for (auto& c : t) c = (char)std::tolower((unsigned char)c);
    return t == "true" || t == "yes" || t == "on" || t == "1";
}
std::vector<int> parseIntList(const std::string& v) {
    std::vector<int> out;
    std::string t = v;
    for (auto& c : t) if (c == '[' || c == ']' || c == ',') c = ' ';
    std::istringstream iss(t);
    int x;
    while (iss >> x) out.push_back(x);
    return out;
}

bool readConfig(const std::string& path, Cfg& cfg, std::string& err) {
    std::ifstream f(path);
    if (!f.is_open()) { err = "Cannot open " + path; return false; }
    std::string line;
    std::string section;  // "" / "quality" / "patch" / "improve" / "tetgen"
    int sectionIndent = -1;
    while (std::getline(f, line)) {
        // strip comment
        size_t hash = line.find('#');
        if (hash != std::string::npos) line = line.substr(0, hash);
        if (line.find_first_not_of(" \t\r\n") == std::string::npos) continue;

        // determine indent (count leading spaces)
        int indent = 0;
        while (indent < (int)line.size() && (line[indent] == ' ' || line[indent] == '\t'))
            ++indent;
        std::string body = trim(line);
        size_t colon = body.find(':');
        if (colon == std::string::npos) continue;
        std::string key = trim(body.substr(0, colon));
        std::string val = stripQuotes(trim(body.substr(colon + 1)));

        // Section start: top-level key with empty value -> opens section
        if (indent == 0) {
            section.clear();
            sectionIndent = -1;
            if (val.empty() &&
                (key == "quality" || key == "patch" || key == "improve" ||
                 key == "tetgen" || key == "selection" || key == "iterate")) {
                section = key;
                sectionIndent = 0;
                continue;
            }
        } else if (sectionIndent < 0 || indent <= sectionIndent) {
            section.clear();
        }

        // Top-level keys
        if (section.empty()) {
            if      (key == "model")        cfg.model = val;
            else if (key == "output")       cfg.output = val;
            else if (key == "backend")      cfg.backend = val;
            else if (key == "fallback")     cfg.fallback = val;
            else if (key == "report_only")  cfg.reportOnly = parseBool(val);
            else if (key == "target_pids")  cfg.targetPids = parseIntList(val);
            // Convenience: top-level selection_mode / element_ids /
            // ring_mode / iterate (without nesting under section)
            else if (key == "selection_mode") cfg.selectionMode = val;
            else if (key == "element_ids")    cfg.selectedElementIds = parseIntList(val);
            else if (key == "ring_mode")      cfg.ringMode = val;
            else if (key == "iterate")      { /* may also be section header */
                // bool form: iterate: true
                if (!val.empty()) cfg.iterate = parseBool(val);
            }
            continue;
        }

        // Section keys
        if (section == "selection") {
            if      (key == "mode")              cfg.selectionMode = val;
            else if (key == "element_ids")       cfg.selectedElementIds = parseIntList(val);
            else if (key == "ring_mode")         cfg.ringMode = val;
            else if (key == "ring_expand")       cfg.ringExpand = std::stoi(val);
        } else if (section == "iterate") {
            cfg.iterate = true;  // any sub-key under section enables it
            if      (key == "max_iterations")   cfg.iterMax = std::stoi(val);
            else if (key == "quality_target")   cfg.iterTarget = std::stod(val);
            else if (key == "convergence_tol")  cfg.iterConvergenceTol = std::stod(val);
            else if (key == "keep_best")        cfg.iterKeepBest = parseBool(val);
        } else if (section == "quality") {
            if      (key == "min_jacobian")     cfg.minJacobian = std::stod(val);
            else if (key == "max_aspect_ratio") cfg.maxAspectRatio = std::stod(val);
        } else if (section == "patch") {
            if      (key == "ring_expand")            cfg.ringExpand = std::stoi(val);
            else if (key == "surface_flatness_deg")   cfg.surfaceFlatnessDeg = std::stod(val);
            else if (key == "surface_move_tolerance") cfg.surfaceMoveTolerance = std::stod(val);
            else if (key == "preserve_multi_material") cfg.preserveMultiMaterial = parseBool(val);
        } else if (section == "improve") {
            if      (key == "laplacian_iters")  cfg.laplacianIters = std::stoi(val);
            else if (key == "max_outer_iters")  cfg.maxOuterIters = std::stoi(val);
            else if (key == "allow_subdivide")  cfg.allowSubdivide = parseBool(val);
        } else if (section == "tetgen") {
            if      (key == "quality_ratio")    cfg.tetgenQualityRatio = std::stod(val);
            else if (key == "min_dihedral_deg") cfg.tetgenMinDihedral  = std::stod(val);
        }
    }
    if (cfg.model.empty() || cfg.output.empty()) {
        err = "Required keys missing: model, output";
        return false;
    }
    return true;
}

}  // anonymous namespace

int runTetRemesh(const std::string& configPath,
                 const KooRemapper::ConsoleOutput& console) {
    using namespace KooRemapper;
    using namespace KooRemapper::remesh;

    Cfg cfg;
    std::string err;
    if (!readConfig(configPath, cfg, err)) {
        console.error("tetremesh config: " + err);
        return 1;
    }

    Timer timer;

    console.info("Loading mesh: " + cfg.model);
    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(cfg.model);
    } catch (const std::exception& e) {
        console.error(std::string("Failed to load mesh: ") + e.what());
        return 1;
    }
    console.success("Loaded " + std::to_string(mesh.getNodeCount()) + " nodes, " +
                   std::to_string(mesh.getElementCount()) + " elements");

    PatchExtractor::Config pc;
    pc.targetPids            = cfg.targetPids;
    pc.minJacobianThreshold  = cfg.minJacobian;
    pc.maxAspectRatio        = cfg.maxAspectRatio;
    pc.ringExpand            = cfg.ringExpand;
    pc.surfaceFlatnessDeg    = cfg.surfaceFlatnessDeg;
    pc.surfaceMoveTolerance  = cfg.surfaceMoveTolerance;
    pc.preserveMultiMaterial = cfg.preserveMultiMaterial;
    pc.laplacianIters        = cfg.laplacianIters;
    pc.maxOuterIters         = cfg.maxOuterIters;
    pc.allowSubdivide        = cfg.allowSubdivide;
    pc.tetgenQualityRatio    = cfg.tetgenQualityRatio;
    pc.tetgenMinDihedral     = cfg.tetgenMinDihedral;

    // selection mode
    {
        std::string sm = cfg.selectionMode;
        for (auto& c : sm) c = (char)std::tolower((unsigned char)c);
        if (sm == "explicit_ids" || sm == "explicit") {
            pc.selectionMode = PatchExtractor::SelectionMode::EXPLICIT_IDS;
            pc.selectedElementIds = cfg.selectedElementIds;
            if (cfg.selectedElementIds.empty()) {
                console.warning("selection_mode=explicit_ids but element_ids list is empty");
            }
        } else {
            pc.selectionMode = PatchExtractor::SelectionMode::BAD_QUALITY;
        }
    }
    {
        std::string rm = cfg.ringMode;
        for (auto& c : rm) c = (char)std::tolower((unsigned char)c);
        pc.ringMode = (rm == "face")
            ? PatchExtractor::RingMode::FACE
            : PatchExtractor::RingMode::NODE;
    }

    auto makeBackend = [](std::string key) -> std::shared_ptr<Remesher> {
        for (auto& c : key) c = (char)std::tolower((unsigned char)c);
        if (key == "tetgen")     return std::make_shared<TetGenRemesher>();
        if (key == "localimprove" || key.empty())
                                  return std::make_shared<LocalImproveRemesher>();
        return nullptr;
    };

    auto backend  = makeBackend(cfg.backend);
    auto fallback = cfg.fallback.empty() ? nullptr : makeBackend(cfg.fallback);
    if (!backend) {
        console.error("Unknown backend: " + cfg.backend);
        return 1;
    }
    console.info("Backend: " + std::string(backend->name()) +
                 (fallback ? std::string("  fallback=") + fallback->name() : ""));

    RemeshOrchestrator orch(pc, backend, fallback);
    RemeshSummary summary;
    if (cfg.reportOnly) {
        console.info("Report-only mode: scanning quality, no mesh changes will be written.");
        summary = orch.report(mesh);
    } else if (cfg.iterate) {
        // Iterative driver: keep remeshing until quality target met or
        // max iterations exhausted. Emits per-iteration summary inline.
        RemeshOrchestrator::IterativeOptions iopts;
        iopts.maxIterations  = cfg.iterMax;
        iopts.qualityTarget  = cfg.iterTarget;
        iopts.convergenceTol = cfg.iterConvergenceTol;
        iopts.keepBest       = cfg.iterKeepBest;
        iopts.verbose        = true;
        console.info("Iterative remesh: max=" + std::to_string(iopts.maxIterations) +
                     "  target=" + std::to_string(iopts.qualityTarget) +
                     "  keepBest=" + (iopts.keepBest ? "yes" : "no"));
        auto ires = orch.runIterative(mesh, iopts);
        // Use the best-iteration summary as the "primary" reported summary.
        if (ires.bestIteration >= 0 &&
            ires.bestIteration < (int)ires.perIteration.size()) {
            summary = ires.perIteration[ires.bestIteration];
        } else if (!ires.perIteration.empty()) {
            summary = ires.perIteration.back();
        }
        std::cout << "\n";
        console.header("Iterative Driver Result");
        console.keyValue("Iterations run",     std::to_string(ires.iterationsRun));
        console.keyValue("Best iteration",     std::to_string(ires.bestIteration + 1));
        {
            std::ostringstream m; m << ires.bestMinJac;
            console.keyValue("Best min Jacobian", m.str());
        }
        console.keyValue("Target reached",     ires.targetReached ? "yes" : "no");
        // Print every iteration's brief stats
        for (size_t i = 0; i < ires.perIteration.size(); ++i) {
            const auto& s = ires.perIteration[i];
            std::ostringstream m;
            m << "iter " << (i + 1) << ": patches=" << s.patchCount
              << "  succeed=" << s.patchSucceeded
              << "  minJac " << s.minJacBefore << " -> " << s.minJacAfter;
            console.println("  " + m.str());
        }
    } else {
        summary = orch.run(mesh);
    }

    std::cout << "\n";
    console.header("TET Remesh Summary");
    console.keyValue("Patches found",     std::to_string(summary.patchCount));
    console.keyValue("Patches succeeded", std::to_string(summary.patchSucceeded));
    if (summary.patchFailed > 0) {
        console.warning("Patches failed: " + std::to_string(summary.patchFailed));
    }
    console.keyValue("Elements removed",  std::to_string(summary.elementsRemoved));
    console.keyValue("Elements added",    std::to_string(summary.elementsAdded));
    console.keyValue("Nodes added",       std::to_string(summary.nodesAdded));
    {
        std::ostringstream b, a;
        b << summary.minJacBefore;
        a << summary.minJacAfter;
        console.keyValue("Min jacobian (before)", b.str());
        console.keyValue("Min jacobian (after)",  a.str());
    }
    for (const auto& m : summary.messages) {
        console.println("  " + m);
    }

    if (cfg.reportOnly) {
        console.info("Report-only: skipping output write.");
    } else {
        console.info("Writing: " + cfg.output);
        KFileWriter writer;
        if (!writer.writeFile(cfg.output, mesh, /*useMappedPositions=*/false)) {
            console.error("Failed to write output: " + writer.getErrorMessage());
            return 1;
        }
        console.success("Output written");
    }

    timer.stop();
    console.info("Total time: " + timer.elapsedString());
    return 0;
}
