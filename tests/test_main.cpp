#include "TestFramework.h"

// Include all test files
#include "test_Vector3D.cpp"
#include "test_Mesh.cpp"
#include "test_Interpolation.cpp"
#include "test_Mapping.cpp"

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    return KooRemapper::Test::TestFramework::instance().runAll();
}
