# Run the V1 E2E validation suite and write a markdown report artifact.
# Usage:
# powershell -ExecutionPolicy Bypass -File .\scripts\run-v1-validation.ps1

$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$reportDir = "reports\validation"
$reportPath = Join-Path $reportDir "v1-validation-report-$timestamp.md"

New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$command = "python -m pytest tests/test_e2e_v1_validation.py -q"
$output = & powershell -NoProfile -Command $command 2>&1
$exitCode = $LASTEXITCODE

$status = if ($exitCode -eq 0) { "PASS" } else { "FAIL" }

$reportLines = @(
    "# V1 Validation Report",
    "",
    "- Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
    "- Command: $command",
    "- Result: **$status**",
    "",
    "## Output",
    "",
    '```text',
    ($output -join "`n"),
    '```'
)
$report = $reportLines -join "`n"

Set-Content -Path $reportPath -Value $report

Write-Host "Validation result: $status"
Write-Host "Report written to: $reportPath"

if ($exitCode -ne 0) {
    exit $exitCode
}
