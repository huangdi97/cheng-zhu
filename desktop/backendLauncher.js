// R2 Stage AG/AH: how the Electron main process starts the backend.
//
// Packaged: resources/backend/chengzhu-backend.exe (PyInstaller sidecar).
//   No system Python, no pip. All user data goes to app.getPath('userData')
//   via CHENGZHU_HOME; the prebuilt frontend is resources/frontend-dist.
// Development: `python start.py --mode network --no-build` from the repo.

const crypto = require('crypto');
const fs = require('fs');
const net = require('net');
const path = require('path');

function sidecarExecutable(resourcesPath, platform = process.platform) {
  const name = platform === 'win32' ? 'chengzhu-backend.exe' : 'chengzhu-backend';
  return path.join(resourcesPath, 'backend', name);
}

function newInstanceNonce() {
  return crypto.randomBytes(16).toString('hex');
}

// Only a backend that echoes this launch's nonce is ours; anything else on the
// port (another app, a dev server) must never be attached to the window.
function isOwnInstance(body, nonce) {
  return Boolean(body && body.app === 'chengzhu' && nonce && body.nonce === nonce);
}

function resolveBackendCommand({ isPackaged, resourcesPath, repoRoot, port, userDataDir, nonce = '', env = process.env, platform = process.platform }) {
  if (isPackaged) {
    const exe = sidecarExecutable(resourcesPath, platform);
    return {
      command: exe,
      args: ['--port', String(port), '--host', '127.0.0.1'],
      cwd: path.dirname(exe),
      env: {
        ...env,
        CHENGZHU_HOME: userDataDir,
        CHENGZHU_FRONTEND_DIST: path.join(resourcesPath, 'frontend-dist'),
        CHENGZHU_INSTANCE_NONCE: nonce,
        CHENGZHU_DESKTOP_RUNTIME: '1',
        PYTHONIOENCODING: 'utf-8',
      },
      packaged: true,
    };
  }
  const python = env.IA_PYTHON_EXE || (platform === 'win32' ? 'python' : 'python3');
  return {
    command: python,
    args: [path.join(repoRoot, 'start.py'), '--mode', 'network', '--no-build', '--port', String(port)],
    cwd: repoRoot,
    env: { ...env, CHENGZHU_INSTANCE_NONCE: nonce, CHENGZHU_DESKTOP_RUNTIME: '1' },
    packaged: false,
  };
}

function ensureUserDataLayout(userDataDir) {
  for (const sub of ['data', 'config', 'logs', 'cache', 'exports']) {
    fs.mkdirSync(path.join(userDataDir, sub), { recursive: true });
  }
}

// Something already answering on the port means it is taken, even when a
// bind on 127.0.0.1 would succeed next to a 0.0.0.0 listener (Windows).
function isPortAnswering(port, host = '127.0.0.1', timeoutMs = 400) {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host });
    const done = (value) => { socket.destroy(); resolve(value); };
    socket.setTimeout(timeoutMs, () => done(false));
    socket.once('connect', () => done(true));
    socket.once('error', () => done(false));
  });
}

async function isPortFree(port, host = '127.0.0.1') {
  if (await isPortAnswering(port, host)) return false;
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once('error', () => resolve(false));
    server.listen({ port, host }, () => server.close(() => resolve(true)));
  });
}

async function pickPort(preferred, { attempts = 20, isFree = isPortFree } = {}) {
  for (let i = 0; i < attempts; i += 1) {
    const candidate = preferred + i;
    // eslint-disable-next-line no-await-in-loop
    if (await isFree(candidate)) return candidate;
  }
  return null;
}

// User-facing startup error text (shown in a dialog, never only in a terminal).
function describeStartupFailure({ code, stderrTail = '', port, packaged }) {
  const tail = String(stderrTail || '');
  if (/address already in use|10048|EADDRINUSE/i.test(tail)) {
    return `端口 ${port} 被占用。请关闭占用该端口的程序后重试。`;
  }
  if (packaged && /ENOENT/i.test(tail)) {
    return '找不到内置后端程序，安装可能不完整。请重新安装成竹。';
  }
  if (!packaged && /ENOENT/i.test(tail)) {
    return '开发模式需要本机 Python 3.11+（或设置 IA_PYTHON_EXE）。安装版无需 Python。';
  }
  return `后端进程异常退出 (code ${code})。${tail ? `\n\n最近日志：\n${tail.slice(-600)}` : ''}`;
}

module.exports = {
  newInstanceNonce,
  isOwnInstance,
  isPortAnswering,
  sidecarExecutable,
  resolveBackendCommand,
  ensureUserDataLayout,
  isPortFree,
  pickPort,
  describeStartupFailure,
};
