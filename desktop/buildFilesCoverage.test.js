// Regression gate: every local module required by packaged main-process code
// must be present in the electron-builder `build.files` list. A missing entry
// silently ships a Windows package whose main process throws
// "Cannot find module './X'" on first launch (P1: packaged app unusable).
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const { test } = require('node:test')

test('build.files covers every local module required by packaged main-process code', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'))
  const files = new Set(pkg.build.files || [])
  const sources = ['main.js', 'preload.js', 'regionPreload.js', 'backendLauncher.js', 'sharePrivacy.js',
    'multiScreenBatch.js', 'shortcuts.js', 'windowOptions.js', 'conversationReminders.js', 'overlayLayout.js']
  const required = new Set()
  for (const file of sources) {
    if (!fs.existsSync(path.join(__dirname, file))) continue
    const src = fs.readFileSync(path.join(__dirname, file), 'utf8')
    const re = /require\(\s*['"]\.\/([^'"\\/]+)['"]\s*\)/g
    let match
    while ((match = re.exec(src)) !== null) required.add(match[1])
  }
  const missing = [...required].filter((name) => !files.has(name) && !files.has(`${name}.js`))
  assert.deepStrictEqual(
    missing,
    [],
    `packaged main-process modules missing from desktop/package.json build.files: ${missing.join(', ')}`,
  )
})
