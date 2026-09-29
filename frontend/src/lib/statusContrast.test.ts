// R2 Stage Z: every semantic status color must reach WCAG AA (4.5:1) for body
// text against the primary, secondary (Surface) and tertiary (SurfaceAlt)
// backgrounds of every theme. Parses index.css so the check cannot drift.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(__dirname, '../index.css'), 'utf-8')

type Rgb = [number, number, number]

function blocks(): Array<{ selectors: string[]; vars: Record<string, Rgb> }> {
  const out: Array<{ selectors: string[]; vars: Record<string, Rgb> }> = []
  const re = /([^{}]+)\{([^{}]*)\}/g
  let match: RegExpExecArray | null
  while ((match = re.exec(css))) {
    const selectors = match[1].split(',').map((s) => s.replace(/\/\*[\s\S]*?\*\//g, '').trim()).filter(Boolean)
    const vars: Record<string, Rgb> = {}
    for (const line of match[2].split(';')) {
      const m = /--c-([a-z-]+):\s*(\d+)\s+(\d+)\s+(\d+)/.exec(line)
      if (m) vars[m[1]] = [Number(m[2]), Number(m[3]), Number(m[4])]
    }
    if (Object.keys(vars).length) out.push({ selectors, vars })
  }
  return out
}

function themeVars(): Record<string, Record<string, Rgb>> {
  const themes: Record<string, Record<string, Rgb>> = {}
  for (const { selectors, vars } of blocks()) {
    for (const sel of selectors) {
      const m = /data-theme='([^']+)'/.exec(sel)
      const key = m ? m[1] : sel === ':root' ? 'vscode-light-plus' : ''
      if (!key) continue
      themes[key] = { ...(themes[key] ?? {}), ...vars }
    }
  }
  return themes
}

function luminance([r, g, b]: Rgb): number {
  const lin = (c: number) => {
    const v = c / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

export function contrast(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const STATUS = ['status-direct', 'status-supported', 'status-inferred', 'status-unknown', 'status-risk']
const SURFACES = ['bg-primary', 'bg-secondary', 'bg-tertiary']

describe('status colors meet WCAG AA on every theme surface', () => {
  const themes = themeVars()
  it('parses all themes', () => {
    expect(Object.keys(themes).length).toBeGreaterThanOrEqual(6)
  })
  for (const [theme, vars] of Object.entries(themes)) {
    for (const status of STATUS) {
      it(`${theme} ${status}`, () => {
        expect(vars[status], `${theme} is missing --c-${status}`).toBeDefined()
        for (const surface of SURFACES) {
          const ratio = contrast(vars[status], vars[surface])
          expect(ratio, `${theme} ${status} on ${surface} = ${ratio.toFixed(2)}`).toBeGreaterThanOrEqual(4.5)
        }
      })
    }
  }
})
