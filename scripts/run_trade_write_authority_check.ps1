param(
    [string]$RepoRoot = "C:\xtquant-mcp-example\repo",
    [string]$InstanceRoot = "C:\xtquant-mcp-example\instance\prod",
    [string]$PythonExe = "",
    [string]$AuthoritySourcePath = ""
)

$ErrorActionPreference = "Stop"

function Resolve-PythonExe {
    param([string]$RequestedPythonExe)

    if ($RequestedPythonExe -and (Test-Path -LiteralPath $RequestedPythonExe)) {
        return (Resolve-Path -LiteralPath $RequestedPythonExe).Path
    }

    $venvPython = "C:\xtquant-mcp-example\venv313\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return (Resolve-Path -LiteralPath $venvPython).Path
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

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "No usable Python interpreter found."
}

$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$resolvedInstanceRoot = (Resolve-Path -LiteralPath $InstanceRoot).Path
$resolvedPythonExe = Resolve-PythonExe -RequestedPythonExe $PythonExe
$resolvedAuthoritySourcePath = if ($AuthoritySourcePath) {
    (Resolve-Path -LiteralPath $AuthoritySourcePath).Path
} else {
    Join-Path $resolvedInstanceRoot "state\trade_resources\trade_write_authority_source_latest.json"
}
$outputPath = Join-Path $resolvedInstanceRoot "state\trade_resources\trade_write_authority_latest.json"

Push-Location $resolvedRepoRoot
try {
    & $resolvedPythonExe -m xtqmt_mcp.trade_write_authority `
        --instance-root $resolvedInstanceRoot `
        --authority-source-path $resolvedAuthoritySourcePath `
        --output-path $outputPath
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
