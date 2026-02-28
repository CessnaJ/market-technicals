import { useState } from 'react'
import { useChartData } from '../hooks/useChartData'
import { useIndicators } from '../hooks/useIndicators'
import CandlestickChart from '../components/Chart/CandlestickChart'
import VolumePanel from '../components/Chart/VolumePanel'
import IndicatorPanel from '../components/Chart/IndicatorPanel'
import FinancialMetrics from '../components/FinancialMetrics'
import Watchlist from '../components/Watchlist'
import apiClient from '../api/client'
import { COLORS } from '../types'

export default function Dashboard() {
  const[ticker, setTicker] = useState('010950')
  const [timeframe, setTimeframe] = useState<'daily' | 'weekly'>('daily')
  const [scale, setScale] = useState<'linear' | 'log'>('linear')
  const [showSMA, setShowSMA] = useState(true)
  const [showBollinger, setShowBollinger] = useState(true)
  const[showDarvas, setShowDarvas] = useState(true)
  const [showFibonacci, setShowFibonacci] = useState(true)
  const [showWeinstein, setShowWeinstein] = useState(true)

  // ★ 수정됨: isRefetching과 refetch 함수를 꺼내옵니다.
  const { 
    data: chartData, 
    loading: chartLoading, 
    isRefetching, 
    refetch, 
    error: chartError 
  } = useChartData({
    ticker,
    timeframe,
    scale,
    enabled: ticker.length > 0,
  })

  const { weinstein, darvas, fibonacci, signals } = useIndicators({
    ticker,
    enabled: ticker.length > 0,
  })

  const handleForceRefreshData = async () => {
    try {
      // Use force_refresh=true with POST to get fresh data from KIS API
      await apiClient.post(`/fetch/${ticker}`, {
        force_refresh: true
      })
      window.location.reload()
    } catch (err: any) {
      console.error('Failed to fetch data:', err)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* 헤더 */}
      <header className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex-1 flex items-center gap-4">
            <h1 className="text-2xl font-bold">Technical Analysis Dashboard</h1>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="Ticker (e.g., 010950)"
                className="px-4 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500 focus:outline-none w-48"
              />
              <button
                onClick={handleForceRefreshData}
                disabled={chartLoading || !ticker}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {chartLoading ? 'Loading...' : 'Fetch Data'}
              </button>
            </div>
          </div>

          {/* 타임프레임 & 스케일 */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-400">Timeframe:</label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value as 'daily' | 'weekly')}
                className="px-3 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-400">Scale:</label>
              <select
                value={scale}
                onChange={(e) => setScale(e.target.value as 'linear' | 'log')}
                className="px-3 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
              >
                <option value="linear">Linear</option>
                <option value="log">Log</option>
              </select>
            </div>
          </div>
        </div>
      </header>

      {/* 메인 컨텐츠 */}
      <main className="max-w-7xl mx-auto p-4">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {/* 왼쪽: 차트 영역 */}
          <div className="lg:col-span-3 space-y-4">
            {/* 종목 정보 */}
            {chartData && (
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-4">
                  <div>
                    <h2 className="text-xl font-bold">{chartData.ticker}</h2>
                    <p className="text-gray-400">{chartData.name}</p>
                  </div>
                  {weinstein && (
                    <div className="text-right">
                      <div className="text-sm text-gray-400">Weinstein Stage</div>
                      <div
                        className={`font-semibold px-2 py-1 rounded`}
                        style={{ backgroundColor: getWeinsteinStageColor(weinstein.current_stage) }}
                      >
                        {weinstein.current_stage}
                      </div>
                    </div>
                  )}
                </div>

                {/* 지표 토글 */}
                <div className="flex flex-wrap gap-2 mb-4">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showSMA}
                      onChange={(e) => setShowSMA(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span>SMA</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showBollinger}
                      onChange={(e) => setShowBollinger(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span>Bollinger</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showDarvas}
                      onChange={(e) => setShowDarvas(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span>Darvas Box</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showFibonacci}
                      onChange={(e) => setShowFibonacci(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span>Fibonacci</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showWeinstein}
                      onChange={(e) => setShowWeinstein(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span>Weinstein Stage</span>
                  </label>
                </div>

                {/* 캔들 차트 */}
                {chartData && (
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
                    // ★ 수정됨: Lazy Loading 기능 배선
                    onLoadMore={refetch}
                    isRefetching={isRefetching}
                  />
                )}

                {/* 거래량 패널 */}
                {chartData && <VolumePanel data={chartData.ohlcv} />}

                {/* 지표 패널 */}
                {chartData && (
                  <IndicatorPanel
                    rsi={chartData.indicators?.rsi}
                    macd={chartData.indicators?.macd}
                    vpci={chartData.indicators?.vpci}
                  />
                )}
              </div>
            )}
          </div>

          {/* 오른쪽: 사이드 패널 */}
          <div className="space-y-4">
            {/* 관심종목 */}
            <Watchlist />

            {/* 재무지표 */}
            {chartData && (
              <FinancialMetrics
                weinstein={weinstein ?? undefined}
                financial={undefined}
                signals={signals}
              />
            )}

            {/* API 문서 링크 */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold mb-3">API Documentation</h3>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:underline"
              >
                Swagger UI
              </a>
            </div>
          </div>
        </div>

        {/* 최초 로딩 상태 (배경 전체 덮음) */}
        {chartLoading && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg p-6">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-t-4 border-blue-500"></div>
              <p className="mt-4 text-center">Loading chart data...</p>
            </div>
          </div>
        )}

        {/* 에러 상태 */}
        {chartError && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-red-900 rounded-lg p-6">
              <p className="text-center text-lg font-semibold mb-2">Error</p>
              <p className="text-center">{chartError}</p>
              <button
                onClick={() => window.location.reload()}
                className="mt-4 w-full px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                Retry
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

function getWeinsteinStageColor(stage: number): string {
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