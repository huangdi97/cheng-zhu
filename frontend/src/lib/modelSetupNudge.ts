/** Interview model setup must never gate deterministic Conversation-only surfaces. */
const CONVERSATION_ROUTES = new Set([
  'conversation-home',
  'conversation-onboarding',
  'conversations',
  'conversation',
  'conversation-live',
])

export function shouldPromptForInterviewModel(
  config: { api_key_set?: boolean } | null | undefined,
  productProfile: 'interview' | 'conversation',
  routeName: string,
): boolean {
  if (!config || config.api_key_set) return false
  // Route wins over stale localStorage during first render / deep linking.
  if (CONVERSATION_ROUTES.has(routeName)) return false
  return productProfile === 'interview'
}
