import { useCallback, useEffect, useState } from 'react'

import apiClient from '../api/client'
import { DarvasBox, FibonacciData, Signal, WeinsteinData } from '../types'

interface UseIndicatorsParams {
  ticker: string
  enabled?: boolean
  benchmarkTicker?: string
  startDate?: string
  endDate?: string
  fibonacciMode?: 'auto' | 'manual'
  fibonacciTrend?: 'UP' | 'DOWN'
  manualSwingLow?: number | null
  manualSwingHigh?: number | null
}

export function useIndicators({
  ticker,
  enabled = true,
  benchmarkTicker = '069500',
  startDate,
  endDate,
  fibonacciMode = 'auto',
  fibonacciTrend = 'UP',
  manualSwingLow,
  manualSwingHigh,
}: UseIndicatorsParams) {
  const [weinstein, setWeinstein] = useState<WeinsteinData | null>(null)
  const [darvas, setDarvas] = useState<DarvasBox[]>([])
  const [fibonacci, setFibonacci] = useState<FibonacciData | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchIndicators = useCallback(async () => {
    if (!enabled || !ticker) {
      setWeinstein(null)
      setDarvas([])
      setFibonacci(null)
      setSignals([])
      setError(null)
      return null
    }

    setLoading(true)
    setError(null)

    try {
      const weinsteinParams = new URLSearchParams()
      if (benchmarkTicker) {
        weinsteinParams.append('benchmark_ticker', benchmarkTicker)
      }
      if (startDate) {
        weinsteinParams.append('start_date', startDate)
      }
      if (endDate) {
        weinsteinParams.append('end_date', endDate)
      }

      let fibonacciRequest: Promise<{ data: { fibonacci: FibonacciData | null } }>
      if (fibonacciMode === 'manual' && (manualSwingLow == null || manualSwingHigh == null)) {
        fibonacciRequest = Promise.resolve({ data: { fibonacci: null } })
      } else {
        const fibonacciParams = new URLSearchParams({
          trend: fibonacciTrend,
          mode: fibonacciMode,
        })
        if (fibonacciMode === 'manual') {
          fibonacciParams.append('swing_low', String(manualSwingLow))
          fibonacciParams.append('swing_high', String(manualSwingHigh))
        }
        fibonacciRequest = apiClient
          .get<{ fibonacci: FibonacciData | null }>(`/indicators/${ticker}/fibonacci?${fibonacciParams.toString()}`)
          .catch(() => ({ data: { fibonacci: null } }))
      }

      const [weinsteinRes, darvasRes, fibRes, signalsRes] = await Promise.all([
        apiClient
          .get<{ weinstein: WeinsteinData | null }>(`/indicators/${ticker}/weinstein?${weinsteinParams.toString()}`)
          .catch(() => ({ data: { weinstein: null } })),
        apiClient
          .get<{ darvas_boxes: DarvasBox[] }>(`/indicators/${ticker}/darvas`)
          .catch(() => ({ data: { darvas_boxes: [] } })),
        fibonacciRequest,
        apiClient
          .get<{ signals: Signal[] }>(`/signals/${ticker}`)
          .catch(() => ({ data: { signals: [] } })),
      ])

      setWeinstein(weinsteinRes.data.weinstein)
      setDarvas(darvasRes.data.darvas_boxes)
      setFibonacci(fibRes.data.fibonacci)
      setSignals(signalsRes.data.signals)

      return {
        weinstein: weinsteinRes.data.weinstein,
        darvas: darvasRes.data.darvas_boxes,
        fibonacci: fibRes.data.fibonacci,
        signals: signalsRes.data.signals,
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch indicators')
      return null
    } finally {
      setLoading(false)
    }
  }, [benchmarkTicker, enabled, endDate, fibonacciMode, fibonacciTrend, manualSwingHigh, manualSwingLow, startDate, ticker])

  useEffect(() => {
    if (!enabled || !ticker) {
      setWeinstein(null)
      setDarvas([])
      setFibonacci(null)
      setSignals([])
      setError(null)
      return
    }

    void fetchIndicators()
  }, [enabled, endDate, startDate, ticker, fetchIndicators])

  return { weinstein, darvas, fibonacci, signals, loading, error, refetch: fetchIndicators }
}
