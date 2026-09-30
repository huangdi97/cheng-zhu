# Host side: run the clean-install verification in Windows Sandbox.
#
#   powershell -ExecutionPolicy Bypass -File scripts\sandbox\run-clean-install.ps1 -ReleaseDir <dir with downloaded assets> -OutDir <evidence dir>
#
# ReleaseDir must hold the files downloaded from the GitHub Release
# (Chengzhu-Setup-x64.exe, Chengzhu-Portable-x64.zip, SHA256SUMS.txt). They are
# mapped read-only into a fresh sandbox together with the verification script
# and two small fixtures; results come back through a writable mapped folder.
param(
  [Parameter(Mandatory = $true)][string]$ReleaseDir,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [int]$TimeoutMinutes = 40
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$stage = Join-Path $env:TEMP ("chengzhu-sandbox-in-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force $stage, $OutDir | Out-Null
Get-ChildItem $OutDir -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
foreach ($f in @('Chengzhu-Setup-x64.exe', 'Chengzhu-Portable-x64.zip', 'SHA256SUMS.txt')) {
  Copy-Item (Join-Path $ReleaseDir $f) $stage
}
Copy-Item (Join-Path $here 'verify-clean-install.ps1') $stage
Copy-Item (Join-Path $here 'resume.txt') $stage
Copy-Item (Join-Path $here 'jd.txt') $stage
$outFull = (Resolve-Path $OutDir).Path
$wsb = @"
<Configuration>
  <VGpu>Enable</VGpu>
  <Networking>Enable</Networking>
  <MemoryInMB>6144</MemoryInMB>
  <MappedFolders>
    <MappedFolder><HostFolder>$stage</HostFolder><SandboxFolder>C:\cz\in</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$outFull</HostFolder><SandboxFolder>C:\cz\out</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\cz\in\verify-clean-install.ps1</Command></LogonCommand>
</Configuration>
"@
$wsbPath = Join-Path $stage 'chengzhu-clean-install.wsb'
Set-Content -Path $wsbPath -Value $wsb -Encoding UTF8
Write-Host "Starting Windows Sandbox: $wsbPath"
Start-Process "$env:windir\System32\WindowsSandbox.exe" -ArgumentList "`"$wsbPath`""
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
while ((Get-Date) -lt $deadline -and -not (Test-Path (Join-Path $OutDir 'done.flag'))) { Start-Sleep -Seconds 10 }
if (-not (Test-Path (Join-Path $OutDir 'done.flag'))) { Write-Host 'TIMEOUT'; exit 2 }
Get-Content (Join-Path $OutDir 'results.json') -Raw -Encoding UTF8
# Close the sandbox (it discards all state).
Get-Process WindowsSandboxClient, WindowsSandboxRemoteSession, WindowsSandbox -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$res = Get-Content (Join-Path $OutDir 'results.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($res.passed) { exit 0 } else { exit 1 }
