// Conversation Beta packaged runtime evidence.
//
// Uses the real packaged sidecar + packaged frontend-dist, not the source tree
// and not a mocked backend.  This complements the existing packaged Electron
// BrowserWindow evidence with Conversation-specific screenshots and a manifest.
import { spawn, spawnSync } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const APP_VERSION = JSON.parse(fs.readFileSync(path.join(ROOT, 'desktop', 'package.json'), 'utf8')).version
const EVIDENCE_VERSION = 'v' + APP_VERSION
const BACKEND_EXE = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'resources', 'backend', 'chengzhu-backend.exe')
const FRONTEND_DIST = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'resources', 'frontend-dist')
const OUT = path.join(ROOT, 'artifacts', 'release-evidence', EVIDENCE_VERSION, 'conversation-beta')
fs.mkdirSync(OUT, { recursive: true })

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const a = server.address()
      const port = typeof a === 'object' && a ? a.port : 0
      server.close(() => resolve(port))
    })
  })
}

async function request(base, method, pathname, body) {
  const res = await fetch(base + pathname, {
    method,
    headers: body === undefined ? undefined : { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  let payload
  try { payload = text ? JSON.parse(text) : {} } catch { payload = { raw: text } }
  if (!res.ok) throw new Error(method + ' ' + pathname + ' -> ' + res.status + ': ' + text.slice(0, 700))
  return payload
}

async function waitReady(base, proc) {
  const deadline = Date.now() + 120000
  let last = ''
  while (Date.now() < deadline) {
    if (proc.exitCode != null) throw new Error('packaged sidecar exited before ready')
    try {
      const instance = await request(base, 'GET', '/api/instance')
      if (instance.app === 'chengzhu') return
      last = 'instance mismatch'
    } catch (e) {
      last = e instanceof Error ? e.message : String(e)
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error('sidecar timeout: ' + last)
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
}

const port = await freePort()
const base = 'http://127.0.0.1:' + port
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-v2-conversation-evidence-'))
fs.mkdirSync(path.join(userData, 'config'), { recursive: true })
fs.writeFileSync(path.join(userData, 'config', 'config.json'), JSON.stringify({
  onboarding_completed: true,
  stt_provider: 'whisper',
  models: [],
  active_model: 0,
}, null, 2))

let sidecar
let browser
const screenshots = []
try {
  sidecar = spawn(BACKEND_EXE, ['--port', String(port), '--host', '127.0.0.1'], {
    cwd: path.dirname(BACKEND_EXE),
    env: {
      ...process.env,
      CHENGZHU_HOME: userData,
      CHENGZHU_FRONTEND_DIST: FRONTEND_DIST,
      CHENGZHU_INSTANCE_NONCE: 'conversation-evidence-' + crypto.randomBytes(8).toString('hex'),
      PYTHONIOENCODING: 'utf-8',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  sidecar.stdout?.on('data', (x) => process.stdout.write('[conversation-sidecar] ' + x.toString('utf8')))
  sidecar.stderr?.on('data', (x) => process.stderr.write('[conversation-sidecar] ' + x.toString('utf8')))
  await waitReady(base, sidecar)

  const space = await request(base, 'POST', '/api/product/conversation/spaces', {
    title: 'Release Architecture Review',
    profile: 'DESIGN_REVIEW',
    default_goal: '确认 rollout owner、rollback drill 与下一步',
    description: 'Conversation Beta packaged evidence',
  })
  const session = await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/sessions', {
    title: 'Release Architecture Review · Session 1',
    capture_mode: 'NOTES_ONLY',
    processing_mode: 'LOCAL',
    assistance_mode: 'BALANCED',
    consent_ack: true,
    policy: {
      ai_assistance: 'AI_ALLOWED',
      human_assistance: 'HUMAN_PRACTICE_ONLY',
      screen_context: 'OFF',
      share_privacy: 'OFF',
      external_writeback: 'REVIEW_REQUIRED',
      participant_consent_status: 'NOT_APPLICABLE',
      participant_transparency_plan: 'NOT_APPLICABLE',
    },
  })
  const preflight = await request(base, 'GET', '/api/product/conversation/sessions/' + session.id + '/preflight')
  if ((preflight.blockers || []).length) throw new Error('Conversation preflight blocked: ' + JSON.stringify(preflight.blockers))
  const started = await request(base, 'POST', '/api/product/conversation/sessions/' + session.id + '/start', {})

  const decision = await request(base, 'POST', '/api/product/conversation/sessions/' + session.id + '/items', {
    item_type: 'Decision',
    title: '先完成 rollback drill，再扩大 rollout',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'release evidence explicit decision', visibility: 'PRIVATE' }],
    epistemic_status: 'OBSERVED',
  })
  await request(base, 'POST', '/api/product/conversation/items/' + decision.id + '/review', { action: 'CONFIRM', patch: {} })
  const risk = await request(base, 'POST', '/api/product/conversation/sessions/' + session.id + '/items', {
    item_type: 'Risk',
    title: 'rollback owner 仍需明确',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'release evidence explicit risk', visibility: 'PRIVATE' }],
    epistemic_status: 'OBSERVED',
  })
  await request(base, 'POST', '/api/product/conversation/items/' + risk.id + '/review', { action: 'CONFIRM', patch: {} })

  browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.goto(base + '/#/conversation', { waitUntil: 'networkidle' })
  await page.evaluate(() => {
    localStorage.setItem('chengzhu-product-profile', 'conversation')
    localStorage.setItem('chengzhu-conversation-optin', '1')
    localStorage.setItem('ia-color-scheme', 'vscode-light-plus')
  })
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForSelector('[data-testid="conversation-home"]', { timeout: 30000 })

  async function capture(name, note) {
    const file = path.join(OUT, name + '.png')
    await page.screenshot({ path: file, fullPage: true })
    screenshots.push({ name, note, file: path.relative(ROOT, file), sha256: sha256(file), url: page.url() })
  }

  await capture('01-conversation-home', 'real packaged Conversation Home')

  await page.goto(base + '/#/conversation/spaces/' + space.id, { waitUntil: 'networkidle' })
  await page.waitForSelector('[data-testid="conversation-space"]', { timeout: 30000 })
  await capture('02-conversation-space', 'real packaged Conversation Space overview with reviewed continuity')

  await page.goto(base + '/#/conversation/spaces/' + space.id + '/prepare', { waitUntil: 'networkidle' })
  await page.waitForSelector('[data-testid="conversation-space"]', { timeout: 30000 })
  await capture('03-conversation-prepare', 'real packaged Prepare surface')

  await page.goto(base + '/#/conversation/live/' + session.id, { waitUntil: 'networkidle' })
  await page.waitForSelector('[data-testid="conversation-live"]', { timeout: 30000 })
  await page.waitForSelector('[data-testid="conversation-session-pulse"]', { timeout: 30000 })
  await capture('04-conversation-live', 'real packaged Live with frozen Session Pulse')

  const ended = await request(base, 'POST', '/api/product/conversation/sessions/' + session.id + '/end', {})
  if (!(ended.decisions || []).length) throw new Error('Continue did not retain reviewed Decision')

  await page.goto(base + '/#/conversation/spaces/' + space.id + '/sessions', { waitUntil: 'networkidle' })
  await page.waitForSelector('[data-testid="conversation-space"]', { timeout: 30000 })
  await capture('05-conversation-sessions', 'real packaged Sessions / Continue entry surface')

  await page.goto(base + '/#/history', { waitUntil: 'networkidle' })
  await page.waitForSelector('[data-testid="conversation-history"]', { timeout: 30000 })
  await capture('06-conversation-history', 'real packaged Conversation-only History')

  const context = await request(base, 'GET', '/api/product/conversation/sessions/' + session.id + '/context')
  const history = await request(base, 'GET', '/api/product/conversation/history?limit=20')
  const manifest = {
    evidence_type: 'PACKAGED_CONVERSATION_WEB_RUNTIME',
    version: APP_VERSION,
    packaged_backend: path.relative(ROOT, BACKEND_EXE),
    packaged_frontend: path.relative(ROOT, FRONTEND_DIST),
    session_id: session.id,
    space_id: space.id,
    pack_digest: context.pack_digest,
    started_status: started.session?.status,
    history_contains_session: (history.items || []).some((x) => x.id === session.id),
    screenshots,
    source_sha: process.env.CHENGZHU_RELEASE_SOURCE_SHA || process.env.GITHUB_SHA || '',
    completed_at: new Date().toISOString(),
  }
  if (!manifest.pack_digest || !manifest.history_contains_session) throw new Error('Conversation packaged evidence integrity check failed')
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2))
  console.log(JSON.stringify(manifest, null, 2))
} finally {
  if (browser) await browser.close().catch(() => {})
  if (sidecar && sidecar.exitCode == null) {
    if (process.platform === 'win32' && sidecar.pid) spawnSync('taskkill', ['/PID', String(sidecar.pid), '/T', '/F'], { stdio: 'ignore' })
    else sidecar.kill('SIGKILL')
  }
}
