cmake_minimum_required(VERSION 3.16)
project(KooRemapper VERSION 1.0.0 LANGUAGES CXX)

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

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/include)

# Source files - Core
set(CORE_SOURCES
    src/core/Vector3D.cpp
    src/core/Node.cpp
    src/core/Element.cpp
    src/core/Mesh.cpp
    src/core/Platform.cpp
)

# Source files - Parser
set(PARSER_SOURCES
    src/parser/KFileReader.cpp
    src/parser/KFileWriter.cpp
    src/parser/DynainWriter.cpp
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
)

# Source files - Example
set(EXAMPLE_SOURCES
    src/example/ExampleMeshGenerator.cpp
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
)

# Create library
add_library(kooremapper_lib STATIC
    ${CORE_SOURCES}
    ${PARSER_SOURCES}
    ${GRID_SOURCES}
    ${MAPPER_SOURCES}
    ${EXAMPLE_SOURCES}
    ${ANALYSIS_SOURCES}
    ${CLI_SOURCES}
    ${UTIL_SOURCES}
)

# Define M_PI for MSVC
if(MSVC)
    target_compile_definitions(kooremapper_lib PRIVATE _USE_MATH_DEFINES)
endif()

# Main executable
add_executable(KooRemapper src/main.cpp)
target_link_libraries(KooRemapper PRIVATE kooremapper_lib)

# Install targets
install(TARGETS KooRemapper DESTINATION bin)

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
