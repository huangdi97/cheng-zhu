"""运行时数据目录。

开发模式：数据在 backend/data/，并从旧版 backend/*.db 自动迁移一次。
安装包模式（R2 Stage AH）：Electron 把 app.getPath('userData') 通过环境变量
``CHENGZHU_HOME`` 传给后端 sidecar，所有用户数据都写到该目录，绝不写安装目录：

    %APPDATA%\\Chengzhu\\
      data\\    SQLite、知识库、策略树
      config\\  config.json
      logs\\    运行日志
      cache\\   模型等可再生缓存
      exports\\ 导出文件
"""

from __future__ import annotations

import os

_STORAGE_PKG = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_STORAGE_PKG, "..", ".."))


def backend_root() -> str:
    """Directory of the backend code (read-only in an installed build)."""
    return _BACKEND_ROOT


def app_home() -> str:
    """Root for user-writable state: CHENGZHU_HOME when packaged, else backend/."""
    home = (os.environ.get("CHENGZHU_HOME") or "").strip()
    return os.path.abspath(home) if home else _BACKEND_ROOT


def is_packaged_home() -> bool:
    return bool((os.environ.get("CHENGZHU_HOME") or "").strip())


def _ensure(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def data_dir() -> str:
    return _ensure(os.path.join(app_home(), "data"))


def config_dir() -> str:
    return _ensure(os.path.join(app_home(), "config")) if is_packaged_home() else _BACKEND_ROOT


def logs_dir() -> str:
    if is_packaged_home():
        return _ensure(os.path.join(app_home(), "logs"))
    return os.path.join(os.path.dirname(_BACKEND_ROOT), "log")


def cache_dir() -> str:
    return _ensure(os.path.join(app_home(), "cache"))


def exports_dir() -> str:
    return _ensure(os.path.join(app_home(), "exports"))


def sqlite_path(filename: str) -> str:
    """
    SQLite 文件路径（仅文件名，如 knowledge.db）。
    若 data/ 下不存在而 backend 根目录存在同名旧库，则整体迁移 .db 及 -wal/-shm。
    """
    d = data_dir()
    new_p = os.path.join(d, filename)
    old_p = os.path.join(_BACKEND_ROOT, filename)
    if not is_packaged_home() and not os.path.isfile(new_p) and os.path.isfile(old_p):
        try:
            os.replace(old_p, new_p)
            for ext in ("-wal", "-shm"):
                o2 = old_p + ext
                n2 = new_p + ext
                if os.path.isfile(o2):
                    try:
                        os.replace(o2, n2)
                    except OSError:
                        pass
        except OSError:
            pass
    return new_p
