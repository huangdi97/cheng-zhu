"""启动器依赖探测回归测试。"""

import importlib.util
from types import SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
START_PY = ROOT / "start.py"


def load_start():
    spec = importlib.util.spec_from_file_location("start_launcher_dependencies", START_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runtime_import_map_handles_distribution_name_differences():
    start = load_start()
    imports = start._runtime_imports()

    assert imports["python-multipart"] == "multipart"
    assert imports["websocket-client"] == "websocket"
    assert imports["pymupdf"] == "fitz"
    assert imports["Pillow"] == "PIL"
    assert imports["python-docx"] == "docx"


def test_node_bootstrap_prefers_lockfile_ci(monkeypatch):
    start = load_start()
    directory = "frontend"

    monkeypatch.setattr(start.os.path, "isfile", lambda path: False)
    assert start._npm_install_command("npm", str(directory)) == ["npm", "install"]

    monkeypatch.setattr(start.os.path, "isfile", lambda path: path.endswith("package-lock.json"))
    assert start._npm_install_command("npm", str(directory)) == ["npm", "ci"]


def test_desktop_node_version_gate_matches_electron_requirement(monkeypatch):
    start = load_start()
    monkeypatch.setattr(start, "_find_node", lambda: "node")
    monkeypatch.setattr(
        start.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="v22.11.0", stderr=""),
    )

    assert start.ensure_node_version("desktop", needs_build=True) is False


def test_network_no_build_does_not_require_node(monkeypatch):
    start = load_start()
    monkeypatch.setattr(start, "_find_node", lambda: None)

    assert start.ensure_node_version("network", needs_build=False) is True


def test_dependency_check_retries_all_runtime_imports_after_install(monkeypatch):
    start = load_start()
    monkeypatch.setattr(start, "_runtime_imports", lambda: {"python-docx": "docx"})
    import_calls = []

    def fake_import(module):
        import_calls.append(module)
        if len(import_calls) == 1:
            raise ImportError("missing in test")
        return object()

    monkeypatch.setattr(start.importlib, "import_module", fake_import)
    pip_calls = []

    class Result:
        returncode = 0

    def fake_run(cmd):
        pip_calls.append(cmd)
        return Result()

    monkeypatch.setattr(start.subprocess, "run", fake_run)

    start.ensure_python_deps()

    assert import_calls == ["docx", "docx"]
    assert pip_calls == [
        [start.sys.executable, "-m", "pip", "install", "-r", start.REQUIREMENTS, "--quiet"]
    ]
