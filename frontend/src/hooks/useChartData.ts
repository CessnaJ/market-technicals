import { useState, useEffect, useCallback } from 'react'
import apiClient from '../api/client'
import { ChartDataResponse } from '../types'

interface UseChartDataParams {
  ticker: string;
  timeframe?: 'daily' | 'weekly';
  scale?: 'linear' | 'log';
  enabled?: boolean;
  startDate?: string;
  endDate?: string;
  forceRefresh?: boolean;
}

export function useChartData({
  ticker,
  timeframe = 'daily',
  scale = 'linear',
  enabled = true,
  startDate,
  endDate,
  forceRefresh
}: UseChartDataParams) {
  const [data, setData] = useState<ChartDataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [isRefetching, setIsRefetching] = useState(false) // 추가: 배경 업데이트 상태
  const[error, setError] = useState<string | null>(null)

  // API 호출 로직을 useCallback으로 분리
  const fetchData = useCallback(async (isBackgroundUpdate = false) => {
    if (!ticker) return;

    if (isBackgroundUpdate) {
      setIsRefetching(true)
    } else {
      setLoading(true)
    }
    
    setError(null)
    
    try {
      const params = new URLSearchParams({ timeframe, scale })
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)
      if (forceRefresh) params.append('force_refresh', 'true')

      const response = await apiClient.get<ChartDataResponse>(
        `/chart/${ticker}?${params.toString()}`
      )
      
      setData(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch chart data')
    } finally {
      setLoading(false)
      setIsRefetching(false)
    }
  }, [ticker, timeframe, scale, startDate, endDate, forceRefresh])

  // 최초 로딩
  useEffect(() => {
    if (!enabled || !ticker) {
      setData(null)
      setError(null)
      return
    }
    fetchData()
  },[fetchData, enabled, ticker])

  // refetch 함수와 isRefetching 상태를 함께 반환합니다.
  return { data, loading, isRefetching, error, refetch: () => fetchData(true) }
}