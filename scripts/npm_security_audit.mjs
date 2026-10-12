#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'

const SEVERITY_ORDER = { info: 0, low: 1, moderate: 2, high: 3, critical: 4 }

function readJson(file) {
  const raw = fs.readFileSync(file, 'utf8')
  const value = JSON.parse(raw)
  if (!value || typeof value !== 'object' || !value.vulnerabilities || !value.metadata) {
    throw new Error(`Unsupported npm audit JSON: ${file}`)
  }
  return value
}

function counts(report) {
  return report.metadata?.vulnerabilities ?? {}
}

function entries(report) {
  return Object.entries(report.vulnerabilities ?? {}).map(([name, item]) => ({
    name,
    severity: String(item?.severity || 'unknown'),
    isDirect: Boolean(item?.isDirect),
    range: String(item?.range || ''),
    fixAvailable: item?.fixAvailable ?? false,
    effects: Array.isArray(item?.effects) ? item.effects.map(String) : [],
    nodes: Array.isArray(item?.nodes) ? item.nodes.map(String) : [],
  }))
}

function blocking(entriesList, minSeverity = 'high') {
  const min = SEVERITY_ORDER[minSeverity]
  return entriesList.filter((item) => (SEVERITY_ORDER[item.severity] ?? -1) >= min)
}

function electronRuntimeSensitive(item) {
  // Electron is declared as a devDependency because electron-builder consumes
  // it at build time, but the Electron runtime binary is shipped to users.
  // Only advisories that npm attributes to Electron itself are an automatic
  // runtime gate here. Build/install helpers remain visible in the full audit
  // report and require target/applicability review rather than being silently
  // called packaged-runtime vulnerabilities.
  return item.name === 'electron'
}

function esc(value) {
  return String(value).replaceAll('|', '\\|').replaceAll('\n', ' ')
}

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) {
  args.set(process.argv[i], process.argv[i + 1])
}

const frontProdPath = args.get('--frontend-production')
const frontFullPath = args.get('--frontend-full')
const desktopFullPath = args.get('--desktop-full')
const outPath = args.get('--out')
if (!frontProdPath || !frontFullPath || !desktopFullPath || !outPath) {
  throw new Error('usage: npm_security_audit.mjs --frontend-production <json> --frontend-full <json> --desktop-full <json> --out <md>')
}

const frontProd = readJson(frontProdPath)
const frontFull = readJson(frontFullPath)
const desktopFull = readJson(desktopFullPath)

const frontProdEntries = entries(frontProd)
const frontFullEntries = entries(frontFull)
const desktopFullEntries = entries(desktopFull)

const frontProdBlocking = blocking(frontProdEntries)
const electronRuntimeBlocking = blocking(desktopFullEntries.filter(electronRuntimeSensitive))
const buildOnlyHigh = blocking(desktopFullEntries.filter((item) => !electronRuntimeSensitive(item)))

const lines = [
  '# npm dependency security audit',
  '',
  '> Scope-aware CI report. A package appearing in the full audit is not automatically a vulnerability in the shipped Windows runtime.',
  '',
  '## Policy result',
  '',
  `- Frontend production high/critical: **${frontProdBlocking.length}**`,
  `- Electron runtime high/critical: **${electronRuntimeBlocking.length}**`,
  `- Desktop full-audit high/critical requiring build/target applicability review: **${buildOnlyHigh.length}**`,
  '',
  'Automatic blocking policy:',
  '- frontend production dependency high/critical => FAIL;',
  '- advisory directly attributed to Electron runtime high/critical => FAIL;',
  '- dev/build-only findings => REPORT, then assess target and reachable workflow before upgrade/release decisions.',
  '',
  '## Aggregate counts',
  '',
  '| Scope | info | low | moderate | high | critical | total |',
  '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
  `| frontend production | ${counts(frontProd).info ?? 0} | ${counts(frontProd).low ?? 0} | ${counts(frontProd).moderate ?? 0} | ${counts(frontProd).high ?? 0} | ${counts(frontProd).critical ?? 0} | ${counts(frontProd).total ?? 0} |`,
  `| frontend full | ${counts(frontFull).info ?? 0} | ${counts(frontFull).low ?? 0} | ${counts(frontFull).moderate ?? 0} | ${counts(frontFull).high ?? 0} | ${counts(frontFull).critical ?? 0} | ${counts(frontFull).total ?? 0} |`,
  `| desktop full | ${counts(desktopFull).info ?? 0} | ${counts(desktopFull).low ?? 0} | ${counts(desktopFull).moderate ?? 0} | ${counts(desktopFull).high ?? 0} | ${counts(desktopFull).critical ?? 0} | ${counts(desktopFull).total ?? 0} |`,
  '',
]

function addEntries(title, list) {
  lines.push(`## ${title}`, '')
  if (!list.length) {
    lines.push('None.', '')
    return
  }
  lines.push('| Package | Severity | Direct | Range | Fix available | Effects |', '| --- | --- | --- | --- | --- | --- |')
  for (const item of list.sort((a, b) => (SEVERITY_ORDER[b.severity] ?? -1) - (SEVERITY_ORDER[a.severity] ?? -1) || a.name.localeCompare(b.name))) {
    lines.push(`| ${esc(item.name)} | ${esc(item.severity)} | ${item.isDirect} | ${esc(item.range)} | ${esc(JSON.stringify(item.fixAvailable))} | ${esc(item.effects.join(', '))} |`)
  }
  lines.push('')
}

addEntries('Frontend production findings', frontProdEntries)
addEntries('Frontend full findings', frontFullEntries)
addEntries('Desktop full findings', desktopFullEntries)

fs.mkdirSync(path.dirname(outPath), { recursive: true })
fs.writeFileSync(outPath, lines.join('\n') + '\n', 'utf8')

console.log(JSON.stringify({
  frontend_production: counts(frontProd),
  frontend_full: counts(frontFull),
  desktop_full: counts(desktopFull),
  frontend_production_blocking: frontProdBlocking.map((item) => item.name),
  electron_runtime_blocking: electronRuntimeBlocking.map((item) => item.name),
  desktop_build_or_toolchain_high: buildOnlyHigh.map((item) => item.name),
  report: outPath,
}, null, 2))

if (frontProdBlocking.length || electronRuntimeBlocking.length) {
  process.exitCode = 1
}
