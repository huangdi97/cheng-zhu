// Bundle budget for the built Studio app.
//
// The interesting number is not "how big is dist" — it is "what does a first
// visit actually download before the first interactive frame". So this splits the
// build into the entry graph (what index.html pulls in eagerly) and the lazy route
// chunks, and budgets only the eager part plus a hard ceiling on any single chunk.
//
// Usage:
//   node scripts/ui-v2-bundle-budget.mjs            # report + enforce
//   node scripts/ui-v2-bundle-budget.mjs --write     # rewrite budgets to current+margin
import { readFile, readdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HERE, '..')
const DIST = path.join(FRONTEND, 'dist')
const BUDGETS = path.join(FRONTEND, 'perf-budgets.json')
const WRITE = process.argv.includes('--write')
const MARGIN = 1.05

if (!existsSync(path.join(DIST, 'index.html'))) {
  console.error('dist/index.html not found — run `npm run build` first')
  process.exit(2)
}

const indexHtml = await readFile(path.join(DIST, 'index.html'), 'utf8')
const eager = new Set()
for (const match of indexHtml.matchAll(/(?:src|href)="\/?(assets\/[^"]+)"/g)) {
  eager.add(match[1])
}

async function walk(dir) {
  const out = []
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...await walk(full))
    else out.push(full)
  }
  return out
}

const files = (await walk(DIST)).filter((file) => /\.(js|css)$/.test(file))
const rows = []
for (const file of files) {
  const rel = path.relative(DIST, file).split(path.sep).join('/')
  const raw = await readFile(file)
  rows.push({
    file: rel,
    eager: eager.has(rel),
    raw: raw.length,
    gzip: gzipSync(raw, { level: 9 }).length,
  })
}
rows.sort((a, b) => b.gzip - a.gzip)

const kb = (bytes) => Math.round(bytes / 102.4) / 10
const totals = rows.reduce((acc, row) => {
  acc.raw += row.raw
  acc.gzip += row.gzip
  if (row.eager) {
    acc.eagerRaw += row.raw
    acc.eagerGzip += row.gzip
  }
  return acc
}, { raw: 0, gzip: 0, eagerRaw: 0, eagerGzip: 0 })

const largest = rows[0]
const current = {
  eagerJsCssGzipKb: kb(totals.eagerGzip),
  totalGzipKb: kb(totals.gzip),
  largestChunkGzipKb: kb(largest?.gzip ?? 0),
}

console.log('Eager graph (what index.html loads before first paint)')
for (const row of rows.filter((r) => r.eager)) {
  console.log(`  ${String(kb(row.gzip)).padStart(6)} kB gz  ${row.file}`)
}
console.log(`\nLargest chunks overall`)
for (const row of rows.slice(0, 1)) {
  console.log(`  ${String(kb(row.gzip)).padStart(6)} kB gz  ${row.file}`)
}
console.log('\nCurrent', JSON.stringify(current))

let budgets = null
if (existsSync(BUDGETS)) budgets = JSON.parse(await readFile(BUDGETS, 'utf8'))

if (WRITE || !budgets) {
  const next = budgets ?? {}
  next.eagerJsCssGzipKb = Math.ceil(current.eagerJsCssGzipKb * MARGIN)
  next.totalGzipKb = Math.ceil(current.totalGzipKb * MARGIN)
  next.largestChunkGzipKb = Math.ceil(current.largestChunkGzipKb * MARGIN)
  next.note = 'Rewritten with --write: current value +5% headroom. Lower these deliberately, never by regeneration.'
  await writeFile(BUDGETS, `${JSON.stringify(next, null, 2)}\n`, 'utf8')
  console.log(`\nWrote ${path.relative(FRONTEND, BUDGETS)}`)
}

const failures = []
for (const [key, limit] of Object.entries(budgets ?? {})) {
  if (key === 'note' || typeof limit !== 'number') continue
  if (current[key] > limit) failures.push(`${key}: ${current[key]} kB > budget ${limit} kB`)
}

if (failures.length) {
  console.error('\nBundle budget exceeded:')
  for (const line of failures) console.error(`  - ${line}`)
  process.exit(1)
}
console.log('\nBundle budget ok')
