#include "matswap.h"
#include "kw_util.h"
#include "optimize.h"
#include "cli/ConsoleOutput.h"
#include "assembly/ModelAssembler.h"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <stdexcept>

using namespace KooRemapper;

// =====================================================================
// msw_* helpers
// =====================================================================

static std::string msw_idType(const std::string& name) {
    std::string u = kw_upper(name);
    if (u.size() >= 5 && u.substr(0,5) == "SECID") return "SECID";
    if (u.size() >= 4 && u.substr(0,4) == "HGID")  return "HGID";
    if (u.size() >= 4 && u.substr(0,4) == "LCID")  return "LCID";
    if (u.size() >= 3 && u.substr(0,3) == "MID")   return "MID";
    if (u.size() >= 3 && u.substr(0,3) == "PID")   return "PID";
    return "";
}

struct MswParam { char type; std::string name; int ivalue; };

struct MswBundle {
    std::vector<MswParam>     params;
    std::vector<std::string>  cards;  // all lines except *PARAMETER, *PART, *END
    int bundlePid=0, bundleSecid=0, bundleMid=0, bundleHgid=0;
};

struct MswPartInfo { int pid=0,secid=0,mid=0,hgid=0,dataLine=-1; };

static int msw_resolveInt(const std::string& tok, const std::vector<MswParam>& params) {
    if (!tok.empty() && tok[0]=='&') {
        std::string nm = kw_upper(tok.substr(1));
        for (const auto& p : params) if (kw_upper(p.name)==nm) return p.ivalue;
        return 0;
    }
    try { return std::stoi(tok); } catch(...){ return 0; }
}

static MswBundle msw_parseBundle(const std::string& path) {
    MswBundle bnd;
    std::ifstream f(path);
    if (!f.is_open()) throw std::runtime_error("Cannot open bundle: " + path);

    enum Sec { OTHER, PARAM, PART } sec = OTHER;
    bool partTitle=false, partData=false;
    std::string ln;

    while (std::getline(f, ln)) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) { if (sec==OTHER) bnd.cards.push_back(ln); continue; }

        if (tr[0] == '*') {
            std::string up = kw_upper(tr);
            if (up=="*PARAMETER" || up.rfind("*PARAMETER_",0)==0 || up.rfind("*PARAMETER ",0)==0)
                { sec=PARAM; continue; }
            if (up=="*PART")
                { sec=PART; partTitle=false; partData=false; continue; }
            if (up=="*END") { sec=OTHER; continue; }
            sec=OTHER;
            bnd.cards.push_back(ln);
            continue;
        }
        if (tr[0]=='$') { if (sec==OTHER) bnd.cards.push_back(ln); continue; }

        if (sec==PARAM) {
            auto toks = kw_tok10(ln);
            for (size_t i=0; i+1<toks.size(); i+=2) {
                const auto& nf = toks[i];
                if (nf.size() < 2) continue;
                MswParam p;
                p.type  = (char)std::toupper((unsigned char)nf[0]);
                p.name  = kw_trim(nf.substr(1));
                p.ivalue = 0;
                if (p.name.empty()) continue;
                try {
                    if      (p.type=='I') p.ivalue = std::stoi(toks[i+1]);
                    else if (p.type=='R') p.ivalue = (int)std::stod(toks[i+1]);
                } catch(...) {}
                bnd.params.push_back(p);
            }
        } else if (sec==PART) {
            if (!partTitle) { partTitle=true; continue; }
            if (!partData) {
                auto toks = kw_tok10(ln);
                if (toks.size()>=5) {
                    bnd.bundlePid   = msw_resolveInt(toks[0], bnd.params);
                    bnd.bundleSecid = msw_resolveInt(toks[1], bnd.params);
                    bnd.bundleMid   = msw_resolveInt(toks[2], bnd.params);
                    bnd.bundleHgid  = msw_resolveInt(toks[4], bnd.params);
                }
                partData=true;
            }
        } else {
            bnd.cards.push_back(ln);
        }
    }
    return bnd;
}

static int msw_scanMaxId(const std::vector<std::string>& lines,
                          const std::string& prefix) {
    int maxId=0;
    bool active=false; bool hasTitle=false; bool titleDone=false;
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = kw_upper(tr);
            if (up.rfind(prefix,0)==0) {
                active=true;
                hasTitle=(up.find("_TITLE")!=std::string::npos);
                titleDone=!hasTitle;
            } else { active=false; }
            continue;
        }
        if (!active || tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = kw_tok10(ln);
        if (!toks.empty()) { try { int id=std::stoi(toks[0]); if(id>maxId) maxId=id; } catch(...){} }
        active=false;
    }
    return maxId;
}

static MswPartInfo msw_getPartInfo(const std::vector<std::string>& lines, int targetPid) {
    MswPartInfo info;
    bool inPart=false; bool titleDone=false;
    for (int i=0; i<(int)lines.size(); ++i) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=kw_upper(tr);
            inPart=(up=="*PART"||up=="*PART_TITLE"); titleDone=false; continue;
        }
        if (!inPart || tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = kw_tok10(lines[i]);
        if (toks.size()>=5) {
            try {
                int pid=std::stoi(toks[0]);
                if (pid==targetPid) {
                    info.pid=pid; info.secid=std::stoi(toks[1]);
                    info.mid=std::stoi(toks[2]); info.hgid=std::stoi(toks[4]);
                    info.dataLine=i; return info;
                }
            } catch(...) {}
        }
        titleDone=false;
    }
    return info;
}

static bool msw_isShared(const std::vector<std::string>& lines,
                          int fieldIdx, int targetId, int excludePid) {
    bool inPart=false; bool titleDone=false;
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=kw_upper(tr);
            inPart=(up=="*PART"||up=="*PART_TITLE"); titleDone=false; continue;
        }
        if (!inPart || tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = kw_tok10(ln);
        if ((int)toks.size()>fieldIdx) {
            try {
                int pid=std::stoi(toks[0]);
                if (pid==excludePid) { titleDone=false; continue; }
                if (std::stoi(toks[fieldIdx])==targetId) return true;
            } catch(...) {}
        }
        titleDone=false;
    }
    return false;
}

static std::vector<std::string> msw_removeBlock(
        const std::vector<std::string>& lines,
        const std::string& prefix, int targetId) {
    std::vector<bool> rm(lines.size(), false);

    for (int i=0; i<(int)lines.size(); ) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty() || tr[0]!='*') { ++i; continue; }
        std::string up = kw_upper(tr);
        if (up.rfind(prefix,0)!=0) { ++i; continue; }

        bool hasTitle=(up.find("_TITLE")!=std::string::npos);
        int titlesLeft=hasTitle?1:0, id=-1;

        for (int j=i+1; j<(int)lines.size(); ++j) {
            std::string jt = kw_trim(lines[j]);
            if (jt.empty()||jt[0]=='$') continue;
            if (jt[0]=='*') break;
            if (titlesLeft-->0) continue;
            auto toks=kw_tok10(lines[j]);
            if (!toks.empty()) { try{id=std::stoi(toks[0]);}catch(...){} }
            break;
        }
        if (id!=targetId) { ++i; continue; }

        int start=i, end=i+1;
        while (end<(int)lines.size()) {
            std::string et=kw_trim(lines[end]);
            if (!et.empty()&&et[0]=='*') break;
            ++end;
        }
        for (int k=start;k<end;++k) rm[k]=true;
        i=end;
    }

    std::vector<std::string> out;
    for (int i=0;i<(int)lines.size();++i) if (!rm[i]) out.push_back(lines[i]);
    return out;
}

static std::string msw_resolveLine(const std::string& line,
        const std::vector<std::pair<std::string,int>>& sortedRemap) {
    std::string r = line;
    for (const auto& kv : sortedRemap) {
        std::string pat = "&" + kv.first;
        int patLen = (int)pat.size();
        std::string val = std::to_string(kv.second);
        std::string repl = ((int)val.size()<=patLen)
            ? std::string(patLen-(int)val.size(),' ')+val : val;
        size_t pos=0;
        while ((pos=r.find(pat,pos))!=std::string::npos) {
            r.replace(pos,patLen,repl);
            pos+=repl.size();
        }
    }
    return r;
}

static std::string msw_updatePartLine(const std::string& ln,
                                       int newSecid, int newMid, int newHgid) {
    std::string r = ln;
    while ((int)r.size()<50) r+=' ';
    auto setF = [&](int start, int w, int v) {
        std::string vs=std::to_string(v);
        if ((int)vs.size()>w) vs=vs.substr(vs.size()-w);
        r.replace(start, w, std::string(w-(int)vs.size(),' ')+vs);
    };
    setF(10,10,newSecid); setF(20,10,newMid); setF(40,10,newHgid);
    return r;
}

// =====================================================================
// runMatswap — legacy positional-args interface
// =====================================================================

int runMatswap(const std::string& modelFile, const std::string& bundleFile,
               int targetPid, const std::string& outputFile,
               ConsoleOutput& console) {

    console.println("[matswap] Model  : " + modelFile);
    console.println("[matswap] Bundle : " + bundleFile);
    console.println("[matswap] Target PID: " + std::to_string(targetPid));

    // 1. Read model
    std::vector<std::string> modelLines;
    {
        std::ifstream f(modelFile);
        if (!f.is_open()) { console.error("Cannot open model: " + modelFile); return 1; }
        std::string ln; while (std::getline(f,ln)) modelLines.push_back(ln);
    }

    // 2. Parse bundle
    MswBundle bundle;
    try { bundle = msw_parseBundle(bundleFile); }
    catch (const std::exception& e) { console.error(std::string(e.what())); return 1; }

    console.println("[matswap] Bundle cards: " + std::to_string(bundle.cards.size()) +
                    "  params: " + std::to_string(bundle.params.size()));
    console.println("[matswap] Bundle PART -> MID=" + std::to_string(bundle.bundleMid) +
                    " SECID=" + std::to_string(bundle.bundleSecid) +
                    " HGID=" + std::to_string(bundle.bundleHgid));

    // 3. Get target PART info
    MswPartInfo tp = msw_getPartInfo(modelLines, targetPid);
    if (tp.dataLine < 0) {
        console.error("PID " + std::to_string(targetPid) + " not found in model");
        return 1;
    }
    console.println("[matswap] Current PART " + std::to_string(targetPid) +
                    " -> MID=" + std::to_string(tp.mid) +
                    " SECID=" + std::to_string(tp.secid) +
                    " HGID=" + std::to_string(tp.hgid));

    // 4. Check which IDs are shared with other PARTs
    bool hgidShared  = msw_isShared(modelLines, 4, tp.hgid,  targetPid);
    bool secidShared = msw_isShared(modelLines, 1, tp.secid, targetPid);
    bool midShared   = msw_isShared(modelLines, 2, tp.mid,   targetPid);
    console.println("[matswap] ID sharing -> MID:" + std::string(midShared?"shared":"orphan") +
                    "  SECID:" + std::string(secidShared?"shared":"orphan") +
                    "  HGID:" + std::string(hgidShared?"shared":"orphan"));

    // 5. Scan model for max IDs (for new ID allocation)
    int maxHGID  = msw_scanMaxId(modelLines, "*HOURGLASS");
    int maxLCID  = msw_scanMaxId(modelLines, "*DEFINE_CURVE");
    int maxSECID = msw_scanMaxId(modelLines, "*SECTION");
    int maxMID   = msw_scanMaxId(modelLines, "*MAT_");
    console.println("[matswap] Model max IDs -> HGID=" + std::to_string(maxHGID) +
                    " LCID=" + std::to_string(maxLCID) +
                    " SECID=" + std::to_string(maxSECID) +
                    " MID=" + std::to_string(maxMID));

    // 6. Build remap table: &PARAM_NAME -> new integer value
    std::map<std::string,int> remap;
    for (const auto& p : bundle.params) {
        if (p.type!='I' && p.type!='R') continue;
        std::string idt = msw_idType(p.name);
        int newVal;
        if      (idt=="HGID")  newVal = ++maxHGID;
        else if (idt=="LCID")  newVal = ++maxLCID;
        else if (idt=="SECID") newVal = ++maxSECID;
        else if (idt=="MID")   newVal = midShared ? ++maxMID : tp.mid;
        else if (idt=="PID")   continue;
        else                   newVal = p.ivalue;
        remap[p.name] = newVal;
        console.println("[matswap]   &" + p.name + " (" + idt + ") " +
                        std::to_string(p.ivalue) + " -> " + std::to_string(newVal));
    }

    // Sort by name length descending to avoid prefix collisions
    std::vector<std::pair<std::string,int>> sortedRemap(remap.begin(), remap.end());
    std::sort(sortedRemap.begin(), sortedRemap.end(),
              [](const auto& a, const auto& b){ return a.first.size() > b.first.size(); });

    // 7. Resolve bundle cards
    std::vector<std::string> resolvedCards;
    for (const auto& c : bundle.cards)
        resolvedCards.push_back(msw_resolveLine(c, sortedRemap));

    // 8. Remove orphaned old cards from model
    if (!hgidShared  && tp.hgid >0) {
        modelLines = msw_removeBlock(modelLines, "*HOURGLASS", tp.hgid);
        console.println("[matswap] Removed *HOURGLASS HGID=" + std::to_string(tp.hgid));
    }
    if (!secidShared && tp.secid>0) {
        modelLines = msw_removeBlock(modelLines, "*SECTION",   tp.secid);
        console.println("[matswap] Removed *SECTION SECID=" + std::to_string(tp.secid));
    }
    if (!midShared   && tp.mid  >0) {
        modelLines = msw_removeBlock(modelLines, "*MAT_",      tp.mid);
        console.println("[matswap] Removed *MAT_ MID=" + std::to_string(tp.mid));
    }

    // 9. Update target PART data line with new IDs
    int newSecid=tp.secid, newMid=tp.mid, newHgid=tp.hgid;
    for (const auto& p : bundle.params) {
        if (!remap.count(p.name)) continue;
        std::string idt = msw_idType(p.name);
        if (idt=="SECID") newSecid = remap.at(p.name);
        if (idt=="MID")   newMid   = remap.at(p.name);
        if (idt=="HGID")  newHgid  = remap.at(p.name);
    }
    MswPartInfo tp2 = msw_getPartInfo(modelLines, targetPid);
    if (tp2.dataLine >= 0) {
        modelLines[tp2.dataLine] = msw_updatePartLine(modelLines[tp2.dataLine],
                                                      newSecid, newMid, newHgid);
        console.println("[matswap] Updated PART " + std::to_string(targetPid) +
                        " -> SECID=" + std::to_string(newSecid) +
                        " MID=" + std::to_string(newMid) +
                        " HGID=" + std::to_string(newHgid));
    }

    // 10. Insert resolved bundle cards just before *END
    std::vector<std::string> output;
    bool inserted = false;
    for (const auto& ln : modelLines) {
        if (!inserted && kw_upper(kw_trim(ln))=="*END") {
            for (const auto& c : resolvedCards) output.push_back(c);
            inserted = true;
        }
        output.push_back(ln);
    }
    if (!inserted) for (const auto& c : resolvedCards) output.push_back(c);

    // 11. Write output file
    {
        std::ofstream fout(outputFile);
        if (!fout.is_open()) { console.error("Cannot write: " + outputFile); return 1; }
        for (const auto& ln : output) fout << ln << "\n";
    }
    console.println("[matswap] Done -> " + outputFile);
    return 0;
}

// =====================================================================
// runMatswapYaml — YAML-based interface (multiple swaps + optimize)
// =====================================================================

int runMatswapYaml(const std::string& yamlFile, ConsoleOutput& console) {
    // Simple YAML parser for matswap config
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    // Config directory for relative paths
    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    auto trim = [](const std::string& s) -> std::string {
        size_t a=0, b=s.size();
        while (a<b && std::isspace((unsigned char)s[a])) ++a;
        while (b>a && std::isspace((unsigned char)s[b-1])) --b;
        return s.substr(a,b-a);
    };
    auto countIndent = [](const std::string& s) -> int {
        int n=0; while (n<(int)s.size() && s[n]==' ') ++n; return n;
    };

    std::string modelFile, outputFile;
    std::string optimizeMode;
    double optimizeTssfac = 0.67;
    std::string optimizeAnalysisType;
    std::vector<MatswapOperation> swaps;
    bool inSwapsList = false;
    int swapsIndent = 0;
    bool inSwapItem = false;
    int swapItemIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        int indent = countIndent(ln);

        // New swap item
        if (inSwapsList && indent > swapsIndent && tr[0]=='-') {
            swaps.push_back(MatswapOperation{});
            inSwapItem = true;
            swapItemIndent = indent;
            std::string rest = trim(tr.substr(1));
            size_t cp = rest.find(':');
            if (cp != std::string::npos) {
                std::string key = trim(rest.substr(0,cp));
                std::string val = trim(rest.substr(cp+1));
                auto parseIL = [&](const std::string& v, std::vector<int>& out) {
                    std::string lv=v;
                    if (!lv.empty()&&lv.front()=='[') lv=lv.substr(1);
                    if (!lv.empty()&&lv.back()==']') lv.pop_back();
                    std::istringstream ss(lv); std::string tok;
                    while (std::getline(ss,tok,',')) { std::string t=trim(tok); if(!t.empty()) try{ out.push_back(std::stoi(t)); }catch(...){} }
                };
                if (key=="bundle") swaps.back().bundleFile = val;
                else if (key=="swap_all") swaps.back().swapAll = (val=="true"||val=="yes"||val=="1");
                else if (key=="pid")  swaps.back().pids = { std::stoi(val) };
                else if (key=="pids") parseIL(val, swaps.back().pids);
                else if (key=="mid")  swaps.back().mids = { std::stoi(val) };
                else if (key=="mids") parseIL(val, swaps.back().mids);
            }
            continue;
        }

        // Sub-keys of current swap item
        if (inSwapItem && !swaps.empty() && indent > swapItemIndent) {
            size_t cp = tr.find(':');
            if (cp != std::string::npos) {
                std::string key = trim(tr.substr(0,cp));
                std::string val = trim(tr.substr(cp+1));
                auto parseIL = [&](const std::string& v, std::vector<int>& out) {
                    std::string lv=v;
                    if (!lv.empty()&&lv.front()=='[') lv=lv.substr(1);
                    if (!lv.empty()&&lv.back()==']') lv.pop_back();
                    std::istringstream ss(lv); std::string tok;
                    while (std::getline(ss,tok,',')) { std::string t=trim(tok); if(!t.empty()) try{ out.push_back(std::stoi(t)); }catch(...){} }
                };
                try {
                    if (key=="bundle") swaps.back().bundleFile = val;
                    else if (key=="swap_all") swaps.back().swapAll=(val=="true"||val=="yes"||val=="1");
                    else if (key=="pid")  swaps.back().pids = { std::stoi(val) };
                    else if (key=="pids") parseIL(val, swaps.back().pids);
                    else if (key=="mid")  swaps.back().mids = { std::stoi(val) };
                    else if (key=="mids") parseIL(val, swaps.back().mids);
                } catch(...) {}
            }
            continue;
        }

        // Exit lists if indent drops
        if (inSwapsList && indent <= swapsIndent) { inSwapsList=false; inSwapItem=false; }

        // Top-level keys
        size_t cp = tr.find(':');
        if (cp != std::string::npos) {
            std::string key = trim(tr.substr(0,cp));
            std::string val = trim(tr.substr(cp+1));
            auto parseIL = [&](const std::string& v, std::vector<int>& out) {
                std::string lv=v;
                if (!lv.empty()&&lv.front()=='[') lv=lv.substr(1);
                if (!lv.empty()&&lv.back()==']') lv.pop_back();
                std::istringstream ss(lv); std::string tok;
                while (std::getline(ss,tok,',')) { std::string t=trim(tok); if(!t.empty()) try{ out.push_back(std::stoi(t)); }catch(...){} }
            };
            if      (key=="model")  modelFile  = val;
            else if (key=="output") outputFile = val;
            else if (key=="swaps")  { inSwapsList=true; swapsIndent=indent; }
            else if (key=="bundle") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                swaps.back().bundleFile = val;
            }
            else if (key=="pid") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                swaps.back().pids = { std::stoi(val) };
            }
            else if (key=="pids") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                parseIL(val, swaps.back().pids);
            }
            else if (key=="mid") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                swaps.back().mids = { std::stoi(val) };
            }
            else if (key=="mids") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                parseIL(val, swaps.back().mids);
            }
            else if (key=="swap_all") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                swaps.back().swapAll = (val=="true"||val=="yes"||val=="1");
            }
            else if (key=="optimize")       optimizeMode = val;
            else if (key=="tssfac")         { try { optimizeTssfac = std::stod(val); } catch(...) {} }
            else if (key=="analysis_type")  optimizeAnalysisType = val;
        }
    }

    if (modelFile.empty())  { console.error("matswap YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("matswap YAML: 'output' not specified"); return 1; }
    if (swaps.empty())      { console.error("matswap YAML: no swaps defined");        return 1; }

    console.println("[matswap] Model  : " + modelFile);
    console.println("[matswap] Output : " + outputFile);
    console.println("[matswap] Swaps  : " + std::to_string(swaps.size()));

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelFile)) {
        console.error(assembler.getErrorMessage()); return 1;
    }

    for (size_t i=0; i<swaps.size(); ++i) {
        console.println("[matswap] --- Swap " + std::to_string(i+1) + "/" + std::to_string(swaps.size()) + " ---");
        if (!assembler.applyMatswap(swaps[i], configDir)) {
            console.error(assembler.getErrorMessage()); return 1;
        }
        for (const auto& msg : assembler.infoMessages) console.println(msg);
        assembler.infoMessages.clear();
    }

    // writeOutput appends ".k" - strip trailing ".k" from outputFile if present
    std::string outputPrefix = outputFile;
    if (outputPrefix.size() >= 2 &&
        outputPrefix.substr(outputPrefix.size()-2) == ".k") {
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);
    }

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage()); return 1;
    }
    console.println("[matswap] Done -> " + outputPrefix + ".k");

    // Apply optimize if specified
    if (!optimizeMode.empty()) {
        console.println("");
        console.println("[optimize] Applying '" + optimizeMode + "' optimization...");

        OptimizeConfig optCfg;
        optCfg.mode = optimizeMode;
        optCfg.tssfac = optimizeTssfac;
        optCfg.analysisType = optimizeAnalysisType;
        for (const auto& sw : swaps) {
            for (int pid : sw.pids) optCfg.pids.push_back(pid);
        }

        std::string outputPath = outputPrefix + ".k";
        std::vector<std::string> lines;
        {
            std::ifstream fin(outputPath);
            if (!fin.is_open()) { console.error("Cannot re-read: " + outputPath); return 1; }
            std::string l;
            while (std::getline(fin, l)) {
                if (!l.empty() && l.back()=='\r') l.pop_back();
                lines.push_back(l);
            }
        }

        std::vector<std::string> msgs;
        if (optCfg.mode == "rubber") {
            msgs = opt_applyRubber(lines, optCfg);
        } else {
            console.error("Unknown optimize mode: " + optCfg.mode);
            return 1;
        }
        for (const auto& m : msgs) console.println(m);

        {
            std::ofstream fout(outputPath);
            if (!fout.is_open()) { console.error("Cannot write: " + outputPath); return 1; }
            for (const auto& l : lines) fout << l << "\n";
        }
        console.println("[optimize] Done -> " + outputPath);
    }

    return 0;
}
