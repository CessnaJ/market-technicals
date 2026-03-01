import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ColorType, HistogramData, Time } from 'lightweight-charts'
import { OHLCV, COLORS } from '../../types'

interface VolumeChartProps {
  data: OHLCV[]
}

export default function VolumeChart({ data }: VolumeChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current) return
    
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 120,
      layout: {
        background: { type: ColorType.Solid, color: COLORS.background },
        textColor: COLORS.text,
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      timeScale: {
        borderColor: '#1f2937',
        timeVisible: true,
      },
    })

    seriesRef.current = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
    })

    chartRef.current = chart

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !data) return

    const vData: HistogramData[] = data
      .filter(d => d.date && d.volume != null)
      .map(d => ({
        time: (new Date(d.date).getTime() / 1000) as Time,
        value: Number(d.volume),
        color: Number(d.close) >= Number(d.open) ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
      }))
      .sort((a, b) => (a.time as number) - (b.time as number))
    
    seriesRef.current.setData(vData)
  }, [data])

  return (
    <div className="mt-4 pt-4 border-t border-gray-700">
      <div className="text-[10px] font-bold text-gray-500 uppercase ml-2 mb-1">Volume Analysis</div>
      <div ref={containerRef} className="w-full" />
    </div>
  )
}