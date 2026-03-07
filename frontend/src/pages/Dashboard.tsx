import { useState } from 'react'

import apiClient from '../api/client'
import CandlestickChart from '../components/Chart/CandlestickChart'
import FinancialMetrics from '../components/FinancialMetrics'
import Watchlist from '../components/Watchlist'
import { useChartData } from '../hooks/useChartData'
import { useFinancialMetrics } from '../hooks/useFinancialMetrics'
import { useIndicators } from '../hooks/useIndicators'
import { COLORS } from '../types'

export default function Dashboard() {
  const [ticker, setTicker] = useState('010950')
  const [timeframe, setTimeframe] = useState<'daily' | 'weekly'>('daily')
  const [scale, setScale] = useState<'linear' | 'log'>('linear')
  const [isSyncing, setIsSyncing] = useState(false)

  const [showSMA, setShowSMA] = useState(true)
  const [showBollinger, setShowBollinger] = useState(true)
  const [showDarvas, setShowDarvas] = useState(true)
  const [showFibonacci, setShowFibonacci] = useState(true)
  const [showWeinstein, setShowWeinstein] = useState(true)
  const [activeIndicator, setActiveIndicator] = useState<'rsi' | 'macd' | 'vpci'>('rsi')

  const {
    data: chartData,
    loading: chartLoading,
    error: chartError,
    refetch: refetchChart,
  } = useChartData({
    ticker,
    timeframe,
    scale,
    enabled: ticker.length > 0,
  })

  const indicatorsEnabled = ticker.length > 0 && !chartLoading && chartData?.ticker === ticker

  const {
    weinstein,
    darvas,
    fibonacci,
    signals,
    refetch: refetchIndicators,
  } = useIndicators({
    ticker,
    enabled: indicatorsEnabled,
  })

  const {
    financial,
    refetch: refetchFinancial,
  } = useFinancialMetrics({
    ticker,
    enabled: indicatorsEnabled,
  })

  const handleForceRefreshData = async () => {
    if (!ticker || isSyncing) {
      return
    }

    setIsSyncing(true)
    try {
      await apiClient.post(`/fetch/${ticker}`, { force_refresh: true })
      await refetchChart()
      await refetchIndicators()
      await refetchFinancial()
    } catch (err: any) {
      console.error('Failed to fetch data:', err)
    } finally {
      setIsSyncing(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0b0e14] text-gray-100 font-sans">
      <header className="bg-[#131722] border-b border-gray-800 p-4 sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-black tracking-tighter text-blue-500">QUANT-VIZ Pro</h1>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={ticker}
                onChange={(event) => setTicker(event.target.value)}
                className="px-4 py-2 bg-[#1e222d] rounded border border-gray-700 w-48 focus:border-blue-500 outline-none transition-all text-sm font-bold uppercase"
              />
              <button
                onClick={handleForceRefreshData}
                disabled={isSyncing || chartLoading}
                className="px-4 py-2 bg-blue-600 rounded font-bold text-sm hover:bg-blue-500 transition-colors shadow-lg shadow-blue-900/20 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isSyncing ? 'SYNCING...' : 'FETCH DATA'}
              </button>
            </div>
          </div>
          <div className="flex gap-4">
            <select
              value={timeframe}
              onChange={(event) => setTimeframe(event.target.value as 'daily' | 'weekly')}
              className="bg-[#1e222d] p-2 rounded border border-gray-700 text-xs font-bold outline-none"
            >
              <option value="daily">DAILY</option>
              <option value="weekly">WEEKLY</option>
            </select>
            <select
              value={scale}
              onChange={(event) => setScale(event.target.value as 'linear' | 'log')}
              className="bg-[#1e222d] p-2 rounded border border-gray-700 text-xs font-bold outline-none"
            >
              <option value="linear">LINEAR SCALE</option>
              <option value="log">LOG SCALE</option>
            </select>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto p-4">
        {chartError && (
          <div className="mb-4 p-4 bg-red-900/30 border border-red-500/50 rounded-lg text-red-400 text-sm flex items-center gap-3">
            <span className="animate-ping w-2 h-2 bg-red-500 rounded-full"></span>
            <strong>Engine Error:</strong> {chartError}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 space-y-6">
            {chartData && (
              <div className="bg-[#131722] rounded-2xl p-6 border border-gray-800 shadow-2xl transition-all">
                <div className="flex justify-between items-start mb-8 gap-4">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-baseline gap-3 flex-wrap">
                      <h2 className="text-4xl font-black tracking-tight">{chartData.name}</h2>
                      <span className="text-gray-500 font-mono text-2xl uppercase tracking-widest">{chartData.ticker}</span>
                      <span className="text-[10px] font-black tracking-[0.25em] px-2 py-1 rounded bg-blue-600/15 text-blue-300 border border-blue-500/20">
                        1Y WINDOW
                      </span>
                    </div>
                    {weinstein && (
                      <div className="flex items-center gap-2 mt-2">
                        <div
                          className="px-3 py-0.5 rounded-full text-[10px] font-black text-white"
                          style={{ backgroundColor: getWeinsteinStageColor(weinstein.current_stage) }}
                        >
                          STAGE {weinstein.current_stage}
                        </div>
                        <span className="text-[10px] text-gray-500 font-bold uppercase tracking-tighter">Weinstein Market Cycle</span>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 bg-[#0b0e14] p-1.5 rounded-xl border border-gray-800 shadow-inner">
                    {(['rsi', 'macd', 'vpci'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveIndicator(tab)}
                        className={`px-5 py-2 rounded-lg text-[11px] font-black tracking-widest transition-all ${
                          activeIndicator === tab ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/50' : 'text-gray-500 hover:text-gray-300'
                        }`}
                      >
                        {tab.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap gap-8 mb-8 px-2">
                  <label className="flex items-center gap-3 cursor-pointer group">
                    <input type="checkbox" checked={showSMA} onChange={(event) => setShowSMA(event.target.checked)} className="hidden" />
                    <div className={`w-5 h-5 rounded-md border-2 transition-all flex items-center justify-center ${showSMA ? 'bg-blue-500 border-blue-500' : 'border-gray-700 group-hover:border-gray-500'}`}>
                      {showSMA && <span className="text-white text-[10px]">✓</span>}
                    </div>
                    <span className={`text-[11px] font-black tracking-widest ${showSMA ? 'text-gray-100' : 'text-gray-600'}`}>SMA</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer group">
                    <input type="checkbox" checked={showBollinger} onChange={(event) => setShowBollinger(event.target.checked)} className="hidden" />
                    <div className={`w-5 h-5 rounded-md border-2 transition-all flex items-center justify-center ${showBollinger ? 'bg-blue-500 border-blue-500' : 'border-gray-700 group-hover:border-gray-500'}`}>
                      {showBollinger && <span className="text-white text-[10px]">✓</span>}
                    </div>
                    <span className={`text-[11px] font-black tracking-widest ${showBollinger ? 'text-gray-100' : 'text-gray-600'}`}>BOLL</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer group">
                    <input type="checkbox" checked={showDarvas} onChange={(event) => setShowDarvas(event.target.checked)} className="hidden" />
                    <div className={`w-5 h-5 rounded-md border-2 transition-all flex items-center justify-center ${showDarvas ? 'bg-blue-500 border-blue-500' : 'border-gray-700 group-hover:border-gray-500'}`}>
                      {showDarvas && <span className="text-white text-[10px]">✓</span>}
                    </div>
                    <span className={`text-[11px] font-black tracking-widest ${showDarvas ? 'text-gray-100' : 'text-gray-600'}`}>DARVAS</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer group">
                    <input type="checkbox" checked={showFibonacci} onChange={(event) => setShowFibonacci(event.target.checked)} className="hidden" />
                    <div className={`w-5 h-5 rounded-md border-2 transition-all flex items-center justify-center ${showFibonacci ? 'bg-blue-500 border-blue-500' : 'border-gray-700 group-hover:border-gray-500'}`}>
                      {showFibonacci && <span className="text-white text-[10px]">✓</span>}
                    </div>
                    <span className={`text-[11px] font-black tracking-widest ${showFibonacci ? 'text-gray-100' : 'text-gray-600'}`}>FIBO</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer group">
                    <input type="checkbox" checked={showWeinstein} onChange={(event) => setShowWeinstein(event.target.checked)} className="hidden" />
                    <div className={`w-5 h-5 rounded-md border-2 transition-all flex items-center justify-center ${showWeinstein ? 'bg-blue-500 border-blue-500' : 'border-gray-700 group-hover:border-gray-500'}`}>
                      {showWeinstein && <span className="text-white text-[10px]">✓</span>}
                    </div>
                    <span className={`text-[11px] font-black tracking-widest ${showWeinstein ? 'text-gray-100' : 'text-gray-600'}`}>STAGE</span>
                  </label>
                </div>

                <CandlestickChart
                  data={chartData.ohlcv}
                  indicators={chartData.indicators}
                  darvasBoxes={darvas}
                  fibonacci={fibonacci ? { levels: fibonacci.levels } : undefined}
                  weinstein={weinstein ?? undefined}
                  scale={scale}
                  showSMA={showSMA}
                  showBollinger={showBollinger}
                  showDarvas={showDarvas}
                  showFibonacci={showFibonacci}
                  showWeinstein={showWeinstein}
                  activeIndicator={activeIndicator}
                />
              </div>
            )}
          </div>

          <div className="space-y-6">
            <Watchlist currentTicker={ticker} onSelectTicker={setTicker} />
            <FinancialMetrics
              weinstein={weinstein}
              financial={financial}
              signals={signals}
            />
          </div>
        </div>
      </main>

      {chartLoading && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-[#1e222d] p-10 rounded-3xl border border-gray-800 flex flex-col items-center shadow-3xl">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-blue-500/20 rounded-full"></div>
              <div className="absolute top-0 left-0 w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
            <p className="mt-6 font-black tracking-[0.2em] text-sm text-blue-500">INITIALIZING ENGINE</p>
          </div>
        </div>
      )}
    </div>
  )
}

function getWeinsteinStageColor(stage: number): string {
  const colors: Record<number, string> = {
    1: COLORS.stage1,
    2: COLORS.stage2,
    3: COLORS.stage3,
    4: COLORS.stage4,
  }
  return colors[stage] || '#374151'
}
