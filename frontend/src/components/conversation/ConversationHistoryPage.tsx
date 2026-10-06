import { ArrowRight, Clock3, MessageSquareText } from 'lucide-react'
import { conversationApi } from '@/lib/conversationApi'
import { navigate, paths } from '@/lib/router'
import { EmptyState, ErrorState, Loading, Page, PageHeader, StatusBadge, formatWhen, useAsync } from '@/components/os/ui'

export default function ConversationHistoryPage() {
  const history = useAsync(() => conversationApi.history(120), [])

  return (
    <Page testId="conversation-history">
      <PageHeader title="历史" subtitle="按真实 Conversation Session 回看发生了什么，并从同一个 Space 继续。" />
      {history.loading ? <Loading /> : history.error ? <ErrorState message={history.error} onRetry={history.reload} /> : !history.data?.items.length ? (
        <EmptyState title="还没有已结束的对话" body="结束一场 Conversation 后，这里会保留可追溯的 Continue 入口。" />
      ) : (
        <div className="space-y-2">
          {history.data.items.map((item) => (
            <button key={item.id} type="button" onClick={() => navigate(paths.conversationSpace(item.space_id, 'sessions'))}
              className="group flex w-full items-start justify-between gap-4 rounded-2xl border border-bg-tertiary/70 bg-bg-secondary/25 px-4 py-3 text-left hover:bg-bg-hover/45">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <MessageSquareText className="h-4 w-4 text-accent-blue" aria-hidden />
                  <span className="truncate text-sm font-semibold text-text-primary">{item.title || item.space_title}</span>
                  <StatusBadge tone="muted">{item.space_profile}</StatusBadge>
                  {item.review_required ? <StatusBadge tone="warn">{item.review_required} 待确认</StatusBadge> : null}
                </div>
                <p className="mt-1 text-xs text-text-secondary">{item.space_title}</p>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-text-muted">
                  <span>{item.decisions_count} Decisions</span>
                  <span>{item.commitments_count} Commitments</span>
                  <span>{item.open_questions_count} Open Questions</span>
                  <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" />{formatWhen(item.ended_at ?? item.started_at ?? item.created_at)}</span>
                </div>
              </div>
              <ArrowRight className="mt-1 h-4 w-4 flex-shrink-0 text-text-muted group-hover:text-text-primary" aria-hidden />
            </button>
          ))}
        </div>
      )}
    </Page>
  )
}
