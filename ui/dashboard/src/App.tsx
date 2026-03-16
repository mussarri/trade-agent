import { useState, useEffect, useMemo } from 'react'
import { Header } from './components/Header'
import { StatsBar } from './components/StatsBar'
import { SignalList } from './components/SignalList'
import { ScenarioStats } from './components/ScenarioStats'
import { SymbolTable } from './components/SymbolTable'
import { HistoryTable } from './components/HistoryTable'
import { TimeframeMatrix } from './components/TimeframeMatrix'
import { Sidebar } from './components/Sidebar'
import { useSignals } from './hooks/useSignals'
import type { FilterState } from './types/signal'

export default function App() {
  const [darkMode, setDarkMode] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [filters, setFilters] = useState<FilterState>({
    symbol: '',
    direction: '',
    scenario: '',
    minScore: 0,
    sortBy: 'score',
  })

  const { signals, history, stats, wsStatus, isMock } = useSignals()

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

  const filteredSignals = useMemo(() => {
    return signals
      .filter(s => s.status === 'active')
      .filter(s => !filters.symbol || s.symbol.toLowerCase().includes(filters.symbol.toLowerCase()))
      .filter(s => !filters.direction || s.direction === filters.direction)
      .filter(s => !filters.scenario || s.scenario_name === filters.scenario)
      .filter(s => s.score >= filters.minScore)
      .sort((a, b) => {
        if (filters.sortBy === 'rr') return b.rr_ratio - a.rr_ratio
        if (filters.sortBy === 'time') return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        return b.score - a.score
      })
  }, [signals, filters])

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <Header
        wsStatus={wsStatus}
        isMock={isMock}
        darkMode={darkMode}
        onToggleDark={() => setDarkMode(d => !d)}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(o => !o)}
      />

      <div className="flex">
        {/* Desktop sticky sidebar */}
        <aside
          className={`
            sticky top-14 h-[calc(100vh-3.5rem)] flex-shrink-0 overflow-y-auto
            border-r border-slate-700/60 bg-slate-900
            transition-all duration-300 ease-in-out
            hidden lg:block
            ${sidebarOpen ? 'w-64' : 'w-0 overflow-hidden border-none'}
          `}
        >
          {sidebarOpen && (
            <Sidebar
              signals={signals}
              stats={stats}
              filters={filters}
              onFilterChange={setFilters}
            />
          )}
        </aside>

        {/* Mobile overlay backdrop */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/60 z-30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Mobile sidebar drawer */}
        <div
          className={`
            fixed top-14 left-0 bottom-0 w-72 z-40 lg:hidden
            bg-slate-900 border-r border-slate-700/60 overflow-y-auto
            transition-transform duration-300
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          `}
        >
          <Sidebar
            signals={signals}
            stats={stats}
            filters={filters}
            onFilterChange={setFilters}
          />
        </div>

        {/* Main content */}
        <main className="flex-1 min-w-0">
          <div className="max-w-screen-2xl mx-auto px-4 lg:px-6 py-6 space-y-6">
            <StatsBar signals={signals} stats={stats} />

            <TimeframeMatrix signals={filteredSignals} />

            <SignalList signals={filteredSignals} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <ScenarioStats stats={stats} />
              <SymbolTable stats={stats} />
            </div>

            <HistoryTable history={history} />
          </div>
        </main>
      </div>
    </div>
  )
}
