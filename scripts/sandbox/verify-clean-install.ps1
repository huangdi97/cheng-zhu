# Clean-install verification INSIDE Windows Sandbox (v1.2-R2 Stage X).
#
# Runs as the sandbox LogonCommand. Windows PowerShell 5.1 only: the sandbox
# has no Python, no Node and no repo checkout, which is the point.
#
#   C:\cz\in   (read-only)  downloaded release files + this script
#   C:\cz\out  (writable)   results.json, screenshots, logs, done.flag
#
# Steps: environment facts -> SHA256 -> installer UI screenshot -> silent
# install -> launch -> own sidecar on 18080 -> onboarding through the API
# (fake local provider, model optional) -> resume -> job goal -> freeze ->
# Live ask: Fast Cue before the first deep chunk -> restart -> persistence
# -> install dir untouched -> uninstall -> portable zip launch.
$ErrorActionPreference = 'Continue'
$In = 'C:\cz\in'
$Out = 'C:\cz\out'
New-Item -ItemType Directory -Force $Out | Out-Null
$Log = Join-Path $Out 'verify.log'
$R = [ordered]@{ started = (Get-Date).ToString('o'); checks = [ordered]@{} }
function Log($m) { $line = "$(Get-Date -Format HH:mm:ss) $m"; Add-Content -Path $Log -Value $line -Encoding UTF8 }
function Check($name, $value) { $R.checks[$name] = $value; Log "CHECK $name = $($value | ConvertTo-Json -Compress -Depth 6)" }

Add-Type -AssemblyName System.Drawing, System.Windows.Forms, System.Net.Http
function Shot($name) {
  try {
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $bmp.Save((Join-Path $Out "$name.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Log "shot $name"
  } catch { Log "shot $name failed: $_" }
}
function Api($path, $method = 'GET', $body = $null) {
  $p = @{ Uri = "http://127.0.0.1:18080$path"; Method = $method; TimeoutSec = 30; UseBasicParsing = $true }
  if ($body -ne $null) { $p.Body = [System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 8)); $p.ContentType = 'application/json; charset=utf-8' }
  $r = Invoke-WebRequest @p
  $text = [System.Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray())
  if ($text.Trim().StartsWith('{') -or $text.Trim().StartsWith('[')) { return $text | ConvertFrom-Json }
  return $text
}
function WaitInstance($seconds) {
  $t0 = Get-Date
  while (((Get-Date) - $t0).TotalSeconds -lt $seconds) {
    try { $i = Api '/api/instance'; if ($i.app -eq 'chengzhu') { return [math]::Round(((Get-Date) - $t0).TotalSeconds, 1) } } catch {}
    Start-Sleep -Milliseconds 700
  }
  return $null
}

try {
  # --- 1. environment ---------------------------------------------------------
  Check 'os' ((Get-CimInstance Win32_OperatingSystem).Caption + ' ' + (Get-CimInstance Win32_OperatingSystem).Version)
  Check 'python_on_path' ([bool](Get-Command python -ErrorAction SilentlyContinue) -or [bool](Get-Command py -ErrorAction SilentlyContinue))
  Check 'node_on_path' ([bool](Get-Command node -ErrorAction SilentlyContinue))
  Check 'repo_checkout_present' (Test-Path 'C:\cz\in\.git')

  # --- 2. checksums ---------------------------------------------------------------
  $sums = @{}
  Get-Content (Join-Path $In 'SHA256SUMS.txt') | ForEach-Object { $p = $_ -split '\s+', 2; if ($p.Count -eq 2) { $sums[$p[1].Trim()] = $p[0].Trim().ToLower() } }
  $shaOk = $true
  foreach ($f in @('Chengzhu-Setup-x64.exe', 'Chengzhu-Portable-x64.zip')) {
    $h = (Get-FileHash (Join-Path $In $f) -Algorithm SHA256).Hash.ToLower()
    Check "sha256_$f" @{ actual = $h; expected = $sums[$f]; match = ($h -eq $sums[$f]) }
    $shaOk = $shaOk -and ($h -eq $sums[$f])
  }
  Check 'sha256_all_match' $shaOk

  # --- 3. installer UI (screenshot), then silent per-user install -------------------
  $setup = Join-Path $In 'Chengzhu-Setup-x64.exe'
  $ui = Start-Process $setup -PassThru
  Start-Sleep -Seconds 8
  Shot 'installer'
  try { Stop-Process -Id $ui.Id -Force } catch {}
  Get-Process | Where-Object { $_.Path -like '*Chengzhu-Setup*' -or $_.ProcessName -like 'Chengzhu-Setup*' } | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
  $t0 = Get-Date
  Start-Process $setup -ArgumentList '/S' -Wait
  Check 'install_seconds' ([math]::Round(((Get-Date) - $t0).TotalSeconds, 1))
  $inst = Join-Path $env:LOCALAPPDATA 'Programs\Chengzhu'
  Check 'install_dir' $inst
  Check 'installed_exe' (Test-Path (Join-Path $inst 'Chengzhu.exe'))
  Check 'bundled_license' ((Test-Path (Join-Path $inst 'resources\LICENSE')) -and ((Get-Content (Join-Path $inst 'resources\LICENSE') -TotalCount 1) -like 'MIT License*'))
  Check 'bundled_notices' (Test-Path (Join-Path $inst 'resources\THIRD_PARTY_NOTICES.md'))
  $beforeList = Get-ChildItem $inst -Recurse -File | ForEach-Object { $_.FullName.Substring($inst.Length) } | Sort-Object

  # --- 4. fake OpenAI-compatible provider (local, in-sandbox) --------------------------
  $fakeJob = Start-Job -ScriptBlock {
    $l = New-Object System.Net.HttpListener
    $l.Prefixes.Add('http://127.0.0.1:18999/')
    $l.Start()
    $answer = '先讲结论：两级缓存加失效广播。本地缓存短 TTL，Redis 作共享层，写后删除并广播失效。'
    while ($l.IsListening) {
      $ctx = $l.GetContext()
      $req = $ctx.Request; $res = $ctx.Response
      $body = (New-Object IO.StreamReader($req.InputStream, [Text.Encoding]::UTF8)).ReadToEnd()
      if ($req.HttpMethod -eq 'GET') {
        $b = [Text.Encoding]::UTF8.GetBytes('{"object":"list","data":[{"id":"fake-model","object":"model"}]}')
        $res.ContentType = 'application/json'; $res.OutputStream.Write($b, 0, $b.Length); $res.Close(); continue
      }
      if ($body -notmatch '"stream"\s*:\s*true') {
        $json = @{ id = 'c1'; object = 'chat.completion'; model = 'fake-model'; choices = @(@{ index = 0; message = @{ role = 'assistant'; content = $answer }; finish_reason = 'stop' }) } | ConvertTo-Json -Depth 6 -Compress
        $b = [Text.Encoding]::UTF8.GetBytes($json); $res.ContentType = 'application/json'; $res.OutputStream.Write($b, 0, $b.Length); $res.Close(); continue
      }
      $res.ContentType = 'text/event-stream'; $res.SendChunked = $true
      for ($i = 0; $i -lt $answer.Length; $i += 6) {
        $piece = $answer.Substring($i, [Math]::Min(6, $answer.Length - $i))
        $chunk = @{ id = 'c1'; object = 'chat.completion.chunk'; model = 'fake-model'; choices = @(@{ index = 0; delta = @{ content = $piece }; finish_reason = $null }) } | ConvertTo-Json -Depth 6 -Compress
        $b = [Text.Encoding]::UTF8.GetBytes("data: $chunk`n`n"); $res.OutputStream.Write($b, 0, $b.Length); $res.OutputStream.Flush()
        Start-Sleep -Milliseconds 30
      }
      $b = [Text.Encoding]::UTF8.GetBytes("data: [DONE]`n`n"); $res.OutputStream.Write($b, 0, $b.Length); $res.Close()
    }
  }

  # --- 5. launch + first screen --------------------------------------------------------
  $app = Start-Process (Join-Path $inst 'Chengzhu.exe') -PassThru
  $ready = WaitInstance 240
  Check 'first_launch_backend_ready_seconds' $ready
  Start-Sleep -Seconds 6
  Shot 'first-launch'
  $inst1 = Api '/api/instance'
  Check 'instance' $inst1
  $cfg0 = Api '/api/config'
  Check 'share_privacy_default' $cfg0.share_privacy_mode
  Check 'onboarding_completed_initially' $cfg0.onboarding_completed
  $appdata = Join-Path $env:APPDATA 'Chengzhu'
  Check 'app_data_dir_exists' (Test-Path $appdata)
  Check 'app_data_layout' ((Get-ChildItem $appdata -Directory -ErrorAction SilentlyContinue | ForEach-Object Name) -join ',')

  # --- 6. onboarding (model optional -> fake local provider), resume, job, freeze -----
  $null = Api '/api/config' 'POST' @{ models = @(@{ name = 'Fake (sandbox)'; api_base_url = 'http://127.0.0.1:18999/v1'; api_key = 'test-key-not-real'; model = 'fake-model'; enabled = $true; supports_think = $false; supports_vision = $false }); active_model = 0; onboarding_completed = $true }
  $cfg1 = Api '/api/config'
  Check 'onboarding_completed_after' $cfg1.onboarding_completed
  $diag = try { Api '/api/intelligence/diagnostics' } catch { "error: $_" }
  Check 'diagnostics_reachable' ($diag -ne $null -and -not ("$diag" -like 'error:*'))
  $resumeText = [IO.File]::ReadAllText((Join-Path $In 'resume.txt'), [Text.Encoding]::UTF8)
  $client = New-Object System.Net.Http.HttpClient
  $mp = New-Object System.Net.Http.MultipartFormDataContent
  $fileContent = New-Object System.Net.Http.ByteArrayContent (, [Text.Encoding]::UTF8.GetBytes($resumeText))
  $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('text/plain')
  $mp.Add($fileContent, 'file', 'resume.txt')
  $up = $client.PostAsync('http://127.0.0.1:18080/api/resume', $mp).Result
  Check 'resume_upload_status' ([int]$up.StatusCode)
  $jd = [IO.File]::ReadAllText((Join-Path $In 'jd.txt'), [Text.Encoding]::UTF8)
  $space = Api '/api/prep/spaces' 'POST' @{ title = '高级后端工程师'; role = '高级后端工程师'; company = '示例公司'; jd_text = $jd; resume_text = $resumeText }
  Check 'job_goal_created' ($space.id -ne $null)
  $launch = Api "/api/prep/spaces/$($space.id)/launch-pack" 'POST' @{}
  $pack = Api '/api/intelligence/pack'
  Check 'pack_frozen' ([bool]$pack.frozen)
  $packId = $pack.pack.id
  Check 'pack_id' $packId

  # --- 7. Live: ask -> guidance_fast before the first answer_chunk ------------------------
  $ws = New-Object System.Net.WebSockets.ClientWebSocket
  $ct = [Threading.CancellationToken]::None
  $ws.ConnectAsync([Uri]'ws://127.0.0.1:18080/ws', $ct).Wait()
  $null = Api '/api/ask' 'POST' @{ text = '你们的缓存一致性是怎么做的？' }
  $types = New-Object System.Collections.Generic.List[string]
  $buf = New-Object byte[] 65536
  $deadline = (Get-Date).AddSeconds(60)
  $firstCueAt = $null; $firstChunkAt = $null
  while ((Get-Date) -lt $deadline -and $ws.State -eq 'Open') {
    $sb = New-Object Text.StringBuilder
    do {
      $seg = New-Object System.ArraySegment[byte] (, $buf)
      $task = $ws.ReceiveAsync($seg, $ct)
      if (-not $task.Wait(20000)) { break }
      $null = $sb.Append([Text.Encoding]::UTF8.GetString($buf, 0, $task.Result.Count))
    } while (-not $task.Result.EndOfMessage)
    try { $msg = $sb.ToString() | ConvertFrom-Json } catch { continue }
    if ($msg.type -eq 'ping') { $pong = [Text.Encoding]::UTF8.GetBytes('{"type":"pong"}'); $ws.SendAsync((New-Object System.ArraySegment[byte] (, $pong)), 'Text', $true, $ct).Wait(); continue }
    $types.Add([string]$msg.type)
    if ($msg.type -eq 'guidance_fast' -and -not $firstCueAt) { $firstCueAt = Get-Date }
    if ($msg.type -eq 'answer_chunk' -and -not $firstChunkAt) { $firstChunkAt = Get-Date }
    if ($msg.type -in @('answer_done', 'answer_error')) { break }
  }
  $cueIdx = $types.IndexOf('guidance_fast'); $chunkIdx = $types.IndexOf('answer_chunk')
  Check 'live_event_types' (($types | Select-Object -Unique) -join ',')
  Check 'fast_cue_before_deep' (($cueIdx -ge 0) -and ($chunkIdx -ge 0) -and ($cueIdx -lt $chunkIdx))
  Check 'answer_done' ($types.Contains('answer_done'))
  Start-Sleep -Seconds 2
  Shot 'live-after-ask'

  # --- 8. restart -> persistence -------------------------------------------------------------
  Get-Process Chengzhu -ErrorAction SilentlyContinue | ForEach-Object { $_.CloseMainWindow() | Out-Null }
  Start-Sleep -Seconds 6
  Get-Process Chengzhu, chengzhu-backend -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 3
  $app2 = Start-Process (Join-Path $inst 'Chengzhu.exe') -PassThru
  Check 'restart_backend_ready_seconds' (WaitInstance 180)
  $pack2 = Api '/api/intelligence/pack'
  Check 'pack_persisted_after_restart' ([bool]$pack2.frozen -and $pack2.pack.id -eq $packId)
  $cfg2 = Api '/api/config'
  Check 'onboarding_persisted' ([bool]$cfg2.onboarding_completed)
  Check 'resume_persisted' ([bool]("$($cfg2.resume_text)".Length -gt 20) -or [bool]$cfg2.has_resume)
  Start-Sleep -Seconds 4
  Shot 'after-restart'
  Get-Process Chengzhu -ErrorAction SilentlyContinue | ForEach-Object { $_.CloseMainWindow() | Out-Null }
  Start-Sleep -Seconds 6
  Get-Process Chengzhu, chengzhu-backend -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 2

  # --- 9. install dir untouched, uninstall ---------------------------------------------------
  $afterList = Get-ChildItem $inst -Recurse -File | ForEach-Object { $_.FullName.Substring($inst.Length) } | Sort-Object
  $diff = Compare-Object $beforeList $afterList
  Check 'install_dir_unchanged_after_use' (-not $diff)
  if ($diff) { Check 'install_dir_diff' (($diff | Select-Object -First 20 | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" }) -join '; ') }
  $uninst = Get-ChildItem $inst -Filter 'Uninstall*.exe' | Select-Object -First 1
  if ($uninst) {
    Start-Process $uninst.FullName -ArgumentList '/S' -Wait
    Start-Sleep -Seconds 8
    Check 'install_dir_removed_by_uninstall' (-not (Test-Path (Join-Path $inst 'Chengzhu.exe')))
    Check 'user_data_kept_after_uninstall' (Test-Path $appdata)
  } else { Check 'uninstaller_found' $false }

  # --- 10. portable ---------------------------------------------------------------------------
  $port = 'C:\cz\portable'
  Expand-Archive (Join-Path $In 'Chengzhu-Portable-x64.zip') -DestinationPath $port -Force
  $pexe = Get-ChildItem $port -Recurse -Filter 'Chengzhu.exe' | Select-Object -First 1
  Check 'portable_exe_found' ([bool]$pexe)
  if ($pexe) {
    $p = Start-Process $pexe.FullName -PassThru
    Check 'portable_backend_ready_seconds' (WaitInstance 240)
    $pk = try { Api '/api/intelligence/pack' } catch { $null }
    Check 'portable_sees_same_user_data' ([bool]($pk -and $pk.pack.id -eq $packId))
    Start-Sleep -Seconds 4
    Shot 'portable-launch'
    Get-Process Chengzhu, chengzhu-backend -ErrorAction SilentlyContinue | Stop-Process -Force
  }
  Stop-Job $fakeJob -ErrorAction SilentlyContinue
} catch {
  Check 'fatal_error' "$_"
} finally {
  $R.finished = (Get-Date).ToString('o')
  $req = @('python_on_path', 'node_on_path', 'sha256_all_match', 'installed_exe', 'first_launch_backend_ready_seconds', 'onboarding_completed_after', 'resume_upload_status', 'pack_frozen', 'fast_cue_before_deep', 'pack_persisted_after_restart', 'install_dir_unchanged_after_use', 'install_dir_removed_by_uninstall', 'portable_backend_ready_seconds')
  $pass = ($R.checks['python_on_path'] -eq $false) -and ($R.checks['node_on_path'] -eq $false) -and ($R.checks['sha256_all_match'] -eq $true) -and ($R.checks['installed_exe'] -eq $true) -and ($R.checks['first_launch_backend_ready_seconds'] -ne $null) -and ($R.checks['onboarding_completed_after'] -eq $true) -and ($R.checks['resume_upload_status'] -eq 200) -and ($R.checks['pack_frozen'] -eq $true) -and ($R.checks['fast_cue_before_deep'] -eq $true) -and ($R.checks['pack_persisted_after_restart'] -eq $true) -and ($R.checks['install_dir_unchanged_after_use'] -eq $true) -and ($R.checks['install_dir_removed_by_uninstall'] -eq $true) -and ($R.checks['portable_backend_ready_seconds'] -ne $null) -and (-not $R.checks.Contains('fatal_error'))
  $R.required_checks = $req
  $R.passed = [bool]$pass
  ($R | ConvertTo-Json -Depth 8) | Set-Content -Path (Join-Path $Out 'results.json') -Encoding UTF8
  Set-Content -Path (Join-Path $Out 'done.flag') -Value 'done'
}
