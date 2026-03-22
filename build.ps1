# Build the blend-ai Blender addon zip for distribution.
# Usage: .\build.ps1 [version]
# Example: .\build.ps1 0.2.0
#
# If no version is provided, reads it from addon\__init__.py bl_info.
# The zip contains a blend_ai\ folder so Blender installs it as the
# "blend_ai" addon module.

param(
    [string]$Version
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AddonDir = Join-Path $ScriptDir "addon"

if (-not (Test-Path $AddonDir)) {
    Write-Error "addon\ directory not found at $AddonDir"
    exit 1
}

# Get version from argument or parse from bl_info
if (-not $Version) {
    $initContent = Get-Content (Join-Path $AddonDir "__init__.py") -Raw
    if ($initContent -match '"version":\s*\((\d+),\s*(\d+),\s*(\d+)\)') {
        $Version = "$($Matches[1]).$($Matches[2]).$($Matches[3])"
    } else {
        Write-Error "Could not parse version from addon\__init__.py"
        exit 1
    }
}

$Output = Join-Path $ScriptDir "blend-ai-v${Version}.zip"

Write-Host "Building blend-ai addon v${Version}..."

# Remove old zip if it exists
if (Test-Path $Output) {
    Remove-Item $Output
}

# Create temp dir with addon contents under blend_ai\ name
$tempDir = Join-Path $env:TEMP "blend-ai-build-$(Get-Random)"
$destDir = Join-Path $tempDir "blend_ai"
New-Item -ItemType Directory -Path $destDir -Force | Out-Null

# Copy addon files, excluding __pycache__ and .pyc
Get-ChildItem -Path $AddonDir -Recurse |
    Where-Object {
        $_.FullName -notmatch '__pycache__' -and
        $_.Extension -ne '.pyc'
    } |
    ForEach-Object {
        $relativePath = $_.FullName.Substring($AddonDir.Length)
        $destPath = Join-Path $destDir $relativePath
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $destPath -Force | Out-Null
        } else {
            $parentDir = Split-Path -Parent $destPath
            if (-not (Test-Path $parentDir)) {
                New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
            }
            Copy-Item $_.FullName $destPath
        }
    }

Compress-Archive -Path $destDir -DestinationPath $Output -Force

# Cleanup
Remove-Item -Recurse -Force $tempDir

Write-Host "Built: $Output"
