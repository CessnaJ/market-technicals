import { useCallback, useEffect, useMemo, useState } from 'react'

import apiClient from '../api/client'
import { BollingerData, ChartDataResponse, IndicatorData, MACDData, OHLCV, RSIData, VPCIData } from '../types'

type Timeframe = 'daily' | 'weekly' | 'monthly'

interface UseChartDataParams {
  ticker: string
  timeframe?: Timeframe
  scale?: 'linear' | 'log'
  enabled?: boolean
  startDate?: string
  endDate?: string
  forceRefresh?: boolean
  smaPeriods?: number[]
}

const OLDER_HISTORY_LIMITS: Record<Timeframe, number> = {
  daily: 240,
  weekly: 120,
  monthly: 72,
}

export function useChartData({
  ticker,
  timeframe = 'daily',
  scale = 'linear',
  enabled = true,
  startDate,
  endDate,
  forceRefresh,
  smaPeriods,
}: UseChartDataParams) {
  const [data, setData] = useState<ChartDataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [isFetchingOlder, setIsFetchingOlder] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const smaPeriodsKey = useMemo(
    () => (smaPeriods && smaPeriods.length > 0 ? smaPeriods.join(',') : ''),
    [smaPeriods]
  )

  const fetchData = useCallback(async () => {
    if (!ticker) {
      setData(null)
      return null
    }

    setLoading(true)
    setError(null)

    try {
      const response = await apiClient.get<ChartDataResponse>(
        `/chart/${ticker}?${buildChartParams({
          timeframe,
          scale,
          startDate,
          endDate,
          forceRefresh,
          smaPeriodsKey,
        }).toString()}`
      )
      setData(response.data)
      return response.data
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch chart data')
      setData(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [ticker, timeframe, scale, startDate, endDate, forceRefresh, smaPeriodsKey])

  const fetchOlder = useCallback(async () => {
    if (!enabled || !ticker || !data?.history.oldest_date || !data.history.has_more_before || isFetchingOlder) {
      return 0
    }

    setIsFetchingOlder(true)
    setError(null)

    try {
      const response = await apiClient.get<ChartDataResponse>(
        `/chart/${ticker}?${buildChartParams({
          timeframe,
          scale,
          beforeDate: data.history.oldest_date,
          limit: OLDER_HISTORY_LIMITS[timeframe],
          smaPeriodsKey,
        }).toString()}`
      )

      const merged = mergeChartResponses(data, response.data)
      setData(merged)
      return Math.max(0, merged.ohlcv.length - data.ohlcv.length)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch older history')
      return 0
    } finally {
      setIsFetchingOlder(false)
    }
  }, [data, enabled, isFetchingOlder, scale, smaPeriodsKey, ticker, timeframe])

  useEffect(() => {
    if (!enabled || !ticker) {
      setData(null)
      setError(null)
      return
    }

    setData(null)
    void fetchData()
  }, [enabled, ticker, fetchData])

  return {
    data,
    loading,
    error,
    refetch: fetchData,
    fetchOlder,
    isFetchingOlder,
    hasMoreBefore: data?.history.has_more_before ?? false,
  }
}

function buildChartParams({
  timeframe,
  scale,
  startDate,
  endDate,
  beforeDate,
  limit,
  forceRefresh,
  smaPeriodsKey,
}: {
  timeframe: Timeframe
  scale: 'linear' | 'log'
  startDate?: string
  endDate?: string
  beforeDate?: string
  limit?: number
  forceRefresh?: boolean
  smaPeriodsKey?: string
}) {
  const params = new URLSearchParams({ timeframe, scale })
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  if (beforeDate) params.append('before_date', beforeDate)
  if (limit != null) params.append('limit', String(limit))
  if (forceRefresh) params.append('force_refresh', 'true')
  if (smaPeriodsKey) params.append('sma_periods', smaPeriodsKey)
  return params
}

function mergeChartResponses(current: ChartDataResponse, older: ChartDataResponse): ChartDataResponse {
  const mergedOhlcv = mergeByDate<OHLCV>(current.ohlcv, older.ohlcv)

  return {
    ...current,
    ohlcv: mergedOhlcv,
    indicators: mergeIndicatorPayload(current.indicators, older.indicators),
    history: {
      oldest_date: mergedOhlcv[0]?.date ?? null,
      newest_date: mergedOhlcv[mergedOhlcv.length - 1]?.date ?? null,
      has_more_before: older.history.has_more_before,
      loaded_count: mergedOhlcv.length,
    },
  }
}

function mergeIndicatorPayload(
  current: ChartDataResponse['indicators'] | undefined,
  older: ChartDataResponse['indicators'] | undefined,
): ChartDataResponse['indicators'] {
  return {
    sma: mergeSmaPayload(current?.sma, older?.sma),
    macd: mergeByDate<MACDData>(current?.macd ?? [], older?.macd ?? []),
    rsi: mergeByDate<RSIData>(current?.rsi ?? [], older?.rsi ?? []),
    bollinger: mergeByDate<BollingerData>(current?.bollinger ?? [], older?.bollinger ?? []),
    vpci: mergeByDate<VPCIData>(current?.vpci ?? [], older?.vpci ?? []),
  }
}

function mergeSmaPayload(
  current: Record<string, IndicatorData[]> | undefined,
  older: Record<string, IndicatorData[]> | undefined,
) {
  const merged: Record<string, IndicatorData[]> = {}
  const periods = new Set<string>([
    ...Object.keys(current ?? {}),
    ...Object.keys(older ?? {}),
  ])

  periods.forEach((period) => {
    merged[period] = mergeByDate<IndicatorData>(current?.[period] ?? [], older?.[period] ?? [])
  })

  return merged
}

function mergeByDate<T extends { date: string }>(current: T[], older: T[]) {
  const merged = new Map<string, T>()
  older.forEach((item) => merged.set(item.date, item))
  current.forEach((item) => merged.set(item.date, item))
  return Array.from(merged.values()).sort((left, right) => left.date.localeCompare(right.date))
}
