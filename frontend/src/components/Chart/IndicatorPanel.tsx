import { useState } from 'react'
import { IndicatorData, MACDData, VPCIData, COLORS } from '../../types'

interface IndicatorPanelProps {
  rsi?: IndicatorData[]
  macd?: MACDData[]
  vpci?: VPCIData[]
}

export default function IndicatorPanel({ rsi, macd, vpci }: IndicatorPanelProps) {
  const [activeTab, setActiveTab] = useState<'rsi' | 'macd' | 'vpci'>('rsi')

  return (
    <div className="w-full bg-gray-800 rounded-lg p-4">
      {/* 탭 버튼 */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setActiveTab('rsi')}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
            activeTab === 'rsi'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          RSI
        </button>
        <button
          onClick={() => setActiveTab('macd')}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
            activeTab === 'macd'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          MACD
        </button>
        <button
          onClick={() => setActiveTab('vpci')}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
            activeTab === 'vpci'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          VPCI
        </button>
      </div>

      {/* RSI 패널 */}
      {activeTab === 'rsi' && rsi && rsi.length > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">RSI (14)</span>
            <div className="flex gap-4">
              <span className="text-green-500">Overbought: {'>'} 70</span>
              <span className="text-red-500">Oversold: {'<'} 30</span>
            </div>
          </div>
          <div className="h-32 bg-gray-900 rounded p-2">
            <svg viewBox="0 0 400 100" className="w-full h-full">
              {/* RSI 라인 */}
              <polyline
                points={rsi.map((d, i) => `${i * (400 / (rsi.length - 1))},${100 - d.value}`).join(' ')}
                fill="none"
                stroke={COLORS.text}
                strokeWidth="2"
              />
              {/* 기준선 */}
              <line x1="0" y1="30" x2="400" y2="30" stroke="#4b5563" strokeWidth="1" strokeDasharray="4" />
              <line x1="0" y1="70" x2="400" y2="70" stroke="#22c55e" strokeWidth="1" strokeDasharray="4" />
              <line x1="0" y1="0" x2="400" y2="0" stroke="#ef4444" strokeWidth="1" strokeDasharray="4" />
            </svg>
          </div>
        </div>
      )}

      {/* MACD 패널 */}
      {activeTab === 'macd' && macd && macd.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm text-gray-400">MACD (12, 26, 9)</div>
          <div className="h-32 bg-gray-900 rounded p-2">
            <svg viewBox="0 0 400 100" className="w-full h-full">
              {/* MACD 라인 */}
              <polyline
                points={macd.map((d, i) => `${i * (400 / (macd.length - 1))},${50 - d.value}`).join(' ')}
                fill="none"
                stroke={COLORS.bullish}
                strokeWidth="2"
              />
              {/* Signal 라인 */}
              <polyline
                points={macd.map((d, i) => `${i * (400 / (macd.length - 1))},${50 - d.signal}`).join(' ')}
                fill="none"
                stroke="#f59e0b"
                strokeWidth="1"
              />
              {/* 히스토그램 */}
              {macd.map((d, i) => {
                const x = i * (400 / (macd.length - 1))
                const y = 50
                const height = d.histogram * 20
                return (
                  <rect
                    key={i}
                    x={x}
                    y={height >= 0 ? y - height : y}
                    width={400 / (macd.length - 1) - 1}
                    height={Math.abs(height)}
                    fill={d.histogram >= 0 ? COLORS.bullish : COLORS.bearish}
                    opacity="0.7"
                  />
                )
              })}
              {/* 기준선 */}
              <line x1="0" y1="50" x2="400" y2="50" stroke="#4b5563" strokeWidth="1" />
            </svg>
          </div>
        </div>
      )}

      {/* VPCI 패널 */}
      {activeTab === 'vpci' && vpci && vpci.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm text-gray-400">VPCI (Volume Price Confirmation Indicator)</div>
          <div className="h-32 bg-gray-900 rounded p-2">
            <svg viewBox="0 0 400 100" className="w-full h-full">
              {/* VPCI 라인 */}
              <polyline
                points={vpci.map((d, i) => `${i * (400 / (vpci.length - 1))},${50 - d.value}`).join(' ')}
                fill="none"
                stroke={COLORS.text}
                strokeWidth="2"
              />
              {/* 기준선 */}
              <line x1="0" y1="50" x2="400" y2="50" stroke="#4b5563" strokeWidth="1" strokeDasharray="4" />
              {/* 다이버전스 마커 */}
              {vpci.map((d, i) => {
                if (d.signal.includes('DIVERGE')) {
                  const x = i * (400 / (vpci.length - 1))
                  const y = 50 - d.value
                  const isBearish = d.signal === 'DIVERGE_BEAR'
                  return (
                    <circle
                      key={i}
                      cx={x}
                      cy={y}
                      r="4"
                      fill={isBearish ? '#ef4444' : '#22c55e'}
                    />
                  )
                }
                return null
              })}
              {/* 기준선 */}
              <line x1="0" y1="50" x2="400" y2="50" stroke="#4b5563" strokeWidth="1" strokeDasharray="4" />
            </svg>
          </div>
          <div className="text-xs text-gray-400 mt-2">
            <div className="flex gap-4">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>Confirm Bull/Bear</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                <span>Diverge (False Signal)</span>
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
