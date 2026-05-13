# Assign GitHub Project "Priority" values for SellThrough V1 issues.
# Run from the repo folder:
# powershell -ExecutionPolicy Bypass -File .\scripts\set-priorities.ps1

$ErrorActionPreference = "Stop"

$Owner = "robertmccarn"
$ProjectNumber = 1
$ProjectId = "PVT_kwHOAzxw084BXhvh"
$PriorityFieldName = "Priority"

Write-Host "Loading project fields..."

$fieldsJson = gh project field-list $ProjectNumber --owner $Owner --format json | ConvertFrom-Json
$priorityField = $fieldsJson.fields | Where-Object { $_.name -eq $PriorityFieldName }

if (-not $priorityField) {
    throw "Could not find field named '$PriorityFieldName'. Confirm it exists in the GitHub Project."
}

$PriorityFieldId = $priorityField.id

function Get-OptionId {
    param(
        [string]$OptionName
    )

    $option = $priorityField.options | Where-Object { $_.name -eq $OptionName }

    if (-not $option) {
        throw "Could not find Priority option '$OptionName'. Check spelling in GitHub Projects."
    }

    return $option.id
}

# These option names must exactly match your GitHub Project Priority field values.
$OptionIds = @{
    "P0 - Critical" = Get-OptionId "P0 - Critical"
    "P1 - High" = Get-OptionId "P1 - High"
    "P2 - Medium" = Get-OptionId "P2 - Medium"
    "P3 - Low" = Get-OptionId "P3 - Low"
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
    "P0 - Critical" = @(43, 32, 27, 14)
    "P1 - High" = @(42, 41, 38, 36, 34, 19)
    "P2 - Medium" = @(37, 33, 30, 28, 22, 16, 15)
    "P3 - Low" = @(40, 24, 23, 20)
}

foreach ($priority in $Assignments.Keys) {
    $optionId = $OptionIds[$priority]

    foreach ($issueNumber in $Assignments[$priority]) {
        $itemId = Get-ProjectItemIdForIssue $issueNumber

        Write-Host "Setting issue #$issueNumber to Priority: $priority"

        gh project item-edit `
            --id $itemId `
            --project-id $ProjectId `
            --field-id $PriorityFieldId `
            --single-select-option-id $optionId
    }
}

Write-Host "Done. Priority assignments applied."