<#
.SYNOPSIS
    Builds the MSIX package for Vāk for Microsoft Store submission.
.DESCRIPTION
    Packages the existing PyInstaller onedir distribution (dist/Vak) alongside the
    AppxManifest.xml and visual assets into an MSIX package using the Windows SDK MakeAppx tool.
.PARAMETER BuildExe
    Forces a rebuild of the PyInstaller distribution before packaging.
#>
param(
    [switch]$BuildExe
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

# 1. Locate Windows SDK MakeAppx.exe
$MakeAppxCandidates = @(
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\makeappx.exe",
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\makeappx.exe",
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.28000.0\x64\makeappx.exe"
)
$MakeAppxCmd = Get-Command makeappx.exe -ErrorAction SilentlyContinue
if ($MakeAppxCmd) {
    $MakeAppx = $MakeAppxCmd.Source
} else {
    $Found = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($Found) {
        $MakeAppx = $Found.FullName
    } else {
        $MakeAppx = $MakeAppxCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
}

if (!$MakeAppx -or !(Test-Path $MakeAppx)) {
    throw "Windows SDK MakeAppx.exe was not found. Please install the Windows 10/11 SDK."
}

Write-Host "[*] Using MakeAppx: $MakeAppx" -ForegroundColor Cyan

# 2. Verify or build PyInstaller executable distribution
$DistVak = Join-Path $Root "dist\Vak"
$VakExe = Join-Path $DistVak "Vak.exe"

if ($BuildExe -or !(Test-Path -LiteralPath $VakExe)) {
    Write-Host "[*] Building PyInstaller onedir distribution..." -ForegroundColor Cyan
    & (Join-Path $Root "scripts\build_windows.ps1")
}

if (!(Test-Path -LiteralPath $VakExe)) {
    throw "Executable missing at $VakExe. Run with -BuildExe or execute scripts\build_windows.ps1 first."
}

# 3. Ensure MSIX visual assets exist
$MsixAssetsDir = Join-Path $Root "packaging\msix\assets"
$RequiredBaseAsset = Join-Path $MsixAssetsDir "Square150x150Logo.png"
if (!(Test-Path -LiteralPath $RequiredBaseAsset)) {
    Write-Host "[*] Generating MSIX visual assets from branding master..." -ForegroundColor Cyan
    & $Python (Join-Path $Root "packaging\msix\generate_assets.py")
}

# 4. Prepare staging layout directory
$LayoutDir = Join-Path $Root "build\msix_layout"
if (Test-Path -LiteralPath $LayoutDir) {
    Remove-Item -LiteralPath $LayoutDir -Recurse -Force
}
New-Item -ItemType Directory -Path $LayoutDir -Force | Out-Null

Write-Host "[*] Staging application files into layout directory..." -ForegroundColor Cyan
# Copy dist/Vak content (Vak.exe and _internal)
Copy-Item -Path (Join-Path $DistVak "*") -Destination $LayoutDir -Recurse -Force

# Copy AppxManifest.xml
$ManifestSource = Join-Path $Root "packaging\msix\AppxManifest.xml"
if (!(Test-Path -LiteralPath $ManifestSource)) {
    throw "Manifest missing at $ManifestSource."
}
Copy-Item -LiteralPath $ManifestSource -Destination (Join-Path $LayoutDir "AppxManifest.xml") -Force

# Copy visual assets to Assets folder in layout
$LayoutAssetsDir = Join-Path $LayoutDir "Assets"
New-Item -ItemType Directory -Path $LayoutAssetsDir -Force | Out-Null
Copy-Item -Path (Join-Path $MsixAssetsDir "*") -Destination $LayoutAssetsDir -Recurse -Force

# 5. Pack into MSIX
$DistMsixDir = Join-Path $Root "dist\msix"
if (!(Test-Path -LiteralPath $DistMsixDir)) {
    New-Item -ItemType Directory -Path $DistMsixDir -Force | Out-Null
}

$PackageName = "KrishnaPaliwal.Vak_1.0.0.0_x64.msix"
$PackagePath = Join-Path $DistMsixDir $PackageName

Write-Host "[*] Packaging MSIX: $PackagePath" -ForegroundColor Cyan
& $MakeAppx pack /d $LayoutDir /p $PackagePath /o

$PackageItem = Get-Item -LiteralPath $PackagePath
$PackageSizeMB = [math]::Round($PackageItem.Length / 1MB, 2)
Write-Host "[+] MSIX package created successfully: $PackagePath ($PackageSizeMB MB)" -ForegroundColor Green
Write-Host "[!] Note: For Microsoft Store submission, upload this .msix package directly to Partner Center (Store signs it)." -ForegroundColor Yellow
