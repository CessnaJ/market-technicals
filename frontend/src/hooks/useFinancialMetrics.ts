import { useCallback, useEffect, useState } from 'react'

import apiClient from '../api/client'
import { FinancialMetrics } from '../types'

interface UseFinancialMetricsParams {
  ticker: string
  enabled?: boolean
}

export function useFinancialMetrics({ ticker, enabled = true }: UseFinancialMetricsParams) {
  const [financial, setFinancial] = useState<FinancialMetrics | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchFinancialMetrics = useCallback(async () => {
    if (!enabled || !ticker) {
      setFinancial(null)
      setError(null)
      return null
    }

    setLoading(true)
    setError(null)

    try {
      const response = await apiClient.get<FinancialMetrics>(`/financial/${ticker}`)
      setFinancial(response.data)
      return response.data
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch financial metrics')
      setFinancial(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [enabled, ticker])

  useEffect(() => {
    if (!enabled || !ticker) {
      setFinancial(null)
      setError(null)
      return
    }

    void fetchFinancialMetrics()
  }, [enabled, ticker, fetchFinancialMetrics])

  return { financial, loading, error, refetch: fetchFinancialMetrics }
}
