param(
  [Parameter(Mandatory = $true)]
  [string]$Path,

  [Parameter(Mandatory = $true)]
  [string]$TagSha,

  [Parameter(Mandatory = $true)]
  [ValidateSet("STABLE", "PRERELEASE")]
  [string]$ReleaseChannel,

  [Parameter(Mandatory = $true)]
  [bool]$IsPrerelease
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Path)) {
  throw "release verification file not found: $Path"
}

$verification = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
if ($null -eq $verification) {
  throw "release verification JSON is empty: $Path"
}

# ConvertFrom-Json returns a PSCustomObject whose shape is fixed to the
# properties present in the source JSON. Direct assignment to a missing
# property throws under PowerShell. Add-Member -Force safely handles both
# existing and new fields, which is required because pre-publish verification
# intentionally writes tag_sha=null and omits publication-only metadata.
$verification | Add-Member -NotePropertyName "tag_sha" -NotePropertyValue $TagSha -Force
$verification | Add-Member -NotePropertyName "release_channel" -NotePropertyValue $ReleaseChannel -Force
$verification | Add-Member -NotePropertyName "is_prerelease" -NotePropertyValue $IsPrerelease -Force

$verification | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding utf8
