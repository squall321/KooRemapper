$lsdyna = "D:\Program Files\LS-DYNA Suite R16.1 Student\lsdyna\ls-dyna_smp_d_R16.1_180-gd50332dbe5_winx64_ifort190_sse2_studentversion.exe"
$runDir = "D:\KooRemapper\tests\integration\rubber_static_lv3"
Set-Location $runDir
Remove-Item -ErrorAction SilentlyContinue messag, d3hsp, d3plot*
$proc = Start-Process -FilePath $lsdyna -ArgumentList "i=input.k memory=256m ncpu=1" `
    -WorkingDirectory $runDir -NoNewWindow -PassThru `
    -RedirectStandardOutput stdout.txt -RedirectStandardError stderr.txt -Wait
$lines = Get-Content messag -ErrorAction SilentlyContinue
$allText = $lines -join " "
$status = if ($allText -match "N o r m a l") { "NORMAL" } else { "FAILED" }
Write-Host "Result: $status"
$disc = $lines | Where-Object { $_ -match "(?i)discretization|Curve ID" }
if ($disc) {
    Write-Host "Discretization warnings:"
    $disc | Select-Object -First 5 | ForEach-Object { Write-Host "  >> $_" }
} else {
    Write-Host "No discretization warnings found"
}
Set-Location "D:\KooRemapper"
