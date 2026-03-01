import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ColorType, Time, ISeriesApi } from 'lightweight-charts'
import { COLORS, IndicatorData } from '../../types'

interface IndicatorPanelProps {
  rsi?: IndicatorData[];
  macd?: any[]; // MACDData
  vpci?: any[]; // VPCIData
  activeIndicator: 'rsi' | 'macd' | 'vpci';
}

export default function IndicatorPanel({ rsi, macd, vpci, activeIndicator }: IndicatorPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRefs = useRef<ISeriesApi<any>[]>([])

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 180,
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
    if (!chartRef.current) return

    // 기존 시리즈 제거
    seriesRefs.current.forEach(s => chartRef.current?.removeSeries(s))
    seriesRefs.current = []

    if (activeIndicator === 'rsi' && rsi) {
      const s = chartRef.current.addLineSeries({ color: '#8b5cf6', lineWidth: 2, title: 'RSI' })
      const data = rsi
        .map(d => ({ time: (new Date(d.date).getTime() / 1000) as Time, value: Number(d.value) }))
        .filter(d => !isNaN(d.value))
        .sort((a, b) => (a.time as number) - (b.time as number))
      
      s.setData(data)
      s.createPriceLine({ price: 70, color: '#ef4444', lineStyle: 2, axisLabelVisible: true, title: '70' })
      s.createPriceLine({ price: 30, color: '#22c55e', lineStyle: 2, axisLabelVisible: true, title: '30' })
      seriesRefs.current.push(s)
    } 
    
    else if (activeIndicator === 'macd' && macd) {
      const hist = chartRef.current.addHistogramSeries({ title: 'Histogram' })
      const line = chartRef.current.addLineSeries({ color: '#3b82f6', lineWidth: 2, title: 'MACD' })
      const signal = chartRef.current.addLineSeries({ color: '#f59e0b', lineWidth: 2, title: 'Signal' })

      const data = macd
        .map(d => ({
          time: (new Date(d.date).getTime() / 1000) as Time,
          macd: Number(d.macd || d.value),
          sig: Number(d.signal),
          h: Number(d.histogram)
        }))
        .filter(d => !isNaN(d.macd))
        .sort((a, b) => (a.time as number) - (b.time as number))

      hist.setData(data.map(d => ({ time: d.time, value: d.h, color: d.h >= 0 ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)' })))
      line.setData(data.map(d => ({ time: d.time, value: d.macd })))
      signal.setData(data.map(d => ({ time: d.time, value: d.sig })))
      seriesRefs.current.push(hist, line, signal)
    }

    else if (activeIndicator === 'vpci' && vpci) {
      const s = chartRef.current.addLineSeries({ color: '#f8fafc', lineWidth: 2, title: 'VPCI' })
      const data = vpci
        .map(d => ({ time: (new Date(d.date).getTime() / 1000) as Time, value: Number(d.value) }))
        .filter(d => !isNaN(d.value))
        .sort((a, b) => (a.time as number) - (b.time as number))
      
      s.setData(data)
      seriesRefs.current.push(s)
    }

  }, [activeIndicator, rsi, macd, vpci])

  return (
    <div className="mt-4 pt-4 border-t border-gray-700">
      <div className="text-[10px] font-bold text-gray-500 uppercase ml-2 mb-2">{activeIndicator} Indicator</div>
      <div ref={containerRef} className="w-full" />
    </div>
  )
}