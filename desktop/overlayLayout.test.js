'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { computeOverlayBounds, interactionFlags, normalizeLayout } = require('./overlayLayout');

const primary = { x: 0, y: 0, width: 1920, height: 1040 };
const secondary = { x: 1920, y: 0, width: 1280, height: 680 }; // e.g. a 150% DPI laptop panel in DIP

test('dock positions stay inside the work area of the overlay display', () => {
  for (const area of [primary, secondary]) {
    for (const dock of ['TOP', 'LEFT', 'RIGHT', 'FREE']) {
      for (const size of ['COMPACT', 'STANDARD', 'FOCUS']) {
        const b = computeOverlayBounds(area, { dock, size }, { x: area.x + 50, y: area.y + 50, width: 10, height: 10 });
        assert.ok(b.x >= area.x && b.y >= area.y, `${dock}/${size} origin`);
        assert.ok(b.x + b.width <= area.x + area.width, `${dock}/${size} right edge`);
        assert.ok(b.y + b.height <= area.y + area.height, `${dock}/${size} bottom edge`);
      }
    }
  }
});

test('top dock is centred, right dock hugs the right edge', () => {
  const top = computeOverlayBounds(primary, { dock: 'TOP', size: 'COMPACT' });
  assert.equal(top.y, 12);
  assert.equal(top.x, Math.round((1920 - top.width) / 2));
  const right = computeOverlayBounds(secondary, { dock: 'RIGHT', size: 'STANDARD' });
  assert.equal(right.x + right.width, secondary.x + secondary.width - 12);
});

test('compact is a single strip, focus is large', () => {
  const compact = computeOverlayBounds(primary, { size: 'COMPACT' });
  const focus = computeOverlayBounds(primary, { size: 'FOCUS' }, null, { widthPct: 60, heightPct: 55 });
  assert.ok(compact.height <= 56);
  assert.ok(focus.width > 1000 && focus.height > 500);
});

test('free dock keeps the user position but clamps off-screen positions', () => {
  const kept = computeOverlayBounds(primary, { dock: 'FREE', size: 'STANDARD' }, { x: 300, y: 200, width: 1, height: 1 });
  assert.deepEqual([kept.x, kept.y], [300, 200]);
  const clamped = computeOverlayBounds(primary, { dock: 'FREE', size: 'STANDARD' }, { x: 5000, y: -400, width: 1, height: 1 });
  assert.ok(clamped.x + clamped.width <= 1920 && clamped.y >= 0);
});

test('passive overlays are click-through; neither mode steals keyboard focus', () => {
  assert.deepEqual(interactionFlags('PASSIVE'), { ignoreMouseEvents: true, focusable: false });
  assert.deepEqual(interactionFlags('INTERACTIVE'), { ignoreMouseEvents: false, focusable: false });
  assert.deepEqual(normalizeLayout({ dock: 'BOTTOM', size: 'HUGE' }), { dock: 'FREE', interaction: 'INTERACTIVE', size: 'STANDARD' });
});

test('v1.2 bounds logic stays in charge for free standard/focus overlays', () => {
  const { layoutOwnsBounds } = require('./overlayLayout');
  assert.equal(layoutOwnsBounds({ dock: 'FREE', size: 'STANDARD' }), false);
  assert.equal(layoutOwnsBounds({ dock: 'FREE', size: 'COMPACT' }), true);
  assert.equal(layoutOwnsBounds({ dock: 'TOP', size: 'FOCUS' }), true);
});
