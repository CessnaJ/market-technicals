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
  COLORS,
  DarvasBox,
  FibonacciData,
  IndicatorData,
  OHLCV,
  RelativeStrengthData,
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
  showSMA: boolean
  showBollinger: boolean
  showDarvas: boolean
  showFibonacci: boolean
  showWeinstein: boolean
  activeIndicator: 'rsi' | 'macd' | 'vpci' | 'rs'
}

interface HoverSnapshot {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  changePct: number | null
  sma: Record<string, number | null>
  bollinger?: {
    upper: number | null
    middle: number | null
    lower: number | null
  }
  rsi?: number | null
  macd?: {
    value: number | null
    signal: number | null
    histogram: number | null
  }
  vpci?: {
    value: number | null
    signal?: string
  }
  stage?: {
    stage: number
    label: string
    ma30w: number | null
    mansfield: number | null
  } | null
  rs?: {
    stock: number
    benchmark: number
    ratio: number
    mansfield: number | null
  } | null
}

type StageOverlayPoint = {
  date: string
  stage: number
  stageLabel: string
  ma30w: number | null
  mansfield: number | null
}

const SMA_COLOR_PALETTE = ['#f59e0b', '#3b82f6', '#8b5cf6', '#ec4899', '#10b981', '#f43f5e']

export default function CandlestickChart({
  data,
  indicators,
  darvasBoxes,
  fibonacci,
  weinstein,
  relativeStrength,
  scale,
  showSMA,
  showBollinger,
  showDarvas,
  showFibonacci,
  showWeinstein,
  activeIndicator,
}: CandlestickChartProps) {
  const mainContainerRef = useRef<HTMLDivElement>(null)
  const indicatorContainerRef = useRef<HTMLDivElement>(null)
  const mainChartRef = useRef<IChartApi | null>(null)
  const indicatorChartRef = useRef<IChartApi | null>(null)

  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const smaSeriesRefs = useRef<Record<string, ISeriesApi<'Line'>>>({})
  const bollingerSeriesRefs = useRef<ISeriesApi<'Line'>[]>([])
  const darvasSeriesRefs = useRef<ISeriesApi<'Line'>[]>([])
  const fibonacciSeriesRefs = useRef<ISeriesApi<'Line'>[]>([])
  const weinsteinMaSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const stageStripSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const bottomSeriesRefs = useRef<ISeriesApi<any>[]>([])
  const [hoveredDateKey, setHoveredDateKey] = useState<string | null>(null)

  const stageOverlay = useMemo(
    () => buildStageOverlayData(data, weinstein?.stage_history ?? []),
    [data, weinstein?.stage_history]
  )
  const hoverLookup = useMemo(
    () => buildHoverLookup(data, indicators, stageOverlay, relativeStrength),
    [data, indicators, relativeStrength, stageOverlay]
  )
  const latestKey = useMemo(() => (data.length > 0 ? data[data.length - 1].date : null), [data])
  const activeSnapshot = useMemo(
    () => (hoveredDateKey && hoverLookup[hoveredDateKey]) || (latestKey ? hoverLookup[latestKey] : null),
    [hoverLookup, hoveredDateKey, latestKey]
  )

  const priceChangePct =
    data.length > 1 && data[data.length - 2].close !== 0
      ? ((data[data.length - 1].close - data[data.length - 2].close) / data[data.length - 2].close) * 100
      : null
  const headlineChange = hoveredDateKey ? activeSnapshot?.changePct ?? null : priceChangePct

  useEffect(() => {
    if (!mainContainerRef.current || !indicatorContainerRef.current) {
      return
    }

    const mainChart = createChart(mainContainerRef.current, {
      width: mainContainerRef.current.clientWidth,
      height: 450,
      layout: { background: { type: ColorType.Solid, color: COLORS.background }, textColor: COLORS.text },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      crosshair: { mode: 1 },
      rightPriceScale: {
        mode: scale === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
        borderColor: '#1f2937',
      },
      timeScale: { borderColor: '#1f2937', timeVisible: true, rightOffset: 5 },
    })

    const indicatorChart = createChart(indicatorContainerRef.current, {
      width: indicatorContainerRef.current.clientWidth,
      height: 180,
      layout: { background: { type: ColorType.Solid, color: COLORS.background }, textColor: COLORS.text },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      timeScale: { borderColor: '#1f2937', timeVisible: true },
      rightPriceScale: { borderColor: '#1f2937' },
    })

    mainChartRef.current = mainChart
    indicatorChartRef.current = indicatorChart

    let isSyncing = false
    const mainTimeScale = mainChart.timeScale()
    const indicatorTimeScale = indicatorChart.timeScale()

    const syncHandler = (target: any) => (range: LogicalRange | null) => {
      if (isSyncing || !range) {
        return
      }
      isSyncing = true
      target.setVisibleLogicalRange(range)
      isSyncing = false
    }

    mainTimeScale.subscribeVisibleLogicalRangeChange(syncHandler(indicatorTimeScale))
    indicatorTimeScale.subscribeVisibleLogicalRangeChange(syncHandler(mainTimeScale))

    candlestickSeriesRef.current = mainChart.addCandlestickSeries({
      upColor: COLORS.candleUp,
      downColor: COLORS.candleDown,
      borderUpColor: COLORS.candleUp,
      borderDownColor: COLORS.candleDown,
      wickUpColor: COLORS.candleUp,
      wickDownColor: COLORS.candleDown,
    })

    volumeSeriesRef.current = mainChart.addHistogramSeries({
      priceScaleId: 'volume',
      priceFormat: { type: 'volume' },
      priceLineVisible: false,
      lastValueVisible: false,
    })

    mainChart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.78, bottom: 0.12 },
      visible: false,
    })

    return () => {
      mainChart.remove()
      indicatorChart.remove()
    }
  }, [])

  useEffect(() => {
    if (!mainChartRef.current) {
      return
    }

    const chart = mainChartRef.current
    const handleCrosshairMove = (param: any) => {
      if (!param?.time) {
        setHoveredDateKey(null)
        return
      }

      const timeValue =
        typeof param.time === 'number'
          ? param.time
          : Date.UTC(param.time.year, param.time.month - 1, param.time.day) / 1000
      const dateKey = new Date(timeValue * 1000).toISOString().slice(0, 10)
      setHoveredDateKey(hoverLookup[dateKey] ? dateKey : null)
    }

    chart.subscribeCrosshairMove(handleCrosshairMove)
    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
    }
  }, [hoverLookup])

  useEffect(() => {
    if (!mainChartRef.current || !indicatorChartRef.current || !candlestickSeriesRef.current) {
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
        color: Number(item.close) >= Number(item.open) ? 'rgba(34, 197, 94, 0.35)' : 'rgba(239, 68, 68, 0.35)',
      }))
      volumeSeriesRef.current.setData(volumeData)
    }

    const smaPeriods = Object.keys(indicators?.sma ?? {}).sort((left, right) => Number(left) - Number(right))
    smaPeriods.forEach((period, index) => {
      const smaData = indicators?.sma?.[period]
      if (showSMA && smaData) {
        if (!smaSeriesRefs.current[period]) {
          smaSeriesRefs.current[period] = mainChartRef.current!.addLineSeries({
            color: getSmaColor(period, index),
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: false,
          })
        }
        smaSeriesRefs.current[period].setData(
          smaData
            .map((item) => ({ time: toChartTime(item.date), value: Number(item.value) }))
            .filter((item) => !Number.isNaN(item.value))
        )
      } else if (smaSeriesRefs.current[period]) {
        mainChartRef.current!.removeSeries(smaSeriesRefs.current[period])
        delete smaSeriesRefs.current[period]
      }
    })

    Object.keys(smaSeriesRefs.current).forEach((period) => {
      if (!smaPeriods.includes(period) || !showSMA) {
        mainChartRef.current?.removeSeries(smaSeriesRefs.current[period])
        delete smaSeriesRefs.current[period]
      }
    })

    if (showBollinger && indicators?.bollinger) {
      if (bollingerSeriesRefs.current.length === 0) {
        bollingerSeriesRefs.current = [
          mainChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.12)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }),
          mainChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.2)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }),
          mainChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.12)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }),
        ]
      }
      const bollingerData = indicators.bollinger
      bollingerSeriesRefs.current[0].setData(bollingerData.map((item) => ({ time: toChartTime(item.date), value: Number(item.upper) })))
      bollingerSeriesRefs.current[1].setData(bollingerData.map((item) => ({ time: toChartTime(item.date), value: Number(item.middle) })))
      bollingerSeriesRefs.current[2].setData(bollingerData.map((item) => ({ time: toChartTime(item.date), value: Number(item.lower) })))
    } else {
      bollingerSeriesRefs.current.forEach((series) => mainChartRef.current?.removeSeries(series))
      bollingerSeriesRefs.current = []
    }

    darvasSeriesRefs.current.forEach((series) => mainChartRef.current?.removeSeries(series))
    darvasSeriesRefs.current = []
    if (showDarvas && darvasBoxes) {
      const activeBox = darvasBoxes.find((box) => box.status === 'ACTIVE') ?? darvasBoxes[0]
      if (activeBox?.top && activeBox?.bottom) {
        const topSeries = mainChartRef.current.addLineSeries({
          color: COLORS.darvasBorder,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        })
        const bottomSeries = mainChartRef.current.addLineSeries({
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

    fibonacciSeriesRefs.current.forEach((series) => mainChartRef.current?.removeSeries(series))
    fibonacciSeriesRefs.current = []
    if (showFibonacci && fibonacci?.levels && data.length > 0) {
      const firstTime = toChartTime(data[0].date)
      const lastTime = toChartTime(data[data.length - 1].date)
      fibonacciSeriesRefs.current = Object.entries(fibonacci.levels).map(([level, price]) => {
        const series = mainChartRef.current!.addLineSeries({
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
        weinsteinMaSeriesRef.current = mainChartRef.current.addLineSeries({
          color: '#fb923c',
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: false,
        })
      }

      if (!stageStripSeriesRef.current) {
        stageStripSeriesRef.current = mainChartRef.current.addHistogramSeries({
          priceScaleId: 'stage-strip',
          priceFormat: { type: 'volume' },
          priceLineVisible: false,
          lastValueVisible: false,
        })
        mainChartRef.current.priceScale('stage-strip').applyOptions({
          scaleMargins: { top: 0.9, bottom: 0.02 },
          visible: false,
        })
      }

      weinsteinMaSeriesRef.current.setData(
        stageOverlay
          .filter((item) => item.ma30w != null)
          .map((item) => ({ time: toChartTime(item.date), value: Number(item.ma30w) }))
      )
      stageStripSeriesRef.current.setData(
        stageOverlay.map((item) => ({
          time: toChartTime(item.date),
          value: 1,
          color: getStageColor(item.stage, 0.55),
        }))
      )
    } else {
      if (weinsteinMaSeriesRef.current) {
        mainChartRef.current.removeSeries(weinsteinMaSeriesRef.current)
        weinsteinMaSeriesRef.current = null
      }
      if (stageStripSeriesRef.current) {
        mainChartRef.current.removeSeries(stageStripSeriesRef.current)
        stageStripSeriesRef.current = null
      }
    }

    updateBottomIndicator(indicatorChartRef.current, bottomSeriesRefs, activeIndicator, indicators, relativeStrength)
    mainChartRef.current.timeScale().fitContent()
    indicatorChartRef.current.timeScale().fitContent()
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
    stageOverlay,
  ])

  useEffect(() => {
    mainChartRef.current?.applyOptions({
      rightPriceScale: { mode: scale === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal },
    })
  }, [scale])

  useEffect(() => {
    const handleResize = () => {
      const width = mainContainerRef.current?.clientWidth || 0
      mainChartRef.current?.applyOptions({ width })
      indicatorChartRef.current?.applyOptions({ width })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const smaLegend = useMemo(
    () =>
      Object.keys(indicators?.sma ?? {})
        .sort((left, right) => Number(left) - Number(right))
        .map((period, index) => ({
          period,
          color: getSmaColor(period, index),
          value: activeSnapshot?.sma?.[period] ?? null,
        })),
    [activeSnapshot?.sma, indicators?.sma]
  )

  return (
    <div className="w-full">
      <div className="mb-4 grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <div className="rounded-2xl border border-gray-800 bg-[#0b0e14] p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">
                {hoveredDateKey ? 'Hover Snapshot' : 'Current Value'}
              </div>
              <div className="mt-2 flex items-baseline gap-3">
                <div className="text-3xl font-black">{activeSnapshot ? formatPrice(activeSnapshot.close) : '-'}</div>
                <div className={`text-sm font-black ${headlineChange != null && headlineChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {headlineChange != null ? `${headlineChange >= 0 ? '+' : ''}${headlineChange.toFixed(2)}%` : '-'}
                </div>
              </div>
            </div>
            <div className="text-right text-xs text-gray-400">
              <div>{activeSnapshot?.date ?? '-'}</div>
              {activeSnapshot?.stage && (
                <div className="mt-1">
                  Stage {activeSnapshot.stage.stage} · {activeSnapshot.stage.label}
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <InfoPill label="Open" value={activeSnapshot ? formatPrice(activeSnapshot.open) : '-'} />
            <InfoPill label="High" value={activeSnapshot ? formatPrice(activeSnapshot.high) : '-'} />
            <InfoPill label="Low" value={activeSnapshot ? formatPrice(activeSnapshot.low) : '-'} />
            <InfoPill label="Close" value={activeSnapshot ? formatPrice(activeSnapshot.close) : '-'} />
            <InfoPill label="Volume" value={activeSnapshot ? formatVolume(activeSnapshot.volume) : '-'} />
            <InfoPill label="Change" value={activeSnapshot?.changePct != null ? `${activeSnapshot.changePct >= 0 ? '+' : ''}${activeSnapshot.changePct.toFixed(2)}%` : '-'} />
          </div>
        </div>

        <div className="rounded-2xl border border-gray-800 bg-[#0b0e14] p-4">
          <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">SMA Legend</div>
          <div className="mt-3 space-y-2">
            {smaLegend.length > 0 ? (
              smaLegend.map((item) => (
                <div key={item.period} className="flex items-center justify-between rounded-xl bg-[#131722] px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                    <span className="font-black text-gray-100">SMA {item.period}</span>
                  </div>
                  <span className="font-mono text-gray-300">{item.value != null ? formatPrice(item.value) : '-'}</span>
                </div>
              ))
            ) : (
              <div className="text-sm text-gray-500">No SMA data</div>
            )}
          </div>

          {(activeSnapshot?.rs || activeSnapshot?.stage) && (
            <div className="mt-4 space-y-2 rounded-xl border border-gray-800 bg-[#131722] p-3 text-xs">
              {activeSnapshot?.stage && (
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">30W MA / Mansfield</span>
                  <span className="font-bold text-gray-100">
                    {activeSnapshot.stage.ma30w != null ? formatPrice(activeSnapshot.stage.ma30w) : '-'} / {activeSnapshot.stage.mansfield != null ? `${activeSnapshot.stage.mansfield >= 0 ? '+' : ''}${activeSnapshot.stage.mansfield.toFixed(2)}` : '-'}
                  </span>
                </div>
              )}
              {activeSnapshot?.rs && (
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">RS Stock / Benchmark / Ratio</span>
                  <span className="font-bold text-gray-100">
                    {activeSnapshot.rs.stock.toFixed(2)} / {activeSnapshot.rs.benchmark.toFixed(2)} / {activeSnapshot.rs.ratio.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2 w-full relative">
        <div ref={mainContainerRef} className="w-full bg-[#131722] rounded-t-xl border-x border-t border-gray-800 overflow-hidden shadow-2xl" />
        <div ref={indicatorContainerRef} className="w-full bg-[#131722] rounded-b-xl border border-gray-800 overflow-hidden shadow-2xl" />
      </div>
    </div>
  )
}

function updateBottomIndicator(
  chart: IChartApi,
  refs: MutableRefObject<ISeriesApi<any>[]>,
  type: 'rsi' | 'macd' | 'vpci' | 'rs',
  indicators: CandlestickChartProps['indicators'],
  relativeStrength?: RelativeStrengthData | null,
) {
  refs.current.forEach((series) => chart.removeSeries(series))
  refs.current = []

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
    series.setMarkers(
      data
        .filter((item) => item.signal && item.signal.includes('DIVERGE'))
        .map((item) => ({
          time: item.time,
          position: item.signal === 'DIVERGE_BEAR' ? 'aboveBar' : 'belowBar',
          color: item.signal === 'DIVERGE_BEAR' ? '#ef4444' : '#22c55e',
          shape: 'circle',
          text: 'Div',
        })) as any
    )
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
      while (
        historyIndex + 1 < sortedHistory.length &&
        sortedHistory[historyIndex + 1].date <= point.date
      ) {
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
): Record<string, HoverSnapshot> {
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

  return data.reduce<Record<string, HoverSnapshot>>((accumulator, item, index) => {
    const previousClose = index > 0 ? data[index - 1].close : null
    accumulator[item.date] = {
      date: item.date,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: item.volume,
      changePct:
        previousClose != null && previousClose !== 0
          ? ((item.close - previousClose) / previousClose) * 100
          : null,
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

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-[#131722] px-3 py-2">
      <div className="text-[10px] font-black tracking-[0.18em] text-gray-500 uppercase">{label}</div>
      <div className="mt-1 text-sm font-bold text-gray-100">{value}</div>
    </div>
  )
}

function toChartTime(dateValue: string): Time {
  return (new Date(dateValue).getTime() / 1000) as Time
}

function getSmaColor(_period: string, index: number) {
  return SMA_COLOR_PALETTE[index % SMA_COLOR_PALETTE.length]
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
