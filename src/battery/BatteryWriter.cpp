#include "BatteryWriter.h"
#include <vector>
#include <ostream>
#include <cstdio>

namespace bat {

void writeSetNodeList(std::ostream& out, int sid,
                      const std::string& title,
                      const std::vector<int>& nids) {
    out << "*SET_NODE_LIST_TITLE\n"
        << title << "\n"
        << iField(sid) << "\n";
    int count = 0;
    for (int nid : nids) {
        out << iField(nid);
        if (++count % 8 == 0) out << "\n";
    }
    if (count % 8 != 0) out << "\n";
}

void writeSetPartList(std::ostream& out, int sid,
                      const std::string& title,
                      const std::vector<int>& pids) {
    out << "*SET_PART_LIST_TITLE\n"
        << title << "\n"
        << iField(sid) << "\n";
    int count = 0;
    for (int pid : pids) {
        out << iField(pid);
        if (++count % 8 == 0) out << "\n";
    }
    if (count % 8 != 0) out << "\n";
}

void writeDefineCurve(std::ostream& out, int lcid,
                      const std::string& title,
                      const std::vector<std::pair<double,double>>& pts) {
    out << "*DEFINE_CURVE_TITLE\n"
        << title << "\n"
        << "$#  lcid    sidr     sfa     sfo    offa    offo  dattyp\n"
        << iField(lcid) << iField(0)  // SIDR=0
        << fldG(1.0) << fldG(1.0)     // SFA SFO
        << fldG(0.0) << fldG(0.0)     // OFFA OFFO
        << iField(0) << "\n";         // DATTYP
    out << "$#                a1                  o1\n";
    for (const auto& p : pts) {
        char buf[64];
        snprintf(buf, sizeof(buf), "%20.6E%20.6E\n", p.first, p.second);
        out << buf;
    }
}

} // namespace bat
