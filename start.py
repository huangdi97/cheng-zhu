#!/usr/bin/env python3
"""Unified launcher for Cheng Zhu (成竹)."""

import argparse
import contextlib
import importlib
import io
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import warnings
from typing import Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT, "backend")
FRONTEND_DIR = os.path.join(ROOT, "frontend")
FRONTEND_DIST = os.path.join(FRONTEND_DIR, "dist")
DESKTOP_DIR = os.path.join(ROOT, "desktop")

REQUIREMENTS = os.path.join(BACKEND_DIR, "requirements.txt")
HIDE_CONSOLE_ENV = "IA_HIDE_CONSOLE"

# Keep distribution names separate from import names.  Several runtime
# packages deliberately use a different import path (for example
# ``python-multipart`` -> ``multipart`` and ``Pillow`` -> ``PIL``).  The old
# probe used ``pkg.replace("-", "_")`` and therefore missed these packages,
# allowing the server to start and fail later when a resume/KB route was used.
PYTHON_RUNTIME_IMPORTS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "websockets": "websockets",
    "python-multipart": "multipart",
    "openai": "openai",
    "requests": "requests",
    "websocket-client": "websocket",
    "aiohttp": "aiohttp",
    "pymupdf": "fitz",
    "sounddevice": "sounddevice",
    "numpy": "numpy",
    "faster-whisper": "faster_whisper",
    "pydantic": "pydantic",
    "qrcode": "qrcode",
    "mss": "mss",
    "Pillow": "PIL",
    "opencc-python-reimplemented": "opencc",
    "python-docx": "docx",
    "pypdf": "pypdf",
    # PyAV is pulled in by faster-whisper and is required by audio review
    # uploads.  Probe it explicitly so that route does not fail lazily.
    "av": "av",
}


def _runtime_imports() -> dict[str, str]:
    """Return imports required by the current platform."""
    imports = dict(PYTHON_RUNTIME_IMPORTS)
    # soundcard is a Windows-only direct dependency (WASAPI loopback).
    if platform.system() == "Windows":
        imports["soundcard"] = "soundcard"
    return imports


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------

def _set_utf8_console():
    """Windows: switch active code page to UTF-8 so Unicode chars render."""
    if platform.system() != "Windows":
        return
    try:
        subprocess.run(["chcp", "65001"], capture_output=True, shell=True)
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _hidden_process_kwargs() -> dict:
    if platform.system() != "Windows":
        return {}
    if os.environ.get(HIDE_CONSOLE_ENV, "").strip().lower() not in ("1", "true", "yes"):
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _print_access_info(port: int):
    """Print access URLs for both local and LAN."""
    ip = get_local_ip()
    print(f"  本机访问:   http://localhost:{port}")
    print(f"  局域网访问: http://{ip}:{port}")
    print()
    print(f"  手机扫码:   打开上方页面 → 右上角设置 → 底部二维码")
    print(f"  (手机和电脑需在同一 WiFi 下，音频在电脑端采集)")
    print()


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _pip_install(packages: list[str]):
    """Install packages using the *current* Python interpreter."""
    print(f"[...] 正在安装: {' '.join(packages)}")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", *packages]
    )
    return r.returncode == 0


def ensure_python_deps():
    """Make sure all backend Python dependencies are importable.

    Strategy:
    1. Try importing key packages. If they all work, do nothing.
    2. If any is missing, run: pip install -r backend/requirements.txt
       using *sys.executable* (same Python that is running this script).
    3. After installing, re-check; exit with helpful message if still missing.
    """
    def missing_runtime_imports() -> list[tuple[str, str, str]]:
        missing: list[tuple[str, str, str]] = []
        for distribution, module in _runtime_imports().items():
            try:
                # A few binary packages emit deprecation notices while being
                # imported.  They are not actionable startup failures, so do
                # not make normal launch noisy because of them.
                with (
                    warnings.catch_warnings(),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    warnings.simplefilter("ignore")
                    importlib.import_module(module)
            except Exception as exc:  # noqa: BLE001 - report any broken wheel
                missing.append((distribution, module, str(exc).strip()))
        return missing

    missing = missing_runtime_imports()

    if not missing:
        return  # all good

    print("[WARN] 当前 Python 环境缺少或无法导入运行依赖:")
    for distribution, module, reason in missing:
        suffix = f" ({reason})" if reason else ""
        print(f"       - {distribution} -> import {module}{suffix}")
    print(f"[...] 尝试自动安装 backend/requirements.txt ...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS, "--quiet"]
    )
    if r.returncode != 0:
        _print_dep_help()
        sys.exit(1)

    # Re-check
    still_missing = missing_runtime_imports()
    if still_missing:
        print("\n[ERROR] 安装后仍缺少或无法导入:")
        for distribution, module, reason in still_missing:
            suffix = f" ({reason})" if reason else ""
            print(f"       - {distribution} -> import {module}{suffix}")
        _print_dep_help()
        sys.exit(1)

    print("[OK] 依赖安装完成")


def _print_dep_help():
    print()
    print("  请手动安装后端依赖：")
    print(f"    {sys.executable} -m pip install -r backend/requirements.txt")
    print()
    print("  如果你在使用虚拟环境，请先激活它：")
    if platform.system() == "Windows":
        print("    venv\\Scripts\\activate       # CMD")
        print("    venv\\Scripts\\Activate.ps1   # PowerShell")
    else:
        print("    source venv/bin/activate")
    print()
    print("  也可以用 conda：")
    print("    conda activate <your-env>")


def _find_npx() -> Optional[str]:
    """Return path to npx, or None if not found."""
    return shutil.which("npx") or shutil.which("npx.cmd")


def _find_node() -> Optional[str]:
    return shutil.which("node") or shutil.which("node.exe")


def _find_npm() -> Optional[str]:
    return shutil.which("npm") or shutil.which("npm.cmd")


def _npm_install_command(npm: str, directory: str) -> list[str]:
    """Use the lockfile when bootstrapping a Node workspace."""
    lockfile = os.path.join(directory, "package-lock.json")
    return [npm, "ci"] if os.path.isfile(lockfile) else [npm, "install"]


def _print_node_help():
    system = platform.system()
    print()
    print("[ERROR] 未找到 Node.js / npm；桌面模式需要 Node.js 22.12+，前端构建至少需要 Node.js 18+。")
    print()
    if system == "Windows":
        print("  安装方法（选一种）：")
        print("  1. 官网下载安装包: https://nodejs.org （推荐 LTS 版）")
        print("  2. winget: winget install OpenJS.NodeJS.LTS")
        print("  3. 用 nvm-windows 管理多版本: https://github.com/coreybutler/nvm-windows")
    elif system == "Darwin":
        print("  安装方法（选一种）：")
        print("  1. Homebrew: brew install node")
        print("  2. 官网下载: https://nodejs.org")
        print("  3. nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/HEAD/install.sh | bash")
        print("         nvm install --lts")
    else:
        print("  安装方法（选一种）：")
        print("  1. 包管理器: sudo apt install nodejs npm  / sudo dnf install nodejs")
        print("  2. nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/HEAD/install.sh | bash")
        print("          nvm install --lts")
    print()
    print("  安装后重新打开终端再运行本脚本。")
    print()
    print("  如果只想用网络模式（浏览器访问），可以先跳过桌面模式：")
    print("    python start.py --mode network")


def ensure_node_version(mode: str, *, needs_build: bool) -> bool:
    """Fail early when the selected mode cannot run on the installed Node."""
    if not needs_build and mode != "desktop":
        return True

    node = _find_node()
    if node is None:
        _print_node_help()
        return False

    result = subprocess.run([node, "--version"], capture_output=True, text=True)
    raw = (result.stdout or result.stderr or "").strip().lstrip("v")
    try:
        parts = tuple(int(part) for part in raw.split(".")[:3])
        version = (parts + (0, 0, 0))[:3]
    except (TypeError, ValueError):
        print(f"[WARN] 无法解析 Node.js 版本: {raw or '<empty>'}，继续尝试启动。")
        return True

    required = (22, 12, 0) if mode == "desktop" else (18, 0, 0)
    if version < required:
        requirement = "22.12+" if mode == "desktop" else "18+"
        print(f"[ERROR] 当前 Node.js 为 {raw}，{mode} 模式需要 Node.js {requirement}。")
        print("        升级 Node.js 后再启动，避免 Electron/Vite 安装阶段才失败。")
        return False
    return True


# ---------------------------------------------------------------------------
# Frontend build
# ---------------------------------------------------------------------------

def build_frontend(force: bool = False):
    if not force and os.path.isdir(FRONTEND_DIST):
        print("[OK] 前端已构建，跳过 (用 --rebuild 强制重新构建)")
        return True

    npm = _find_npm()
    if npm is None:
        _print_node_help()
        return False

    if force and os.path.isdir(FRONTEND_DIST):
        print("[...] 清除旧构建产物...")
        shutil.rmtree(FRONTEND_DIST, ignore_errors=True)

    print("[...] 构建前端...")
    if not os.path.isdir(os.path.join(FRONTEND_DIR, "node_modules")):
        print("  安装前端 npm 依赖...")
        r = subprocess.run(
            _npm_install_command(npm, FRONTEND_DIR),
            cwd=FRONTEND_DIR,
            **_hidden_process_kwargs(),
        )
        if r.returncode != 0:
            print("[ERROR] 前端依赖安装失败")
            return False
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND_DIR, **_hidden_process_kwargs())
    if r.returncode != 0:
        print("[ERROR] 前端构建失败")
        return False
    print("[OK] 前端构建完成")
    return True


def ensure_electron():
    """Make sure desktop/node_modules/electron exists."""
    if os.path.isdir(os.path.join(DESKTOP_DIR, "node_modules", "electron")):
        return True

    npm = _find_npm()
    if npm is None:
        _print_node_help()
        return False

    print("[...] 安装 Electron 依赖...")
    r = subprocess.run(
        _npm_install_command(npm, DESKTOP_DIR),
        cwd=DESKTOP_DIR,
        **_hidden_process_kwargs(),
    )
    return r.returncode == 0


# ---------------------------------------------------------------------------
# Port management
# ---------------------------------------------------------------------------

def _port_in_use(port: int) -> bool:
    """Return True if something is listening on 127.0.0.1:port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def _is_our_server_running(port: int) -> bool:
    """Return True if the Cheng Zhu backend is already serving on port."""
    if not _port_in_use(port):
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/config", timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def _find_pid_on_port(port: int) -> Optional[str]:
    """返回监听指定端口的 PID；找不到返回 None。"""
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        return parts[-1]
        else:
            result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
            pids = result.stdout.strip().split()
            return pids[0] if pids else None
    except Exception:
        pass
    return None


def ensure_port_available(port: int) -> bool:
    """确认端口可启动。

    安全策略：
    - 端口空闲 -> 可用；
    - 已运行本应用后端(/api/config 有响应) -> 复用，不杀；
    - 被其他程序占用 -> 不自动强杀（避免误杀无关进程），提示用户处理或换端口。
    """
    if _is_our_server_running(port):
        return True
    if not _port_in_use(port):
        return True
    pid = _find_pid_on_port(port) or "?"
    print(f"[ERROR] 端口 {port} 被其他程序占用 (PID {pid})，且不是本应用后端。")
    print("        请关闭占用程序，或用 `--port <端口>` 换一个端口后重试。")
    print("        为安全起见，启动器不会自动强杀其他程序的进程。")
    return False


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def _idle_keepalive() -> None:
    """???????????????????????????????

    Electron ??????????????????????????
    ??????????? return????????????????
    """
    print("[INFO] ???????????????????????????????")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def start_server(host: str, port: int):
    if _is_our_server_running(port):
        print(f"[INFO] 后端已在端口 {port} 运行，复用中...")
        _idle_keepalive()
        return
    if not ensure_port_available(port):
        sys.exit(1)

    # Add backend to sys.path so all relative imports work correctly
    if BACKEND_DIR not in sys.path:
        sys.path.insert(0, BACKEND_DIR)
    os.chdir(BACKEND_DIR)

    # Try direct import first (fastest, works when deps are in current env)
    try:
        import uvicorn
        _access_log = os.environ.get("IA_ACCESS_LOG", "1").strip().lower() not in ("0", "false", "no")
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            log_level="info",
            reload=False,
            access_log=_access_log,
        )
        return
    except ImportError:
        pass

    # Fallback: subprocess using sys.executable (handles venv / conda / pyenv)
    print("[INFO] uvicorn 不在当前 Python 路径，尝试通过 subprocess 启动...")
    uv_args = [
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", host,
        "--port", str(port),
        "--log-level", "info",
    ]
    if os.environ.get("IA_ACCESS_LOG", "1").strip().lower() in ("0", "false", "no"):
        uv_args.append("--no-access-log")
    r = subprocess.run(uv_args, cwd=BACKEND_DIR, **_hidden_process_kwargs())
    sys.exit(r.returncode)


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

def run_desktop_mode(port: int):
    """Desktop mode: Electron window with content protection and global hotkeys."""
    npx = _find_npx()
    if npx is None:
        _print_node_help()
        sys.exit(1)

    if not ensure_electron():
        print("[ERROR] Electron 安装失败，请检查网络后重试。")
        print("  手动安装: cd desktop && npm install")
        print()
        print("  或者直接用无 Electron 模式启动:")
        print(f"    python start.py --mode network")
        sys.exit(1)

    # ??????????????????????????????/??????
    # ????????????zombie??????
    if _is_our_server_running(port):
        print(f"[INFO] 后端已在端口 {port} 运行，复用中...")
    elif not ensure_port_available(port):
        sys.exit(1)

    # Windows: 如果当前进程还有控制台窗口，先以无窗口模式重启自己
    # 这样用户双击启动时，初始的命令行窗口会消失，只留 Electron 窗口
    if platform.system() == "Windows" and os.environ.get(HIDE_CONSOLE_ENV) != "1":
        print("  Electron 桌面模式")
        print("  - 窗口隐私保护: 已开启（按系统能力尽量减少意外捕获）")
        print("  - 全局快捷键: Ctrl+B 显示/隐藏")
        print("  - 系统托盘: 右键切换置顶、窗口隐私保护等")
        print()
        _print_access_info(port)
        print()
        print("  正在启动桌面应用...")
        import time
        time.sleep(1)  # 给用户 1 秒看到消息

        # 重启自己，但这次带上隐藏标志
        env = {**os.environ, HIDE_CONSOLE_ENV: "1"}
        subprocess.Popen(
            [sys.executable] + sys.argv,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            cwd=os.getcwd(),
        )
        sys.exit(0)

    # 到这里说明已经是无窗口模式了（或者不是 Windows）
    env = {**os.environ, "PORT": str(port), HIDE_CONSOLE_ENV: "1", "IA_PYTHON_EXE": sys.executable}
    proc = subprocess.run([npx, "electron", "."], cwd=DESKTOP_DIR, env=env, **_hidden_process_kwargs())
    sys.exit(proc.returncode)


def run_network_mode(port: int):
    """Network mode: LAN accessible via browser (no Electron needed)."""
    os.environ.setdefault("IA_AUTH_ENABLE", "1")
    print("  纯浏览器模式（无 Electron）")
    print()
    _print_access_info(port)

    start_server("0.0.0.0", port)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Switch console to UTF-8 immediately on Windows (before any print)
    _set_utf8_console()

    parser = argparse.ArgumentParser(description="成竹启动器")
    parser.add_argument("--mode", choices=["desktop", "network"], default="desktop",
                        help="运行模式: desktop (Electron 桌面窗口) 或 network (局域网浏览器访问)")
    parser.add_argument("--port", type=int, default=18080, help="服务端口 (默认 18080)")
    parser.add_argument("--no-build", action="store_true", help="跳过前端构建")
    parser.add_argument("--rebuild", action="store_true", help="强制重新构建前端（即使 dist 已存在）")
    parser.add_argument("--skip-dep-check", action="store_true",
                        help="跳过 Python 依赖检查（已确认环境正确时可加速启动）")
    args = parser.parse_args()

    print("=" * 50)
    print("  成竹 Cheng Zhu")
    print("=" * 50)
    print()

    # Python 版本检查
    if sys.version_info < (3, 10):
        print(f"[ERROR] 需要 Python 3.10+，当前版本: {sys.version}")
        print("  请升级 Python: https://www.python.org/downloads/")
        sys.exit(1)

    print(f"  Python: {sys.version.split()[0]}  ({sys.executable})")
    print(f"  平台: {platform.system()} {platform.machine()}")
    print()

    # Electron 41.10.x requires Node 22.12+; frontend-only builds still
    # support Node 18+.  Check before npm starts so failures are actionable.
    if not ensure_node_version(args.mode, needs_build=not args.no_build):
        sys.exit(1)

    # Ensure Python deps (auto-install if missing)
    if not args.skip_dep_check:
        ensure_python_deps()

    if not args.no_build:
        if not build_frontend(force=args.rebuild):
            print()
            print("  前端构建失败，可以用 --no-build 跳过（需先手动构建）：")
            print(f"    cd frontend && npm install && npm run build && cd ..")
            print(f"    python start.py --no-build")
            sys.exit(1)

    mode_label = "Electron 桌面窗口" if args.mode == "desktop" else "局域网浏览器"
    print(f"  模式: {mode_label}  端口: {args.port}")
    print("=" * 50)
    print()

    if args.mode == "desktop":
        run_desktop_mode(args.port)
    else:
        run_network_mode(args.port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  已停止。")
        sys.exit(0)
