param(
    [switch]$Installer
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

$Icon = Join-Path $Root "assets\branding\ico\vak.ico"
if (!(Test-Path -LiteralPath $Icon)) {
    $FallbackIcon = Join-Path $Root "assets\vak.ico"
    if (!(Test-Path -LiteralPath $FallbackIcon)) {
        & $Python (Join-Path $Root "scripts\make_icon.py") $FallbackIcon
    }
}

Push-Location $Root
try {
    & $Python -m PyInstaller --clean --noconfirm "packaging\vak.spec"
} finally {
    Pop-Location
}

if ($Installer) {
    $IsccCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )
    $IsccCmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($IsccCmd) {
        $Iscc = $IsccCmd.Source
    } else {
        $Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (!$Iscc -or !(Test-Path $Iscc)) {
        throw "Inno Setup 6 was not found. Install it or run without -Installer."
    }
    & $Iscc (Join-Path $Root "packaging\vak.iss")
}
