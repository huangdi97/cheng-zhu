import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..')
const EVIDENCE_ROOT = path.join(ROOT, 'artifacts', 'release-evidence')
const OUT = path.join(ROOT, 'docs', 'screenshots')

const mapping = [
  ['02-action-home.png', 'action-home.png'],
  ['04-goal-overview.png', 'goal-room.png'],
  ['14-practice-setup.png', 'practice.png'],
  ['21-preflight.png', 'preflight.png'],
  ['23-live-fast-cue.png', 'live-fast-cue.png'],
  ['16-reflection.png', 'reflection.png'],
  ['20-command-palette.png', 'command-palette.png'],
  ['29-mobile-390-goal-prepare.png', 'goal-prepare-390.png'],
]

function candidates() {
  if (!fs.existsSync(EVIDENCE_ROOT)) return []
  return fs.readdirSync(EVIDENCE_ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^v\d+\.\d+/.test(entry.name))
    .map((entry) => path.join(EVIDENCE_ROOT, entry.name))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)
}

function findSource(dir, name) {
  const direct = path.join(dir, name)
  if (fs.existsSync(direct)) return direct
  const stack = [dir]
  while (stack.length) {
    const current = stack.pop()
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const p = path.join(current, entry.name)
      if (entry.isDirectory()) stack.push(p)
      else if (entry.name === name) return p
    }
  }
  return null
}

const dirs = candidates()
const sourceDir = dirs.find((dir) => mapping.every(([source]) => findSource(dir, source)))
if (!sourceDir) {
  console.error([
    'No complete Goal-centered runtime-evidence set was found.',
    'README media must come from current runtime evidence; the old Assist demo generator is intentionally no longer used.',
    'Run/download the packaged runtime UI evidence first, then retry:',
    '  npm run screenshots:readme',
    `Expected root: ${EVIDENCE_ROOT}`,
  ].join('\n'))
  process.exit(2)
}

fs.mkdirSync(OUT, { recursive: true })
for (const [sourceName, targetName] of mapping) {
  const source = findSource(sourceDir, sourceName)
  const target = path.join(OUT, targetName)
  fs.copyFileSync(source, target)
  const size = fs.statSync(target).size
  if (size < 10_000) throw new Error(`promoted screenshot is unexpectedly small: ${target} (${size})`)
  console.log(`promoted ${path.relative(ROOT, source)} -> ${path.relative(ROOT, target)}`)
}

console.log([
  '',
  'README product media now reflects the current Goal-centered runtime.',
  'The historical assist-demo.*, assist-mode.png, knowledge-map.png and resume-optimizer.png are not modified.',
  'They are retained only as historical media and are not used by the current README hero.',
].join('\n'))
