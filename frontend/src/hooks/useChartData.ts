import { useState, useEffect } from 'react'
import apiClient from '../api/client'
import { ChartDataResponse } from '../types'

interface UseChartDataParams {
  ticker: string;
  timeframe?: 'daily' | 'weekly';
  scale?: 'linear' | 'log';
  enabled?: boolean;
}

export function useChartData({ ticker, timeframe = 'daily', scale = 'linear', enabled = true }: UseChartDataParams) {
  const [data, setData] = useState<ChartDataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled || !ticker) {
      setData(null)
      setError(null)
      return
    }

    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await apiClient.get<ChartDataResponse>(
          `/chart/${ticker}?timeframe=${timeframe}&scale=${scale}`
        )
        setData(response.data)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch chart data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [ticker, timeframe, scale, enabled])

  return { data, loading, error }
}
