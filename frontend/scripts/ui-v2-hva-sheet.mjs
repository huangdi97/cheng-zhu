#!/usr/bin/env node
/**
 * Build the human-facing acceptance pack for the UI v2 HVA run.
 *
 * The measurement harness (scripts/ui-v2-hva.mjs) writes evidence into
 * <HVA_ROOT>/<dir>/*.png + hva-metrics.json. This script turns that into:
 *
 *   - the numbered evidence folders the review contract asks for
 *     (01-first-run … 14-responsive mirrored from the latest run);
 *   - a single index.html contact sheet that a human can page through to make
 *     the final visual judgement (the agent that produced it has no eyes).
 *
 * Usage: node scripts/ui-v2-hva-sheet.mjs [rootDir]
 */
import { copyFile, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '..', '..')
const ROOT = path.resolve(process.argv[2] ?? process.env.HVA_ROOT ?? path.join(REPO, '.runtime', 'ui-v2-hva'))
const LATEST = path.join(ROOT, '15-final')

const DIRS = [
  '01-first-run', '02-home', '03-goals', '04-goal-room', '05-prepare', '06-practice',
  '07-preflight', '08-live', '09-reflection', '10-history', '11-me', '12-library',
  '13-settings', '14-responsive',
]

const LABELS = {
  '01-first-run': 'First Run / Create Goal',
  '02-home': 'Home',
  '03-goals': 'Goals',
  '04-goal-room': 'Goal Room',
  '05-prepare': 'Goal Prepare',
  '06-practice': 'Practice Setup',
  '07-preflight': 'Preflight',
  '08-live': 'Live Cockpit',
  '09-reflection': 'Reflection',
  '10-history': 'History',
  '11-me': 'My Chengzhu',
  '12-library': 'Library',
  '13-settings': 'Settings',
  '14-responsive': 'Responsive matrix',
}

async function listPngs(dir) {
  if (!existsSync(dir)) return []
  const entries = await readdir(dir)
  return entries.filter((name) => name.endsWith('.png')).sort()
}

async function main() {
  if (!existsSync(path.join(LATEST, 'hva-metrics.json'))) {
    console.error(`未找到 ${path.join(LATEST, 'hva-metrics.json')}；先运行 node scripts/ui-v2-hva.mjs`)
    process.exit(2)
  }
  const report = JSON.parse(await readFile(path.join(LATEST, 'hva-metrics.json'), 'utf8'))
  const byState = new Map()
  for (const state of report.states) {
    if (!byState.has(state.id)) byState.set(state.id, { label: state.label ?? state.id, failures: 0, viewports: [] })
    const entry = byState.get(state.id)
    entry.failures += (state.failures ?? []).length + (state.error ? 1 : 0)
    entry.viewports.push(state.viewport)
  }

  const sections = []
  for (const dir of DIRS) {
    const pngs = await listPngs(path.join(LATEST, dir))
    if (!pngs.length) continue
    const target = path.join(ROOT, dir)
    await mkdir(target, { recursive: true })
    for (const png of pngs) {
      if (!png.includes('1440x900') && dir !== '14-responsive') continue
      await copyFile(path.join(LATEST, dir, png), path.join(target, png))
    }
    sections.push({ dir, label: LABELS[dir] ?? dir, pngs, base: '15-final' })
  }

  const rows = []
  for (const state of byState.entries()) {
    const [id, entry] = state
    const ok = entry.failures === 0
    rows.push(`<tr><td>${id}</td><td>${entry.label}</td><td class="${ok ? 'ok' : 'bad'}">${ok ? 'PASS' : `FAIL (${entry.failures})`}</td><td>${entry.viewports.join(', ')}</td></tr>`)
  }

  const gallery = sections.map((section) => `
    <section>
      <h2>${section.dir} · ${section.label}</h2>
      <div class="grid">
        ${section.pngs.map((png) => `
          <figure>
            <img loading="lazy" src="${section.base}/${section.dir}/${encodeURIComponent(png)}" alt="${png}" />
            <figcaption>${png}</figcaption>
          </figure>`).join('')}
      </div>
    </section>`).join('')

  const html = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>Chengzhu UI v2 · Human Visual Acceptance</title>
<style>
  :root { color-scheme: light; }
  body { margin: 0; padding: 32px; font: 14px/1.6 Inter, "Segoe UI", "Microsoft YaHei UI", system-ui, sans-serif; color: #1B2420; background: #F6F7F6; }
  h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: -0.01em; }
  p.meta { margin: 0 0 24px; color: #58625D; font-size: 12px; }
  table { border-collapse: collapse; width: 100%; max-width: 900px; margin-bottom: 32px; font-size: 12px; }
  th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #DDE3DF; }
  th { font-weight: 600; color: #58625D; }
  td.ok { color: #256A4B; font-weight: 600; }
  td.bad { color: #AD4545; font-weight: 600; }
  section { margin-bottom: 40px; }
  h2 { font-size: 15px; margin: 0 0 12px; padding-bottom: 6px; border-bottom: 1px solid #DDE3DF; }
  .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
  figure { margin: 0; }
  img { width: 100%; border: 1px solid #DDE3DF; border-radius: 8px; background: #fff; display: block; }
  figcaption { margin-top: 4px; font-size: 11px; color: #69746E; }
</style>
</head>
<body>
<h1>Chengzhu UI v2 · Human Visual Acceptance</h1>
<p class="meta">
  HEAD ${report.head || '(not recorded)'} · branch ${report.branch || '(not recorded)'} · generated ${report.generatedAt}<br />
  ${report.states.length} state renders · ${report.viewports.join(' / ')} · ${report.failures.length} measured failures<br />
  这些截图是“待人类签收”的证据：机器只保证规则可测量，观感由你判断。
</p>
<table>
  <thead><tr><th>state</th><th>surface</th><th>measured</th><th>viewports</th></tr></thead>
  <tbody>${rows.join('')}</tbody>
</table>
${gallery}
</body>
</html>`

  await writeFile(path.join(ROOT, 'index.html'), html, 'utf8')
  console.log(`contact sheet: ${path.join(ROOT, 'index.html')}`)
  console.log(`sections: ${sections.length} · states: ${byState.size} · measured failures: ${report.failures.length}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(2)
})
