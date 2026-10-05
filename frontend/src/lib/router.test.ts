import { describe, expect, it } from 'vitest'
import { legacyModeForRoute, parsePath, paths, routeForLegacyMode } from './router'

describe('v1.3 object-centric routes', () => {
  it('parses every canonical route', () => {
    expect(parsePath('#/home').name).toBe('home')
    expect(parsePath('').name).toBe('home')
    expect(parsePath('#/goals').name).toBe('goals')
    const goal = parsePath('#/goals/g_1/prepare')
    expect(goal).toMatchObject({ name: 'goal', params: { goalId: 'g_1', tab: 'prepare' } })
    expect(parsePath('#/goals/g_1/unknown').params.tab).toBe('overview')
    expect(parsePath('#/goals/g_1/interviews').params.tab).toBe('interviews')
    expect(parsePath('#/goals/g_1/offer').params.tab).toBe('offer')
    expect(parsePath('#/me/inbox')).toMatchObject({ name: 'me', params: { tab: 'inbox' } })
    expect(parsePath('#/practice/pr_1')).toMatchObject({ name: 'practice', params: { practiceId: 'pr_1' } })
    expect(parsePath('#/practice?goal=g_1&focus=nf_2').query).toEqual({ goal: 'g_1', focus: 'nf_2' })
    expect(parsePath('#/library/banks').params.tab).toBe('banks')
    expect(parsePath('#/reflection/review/12')).toMatchObject({ name: 'reflection', params: { kind: 'REVIEW', ref: '12' } })
    expect(parsePath('#/settings/language').params.group).toBe('language')
    expect(parsePath('#/live/s-1')).toMatchObject({ name: 'live', params: { sessionId: 's-1' } })
    expect(parsePath('#/nowhere').name).toBe('home')
  })

  it('round-trips the path builders', () => {
    expect(parsePath(paths.goal('a b', 'offer'))).toMatchObject({ name: 'goal', params: { goalId: 'a b', tab: 'offer' } })
    expect(parsePath(paths.practice(undefined, { goal: 'g', round: '' })).query).toEqual({ goal: 'g' })
    expect(parsePath(paths.reflection('PRACTICE', 'pr_9')).params).toEqual({ kind: 'PRACTICE', ref: 'pr_9' })
  })

  it('adapts the v1.2 appMode both ways', () => {
    expect(routeForLegacyMode('job-tracker')).toBe('/goals')
    expect(routeForLegacyMode('prep')).toBe('/practice')
    expect(routeForLegacyMode('assist')).toBe('/live')
    expect(routeForLegacyMode('review')).toBe('/history')
    expect(routeForLegacyMode('knowledge')).toBe('/history')
    expect(routeForLegacyMode('resume-opt')).toBe('/me')
    expect(legacyModeForRoute(parsePath('#/live'))).toBe('assist')
    expect(legacyModeForRoute(parsePath('#/goals/g/prepare'))).toBe('job-tracker')
    expect(legacyModeForRoute(parsePath('#/reflection/practice/p'))).toBe('review')
    expect(legacyModeForRoute(parsePath('#/library'))).toBe('home')
  })
})
