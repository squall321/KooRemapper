# Analyze shield can formstrain result
$file = "$PSScriptRoot\shield_can_result.k"
$lines = Get-Content $file

# Find INITIAL_STRESS_SHELL section and extract EPS values per element
$inSection = $false
$results = @()
$currentEid = 0

foreach ($line in $lines) {
    if ($line -match "^\*INITIAL_STRESS_SHELL") {
        $inSection = $true
        continue
    }
    if ($inSection -and $line -match "^\*") {
        break
    }
    if (-not $inSection) { continue }
    if ($line -match "^\$") { continue }
    if ($line -match "^\s*$") { continue }

    # Try to parse as Card 1 (EID line): eid nplane nthick ...
    $trimmed = $line.Trim()
    $tokens = $trimmed -split '\s+'

    if ($tokens.Count -ge 3 -and $tokens[1] -eq "1" -and $tokens[2] -eq "2") {
        # This is Card 1: EID NPLANE NTHICK ...
        $currentEid = [int]$tokens[0]
    }
    elseif ($tokens.Count -ge 8) {
        # Stress card: T sigxx sigyy sigzz sigxy sigyz sigzx eps
        $T = [double]$tokens[0]
        $eps = [double]$tokens[7]
        if ($T -gt 0) {
            # Top surface (T=+1), record once per element
            $results += [PSCustomObject]@{
                EID = $currentEid
                EPS = $eps
            }
        }
    }
}

Write-Host "=== Shield Can Formstrain Results ==="
Write-Host "Total elements with EPS: $($results.Count)"

# Element ranges:
# Bottom: EID 1-300 (20x15)
# Wall -Y: EID 301-360 (20x3)
# Wall +Y: EID 361-420 (20x3)
# Wall -X: EID 421-465 (15x3)
# Wall +X: EID 466-510 (15x3)

$bottom = $results | Where-Object { $_.EID -ge 1 -and $_.EID -le 300 }
$wallNY = $results | Where-Object { $_.EID -ge 301 -and $_.EID -le 360 }
$wallPY = $results | Where-Object { $_.EID -ge 361 -and $_.EID -le 420 }
$wallNX = $results | Where-Object { $_.EID -ge 421 -and $_.EID -le 465 }
$wallPX = $results | Where-Object { $_.EID -ge 466 -and $_.EID -le 510 }

Write-Host ""
Write-Host "--- Distribution by region ---"
Write-Host "Bottom plate: $($bottom.Count) elements with EPS"
Write-Host "Wall -Y:      $($wallNY.Count) elements with EPS"
Write-Host "Wall +Y:      $($wallPY.Count) elements with EPS"
Write-Host "Wall -X:      $($wallNX.Count) elements with EPS"
Write-Host "Wall +X:      $($wallPX.Count) elements with EPS"

# Bottom plate edge elements (row 0, row 14, col 0, col 19)
# Bottom EID = (row * 20) + col + 1
$bottomEdge = @()
$bottomInterior = @()
foreach ($r in $bottom) {
    $eid = $r.EID
    $row = [Math]::Floor(($eid - 1) / 20)
    $col = ($eid - 1) % 20
    if ($row -eq 0 -or $row -eq 14 -or $col -eq 0 -or $col -eq 19) {
        $bottomEdge += $r
    } else {
        $bottomInterior += $r
    }
}

Write-Host ""
Write-Host "--- Bottom plate breakdown ---"
Write-Host "Edge elements (adjacent to walls): $($bottomEdge.Count)"
Write-Host "Interior elements: $($bottomInterior.Count)"

if ($bottom.Count -gt 0) {
    $epsVals = $bottom | ForEach-Object { $_.EPS }
    $minEps = ($epsVals | Measure-Object -Minimum).Minimum
    $maxEps = ($epsVals | Measure-Object -Maximum).Maximum
    Write-Host "Bottom EPS range: $minEps ~ $maxEps"
}

# Wall edge elements (first row of wall = adjacent to bottom)
$wallBottomRow = @()
$wallUpperRows = @()
foreach ($r in ($wallNY + $wallPY)) {
    $localEid = $r.EID
    if ($localEid -ge 301 -and $localEid -le 360) {
        $localRow = [Math]::Floor(($localEid - 301) / 20)
    } else {
        $localRow = [Math]::Floor(($localEid - 361) / 20)
    }
    if ($localRow -eq 0) { $wallBottomRow += $r }
    else { $wallUpperRows += $r }
}
foreach ($r in ($wallNX + $wallPX)) {
    $localEid = $r.EID
    if ($localEid -ge 421 -and $localEid -le 465) {
        $localRow = [Math]::Floor(($localEid - 421) / 15)
    } else {
        $localRow = [Math]::Floor(($localEid - 466) / 15)
    }
    if ($localRow -eq 0) { $wallBottomRow += $r }
    else { $wallUpperRows += $r }
}

Write-Host ""
Write-Host "--- Wall breakdown ---"
Write-Host "Wall bottom row (adjacent to bend): $($wallBottomRow.Count)"
Write-Host "Wall upper rows: $($wallUpperRows.Count)"

if ($wallBottomRow.Count -gt 0) {
    $epsVals = $wallBottomRow | ForEach-Object { $_.EPS }
    Write-Host "Wall bottom-row EPS range: $(($epsVals | Measure-Object -Minimum).Minimum) ~ $(($epsVals | Measure-Object -Maximum).Maximum)"
}

Write-Host ""
Write-Host "--- Manual verification ---"
Write-Host "90deg bend, centroid L = sqrt(0.5^2 + 0.5^2) = 0.707"
$theta = [Math]::PI / 2
$L = [Math]::Sqrt(0.5*0.5 + 0.5*0.5)
$kappa = $theta / $L
$t = 0.2
$epsB = $kappa * $t / 2.0
$epsY = 215.0 / 193000.0
$epsP = [Math]::Max(0, $epsB - $epsY)
Write-Host "kappa = $([Math]::Round($kappa, 4))"
Write-Host "eps_bending = kappa * t/2 = $([Math]::Round($epsB, 6))"
Write-Host "eps_yield = SIGY/E = $([Math]::Round($epsY, 6))"
Write-Host "eps_plastic = $([Math]::Round($epsP, 6))"
