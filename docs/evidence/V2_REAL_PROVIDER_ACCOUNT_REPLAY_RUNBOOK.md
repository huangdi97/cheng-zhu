# Chengzhu v2 Real Provider Account Replay Runbook

**Status**: SOURCE-SIDE OPERATOR TOOLING  
**Public Conversation Beta**: v2.0.0-beta.5  
**Purpose**: close real-provider account evidence without weakening credential, write-action or release truth boundaries.

Tool:

`scripts/v2_real_provider_account_replay.py`

The harness launches an isolated temporary Chengzhu backend with a local fake model provider. The only intended external network traffic is the selected connector provider.

## 1. Evidence classes

A run may produce one of three positive evidence classes:

```text
PASS_REAL_ACCOUNT_AUTH_PRODUCT_REPLAY_WRITE_NOT_EXECUTED
PASS_REAL_ACCOUNT_READ_PRODUCT_REPLAY
PASS_REAL_ACCOUNT_WRITE_PRODUCT_REPLAY
```

They are not interchangeable.

### Account auth only

For Gmail / Microsoft To Do, a default run verifies the real account/provider capability needed by `health()`, creates a local reviewed Draft, and stops **before external execution**.

This proves:

```text
REAL_ACCOUNT_AUTH_VALIDATED = TRUE
REAL_PROVIDER_WRITE_REPLAY_VALIDATED = FALSE
```

It does not prove that a Gmail message or Microsoft task was created.

### Real read replay

For Calendar / Drive:

```text
real account verify
→ real provider read
→ immutable Connector Snapshot
→ select into Space
→ frozen Session Pack
→ token absence checks
```

This may set:

```text
REAL_ACCOUNT_AUTH_VALIDATED = TRUE
REAL_PROVIDER_READ_REPLAY_VALIDATED = TRUE
```

### Real write replay

For Gmail / Microsoft To Do, a real external side effect requires both:

```text
--execute-write
--confirm-write <exact marker>
```

Only a provider `SUCCEEDED` result may set:

```text
REAL_PROVIDER_WRITE_REPLAY_VALIDATED = TRUE
```

## 2. Credential handling

Pass the **name** of an environment variable, never the access token on the command line.

Examples below use illustrative variable names. The actual token remains only in the parent/child process environment.

The replay report never intentionally contains:

- raw access token;
- raw account identity;
- raw recipient;
- provider object id;
- Calendar event title/body;
- Drive file title/content;
- backend log content.

The harness scans the isolated `product.db` and Space export to ensure the credential value was not persisted.

If the environment variable is absent, the result is:

```text
BLOCKED_ACCOUNT
REAL_ACCOUNT_AUTH_VALIDATED = FALSE
```

That is not a failed provider implementation and must not be rewritten as PASS.

## 3. Google Calendar — read only

Adapter contract:

```text
provider_id = GOOGLE_CALENDAR
capability = calendar.read
write = unsupported
```

Example:

```bash
export GOOGLE_CALENDAR_ACCESS_TOKEN="..."
python scripts/v2_real_provider_account_replay.py \
  --provider google-calendar \
  --token-env GOOGLE_CALENDAR_ACCESS_TOKEN \
  --target primary \
  --out artifacts/runtime-evidence/real-providers/google-calendar.json
```

`--target` is a Calendar id; `primary` is supported.

The selected Calendar must contain at least one readable event in the adapter's bounded initial-sync window if the run is to prove snapshot/frozen-pack replay.

If a high-volume Calendar exceeds Chengzhu's current safe sync limit, use a dedicated test Calendar rather than raising/truncating the limit.

No Calendar create/update/delete is performed.

## 4. Google Drive — read only

Adapter contract:

```text
provider_id = GOOGLE_DRIVE
capability = docs.read
write = unsupported
sync = explicit folder direct-children refresh
```

Example:

```bash
export GOOGLE_DRIVE_ACCESS_TOKEN="..."
python scripts/v2_real_provider_account_replay.py \
  --provider google-drive \
  --token-env GOOGLE_DRIVE_ACCESS_TOKEN \
  --target <TEST_FOLDER_ID> \
  --out artifacts/runtime-evidence/real-providers/google-drive.json
```

Use a dedicated small test folder containing at least one readable file.

The harness intentionally fails rather than turning an incomplete/oversized folder read into a fake "complete" snapshot set.

## 5. Gmail — send only

Adapter contract:

```text
provider_id = GOOGLE_MAIL
capability = email.send
mail.read = unsupported
provider-side idempotency = NONE
```

Required adapter scopes are the repository contract:

```text
openid
email
https://www.googleapis.com/auth/gmail.send
```

### Safe default: account probe, no email

```bash
export CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN="..."
python scripts/v2_real_provider_account_replay.py \
  --provider google-mail \
  --token-env CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN \
  --out artifacts/runtime-evidence/real-providers/gmail-auth.json
```

This does **not** send a message.

### Explicit real send

Use only a test recipient that is authorized to receive the replay message:

```bash
python scripts/v2_real_provider_account_replay.py \
  --provider google-mail \
  --token-env CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN \
  --target replay-recipient@example.test \
  --execute-write \
  --confirm-write SEND_EMAIL \
  --write-title "Chengzhu Gmail real-provider replay" \
  --write-body "Explicit test message for Chengzhu provider replay." \
  --out artifacts/runtime-evidence/real-providers/gmail-send.json
```

Gmail `messages.send` has no provider-side idempotency primitive in this adapter.

If a real send ends with an ambiguous/unknown outcome, **do not automatically rerun the same write**. Investigate/reconcile first.

A successful real replay still does not prove Google public OAuth verification / sensitive-scope publication approval. The report keeps:

```text
GOOGLE_OAUTH_PUBLICATION_VERIFIED = FALSE
```

unless that external gate is evidenced separately.

## 6. Microsoft To Do — task.create only

Adapter contract:

```text
provider_id = MICROSOFT_GRAPH
capability = task.create
delegated permission = Tasks.ReadWrite
task read sync = unsupported
provider-side idempotency = NONE
```

### Safe default: account/list probe, no task create

```bash
export CHENGZHU_MICROSOFT_TODO_TOKEN="..."
python scripts/v2_real_provider_account_replay.py \
  --provider microsoft-todo \
  --token-env CHENGZHU_MICROSOFT_TODO_TOKEN \
  --out artifacts/runtime-evidence/real-providers/microsoft-todo-auth.json
```

### Explicit real task creation

```bash
python scripts/v2_real_provider_account_replay.py \
  --provider microsoft-todo \
  --token-env CHENGZHU_MICROSOFT_TODO_TOKEN \
  --target default \
  --execute-write \
  --confirm-write CREATE_TASK \
  --write-title "Chengzhu Microsoft To Do replay" \
  --write-body "Explicit test task created by the real-provider replay." \
  --out artifacts/runtime-evidence/real-providers/microsoft-todo-create.json
```

`--target default` resolves the built-in default Tasks list; an explicit list id is also supported.

The created task is a real side effect. The harness deliberately does not execute the same request twice because the provider contract does not offer idempotent task creation.

## 7. Why the harness starts a real Chengzhu backend

Directly calling an adapter would only prove transport code.

This harness verifies the product boundary:

```text
connector opt-in gate
→ catalog registration
→ opaque credential_ref
→ real account verify
→ Connection state

READ:
→ real sync
→ immutable snapshots
→ Space selection
→ frozen Session Pack

WRITE:
→ local Draft
→ explicit APPROVE
→ explicit Execution Request
→ one real provider execute

ALL:
→ audit/provenance checks
→ credential absence from product.db/export
```

The backend uses an isolated temporary `CHENGZHU_HOME`, so replay data does not pollute the user's normal Chengzhu database.

## 8. What the report still cannot prove

Even a full PASS does not establish:

```text
REAL_USER_VALIDATED = TRUE
V2_STABLE_RELEASE = TRUE
PMF_PROVEN = TRUE
GOOGLE_OAUTH_PUBLICATION_VERIFIED = TRUE
```

It is connector/provider engineering evidence only.

Provider replay should be paired with the separate Real Pilot evidence flow when evaluating stable product readiness.

## 9. Current expected evidence status

Before an operator runs the harness with real credentials:

```text
GitHub real account replay = PASS (existing evidence)
Google Calendar real account replay = PENDING
Google Drive real account replay = PENDING
Gmail real account replay = PENDING
Microsoft To Do real account replay = PENDING
```

Source-side tooling availability is not provider evidence.
