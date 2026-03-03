$exe = "D:\KooRemapper\build\bin\Release\KooRemapper.exe"
$dirs = @("static_lv1","static_lv3","static_lv5","dynamic_lv3","dynamic_lv5","dynamic_lv8")
$base = "D:\KooRemapper\tests\integration"

foreach ($dir in $dirs) {
    Write-Host "=== $dir ===" -ForegroundColor Cyan
    $yaml = "$base\$dir\implicit.yaml"
    & $exe implicit $yaml 2>&1 | Where-Object { $_ -match "\[implicit\]|Error|error" }
    Write-Host ""
}
