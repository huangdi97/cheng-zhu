// Chengzhu v2 Conversation packaged UI evidence.
//
// This intentionally proves the production frontend bundle + packaged backend
// sidecar on a clean temporary CHENGZHU_HOME. It does NOT claim Electron
// BrowserWindow evidence on hosted runners; the manifest states that boundary.
import { chromium } from 'playwright'
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const APP_VERSION = JSON.parse(fs.readFileSync(path.join(ROOT, 'desktop', 'package.json'), 'utf8')).version
const OUT = path.join(ROOT, 'artifacts', 'release-evidence', 'v' + APP_VERSION, 'conversation-beta')
const RESOURCES = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'resources')
const BACKEND_EXE = path.join(RESOURCES, 'backend', 'chengzhu-backend.exe')
const FRONTEND_DIST = path.join(RESOURCES, 'frontend-dist')
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

function fakeProvider() {
  const server = http.createServer((req, res) => {
    let body = ''
    req.on('data', (chunk) => { body += chunk })
    req.on('end', () => {
      if (req.method === 'GET') {
        res.setHeader('content-type', 'application/json')
        res.end(JSON.stringify({ object: 'list', data: [{ id: 'fake-model', object: 'model' }] }))
        return
      }
      const text = 'Packaged Conversation evidence uses deterministic v2 product logic.'
      const requestBody = body ? JSON.parse(body) : {}
      if (!requestBody.stream) {
        res.setHeader('content-type', 'application/json')
        res.end(JSON.stringify({
          id: 'c', object: 'chat.completion', model: 'fake-model',
          choices: [{ index: 0, message: { role: 'assistant', content: text }, finish_reason: 'stop' }],
        }))
        return
      }
      res.writeHead(200, { 'content-type': 'text/event-stream' })
      res.write('data: ' + JSON.stringify({
        id: 'c', object: 'chat.completion.chunk', model: 'fake-model',
        choices: [{ index: 0, delta: { content: text }, finish_reason: null }],
      }) + '\n\n')
      res.write('data: [DONE]\n\n')
      res.end()
    })
  })
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)))
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
  if (!response.ok) throw new Error(method + ' ' + pathname + ' -> ' + response.status + ': ' + text.slice(0, 600))
  return payload
}

async function waitForBackend(base, proc) {
  const deadline = Date.now() + 120000
  let last = ''
  while (Date.now() < deadline) {
    if (proc.exitCode != null) throw new Error('packaged sidecar exited before ready')
    try {
      const instance = await request(base, 'GET', '/api/instance')
      if (instance.app === 'chengzhu') return
    } catch (error) {
      last = error instanceof Error ? error.message : String(error)
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error('packaged sidecar timeout: ' + last)
}

async function settle(page) {
  await page.waitForTimeout(400)
  await page.locator('[role="status"]').evaluateAll((nodes) =>
    Promise.resolve(nodes.every((node) => !/加载|读取|整理中/.test(node.textContent || '')))
  ).catch(() => true)
}

const entries = []
async function capture(page, name, note) {
  await settle(page)
  const file = path.join(OUT, name + '.png')
  await page.screenshot({ path: file, fullPage: false })
  entries.push({ name, file: path.relative(ROOT, file), note })
  console.log('captured', name)
}

const provider = await fakeProvider()
const backendPort = await freePort()
const base = 'http://127.0.0.1:' + backendPort
const home = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-v2-conversation-evidence-'))
fs.mkdirSync(path.join(home, 'config'), { recursive: true })
fs.writeFileSync(path.join(home, 'config', 'config.json'), JSON.stringify({
  models: [{
    name: 'Fake packaged evidence',
    api_base_url: 'http://127.0.0.1:' + provider.address().port + '/v1',
    api_key: 'not-a-real-key',
    model: 'fake-model',
    enabled: true,
    supports_think: false,
    supports_vision: false,
  }],
  active_model: 0,
  onboarding_completed: true,
  stt_provider: 'whisper',
}))

let sidecar
let browser
let sidecarOut = ''
try {
  sidecar = spawn(BACKEND_EXE, ['--port', String(backendPort), '--host', '127.0.0.1'], {
    cwd: path.dirname(BACKEND_EXE),
    env: {
      ...process.env,
      CHENGZHU_HOME: home,
      CHENGZHU_FRONTEND_DIST: FRONTEND_DIST,
      PYTHONIOENCODING: 'utf-8',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  sidecar.stdout?.on('data', (chunk) => { sidecarOut = (sidecarOut + chunk.toString('utf8')).slice(-16000) })
  sidecar.stderr?.on('data', (chunk) => { sidecarOut = (sidecarOut + chunk.toString('utf8')).slice(-16000) })
  await waitForBackend(base, sidecar)

  // Seed reviewed continuity from a prior Session. The UI evidence that follows
  // must consume this through the real product API, not a Playwright mock.
  const space = await request(base, 'POST', '/api/product/conversation/spaces', {
    title: 'Architecture Sync',
    profile: 'PROJECT_SYNC',
    default_goal: '决定 Conversation Beta rollout boundary',
    default_mode: 'BALANCED',
  })
  await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/participants', {
    display_name: 'Alex',
    role: 'CTO',
    explicit_priority: 'packaged stability',
    explicit_concern: 'rollback safety',
    stated_position: 'beta first',
    decision_authority: 'architecture approval',
    relationship_context: 'client technical lead',
    source_refs: [{ kind: 'USER_INPUT', excerpt: 'explicit packaged evidence fixture' }],
  })
  const prior = await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/sessions', {
    title: 'Prior Architecture Review',
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
  await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/start', {})
  const decision = await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/items', {
    item_type: 'Decision',
    title: 'Conversation Beta 先走 Profile Switcher，不拆独立产品',
    source_refs: [{ kind: 'USER_NOTE', excerpt: '明确确认 beta rollout', visibility: 'PRIVATE' }],
    epistemic_status: 'OBSERVED',
  })
  await request(base, 'POST', '/api/product/conversation/items/' + decision.id + '/review', { action: 'CONFIRM', patch: {} })
  const question = await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/items', {
    item_type: 'OpenQuestion',
    title: '谁负责 Windows packaged beta 的 rollback drill？',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'owner 待确认', visibility: 'PRIVATE' }],
    epistemic_status: 'OBSERVED',
  })
  await request(base, 'POST', '/api/product/conversation/items/' + question.id + '/review', { action: 'CONFIRM', patch: {} })
  await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/end', {})

  browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.addInitScript(() => {
    localStorage.setItem('chengzhu-product-profile', 'conversation')
    localStorage.setItem('chengzhu-conversation-optin', '1')
    localStorage.setItem('ia-color-scheme', 'vscode-light-plus')
  })

  await page.goto(base + '/#/conversation', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('conversation-home').waitFor({ timeout: 30000 })
  await capture(page, '01-conversation-home', 'real packaged Conversation Home with reviewed continuity')

  await page.evaluate((hash) => { window.location.hash = hash }, '#/conversation/spaces/' + space.id)
  await page.getByTestId('conversation-space').waitFor({ timeout: 20000 })
  await capture(page, '02-space-overview', 'Space overview with explicit counterparty and longitudinal state')

  await page.evaluate((hash) => { window.location.hash = hash }, '#/conversation/spaces/' + space.id + '/prepare')
  await page.getByTestId('conversation-space').waitFor({ timeout: 20000 })
  await page.getByText('Session Pack Preview').count().catch(() => 0)
  await capture(page, '03-prepare', 'Prepare before new Session')

  const consent = page.locator('label').filter({ hasText: '我已确认当前场景允许' }).locator('input[type="checkbox"]')
  await consent.check()
  await page.getByRole('button', { name: '生成本场并检查' }).click()
  await page.getByText('Session Pack Preview').waitFor({ timeout: 20000 })
  await capture(page, '04-preflight-pack', 'real Preflight with resolved data path and auditable Session Pack Preview')

  await page.getByRole('button', { name: '开始会话' }).click()
  await page.getByTestId('conversation-live').waitFor({ timeout: 20000 })
  await page.getByTestId('conversation-session-pulse').waitFor({ timeout: 20000 })
  await capture(page, '05-live-session-pulse', 'Guidance-first Live with frozen Session Pulse')

  const askBox = page.getByPlaceholder('例如：之前为什么用 v2？Q4 benchmark 说了什么？刚才是否提到 rollback？')
  await askBox.fill('Conversation Beta rollout')
  await page.getByRole('button', { name: '查本场可用来源' }).click()
  await page.getByText('CONFIRMED_TRUTH').waitFor({ timeout: 15000 })
  await capture(page, '06-manual-ask-provenance', 'Manual Ask returns provenance tier instead of generic chat')

  await page.getByRole('button', { name: '结束并 Continue' }).click()
  await page.getByText('What changed').waitFor({ timeout: 15000 }).catch(() => {})
  await capture(page, '07-continue', 'Continue after real packaged Session end')

  await page.evaluate(() => { window.location.hash = '#/history' })
  await page.getByTestId('conversation-history').waitFor({ timeout: 20000 })
  await capture(page, '08-conversation-history', 'Conversation-only History remains in Conversation Profile')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => { window.location.hash = '#/conversation' })
  await page.getByTestId('conversation-home').waitFor({ timeout: 20000 })
  await capture(page, '09-mobile-390-home', '390px Conversation Home from packaged production bundle')

  const manifest = {
    captured_at: new Date().toISOString(),
    app_version: APP_VERSION,
    evidence_type: 'PACKAGED_SIDECAR_PLUS_PACKAGED_FRONTEND_DIST_PLAYWRIGHT',
    electron_browserwindow_proven: false,
    limitation: 'Hosted-runner Chromium proves packaged production assets and real packaged backend integration, not an interactive Electron BrowserWindow.',
    backend_executable: path.relative(ROOT, BACKEND_EXE),
    frontend_dist: path.relative(ROOT, FRONTEND_DIST),
    space_id: space.id,
    prior_session_id: prior.id,
    entries,
  }
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2))
  if (entries.length !== 9) throw new Error('expected 9 Conversation packaged evidence captures, got ' + entries.length)
  console.log(JSON.stringify(manifest, null, 2))
} catch (error) {
  console.error(error)
  console.error('sidecar output tail:', sidecarOut.slice(-5000))
  throw error
} finally {
  if (browser) await browser.close()
  if (sidecar && sidecar.exitCode == null) {
    if (process.platform === 'win32' && sidecar.pid) spawnSync('taskkill', ['/PID', String(sidecar.pid), '/T', '/F'], { stdio: 'ignore' })
    else sidecar.kill('SIGKILL')
  }
  provider.close()
  fs.rmSync(home, { recursive: true, force: true })
}
