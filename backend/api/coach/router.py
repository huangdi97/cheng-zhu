"""Human Coach API (R2 Stage U).

Two surfaces:
  - candidate_router  (/api/coach/*) — mounted on the main app, which binds
    127.0.0.1 only. Create / list / revoke sessions, play voice cues.
  - helper_app        — a separate tiny FastAPI app exposing ONLY the helper
    page and its token-guarded endpoints. For LAN coaching it is served on
    its own listener (0.0.0.0:COACH_PORT) so the main API is never exposed.
"""
from __future__ import annotations

import os
import socket
import threading
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from core.logger import get_logger
from services import coach
from services.coach import CoachAuthError, CoachPolicyError, CoachRateLimited

_log = get_logger("coach")
COACH_PORT = int(os.environ.get("COACH_PORT", "18180"))

candidate_router = APIRouter(tags=["coach"])

_last_fast_cue: dict[str, Any] = {}
_lan_server: dict[str, Any] = {"thread": None, "server": None, "port": 0}


def remember_fast_cue(payload: dict[str, Any]) -> None:
    """Called when a guidance_fast is emitted; helpers with the ai_cue
    permission see the latest one."""
    _last_fast_cue.clear()
    _last_fast_cue.update({k: payload.get(k) for k in ("id", "direction", "cues", "cautions", "resolved_question")})


def _human_policy_for(session_kind: str, target_session_id: str = "") -> str:
    kind = str(session_kind or "").strip().lower()
    if kind == "conversation":
        if not target_session_id:
            return "HUMAN_FORBIDDEN"
        try:
            from services.product import conversations

            session = conversations.require_session(target_session_id)
            if session.get("status") != "ACTIVE":
                return "HUMAN_FORBIDDEN"
            return str((session.get("policy") or {}).get("human_assistance") or "HUMAN_PRACTICE_ONLY")
        except Exception:
            return "HUMAN_FORBIDDEN"

    from core.config import get_config
    from core.session import session_id
    from services.intelligence.interview_pack import load_frozen_pack

    cfg = get_config()
    if kind == "live":
        pack = load_frozen_pack(session_id())
        if pack is not None:
            return pack.human_assistance_policy
    return str(getattr(cfg, "human_assistance_policy", "HUMAN_PRACTICE_ONLY") or "HUMAN_PRACTICE_ONLY")


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


def _ensure_lan_listener() -> int:
    if _lan_server["thread"] is not None and _lan_server["thread"].is_alive():
        return _lan_server["port"]
    import uvicorn

    config = uvicorn.Config(helper_app, host="0.0.0.0", port=COACH_PORT, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="coach-lan", daemon=True)
    thread.start()
    _lan_server.update(thread=thread, server=server, port=COACH_PORT)
    return COACH_PORT


def _stop_lan_listener_if_idle() -> None:
    if any(s["active"] for s in coach.registry.list()):
        return
    server = _lan_server.get("server")
    if server is not None:
        server.should_exit = True
    _lan_server.update(thread=None, server=None, port=0)


class CreateCoachSession(BaseModel):
    session_kind: str = Field(default="practice", pattern="^(practice|live|conversation)$")
    target_session_id: str = Field(default="", max_length=160)
    permissions: dict[str, bool] = Field(default_factory=lambda: {"transcript": True})
    ttl_min: int = Field(default=coach.DEFAULT_TTL_MIN, ge=5, le=coach.MAX_TTL_MIN)
    lan: bool = False


@candidate_router.post("/coach/sessions")
def create_session(body: CreateCoachSession, request: Request):
    from core.session import session_id

    target_session_id = (
        str(body.target_session_id or "").strip()
        if body.session_kind == "conversation"
        else session_id()
    )
    policy = _human_policy_for(body.session_kind, target_session_id)
    try:
        session, token = coach.registry.create(
            human_policy=policy,
            session_kind=body.session_kind,
            permissions=body.permissions,
            ttl_min=body.ttl_min,
            live_session_id=target_session_id,
        )
    except CoachPolicyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    local_base = str(request.base_url).rstrip("/")
    urls = {"local": f"{local_base}/coach#t={token}"}
    if body.lan:
        port = _ensure_lan_listener()
        urls["lan"] = f"http://{_lan_ip()}:{port}/coach#t={token}"
    public = coach.public_base_url()
    urls["public"] = f"{public}/coach#t={token}" if public else ""
    # The token is returned exactly once and never logged.
    _log.info("COACH_SESSION_CREATED id=%s kind=%s lan=%s", session.id, session.session_kind, body.lan)
    return {
        **session.public(),
        "urls": urls,
        "public_relay": "CONFIGURED" if public else "BLOCKED-EXTERNAL",
        "human_policy": policy,
    }


@candidate_router.get("/coach/sessions")
def list_sessions():
    return {"sessions": coach.registry.list(), "public_relay": "CONFIGURED" if coach.public_base_url() else "BLOCKED-EXTERNAL"}


@candidate_router.post("/coach/sessions/{coach_id}/revoke")
def revoke_session(coach_id: str):
    ok = coach.registry.revoke(coach_id)
    _stop_lan_listener_if_idle()
    if not ok:
        raise HTTPException(status_code=404, detail="coach session not found")
    return {"id": coach_id, "revoked": True}


@candidate_router.get("/coach/voice/{voice_id}")
def get_voice(voice_id: str):
    item = coach.registry.get_voice(voice_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    data, mime = item
    return Response(content=data, media_type=mime)


# ---------------------------------------------------------------------------
# Helper surface (served on the main loopback app AND the LAN listener)
# ---------------------------------------------------------------------------

helper_router = APIRouter(tags=["coach-helper"])


def _auth(token: Optional[str]) -> coach.CoachSession:
    try:
        return coach.registry.authenticate(token or "")
    except CoachAuthError:
        raise HTTPException(status_code=401, detail="链接无效、已过期或已被撤销") from None


def _broadcast(payload: dict[str, Any]) -> None:
    try:
        from api.realtime.ws import broadcast

        broadcast(payload)
    except Exception as exc:  # noqa: BLE001
        _log.warning("coach broadcast failed: %s", exc)


@helper_router.get("/coach", response_class=HTMLResponse)
def helper_page():
    return HTMLResponse(_HELPER_HTML, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@helper_router.get("/coach/api/state")
def helper_state(x_coach_token: Optional[str] = Header(default=None)):
    session = _auth(x_coach_token)
    state: dict[str, Any] = {
        "session": {
            "kind": session.session_kind,
            "expires_at": session.expires_at,
            "permissions": session.permissions,
            "target_session_id": session.live_session_id,
        },
        "current_question": "",
    }

    if session.session_kind == "conversation":
        try:
            from services.product import conversation_capture, conversations

            target = conversations.require_session(session.live_session_id)
            if target.get("status") != "ACTIVE":
                raise CoachPolicyError("Conversation Session 已结束")
            target_state = dict(target.get("state") or {})
            state["current_question"] = str(target_state.get("current_topic") or "")
            if session.permissions.get("transcript"):
                state["transcript"] = conversation_capture.transcript(session.live_session_id)[-6:]
            if session.permissions.get("ai_cue"):
                latest = [
                    row for row in conversations.guidance_history(session.live_session_id, 8)
                    if row.get("kind") != "HUMAN_COACH"
                ]
                state["ai_cue"] = latest[0] if latest else {}
            if session.permissions.get("session_context"):
                context = conversations.session_context(session.live_session_id)
                state["conversation_context"] = {
                    "space": context.get("space") or {},
                    "brief": context.get("brief") or {},
                    "sources": context.get("sources") or [],
                    "participants": context.get("participants") or [],
                    "profile_playbook": context.get("profile_playbook") or {},
                }
            return state
        except CoachPolicyError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=409, detail=f"Conversation 教练上下文不可用：{exc}") from None

    from core.session import get_session

    live = get_session()
    qa = live.qa_pairs[-1] if getattr(live, "qa_pairs", None) else None
    state["current_question"] = getattr(qa, "question", "") if qa else ""
    if session.permissions.get("transcript"):
        state["transcript"] = list(getattr(live, "transcription_history", []) or [])[-6:]
    if session.permissions.get("ai_cue"):
        state["ai_cue"] = dict(_last_fast_cue)
    if session.permissions.get("resume_jd"):
        try:
            from core.config import get_config
            from services.intelligence.interview_pack import resolve_live_pack

            pack = resolve_live_pack(session.live_session_id or "default", get_config())
            state["resume_jd"] = {
                "job": {"title": pack.job.get("title", ""), "requirements": pack.job_requirements},
                "profile_preview": pack.profile_text[:400],
            }
        except Exception:  # noqa: BLE001
            state["resume_jd"] = {}
    return state


class HelperCue(BaseModel):
    text: str = Field(min_length=1, max_length=coach.MAX_TEXT_CHARS)


def _guard(session: coach.CoachSession) -> None:
    try:
        coach.registry.check_policy(
            session,
            _human_policy_for(session.session_kind, session.live_session_id),
        )
        coach.registry.take_rate(session)
    except CoachPolicyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except CoachRateLimited:
        raise HTTPException(status_code=429, detail="发送太频繁，请稍后再试") from None


@helper_router.post("/coach/api/cue")
def helper_cue(body: HelperCue, x_coach_token: Optional[str] = Header(default=None)):
    session = _auth(x_coach_token)
    _guard(session)
    payload = coach.coach_cue_payload(session, text=body.text.strip())
    if session.session_kind == "conversation":
        from services.product import conversations

        event = conversations.record_human_coach_cue(
            session.live_session_id,
            text=body.text.strip(),
            coach_session_id=session.id,
        )
        payload["id"] = event["id"]
    _broadcast(payload)
    return {"ok": True, "id": payload["id"]}


@helper_router.post("/coach/api/voice")
async def helper_voice(request: Request, x_coach_token: Optional[str] = Header(default=None)):
    session = _auth(x_coach_token)
    _guard(session)
    data = await request.body()
    try:
        vid = coach.registry.store_voice(data, request.headers.get("content-type", "audio/webm"))
    except ValueError:
        raise HTTPException(status_code=413, detail="语音太长") from None
    payload = coach.coach_cue_payload(session, voice_id=vid)
    if session.session_kind == "conversation":
        from services.product import conversations

        event = conversations.record_human_coach_cue(
            session.live_session_id,
            text="",
            coach_session_id=session.id,
            voice_id=vid,
        )
        payload["id"] = event["id"]
    _broadcast(payload)
    return {"ok": True, "id": payload["id"]}


helper_app = FastAPI(title="Chengzhu Coach Helper", docs_url=None, redoc_url=None, openapi_url=None)
helper_app.include_router(helper_router)


_HELPER_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>成竹 · 教练端</title>
<style>
:root{--bg:#f7f8fa;--fg:#0f172a;--muted:#475569;--line:#dfe3ea;--accent:#1d4ed8;--risk:#b91c1c}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--fg:#e5e7eb;--muted:#a3aab5;--line:#2a2f38;--accent:#8ab4ff;--risk:#f28f8f}}
body{margin:0;font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
main{max-width:720px;margin:0 auto;padding:16px}
h1{font-size:18px;margin:0 0 4px}.muted{color:var(--muted);font-size:13px}
section{border:1px solid var(--line);border-radius:12px;padding:12px;margin:12px 0}
h2{font-size:13px;margin:0 0 6px;color:var(--muted)}
textarea{width:100%;box-sizing:border-box;min-height:70px;border:1px solid var(--line);border-radius:8px;padding:8px;background:transparent;color:inherit;font:inherit}
button{margin-top:8px;padding:8px 14px;border-radius:8px;border:1px solid var(--accent);background:var(--accent);color:#fff;font:inherit;cursor:pointer}
button.secondary{background:transparent;color:var(--accent)}
.err{color:var(--risk)}ul{margin:0;padding-left:18px}
</style></head><body><main>
<h1>成竹 · 教练端</h1>
<p class="muted">你给出的是建议，不是事实；候选人会看到它标注为「教练建议」。本页不能控制对方电脑。</p>
<p id="status" class="muted">连接中…</p>
<section><h2>当前问题</h2><div id="q">—</div></section>
<section id="tr" hidden><h2>转写</h2><ul id="trl"></ul></section>
<section id="cue" hidden><h2>AI Cue / Guidance</h2><ul id="cuel"></ul></section>
<section id="ctx" hidden><h2>本场冻结上下文</h2><div id="ctxd"></div></section>
<section id="rj" hidden><h2>简历 / 岗位</h2><div id="rjd"></div></section>
<section><h2>发送文字建议（最多 280 字）</h2>
<textarea id="t" maxlength="280" aria-label="建议内容"></textarea>
<button id="send">发送</button>
<button id="rec" class="secondary">按住录一段语音</button>
<p id="msg" class="muted" aria-live="polite"></p></section>
</main><script>
const token=new URLSearchParams(location.hash.slice(1)).get('t')||'';
history.replaceState(null,'',location.pathname);
const H={'X-Coach-Token':token};
const $=id=>document.getElementById(id);
function li(list,items){list.textContent='';for(const x of items||[]){const e=document.createElement('li');e.textContent=typeof x==='string'?x:x.text;list.appendChild(e)}}
function line(parent,text){const e=document.createElement('div');e.textContent=text;parent.appendChild(e)}
function renderConversationContext(ctx){
  const root=$('ctxd');root.textContent='';
  if(!ctx)return;
  const brief=ctx.brief||{},space=ctx.space||{},playbook=ctx.profile_playbook||{};
  line(root,'Space · '+(space.title||space.id||'—'));
  if(brief.goal)line(root,'Goal · '+brief.goal);
  if(Array.isArray(brief.agenda)&&brief.agenda.length)line(root,'Agenda · '+brief.agenda.slice(0,5).join(' / '));
  if(playbook.closing_objective)line(root,'Playbook · '+playbook.closing_objective);
  if(Array.isArray(ctx.sources)&&ctx.sources.length)line(root,'Sources · '+ctx.sources.slice(0,8).map(x=>x.title||x.material_id).join(' / '));
  if(Array.isArray(ctx.participants)&&ctx.participants.length)line(root,'Participants · '+ctx.participants.slice(0,8).map(x=>(x.display_name||'未命名')+(x.role?' · '+x.role:'')).join(' / '));
}
async function poll(){try{const r=await fetch('/coach/api/state',{headers:H});if(!r.ok){$('status').textContent=(await r.json()).detail||'链接不可用';$('status').className='err';return}
const s=await r.json();const kindLabel=s.session.kind==='conversation'?'Conversation Session':s.session.kind==='live'?'允许协助的正式面试':'练习';$('status').textContent='已连接 · '+kindLabel+' · 有效期至 '+new Date(s.session.expires_at*1000).toLocaleTimeString();
$('q').textContent=s.current_question||'—';
if(s.transcript){$('tr').hidden=false;li($('trl'),s.transcript)}else{$('tr').hidden=true}
if(s.ai_cue){$('cue').hidden=false;const items=Array.isArray(s.ai_cue.cues)?s.ai_cue.cues:[{text:s.ai_cue.text||s.ai_cue.expression_plan?.text||s.ai_cue.kind||'当前 Guidance'}];li($('cuel'),items)}else{$('cue').hidden=true}
if(s.conversation_context){$('ctx').hidden=false;renderConversationContext(s.conversation_context)}else{$('ctx').hidden=true}
if(s.resume_jd){$('rj').hidden=false;$('rjd').textContent=((s.resume_jd.job||{}).title||'')+' '+((s.resume_jd.job||{}).requirements||[]).join('、')}else{$('rj').hidden=true}
}catch(e){$('status').textContent='连接中断，重试中…'}setTimeout(poll,2000)}
$('send').onclick=async()=>{const text=$('t').value.trim();if(!text)return;const r=await fetch('/coach/api/cue',{method:'POST',headers:{...H,'Content-Type':'application/json'},body:JSON.stringify({text})});
$('msg').textContent=r.ok?'已发送':((await r.json()).detail||'发送失败');if(r.ok)$('t').value=''};
let rec,chunks=[];$('rec').onpointerdown=async()=>{try{const s=await navigator.mediaDevices.getUserMedia({audio:true});rec=new MediaRecorder(s);chunks=[];rec.ondataavailable=e=>chunks.push(e.data);
rec.onstop=async()=>{s.getTracks().forEach(t=>t.stop());const b=new Blob(chunks,{type:rec.mimeType||'audio/webm'});const r=await fetch('/coach/api/voice',{method:'POST',headers:{...H,'Content-Type':b.type},body:b});$('msg').textContent=r.ok?'语音已发送':((await r.json()).detail||'发送失败')};rec.start()}catch(e){$('msg').textContent='无法使用麦克风'}};
$('rec').onpointerup=()=>{if(rec&&rec.state==='recording')rec.stop()};
poll();
</script></body></html>
"""
