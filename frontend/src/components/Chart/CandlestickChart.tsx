import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ColorType, LineData, CandlestickData, Time, LogicalRange } from 'lightweight-charts'
import { OHLCV, IndicatorData, BollingerData, DarvasBox, WeinsteinData, COLORS } from '../../types'

interface CandlestickChartProps {
  data: OHLCV[]
  indicators?: {
    sma?: Record<string, IndicatorData[]>
    bollinger?: BollingerData[]
    rsi?: IndicatorData[]
    macd?: any[] // MACDData
    vpci?: any[] // VPCIData
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
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  
  const fetchThrottleRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  
  const seriesRefs = useRef<{
    candlestick?: any
    volume?: any
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
    indicatorSeries: any[]
  }>({ indicatorSeries: [] })

  // 1. 차트 초기화 및 레이아웃 분할
  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 600, // 패널이 늘어났으므로 높이 500 -> 600으로 증가
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
      timeScale: {
        borderColor: '#1f2937',
        timeVisible: true,
      },
      // 메인 차트 영역 (상단 60%)
      rightPriceScale: {
        mode: scale === 'log' ? 2 : 0,
        borderColor: '#1f2937',
        scaleMargins: {
          top: 0.05,
          bottom: 0.4, 
        },
      },
    })

    // 거래량 스케일 (중단 15%)
    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.65,
        bottom: 0.2,
      },
      visible: false, // y축 숫자 숨김
    })

    // 보조지표 스케일 (하단 20%)
    chart.priceScale('indicator').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
      borderColor: '#1f2937',
    })

    chartRef.current = chart

    // 캔들스틱 시리즈
    seriesRefs.current.candlestick = chart.addCandlestickSeries({
      upColor: COLORS.candleUp,
      downColor: COLORS.candleDown,
      borderUpColor: COLORS.candleUp,
      borderDownColor: COLORS.candleDown,
      wickUpColor: COLORS.candleUp,
      wickDownColor: COLORS.candleDown,
    })

    // 거래량 시리즈
    seriesRefs.current.volume = chart.addHistogramSeries({
      priceScaleId: 'volume',
      priceFormat: { type: 'volume' },
    })

    // Weinstein Stage 배경색
    if (showWeinstein && weinstein) {
      seriesRefs.current.weinsteinBackground = chart.addAreaSeries({
        lineColor: 'transparent',
        topColor: getWeinsteinColor(weinstein.current_stage),
        bottomColor: 'transparent',
        priceLineVisible: false,
      })
    }

    return () => {
      chart.remove()
    }
  },[])

  // 2. 스크롤 감지 및 Lazy Loading 로직
  useEffect(() => {
    if (!chartRef.current || !onLoadMore) return;

    const handleVisibleLogicalRangeChange = (logicalRange: LogicalRange | null) => {
      if (!logicalRange) return;

      if (logicalRange.from < 10 && !isRefetching) {
        if (fetchThrottleRef.current) return;

        fetchThrottleRef.current = setTimeout(() => {
          onLoadMore();
          fetchThrottleRef.current = null;
        }, 1000);
      }
    };

    chartRef.current.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleLogicalRangeChange);

    return () => {
      if (chartRef.current) {
        chartRef.current.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleLogicalRangeChange);
      }
      if (fetchThrottleRef.current) clearTimeout(fetchThrottleRef.current);
    };
  }, [onLoadMore, isRefetching]);


  // 3. 데이터 업데이트
  useEffect(() => {
    if (!chartRef.current || !seriesRefs.current.candlestick) return

    // 유효한 데이터 필터링
    const validData = data.filter(d => d.date && d.open != null && d.high != null && d.low != null && d.close != null)

    // 캔들 데이터
    const candleData: CandlestickData[] = validData
      .map((d) => ({
        time: new Date(d.date).getTime() / 1000 as Time,
        open: Number(d.open),
        high: Number(d.high),
        low: Number(d.low),
        close: Number(d.close),
      }))
      .sort((a, b) => (a.time as number) - (b.time as number))
      
    seriesRefs.current.candlestick.setData(candleData)

    // 거래량 데이터 주입 (양봉/음봉 색상 구분)
    const volumeData = validData
      .map((d) => ({
        time: new Date(d.date).getTime() / 1000 as Time,
        value: Number(d.volume || 0),
        color: Number(d.close) >= Number(d.open) ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)'
      }))
      .sort((a, b) => (a.time as number) - (b.time as number))

    if (seriesRefs.current.volume) {
      seriesRefs.current.volume.setData(volumeData)
    }

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
    if (showFibonacci && fibonacci && fibonacci.levels) {
      updateFibonacci(chartRef.current, seriesRefs.current, fibonacci.levels)
    }

    // Weinstein 배경색
    if (showWeinstein && weinstein && seriesRefs.current.weinsteinBackground) {
      const maValue = Number(weinstein.ma_30w) || 0
      const weinsteinData = candleData.map((d) => ({
        time: d.time,
        value: maValue,
      }))
      seriesRefs.current.weinsteinBackground.setData(weinsteinData)
    }

    // 하단 보조지표 업데이트 (RSI, MACD, VPCI)
    updateBottomIndicator(chartRef.current, seriesRefs.current, activeIndicator, indicators)

  }, [data, indicators, darvasBoxes, fibonacci, weinstein, showSMA, showBollinger, showDarvas, showFibonacci, showWeinstein, activeIndicator])

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
  },[])

  return (
    <div className="relative w-full">
      {isRefetching && (
        <div className="absolute top-2 left-2 z-10 bg-gray-800 text-xs text-white px-2 py-1 rounded shadow-md opacity-70">
          과거 데이터 로딩 중...
        </div>
      )}
      <div ref={chartContainerRef} className="w-full h-[600px]" />
    </div>
  )
}

// ----------------------
// 하단 지표 렌더링 함수
// ----------------------
function updateBottomIndicator(chart: IChartApi, refs: any, type: string, indicators: any) {
  // 1. 기존에 그려진 하단 지표 모두 지우기
  if (refs.indicatorSeries.length > 0) {
    refs.indicatorSeries.forEach((s: any) => chart.removeSeries(s))
    refs.indicatorSeries = []
  }

  if (!indicators) return

  if (type === 'rsi' && indicators.rsi) {
    // 수정: lineWidth를 1.5에서 2로 변경
    const rsiSeries = chart.addLineSeries({ priceScaleId: 'indicator', color: '#8b5cf6', lineWidth: 2 })
    
    rsiSeries.setData(indicators.rsi
      .filter((d: any) => d.value != null && !isNaN(Number(d.value)))
      .map((d: any) => ({
        time: new Date(d.date).getTime() / 1000 as Time, 
        value: Number(d.value)
      }))
      .sort((a: any, b: any) => a.time - b.time)
    )

    // 과매수/과매도 기준선
    rsiSeries.createPriceLine({ price: 70, color: '#ef4444', lineStyle: 2, axisLabelVisible: false })
    rsiSeries.createPriceLine({ price: 30, color: '#22c55e', lineStyle: 2, axisLabelVisible: false })
    
    refs.indicatorSeries.push(rsiSeries)
  } 
  
  else if (type === 'macd' && indicators.macd) {
    const macdHist = chart.addHistogramSeries({ priceScaleId: 'indicator', base: 0 })
    // 수정: lineWidth를 1.5에서 2로 변경
    const macdLine = chart.addLineSeries({ priceScaleId: 'indicator', color: '#3b82f6', lineWidth: 2 })
    const signalLine = chart.addLineSeries({ priceScaleId: 'indicator', color: '#f59e0b', lineWidth: 2 })

    const validData = indicators.macd.filter((d: any) => d.value != null && !isNaN(Number(d.value)))
    
    macdHist.setData(validData.map((d: any) => ({
      time: new Date(d.date).getTime() / 1000 as Time, 
      value: Number(d.histogram),
      color: Number(d.histogram) >= 0 ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)'
    })).sort((a: any, b: any) => a.time - b.time))

    macdLine.setData(validData.map((d: any) => ({
      time: new Date(d.date).getTime() / 1000 as Time, 
      value: Number(d.value)
    })).sort((a: any, b: any) => a.time - b.time))

    signalLine.setData(validData.map((d: any) => ({
      time: new Date(d.date).getTime() / 1000 as Time, 
      value: Number(d.signal)
    })).sort((a: any, b: any) => a.time - b.time))

    refs.indicatorSeries.push(macdHist, macdLine, signalLine)
  } 
  
  else if (type === 'vpci' && indicators.vpci) {
    // 수정: lineWidth를 1.5에서 2로 변경
    const vpciSeries = chart.addLineSeries({ priceScaleId: 'indicator', color: COLORS.text, lineWidth: 2 })
    const validData = indicators.vpci.filter((d: any) => d.value != null && !isNaN(Number(d.value)))
    
    vpciSeries.setData(validData.map((d: any) => ({
      time: new Date(d.date).getTime() / 1000 as Time, 
      value: Number(d.value)
    })).sort((a: any, b: any) => a.time - b.time))

    // 다이버전스 마커
    const markers = validData
      .filter((d: any) => d.signal && d.signal.includes('DIVERGE'))
      .map((d: any) => ({
        time: new Date(d.date).getTime() / 1000 as Time,
        position: d.signal === 'DIVERGE_BEAR' ? 'aboveBar' : 'belowBar',
        color: d.signal === 'DIVERGE_BEAR' ? '#ef4444' : '#22c55e',
        shape: 'circle',
        size: 1
      }))
    
    if (markers.length > 0) {
      vpciSeries.setMarkers(markers)
    }
    
    refs.indicatorSeries.push(vpciSeries)
  }
}

// ----------------------
// 헬퍼 함수들
// ----------------------
function updateSMA(chart: IChartApi, refs: any, period: string, data: IndicatorData[] | undefined) {
  const key = `sma${period}` as keyof typeof refs
  if (!data || data.length === 0) {
    if (refs[key]) {
      chart.removeSeries(refs[key])
      refs[key] = undefined
    }
    return
  }

  const smaData: LineData[] = data
    .filter(d => d.value != null && !isNaN(Number(d.value))) 
    .map((d) => ({
      time: new Date(d.date).getTime() / 1000 as Time,
      value: Number(d.value), 
    }))
    .sort((a, b) => (a.time as number) - (b.time as number))

  const colors: Record<string, string> = {
    '5': '#f59e0b', '10': '#3b82f6', '20': '#8b5cf6', '60': '#ec4899', '120': '#6b7280',
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
      chart.removeSeries(refs.bollingerMiddle)
      chart.removeSeries(refs.bollingerLower)
      refs.bollingerUpper = undefined
      refs.bollingerMiddle = undefined
      refs.bollingerLower = undefined
    }
    return
  }

  const mapBollinger = (key: keyof BollingerData) => 
    data
      .filter(d => d[key] != null && !isNaN(Number(d[key])))
      .map(d => ({
        time: new Date(d.date).getTime() / 1000 as Time,
        value: Number(d[key]),
      }))
      .sort((a, b) => (a.time as number) - (b.time as number))

  if (!refs.bollingerUpper) {
    refs.bollingerUpper = chart.addLineSeries({ color: 'rgba(239, 68, 68, 0.3)', lineWidth: 1, priceLineVisible: false })
    refs.bollingerMiddle = chart.addLineSeries({ color: 'rgba(156, 163, 175, 0.5)', lineWidth: 1, priceLineVisible: false })
    refs.bollingerLower = chart.addLineSeries({ color: 'rgba(239, 68, 68, 0.3)', lineWidth: 1, priceLineVisible: false })
  }

  refs.bollingerUpper.setData(mapBollinger('upper'))
  refs.bollingerMiddle.setData(mapBollinger('middle'))
  refs.bollingerLower.setData(mapBollinger('lower'))
}

function updateDarvasBoxes(chart: IChartApi, refs: any, boxes: DarvasBox[]) {
  if (refs.darvasBox) {
    chart.removeSeries(refs.darvasBox.topLine)
    chart.removeSeries(refs.darvasBox.bottomLine)
    refs.darvasBox = undefined
  }

  if (!boxes || boxes.length === 0) return

  const activeBox = boxes.find((b) => b.status === 'ACTIVE')
  if (!activeBox || activeBox.top == null || activeBox.bottom == null) return

  const topLine = chart.addLineSeries({ color: COLORS.darvasBorder, lineWidth: 2, priceLineVisible: false })
  const bottomLine = chart.addLineSeries({ color: COLORS.darvasBorder, lineWidth: 2, priceLineVisible: false })

  let startDate = new Date(activeBox.start_date).getTime() / 1000
  let endDate = activeBox.end_date ? new Date(activeBox.end_date).getTime() / 1000 : Date.now() / 1000

  if (startDate > endDate) {
    [startDate, endDate] = [endDate, startDate];
  }

  topLine.setData([
    { time: startDate as Time, value: Number(activeBox.top) },
    { time: endDate as Time, value: Number(activeBox.top) },
  ])

  bottomLine.setData([
    { time: startDate as Time, value: Number(activeBox.bottom) },
    { time: endDate as Time, value: Number(activeBox.bottom) },
  ])

  refs.darvasBox = { topLine, bottomLine }
}

function updateFibonacci(chart: IChartApi, refs: any, levels: Record<string, number>) {
  if (refs.fibonacciLines) {
    refs.fibonacciLines.forEach((line: any) => chart.removeSeries(line))
    refs.fibonacciLines = []
  }

  if (!levels || Object.keys(levels).length === 0) return

  const fibLines = Object.entries(levels)
    .filter(([_level, price]) => price != null && !isNaN(Number(price))) 
    .map(([_level, price]) => {
      const line = chart.addLineSeries({
        color: COLORS.fibonacciLine,
        lineWidth: 1,
        priceLineVisible: false,
        lineStyle: 2, 
      })

      const now = Date.now() / 1000
      line.setData([
        { time: (now - 86400 * 365) as Time, value: Number(price) },
        { time: now as Time, value: Number(price) },
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