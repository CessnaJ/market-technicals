import { KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react'

import { useStockSearch } from '../hooks/useStockSearch'

interface StockSearchInputProps {
  value: string
  placeholder?: string
  onCommit: (ticker: string) => void
  onSyncMaster: () => Promise<void> | void
  isSyncingMaster?: boolean
  refreshKey?: number
  className?: string
}

function normalizeSearchText(text: string) {
  return text.toUpperCase().replace(/[^0-9A-Z가-힣ㄱ-ㅎㅏ-ㅣ]/g, '')
}

function isEligibleQuery(query: string) {
  const normalized = normalizeSearchText(query)
  if (!normalized) {
    return false
  }
  if (/^[A-Z0-9]+$/.test(normalized)) {
    return normalized.length >= 1
  }
  return normalized.length >= 2
}

function isRawTicker(value: string) {
  return /^[A-Z]?\d{6}$/.test(value.trim().toUpperCase())
}

export default function StockSearchInput({
  value,
  placeholder,
  onCommit,
  onSyncMaster,
  isSyncingMaster = false,
  refreshKey = 0,
  className = '',
}: StockSearchInputProps) {
  const [draftQuery, setDraftQuery] = useState(value)
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [isComposing, setIsComposing] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const eligible = useMemo(() => isEligibleQuery(draftQuery), [draftQuery])
  const {
    suggestions,
    masterReady,
    loading,
  } = useStockSearch({
    query: draftQuery,
    enabled: isOpen && eligible,
    refreshKey,
  })

  useEffect(() => {
    setDraftQuery(value)
  }, [value])

  useEffect(() => {
    setActiveIndex(suggestions.length > 0 ? 0 : -1)
  }, [suggestions])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const commitTicker = (ticker: string) => {
    const normalized = ticker.trim().toUpperCase()
    if (!normalized) {
      return
    }
    onCommit(normalized)
    setDraftQuery(normalized)
    setIsOpen(false)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setIsOpen(false)
      setDraftQuery(value)
      return
    }
    if (isComposing) {
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setIsOpen(true)
      setActiveIndex((current) => {
        if (suggestions.length === 0) {
          return -1
        }
        return current >= suggestions.length - 1 ? 0 : current + 1
      })
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setIsOpen(true)
      setActiveIndex((current) => {
        if (suggestions.length === 0) {
          return -1
        }
        return current <= 0 ? suggestions.length - 1 : current - 1
      })
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      if (activeIndex >= 0 && suggestions[activeIndex]) {
        commitTicker(suggestions[activeIndex].ticker)
        return
      }
      if (isRawTicker(draftQuery)) {
        commitTicker(draftQuery)
      }
    }
  }

  const showDropdown = isOpen && draftQuery.trim() !== ''

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <input
        type="text"
        value={draftQuery}
        placeholder={placeholder}
        onFocus={() => setIsOpen(true)}
        onChange={(event) => {
          setDraftQuery(event.target.value.toUpperCase())
          setIsOpen(true)
        }}
        onKeyDown={handleKeyDown}
        onCompositionStart={() => setIsComposing(true)}
        onCompositionEnd={() => setIsComposing(false)}
        className="w-full rounded border border-gray-700 bg-[#1e222d] px-4 py-2 text-sm font-bold uppercase outline-none transition-all focus:border-blue-500"
      />

      {showDropdown && (
        <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-40 overflow-hidden rounded-2xl border border-gray-800 bg-[#0b0e14]/98 shadow-2xl backdrop-blur">
          {!eligible ? (
            <div className="px-4 py-3 text-sm text-gray-400">한글/초성 검색은 2글자 이상 입력하세요.</div>
          ) : loading ? (
            <div className="px-4 py-3 text-sm text-gray-400">검색 중...</div>
          ) : suggestions.length > 0 ? (
            <div className="max-h-80 overflow-y-auto py-2">
              {suggestions.map((item, index) => (
                <button
                  key={`${item.ticker}-${item.name}`}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => commitTicker(item.ticker)}
                  className={`flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors ${
                    index === activeIndex ? 'bg-blue-600/20' : 'hover:bg-white/5'
                  }`}
                >
                  <div>
                    <div className="text-sm font-black text-white">{item.name}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] font-black uppercase tracking-[0.14em] text-gray-500">
                      <span>{item.ticker}</span>
                      {item.market && <span>{item.market}</span>}
                    </div>
                  </div>
                  <div className="max-w-[45%] text-right text-xs text-gray-400">
                    {item.industry ?? item.sector ?? '-'}
                  </div>
                </button>
              ))}
            </div>
          ) : !masterReady ? (
            <div className="px-4 py-4">
              <div className="text-sm font-bold text-white">종목 마스터 동기화 필요</div>
              <div className="mt-1 text-xs text-gray-400">
                검색 추천과 초성 검색은 마스터 적재 후 사용할 수 있습니다.
              </div>
              <button
                type="button"
                onClick={() => void onSyncMaster()}
                disabled={isSyncingMaster}
                className="mt-3 rounded-lg border border-blue-500/40 bg-blue-600/20 px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-blue-300 disabled:opacity-50"
              >
                {isSyncingMaster ? 'SYNCING...' : 'SYNC MASTER'}
              </button>
            </div>
          ) : (
            <div className="px-4 py-3 text-sm text-gray-400">검색 결과 없음</div>
          )}
        </div>
      )}
    </div>
  )
}
