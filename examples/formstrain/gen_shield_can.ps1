# Generate PBA shield can mesh
# Box: 20x15mm bottom, 3mm wall height, t=0.2mm
# SUS304: E=193000, nu=0.29, SIGY=215

$out = "$PSScriptRoot\shield_can.k"

$lines = @()
$lines += "*KEYWORD"
$lines += "*TITLE"
$lines += "PBA Shield Can - formstrain verification"

# --- NODES ---
$lines += "*NODE"

$nid = 0
$nodeMap = @{}  # key="x,y,z" -> nid

function AddNode($x, $y, $z) {
    $key = "$x,$y,$z"
    if ($script:nodeMap.ContainsKey($key)) {
        return $script:nodeMap[$key]
    }
    $script:nid++
    $script:nodeMap[$key] = $script:nid
    $line = "{0,10}{1,16:F6}{2,16:F6}{3,16:F6}" -f $script:nid, $x, $y, $z
    $script:lines += $line
    return $script:nid
}

# Bottom plate: 21x16 nodes (x=0..20, y=0..15, z=0)
$bottomNids = @{}
for ($j = 0; $j -le 15; $j++) {
    for ($i = 0; $i -le 20; $i++) {
        $id = AddNode $i $j 0
        $bottomNids["$i,$j"] = $id
    }
}

# Wall -Y (y=0): z=1,2,3 rows
$wallNY = @{}
for ($k = 1; $k -le 3; $k++) {
    for ($i = 0; $i -le 20; $i++) {
        $id = AddNode $i 0 $k
        $wallNY["$i,$k"] = $id
    }
}

# Wall +Y (y=15): z=1,2,3 rows
$wallPY = @{}
for ($k = 1; $k -le 3; $k++) {
    for ($i = 0; $i -le 20; $i++) {
        $id = AddNode $i 15 $k
        $wallPY["$i,$k"] = $id
    }
}

# Wall -X (x=0): z=1,2,3, y=0..15
$wallNX = @{}
for ($k = 1; $k -le 3; $k++) {
    for ($j = 0; $j -le 15; $j++) {
        $id = AddNode 0 $j $k
        $wallNX["$j,$k"] = $id
    }
}

# Wall +X (x=20): z=1,2,3, y=0..15
$wallPX = @{}
for ($k = 1; $k -le 3; $k++) {
    for ($j = 0; $j -le 15; $j++) {
        $id = AddNode 20 $j $k
        $wallPX["$j,$k"] = $id
    }
}

# --- ELEMENTS ---
$lines += "*ELEMENT_SHELL"

$eid = 0
$partId = 1

function AddElem($n1, $n2, $n3, $n4) {
    $script:eid++
    $line = "{0,8}{1,8}{2,8}{3,8}{4,8}{5,8}" -f $script:eid, $script:partId, $n1, $n2, $n3, $n4
    $script:lines += $line
}

# Bottom plate: 20x15 elements
for ($j = 0; $j -lt 15; $j++) {
    for ($i = 0; $i -lt 20; $i++) {
        $n1 = $bottomNids["$i,$j"]
        $n2 = $bottomNids["$($i+1),$j"]
        $n3 = $bottomNids["$($i+1),$($j+1)"]
        $n4 = $bottomNids["$i,$($j+1)"]
        AddElem $n1 $n2 $n3 $n4
    }
}

# Wall -Y: 20x3 elements (x-direction x z-direction)
# z=0 row uses bottom nids (y=0), z>0 uses wallNY
function GetWallNY_nid($i, $k) {
    if ($k -eq 0) { return $bottomNids["$i,0"] }
    return $wallNY["$i,$k"]
}

for ($k = 0; $k -lt 3; $k++) {
    for ($i = 0; $i -lt 20; $i++) {
        $n1 = GetWallNY_nid $i $k
        $n2 = GetWallNY_nid ($i+1) $k
        $n3 = GetWallNY_nid ($i+1) ($k+1)
        $n4 = GetWallNY_nid $i ($k+1)
        AddElem $n1 $n2 $n3 $n4
    }
}

# Wall +Y: 20x3 elements
function GetWallPY_nid($i, $k) {
    if ($k -eq 0) { return $bottomNids["$i,15"] }
    return $wallPY["$i,$k"]
}

for ($k = 0; $k -lt 3; $k++) {
    for ($i = 0; $i -lt 20; $i++) {
        $n1 = GetWallPY_nid $i $k
        $n2 = GetWallPY_nid ($i+1) $k
        $n3 = GetWallPY_nid ($i+1) ($k+1)
        $n4 = GetWallPY_nid $i ($k+1)
        AddElem $n1 $n2 $n3 $n4
    }
}

# Wall -X: 15x3 elements (y-direction x z-direction)
function GetWallNX_nid($j, $k) {
    if ($k -eq 0) { return $bottomNids["0,$j"] }
    return $wallNX["$j,$k"]
}

for ($k = 0; $k -lt 3; $k++) {
    for ($j = 0; $j -lt 15; $j++) {
        $n1 = GetWallNX_nid $j $k
        $n2 = GetWallNX_nid ($j+1) $k
        $n3 = GetWallNX_nid ($j+1) ($k+1)
        $n4 = GetWallNX_nid $j ($k+1)
        AddElem $n1 $n2 $n3 $n4
    }
}

# Wall +X: 15x3 elements
function GetWallPX_nid($j, $k) {
    if ($k -eq 0) { return $bottomNids["20,$j"] }
    return $wallPX["$j,$k"]
}

for ($k = 0; $k -lt 3; $k++) {
    for ($j = 0; $j -lt 15; $j++) {
        $n1 = GetWallPX_nid $j $k
        $n2 = GetWallPX_nid ($j+1) $k
        $n3 = GetWallPX_nid ($j+1) ($k+1)
        $n4 = GetWallPX_nid $j ($k+1)
        AddElem $n1 $n2 $n3 $n4
    }
}

# --- PART, SECTION, MATERIAL ---
$lines += "*PART"
$lines += "Shield Can"
$lines += "         1         1         1"
$lines += "*SECTION_SHELL"
$lines += ("$" + "#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp")
$lines += "         1         2       1.0         2       1.0         0         0         1"
$lines += ("$" + "#      t1        t2        t3        t4      nloc     marea      idof    edgset")
$lines += "  0.200000  0.200000  0.200000  0.200000       0.0       0.0       0.0       0.0"
$lines += "*MAT_PIECEWISE_LINEAR_PLASTICITY"
$lines += ("$" + "#     mid        ro         e        pr      sigy      etan      fail      tdel")
$lines += "         1  7.93E-09    193000      0.29       215       0.0       0.0       0.0"
$lines += ("$" + "#       c         p      lcss      lcsr        vp       lcf")
$lines += "       0.0       0.0         0         0       0.0         0"
$lines += ("$" + "#    eps1      eps2      eps3      eps4      eps5      eps6      eps7      eps8")
$lines += "       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0"
$lines += ("$" + "#     es1       es2       es3       es4       es5       es6       es7       es8")
$lines += "       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0"
$lines += "*END"

$lines | Out-File -FilePath $out -Encoding ASCII

Write-Host "Generated $out"
Write-Host "  Nodes: $nid"
Write-Host "  Elements: $eid"
Write-Host "  Bottom: 300 elements (20x15)"
Write-Host "  Wall -Y: 60 elements (20x3)"
Write-Host "  Wall +Y: 60 elements (20x3)"
Write-Host "  Wall -X: 45 elements (15x3)"
Write-Host "  Wall +X: 45 elements (15x3)"
Write-Host "  Total walls: 210 elements"
Write-Host "  Grand total: $($eid) elements"
