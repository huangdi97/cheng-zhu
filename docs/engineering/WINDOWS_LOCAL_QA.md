# Windows local QA — packaged app, scaling and screenshots

This is the recipe that actually works on a Windows workstation when you need to
verify the packaged Electron build by hand. It exists because the obvious
approach silently fails three different ways.

## 1. Build a runnable package

```powershell
# sidecar (PyInstaller) + frontend, then the portable/installer target
python scripts/build_sidecar.py --clean
cd frontend; npm ci; npm run build; cd ..
cd desktop; npm ci; npm run dist:win      # -> ../dist/desktop
```

If `npm ci` in `desktop/` fails while downloading Electron (`@electron/get`), the
environment cannot reach the Electron binary mirror. You can still verify the app
by reusing an existing portable build: keep its Electron runtime, replace
`resources/backend` with the freshly built sidecar and `resources/frontend-dist`
with `frontend/dist`. `main.js`/`preload.js` are unchanged by UI work, so reusing
the original `app.asar` is faithful.

## 2. Launch it so it stays up

Three things break a headless/automated launch, in this order:

1. **Chromium sandbox.** In a session without a normal interactive desktop the
   app exits immediately with `-2147483645` (`0x80000003`), no window, no log.
   Add `--no-sandbox --disable-gpu`.
2. **`ELECTRON_RUN_AS_NODE`.** If the variable is *present at all* — even as an
   empty string — Electron behaves as plain Node and every Chromium switch is
   rejected (`bad option: --no-sandbox`). It must be **unset**, not blank.
3. **Unwritable user data.** Electron aborts before creating a window when
   `%APPDATA%` is not writable. Point everything at a writable directory:

```powershell
$env:CHENGZHU_USER_DATA_DIR = "E:\work\chengzhu-userdata"
$env:APPDATA               = "E:\work\appdata"
$env:LOCALAPPDATA          = "E:\work\localappdata"
$env:TEMP = $env:TMP       = "E:\work\tmp"
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue

Start-Process .\Chengzhu.exe -ArgumentList '--no-sandbox','--disable-gpu','--remote-debugging-port=9222'
```

## 3. There are two windows

The app opens the main window **and** a transparent overlay window at
`?overlay=1`. Driving the first CDP page gives you the empty overlay and looks
like a broken build. Always pick the main window:

```js
const page = context.pages().find((p) => !p.url().includes('overlay=1'))
```

## 4. Verify scaling

Pass `--force-device-scale-factor=1.25` (or `1.5`) and assert in the page:

```js
await page.evaluate(() => ({ dpr: devicePixelRatio, w: innerWidth, h: innerHeight }))
```

Expected: `dpr` equals the factor; `document.documentElement.scrollWidth` equals
`clientWidth` (no horizontal overflow); a dialog opened afterwards still fits
inside `innerWidth`/`innerHeight`.

## 5. Screenshot without a compositor

`page.screenshot()` over CDP works and is far more reliable than capturing the
desktop window rect:

```js
await page.screenshot({ path: 'first-run.png' })
```

If you must capture the real window (for DPI/font proof), use `GetWindowRect` +
`CopyFromScreen` on the window handle, and remember the captured bitmap is in
physical pixels while `innerWidth` is in CSS pixels.

## 6. What "verified" means

For a UI change, a local Windows pass is: launch → first run visible → goal
created → goal room → Preflight (blocked or ready, with the CTA visible) →
restart with the same profile and confirm the Goal persisted. Record
`devicePixelRatio`, window size, horizontal overflow and the dialog rectangle.
