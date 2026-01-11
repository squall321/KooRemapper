#!/bin/bash

echo "============================================"
echo " KooRemapper Build Script for Linux"
echo "============================================"
echo

# Check for CMake
if ! command -v cmake &> /dev/null; then
    echo "ERROR: CMake not found"
    echo "Please install CMake: sudo apt install cmake"
    exit 1
fi

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Create build directory
BUILD_DIR="build/linux"
mkdir -p "$BUILD_DIR"

# Configure
echo "[1/2] Configuring with CMake..."
cmake -DCMAKE_BUILD_TYPE=Release -S . -B "$BUILD_DIR"
if [ $? -ne 0 ]; then
    echo
    echo "ERROR: CMake configuration failed"
    exit 1
fi

# Build
echo
echo "[2/2] Building..."
cmake --build "$BUILD_DIR" -j$(nproc)
if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Build failed"
    exit 1
fi

echo
echo "============================================"
echo " Build completed successfully!"
echo " Executable: $BUILD_DIR/bin/KooRemapper"
echo "============================================"
