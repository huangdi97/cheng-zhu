/**
 * v1.3 object-centric hash router.
 *
 * Routes (canonical §3): /home · /goals · /goals/:id[/prepare|/interviews|/offer] · /me[/:tab] ·
 * /practice[/:practiceId] · /library[/:tab] · /history · /reflection/:kind/:ref · /settings[/:group] ·
 * /live[/:sessionId]
 *
 * Compatibility: the v1.2 `appMode` keeps working through a route adapter —
 * legacy callers still call `setAppMode('job-tracker')`, which navigates to
 * `/goals`. Nothing here imports UI stores, so stores can depend on it.
 */
import { create } from 'zustand'

export type RouteName =
  | 'home'
  | 'goals'
  | 'goal'
  | 'me'
  | 'practice'
  | 'library'
  | 'history'
  | 'reflection'
  | 'settings'
  | 'live'

export type GoalTab = 'overview' | 'prepare' | 'interviews' | 'offer'

export interface Route {
  name: RouteName
  path: string
  params: Record<string, string>
  query: Record<string, string>
}

export type LegacyMode = 'home' | 'assist' | 'review' | 'knowledge' | 'resume-opt' | 'job-tracker' | 'prep'

const GOAL_TABS: GoalTab[] = ['overview', 'prepare', 'interviews', 'offer']

function parseQuery(raw: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const part of raw.split('&')) {
    if (!part) continue
    const [k, v = ''] = part.split('=')
    try {
      out[decodeURIComponent(k)] = decodeURIComponent(v)
    } catch {
      out[k] = v
    }
  }
  return out
}

export function parsePath(input: string): Route {
  const raw = (input || '').replace(/^#/, '') || '/home'
  const [pathPart, queryPart = ''] = raw.split('?')
  const segs = pathPart.split('/').filter(Boolean).map((s) => {
    try {
      return decodeURIComponent(s)
    } catch {
      return s
    }
  })
  const query = parseQuery(queryPart)
  const path = '/' + segs.map(encodeURIComponent).join('/')
  const route = (name: RouteName, params: Record<string, string> = {}): Route => ({ name, path, params, query })
  switch (segs[0]) {
    case 'goals':
      if (segs[1]) {
        const tab = (GOAL_TABS as string[]).includes(segs[2] ?? '') ? segs[2] : 'overview'
        return route('goal', { goalId: segs[1], tab })
      }
      return route('goals')
    case 'me':
      return route('me', { tab: segs[1] ?? 'overview' })
    case 'practice':
      return route('practice', segs[1] ? { practiceId: segs[1] } : {})
    case 'library':
      return route('library', { tab: segs[1] ?? 'materials' })
    case 'history':
      return route('history')
    case 'reflection':
      return route('reflection', { kind: (segs[1] ?? 'practice').toUpperCase(), ref: segs[2] ?? '' })
    case 'settings':
      return route('settings', { group: segs[1] ?? 'general' })
    case 'live':
      return route('live', segs[1] ? { sessionId: segs[1] } : {})
    case 'home':
    default:
      return { name: 'home', path: '/home', params: {}, query }
  }
}

export const paths = {
  home: () => '/home',
  goals: () => '/goals',
  goal: (goalId: string, tab: GoalTab = 'overview') => (tab === 'overview' ? `/goals/${encodeURIComponent(goalId)}` : `/goals/${encodeURIComponent(goalId)}/${tab}`),
  me: (tab = 'overview') => (tab === 'overview' ? '/me' : `/me/${tab}`),
  practice: (practiceId?: string, query?: Record<string, string>) => withQuery(practiceId ? `/practice/${encodeURIComponent(practiceId)}` : '/practice', query),
  library: (tab = 'materials') => `/library/${tab}`,
  history: (query?: Record<string, string>) => withQuery('/history', query),
  reflection: (kind: string, ref: string) => `/reflection/${kind.toLowerCase()}/${encodeURIComponent(ref)}`,
  settings: (group = 'general') => `/settings/${group}`,
  live: (sessionId?: string) => (sessionId ? `/live/${encodeURIComponent(sessionId)}` : '/live'),
}

function withQuery(path: string, query?: Record<string, string>): string {
  const entries = Object.entries(query ?? {}).filter(([, v]) => v !== '' && v != null)
  if (!entries.length) return path
  return `${path}?${entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')}`
}

// ---------------------------------------------------------------------------
// Legacy appMode adapter
// ---------------------------------------------------------------------------

export function legacyModeForRoute(route: Route): LegacyMode {
  switch (route.name) {
    case 'live':
      return 'assist'
    case 'goals':
    case 'goal':
      return 'job-tracker'
    case 'me':
      return 'resume-opt'
    case 'practice':
      return 'prep'
    case 'history':
    case 'reflection':
      return 'review'
    default:
      return 'home'
  }
}

export function routeForLegacyMode(mode: LegacyMode | string): string {
  switch (mode) {
    case 'assist':
      return paths.live()
    case 'job-tracker':
      return paths.goals()
    case 'prep':
      return paths.practice()
    case 'review':
    case 'knowledge':
      return paths.history()
    case 'resume-opt':
      return paths.me()
    default:
      return paths.home()
  }
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

function currentHash(): string {
  if (typeof window === 'undefined') return ''
  return window.location.hash || ''
}

interface RouterState {
  route: Route
  navigate: (path: string, opts?: { replace?: boolean }) => void
  back: () => void
}

export const useRouter = create<RouterState>((set) => ({
  route: parsePath(currentHash()),
  navigate: (path, opts) => {
    const next = parsePath(path)
    if (typeof window !== 'undefined') {
      const target = `#${path.startsWith('/') ? path : `/${path}`}`
      if (window.location.hash !== target) {
        try {
          if (opts?.replace) window.history.replaceState(null, '', target)
          else window.history.pushState(null, '', target)
        } catch {
          window.location.hash = target
        }
      }
    }
    set({ route: next })
  },
  back: () => {
    if (typeof window !== 'undefined' && window.history.length > 1) window.history.back()
    else set({ route: parsePath(paths.home()) })
  },
}))

let listening = false

/** Keep the store in sync with browser back/forward. Idempotent. */
export function startRouterListener(): () => void {
  if (typeof window === 'undefined' || listening) return () => undefined
  listening = true
  const onChange = () => useRouter.setState({ route: parsePath(currentHash()) })
  window.addEventListener('hashchange', onChange)
  window.addEventListener('popstate', onChange)
  return () => {
    listening = false
    window.removeEventListener('hashchange', onChange)
    window.removeEventListener('popstate', onChange)
  }
}

export function navigate(path: string, opts?: { replace?: boolean }): void {
  useRouter.getState().navigate(path, opts)
}

export function hasExplicitRoute(): boolean {
  return Boolean(currentHash().replace(/^#\/?/, ''))
}
