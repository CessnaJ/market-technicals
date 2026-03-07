import { useEffect, useState } from 'react'

import apiClient from '../api/client'
import { WatchlistItem } from '../types'

interface WatchlistProps {
  currentTicker: string
  onSelectTicker: (ticker: string) => void
}

export default function Watchlist({ currentTicker, onSelectTicker }: WatchlistProps) {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(false)
  const [newTicker, setNewTicker] = useState('')
  const [newName, setNewName] = useState('')

  useEffect(() => {
    void fetchWatchlist()
  }, [])

  const fetchWatchlist = async () => {
    setLoading(true)
    try {
      const response = await apiClient.get<WatchlistItem[]>('/watchlist')
      setWatchlist(response.data)
    } catch (err: any) {
      console.error('Failed to fetch watchlist:', err)
    } finally {
      setLoading(false)
    }
  }

  const addToWatchlist = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!newTicker.trim()) return

    try {
      await apiClient.post('/watchlist', null, {
        params: {
          ticker: newTicker.trim(),
          name: newName.trim() || newTicker.trim(),
        },
      })
      const addedTicker = newTicker.trim()
      setNewTicker('')
      setNewName('')
      await fetchWatchlist()
      onSelectTicker(addedTicker)
    } catch (err: any) {
      console.error('Failed to add to watchlist:', err)
    }
  }

  const removeFromWatchlist = async (ticker: string) => {
    try {
      await apiClient.delete(`/watchlist/${ticker}`)
      await fetchWatchlist()
    } catch (err: any) {
      console.error('Failed to remove from watchlist:', err)
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold mb-3">Watchlist</h3>

      <form onSubmit={addToWatchlist} className="mb-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={newTicker}
            onChange={(event) => setNewTicker(event.target.value)}
            placeholder="Ticker (e.g., 010950)"
            className="flex-1 px-3 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
          />
          <input
            type="text"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder="Name (optional)"
            className="flex-1 px-3 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading || !newTicker.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Add
          </button>
        </div>
      </form>

      {loading ? (
        <div className="text-center text-gray-400 py-8">Loading...</div>
      ) : watchlist.length === 0 ? (
        <div className="text-center text-gray-400 py-8">No items in watchlist</div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {watchlist.map((item) => {
            const isSelected = item.ticker === currentTicker

            return (
              <div
                key={item.id}
                className={`w-full flex items-center justify-between p-3 rounded transition-colors text-left ${
                  isSelected ? 'bg-blue-600/30 border border-blue-500/50' : 'bg-gray-700 hover:bg-gray-600 border border-transparent'
                }`}
              >
                <div className="flex-1">
                  <button
                    type="button"
                    onClick={() => onSelectTicker(item.ticker)}
                    className="w-full text-left"
                  >
                    <div className="font-semibold">{item.ticker}</div>
                    <div className="text-sm text-gray-400">{item.name || '-'}</div>
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => void removeFromWatchlist(item.ticker)}
                  className="text-red-400 hover:text-red-300 ml-2"
                  title="Remove from watchlist"
                >
                  X
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
