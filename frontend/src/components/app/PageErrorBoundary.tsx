/**
 * Page-level error boundary for the routed v1.3 screens.
 *
 * INVARIANT: a failure inside one screen must never unmount the app shell.
 * Without this boundary an uncaught render error makes React unmount the whole
 * root, so a single unexpected API payload blanks the window and the user loses
 * the navigation, the session and any way to recover. The boundary keeps the
 * shell alive and turns the failure into an explicit, retryable state.
 */
import { Component, type ErrorInfo, type ReactNode } from 'react'

import { ErrorState, Page } from '@/components/os/ui'

interface Props {
  children: ReactNode
  /** Remount key: change it to retry from a clean tree. */
  resetKey?: string
}

interface State {
  error: Error | null
}

export default class PageErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Not silent: the failure stays visible in the UI and in the console.
    console.error('[chengzhu] screen crashed', error, info.componentStack)
  }

  componentDidUpdate(previous: Props): void {
    if (this.state.error && previous.resetKey !== this.props.resetKey) this.reset()
  }

  private reset = (): void => {
    this.setState({ error: null })
  }

  render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <Page testId="page-error">
        <ErrorState
          message={`这个页面出错了：${error.message || '未知错误'}`}
          onRetry={this.reset}
          extra={<p className="mt-1.5 text-xs text-text-muted">可以切换上方其他页面继续使用，成竹的数据没有丢失。</p>}
        />
      </Page>
    )
  }
}
