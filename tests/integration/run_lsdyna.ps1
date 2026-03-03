$lsdyna = "D:\Program Files\LS-DYNA Suite R16.1 Student\lsdyna\ls-dyna_smp_d_R16.1_180-gd50332dbe5_winx64_ifort190_sse2_studentversion.exe"
$dirs   = @("static_lv1","static_lv3","static_lv5","dynamic_lv3","dynamic_lv5","dynamic_lv8")
$base   = "D:\KooRemapper\tests\integration"

$results = @()

foreach ($dir in $dirs) {
    $runDir = "$base\$dir"
    $inp    = "$runDir\input.k"
    if (-not (Test-Path $inp)) {
        Write-Host "[$dir] SKIP: input.k not found" -ForegroundColor Yellow
        continue
    }

    Write-Host "=== $dir - running LS-DYNA ===" -ForegroundColor Cyan
    Set-Location $runDir

    # Clean previous run output
    Remove-Item -ErrorAction SilentlyContinue messag, d3hsp, status.out, lspost.msg, d3plot*

    $proc = Start-Process -FilePath $lsdyna `
        -ArgumentList "i=input.k memory=256m ncpu=1" `
        -WorkingDirectory $runDir `
        -NoNewWindow -PassThru -RedirectStandardOutput "$runDir\stdout.txt" -RedirectStandardError "$runDir\stderr.txt" `
        -Wait

    $exitCode = $proc.ExitCode

    # Parse messag file for result
    $status = "UNKNOWN"
    $errors = @()
    if (Test-Path "$runDir\messag") {
        $msg = Get-Content "$runDir\messag" -Raw
        if ($msg -match "N o r m a l\s+t e r m i n a t i o n") { $status = "NORMAL" }
        elseif ($msg -match "E r r o r\s+t e r m i n a t i o n") { $status = "ERROR" }

        # Extract error lines
        $lines = Get-Content "$runDir\messag"
        foreach ($ln in $lines) {
            if ($ln -match "(?i)(error|warning.*fatal|\*\*\* Error)" -and
                $ln -notmatch "error tolerance|error norm|convergence error|relative error") {
                $errors += $ln.Trim()
            }
        }
    }

    $color = if ($status -eq "NORMAL") { "Green" } elseif ($status -eq "ERROR") { "Red" } else { "Yellow" }
    Write-Host "  Result : $status (exit=$exitCode)" -ForegroundColor $color
    foreach ($e in ($errors | Select-Object -Unique | Select-Object -First 5)) {
        Write-Host "  >> $e" -ForegroundColor Red
    }

    $results += [PSCustomObject]@{ Dir=$dir; Status=$status; ExitCode=$exitCode; Errors=($errors -join " | ") }
    Write-Host ""
}

Set-Location "D:\KooRemapper"
Write-Host "=== Summary ===" -ForegroundColor Cyan
$results | Format-Table -AutoSize
