import { useCallback, useEffect, useState } from 'react'

import apiClient from '../api/client'
import { StockProfileResponse } from '../types'

interface UseStockProfileParams {
  ticker: string
  enabled?: boolean
  refreshKey?: number
}

export function useStockProfile({
  ticker,
  enabled = true,
  refreshKey = 0,
}: UseStockProfileParams) {
  const [profile, setProfile] = useState<StockProfileResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchProfile = useCallback(async () => {
    if (!enabled || !ticker) {
      setProfile(null)
      setError(null)
      return null
    }

    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get<StockProfileResponse>(`/stocks/${ticker}/profile`)
      setProfile(response.data)
      return response.data
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch stock profile')
      setProfile(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [enabled, ticker])

  useEffect(() => {
    void fetchProfile()
  }, [fetchProfile, refreshKey])

  return { profile, loading, error, refetch: fetchProfile }
}
