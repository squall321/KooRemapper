$line = "         1  7.93E-09    193000       0.29       215       0.0       0.0       0.0"
Write-Host "Length: $($line.Length)"
for ($i = 0; $i -lt 8; $i++) {
    $start = $i * 10
    $len = [Math]::Min(10, $line.Length - $start)
    if ($len -le 0) { break }
    $field = $line.Substring($start, $len)
    Write-Host "Field $i : [$field]"
}
