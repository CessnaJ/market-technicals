import { useCallback, useEffect, useState } from 'react'

import apiClient from '../api/client'
import { DarvasBox, FibonacciData, Signal, WeinsteinData } from '../types'

interface UseIndicatorsParams {
  ticker: string
  enabled?: boolean
}

export function useIndicators({ ticker, enabled = true }: UseIndicatorsParams) {
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
      const [weinsteinRes, darvasRes, fibRes, signalsRes] = await Promise.all([
        apiClient
          .get<{ weinstein: WeinsteinData | null }>(`/indicators/${ticker}/weinstein`)
          .catch(() => ({ data: { weinstein: null } })),
        apiClient
          .get<{ darvas_boxes: DarvasBox[] }>(`/indicators/${ticker}/darvas`)
          .catch(() => ({ data: { darvas_boxes: [] } })),
        apiClient
          .get<{ fibonacci: FibonacciData | null }>(`/indicators/${ticker}/fibonacci`)
          .catch(() => ({ data: { fibonacci: null } })),
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
  }, [enabled, ticker])

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
  }, [enabled, ticker, fetchIndicators])

  return { weinstein, darvas, fibonacci, signals, loading, error, refetch: fetchIndicators }
}
