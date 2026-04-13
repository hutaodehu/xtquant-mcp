param(
    [string]$RepoRoot = "D:\xtquant-mcp\repo",
    [string]$PythonHome = "C:\Python313\python.exe",
    [string]$VenvPath = "D:\xtquant-mcp\venv313",
    [string]$BundleRoot = "D:\xtquant-mcp\vendor\xtquant_250807",
    [switch]$InstallPython,
    [switch]$ForceRecreateVenv
)

$ErrorActionPreference = "Stop"

function Resolve-PythonHome {
    param([string]$RequestedPythonHome, [switch]$AllowInstall)

    if (Test-Path -LiteralPath $RequestedPythonHome) {
        return (Resolve-Path -LiteralPath $RequestedPythonHome).Path
    }

    $py313 = ""
    try {
        $py313 = (& py -3.13 -c "import sys; print(sys.executable)") 2>$null
    } catch {
        $py313 = ""
    }
    if ($LASTEXITCODE -eq 0 -and $py313) {
        return $py313.Trim()
    }

    if (-not $AllowInstall) {
        throw "Python 3.13 not found at $RequestedPythonHome. Re-run with -InstallPython or install Python 3.13 manually."
    }

    $installRoot = Split-Path -Parent $RequestedPythonHome
    winget install `
        --id Python.Python.3.13 `
        --exact `
        --accept-package-agreements `
        --accept-source-agreements `
        --scope machine `
        --location $installRoot `
        --silent

    if (Test-Path -LiteralPath $RequestedPythonHome) {
        return (Resolve-Path -LiteralPath $RequestedPythonHome).Path
    }

    $py313 = (& py -3.13 -c "import sys; print(sys.executable)") 2>$null
    if ($LASTEXITCODE -eq 0 -and $py313) {
        return $py313.Trim()
    }

    throw "Python 3.13 installation did not expose a usable interpreter."
}

$resolvedPython = Resolve-PythonHome -RequestedPythonHome $PythonHome -AllowInstall:$InstallPython
$venvPython = Join-Path $VenvPath "Scripts\python.exe"

if ($ForceRecreateVenv -and (Test-Path -LiteralPath $VenvPath)) {
    Remove-Item -LiteralPath $VenvPath -Recurse -Force
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $resolvedPython -m venv $VenvPath
}

& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -e $RepoRoot

$sitePackages = (& $venvPython -c "import site; print(next(path for path in site.getsitepackages() if path.endswith('site-packages')))").Trim()
& $venvPython (Join-Path $RepoRoot "scripts\verify_xtquant_bundle.py") --bundle-root $BundleRoot --write-pth $sitePackages --import-check

$summary = @{
    ok = $true
    python_home = $resolvedPython
    venv_python = $venvPython
    bundle_root = $BundleRoot
    repo_root = $RepoRoot
    site_packages = $sitePackages
}
$summary | ConvertTo-Json -Depth 4
