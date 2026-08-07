<#
.SYNOPSIS
    Build the BookWriter image and stage it for a registry-free deploy.

.DESCRIPTION
    Builds iezious/bookwriter from the repo root, saves it through 7z, and
    stages the archive plus the deploy config into $env:DOCKER_STORE/bookwriter.
    The Linux side is update.sh, which reads the same folder.

    With neither -Images nor -Config, both are done.

.PARAMETER Images
    Build the image, save it and stage bookwriter-latest.7z.

.PARAMETER Config
    Stage docker-compose.prod.yml (renamed docker-compose.yml) and .env.example.

.PARAMETER Push
    Optional scp destination, e.g. user@host:/srv/bookwriter. Used in addition
    to the share, after the store has been written.

.EXAMPLE
    ./build.ps1
    ./build.ps1 -Config
    ./build.ps1 -Images -Push deploy@server:/srv/bookwriter
#>
param(
    [switch]$Images,
    [switch]$Config,
    [string]$Push
)

$ErrorActionPreference = "Stop"

# Fixed archive name — update.sh never has to discover one.
$archiveName = "bookwriter-latest.7z"

# Default: --all (both images and config)
if (-not $Images -and -not $Config) {
    $Images = $true
    $Config = $true
}

# Version comes from the latest git tag.
$version = git describe --tags --abbrev=0 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($version)) {
    Write-Host "ERROR: No git tags found. Create one with: git tag v0.0.1" -ForegroundColor Red
    exit 1
}

Write-Host "Building version: $version" -ForegroundColor Cyan

# Validate DOCKER_STORE
if (-not $env:DOCKER_STORE) {
    Write-Host "ERROR: DOCKER_STORE environment variable is not set" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $env:DOCKER_STORE)) {
    Write-Host "ERROR: DOCKER_STORE path does not exist: $env:DOCKER_STORE" -ForegroundColor Red
    exit 1
}

$outputDir = Join-Path $env:DOCKER_STORE "bookwriter"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if ($Images) {
    Write-Host "`nBuilding iezious/bookwriter..." -ForegroundColor Yellow
    docker build -f Dockerfile `
        -t "iezious/bookwriter:$version" `
        -t "iezious/bookwriter:latest" `
        .
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Image build failed" -ForegroundColor Red; exit 1 }

    # Stage locally, then move onto the store: a partial-file guard for a
    # network mount.
    $tempDir = Join-Path $env:TEMP "bookwriter-build"
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item -ItemType Directory -Path $tempDir | Out-Null

    try {
        Write-Host "`nSaving iezious/bookwriter to 7z..." -ForegroundColor Yellow
        $archiveTemp = Join-Path $tempDir $archiveName
        docker save "iezious/bookwriter:latest" | 7z a -si "$archiveTemp"
        if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Image save failed" -ForegroundColor Red; exit 1 }

        Write-Host "`nMoving archive to $outputDir..." -ForegroundColor Yellow
        Move-Item $archiveTemp -Destination $outputDir -Force

        Write-Host "  Image: $outputDir\$archiveName" -ForegroundColor Green
    } finally {
        if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    }
}

if ($Config) {
    Write-Host "`nStaging deploy config..." -ForegroundColor Yellow
    Copy-Item "docker-compose.prod.yml" -Destination (Join-Path $outputDir "docker-compose.yml") -Force
    Copy-Item ".env.example" -Destination (Join-Path $outputDir ".env.example") -Force

    Write-Host "  Compose: $outputDir\docker-compose.yml" -ForegroundColor Green
    Write-Host "  Env:     $outputDir\.env.example" -ForegroundColor Green
}

if ($Push) {
    Write-Host "`nPushing to $Push..." -ForegroundColor Yellow
    $archivePath = Join-Path $outputDir $archiveName
    $composePath = Join-Path $outputDir "docker-compose.yml"

    scp "$archivePath" "$composePath" "$Push"
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: scp to $Push failed" -ForegroundColor Red; exit 1 }

    Write-Host "  Pushed: $archiveName, docker-compose.yml" -ForegroundColor Green
}

Write-Host "`nBuild complete!" -ForegroundColor Green
