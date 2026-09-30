// Release evidence capture (v1.2-R2 Stage Y).
//
// Drives the INSTALLED Chengzhu.exe (installed from the GitHub Release
// download, not a repo build) with Playwright's Electron driver, an isolated
// user-data dir, its own port and a local fake OpenAI-compatible provider,
// then walks the product and saves screenshots + manifest.json.
//
//   node scripts/capture-release-evidence.mjs --exe "<install dir>\Chengzhu.exe" \
//        --out ../artifacts/release-evidence/v1.2.0-download-back [--port 18081]
//
// Every shot is best-effort and recorded honestly in the manifest: a screen
// that could not be reached is listed with its error, never faked.
import { _electron as electron } from 'playwright'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, cur, i, all) => (cur.startsWith('--') ? [...acc, [cur.slice(2), all[i + 1]]] : acc), []),
)
const exe = path.resolve(args.exe)
const outDir = path.resolve(args.out)
const port = Number(args.port || 18081)
const base = `http://127.0.0.1:${port}`
fs.mkdirSync(outDir, { recursive: true })

const RESUME = `张三 · 后端开发工程师 · 5 年经验
工作经历：
- 某电商公司 2021-至今：负责订单系统重构，把下单接口 P99 从 800ms 降到 120ms；引入 Redis 缓存与本地缓存两级架构。
- 用 Kafka 做订单事件异步化，峰值 3000 QPS；设计了幂等消费与死信重试。
技能：Java, Go, Redis, Kafka, MySQL, Kubernetes`
const JD = `高级后端工程师（交易方向）
职责：负责交易与订单核心链路的设计与稳定性；推动缓存、消息队列、限流降级方案落地。
要求：熟悉 Redis、Kafka、MySQL；有高并发系统设计经验；有容量评估与故障排查经验。`

// --- fake OpenAI-compatible provider ------------------------------------------
const ANSWER = '先讲结论：两级缓存 + 失效广播。再讲机制：本地缓存短 TTL，Redis 作为共享层，写后删除并通过消息广播失效。最后讲取舍：一致性窗口换延迟。'
const fake = http.createServer((req, res) => {
  let body = ''
  req.on('data', (c) => { body += c })
  req.on('end', () => {
    if (req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      return res.end(JSON.stringify({ object: 'list', data: [{ id: 'fake-model', object: 'model' }] }))
    }
    const reqJson = JSON.parse(body || '{}')
    if (!reqJson.stream) {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      return res.end(JSON.stringify({ id: 'c1', object: 'chat.completion', model: 'fake-model', choices: [{ index: 0, message: { role: 'assistant', content: ANSWER }, finish_reason: 'stop' }] }))
    }
    res.writeHead(200, { 'Content-Type': 'text/event-stream' })
    const parts = ANSWER.match(/.{1,8}/gu) ?? [ANSWER]
    let i = 0
    const timer = setInterval(() => {
      if (i >= parts.length) {
        res.write('data: [DONE]\n\n')
        clearInterval(timer)
        return res.end()
      }
      res.write(`data: ${JSON.stringify({ id: 'c1', object: 'chat.completion.chunk', model: 'fake-model', choices: [{ index: 0, delta: { content: parts[i++] }, finish_reason: null }] })}\n\n`)
    }, 40)
  })
})
await new Promise((r) => fake.listen(0, '127.0.0.1', r))
const fakeBase = `http://127.0.0.1:${fake.address().port}/v1`

const manifest = { captured_at: new Date().toISOString(), exe, port, entries: [] }
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'chengzhu-release-evidence-'))
manifest.userData = userData

async function api(p, init = {}) {
  const res = await fetch(`${base}${p}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  const text = await res.text()
  if (!res.ok) throw new Error(`${p} -> ${res.status} ${text.slice(0, 200)}`)
  return text.trim().startsWith('{') || text.trim().startsWith('[') ? JSON.parse(text) : text
}

const app = await electron.launch({
  executablePath: exe,
  args: [`--user-data-dir=${userData}`],
  env: { ...process.env, PORT: String(port) },
  timeout: 180000,
})
// The app also opens a hidden overlay window (?overlay=1) — pick the main one.
async function mainWindow() {
  for (let i = 0; i < 180; i++) {
    const main = app.windows().find((w) => !w.url().includes('overlay=1') && w.url().startsWith('http'))
    if (main) return main
    await new Promise((r) => setTimeout(r, 1000))
  }
  throw new Error('main window not found')
}
const win = await mainWindow()
await win.setViewportSize({ width: 1440, height: 900 }).catch(() => {})

async function shot(name, note, action) {
  const file = path.join(outDir, `${name}.png`)
  try {
    if (action) await action()
    await win.waitForTimeout(600)
    await win.screenshot({ path: file })
    manifest.entries.push({ name, file: path.relative(path.resolve(outDir, '..', '..', '..'), file), note })
    console.log('shot', name)
  } catch (err) {
    manifest.entries.push({ name, error: String(err?.message || err).slice(0, 300), note })
    console.log('MISS', name, String(err?.message || err).slice(0, 160))
  }
}
const tab = (name) => win.getByRole('tab', { name, exact: true }).first().click()

// wait for our own sidecar
for (let i = 0; i < 180; i++) {
  try { const inst = await api('/api/instance'); if (inst.app === 'chengzhu') break } catch { /* not yet */ }
  await new Promise((r) => setTimeout(r, 1000))
}
await win.waitForLoadState('domcontentloaded')
await shot('first-launch', 'fresh user data: the first screen the installed app shows')
await shot('onboarding', 'first-run guide', async () => {
  await win.getByText(/首次|引导|欢迎|开始使用/).first().waitFor({ timeout: 20000 })
})

// Onboarding through the product API (model optional → fake local provider)
const cfg = await api('/api/config', {
  method: 'POST',
  body: JSON.stringify({
    models: [{ name: 'Fake (evidence)', api_base_url: fakeBase, api_key: 'test-key-not-real', model: 'fake-model', enabled: true, supports_think: false, supports_vision: false }],
    active_model: 0,
    onboarding_completed: true,
  }),
}).catch((e) => ({ error: String(e) }))
manifest.config_result = cfg.error ? cfg : 'ok'
const form = new FormData()
form.append('file', new Blob([RESUME], { type: 'text/plain' }), 'resume.txt')
manifest.resume_upload = await fetch(`${base}/api/resume`, { method: 'POST', body: form }).then((r) => r.status)
const space = await api('/api/prep/spaces', { method: 'POST', body: JSON.stringify({ title: '高级后端工程师', role: '高级后端工程师', company: '示例公司', jd_text: JD, resume_text: RESUME }) })
manifest.space_id = space.id
const launch = await api(`/api/prep/spaces/${space.id}/launch-pack`, { method: 'POST', body: '{}' }).catch((e) => ({ error: String(e) }))
manifest.launch_pack = launch.error ? launch : { interview_pack: launch.interview_pack ?? launch.pack ?? null }
const pack = await api('/api/intelligence/pack').catch((e) => ({ error: String(e) }))
manifest.pack_frozen = Boolean(pack?.frozen)
manifest.pack_id = pack?.pack?.id ?? null

await win.reload()
await win.waitForLoadState('domcontentloaded')
await shot('home', 'home after onboarding', async () => { await tab('首页').catch(() => {}) })
await shot('facts', '我的成竹 → 事实与来源', async () => {
  await tab('我的成竹')
  await win.getByRole('tab', { name: /事实与来源/ }).first().click()
})
await shot('prepare', '求职 → 岗位目标 (prepare)', async () => { await tab('求职') })
await shot('freeze', 'job goal opened: prepare + frozen InterviewPack', async () => {
  await win.getByText('高级后端工程师').first().click()
  await win.waitForTimeout(1500)
})
await shot('preflight', '上场 → pack bar / preflight', async () => { await tab('上场') })

// Live: a question through the real ask path → Fast Cue before the deep answer
await api('/api/ask', { method: 'POST', body: JSON.stringify({ text: '你们的缓存一致性是怎么做的？' }) }).catch((e) => { manifest.ask_error = String(e) })
await shot('live-fast-cue', 'Fast Cue rendered above the deep answer (fake provider)', async () => {
  await win.getByText(/缓存一致性/).first().waitFor({ timeout: 30000 })
  await win.waitForTimeout(2500)
})

// Overlay: the app's own overlay window (?overlay=1), shown, with a live cue
try {
  const overlay = app.windows().find((w) => w.url().includes('overlay=1'))
  if (!overlay) throw new Error('overlay window not found')
  await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows().find((x) => x.webContents.getURL().includes('overlay=1'))
    if (w) { w.setBounds({ width: 480, height: 420 }); w.show() }
  })
  await api('/api/ask', { method: 'POST', body: JSON.stringify({ text: '消息队列怎么保证不丢消息？' }) })
  await overlay.waitForTimeout(4000)
  const file = path.join(outDir, 'overlay.png')
  await overlay.screenshot({ path: file })
  manifest.entries.push({ name: 'overlay', file: path.relative(path.resolve(outDir, '..', '..', '..'), file), note: 'the app overlay window (?overlay=1) after a Live question' })
} catch (err) {
  manifest.entries.push({ name: 'overlay', error: String(err?.message || err).slice(0, 300) })
}
await shot('review', '复盘', async () => { await tab('复盘') })
await shot('settings', 'settings drawer', async () => {
  await win.keyboard.press('Escape').catch(() => {})
  await win.getByRole('button', { name: '设置', exact: true }).first().click()
})
await shot('about-version', 'settings → 关于: version / license / source', async () => {
  const search = win.getByLabel('搜索设置项')
  if (await search.isDisabled()) await win.getByRole('button', { name: '常用' }).first().click()
  await search.fill('关于')
  const v = win.getByText(/1\.2\.0/).first()
  await v.scrollIntoViewIfNeeded()
  await v.waitFor({ timeout: 10000 })
})

manifest.version_api = await api('/api/instance').catch(() => null)
fs.writeFileSync(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2))
await app.close()
fake.close()
console.log('done', outDir)
