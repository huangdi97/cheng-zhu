// R2 Stage T: Share Privacy.
//
// Two modes only: OFF (default) and PRIVATE_OVERLAY. When on, Chengzhu asks
// the OS to exclude its main window and overlay from supported screen-share /
// recording paths via Electron's standard setContentProtection.
//
// This reduces accidental exposure of private material. It is NOT a security
// or "undetectable" guarantee: capture paths differ by OS and tool. No code
// here tries to defeat third-party security or proctoring mechanisms.

const MODES = Object.freeze(['OFF', 'PRIVATE_OVERLAY']);
const DEFAULT_MODE = 'OFF';

const SHARE_PRIVACY_COPY =
  '用于减少成竹中的私人资料意外出现在受支持的屏幕共享或录制路径中。' +
  '不同系统和捕获方式行为不同，这不是安全或“不可检测”保证。';

function normalizeMode(value) {
  const mode = String(value || '').trim().toUpperCase();
  return MODES.includes(mode) ? mode : DEFAULT_MODE;
}

function isProtected(mode) {
  return normalizeMode(mode) === 'PRIVATE_OVERLAY';
}

function createSharePrivacyState(initial = DEFAULT_MODE) {
  let mode = normalizeMode(initial);
  const listeners = new Set();
  return {
    get mode() {
      return mode;
    },
    get protected() {
      return isProtected(mode);
    },
    set(next) {
      const normalized = normalizeMode(next);
      if (normalized === mode) return mode;
      mode = normalized;
      for (const listener of listeners) listener(mode);
      return mode;
    },
    onChange(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

function applyToWindow(win, mode) {
  if (!win || (typeof win.isDestroyed === 'function' && win.isDestroyed())) return false;
  const on = isProtected(mode);
  win.setContentProtection(on);
  return on;
}

function readWindowProtection(win) {
  if (!win || (typeof win.isDestroyed === 'function' && win.isDestroyed())) return null;
  if (typeof win.isContentProtected !== 'function') return null;
  try {
    return Boolean(win.isContentProtected());
  } catch {
    return null;
  }
}

function runtimeSnapshot(mode, mainWindow, overlayWindow, platform = process.platform) {
  const normalized = normalizeMode(mode);
  const requested = isProtected(normalized);
  const mainProtected = readWindowProtection(mainWindow);
  const overlayProtected = readWindowProtection(overlayWindow);
  const liveFlags = [mainProtected, overlayProtected].filter((value) => value !== null);
  const anyProtected = liveFlags.some(Boolean);
  const allProtected = liveFlags.length > 0 && liveFlags.every(Boolean);
  const runtimeVerified = requested ? allProtected : !anyProtected;

  return {
    mode: normalized,
    protected: requested ? allProtected : anyProtected,
    runtime_verified: runtimeVerified,
    main_window_protected: mainProtected,
    overlay_window_protected: overlayProtected,
    platform,
    windows_capture_exclusion_may_lag: platform === 'win32' && requested,
    macos_screencapturekit_limitation: platform === 'darwin' && requested,
    note: SHARE_PRIVACY_COPY,
  };
}

module.exports = {
  MODES,
  DEFAULT_MODE,
  SHARE_PRIVACY_COPY,
  normalizeMode,
  isProtected,
  createSharePrivacyState,
  applyToWindow,
  readWindowProtection,
  runtimeSnapshot,
};
