# Chengzhu v1.2-R2 — InterviewPack Snapshot & Context Authority

## InterviewPack

- Table `interview_pack` (migration v2): immutable rows; a revision is a new row with `revision+1` and `parent_id`.
- Payload holds actual content: candidate_context, claims (with axes, minus USER_DENIED), evidence_refs, user-reviewed skill cards, stories, job + alignment + company, selected KB, voice profile, AI / human / share-privacy / screen-context policies, model profile (names only, never keys), answer preferences (notes), controlled memory, source versions, per-section content hashes.
- Freezing: 求职 → 岗位目标 → 冻结并用于本场 (`/api/prep/spaces/{id}/launch-pack`) or `/api/intelligence/pack/freeze`.
- Live: `answer_worker._resolve_live_pack(session_id)` → frozen pack, or an ephemeral pack with the configured resume and **no job**.

### Snapshot acceptance fixture (first acceptance case)

`test_job_a_pack_is_not_contaminated_by_later_job_b` runs the real answer worker:
1. Save + freeze Pack A (AI Agent Engineer, LangGraph / RAG)
2. Analyze Job B afterwards (Data Engineer, Spark / Flink) — becomes `latest_job_id()`
3. Ask a live question in session A
4. Assert the user prompt **and** system prompt contain no Spark / Flink / "Data Engineer", contain LangGraph, `answer_done.guidance.context.pack_id == Pack A`, frozen job stays job-A.

Also: `test_live_path_has_no_latest_reads` (source check), `test_pack_revision_keeps_original_row`, `test_unfrozen_session_never_reads_latest_job`, `test_pack_never_holds_api_keys`, packaged smoke `pack_persisted_after_restart`.

## Context authority

- `compile_live_context(pack, …)` providers: InterviewPackCandidate, InterviewPackEvidence, InterviewPackSkillCard, InterviewPackStory, SessionMemory, LongTermMemory, Job (from pack), KB (filtered by the pack's KB selection), Screen, WorldKnowledgePermission.
- Every fragment has `fragment_id / source_type / source_id / content_hash`; exact and contained duplicates are dropped (stronger evidence wins).
- On success `build_system_prompt(context_authoritative=True)` omits resume, KB, memo and global JD; notes come from the pack. `compiler_fallback=true` only when compilation raises, and is recorded in `answer_done.guidance.context` and the turn trace.

### Dedupe gate (`test_fragment_dedupe_gate`, `test_system_prompt_does_not_reinject_when_authoritative`)

| Fragment | Appearances in final prompt |
|---|---|
| Same resume line (resume ×2 + memo) | 1 |
| Same KB hit ×2 | 1 |
| Resume / JD / memo in system prompt when authoritative | 0 |
| Compact interview state (was 2 in v1.x) | 1 |
| Question intent (plan + state) | 1 |

### Before / after on the v1.x follow-up regression case

`test_short_followup_keeps_tail_of_long_previous_answer` (prompt must stay < answer + 160 chars): v1.x 697 chars with the state block twice → R2 < 629 with each fragment once, while also carrying the new per-turn assertion-policy line.

### Soak

Prompt size first hour 451 chars → last hour 490 chars over 300 turns: no context pollution (`CHENGZHU_V1_2_R2_SOAK.md`).
