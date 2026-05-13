# Assign GitHub Project "Workstream" values for SellThrough V1 issues.
# Run from the repo folder:
# powershell -ExecutionPolicy Bypass -File .\scripts\set-workstreams.ps1

$ErrorActionPreference = "Stop"

$Owner = "robertmccarn"
$ProjectNumber = 1
$ProjectId = "PVT_kwHOAzxw084BXhvh"
$WorkstreamFieldName = "Workstream"

Write-Host "Loading project fields..."

$fieldsJson = gh project field-list $ProjectNumber --owner $Owner --format json | ConvertFrom-Json
$workstreamField = $fieldsJson.fields | Where-Object { $_.name -eq $WorkstreamFieldName }

if (-not $workstreamField) {
    throw "Could not find field named '$WorkstreamFieldName'. Confirm it exists in the GitHub Project."
}

$WorkstreamFieldId = $workstreamField.id

function Get-OptionId {
    param(
        [string]$OptionName
    )

    $option = $workstreamField.options | Where-Object { $_.name -eq $OptionName }

    if (-not $option) {
        throw "Could not find Workstream option '$OptionName'. Check spelling in GitHub Projects."
    }

    return $option.id
}

$OptionIds = @{
    "eBay API Integration" = Get-OptionId "eBay API Integration"
    "Data Pipeline & Storage" = Get-OptionId "Data Pipeline & Storage"
    "CLI / Core Logic" = Get-OptionId "CLI / Core Logic"
    "Web UI / Dashboard" = Get-OptionId "Web UI / Dashboard"
    "Quality & Security" = Get-OptionId "Quality & Security"
    "Documentation" = Get-OptionId "Documentation"
    "Research / Blocked Dependencies" = Get-OptionId "Research / Blocked Dependencies"
}

Write-Host "Loading project items..."

$itemsJson = gh project item-list $ProjectNumber --owner $Owner --limit 100 --format json | ConvertFrom-Json

function Get-ProjectItemIdForIssue {
    param(
        [int]$IssueNumber
    )

    $item = $itemsJson.items | Where-Object {
        $_.content.number -eq $IssueNumber
    }

    if (-not $item) {
        throw "Could not find project item for issue #$IssueNumber. Make sure the issue is added to the project."
    }

    return $item.id
}

$Assignments = @{
    "eBay API Integration" = @(27, 32)
    "Data Pipeline & Storage" = @(14, 22, 28, 36)
    "CLI / Core Logic" = @(23, 40)
    "Web UI / Dashboard" = @(15, 20, 24, 33, 34, 37)
    "Quality & Security" = @(30, 38, 42)
    "Documentation" = @(41)
    "Research / Blocked Dependencies" = @(16, 19, 43)
}

foreach ($workstream in $Assignments.Keys) {
    $optionId = $OptionIds[$workstream]

    foreach ($issueNumber in $Assignments[$workstream]) {
        $itemId = Get-ProjectItemIdForIssue $issueNumber

        Write-Host "Setting issue #$issueNumber to Workstream: $workstream"

        gh project item-edit `
            --id $itemId `
            --project-id $ProjectId `
            --field-id $WorkstreamFieldId `
            --single-select-option-id $optionId
    }
}

Write-Host "Done. Workstream assignments applied."