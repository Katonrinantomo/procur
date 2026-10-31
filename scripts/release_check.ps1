<#
.SYNOPSIS
  Release check: run before every push from M20 on, and before the freeze.

.DESCRIPTION
  Runs, in order, and stops at the first failure:
    1. pytest with coverage over app/services (and app/audit once it exists)
    2. coverage report (writes backend/coverage.json)
    3. npm run build (frontend)
    4. Langflow export secrets check + python -m app.flowcheck (live flows)
    5. claims check (README test count vs pytest --collect-only)

  Windows PowerShell 5.1 or later.  From the repo root:
    powershell -ExecutionPolicy Bypass -File scripts\release_check.ps1
  Pass -SkipFlowcheck when Langflow is not running (the run is then NOT a
  full release check and says so at the end).
#>
param(
    [switch]$SkipFlowcheck
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'

$Py = Join-Path $Backend '.venv\Scripts\python.exe'
if (-not (Test-Path $Py)) {
    Write-Host "backend\.venv not found; using python on PATH" -ForegroundColor Yellow
    $Py = 'python'
}

$script:Step = 0
function Invoke-Step {
    param([string]$Name, [string]$Dir, [scriptblock]$Body)
    $script:Step++
    Write-Host ""
    Write-Host "== [$script:Step] $Name" -ForegroundColor Cyan
    Push-Location $Dir
    try {
        $global:LASTEXITCODE = 0
        & $Body
        if ($LASTEXITCODE -ne 0) {
            throw "exit code $LASTEXITCODE"
        }
    }
    catch {
        Write-Host ""
        Write-Host "RELEASE CHECK FAILED at step $script:Step ($Name): $_" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-Host "OK: $Name" -ForegroundColor Green
}

$CovArgs = @('--cov=app/services')
if (Test-Path (Join-Path $Backend 'app\audit')) {
    $CovArgs += '--cov=app/audit'
}

Invoke-Step 'pytest (with coverage)' $Backend {
    & $Py -m pytest -q -p no:cacheprovider @CovArgs --cov-report=
}

Invoke-Step 'coverage report' $Backend {
    & $Py -m coverage report
    if ($LASTEXITCODE -eq 0) { & $Py -m coverage json -q -o coverage.json }
}

Invoke-Step 'npm run build' $Frontend {
    & npm run build
}

if ($SkipFlowcheck) {
    Write-Host ""
    Write-Host "== flowcheck SKIPPED (-SkipFlowcheck)" -ForegroundColor Yellow
}
else {
    Invoke-Step 'flow export secrets check' $Root {
        & $Py scripts\check_langflow_secrets.py
    }
    Invoke-Step 'flowcheck (live Langflow)' $Backend {
        & $Py -m app.flowcheck
    }
}

Invoke-Step 'claims check' $Root {
    & $Py scripts\check_claims.py
}

Write-Host ""
if ($SkipFlowcheck) {
    Write-Host "Release check passed WITHOUT flowcheck; run it again with Langflow up before pushing." -ForegroundColor Yellow
}
else {
    Write-Host "Release check passed." -ForegroundColor Green
}
exit 0
