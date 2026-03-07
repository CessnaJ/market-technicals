import { MutableRefObject, useEffect, useMemo, useRef, useState } from 'react'
import {
  CandlestickData,
  ColorType,
  createChart,
  HistogramData,
  IChartApi,
  ISeriesApi,
  LineStyle,
  LogicalRange,
  PriceScaleMode,
  Time,
} from 'lightweight-charts'

import {
  BollingerData,
  ChartHoverSnapshot,
  COLORS,
  DarvasBox,
  FibonacciData,
  IndicatorData,
  OHLCV,
  RelativeStrengthData,
  SmaConfig,
  WeinsteinData,
} from '../../types'

interface CandlestickChartProps {
  data: OHLCV[]
  indicators?: {
    sma?: Record<string, IndicatorData[]>
    bollinger?: BollingerData[]
    rsi?: IndicatorData[]
    macd?: Array<{ date: string; value: number; signal: number; histogram: number }>
    vpci?: Array<{ date: string; value: number; signal?: string }>
  }
  darvasBoxes?: DarvasBox[]
  fibonacci?: FibonacciData | null
  weinstein?: WeinsteinData
  relativeStrength?: RelativeStrengthData | null
  scale: 'linear' | 'log'
  smaConfigs: SmaConfig[]
  headerCollapsed: boolean
  onToggleHeaderCollapsed: () => void
  onSmaConfigsChange: (configs: SmaConfig[]) => void
  showSMA: boolean
  showBollinger: boolean
  showDarvas: boolean
  showFibonacci: boolean
  showWeinstein: boolean
  activeIndicator: 'rsi' | 'macd' | 'vpci' | 'rs'
  onLoadOlder: () => Promise<number>
  isFetchingOlder: boolean
  hasMoreBefore: boolean
}

type StageOverlayPoint = {
  date: string
  stage: number
  stageLabel: string
  ma30w: number | null
  mansfield: number | null
}

type TooltipState = {
  visible: boolean
  x: number
  y: number
  dateKey: string | null
}

const MAX_SMA_LINES = 6
const AUTO_LOAD_THRESHOLD = 10
const AUTO_LOAD_DEBOUNCE_MS = 350
const RIGHT_SCALE_MIN_WIDTH = 84
const DEFAULT_SMA_COLORS = ['#f59e0b', '#3b82f6', '#8b5cf6', '#ec4899', '#10b981', '#f43f5e']
const STAGE_LEGEND = [
  { stage: 1, label: 'Accumulation' },
  { stage: 2, label: 'Markup' },
  { stage: 3, label: 'Distribution' },
  { stage: 4, label: 'Markdown' },
]

export default function CandlestickChart({
  data,
  indicators,
  darvasBoxes,
  fibonacci,
  weinstein,
  relativeStrength,
  scale,
  smaConfigs,
  headerCollapsed,
  onToggleHeaderCollapsed,
  onSmaConfigsChange,
  showSMA,
  showBollinger,
  showDarvas,
  showFibonacci,
  showWeinstein,
  activeIndicator,
  onLoadOlder,
  isFetchingOlder,
  hasMoreBefore,
}: CandlestickChartProps) {
  const priceContainerRef = useRef<HTMLDivElement>(null)
  const stageContainerRef = useRef<HTMLDivElement>(null)
  const volumeContainerRef = useRef<HTMLDivElement>(null)
  const indicatorContainerRef = useRef<HTMLDivElement>(null)

  const priceChartRef = useRef<IChartApi | null>(null)
  const stageChartRef = useRef<IChartApi | null>(null)
  const volumeChartRef = useRef<IChartApi | null>(null)
  const indicatorChartRef = useRef<IChartApi | null>(null)

  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const stageSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const stageTimelineSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const smaSeriesRefs = useRef<Record<string, ISeriesApi<'Line'>>>({})
  const bollingerSeriesRefs = useRef<ISeriesApi<'Line'>[]>([])
  const darvasSeriesRefs = useRef<ISeriesApi<'Line'>[]>([])
  const fibonacciSeriesRefs = useRef<ISeriesApi<'Line'>[]>([])
  const weinsteinMaSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const bottomSeriesRefs = useRef<ISeriesApi<any>[]>([])
  const latestVisibleRangeRef = useRef<LogicalRange | null>(null)
  const pendingPrependRangeRef = useRef<LogicalRange | null>(null)
  const previousWindowRef = useRef<{ oldest: string | null; newest: string | null; length: number }>({
    oldest: null,
    newest: null,
    length: 0,
  })
  const programmaticRangeChangeRef = useRef(false)
  const lastOlderLoadAtRef = useRef(0)
  const olderBoundaryInFlightRef = useRef<string | null>(null)
  const onLoadOlderRef = useRef(onLoadOlder)
  const isFetchingOlderRef = useRef(isFetchingOlder)
  const hasMoreBeforeRef = useRef(hasMoreBefore)

  const [tooltipState, setTooltipState] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    dateKey: null,
  })
  const [isSmaSettingsOpen, setIsSmaSettingsOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  const paneHeights = useMemo(() => getPaneHeights(isMobile), [isMobile])
  const orderedSmaConfigs = useMemo(
    () => [...smaConfigs].sort((left, right) => left.period - right.period),
    [smaConfigs]
  )
  const stageOverlay = useMemo(
    () => buildStageOverlayData(data, weinstein?.stage_history ?? []),
    [data, weinstein?.stage_history]
  )
  const hoverLookup = useMemo(
    () => buildHoverLookup(data, indicators, stageOverlay, relativeStrength),
    [data, indicators, relativeStrength, stageOverlay]
  )
  const latestKey = data.length > 0 ? data[data.length - 1].date : null
  const latestSnapshot = latestKey ? hoverLookup[latestKey] ?? null : null
  const tooltipSnapshot = tooltipState.dateKey ? hoverLookup[tooltipState.dateKey] ?? null : null
  const legendSnapshot = tooltipSnapshot ?? latestSnapshot
  const visibleSmaConfigs = orderedSmaConfigs.filter((config) => config.visible)
  const activeSmaCount = showSMA ? visibleSmaConfigs.length : 0

  useEffect(() => {
    onLoadOlderRef.current = onLoadOlder
  }, [onLoadOlder])

  useEffect(() => {
    isFetchingOlderRef.current = isFetchingOlder
  }, [isFetchingOlder])

  useEffect(() => {
    hasMoreBeforeRef.current = hasMoreBefore
  }, [hasMoreBefore])

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 768px)')
    const syncMediaState = () => setIsMobile(mediaQuery.matches)
    syncMediaState()
    mediaQuery.addEventListener('change', syncMediaState)
    return () => mediaQuery.removeEventListener('change', syncMediaState)
  }, [])

  useEffect(() => {
    if (!priceContainerRef.current || !stageContainerRef.current || !volumeContainerRef.current || !indicatorContainerRef.current) {
      return
    }

    const sharedLayout = {
      background: { type: ColorType.Solid as const, color: COLORS.background },
      textColor: COLORS.text,
    }
    const sharedGrid = {
      vertLines: { color: '#1f2937' },
      horzLines: { color: '#1f2937' },
    }
    const width = priceContainerRef.current.clientWidth

    const priceChart = createChart(priceContainerRef.current, {
      width,
      height: paneHeights.price,
      layout: sharedLayout,
      grid: sharedGrid,
      crosshair: { mode: 1 },
      rightPriceScale: {
        mode: scale === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
        borderColor: '#1f2937',
        minimumWidth: RIGHT_SCALE_MIN_WIDTH,
      },
      timeScale: {
        visible: false,
        borderColor: '#1f2937',
        timeVisible: true,
        rightOffset: 5,
      },
    })

    const stageChart = createChart(stageContainerRef.current, {
      width,
      height: paneHeights.stage,
      layout: sharedLayout,
      grid: {
        vertLines: { color: 'transparent' },
        horzLines: { color: 'transparent' },
      },
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      rightPriceScale: {
        visible: true,
        minimumWidth: RIGHT_SCALE_MIN_WIDTH,
        ticksVisible: false,
        borderColor: 'transparent',
        textColor: 'rgba(17, 24, 39, 0)',
      },
      leftPriceScale: { visible: false },
      timeScale: {
        visible: false,
        borderColor: '#1f2937',
        timeVisible: true,
      },
    })

    const volumeChart = createChart(volumeContainerRef.current, {
      width,
      height: paneHeights.volume,
      layout: sharedLayout,
      grid: sharedGrid,
      rightPriceScale: {
        borderColor: '#1f2937',
        minimumWidth: RIGHT_SCALE_MIN_WIDTH,
      },
      timeScale: {
        visible: false,
        borderColor: '#1f2937',
        timeVisible: true,
      },
    })

    const indicatorChart = createChart(indicatorContainerRef.current, {
      width,
      height: paneHeights.indicator,
      layout: sharedLayout,
      grid: sharedGrid,
      rightPriceScale: {
        borderColor: '#1f2937',
        minimumWidth: RIGHT_SCALE_MIN_WIDTH,
      },
      timeScale: {
        visible: true,
        borderColor: '#1f2937',
        timeVisible: true,
      },
    })

    priceChartRef.current = priceChart
    stageChartRef.current = stageChart
    volumeChartRef.current = volumeChart
    indicatorChartRef.current = indicatorChart

    candlestickSeriesRef.current = priceChart.addCandlestickSeries({
      upColor: COLORS.candleUp,
      downColor: COLORS.candleDown,
      borderUpColor: COLORS.candleUp,
      borderDownColor: COLORS.candleDown,
      wickUpColor: COLORS.candleUp,
      wickDownColor: COLORS.candleDown,
    })

    stageSeriesRef.current = stageChart.addHistogramSeries({
      priceScaleId: 'stage-strip',
      priceFormat: { type: 'volume' },
      priceLineVisible: false,
      lastValueVisible: false,
    })

    volumeSeriesRef.current = volumeChart.addHistogramSeries({
      priceScaleId: 'volume',
      priceFormat: { type: 'volume' },
      priceLineVisible: false,
      lastValueVisible: false,
    })
    stageTimelineSeriesRef.current = stageChart.addLineSeries({
      color: 'rgba(0,0,0,0)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })

    volumeChart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.08, bottom: 0.02 },
      visible: true,
      minimumWidth: RIGHT_SCALE_MIN_WIDTH,
    })
    stageChart.priceScale('stage-strip').applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.05 },
      visible: true,
      minimumWidth: RIGHT_SCALE_MIN_WIDTH,
      ticksVisible: false,
      borderColor: 'transparent',
      textColor: 'rgba(17, 24, 39, 0)',
    })

    const charts = [priceChart, stageChart, volumeChart, indicatorChart]
    let isSyncing = false
    const syncChartsToRange = (range: LogicalRange) => {
      latestVisibleRangeRef.current = range
      charts.forEach((targetChart) => {
        targetChart.timeScale().setVisibleLogicalRange(range)
      })
    }
    const maybeLoadOlder = async (range: LogicalRange) => {
      const currentOldest = previousWindowRef.current.oldest
      if (
        !currentOldest ||
        !hasMoreBeforeRef.current ||
        isFetchingOlderRef.current ||
        olderBoundaryInFlightRef.current === currentOldest
      ) {
        return
      }

      const now = Date.now()
      if (now - lastOlderLoadAtRef.current < AUTO_LOAD_DEBOUNCE_MS) {
        return
      }

      lastOlderLoadAtRef.current = now
      olderBoundaryInFlightRef.current = currentOldest
      pendingPrependRangeRef.current = range

      try {
        const addedCount = await onLoadOlderRef.current()
        if (addedCount <= 0) {
          pendingPrependRangeRef.current = null
        }
      } finally {
        if (previousWindowRef.current.oldest === currentOldest) {
          olderBoundaryInFlightRef.current = null
        }
      }
    }
    const subscriptions = charts.map((chart, index) => {
      const handler = (range: LogicalRange | null) => {
        if (isSyncing || !range) {
          return
        }
        isSyncing = true
        syncChartsToRange(range)
        isSyncing = false

        if (index === 0 && programmaticRangeChangeRef.current) {
          programmaticRangeChangeRef.current = false
          return
        }

        if (range.from <= AUTO_LOAD_THRESHOLD) {
          void maybeLoadOlder(range)
        }
      }
      chart.timeScale().subscribeVisibleLogicalRangeChange(handler)
      return { chart, handler }
    })

    return () => {
      subscriptions.forEach(({ chart, handler }) => {
        chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler)
      })
      priceChart.remove()
      stageChart.remove()
      volumeChart.remove()
      indicatorChart.remove()
    }
  }, [paneHeights.indicator, paneHeights.price, paneHeights.stage, paneHeights.volume])

  useEffect(() => {
    const charts = [
      { chart: priceChartRef.current, container: priceContainerRef.current, height: paneHeights.price },
      { chart: stageChartRef.current, container: stageContainerRef.current, height: paneHeights.stage },
      { chart: volumeChartRef.current, container: volumeContainerRef.current, height: paneHeights.volume },
      { chart: indicatorChartRef.current, container: indicatorContainerRef.current, height: paneHeights.indicator },
    ]

    const applyChartSizes = () => {
      charts.forEach(({ chart, container, height }) => {
        if (!chart || !container) {
          return
        }
        chart.applyOptions({
          width: container.clientWidth,
          height,
        })
      })
    }

    applyChartSizes()
    window.addEventListener('resize', applyChartSizes)
    return () => window.removeEventListener('resize', applyChartSizes)
  }, [paneHeights.indicator, paneHeights.price, paneHeights.stage, paneHeights.volume])

  useEffect(() => {
    if (!priceChartRef.current || !priceContainerRef.current) {
      return
    }

    const tooltipWidth = isMobile ? 240 : 300
    const tooltipHeight = isMobile ? 214 : 240
    const tooltipPadding = 12
    const tooltipOffsetX = isMobile ? 20 : 30
    const tooltipOffsetY = isMobile ? 24 : 34
    const tooltipFallbackGap = 18
    const handleCrosshairMove = (param: any) => {
      const point = param?.point
      if (!param?.time || !point || point.x < 0 || point.y < 0) {
        setTooltipState((current) => ({ ...current, visible: false, dateKey: null }))
        return
      }

      const timeValue =
        typeof param.time === 'number'
          ? param.time
          : Date.UTC(param.time.year, param.time.month - 1, param.time.day) / 1000
      const dateKey = new Date(timeValue * 1000).toISOString().slice(0, 10)

      if (!hoverLookup[dateKey]) {
        setTooltipState((current) => ({ ...current, visible: false, dateKey: null }))
        return
      }

      const containerWidth = priceContainerRef.current?.clientWidth ?? 0
      const containerHeight = priceContainerRef.current?.clientHeight ?? 0
      const maxX = Math.max(tooltipPadding, containerWidth - tooltipWidth - tooltipPadding)
      const maxY = Math.max(tooltipPadding, containerHeight - tooltipHeight - tooltipPadding)

      let nextX = point.x + tooltipOffsetX
      let nextY = point.y + tooltipOffsetY

      if (nextX > maxX) {
        nextX = point.x - tooltipWidth - tooltipFallbackGap
      }
      if (nextY > maxY) {
        nextY = point.y - tooltipHeight - tooltipFallbackGap
      }

      nextX = Math.min(Math.max(nextX, tooltipPadding), maxX)
      nextY = Math.min(Math.max(nextY, tooltipPadding), maxY)

      setTooltipState({
        visible: true,
        x: nextX,
        y: nextY,
        dateKey,
      })
    }

    priceChartRef.current.subscribeCrosshairMove(handleCrosshairMove)
    return () => priceChartRef.current?.unsubscribeCrosshairMove(handleCrosshairMove)
  }, [hoverLookup, isMobile])

  useEffect(() => {
    priceChartRef.current?.applyOptions({
      rightPriceScale: { mode: scale === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal },
    })
  }, [scale])

  useEffect(() => {
    if (
      !priceChartRef.current ||
      !volumeChartRef.current ||
      !indicatorChartRef.current ||
      !candlestickSeriesRef.current ||
      !stageChartRef.current
    ) {
      return
    }

    const validData = data.filter((item) => item.date && item.open != null && item.high != null && item.low != null && item.close != null)
    const candleData: CandlestickData[] = validData.map((item) => ({
      time: toChartTime(item.date),
      open: Number(item.open),
      high: Number(item.high),
      low: Number(item.low),
      close: Number(item.close),
    }))

    candlestickSeriesRef.current.setData(candleData)

    if (volumeSeriesRef.current) {
      const volumeData: HistogramData[] = validData.map((item) => ({
        time: toChartTime(item.date),
        value: Number(item.volume || 0),
        color: Number(item.close) >= Number(item.open) ? 'rgba(34, 197, 94, 0.55)' : 'rgba(239, 68, 68, 0.55)',
      }))
      volumeSeriesRef.current.setData(volumeData)
    }

    if (stageSeriesRef.current) {
      stageSeriesRef.current.setData(
        (showWeinstein ? stageOverlay : []).map((item) => ({
          time: toChartTime(item.date),
          value: 1,
          color: getStageColor(item.stage, 0.9),
        }))
      )
    }
    if (stageTimelineSeriesRef.current) {
      stageTimelineSeriesRef.current.setData(
        validData.map((item) => ({ time: toChartTime(item.date) }))
      )
    }

    const activeSmaIds = new Set<string>()
    orderedSmaConfigs.forEach((config) => {
      const periodKey = String(config.period)
      const seriesId = config.id
      const smaData = indicators?.sma?.[periodKey]

      if (showSMA && config.visible && smaData) {
        activeSmaIds.add(seriesId)
        if (!smaSeriesRefs.current[seriesId]) {
          smaSeriesRefs.current[seriesId] = priceChartRef.current!.addLineSeries({
            color: config.color,
            lineWidth: config.lineWidth,
            priceLineVisible: false,
            lastValueVisible: false,
          })
        }

        smaSeriesRefs.current[seriesId].applyOptions({
          color: config.color,
          lineWidth: config.lineWidth,
        })
        smaSeriesRefs.current[seriesId].setData(
          smaData
            .map((item) => ({ time: toChartTime(item.date), value: Number(item.value) }))
            .filter((item) => !Number.isNaN(item.value))
        )
      }
    })

    Object.entries(smaSeriesRefs.current).forEach(([seriesId, series]) => {
      if (!activeSmaIds.has(seriesId)) {
        priceChartRef.current?.removeSeries(series)
        delete smaSeriesRefs.current[seriesId]
      }
    })

    if (showBollinger && indicators?.bollinger) {
      if (bollingerSeriesRefs.current.length === 0) {
        bollingerSeriesRefs.current = [
          priceChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.12)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }),
          priceChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.2)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }),
          priceChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.12)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }),
        ]
      }
      const bollingerData = indicators.bollinger
      bollingerSeriesRefs.current[0].setData(bollingerData.map((item) => ({ time: toChartTime(item.date), value: Number(item.upper) })))
      bollingerSeriesRefs.current[1].setData(bollingerData.map((item) => ({ time: toChartTime(item.date), value: Number(item.middle) })))
      bollingerSeriesRefs.current[2].setData(bollingerData.map((item) => ({ time: toChartTime(item.date), value: Number(item.lower) })))
    } else {
      bollingerSeriesRefs.current.forEach((series) => priceChartRef.current?.removeSeries(series))
      bollingerSeriesRefs.current = []
    }

    darvasSeriesRefs.current.forEach((series) => priceChartRef.current?.removeSeries(series))
    darvasSeriesRefs.current = []
    if (showDarvas && darvasBoxes) {
      const activeBox = darvasBoxes.find((box) => box.status === 'ACTIVE') ?? darvasBoxes[0]
      if (activeBox?.top && activeBox?.bottom) {
        const topSeries = priceChartRef.current.addLineSeries({
          color: COLORS.darvasBorder,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        })
        const bottomSeries = priceChartRef.current.addLineSeries({
          color: COLORS.darvasBorder,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        })
        const start = toChartTime(activeBox.start_date)
        const end = toChartTime(activeBox.end_date ?? data[data.length - 1]?.date ?? activeBox.start_date)
        topSeries.setData([{ time: start, value: Number(activeBox.top) }, { time: end, value: Number(activeBox.top) }])
        bottomSeries.setData([{ time: start, value: Number(activeBox.bottom) }, { time: end, value: Number(activeBox.bottom) }])
        darvasSeriesRefs.current = [topSeries, bottomSeries]
      }
    }

    fibonacciSeriesRefs.current.forEach((series) => priceChartRef.current?.removeSeries(series))
    fibonacciSeriesRefs.current = []
    if (showFibonacci && fibonacci?.levels && data.length > 0) {
      const firstTime = toChartTime(data[0].date)
      const lastTime = toChartTime(data[data.length - 1].date)
      fibonacciSeriesRefs.current = Object.entries(fibonacci.levels).map(([level, price]) => {
        const series = priceChartRef.current!.addLineSeries({
          color: COLORS.fibonacciLine,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: true,
          title: level,
        })
        series.setData([{ time: firstTime, value: Number(price) }, { time: lastTime, value: Number(price) }])
        return series
      })
    }

    if (showWeinstein && stageOverlay.length > 0) {
      if (!weinsteinMaSeriesRef.current) {
        weinsteinMaSeriesRef.current = priceChartRef.current.addLineSeries({
          color: '#fb923c',
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: false,
        })
      }

      weinsteinMaSeriesRef.current.setData(
        stageOverlay
          .filter((item) => item.ma30w != null)
          .map((item) => ({ time: toChartTime(item.date), value: Number(item.ma30w) }))
      )
    } else if (weinsteinMaSeriesRef.current) {
      priceChartRef.current.removeSeries(weinsteinMaSeriesRef.current)
      weinsteinMaSeriesRef.current = null
    }

    updateBottomIndicator(
      indicatorChartRef.current,
      bottomSeriesRefs,
      activeIndicator,
      indicators,
      relativeStrength,
      validData.map((item) => item.date)
    )

    const currentWindow = {
      oldest: validData[0]?.date ?? null,
      newest: validData[validData.length - 1]?.date ?? null,
      length: validData.length,
    }
    const previousWindow = previousWindowRef.current
    const windowChanged =
      currentWindow.oldest !== previousWindow.oldest ||
      currentWindow.newest !== previousWindow.newest ||
      currentWindow.length !== previousWindow.length
    const isOlderPrepend =
      previousWindow.length > 0 &&
      currentWindow.length > previousWindow.length &&
      currentWindow.newest === previousWindow.newest &&
      currentWindow.oldest !== previousWindow.oldest

    if (windowChanged) {
      if (isOlderPrepend && pendingPrependRangeRef.current) {
        const addedBars = currentWindow.length - previousWindow.length
        programmaticRangeChangeRef.current = true
        priceChartRef.current.timeScale().setVisibleLogicalRange({
          from: pendingPrependRangeRef.current.from + addedBars,
          to: pendingPrependRangeRef.current.to + addedBars,
        })
        window.setTimeout(() => {
          programmaticRangeChangeRef.current = false
        }, 0)
      } else if (currentWindow.length > 0 && previousWindow.length === 0) {
        programmaticRangeChangeRef.current = true
        priceChartRef.current.timeScale().fitContent()
        window.setTimeout(() => {
          programmaticRangeChangeRef.current = false
        }, 0)
      }
    }

    latestVisibleRangeRef.current = priceChartRef.current.timeScale().getVisibleLogicalRange()
    if (currentWindow.oldest !== previousWindow.oldest) {
      olderBoundaryInFlightRef.current = null
    }
    pendingPrependRangeRef.current = null
    previousWindowRef.current = currentWindow
  }, [
    activeIndicator,
    darvasBoxes,
    data,
    fibonacci,
    indicators,
    relativeStrength,
    showBollinger,
    showDarvas,
    showFibonacci,
    showSMA,
    showWeinstein,
    orderedSmaConfigs,
    stageOverlay,
  ])

  const inlineLegend = visibleSmaConfigs.map((config) => ({
    ...config,
    value: showSMA ? legendSnapshot?.sma?.[String(config.period)] ?? null : null,
  }))

  return (
    <div className="w-full">
      <div className="mb-4 rounded-2xl border border-gray-800 bg-[#0b0e14] p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">Chart Summary</div>
              <div className="mt-1 flex items-baseline gap-3">
                <div className="text-3xl font-black">{latestSnapshot ? formatPrice(latestSnapshot.close) : '-'}</div>
                <div className={`text-sm font-black ${(latestSnapshot?.changePct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {latestSnapshot?.changePct != null ? `${latestSnapshot.changePct >= 0 ? '+' : ''}${latestSnapshot.changePct.toFixed(2)}%` : '-'}
                </div>
              </div>
            </div>
            {latestSnapshot?.stage && (
              <div
                className="rounded-full px-3 py-1 text-[11px] font-black text-white"
                style={{ backgroundColor: getStageColor(latestSnapshot.stage.stage, 1) }}
              >
                STAGE {latestSnapshot.stage.stage}
              </div>
            )}
            <div className="rounded-full border border-gray-800 bg-[#131722] px-3 py-1 text-[11px] font-black text-gray-300">
              ACTIVE SMA {activeSmaCount}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isFetchingOlder && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-amber-200">
                Loading History
              </div>
            )}
            <button
              type="button"
              onClick={() => setIsSmaSettingsOpen((current) => !current)}
              className="rounded-lg border border-gray-700 bg-[#131722] px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-gray-200 hover:border-blue-500"
            >
              SMA Settings
            </button>
            <button
              type="button"
              onClick={onToggleHeaderCollapsed}
              className="rounded-lg border border-gray-700 bg-[#131722] px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-gray-200 hover:border-blue-500"
            >
              {headerCollapsed ? 'Expand' : 'Collapse'}
            </button>
          </div>
        </div>

        {!headerCollapsed && latestSnapshot && (
          <div className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_1fr]">
            <div className="rounded-2xl border border-gray-800 bg-[#131722] p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">Latest Snapshot</div>
                  <div className="mt-2 text-xs text-gray-400">{latestSnapshot.date}</div>
                </div>
                {latestSnapshot.stage && (
                  <div className="text-right text-xs text-gray-400">
                    Stage {latestSnapshot.stage.stage} · {latestSnapshot.stage.label}
                  </div>
                )}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <InfoPill label="Open" value={formatPrice(latestSnapshot.open)} />
                <InfoPill label="High" value={formatPrice(latestSnapshot.high)} />
                <InfoPill label="Low" value={formatPrice(latestSnapshot.low)} />
                <InfoPill label="Close" value={formatPrice(latestSnapshot.close)} />
                <InfoPill label="Volume" value={formatVolume(latestSnapshot.volume)} />
                <InfoPill label="Change" value={latestSnapshot.changePct != null ? `${latestSnapshot.changePct >= 0 ? '+' : ''}${latestSnapshot.changePct.toFixed(2)}%` : '-'} />
              </div>
            </div>

            <div className="rounded-2xl border border-gray-800 bg-[#131722] p-4">
              <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">SMA / RS Overview</div>
              <div className="mt-3 space-y-2">
                {inlineLegend.length > 0 ? (
                  inlineLegend.map((item) => (
                    <div key={item.id} className="flex items-center justify-between rounded-xl bg-[#0b0e14] px-3 py-2 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                        <span className="font-black text-gray-100">SMA {item.period}</span>
                      </div>
                      <span className="font-mono text-gray-300">{item.value != null ? formatPrice(item.value) : '-'}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-gray-500">No visible SMA lines</div>
                )}
              </div>

              {(latestSnapshot.rs || latestSnapshot.stage) && (
                <div className="mt-4 space-y-2 rounded-xl border border-gray-800 bg-[#0b0e14] p-3 text-xs">
                  {latestSnapshot.stage && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">30W MA / Mansfield</span>
                      <span className="font-bold text-gray-100">
                        {latestSnapshot.stage.ma30w != null ? formatPrice(latestSnapshot.stage.ma30w) : '-'} / {latestSnapshot.stage.mansfield != null ? `${latestSnapshot.stage.mansfield >= 0 ? '+' : ''}${latestSnapshot.stage.mansfield.toFixed(2)}` : '-'}
                      </span>
                    </div>
                  )}
                  {latestSnapshot.rs && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">RS Stock / Benchmark / Ratio</span>
                      <span className="font-bold text-gray-100">
                        {latestSnapshot.rs.stock.toFixed(2)} / {latestSnapshot.rs.benchmark.toFixed(2)} / {latestSnapshot.rs.ratio.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {isSmaSettingsOpen && (
          <div className="mt-4 rounded-2xl border border-gray-800 bg-[#131722] p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">SMA Config Editor</div>
                <div className="mt-1 text-xs text-gray-400">Period changes refetch data. Color, width, visibility update immediately.</div>
              </div>
              <button
                type="button"
                onClick={() => setIsSmaSettingsOpen(false)}
                className="rounded-lg border border-gray-700 bg-[#0b0e14] px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-gray-200"
              >
                Close
              </button>
            </div>

            <div className="max-h-72 space-y-3 overflow-y-auto pr-1">
              {orderedSmaConfigs.map((config) => (
                <div key={config.id} className="grid gap-3 rounded-xl border border-gray-800 bg-[#0b0e14] p-3 lg:grid-cols-[auto_120px_90px_90px_auto]">
                  <label className="flex items-center gap-2 text-sm font-bold text-gray-200">
                    <input
                      type="checkbox"
                      checked={config.visible}
                      onChange={(event) => updateSmaConfig(config.id, { visible: event.target.checked }, orderedSmaConfigs, onSmaConfigsChange)}
                    />
                    SHOW
                  </label>

                  <input
                    type="number"
                    min={2}
                    max={240}
                    value={config.period}
                    onChange={(event) => updateSmaPeriod(config.id, Number(event.target.value), orderedSmaConfigs, onSmaConfigsChange)}
                    className="rounded-lg border border-gray-700 bg-[#131722] px-3 py-2 text-sm font-bold outline-none focus:border-blue-500"
                  />

                  <input
                    type="color"
                    value={config.color}
                    onChange={(event) => updateSmaConfig(config.id, { color: event.target.value }, orderedSmaConfigs, onSmaConfigsChange)}
                    className="h-10 w-full rounded-lg border border-gray-700 bg-[#131722] px-2 py-1"
                  />

                  <select
                    value={config.lineWidth}
                    onChange={(event) => updateSmaConfig(config.id, { lineWidth: Number(event.target.value) as 1 | 2 | 3 | 4 }, orderedSmaConfigs, onSmaConfigsChange)}
                    className="rounded-lg border border-gray-700 bg-[#131722] px-3 py-2 text-sm font-bold outline-none focus:border-blue-500"
                  >
                    <option value={1}>WIDTH 1</option>
                    <option value={2}>WIDTH 2</option>
                    <option value={3}>WIDTH 3</option>
                    <option value={4}>WIDTH 4</option>
                  </select>

                  <button
                    type="button"
                    onClick={() => removeSmaConfig(config.id, orderedSmaConfigs, onSmaConfigsChange)}
                    disabled={orderedSmaConfigs.length <= 1}
                    className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-red-300 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => addSmaConfig(orderedSmaConfigs, onSmaConfigsChange)}
                disabled={orderedSmaConfigs.length >= MAX_SMA_LINES}
                className="rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-blue-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Add SMA Line
              </button>
              <div className="text-xs text-gray-500">Max {MAX_SMA_LINES} lines</div>
            </div>
          </div>
        )}
      </div>

      <div className="relative">
        <div ref={priceContainerRef} className="w-full overflow-hidden rounded-t-2xl border border-gray-800 bg-[#131722] shadow-2xl" />

      {showSMA && inlineLegend.length > 0 && (
        <div className="pointer-events-auto absolute left-3 top-3 z-20 flex max-w-[calc(100%-1.5rem)] flex-wrap items-center gap-2 rounded-xl border border-gray-800 bg-[#0b0e14]/95 px-3 py-2 shadow-xl">
            {inlineLegend.map((item) => (
              <div key={item.id} className="flex items-center gap-2 rounded-full border border-gray-800 bg-[#131722] px-3 py-1 text-[11px] font-black">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                <span>SMA {item.period}</span>
                <span className="font-mono text-gray-400">{item.value != null ? formatPrice(item.value) : '-'}</span>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setIsSmaSettingsOpen((current) => !current)}
              className="rounded-full border border-gray-700 bg-[#131722] px-3 py-1 text-[11px] font-black uppercase tracking-[0.18em] text-gray-200"
            >
              Gear
            </button>
          </div>
        )}

        {tooltipState.visible && tooltipSnapshot && (
          <div
            className="pointer-events-none absolute z-30 w-[240px] max-w-[calc(100%-1.5rem)] rounded-2xl border border-white/10 bg-[#08111d]/62 p-3.5 shadow-[0_16px_34px_rgba(0,0,0,0.28)] backdrop-blur-md sm:w-[300px]"
            style={{ left: tooltipState.x, top: tooltipState.y }}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">Hover Tooltip</div>
                <div className="mt-1 text-sm font-bold text-gray-100">{tooltipSnapshot.date}</div>
              </div>
              {tooltipSnapshot.stage && (
                <div
                  className="rounded-full px-3 py-1 text-[10px] font-black text-white"
                  style={{ backgroundColor: getStageColor(tooltipSnapshot.stage.stage, 1) }}
                >
                  STAGE {tooltipSnapshot.stage.stage}
                </div>
              )}
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <TooltipRow label="Open" value={formatPrice(tooltipSnapshot.open)} />
              <TooltipRow label="High" value={formatPrice(tooltipSnapshot.high)} />
              <TooltipRow label="Low" value={formatPrice(tooltipSnapshot.low)} />
              <TooltipRow label="Close" value={formatPrice(tooltipSnapshot.close)} />
              <TooltipRow label="Change" value={tooltipSnapshot.changePct != null ? `${tooltipSnapshot.changePct >= 0 ? '+' : ''}${tooltipSnapshot.changePct.toFixed(2)}%` : '-'} />
              <TooltipRow label="Volume" value={formatVolume(tooltipSnapshot.volume)} />
            </div>

            {showSMA && visibleSmaConfigs.length > 0 && (
              <div className="mt-3 space-y-2">
                <div className="text-[10px] font-black tracking-[0.18em] text-gray-500 uppercase">Visible SMA</div>
                {visibleSmaConfigs.map((config) => (
                  <div key={config.id} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-gray-300">
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: config.color }} />
                      <span>SMA {config.period}</span>
                    </div>
                    <span className="font-mono text-gray-100">{tooltipSnapshot.sma[String(config.period)] != null ? formatPrice(tooltipSnapshot.sma[String(config.period)] as number) : '-'}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-3 grid gap-2 border-t border-white/10 pt-3 sm:grid-cols-2">
              {buildActiveIndicatorRows(activeIndicator, tooltipSnapshot).map((row) => (
                <TooltipRow key={row.label} label={row.label} value={row.value} />
              ))}
              <TooltipRow
                label="Mansfield"
                value={
                  tooltipSnapshot.rs?.mansfield != null
                    ? `${tooltipSnapshot.rs.mansfield >= 0 ? '+' : ''}${tooltipSnapshot.rs.mansfield.toFixed(2)}`
                    : tooltipSnapshot.stage?.mansfield != null
                      ? `${tooltipSnapshot.stage.mansfield >= 0 ? '+' : ''}${tooltipSnapshot.stage.mansfield.toFixed(2)}`
                      : '-'
                }
              />
            </div>
          </div>
        )}
      </div>

      <div ref={stageContainerRef} className="w-full border-x border-gray-800 bg-[#131722]" />

      {showWeinstein && (
        <div className="flex flex-wrap items-center gap-2 border-x border-gray-800 bg-[#131722] px-3 py-2">
          {STAGE_LEGEND.map((item) => (
            <div key={item.stage} className="flex items-center gap-2 rounded-full border border-gray-800 bg-[#0b0e14] px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-gray-300">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: getStageColor(item.stage, 1) }} />
              <span>{item.stage} {item.label}</span>
            </div>
          ))}
        </div>
      )}

      <div ref={volumeContainerRef} className="w-full border-x border-t border-gray-800 bg-[#131722]" />
      <div ref={indicatorContainerRef} className="w-full overflow-hidden rounded-b-2xl border border-gray-800 bg-[#131722] shadow-2xl" />
    </div>
  )
}

function updateBottomIndicator(
  chart: IChartApi,
  refs: MutableRefObject<ISeriesApi<any>[]>,
  type: 'rsi' | 'macd' | 'vpci' | 'rs',
  indicators: CandlestickChartProps['indicators'],
  relativeStrength?: RelativeStrengthData | null,
  timelineDates: string[] = [],
) {
  refs.current.forEach((series) => chart.removeSeries(series))
  refs.current = []

  if (timelineDates.length > 0) {
    const anchorSeries = chart.addLineSeries({
      color: 'rgba(0,0,0,0)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    anchorSeries.setData(timelineDates.map((date) => ({ time: toChartTime(date) })))
    refs.current.push(anchorSeries)
  }

  if (type === 'rsi' && indicators?.rsi) {
    const series = chart.addLineSeries({ color: '#8b5cf6', lineWidth: 2, title: 'RSI' })
    series.setData(
      indicators.rsi
        .map((item) => ({ time: toChartTime(item.date), value: Number(item.value) }))
        .filter((item) => !Number.isNaN(item.value))
    )
    series.createPriceLine({ price: 70, color: 'rgba(239, 68, 68, 0.45)', lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: '70' })
    series.createPriceLine({ price: 30, color: 'rgba(34, 197, 94, 0.45)', lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: '30' })
    refs.current.push(series)
    return
  }

  if (type === 'macd' && indicators?.macd) {
    const histogram = chart.addHistogramSeries({ title: 'Histogram', priceFormat: { type: 'volume' } })
    const macdLine = chart.addLineSeries({ color: '#3b82f6', lineWidth: 2, title: 'MACD' })
    const signalLine = chart.addLineSeries({ color: '#f59e0b', lineWidth: 2, title: 'Signal' })
    const data = indicators.macd
      .map((item) => ({
        time: toChartTime(item.date),
        macd: Number(item.value),
        signal: Number(item.signal),
        histogram: Number(item.histogram),
      }))
      .filter((item) => !Number.isNaN(item.macd))
    histogram.setData(
      data.map((item) => ({
        time: item.time,
        value: item.histogram,
        color: item.histogram >= 0 ? 'rgba(34, 197, 94, 0.45)' : 'rgba(239, 68, 68, 0.45)',
      }))
    )
    macdLine.setData(data.map((item) => ({ time: item.time, value: item.macd })))
    signalLine.setData(data.map((item) => ({ time: item.time, value: item.signal })))
    refs.current.push(histogram, macdLine, signalLine)
    return
  }

  if (type === 'vpci' && indicators?.vpci) {
    const series = chart.addLineSeries({ color: '#f8fafc', lineWidth: 2, title: 'VPCI' })
    const data = indicators.vpci
      .map((item) => ({ time: toChartTime(item.date), value: Number(item.value), signal: item.signal }))
      .filter((item) => !Number.isNaN(item.value))
    series.setData(data.map((item) => ({ time: item.time, value: item.value })))
    refs.current.push(series)
    return
  }

  if (type === 'rs' && relativeStrength?.series) {
    const stockSeries = chart.addLineSeries({ color: '#38bdf8', lineWidth: 2, title: 'Stock' })
    const benchmarkSeries = chart.addLineSeries({ color: '#94a3b8', lineWidth: 2, title: 'Benchmark' })
    const ratioSeries = chart.addLineSeries({ color: '#22c55e', lineWidth: 2, lineStyle: LineStyle.Dashed, title: 'RS Ratio' })

    stockSeries.setData(relativeStrength.series.map((item) => ({ time: toChartTime(item.date), value: item.stock_performance })))
    benchmarkSeries.setData(relativeStrength.series.map((item) => ({ time: toChartTime(item.date), value: item.benchmark_performance })))
    ratioSeries.setData(relativeStrength.series.map((item) => ({ time: toChartTime(item.date), value: item.relative_ratio })))
    refs.current.push(stockSeries, benchmarkSeries, ratioSeries)
  }
}

function buildStageOverlayData(data: OHLCV[], history: NonNullable<WeinsteinData['stage_history']>): StageOverlayPoint[] {
  if (!history || history.length === 0) {
    return []
  }

  const sortedHistory = [...history].sort((left, right) => left.date.localeCompare(right.date))
  let historyIndex = 0
  let currentHistory = sortedHistory[historyIndex]

  return data
    .map((point) => {
      while (historyIndex + 1 < sortedHistory.length && sortedHistory[historyIndex + 1].date <= point.date) {
        historyIndex += 1
        currentHistory = sortedHistory[historyIndex]
      }

      if (!currentHistory || currentHistory.date > point.date) {
        return null
      }

      return {
        date: point.date,
        stage: currentHistory.stage,
        stageLabel: currentHistory.stage_label,
        ma30w: currentHistory.ma_30w,
        mansfield: currentHistory.mansfield_rs,
      }
    })
    .filter((item): item is StageOverlayPoint => item != null)
}

function buildHoverLookup(
  data: OHLCV[],
  indicators: CandlestickChartProps['indicators'],
  stageOverlay: StageOverlayPoint[],
  relativeStrength?: RelativeStrengthData | null,
): Record<string, ChartHoverSnapshot> {
  const smaMap = new Map<string, Record<string, number>>()
  Object.entries(indicators?.sma ?? {}).forEach(([period, values]) => {
    values.forEach((item) => {
      const entry = smaMap.get(item.date) ?? {}
      entry[period] = item.value
      smaMap.set(item.date, entry)
    })
  })

  const bollingerMap = new Map<string, BollingerData>()
  indicators?.bollinger?.forEach((item) => bollingerMap.set(item.date, item))

  const rsiMap = new Map<string, number>()
  indicators?.rsi?.forEach((item) => rsiMap.set(item.date, item.value))

  const macdMap = new Map<string, { value: number; signal: number; histogram: number }>()
  indicators?.macd?.forEach((item) => macdMap.set(item.date, item))

  const vpciMap = new Map<string, { value: number; signal?: string }>()
  indicators?.vpci?.forEach((item) => vpciMap.set(item.date, item))

  const stageMap = new Map<string, StageOverlayPoint>()
  stageOverlay.forEach((item) => stageMap.set(item.date, item))

  const rsMap = new Map<string, RelativeStrengthData['series'][number]>()
  relativeStrength?.series?.forEach((item) => rsMap.set(item.date, item))

  return data.reduce<Record<string, ChartHoverSnapshot>>((accumulator, item, index) => {
    const previousClose = index > 0 ? data[index - 1].close : null
    accumulator[item.date] = {
      date: item.date,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: item.volume,
      changePct: previousClose != null && previousClose !== 0 ? ((item.close - previousClose) / previousClose) * 100 : null,
      sma: smaMap.get(item.date) ?? {},
      bollinger: bollingerMap.has(item.date)
        ? {
            upper: bollingerMap.get(item.date)?.upper ?? null,
            middle: bollingerMap.get(item.date)?.middle ?? null,
            lower: bollingerMap.get(item.date)?.lower ?? null,
          }
        : undefined,
      rsi: rsiMap.get(item.date) ?? null,
      macd: macdMap.has(item.date)
        ? {
            value: macdMap.get(item.date)?.value ?? null,
            signal: macdMap.get(item.date)?.signal ?? null,
            histogram: macdMap.get(item.date)?.histogram ?? null,
          }
        : undefined,
      vpci: vpciMap.has(item.date)
        ? {
            value: vpciMap.get(item.date)?.value ?? null,
            signal: vpciMap.get(item.date)?.signal,
          }
        : undefined,
      stage: stageMap.has(item.date)
        ? {
            stage: stageMap.get(item.date)!.stage,
            label: stageMap.get(item.date)!.stageLabel,
            ma30w: stageMap.get(item.date)!.ma30w,
            mansfield: stageMap.get(item.date)!.mansfield,
          }
        : null,
      rs: rsMap.has(item.date)
        ? {
            stock: rsMap.get(item.date)!.stock_performance,
            benchmark: rsMap.get(item.date)!.benchmark_performance,
            ratio: rsMap.get(item.date)!.relative_ratio,
            mansfield: rsMap.get(item.date)!.mansfield_rs,
          }
        : null,
    }
    return accumulator
  }, {})
}

function updateSmaConfig(
  id: string,
  patch: Partial<SmaConfig>,
  configs: SmaConfig[],
  onChange: (configs: SmaConfig[]) => void,
) {
  onChange(configs.map((config) => (config.id === id ? { ...config, ...patch } : config)))
}

function updateSmaPeriod(
  id: string,
  nextPeriod: number,
  configs: SmaConfig[],
  onChange: (configs: SmaConfig[]) => void,
) {
  const normalizedPeriod = Math.min(240, Math.max(2, Math.round(nextPeriod || 2)))
  const hasDuplicate = configs.some((config) => config.id !== id && config.period === normalizedPeriod)
  if (hasDuplicate) {
    return
  }

  onChange(configs.map((config) => (config.id === id ? { ...config, period: normalizedPeriod } : config)))
}

function addSmaConfig(configs: SmaConfig[], onChange: (configs: SmaConfig[]) => void) {
  if (configs.length >= MAX_SMA_LINES) {
    return
  }

  const usedPeriods = new Set(configs.map((config) => config.period))
  const fallbackPeriod = [5, 10, 20, 30, 60, 120, 180].find((period) => !usedPeriods.has(period)) ?? (configs[configs.length - 1]?.period ?? 10) + 5

  onChange([
    ...configs,
    {
      id: `sma-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      visible: true,
      period: Math.min(240, fallbackPeriod),
      color: DEFAULT_SMA_COLORS[configs.length % DEFAULT_SMA_COLORS.length],
      lineWidth: 2,
    },
  ])
}

function removeSmaConfig(
  id: string,
  configs: SmaConfig[],
  onChange: (configs: SmaConfig[]) => void,
) {
  if (configs.length <= 1) {
    return
  }
  onChange(configs.filter((config) => config.id !== id))
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-[#0b0e14] px-3 py-2">
      <div className="text-[10px] font-black tracking-[0.18em] text-gray-500 uppercase">{label}</div>
      <div className="mt-1 text-sm font-bold text-gray-100">{value}</div>
    </div>
  )
}

function TooltipRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2">
      <div className="text-[10px] font-black tracking-[0.16em] text-gray-500 uppercase">{label}</div>
      <div className="mt-1 text-xs font-bold text-gray-100">{value}</div>
    </div>
  )
}

function buildActiveIndicatorRows(
  activeIndicator: CandlestickChartProps['activeIndicator'],
  snapshot: ChartHoverSnapshot,
) {
  if (activeIndicator === 'rsi') {
    return [{ label: 'RSI', value: snapshot.rsi != null ? snapshot.rsi.toFixed(2) : '-' }]
  }

  if (activeIndicator === 'macd') {
    return [
      { label: 'MACD', value: snapshot.macd?.value != null ? snapshot.macd.value.toFixed(2) : '-' },
      { label: 'MACD Signal', value: snapshot.macd?.signal != null ? snapshot.macd.signal.toFixed(2) : '-' },
      { label: 'Histogram', value: snapshot.macd?.histogram != null ? snapshot.macd.histogram.toFixed(2) : '-' },
    ]
  }

  if (activeIndicator === 'vpci') {
    return [
      { label: 'VPCI', value: snapshot.vpci?.value != null ? snapshot.vpci.value.toFixed(2) : '-' },
      { label: 'VPCI Signal', value: snapshot.vpci?.signal ?? '-' },
    ]
  }

  if (activeIndicator === 'rs') {
    return [
      { label: 'RS Stock', value: snapshot.rs ? snapshot.rs.stock.toFixed(2) : '-' },
      { label: 'RS Benchmark', value: snapshot.rs ? snapshot.rs.benchmark.toFixed(2) : '-' },
      { label: 'RS Ratio', value: snapshot.rs ? snapshot.rs.ratio.toFixed(2) : '-' },
    ]
  }

  return []
}

function getPaneHeights(isMobile: boolean) {
  return isMobile
    ? { price: 400, stage: 12, volume: 110, indicator: 150 }
    : { price: 560, stage: 14, volume: 140, indicator: 180 }
}

function toChartTime(dateValue: string): Time {
  return (new Date(dateValue).getTime() / 1000) as Time
}

function getStageColor(stage: number, alpha = 1) {
  const colorMap: Record<number, [number, number, number]> = {
    1: [139, 92, 246],
    2: [22, 163, 74],
    3: [234, 88, 12],
    4: [220, 38, 38],
  }

  const [red, green, blue] = colorMap[stage] ?? [75, 85, 99]
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
}

function formatPrice(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function formatVolume(value: number) {
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)}B`
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(2)}K`
  }
  return String(value)
}
