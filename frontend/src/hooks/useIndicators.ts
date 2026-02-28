import { useState, useEffect } from 'react'
import apiClient from '../api/client'
import { WeinsteinData, DarvasBox, FibonacciData, Signal } from '../types'

interface UseIndicatorsParams {
  ticker: string;
  enabled?: boolean;
}

export function useIndicators({ ticker, enabled = true }: UseIndicatorsParams) {
  const [weinstein, setWeinstein] = useState<WeinsteinData | null>(null)
  const [darvas, setDarvas] = useState<DarvasBox[]>([])
  const [fibonacci, setFibonacci] = useState<FibonacciData | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled || !ticker) {
      setWeinstein(null)
      setDarvas([])
      setFibonacci(null)
      setSignals([])
      setError(null)
      return
    }

    const fetchIndicators = async () => {
      setLoading(true)
      setError(null)
      try {
        // 병렬로 모든 지표 데이터 가져오기
        const [weinsteinRes, darvasRes, fibRes, signalsRes] = await Promise.all([
          apiClient.get<{ weinstein: WeinsteinData }>(`/indicators/${ticker}/weinstein`).catch(() => ({ data: { weinstein: null as any } })),
          apiClient.get<{ darvas_boxes: DarvasBox[] }>(`/indicators/${ticker}/darvas`).catch(() => ({ data: { darvas_boxes: [] } })),
          apiClient.get<{ fibonacci: FibonacciData }>(`/indicators/${ticker}/fibonacci`).catch(() => ({ data: { fibonacci: null as any } })),
          apiClient.get<{ signals: Signal[] }>(`/signals/${ticker}`).catch(() => ({ data: { signals: [] } })),
        ])

        setWeinstein(weinsteinRes.data.weinstein)
        setDarvas(darvasRes.data.darvas_boxes)
        setFibonacci(fibRes.data.fibonacci)
        setSignals(signalsRes.data.signals)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch indicators')
      } finally {
        setLoading(false)
      }
    }

    fetchIndicators()
  }, [ticker, enabled])

  return { weinstein, darvas, fibonacci, signals, loading, error }
}
