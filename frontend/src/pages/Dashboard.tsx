import { useEffect, useState } from 'react'

import apiClient from '../api/client'
import CandlestickChart from '../components/Chart/CandlestickChart'
import FinancialMetrics from '../components/FinancialMetrics'
import Watchlist from '../components/Watchlist'
import { useChartData } from '../hooks/useChartData'
import { useFinancialMetrics } from '../hooks/useFinancialMetrics'
import { useIndicators } from '../hooks/useIndicators'
import { useRelativeStrength } from '../hooks/useRelativeStrength'
import { COLORS } from '../types'

type Timeframe = 'daily' | 'weekly' | 'monthly'
type ScaleMode = 'linear' | 'log'
type IndicatorTab = 'rsi' | 'macd' | 'vpci' | 'rs'
type FibonacciMode = 'auto' | 'manual'
type FibonacciTrend = 'UP' | 'DOWN'

type DashboardSettings = {
  timeframe: Timeframe
  scale: ScaleMode
  benchmarkTicker: string
  activeIndicator: IndicatorTab
  smaByTimeframe: Record<Timeframe, number[]>
  fibonacciMode: FibonacciMode
  fibonacciTrend: FibonacciTrend
  manualSwingLow: string
  manualSwingHigh: string
}

const STORAGE_KEY = 'quant-viz:dashboard-settings:v3'
const DEFAULT_SMA_BY_TIMEFRAME: Record<Timeframe, number[]> = {
  daily: [5, 10, 20, 60, 120],
  weekly: [5, 10, 20, 30],
  monthly: [3, 6, 12],
}

const DEFAULT_SETTINGS: DashboardSettings = {
  timeframe: 'daily',
  scale: 'linear',
  benchmarkTicker: '069500',
  activeIndicator: 'rsi',
  smaByTimeframe: DEFAULT_SMA_BY_TIMEFRAME,
  fibonacciMode: 'auto',
  fibonacciTrend: 'UP',
  manualSwingLow: '',
  manualSwingHigh: '',
}

export default function Dashboard() {
  const [storedSettings] = useState(loadDashboardSettings)

  const [ticker, setTicker] = useState('010950')
  const [timeframe, setTimeframe] = useState<Timeframe>(storedSettings.timeframe)
  const [scale, setScale] = useState<ScaleMode>(storedSettings.scale)
  const [benchmarkTicker, setBenchmarkTicker] = useState(storedSettings.benchmarkTicker)
  const [activeIndicator, setActiveIndicator] = useState<IndicatorTab>(storedSettings.activeIndicator)
  const [smaByTimeframe, setSmaByTimeframe] = useState<Record<Timeframe, number[]>>(storedSettings.smaByTimeframe)
  const [smaInput, setSmaInput] = useState(storedSettings.smaByTimeframe[storedSettings.timeframe].join(','))
  const [fibonacciMode, setFibonacciMode] = useState<FibonacciMode>(storedSettings.fibonacciMode)
  const [fibonacciTrend, setFibonacciTrend] = useState<FibonacciTrend>(storedSettings.fibonacciTrend)
  const [manualSwingLow, setManualSwingLow] = useState(storedSettings.manualSwingLow)
  const [manualSwingHigh, setManualSwingHigh] = useState(storedSettings.manualSwingHigh)
  const [isSyncing, setIsSyncing] = useState(false)

  const [showSMA, setShowSMA] = useState(true)
  const [showBollinger, setShowBollinger] = useState(true)
  const [showDarvas, setShowDarvas] = useState(true)
  const [showFibonacci, setShowFibonacci] = useState(true)
  const [showWeinstein, setShowWeinstein] = useState(true)

  const smaPeriods = smaByTimeframe[timeframe]
  const parsedManualSwingLow = manualSwingLow.trim() === '' ? null : Number(manualSwingLow)
  const parsedManualSwingHigh = manualSwingHigh.trim() === '' ? null : Number(manualSwingHigh)
  const manualSwingLowValue = parsedManualSwingLow != null && Number.isFinite(parsedManualSwingLow) ? parsedManualSwingLow : null
  const manualSwingHighValue = parsedManualSwingHigh != null && Number.isFinite(parsedManualSwingHigh) ? parsedManualSwingHigh : null

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
    smaPeriods,
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
    benchmarkTicker,
    fibonacciMode,
    fibonacciTrend,
    manualSwingLow: manualSwingLowValue,
    manualSwingHigh: manualSwingHighValue,
  })

  const {
    financial,
    refetch: refetchFinancial,
  } = useFinancialMetrics({
    ticker,
    enabled: indicatorsEnabled,
  })

  const {
    relativeStrength,
    refetch: refetchRelativeStrength,
  } = useRelativeStrength({
    ticker,
    benchmarkTicker,
    timeframe,
    enabled: indicatorsEnabled,
  })

  useEffect(() => {
    setSmaInput((smaByTimeframe[timeframe] ?? DEFAULT_SMA_BY_TIMEFRAME[timeframe]).join(','))
  }, [smaByTimeframe, timeframe])

  useEffect(() => {
    saveDashboardSettings({
      timeframe,
      scale,
      benchmarkTicker,
      activeIndicator,
      smaByTimeframe,
      fibonacciMode,
      fibonacciTrend,
      manualSwingLow,
      manualSwingHigh,
    })
  }, [
    activeIndicator,
    benchmarkTicker,
    fibonacciMode,
    fibonacciTrend,
    manualSwingHigh,
    manualSwingLow,
    scale,
    smaByTimeframe,
    timeframe,
  ])

  const handleSmaCommit = () => {
    const parsed = parseSmaInput(smaInput, timeframe)
    setSmaByTimeframe((current) => ({
      ...current,
      [timeframe]: parsed,
    }))
    setSmaInput(parsed.join(','))
  }

  const handleForceRefreshData = async () => {
    if (!ticker || isSyncing) {
      return
    }

    setIsSyncing(true)
    try {
      await apiClient.post(`/fetch/${ticker}`, { force_refresh: true })
      await refetchChart()
      await Promise.all([refetchIndicators(), refetchFinancial(), refetchRelativeStrength()])
    } catch (err: any) {
      console.error('Failed to fetch data:', err)
    } finally {
      setIsSyncing(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0b0e14] text-gray-100 font-sans">
      <header className="sticky top-0 z-30 border-b border-gray-800 bg-[#131722] p-4">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:gap-6">
            <div>
              <h1 className="text-xl font-black tracking-tighter text-blue-500">QUANT-VIZ Pro</h1>
              <div className="text-[10px] font-black uppercase tracking-[0.28em] text-gray-500">
                Stage / RS / Monthly / Manual Fib
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={ticker}
                onChange={(event) => setTicker(event.target.value.toUpperCase())}
                className="w-44 rounded border border-gray-700 bg-[#1e222d] px-4 py-2 text-sm font-bold uppercase outline-none transition-all focus:border-blue-500"
              />
              <button
                onClick={handleForceRefreshData}
                disabled={isSyncing || chartLoading}
                className="rounded bg-blue-600 px-4 py-2 text-sm font-bold transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSyncing ? 'SYNCING...' : 'FETCH DATA'}
              </button>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <select
              value={timeframe}
              onChange={(event) => setTimeframe(event.target.value as Timeframe)}
              className="rounded border border-gray-700 bg-[#1e222d] p-2 text-xs font-black uppercase outline-none"
            >
              <option value="daily">DAILY</option>
              <option value="weekly">WEEKLY</option>
              <option value="monthly">MONTHLY</option>
            </select>

            <select
              value={scale}
              onChange={(event) => setScale(event.target.value as ScaleMode)}
              className="rounded border border-gray-700 bg-[#1e222d] p-2 text-xs font-black uppercase outline-none"
            >
              <option value="linear">LINEAR SCALE</option>
              <option value="log">LOG SCALE</option>
            </select>

            <input
              type="text"
              value={benchmarkTicker}
              onChange={(event) => setBenchmarkTicker(event.target.value.toUpperCase())}
              placeholder="BENCHMARK"
              className="rounded border border-gray-700 bg-[#1e222d] px-3 py-2 text-xs font-black uppercase outline-none focus:border-blue-500"
            />

            <input
              type="text"
              value={smaInput}
              onChange={(event) => setSmaInput(event.target.value)}
              onBlur={handleSmaCommit}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  handleSmaCommit()
                }
              }}
              placeholder="SMA 5,10,20"
              className="rounded border border-gray-700 bg-[#1e222d] px-3 py-2 text-xs font-black uppercase outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] p-4">
        {chartError && (
          <div className="mb-4 flex items-center gap-3 rounded-lg border border-red-500/50 bg-red-900/30 p-4 text-sm text-red-400">
            <span className="h-2 w-2 animate-ping rounded-full bg-red-500" />
            <strong>Engine Error:</strong> {chartError}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
          <div className="space-y-6 lg:col-span-3">
            {chartData && (
              <div className="rounded-2xl border border-gray-800 bg-[#131722] p-6 shadow-2xl transition-all">
                <div className="mb-8 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-baseline gap-3">
                      <h2 className="text-4xl font-black tracking-tight">{chartData.name}</h2>
                      <span className="font-mono text-2xl uppercase tracking-widest text-gray-500">{chartData.ticker}</span>
                      <span className="rounded border border-blue-500/20 bg-blue-600/15 px-2 py-1 text-[10px] font-black tracking-[0.25em] text-blue-300">
                        {timeframe.toUpperCase()} WINDOW
                      </span>
                    </div>

                    {weinstein && (
                      <div className="flex flex-wrap items-center gap-2">
                        <div
                          className="rounded-full px-3 py-0.5 text-[10px] font-black text-white"
                          style={{ backgroundColor: getWeinsteinStageColor(weinstein.current_stage) }}
                        >
                          STAGE {weinstein.current_stage}
                        </div>
                        <span className="text-[11px] font-black uppercase tracking-[0.18em] text-gray-400">
                          {weinstein.stage_label}
                        </span>
                        <span className="text-[11px] text-gray-500">
                          {weinstein.description?.summary ?? 'Weinstein market cycle analysis'}
                        </span>
                      </div>
                    )}

                    {relativeStrength && (
                      <div className="flex flex-wrap items-center gap-3 text-xs">
                        <span className="rounded-full border border-gray-800 bg-[#0b0e14] px-3 py-1 font-black text-gray-300">
                          RS vs {relativeStrength.benchmark_name} ({relativeStrength.benchmark_ticker})
                        </span>
                        <span className={`font-black ${relativeStrength.current_relative_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          Spread {relativeStrength.current_relative_return >= 0 ? '+' : ''}{relativeStrength.current_relative_return.toFixed(2)}
                        </span>
                        <span className={`font-black ${(relativeStrength.current_mansfield_rs ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          Mansfield {relativeStrength.current_mansfield_rs != null ? `${relativeStrength.current_mansfield_rs >= 0 ? '+' : ''}${relativeStrength.current_mansfield_rs.toFixed(2)}` : '-'}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2 rounded-xl border border-gray-800 bg-[#0b0e14] p-1.5 shadow-inner">
                    {(['rsi', 'macd', 'vpci', 'rs'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveIndicator(tab)}
                        className={`rounded-lg px-5 py-2 text-[11px] font-black tracking-widest transition-all ${
                          activeIndicator === tab ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/50' : 'text-gray-500 hover:text-gray-300'
                        }`}
                      >
                        {tab.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mb-5 flex flex-wrap gap-8 px-2">
                  <ToggleChip checked={showSMA} onChange={setShowSMA} label="SMA" />
                  <ToggleChip checked={showBollinger} onChange={setShowBollinger} label="BOLL" />
                  <ToggleChip checked={showDarvas} onChange={setShowDarvas} label="DARVAS" />
                  <ToggleChip checked={showFibonacci} onChange={setShowFibonacci} label="FIBO" />
                  <ToggleChip checked={showWeinstein} onChange={setShowWeinstein} label="STAGE" />
                </div>

                <div className="mb-6 grid gap-3 rounded-2xl border border-gray-800 bg-[#0b0e14] p-4 lg:grid-cols-[1fr_0.8fr]">
                  <div>
                    <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">SMA Settings</div>
                    <div className="mt-2 text-sm text-gray-300">
                      {timeframe.toUpperCase()} timeframe uses <span className="font-black text-white">{smaPeriods.join(', ')}</span>
                    </div>
                    <div className="mt-1 text-xs text-gray-500">Saved in localStorage per timeframe</div>
                  </div>
                  <div>
                    <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">Fibonacci Mode</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(['auto', 'manual'] as const).map((mode) => (
                        <button
                          key={mode}
                          onClick={() => setFibonacciMode(mode)}
                          className={`rounded-lg px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] ${
                            fibonacciMode === mode ? 'bg-amber-500 text-black' : 'bg-[#131722] text-gray-400'
                          }`}
                        >
                          {mode}
                        </button>
                      ))}
                      <select
                        value={fibonacciTrend}
                        onChange={(event) => setFibonacciTrend(event.target.value as FibonacciTrend)}
                        className="rounded-lg border border-gray-800 bg-[#131722] px-3 py-2 text-[11px] font-black uppercase outline-none"
                      >
                        <option value="UP">UPTREND</option>
                        <option value="DOWN">DOWNTREND</option>
                      </select>
                    </div>
                    {fibonacciMode === 'manual' && (
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        <input
                          type="number"
                          value={manualSwingLow}
                          onChange={(event) => setManualSwingLow(event.target.value)}
                          placeholder="SWING LOW"
                          className="rounded-lg border border-gray-800 bg-[#131722] px-3 py-2 text-xs font-black outline-none focus:border-amber-500"
                        />
                        <input
                          type="number"
                          value={manualSwingHigh}
                          onChange={(event) => setManualSwingHigh(event.target.value)}
                          placeholder="SWING HIGH"
                          className="rounded-lg border border-gray-800 bg-[#131722] px-3 py-2 text-xs font-black outline-none focus:border-amber-500"
                        />
                      </div>
                    )}
                  </div>
                </div>

                <CandlestickChart
                  data={chartData.ohlcv}
                  indicators={chartData.indicators}
                  darvasBoxes={darvas}
                  fibonacci={fibonacci}
                  weinstein={weinstein ?? undefined}
                  relativeStrength={relativeStrength}
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
            <FinancialMetrics weinstein={weinstein} financial={financial} signals={signals} />
          </div>
        </div>
      </main>

      {chartLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="flex flex-col items-center rounded-3xl border border-gray-800 bg-[#1e222d] p-10 shadow-2xl">
            <div className="relative">
              <div className="h-16 w-16 rounded-full border-4 border-blue-500/20" />
              <div className="absolute left-0 top-0 h-16 w-16 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
            </div>
            <p className="mt-6 text-sm font-black tracking-[0.2em] text-blue-500">INITIALIZING ENGINE</p>
          </div>
        </div>
      )}
    </div>
  )
}

function ToggleChip({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  label: string
}) {
  return (
    <label className="group flex cursor-pointer items-center gap-3">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="hidden" />
      <div className={`flex h-5 w-5 items-center justify-center rounded-md border-2 transition-all ${checked ? 'border-blue-500 bg-blue-500' : 'border-gray-700 group-hover:border-gray-500'}`}>
        {checked && <span className="text-[10px] text-white">✓</span>}
      </div>
      <span className={`text-[11px] font-black tracking-widest ${checked ? 'text-gray-100' : 'text-gray-600'}`}>{label}</span>
    </label>
  )
}

function loadDashboardSettings(): DashboardSettings {
  if (typeof window === 'undefined') {
    return DEFAULT_SETTINGS
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return DEFAULT_SETTINGS
    }

    const parsed = JSON.parse(raw) as Partial<DashboardSettings>
    return {
      ...DEFAULT_SETTINGS,
      ...parsed,
      smaByTimeframe: {
        ...DEFAULT_SMA_BY_TIMEFRAME,
        ...(parsed.smaByTimeframe ?? {}),
      },
    }
  } catch {
    return DEFAULT_SETTINGS
  }
}

function saveDashboardSettings(settings: DashboardSettings) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
}

function parseSmaInput(input: string, timeframe: Timeframe) {
  const parsed = input
    .split(',')
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value) && value >= 2 && value <= 240)

  const unique = Array.from(new Set(parsed)).sort((left, right) => left - right)
  return unique.length > 0 ? unique.slice(0, 6) : DEFAULT_SMA_BY_TIMEFRAME[timeframe]
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
