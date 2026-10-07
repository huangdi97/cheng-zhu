// Packaged Conversation Beta UI evidence.
//
// This is intentionally separate from the Interview BrowserWindow evidence.
// It always drives the production frontend bundle served by the packaged
// sidecar, so the evidence remains reproducible on hosted Windows runners even
// when Electron cannot open an interactive desktop.
//
// Truth boundary:
//   PACKAGED_FRONTEND_DIST + PACKAGED_SIDECAR = proven
//   Electron BrowserWindow = not claimed by this harness
//   real microphone / loopback hardware = not claimed
import { chromium } from 'playwright'
import { spawn, spawnSync } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const APP_VERSION = JSON.parse(fs.readFileSync(path.join(ROOT, 'desktop', 'package.json'), 'utf8')).version
const EVIDENCE_VERSION = 'v' + APP_VERSION
const RESOURCES = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'resources')
const BACKEND_EXE = path.join(RESOURCES, 'backend', 'chengzhu-backend.exe')
const FRONTEND_DIST = path.join(RESOURCES, 'frontend-dist')
const OUT = path.join(ROOT, 'artifacts', 'release-evidence', EVIDENCE_VERSION, 'conversation-beta')
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
  const answer = '这是 packaged Conversation Beta runtime evidence 的本地 fake provider。'
  const server = http.createServer((req, res) => {
    let body = ''
    req.on('data', (chunk) => { body += chunk })
    req.on('end', () => {
      if (req.method === 'GET') {
        res.setHeader('content-type', 'application/json')
        res.end(JSON.stringify({ object: 'list', data: [{ id: 'fake-model', object: 'model' }] }))
        return
      }
      const requestBody = body ? JSON.parse(body) : {}
      if (!requestBody.stream) {
        res.setHeader('content-type', 'application/json')
        res.end(JSON.stringify({
          id: 'conversation-evidence',
          object: 'chat.completion',
          model: 'fake-model',
          choices: [{ index: 0, message: { role: 'assistant', content: answer }, finish_reason: 'stop' }],
        }))
        return
      }
      res.writeHead(200, { 'content-type': 'text/event-stream' })
      res.write('data: ' + JSON.stringify({
        id: 'conversation-evidence',
        object: 'chat.completion.chunk',
        model: 'fake-model',
        choices: [{ index: 0, delta: { content: answer }, finish_reason: null }],
      }) + '\n\n')
      res.write('data: [DONE]\n\n')
      res.end()
    })
  })
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)))
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

async function formRequest(base, pathname, fields) {
  const form = new FormData()
  for (const [key, value] of Object.entries(fields)) form.append(key, String(value))
  const res = await fetch(base + pathname, { method: 'POST', body: form })
  const text = await res.text()
  if (!res.ok) throw new Error('POST ' + pathname + ' -> ' + res.status + ': ' + text.slice(0, 700))
  return JSON.parse(text)
}

async function waitForBackend(base, proc, nonce) {
  const deadline = Date.now() + 120000
  let last = ''
  while (Date.now() < deadline) {
    if (proc.exitCode != null) throw new Error('packaged sidecar exited before ready')
    try {
      const status = await request(base, 'GET', '/api/instance')
      if (status.app === 'chengzhu' && status.nonce === nonce) return status
      last = 'instance nonce mismatch'
    } catch (error) {
      last = error instanceof Error ? error.message : String(error)
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error('packaged Conversation sidecar timeout: ' + last)
}

async function settle(page, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const busy = await page.locator('[role="status"]').evaluateAll((nodes) =>
      nodes.some((node) => /加载|读取|整理中/.test(node.textContent || ''))
    ).catch(() => false)
    if (!busy) {
      await page.waitForTimeout(300)
      return
    }
    await page.waitForTimeout(150)
  }
  throw new Error('Conversation UI did not settle: ' + await page.url())
}

const entries = []
async function shot(page, name, note) {
  await settle(page)
  const file = path.join(OUT, name + '.png')
  await page.screenshot({ path: file, fullPage: true })
  entries.push({ name, file: path.relative(ROOT, file), note })
  console.log('captured', name)
}

async function go(page, hash, selector) {
  await page.evaluate((h) => { window.location.hash = h }, hash)
  if (selector) await page.locator(selector).waitFor({ timeout: 30000 })
  await settle(page)
}

const provider = await fakeProvider()
const backendPort = await freePort()
const base = 'http://127.0.0.1:' + backendPort
const nonce = crypto.randomBytes(18).toString('hex')
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-conversation-packaged-evidence-'))
fs.mkdirSync(path.join(userData, 'config'), { recursive: true })
fs.writeFileSync(path.join(userData, 'config', 'config.json'), JSON.stringify({
  models: [{
    name: 'Fake Conversation runtime evidence',
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
  practice_delivery_analytics_enabled: true,
}, null, 2))

let sidecar
let browser
let sidecarOut = ''
try {
  sidecar = spawn(BACKEND_EXE, ['--port', String(backendPort), '--host', '127.0.0.1'], {
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
  sidecar.stdout?.on('data', (chunk) => {
    const text = chunk.toString('utf8')
    sidecarOut = (sidecarOut + text).slice(-16000)
    process.stdout.write('[sidecar] ' + text)
  })
  sidecar.stderr?.on('data', (chunk) => {
    const text = chunk.toString('utf8')
    sidecarOut = (sidecarOut + text).slice(-16000)
    process.stderr.write('[sidecar] ' + text)
  })
  await waitForBackend(base, sidecar, nonce)

  // Seed real packaged product state. Source text is intentionally long enough
  // to enter READY synchronously in the current material lifecycle.
  const material = await formRequest(base, '/api/product/materials', {
    title: 'Q4 Architecture Benchmark',
    kind: 'PROJECT',
    usage: 'FACTS',
    text: 'Q4 benchmark validated offline migration at 10x data scale. The rollback owner remains open and must be confirmed before the release window. '.repeat(3),
    background: 'false',
  })
  const note = await request(base, 'POST', '/api/product/quick-notes', {
    title: 'Design Review reminder',
    content: '先确认 rollback owner，再谈 rollout window。Quick Note 不是 confirmed evidence。',
    scope: 'GLOBAL',
    pinned: true,
    tags: ['conversation-beta'],
  })
  const space = await request(base, 'POST', '/api/product/conversation/spaces', {
    title: 'PDIG · Packaged Architecture Review',
    profile: 'DESIGN_REVIEW',
    description: 'Packaged Conversation Beta visual evidence',
    default_goal: '决定 offline migration rollout 条件',
    selected_source_ids: [material.id],
    selected_quick_note_ids: [note.id],
  })
  await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/participants', {
    display_name: 'Alex',
    role: 'Backend Lead',
    organization: 'PDIG',
    explicit_priority: '迁移稳定性',
    explicit_concern: '回滚风险',
    stated_position: '先确认 rollback owner',
    decision_authority: '架构方案批准人',
    relationship_context: '项目技术负责人',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'Alex 明确关注回滚风险', visibility: 'PRIVATE' }],
  })
  const goal = await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/goals', {
    title: '形成 conflict merge strategy 决策',
    outcome_definition: '方案、owner 与 rollout 条件明确',
    priority: 90,
  })

  // Create one ended prior session so Home/Space show real continuity.
  const prior = await request(base, 'POST', '/api/product/conversation/spaces/' + space.id + '/sessions', {
    title: 'Architecture Review · Prior',
    goal_ids: [goal.id],
    capture_mode: 'NOTES_ONLY',
    processing_mode: 'LOCAL',
    assistance_mode: 'BALANCED',
    consent_ack: true,
    policy: {
      screen_context: 'OFF',
      ai_assistance: 'AI_ALLOWED',
      human_assistance: 'HUMAN_PRACTICE_ONLY',
      share_privacy: 'OFF',
      external_writeback: 'REVIEW_REQUIRED',
      participant_consent_status: 'NOT_APPLICABLE',
      participant_transparency_plan: 'NOT_APPLICABLE',
    },
  })
  await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/start', {})
  const decision = await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/items', {
    item_type: 'Decision',
    title: 'offline migration 采用 v2',
    state: 'PROPOSED',
    source_refs: [{ kind: 'USER_NOTE', excerpt: '明确采用 v2', visibility: 'PRIVATE' }],
    source_excerpt: '明确采用 v2',
    confidence: 1,
    epistemic_status: 'OBSERVED',
  })
  await request(base, 'POST', '/api/product/conversation/items/' + decision.id + '/review', {
    action: 'CONFIRM', patch: {},
  })
  const openQuestion = await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/items', {
    item_type: 'OpenQuestion',
    title: 'rollback owner 还没有明确',
    state: 'PROPOSED',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'owner 未确认', visibility: 'PRIVATE' }],
    confidence: 1,
    epistemic_status: 'OBSERVED',
  })
  await request(base, 'POST', '/api/product/conversation/items/' + openQuestion.id + '/review', {
    action: 'CONFIRM', patch: {},
  })
  await request(base, 'POST', '/api/product/conversation/sessions/' + prior.id + '/end', {})

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
  await shot(page, '01-conversation-home', 'Packaged Conversation Home with cross-session continuity')

  await go(page, '#/conversation/spaces/' + space.id, '[data-testid="conversation-space"]')
  await shot(page, '02-conversation-space', 'Packaged Conversation Space overview with reviewed continuity')

  await go(page, '#/conversation/spaces/' + space.id + '/prepare', '[data-testid="conversation-space"]')
  await shot(page, '03-prepare', 'Packaged Prepare with agenda, source and counterparty context')

  await page.getByRole('button', { name: '生成本场并检查' }).click()
  await page.getByText('Session Pack Preview').waitFor({ timeout: 20000 })
  await shot(page, '04-preflight-pack-preview', 'Packaged Preflight + auditable frozen Session Pack Preview')

  await page.getByRole('button', { name: '开始会话' }).click()
  await page.getByTestId('conversation-live').waitFor({ timeout: 20000 })
  const liveUrl = page.url()
  const match = liveUrl.match(/conversation\/live\/([^/?#]+)/)
  if (!match) throw new Error('cannot resolve live Conversation session id from ' + liveUrl)
  const liveSessionId = match[1]

  await request(base, 'POST', '/api/product/conversation/sessions/' + liveSessionId + '/guidance/evaluate', {
    direct_question: '本场最重要的下一步是什么？',
    answer_cue: '先确认 rollback owner，再决定 rollout window。',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'packaged visual evidence source', visibility: 'PRIVATE' }],
  })
  await page.getByText('先确认 rollback owner，再决定 rollout window。').waitFor({ timeout: 15000 })
  await shot(page, '05-live-guidance', 'Packaged Live with frozen Session Pulse and sourced Guidance')

  await page.getByRole('button', { name: '结束并 Continue' }).click()
  await page.getByText('这场之后').waitFor({ timeout: 15000 })
  await shot(page, '06-continue', 'Packaged Continue with reviewed longitudinal state')

  await go(page, '#/history', '[data-testid="conversation-history"]')
  await shot(page, '07-history', 'Packaged Conversation-native History')

  await page.setViewportSize({ width: 390, height: 844 })
  await go(page, '#/conversation', '[data-testid="conversation-home"]')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  if (overflow) throw new Error('390px Conversation Home has horizontal overflow')
  await shot(page, '08-mobile-390-home', 'Packaged Conversation Home at 390px')

  const manifest = {
    captured_at: new Date().toISOString(),
    evidence_type: 'PACKAGED_CONVERSATION_FRONTEND_DIST_VIA_PACKAGED_SIDECAR_HEADLESS_CHROMIUM',
    electron_browserwindow: 'NOT_CLAIMED_BY_THIS_HARNESS',
    real_audio_hardware: 'NOT_CLAIMED',
    backend_executable: BACKEND_EXE,
    frontend_dist: FRONTEND_DIST,
    space_id: space.id,
    prior_session_id: prior.id,
    live_session_id: liveSessionId,
    entries,
  }
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2))
  if (entries.length !== 8) throw new Error('expected 8 Conversation packaged captures, got ' + entries.length)
  console.log('Conversation packaged UI evidence complete captures=' + entries.length)
} catch (error) {
  console.error(error)
  console.error('sidecar output tail:', sidecarOut.slice(-5000))
  throw error
} finally {
  if (browser) await browser.close().catch(() => undefined)
  if (sidecar && sidecar.exitCode == null) {
    if (process.platform === 'win32' && sidecar.pid) spawnSync('taskkill', ['/PID', String(sidecar.pid), '/T', '/F'], { stdio: 'ignore' })
    else sidecar.kill('SIGKILL')
  }
  provider.close()
}
