// Fallback packaged UI evidence for hosted Windows runners without an
// interactive desktop.
//
// This script never pretends to be BrowserWindow evidence. It launches the
// *packaged backend sidecar* and serves the *packaged frontend-dist* from the
// win-unpacked resources, then drives that production bundle in Playwright
// Chromium. The manifest explicitly records that Electron BrowserWindow
// capture is BLOCKED_HOSTED_RUNNER. Product behavior, routes, API integration,
// migrations and rendered production assets remain real packaged artifacts.
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
const OUT = path.join(ROOT, 'artifacts', 'release-evidence', EVIDENCE_VERSION)
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
  const answer = '先给结论：知识频繁更新且需要来源追溯时优先 RAG；稳定行为与风格才更偏向微调。'
  const server = http.createServer((req, res) => {
    let body = ''
    req.on('data', (chunk) => { body += chunk })
    req.on('end', () => {
      if (req.method === 'GET') {
        res.setHeader('content-type', 'application/json')
        res.end(JSON.stringify({ object: 'list', data: [{ id: 'fake-model', object: 'model' }] }))
        return
      }
      const request = body ? JSON.parse(body) : {}
      if (!request.stream) {
        res.setHeader('content-type', 'application/json')
        res.end(JSON.stringify({
          id: 'c', object: 'chat.completion', model: 'fake-model',
          choices: [{ index: 0, message: { role: 'assistant', content: answer }, finish_reason: 'stop' }],
        }))
        return
      }
      res.writeHead(200, { 'content-type': 'text/event-stream' })
      res.write('data: ' + JSON.stringify({
        id: 'c', object: 'chat.completion.chunk', model: 'fake-model',
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
  if (!res.ok) throw new Error(method + ' ' + pathname + ' -> ' + res.status + ': ' + text.slice(0, 500))
  return payload
}

async function formRequest(base, pathname, fields) {
  const form = new FormData()
  for (const [key, value] of Object.entries(fields)) form.append(key, String(value))
  const res = await fetch(base + pathname, { method: 'POST', body: form })
  const text = await res.text()
  if (!res.ok) throw new Error('POST ' + pathname + ' -> ' + res.status + ': ' + text.slice(0, 500))
  return JSON.parse(text)
}

async function waitForBackend(base, proc, nonce) {
  const deadline = Date.now() + 120000
  let last = ''
  while (Date.now() < deadline) {
    if (proc.exitCode != null) throw new Error('packaged sidecar exited before it was ready')
    try {
      const status = await request(base, 'GET', '/api/instance')
      if (status.app === 'chengzhu' && status.nonce === nonce) return status
      last = 'instance nonce mismatch'
    } catch (error) {
      last = error instanceof Error ? error.message : String(error)
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error('packaged sidecar timeout: ' + last)
}

const provider = await fakeProvider()
const backendPort = await freePort()
const base = 'http://127.0.0.1:' + backendPort
const nonce = crypto.randomBytes(18).toString('hex')
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-runtime-web-evidence-'))
fs.mkdirSync(path.join(userData, 'config'), { recursive: true })
fs.writeFileSync(path.join(userData, 'config', 'config.json'), JSON.stringify({
  models: [{
    name: 'Fake runtime evidence',
    api_base_url: 'http://127.0.0.1:' + provider.address().port + '/v1',
    api_key: 'not-a-real-key',
    model: 'fake-model',
    enabled: true,
    supports_think: false,
    supports_vision: false,
  }],
  active_model: 0,
  onboarding_completed: false,
  stt_provider: 'whisper',
  practice_delivery_analytics_enabled: true,
}))

let sidecar
let browser
let sidecarOut = ''
const entries = []

async function settle(page, timeoutMs = 12000) {
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
  throw new Error('UI did not settle before evidence capture: ' + await page.url())
}

async function shot(page, name, note) {
  await settle(page)
  const file = path.join(OUT, name + '.png')
  await page.screenshot({ path: file, fullPage: false })
  entries.push({ name, file: path.relative(ROOT, file), note })
  console.log('captured', name)
}

async function go(page, hash, selector) {
  await page.evaluate((h) => { window.location.hash = h }, hash)
  if (selector) await page.locator(selector).waitFor({ timeout: 30000 })
  await settle(page)
}

async function completeOnboarding(page) {
  const wizard = page.getByTestId('onboarding')
  await wizard.waitFor({ timeout: 30000 })
  await shot(page, '01-onboarding-web-fallback', 'packaged frontend first-run onboarding; BrowserWindow blocked by hosted runner')

  for (let i = 0; i < 8; i++) {
    await wizard.getByTestId('onboarding-next').click()
    await page.waitForTimeout(120)
  }
  await wizard.getByTestId('onboarding-goal-company').fill('Onboarding Demo')
  await wizard.getByTestId('onboarding-goal-role').fill('AI Agent Engineer')
  await wizard.getByTestId('onboarding-goal-jd').fill('负责 Agent、RAG、评估与系统设计。')
  await shot(page, '01b-first-goal-web-fallback', 'first Goal inside packaged frontend onboarding')
  await wizard.getByTestId('onboarding-next').click()

  await wizard.getByTestId('guided-start').click()
  await wizard.getByTestId('guided-question').waitFor({ timeout: 20000 })
  await shot(page, '01c-guided-question-web-fallback', 'Guided First Practice question')

  await wizard.getByTestId('guided-cue').click()
  await wizard.getByTestId('guided-fast-cue').waitFor({ timeout: 30000 })
  await shot(page, '01d-guided-cue-web-fallback', 'real Fast Cue using packaged sidecar + fake provider')

  // Browser fallback cannot instantiate Electron Overlay. Exercise the explicit
  // product fallback state instead and record it honestly.
  await wizard.getByTestId('guided-overlay-toggle').click()
  await expectText(wizard.getByTestId('guided-overlay-state'), '没有 Electron Overlay')
  await shot(page, '01e-guided-overlay-blocked', 'Overlay correctly reports unavailable outside Electron BrowserWindow')

  await wizard.getByTestId('guided-note').fill('Redis 没做过 Cluster；只讲 session state。')
  await wizard.getByTestId('guided-note-save').click()
  await page.waitForTimeout(300)
  await shot(page, '01f-guided-note-web-fallback', 'Quick Note created during first practice')

  await wizard.getByTestId('guided-answer').fill('先给结论：知识更新频繁且需要来源追溯，所以这个场景优先用 RAG。')
  await wizard.getByTestId('guided-submit').click()
  await wizard.getByTestId('guided-reflection').waitFor({ timeout: 20000 })
  await wizard.getByTestId('guided-practice-complete').waitFor({ timeout: 20000 })
  await shot(page, '01g-guided-reflection-web-fallback', 'Demo Reflection closes onboarding product loop')

  await wizard.getByTestId('onboarding-next').click()
  await wizard.getByTestId('onboarding-complete-step').waitFor({ timeout: 5000 })
  await shot(page, '01h-onboarding-complete-web-fallback', 'Goal-centered onboarding completion')
  await wizard.getByTestId('onboarding-finish').click()
  await page.getByTestId('action-home').waitFor({ timeout: 10000 })
}

async function expectText(locator, text) {
  const deadline = Date.now() + 10000
  while (Date.now() < deadline) {
    const value = await locator.textContent().catch(() => '')
    if ((value || '').includes(text)) return
    await new Promise((r) => setTimeout(r, 200))
  }
  throw new Error('expected text not found: ' + text)
}

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

  browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  await page.goto(base + '/', { waitUntil: 'domcontentloaded', timeout: 60000 })

  await completeOnboarding(page)

  const resume = 'WenNian：我负责 RAG 检索链路，用 Redis 管理 session state。'
  await request(base, 'POST', '/api/intelligence/candidate/rebuild', { resume_text: resume, interview_notes: '' })
  await request(base, 'POST', '/api/config', { resume_text: resume })

  const goal = await request(base, 'POST', '/api/product/goals', {
    company: 'MindRank',
    role: 'AIDD Agent Engineer',
    jd: '负责 Agent / RAG / CADD；要求系统设计、评估与高可用。',
    stage: '技术二面',
    interview_round: 'TECHNICAL',
    next_interview_at: Math.floor(Date.now() / 1000) + 86400,
  })
  await request(base, 'POST', '/api/product/goals/' + goal.id + '/interviews', {
    round: '技术二面', scheduled_at: Math.floor(Date.now() / 1000) + 86400,
    kind: 'REAL', notes: 'v1.3 packaged evidence',
  })
  const material = await formRequest(base, '/api/product/materials', {
    title: 'WenNian 架构说明', kind: 'PROJECT', usage: 'FACTS',
    text: 'Redis 只用于 session state，没有 Redis Cluster 生产经历。', background: 'false',
  })
  const note = await request(base, 'POST', '/api/product/quick-notes', {
    title: 'MindRank 二面速记',
    content: 'Redis：只讲 session state；反问 Agent eval 上线门槛。',
    scope: 'GOAL', goal_id: goal.id, pinned: true, tags: ['想问'],
  })
  const bank = await request(base, 'POST', '/api/product/question-banks', {
    name: 'AIDD Agent 深挖', scope: 'GOAL', role: 'AI_ML', goal_id: goal.id,
  })
  await request(base, 'POST', '/api/product/question-banks/' + bank.id + '/items', {
    text: '如果 Agent 线上效果下降，你怎么定位？',
    category: 'SYSTEM_DESIGN', difficulty: 'STANDARD', origin: 'USER_ADDED', rounds: ['TECHNICAL'],
  })
  await request(base, 'PATCH', '/api/product/goals/' + goal.id, {
    selected_material_ids: [material.id],
    selected_quick_note_ids: [note.id],
    active_question_bank_ids: [bank.id],
    role_family: 'AI_ML',
  })

  const practice = await request(base, 'POST', '/api/product/practice', {
    goal_id: goal.id, round: 'TECHNICAL', personas: ['TECH_LEAD', 'HIRING_MANAGER'],
    demeanor: 'SKEPTICAL', difficulty: 'PRESSURE', sources: ['GOAL_GRAPH', 'ROLE_BANK'],
    questions: 2, language: 'zh', human_coach: false, delivery_analytics: true,
  })
  await request(base, 'POST', '/api/product/practice/' + practice.practice_id + '/answer', {
    answer: '先给结论，我会同时看离线回归集、线上成功率和失败分桶。',
  })
  await request(base, 'POST', '/api/product/practice/' + practice.practice_id + '/finish', {})

  const conversationSpace = await request(base, 'POST', '/api/product/conversation/spaces', {
    title: 'Architecture Weekly',
    profile: 'PROJECT_SYNC',
    description: 'packaged Conversation web-fallback evidence',
    default_goal: '把 rollout 决策与未决 rollback owner 带到下一场',
  })
  await request(base, 'POST', '/api/product/conversation/spaces/' + conversationSpace.id + '/participants', {
    display_name: 'Alex',
    role: 'CTO',
    explicit_priority: 'migration stability',
    explicit_concern: 'rollback risk',
    source_refs: [{ kind: 'USER_INPUT', excerpt: 'packaged evidence fixture', visibility: 'PRIVATE' }],
  })
  const endedConversation = await request(base, 'POST', '/api/product/conversation/spaces/' + conversationSpace.id + '/sessions', {
    title: 'Architecture Review #1',
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
  await request(base, 'POST', '/api/product/conversation/sessions/' + endedConversation.id + '/start', {})
  const packagedDecision = await request(base, 'POST', '/api/product/conversation/sessions/' + endedConversation.id + '/items', {
    item_type: 'Decision',
    title: '采用 staged rollout',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'reviewed packaged evidence', visibility: 'PRIVATE' }],
    source_excerpt: 'reviewed packaged evidence',
    epistemic_status: 'OBSERVED',
  })
  await request(base, 'POST', '/api/product/conversation/items/' + packagedDecision.id + '/review', { action: 'CONFIRM', patch: {} })
  const packagedQuestion = await request(base, 'POST', '/api/product/conversation/sessions/' + endedConversation.id + '/items', {
    item_type: 'OpenQuestion',
    title: '谁负责 rollback drill？',
    source_refs: [{ kind: 'USER_NOTE', excerpt: 'owner unresolved', visibility: 'PRIVATE' }],
    source_excerpt: 'owner unresolved',
    epistemic_status: 'OBSERVED',
  })
  await request(base, 'POST', '/api/product/conversation/items/' + packagedQuestion.id + '/review', { action: 'CONFIRM', patch: {} })
  await request(base, 'POST', '/api/product/conversation/sessions/' + endedConversation.id + '/end', {})

  const activeConversation = await request(base, 'POST', '/api/product/conversation/spaces/' + conversationSpace.id + '/sessions', {
    title: 'Architecture Review #2',
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
  await request(base, 'POST', '/api/product/conversation/sessions/' + activeConversation.id + '/start', {})

  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByTestId('action-home').waitFor({ timeout: 30000 })
  await shot(page, '02-action-home', 'Action Home')

  const routes = [
    ['#/goals', '[data-testid="goals-page"]', '03-goals', 'Goal list'],
    ['#/goals/' + goal.id, '[data-testid="goal-room"]', '04-goal-overview', 'Goal Room overview'],
    ['#/goals/' + goal.id + '/prepare', '[data-testid="goal-room"]', '05-goal-prepare', 'Goal Prepare'],
    ['#/goals/' + goal.id + '/interviews', '[data-testid="goal-room"]', '06-goal-interviews', 'Goal interviews'],
    ['#/goals/' + goal.id + '/offer', '[data-testid="goal-room"]', '07-goal-offer', 'Offer metadata'],
    ['#/me/resume', '[data-testid="me-page"]', '08-me-resume', 'Person resume'],
    ['#/me/inbox', '[data-testid="me-page"]', '09-fact-inbox', 'Fact Inbox'],
    ['#/me/stories', '[data-testid="me-page"]', '10-stories', 'Stories 3.0'],
    ['#/library/materials', '[data-testid="library-page"]', '11-materials', 'Material lifecycle'],
    ['#/library/notes', '[data-testid="library-page"]', '12-quick-notes', 'Quick Notes'],
    ['#/library/banks', '[data-testid="library-page"]', '13-question-banks', 'Question Banks'],
    ['#/practice?goal=' + goal.id, '[data-testid="practice-setup"]', '14-practice-setup', 'Practice 3.0'],
    ['#/practice/' + practice.practice_id, '[data-testid="practice-session"]', '15-panel-practice', 'Panel practice'],
    ['#/reflection/practice/' + practice.practice_id, '[data-testid="reflection-page"]', '16-reflection', 'Reflection'],
    ['#/settings/live', '[data-testid="settings-page"]', '17-settings-live', 'Settings + Overlay preferences'],
    ['#/settings/diagnostics', '[data-testid="settings-page"]', '18-validation', 'v1.4 validation UI'],
    ['#/history', '[data-testid="history-page"]', '19-history', 'History'],
  ]
  for (const [hash, selector, name, noteText] of routes) {
    await go(page, hash, selector)
    await shot(page, name, noteText)
  }

  await go(page, '#/home', '[data-testid="action-home"]')
  await page.keyboard.press('Control+K')
  await page.getByTestId('command-palette').waitFor({ timeout: 5000 })
  await shot(page, '20-command-palette', 'Ctrl+K contextual commands')
  await page.keyboard.press('Escape')

  await go(page, '#/goals/' + goal.id, '[data-testid="goal-room"]')
  await page.getByTestId('go-live').click()
  await page.getByTestId('preflight').waitFor({ timeout: 10000 })
  await shot(page, '21-preflight', 'Preflight 3.0')
  await page.getByTestId('preflight-start').click()
  await page.getByTestId('live-status-line').waitFor({ timeout: 15000 })
  await shot(page, '22-live-idle', 'Live Cockpit idle')
  await request(base, 'POST', '/api/ask', { text: 'RAG 和微调怎么选？' })
  await page.getByTestId('fast-cue').first().waitFor({ timeout: 30000 })
  await shot(page, '23-live-fast-cue', 'Fast Cue before Deep')
  await page.waitForTimeout(1200)
  await shot(page, '24-live-deep', 'Deep second layer')

  await page.keyboard.press('Control+P')
  await page.getByTestId('pin-dialog').waitFor({ timeout: 5000 })
  await shot(page, '25-pin', 'Pin Moment')
  await page.keyboard.press('Escape')

  await page.getByTestId('live-quick-notes').click()
  await page.getByTestId('quick-notes-drawer').waitFor({ timeout: 5000 })
  await shot(page, '26-live-notes', 'Live Quick Notes')
  await page.keyboard.press('Escape')

  await request(base, 'POST', '/api/ask', { text: '你还有什么想问我们的吗？' })
  await page.getByTestId('closing-panel').waitFor({ timeout: 15000 })
  await shot(page, '27-closing', 'Closing Mode')

  await page.evaluate(() => localStorage.setItem('ia-color-scheme', 'vscode-dark-plus'))
  await page.reload({ waitUntil: 'domcontentloaded' })
  await go(page, '#/home', '[data-testid="action-home"]')
  await shot(page, '28-dark-home', 'Dark theme')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => localStorage.setItem('ia-color-scheme', 'vscode-light-plus'))
  await page.reload({ waitUntil: 'domcontentloaded' })
  await go(page, '#/goals/' + goal.id + '/prepare', '[data-testid="goal-room"]')
  await shot(page, '29-mobile-390-goal-prepare', '390px Goal Prepare')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  if (overflow) throw new Error('390px Goal Prepare has horizontal overflow')

  // Switch the packaged production bundle to Conversation Profile and prove
  // the real sidecar-backed surfaces, not mocked Playwright routes.
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.evaluate(() => {
    localStorage.setItem('chengzhu-product-profile', 'conversation')
    localStorage.setItem('chengzhu-conversation-optin', '1')
    window.location.hash = '#/conversation'
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByTestId('conversation-home').waitFor({ timeout: 30000 })
  await shot(page, '30-conversation-home', 'Conversation Beta Home from packaged frontend-dist')

  await go(page, '#/conversation/spaces/' + conversationSpace.id, '[data-testid="conversation-space"]')
  await shot(page, '31-conversation-space', 'Conversation Space overview with reviewed continuity')
  await go(page, '#/conversation/spaces/' + conversationSpace.id + '/prepare', '[data-testid="conversation-space"]')
  await shot(page, '32-conversation-prepare', 'Conversation Prepare and frozen-context preview')
  await go(page, '#/conversation/spaces/' + conversationSpace.id + '/decisions', '[data-testid="conversation-space"]')
  await shot(page, '33-conversation-decisions', 'Conversation Decisions/Open Threads truth surface')
  await go(page, '#/conversation/live/' + activeConversation.id, '[data-testid="conversation-live"]')
  await page.getByTestId('conversation-session-pulse').waitFor({ timeout: 15000 })
  await shot(page, '34-conversation-live', 'Conversation Live with frozen Session Pulse')
  await go(page, '#/history', '[data-testid="conversation-history"]')
  await shot(page, '35-conversation-history', 'Profile-aware Conversation History from packaged frontend-dist')

  const manifest = {
    captured_at: new Date().toISOString(),
    evidence_type: 'PACKAGED_FRONTEND_DIST_VIA_PACKAGED_SIDECAR_HEADLESS_CHROMIUM',
    browserwindow_evidence: 'BLOCKED_HOSTED_WINDOWS_RUNNER_NO_INTERACTIVE_DESKTOP',
    backend_executable: BACKEND_EXE,
    frontend_dist: FRONTEND_DIST,
    goal_id: goal.id,
    practice_id: practice.practice_id,
    conversation_space_id: conversationSpace.id,
    conversation_ended_session_id: endedConversation.id,
    conversation_active_session_id: activeConversation.id,
    entries,
  }
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2))
  if (entries.length < 35) throw new Error('expected at least 35 packaged fallback captures including Conversation Beta, got ' + entries.length)
  console.log('packaged web fallback evidence complete captures=' + entries.length)
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
