"""Opt-in local Markdown / Obsidian Decision Log provider.

This provider closes the reviewed `decision_log.write` capability without
requiring a cloud account. It deliberately does *not* expose general filesystem
access.

Configuration:
- CHENGZHU_LOCAL_MARKDOWN_CONNECTOR_ENABLE=1
- credential_ref = provider:local-markdown:env:<ENV_VAR>
- ENV_VAR value = one explicit writable root directory

Execution target:
- relative path under that root
- .md only
- default: decisions.md

The root path itself never enters product.db. The adapter returns only the
relative target and a content hash. Writes are marker-idempotent and use a
same-directory temp file + os.replace so a completed provider response maps to
one durable reviewed Markdown state.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Optional


_ENV_REF_RE = re.compile(
    r"^provider:local-markdown:env:([A-Za-z_][A-Za-z0-9_]{0,127})$"
)
_MAX_EXISTING_BYTES = 10 * 1024 * 1024
_MAX_TITLE_CHARS = 500
_MAX_CONTENT_CHARS = 20_000


class LocalMarkdownDecisionLogAdapter:
    provider_id = "LOCAL_MARKDOWN"
    capabilities = {"decision_log.write"}

    @staticmethod
    def _resolve_root(connection: dict[str, Any]) -> Path:
        credential_ref = str(connection.get("credential_ref") or "").strip()
        match = _ENV_REF_RE.fullmatch(credential_ref)
        if not match:
            raise ValueError(
                "Local Markdown credential_ref 当前只支持 "
                "provider:local-markdown:env:<ENV_VAR>；root path 本身不能写入 product.db"
            )
        env_name = match.group(1)
        raw = str(os.environ.get(env_name) or "").strip()
        if not raw:
            raise ValueError(f"Local Markdown root environment variable 未设置：{env_name}")
        root = Path(raw).expanduser()
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise ValueError("Local Markdown root 不存在或无法解析") from exc
        if not resolved.is_dir():
            raise ValueError("Local Markdown root 必须是目录")
        if not os.access(resolved, os.R_OK | os.W_OK):
            raise ValueError("Local Markdown root 当前不可读写")
        return resolved

    @staticmethod
    def _target(root: Path, value: str) -> tuple[str, Path]:
        raw = str(value or "").strip().replace("\\", "/") or "decisions.md"
        if "\x00" in raw or "\r" in raw or "\n" in raw or len(raw) > 500:
            raise ValueError("Local Markdown target 包含非法字符或过长")
        if re.match(r"^[A-Za-z]:", raw) or raw.startswith(("/", "//")):
            raise ValueError("Local Markdown target 必须是 root 下的相对路径")
        rel = PurePosixPath(raw)
        if any(part in {"", ".", ".."} for part in rel.parts):
            raise ValueError("Local Markdown target 不允许空目录、. 或 ..")
        if rel.suffix.lower() != ".md":
            raise ValueError("Local Markdown target 只允许 .md 文件")

        target = root.joinpath(*rel.parts)
        # Resolve the nearest existing ancestor before creating directories.
        ancestor = target.parent
        while not ancestor.exists() and ancestor != root:
            ancestor = ancestor.parent
        resolved_ancestor = ancestor.resolve(strict=True)
        if resolved_ancestor != root and root not in resolved_ancestor.parents:
            raise ValueError("Local Markdown target 越出已授权 root")

        target.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = target.parent.resolve(strict=True)
        if resolved_parent != root and root not in resolved_parent.parents:
            raise ValueError("Local Markdown target 通过 symlink 越出已授权 root")
        resolved_target = resolved_parent / target.name
        return rel.as_posix(), resolved_target

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if connection is None:
            return {
                "ok": True,
                "label": "Local Markdown Decision Log",
                "runtime": "OPT_IN_LOCAL_PROVIDER",
            }
        root = self._resolve_root(connection)
        return {
            "ok": True,
            "label": "Local Markdown / Obsidian",
            "account_hint": root.name or "Markdown root",
            "verify": "LOCAL_ROOT_READ_WRITE_PROBE",
            "decision_log_write_capability_proof": "TARGET_VALIDATED_ON_EXECUTE",
        }

    def read_context(
        self,
        *,
        connection: dict[str, Any],
        capability: str,
        query: dict[str, Any],
        cursor: str,
        limit: int,
    ) -> dict[str, Any]:
        raise ValueError("Local Markdown provider 是 decision_log.write only；不读取 vault/目录内容")

    @staticmethod
    def _entry(title: str, content: str, marker: str) -> bytes:
        body = (
            f"\n\n{marker}\n"
            f"## {title.strip()}\n\n"
            f"{content.strip()}\n"
        )
        return body.encode("utf-8")

    def execute(
        self,
        *,
        connection: dict[str, Any],
        capability: str,
        operation: str,
        target: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if capability != "decision_log.write" or operation != "UPDATE_DECISION_LOG":
            return {
                "ok": False,
                "error": "Local Markdown provider 只支持 reviewed decision_log.write / UPDATE_DECISION_LOG",
                "retry_safe": False,
            }
        if bool(payload.get("outbound_redaction_applied")):
            return {
                "ok": False,
                "error": "Execution payload 已被安全层改写；Local Markdown 不会把未重新审核的变体写入 Decision Log",
                "retry_safe": False,
            }

        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or "").strip()
        if not title or not content:
            return {
                "ok": False,
                "error": "Decision Log 需要非空 title 与 content",
                "retry_safe": False,
            }
        if len(title) > _MAX_TITLE_CHARS or len(content) > _MAX_CONTENT_CHARS:
            return {
                "ok": False,
                "error": "Reviewed Decision Log 内容超过 provider 上限；不会静默截断，请回到 Draft 显式缩短后重新审核",
                "retry_safe": False,
            }

        root = self._resolve_root(connection)
        try:
            relative_target, target_path = self._target(root, target)
        except ValueError as exc:
            return {
                "ok": False,
                "error": str(exc),
                "retry_safe": True,
                "phase": "TARGET_VALIDATION_PRE_WRITE",
            }

        marker_key = str(idempotency_key or "").strip()
        if not marker_key or len(marker_key) > 300:
            return {
                "ok": False,
                "error": "缺少有效 execution idempotency key",
                "retry_safe": False,
            }
        marker = f"<!-- chengzhu-execution:{marker_key} -->"
        marker_bytes = marker.encode("utf-8")

        before_exists = target_path.exists()
        before_stat = target_path.stat() if before_exists else None
        before = target_path.read_bytes() if before_exists else b""
        if len(before) > _MAX_EXISTING_BYTES:
            return {
                "ok": False,
                "error": "Decision Log 文件超过 10 MiB 安全上限；请选择新的 Markdown target",
                "retry_safe": True,
                "phase": "TARGET_VALIDATION_PRE_WRITE",
            }
        if marker_bytes in before:
            return {
                "ok": True,
                "provider_id": "LOCAL_MARKDOWN",
                "external_id": f"local-markdown:{hashlib.sha256(marker_bytes).hexdigest()[:24]}",
                "target": relative_target,
                "deduplicated": True,
                "provider_idempotency": "MARKER_IN_FILE",
                "reviewed_payload_unchanged": True,
                "content_sha256": hashlib.sha256(before).hexdigest(),
            }

        entry = self._entry(title, content, marker)
        temp_name = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                dir=str(target_path.parent),
                prefix=f".{target_path.name}.chengzhu-",
                suffix=".tmp",
            ) as tmp:
                temp_name = tmp.name
                tmp.write(before)
                tmp.write(entry)
                tmp.flush()
                os.fsync(tmp.fileno())

            # Fail before replace if an editor changed the source file while the
            # candidate was being prepared. This is safely retryable because no
            # provider side effect has happened yet.
            now_exists = target_path.exists()
            if before_exists != now_exists:
                os.unlink(temp_name)
                return {
                    "ok": False,
                    "error": "Decision Log target 在写入前发生并发变化；未执行 replace",
                    "retry_safe": True,
                    "phase": "CONCURRENT_FILE_CHANGE_PRE_WRITE",
                }
            if before_exists:
                current = target_path.stat()
                if (
                    current.st_size != before_stat.st_size
                    or current.st_mtime_ns != before_stat.st_mtime_ns
                ):
                    os.unlink(temp_name)
                    return {
                        "ok": False,
                        "error": "Decision Log target 在写入前被其他程序修改；未执行 replace",
                        "retry_safe": True,
                        "phase": "CONCURRENT_FILE_CHANGE_PRE_WRITE",
                    }

            # os.replace is atomic on the same filesystem. If this raises after
            # the OS may have applied the rename, the shared integration layer
            # correctly records UNKNOWN_OUTCOME instead of auto-retrying.
            os.replace(temp_name, target_path)
            temp_name = ""
        finally:
            if temp_name:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass

        final_bytes = target_path.read_bytes()
        if marker_bytes not in final_bytes:
            raise RuntimeError("Local Markdown replace completed without expected execution marker")
        return {
            "ok": True,
            "provider_id": "LOCAL_MARKDOWN",
            "external_id": f"local-markdown:{hashlib.sha256(marker_bytes).hexdigest()[:24]}",
            "target": relative_target,
            "deduplicated": False,
            "provider_idempotency": "MARKER_IN_FILE",
            "reviewed_payload_unchanged": True,
            "content_sha256": hashlib.sha256(final_bytes).hexdigest(),
        }


def register_local_markdown_adapter_from_env() -> dict[str, Any]:
    enabled = str(os.environ.get("CHENGZHU_LOCAL_MARKDOWN_CONNECTOR_ENABLE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"registered": False, "provider_id": "LOCAL_MARKDOWN", "reason": "NOT_ENABLED"}

    from services.product import conversation_integrations

    adapter = LocalMarkdownDecisionLogAdapter()
    conversation_integrations.register_adapter(adapter)
    return {
        "registered": True,
        "provider_id": "LOCAL_MARKDOWN",
        "capabilities": sorted(adapter.capabilities),
        "credential_ref_format": "provider:local-markdown:env:<ENV_VAR>",
        "provider_scope": "local.filesystem.markdown.write",
        "read_capabilities": [],
        "write_capabilities": ["decision_log.write"],
        "default_target": "decisions.md",
    }
