import { useEffect, useRef } from 'react'
import { 
  createChart, 
  IChartApi, 
  ColorType, 
  CandlestickData, 
  Time, 
  LogicalRange, 
  HistogramData,
  ISeriesApi,
  LineStyle,
  PriceScaleMode
} from 'lightweight-charts'
import { OHLCV, IndicatorData, BollingerData, DarvasBox, WeinsteinData, COLORS } from '../../types'

interface CandlestickChartProps {
  data: OHLCV[]
  indicators?: {
    sma?: Record<string, IndicatorData[]>
    bollinger?: BollingerData[]
    rsi?: IndicatorData[]
    macd?: any[]
    vpci?: any[]
  }
  darvasBoxes?: DarvasBox[]
  fibonacci?: { levels: Record<string, number> }
  weinstein?: WeinsteinData
  scale: 'linear' | 'log'
  showSMA: boolean
  showBollinger: boolean
  showDarvas: boolean
  showFibonacci: boolean
  showWeinstein: boolean
  activeIndicator: 'rsi' | 'macd' | 'vpci'
  onLoadMore?: () => void;
  isRefetching?: boolean; 
}

export default function CandlestickChart({
  data,
  indicators,
  darvasBoxes,
  fibonacci,
  weinstein,
  scale,
  showSMA,
  showBollinger,
  showDarvas,
  showFibonacci,
  showWeinstein,
  activeIndicator,
  onLoadMore,     
  isRefetching,   
}: CandlestickChartProps) {
  // --- Refs ---
  const mainContainerRef = useRef<HTMLDivElement>(null)
  const indicatorContainerRef = useRef<HTMLDivElement>(null)
  const mainChartRef = useRef<IChartApi | null>(null)
  const indicatorChartRef = useRef<IChartApi | null>(null)
  
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null)
  const smaSeriesRefs = useRef<Record<string, ISeriesApi<"Line">>>({})
  const bollingerSeriesRefs = useRef<ISeriesApi<"Line">[]>([])
  const darvasSeriesRefs = useRef<ISeriesApi<"Line">[]>([])
  const fibonacciSeriesRefs = useRef<ISeriesApi<"Line">[]>([])
  const weinsteinSeriesRef = useRef<ISeriesApi<"Area"> | null>(null)
  const bottomSeriesRefs = useRef<ISeriesApi<any>[]>([])

  const fetchThrottleRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 1. 차트 초기화
  useEffect(() => {
    if (!mainContainerRef.current || !indicatorContainerRef.current) return

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
    })

    mainChartRef.current = mainChart
    indicatorChartRef.current = indicatorChart

    // X축 동기화
    let isSyncing = false
    const mainTimeScale = mainChart.timeScale()
    const indTimeScale = indicatorChart.timeScale()

    const syncHandler = (target: any) => (range: LogicalRange | null) => {
      if (isSyncing || !range) return
      isSyncing = true
      target.setVisibleLogicalRange(range)
      isSyncing = false
    }

    mainTimeScale.subscribeVisibleLogicalRangeChange(syncHandler(indTimeScale))
    indTimeScale.subscribeVisibleLogicalRangeChange(syncHandler(mainTimeScale))

    candlestickSeriesRef.current = mainChart.addCandlestickSeries({
      upColor: COLORS.candleUp, downColor: COLORS.candleDown, borderUpColor: COLORS.candleUp,
      borderDownColor: COLORS.candleDown, wickUpColor: COLORS.candleUp, wickDownColor: COLORS.candleDown,
    })

    volumeSeriesRef.current = mainChart.addHistogramSeries({
      priceScaleId: 'volume',
      priceFormat: { type: 'volume' },
    })

    mainChart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
      visible: false,
    })

    return () => {
      mainChart.remove()
      indicatorChart.remove()
    }
  }, [])

  // 2. 스크롤 트리거
  useEffect(() => {
    if (!mainChartRef.current || !onLoadMore) return
    const handleRangeChange = (logicalRange: LogicalRange | null) => {
      if (logicalRange && logicalRange.from < 15 && !isRefetching) {
        if (fetchThrottleRef.current) return
        fetchThrottleRef.current = setTimeout(() => {
          onLoadMore()
          fetchThrottleRef.current = null
        }, 1500)
      }
    }
    mainChartRef.current.timeScale().subscribeVisibleLogicalRangeChange(handleRangeChange)
    return () => mainChartRef.current?.timeScale().unsubscribeVisibleLogicalRangeChange(handleRangeChange)
  }, [onLoadMore, isRefetching])

  // 3. 데이터 업데이트 통합 로직
  useEffect(() => {
    if (!mainChartRef.current || !indicatorChartRef.current || !candlestickSeriesRef.current) return

    const validData = data.filter(d => d.date && d.open != null && d.high != null && d.low != null && d.close != null)
    
    // [A] 캔들
    const candleData: CandlestickData[] = validData.map(d => ({
      time: (new Date(d.date).getTime() / 1000) as Time,
      open: Number(d.open), high: Number(d.high), low: Number(d.low), close: Number(d.close),
    })).sort((a, b) => (a.time as number) - (b.time as number))
    
    candlestickSeriesRef.current.setData(candleData)

    // [B] 거래량
    if (volumeSeriesRef.current) {
      const volumeData: HistogramData[] = validData.map(d => ({
        time: (new Date(d.date).getTime() / 1000) as Time,
        value: Number(d.volume || 0),
        color: Number(d.close) >= Number(d.open) ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)'
      })).sort((a, b) => (a.time as number) - (b.time as number))
      volumeSeriesRef.current.setData(volumeData)
    }

    // [C] SMA (빌드 에러 수정: lineWidth as any)
    const smaPeriods = ['5', '10', '20', '60', '120']
    const smaColors: any = { '5': '#f59e0b', '10': '#3b82f6', '20': '#8b5cf6', '60': '#ec4899', '120': '#6b7280' }
    
    smaPeriods.forEach(p => {
      const smaData = indicators?.sma?.[p]
      if (showSMA && smaData) {
        if (!smaSeriesRefs.current[p]) {
          smaSeriesRefs.current[p] = mainChartRef.current!.addLineSeries({ 
            color: smaColors[p], lineWidth: 1 as any, priceLineVisible: false, lastValueVisible: false 
          })
        }
        smaSeriesRefs.current[p].setData(
          smaData.map(i => ({ time: (new Date(i.date).getTime() / 1000) as Time, value: Number(i.value) }))
          .filter(i => !isNaN(i.value)).sort((a, b) => (a.time as number) - (b.time as number))
        )
      } else if (smaSeriesRefs.current[p]) {
        mainChartRef.current!.removeSeries(smaSeriesRefs.current[p])
        delete smaSeriesRefs.current[p]
      }
    })

    // [D] 볼린저 (빌드 에러 수정: lineWidth as any)
    if (showBollinger && indicators?.bollinger) {
      if (bollingerSeriesRefs.current.length === 0) {
        const common = { lineWidth: 1 as any, priceLineVisible: false, lastValueVisible: false }
        bollingerSeriesRefs.current = [
          mainChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.1)', ...common }),
          mainChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.2)', ...common }),
          mainChartRef.current.addLineSeries({ color: 'rgba(255,255,255,0.1)', ...common })
        ]
      }
      const bData = indicators.bollinger
      const getTime = (d: string) => (new Date(d).getTime() / 1000) as Time
      bollingerSeriesRefs.current[0].setData(bData.map(i => ({ time: getTime(i.date), value: Number(i.upper) })))
      bollingerSeriesRefs.current[1].setData(bData.map(i => ({ time: getTime(i.date), value: Number(i.middle) })))
      bollingerSeriesRefs.current[2].setData(bData.map(i => ({ time: getTime(i.date), value: Number(i.lower) })))
    } else {
      bollingerSeriesRefs.current.forEach(s => mainChartRef.current?.removeSeries(s))
      bollingerSeriesRefs.current = []
    }

    // [E] 다바스
    darvasSeriesRefs.current.forEach(s => mainChartRef.current?.removeSeries(s))
    darvasSeriesRefs.current = []
    if (showDarvas && darvasBoxes) {
      const active = darvasBoxes.find(b => b.status === 'ACTIVE')
      if (active && active.top && active.bottom) {
        const t = mainChartRef.current.addLineSeries({ color: COLORS.darvasBorder, lineWidth: 2 as any, priceLineVisible: false })
        const b = mainChartRef.current.addLineSeries({ color: COLORS.darvasBorder, lineWidth: 2 as any, priceLineVisible: false })
        const start = (new Date(active.start_date).getTime() / 1000) as Time
        const end = (active.end_date ? new Date(active.end_date).getTime() / 1000 : Date.now() / 1000) as Time
        t.setData([{ time: start, value: Number(active.top) }, { time: end, value: Number(active.top) }])
        b.setData([{ time: start, value: Number(active.bottom) }, { time: end, value: Number(active.bottom) }])
        darvasSeriesRefs.current = [t, b]
      }
    }

    // [F] 피보나치
    fibonacciSeriesRefs.current.forEach(s => mainChartRef.current?.removeSeries(s))
    fibonacciSeriesRefs.current = []
    if (showFibonacci && fibonacci?.levels) {
      fibonacciSeriesRefs.current = Object.entries(fibonacci.levels).map(([lv, price]) => {
        const s = mainChartRef.current!.addLineSeries({ 
          color: COLORS.fibonacciLine, lineWidth: 1 as any, lineStyle: LineStyle.Dashed, 
          priceLineVisible: false, lastValueVisible: true, title: lv 
        })
        const now = (Date.now() / 1000) as Time
        const past = (now as number - 86400 * 365 * 2) as Time
        s.setData([{ time: past, value: Number(price) }, { time: now, value: Number(price) }])
        return s
      })
    }

    // [G] 바인스타인
    if (showWeinstein && weinstein) {
      if (!weinsteinSeriesRef.current) {
        weinsteinSeriesRef.current = mainChartRef.current.addAreaSeries({
          lineColor: 'transparent', topColor: getWeinsteinColor(weinstein.current_stage), bottomColor: 'transparent', priceLineVisible: false, lastValueVisible: false,
        })
      }
      const maVal = Number(weinstein.ma_30w)
      if (!isNaN(maVal)) {
        weinsteinSeriesRef.current.setData(candleData.map(c => ({ time: c.time, value: maVal })))
        weinsteinSeriesRef.current.applyOptions({ topColor: getWeinsteinColor(weinstein.current_stage) })
      }
    } else if (weinsteinSeriesRef.current) {
      mainChartRef.current.removeSeries(weinsteinSeriesRef.current)
      weinsteinSeriesRef.current = null
    }

    updateBottomIndicator(indicatorChartRef.current!, bottomSeriesRefs, activeIndicator, indicators)

  }, [data, indicators, darvasBoxes, fibonacci, weinstein, showSMA, showBollinger, showDarvas, showFibonacci, showWeinstein, activeIndicator])

  useEffect(() => {
    mainChartRef.current?.applyOptions({
      rightPriceScale: { mode: scale === 'log' ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal }
    })
  }, [scale])

  useEffect(() => {
    const handleResize = () => {
      const w = mainContainerRef.current?.clientWidth || 0
      mainChartRef.current?.applyOptions({ width: w })
      indicatorChartRef.current?.applyOptions({ width: w })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className="flex flex-col gap-2 w-full relative">
      {isRefetching && (
        <div className="absolute top-4 left-4 z-20 bg-blue-600/90 backdrop-blur-md text-[10px] font-bold text-white px-3 py-1 rounded-full shadow-2xl animate-pulse">
          HISTORICAL DATA SYNCING...
        </div>
      )}
      <div ref={mainContainerRef} className="w-full bg-[#131722] rounded-t-xl border-x border-t border-gray-800 overflow-hidden shadow-2xl" />
      <div ref={indicatorContainerRef} className="w-full bg-[#131722] rounded-b-xl border border-gray-800 overflow-hidden shadow-2xl" />
    </div>
  )
}

function updateBottomIndicator(
  chart: IChartApi, 
  refs: React.MutableRefObject<ISeriesApi<any>[]>, 
  type: string, 
  indicators: any
) {
  refs.current.forEach(s => chart.removeSeries(s))
  refs.current = []
  if (!indicators) return

  const getTime = (d: string) => (new Date(d).getTime() / 1000) as Time

  if (type === 'rsi' && indicators.rsi) {
    const s = chart.addLineSeries({ color: '#8b5cf6', lineWidth: 2 as any, title: 'RSI' })
    s.setData(indicators.rsi.map((i: any) => ({ time: getTime(i.date), value: Number(i.value) })).filter((i: any) => !isNaN(i.value)).sort((a: any, b: any) => (a.time as number) - (b.time as number)))
    s.createPriceLine({ price: 70, color: 'rgba(239, 68, 68, 0.5)', lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: '70' })
    s.createPriceLine({ price: 30, color: 'rgba(34, 197, 94, 0.5)', lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: '30' })
    refs.current.push(s)
  } 
  else if (type === 'macd' && indicators.macd) {
    const hist = chart.addHistogramSeries({ title: 'Histogram', priceFormat: { type: 'volume' } })
    const line = chart.addLineSeries({ color: '#3b82f6', lineWidth: 2 as any, title: 'MACD' })
    const signal = chart.addLineSeries({ color: '#f59e0b', lineWidth: 2 as any, title: 'Signal' })
    const data = indicators.macd.map((i: any) => ({ time: getTime(i.date), m: Number(i.macd || i.value), s: Number(i.signal), h: Number(i.histogram) })).filter((i: any) => !isNaN(i.m)).sort((a: any, b: any) => (a.time as number) - (b.time as number))
    hist.setData(data.map((i: any) => ({ time: i.time, value: i.h, color: i.h >= 0 ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)' })))
    line.setData(data.map((i: any) => ({ time: i.time, value: i.m }))); signal.setData(data.map((i: any) => ({ time: i.time, value: i.s })))
    refs.current.push(hist, line, signal)
  }
  else if (type === 'vpci' && indicators.vpci) {
    const s = chart.addLineSeries({ color: '#f8fafc', lineWidth: 2 as any, title: 'VPCI' })
    const data = indicators.vpci.map((i: any) => ({ time: getTime(i.date), value: Number(i.value), signal: i.signal })).filter((i: any) => !isNaN(i.value)).sort((a: any, b: any) => (a.time as number) - (b.time as number))
    s.setData(data)
    const markers = data.filter((i: any) => i.signal && i.signal.includes('DIVERGE')).map((i: any) => ({
      time: i.time, position: i.signal === 'DIVERGE_BEAR' ? 'aboveBar' : 'belowBar', color: i.signal === 'DIVERGE_BEAR' ? '#ef4444' : '#22c55e', shape: 'circle', text: 'Div'
    }))
    s.setMarkers(markers as any); refs.current.push(s)
  }
}

function getWeinsteinColor(stage: number | undefined): string {
  if (stage === 1) return 'rgba(156, 163, 175, 0.25)';
  if (stage === 2) return 'rgba(34, 197, 94, 0.25)';
  if (stage === 3) return 'rgba(245, 158, 11, 0.25)';
  if (stage === 4) return 'rgba(239, 68, 68, 0.25)';
  return 'transparent';
}