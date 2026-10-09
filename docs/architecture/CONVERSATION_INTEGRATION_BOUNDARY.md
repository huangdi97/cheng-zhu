# Chengzhu Conversation Integration Boundary

**Status:** schema v8 / pure-repository runtime boundary  
**Stable product status:** unchanged; v2 stable release is not claimed  
**Provider connectivity:** no concrete Google/Microsoft/GitHub/MCP adapter is enabled by default

## 1. Why this boundary exists

Conversation needs Calendar, Mail, Docs, project/task systems and MCP eventually, but external context must not bypass the v2 truth model.

The integration path is therefore:

```text
External provider
→ least-privilege connection
→ immutable Connector Snapshot
→ explicit Space selection
→ Frozen Session Pack
→ retrieval as source
→ review before truth promotion
```

External action uses a separate path:

```text
Conversation Item truth
→ local DraftAction
→ user review
→ APPROVED
→ Execution Request
→ connection / scope / adapter recheck
→ second explicit Execute
→ provider response or failure
→ immutable audit row
```

These paths deliberately do not share an “automatic sync = truth” shortcut.

## 2. Provider catalog

The catalog describes what an adapter may support. It never means that provider is connected.

| Provider | Read capabilities | Write capabilities |
| --- | --- | --- |
| Google Calendar | calendar.read | — |
| Gmail | mail.read | mail.send |
| Google Drive / Docs | docs.read | — |
| Microsoft Graph | calendar.read, mail.read, docs.read, tasks.read | mail.send, tasks.write |
| GitHub | issues.read | issues.write |
| MCP | context.read | action.execute |

Provider-specific OAuth/permission strings are metadata used by future adapters.

Design rule:

> read permission never implies write permission.

## 3. Secret boundary

`product.db` must not contain OAuth access tokens, refresh tokens, client secrets or raw provider API keys.

The only value persisted on a connection is an opaque credential handle:

```text
keyring:...
oskeychain:...
provider:...
plugin:...
```

A provider adapter is responsible for resolving that handle through the OS keychain or provider credential store.

A string that does not follow the opaque-reference contract is rejected.

## 4. Connection state

```text
DISCONNECTED
CONNECTED
ERROR
REVOKED
```

A connection cannot become `CONNECTED` unless:
- its provider adapter is registered;
- it has an opaque credential reference.

The public Conversation API does not expose a generic “mark connected” endpoint.

OAuth/provider setup must perform the real verification before connection state changes.

## 5. Read path and snapshot provenance

Adapters return normalized external items. Chengzhu persists immutable snapshots containing:

- connection id;
- Space id;
- external kind;
- external id;
- title / bounded excerpt;
- content hash;
- source URL;
- occurred_at;
- visibility;
- provider metadata.

A new hash for the same external id becomes a new snapshot.

No external snapshot automatically enters a Session. The user explicitly selects snapshot ids on a Space; only those ids are frozen into the next Session Pack.

## 6. Frozen Pack semantics

Pack fingerprint includes:

- selected connector snapshot ids;
- connection id;
- external kind/id;
- content hash;
- visibility.

Once a Session starts:
- later provider sync does not rewrite its Pack;
- later source edits do not rewrite its Pack;
- Manual Ask sees the frozen snapshot;
- authority remains `REFERENCE_SOURCE`;
- snapshot content does not become Decision / Commitment truth without the normal review path.

## 7. Connector permission resolution

Session Policy may request connector permissions.

Preflight resolves them only against connections that are:

```text
status = CONNECTED
AND provider adapter is registered
AND granted scope contains the requested scope
```

A missing scope is a blocker.

There is no:
- silent OAuth scope expansion;
- read→write promotion;
- provider fallback to a broader permission.

## 8. Reviewed write-back boundary

Supported DraftAction mappings:

| DraftAction | Operation | Required scope |
| --- | --- | --- |
| FOLLOWUP_EMAIL_DRAFT | SEND_EMAIL | mail.send |
| CREATE_TASK_DRAFT | CREATE_TASK | tasks.write |
| CREATE_ISSUE_DRAFT | CREATE_ISSUE | issues.write |
| UPDATE_DECISION_LOG_DRAFT | UPDATE_DECISION_LOG | action.execute |

Execution requires:

1. DraftAction status = `APPROVED`;
2. user creates an Execution Request;
3. connection is rechecked;
4. exact write scope is rechecked;
5. adapter availability is rechecked;
6. user performs a second explicit Execute action.

Possible execution states:

```text
PENDING
EXECUTING
SUCCEEDED
FAILED
BLOCKED
CANCELLED
```

Only:

```text
SUCCEEDED + provider response
```

is external-success evidence.

## 9. Idempotency

Execution idempotency key includes:

- draft id;
- draft updated_at;
- connection id;
- operation;
- target.

Creating the same request again returns the existing audit row.

Calling execute on a SUCCEEDED request returns the existing success instead of calling the provider again.

## 10. Failure truth

Failures are first-class audit state.

Examples:

- adapter absent → BLOCKED;
- connection disconnected → BLOCKED;
- missing write scope → BLOCKED;
- DraftAction no longer APPROVED → BLOCKED;
- provider exception → FAILED.

The UI must not turn any of these into “sent” or “created”.

## 11. Retention

Connector snapshots have independent retention:

- Minimum: 7 days;
- Standard: 30 days.

Exceptions:
- a snapshot still selected on the Space is kept;
- a snapshot already frozen into an old Session Pack remains in that Pack;
- external execution audit is kept by ordinary retention;
- a DraftAction with external execution audit is not removed by ordinary draft retention.

Complete Space erase remains the explicit destructive boundary.

## 12. Export

Space / Session export may contain:

- connector snapshot provenance;
- source content hash;
- external id/kind;
- execution request/response audit.

Export must not contain:
- credential_ref;
- access token;
- refresh token;
- client secret;
- raw provider key.

## 13. Adapter interface

A provider adapter implements:

```python
read_snapshots(connection, space_id, cursor, limit)
execute(connection, operation, target, payload, idempotency_key)
```

Read response:

```text
items[]
next_cursor
```

Different providers may map `next_cursor` to:
- Google Calendar sync token;
- Graph delta cursor;
- ETag/page cursor;
- MCP server-defined continuation.

## 14. Current evidence boundary

Allowed after this boundary is green:

```text
INTEGRATION_BOUNDARY_AVAILABLE = TRUE
CONNECTOR_SNAPSHOT_PROVENANCE_AVAILABLE = TRUE
REVIEWED_EXTERNAL_EXECUTION_BOUNDARY_AVAILABLE = TRUE
```

Not allowed without real provider adapters and credentials:

```text
GOOGLE_CALENDAR_CONNECTED = TRUE
GMAIL_CONNECTED = TRUE
MICROSOFT_GRAPH_CONNECTED = TRUE
GITHUB_CONNECTED = TRUE
MCP_CONNECTED = TRUE

MAIL_SENT = TRUE
TASK_CREATED = TRUE
ISSUE_CREATED = TRUE
DECISION_LOG_WRITTEN = TRUE
```

## 15. External design references

The boundary follows provider principles rather than copying provider-specific schemas into Conversation truth:

- Google Calendar incremental synchronization persists a synchronization token between runs.
- Gmail separates readonly and send OAuth scopes.
- Microsoft Graph recommends least-privilege delegated/application permissions and exposes separate read/write permissions.
- GitHub fine-grained access tokens use resource-specific permissions.
- MCP permissions remain adapter/server-defined, but still pass through the same Chengzhu read-source vs explicit-action boundary.

Provider documentation should be re-verified when concrete adapters are implemented because permission names and APIs can change.
