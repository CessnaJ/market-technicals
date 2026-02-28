import { COLORS } from '../types'

interface SignalBadgeProps {
  type: 'false_signal' | 'true_breakout' | 'bullish_divergence' | 'bearish_divergence'
  date?: string
  confidence?: number
}

export default function SignalBadge({ type, date, confidence }: SignalBadgeProps) {
  return (
    <div className="relative">
      {type === 'false_signal' && (
        <div className="absolute top-0 left-0 transform -translate-x-1/2 -translate-y-1/2">
          <svg width="20" height="20" viewBox="0 0 20 20" className="drop-shadow-lg">
            <polygon
              points="10,0 20,10 10,20"
              fill={COLORS.bearish}
              stroke="white"
              strokeWidth="2"
            />
          </svg>
        </div>
      )}
      {type === 'true_breakout' && (
        <div className="absolute top-0 left-0 transform -translate-x-1/2 -translate-y-1/2">
          <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center">
            <div className="w-2 h-2 bg-white rounded-full" />
          </div>
        </div>
      )}
      {type === 'bullish_divergence' && (
        <div className="absolute top-0 left-0 transform -translate-x-1/2 -translate-y-1/2">
          <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center">
            <span className="text-white text-xs">🟢</span>
          </div>
        </div>
      )}
      {type === 'bearish_divergence' && (
        <div className="absolute top-0 left-0 transform -translate-x-1/2 -translate-y-1/2">
          <div className="w-6 h-6 rounded-full bg-red-500 flex items-center justify-center">
            <span className="text-white text-xs">🔴</span>
          </div>
        </div>
      )}
      {date && (
        <div className="absolute top-6 left-1/2 transform -translate-x-1/2 text-xs text-gray-400">
          {date}
        </div>
      )}
      {confidence !== undefined && (
        <div className="absolute top-6 right-0 text-xs text-gray-400">
          {Math.round(confidence * 100)}%
        </div>
      )}
    </div>
  )
}
