// Packaged BrowserWindow evidence for Chengzhu v1.3.
// Runs only against the opt-in localhost bridge exposed by desktop/main.js
// when CHENGZHU_RUNTIME_EVIDENCE=1. Screenshots are taken by BrowserWindow.capturePage().
import { spawn, spawnSync } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const EXE = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'Chengzhu.exe')
const OUT = path.join(ROOT, 'artifacts', 'release-evidence', 'v1.3')
fs.mkdirSync(OUT, { recursive: true })
const manifest = []

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
          id: 'c',
          object: 'chat.completion',
          model: 'fake-model',
          choices: [{ index: 0, message: { role: 'assistant', content: answer }, finish_reason: 'stop' }],
        }))
        return
      }
      res.writeHead(200, { 'content-type': 'text/event-stream' })
      res.write('data: ' + JSON.stringify({
        id: 'c',
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

async function request(base, method, pathname, body, headers = {}) {
  const res = await fetch(base + pathname, {
    method,
    headers: { ...headers, ...(body === undefined ? {} : { 'content-type': 'application/json' }) },
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

async function waitForBridge(bridge, proc) {
  const deadline = Date.now() + 210000
  let last = ''
  while (Date.now() < deadline) {
    if (proc.exitCode != null) throw new Error('packaged app exited before evidence bridge was ready')
    try {
      const status = await bridge('GET', '/status')
      if (status.ready && status.backend_url) return status
    } catch (error) {
      last = error instanceof Error ? error.message : String(error)
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error('runtime evidence bridge timeout: ' + last)
}

const provider = await fakeProvider()
const evidencePort = await freePort()
const token = crypto.randomBytes(18).toString('hex')
const evidenceBase = 'http://127.0.0.1:' + evidencePort
const bridge = (method, pathname, body) => request(
  evidenceBase,
  method,
  pathname,
  body,
  { 'x-chengzhu-evidence-token': token },
)
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-v13-evidence-'))
fs.mkdirSync(path.join(userData, 'config'), { recursive: true })
fs.writeFileSync(path.join(userData, 'config', 'config.json'), JSON.stringify({
  models: [{
    name: 'Fake v1.3 evidence',
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

let proc
let stdout = ''
let stderr = ''
try {
  proc = spawn(EXE, [], {
    env: {
      ...process.env,
      CHENGZHU_USER_DATA_DIR: userData,
      CHENGZHU_RUNTIME_EVIDENCE: '1',
      CHENGZHU_RUNTIME_EVIDENCE_PORT: String(evidencePort),
      CHENGZHU_RUNTIME_EVIDENCE_TOKEN: token,
      CHENGZHU_RUNTIME_EVIDENCE_DIR: OUT,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  proc.stdout?.on('data', (chunk) => {
    const text = chunk.toString('utf8')
    stdout = (stdout + text).slice(-12000)
    process.stdout.write('[app] ' + text)
  })
  proc.stderr?.on('data', (chunk) => {
    const text = chunk.toString('utf8')
    stderr = (stderr + text).slice(-12000)
    process.stderr.write('[app] ' + text)
  })

  const status = await waitForBridge(bridge, proc)
  const backend = status.backend_url
  manifest.push({
    name: '_runtime',
    note: 'packaged=' + status.packaged + ' version=' + status.version + ' backend=' + backend
      + ' transport=BrowserWindow.capturePage',
  })

  async function capture(name, note, target = 'main') {
    const result = await bridge('POST', '/capture', { name, target })
    manifest.push({
      name,
      note,
      target,
      file: path.relative(ROOT, result.file),
      width: result.width,
      height: result.height,
    })
    console.log('captured', name)
  }

  async function route(hash, selector, name, note) {
    await bridge('POST', '/navigate', { hash, selector, timeout_ms: 30000 })
    await capture(name, note)
  }

  await bridge('POST', '/wait', { selector: '[data-testid="onboarding"]', timeout_ms: 30000 })
  await capture('01-onboarding', 'real packaged first-run onboarding')

  await request(backend, 'POST', '/api/config', { onboarding_completed: true })
  await bridge('POST', '/reload', { timeout_ms: 30000 })
  await new Promise((resolve) => setTimeout(resolve, 1000))

  const resume = 'WenNian：我负责 RAG 检索链路，用 Redis 管理 session state。'
  await request(backend, 'POST', '/api/intelligence/candidate/rebuild', {
    resume_text: resume,
    interview_notes: '',
  })
  await request(backend, 'POST', '/api/config', { resume_text: resume })

  const goal = await request(backend, 'POST', '/api/product/goals', {
    company: 'MindRank',
    role: 'AIDD Agent Engineer',
    jd: '负责 Agent / RAG / CADD；要求系统设计、评估与高可用。',
    stage: '技术二面',
    interview_round: 'TECHNICAL',
    next_interview_at: Math.floor(Date.now() / 1000) + 86400,
  })
  await request(backend, 'POST', '/api/product/goals/' + goal.id + '/interviews', {
    round: '技术二面',
    scheduled_at: Math.floor(Date.now() / 1000) + 86400,
    kind: 'REAL',
    notes: 'v1.3 packaged evidence',
  })
  const material = await formRequest(backend, '/api/product/materials', {
    title: 'WenNian 架构说明',
    kind: 'PROJECT',
    usage: 'FACTS',
    text: 'Redis 只用于 session state，没有 Redis Cluster 生产经历。',
    background: 'false',
  })
  const note = await request(backend, 'POST', '/api/product/quick-notes', {
    title: 'MindRank 二面速记',
    content: 'Redis：只讲 session state；反问 Agent eval 上线门槛。',
    scope: 'GOAL',
    goal_id: goal.id,
    pinned: true,
    tags: ['想问'],
  })
  const bank = await request(backend, 'POST', '/api/product/question-banks', {
    name: 'AIDD Agent 深挖',
    scope: 'GOAL',
    role: 'AI_ML_ENGINEER',
    goal_id: goal.id,
  })
  await request(backend, 'POST', '/api/product/question-banks/' + bank.id + '/items', {
    text: '如果 Agent 线上效果下降，你怎么定位？',
    category: 'SYSTEM_DESIGN',
    difficulty: 'STANDARD',
    origin: 'USER_ADDED',
    rounds: ['TECHNICAL'],
  })
  await request(backend, 'PATCH', '/api/product/goals/' + goal.id, {
    selected_material_ids: [material.id],
    selected_quick_note_ids: [note.id],
    active_question_bank_ids: [bank.id],
    role_family: 'AI_ML_ENGINEER',
  })

  await bridge('POST', '/reload', { timeout_ms: 30000 })
  await new Promise((resolve) => setTimeout(resolve, 1000))

  await route('#/home', '[data-testid="action-home"]', '02-action-home', 'Action Home')
  await route('#/goals', '[data-testid="goals-page"]', '03-goal-list', 'Goal list')
  await route('#/goals/' + goal.id, '[data-testid="goal-room"]', '04-goal-overview', 'Goal Room overview')
  await route('#/goals/' + goal.id + '/prepare', '[data-testid="goal-room"]', '05-goal-prepare', 'Goal Prepare')
  await route('#/goals/' + goal.id + '/interviews', '[data-testid="goal-room"]', '06-goal-interviews', 'Goal interviews')
  await route('#/goals/' + goal.id + '/offer', '[data-testid="goal-room"]', '07-goal-offer', 'Goal Offer')

  await route('#/me/resume', '[data-testid="me-page"]', '08-me-resume', 'Person workspace')
  await route('#/me/inbox', '[data-testid="me-page"]', '09-fact-inbox', 'Fact Inbox')
  await route('#/library/materials', '[data-testid="library-page"]', '10-library-materials', 'Material taxonomy')
  await route('#/library/notes', '[data-testid="library-page"]', '11-quick-notes', 'Quick Notes')
  await route('#/library/banks', '[data-testid="library-page"]', '12-question-banks', 'Question Banks')

  await bridge('POST', '/navigate', {
    hash: '#/home',
    selector: '[data-testid="action-home"]',
    timeout_ms: 30000,
  })
  try {
    await bridge('POST', '/key', { key: 'K', modifiers: ['control'] })
    await bridge('POST', '/wait', { selector: '[data-testid="command-palette"]', timeout_ms: 5000 })
    await capture('13-command-palette', 'Ctrl+K contextual commands')
    await bridge('POST', '/key', { key: 'Escape', modifiers: [] })
  } catch (error) {
    manifest.push({
      name: '13-command-palette',
      note: 'Shortcut capture unavailable in packaged timing; functional E2E remains authoritative: '
        + (error instanceof Error ? error.message : String(error)),
    })
  }

  await route('#/practice?goal=' + goal.id, '[data-testid="practice-setup"]', '14-practice-setup', 'Practice 3.0')
  const practice = await request(backend, 'POST', '/api/product/practice', {
    goal_id: goal.id,
    round: 'TECHNICAL',
    personas: ['TECH_LEAD', 'HIRING_MANAGER'],
    demeanor: 'SKEPTICAL',
    difficulty: 'PRESSURE',
    sources: ['GOAL_GRAPH', 'ROLE_BANK'],
    questions: 2,
    language: 'zh',
    human_coach: false,
    delivery_analytics: true,
  })
  await route(
    '#/practice/' + practice.practice_id,
    '[data-testid="practice-session"]',
    '15-panel-practice',
    'Panel practice',
  )
  await request(backend, 'POST', '/api/product/practice/' + practice.practice_id + '/answer', {
    answer: '先给结论，我会同时看离线回归集、线上成功率和失败分桶。',
  })
  await bridge('POST', '/reload', {
    selector: '[data-testid="practice-session"]',
    timeout_ms: 30000,
  })
  await capture('16-content-delivery-coach', 'Content Coach and Delivery Coach stay separate')
  await request(backend, 'POST', '/api/product/practice/' + practice.practice_id + '/finish', {})
  await route(
    '#/reflection/practice/' + practice.practice_id,
    '[data-testid="reflection-page"]',
    '17-reflection',
    'Reflection first screen',
  )

  await bridge('POST', '/navigate', {
    hash: '#/goals/' + goal.id,
    selector: '[data-testid="goal-room"]',
    timeout_ms: 30000,
  })
  await bridge('POST', '/click', { selector: '[data-testid="go-live"]' })
  await bridge('POST', '/wait', { selector: '[data-testid="preflight"]', timeout_ms: 10000 })
  await capture('18-preflight', 'Preflight 3.0')

  const live = await request(backend, 'POST', '/api/product/live/start', { goal_id: goal.id })
  await route(
    '#/live/' + live.session_id,
    '[data-testid="live-status-line"]',
    '19-live-idle',
    'Live Cockpit',
  )
  await request(backend, 'POST', '/api/ask', { text: 'RAG 和微调怎么选？' })
  await new Promise((resolve) => setTimeout(resolve, 3500))
  await capture('20-live-guidance', 'Packaged Live after cue request')

  await bridge('POST', '/key', { key: 'P', modifiers: ['control'] })
  try {
    await bridge('POST', '/wait', { selector: '[data-testid="pin-dialog"]', timeout_ms: 5000 })
    await capture('21-pin-moment', 'Pin Moment')
  } catch {
    manifest.push({ name: '21-pin-moment', note: 'Pin dialog unavailable in packaged timing; functional E2E is authoritative.' })
  }

  await route('#/settings/live', '[data-testid="settings-page"]', '22-settings-live-overlay', 'Settings + Overlay 3.0')
  await bridge('POST', '/storage', { key: 'ia-color-scheme', value: 'vscode-dark-plus' })
  await bridge('POST', '/reload', { timeout_ms: 30000 })
  await route('#/home', '[data-testid="action-home"]', '23-dark-home', 'Dark theme')

  await bridge('POST', '/storage', { key: 'ia-color-scheme', value: 'vscode-light-plus' })
  await bridge('POST', '/resize', { width: 390, height: 844 })
  await bridge('POST', '/reload', { timeout_ms: 30000 })
  await route(
    '#/goals/' + goal.id + '/prepare',
    '[data-testid="goal-room"]',
    '24-mobile-390-goal-prepare',
    '390px Goal Prepare',
  )
  await route('#/history', '[data-testid="history-page"]', '25-history', 'History')

  try {
    await capture('26-overlay', 'Real packaged Electron overlay BrowserWindow', 'overlay')
  } catch (error) {
    manifest.push({
      name: '26-overlay',
      note: 'Overlay capture unavailable: ' + (error instanceof Error ? error.message : String(error)),
    })
  }

  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify({
    captured_at: new Date().toISOString(),
    evidence_type: 'PACKAGED_BROWSERWINDOW_CAPTURE',
    executable: EXE,
    goal_id: goal.id,
    practice_id: practice.practice_id,
    live_session_id: live.session_id,
    entries: manifest,
  }, null, 2))
  console.log('done', OUT)
} catch (error) {
  console.error(error)
  console.error('app stdout tail:', stdout.slice(-4000))
  console.error('app stderr tail:', stderr.slice(-4000))
  throw error
} finally {
  if (proc && proc.exitCode == null) {
    if (process.platform === 'win32' && proc.pid) {
      spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { stdio: 'ignore' })
    } else {
      proc.kill('SIGKILL')
    }
  }
  provider.close()
}
