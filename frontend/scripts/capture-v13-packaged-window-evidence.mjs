// Real packaged Windows UI evidence for the current Chengzhu package version.
//
// Hosted Windows runners can block a newly packaged GUI executable from
// opening a localhost listener. Instead of weakening the runtime evidence gate,
// this harness gives the real Chengzhu.exe a file-based evidence plan. The app
// still renders every frame in its actual packaged BrowserWindow and captures
// with BrowserWindow.capturePage().
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
const EXE = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'Chengzhu.exe')
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

async function waitForFile(file, proc, timeoutMs = 180000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'))
    if (proc.exitCode != null) throw new Error('packaged app exited before writing evidence result (code=' + proc.exitCode + ')')
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error('packaged evidence plan timed out: ' + file)
}

async function runPlan({ name, userData, backendBase, nonce, token, steps }) {
  const planPath = path.join(userData, name + '-plan.json')
  const resultPath = path.join(userData, name + '-result.json')
  const statusPath = path.join(userData, name + '-status.json')
  try { fs.unlinkSync(resultPath) } catch {}
  try { fs.unlinkSync(statusPath) } catch {}
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
  proc.stdout?.on('data', (chunk) => {
    const text = chunk.toString('utf8')
    stdout = (stdout + text).slice(-16000)
    process.stdout.write('[app] ' + text)
  })
  proc.stderr?.on('data', (chunk) => {
    const text = chunk.toString('utf8')
    stderr = (stderr + text).slice(-16000)
    process.stderr.write('[app] ' + text)
  })
  try {
    const result = await waitForFile(resultPath, proc)
    if (!result.ok) throw new Error('evidence plan failed: ' + result.error)
    await new Promise((resolve) => setTimeout(resolve, 700))
    return result
  } catch (error) {
    console.error('app stdout tail:', stdout.slice(-5000))
    console.error('app stderr tail:', stderr.slice(-5000))
    if (fs.existsSync(statusPath)) {
      console.error('app evidence stage:', fs.readFileSync(statusPath, 'utf8'))
    } else {
      console.error('app evidence stage: no status file; packaged main entry did not reach evidence instrumentation')
    }
    throw error
  } finally {
    if (proc.exitCode == null) {
      if (process.platform === 'win32' && proc.pid) spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { stdio: 'ignore' })
      else proc.kill('SIGKILL')
    }
  }
}

const provider = await fakeProvider()
const backendPort = await freePort()
const backendBase = 'http://127.0.0.1:' + backendPort
const nonce = crypto.randomBytes(18).toString('hex')
const token = crypto.randomBytes(18).toString('hex')
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-runtime-evidence-'))
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
  await waitForBackend(backendBase, sidecar, nonce)

  // Launch 1: prove the *actual* first-use loop in the packaged app. Do not
  // flip onboarding_completed through the backend: the renderer must create a
  // Goal, run a Guided First Practice, receive a Fast Cue, show Reflection,
  // exercise Overlay + Quick Notes, and finish onboarding itself.
  const first = await runPlan({
    name: 'fresh-install',
    userData,
    backendBase,
    nonce,
    token,
    steps: [
      { kind: 'wait', selector: '[data-testid="onboarding"]', timeout_ms: 30000 },
      { kind: 'capture', name: '01-onboarding', note: 'real packaged fresh-install onboarding' },

      // Welcome → local data → model → STT → mic → system audio → privacy → resume → first Goal.
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'sleep', ms: 250 },
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'sleep', ms: 250 },
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'sleep', ms: 250 },
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'sleep', ms: 250 },
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'sleep', ms: 250 },
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'sleep', ms: 250 },
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'sleep', ms: 250 },
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'sleep', ms: 250 },
      { kind: 'wait', selector: '[data-testid="onboarding-goal-role"]', timeout_ms: 10000 },
      { kind: 'fill', selector: '[data-testid="onboarding-goal-company"]', value: 'Onboarding Demo' },
      { kind: 'fill', selector: '[data-testid="onboarding-goal-role"]', value: 'AI Agent Engineer' },
      { kind: 'fill', selector: '[data-testid="onboarding-goal-jd"]', value: '负责 Agent、RAG、评估与系统设计。' },
      { kind: 'capture', name: '01b-first-goal', note: 'first packaged Goal during onboarding' },
      { kind: 'click', selector: '[data-testid="onboarding-next"]' },

      { kind: 'wait', selector: '[data-testid="guided-first-practice"]', timeout_ms: 10000 },
      { kind: 'click', selector: '[data-testid="guided-start"]' },
      { kind: 'wait', selector: '[data-testid="guided-question"]', timeout_ms: 20000 },
      { kind: 'capture', name: '01c-guided-question', note: 'real Practice 3.0 question in onboarding' },

      { kind: 'click', selector: '[data-testid="guided-cue"]' },
      { kind: 'wait', selector: '[data-testid="guided-fast-cue"]', timeout_ms: 30000 },
      { kind: 'capture', name: '01d-guided-fast-cue', note: 'real Fast Cue in packaged Guided First Practice' },

      { kind: 'click', selector: '[data-testid="guided-overlay-toggle"]' },
      { kind: 'sleep', ms: 800 },
      { kind: 'capture', target: 'overlay', name: '01e-guided-overlay', note: 'Compact Overlay opened from onboarding' },
      { kind: 'click', selector: '[data-testid="guided-overlay-toggle"]' },
      { kind: 'sleep', ms: 350 },

      { kind: 'fill', selector: '[data-testid="guided-note"]', value: 'Redis 没做过 Cluster；只讲 session state。' },
      { kind: 'click', selector: '[data-testid="guided-note-save"]' },
      { kind: 'sleep', ms: 500 },
      { kind: 'capture', name: '01f-guided-quick-note', note: 'Quick Note created inside first practice' },

      { kind: 'fill', selector: '[data-testid="guided-answer"]', value: '先给结论：知识更新频繁且需要来源追溯，所以这个场景优先用 RAG。' },
      { kind: 'click', selector: '[data-testid="guided-submit"]' },
      { kind: 'wait', selector: '[data-testid="guided-reflection"]', timeout_ms: 20000 },
      { kind: 'wait', selector: '[data-testid="guided-practice-complete"]', timeout_ms: 20000 },
      { kind: 'capture', name: '01g-guided-reflection', note: 'Content/Delivery feedback plus Demo Reflection closes the first-use loop' },

      { kind: 'click', selector: '[data-testid="onboarding-next"]' },
      { kind: 'wait', selector: '[data-testid="onboarding-complete-step"]', timeout_ms: 5000 },
      { kind: 'capture', name: '01h-onboarding-complete', note: 'canonical Goal-centered completion message' },
      { kind: 'click', selector: '[data-testid="onboarding-finish"]' },
      { kind: 'wait', selector: '[data-testid="action-home"]', timeout_ms: 10000 },
    ],
  })

  // Seed the richer release-evidence scenario only after the packaged renderer
  // has completed onboarding through the real UI.
  const resume = 'WenNian：我负责 RAG 检索链路，用 Redis 管理 session state。'
  await request(backendBase, 'POST', '/api/intelligence/candidate/rebuild', { resume_text: resume, interview_notes: '' })
  await request(backendBase, 'POST', '/api/config', { resume_text: resume })

  const goal = await request(backendBase, 'POST', '/api/product/goals', {
    company: 'MindRank',
    role: 'AIDD Agent Engineer',
    jd: '负责 Agent / RAG / CADD；要求系统设计、评估与高可用。',
    stage: '技术二面',
    interview_round: 'TECHNICAL',
    next_interview_at: Math.floor(Date.now() / 1000) + 86400,
  })
  await request(backendBase, 'POST', '/api/product/goals/' + goal.id + '/interviews', {
    round: '技术二面',
    scheduled_at: Math.floor(Date.now() / 1000) + 86400,
    kind: 'REAL',
    notes: 'v1.3 packaged evidence',
  })
  const material = await formRequest(backendBase, '/api/product/materials', {
    title: 'WenNian 架构说明',
    kind: 'PROJECT',
    usage: 'FACTS',
    text: 'Redis 只用于 session state，没有 Redis Cluster 生产经历。',
    background: 'false',
  })
  const note = await request(backendBase, 'POST', '/api/product/quick-notes', {
    title: 'MindRank 二面速记',
    content: 'Redis：只讲 session state；反问 Agent eval 上线门槛。',
    scope: 'GOAL',
    goal_id: goal.id,
    pinned: true,
    tags: ['想问'],
  })
  const bank = await request(backendBase, 'POST', '/api/product/question-banks', {
    name: 'AIDD Agent 深挖',
    scope: 'GOAL',
    role: 'AI_ML',
    goal_id: goal.id,
  })
  await request(backendBase, 'POST', '/api/product/question-banks/' + bank.id + '/items', {
    text: '如果 Agent 线上效果下降，你怎么定位？',
    category: 'SYSTEM_DESIGN',
    difficulty: 'STANDARD',
    origin: 'USER_ADDED',
    rounds: ['TECHNICAL'],
  })
  await request(backendBase, 'PATCH', '/api/product/goals/' + goal.id, {
    selected_material_ids: [material.id],
    selected_quick_note_ids: [note.id],
    active_question_bank_ids: [bank.id],
    role_family: 'AI_ML',
  })
  const practice = await request(backendBase, 'POST', '/api/product/practice', {
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
  await request(backendBase, 'POST', '/api/product/practice/' + practice.practice_id + '/answer', {
    answer: '先给结论，我会同时看离线回归集、线上成功率和失败分桶。',
  })
  await request(backendBase, 'POST', '/api/product/practice/' + practice.practice_id + '/finish', {})

  // Seed Conversation Beta through the *packaged sidecar*. UI evidence below
  // still navigates/clicks the real packaged BrowserWindow.
  const conversationSpace = await request(backendBase, 'POST', '/api/product/conversation/spaces', {
    title: 'WenNian Project Sync',
    profile: 'PROJECT_SYNC',
    description: 'Packaged Conversation Beta evidence',
    default_goal: '确认 rollout strategy 与 rollback owner',
    default_mode: 'BALANCED',
    selected_source_ids: [material.id],
    selected_quick_note_ids: [note.id],
  })
  const conversationSession = await request(
    backendBase,
    'POST',
    '/api/product/conversation/spaces/' + conversationSpace.id + '/sessions',
    {
      title: 'Packaged Project Sync',
      capture_mode: 'NOTES_ONLY',
      processing_mode: 'LOCAL',
      assistance_mode: 'BALANCED',
      consent_ack: true,
      policy: {
        ai_assistance: 'AI_ALLOWED',
        external_writeback: 'REVIEW_REQUIRED',
        participant_consent_status: 'NOT_APPLICABLE',
        participant_transparency_plan: 'NOT_APPLICABLE',
      },
    },
  )
  const conversationDecision = await request(
    backendBase,
    'POST',
    '/api/product/conversation/sessions/' + conversationSession.id + '/items',
    {
      item_type: 'Decision',
      title: 'offline migration 采用 v2',
      source_refs: [{ kind: 'DOCUMENT', id: material.id, excerpt: 'WenNian 架构说明', visibility: 'PRIVATE' }],
      source_excerpt: 'WenNian 架构说明',
      epistemic_status: 'OBSERVED',
    },
  )
  await request(backendBase, 'POST', '/api/product/conversation/items/' + conversationDecision.id + '/review', {
    action: 'CONFIRM',
    patch: {},
  })
  await request(backendBase, 'POST', '/api/product/conversation/sessions/' + conversationSession.id + '/start', {})
  const conversationGuidance = await request(
    backendBase,
    'POST',
    '/api/product/conversation/sessions/' + conversationSession.id + '/guidance/evaluate',
    {
      direct_question: '为什么之前选择 v2？',
      source_refs: [{ kind: 'DOCUMENT', id: material.id, excerpt: 'WenNian 架构说明', visibility: 'PRIVATE' }],
    },
  )

  // Launch 2: real packaged BrowserWindow, real routes and real UI interactions.
  const steps = [
    { kind: 'wait', selector: '[data-testid="action-home"]', timeout_ms: 30000 },
    { kind: 'capture', name: '02-action-home', note: 'Action Home' },

    { kind: 'navigate', hash: '#/goals', selector: '[data-testid="goals-page"]' },
    { kind: 'capture', name: '03-goal-list', note: 'Goal list' },
    { kind: 'navigate', hash: '#/goals/' + goal.id, selector: '[data-testid="goal-room"]' },
    { kind: 'capture', name: '04-goal-overview', note: 'Goal Room overview with Next Focus and trends' },
    { kind: 'navigate', hash: '#/goals/' + goal.id + '/prepare', selector: '[data-testid="goal-room"]' },
    { kind: 'capture', name: '05-goal-prepare', note: 'Goal Prepare' },
    { kind: 'navigate', hash: '#/goals/' + goal.id + '/interviews', selector: '[data-testid="goal-room"]' },
    { kind: 'capture', name: '06-goal-interviews', note: 'Goal interviews' },
    { kind: 'navigate', hash: '#/goals/' + goal.id + '/offer', selector: '[data-testid="goal-room"]' },
    { kind: 'capture', name: '07-goal-offer', note: 'Offer metadata without ATS-first UI' },

    { kind: 'navigate', hash: '#/me/resume', selector: '[data-testid="me-page"]' },
    { kind: 'capture', name: '08-me-resume', note: 'Person workspace: current resume' },
    { kind: 'navigate', hash: '#/me/inbox', selector: '[data-testid="me-page"]' },
    { kind: 'capture', name: '09-fact-inbox', note: 'Fact Inbox' },
    { kind: 'navigate', hash: '#/me/stories', selector: '[data-testid="me-page"]' },
    { kind: 'capture', name: '10-stories', note: 'Stories 3.0 and competency coverage' },

    { kind: 'navigate', hash: '#/library/materials', selector: '[data-testid="library-page"]' },
    { kind: 'capture', name: '11-library-materials', note: 'Material taxonomy/lifecycle' },
    { kind: 'navigate', hash: '#/library/notes', selector: '[data-testid="library-page"]' },
    { kind: 'capture', name: '12-quick-notes', note: 'Quick Notes' },
    { kind: 'navigate', hash: '#/library/banks', selector: '[data-testid="library-page"]' },
    { kind: 'capture', name: '13-question-banks', note: 'Question Banks' },

    { kind: 'navigate', hash: '#/home', selector: '[data-testid="action-home"]' },
    { kind: 'key', key: 'K', modifiers: ['control'] },
    { kind: 'wait', selector: '[data-testid="command-palette"]', timeout_ms: 5000 },
    { kind: 'capture', name: '14-command-palette', note: 'Ctrl+K contextual command palette' },
    { kind: 'key', key: 'Escape', modifiers: [] },

    { kind: 'navigate', hash: '#/practice?goal=' + goal.id, selector: '[data-testid="practice-setup"]' },
    { kind: 'capture', name: '15-practice-setup', note: 'Practice 3.0 setup' },
    { kind: 'navigate', hash: '#/practice/' + practice.practice_id, selector: '[data-testid="practice-session"]' },
    { kind: 'capture', name: '16-panel-practice', note: 'Panel practice with controlled personas and split coaching' },

    { kind: 'navigate', hash: '#/reflection/practice/' + practice.practice_id, selector: '[data-testid="reflection-page"]' },
    { kind: 'capture', name: '17-reflection', note: 'Action-first Reflection' },

    { kind: 'navigate', hash: '#/goals/' + goal.id, selector: '[data-testid="goal-room"]' },
    { kind: 'click', selector: '[data-testid="go-live"]' },
    { kind: 'wait', selector: '[data-testid="preflight"]', timeout_ms: 10000 },
    { kind: 'capture', name: '18-preflight', note: 'Preflight 3.0 origins and policies' },
    { kind: 'click', selector: '[data-testid="preflight-start"]' },
    { kind: 'wait', selector: '[data-testid="live-status-line"]', timeout_ms: 15000 },
    { kind: 'capture', name: '19-live-idle', note: 'Live Cockpit one-status-line idle state' },
    { kind: 'ask', text: 'RAG 和微调怎么选？' },
    { kind: 'wait', selector: '[data-testid="fast-cue"]', timeout_ms: 30000 },
    { kind: 'capture', name: '20-live-fast-cue', note: 'Question → Fast Cue before Deep' },
    { kind: 'sleep', ms: 1800 },
    { kind: 'capture', name: '21-live-deep', note: 'Deep answer as second layer' },
    { kind: 'key', key: 'P', modifiers: ['control'] },
    { kind: 'wait', selector: '[data-testid="pin-dialog"]', timeout_ms: 5000 },
    { kind: 'capture', name: '22-pin-moment', note: 'Pin Moment' },
    { kind: 'key', key: 'Escape', modifiers: [] },
    { kind: 'click', selector: '[data-testid="live-quick-notes"]' },
    { kind: 'wait', selector: '[data-testid="quick-notes-drawer"]', timeout_ms: 5000 },
    { kind: 'capture', name: '23-live-quick-notes', note: 'Live read-only Quick Notes drawer' },
    { kind: 'key', key: 'Escape', modifiers: [] },
    { kind: 'ask', text: '你还有什么想问我们的吗？' },
    { kind: 'wait', selector: '[data-testid="closing-panel"]', timeout_ms: 15000 },
    { kind: 'capture', name: '24-closing-mode', note: 'Contextual Closing Mode' },

    { kind: 'navigate', hash: '#/settings/live', selector: '[data-testid="settings-page"]' },
    { kind: 'capture', name: '25-settings-overlay', note: 'Settings 3.0 + Overlay 3.0' },
    { kind: 'navigate', hash: '#/settings/diagnostics', selector: '[data-testid="settings-page"]' },
    { kind: 'capture', name: '26-validation', note: 'v1.4 product-loop validation UI' },

    { kind: 'storage', key: 'ia-color-scheme', value: 'vscode-dark-plus' },
    { kind: 'reload', selector: '[data-testid="settings-page"]', timeout_ms: 30000 },
    { kind: 'navigate', hash: '#/home', selector: '[data-testid="action-home"]' },
    { kind: 'capture', name: '27-dark-home', note: 'Dark theme' },

    { kind: 'storage', key: 'ia-color-scheme', value: 'vscode-light-plus' },
    { kind: 'resize', width: 390, height: 844 },
    { kind: 'reload', selector: '[data-testid="action-home"]', timeout_ms: 30000 },
    { kind: 'navigate', hash: '#/goals/' + goal.id + '/prepare', selector: '[data-testid="goal-room"]' },
    { kind: 'capture', name: '28-mobile-390-goal-prepare', note: '390px Goal Prepare' },
    { kind: 'navigate', hash: '#/history', selector: '[data-testid="history-page"]' },
    { kind: 'capture', name: '29-history', note: 'Unified Interview History' },

    // Conversation Beta packaged productization evidence.
    { kind: 'resize', width: 1280, height: 900 },
    { kind: 'storage', key: 'chengzhu-product-profile', value: 'conversation' },
    { kind: 'storage', key: 'chengzhu-conversation-optin', value: '1' },
    { kind: 'navigate', hash: '#/conversation', selector: '[data-testid="conversation-home"]' },
    { kind: 'capture', name: '30-conversation-home', note: 'Packaged Conversation Home' },
    { kind: 'navigate', hash: '#/conversation/spaces/' + conversationSpace.id, selector: '[data-testid="conversation-space"]' },
    { kind: 'capture', name: '31-conversation-space', note: 'Conversation Space overview and longitudinal state' },
    { kind: 'navigate', hash: '#/conversation/spaces/' + conversationSpace.id + '/prepare', selector: '[data-testid="conversation-space"]' },
    { kind: 'capture', name: '32-conversation-prepare', note: 'Conversation Prepare before Preflight' },
    { kind: 'click', selector: '[data-testid="conversation-create-preflight"]' },
    { kind: 'wait', selector: '[data-testid="conversation-start-session"]', timeout_ms: 15000 },
    { kind: 'capture', name: '33-conversation-preflight', note: 'Conversation Preflight + Pack/Data-path truth' },
    { kind: 'navigate', hash: '#/conversation/live/' + conversationSession.id, selector: '[data-testid="conversation-live"]' },
    { kind: 'wait', selector: '[data-testid="conversation-session-pulse"]', timeout_ms: 15000 },
    { kind: 'wait', selector: '[data-testid="guidance-dogfood-feedback"]', timeout_ms: 15000 },
    { kind: 'capture', name: '34-conversation-live-guidance', note: 'Conversation Live primary Guidance + frozen Session Pulse' },
    { kind: 'click', selector: '[data-testid="guidance-feedback-useful"]' },
    { kind: 'sleep', ms: 500 },
    { kind: 'capture', name: '35-conversation-dogfood-label', note: 'Local human Guidance label in packaged UI' },
    { kind: 'click', selector: '[data-testid="conversation-end-session"]' },
    { kind: 'wait', selector: '[data-testid="conversation-continue-summary"]', timeout_ms: 15000 },
    { kind: 'capture', name: '36-conversation-continue', note: 'Conversation Continue + session dogfood labels' },
    { kind: 'navigate', hash: '#/history', selector: '[data-testid="conversation-history"]' },
    { kind: 'capture', name: '37-conversation-history', note: 'Profile-aware Conversation History' },
    { kind: 'resize', width: 390, height: 844 },
    { kind: 'navigate', hash: '#/conversation/spaces/' + conversationSpace.id + '/prepare', selector: '[data-testid="conversation-space"]' },
    { kind: 'capture', name: '38-conversation-mobile-390-prepare', note: '390px packaged Conversation Prepare' },
  ]

  const second = await runPlan({ name: 'product-loop', userData, backendBase, nonce, token, steps })
  const manifest = {
    captured_at: new Date().toISOString(),
    evidence_type: 'PACKAGED_BROWSERWINDOW_FILE_PLAN_WITH_PACKAGED_SIDECAR',
    executable: EXE,
    backend_executable: BACKEND_EXE,
    goal_id: goal.id,
    practice_id: practice.practice_id,
    conversation_space_id: conversationSpace.id,
    conversation_session_id: conversationSession.id,
    conversation_guidance_id: conversationGuidance.guidance?.id || '',
    conversation_beta_evidence: true,
    entries: [...(first.entries || []), ...(second.entries || [])],
  }
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2))
  if (manifest.entries.length < 45) throw new Error('expected at least 45 packaged UI captures including Conversation Beta, got ' + manifest.entries.length)
  console.log('done', OUT, 'captures=' + manifest.entries.length)
} catch (error) {
  console.error(error)
  console.error('sidecar output tail:', sidecarOut.slice(-5000))
  throw error
} finally {
  if (sidecar && sidecar.exitCode == null) {
    if (process.platform === 'win32' && sidecar.pid) spawnSync('taskkill', ['/PID', String(sidecar.pid), '/T', '/F'], { stdio: 'ignore' })
    else sidecar.kill('SIGKILL')
  }
  provider.close()
}
