import { useCallback, useEffect, useState } from 'react'

import apiClient from '../api/client'
import { RelativeStrengthData } from '../types'

interface UseRelativeStrengthParams {
  ticker: string
  benchmarkTicker: string
  timeframe: 'daily' | 'weekly' | 'monthly'
  startDate?: string
  endDate?: string
  enabled?: boolean
}

export function useRelativeStrength({
  ticker,
  benchmarkTicker,
  timeframe,
  startDate,
  endDate,
  enabled = true,
}: UseRelativeStrengthParams) {
  const [relativeStrength, setRelativeStrength] = useState<RelativeStrengthData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchRelativeStrength = useCallback(async () => {
    if (!enabled || !ticker || !benchmarkTicker) {
      setRelativeStrength(null)
      setError(null)
      return null
    }

    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        benchmark_ticker: benchmarkTicker,
        timeframe,
      })
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)
      const response = await apiClient.get<{ relative_strength: RelativeStrengthData | null }>(
        `/indicators/${ticker}/relative-strength?${params.toString()}`
      )
      setRelativeStrength(response.data.relative_strength)
      return response.data.relative_strength
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch relative strength data')
      setRelativeStrength(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [benchmarkTicker, enabled, endDate, startDate, ticker, timeframe])

  useEffect(() => {
    if (!enabled || !ticker || !benchmarkTicker) {
      setRelativeStrength(null)
      setError(null)
      return
    }

    void fetchRelativeStrength()
  }, [benchmarkTicker, enabled, endDate, startDate, ticker, timeframe, fetchRelativeStrength])

  return { relativeStrength, loading, error, refetch: fetchRelativeStrength }
}
