import { useState, useEffect } from 'react'
import apiClient from '../api/client'
import { ChartDataResponse } from '../types'

interface UseChartDataParams {
  ticker: string;
  timeframe?: 'daily' | 'weekly';
  scale?: 'linear' | 'log';
  enabled?: boolean;
  startDate?: string; // YYYY-MM-DD format
  endDate?: string;   // YYYY-MM-DD format
}

export function useChartData({
  ticker,
  timeframe = 'daily',
  scale = 'linear',
  enabled = true,
  startDate,
  endDate
}: UseChartDataParams) {
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
        // Build query parameters
        const params = new URLSearchParams({
          timeframe,
          scale,
        })
        
        if (startDate) {
          params.append('start_date', startDate)
        }
        if (endDate) {
          params.append('end_date', endDate)
        }

        const response = await apiClient.get<ChartDataResponse>(
          `/chart/${ticker}?${params.toString()}`
        )
        setData(response.data)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch chart data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [ticker, timeframe, scale, enabled, startDate, endDate])

  return { data, loading, error }
}
