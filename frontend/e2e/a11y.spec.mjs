import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

import { COMMON_WS_BOOTSTRAP, installMocks } from './fixtures/setup.mjs'

// R2 Stage Z accessibility smoke: no critical/serious axe violations on the
// main R2 screens, and the primary navigation is keyboard reachable.
const SCREENS = [
  ['home', 'home'],
  ['my-chengzhu', 'resume-opt'],
  ['job', 'job-tracker'],
  ['rehearse', 'prep'],
  ['live', 'assist'],
  ['review', 'review'],
]

for (const [name, mode] of SCREENS) {
  test(`a11y: ${name} has no critical/serious violations`, async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: mode },
    })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: '成竹', exact: true })).toBeVisible()
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
    localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: 'home' },
  })
  await page.goto('/')
  const jobTab = page.getByRole('tab', { name: '求职' })
  await jobTab.focus()
  await expect(jobTab).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(jobTab).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('Tab')
  await expect(page.locator(':focus')).toBeVisible()
})
