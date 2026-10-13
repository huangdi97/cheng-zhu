param(
  [Parameter(Mandatory = $true)]
  [string]$Version,

  [Parameter(Mandatory = $true)]
  [string]$SourceSha
)

$ErrorActionPreference = "Stop"

$normalizedVersion = [string]$Version
$major = [int]($normalizedVersion.Split('.')[0])
$isPrerelease = $normalizedVersion.Contains('-')

if ($isPrerelease -or $major -lt 2) {
  python scripts/verify_stable_release_source.py `
    --version $normalizedVersion `
    --source-sha $SourceSha `
    --current-main-sha $SourceSha `
    --successful-main-ci-count 0
  if ($LASTEXITCODE -ne 0) { throw "release source verifier failed" }
  exit 0
}

if (-not $env:GH_TOKEN) {
  throw "GH_TOKEN is required for Stable v2+ green-main verification"
}
if (-not $env:GITHUB_REPOSITORY) {
  throw "GITHUB_REPOSITORY is required for Stable v2+ green-main verification"
}

$currentMain = (
  gh api "repos/$env:GITHUB_REPOSITORY/git/ref/heads/main" --jq '.object.sha'
).Trim()

$runs = gh api (
  "repos/$env:GITHUB_REPOSITORY/actions/workflows/ci.yml/runs" +
  "?branch=main&event=push&status=success&per_page=100"
) | ConvertFrom-Json

$successfulMainCiCount = @(
  $runs.workflow_runs | Where-Object {
    [string]$_.head_sha -eq [string]$SourceSha -and
    [string]$_.head_branch -eq "main" -and
    [string]$_.event -eq "push" -and
    [string]$_.conclusion -eq "success"
  }
).Count

python scripts/verify_stable_release_source.py `
  --version $normalizedVersion `
  --source-sha $SourceSha `
  --current-main-sha $currentMain `
  --successful-main-ci-count $successfulMainCiCount
if ($LASTEXITCODE -ne 0) {
  throw "Stable v2+ release source is not the exact current green main"
}
