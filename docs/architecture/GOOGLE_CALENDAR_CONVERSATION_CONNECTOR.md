# Google Calendar Conversation Connector
## Real read-only provider boundary · 2026-10-10

This document records the implemented Google Calendar provider contract for
Chengzhu v2 Conversation.

## Product boundary

Implemented:

- provider: `GOOGLE_CALENDAR`
- capability: `calendar.read`
- external kind: `CALENDAR_EVENT`
- explicit runtime opt-in:
  `CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE=1`
- opaque credential ref:
  `provider:google-calendar:env:<ENV_VAR>`
- access token resolved only from process environment
- immutable Conversation connector snapshots
- explicit snapshot selection into a Space / Session Pack
- explicit future event → UPCOMING Session import
- native Google Events sync token pagination + 410 reset

Not implemented / not claimed:

- OAuth authorization UI / refresh-token lifecycle
- event.create / event.update / event.delete
- automatic meeting join
- automatic capture
- automatic participant notification
- real Google account evidence in repository CI

## Least privilege

The built-in provider uses:

```text
https://www.googleapis.com/auth/calendar.events.readonly
```

It does not request Calendar write scope.

Official Google scope reference:
https://developers.google.com/workspace/calendar/api/auth

## Connection lifecycle

```text
create local metadata
→ DISCONNECTED
→ Verify (one-page events read probe)
→ CONNECTED
→ explicit Sync
```

Verify is deliberately not a full sync. It proves that the environment-backed
credential can read the configured calendar target (default `primary`).

A later 403/404 for another explicit calendar target is treated as a target
failure, not automatic proof that the whole Google account credential died.
A 401 remains connection-fatal.

## Native sync-token semantics

Google's native Events synchronization contract is used.

Initial sync:

- `singleEvents=true`
- `showDeleted=true`
- bounded initial history: `timeMin = now - 365 days`
- paginate every page
- save `nextSyncToken` only from the final page

Incremental sync:

- use only the stored `syncToken` plus compatible pagination parameters
- paginate to the final page
- save the replacement `nextSyncToken`

HTTP 410:

```text
expired/invalid sync token
→ reset only calendar.read capability cursor
→ one full resync
→ advance cursor only after full result succeeds
```

Official Google reference:
https://developers.google.com/workspace/calendar/api/guides/sync

## No partial cursor advancement

Chengzhu's generic connector boundary accepts at most 500 snapshots per Calendar
sync transaction. The provider still reads the complete Google change set.

If the complete change set exceeds the safe snapshot write bound:

```text
FAIL ENTIRE SYNC
DO NOT SAVE nextSyncToken
DO NOT CLAIM COMPLETE
```

This prevents the dangerous state:

```text
store first N rows
+ save final provider cursor
= permanently skip the rest
```

## Calendar-target-bound cursor

A Google sync token belongs to one calendar collection. Chengzhu wraps it in an
opaque target-bound cursor envelope:

```text
{ version, calendar_id, sync_token }
```

Changing from `primary` to another calendar id therefore starts a full sync;
a token from one target is never reused on another target.

## Immutable event snapshots

Normalized snapshot carries:

- calendar id
- event id
- title
- description excerpt
- status / cancelled
- start / end
- location
- organizer
- bounded attendee metadata
- hangout link
- updated timestamp
- recurring event id
- provider event URL (query stripped by the generic snapshot boundary)

Snapshot authority remains:

```text
REFERENCE_SOURCE
```

A Calendar event is not automatically a Decision, Commitment, Deadline or truth
claim.

## Event → Next Session import

The user may explicitly choose a future, non-cancelled `CALENDAR_EVENT`
snapshot in the current Space and select **作为下一场**.

The import:

- validates Space ownership
- validates Google provider provenance
- validates `calendar.read`
- rejects cancelled/past events
- creates one UPCOMING Conversation Session
- stores `source_calendar_event` provenance
- selects the immutable snapshot into the Space
- is idempotent per snapshot

After import, future provider syncs do not silently rewrite that Session's title
or scheduled time.

## Evidence boundary

Repository tests may prove:

- adapter contract
- fake-transport HTTP behavior
- pagination
- sync-token replacement
- 410 reset
- target-bound cursor
- immutable snapshots
- Calendar event → Next Session product flow

Repository tests cannot prove:

- a real user granted Google OAuth consent
- a real Google Calendar was read
- a real event was imported from a user's account

Those require an explicit local/account replay and must remain separately
labelled as external evidence.
