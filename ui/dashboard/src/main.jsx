import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'

function App() {
  const [signals, setSignals] = useState([])

  useEffect(() => {
    fetch('/api/signals')
      .then((r) => r.json())
      .then(setSignals)
      .catch(() => {})

    const ws = new WebSocket(`ws://${window.location.host}/ws`)
    ws.onopen = () => ws.send('subscribe')
    ws.onmessage = (evt) => {
      try {
        const signal = JSON.parse(evt.data)
        setSignals((prev) => [signal, ...prev].slice(0, 50))
      } catch {
        // ignore parse errors
      }
    }
    return () => ws.close()
  }, [])

  return (
    <main style={{fontFamily: 'sans-serif', padding: 16}}>
      <h1>Trade Agent Signals</h1>
      {signals.length === 0 ? <p>No active signals.</p> : null}
      <ul>
        {signals.map((s, idx) => (
          <li key={`${s.symbol}-${s.scenario_name}-${idx}`}>
            {s.symbol} {s.direction} | {s.scenario_name} | score {s.score}
          </li>
        ))}
      </ul>
    </main>
  )
}

createRoot(document.getElementById('root')).render(<App />)
