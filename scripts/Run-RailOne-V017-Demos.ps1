# RailOne v0.17: local synthetic sandbox demos. Run from your RailOne repository root.
# WARNING: Each scenario DROPS and recreates the railone and railone_bank schemas.
# This runner targets only the explicitly named disposable Docker PostgreSQL instance.
param(
    [string]$EvidenceDir = (Join-Path $env:TEMP "railone-v017-evidence")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".\demo_sandbox.py")) {
    throw "Run this script from the RailOne repository root (demo_sandbox.py not found)."
}

$gitRoot = (& git rev-parse --show-toplevel)
if ($LASTEXITCODE -ne 0 -or -not $gitRoot) {
    throw "Not inside a Git repository."
}

$running = (& docker ps --filter "name=^/railone-pg-disposable$" --format "{{.Names}}")
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not accessible. Start Docker Desktop, then retry."
}
if ((@($running) | Where-Object { $_ -eq "railone-pg-disposable" }).Count -eq 0) {
    & docker start railone-pg-disposable | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Cannot start disposable PostgreSQL container." }
}

& docker exec railone-pg-disposable pg_isready -U railone_test -d railone_test
if ($LASTEXITCODE -ne 0) { throw "Disposable PostgreSQL is not ready." }

$published = & docker port railone-pg-disposable 5432/tcp
if ($LASTEXITCODE -ne 0 -or -not (@($published) | Where-Object { $_ -match ':55432$' })) {
    throw "Expected disposable PostgreSQL port 55432 is not published. Refusing schema resets."
}

$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:railone_test@localhost:55432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$scenarios = @("accepted", "timeout", "crash")
foreach ($scenario in $scenarios) {
    $report = Join-Path $EvidenceDir ("v017-" + $scenario + ".json")
    if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report }

    Write-Host "`n==== RailOne v0.17: $scenario ====" -ForegroundColor Cyan
    & python demo_sandbox.py --reset-disposable-db --http-bilateral --scenario $scenario --report-json $report
    if ($LASTEXITCODE -ne 0) { throw "Scenario $scenario failed. No commit should be made." }
    if (-not (Test-Path -LiteralPath $report)) { throw "No evidence report for $scenario." }

    $e = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($e.protocol -ne "RAILONE" -or
        $e.profile -ne "V0.17_INSTITUTIONAL_SANDBOX" -or
        $e.transport -ne "IN_PROCESS_ASGI_HTTP" -or
        $e.scenario -ne $scenario -or
        $e.result -ne "PASS") {
        throw "Evidence metadata check failed for $scenario."
    }

    $checks = [string]::Join("`n", [string[]]$e.checks)
    $required = @(
        "Authenticated sender ETK-S verified over HTTP",
        "Authenticated receiver ETK-R verified against the exact ETK-S",
        "Compromised partner impersonation and amount tampering denied before UTT",
        "Immutable bilateral UTT accepted by authenticated HTTP and persisted to PostgreSQL",
        "Repeated HTTP acceptance returned the same UTT without duplication",
        "Verified committed economic hold through a separate database connection",
        "Recreated dispatcher; duplicate attempt blocked; adapter invoked once",
        "settlement evidence count 0",
        "Authenticated API audit: 4 allowed, 2 denied; all durably recorded"
    )
    switch ($scenario) {
        "accepted" { $required += "Provider submission state ACCEPTED" }
        "timeout"  { $required += "Provider submission state UNKNOWN" }
        "crash"    { $required += "Simulated worker interruption after reservation" }
    }
    foreach ($item in $required) {
        if (-not $checks.Contains($item)) {
            throw "Evidence for $scenario is missing required check: $item"
        }
    }
    Write-Host "PASS: $scenario, verified report $report" -ForegroundColor Green
}

Write-Host "`nALL THREE V0.17 DEMOS PASSED." -ForegroundColor Green
Write-Host "Reports: $EvidenceDir"
Write-Host "No Git changes were committed. Review 'git status --short' and commit the implementation when ready."
