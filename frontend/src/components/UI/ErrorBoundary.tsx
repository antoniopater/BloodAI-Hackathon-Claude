import React from 'react'

interface State {
  error: Error | null
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-[50vh] items-center justify-center p-6">
          <div className="w-full max-w-lg rounded-2xl border border-danger-500/40 bg-danger-50 p-6 dark:bg-danger-700/20">
            <p className="text-lg font-bold text-danger-700 dark:text-danger-400">
              Something went wrong
            </p>
            <p className="mt-1 font-mono text-sm text-slate-700 dark:text-slate-300">
              {this.state.error.message}
            </p>
            <button
              className="mt-4 rounded-xl bg-primary-700 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-800"
              onClick={() => {
                this.setState({ error: null })
                window.location.href = '/input'
              }}
            >
              Go back to input
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
