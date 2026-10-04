const { app, BrowserWindow, globalShortcut, Tray, Menu, nativeImage, ipcMain, screen } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

// Release/runtime evidence needs a disposable profile so CI never touches a
// developer or runner's normal Chengzhu data. Electron's Chromium
// --user-data-dir flag does not reliably change app.getPath('userData') early
// enough for our backend launcher, so support an explicit process-level
// override before app.whenReady(). Normal users never set this variable.
if (process.env.CHENGZHU_USER_DATA_DIR) {
  app.setPath('userData', path.resolve(process.env.CHENGZHU_USER_DATA_DIR));
}

// Windows: 透明 BrowserWindow 需要 DWM 硬件加速。
// 保留硬件加速可以让成竹的窗口隐私保护标记按系统能力工作；
// 这只是尽量减少本机录屏/截图的意外捕获，不承诺对第三方会议软件或系统策略隐身。
// 如个别旧设备透明窗口出现渲染异常，可设环境变量 ELECTRON_DISABLE_HW_ACCEL=1 回退。
const RUNTIME_EVIDENCE_MODE = process.env.CHENGZHU_RUNTIME_EVIDENCE === '1';

if (process.platform === 'win32') {
  if (!RUNTIME_EVIDENCE_MODE) {
    app.commandLine.appendSwitch('enable-transparent-visuals');
  }
  if (process.env.ELECTRON_DISABLE_HW_ACCEL === '1' || RUNTIME_EVIDENCE_MODE) {
    app.disableHardwareAcceleration();
  }
}

// 跨平台：尽早设置窗口隐私保护，降低 overlay 被本机截图/录屏意外捕获的概率。
// 这是 best-effort 的系统能力，不绕过会议软件、监考或反作弊策略。
app.commandLine.appendSwitch('enable-features', 'ScreenCaptureKitMac');
app.commandLine.appendSwitch(
  'disable-features',
  'CalculateNativeWinOcclusion,IOSurfaceCapturer,DesktopCaptureMacV2',
);
const {
  ShortcutStatus,
  createShortcutState,
  loadShortcutConfig,
  saveShortcutConfig,
  validateShortcutMap,
} = require('./shortcuts');
const {
  createOverlayChromeOptions,
  getPromptOverlayInitialWidth,
  relayChildOutput,
} = require('./windowOptions');
const { createMultiScreenBatch } = require('./multiScreenBatch');

const pkg = require('./package.json');

/** 应用显示名：环境变量 ELECTRON_APP_DISPLAY_NAME > desktop/app-title.json > package.json appDisplayName > 默认 */
function loadAppDisplayName() {
  const env = process.env.ELECTRON_APP_DISPLAY_NAME;
  if (env && String(env).trim()) return String(env).trim();
  const titlePath = path.join(__dirname, 'app-title.json');
  try {
    const raw = fs.readFileSync(titlePath, 'utf8');
    const j = JSON.parse(raw);
    if (j && typeof j.appDisplayName === 'string' && j.appDisplayName.trim()) {
      return j.appDisplayName.trim();
    }
  } catch {
    /* 无文件或解析失败 */
  }
  if (pkg.appDisplayName && String(pkg.appDisplayName).trim()) {
    return String(pkg.appDisplayName).trim();
  }
  return '成竹';
}

const APP_DISPLAY_NAME = loadAppDisplayName();

const ROOT = path.resolve(__dirname, '..');
const BACKEND_DIR = path.join(ROOT, 'backend');
const PREFERRED_PORT = parseInt(process.env.PORT || '18080', 10);
// Port is chosen at startup (the preferred one may be occupied).
let PORT = PREFERRED_PORT;
let SERVER_URL = `http://127.0.0.1:${PORT}`;
const sharePrivacy = require('./sharePrivacy');
const backendLauncher = require('./backendLauncher');
const overlayLayout = require('./overlayLayout');
// R2 Stage T: Share Privacy is OFF by default; one state drives both windows.
const sharePrivacyState = sharePrivacy.createSharePrivacyState(sharePrivacy.DEFAULT_MODE);
let backendStderrTail = '';
const evidenceNonce = String(process.env.CHENGZHU_INSTANCE_NONCE || '').trim();
const INSTANCE_NONCE = (
  process.env.CHENGZHU_RUNTIME_EVIDENCE === '1' && evidenceNonce.length >= 24
)
  ? evidenceNonce
  : backendLauncher.newInstanceNonce();

let mainWindow = null;
let overlayWindow = null;
let overlayLayoutState = { dock: 'FREE', interaction: 'INTERACTIVE', size: 'STANDARD' };
let tray = null;
let pythonProcess = null;
let isQuitting = false;
let shortcuts = {};
let _overlayDragging = false;
let _blurTimer = null;
let overlayAutoResizeUntil = 0;
let overlayPositionSaveTimer = null;
let lastOverlayState = {
  initialized: false,
  enabled: false,
  visible: false,
  opacity: 0.88,
  fontSize: 14,
  fontColor: '#e2e8f0',
  showBg: true,
  mode: 'glass',
  focusWidthPct: 96,
  focusHeightPct: 90,
  promptMaxWidth: 900,
  promptAutoFollow: false,
  maxLines: 0,
};

let runtimeEvidenceServer = null;

function runtimeEvidenceEnabled() {
  const token = String(process.env.CHENGZHU_RUNTIME_EVIDENCE_TOKEN || '');
  return process.env.CHENGZHU_RUNTIME_EVIDENCE === '1' && token.length >= 24;
}

function evidenceJson(res, status, payload) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(JSON.stringify(payload));
}

function evidenceReadJson(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > 256 * 1024) {
        reject(new Error('runtime evidence request too large'));
        try { req.destroy(); } catch { /* ignore */ }
      }
    });
    req.on('end', () => {
      if (!body) return resolve({});
      try { resolve(JSON.parse(body)); } catch (error) { reject(error); }
    });
    req.on('error', reject);
  });
}

function evidenceSafeName(name) {
  const raw = String(name || 'capture').trim();
  const safe = raw.replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  return (safe || 'capture').slice(0, 120);
}

function runtimeEvidencePlanPath() {
  // File-plan mode is local process orchestration: it never opens an evidence
  // HTTP listener, so it does not need the bridge bearer token. Requiring the
  // token here made plan startup depend on an unrelated transport concern.
  if (process.env.CHENGZHU_RUNTIME_EVIDENCE !== '1') return '';
  const raw = String(process.env.CHENGZHU_RUNTIME_EVIDENCE_PLAN || '').trim();
  if (!raw) return '';
  return path.resolve(raw);
}

function waitForMainWindowLoad(timeoutMs = 45000) {
  return new Promise((resolve, reject) => {
    if (!mainWindow || mainWindow.isDestroyed()) {
      reject(new Error('main window unavailable before evidence plan'));
      return;
    }

    // createWindow() intentionally clears Chromium cache before calling
    // loadURL(). During that small gap isLoadingMainFrame() is false even
    // though the renderer is still on the initial blank document. Treating
    // that as "loaded" lets executeJavaScript() race the first navigation and
    // can leave the packaged evidence plan pending forever on hosted Windows.
    // A ready renderer therefore means: the real Chengzhu HTTP document has
    // committed, it belongs to this sidecar, and the main frame is idle.
    const isAppDocumentReady = () => {
      if (!mainWindow || mainWindow.isDestroyed()) return false;
      const url = String(mainWindow.webContents.getURL() || '');
      if (!/^https?:\/\//i.test(url)) return false;
      if (SERVER_URL && !url.startsWith(SERVER_URL)) return false;
      return !mainWindow.webContents.isLoadingMainFrame();
    };

    let settled = false;
    let poll = null;
    const finish = (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (poll) clearInterval(poll);
      mainWindow?.webContents.removeListener('did-finish-load', onFinish);
      mainWindow?.webContents.removeListener('did-fail-load', onFail);
      mainWindow?.webContents.removeListener('did-start-navigation', onNavigation);
      if (error) reject(error);
      else resolve();
    };
    const check = () => {
      if (!mainWindow || mainWindow.isDestroyed()) {
        finish(new Error('main window destroyed before evidence plan'));
        return;
      }
      if (isAppDocumentReady()) finish();
    };
    const onFinish = () => check();
    const onNavigation = () => check();
    const onFail = (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
      if (isMainFrame === false) return;
      finish(new Error(`main window failed to load (${errorCode}): ${errorDescription} ${validatedURL || ''}`));
    };
    const timer = setTimeout(
      () => finish(new Error(`main window load timeout after ${timeoutMs}ms; url=${mainWindow && !mainWindow.isDestroyed() ? mainWindow.webContents.getURL() : 'destroyed'}`)),
      Math.max(1000, Number(timeoutMs) || 45000),
    );

    mainWindow.webContents.on('did-finish-load', onFinish);
    mainWindow.webContents.on('did-fail-load', onFail);
    mainWindow.webContents.on('did-start-navigation', onNavigation);
    poll = setInterval(check, 100);
    check();
  });
}

async function evidenceCaptureToFile(outputDir, name, targetName = 'main') {
  const target = targetName === 'overlay' ? overlayWindow : mainWindow;
  if (!target || target.isDestroyed()) throw new Error(`${targetName} window unavailable`);
  const image = await target.capturePage();
  const safe = evidenceSafeName(name);
  const file = path.join(outputDir, safe.endsWith('.png') ? safe : `${safe}.png`);
  fs.writeFileSync(file, image.toPNG());
  return { file, target: targetName, width: image.getSize().width, height: image.getSize().height, url: target.webContents.getURL() };
}

function evidenceFillSelector(selector, value) {
  if (!mainWindow || mainWindow.isDestroyed()) throw new Error('main window unavailable');
  return mainWindow.webContents.executeJavaScript(
    `(() => {
      const el = document.querySelector(${JSON.stringify(String(selector || ''))});
      if (!el) return false;
      const proto = Object.getPrototypeOf(el);
      const setter = proto && Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      if (setter) setter.call(el, ${JSON.stringify(String(value ?? ''))});
      else el.value = ${JSON.stringify(String(value ?? ''))};
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()`,
    true,
  );
}

async function runRuntimeEvidencePlan() {
  const planPath = runtimeEvidencePlanPath();
  if (!planPath) return;
  const outputDir = path.resolve(
    process.env.CHENGZHU_RUNTIME_EVIDENCE_DIR || path.join(app.getPath('userData'), 'runtime-evidence'),
  );
  fs.mkdirSync(outputDir, { recursive: true });
  const resultPath = path.resolve(
    process.env.CHENGZHU_RUNTIME_EVIDENCE_RESULT || path.join(outputDir, 'plan-result.json'),
  );
  const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
  const entries = [];
  const startedAt = new Date().toISOString();
  try {
    for (const [index, rawStep] of (Array.isArray(plan.steps) ? plan.steps : []).entries()) {
      const step = rawStep && typeof rawStep === 'object' ? rawStep : {};
      const kind = String(step.kind || '');
      if (kind === 'sleep') {
        await new Promise((resolve) => setTimeout(resolve, Math.max(0, Math.min(30000, Number(step.ms) || 0))));
        continue;
      }
      if (kind === 'wait') {
        const found = await evidenceWaitForSelector(step.selector, step.timeout_ms);
        if (!found) throw new Error(`step ${index}: selector timeout ${step.selector}`);
        continue;
      }
      if (kind === 'navigate') {
        if (!mainWindow || mainWindow.isDestroyed()) throw new Error('main window unavailable');
        const hash = String(step.hash || '#/home');
        await mainWindow.webContents.executeJavaScript(`location.hash = ${JSON.stringify(hash)}`, true);
        if (step.selector && !(await evidenceWaitForSelector(step.selector, step.timeout_ms))) {
          throw new Error(`step ${index}: navigation selector timeout ${step.selector}`);
        }
        continue;
      }
      if (kind === 'reload') {
        if (!mainWindow || mainWindow.isDestroyed()) throw new Error('main window unavailable');
        mainWindow.webContents.reload();
        if (step.selector && !(await evidenceWaitForSelector(step.selector, step.timeout_ms))) {
          throw new Error(`step ${index}: reload selector timeout ${step.selector}`);
        }
        continue;
      }
      if (kind === 'click') {
        if (!mainWindow || mainWindow.isDestroyed()) throw new Error('main window unavailable');
        const selector = String(step.selector || '');
        const clicked = await mainWindow.webContents.executeJavaScript(
          `(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return false; el.click(); return true })()`,
          true,
        );
        if (!clicked) throw new Error(`step ${index}: click target missing ${selector}`);
        continue;
      }
      if (kind === 'fill') {
        const filled = await evidenceFillSelector(step.selector, step.value);
        if (!filled) throw new Error(`step ${index}: fill target missing ${step.selector}`);
        continue;
      }
      if (kind === 'key') {
        if (!mainWindow || mainWindow.isDestroyed()) throw new Error('main window unavailable');
        const keyCode = String(step.key || '');
        const modifiers = Array.isArray(step.modifiers) ? step.modifiers.map(String) : [];
        if (!keyCode) throw new Error(`step ${index}: key required`);
        mainWindow.webContents.sendInputEvent({ type: 'keyDown', keyCode, modifiers });
        mainWindow.webContents.sendInputEvent({ type: 'keyUp', keyCode, modifiers });
        continue;
      }
      if (kind === 'storage') {
        if (!mainWindow || mainWindow.isDestroyed()) throw new Error('main window unavailable');
        const key = String(step.key || '');
        if (!key) throw new Error(`step ${index}: storage key required`);
        await mainWindow.webContents.executeJavaScript(
          `localStorage.setItem(${JSON.stringify(key)}, ${JSON.stringify(String(step.value ?? ''))})`,
          true,
        );
        continue;
      }
      if (kind === 'resize') {
        if (!mainWindow || mainWindow.isDestroyed()) throw new Error('main window unavailable');
        const width = Math.max(360, Math.min(2400, Number(step.width) || 1200));
        const height = Math.max(500, Math.min(1800, Number(step.height) || 800));
        mainWindow.setMinimumSize(360, 500);
        mainWindow.setSize(Math.round(width), Math.round(height));
        continue;
      }
      if (kind === 'ask') {
        await postBackend('/api/ask', JSON.stringify({ text: String(step.text || '') }));
        continue;
      }
      if (kind === 'capture') {
        if (step.selector && !(await evidenceWaitForSelector(step.selector, step.timeout_ms))) {
          throw new Error(`step ${index}: capture selector timeout ${step.selector}`);
        }
        if (step.delay_ms) await new Promise((resolve) => setTimeout(resolve, Math.min(10000, Number(step.delay_ms) || 0)));
        const captured = await evidenceCaptureToFile(outputDir, step.name || `capture-${index + 1}`, step.target || 'main');
        entries.push({ name: step.name || `capture-${index + 1}`, note: String(step.note || ''), ...captured });
        continue;
      }
      throw new Error(`step ${index}: unsupported evidence plan kind ${kind}`);
    }
    const result = {
      ok: true,
      evidence_type: 'PACKAGED_BROWSERWINDOW_FILE_PLAN',
      packaged: app.isPackaged,
      version: app.getVersion(),
      backend_url: SERVER_URL,
      user_data: app.getPath('userData'),
      started_at: startedAt,
      completed_at: new Date().toISOString(),
      entries,
    };
    fs.writeFileSync(resultPath, JSON.stringify(result, null, 2));
    fs.writeFileSync(path.join(outputDir, 'manifest.json'), JSON.stringify(result, null, 2));
  } catch (error) {
    const result = {
      ok: false,
      evidence_type: 'PACKAGED_BROWSERWINDOW_FILE_PLAN',
      error: error?.message || String(error),
      packaged: app.isPackaged,
      version: app.getVersion(),
      started_at: startedAt,
      completed_at: new Date().toISOString(),
      entries,
    };
    fs.writeFileSync(resultPath, JSON.stringify(result, null, 2));
    throw error;
  } finally {
    if (plan.auto_quit !== false) setTimeout(() => { isQuitting = true; app.quit(); }, 250);
  }
}

async function evidenceWaitForSelector(selector, timeoutMs = 20000) {
  if (!mainWindow || mainWindow.isDestroyed()) throw new Error('main window unavailable');
  const deadline = Date.now() + Math.max(250, Math.min(120000, Number(timeoutMs) || 20000));
  const encoded = JSON.stringify(String(selector || ''));
  while (Date.now() < deadline) {
    const found = await mainWindow.webContents.executeJavaScript(
      `Boolean(document.querySelector(${encoded}))`,
      true,
    ).catch(() => false);
    if (found) return true;
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  return false;
}

function startRuntimeEvidenceBridge() {
  if (!runtimeEvidenceEnabled() || runtimeEvidenceServer) return;
  const requestedPort = Number(process.env.CHENGZHU_RUNTIME_EVIDENCE_PORT || 0);
  const token = String(process.env.CHENGZHU_RUNTIME_EVIDENCE_TOKEN || '');
  const outputDir = path.resolve(
    process.env.CHENGZHU_RUNTIME_EVIDENCE_DIR
      || path.join(app.getPath('userData'), 'runtime-evidence'),
  );
  fs.mkdirSync(outputDir, { recursive: true });

  runtimeEvidenceServer = http.createServer(async (req, res) => {
    try {
      if (token && req.headers['x-chengzhu-evidence-token'] !== token) {
        evidenceJson(res, 403, { ok: false, error: 'forbidden' });
        return;
      }
      const url = new URL(req.url || '/', 'http://127.0.0.1');
      if (req.method === 'GET' && url.pathname === '/status') {
        evidenceJson(res, 200, {
          ok: true,
          ready: Boolean(mainWindow && !mainWindow.isDestroyed()),
          backend_url: SERVER_URL,
          window_url: mainWindow && !mainWindow.isDestroyed() ? mainWindow.webContents.getURL() : '',
          user_data: app.getPath('userData'),
          output_dir: outputDir,
          packaged: app.isPackaged,
          version: app.getVersion(),
        });
        return;
      }
      if (!mainWindow || mainWindow.isDestroyed()) {
        evidenceJson(res, 409, { ok: false, error: 'main window unavailable' });
        return;
      }

      const body = req.method === 'POST' ? await evidenceReadJson(req) : {};
      if (req.method === 'POST' && url.pathname === '/navigate') {
        const hash = String(body.hash || '#/home');
        await mainWindow.webContents.executeJavaScript(
          `location.hash = ${JSON.stringify(hash)}`,
          true,
        );
        const found = body.selector
          ? await evidenceWaitForSelector(body.selector, body.timeout_ms)
          : true;
        evidenceJson(res, found ? 200 : 408, { ok: found, hash, selector: body.selector || null });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/reload') {
        mainWindow.webContents.reload();
        const found = body.selector
          ? await evidenceWaitForSelector(body.selector, body.timeout_ms)
          : true;
        evidenceJson(res, found ? 200 : 408, { ok: found });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/wait') {
        const found = await evidenceWaitForSelector(body.selector, body.timeout_ms);
        evidenceJson(res, found ? 200 : 408, { ok: found, selector: body.selector || null });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/storage') {
        const key = String(body.key || '');
        if (!key) throw new Error('storage key required');
        await mainWindow.webContents.executeJavaScript(
          `localStorage.setItem(${JSON.stringify(key)}, ${JSON.stringify(String(body.value ?? ''))})`,
          true,
        );
        evidenceJson(res, 200, { ok: true, key });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/resize') {
        const width = Math.max(360, Math.min(2400, Number(body.width) || 1200));
        const height = Math.max(500, Math.min(1800, Number(body.height) || 800));
        mainWindow.setMinimumSize(360, 500);
        mainWindow.setSize(Math.round(width), Math.round(height));
        evidenceJson(res, 200, { ok: true, width, height });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/key') {
        const modifiers = Array.isArray(body.modifiers) ? body.modifiers.map(String) : [];
        const keyCode = String(body.key || '');
        if (!keyCode) throw new Error('key required');
        mainWindow.webContents.sendInputEvent({ type: 'keyDown', keyCode, modifiers });
        mainWindow.webContents.sendInputEvent({ type: 'keyUp', keyCode, modifiers });
        evidenceJson(res, 200, { ok: true });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/click') {
        const selector = String(body.selector || '');
        if (!selector) throw new Error('selector required');
        const clicked = await mainWindow.webContents.executeJavaScript(
          `(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return false; el.click(); return true })()`,
          true,
        );
        evidenceJson(res, clicked ? 200 : 404, { ok: Boolean(clicked), selector });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/fill') {
        const selector = String(body.selector || '');
        if (!selector) throw new Error('selector required');
        const filled = await mainWindow.webContents.executeJavaScript(
          `(() => {
            const el = document.querySelector(${JSON.stringify(selector)});
            if (!el) return false;
            const setter = Object.getOwnPropertyDescriptor(el.__proto__, 'value')?.set;
            if (setter) setter.call(el, ${JSON.stringify(String(body.value ?? ''))});
            else el.value = ${JSON.stringify(String(body.value ?? ''))};
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
          })()`,
          true,
        );
        evidenceJson(res, filled ? 200 : 404, { ok: Boolean(filled), selector });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/capture') {
        const name = evidenceSafeName(body.name);
        const target = body.target === 'overlay' ? overlayWindow : mainWindow;
        if (!target || target.isDestroyed()) {
          evidenceJson(res, 409, { ok: false, error: `${body.target || 'main'} window unavailable` });
          return;
        }
        const image = await target.capturePage();
        const file = path.join(outputDir, name.endsWith('.png') ? name : `${name}.png`);
        fs.writeFileSync(file, image.toPNG());
        evidenceJson(res, 200, {
          ok: true,
          file,
          target: body.target === 'overlay' ? 'overlay' : 'main',
          width: image.getSize().width,
          height: image.getSize().height,
          url: target.webContents.getURL(),
        });
        return;
      }
      evidenceJson(res, 404, { ok: false, error: 'not found' });
    } catch (error) {
      evidenceJson(res, 500, { ok: false, error: error?.message || String(error) });
    }
  });

  runtimeEvidenceServer.listen(
    Number.isFinite(requestedPort) ? requestedPort : 0,
    '127.0.0.1',
    () => {
      const address = runtimeEvidenceServer.address();
      console.log(`[runtime-evidence] bridge ready on 127.0.0.1:${address && typeof address === 'object' ? address.port : requestedPort}`);
    },
  );
}

const OVERLAY_PRESET = { width: 480, height: 320, minWidth: 300, minHeight: 100, resizable: true };

const REGION_OVERLAY_HTML = `<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;overflow:hidden;cursor:crosshair;user-select:none;-webkit-user-select:none}
body{background:transparent}
#dim{position:fixed;inset:0;background:rgba(0,0,0,0.35);z-index:1;transition:opacity .12s ease}
#tip{position:fixed;left:50%;top:24px;transform:translateX(-50%);background:rgba(10,10,10,0.86);color:#fff;font:13px/1.5 system-ui,sans-serif;padding:8px 14px;border-radius:8px;pointer-events:none;z-index:5;white-space:nowrap}
#sel{position:fixed;border:1.5px solid #3b82f6;background:rgba(59,130,246,0.12);display:none;z-index:2;box-shadow:0 0 0 100vmax rgba(0,0,0,0.28)}
#size{position:fixed;background:rgba(10,10,10,0.82);color:#93c5fd;font:11px/1.4 monospace;padding:2px 6px;border-radius:4px;display:none;z-index:6;pointer-events:none}
#hx,#vx{position:fixed;pointer-events:none;z-index:3;display:none}
#hx{left:0;right:0;height:0;border-top:1px dashed rgba(255,255,255,0.55)}
#vx{top:0;bottom:0;width:0;border-left:1px dashed rgba(255,255,255,0.55)}
</style></head><body>
<div id="dim"></div>
<div id="tip">按住左键拖选截图区域，松开即提交；按 Esc 取消</div>
<div id="sel"></div><div id="size"></div>
<div id="hx"></div><div id="vx"></div>
<script>
const sel=document.getElementById('sel'),size=document.getElementById('size'),tip=document.getElementById('tip'),dim=document.getElementById('dim'),hx=document.getElementById('hx'),vx=document.getElementById('vx');
let sx=0,sy=0,drag=false;
window.addEventListener('mousedown',(e)=>{drag=true;sx=e.clientX;sy=e.clientY;sel.style.display='block';tip.style.display='none';dim.style.opacity='0.10';hx.style.display='block';vx.style.display='block';});
window.addEventListener('mousemove',(e)=>{if(!drag){hx.style.top=e.clientY+'px';vx.style.left=e.clientX+'px';return;}const x=Math.min(sx,e.clientX),y=Math.min(sy,e.clientY);const w=Math.abs(e.clientX-sx),h=Math.abs(e.clientY-sy);sel.style.left=x+'px';sel.style.top=y+'px';sel.style.width=w+'px';sel.style.height=h+'px';size.style.display='block';size.textContent=w+' x '+h;size.style.left=(x+8)+'px';size.style.top=(y+8)+'px';hx.style.top=e.clientY+'px';vx.style.left=e.clientX+'px';});
window.addEventListener('mouseup',(e)=>{if(!drag)return;drag=false;const x=Math.min(sx,e.clientX),y=Math.min(sy,e.clientY);const w=Math.abs(e.clientX-sx),h=Math.abs(e.clientY-sy);if(w<12||h<12){window.regionCapture&&window.regionCapture.cancel();return;}window.regionCapture&&window.regionCapture.done({left:x,top:y,width:w,height:h});});
window.addEventListener('keydown',(e)=>{if(e.key==='Escape'){window.regionCapture&&window.regionCapture.cancel();}});
</script></body></html>`;

const PROMPT_OVERLAY_MIN_SIZE = { width: 180, height: 72 };
const PROMPT_OVERLAY_MAX_SIZE = { heightRatio: 0.48 };
const FOCUS_OVERLAY_MARGIN = 14;

let _frontReassertTimer = null;
const FRONT_REASSERT_LEVEL = 1;
const FOCUS_OVERLAY_SHORTCUT_ACTIONS = new Set(['focusPrevTab', 'focusNextTab']);
const VISIBLE_OVERLAY_SHORTCUT_ACTIONS = new Set(['cancelAnswer', 'overlayPrevQuestion', 'overlayNextQuestion']);
const FRONT_REASSERT_DURATION = 5000;
const FRONT_REASSERT_INTERVAL = 500;

function applyTopMost(win) {
  if (!win || win.isDestroyed()) return;
  win.setAlwaysOnTop(true, 'screen-saver', FRONT_REASSERT_LEVEL);
  sharePrivacy.applyToWindow(win, sharePrivacyState.mode);
  win.moveTop();
}

function keepWindowInFront(win) {
  if (_frontReassertTimer) { clearInterval(_frontReassertTimer); _frontReassertTimer = null; }
  if (!win || win.isDestroyed()) return;
  const start = Date.now();
  applyTopMost(win);
  _frontReassertTimer = setInterval(() => {
    if (!win || win.isDestroyed() || Date.now() - start > FRONT_REASSERT_DURATION) {
      clearInterval(_frontReassertTimer);
      _frontReassertTimer = null;
      return;
    }
    applyTopMost(win);
  }, FRONT_REASSERT_INTERVAL);
}

function getOverlayStateFilePath() {
  return path.join(app.getPath('userData'), 'overlay-window.json');
}

function loadOverlayWindowState() {
  try {
    const raw = fs.readFileSync(getOverlayStateFilePath(), 'utf8');
    const data = JSON.parse(raw);
    if (data && typeof data === 'object') return data;
  } catch {
    /* ignore */
  }
  return { positions: {} };
}

function saveOverlayWindowState(data) {
  try {
    fs.writeFileSync(getOverlayStateFilePath(), JSON.stringify(data, null, 2), 'utf8');
  } catch (error) {
    console.warn('saveOverlayWindowState failed:', error);
  }
}

function getStoredOverlayPosition() {
  const saved = loadOverlayWindowState();
  const pos = saved?.position;
  if (!pos || typeof pos.x !== 'number' || typeof pos.y !== 'number') return null;
  const displays = screen.getAllDisplays();
  const fitsSomeDisplay = displays.some((display) => {
    const area = display.workArea;
    return (
      pos.x >= area.x - 40
      && pos.x <= area.x + area.width - 80
      && pos.y >= area.y - 40
      && pos.y <= area.y + area.height - 60
    );
  });
  if (fitsSomeDisplay) return { x: pos.x, y: pos.y };
  const primary = screen.getPrimaryDisplay().workArea;
  return {
    x: primary.x + Math.max(16, Math.round((primary.width - OVERLAY_PRESET.width) / 2)),
    y: primary.y + Math.max(16, Math.round((primary.height - OVERLAY_PRESET.height) * 0.18)),
  };
}

function getDefaultOverlayBounds() {
  const primary = screen.getPrimaryDisplay().workArea;
  return {
    x: primary.x + Math.max(16, Math.round((primary.width - OVERLAY_PRESET.width) / 2)),
    y: primary.y + Math.max(16, Math.round((primary.height - OVERLAY_PRESET.height) * 0.18)),
    width: OVERLAY_PRESET.width,
    height: OVERLAY_PRESET.height,
  };
}

function getFocusOverlayBounds() {
  const canUseOverlayBounds = overlayWindow
    && !overlayWindow.isDestroyed()
    && (typeof overlayWindow.isVisible !== 'function' || overlayWindow.isVisible());
  const point = canUseOverlayBounds
    ? {
        x: overlayWindow.getBounds().x + Math.round(overlayWindow.getBounds().width / 2),
        y: overlayWindow.getBounds().y + Math.round(overlayWindow.getBounds().height / 2),
      }
    : screen.getCursorScreenPoint();
  const display = screen.getDisplayNearestPoint(point);
  const area = display.workArea;
  const margin = FOCUS_OVERLAY_MARGIN;
  const widthPct = Math.max(50, Math.min(100, Number(lastOverlayState?.focusWidthPct) || 96));
  const heightPct = Math.max(35, Math.min(100, Number(lastOverlayState?.focusHeightPct) || 90));
  const width = Math.round((area.width - margin * 2) * (widthPct / 100));
  const height = Math.round((area.height - margin * 2) * (heightPct / 100));
  return {
    x: area.x + margin + Math.max(0, Math.round(((area.width - margin * 2) - width) / 2)),
    y: area.y + margin + Math.max(0, Math.round(((area.height - margin * 2) - height) / 2)),
    width: Math.max(OVERLAY_PRESET.minWidth, width),
    height: Math.max(OVERLAY_PRESET.minHeight, height),
  };
}

function getNormalOverlayBounds(mode) {
  const storedPos = getStoredOverlayPosition();
  const saved = loadOverlayWindowState();
  const storedSize = saved?.position;
  const minOverlayWidth = OVERLAY_PRESET.minWidth || OVERLAY_PRESET.width;
  const minOverlayHeight = OVERLAY_PRESET.minHeight || OVERLAY_PRESET.height;
  // prompt 模式宽度由内容自适应驱动 (受 promptMaxWidth 约束), 旧物理 position.w 无意义;
  // 直接用 promptMaxWidth 作初始宽, 避免重开时先显示旧值再被前端收窄/撑开。
  let width;
  let height;
  if (mode === 'prompt') {
    width = getPromptOverlayInitialWidth(lastOverlayState?.promptMaxWidth);
    height = Math.max((storedSize?.h > 0) ? storedSize.h : OVERLAY_PRESET.height, minOverlayHeight);
  } else {
    width = Math.max((storedSize?.w > 0) ? storedSize.w : OVERLAY_PRESET.width, minOverlayWidth);
    height = Math.max((storedSize?.h > 0) ? storedSize.h : OVERLAY_PRESET.height, minOverlayHeight);
  }
  return {
    ...(storedPos ? storedPos : getDefaultOverlayBounds()),
    width,
    height,
  };
}

function applyOverlayModeBounds() {
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  const mode = lastOverlayState?.mode || (lastOverlayState?.showBg === false ? 'prompt' : 'glass');
  overlayWindow.setMinimumSize(
    mode === 'prompt' ? PROMPT_OVERLAY_MIN_SIZE.width : OVERLAY_PRESET.minWidth,
    mode === 'prompt' ? PROMPT_OVERLAY_MIN_SIZE.height : OVERLAY_PRESET.minHeight,
  );
  const bounds = mode === 'focus' ? getFocusOverlayBounds() : getNormalOverlayBounds(mode);
  overlayWindow.setBounds(bounds, false);
}

function persistOverlayPosition(force = false) {
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  if (lastOverlayState?.mode === 'focus') return;
  // fuse 屏蔽窗口 resize/moved 事件在程序化 setBounds 后 500ms 内的频繁写盘;
  // force=true 用于程序化设尺寸后的显式落盘 (来自 resize-overlay-window IPC), 绕过 fuse。
  if (!force && Date.now() < overlayAutoResizeUntil) return;
  const bounds = overlayWindow.getBounds();
  const saved = loadOverlayWindowState();
  saved.position = { x: bounds.x, y: bounds.y, w: bounds.width, h: bounds.height };
  saveOverlayWindowState(saved);
}

function schedulePersistOverlayPosition(force = false) {
  if (overlayPositionSaveTimer) clearTimeout(overlayPositionSaveTimer);
  const scheduledForce = force;
  overlayPositionSaveTimer = setTimeout(() => {
    overlayPositionSaveTimer = null;
    persistOverlayPosition(scheduledForce);
  }, 180);
}

function createTrayIcon() {
  const size = 16;
  const canvas = nativeImage.createFromBuffer(
    Buffer.alloc(size * size * 4, 0),
    { width: size, height: size }
  );
  return canvas;
}

function waitForServer(timeout = 40000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      if (!pythonProcess && Date.now() - start > 1500) {
        return reject(new Error('Backend process exited before it was ready'));
      }
      // Only our own sidecar (matching nonce) counts as ready.
      const req = http.get(`${SERVER_URL}/api/instance`, { timeout: 1000 }, (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            if (res.statusCode === 200 && backendLauncher.isOwnInstance(JSON.parse(body), INSTANCE_NONCE)) return resolve();
          } catch { /* not ours */ }
          retry();
        });
      });
      req.on('error', retry);
      req.on('timeout', () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - start > timeout) return reject(new Error('Server start timeout'));
      setTimeout(check, 300);
    };
    check();
  });
}

function evidenceExternalBackendUrl() {
  if (!runtimeEvidenceEnabled()) return '';
  const raw = String(process.env.CHENGZHU_EVIDENCE_BACKEND_URL || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw);
    if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) return '';
    return url.origin;
  } catch {
    return '';
  }
}

function waitForOwnedExternalServer(timeout = 90000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const req = http.get(`${SERVER_URL}/api/instance`, { timeout: 1000 }, (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            if (res.statusCode === 200 && backendLauncher.isOwnInstance(JSON.parse(body), INSTANCE_NONCE)) return resolve();
          } catch { /* retry below */ }
          retry();
        });
      });
      req.on('error', retry);
      req.on('timeout', () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - start > timeout) return reject(new Error('Evidence backend start timeout'));
      setTimeout(check, 300);
    };
    check();
  });
}

function startPythonBackend() {
  const userDataDir = app.getPath('userData');
  if (app.isPackaged) backendLauncher.ensureUserDataLayout(userDataDir);
  const plan = backendLauncher.resolveBackendCommand({
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    repoRoot: ROOT,
    port: PORT,
    userDataDir,
    nonce: INSTANCE_NONCE,
  });
  backendStderrTail = '';
  try {
    pythonProcess = spawn(plan.command, plan.args, {
      cwd: plan.cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: plan.env,
      windowsHide: true,
    });
  } catch (error) {
    backendStderrTail = String(error?.message || error);
    pythonProcess = null;
    return;
  }
  pythonProcess.on('error', (error) => {
    backendStderrTail += `\n${error?.code || ''} ${error?.message || error}`;
  });
  pythonProcess.stderr?.on('data', (chunk) => {
    backendStderrTail = (backendStderrTail + chunk.toString('utf8')).slice(-4000);
  });

  relayChildOutput(pythonProcess.stdout, process.stdout, '[py] ');
  relayChildOutput(pythonProcess.stderr, process.stderr, '[py] ');
  pythonProcess.on('close', (code) => {
    console.log(`[py] exited with code ${code}`);
    pythonProcess = null;
    if (!isQuitting) {
      const { dialog } = require('electron');
      dialog.showErrorBox(
        '成竹后端已退出',
        backendLauncher.describeStartupFailure({ code, stderrTail: backendStderrTail, port: PORT, packaged: app.isPackaged }),
      );
      app.quit();
    }
  });
}

// Pull the persisted Share Privacy default from the backend config.
function syncSharePrivacyFromConfig() {
  http.get(`${SERVER_URL}/api/config`, { timeout: 3000 }, (res) => {
    let body = '';
    res.setEncoding('utf8');
    res.on('data', (chunk) => { body += chunk; });
    res.on('end', () => {
      try {
        const cfg = JSON.parse(body);
        setSharePrivacyMode(cfg.share_privacy_mode);
      } catch { /* keep OFF */ }
    });
  }).on('error', () => { /* keep OFF */ });
}

function setSharePrivacyMode(mode) {
  sharePrivacyState.set(mode);
  sharePrivacy.applyToWindow(mainWindow, sharePrivacyState.mode);
  sharePrivacy.applyToWindow(overlayWindow, sharePrivacyState.mode);
  if (tray && !tray.isDestroyed?.()) {
    tray.setToolTip(`${APP_DISPLAY_NAME} · 共享隐私：${sharePrivacyState.protected ? '开（私有悬浮窗）' : '关'}`);
    try { createTrayMenu(); } catch { /* menu rebuild best effort */ }
  }
  return sharePrivacyState.mode;
}

function createWindow() {
  const isWindows = process.platform === 'win32';
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 500,
    title: APP_DISPLAY_NAME,
    frame: false,
    show: false,
    // Hosted Windows CI has no reliable interactive DWM desktop. Runtime
    // evidence renders through webPreferences.offscreen below; production
    // remains the normal visible window path.
    // R2: a normal installed app shows in the taskbar (no stealth default).
    skipTaskbar: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      offscreen: RUNTIME_EVIDENCE_MODE,
    },
  });

  sharePrivacy.applyToWindow(mainWindow, sharePrivacyState.mode);

  // 每次启动清除缓存，确保加载到最新的前端构建（避免设置里识别引擎等不更新）
  mainWindow.webContents.session.clearCache().then(() => {
    mainWindow.loadURL(SERVER_URL);
  });

  mainWindow.webContents.on('did-finish-load', () => {
    const t = JSON.stringify(APP_DISPLAY_NAME);
    mainWindow.webContents.executeJavaScript(`document.title = ${t}`).catch(() => {});
    mainWindow.setTitle(APP_DISPLAY_NAME);
  });

  mainWindow.once('ready-to-show', () => {
    if (!RUNTIME_EVIDENCE_MODE) mainWindow.show();
  });

  // Windows 下最小化 = 隐藏到托盘
  mainWindow.on('minimize', (e) => {
    if (process.platform === 'win32') {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  // 关闭按钮 = 真正退出
  mainWindow.on('close', () => {
    isQuitting = true;
  });
}

function createOverlayWindow() {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    return overlayWindow;
  }

  const initialMode = lastOverlayState?.mode || (lastOverlayState?.showBg === false ? 'prompt' : 'glass');
  const initialBounds = initialMode === 'focus' ? getFocusOverlayBounds() : getNormalOverlayBounds(initialMode);

  // 透明浮窗: 视觉上能看到桌面, 需要 transparent: true + alpha=0 背景.
  // 注意: setContentProtection 在 macOS 的透明窗口上只是 best effort,
  // 对部分截图路径 (尤其是 ScreenCaptureKit) 可能无效; 这是 OS 级限制.
  overlayWindow = new BrowserWindow({
    width: initialBounds.width,
    height: initialBounds.height,
    x: initialBounds.x,
    y: initialBounds.y,
    minWidth: OVERLAY_PRESET.minWidth,
    minHeight: OVERLAY_PRESET.minHeight,
    ...createOverlayChromeOptions(process.platform, OVERLAY_PRESET.resizable),
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    focusable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    hiddenInMissionControl: true,
    show: false,
    autoHideMenuBar: true,
    roundedCorners: true,
    title: `${APP_DISPLAY_NAME} Overlay`,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
      offscreen: RUNTIME_EVIDENCE_MODE,
    },
  });

  // Content protection 必须尽早调用 —— 等到 ready-to-show 时,
  // 窗口可能已经被 window server 登记过一次, 导致 NSWindowSharingNone 漏掉初始帧
  sharePrivacy.applyToWindow(overlayWindow, sharePrivacyState.mode);
  overlayWindow.setBackgroundColor('#00000000');
  overlayWindow.setAlwaysOnTop(true, 'screen-saver', FRONT_REASSERT_LEVEL);
  overlayWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true, skipTransformProcessType: true });
  if (process.platform === 'darwin') {
    // macOS: NSWindowCollectionBehaviorCanJoinAllSpaces + Transient
    // 让窗口不进入 Cmd+Tab, Mission Control, Exposé, 以及 CGWindowList
    try {
      overlayWindow.setHiddenInMissionControl(true);
    } catch { /* older electron */ }
  }

  overlayWindow._overlayReady = false;

  overlayWindow.once('ready-to-show', () => {
    if (!overlayWindow || overlayWindow.isDestroyed()) return;
    sharePrivacy.applyToWindow(overlayWindow, sharePrivacyState.mode);
    overlayWindow.setBackgroundColor('#00000000');
    overlayWindow.setFocusable(false);
    overlayWindow.setAlwaysOnTop(true, 'screen-saver', FRONT_REASSERT_LEVEL);
  });
  overlayWindow.loadURL(`${SERVER_URL}?overlay=1`);
  overlayWindow.webContents.on('did-finish-load', () => {
    if (!overlayWindow || overlayWindow.isDestroyed()) return;
    sharePrivacy.applyToWindow(overlayWindow, sharePrivacyState.mode);
    overlayWindow.setBackgroundColor('#00000000');
    overlayWindow.setFocusable(false);
    if (lastOverlayState) {
      overlayWindow.webContents.send('overlay-state', lastOverlayState);
    }
    setTimeout(() => {
      if (!overlayWindow || overlayWindow.isDestroyed()) return;
      overlayWindow._overlayReady = true;
      if (overlayWindow._pendingShow) {
        overlayWindow._pendingShow = false;
        showOverlayWindow();
      }
    }, process.platform === 'win32' ? 120 : 0);
  });
  overlayWindow.on('show', () => {
    if (!overlayWindow || overlayWindow.isDestroyed()) return;
    sharePrivacy.applyToWindow(overlayWindow, sharePrivacyState.mode);
    overlayWindow.setBackgroundColor('#00000000');
    overlayWindow.setFocusable(false);
  });

  overlayWindow.on('closed', () => {
    overlayWindow = null;
    _overlayDragging = false;
    if (_blurTimer) { clearTimeout(_blurTimer); _blurTimer = null; }
    if (_frontReassertTimer) { clearInterval(_frontReassertTimer); _frontReassertTimer = null; }
  });
  overlayWindow.on('moved', () => schedulePersistOverlayPosition());
  overlayWindow.on('resize', () => schedulePersistOverlayPosition());
  overlayWindow.on('focus', () => {
    if (_blurTimer) clearTimeout(_blurTimer);
    _blurTimer = setTimeout(() => {
      _blurTimer = null;
      if (!_overlayDragging && overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.blur();
      }
    }, 150);
  });

  return overlayWindow;
}

function sendOverlayState(payload) {
  lastOverlayState = payload;
  [mainWindow, overlayWindow].forEach((win) => {
    if (!win || win.isDestroyed()) return;
    win.webContents.send('overlay-state', payload);
  });
}

function sendShortcutsState() {
  [mainWindow, overlayWindow].forEach((win) => {
    if (!win || win.isDestroyed()) return;
    win.webContents.send('shortcuts-state', shortcuts);
  });
}

function applyOverlayLayout() {
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  const flags = overlayLayout.interactionFlags(overlayLayoutState.interaction);
  overlayWindow.setIgnoreMouseEvents(flags.ignoreMouseEvents, { forward: true });
  overlayWindow.setFocusable(flags.focusable);
  if (!overlayLayout.layoutOwnsBounds(overlayLayoutState)) return;
  const current = overlayWindow.getBounds();
  const display = screen.getDisplayMatching(current);
  const bounds = overlayLayout.computeOverlayBounds(display.workArea, overlayLayoutState, current, {
    widthPct: lastOverlayState?.focusWidthPct,
    heightPct: lastOverlayState?.focusHeightPct,
  });
  overlayAutoResizeUntil = Date.now() + 500;
  overlayWindow.setMinimumSize(Math.min(200, bounds.width), Math.min(40, bounds.height));
  overlayWindow.setBounds(bounds, false);
}

function showOverlayWindow() {
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  if (!overlayWindow._overlayReady) {
    overlayWindow._pendingShow = true;
    return;
  }
  applyOverlayModeBounds();
  overlayWindow.setFocusable(false);
  applyOverlayLayout();
  if (process.platform === 'darwin' || process.platform === 'win32') {
    overlayWindow.showInactive();
  } else {
    overlayWindow.show();
  }
  sharePrivacy.applyToWindow(overlayWindow, sharePrivacyState.mode);
  keepWindowInFront(overlayWindow);
}

function toggleWindow() {
  if (!mainWindow) return;
  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
}

function postBackend(pathname, body = '{}') {
  return new Promise((resolve, reject) => {
    const req = http.request(
      `${SERVER_URL}${pathname}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
      },
      (res) => {
        let raw = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => { raw += chunk; });
        res.on('end', () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            if (!raw) { resolve({ ok: true }); return; }
            try { resolve(JSON.parse(raw)); } catch { resolve({ ok: true }); }
            return;
          }
          reject(new Error(raw || res.statusMessage || `HTTP ${res.statusCode}`));
        });
      }
    );
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

function getBackend(pathname) {
  return new Promise((resolve, reject) => {
    const req = http.request(`${SERVER_URL}${pathname}`, { method: 'GET' }, (res) => {
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { raw += chunk; });
      res.on('end', () => {
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          if (!raw) { resolve({}); return; }
          try { resolve(JSON.parse(raw)); } catch { resolve({}); }
          return;
        }
        reject(new Error(raw || res.statusMessage || `HTTP ${res.statusCode}`));
      });
    });
    req.on('error', reject);
    req.end();
  });
}

async function getMultiScreenIdleMs() {
  try {
    const cfg = await getBackend('/api/config');
    const sec = Number(cfg?.multi_screen_capture_idle_sec ?? 10);
    return Math.max(1, Math.min(60, Number.isFinite(sec) ? sec : 10)) * 1000;
  } catch {
    return 10000;
  }
}

const multiServerScreenBatch = createMultiScreenBatch({
  submitImages: (images) => (
    postBackend('/api/ask-from-server-screens', JSON.stringify({ images }))
  ),
  onError: (error) => {
    console.error('flushMultiServerScreenBatch failed:', error);
  },
});

async function addMultiServerScreenShot() {
  try {
    const res = await postBackend('/api/capture-server-screen');
    if (!res?.image) throw new Error('capture response missing image');
    const idleMs = await getMultiScreenIdleMs();
    multiServerScreenBatch.add(res.image, idleMs);
  } catch (error) {
    console.error('addMultiServerScreenShot failed:', error);
  }
}

function createTrayMenu() {
  if (!tray) return;
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示窗口', click: () => { mainWindow?.show(); mainWindow?.focus(); } },
    { label: '隐藏到托盘', click: () => toggleWindow() },
    { type: 'separator' },
    {
      label: '窗口置顶',
      type: 'checkbox',
      checked: false,
      click: (menuItem) => {
        mainWindow?.setAlwaysOnTop(menuItem.checked, 'floating');
      },
    },
    {
      label: '共享隐私（私有悬浮窗）',
      type: 'checkbox',
      checked: sharePrivacyState.protected,
      toolTip: sharePrivacy.SHARE_PRIVACY_COPY,
      click: (menuItem) => {
        setSharePrivacyMode(menuItem.checked ? 'PRIVATE_OVERLAY' : 'OFF');
      },
    },
    { type: 'separator' },
    { label: '退出', click: () => { isQuitting = true; app.quit(); } },
  ]);

  tray.setContextMenu(contextMenu);
}

function createTray() {
  const iconPath = path.join(__dirname, 'icon.png');
  let icon;
  try {
    icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } catch {
    icon = createTrayIcon();
  }

  tray = new Tray(icon);
  tray.setToolTip(`${APP_DISPLAY_NAME} · 共享隐私：${sharePrivacyState.protected ? '开（私有悬浮窗）' : '关'}`);

  createTrayMenu();
  tray.on('click', () => { mainWindow?.show(); mainWindow?.focus(); });
  // Windows 双击托盘图标也能显示
  tray.on('double-click', () => { mainWindow?.show(); mainWindow?.focus(); });
}

function isFocusOverlayActive() {
  const mode = lastOverlayState?.mode || (lastOverlayState?.showBg === false ? 'prompt' : 'glass');
  return Boolean(lastOverlayState?.visible) && mode === 'focus';
}

function isOverlayShortcutActive(action) {
  if (FOCUS_OVERLAY_SHORTCUT_ACTIONS.has(action)) return isFocusOverlayActive();
  if (VISIBLE_OVERLAY_SHORTCUT_ACTIONS.has(action)) return Boolean(lastOverlayState?.visible);
  // Non-overlay shortcuts are intentionally global and should stay registered.
  return true;
}

function registerManagedShortcut(shortcut) {
  const callback = shortcutCallbacks[shortcut.action];
  if (!callback) {
    shortcut.status = ShortcutStatus.Available;
    return false;
  }
  if (globalShortcut.register(shortcut.key, callback)) {
    shortcut.status = ShortcutStatus.Registered;
    return true;
  }
  shortcut.status = ShortcutStatus.Failed;
  return false;
}

function registerShortcuts() {
  shortcuts = loadShortcutConfig(app);
  Object.values(shortcuts).forEach((shortcut) => {
    if (!isOverlayShortcutActive(shortcut.action)) {
      shortcut.status = ShortcutStatus.Available;
      return;
    }
    registerManagedShortcut(shortcut);
  });
  syncFocusOverlayShortcuts();
}

function unregisterShortcut(action) {
  const shortcut = shortcuts[action];
  if (!shortcut) return;
  globalShortcut.unregister(shortcut.key);
  shortcut.status = ShortcutStatus.Available;
}

function unregisterAllManagedShortcuts() {
  Object.keys(shortcuts).forEach((action) => unregisterShortcut(action));
}

function syncFocusOverlayShortcuts() {
  for (const action of FOCUS_OVERLAY_SHORTCUT_ACTIONS) {
    const shortcut = shortcuts[action];
    if (!shortcut) continue;
    if (isOverlayShortcutActive(action)) {
      if (shortcut.status !== ShortcutStatus.Registered) registerManagedShortcut(shortcut);
    } else if (shortcut.status === ShortcutStatus.Registered || shortcut.status === ShortcutStatus.Failed) {
      unregisterShortcut(action);
    }
  }
  for (const action of VISIBLE_OVERLAY_SHORTCUT_ACTIONS) {
    const shortcut = shortcuts[action];
    if (!shortcut) continue;
    if (isOverlayShortcutActive(action)) {
      if (shortcut.status !== ShortcutStatus.Registered) registerManagedShortcut(shortcut);
    } else if (shortcut.status === ShortcutStatus.Registered || shortcut.status === ShortcutStatus.Failed) {
      unregisterShortcut(action);
    }
  }
  sendShortcutsState();
}

function registerShortcutSet(nextShortcuts) {
  const validation = validateShortcutMap(nextShortcuts);
  if (!validation.ok) {
    return { ok: false, error: validation.error, shortcuts };
  }

  const prevShortcuts = shortcuts;
  unregisterAllManagedShortcuts();

  const nextState = JSON.parse(JSON.stringify(nextShortcuts));
  let failedKey = null;
  for (const shortcut of Object.values(nextState)) {
    if (!isOverlayShortcutActive(shortcut.action)) {
      shortcut.status = ShortcutStatus.Available;
      continue;
    }
    const callback = shortcutCallbacks[shortcut.action];
    if (!callback) continue;
    if (globalShortcut.register(shortcut.key, callback)) {
      shortcut.status = ShortcutStatus.Registered;
    } else {
      shortcut.status = ShortcutStatus.Failed;
      failedKey = shortcut.key;
      break;
    }
  }

  if (failedKey) {
    Object.values(nextState).forEach((shortcut) => globalShortcut.unregister(shortcut.key));
    shortcuts = prevShortcuts;
    Object.values(shortcuts).forEach((shortcut) => {
      if (!isOverlayShortcutActive(shortcut.action)) {
        shortcut.status = ShortcutStatus.Available;
        return;
      }
      const callback = shortcutCallbacks[shortcut.action];
      if (!callback) return;
      globalShortcut.register(shortcut.key, callback);
      shortcut.status = ShortcutStatus.Registered;
    });
    return { ok: false, error: `快捷键注册失败：${failedKey}`, shortcuts };
  }

  shortcuts = nextState;
  syncFocusOverlayShortcuts();
  saveShortcutConfig(app, shortcuts);
  return { ok: true, shortcuts };
}

const shortcutCallbacks = {
  hideOrShowWindow: () => toggleWindow(),
  hardClearSession: async () => {
    try {
      await postBackend('/api/clear');
    } catch (error) {
      console.error('hardClearSession failed:', error);
    }
  },
  askFromServerScreen: async () => {
    try {
      await postBackend('/api/ask-from-server-screen');
    } catch (error) {
      console.error('askFromServerScreen failed:', error);
    }
  },
  cancelAnswer: async () => {
    try {
      await postBackend('/api/ask/cancel');
    } catch (error) {
      console.error('cancelAnswer failed:', error);
    }
  },
  addMultiServerScreenShot,
  toggleInterviewOverlay: () => {
    const nextVisible = !Boolean(lastOverlayState.visible);
    const nextState = {
      ...lastOverlayState,
      initialized: true,
      enabled: nextVisible || lastOverlayState.enabled,
      visible: nextVisible,
    };
    sendOverlayState(nextState);
    syncFocusOverlayShortcuts();

    if (nextVisible) {
      if (mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()) {
        mainWindow._hiddenByOverlay = true;
        mainWindow.hide();
      }
      createOverlayWindow();
      showOverlayWindow();
    } else {
      // 快捷键仅切换 overlay 可见性, 主窗口保持原状 (用户可通过 Cmd+B 或托盘唤回).
      // 只有 ControlBar 的 "结束面试" 按钮会走 sync-overlay-window IPC 恢复主窗口.
      if (overlayWindow && !overlayWindow.isDestroyed()) overlayWindow.hide();
    }
  },
  moveOverlayToMouse: () => {
    if (!overlayWindow || overlayWindow.isDestroyed()) return;
    const cursor = screen.getCursorScreenPoint();
    const offsetX = 20;
    const offsetY = 20;
    const nextX = Math.round(cursor.x - offsetX);
    const nextY = Math.round(cursor.y - offsetY);
    overlayWindow.setPosition(nextX, nextY);
    schedulePersistOverlayPosition();
  },
  focusPrevTab: () => sendFocusTabCommand('prev'),
  focusNextTab: () => sendFocusTabCommand('next'),
  overlayPrevQuestion: () => sendOverlayQuestionCommand('prev'),
  overlayNextQuestion: () => sendOverlayQuestionCommand('next'),
};

function sendFocusTabCommand(direction) {
  if (!isFocusOverlayActive()) return;
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  overlayWindow.webContents.send('focus-tab-command', direction);
}

function sendOverlayQuestionCommand(direction) {
  if (!lastOverlayState?.visible) return;
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  overlayWindow.webContents.send('overlay-question-command', direction);
}

ipcMain.handle('hide-window', () => mainWindow?.hide());
ipcMain.handle('minimize-window', () => mainWindow?.minimize());
ipcMain.handle('quit-app', () => { isQuitting = true; app.quit(); });
ipcMain.handle('show-window', () => { mainWindow?.show(); mainWindow?.focus(); });
ipcMain.handle('get-shortcuts', () => shortcuts);
ipcMain.handle('update-shortcuts', (_event, updates) => {
  const next = JSON.parse(JSON.stringify(shortcuts));
  for (const update of updates || []) {
    if (!update || typeof update.action !== 'string' || typeof update.key !== 'string') continue;
    if (!next[update.action]) continue;
    next[update.action].key = update.key;
  }
  const result = registerShortcutSet(next);
  if (result.ok) sendShortcutsState();
  return result;
});
ipcMain.handle('reset-shortcuts', () => {
  try { fs.unlinkSync(path.join(app.getPath('userData'), 'shortcuts.json')); } catch {}
  const defaults = createShortcutState();
  const result = registerShortcutSet(defaults);
  if (result.ok) sendShortcutsState();
  return result;
});
ipcMain.handle('toggle-always-on-top', () => {
  if (!mainWindow) return false;
  const next = !mainWindow.isAlwaysOnTop();
  mainWindow.setAlwaysOnTop(next, 'floating');
  return next;
});
ipcMain.handle('toggle-content-protection', () => {
  const next = sharePrivacyState.protected ? 'OFF' : 'PRIVATE_OVERLAY';
  return sharePrivacy.isProtected(setSharePrivacyMode(next));
});
ipcMain.handle('set-share-privacy', (_event, mode) => setSharePrivacyMode(mode));
ipcMain.handle('get-share-privacy', () => ({
  mode: sharePrivacyState.mode,
  protected: sharePrivacyState.protected,
  note: sharePrivacy.SHARE_PRIVACY_COPY,
}));
ipcMain.handle('get-window-state', () => ({
  alwaysOnTop: mainWindow?.isAlwaysOnTop() ?? false,
  contentProtection: sharePrivacyState.protected,
  visible: mainWindow?.isVisible() ?? false,
}));
ipcMain.handle('sync-overlay-window', (_event, payload = {}) => {
  const style = {};
  if ('opacity' in payload) {
    const opacity = Number(payload.opacity);
    if (Number.isFinite(opacity)) style.opacity = Math.max(0, Math.min(1, opacity));
  }
  if ('fontSize' in payload) {
    const fontSize = Number(payload.fontSize);
    if (Number.isFinite(fontSize)) style.fontSize = Math.max(10, Math.min(48, Math.round(fontSize)));
  }
  if ('fontColor' in payload && typeof payload.fontColor === 'string' && /^#[0-9a-fA-F]{6}$/.test(payload.fontColor)) {
    style.fontColor = payload.fontColor;
  }
  if ('showBg' in payload && typeof payload.showBg === 'boolean') {
    style.showBg = payload.showBg;
  }
  if ('mode' in payload && ['glass', 'prompt', 'focus'].includes(payload.mode)) {
    style.mode = payload.mode;
    style.showBg = payload.mode !== 'prompt';
  } else if ('showBg' in style && !('mode' in payload)) {
    style.mode = style.showBg ? 'glass' : 'prompt';
  }
  if ('focusWidthPct' in payload) {
    const focusWidthPct = Number(payload.focusWidthPct);
    if (Number.isFinite(focusWidthPct)) style.focusWidthPct = Math.max(50, Math.min(100, Math.round(focusWidthPct)));
  }
  if ('focusHeightPct' in payload) {
    const focusHeightPct = Number(payload.focusHeightPct);
    if (Number.isFinite(focusHeightPct)) style.focusHeightPct = Math.max(35, Math.min(100, Math.round(focusHeightPct)));
  }
  if ('promptMaxWidth' in payload) {
    const promptMaxWidth = Number(payload.promptMaxWidth);
    if (Number.isFinite(promptMaxWidth)) style.promptMaxWidth = Math.max(200, Math.min(1500, Math.round(promptMaxWidth)));
  }
  if ('promptAutoFollow' in payload && typeof payload.promptAutoFollow === 'boolean') {
    style.promptAutoFollow = payload.promptAutoFollow;
  }
  if ('maxLines' in payload) {
    const maxLines = Number(payload.maxLines);
    if (Number.isFinite(maxLines)) style.maxLines = Math.max(0, Math.min(50, Math.round(maxLines)));
  }

  const nextEnabled = typeof payload.enabled === 'boolean' ? payload.enabled : Boolean(lastOverlayState.enabled);
  const nextVisible = typeof payload.visible === 'boolean' ? payload.visible : Boolean(lastOverlayState.visible);

  const state = { ...lastOverlayState, ...style, enabled: nextEnabled, visible: nextVisible };
  state.initialized = true;
  const visibleChanged = Boolean(lastOverlayState.visible) !== state.visible;

  lastOverlayState = state;
  sendOverlayState(state);
  syncFocusOverlayShortcuts();

  if (visibleChanged) {
    if (state.visible) {
      if (mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()) {
        mainWindow._hiddenByOverlay = true;
        mainWindow.hide();
      }
    } else {
      if (mainWindow && !mainWindow.isDestroyed() && mainWindow._hiddenByOverlay) {
        mainWindow._hiddenByOverlay = false;
        mainWindow.show();
        mainWindow.focus();
      }
    }
  }

  if (!state.visible) {
    if (overlayWindow && !overlayWindow.isDestroyed()) overlayWindow.hide();
    return { ok: true, visible: false };
  }

  if (!overlayWindow || overlayWindow.isDestroyed()) {
    createOverlayWindow();
  }

  showOverlayWindow();
  return { ok: true, visible: true };
});
ipcMain.handle('get-overlay-state', () => lastOverlayState);
// v1.3 Overlay 3.0: Dock × Interaction × Size, requested by the overlay renderer
// (it knows when it is idle → COMPACT or showing a cue → STANDARD/FOCUS).
ipcMain.handle('set-overlay-layout', (_event, payload = {}) => {
  overlayLayoutState = overlayLayout.normalizeLayout({ ...overlayLayoutState, ...payload });
  applyOverlayLayout();
  return { ok: true, layout: overlayLayoutState };
});
ipcMain.handle('resize-overlay-window', (_event, payload = {}) => {
  if (!overlayWindow || overlayWindow.isDestroyed()) return { ok: false };
  const mode = lastOverlayState?.mode || (lastOverlayState?.showBg === false ? 'prompt' : 'glass');
  if (mode !== 'prompt') return { ok: true, skipped: true };

  const bounds = overlayWindow.getBounds();
  const center = {
    x: bounds.x + Math.round(bounds.width / 2),
    y: bounds.y + Math.round(bounds.height / 2),
  };
  const area = screen.getDisplayNearestPoint(center).workArea;
  const nextWidth = Number(payload.width);
  const nextHeight = Number(payload.height);
  const promptMaxWidth = Math.max(200, Math.min(1500, Number(lastOverlayState?.promptMaxWidth) || 900));
  const width = Number.isFinite(nextWidth)
    ? Math.max(PROMPT_OVERLAY_MIN_SIZE.width, Math.min(promptMaxWidth, area.width - 16, Math.round(nextWidth)))
    : bounds.width;
  const height = Number.isFinite(nextHeight)
    ? Math.max(PROMPT_OVERLAY_MIN_SIZE.height, Math.min(Math.round(area.height * PROMPT_OVERLAY_MAX_SIZE.heightRatio), Math.round(nextHeight)))
    : bounds.height;
  const x = Math.max(area.x + 8, Math.min(bounds.x, area.x + area.width - width - 8));
  const y = Math.max(area.y + 8, Math.min(bounds.y, area.y + area.height - height - 8));

  overlayAutoResizeUntil = Date.now() + 500;
  overlayWindow.setBounds({ x, y, width, height }, false);
  // 程序化设的尺寸是 prompt 自适应的权威值, 显式落盘 (绕过 fuse), 使重开时生效。
  schedulePersistOverlayPosition(true);
  return { ok: true, width, height };
});
// M3: 添加 destroyOverlay 接口，支持显式销毁悬浮窗
ipcMain.handle('destroy-overlay', () => {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.destroy();
    overlayWindow = null;
  }
  return { ok: true };
});
ipcMain.handle('move-overlay-window', (_event, dx, dy) => {
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  const [x, y] = overlayWindow.getPosition();
  overlayWindow.setPosition(x + Math.round(dx), y + Math.round(dy));
});

// ── 框选截图：透明全屏遮罩，拖选矩形后回传物理像素坐标 ──
let regionOverlayWindow = null;

function startRegionCapture() {
  return new Promise((resolve) => {
    try {
      if (regionOverlayWindow && !regionOverlayWindow.isDestroyed()) {
        regionOverlayWindow.destroy();
        regionOverlayWindow = null;
      }
      const primary = screen.getPrimaryDisplay();
      const { x, y, width, height } = primary.bounds;
      const scale = primary.scaleFactor || 1;
      const overlay = new BrowserWindow({
        x, y, width, height,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        skipTaskbar: true,
        resizable: false,
        movable: false,
        minimizable: false,
        maximizable: false,
        fullscreenable: false,
        hasShadow: false,
        enableLargerThanScreen: true,
        webPreferences: {
          nodeIntegration: false,
          contextIsolation: true,
          preload: path.join(__dirname, 'regionPreload.js'),
        },
      });
      regionOverlayWindow = overlay;
      overlay.setAlwaysOnTop(true, 'screen-saver');
      let settled = false;
      const finish = (rect) => {
        if (settled) return;
        settled = true;
        if (regionOverlayWindow && !regionOverlayWindow.isDestroyed()) {
          regionOverlayWindow.destroy();
        }
        regionOverlayWindow = null;
        const physical = rect && rect.width > 0 && rect.height > 0
          ? {
              left: Math.round(rect.left * scale),
              top: Math.round(rect.top * scale),
              width: Math.round(rect.width * scale),
              height: Math.round(rect.height * scale),
            }
          : null;
        resolve(physical);
      };
      ipcMain.removeAllListeners('region-capture-done');
      ipcMain.removeAllListeners('region-capture-cancel');
      ipcMain.once('region-capture-done', (_e, rect) => finish(rect || null));
      ipcMain.once('region-capture-cancel', () => finish(null));
      overlay.on('closed', () => {
        if (regionOverlayWindow === overlay) regionOverlayWindow = null;
        finish(null);
      });
      overlay.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(REGION_OVERLAY_HTML));
    } catch (err) {
      console.warn('[region] capture start failed:', err && err.message);
      resolve(null);
    }
  });
}

ipcMain.handle('capture-region-start', async () => {
  return await startRegionCapture();
});

ipcMain.on('overlay-drag-start', (event) => {
  _overlayDragging = true;
  if (_blurTimer) { clearTimeout(_blurTimer); _blurTimer = null; }
  event.returnValue = true;
});
ipcMain.on('overlay-drag-end', () => {
  _overlayDragging = false;
  if (_blurTimer) { clearTimeout(_blurTimer); _blurTimer = null; }
  if (overlayWindow && !overlayWindow.isDestroyed()) overlayWindow.blur();
});

function createAppMenu() {
  if (process.platform !== 'darwin') return;
  const template = [
    {
      label: app.name,
      submenu: [
        { role: 'about', label: `关于 ${app.name}` },
        { type: 'separator' },
        { label: '隐藏/显示窗口', click: () => toggleWindow() },
        { type: 'separator' },
        { role: 'hide', label: '隐藏应用' },
        { role: 'unhide', label: '显示应用' },
        { type: 'separator' },
        { label: '退出', accelerator: 'CommandOrControl+Q', click: () => { isQuitting = true; app.quit(); } },
      ],
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function requestAssistStop(timeoutMs = 12000) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      resolve();
    };
    const req = http.request(`${SERVER_URL}/api/assist/stop`, {
      method: 'POST',
      timeout: timeoutMs,
    }, (res) => {
      res.resume();
      res.on('end', finish);
      res.on('close', finish);
    });
    req.on('error', finish);
    req.on('timeout', () => {
      try { req.destroy(); } catch (_) { /* ignore */ }
      finish();
    });
    req.end();
  });
}

// 优雅停止后端：先主动请求 assist stop，让复盘归档和 SQLite 刷盘完成；
// 再发 SIGTERM，超时后兜底 SIGKILL。
let pythonStopPromise = null;
function gracefulStopPython(timeoutMs = 20000) {
  if (pythonStopPromise) return pythonStopPromise;
  const proc = pythonProcess;
  if (!proc) return Promise.resolve();
  pythonStopPromise = new Promise((resolve) => {
    let settled = false;
    const finish = () => { if (settled) return; settled = true; resolve(); };
    proc.once('exit', finish);
    const stopTimeoutMs = Math.max(1000, Math.min(15000, timeoutMs - 5000));
    requestAssistStop(stopTimeoutMs).then(() => {
      if (settled) return;
      try { proc.kill('SIGTERM'); } catch (err) { console.warn('[py] SIGTERM failed:', err.message); }
      setTimeout(() => {
        if (settled) return;
        try {
          if (!proc.killed) {
            console.warn('[py] graceful timeout, escalating to SIGKILL');
            proc.kill('SIGKILL');
          }
        } catch (err) {
          console.warn('[py] SIGKILL failed:', err.message);
        }
        finish();
      }, Math.max(1000, timeoutMs - stopTimeoutMs));
    });
  });
  return pythonStopPromise;
}

app.on('before-quit', (event) => {
  isQuitting = true;
  if (runtimeEvidenceServer) {
    try { runtimeEvidenceServer.close(); } catch { /* ignore */ }
    runtimeEvidenceServer = null;
  }
  if (!pythonProcess || pythonStopPromise) return;
  event.preventDefault();
  gracefulStopPython().then(() => {
    pythonProcess = null;
    app.quit();
  });
});

app.whenReady().then(async () => {
  try {
    app.setName(APP_DISPLAY_NAME);
  } catch {
    /* 个别平台/版本可能不支持 */
  }
  createAppMenu();

  // CI runtime-evidence mode may orchestrate the *packaged* sidecar explicitly
  // before launching the GUI. This avoids Windows runner deadlocks caused by a
  // GUI process recursively owning another long-lived child, while still
  // exercising the real Chengzhu.exe, real packaged backend and installed
  // frontend resources. Normal production launches never take this branch.
  const externalEvidenceBackend = evidenceExternalBackendUrl();
  if (externalEvidenceBackend) {
    SERVER_URL = externalEvidenceBackend;
    try {
      const parsed = new URL(SERVER_URL);
      PORT = Number(parsed.port || 80);
      console.log(`Using evidence sidecar on ${SERVER_URL} (packaged=${app.isPackaged})...`);
      await waitForOwnedExternalServer(app.isPackaged ? 90000 : 40000);
      console.log('Evidence sidecar ready, creating window...');
    } catch (err) {
      console.error('Failed to connect to evidence sidecar:', err.message);
      isQuitting = true;
      app.quit();
      return;
    }
  } else {
    const picked = await backendLauncher.pickPort(PREFERRED_PORT);
    if (picked == null) {
      const { dialog } = require('electron');
      dialog.showErrorBox('成竹无法启动', `端口 ${PREFERRED_PORT}–${PREFERRED_PORT + 19} 都被占用。请关闭占用端口的程序后重试。`);
      app.quit();
      return;
    }
    PORT = picked;
    SERVER_URL = `http://127.0.0.1:${PORT}`;
    console.log(`Starting backend on ${SERVER_URL} (packaged=${app.isPackaged})...`);
    startPythonBackend();

    try {
      // First launch of the packaged sidecar unpacks and imports more modules.
      await waitForServer(app.isPackaged ? 90000 : 40000);
      console.log('Backend ready, creating window...');
    } catch (err) {
      console.error('Failed to start backend:', err.message);
      const { dialog } = require('electron');
      dialog.showErrorBox(
        '成竹后端启动超时',
        backendLauncher.describeStartupFailure({ code: 'timeout', stderrTail: backendStderrTail, port: PORT, packaged: app.isPackaged }),
      );
      isQuitting = true;
      app.quit();
      return;
    }
  }

  syncSharePrivacyFromConfig();
  createWindow();
  if (runtimeEvidencePlanPath()) {
    // File-plan mode avoids a localhost listener entirely. Wait until the real
    // packaged renderer has completed its first navigation before sending DOM
    // queries. executeJavaScript() issued during the initial load can otherwise
    // remain pending indefinitely on hosted Windows runners, leaving neither a
    // success nor a failure result file.
    void waitForMainWindowLoad()
      .then(() => runRuntimeEvidencePlan())
      .catch((error) => {
        console.error('Runtime evidence plan failed:', error?.message || error);
        const resultPath = String(process.env.CHENGZHU_RUNTIME_EVIDENCE_RESULT || '').trim();
        if (resultPath) {
          try {
            fs.writeFileSync(path.resolve(resultPath), JSON.stringify({
              ok: false,
              evidence_type: 'PACKAGED_BROWSERWINDOW_FILE_PLAN',
              error: error?.message || String(error),
              packaged: app.isPackaged,
              version: app.getVersion(),
              completed_at: new Date().toISOString(),
              entries: [],
            }, null, 2));
          } catch (writeError) {
            console.error('Failed to write runtime evidence startup failure:', writeError?.message || writeError);
          }
        }
      });
  } else {
    startRuntimeEvidenceBridge();
  }
  createTray();
  registerShortcuts();

  setImmediate(() => {
    if (overlayWindow && !overlayWindow.isDestroyed()) return;
    try {
      createOverlayWindow();
    } catch (error) {
      console.warn('overlay preheat failed:', error?.message || error);
    }
  });
});

app.on('window-all-closed', () => {
  app.quit();
});

app.on('activate', () => {
  mainWindow?.show();
  mainWindow?.focus();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (overlayPositionSaveTimer) {
    clearTimeout(overlayPositionSaveTimer);
    overlayPositionSaveTimer = null;
  }
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.destroy();
    overlayWindow = null;
  }
  // 兜底:before-quit 通常已经 graceful 停过 pythonProcess,
  // 这里 fallback 防止异常路径泄漏子进程。
  if (pythonProcess) {
    try { pythonProcess.kill('SIGKILL'); } catch (_) { /* ignore */ }
    pythonProcess = null;
  }
});
