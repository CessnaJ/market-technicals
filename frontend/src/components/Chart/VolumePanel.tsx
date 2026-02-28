import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ColorType, HistogramData, Time } from 'lightweight-charts'
import { OHLCV, COLORS } from '../../types'

interface VolumePanelProps {
  data: OHLCV[]
}

export default function VolumePanel({ data }: VolumePanelProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const volumeSeriesRef = useRef<any>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 100,
      layout: {
        background: { type: ColorType.Solid, color: COLORS.background },
        textColor: COLORS.textMuted,
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      timeScale: {
        visible: false,
      },
      rightPriceScale: {
        visible: false,
      },
    })

    chartRef.current = chart

    // 거래량 히스토그램 시리즈
    const volumeSeries = chart.addHistogramSeries({
      color: COLORS.volumeNormal,
    })
    volumeSeriesRef.current = volumeSeries

    return () => {
      chart.remove()
    }
  }, [])

  // 데이터 업데이트
  useEffect(() => {
    if (!chartRef.current || !volumeSeriesRef.current || !data.length) return

    // 평균 거래량 계산
    const avgVolume = data.reduce((sum, d) => sum + d.volume, 0) / data.length

    const volumeData: HistogramData[] = data.map((d) => ({
      time: new Date(d.date).getTime() / 1000 as Time,
      value: d.volume,
      color: d.volume >= avgVolume * 2 ? COLORS.volumeHigh : COLORS.volumeNormal,
    }))

    volumeSeriesRef.current.setData(volumeData)
  }, [data])

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
    <div className="w-full">
      <div className="text-xs text-gray-400 mb-1">Volume</div>
      <div ref={chartContainerRef} className="w-full h-[100px]" />
    </div>
  )
}
