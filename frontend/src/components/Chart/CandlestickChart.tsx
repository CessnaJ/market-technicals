import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ColorType, LineData, CandlestickData, Time } from 'lightweight-charts'
import { OHLCV, IndicatorData, BollingerData, DarvasBox, WeinsteinData, COLORS } from '../../types'

interface CandlestickChartProps {
  data: OHLCV[]
  indicators?: {
    sma?: Record<string, IndicatorData[]>
    bollinger?: BollingerData[]
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
}: CandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRefs = useRef<{
    candlestick?: any
    sma5?: any
    sma10?: any
    sma20?: any
    sma60?: any
    sma120?: any
    bollingerUpper?: any
    bollingerMiddle?: any
    bollingerLower?: any
    darvasBox?: any
    fibonacciLines?: any[]
    weinsteinBackground?: any
  }>({})

  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 500,
      layout: {
        background: { type: ColorType.Solid, color: COLORS.background },
        textColor: COLORS.text,
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        mode: scale === 'log' ? 2 : 0,
        borderColor: '#1f2937',
      },
      timeScale: {
        borderColor: '#1f2937',
        timeVisible: true,
      },
    })

    chartRef.current = chart

    // 캔들스틱 시리즈
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: COLORS.candleUp,
      downColor: COLORS.candleDown,
      borderUpColor: COLORS.candleUp,
      borderDownColor: COLORS.candleDown,
      wickUpColor: COLORS.candleUp,
      wickDownColor: COLORS.candleDown,
    })
    seriesRefs.current.candlestick = candlestickSeries

    // Weinstein Stage 배경색
    if (showWeinstein && weinstein) {
      const weinsteinSeries = chart.addAreaSeries({
        lineColor: 'transparent',
        topColor: getWeinsteinColor(weinstein.current_stage),
        bottomColor: 'transparent',
        priceLineVisible: false,
      })
      seriesRefs.current.weinsteinBackground = weinsteinSeries
    }

    return () => {
      chart.remove()
    }
  }, [])

  // 데이터 업데이트
  useEffect(() => {
    if (!chartRef.current || !seriesRefs.current.candlestick) return

    // 캔들 데이터
    const candleData: CandlestickData[] = data.map((d) => ({
      time: new Date(d.date).getTime() / 1000 as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))
    seriesRefs.current.candlestick.setData(candleData)

    // SMA 라인
    if (showSMA && indicators?.sma) {
      updateSMA(chartRef.current, seriesRefs.current, '5', indicators.sma['5'])
      updateSMA(chartRef.current, seriesRefs.current, '10', indicators.sma['10'])
      updateSMA(chartRef.current, seriesRefs.current, '20', indicators.sma['20'])
      updateSMA(chartRef.current, seriesRefs.current, '60', indicators.sma['60'])
      updateSMA(chartRef.current, seriesRefs.current, '120', indicators.sma['120'])
    }

    // 볼린저밴드
    if (showBollinger && indicators?.bollinger) {
      updateBollinger(chartRef.current, seriesRefs.current, indicators.bollinger)
    }

    // 다바스 박스
    if (showDarvas && darvasBoxes) {
      updateDarvasBoxes(chartRef.current, seriesRefs.current, darvasBoxes)
    }

    // 피보나치
    if (showFibonacci && fibonacci) {
      updateFibonacci(chartRef.current, seriesRefs.current, fibonacci.levels)
    }

    // Weinstein 배경색 업데이트
    if (showWeinstein && weinstein && seriesRefs.current.weinsteinBackground) {
      const weinsteinData = data.map((d) => ({
        time: new Date(d.date).getTime() / 1000 as Time,
        value: weinstein.ma_30w,
      }))
      seriesRefs.current.weinsteinBackground.setData(weinsteinData)
    }
  }, [data, indicators, darvasBoxes, fibonacci, weinstein, showSMA, showBollinger, showDarvas, showFibonacci, showWeinstein])

  // 스케일 변경
  useEffect(() => {
    if (!chartRef.current) return
    chartRef.current.applyOptions({
      rightPriceScale: {
        mode: scale === 'log' ? 2 : 0,
      },
    })
  }, [scale])

  // 리사이즈 핸들러
  useEffect(() => {
    const handleResize = () => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div ref={chartContainerRef} className="w-full h-[500px]" />
  )
}

// 헬퍼 함수들
function updateSMA(chart: IChartApi, refs: any, period: string, data: IndicatorData[] | undefined) {
  const key = `sma${period}` as keyof typeof refs
  if (!data || data.length === 0) {
    if (refs[key]) {
      chart.removeSeries(refs[key])
      refs[key] = undefined
    }
    return
  }

  const smaData: LineData[] = data.map((d) => ({
    time: new Date(d.date).getTime() / 1000 as Time,
    value: d.value,
  }))

  const colors: Record<string, string> = {
    '5': '#f59e0b',
    '10': '#3b82f6',
    '20': '#8b5cf6',
    '60': '#ec4899',
    '120': '#6b7280',
  }

  if (!refs[key]) {
    refs[key] = chart.addLineSeries({
      color: colors[period] || '#9ca3af',
      lineWidth: 1,
      priceLineVisible: false,
    })
  }

  refs[key].setData(smaData)
}

function updateBollinger(chart: IChartApi, refs: any, data: BollingerData[] | undefined) {
  if (!data || data.length === 0) {
    if (refs.bollingerUpper) {
      chart.removeSeries(refs.bollingerUpper)
      refs.bollingerUpper = undefined
      refs.bollingerMiddle = undefined
      refs.bollingerLower = undefined
    }
    return
  }

  const upperData: LineData[] = data.map((d) => ({
    time: new Date(d.date).getTime() / 1000 as Time,
    value: d.upper,
  }))

  const middleData: LineData[] = data.map((d) => ({
    time: new Date(d.date).getTime() / 1000 as Time,
    value: d.middle,
  }))

  const lowerData: LineData[] = data.map((d) => ({
    time: new Date(d.date).getTime() / 1000 as Time,
    value: d.lower,
  }))

  if (!refs.bollingerUpper) {
    refs.bollingerUpper = chart.addLineSeries({
      color: 'rgba(239, 68, 68, 0.3)',
      lineWidth: 1,
      priceLineVisible: false,
    })
    refs.bollingerMiddle = chart.addLineSeries({
      color: 'rgba(156, 163, 175, 0.5)',
      lineWidth: 1,
      priceLineVisible: false,
    })
    refs.bollingerLower = chart.addLineSeries({
      color: 'rgba(239, 68, 68, 0.3)',
      lineWidth: 1,
      priceLineVisible: false,
    })
  }

  refs.bollingerUpper.setData(upperData)
  refs.bollingerMiddle.setData(middleData)
  refs.bollingerLower.setData(lowerData)
}

function updateDarvasBoxes(chart: IChartApi, refs: any, boxes: DarvasBox[]) {
  // 기존 박스 제거
  if (refs.darvasBox) {
    chart.removeSeries(refs.darvasBox)
    refs.darvasBox = undefined
  }

  if (!boxes || boxes.length === 0) return

  // 활성 박스만 표시
  const activeBox = boxes.find((b) => b.status === 'ACTIVE')
  if (!activeBox) return

  // 박스 오버레이 (수평선)
  const topLine = chart.addLineSeries({
    color: COLORS.darvasBorder,
    lineWidth: 2,
    priceLineVisible: false,
  })

  const bottomLine = chart.addLineSeries({
    color: COLORS.darvasBorder,
    lineWidth: 2,
    priceLineVisible: false,
  })

  const startDate = new Date(activeBox.start_date).getTime() / 1000
  const endDate = activeBox.end_date ? new Date(activeBox.end_date).getTime() / 1000 : Date.now() / 1000

  topLine.setData([
    { time: startDate as Time, value: activeBox.top },
    { time: endDate as Time, value: activeBox.top },
  ])

  bottomLine.setData([
    { time: startDate as Time, value: activeBox.bottom },
    { time: endDate as Time, value: activeBox.bottom },
  ])

  refs.darvasBox = { topLine, bottomLine }
}

function updateFibonacci(chart: IChartApi, refs: any, levels: Record<string, number>) {
  // 기존 라인 제거
  if (refs.fibonacciLines) {
    refs.fibonacciLines.forEach((line: any) => chart.removeSeries(line))
    refs.fibonacciLines = []
  }

  if (!levels || Object.keys(levels).length === 0) return

  const fibLines = Object.entries(levels).map(([_level, price]) => {
    const line = chart.addLineSeries({
      color: COLORS.fibonacciLine,
      lineWidth: 1,
      priceLineVisible: false,
      lineStyle: 2, // dashed
    })

    // 전체 범위에 라인 그리기
    const now = Date.now() / 1000
    line.setData([
      { time: now as Time, value: price },
      { time: (now - 86400 * 365) as Time, value: price },
    ])

    return line
  })

  refs.fibonacciLines = fibLines
}

function getWeinsteinColor(stage: number): string {
  switch (stage) {
    case 1:
      return COLORS.stage1
    case 2:
      return COLORS.stage2
    case 3:
      return COLORS.stage3
    case 4:
      return COLORS.stage4
    default:
      return 'transparent'
  }
}
