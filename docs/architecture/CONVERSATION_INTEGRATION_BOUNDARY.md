# Conversation Integration Boundary

**Status**: CURRENT-MAIN CANDIDATE · PR #61  
**Scope**: v2 Conversation external read context + reviewed external execution  
**Non-goal**: this document does not claim a Google / Microsoft / GitHub / MCP account is currently connected.

---

## 1. Why this is a separate boundary

Chengzhu has three different truths that must not be collapsed:

```text
Capability Registry
!=
Connected Account
!=
External Action Succeeded
```

### Capability Registry

`conversation_connectors.py` answers:

> “Does a real runtime adapter claim it can satisfy capability X?”

Default registry is empty and fail-closed.

### Integration Boundary

`conversation_integrations.py` answers:

> “Which verified user connection may use that capability, what immutable external snapshot entered this Space/Session, and what external action was explicitly attempted?”

### Provider Adapter

A provider/plugin owns:

- OAuth / PAT / provider login;
- secure credential resolution;
- provider API calls;
- paging / cursor semantics;
- provider error mapping.

No provider adapter means no connection can become `CONNECTED`.

---

## 2. Canonical capability vocabulary

Read-only Session capabilities:

- `calendar.read`
- `docs.read`
- `mail.read`
- `project.read`

Reviewed external execution capabilities:

- `email.send`
- `task.create`
- `issue.create`
- `decision_log.write`

Write capabilities are never valid Session read permissions.

---

## 3. Provider catalog is metadata, not connectivity

The built-in catalog describes possible adapter mappings:

| Provider | Read | Write | Default claim |
| --- | --- | --- | --- |
| Google Calendar | calendar.read | — | adapter not configured |
| Gmail | mail.read | email.send | adapter not configured |
| Google Drive / Docs | docs.read | — | adapter not configured |
| Microsoft Graph | calendar.read / mail.read / docs.read / project.read | email.send / task.create | adapter not configured |
| GitHub | project.read | issue.create | adapter not configured |
| MCP | server-defined subset of canonical capabilities | server-defined subset | adapter not configured |

A catalog entry never means:

- account connected;
- permission granted;
- remote API reachable;
- external action completed.

---

## 4. Least-privilege provider scopes

Provider scopes are derived from the granted Chengzhu capability set.

Examples:

```text
Google calendar.read
→ https://www.googleapis.com/auth/calendar.readonly

Google mail.read
→ https://www.googleapis.com/auth/gmail.readonly

Google email.send
→ https://www.googleapis.com/auth/gmail.send

Microsoft calendar.read
→ Calendars.Read

Microsoft mail.read
→ Mail.Read

Microsoft email.send
→ Mail.Send

GitHub project.read
→ Issues: read

GitHub issue.create
→ Issues: write
```

For catalog providers, stored scope metadata must equal the exact minimum scope set implied by the selected capability set.

MCP scope remains `server-defined`; Chengzhu does not fabricate OAuth-like scope strings for an MCP server.

---

## 5. Credential rule

`product.db` may store only an opaque credential reference:

```text
keyring:...
oskeychain:...
provider:...
plugin:...
```

It must never store:

- OAuth access token;
- refresh token;
- API key;
- Authorization header;
- password;
- client secret;
- provider cookie.

The adapter resolves the opaque reference through an OS secure store / provider plugin / connector-owned secure layer.

Public API and exports expose only:

```text
credential_ref_present = true / false
```

Never the reference value.

---

## 6. Connection lifecycle

```text
create metadata
→ DISCONNECTED
→ adapter health + credential resolution + exact capability check
→ CONNECTED
→ DISCONNECTED / ERROR / REVOKED
```

There is intentionally no API that lets UI directly set:

```text
status = CONNECTED
```

`verify_and_connect` is the only promotion path.

Revocation:

- clears the local opaque credential reference;
- clears sync cursor;
- blocks future reads/writes;
- does not rewrite frozen Session Packs or past execution audit.

---

## 7. Read path

```text
CONNECTED account
→ explicit Sync
→ adapter.read_context
→ immutable normalized snapshot
→ user explicitly selects snapshot in Space
→ Preflight
→ Session Pack freeze
→ Manual Ask / Context Retrieval
```

Sync does not silently add external content to a Session.

A snapshot is identified by:

- connection id;
- capability;
- external kind;
- external id;
- content hash.

If the same external object changes, it becomes a new immutable snapshot.

---

## 8. Snapshot truth authority

External snapshot authority is always:

```text
REFERENCE_SOURCE
```

Examples:

```text
Calendar event title
!= Chengzhu Decision

Mail sentence
!= Chengzhu Commitment

GitHub issue due date
!= reviewed Chengzhu Deadline
```

Promotion still requires the normal Conversation Item review path.

---

## 9. Session Pack freeze

The Pack freezes:

- selected connector snapshot ids;
- snapshot content/provenance;
- provider id;
- connection id;
- capability;
- external kind/id;
- content hash;
- visibility;
- exact read grant.

After Session start:

- new Sync does not rewrite the Pack;
- account disconnect/revoke does not rewrite the Pack;
- provider health change does not rewrite the Pack.

This is required for temporal reproducibility.

---

## 9.1 Space-scoped snapshot identity and sync cursors

Connector snapshot identity is scoped by Conversation Space:

```text
space_id
+ connection_id
+ capability
+ external_kind
+ external_id
+ Chengzhu canonical content_hash
```

The provider may report its own content hash, but that value is provenance metadata only; it never controls Chengzhu deduplication or frozen identity.

One account may expose multiple independent read capabilities. Incremental sync cursor state is therefore stored **per capability**. A Calendar cursor must never be reused for Docs/Mail/Project reads.

Cross-Space snapshot IDs are rejected before Space state is persisted.

---

## 10. Preflight

For every requested read capability, Preflight requires:

```text
real adapter
+ CONNECTED account
+ exact granted capability
+ current adapter health
```

Otherwise Session start fails closed.

Preflight separately shows:

- requested connector permissions;
- exact provider/connection grant;
- selected immutable snapshots;
- missing snapshot warnings.

Write capabilities supplied as Session permissions are blocked with:

```text
WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW
```

---

## 11. Reviewed write-back

External write-back uses two user decisions after the Conversation truth/review layer:

```text
Conversation truth
→ local DraftAction
→ user APPROVE / DISMISS

APPROVED
→ select exact CONNECTED account
→ create Execution Request

PENDING
→ second explicit Execute

provider explicitly returns ok=true
→ SUCCEEDED / source = DIRECT_PROVIDER_RESPONSE

UNKNOWN_OUTCOME + user records provider-side reconciliation CONFIRMED_SUCCEEDED
→ SUCCEEDED / source = USER_REPORTED_PROVIDER_CHECK
→ executed_at stays unknown; reconciliation.recorded_at is only the audit time

provider explicitly returns ok=false
→ FAILED
→ retry only when provider explicitly returns retry_safe=true

transport exception / timeout / missing explicit ok
→ UNKNOWN_OUTCOME
→ reconcile at provider before any retry
```

Therefore:

```text
APPROVED != external side effect
Execution Request != external side effect
SUCCEEDED == either DIRECT_PROVIDER_RESPONSE(ok=true) or explicit USER_REPORTED_PROVIDER_CHECK(CONFIRMED_SUCCEEDED)
FAILED == provider explicitly returned ok=false, or provider-side reconciliation confirmed NOT_APPLIED
UNKNOWN_OUTCOME == Chengzhu cannot know whether the side effect already happened
```

---

## 12. Execution capability mapping

```text
FOLLOWUP_EMAIL_DRAFT
→ email.send

CREATE_TASK_DRAFT
→ task.create

CREATE_ISSUE_DRAFT
→ issue.create

UPDATE_DECISION_LOG_DRAFT
→ decision_log.write
```

The exact capability is rechecked immediately before execution.

---

## 13. Idempotency and audit

Every execution request has an idempotency key derived from:

- DraftAction id/version;
- connection;
- capability;
- operation;
- target.

A successful request cannot execute again through the same audit row.

Audit states:

```text
PENDING
EXECUTING
SUCCEEDED
FAILED
UNKNOWN_OUTCOME
BLOCKED
CANCELLED
```

Outcome semantics are deliberately conservative:

- adapter result MUST contain an explicit boolean `ok`;
- `ok=true` → `SUCCEEDED`;
- `ok=false` → `FAILED`; retry is exposed only when the provider also explicitly returns `retry_safe=true`;
- exception / timeout / malformed result without boolean `ok` → `UNKNOWN_OUTCOME`;
- `UNKNOWN_OUTCOME` cannot be executed again through Chengzhu until provider-side reconciliation establishes what happened;
- reconciliation never rewrites the ambiguous adapter response into a fake `ok=true`;
- `CONFIRMED_SUCCEEDED` records a distinct user-reported provider check and leaves `executed_at` unknown;
- `CONFIRMED_NOT_APPLIED` is the only reconciliation path that sets `retry_safe=true`.

The idempotency key is passed to the adapter, but it is not treated as magic: a concrete provider must actually enforce idempotency before retry safety can be claimed.

Crash/restart recovery follows the same rule. An audit row persisted as `EXECUTING` with no live in-process execution is treated as an interrupted external call and converges to `UNKNOWN_OUTCOME`; it is never silently reset to `PENDING` or `FAILED`.

---

## 14. Sensitive-field sanitization

Provider snapshot metadata and execution responses are sanitized recursively.

Keys matching credential/token/secret/auth/cookie/password/private-key patterns are removed.

Source URLs retain only:

```text
scheme + host + path
```

userinfo / query / fragment are stripped. In addition to sensitive-key removal, obvious credential-shaped values (Bearer tokens, OAuth token forms, PAT/API-key/JWT-like values) are redacted before persistence. Opaque credential references are rejected if they merely wrap a token-looking secret.

---

## 15. Retention

Default external snapshot retention:

```text
30 days
```

Ordinary retention may delete an old unselected snapshot.

It must keep:

- snapshots explicitly selected by the current Space;
- frozen copies in Session Pack;
- all external execution audit rows;
- DraftActions referenced by execution audit.

Retention never uses cleanup to erase evidence of a real-world side-effect attempt.

---

## 16. Export

Local export may include:

- public connection metadata;
- immutable connector snapshots;
- frozen snapshot provenance;
- external execution audit.

It must not include:

- credential reference;
- token;
- API key;
- refresh token;
- raw authorization material.

Export manifest states:

```text
contains_external_secrets = false
credential_refs_exported = false
```

---

## 17. Diagnostics

Diagnostics distinguishes:

```text
NOT_CONFIGURED
ADAPTER_AVAILABLE_NOT_CONNECTED
CONNECTED
```

It also reports:

- registered adapters;
- connected account count;
- snapshot count;
- execution count.

This does not imply a provider is healthy forever; Preflight and execution recheck current health.

---

## 18. Current truth

When PR #61 is green/merged, the repository may claim:

```text
CONNECTOR_CAPABILITY_REGISTRY = IMPLEMENTED
EXTERNAL_INTEGRATION_BOUNDARY = IMPLEMENTED
IMMUTABLE_EXTERNAL_SNAPSHOT_PATH = IMPLEMENTED
REVIEWED_TWO_STEP_EXECUTION_BOUNDARY = IMPLEMENTED
AMBIGUOUS_EXTERNAL_OUTCOME_GUARD = IMPLEMENTED
DEFAULT_EXTERNAL_PROVIDER_STATE = FAIL_CLOSED
```

It must still not claim:

```text
GOOGLE_ACCOUNT_CONNECTED = TRUE
MICROSOFT_ACCOUNT_CONNECTED = TRUE
GITHUB_ACCOUNT_CONNECTED = TRUE
MCP_SERVER_CONNECTED = TRUE
REAL_EXTERNAL_ACTION_EVIDENCE = TRUE
```

Those require actual adapters, credentials/accounts and runtime evidence.
