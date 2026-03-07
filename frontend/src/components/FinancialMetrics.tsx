import { COLORS, FinancialMetrics as FinancialMetricsType, Signal, WeinsteinData } from '../types'

interface FinancialMetricsProps {
  weinstein?: WeinsteinData | null
  financial?: FinancialMetricsType | null
  signals?: Signal[]
}

function formatMetric(value: number | null | undefined, suffix = '') {
  if (value == null) {
    return '-'
  }

  return `${value.toFixed(2)}${suffix}`
}

function getStageColor(stage: number) {
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

function getStageLabel(stage: number) {
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

export default function FinancialMetrics({ weinstein, financial, signals = [] }: FinancialMetricsProps) {
  const latestSignal = signals.length > 0 ? signals[0] : null

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-4">
      <h3 className="text-lg font-semibold mb-3">Financial Metrics</h3>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">Period:</span>
        <span className="font-semibold">{financial?.period_date ?? '-'}</span>
      </div>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">PSR:</span>
        <span className="font-semibold">{formatMetric(financial?.psr)}</span>
      </div>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">PER:</span>
        <span className="font-semibold">{formatMetric(financial?.per)}</span>
      </div>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">PBR:</span>
        <span className="font-semibold">{formatMetric(financial?.pbr)}</span>
      </div>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">ROE:</span>
        <span className="font-semibold">{formatMetric(financial?.roe, '%')}</span>
      </div>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">Debt Ratio:</span>
        <span className="font-semibold">{formatMetric(financial?.debt_ratio, '%')}</span>
      </div>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">Market Cap:</span>
        <span className="font-semibold">{financial?.market_cap != null ? financial.market_cap.toLocaleString() : '-'}</span>
      </div>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">Weinstein Stage:</span>
        <div className="flex items-center gap-2">
          <span
            className="font-semibold px-2 py-1 rounded"
            style={{ backgroundColor: getStageColor(weinstein?.current_stage ?? 0) }}
          >
            {weinstein ? `${weinstein.current_stage} (${getStageLabel(weinstein.current_stage)})` : '-'}
          </span>
        </div>
      </div>

      <div className="flex justify-between items-center">
        <span className="text-gray-400">Mansfield RS:</span>
        <span className={`font-semibold ${(weinstein?.mansfield_rs ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
          {weinstein?.mansfield_rs != null ? `${weinstein.mansfield_rs >= 0 ? '+' : ''}${weinstein.mansfield_rs.toFixed(2)}` : '-'}
        </span>
      </div>

      <div className="pt-4 border-t border-gray-700">
        <div className="text-sm text-gray-400 mb-2">Recent Signal</div>
        {latestSignal ? (
          <div className="flex justify-between items-center">
            <div>
              <div className="font-semibold">{latestSignal.signal_type}</div>
              <div className="text-xs text-gray-400">{latestSignal.signal_date}</div>
              <div className="text-xs text-gray-500">{latestSignal.direction}</div>
            </div>
            <div className="text-right">
              <div className="text-sm">Confidence</div>
              <div className={`font-semibold ${latestSignal.strength != null && latestSignal.strength > 0.7 ? 'text-green-500' : 'text-yellow-500'}`}>
                {latestSignal.strength != null ? `${Math.round(latestSignal.strength * 100)}%` : '-'}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-400">No recent signals</div>
        )}
      </div>
    </div>
  )
}
