'use strict';

const DEFAULT_LEAD_MINUTES = 10;
const MAX_LEAD_MINUTES = 24 * 60;
const STALE_GRACE_MS = 5 * 60 * 1000;

function clampLeadMinutes(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return DEFAULT_LEAD_MINUTES;
  return Math.max(0, Math.min(MAX_LEAD_MINUTES, Math.round(n)));
}

function normalizeReminder(input, leadMinutes = DEFAULT_LEAD_MINUTES) {
  if (!input || typeof input !== 'object') return null;
  const sessionId = String(input.session_id || input.sessionId || '').trim();
  const spaceId = String(input.space_id || input.spaceId || '').trim();
  const scheduledAt = Number(input.scheduled_at ?? input.scheduledAt);
  if (!sessionId || !spaceId || !Number.isFinite(scheduledAt) || scheduledAt <= 0) return null;
  const lead = clampLeadMinutes(input.lead_minutes ?? input.leadMinutes ?? leadMinutes);
  return {
    session_id: sessionId.slice(0, 160),
    space_id: spaceId.slice(0, 160),
    scheduled_at: scheduledAt,
    lead_minutes: lead,
    notify_at_ms: Math.round(scheduledAt * 1000 - lead * 60 * 1000),
    delivered_at_ms: null,
  };
}

function mergeReminderRegistry(previous, incoming, leadMinutes = DEFAULT_LEAD_MINUTES) {
  const existing = new Map();
  for (const item of Array.isArray(previous) ? previous : []) {
    if (!item || !item.session_id) continue;
    existing.set(String(item.session_id), item);
  }

  const next = [];
  const seen = new Set();
  for (const raw of Array.isArray(incoming) ? incoming : []) {
    const item = normalizeReminder(raw, leadMinutes);
    if (!item || seen.has(item.session_id)) continue;
    seen.add(item.session_id);
    const old = existing.get(item.session_id);
    if (
      old
      && Number(old.scheduled_at) === item.scheduled_at
      && Number(old.lead_minutes) === item.lead_minutes
      && Number.isFinite(Number(old.delivered_at_ms))
    ) {
      item.delivered_at_ms = Number(old.delivered_at_ms);
    }
    next.push(item);
  }
  next.sort((a, b) => a.scheduled_at - b.scheduled_at);
  return next;
}

function dueReminders(registry, nowMs = Date.now()) {
  const due = [];
  for (const item of Array.isArray(registry) ? registry : []) {
    if (!item || item.delivered_at_ms != null) continue;
    const scheduledMs = Number(item.scheduled_at) * 1000;
    const notifyAt = Number(item.notify_at_ms);
    if (!Number.isFinite(scheduledMs) || !Number.isFinite(notifyAt)) continue;
    if (scheduledMs < nowMs - STALE_GRACE_MS) continue;
    if (notifyAt <= nowMs) due.push(item);
  }
  return due;
}

function markDelivered(registry, sessionId, nowMs = Date.now()) {
  return (Array.isArray(registry) ? registry : []).map((item) => (
    item && item.session_id === sessionId
      ? { ...item, delivered_at_ms: nowMs }
      : item
  ));
}

function runtimeSnapshot(registry, supported, enabled) {
  const items = Array.isArray(registry) ? registry : [];
  const pending = items.filter((item) => item && item.delivered_at_ms == null);
  return {
    supported: Boolean(supported),
    enabled: Boolean(enabled),
    scheduled_count: items.length,
    pending_count: pending.length,
    next_notify_at_ms: pending.length
      ? Math.min(...pending.map((item) => Number(item.notify_at_ms)).filter(Number.isFinite))
      : null,
    privacy: 'GENERIC_BODY_NO_SESSION_TITLE',
    source: 'LOCAL_CHENGZHU_SCHEDULE_ONLY',
  };
}

module.exports = {
  DEFAULT_LEAD_MINUTES,
  STALE_GRACE_MS,
  clampLeadMinutes,
  normalizeReminder,
  mergeReminderRegistry,
  dueReminders,
  markDelivered,
  runtimeSnapshot,
};
