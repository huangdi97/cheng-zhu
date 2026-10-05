import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

import { COMMON_WS_BOOTSTRAP, installMocks } from './fixtures/setup.mjs'

// v1.3 accessibility smoke: no critical/serious axe violations on the
// Goal-centered IA screens, the primary navigation is keyboard reachable, and
// a v1.2 install still lands on the right v1.3 route through the appMode
// adapter.
//
// The product API is intentionally left at the shared fixture fallback, so
// these screens are measured in their empty state — the state a first-run user
// actually sees. A page that only looks correct once it has data would fail
// here on purpose.
const SCREENS = [
  ['home', '/home'],
  ['goals', '/goals'],
  ['me', '/me'],
  ['practice', '/practice'],
  ['library', '/library'],
  ['history', '/history'],
  ['settings', '/settings'],
]

for (const [name, path] of SCREENS) {
  test(`a11y: ${name} has no critical/serious violations`, async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
    })
    // Reduced motion: axe must measure settled colors, not a mid-fade frame.
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto(`/#${path}`)
    await expect(page.getByRole('heading', { name: '成竹', exact: true })).toBeVisible()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(600)
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    const blocking = results.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious')
    const summary = blocking.map((v) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`)
    expect(summary, summary.join('\n')).toEqual([])
  })
}

test('a11y: primary navigation is keyboard reachable', async ({ context, page }) => {
  await installMocks(context, {
    messages: COMMON_WS_BOOTSTRAP,
    localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
  })
  await page.goto('/#/home')

  const nav = page.getByRole('navigation', { name: '主导航' })
  const goalsButton = nav.getByRole('button', { name: '求职目标' })

  await goalsButton.focus()
  await expect(goalsButton).toBeFocused()
  await page.keyboard.press('Enter')

  await expect(page).toHaveURL(/#\/goals/)
  await expect(nav.getByRole('button', { name: '求职目标' })).toHaveAttribute('aria-current', 'page')

  // Focus must remain usable (and visible) after a keyboard-driven navigation.
  await page.keyboard.press('Tab')
  await expect(page.locator(':focus')).toBeVisible()
})

test('a11y: a v1.2 appMode still lands on its v1.3 route', async ({ context, page }) => {
  await installMocks(context, {
    messages: COMMON_WS_BOOTSTRAP,
    localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: 'job-tracker' },
  })
  // No hash: this is exactly the state an upgraded v1.2 install boots into.
  await page.goto('/')

  await expect(page).toHaveURL(/#\/goals/)
  await expect(page.getByRole('navigation', { name: '主导航' }).getByRole('button', { name: '求职目标' }))
    .toHaveAttribute('aria-current', 'page')
})
