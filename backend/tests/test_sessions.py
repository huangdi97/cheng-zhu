"""Multi-session isolation: create / activate / delete / rename + snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import core.session as s


@pytest.fixture(autouse=True)
def _clean_sessions():
    with s._lock:
        s._sessions.clear()
        s._session = None
        s._active_session_id = ""
    yield
    with s._lock:
        s._sessions.clear()
        s._session = None
        s._active_session_id = ""


def test_default_session_created_on_demand():
    sess = s.get_session()
    assert sess.session_id == "default"
    assert s.session_id() == "default"
    assert len(s.list_sessions()) == 1


def test_create_session_switches_active_and_isolates_data():
    default = s.get_session()
    default.add_transcription("默认会话问题")
    created = s.create_session(label="腾讯一面")
    assert created.session_id != default.session_id
    assert s.session_id() == created.session_id
    assert len(s.get_session().transcription_history) == 0
    assert len(s.list_sessions()) == 2
    active = [x for x in s.list_sessions() if x["is_active"]]
    assert len(active) == 1 and active[0]["id"] == created.session_id


def test_activate_session_switches_back():
    default = s.get_session()
    created = s.create_session(label="第二场")
    created.add_transcription("第二场内容")
    s.activate_session(default.session_id)
    assert s.session_id() == default.session_id
    assert len(s.get_session().transcription_history) == 0  # default has no transcription
    s.activate_session(created.session_id)
    assert s.get_session().transcription_history == ["第二场内容"]


def test_delete_active_rejected_delete_inactive_ok():
    default = s.get_session()
    created = s.create_session(label="待删除")
    assert s.delete_session(created.session_id) is False  # 当前激活的不可删
    s.activate_session(default.session_id)
    assert s.delete_session(created.session_id) is True
    assert s.delete_session("不存在") is False


def test_rename_session():
    s.get_session()
    created = s.create_session(label="旧名字")
    assert s.rename_session(created.session_id, "新名字") is True
    info = [x for x in s.list_sessions() if x["id"] == created.session_id][0]
    assert info["label"] == "新名字"


def test_snapshot_includes_session_identity():
    sess = s.create_session(label="快照")
    snap = s.snapshot_session()
    assert snap["session_id"] == sess.session_id
    assert snap["label"] == "快照"
