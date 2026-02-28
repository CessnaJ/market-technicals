import { WeinsteinData, FinancialMetrics as FinancialMetricsType, COLORS } from '../types'

interface FinancialMetricsProps {
  weinstein?: WeinsteinData
  financial?: FinancialMetricsType
  signals?: any[]
}

export default function FinancialMetrics({ weinstein, financial, signals }: FinancialMetricsProps) {
  const getStageColor = (stage: number) => {
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

  const getStageLabel = (stage: number) => {
    switch (stage) {
      case 1:
        return 'BASING'
      case 2:
        return 'ADVANCING'
      case 3:
        return 'TOPPING'
      case 4:
        return 'DECLINING'
      default:
        return 'UNKNOWN'
    }
  }

  const latestSignal = signals && signals.length > 0 ? signals[0] : null

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-4">
      <h3 className="text-lg font-semibold mb-3">Financial Metrics</h3>

      {/* PSR */}
      {financial && financial.psr !== undefined && (
        <div className="flex justify-between items-center">
          <span className="text-gray-400">PSR:</span>
          <div className="flex items-center gap-2">
            <span className={`font-semibold ${financial.psr < 0.4 ? 'text-green-500' : 'text-yellow-500'}`}>
              {financial.psr?.toFixed(2)}
            </span>
            {financial.psr < 0.4 && (
              <span className="text-xs text-green-500">
                [Best Case {'<'} 0.4]
              </span>
            )}
          </div>
        </div>
      )}

      {/* Weinstein Stage */}
      {weinstein && (
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Weinstein Stage:</span>
          <div className="flex items-center gap-2">
            <span
              className={`font-semibold px-2 py-1 rounded`}
              style={{ backgroundColor: getStageColor(weinstein.current_stage) }}
            >
              {weinstein.current_stage} ({getStageLabel(weinstein.current_stage)})
            </span>
          </div>
        </div>
      )}

      {/* Mansfield RS */}
      {weinstein && (
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Mansfield RS:</span>
          <span className={`font-semibold ${weinstein.mansfield_rs >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {weinstein.mansfield_rs >= 0 ? '+' : ''}{weinstein.mansfield_rs.toFixed(2)}
          </span>
        </div>
      )}

      {/* PER */}
      {financial && financial.per !== undefined && (
        <div className="flex justify-between items-center">
          <span className="text-gray-400">PER:</span>
          <span className="font-semibold">{financial.per?.toFixed(2)}</span>
        </div>
      )}

      {/* PBR */}
      {financial && financial.pbr !== undefined && (
        <div className="flex justify-between items-center">
          <span className="text-gray-400">PBR:</span>
          <span className="font-semibold">{financial.pbr?.toFixed(2)}</span>
        </div>
      )}

      {/* ROE */}
      {financial && financial.roe !== undefined && (
        <div className="flex justify-between items-center">
          <span className="text-gray-400">ROE:</span>
          <span className="font-semibold">{financial.roe?.toFixed(2)}%</span>
        </div>
      )}

      {/* 최근 시그널 */}
      {latestSignal && (
        <div className="pt-4 border-t border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Recent Signal</div>
          <div className="flex justify-between items-center">
            <div>
              <div className="font-semibold">{latestSignal.signal_type}</div>
              <div className="text-xs text-gray-400">{latestSignal.signal_date}</div>
            </div>
            <div className="text-right">
              <div className="text-sm">Confidence</div>
              <div className={`font-semibold ${latestSignal.strength && latestSignal.strength > 0.7 ? 'text-green-500' : 'text-yellow-500'}`}>
                {latestSignal.strength ? Math.round(latestSignal.strength * 100) : 0}%
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
