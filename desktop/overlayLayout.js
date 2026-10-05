'use strict';

/**
 * v1.3 Overlay 3.0 layout: Dock (TOP / LEFT / RIGHT / FREE) × Interaction
 * (PASSIVE / INTERACTIVE) × Size (COMPACT / STANDARD / FOCUS).
 *
 * Pure functions so the geometry is unit-testable without Electron. Bounds are
 * computed inside the work area of the display the overlay is on, so docking
 * works per monitor and with any DPI scaling (Electron work areas are already
 * in DIP).
 */

const DOCKS = ['TOP', 'LEFT', 'RIGHT', 'FREE'];
const INTERACTIONS = ['PASSIVE', 'INTERACTIVE'];
const SIZES = ['COMPACT', 'STANDARD', 'FOCUS'];
const MARGIN = 12;

const SIZE_PRESETS = {
  COMPACT: { width: 420, height: 48 },
  STANDARD: { width: 560, height: 320 },
};

function normalizeLayout(raw = {}) {
  const dock = DOCKS.includes(raw.dock) ? raw.dock : 'FREE';
  const interaction = INTERACTIONS.includes(raw.interaction) ? raw.interaction : 'INTERACTIVE';
  const size = SIZES.includes(raw.size) ? raw.size : 'STANDARD';
  return { dock, interaction, size };
}

function sizeFor(size, workArea, focusPct = {}) {
  if (size === 'FOCUS') {
    const w = Math.max(50, Math.min(100, Number(focusPct.widthPct) || 60));
    const h = Math.max(35, Math.min(100, Number(focusPct.heightPct) || 55));
    return {
      width: Math.round((workArea.width - MARGIN * 2) * (w / 100)),
      height: Math.round((workArea.height - MARGIN * 2) * (h / 100)),
    };
  }
  const preset = SIZE_PRESETS[size] || SIZE_PRESETS.STANDARD;
  return {
    width: Math.min(preset.width, workArea.width - MARGIN * 2),
    height: Math.min(preset.height, workArea.height - MARGIN * 2),
  };
}

/**
 * @param {{x:number,y:number,width:number,height:number}} workArea display work area (DIP)
 * @param {{dock?:string,size?:string}} layout
 * @param {{x:number,y:number,width:number,height:number}|null} current current overlay bounds (FREE keeps position)
 */
function computeOverlayBounds(workArea, layout, current = null, focusPct = {}) {
  const { dock, size } = normalizeLayout(layout);
  const { width, height } = sizeFor(size, workArea, focusPct);
  let x;
  let y;
  if (dock === 'TOP') {
    x = workArea.x + Math.round((workArea.width - width) / 2);
    y = workArea.y + MARGIN;
  } else if (dock === 'LEFT') {
    x = workArea.x + MARGIN;
    y = workArea.y + Math.round((workArea.height - height) / 3);
  } else if (dock === 'RIGHT') {
    x = workArea.x + workArea.width - width - MARGIN;
    y = workArea.y + Math.round((workArea.height - height) / 3);
  } else if (current) {
    // FREE: keep the user's position, clamp into the work area
    x = Math.max(workArea.x + MARGIN / 2, Math.min(current.x, workArea.x + workArea.width - width - MARGIN / 2));
    y = Math.max(workArea.y + MARGIN / 2, Math.min(current.y, workArea.y + workArea.height - height - MARGIN / 2));
  } else {
    x = workArea.x + Math.round((workArea.width - width) / 2);
    y = workArea.y + Math.round(workArea.height * 0.12);
  }
  return { x: Math.round(x), y: Math.round(y), width: Math.round(width), height: Math.round(height) };
}

/**
 * Passive overlays let clicks through to the meeting app; interactive ones
 * accept clicks. Neither takes keyboard focus away from the meeting app
 * (keyboard control stays on global shortcuts), as in v1.2.
 */
function interactionFlags(interaction) {
  const passive = normalizeLayout({ interaction }).interaction === 'PASSIVE';
  return { ignoreMouseEvents: passive, focusable: false };
}

/** Whether the layout should override the v1.2 per-mode bounds logic. */
function layoutOwnsBounds(layout) {
  const { dock, size } = normalizeLayout(layout);
  return dock !== 'FREE' || size === 'COMPACT';
}

module.exports = { DOCKS, INTERACTIONS, SIZES, normalizeLayout, computeOverlayBounds, interactionFlags, layoutOwnsBounds, sizeFor };
