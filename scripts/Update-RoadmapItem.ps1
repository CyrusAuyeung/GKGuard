param(
  [string]$Url = "",
  [string]$Owner = "CyrusAuyeung",
  [int]$ProjectNumber = 2,
  [ValidateSet("Backlog", "Ready", "In progress", "Review", "Done")]
  [string]$Status = "In progress",
  [ValidateSet("Backend", "Frontend", "Desktop", "CampusVision C1", "Docs", "Release")]
  [string]$Area = "Frontend",
  [ValidateSet("Bug", "Feature", "Task", "Polish")]
  [string]$Type = "Task",
  [ValidateSet("High", "Medium", "Low")]
  [string]$Priority = "Medium",
  [ValidateSet("No", "Yes", "Waiting for data", "Waiting for server", "Waiting for review")]
  [string]$Blocked = "No",
  [string]$StartDate = (Get-Date -Format "yyyy-MM-dd"),
  [string]$EndDate = "",
  [double]$TimelineOrder = 0,
  [string]$TargetVersion = "post-v0.1.24"
)

$ErrorActionPreference = "Stop"

function Invoke-GhJson {
  param([string[]]$Arguments)
  $output = & gh @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "gh $($Arguments -join ' ') failed"
  }
  if ([string]::IsNullOrWhiteSpace($output)) {
    return $null
  }
  return $output | ConvertFrom-Json
}

function Invoke-Gh {
  param([string[]]$Arguments)
  & gh @Arguments | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "gh $($Arguments -join ' ') failed"
  }
}

function Get-Field {
  param([object[]]$Fields, [string]$Name)
  $field = $Fields | Where-Object { $_.name -eq $Name } | Select-Object -First 1
  if (-not $field) {
    throw "Project field '$Name' was not found"
  }
  return $field
}

function Set-SingleSelectField {
  param([string]$Name, [string]$Value)
  $field = Get-Field $fields $Name
  $option = $field.options | Where-Object { $_.name -eq $Value } | Select-Object -First 1
  if (-not $option) {
    throw "Option '$Value' was not found for Project field '$Name'"
  }
  Invoke-Gh @(
    "project", "item-edit",
    "--id", $itemId,
    "--project-id", $projectId,
    "--field-id", $field.id,
    "--single-select-option-id", $option.id
  )
}

function Set-TextField {
  param([string]$Name, [string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return
  }
  $field = Get-Field $fields $Name
  Invoke-Gh @(
    "project", "item-edit",
    "--id", $itemId,
    "--project-id", $projectId,
    "--field-id", $field.id,
    "--text", $Value
  )
}

function Set-DateField {
  param([string]$Name, [string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return
  }
  if ($Value -notmatch "^\d{4}-\d{2}-\d{2}$") {
    throw "Date value for '$Name' must use YYYY-MM-DD"
  }
  $field = Get-Field $fields $Name
  Invoke-Gh @(
    "project", "item-edit",
    "--id", $itemId,
    "--project-id", $projectId,
    "--field-id", $field.id,
    "--date", $Value
  )
}

function Set-NumberField {
  param([string]$Name, [double]$Value)
  if ($Value -le 0) {
    return
  }
  $field = Get-Field $fields $Name
  Invoke-Gh @(
    "project", "item-edit",
    "--id", $itemId,
    "--project-id", $projectId,
    "--field-id", $field.id,
    "--number", $Value.ToString([System.Globalization.CultureInfo]::InvariantCulture)
  )
}

if ([string]::IsNullOrWhiteSpace($Url)) {
  $Url = (& gh pr view --json url --jq ".url" 2>$null)
}

if ([string]::IsNullOrWhiteSpace($Url)) {
  throw "Provide -Url, or run the script from a branch that already has a GitHub PR"
}

$project = Invoke-GhJson @("project", "view", "$ProjectNumber", "--owner", $Owner, "--format", "json")
$projectId = $project.id
$fields = (Invoke-GhJson @("project", "field-list", "$ProjectNumber", "--owner", $Owner, "--format", "json")).fields

$items = (Invoke-GhJson @("project", "item-list", "$ProjectNumber", "--owner", $Owner, "--limit", "200", "--format", "json")).items
$existing = $items | Where-Object { $_.content.url -eq $Url } | Select-Object -First 1

if ($existing) {
  $itemId = $existing.id
  Write-Host "Using existing Roadmap item: $($existing.title)"
} else {
  $added = Invoke-GhJson @("project", "item-add", "$ProjectNumber", "--owner", $Owner, "--url", $Url, "--format", "json")
  $itemId = $added.id
  Write-Host "Added Roadmap item: $Url"
}

Set-SingleSelectField "Status" $Status
Set-SingleSelectField "Area" $Area
Set-SingleSelectField "Type" $Type
Set-SingleSelectField "Priority" $Priority
Set-SingleSelectField "Blocked" $Blocked
Set-DateField "Start date" $StartDate
Set-DateField "End date" $EndDate
Set-NumberField "Timeline order" $TimelineOrder
Set-TextField "Target version" $TargetVersion

$visibleItems = (Invoke-GhJson @("project", "item-list", "$ProjectNumber", "--owner", $Owner, "--limit", "200", "--format", "json")).items
$visible = $visibleItems | Where-Object { $_.id -eq $itemId -or $_.content.url -eq $Url } | Select-Object -First 1

if (-not $visible) {
  throw "Roadmap item was edited, but it is not visible in the Project main item list"
}

[PSCustomObject]@{
  ItemId = $itemId
  Title = $visible.title
  Status = $Status
  Area = $Area
  Type = $Type
  Priority = $Priority
  Blocked = $Blocked
  StartDate = $StartDate
  EndDate = $EndDate
  TimelineOrder = $(if ($TimelineOrder -gt 0) { $TimelineOrder } else { $null })
  TargetVersion = $TargetVersion
  Url = $Url
} | Format-List
