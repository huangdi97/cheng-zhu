// Packaged Conversation Beta BrowserWindow evidence.
//
// Uses the real packaged backend sidecar and the real packaged Chengzhu.exe.
// The renderer is driven through the existing file-plan evidence mode in
// desktop/main.js; every screenshot therefore comes from BrowserWindow.capturePage().
//
// Hosted Windows may still block offscreen BrowserWindow/CDP. The workflow has
// a separate packaged-frontend/headless-Chromium fallback that records that
// limitation explicitly instead of pretending it is BrowserWindow evidence.
import { spawn, spawnSync } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const APP_VERSION = JSON.parse(fs.readFileSync(path.join(ROOT, 'desktop', 'package.json'), 'utf8')).version
const RESOURCES = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'resources')
const EXE = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'Chengzhu.exe')
const BACKEND_EXE = path.join(RESOURCES, 'backend', 'chengzhu-backend.exe')
const FRONTEND_DIST = path.join(RESOURCES, 'frontend-dist')
const OUT = path.join(ROOT, 'artifacts', 'conversation-beta-evidence', 'v' + APP_VERSION, 'browserwindow')
fs.mkdirSync(OUT, { recursive: true })

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close(() => resolve(port))
    })
  })
}

async function request(base, method, pathname, body) {
  const response = await fetch(base + pathname, {
    method,
    headers: body === undefined ? undefined : { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await response.text()
  let payload
  try { payload = text ? JSON.parse(text) : {} } catch { payload = { raw: text } }
  if (!response.ok) throw new Error(method + ' ' + pathname + ' -> ' + response.status + ': ' + text.slice(0, 500))
  return payload
}

async function waitForBackend(base, proc, nonce) {
  const deadline = Date.now() + 120000
  let last = ''
  while (Date.now() < deadline) {
    if (proc.exitCode != null) throw new Error('packaged sidecar exited before ready')
    try {
      const status = await request(base, 'GET', '/api/instance')
      if (status.app === 'chengzhu' && status.nonce === nonce) return
      last = 'nonce mismatch'
    } catch (error) {
      last = error instanceof Error ? error.message : String(error)
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error('packaged sidecar timeout: ' + last)
}

async function waitForFile(file, proc, timeoutMs = 180000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'))
    if (proc.exitCode != null) throw new Error('packaged app exited before evidence result, code=' + proc.exitCode)
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error('Conversation BrowserWindow evidence timed out')
}

function killTree(proc) {
  if (!proc || proc.exitCode != null) return
  if (process.platform === 'win32' && proc.pid) {
    spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    try { proc.kill('SIGKILL') } catch {}
  }
}

async function seedConversation(base) {
  const space = await request(base, 'POST', '/api/product/conversation/spaces', {
    title: 'PDIG · Architecture Review',
    profile: 'DESIGN_REVIEW',
    description: 'Packaged Conversation Beta evidence',
    default_goal: '决定 offline migration rollout 与 rollback owner',
  })
  const goal = await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/goals', {
    title: '明确 rollout owner 与 rollback 条件',
    outcome_definition: 'Decision、owner 与 next step 均有来源',
    priority: 90,
  })
  await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/participants', {
    display_name: 'Alex',
    role: 'Backend',
    explicit_priority: '迁移稳定性',
    explicit_concern: 'rollback 风险',
    stated_position: '先灰度',
    decision_authority: '架构方案批准人',
    relationship_context: '项目后端负责人',
    source_refs: [{ kind: 'USER_INPUT', excerpt: 'packaged evidence explicit participant context' }],
  })

  const prior = await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/sessions', {
    title: 'Prior Architecture Review',
    capture_mode: 'NOTES_ONLY',
    processing_mode: 'LOCAL',
    assistance_mode: 'BALANCED',
    consent_ack: false,
  })
  await request(base, 'GET', '/api/product/conversation/sessions/' + prior.id + '/preflight')
  await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/start', {})

  let decision = await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/items', {
    item_type: 'Decision',
    title: 'offline migration 采用 v2',
    source_refs: [{ kind: 'USER_NOTE', excerpt: '明确决定采用 v2', visibility: 'PRIVATE' }],
    source_excerpt: '明确决定采用 v2',
    epistemic_status: 'OBSERVED',
  })
  decision = await request(base, 'POST', '/api/product/conversation/items/' + decision.id + '/review', {
    action: 'CONFIRM', patch: {},
  })

  let open = await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/items', {
    item_type: 'OpenQuestion',
    title: 'rollback owner 还没有明确',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'owner 尚未确认', visibility: 'PRIVATE' }],
    source_excerpt: 'owner 尚未确认',
    epistemic_status: 'OBSERVED',
  })
  open = await request(base, 'POST', '/api/product/conversation/items/' + open.id + '/review', {
    action: 'CONFIRM', patch: {},
  })
  await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/end', {})
  return { space, goal, decision, open }
}

async function runPlan({ userData, backendBase, nonce, token, scenario }) {
  const planPath = path.join(userData, 'conversation-beta-plan.json')
  const resultPath = path.join(userData, 'conversation-beta-result.json')
  const statusPath = path.join(userData, 'conversation-beta-status.json')
  const steps = [
    { kind: 'storage', key: 'chengzhu-product-profile', value: 'conversation' },
    { kind: 'storage', key: 'chengzhu-conversation-optin', value: '1' },
    { kind: 'storage', key: 'ia-color-scheme', value: 'vscode-light-plus' },
    { kind: 'navigate', hash: '#/conversation', selector: '[data-testid="conversation-home"]', timeout_ms: 30000 },
    { kind: 'capture', name: '01-conversation-home', note: 'Packaged Conversation Home with longitudinal Next Focus' },

    { kind: 'navigate', hash: '#/conversation/spaces/' + scenario.space.id, selector: '[data-testid="conversation-space"]', timeout_ms: 30000 },
    { kind: 'capture', name: '02-conversation-space', note: 'Packaged Space overview with reviewed Open Threads and explicit counterparty state' },

    { kind: 'navigate', hash: '#/conversation/spaces/' + scenario.space.id + '/prepare', selector: '[data-testid="conversation-space"]', timeout_ms: 30000 },
    { kind: 'capture', name: '03-conversation-prepare', note: 'Prepare before creating the next Session' },
    { kind: 'click', selector: '[data-testid="conversation-generate-preflight"]' },
    { kind: 'wait', selector: '[data-testid="conversation-start-session"]', timeout_ms: 30000 },
    { kind: 'capture', name: '04-conversation-preflight', note: 'Preflight with resolved data path, AI behavior and Session Pack Preview' },

    { kind: 'click', selector: '[data-testid="conversation-start-session"]' },
    { kind: 'wait', selector: '[data-testid="conversation-live"]', timeout_ms: 30000 },
    { kind: 'wait', selector: '[data-testid="conversation-session-pulse"]', timeout_ms: 30000 },
    { kind: 'capture', name: '05-conversation-live', note: 'Live Participate view with one primary Guidance surface and frozen Session Pulse' },

    { kind: 'capture', name: '06-conversation-live-context', note: 'Frozen Goal / Open Threads / data path remain visible beside Live' },
    { kind: 'click', selector: '[data-testid="conversation-end-session"]' },
    { kind: 'wait', selector: '[data-testid="conversation-return-continue"]', timeout_ms: 30000 },
    { kind: 'capture', name: '07-conversation-inline-continue', note: 'Continue summary immediately after ending the packaged Session' },
    { kind: 'click', selector: '[data-testid="conversation-return-continue"]' },
    { kind: 'wait', selector: '[data-testid="conversation-space"]', timeout_ms: 30000 },
    { kind: 'capture', name: '08-conversation-space-sessions', note: 'Return to same Space after Continue' },

    { kind: 'navigate', hash: '#/history', selector: '[data-testid="conversation-history"]', timeout_ms: 30000 },
    { kind: 'capture', name: '09-conversation-history', note: 'History remains inside Conversation Profile' },

    { kind: 'storage', key: 'ia-color-scheme', value: 'vscode-dark-plus' },
    { kind: 'reload', selector: '[data-testid="conversation-history"]', timeout_ms: 30000 },
    { kind: 'navigate', hash: '#/conversation', selector: '[data-testid="conversation-home"]', timeout_ms: 30000 },
    { kind: 'capture', name: '10-conversation-dark-home', note: 'Conversation Home dark theme' },

    { kind: 'storage', key: 'ia-color-scheme', value: 'vscode-light-plus' },
    { kind: 'resize', width: 390, height: 844 },
    { kind: 'reload', selector: '[data-testid="conversation-home"]', timeout_ms: 30000 },
    { kind: 'capture', name: '11-conversation-mobile-390', note: 'Conversation Home at 390px packaged BrowserWindow' },
  ]
  fs.writeFileSync(planPath, JSON.stringify({ auto_quit: true, steps }, null, 2))

  let stdout = ''
  let stderr = ''
  const proc = spawn(EXE, [], {
    env: {
      ...process.env,
      CHENGZHU_USER_DATA_DIR: userData,
      CHENGZHU_RUNTIME_EVIDENCE: '1',
      CHENGZHU_EVIDENCE_BACKEND_URL: backendBase,
      CHENGZHU_INSTANCE_NONCE: nonce,
      CHENGZHU_RUNTIME_EVIDENCE_TOKEN: token,
      CHENGZHU_RUNTIME_EVIDENCE_DIR: OUT,
      CHENGZHU_RUNTIME_EVIDENCE_PLAN: planPath,
      CHENGZHU_RUNTIME_EVIDENCE_RESULT: resultPath,
      CHENGZHU_RUNTIME_EVIDENCE_STATUS: statusPath,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  proc.stdout?.on('data', (chunk) => { stdout = (stdout + chunk.toString('utf8')).slice(-16000) })
  proc.stderr?.on('data', (chunk) => { stderr = (stderr + chunk.toString('utf8')).slice(-16000) })
  try {
    const result = await waitForFile(resultPath, proc)
    if (!result.ok) throw new Error(result.error || 'Conversation evidence plan failed')
    return result
  } catch (error) {
    console.error('app stdout tail:', stdout.slice(-5000))
    console.error('app stderr tail:', stderr.slice(-5000))
    if (fs.existsSync(statusPath)) console.error('evidence status:', fs.readFileSync(statusPath, 'utf8'))
    throw error
  } finally {
    killTree(proc)
  }
}

const backendPort = await freePort()
const backendBase = 'http://127.0.0.1:' + backendPort
const nonce = crypto.randomBytes(18).toString('hex')
const token = crypto.randomBytes(18).toString('hex')
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-v2-conversation-evidence-'))
fs.mkdirSync(path.join(userData, 'config'), { recursive: true })
fs.writeFileSync(path.join(userData, 'config', 'config.json'), JSON.stringify({
  onboarding_completed: true,
  stt_provider: 'whisper',
  doubao_stt_api_key: '',
  doubao_stt_access_token: '',
  candidate_stt_provider: 'whisper',
  candidate_remote_stt_enabled: false,
  share_privacy_mode: 'OFF',
}, null, 2))

let backend
let backendOut = ''
try {
  backend = spawn(BACKEND_EXE, ['--port', String(backendPort), '--host', '127.0.0.1'], {
    cwd: path.dirname(BACKEND_EXE),
    env: {
      ...process.env,
      CHENGZHU_HOME: userData,
      CHENGZHU_FRONTEND_DIST: FRONTEND_DIST,
      CHENGZHU_INSTANCE_NONCE: nonce,
      PYTHONIOENCODING: 'utf-8',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  backend.stdout?.on('data', (chunk) => { backendOut = (backendOut + chunk.toString('utf8')).slice(-16000) })
  backend.stderr?.on('data', (chunk) => { backendOut = (backendOut + chunk.toString('utf8')).slice(-16000) })
  await waitForBackend(backendBase, backend, nonce)

  const scenario = await seedConversation(backendBase)
  const result = await runPlan({ userData, backendBase, nonce, token, scenario })
  const diagnostics = await request(backendBase, 'GET', '/api/product/conversation/diagnostics')
  const manifest = {
    ...result,
    contract: 'v2.0-R1',
    evidence_type: 'PACKAGED_CONVERSATION_BROWSERWINDOW_WITH_PACKAGED_SIDECAR',
    backend_executable: BACKEND_EXE,
    executable: EXE,
    frontend_dist: FRONTEND_DIST,
    source_space_id: scenario.space.id,
    conversation_runtime: diagnostics.runtime,
    real_audio_capture: 'NOT_PROVEN_ON_HOSTED_WINDOWS_RUNNER',
    real_conversation_user_evidence: 'REAL_CONVERSATION_USER_EVIDENCE_PENDING',
    pmf: 'PMF_PROVEN_FALSE',
  }
  fs.writeFileSync(path.join(OUT, 'conversation-manifest.json'), JSON.stringify(manifest, null, 2))
  if ((manifest.entries || []).length < 11) throw new Error('expected at least 11 Conversation packaged captures')
  console.log('Conversation packaged BrowserWindow evidence complete:', OUT)
} catch (error) {
  console.error(error)
  console.error('sidecar output tail:', backendOut.slice(-5000))
  throw error
} finally {
  killTree(backend)
}
