// Regression guard for the packaged Windows app's asar manifest.
//
// electron-builder replaces its default `**/*` file set with the explicit
// `build.files` list in package.json. A module that main.js requires at module
// scope but that is missing from that list makes the packaged app throw before
// `app.whenReady()` ever runs: Electron then blocks on its main-process error
// dialog, so the shipped product opens no window, never starts the backend and
// never creates its user-data directory. That is exactly what happened when
// `overlayLayout.js` was required by main.js but never added to `build.files`.
//
// This test fails whenever a packaged entry point loads a local module or an
// __dirname-relative resource that `build.files` does not ship.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const DESKTOP_DIR = __dirname;
const pkg = require('./package.json');
const packagedFiles = new Set(pkg.build.files);

function read(f) {
  return fs.readFileSync(path.join(DESKTOP_DIR, f), 'utf8');
}

function localRequires(source) {
  const found = new Set();
  const re = /require\(\s*['"]\.\/([^'"]+)['"]\s*\)/g;
  let match;
  while ((match = re.exec(source)) !== null) found.add(match[1]);
  return found;
}

function dirnameResources(source) {
  const found = new Set();
  const re = /path\.join\(\s*__dirname\s*,\s*['"]([^'"]+)['"]\s*\)/g;
  let match;
  while ((match = re.exec(source)) !== null) found.add(match[1]);
  return found;
}

function resolvePackagedTarget(dep) {
  return path.extname(dep) ? dep : `${dep}.js`;
}

test('build.files ships every local module the packaged entry points require', () => {
  const missing = [];
  for (const file of [...packagedFiles].filter((f) => f.endsWith('.js'))) {
    const source = read(file);
    for (const dep of localRequires(source)) {
      const target = resolvePackagedTarget(dep);
      if (!packagedFiles.has(target)) missing.push(`${file} requires ./${dep} but build.files has no ${target}`);
    }
  }
  assert.deepStrictEqual(missing, []);
});

test('build.files ships every __dirname-relative resource the packaged main process reads', () => {
  const missing = [];
  for (const file of [...packagedFiles].filter((f) => f.endsWith('.js'))) {
    for (const resource of dirnameResources(read(file))) {
      if (!packagedFiles.has(resource)) missing.push(`${file} reads __dirname/${resource} but build.files has no ${resource}`);
    }
  }
  assert.deepStrictEqual(missing, []);
});

test('every file listed in build.files actually exists in the desktop package', () => {
  const absent = [...packagedFiles].filter((f) => !fs.existsSync(path.join(DESKTOP_DIR, f)));
  assert.deepStrictEqual(absent, []);
});
