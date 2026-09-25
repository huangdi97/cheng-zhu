"""准备空间存储层测试。"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.storage import prep_space


def test_create_and_get_space():
    sid = prep_space.create_space(
        title="后端准备空间", role="后端开发", company="某公司",
        jd_text="JD 文本", resume_text="简历文本",
    )
    try:
        space = prep_space.get_space(sid)
        assert space is not None
        assert space["title"] == "后端准备空间"
        assert space["role"] == "后端开发"
        assert space["company"] == "某公司"
        assert space["jd_text"] == "JD 文本"
        assert space["resume_text"] == "简历文本"
        assert space["questions"] == []
        assert space["skill_cards"] == []
        assert space["insight_status"] == "pending"
    finally:
        prep_space.delete_space(sid)


def test_list_spaces_includes_new_space_and_counts():
    a = prep_space.create_space(title="A", role="r")
    b = prep_space.create_space(title="B", role="r")
    try:
        items = prep_space.list_spaces()
        ids = [i["id"] for i in items]
        assert a in ids and b in ids
        by_id = {i["id"]: i for i in items}
        assert by_id[a]["skill_card_count"] == 0
    finally:
        prep_space.delete_space(a)
        prep_space.delete_space(b)


def test_insight_and_questions_update():
    sid = prep_space.create_space(title="t", role="r")
    try:
        prep_space.update_insight(sid, "# 洞察内容", "done")
        prep_space.update_questions(sid, [{"question": "q1", "type": "technical"}], "done")
        space = prep_space.get_space(sid)
        assert space["insight_markdown"] == "# 洞察内容"
        assert space["insight_status"] == "done"
        assert space["questions"][0]["question"] == "q1"
    finally:
        prep_space.delete_space(sid)


def test_skill_card_roundtrip():
    sid = prep_space.create_space(title="t", role="r")
    try:
        cid = prep_space.add_skill_card(sid, "缓存优化项目")
        prep_space.update_skill_card(cid, {"name": "缓存优化项目", "background": "背景"}, "done")
        space = prep_space.get_space(sid)
        assert len(space["skill_cards"]) == 1
        card = space["skill_cards"][0]
        assert card["project_name"] == "缓存优化项目"
        assert card["card"]["background"] == "背景"
        assert card["status"] == "done"
    finally:
        prep_space.delete_space(sid)


def test_delete_missing_space_returns_false():
    assert prep_space.delete_space(99999999) is False


def test_get_missing_space_returns_none():
    assert prep_space.get_space(99999999) is None