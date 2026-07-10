cmake_minimum_required(VERSION 3.16)
project(KooRemapper VERSION 1.4.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# Cross-platform compiler settings
if(MSVC)
    add_compile_options(/W4 /utf-8)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
    # Use static runtime for easier distribution
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Platform definitions
if(WIN32)
    add_definitions(-DPLATFORM_WINDOWS)
elseif(APPLE)
    add_definitions(-DPLATFORM_MACOS)
else()
    add_definitions(-DPLATFORM_LINUX)
endif()

# OpenMP support for parallel processing
find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    message(STATUS "OpenMP: Found (version ${OpenMP_CXX_VERSION})")
else()
    message(STATUS "OpenMP: Not found - parallel processing disabled")
endif()

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/include)

# Source files - Core
set(CORE_SOURCES
    src/core/Vector3D.cpp
    src/core/Node.cpp
    src/core/Element.cpp
    src/core/Mesh.cpp
    src/core/Platform.cpp
    src/core/ShellMesh.cpp
)

# Source files - Parser
set(PARSER_SOURCES
    src/parser/KFileReader.cpp
    src/parser/KFileWriter.cpp
    src/parser/DynainWriter.cpp
    src/parser/ShellReader.cpp
)

# Source files - Grid
set(GRID_SOURCES
    src/grid/ConnectivityAnalyzer.cpp
    src/grid/StructuredGridIndexer.cpp
    src/grid/BoundaryExtractor.cpp
    src/grid/EdgeCalculator.cpp
    src/grid/NeutralGridGenerator.cpp
)

# Source files - Mapper
set(MAPPER_SOURCES
    src/mapper/EdgeInterpolator.cpp
    src/mapper/FaceInterpolator.cpp
    src/mapper/ParametricMapper.cpp
    src/mapper/UnstructuredMeshAnalyzer.cpp
    src/mapper/MeshRemapper.cpp
    src/mapper/FlatMeshGenerator.cpp
    src/mapper/ShellUnfolder.cpp
    src/mapper/ShellMapper.cpp
)

# Source files - Example
set(EXAMPLE_SOURCES
    src/example/ExampleMeshGenerator.cpp
)

# Source files - Generator
set(GENERATOR_SOURCES
    src/generator/YamlConfigReader.cpp
    src/generator/VariableDensityMeshGenerator.cpp
    src/generator/CurveInterpolator.cpp
    src/generator/CurvedMeshGenerator.cpp
)

# Source files - Analysis
set(ANALYSIS_SOURCES
    src/analysis/StrainCalculator.cpp
    src/analysis/DeformationGradient.cpp
    src/analysis/StrainTensor.cpp
    src/analysis/StressTensor.cpp
    src/analysis/MaterialModel.cpp
    src/analysis/ElementAnalyzer.cpp
)

# Source files - Squeeze
set(SQUEEZE_SOURCES
    src/squeeze/SqueezeConfigReader.cpp
)

# Source files - Assembly
set(ASSEMBLY_SOURCES
    src/assembly/AssemblyConfigReader.cpp
    src/assembly/ModelAssembler.cpp
    src/assembly/DeflectionGrid.cpp
    src/assembly/FormulaEvaluator.cpp
    src/assembly/ClosedLoop.cpp
    src/assembly/IndentProfile.cpp
    src/assembly/ShellCurvature.cpp
    src/assembly/WarpageGrid.cpp
)

# Source files - CLI
set(CLI_SOURCES
    src/cli/ArgumentParser.cpp
    src/cli/ConsoleOutput.cpp
)

# Source files - Utility
set(UTIL_SOURCES
    src/util/Logger.cpp
    src/util/Timer.cpp
    src/util/Validator.cpp
    src/util/SpatialHash2D.cpp
)

# Source files - Validation
set(VALIDATION_SOURCES
    src/validation/MaterialCardValidator.cpp
    src/validation/ElementQualityChecker.cpp
    src/validation/IntersectionDetector.cpp
)

# Local TET remesh module (Phase A self-contained; Phase B TetGen optional).
set(REMESH_SOURCES
    src/remesh/PatchExtractor.cpp
    src/remesh/LocalImproveRemesher.cpp
    src/remesh/TetGenRemesher.cpp
    src/remesh/RemeshOrchestrator.cpp
)

# TetGen integration is OPT-IN due to AGPL v3 license. Default OFF.
# Enable with:  cmake -DKOOREMAPPER_BUILD_TETGEN=ON ..
option(KOOREMAPPER_BUILD_TETGEN
       "Build the TetGen-backed remesher (third_party/tetgen, AGPL v3)" OFF)
if(KOOREMAPPER_BUILD_TETGEN)
    list(APPEND REMESH_SOURCES
        third_party/tetgen/predicates.cxx
        third_party/tetgen/tetgen.cxx
    )
    add_definitions(-DKOOREMAPPER_BUILD_TETGEN -DTETLIBRARY)
    include_directories(${CMAKE_SOURCE_DIR}/third_party/tetgen)
    message(STATUS "TetGen backend: ENABLED (AGPL v3 -- check distribution policy)")
else()
    message(STATUS "TetGen backend: disabled (Phase A only). "
                   "Pass -DKOOREMAPPER_BUILD_TETGEN=ON to enable.")
endif()

# Create library
add_library(kooremapper_lib STATIC
    ${CORE_SOURCES}
    ${PARSER_SOURCES}
    ${GRID_SOURCES}
    ${MAPPER_SOURCES}
    ${EXAMPLE_SOURCES}
    ${GENERATOR_SOURCES}
    ${ANALYSIS_SOURCES}
    ${SQUEEZE_SOURCES}
    ${ASSEMBLY_SOURCES}
    ${CLI_SOURCES}
    ${UTIL_SOURCES}
    ${VALIDATION_SOURCES}
    ${REMESH_SOURCES}
)

# Add src/ to lib include path so ModelAssembler can reach commands/ headers
target_include_directories(kooremapper_lib PRIVATE ${CMAKE_SOURCE_DIR}/src)

# Define M_PI for MSVC (apply to both lib and executable)
if(MSVC)
    target_compile_definitions(kooremapper_lib PRIVATE _USE_MATH_DEFINES)
endif()

# TetGen library mode -- ensure TETLIBRARY (causes terminatetetgen to throw
# instead of exit()) is defined for BOTH the tetgen .cxx files and our
# wrapper TetGenRemesher.cpp. add_definitions() above applies post-config
# but we re-apply via target_compile_definitions to be unambiguous.
if(KOOREMAPPER_BUILD_TETGEN)
    target_compile_definitions(kooremapper_lib PRIVATE
        TETLIBRARY
        KOOREMAPPER_BUILD_TETGEN
    )
endif()

# Link OpenMP to library
if(OpenMP_CXX_FOUND)
    target_link_libraries(kooremapper_lib PUBLIC OpenMP::OpenMP_CXX)
    target_compile_definitions(kooremapper_lib PUBLIC USE_OPENMP)
endif()

# Command source files (split from main.cpp one by one)
set(COMMAND_SOURCES
    src/commands/modal.cpp
    src/commands/relax.cpp
    src/commands/implicit.cpp
    src/commands/database.cpp
    src/commands/matdb.cpp
    src/commands/stabilize.cpp
    src/commands/ale.cpp
    src/commands/matswap.cpp
    src/commands/optimize.cpp
    src/commands/contact_helpers.cpp
    src/commands/contact.cpp
    src/commands/load_boundary.cpp
    src/commands/standalone_ops.cpp
    src/commands/core_ops.cpp
    src/commands/squeeze_assemble.cpp
    src/commands/cnrb2solid.cpp
    src/commands/hfdamp.cpp
    src/commands/battery.cpp
    src/commands/strip.cpp
    src/commands/merge.cpp
    src/commands/tetremesh.cpp
    src/commands/meshfix.cpp
    src/commands/surface_extract.cpp
    src/commands/cclip.cpp
    src/battery/BatteryWriter.cpp
    src/battery/BatteryMaterials.cpp
    src/battery/BatteryContacts.cpp
    src/battery/BatteryControl.cpp
    src/battery/BatteryMeshStacked.cpp
    src/battery/BatteryMeshWound.cpp
    src/battery/BatterySwelling.cpp
)

# Main executable
add_executable(KooRemapper src/main.cpp ${COMMAND_SOURCES})
target_include_directories(KooRemapper PRIVATE ${CMAKE_SOURCE_DIR}/src)
target_link_libraries(KooRemapper PRIVATE kooremapper_lib)
if(MSVC)
    target_compile_definitions(KooRemapper PRIVATE _USE_MATH_DEFINES)
endif()

# Install targets
install(TARGETS KooRemapper DESTINATION bin)

# ============================================================
# Platform backend integration (opt-in; ZERO impact when unset)
# ------------------------------------------------------------
# When -DKOOREMAPPER_PLATFORM_BIN=<dir> is passed, the freshly built
# binary and its runtime material DB are copied into that directory
# after every build, so the FastAPI backend always runs the current
# binary. Leaving the cache var empty (the default) makes this a no-op,
# so existing build/CI workflows are completely unaffected.
#   cmake -DKOOREMAPPER_PLATFORM_BIN=$PWD/platform/backend/bin -S . -B build/linux
# ============================================================
set(KOOREMAPPER_PLATFORM_BIN "" CACHE PATH
    "If set, copy the built KooRemapper binary + materials/ here for the FastAPI backend")
if(KOOREMAPPER_PLATFORM_BIN)
    add_custom_command(TARGET KooRemapper POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E make_directory "${KOOREMAPPER_PLATFORM_BIN}"
        COMMAND ${CMAKE_COMMAND} -E copy
            "$<TARGET_FILE:KooRemapper>"
            "${KOOREMAPPER_PLATFORM_BIN}/$<TARGET_FILE_NAME:KooRemapper>"
        COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CMAKE_SOURCE_DIR}/dist/materials"
            "${KOOREMAPPER_PLATFORM_BIN}/materials"
        COMMENT "Copying KooRemapper binary + materials -> ${KOOREMAPPER_PLATFORM_BIN}"
        VERBATIM)
endif()

# ============================================================
# Testing
# ============================================================
option(BUILD_TESTS "Build test suite" ON)

if(BUILD_TESTS)
    enable_testing()

    # Test executable
    add_executable(KooRemapper_tests tests/test_main.cpp)
    target_link_libraries(KooRemapper_tests PRIVATE kooremapper_lib)
    target_include_directories(KooRemapper_tests PRIVATE ${CMAKE_SOURCE_DIR}/tests)

    # Define M_PI for MSVC
    if(MSVC)
        target_compile_definitions(KooRemapper_tests PRIVATE _USE_MATH_DEFINES)
    endif()

    # Register test
    add_test(NAME KooRemapper_tests COMMAND KooRemapper_tests)

    message(STATUS "Tests: Enabled")
endif()

# Print configuration summary
message(STATUS "")
message(STATUS "KooRemapper Configuration Summary")
message(STATUS "==================================")
message(STATUS "Version: ${PROJECT_VERSION}")
message(STATUS "Platform: ${CMAKE_SYSTEM_NAME}")
message(STATUS "Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "")
