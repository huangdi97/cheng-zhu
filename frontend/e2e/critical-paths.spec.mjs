/**
 * Critical-path smoke tests with mocked backend and WebSocket.
 *
 * Goal: catch regressions that break the v1.3 Goal-centered shell — the nav
 * rail, the global 上场 action, per-route rendering, and the settings page —
 * without needing a live backend or any audio device.
 *
 * The product API is deliberately left at the shared fixture fallback, so every
 * routed screen is exercised against a partial payload. A screen that only
 * survives a complete response would fail here on purpose.
 */
import { test, expect } from '@playwright/test'
import { installMocks, COMMON_WS_BOOTSTRAP } from './fixtures/setup.mjs'

/** The canonical §3 IA: 首页 / 求职目标 / 我的成竹 / 练习 / 资料库 / 历史 / 设置. */
const NAV_ITEMS = ['首页', '求职目标', '我的成竹', '练习', '资料库', '历史', '设置']
/** v1.2 module-centric destinations that must no longer be top-level. */
const RETIRED_NAV_ITEMS = ['准备', '复盘', '上场']

const ROUTES = [
  ['/home', '首页'],
  ['/goals', '求职目标'],
  ['/me', '我的成竹'],
  ['/practice', '练习'],
  ['/library', '资料库'],
  ['/history', '历史'],
  ['/settings', '设置'],
]

const IGNORABLE_ERROR = (e) =>
  e.includes('favicon') || e.includes('downloadable font') || e.toLowerCase().includes('manifest')

test.describe('app shell (live)', () => {
  test.beforeEach(async ({ context }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: {
        'ia-color-scheme': 'vscode-light-plus',
        'ia_app_mode': 'assist',
      },
    })
  })

  test('boots and shows the brand header + STT status pill', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: '成竹', exact: true })).toBeVisible()
    // App.tsx 状态 chip 文案为「STT 就绪」（中间有空格），且 md+ 才显示文字；viewport 默认 1440 可见
    await expect(page.getByText('STT 就绪')).toBeVisible({ timeout: 5000 })
  })

  test('does not log uncaught errors during initial render', async ({ page }) => {
    /** @type {string[]} */
    const errors = []
    page.on('pageerror', (err) => errors.push(String(err)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await page.goto('/')
    await expect(page.getByRole('heading', { name: '成竹', exact: true })).toBeVisible()
    await page.waitForTimeout(500)

    const significant = errors.filter((e) => !IGNORABLE_ERROR(e))
    expect(significant, `Console errors:\n${significant.join('\n')}`).toEqual([])
  })
})

test.describe('v1.3 goal-centered navigation', () => {
  test.beforeEach(async ({ context }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
    })
  })

  test('primary nav exposes the Goal-centered IA and retires the module tabs', async ({ page }) => {
    await page.goto('/#/home')

    const nav = page.getByRole('navigation', { name: '主导航' })
    for (const label of NAV_ITEMS) {
      await expect(nav.getByRole('button', { name: label })).toBeVisible()
    }
    for (const label of RETIRED_NAV_ITEMS) {
      await expect(nav.getByRole('button', { name: label })).toHaveCount(0)
    }

    // 上场 is a global action in the header, not a navigation destination.
    await expect(page.getByRole('navigation', { name: '主导航' }).getByRole('button', { name: '上场' })).toHaveCount(0)
    await expect(page.getByTestId('go-live')).toBeVisible()

    await expect(nav.getByRole('button', { name: '首页' })).toHaveAttribute('aria-current', 'page')
  })

  test('clicking each nav item navigates and marks the current page', async ({ page }) => {
    await page.goto('/#/home')
    const nav = page.getByRole('navigation', { name: '主导航' })

    for (const [path, label] of ROUTES) {
      await nav.getByRole('button', { name: label }).click()
      await expect(page).toHaveURL(new RegExp(`#${path}`))
      await expect(nav.getByRole('button', { name: label })).toHaveAttribute('aria-current', 'page')
    }
  })

  test('every v1.3 route renders against a partial payload without uncaught errors', async ({ page }) => {
    const collected = []
    page.on('pageerror', (err) => collected.push(String(err)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') collected.push(msg.text())
    })

    for (const [path] of ROUTES) {
      collected.length = 0
      // A reload gives each route a fresh document, so one screen's crash can
      // never be masked by the previous route's state.
      await page.goto(`/#${path}`)
      await page.reload()
      await expect(page.getByRole('heading', { name: '成竹', exact: true })).toBeVisible()
      await page.waitForTimeout(500)

      const significant = collected.filter((e) => !IGNORABLE_ERROR(e))
      expect(significant, `${path} produced console errors:\n${significant.join('\n')}`).toEqual([])
      // The shell must survive: the nav rail is only gone if the root unmounted.
      await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
      // A screen that blew up renders the boundary state instead of its content.
      await expect(page.getByTestId('page-error')).toHaveCount(0)
    }
  })
})

test.describe('settings', () => {
  test('opens from the nav rail, groups by layer, and searches', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
    })
    await page.goto('/#/home')

    await page.getByRole('navigation', { name: '主导航' }).getByRole('button', { name: '设置' }).click()
    await expect(page.getByTestId('settings-page')).toBeVisible()

    // Canonical §37 groups.
    const groups = page.getByRole('navigation', { name: '设置分组' })
    for (const label of ['通用', '模型', '语音与音频', '语言', '上场与浮窗', '隐私', '知识库', '快捷键', '数据与导出', '诊断']) {
      await expect(groups.getByRole('button', { name: new RegExp(label) })).toBeVisible()
    }

    // Settings Search (canonical §54).
    await page.getByTestId('settings-search').fill('模型')
    await expect(page.getByRole('listbox', { name: '搜索结果' })).toBeVisible()

    // The Models group renders the configured model list.
    await page.goto('/#/settings/models')
    await expect(page.getByText(/GPT-4\.1 Mini/).first()).toBeVisible({ timeout: 8000 })
  })
})

test.describe('assist mode with WebSocket-driven Q/A', () => {
  test('renders streamed transcripts and answer payload from mock WS', async ({ context, page }) => {
    const now = Math.floor(Date.now() / 1000)

    await installMocks(context, {
      messages: [
        ...COMMON_WS_BOOTSTRAP,
        {
          type: 'init',
          delay: 50,
          transcriptions: ['请介绍一下你做过最有挑战的一个项目。'],
          qa_pairs: [
            {
              id: 'qa-mock-1',
              question: '请介绍一下你做过最有挑战的一个项目。',
              answer: '核心要点是先讲背景与目标、再讲关键决策、最后讲量化结果。',
              thinkContent: '',
              timestamp: now - 5,
              source: 'manual_text',
              model_name: 'GPT-4.1 Mini',
            },
          ],
          is_recording: false,
          is_paused: false,
          stt_loaded: true,
        },
      ],
      localStorage: {
        'ia-color-scheme': 'vscode-light-plus',
        'ia_app_mode': 'assist',
      },
    })

    await page.goto('/')
    await expect(page.getByRole('heading', { name: '成竹', exact: true })).toBeVisible()
    await expect(page.getByText('请介绍一下你做过最有挑战的一个项目。').first()).toBeVisible({
      timeout: 5000,
    })
    await expect(
      page.getByText('核心要点是先讲背景与目标、再讲关键决策、最后讲量化结果。'),
    ).toBeVisible({ timeout: 5000 })
  })
})
