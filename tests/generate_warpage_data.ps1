# Test 1: Cylindrical bending - w(x) = A*(x/L - 0.5)^2
$nx = 50
$ny = 50
$L = 100.0
$A = 1.0

$output1 = "d:\KooRemapper\tests\warpage_cylindrical.dat"
$sb1 = New-Object System.Text.StringBuilder

for ($j = 0; $j -lt $ny; $j++) {
    $row = @()
    for ($i = 0; $i -lt $nx; $i++) {
        $x = $i * $L / ($nx - 1)
        $w = $A * ([Math]::Pow(($x/$L - 0.5), 2) - 0.25)
        $row += $w.ToString("0.000000")
    }
    [void]$sb1.AppendLine(($row -join "`t"))
}

[System.IO.File]::WriteAllText($output1, $sb1.ToString())
Write-Host "Created: warpage_cylindrical.dat (50x50, parabolic in x)"

# Test 2: Gaussian bump - w(r) = h0 * exp(-r^2 / sigma^2)
$h0 = 0.5  # mm peak height
$sigma = 30.0  # mm radius
$cx = 50.0  # center x
$cy = 50.0  # center y

$output2 = "d:\KooRemapper\tests\warpage_gaussian.dat"
$sb2 = New-Object System.Text.StringBuilder

for ($j = 0; $j -lt $ny; $j++) {
    $row = @()
    $y = $j * $L / ($ny - 1)
    for ($i = 0; $i -lt $nx; $i++) {
        $x = $i * $L / ($nx - 1)
        $dx = $x - $cx
        $dy = $y - $cy
        $r = [Math]::Sqrt($dx*$dx + $dy*$dy)
        $w = $h0 * [Math]::Exp(-$r*$r / ($sigma*$sigma))
        $row += $w.ToString("0.000000")
    }
    [void]$sb2.AppendLine(($row -join "`t"))
}

[System.IO.File]::WriteAllText($output2, $sb2.ToString())
Write-Host "Created: warpage_gaussian.dat (50x50, Gaussian bump)"
