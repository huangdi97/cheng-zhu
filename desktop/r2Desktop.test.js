const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const sharePrivacy = require('./sharePrivacy');
const launcher = require('./backendLauncher');

test('share privacy defaults OFF and only accepts known modes', () => {
  assert.equal(sharePrivacy.DEFAULT_MODE, 'OFF');
  assert.equal(sharePrivacy.normalizeMode(undefined), 'OFF');
  assert.equal(sharePrivacy.normalizeMode('undetectable'), 'OFF');
  assert.equal(sharePrivacy.normalizeMode('private_overlay'), 'PRIVATE_OVERLAY');
  const state = sharePrivacy.createSharePrivacyState();
  assert.equal(state.mode, 'OFF');
  assert.equal(state.protected, false);
});

test('share privacy applies content protection to windows only when on', () => {
  const calls = [];
  const win = { isDestroyed: () => false, setContentProtection: (v) => calls.push(v) };
  sharePrivacy.applyToWindow(win, 'OFF');
  sharePrivacy.applyToWindow(win, 'PRIVATE_OVERLAY');
  assert.deepEqual(calls, [false, true]);
  assert.equal(sharePrivacy.applyToWindow({ isDestroyed: () => true, setContentProtection: () => { throw new Error('x'); } }, 'PRIVATE_OVERLAY'), false);
});

test('share privacy copy never promises undetectability', () => {
  assert.match(sharePrivacy.SHARE_PRIVACY_COPY, /不是安全或“不可检测”保证/);
});

test('state notifies listeners on change', () => {
  const state = sharePrivacy.createSharePrivacyState('OFF');
  const seen = [];
  state.onChange((m) => seen.push(m));
  state.set('PRIVATE_OVERLAY');
  state.set('PRIVATE_OVERLAY');
  state.set('OFF');
  assert.deepEqual(seen, ['PRIVATE_OVERLAY', 'OFF']);
});

test('packaged backend uses the sidecar exe and the user-data dir, not system python', () => {
  const cmd = launcher.resolveBackendCommand({
    isPackaged: true,
    resourcesPath: 'C:\\Program Files\\Chengzhu\\resources',
    repoRoot: 'C:\\repo',
    port: 18081,
    userDataDir: 'C:\\Users\\u\\AppData\\Roaming\\Chengzhu',
    env: { PATH: 'x' },
    platform: 'win32',
  });
  assert.equal(cmd.command, path.join('C:\\Program Files\\Chengzhu\\resources', 'backend', 'chengzhu-backend.exe'));
  assert.ok(!/python/i.test(cmd.command));
  assert.deepEqual(cmd.args, ['--port', '18081', '--host', '127.0.0.1']);
  assert.equal(cmd.env.CHENGZHU_HOME, 'C:\\Users\\u\\AppData\\Roaming\\Chengzhu');
  assert.equal(cmd.env.CHENGZHU_FRONTEND_DIST, path.join('C:\\Program Files\\Chengzhu\\resources', 'frontend-dist'));
  assert.equal(cmd.env.CHENGZHU_DESKTOP_RUNTIME, '1');
});

test('development backend keeps the python start.py path', () => {
  const cmd = launcher.resolveBackendCommand({ isPackaged: false, resourcesPath: '', repoRoot: '/repo', port: 18080, userDataDir: '/u', env: {}, platform: 'linux' });
  assert.equal(cmd.command, 'python3');
  assert.equal(cmd.args[0], path.join('/repo', 'start.py'));
  assert.equal(cmd.env.CHENGZHU_HOME, undefined);
  assert.equal(cmd.env.CHENGZHU_DESKTOP_RUNTIME, '1');
});

test('pickPort skips occupied ports and gives up after the attempt budget', async () => {
  const busy = new Set([18080, 18081]);
  assert.equal(await launcher.pickPort(18080, { isFree: async (p) => !busy.has(p) }), 18082);
  assert.equal(await launcher.pickPort(18080, { attempts: 2, isFree: async (p) => !busy.has(p) }), null);
});

test('startup failures are explained to the user', () => {
  assert.match(launcher.describeStartupFailure({ code: 1, stderrTail: 'OSError: [Errno 10048] address already in use', port: 18080, packaged: true }), /端口 18080 被占用/);
  assert.match(launcher.describeStartupFailure({ code: -2, stderrTail: 'spawn ENOENT', port: 1, packaged: true }), /重新安装/);
  assert.match(launcher.describeStartupFailure({ code: -2, stderrTail: 'spawn python ENOENT', port: 1, packaged: false }), /安装版无需 Python/);
});

test('only a backend echoing this launch nonce is attached', () => {
  const nonce = launcher.newInstanceNonce();
  assert.equal(nonce.length, 32);
  assert.equal(launcher.isOwnInstance({ app: 'chengzhu', nonce }, nonce), true);
  assert.equal(launcher.isOwnInstance({ app: 'chengzhu', nonce: 'other' }, nonce), false);
  assert.equal(launcher.isOwnInstance({ app: 'chengzhu', nonce: '' }, ''), false);
  assert.equal(launcher.isOwnInstance({ status: 'ok' }, nonce), false);
  const cmd = launcher.resolveBackendCommand({ isPackaged: true, resourcesPath: 'r', repoRoot: 'x', port: 1, userDataDir: 'u', nonce, env: {}, platform: 'win32' });
  assert.equal(cmd.env.CHENGZHU_INSTANCE_NONCE, nonce);
});

test('a port with a listener is not free even if a loopback bind would succeed', async () => {
  const net = require('net');
  const server = net.createServer();
  await new Promise((r) => server.listen(0, '0.0.0.0', r));
  const port = server.address().port;
  assert.equal(await launcher.isPortAnswering(port), true);
  assert.equal(await launcher.isPortFree(port), false);
  await new Promise((r) => server.close(r));
});
