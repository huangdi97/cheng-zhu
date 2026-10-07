// Honest hosted-runner fallback for Conversation Beta packaged UI evidence.
//
// It uses the packaged backend sidecar and packaged frontend-dist, but renders
// through Playwright Chromium because hosted Windows may not provide a usable
// interactive Electron desktop. The manifest records that BrowserWindow proof
// is blocked; this file must never be described as Electron UI evidence.
import { chromium } from 'playwright'
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
const BACKEND_EXE = path.join(RESOURCES, 'backend', 'chengzhu-backend.exe')
const FRONTEND_DIST = path.join(RESOURCES, 'frontend-dist')
const OUT = path.join(ROOT, 'artifacts', 'conversation-beta-evidence', 'v' + APP_VERSION, 'web-fallback')
fs.mkdirSync(OUT, { recursive: true })

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer()
    s.once('error', reject)
    s.listen(0, '127.0.0.1', () => {
      const address = s.address()
      const port = typeof address === 'object' && address ? address.port : 0
      s.close(() => resolve(port))
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

async function waitBackend(base, proc, nonce) {
  const deadline = Date.now() + 120000
  while (Date.now() < deadline) {
    if (proc.exitCode != null) throw new Error('packaged sidecar exited before ready')
    try {
      const status = await request(base, 'GET', '/api/instance')
      if (status.app === 'chengzhu' && status.nonce === nonce) return
    } catch {}
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error('packaged sidecar timeout')
}

function killTree(proc) {
  if (!proc || proc.exitCode != null) return
  if (process.platform === 'win32' && proc.pid) spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { stdio: 'ignore' })
  else { try { proc.kill('SIGKILL') } catch {} }
}

async function seed(base) {
  const space = await request(base, 'POST', '/api/product/conversation/spaces', {
    title: 'PDIG · Architecture Review',
    profile: 'DESIGN_REVIEW',
    description: 'Packaged Conversation Beta web-fallback evidence',
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
    source_refs: [{ kind: 'USER_INPUT', excerpt: 'packaged fallback evidence' }],
  })
  const prior = await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/sessions', {
    title: 'Prior Architecture Review',
    capture_mode: 'NOTES_ONLY',
    processing_mode: 'LOCAL',
    assistance_mode: 'BALANCED',
  })
  await request(base, 'GET', '/api/product/conversation/sessions/' + prior.id + '/preflight')
  await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/start', {})
  let decision = await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/items', {
    item_type: 'Decision',
    title: 'offline migration 采用 v2',
    source_refs: [{ kind: 'USER_NOTE', excerpt: '明确采用 v2', visibility: 'PRIVATE' }],
    source_excerpt: '明确采用 v2',
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

async function settle(page) {
  await page.waitForTimeout(350)
}

const port = await freePort()
const base = 'http://127.0.0.1:' + port
const nonce = crypto.randomBytes(18).toString('hex')
const home = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-v2-conversation-web-'))
fs.mkdirSync(path.join(home, 'config'), { recursive: true })
fs.writeFileSync(path.join(home, 'config', 'config.json'), JSON.stringify({
  onboarding_completed: true,
  stt_provider: 'whisper',
  doubao_stt_api_key: '',
  doubao_stt_access_token: '',
  candidate_stt_provider: 'whisper',
  candidate_remote_stt_enabled: false,
  share_privacy_mode: 'OFF',
}, null, 2))

let sidecar
let browser
let sidecarOut = ''
const entries = []
async function shot(page, name, note) {
  await settle(page)
  const file = path.join(OUT, name + '.png')
  await page.screenshot({ path: file, fullPage: false })
  entries.push({ name, note, file: path.relative(ROOT, file) })
}

try {
  sidecar = spawn(BACKEND_EXE, ['--port', String(port), '--host', '127.0.0.1'], {
    cwd: path.dirname(BACKEND_EXE),
    env: {
      ...process.env,
      CHENGZHU_HOME: home,
      CHENGZHU_FRONTEND_DIST: FRONTEND_DIST,
      CHENGZHU_INSTANCE_NONCE: nonce,
      PYTHONIOENCODING: 'utf-8',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  sidecar.stdout?.on('data', (chunk) => { sidecarOut = (sidecarOut + chunk.toString('utf8')).slice(-16000) })
  sidecar.stderr?.on('data', (chunk) => { sidecarOut = (sidecarOut + chunk.toString('utf8')).slice(-16000) })
  await waitBackend(base, sidecar, nonce)
  const scenario = await seed(base)

  browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  await context.addInitScript(() => {
    localStorage.setItem('chengzhu-product-profile', 'conversation')
    localStorage.setItem('chengzhu-conversation-optin', '1')
    localStorage.setItem('ia-color-scheme', 'vscode-light-plus')
  })
  const page = await context.newPage()

  await page.goto(base + '/#/conversation', { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.getByTestId('conversation-home').waitFor({ timeout: 30000 })
  await shot(page, '01-conversation-home', 'Packaged frontend-dist Conversation Home')

  await page.goto(base + '/#/conversation/spaces/' + scenario.space.id, { waitUntil: 'domcontentloaded' })
  await page.getByTestId('conversation-space').waitFor({ timeout: 30000 })
  await shot(page, '02-conversation-space', 'Space overview with real packaged backend data')

  await page.goto(base + '/#/conversation/spaces/' + scenario.space.id + '/prepare', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('conversation-space').waitFor({ timeout: 30000 })
  await shot(page, '03-conversation-prepare', 'Prepare')
  await page.getByTestId('conversation-generate-preflight').click()
  await page.getByTestId('conversation-start-session').waitFor({ timeout: 30000 })
  await shot(page, '04-conversation-preflight', 'Resolved Data Path + Session Pack Preview')
  await page.getByTestId('conversation-start-session').click()
  await page.getByTestId('conversation-live').waitFor({ timeout: 30000 })
  await page.getByTestId('conversation-session-pulse').waitFor({ timeout: 30000 })
  await shot(page, '05-conversation-live', 'Live Participate + frozen Session Pulse')

  await page.getByTestId('conversation-end-session').click()
  await page.getByTestId('conversation-return-continue').waitFor({ timeout: 30000 })
  await shot(page, '06-conversation-inline-continue', 'Inline Continue after ending')
  await page.getByTestId('conversation-return-continue').click()
  await page.getByTestId('conversation-space').waitFor({ timeout: 30000 })
  await shot(page, '07-conversation-space-sessions', 'Return to same Space')

  await page.goto(base + '/#/history', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('conversation-history').waitFor({ timeout: 30000 })
  await shot(page, '08-conversation-history', 'Profile-aware Conversation History')

  await page.evaluate(() => localStorage.setItem('ia-color-scheme', 'vscode-dark-plus'))
  await page.goto(base + '/#/conversation', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('conversation-home').waitFor({ timeout: 30000 })
  await shot(page, '09-conversation-dark-home', 'Dark Conversation Home')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => localStorage.setItem('ia-color-scheme', 'vscode-light-plus'))
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByTestId('conversation-home').waitFor({ timeout: 30000 })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  if (overflow) throw new Error('390px Conversation Home has horizontal overflow')
  await shot(page, '10-conversation-mobile-390', '390px Conversation Home')

  const diagnostics = await request(base, 'GET', '/api/product/conversation/diagnostics')
  const manifest = {
    captured_at: new Date().toISOString(),
    contract: 'v2.0-R1',
    evidence_type: 'PACKAGED_CONVERSATION_FRONTEND_DIST_VIA_PACKAGED_SIDECAR_HEADLESS_CHROMIUM',
    browserwindow_evidence: 'BLOCKED_HOSTED_WINDOWS_RUNNER_NO_INTERACTIVE_DESKTOP',
    backend_executable: BACKEND_EXE,
    frontend_dist: FRONTEND_DIST,
    source_space_id: scenario.space.id,
    entries,
    conversation_runtime: diagnostics.runtime,
    real_audio_capture: 'NOT_PROVEN_ON_HOSTED_WINDOWS_RUNNER',
    real_conversation_user_evidence: 'REAL_CONVERSATION_USER_EVIDENCE_PENDING',
    pmf: 'PMF_PROVEN_FALSE',
  }
  fs.writeFileSync(path.join(OUT, 'conversation-manifest.json'), JSON.stringify(manifest, null, 2))
  if (entries.length < 10) throw new Error('expected at least 10 Conversation fallback captures')
  console.log('Conversation packaged web fallback complete:', OUT)
} catch (error) {
  console.error(error)
  console.error('sidecar output tail:', sidecarOut.slice(-5000))
  throw error
} finally {
  if (browser) await browser.close().catch(() => undefined)
  killTree(sidecar)
}
