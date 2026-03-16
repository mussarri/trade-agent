import { useState, useEffect } from 'react'
import { ConnectionStatus } from './ConnectionStatus'
import type { WSStatus } from '../hooks/useWebSocket'
import { formatUTCTime } from '../utils/formatters'

interface Props {
  wsStatus: WSStatus
  isMock: boolean
  darkMode: boolean
  onToggleDark: () => void
  sidebarOpen: boolean
  onToggleSidebar: () => void
}

export function Header({ wsStatus, isMock, darkMode, onToggleDark, sidebarOpen, onToggleSidebar }: Props) {
  const [time, setTime] = useState(() => formatUTCTime(new Date()))

  useEffect(() => {
    const id = setInterval(() => setTime(formatUTCTime(new Date())), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="sticky top-0 z-50 bg-slate-900/95 backdrop-blur border-b border-slate-700/60 h-14">
      <div className="px-4 h-full flex items-center justify-between gap-4">
        {/* Left: sidebar toggle + logo */}
        <div className="flex items-center gap-3">
          <button
            onClick={onToggleSidebar}
            className="w-8 h-8 rounded-lg border border-slate-700 bg-slate-800 flex items-center justify-center text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors flex-shrink-0"
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              </svg>
            )}
          </button>

          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
            <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>

          <div>
            <span className="font-semibold text-slate-100 tracking-tight">Signal Engine</span>
            <span className="ml-2 text-xs text-slate-500 hidden sm:inline">ICT · Trend Continuation · HTF Hard Filter</span>
          </div>
        </div>

        {/* Right */}
        <div className="flex items-center gap-2 sm:gap-3">
          <ConnectionStatus status={wsStatus} isMock={isMock} />

          <div className="font-price text-xs text-slate-500 tabular-nums hidden md:flex items-center gap-2 border border-slate-700/60 bg-slate-800/60 px-2.5 py-1 rounded-lg">
            <svg className="w-3 h-3 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {time}
          </div>

          <button
            onClick={onToggleDark}
            className="w-8 h-8 rounded-lg border border-slate-700 bg-slate-800 flex items-center justify-center text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors"
            aria-label="Toggle dark mode"
          >
            {darkMode ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
