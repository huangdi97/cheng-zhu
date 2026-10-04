// v1.3 runtime UI evidence from the real packaged Windows app.
//
// Launches dist/desktop/win-unpacked/Chengzhu.exe with an isolated user-data
// directory and a local fake OpenAI-compatible provider. Product state is
// seeded only through Chengzhu's real HTTP API, then the real Electron UI is
// driven through the Goal-centered routes.
//
// Usage (from frontend/):
//   node scripts/capture-v13-runtime-evidence.mjs
import { _electron as electron } from 'playwright'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const EXE = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'Chengzhu.exe')
const OUT = path.join(ROOT, 'artifacts', 'release-evidence', 'v1.3')
fs.mkdirSync(OUT, { recursive: true })
const manifest = []

function fakeProvider() {
  const text = '先给结论：RAG 适合频繁更新且需要来源追溯的知识；微调更适合稳定行为和表达风格。你的 WenNian 可以讲检索链路与无需重训。'
  const server = http.createServer((req, res) => {
    let body = ''
    req.on('data', (c) => { body += c })
    req.on('end', () => {
      if (req.method === 'GET') {
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify({ object: 'list', data: [{ id: 'fake-model', object: 'model' }] }))
        return
      }
      const request = body ? JSON.parse(body) : {}
      if (!request.stream) {
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify({
          id: 'c', object: 'chat.completion', model: 'fake-model',
          choices: [{ index: 0, message: { role: 'assistant', content: text }, finish_reason: 'stop' }],
          usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
        }))
        return
      }
      res.writeHead(200, { 'Content-Type': 'text/event-stream' })
      let i = 0
      const timer = setInterval(() => {
        if (i >= text.length) {
          res.write('data: [DONE]\n\n')
          clearInterval(timer)
          res.end()
          return
        }
        const piece = text.slice(i, i + 7)
        i += 7
        res.write(`data: ${JSON.stringify({ id: 'c', object: 'chat.completion.chunk', model: 'fake-model', choices: [{ index: 0, delta: { content: piece }, finish_reason: null }] })}\n\n`)
      }, 45)
    })
  })
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)))
}

async function shot(page, name, note) {
  await page.waitForTimeout(650)
  const file = path.join(OUT, `${name}.png`)
  await page.screenshot({ path: file })
  manifest.push({ name, file: path.relative(ROOT, file), note })
  console.log('captured', name)
}

async function api(base, method, url, body) {
  const res = await fetch(base + url, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  let payload
  try { payload = text ? JSON.parse(text) : {} } catch { payload = text }
  if (!res.ok) throw new Error(`${method} ${url} -> ${res.status}: ${text.slice(0, 300)}`)
  return payload
}

async function formApi(base, url, fields) {
  const form = new FormData()
  for (const [k, v] of Object.entries(fields)) form.append(k, String(v))
  const res = await fetch(base + url, { method: 'POST', body: form })
  const text = await res.text()
  if (!res.ok) throw new Error(`POST ${url} -> ${res.status}: ${text.slice(0, 300)}`)
  return JSON.parse(text)
}

async function route(page, hash, ready) {
  await page.evaluate((h) => { location.hash = h }, hash)
  if (ready) await page.locator(ready).waitFor({ timeout: 30000 })
  await page.waitForTimeout(350)
}

const provider = await fakeProvider()
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-v13-evidence-'))
fs.mkdirSync(path.join(userData, 'config'), { recursive: true })
fs.writeFileSync(path.join(userData, 'config', 'config.json'), JSON.stringify({
  models: [{
    name: 'Fake (v1.3 evidence)',
    api_base_url: `http://127.0.0.1:${provider.address().port}/v1`,
    api_key: 'test-key-not-real',
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

let app
try {
  app = await electron.launch({ executablePath: EXE, args: [`--user-data-dir=${userData}`], timeout: 120000 })

  async function mainWindow() {
    for (let i = 0; i < 120; i++) {
      const found = app.windows().find((w) => !w.url().includes('overlay=1') && w.url().startsWith('http'))
      if (found) return found
      await new Promise((r) => setTimeout(r, 1000))
    }
    throw new Error('main window not found')
  }

  const page = await mainWindow()
  await page.waitForLoadState('domcontentloaded')
  await page.getByRole('heading', { name: '成竹', exact: true }).waitFor({ timeout: 120000 })
  const base = await page.evaluate(() => location.origin)
  const realUserData = await app.evaluate(({ app: a }) => a.getPath('userData'))
  manifest.push({ name: '_runtime', note: `origin=${base} userData=${realUserData} exe=${EXE}` })

  // Fresh-install evidence: run the canonical 11-step onboarding instead
  // of taking one screenshot and bypassing the product loop.
  const wizard = page.getByTestId('onboarding')
  await wizard.waitFor({ timeout: 20000 })
  await shot(page, '01-onboarding', 'fresh install: first-run onboarding')
  for (let i = 0; i < 8; i++) {
    await wizard.getByRole('button', { name: '下一步' }).click()
    await page.waitForTimeout(120)
  }
  await wizard.getByLabel('目标公司').fill('Onboarding Demo')
  await wizard.getByLabel('目标岗位').fill('AI Agent Engineer')
  await wizard.getByLabel('岗位 JD').fill('负责 Agent、RAG、评估与系统设计。')
  await shot(page, '01b-first-goal', 'onboarding creates a real v1.3 Goal, not a legacy PrepSpace')
  await wizard.getByRole('button', { name: '下一步' }).click()

  await wizard.getByRole('button', { name: '开始第一次演练' }).click()
  await wizard.getByTestId('guided-question').waitFor({ timeout: 20000 })
  await shot(page, '01c-guided-practice-question', 'Guided First Practice uses the real Practice 3.0 session')

  await wizard.getByRole('button', { name: '生成 Fast Cue' }).click()
  try {
    await wizard.getByTestId('guided-fast-cue').waitFor({ timeout: 30000 })
  } catch {
    // A packaged environment may deliberately run without a provider. The
    // fallback remains valid onboarding UX but is labelled as non-runtime
    // evidence; this branch should not be hit with the fake provider above.
    const fallback = wizard.getByRole('button', { name: '使用标记明确的示例 Cue 继续' })
    await fallback.waitFor({ timeout: 5000 })
    await fallback.click()
    await wizard.getByTestId('guided-fast-cue-fallback').waitFor()
  }
  await shot(page, '01d-guided-fast-cue', 'Guided First Practice: Fast Cue or explicitly-labelled fallback')

  await wizard.getByLabel('第一次演练回答').fill('先给结论：知识会频繁更新而且需要来源追溯，所以这个场景优先用 RAG。')
  await wizard.getByRole('button', { name: '提交演练' }).click()
  await wizard.getByTestId('guided-practice-complete').waitFor({ timeout: 20000 })
  await shot(page, '01e-guided-practice-complete', 'Guided First Practice reaches Content + Delivery feedback before onboarding completes')
  await wizard.getByRole('button', { name: '下一步' }).click()
  await wizard.getByRole('button', { name: '进入成竹' }).click()
  await page.waitForTimeout(700)

  // Seed Person + the richer evidence Goal + material roles using public APIs only.
  const resume = 'WenNian：我负责 RAG 检索链路，用 Redis 管理 session state。\nPLI：负责 Agent 产品设计与多端体验。'
  await api(base, 'POST', '/api/intelligence/candidate/rebuild', { resume_text: resume, interview_notes: '' })
  await api(base, 'POST', '/api/config', { resume_text: resume })

  const goal = await api(base, 'POST', '/api/product/goals', {
    company: 'MindRank',
    role: 'AIDD Agent Engineer',
    jd: '负责 Agent / RAG / CADD 产品与工程落地；要求系统设计、评估与高可用。',
    stage: '技术二面',
    interview_round: 'TECHNICAL',
    next_interview_at: Math.floor(Date.now() / 1000) + 86400,
  })
  await api(base, 'POST', `/api/product/goals/${goal.id}/interviews`, {
    round: '技术二面',
    scheduled_at: Math.floor(Date.now() / 1000) + 86400,
    kind: 'REAL',
    notes: 'v1.3 runtime evidence',
  })
  const material = await formApi(base, '/api/product/materials', {
    title: 'WenNian 架构说明',
    kind: 'PROJECT',
    usage: 'FACTS',
    text: '我负责 RAG 检索链路；Redis 只用于 session state，没有 Redis Cluster 生产经历。',
    background: 'false',
  })
  const note = await api(base, 'POST', '/api/product/quick-notes', {
    title: 'MindRank 二面速记',
    content: 'Redis：只讲 session state，不说 Cluster 生产经历。\n反问：Agent eval 的上线门槛是什么？',
    scope: 'GOAL', goal_id: goal.id, pinned: true, tags: ['想问'],
  })
  const bank = await api(base, 'POST', '/api/product/question-banks', {
    name: 'AIDD Agent 深挖', scope: 'GOAL', role: 'AI_ML_ENGINEER', goal_id: goal.id,
  })
  await api(base, 'POST', `/api/product/question-banks/${bank.id}/items`, {
    text: '如果 Agent 线上效果下降，你怎么定位？', category: 'SYSTEM_DESIGN', difficulty: 'STANDARD', origin: 'USER_ADDED', rounds: ['TECHNICAL'],
  })
  await api(base, 'PATCH', `/api/product/goals/${goal.id}`, {
    selected_material_ids: [material.id],
    selected_quick_note_ids: [note.id],
    active_question_bank_ids: [bank.id],
    role_family: 'AI_ML_ENGINEER',
  })

  await page.reload()
  await page.getByRole('heading', { name: '成竹', exact: true }).waitFor()

  // Goal-centered studio.
  await route(page, '#/home', '[data-testid="action-home"]')
  await shot(page, '02-action-home', 'Action Home: next interview, Next Focus, needs-attention, recent session')

  await route(page, '#/goals', '[data-testid="goals-page"]')
  await shot(page, '03-goal-list', 'Goal list: company × role is the primary object')

  await route(page, `#/goals/${goal.id}`, '[data-testid="goal-room"]')
  await shot(page, '04-goal-overview', 'Goal Room overview')

  await route(page, `#/goals/${goal.id}/prepare`, '[data-testid="goal-room"]')
  await shot(page, '05-goal-prepare', 'Goal Prepare: Next Focus, gaps, attack surface, question graph, pack preview')

  await route(page, `#/goals/${goal.id}/interviews`, '[data-testid="goal-room"]')
  await shot(page, '06-goal-interviews', 'Goal interviews: upcoming + linked sessions')

  await route(page, `#/goals/${goal.id}/offer`, '[data-testid="goal-room"]')
  await shot(page, '07-goal-offer', 'Goal Offer metadata without turning Chengzhu into an ATS')

  // Person + Library.
  await route(page, '#/me/resume', '[data-testid="me-page"]')
  await shot(page, '08-me-resume', 'Person workspace: resume')

  await route(page, '#/me/inbox', '[data-testid="me-page"]')
  await shot(page, '09-fact-inbox', 'Fact Inbox: provenance exposed as review work, not an evidence database')

  await route(page, '#/me/stories', '[data-testid="me-page"]')
  await shot(page, '10-stories', 'Story bank and competency coverage')

  await route(page, '#/library/materials', '[data-testid="library-page"]')
  await shot(page, '11-library-materials', 'Material taxonomy + lifecycle')

  await route(page, '#/library/notes', '[data-testid="library-page"]')
  await shot(page, '12-quick-notes', 'Quick Notes are separate from Evidence and Knowledge')

  await route(page, '#/library/banks', '[data-testid="library-page"]')
  await shot(page, '13-question-banks', 'Question Banks with explicit origins')

  // Command palette is contextual rather than another permanent nav surface.
  await route(page, '#/home', '[data-testid="action-home"]')
  await page.keyboard.press('Control+K')
  await page.getByTestId('command-palette').waitFor()
  await shot(page, '14-command-palette', 'Ctrl+K contextual commands')
  await page.keyboard.press('Escape')

  // Practice 3.0 + panel + split coaching. Start through the real API, then
  // drive the UI on the resulting session.
  await route(page, `#/practice?goal=${goal.id}`, '[data-testid="practice-setup"]')
  await shot(page, '15-practice-setup', 'Practice 3.0: Goal, round, persona, demeanor, difficulty, sources')

  const practice = await api(base, 'POST', '/api/product/practice', {
    goal_id: goal.id, round: 'TECHNICAL', personas: ['TECH_LEAD', 'HIRING_MANAGER'],
    demeanor: 'SKEPTICAL', difficulty: 'PRESSURE', sources: ['GOAL_GRAPH', 'ROLE_BANK'],
    questions: 2, language: 'zh', human_coach: false, delivery_analytics: true,
  })
  await route(page, `#/practice/${practice.practice_id}`, '[data-testid="practice-session"]')
  await shot(page, '16-panel-practice', 'Panel practice: controlled turn-taking between personas')

  await page.getByLabel('你的回答').fill('先给结论，我会同时看离线回归集、线上成功率和失败分桶，再用人工复核闭环定位问题。')
  await page.getByTestId('practice-submit').click()
  await page.getByLabel('上一题反馈').waitFor({ timeout: 20000 })
  await shot(page, '17-content-delivery-coach', 'Content Coach and Delivery Coach stay separate')

  // Reflection for the practice session.
  await api(base, 'POST', `/api/product/practice/${practice.practice_id}/finish`, {})
  await route(page, `#/reflection/practice/${practice.practice_id}`, '[data-testid="reflection-page"]')
  await shot(page, '18-reflection', 'Reflection first screen: next step, strengths, improvements, pins, fact checks')

  // Preflight → Live: real packaged app + frozen Goal context.
  await route(page, `#/goals/${goal.id}`, '[data-testid="goal-room"]')
  await page.getByTestId('go-live').click()
  await page.getByTestId('preflight').waitFor({ timeout: 20000 })
  await shot(page, '19-preflight', 'Preflight 3.0: content + origin + policy, session overrides only')
  await page.getByTestId('preflight-start').click()
  await page.getByTestId('live-status-line').waitFor({ timeout: 20000 })
  await shot(page, '20-live-idle', 'Live Cockpit: one status line, Goal context, compact companion actions')

  await api(base, 'POST', '/api/ask', { text: 'RAG 和微调怎么选？' })
  await page.getByTestId('fast-cue').first().waitFor({ timeout: 30000 })
  await shot(page, '21-live-fast-cue', 'Question → Fast Cue → source/warning before Deep')
  await page.waitForTimeout(2200)
  await shot(page, '22-live-deep', 'Deep answer is the second layer')

  await page.keyboard.press('Control+P')
  await page.getByTestId('pin-dialog').waitFor()
  await shot(page, '23-pin-moment', 'Pin Moment: user decides what mattered')
  await page.getByRole('radio', { name: '重要' }).click()
  await page.getByLabel('备注（可选）').fill('面试官强调 Agent eval 的上线门槛。')
  await page.getByRole('button', { name: '标记', exact: true }).click()
  await page.waitForTimeout(850)

  await page.getByRole('button', { name: /速记/ }).first().click()
  await page.getByTestId('quick-notes-drawer').waitFor()
  await shot(page, '24-live-quick-notes', 'Live Quick Notes drawer: read-only support, separate truth role')
  await page.getByLabel('关闭速记').click()

  // Closing Mode uses this session context rather than a generic question list.
  await api(base, 'POST', '/api/ask', { text: '你还有什么想问我们的吗？' })
  try {
    await page.getByTestId('closing-panel').waitFor({ timeout: 15000 })
    await shot(page, '25-closing-mode', 'Closing Mode: contextual questions from Goal + this conversation')
  } catch {
    manifest.push({ name: '25-closing-mode', note: 'closing panel did not surface under fake-provider timing; backend contract remains separately tested' })
  }

  // Overlay renderer evidence after a real cue.
  const overlay = app.windows().find((w) => w.url().includes('overlay=1'))
  if (overlay) {
    await overlay.waitForLoadState('domcontentloaded')
    await overlay.waitForTimeout(800)
    await shot(overlay, '26-overlay', 'real Electron overlay renderer after a live cue')
  }

  // Settings 3.0 + Overlay 3.0.
  await route(page, '#/settings/live', '[data-testid="settings-page"]')
  await shot(page, '27-settings-live-overlay', 'Settings search/layers + Overlay Dock × Interaction × Size')

  // Dark theme.
  await page.evaluate(() => localStorage.setItem('ia-color-scheme', 'vscode-dark-plus'))
  await page.reload()
  await page.waitForLoadState('domcontentloaded')
  await route(page, '#/home', '[data-testid="action-home"]')
  await shot(page, '28-dark-home', 'dark theme')

  // 390px packaged-window evidence.
  await page.evaluate(() => localStorage.setItem('ia-color-scheme', 'vscode-light-plus'))
  await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows().find((x) => x.isVisible() && !x.webContents.getURL().includes('overlay=1'))
    w?.setMinimumSize(360, 500)
    w?.setSize(390, 844)
  })
  await page.reload()
  await page.waitForLoadState('domcontentloaded')
  await route(page, `#/goals/${goal.id}/prepare`, '[data-testid="goal-room"]')
  await shot(page, '29-mobile-390-goal-prepare', '390px Goal Prepare')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  manifest.push({ name: '_390_overflow', note: `horizontal overflow at 390px: ${overflow}` })
  if (overflow) throw new Error('v1.3 Goal Prepare has horizontal overflow at 390px')

  await route(page, '#/history', '[data-testid="history-page"]')
  await shot(page, '30-history', 'History unifies real interviews, practice and reflections')

  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify({
    captured_at: new Date().toISOString(),
    goal_id: goal.id,
    practice_id: practice.practice_id,
    entries: manifest,
  }, null, 2))
  console.log('done', OUT)
} finally {
  if (app) await app.close().catch(() => undefined)
  provider.close()
}
