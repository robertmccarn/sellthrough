# Run a docs-aware secret scan during release preparation.
# Usage:
# powershell -ExecutionPolicy Bypass -File .\scripts\scan-secrets-release-docs.ps1

$ErrorActionPreference = "Stop"

$placeholderPattern = '(?i)(your-|example|placeholder|\[REDACTED\]|<token>|<secret>|\*{4,}|dummy|sample)'
$findings = @()

if (Get-Command rg -ErrorAction SilentlyContinue) {
    $rgArgs = @(
        "-n",
        "-i",
        "--no-heading",
        "-g", "*.md",
        "-e", "gho_[A-Za-z0-9_]{20,}",
        "-e", "ghp_[A-Za-z0-9_]{20,}",
        "-e", "github_pat_[A-Za-z0-9_]{20,}",
        "-e", "authorization[[:space:]]*[:=][[:space:]]*bearer[[:space:]]+[A-Za-z0-9._-]{20,}",
        "-e", '(access[_-]?token|client[_-]?secret|ebay_client_secret)[[:space:]]*[:=][[:space:]]*["'']?[A-Za-z0-9._-]{20,}',
        "."
    )
    $matches = & rg @rgArgs 2>$null
    if ($LASTEXITCODE -eq 0 -and $matches) {
        $findings = $matches | Where-Object { $_ -notmatch $placeholderPattern }
    }
}
else {
    $regex = '(?i)(gho_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]{20,}|(access[_-]?token|client[_-]?secret|ebay_client_secret)\s*[:=]\s*["'']?[A-Za-z0-9._-]{20,})'
    $mdFiles = Get-ChildItem -Path . -Recurse -File -Filter *.md
    if ($mdFiles) {
        $matches = $mdFiles | Select-String -Pattern $regex
        if ($matches) {
            $findings = $matches | ForEach-Object { "{0}:{1}:{2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() } | Where-Object { $_ -notmatch $placeholderPattern }
        }
    }
}

if ($findings.Count -gt 0) {
    Write-Host "Potential documentation secret(s) detected:"
    $findings | ForEach-Object { Write-Host $_ }
    exit 1
}

Write-Host "No high-signal documentation secret patterns found."
