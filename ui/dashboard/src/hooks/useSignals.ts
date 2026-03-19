import { useState, useCallback, useEffect } from "react";
import type { Signal, Stats } from "../types/signal";
import { useWebSocket, type WSStatus } from "./useWebSocket";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

interface UseSignalsResult {
  signals: Signal[];
  history: Signal[];
  stats: Stats | null;
  wsStatus: WSStatus;
  isMock: boolean;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeSignal(raw: any, htf: string): Signal {
  const rp = raw.risk_plan ?? {};
  const factors = raw.confidence_factors ?? {};
  return {
    id: raw.id ?? `${raw.symbol}|${raw.scenario_name}|${raw.timeframe}`,
    status: raw.status ?? "active",
    timeframe_ltf: raw.timeframe_ltf ?? raw.timeframe ?? "",
    timeframe_htf: raw.timeframe_htf ?? htf,
    scenario_name: raw.scenario_name ?? "",
    alert_type: raw.alert_type === "SETUP_DETECTED" ? "SETUP_DETECTED" : "ENTRY_CONFIRMED",
    pair: raw.pair ?? (raw.symbol ?? "").replace("/", ""),
    symbol: raw.symbol ?? "",
    direction: raw.direction,
    score: raw.score,
    confidence_factors: {
      htf_alignment: !!factors.htf_alignment,
      pullback_active: !!factors.pullback_active,
      zone_reaction: !!factors.zone_reaction,
      displacement: !!factors.displacement,
      micro_bos: !!factors.micro_bos,
      first_pullback: !!factors.first_pullback,
    },
    htf_trend: raw.htf_trend ?? "",
    session: raw.session ?? "",
    ict_full_setup: raw.ict_full_setup ?? false,
    scenario_detail: raw.scenario_detail ?? "",
    timestamp: raw.timestamp,
    entry_low: raw.entry_low ?? rp.entry_low ?? 0,
    entry_high: raw.entry_high ?? rp.entry_high ?? 0,
    stop_loss: raw.stop_loss ?? rp.stop_loss ?? 0,
    tp1: raw.tp1 ?? rp.tp1 ?? 0,
    tp2: raw.tp2 ?? rp.tp2 ?? 0,
    tp3: raw.tp3 ?? rp.tp3 ?? 0,
    rr_ratio: raw.rr_ratio ?? rp.rr_ratio ?? 0,
    invalidation_level: raw.invalidation_level ?? rp.invalidation_level ?? 0,
  };
}

export function useSignals(): UseSignalsResult {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [history, setHistory] = useState<Signal[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [htf, setHtf] = useState<string>("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sigRes, histRes, statsRes, statusRes] = await Promise.all([
          fetch("/api/signals"),
          fetch("/api/signals/history"),
          fetch("/api/stats"),
          fetch("/api/exchange/status"),
        ]);

        let resolvedHtf = htf;
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          resolvedHtf = statusData.htf?.[0] ?? statusData.htf ?? statusData.timeframe_htf ?? "";
          setHtf(resolvedHtf);
        }

        if (sigRes.ok) {
          const data = await sigRes.json();
          setSignals(data.map((r: unknown) => normalizeSignal(r, resolvedHtf)));
        }
        if (histRes.ok) {
          const data = await histRes.json();
          setHistory(data.map((r: unknown) => normalizeSignal(r, resolvedHtf)));
        }
        if (statsRes.ok) setStats(await statsRes.json());
      } catch {
        // backend unavailable – stay empty
      }
    };

    void fetchData();
  }, []); // eslint-disable-line

  const handleNewSignal = useCallback(
    (raw: unknown) => {
      const signal = normalizeSignal(raw, htf);
      setSignals((prev) => {
        const ids = new Set(prev.map((s) => s.id));
        return ids.has(signal.id) ? prev : [signal, ...prev];
      });
      setHistory((prev) => {
        const ids = new Set(prev.map((s) => s.id));
        return ids.has(signal.id) ? prev : [signal, ...prev].slice(0, 50);
      });
      setStats((prev) =>
        prev
          ? {
              ...prev,
              total_signals_today: prev.total_signals_today + 1,
              active_signals: prev.active_signals + 1,
            }
          : prev,
      );
    },
    [htf],
  );

  const handleSignalUpdate = useCallback(
    (raw: unknown) => {
      const updated = normalizeSignal(raw, htf);
      setSignals((prev) =>
        updated.status === "active"
          ? prev.map((s) => (s.id === updated.id ? updated : s))
          : prev.filter((s) => s.id !== updated.id),
      );
      setHistory((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s)),
      );
      setStats((prev) => {
        if (!prev) return prev;
        const delta = updated.status === "active" ? 0 : -1;
        return { ...prev, active_signals: Math.max(0, prev.active_signals + delta) };
      });
    },
    [htf],
  );

  const { status: wsStatus } = useWebSocket({
    url: "ws://localhost:8000/ws",
    enabled: !USE_MOCK,
    onNewSignal: handleNewSignal,
    onSignalUpdate: handleSignalUpdate,
  });

  return {
    signals,
    history,
    stats,
    wsStatus: USE_MOCK ? "connected" : wsStatus,
    isMock: USE_MOCK,
  };
}
