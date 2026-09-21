<#
.SYNOPSIS
    Builds PlantUML C4 diagrams into SVG and PNG images with automated Graphviz dot detection and validation.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# 1. Resolve dot.exe (avoid Chocolatey shim issues)
if (-not $env:GRAPHVIZ_DOT) {
    $candidatePaths = @(
        "C:\Program Files\Graphviz\bin\dot.exe",
        "C:\Program Files (x86)\Graphviz\bin\dot.exe",
        (Get-Command dot.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    )

    foreach ($path in $candidatePaths) {
        if ($path -and (Test-Path $path) -and ($path -notmatch "chocolatey\\bin")) {
            $env:GRAPHVIZ_DOT = $path
            Write-Host "Discovered Graphviz dot at: $path" -ForegroundColor Green
            break
        }
    }
}

if (-not $env:GRAPHVIZ_DOT -or -not (Test-Path $env:GRAPHVIZ_DOT)) {
    Write-Warning "GRAPHVIZ_DOT is not set or not found. PlantUML may fail or produce error diagrams."
} else {
    Write-Host "Using GRAPHVIZ_DOT: $env:GRAPHVIZ_DOT" -ForegroundColor Cyan
}

# 2. Locate plantuml.jar
$plantumlJar = $null
$jarCandidates = @(
    "C:\ProgramData\chocolatey\lib\plantuml\tools\plantuml.jar",
    "$env:USERPROFILE\plantuml.jar"
)

foreach ($jar in $jarCandidates) {
    if (Test-Path $jar) {
        $plantumlJar = $jar
        break
    }
}

if (-not $plantumlJar) {
    throw "Could not locate plantuml.jar. Please ensure PlantUML is installed."
}

Write-Host "Using PlantUML jar: $plantumlJar" -ForegroundColor Cyan

# 3. Compile Diagrams
$pumlDir = "docs/diagrams/puml"
$outDir = "docs/diagrams/images"

New-Item -ItemType Directory -Path $outDir -Force | Out-Null

Write-Host "Compiling PlantUML diagrams (PNG and SVG)..." -ForegroundColor Yellow
& java -jar $plantumlJar -o "../images" "$pumlDir/*.puml"
& java -jar $plantumlJar -tsvg -o "../images" "$pumlDir/*.puml"

# 4. Verify Generated Images are not crash/error diagrams
$svgFiles = Get-ChildItem -Path $outDir -Filter "*.svg"
$hasError = $false

foreach ($file in $svgFiles) {
    $content = Get-Content -Path $file.FullName -Raw
    if ($content -match "An error has occurred" -or $content -match "EmptySvgException" -or $content -match "dot/GraphViz has crashed") {
        Write-Error "ERROR: $($file.Name) contains a PlantUML crash message!"
        $hasError = $true
    } else {
        Write-Host "VALID: $($file.Name) ($($file.Length) bytes)" -ForegroundColor Green
    }
}

if ($hasError) {
    exit 1
}

Write-Host "`nAll diagrams successfully generated and verified!" -ForegroundColor Green
