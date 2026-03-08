import { useEffect, useState } from 'react'

import apiClient from '../api/client'
import { StockSearchResponse, StockSearchSuggestion } from '../types'

interface UseStockSearchParams {
  query: string
  enabled?: boolean
  limit?: number
  refreshKey?: number
}

export function useStockSearch({
  query,
  enabled = true,
  limit = 10,
  refreshKey = 0,
}: UseStockSearchParams) {
  const [suggestions, setSuggestions] = useState<StockSearchSuggestion[]>([])
  const [masterReady, setMasterReady] = useState(true)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!enabled) {
      setSuggestions([])
      return
    }

    const trimmedQuery = query.trim()
    if (!trimmedQuery) {
      setSuggestions([])
      return
    }

    const debounceHandle = window.setTimeout(async () => {
      setLoading(true)
      try {
        const params = new URLSearchParams({
          q: trimmedQuery,
          limit: String(limit),
        })
        const response = await apiClient.get<StockSearchResponse>(`/stocks/search?${params.toString()}`)
        setSuggestions(response.data.suggestions)
        setMasterReady(response.data.master_ready)
      } catch (error) {
        console.error('Failed to search stocks:', error)
        setSuggestions([])
      } finally {
        setLoading(false)
      }
    }, 220)

    return () => window.clearTimeout(debounceHandle)
  }, [enabled, limit, query, refreshKey])

  return { suggestions, masterReady, loading }
}
