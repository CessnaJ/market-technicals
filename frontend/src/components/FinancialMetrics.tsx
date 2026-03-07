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

function formatStageLabel(label?: string | null) {
  return label ?? 'UNKNOWN'
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
      return '#4b5563'
  }
}

export default function FinancialMetrics({ weinstein, financial, signals = [] }: FinancialMetricsProps) {
  const latestSignal = signals.length > 0 ? signals[0] : null
  const stageHistory = (weinstein?.stage_history ?? []).slice(-24)
  const recentTransitions = (weinstein?.transitions ?? []).slice(-3).reverse()

  return (
    <div className="space-y-6">
      <section className="bg-[#131722] rounded-2xl border border-gray-800 p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[10px] font-black tracking-[0.28em] text-gray-500 uppercase">Market Cycle</div>
            <h3 className="mt-2 text-xl font-black tracking-tight">Weinstein Stage</h3>
          </div>
          <div
            className="px-3 py-1 rounded-full text-[11px] font-black text-white"
            style={{ backgroundColor: getStageColor(weinstein?.current_stage ?? 0) }}
          >
            {weinstein ? `STAGE ${weinstein.current_stage}` : 'NO DATA'}
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-4">
          <div>
            <div className="text-lg font-black">{formatStageLabel(weinstein?.stage_label)}</div>
            <div className="text-xs text-gray-400">
              {weinstein?.benchmark_name ? `Benchmark ${weinstein.benchmark_name} (${weinstein.benchmark_ticker})` : 'Benchmark not linked'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">Mansfield RS</div>
            <div className={`text-lg font-black ${(weinstein?.mansfield_rs ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {weinstein?.mansfield_rs != null ? `${weinstein.mansfield_rs >= 0 ? '+' : ''}${weinstein.mansfield_rs.toFixed(2)}` : '-'}
            </div>
          </div>
        </div>

        {stageHistory.length > 0 && (
          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between text-[10px] font-black tracking-[0.18em] text-gray-500 uppercase">
              <span>Stage History Strip</span>
              <span>{stageHistory[0].date} → {stageHistory[stageHistory.length - 1].date}</span>
            </div>
            <div className="flex h-5 overflow-hidden rounded-lg border border-gray-800 bg-[#0b0e14]">
              {stageHistory.map((item) => (
                <div
                  key={`${item.date}-${item.stage}`}
                  className="flex-1"
                  style={{ backgroundColor: getStageColor(item.stage) }}
                  title={`${item.date} · Stage ${item.stage} · ${item.stage_label}`}
                />
              ))}
            </div>
          </div>
        )}

        <div className="mt-5 rounded-xl border border-gray-800 bg-[#0b0e14] p-4">
          <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">Stage Explanation</div>
          <div className="mt-2 text-sm font-bold">{weinstein?.description?.title ?? 'Stage data unavailable'}</div>
          <p className="mt-2 text-sm leading-6 text-gray-300">
            {weinstein?.description?.summary ?? '30주 이상 데이터가 확보되면 단계 설명이 표시됩니다.'}
          </p>
          <div className="mt-3 space-y-2">
            {(weinstein?.description?.checklist ?? []).map((item) => (
              <div key={item} className="text-xs text-gray-400">
                • {item}
              </div>
            ))}
          </div>
        </div>

        {recentTransitions.length > 0 && (
          <div className="mt-5">
            <div className="text-[10px] font-black tracking-[0.24em] text-gray-500 uppercase">Recent Stage Transitions</div>
            <div className="mt-3 space-y-2">
              {recentTransitions.map((item) => (
                <div key={`${item.date}-${item.from_stage}-${item.to_stage}`} className="flex items-center justify-between rounded-xl bg-[#0b0e14] px-3 py-2 text-xs">
                  <span className="text-gray-300">{item.date}</span>
                  <span className="font-bold text-gray-100">
                    {item.from_stage} → {item.to_stage} {item.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="bg-[#131722] rounded-2xl border border-gray-800 p-5 shadow-2xl">
        <div className="text-[10px] font-black tracking-[0.28em] text-gray-500 uppercase">Financial Snapshot</div>
        <div className="mt-4 space-y-3">
          <MetricRow label="Period" value={financial?.period_date ?? '-'} />
          <MetricRow label="PSR" value={formatMetric(financial?.psr)} />
          <MetricRow label="PER" value={formatMetric(financial?.per)} />
          <MetricRow label="PBR" value={formatMetric(financial?.pbr)} />
          <MetricRow label="ROE" value={formatMetric(financial?.roe, '%')} />
          <MetricRow label="Debt Ratio" value={formatMetric(financial?.debt_ratio, '%')} />
          <MetricRow
            label="Market Cap"
            value={financial?.market_cap != null ? financial.market_cap.toLocaleString() : '-'}
          />
        </div>
      </section>

      <section className="bg-[#131722] rounded-2xl border border-gray-800 p-5 shadow-2xl">
        <div className="text-[10px] font-black tracking-[0.28em] text-gray-500 uppercase">Recent Signal</div>
        {latestSignal ? (
          <div className="mt-4 rounded-xl bg-[#0b0e14] p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-black">{latestSignal.signal_type}</div>
                <div className="mt-1 text-xs text-gray-400">{latestSignal.signal_date}</div>
                <div className="mt-1 text-xs text-gray-500">{latestSignal.direction}</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] font-black tracking-[0.18em] text-gray-500 uppercase">Strength</div>
                <div className={`mt-1 text-lg font-black ${latestSignal.strength != null && latestSignal.strength > 0.7 ? 'text-green-400' : 'text-yellow-400'}`}>
                  {latestSignal.strength != null ? `${Math.round(latestSignal.strength * 100)}%` : '-'}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-4 text-sm text-gray-400">No recent signals</div>
        )}
      </section>
    </div>
  )
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-400">{label}</span>
      <span className="font-bold text-gray-100">{value}</span>
    </div>
  )
}
