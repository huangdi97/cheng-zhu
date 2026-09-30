// R2 Stage AK: runtime UI evidence from the real packaged app.
//
// Launches dist/desktop/win-unpacked/Chengzhu.exe (the built product, not the
// dev server) with an isolated --user-data-dir and a local fake
// OpenAI-compatible provider, seeds data through the app's own HTTP API, and
// captures screenshots into artifacts/release-evidence/v1.2-r2/.
//
// Usage (from frontend/): node scripts/capture-runtime-evidence.mjs
import { _electron as electron } from 'playwright'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const EXE = path.join(ROOT, 'dist', 'desktop', 'win-unpacked', 'Chengzhu.exe')
const OUT = path.join(ROOT, 'artifacts', 'release-evidence', 'v1.2-r2')
fs.mkdirSync(OUT, { recursive: true })
const manifest = []

function fakeProvider() {
  const text = 'RAG 更适合频繁更新的知识，来源可追溯。你的 WenNian 项目可以讲无需重训。微调更适合固定风格。'
  const server = http.createServer((req, res) => {
    let body = ''
    req.on('data', (c) => { body += c })
    req.on('end', () => {
      if (req.method === 'GET') {
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify({ object: 'list', data: [{ id: 'fake-model', object: 'model' }] }))
        return
      }
      const reqJson = body ? JSON.parse(body) : {}
      if (!reqJson.stream) {
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify({ id: 'c', object: 'chat.completion', model: 'fake-model', choices: [{ index: 0, message: { role: 'assistant', content: text }, finish_reason: 'stop' }], usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }))
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
        const piece = text.slice(i, i + 6)
        i += 6
        res.write(`data: ${JSON.stringify({ id: 'c', object: 'chat.completion.chunk', model: 'fake-model', choices: [{ index: 0, delta: { content: piece }, finish_reason: null }] })}\n\n`)
      }, 60)
    })
  })
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)))
}

async function shot(page, name, note) {
  await page.waitForTimeout(700)
  const file = path.join(OUT, `${name}.png`)
  await page.screenshot({ path: file })
  manifest.push({ name, file: path.relative(ROOT, file), note })
  console.log('captured', name)
}

async function api(base, method, url, body) {
  const res = await fetch(base + url, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
  const text = await res.text()
  try { return JSON.parse(text) } catch { return text }
}

async function nav(page, label) {
  await page.getByRole('tab', { name: label, exact: true }).first().click()
  await page.waitForTimeout(500)
}

const provider = await fakeProvider()
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-evidence-'))
fs.mkdirSync(path.join(userData, 'config'), { recursive: true })
fs.writeFileSync(path.join(userData, 'config', 'config.json'), JSON.stringify({
  models: [{ name: 'Fake (evidence)', api_base_url: `http://127.0.0.1:${provider.address().port}/v1`, api_key: 'test-key-not-real', model: 'fake-model', enabled: true, supports_think: false, supports_vision: false }],
  active_model: 0,
  onboarding_completed: false,
  stt_provider: 'whisper',
}))

const app = await electron.launch({ executablePath: EXE, args: [`--user-data-dir=${userData}`], timeout: 120000 })
// The overlay window is preheated alongside the main window; pick the main one.
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

// 1. First-run onboarding (fresh config)
await page.getByTestId('onboarding').waitFor({ timeout: 20000 })
await shot(page, 'onboarding', 'fresh config → first-run guide step 1')
await page.getByRole('button', { name: '下一步' }).click()
await shot(page, 'onboarding-local-data', 'step 2 shows the real %APPDATA% data dir')
await page.getByRole('button', { name: '跳过引导' }).click()
await page.waitForTimeout(800)

// Seed through the app's own API (the same calls the UI makes).
const resume = 'WenNian 项目：我用 Redis 管理 session state，负责检索链路\n使用 RAG 做知识问答\n技能：熟悉 Kafka'
await api(base, 'POST', '/api/intelligence/candidate/rebuild', { resume_text: resume, interview_notes: '' })
await api(base, 'POST', '/api/config', { resume_text: resume })
await api(base, 'POST', '/api/intelligence/stories', { title: '灰度回滚事故', situation: '上线后错误率升高', challenge: '需要 10 分钟内止血', action: '按开关回滚并定位配置', result: '8 分钟恢复', reflection: '补了灰度校验', tags: [] })
const space = await api(base, 'POST', '/api/prep/spaces', { title: 'AI Agent 工程师', company: '示例科技', role: 'AI Agent Engineer', jd_text: 'AI Agent Engineer\n任职要求：\n熟悉 RAG 检索增强\n熟悉 Redis\n熟悉 LangGraph 多智能体编排', resume_text: resume })

await page.reload()
await page.getByRole('heading', { name: '成竹', exact: true }).waitFor()
await shot(page, 'home', 'home: 继续准备 / 开始演练 / 上场 into the current Job Goal')

await nav(page, '我的成竹')
await shot(page, 'my-chengzhu-resume', '我的成竹 → 简历 (default tab)')
await page.getByRole('tab', { name: '概览' }).click()
await shot(page, 'my-chengzhu-overview', '我的成竹 → 概览')
await page.getByRole('tab', { name: '事实与来源' }).click()
await shot(page, 'facts', 'facts from the resume rebuild: provenance and user confirmation as separate chips')
await page.getByRole('tab', { name: 'Stories' }).click()
await shot(page, 'story', 'Story Builder + a seeded user-authored story')
await page.getByRole('tab', { name: '我的表达' }).click()
await shot(page, 'voice', '我的表达 preferences')

await nav(page, '求职')
await page.getByText('AI Agent 工程师').first().click()
await page.waitForTimeout(800)
await shot(page, 'job-goal', 'Job Goal detail (JD / alignment / 准备)')
await page.getByRole('button', { name: '冻结并用于本场' }).click()
await page.getByTestId('interview-pack-preview').waitFor({ timeout: 60000 })
await shot(page, 'prepare-pack-frozen', 'InterviewPack frozen with per-session policies (fake provider for strategy generation)')

await nav(page, '演练')
await shot(page, 'rehearse', '演练 hub + practice coach panel')
await page.getByRole('button', { name: '生成教练链接' }).click()
await page.waitForTimeout(800)
await shot(page, 'coach-practice', 'practice coach link generated (token shown once, fragment only)')

await nav(page, '上场')
await page.getByTestId('live-pack-bar').waitFor({ timeout: 20000 })
await shot(page, 'preflight-pack-bar', 'Live: frozen pack bar with AI / human / share-privacy policies')
await api(base, 'POST', '/api/ask', { text: 'RAG 和微调怎么选？' })
await page.getByTestId('fast-cue').first().waitFor({ timeout: 30000 })
await shot(page, 'live-fast-cue', 'Live: Fast Cue visible (guidance_fast) while the deep answer streams')
await page.waitForTimeout(3000)
await shot(page, 'live-deep', 'Live: deep answer completed below the cue')
await api(base, 'POST', '/api/ask', { text: '你实际用过 Redis Cluster 吗？' })
await page.waitForTimeout(3500)
await shot(page, 'live-boundary-cue', 'Live: boundary cue for an unsourced personal claim')

await nav(page, '复盘')
await shot(page, 'review', '复盘 → 场次复盘')
await page.getByRole('tab', { name: '能力分析' }).click()
await shot(page, 'review-ability', '复盘 → 能力分析')

await page.getByRole('button', { name: '设置', exact: true }).click()
await page.getByLabel('共享隐私').first().waitFor()
await shot(page, 'settings-share-privacy-off', 'Settings: share privacy default OFF, human assistance practice-only, about MIT')
await page.getByLabel('共享隐私').first().selectOption('PRIVATE_OVERLAY')
await page.waitForTimeout(800)
const protectedState = await page.evaluate(() => window.electronAPI?.getSharePrivacy?.())
await shot(page, 'settings-share-privacy-on', `Settings: share privacy PRIVATE_OVERLAY → main process state ${JSON.stringify(protectedState)}`)
await page.getByLabel('共享隐私').first().selectOption('OFF')
await page.keyboard.press('Escape')

// Empty / error states
await api(base, 'POST', '/api/config', { models: [{ name: 'Broken', api_base_url: 'http://127.0.0.1:9/v1', api_key: 'test-key-not-real', model: 'x', enabled: true }] })
await nav(page, '上场')
await api(base, 'POST', '/api/ask', { text: '这道题怎么做？' })
await page.waitForTimeout(6000)
await shot(page, 'error', 'provider unreachable → user-facing error in the answer card')

// Dark theme and 390px
await page.evaluate(() => { localStorage.setItem('ia-color-scheme', 'vscode-dark-plus') })
await page.reload()
await page.getByRole('heading', { name: '成竹', exact: true }).waitFor()
await nav(page, '我的成竹')
await page.getByRole('tab', { name: '事实与来源' }).click()
await shot(page, 'dark-facts', 'dark theme: facts & sources (AA status colors)')
await nav(page, '首页')
await shot(page, 'dark-home', 'dark theme: home')
await page.evaluate(() => { localStorage.setItem('ia-color-scheme', 'vscode-light-plus') })
await app.evaluate(({ BrowserWindow }) => { const w = BrowserWindow.getAllWindows().find((x) => x.isVisible() && !x.webContents.getURL().includes('overlay=1')); w?.setMinimumSize(360, 500); w?.setSize(390, 844) })
await page.reload()
// The brand heading is hidden at phone width; wait for the page body instead.
await page.waitForLoadState('domcontentloaded')
await page.waitForTimeout(2500)
await shot(page, 'mobile-390-home', '390px wide window')
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
manifest.push({ name: '_390_overflow', note: `horizontal overflow at 390px: ${overflow}` })

fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify({ captured_at: new Date().toISOString(), space_id: space?.id, entries: manifest }, null, 2))
await app.close()
provider.close()
console.log('done', OUT)
