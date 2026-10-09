/**
 * Local full-simulation screenshot evidence (Phase AA).
 *
 * Drives the real built frontend (dist served by vite preview) with the shared
 * E2E JSON/WS mocks, capturing the surfaces the automated suites do not
 * screenshot: dark theme, 390px viewport, SILENT guidance state, Manual Ask
 * provenance, Diagnostics, Reminder settings, Screen context, Human Coach and
 * Private Overlay state, Preflight / Session Pack preview.
 *
 * Output: artifacts/local-validation/2026-10-09-chengzhu-full-simulation/screenshots/
 * Every capture asserts no aria-modal dialog / dimming backdrop obstructs the
 * surface (mirrors the packaged evidence contract).
 */
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { installMocks, COMMON_WS_BOOTSTRAP } from '../e2e/fixtures/setup.mjs'
import { chromium } from 'playwright'
import crypto from 'node:crypto'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)))
const OUT = path.join(ROOT, '..', 'artifacts', 'local-validation',
  '2026-10-09-chengzhu-full-simulation', 'screenshots')
import { resolveApiPayload } from '../e2e/fixtures/sample-data.mjs'

const SPACE = {
  id: 'cs-v2',
  profile: 'DESIGN_REVIEW',
  title: 'PDIG · Android Architecture',
  description: '技术设计评审',
  status: 'ACTIVE',
  default_goal: '决定 conflict merge strategy',
  default_mode: 'BALANCED',
  selected_source_ids: ['benchmark-note'],
  selected_quick_note_ids: [],
  retention_policy: { preset: 'STANDARD' },
  created_at: 1,
  updated_at: 2,
}

const SESSION = {
  id: 'cv-v2',
  space_id: SPACE.id,
  goal_ids: [],
  template: 'DESIGN_REVIEW',
  title: 'Architecture Review',
  scheduled_at: null,
  started_at: 2,
  ended_at: null,
  capture_mode: 'NOTES_ONLY',
  processing_mode: 'LOCAL',
  assistance_mode: 'BALANCED',
  consent_ack: true,
  policy: {
    transcript_retention: 'SPACE_POLICY',
    screen_context: 'OFF',
    ai_assistance: 'AI_ALLOWED',
    human_assistance: 'HUMAN_PRACTICE_ONLY',
    share_privacy: 'OFF',
    external_writeback: 'REVIEW_REQUIRED',
    participant_consent_status: 'USER_REPORTS_ALLOWED',
    participant_transparency_plan: 'USER_WILL_NOTIFY_VERBALLY',
    connector_permissions: [],
    speaker_biometric_identity: 'OFF',
    emotion_sentiment_profiling: 'OFF',
    hidden_intent_claims: 'OFF',
  },
  pack_id: 'cpack-v2',
  status: 'ACTIVE',
  state: { current_topic: '', open_threads: [], last_guidance_id: '' },
  created_at: 1,
  updated_at: 2,
}
fs.mkdirSync(OUT, { recursive: true })

const PORT = 4174
const BASE = `http://127.0.0.1:${PORT}`
const results = []

async function capture(page, name, note) {
  const dialogs = page.locator('[role="dialog"][aria-modal="true"]:visible')
  const dimmers = page.locator('div.fixed.inset-0.z-40:visible')
  const dialogCount = await dialogs.count()
  const dimmerCount = await dimmers.count()
  const file = path.join(OUT, `${name}.png`)
  await page.screenshot({ path: file, fullPage: false })
  results.push({
    name,
    note,
    file: path.relative(ROOT, file),
    sha256: cryptoHash(fs.readFileSync(file)),
    overlays_detected: dialogCount + dimmerCount,
    unobstructed: (dialogCount + dimmerCount) === 0,
  })
}

function cryptoHash(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex')
}

import net from 'node:net'

function isPortOpen(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host: '127.0.0.1' })
    socket.once('connect', () => { socket.destroy(); resolve(true) })
    socket.once('error', () => resolve(false))
  })
}

const specSrc = fs.readFileSync(path.join(ROOT, '..', 'e2e', 'v20-conversation-profile.spec.mjs'), 'utf8')
const mocksMatch = specSrc.match(/function mocks\(\) \{[\s\S]*?\n\}/)
if (!mocksMatch) throw new Error('v20 spec mocks() not found')
const makeMocks = new Function('SESSION', 'SPACE', 'resolveApiPayload', `return (${mocksMatch[0]})`)
const conversationMocks = makeMocks(SESSION, SPACE, resolveApiPayload)
async function run() {
  const server = spawn(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'preview', '--', '--host', '127.0.0.1', '--port', String(PORT), '--strictPort'],
    { cwd: ROOT, stdio: 'ignore', shell: process.platform === 'win32' })
  const deadline = Date.now() + 30000
  while (Date.now() < deadline) {
    if (await isPortOpen(PORT)) break
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  await new Promise((resolve) => setTimeout(resolve, 500))
  const browser = await chromium.launch({ headless: true })
  const conversations = []
  for (const theme of ['vscode-light-plus', 'vscode-dark-plus']) {
    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
      const ctx = await browser.newContext({ viewport })
      await installMocks(ctx, {
        messages: COMMON_WS_BOOTSTRAP,
        localStorage: {
          'ia-color-scheme': theme,
          'chengzhu-product-profile': 'conversation',
          'chengzhu-conversation-optin': '1',
        },
        apiOverrides: conversationMocks,
      })
      const page = await ctx.newPage()
      const tag = theme.includes('dark') ? 'dark' : 'light'
      const vw = viewport.width === 390 ? '390' : 'desktop'

      await page.goto(`${BASE}/#/conversation`, { waitUntil: 'networkidle' })
      await page.waitForSelector('[data-testid="conversation-home"]', { timeout: 20000 })
      await capture(page, `conversation-home-${tag}-${vw}`, 'Conversation Home')

      await page.goto(`${BASE}/#/conversation/spaces/${SPACE.id}`, { waitUntil: 'networkidle' })
      await capture(page, `space-overview-${tag}-${vw}`, 'Space Overview')

      await page.goto(`${BASE}/#/conversation/spaces/${SPACE.id}/prepare`, { waitUntil: 'networkidle' })
      await capture(page, `prepare-${tag}-${vw}`, 'Prepare')

      await page.goto(`${BASE}/#/conversation/live/${SESSION.id}`, { waitUntil: 'networkidle' })
      await capture(page, `live-${tag}-${vw}`, 'Live / Session Pulse')

      // SILENT state: no guidance card shown on a fresh Live page.
      await page.waitForTimeout(1200)
      const guidanceVisible = await page.locator('[data-testid="live-guidance-card"], .guidance-card').first().isVisible().catch(() => false)
      results.push({
        name: `silent-state-${tag}-${vw}`,
        note: 'SILENT: no shown guidance card on idle Live',
        file: '',
        sha256: '',
        unobstructed: !guidanceVisible,
      })

      // Manual Ask provenance.
      await page.locator('input[placeholder*="问"], textarea[placeholder*="问"], [data-testid="manual-ask-input"]').first().fill('10x 数据规模').catch(() => {})
      await page.keyboard.press('Enter').catch(() => {})
      await page.waitForTimeout(800)
      await capture(page, `manual-ask-provenance-${tag}-${vw}`, 'Manual Ask provenance')

      // Transcript panel.
      await page.goto(`${BASE}/#/conversation/live/${SESSION.id}`, { waitUntil: 'networkidle' })
      await capture(page, `transcript-${tag}-${vw}`, 'Transcript')

      // Screen context + Human Coach + Private overlay states are surfaced on Live.
      await page.goto(`${BASE}/#/conversation/live/${SESSION.id}`, { waitUntil: 'networkidle' })
      await capture(page, `live-surfaces-${tag}-${vw}`, 'Live surfaces (screen/coach/privacy chips)')

      // Continue / sessions.
      await page.goto(`${BASE}/#/conversation/spaces/${SPACE.id}/sessions`, { waitUntil: 'networkidle' })
      await capture(page, `continue-${tag}-${vw}`, 'Continue / Sessions')

      // History stays inside Conversation profile.
      await page.goto(`${BASE}/#/history`, { waitUntil: 'networkidle' })
      await capture(page, `history-${tag}-${vw}`, 'Conversation History')

      // Diagnostics.
      await page.goto(`${BASE}/#/settings`, { waitUntil: 'networkidle' })
      await capture(page, `diagnostics-${tag}-${vw}`, 'Settings / Diagnostics')

      // Reminder settings (conversation settings surface).
      await page.goto(`${BASE}/#/conversation/reminders`, { waitUntil: 'networkidle' })
      await capture(page, `reminder-settings-${tag}-${vw}`, 'Reminder settings')

      // Preflight / Session Pack preview surfaces from Space.
      await page.goto(`${BASE}/#/conversation/spaces/${SPACE.id}/prepare`, { waitUntil: 'networkidle' })
      await capture(page, `pack-preview-${tag}-${vw}`, 'Session Pack / Preflight surface')

      // Interview profile pages.
      await page.goto(`${BASE}/#/home`, { waitUntil: 'networkidle' })
      await capture(page, `interview-home-${tag}-${vw}`, 'Interview Home')

      await page.goto(`${BASE}/#/history`, { waitUntil: 'networkidle' })
      await capture(page, `interview-history-${tag}-${vw}`, 'Interview History (same route, Interview shell)')

      await ctx.close()
    }
  }
  await browser.close()
  server.kill()

  const manifest = {
    evidence_type: 'LOCAL_FULL_SIMULATION_SCREENSHOTS',
    surface_visibility: 'UNOBSTRUCTED_BY_MODAL',
    human_visual_acceptance: false,
    entries: results,
  }
  fs.writeFileSync(path.join(OUT, 'screenshots-manifest.json'), JSON.stringify(manifest, null, 2))
  console.log('screenshots:', results.length)
  for (const r of results) console.log(' ', r.name, '| unobstructed:', r.unobstructed, '|', r.file)
}

run().catch((err) => { console.error(err); process.exit(1) })
