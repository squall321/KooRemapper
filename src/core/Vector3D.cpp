#include "core/Vector3D.h"
#include <sstream>
#include <iomanip>

namespace KooRemapper {

std::string Vector3D::toString() const {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(6);
    oss << "(" << x << ", " << y << ", " << z << ")";
    return oss.str();
}

std::ostream& operator<<(std::ostream& os, const Vector3D& v) {
    os << v.toString();
    return os;
}

} // namespace KooRemapper
