'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  DEFAULT_LEAD_MINUTES,
  normalizeReminder,
  mergeReminderRegistry,
  dueReminders,
  markDelivered,
  runtimeSnapshot,
} = require('./conversationReminders');

test('normalizes a reminder without retaining private titles', () => {
  const item = normalizeReminder({
    session_id: 'cs_1',
    space_id: 'sp_1',
    scheduled_at: 2_000,
    title: 'Secret Client Negotiation',
    space_title: 'Acme',
  });
  assert.equal(item.session_id, 'cs_1');
  assert.equal(item.space_id, 'sp_1');
  assert.equal(item.lead_minutes, DEFAULT_LEAD_MINUTES);
  assert.equal(item.notify_at_ms, (2_000 * 1000) - DEFAULT_LEAD_MINUTES * 60 * 1000);
  assert.equal('title' in item, false);
  assert.equal('space_title' in item, false);
});

test('preserves delivered state only while schedule and lead are unchanged', () => {
  const previous = [{
    session_id: 'cs_1',
    space_id: 'sp_1',
    scheduled_at: 2_000,
    lead_minutes: 10,
    notify_at_ms: 1_400_000,
    delivered_at_ms: 1_450_000,
  }];
  const same = mergeReminderRegistry(previous, [{ session_id: 'cs_1', space_id: 'sp_1', scheduled_at: 2_000 }]);
  assert.equal(same[0].delivered_at_ms, 1_450_000);

  const moved = mergeReminderRegistry(previous, [{ session_id: 'cs_1', space_id: 'sp_1', scheduled_at: 2_600 }]);
  assert.equal(moved[0].delivered_at_ms, null);
});

test('returns only pending reminders that are due and not stale', () => {
  const now = 1_000_000;
  const due = dueReminders([
    { session_id: 'due', scheduled_at: 1_100, notify_at_ms: 900_000, delivered_at_ms: null },
    { session_id: 'future', scheduled_at: 2_000, notify_at_ms: 1_500_000, delivered_at_ms: null },
    { session_id: 'done', scheduled_at: 1_100, notify_at_ms: 900_000, delivered_at_ms: 950_000 },
    { session_id: 'stale', scheduled_at: 100, notify_at_ms: 0, delivered_at_ms: null },
  ], now);
  assert.deepEqual(due.map((x) => x.session_id), ['due']);
});

test('marks a reminder delivered and exposes privacy-safe runtime state', () => {
  const registry = [{
    session_id: 'cs_1',
    space_id: 'sp_1',
    scheduled_at: 2_000,
    lead_minutes: 10,
    notify_at_ms: 1_400_000,
    delivered_at_ms: null,
  }];
  const marked = markDelivered(registry, 'cs_1', 1_450_000);
  assert.equal(marked[0].delivered_at_ms, 1_450_000);

  const snapshot = runtimeSnapshot(registry, true, true);
  assert.equal(snapshot.supported, true);
  assert.equal(snapshot.enabled, true);
  assert.equal(snapshot.pending_count, 1);
  assert.equal(snapshot.privacy, 'GENERIC_BODY_NO_SESSION_TITLE');
  assert.equal(snapshot.source, 'LOCAL_CHENGZHU_SCHEDULE_ONLY');
});
