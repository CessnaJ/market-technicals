import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import apiClient from '../api/client'
import StockSearchInput from '../components/StockSearchInput'
import {
  ScreeningFilterConfig,
  ScreeningFilterName,
  ScreeningResultRow,
  ScreeningResultsResponse,
  ScreeningRunStatusResponse,
  ScreeningScanCreateResponse,
} from '../types'

const DEFAULT_FILTERS: ScreeningFilterName[] = ['vpci_positive', 'rs_positive']

const FILTER_OPTIONS: Array<{
  key: ScreeningFilterName
  label: string
  description: string
  formulaTitle: string
  formulaLines: string[]
}> = [
  {
    key: 'vpci_positive',
    label: 'VPCI Positive',
    description: '최근 VPCI가 0보다 크고 5개 bar 추세가 꺾이지 않은 종목만 포함',
    formulaTitle: 'VPCI 계산식 / 통과 조건',
    formulaLines: [
      'VPCI = (VWMA20 - SMA20) × (VWMA5 / SMA5) × (VolMA5 / VolMA20) / Alpha',
      'Alpha = StdDev(close, 20) / StdDev(volume, 20)',
      'Pass: VPCI[-1] > 0',
      'Trend: VPCI[-1] - VPCI[-5] ≥ 0',
    ],
  },
  {
    key: 'rs_positive',
    label: 'RS Positive',
    description: '벤치마크 대비 Mansfield RS가 양수인 종목만 포함',
    formulaTitle: 'Mansfield RS 계산식 / 통과 조건',
    formulaLines: [
      'StockChange = (Close_t / Close_t-52) - 1',
      'BenchmarkChange = (Benchmark_t / Benchmark_t-52) - 1',
      'Mansfield RS = StockChange - BenchmarkChange',
      'Pass: Mansfield RS[-1] > 0',
    ],
  },
  {
    key: 'volume_confirmed',
    label: 'Volume Confirmed',
    description: 'Stage 2 시작 주간 거래량이 최근 10주 평균보다 충분히 큰 종목만 포함',
    formulaTitle: '거래량 확인식 / 통과 조건',
    formulaLines: [
      'breakout_volume = volume[stage2_transition_week]',
      'prior_avg_10w = mean(volume[t-10:t-1])',
      'volume_ratio = breakout_volume / prior_avg_10w',
      'Pass: volume_ratio ≥ Volume Ratio',
    ],
  },
  {
    key: 'not_extended',
    label: 'Not Extended',
    description: '현재가가 30주선 대비 과도하게 이격된 종목은 제외',
    formulaTitle: '30주선 이격도 / 통과 조건',
    formulaLines: [
      'MA30W = SMA(weekly close, 30)',
      'distance_to_30w_pct = ((close - MA30W) / MA30W) × 100',
      'Pass: distance_to_30w_pct ≤ Max Distance %',
    ],
  },
]

const CORE_GATE_TOOLTIP = {
  title: 'Stage 2 시작 핵심 게이트',
  lines: [
    'MA30W = SMA(weekly close, 30)',
    'ma30w_slope_pct = ((MA30W_t - MA30W_t-4) / MA30W_t-4) × 100',
    'current_stage = 2',
    'close[-1] > MA30W[-1]',
    "ma_slope[-1] = 'RISING' and ma30w_slope_pct[-1] > 0",
    'weeks_since_stage2_start ≤ Stage Window',
  ],
}

const FIELD_TOOLTIPS = {
  stageWindow: {
    title: 'Stage Window',
    lines: [
      '최근 Stage 2 전환을 몇 주 전까지 허용할지 정합니다.',
      'weeks_since_stage2_start = last_index - transition_index',
      'Pass: weeks_since_stage2_start ≤ Stage Window',
    ],
  },
  maxDistance: {
    title: 'Max Distance %',
    lines: [
      '30주선 대비 현재가 이격 허용치입니다.',
      'distance_to_30w_pct = ((close - MA30W) / MA30W) × 100',
      'Not Extended 활성 시 Pass: distance_to_30w_pct ≤ Max Distance %',
    ],
  },
  volumeRatio: {
    title: 'Volume Ratio',
    lines: [
      'Stage 2 전환 주간 거래량이 직전 10주 평균보다 얼마나 큰지 봅니다.',
      'volume_ratio = breakout_volume / prior_avg_10w',
      'Volume Confirmed 활성 시 Pass: volume_ratio ≥ Volume Ratio',
    ],
  },
  excludeInstruments: {
    title: '보통주 중심 제외형',
    lines: [
      'ETF/ETN 브랜드명 패턴은 기본 제외',
      "이름에 '스팩' 포함 시 제외",
      "우선주 패턴(우, 우B, 1우 등) 제외",
    ],
  },
} as const

export default function Screener() {
  const navigate = useNavigate()
  const [benchmarkTicker, setBenchmarkTicker] = useState('069500')
  const [includeFilters, setIncludeFilters] = useState<ScreeningFilterName[]>(DEFAULT_FILTERS)
  const [stageWindowWeeks, setStageWindowWeeks] = useState(8)
  const [maxDistanceTo30w, setMaxDistanceTo30w] = useState(15)
  const [volumeRatioMin, setVolumeRatioMin] = useState(1.5)
  const [excludeInstruments, setExcludeInstruments] = useState(true)
  const [scan, setScan] = useState<ScreeningRunStatusResponse | null>(null)
  const [results, setResults] = useState<ScreeningResultRow[]>([])
  const [resultsTotalCount, setResultsTotalCount] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSyncingMaster, setIsSyncingMaster] = useState(false)
  const [masterRefreshKey, setMasterRefreshKey] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [isLoadingResults, setIsLoadingResults] = useState(false)

  const requestPayload = useMemo<ScreeningFilterConfig>(
    () => ({
      preset: 'weinstein_stage2_start',
      benchmark_ticker: benchmarkTicker,
      include_filters: [...includeFilters].sort(),
      stage_start_window_weeks: stageWindowWeeks,
      max_distance_to_30w_pct: maxDistanceTo30w,
      volume_ratio_min: volumeRatioMin,
      exclude_instruments: excludeInstruments,
    }),
    [benchmarkTicker, excludeInstruments, includeFilters, maxDistanceTo30w, stageWindowWeeks, volumeRatioMin]
  )

  useEffect(() => {
    if (!scan || !['PENDING', 'RUNNING'].includes(scan.status)) {
      return
    }

    const handle = window.setInterval(async () => {
      try {
        const response = await apiClient.get<ScreeningRunStatusResponse>(`/screener/scans/${scan.scan_id}`)
        setScan(response.data)
        if (response.data.status === 'COMPLETED') {
          window.clearInterval(handle)
          void fetchResults(response.data.scan_id)
        }
      } catch (err: any) {
        window.clearInterval(handle)
        setError(err.response?.data?.detail || '스크리너 상태를 불러오지 못했습니다.')
      }
    }, 2000)

    return () => window.clearInterval(handle)
  }, [scan])

  const handleSyncMaster = async () => {
    if (isSyncingMaster) {
      return
    }

    setIsSyncingMaster(true)
    try {
      await apiClient.post('/stocks/sync-master')
      setMasterRefreshKey((current) => current + 1)
    } catch (err) {
      console.error('Failed to sync stock master:', err)
    } finally {
      setIsSyncingMaster(false)
    }
  }

  const fetchResults = async (scanId: number) => {
    setIsLoadingResults(true)
    try {
      const response = await apiClient.get<ScreeningResultsResponse>(`/screener/scans/${scanId}/results?limit=200&offset=0`)
      setResults(response.data.results)
      setResultsTotalCount(response.data.total_count)
    } catch (err: any) {
      setError(err.response?.data?.detail || '스크리너 결과를 불러오지 못했습니다.')
      setResults([])
      setResultsTotalCount(0)
    } finally {
      setIsLoadingResults(false)
    }
  }

  const handleRunScreen = async () => {
    setIsSubmitting(true)
    setError(null)
    try {
      const response = await apiClient.post<ScreeningScanCreateResponse>('/screener/scans', requestPayload)
      setScan(response.data)
      if (response.data.status === 'COMPLETED') {
        await fetchResults(response.data.scan_id)
      } else {
        setResults([])
        setResultsTotalCount(0)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '스크리너 실행을 시작하지 못했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleToggleFilter = (filterKey: ScreeningFilterName) => {
    setIncludeFilters((current) =>
      current.includes(filterKey)
        ? current.filter((item) => item !== filterKey)
        : [...current, filterKey]
    )
  }

  return (
    <div className="min-h-screen bg-[#0b0e14] text-gray-100">
      <header className="sticky top-0 z-30 border-b border-gray-800 bg-[#131722] p-4">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="text-[10px] font-black uppercase tracking-[0.28em] text-gray-500">Universe Screener</div>
            <h1 className="mt-2 text-2xl font-black tracking-tight text-amber-300">Weinstein Stage 2 Starter</h1>
            <p className="mt-2 max-w-3xl text-sm text-gray-400">
              30주선 돌파/전환 구간을 기본 gate로 두고, VPCI, RS, 거래량, 과열 여부를 모듈형 필터로 조합해 후보를 랭킹합니다.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/"
              className="rounded border border-gray-700 bg-[#1e222d] px-3 py-2 text-xs font-black uppercase tracking-[0.16em] text-gray-300 transition-colors hover:bg-[#252b38]"
            >
              Dashboard
            </Link>
            <button
              type="button"
              onClick={handleRunScreen}
              disabled={isSubmitting || scan?.status === 'RUNNING' || scan?.status === 'PENDING'}
              className="rounded bg-amber-500 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-[#111827] transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? 'STARTING...' : scan?.status === 'RUNNING' ? 'RUNNING...' : 'RUN SCREEN'}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1600px] grid-cols-1 gap-6 p-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="rounded-2xl border border-gray-800 bg-[#131722] p-5 shadow-2xl">
          <div className="text-[10px] font-black uppercase tracking-[0.28em] text-gray-500">Preset</div>
          <div className="mt-2 flex items-center gap-2 text-xl font-black">
            <span>Stage 2 Start</span>
            <HoverFormulaTooltip title={CORE_GATE_TOOLTIP.title} lines={CORE_GATE_TOOLTIP.lines} />
          </div>
          <div className="mt-2 text-sm leading-6 text-gray-400">
            현재 Stage 2이면서 최근 Stage 2 전환이 발생했고, 30주선 위에서 상승 기울기를 유지하는 종목을 대상으로 합니다.
          </div>

          <div className="mt-5">
            <div className="mb-2 text-[10px] font-black uppercase tracking-[0.24em] text-gray-500">Benchmark</div>
            <StockSearchInput
              value={benchmarkTicker}
              onCommit={setBenchmarkTicker}
              placeholder="BENCHMARK"
              onSyncMaster={handleSyncMaster}
              isSyncingMaster={isSyncingMaster}
              refreshKey={masterRefreshKey}
            />
          </div>

          <div className="mt-5 space-y-4 rounded-xl border border-gray-800 bg-[#0b0e14] p-4">
            <div className="text-[10px] font-black uppercase tracking-[0.24em] text-gray-500">Filters</div>
            {FILTER_OPTIONS.map((option) => (
              <label
                key={option.key}
                className={`group relative block rounded-xl border px-4 py-3 transition-colors ${
                  includeFilters.includes(option.key)
                    ? 'border-amber-500/30 bg-amber-500/10'
                    : 'border-gray-800 bg-[#131722]'
                }`}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={includeFilters.includes(option.key)}
                    onChange={() => handleToggleFilter(option.key)}
                    className="mt-1 h-4 w-4 rounded border-gray-600 bg-[#0b0e14] text-amber-400"
                  />
                  <div>
                    <div className="flex items-center gap-2 text-sm font-black text-white">
                      <span>{option.label}</span>
                      <HoverFormulaTooltip title={option.formulaTitle} lines={option.formulaLines} />
                    </div>
                    <div className="mt-1 text-xs leading-5 text-gray-400">{option.description}</div>
                  </div>
                </div>
              </label>
            ))}

            <div className="grid grid-cols-2 gap-3">
              <Field label="Stage Window" tooltipTitle={FIELD_TOOLTIPS.stageWindow.title} tooltipLines={FIELD_TOOLTIPS.stageWindow.lines}>
                <input
                  type="number"
                  min={1}
                  max={26}
                  value={stageWindowWeeks}
                  onChange={(event) => setStageWindowWeeks(Number(event.target.value) || 8)}
                  className="w-full rounded border border-gray-700 bg-[#131722] px-3 py-2 text-sm font-bold"
                />
              </Field>
              <Field label="Max Distance %" tooltipTitle={FIELD_TOOLTIPS.maxDistance.title} tooltipLines={FIELD_TOOLTIPS.maxDistance.lines}>
                <input
                  type="number"
                  min={1}
                  max={50}
                  step={0.5}
                  value={maxDistanceTo30w}
                  onChange={(event) => setMaxDistanceTo30w(Number(event.target.value) || 15)}
                  className="w-full rounded border border-gray-700 bg-[#131722] px-3 py-2 text-sm font-bold"
                />
              </Field>
              <Field label="Volume Ratio" tooltipTitle={FIELD_TOOLTIPS.volumeRatio.title} tooltipLines={FIELD_TOOLTIPS.volumeRatio.lines}>
                <input
                  type="number"
                  min={1}
                  max={10}
                  step={0.1}
                  value={volumeRatioMin}
                  onChange={(event) => setVolumeRatioMin(Number(event.target.value) || 1.5)}
                  className="w-full rounded border border-gray-700 bg-[#131722] px-3 py-2 text-sm font-bold"
                />
              </Field>
              <label className="rounded-xl border border-gray-800 bg-[#131722] px-3 py-2 text-sm font-bold text-white">
                <div className="mb-2 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-gray-500">
                  <span>Universe</span>
                  <HoverFormulaTooltip title={FIELD_TOOLTIPS.excludeInstruments.title} lines={FIELD_TOOLTIPS.excludeInstruments.lines} />
                </div>
                <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={excludeInstruments}
                  onChange={() => setExcludeInstruments((current) => !current)}
                  className="h-4 w-4 rounded border-gray-600 bg-[#0b0e14] text-amber-400"
                />
                보통주 중심 제외형
                </div>
              </label>
            </div>
          </div>
        </aside>

        <section className="space-y-6">
          <div className="rounded-2xl border border-gray-800 bg-[#131722] p-5 shadow-2xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[10px] font-black uppercase tracking-[0.28em] text-gray-500">Run Status</div>
                <div className="mt-2 text-2xl font-black">
                  {scan ? `#${scan.scan_id} · ${scan.status}` : 'No scan yet'}
                </div>
                <div className="mt-2 text-sm text-gray-400">
                  {scan
                    ? `${scan.matched_count} matched / ${scan.processed_candidates} processed / ${scan.total_candidates} total`
                    : 'RUN SCREEN을 누르면 전종목 후보군을 계산합니다.'}
                </div>
              </div>

              {scan && (
                <div className="flex flex-wrap gap-2">
                  {scan.is_cached && (
                    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-emerald-300">
                      Cached
                    </span>
                  )}
                  <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-blue-300">
                    Benchmark {scan.benchmark_ticker}
                  </span>
                </div>
              )}
            </div>

            {error && (
              <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

            {scan && (
              <div className="mt-5 grid gap-3 md:grid-cols-4">
                <StatusCard label="Matched" value={String(scan.matched_count)} />
                <StatusCard label="Filtered Out" value={String(scan.summary.filtered_out)} />
                <StatusCard label="Insufficient" value={String(scan.summary.insufficient_data)} />
                <StatusCard label="Excluded" value={String(scan.summary.excluded_instruments)} />
              </div>
            )}
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <SummaryBars
              title="Sector Concentration"
              items={scan?.summary.sector_counts ?? []}
              accentClass="bg-blue-500"
            />
            <SummaryBars
              title="Industry Concentration"
              items={scan?.summary.industry_counts ?? []}
              accentClass="bg-emerald-500"
            />
          </div>

          <section className="rounded-2xl border border-gray-800 bg-[#131722] p-5 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-[10px] font-black uppercase tracking-[0.28em] text-gray-500">Results</div>
                <div className="mt-2 text-xl font-black">Top Ranked Candidates</div>
              </div>
              <div className="text-sm text-gray-400">
                {isLoadingResults ? '결과 로딩 중...' : `${results.length} / ${resultsTotalCount} rows`}
              </div>
            </div>

            <div className="mt-5 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-[10px] uppercase tracking-[0.18em] text-gray-500">
                  <tr>
                    <th className="px-3 py-2">Rank</th>
                    <th className="px-3 py-2">종목</th>
                    <th className="px-3 py-2">Score</th>
                    <th className="px-3 py-2">Stage</th>
                    <th className="px-3 py-2">Weeks</th>
                    <th className="px-3 py-2">30W Dist</th>
                    <th className="px-3 py-2">30W Slope</th>
                    <th className="px-3 py-2">Mansfield RS</th>
                    <th className="px-3 py-2">VPCI</th>
                    <th className="px-3 py-2">Volume</th>
                    <th className="px-3 py-2">Sector / Industry</th>
                  </tr>
                </thead>
                <tbody>
                  {results.length === 0 ? (
                    <tr>
                      <td colSpan={11} className="px-3 py-10 text-center text-sm text-gray-500">
                        {scan?.status === 'RUNNING' || scan?.status === 'PENDING'
                          ? '스크리너 계산이 진행 중입니다.'
                          : '아직 표시할 결과가 없습니다.'}
                      </td>
                    </tr>
                  ) : (
                    results.map((row) => (
                      <tr
                        key={`${row.ticker}-${row.rank}`}
                        onClick={() => navigate(`/?ticker=${row.ticker}`)}
                        className="cursor-pointer border-t border-gray-800 transition-colors hover:bg-white/5"
                      >
                        <td className="px-3 py-3 font-black text-amber-300">{row.rank}</td>
                        <td className="px-3 py-3">
                          <div className="font-black text-white">{row.name}</div>
                          <div className="mt-1 font-mono text-xs text-gray-500">{row.ticker}</div>
                          <div className="mt-2 flex flex-wrap gap-1">
                            {row.matched_filters.map((item) => (
                              <span key={item} className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.12em] text-emerald-300">
                                {formatFilterLabel(item)}
                              </span>
                            ))}
                            {row.failed_filters.map((item) => (
                              <span key={item} className="rounded-full border border-red-500/20 bg-red-500/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.12em] text-red-300">
                                {formatFilterLabel(item)}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-3 py-3 font-black text-white">{row.score.toFixed(2)}</td>
                        <td className="px-3 py-3 text-gray-300">{row.stage_label}</td>
                        <td className="px-3 py-3 text-gray-300">{row.weeks_since_stage2_start ?? '-'}</td>
                        <td className="px-3 py-3 text-gray-300">{formatSigned(row.distance_to_30w_pct, '%')}</td>
                        <td className="px-3 py-3 text-gray-300">{formatSigned(row.ma30w_slope_pct, '%')}</td>
                        <td className="px-3 py-3 text-gray-300">{formatSigned(row.mansfield_rs)}</td>
                        <td className="px-3 py-3 text-gray-300">{formatSigned(row.vpci_value)}</td>
                        <td className="px-3 py-3 text-gray-300">{formatPlain(row.volume_ratio)}</td>
                        <td className="px-3 py-3 text-xs text-gray-400">
                          <div>{row.sector ?? '-'}</div>
                          <div className="mt-1">{row.industry ?? '-'}</div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </section>
      </main>
    </div>
  )
}

function StatusCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-[#0b0e14] px-4 py-3">
      <div className="text-[10px] font-black uppercase tracking-[0.18em] text-gray-500">{label}</div>
      <div className="mt-2 text-xl font-black text-white">{value}</div>
    </div>
  )
}

function Field({
  label,
  children,
  tooltipTitle,
  tooltipLines,
}: {
  label: string
  children: ReactNode
  tooltipTitle?: string
  tooltipLines?: readonly string[]
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-gray-500">
        <span>{label}</span>
        {tooltipTitle && tooltipLines ? <HoverFormulaTooltip title={tooltipTitle} lines={tooltipLines} /> : null}
      </div>
      {children}
    </div>
  )
}

function HoverFormulaTooltip({ title, lines }: { title: string; lines: readonly string[] }) {
  return (
    <span className="group/tooltip relative inline-flex">
      <span className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-gray-700 bg-[#0b0e14] text-[10px] font-black text-amber-300">
        ?
      </span>
      <span className="pointer-events-none absolute left-full top-1/2 z-20 ml-3 w-[320px] -translate-y-1/2 rounded-xl border border-amber-500/20 bg-[#050811]/95 px-4 py-3 opacity-0 shadow-2xl transition-opacity duration-150 group-hover/tooltip:opacity-100">
        <span className="block text-[11px] font-black uppercase tracking-[0.16em] text-amber-300">{title}</span>
        <span className="mt-2 block space-y-1">
          {lines.map((line) => (
            <span key={`${title}-${line}`} className="block text-xs leading-5 text-gray-200">
              {line}
            </span>
          ))}
        </span>
      </span>
    </span>
  )
}

function SummaryBars({
  title,
  items,
  accentClass,
}: {
  title: string
  items: Array<{ name: string; count: number }>
  accentClass: string
}) {
  const maxCount = Math.max(...items.map((item) => item.count), 1)

  return (
    <section className="rounded-2xl border border-gray-800 bg-[#131722] p-5 shadow-2xl">
      <div className="text-[10px] font-black uppercase tracking-[0.28em] text-gray-500">{title}</div>
      <div className="mt-5 space-y-3">
        {items.length === 0 ? (
          <div className="text-sm text-gray-500">요약 데이터가 아직 없습니다.</div>
        ) : (
          items.map((item) => (
            <div key={`${title}-${item.name}`} className="space-y-1">
              <div className="flex items-center justify-between gap-3 text-sm">
                <div className="truncate font-bold text-gray-200">{item.name}</div>
                <div className="font-mono text-xs text-gray-500">{item.count}</div>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[#0b0e14]">
                <div
                  className={`h-full rounded-full ${accentClass}`}
                  style={{ width: `${(item.count / maxCount) * 100}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  )
}

function formatFilterLabel(value: string) {
  switch (value) {
    case 'stage2_start':
      return 'Stage2'
    case 'vpci_positive':
      return 'VPCI'
    case 'rs_positive':
      return 'RS'
    case 'volume_confirmed':
      return 'VOL'
    case 'not_extended':
      return 'NE'
    default:
      return value
  }
}

function formatSigned(value: number | null, suffix = '') {
  if (value == null) {
    return '-'
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}${suffix}`
}

function formatPlain(value: number | null) {
  if (value == null) {
    return '-'
  }
  return value.toFixed(2)
}
