# Local Markdown / Obsidian Conversation Decision Log Connector

**Status**: RUNTIME_AVAILABLE_OPT_IN  
**Provider ID**: `LOCAL_MARKDOWN`  
**Capability**: `decision_log.write` only  
**Read capability**: none  
**Account model**: local authorized root directory, not a cloud account

---

## 1. Why this provider exists

Conversation already has reviewed local DraftActions for:

- follow-up email;
- task;
- issue;
- decision log.

Concrete providers existed for Gmail, Microsoft To Do and GitHub, but
`UPDATE_DECISION_LOG_DRAFT → decision_log.write` still stopped at the local
review boundary.

The Local Markdown provider closes that final execution category without
requiring a cloud service or widening Chengzhu into a generic filesystem agent.

Typical destinations include:

- an Obsidian vault subdirectory;
- a local Git repository containing project decision records;
- a plain Markdown notes folder.

The provider never reads or indexes those folders.

---

## 2. Explicit opt-in

The adapter registers only when:

```text
CHENGZHU_LOCAL_MARKDOWN_CONNECTOR_ENABLE=1
```

The authorized root path is supplied through a separate process environment
variable selected by the user, for example:

```text
CHENGZHU_DECISION_LOG_ROOT=D:\Notes\MyVault
```

Product metadata stores only:

```text
provider:local-markdown:env:CHENGZHU_DECISION_LOG_ROOT
```

The resolved filesystem path never enters:

- product.db;
- frontend state;
- export;
- execution response;
- connector audit.

Verify returns only a non-sensitive root basename as `account_hint`.

---

## 3. Least-privilege contract

The exact capability is:

```text
decision_log.write
```

The canonical provider scope is:

```text
local.filesystem.markdown.write
```

It does **not** implement:

- `docs.read`;
- vault search;
- filesystem enumeration;
- recursive indexing;
- arbitrary file write;
- delete;
- rename;
- shell execution;
- Git commit/push;
- background sync.

A Local Markdown connection therefore cannot be used as a Session read source.

---

## 4. Reviewed execution flow

```text
reviewed Conversation Decision
→ UPDATE_DECISION_LOG_DRAFT
→ user reviews local draft
→ APPROVED
→ select exact LOCAL_MARKDOWN connection
→ explicit relative .md target
→ Execution Request
→ second explicit Execute
→ provider result
```

`APPROVED` does not write a file.

Creating an Execution Request does not write a file.

Only the second explicit Execute may perform the filesystem side effect.

---

## 5. Target boundary

Target examples:

```text
decisions.md
Projects/Alpha/Decisions.md
ADR/2026/decisions.md
```

Rejected:

```text
../outside.md
/absolute/path.md
C:\absolute\path.md
notes.txt
symlinked.md
```

Rules:

- target must be relative to the authorized root;
- `.md` only;
- absolute paths are rejected;
- `..` is rejected;
- backslash target syntax is rejected so one canonical relative form is used;
- existing symlink file targets are rejected;
- resolved parent directories must remain inside the authorized root;
- an existing target larger than 10 MiB is rejected before content is read.

This provider is intentionally not a general file picker.

---

## 6. Reviewed-content integrity

The shared execution boundary sanitizes outbound payloads before provider
execution.

If that safety layer changed the reviewed DraftAction
(`outbound_redaction_applied=true`), Local Markdown returns a definitive
failure and writes nothing.

Reason:

> a local file should not silently contain a different decision record than the
> user actually reviewed.

The user must edit/re-review the DraftAction and create a new Execution Request.

The provider also rejects over-limit title/body content instead of silently
truncating it.

---

## 7. Atomic write and provider-level idempotency

Each execution appends an audit marker:

```html
<!-- chengzhu-execution:<idempotency_key> -->
```

followed by the reviewed title and body.

Write sequence:

```text
read current target
→ prepare candidate in same-directory temp file
→ fsync temp file
→ recheck source file did not change
→ os.replace(temp, target)
→ verify marker exists
```

Because the temp file is on the same filesystem, `os.replace` is the provider's
atomic commit boundary.

Before appending, the provider checks for the execution marker. If it already
exists, Execute returns:

```text
ok=true
deduplicated=true
provider_idempotency=MARKER_IN_FILE
```

without appending the entry again.

This is real provider-level idempotency, unlike providers where the Chengzhu
idempotency key exists only in local audit.

---

## 8. Failure semantics

### Definitive pre-write failure

Examples:

- invalid relative target;
- path escape;
- non-Markdown target;
- symlink target;
- oversized existing file;
- reviewed payload changed by redaction.

These return `ok=false`.

Where no file side effect happened and retry after fixing input is safe, the
provider may return `retry_safe=true`.

### Ambiguous outcome

If an exception occurs after the atomic replace may already have happened, it
bubbles to the shared integration boundary.

The shared boundary records:

```text
UNKNOWN_OUTCOME
```

and forbids automatic retry.

The user must inspect the Markdown target and use the existing provider-side
reconciliation flow.

The execution marker makes that reconciliation practical.

---

## 9. Privacy / provenance

The written Markdown derives only from an already reviewed Decision Log
DraftAction.

The provider does not:

- promote an AI candidate into truth;
- read arbitrary local files;
- inspect unrelated vault notes;
- infer a decision from filesystem content;
- silently change Conversation truth after a write.

The execution audit preserves:

- DraftAction id;
- exact connection;
- capability;
- operation;
- relative target;
- idempotency key;
- provider result;
- content SHA-256.

The absolute root remains outside that audit.

---

## 10. What this closes

After this provider is merged, repo engineering truth may state:

```text
LOCAL_MARKDOWN_DECISION_LOG_ADAPTER = RUNTIME_AVAILABLE_OPT_IN
DECISION_LOG_WRITE_PROVIDER = AVAILABLE_LOCAL_OPT_IN
REVIEWED_DECISION_LOG_SECOND_STEP_EXECUTION = IMPLEMENTED
```

This does **not** imply:

```text
MCP_PROVIDER_CONFIGURED = TRUE
OBSIDIAN_VAULT_READ = TRUE
GENERIC_FILESYSTEM_ACCESS = TRUE
V2_STABLE_RELEASE = TRUE
REAL_USER_VALUE_PROVEN = TRUE
```

Stable promotion and real-user gates remain unchanged.
