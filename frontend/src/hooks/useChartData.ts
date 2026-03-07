import { useCallback, useEffect, useState } from 'react'

import apiClient from '../api/client'
import { ChartDataResponse } from '../types'

interface UseChartDataParams {
  ticker: string
  timeframe?: 'daily' | 'weekly'
  scale?: 'linear' | 'log'
  enabled?: boolean
  startDate?: string
  endDate?: string
  forceRefresh?: boolean
}

export function useChartData({
  ticker,
  timeframe = 'daily',
  scale = 'linear',
  enabled = true,
  startDate,
  endDate,
  forceRefresh,
}: UseChartDataParams) {
  const [data, setData] = useState<ChartDataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!ticker) {
      setData(null)
      return null
    }

    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({ timeframe, scale })
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)
      if (forceRefresh) params.append('force_refresh', 'true')

      const response = await apiClient.get<ChartDataResponse>(`/chart/${ticker}?${params.toString()}`)
      setData(response.data)
      return response.data
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch chart data')
      setData(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [ticker, timeframe, scale, startDate, endDate, forceRefresh])

  useEffect(() => {
    if (!enabled || !ticker) {
      setData(null)
      setError(null)
      return
    }

    setData(null)
    void fetchData()
  }, [enabled, ticker, fetchData])

  return { data, loading, error, refetch: fetchData }
}
