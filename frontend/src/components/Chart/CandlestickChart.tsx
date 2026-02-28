import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ColorType, LineData, CandlestickData, Time, LogicalRange } from 'lightweight-charts'
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
  // 추가된 Props: 데이터 추가 로드 콜백과 상태
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
  onLoadMore,     
  isRefetching,   
}: CandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  
  // 에러 수정: NodeJS.Timeout 대신 범용 ReturnType 사용
  const fetchThrottleRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  
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

  // 1. 차트 초기화
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
  },[])

  // 2. ★ 스크롤 감지 및 Lazy Loading 로직 (추가됨) ★
  useEffect(() => {
    if (!chartRef.current || !onLoadMore) return;

    const handleVisibleLogicalRangeChange = (logicalRange: LogicalRange | null) => {
      if (!logicalRange) return;

      // 과거 데이터(왼쪽)로 스크롤 시 logicalRange.from 이 0에 가까워집니다.
      // 10 캔들 정도 남았을 때 데이터를 더 가져오도록 트리거합니다.
      if (logicalRange.from < 10 && !isRefetching) {
        if (fetchThrottleRef.current) return; // 이미 디바운스 대기중이면 무시

        fetchThrottleRef.current = setTimeout(() => {
          onLoadMore(); // 백엔드에 1년치 풀데이터를 다시 요청(refetch)
          fetchThrottleRef.current = null;
        }, 1000); // 연속 호출 방지를 위해 1초 제한
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

    // 캔들 데이터 - 시간순으로 정렬 (결측치 필터링 및 숫자 변환 포함)
    const candleData: CandlestickData[] = data
      .filter(d => d.date && d.open != null && d.high != null && d.low != null && d.close != null)
      .map((d) => ({
        time: new Date(d.date).getTime() / 1000 as Time,
        open: Number(d.open),
        high: Number(d.high),
        low: Number(d.low),
        close: Number(d.close),
      }))
      .sort((a, b) => (a.time as number) - (b.time as number))
      
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
    if (showFibonacci && fibonacci && fibonacci.levels) {
      updateFibonacci(chartRef.current, seriesRefs.current, fibonacci.levels)
    }

    // Weinstein 배경색 업데이트 (원시 data가 아닌 정제된 candleData 사용)
    if (showWeinstein && weinstein && seriesRefs.current.weinsteinBackground) {
      const maValue = Number(weinstein.ma_30w) || 0
      const weinsteinData = candleData.map((d) => ({
        time: d.time,
        value: maValue,
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
  },[])

  return (
    <div className="relative w-full">
      {/* 데이터 새로고침(백그라운드 조회) 중일 때 좌측 상단에 작은 안내 뱃지 렌더링 */}
      {isRefetching && (
        <div className="absolute top-2 left-2 z-10 bg-gray-800 text-xs text-white px-2 py-1 rounded shadow-md opacity-70">
          과거 데이터 로딩 중...
        </div>
      )}
      <div ref={chartContainerRef} className="w-full h-[500px]" />
    </div>
  )
}

// ----------------------
// 헬퍼 함수들 (기존과 동일)
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
    // 수정: null 뿐만 아니라 숫자로 변환 불가능한 값(NaN)도 필터링
    .filter(d => d.value != null && !isNaN(Number(d.value))) 
    .map((d) => ({
      time: new Date(d.date).getTime() / 1000 as Time,
      value: Number(d.value), // 수정: 확실한 Number 타입 캐스팅
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

  // 상단, 중단, 하단 모두 Number 캐스팅 및 isNaN 필터링 적용
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
  // 수정: top, bottom 값 존재 여부 확실히 체크
  if (!activeBox || activeBox.top == null || activeBox.bottom == null) return

  const topLine = chart.addLineSeries({ color: COLORS.darvasBorder, lineWidth: 2, priceLineVisible: false })
  const bottomLine = chart.addLineSeries({ color: COLORS.darvasBorder, lineWidth: 2, priceLineVisible: false })

  let startDate = new Date(activeBox.start_date).getTime() / 1000
  let endDate = activeBox.end_date ? new Date(activeBox.end_date).getTime() / 1000 : Date.now() / 1000

  // 수정: 반드시 오름차순 시간 배열이 되도록 방어 코드 추가
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
      // 수정: 과거 시간이 인덱스 0, 현재 시간이 인덱스 1에 오도록 배열 순서 교체 (오름차순)
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