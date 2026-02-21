# Offset Operation Regression Test Suite
# Purpose: Verify existing offset functionality is preserved during enhancements

param(
    [switch]$UpdateBaseline = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"
$exe = "build\bin\Release\KooRemapper.exe"
$testDir = "tests\offset\regression"
$baselineDir = "tests\offset\baseline"
$resultsDir = "tests\offset\results"

# Color output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Failure { Write-Host $args -ForegroundColor Red }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }

# Check executable exists
if (!(Test-Path $exe)) {
    Write-Failure "ERROR: KooRemapper.exe not found at $exe"
    Write-Info "Please build the project first: cmake --build build --config Release"
    exit 1
}

# Create results directory
if (!(Test-Path $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir | Out-Null
}

# Get all test YAML files
$tests = Get-ChildItem "$testDir\*.yaml" | Sort-Object Name

if ($tests.Count -eq 0) {
    Write-Failure "No test files found in $testDir"
    exit 1
}

Write-Info "========================================="
Write-Info "Offset Regression Test Suite"
Write-Info "Tests found: $($tests.Count)"
Write-Info "========================================="
Write-Host ""

# Test results
$passed = 0
$failed = 0
$failedTests = @()

foreach ($test in $tests) {
    $testName = $test.BaseName
    Write-Info "Running: $testName"

    # Run KooRemapper
    $output = ""
    $errorOutput = ""
    try {
        # Run and capture output
        & $exe "assemble" $test.FullName > "$resultsDir\${testName}_stdout.txt" 2> "$resultsDir\${testName}_stderr.txt"
        $exitCode = $LASTEXITCODE

        $output = Get-Content "$resultsDir\${testName}_stdout.txt" -Raw -ErrorAction SilentlyContinue
        $errorOutput = Get-Content "$resultsDir\${testName}_stderr.txt" -Raw -ErrorAction SilentlyContinue

        if ($Verbose) {
            Write-Host "  STDOUT: $output"
            if ($errorOutput) {
                Write-Host "  STDERR: $errorOutput"
            }
        }

        if ($exitCode -ne 0) {
            Write-Failure "  FAILED: Exit code $exitCode"
            Write-Host "  Error: $errorOutput"
            $failed++
            $failedTests += $testName
            continue
        }
    } catch {
        Write-Failure "  FAILED: Exception running test"
        Write-Host "  $_"
        $failed++
        $failedTests += $testName
        continue
    }

    # Check output files exist
    $kFile = "$testDir\${testName}.k"
    if (!(Test-Path $kFile)) {
        Write-Failure "  FAILED: Output .k file not found"
        $failed++
        $failedTests += $testName
        continue
    }

    # Extract metrics from output
    $metrics = @{}

    # Parse element counts from stdout
    if ($output -match "Created (\d+) solid elements") {
        $metrics["solid_elements"] = [int]$matches[1]
    }
    if ($output -match "Created \d+ nodes, (\d+) shell elements") {
        $metrics["shell_elements"] = [int]$matches[1]
    }
    if ($output -match "Created (\d+) CZM elements") {
        $metrics["czm_elements"] = [int]$matches[1]
    }
    if ($output -match "Added: (\d+) nodes") {
        $metrics["nodes_added"] = [int]$matches[1]
    }
    if ($output -match "Added: \d+ nodes, (\d+) elements") {
        $metrics["elements_added"] = [int]$matches[1]
    }
    if ($output -match "(\d+) layers") {
        $metrics["num_layers"] = [int]$matches[1]
    }

    # Check for dynain file (dual offset prestress test)
    $dynainFile = "$testDir\${testName}.dynain"
    if (Test-Path $dynainFile) {
        $metrics["has_dynain"] = $true
        $dynainContent = Get-Content $dynainFile -Raw
        if ($dynainContent -match "\*INITIAL_STRESS_SOLID") {
            $metrics["has_initial_stress"] = $true
        }
    } else {
        $metrics["has_dynain"] = $false
    }

    # Parse .k file for additional validation
    $kContent = Get-Content $kFile -Raw

    # Count element sections
    $solidCount = ([regex]::Matches($kContent, "\*ELEMENT_SOLID\b")).Count
    $shellCount = ([regex]::Matches($kContent, "\*ELEMENT_SHELL\b")).Count
    $tshellCount = ([regex]::Matches($kContent, "\*ELEMENT_TSHELL\b")).Count

    if ($solidCount -gt 0) { $metrics["k_solid_sections"] = $solidCount }
    if ($shellCount -gt 0) { $metrics["k_shell_sections"] = $shellCount }
    if ($tshellCount -gt 0) { $metrics["k_tshell_sections"] = $tshellCount }

    # Check for CZM material
    if ($kContent -match "\*MAT_COHESIVE_MIXED_MODE") {
        $metrics["has_czm_material"] = $true
    }

    # Check for contact template (contact mode test)
    if ($kContent -match "\$.*CONTACT.*template") {
        $metrics["has_contact_template"] = $true
    }

    # Save metrics to baseline or compare
    $metricsFile = "$baselineDir\${testName}_metrics.json"
    $currentMetrics = $metrics | ConvertTo-Json -Depth 10

    if ($UpdateBaseline) {
        # Update baseline
        if (!(Test-Path $baselineDir)) {
            New-Item -ItemType Directory -Path $baselineDir | Out-Null
        }
        Set-Content -Path $metricsFile -Value $currentMetrics
        Write-Success "  BASELINE UPDATED"
        $passed++
    } else {
        # Compare with baseline
        if (!(Test-Path $metricsFile)) {
            Write-Warning "  WARNING: No baseline found (run with -UpdateBaseline)"
            Set-Content -Path $metricsFile -Value $currentMetrics
            Write-Success "  PASSED (baseline created)"
            $passed++
        } else {
            $baselineMetrics = Get-Content $metricsFile -Raw | ConvertFrom-Json
            $metricsMatch = $true
            $differences = @()

            # Compare each metric
            foreach ($key in $metrics.Keys) {
                if ($baselineMetrics.PSObject.Properties.Name -notcontains $key) {
                    $metricsMatch = $false
                    $differences += "  + New metric: $key = $($metrics[$key])"
                } elseif ($metrics[$key] -ne $baselineMetrics.$key) {
                    $metricsMatch = $false
                    $differences += "  ~ $key : $($baselineMetrics.$key) → $($metrics[$key])"
                }
            }

            # Check for missing metrics
            foreach ($key in $baselineMetrics.PSObject.Properties.Name) {
                if ($metrics.Keys -notcontains $key) {
                    $metricsMatch = $false
                    $differences += "  - Missing metric: $key (was $($baselineMetrics.$key))"
                }
            }

            if ($metricsMatch) {
                Write-Success "  PASSED"
                $passed++
            } else {
                Write-Failure "  FAILED: Metrics changed"
                foreach ($diff in $differences) {
                    Write-Host $diff
                }
                $failed++
                $failedTests += $testName
            }
        }
    }

    Write-Host ""
}

# Summary
Write-Info "========================================="
Write-Info "Test Summary"
Write-Info "========================================="
Write-Success "Passed: $passed / $($tests.Count)"
if ($failed -gt 0) {
    Write-Failure "Failed: $failed / $($tests.Count)"
    Write-Host ""
    Write-Failure "Failed tests:"
    foreach ($ft in $failedTests) {
        Write-Host "  - $ft"
    }
    exit 1
} else {
    Write-Success "All tests passed!"
    exit 0
}
