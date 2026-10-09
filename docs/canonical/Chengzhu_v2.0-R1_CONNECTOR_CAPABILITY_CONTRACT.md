# Chengzhu v2 Conversation Connector Capability Contract
## Post-beta.2 external integration boundary

**Status**: DESIGN COMPLETE / EXECUTABLE REGISTRY AVAILABLE / NO PROVIDER CLAIMED  
**Applies to**: Calendar, Docs, Mail, project tracker, external write-back

---

## 1. Why this exists

beta.2 correctly fails closed when `connector_permissions` is non-empty, but a permanent blanket blocker is not a scalable integration model.

The connector boundary is now:

```text
Session Policy asks for capability
→ runtime capability registry resolves exact provider
→ Preflight either grants exact capability or blocks
→ grant is frozen into Session Pack
→ read data enters provenance as a source
```

No provider registration means no permission grant.

This does **not** mean Calendar / Mail / Docs / project-tracker integrations already exist.

---

## 2. Capability vocabulary

Read-only Session capabilities:

- `calendar.read`
- `docs.read`
- `mail.read`
- `project.read`

Reviewed execution capabilities:

- `email.send`
- `task.create`
- `issue.create`
- `decision_log.write`

Unknown strings are rejected.

---

## 3. Hard separation: read vs write

Session Policy `connector_permissions` is read-only.

It may never grant:

```text
email.send
task.create
issue.create
decision_log.write
```

A provider advertising write capabilities is still insufficient. Write execution must use a separate flow:

```text
Conversation Item / Continue
→ DraftAction
→ explicit user review
→ explicit target/provider
→ capability re-check
→ explicit execute
→ provider result/failure
→ immutable audit event
```

No “approved draft means external write succeeded”.

---

## 4. Provider registration truth

A real integration registers:

- provider_id;
- exact capabilities;
- runtime health;
- optional user-facing account label.

Registry rules:

- process-local capability truth;
- default empty registry;
- health must be `AVAILABLE` to grant;
- no token, OAuth secret, refresh token or external message body is stored in the registry;
- multiple providers may advertise the same capability;
- deterministic provider resolution is required;
- provider-specific auth/session state stays in that provider's integration layer.

---

## 5. Preflight

For every requested read capability Preflight must expose:

- requested capability;
- selected provider if available;
- blocked reason if unavailable;
- provider health;
- account label if explicitly safe to display.

Blocked reasons include:

- `UNKNOWN_CAPABILITY`;
- `NO_AVAILABLE_PROVIDER`;
- `WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW`.

Any blocked requested capability blocks Session start.

No placeholder provider can satisfy Preflight.

---

## 6. Session Pack

The frozen Pack must contain the connector resolution used at start:

- requested permissions;
- exact grants;
- provider ids;
- safe account labels;
- blocked list (normally empty for a started Session);
- registry health snapshot.

Changing provider/account/config after start does not silently rewrite the running Session Pack.

A future connector-sourced observation must point back to:

- capability;
- provider;
- external object id / immutable version where available;
- retrieval timestamp;
- visibility;
- content hash/version if supported.

---

## 7. Read data truth

Connector content is a **source**, not organizational truth.

Examples:

```text
Calendar event title
!= confirmed Decision

Mail sentence
!= confirmed Commitment

Project issue due date
!= reviewed Chengzhu Deadline
```

Promotion still follows Conversation review rules.

---

## 8. Failure and revocation

If a provider becomes unhealthy or authorization is revoked:

- new Preflight fails closed;
- running Session keeps its frozen Pack;
- new remote reads fail explicitly;
- no cached provider state is silently treated as fresh;
- external execution is not retried without explicit semantics;
- diagnostics must show the provider/capability degradation.

---

## 9. Privacy

Provider registry must never include:

- access tokens;
- refresh tokens;
- API keys;
- message bodies;
- document bodies;
- hidden personal identifiers not already intentionally exposed as account labels.

Connector raw data retention follows source-specific retention policy and user authorization.

---

## 10. Current repo truth

Allowed claim:

```text
CONNECTOR_CAPABILITY_CONTRACT = IMPLEMENTED
CONNECTOR_REGISTRY_DEFAULT = FAIL_CLOSED
```

Not allowed yet:

```text
CALENDAR_CONNECTOR_AVAILABLE = TRUE
MAIL_CONNECTOR_AVAILABLE = TRUE
DOCS_CONNECTOR_AVAILABLE = TRUE
PROJECT_TRACKER_CONNECTOR_AVAILABLE = TRUE
EXTERNAL_WRITEBACK_AVAILABLE = TRUE
```

Those require a real provider, authorization, runtime tests and external result evidence.
