import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { api, type DepthLevels, type WatchlistEntry } from '@/lib/api'
import { QK } from '@/lib/queryKeys'
import { fmtPrice } from '@/lib/format'
import { PageHeader } from '@/components/PageHeader'

/**
 * 五档盘口 — 单只标的的买卖五档实时快照。
 *
 * 数据源可切换: 默认跟随「设置 → 数据源 → 五档盘口」的路由, 也可在下拉里显式
 * 指定某个声明了 depth5 的源 (TickFlow / 插件 / 自定义源) 做口径对照。
 * 后端 /api/depth/levels 不落盘、不跨源回退: 源不可用时直接 503 并展示原因。
 *
 * 刷新口径: 盘中 3 秒一轮 (盘口每秒在变); 休市时降到 30 秒 —— 盘口是收盘快照,
 * 再快也拿不到新数据, 白白消耗数据源额度。
 */

const LIVE_INTERVAL = 3_000
const IDLE_INTERVAL = 30_000

function isTradingTime(): boolean {
  const now = new Date()
  const day = now.getDay()
  if (day === 0 || day === 6) return false
  const hm = now.getHours() * 100 + now.getMinutes()
  return (hm >= 915 && hm <= 1135) || (hm >= 1255 && hm <= 1505)
}

function Levels({ levels }: { levels: DepthLevels | undefined }) {
  const rows = useMemo(() => {
    if (!levels) return []
    const asks = levels.ask_prices.map((p, i) => ({
      label: `卖${5 - i}`, price: p, volume: levels.ask_volumes[4 - i] ?? 0,
    })).reverse()
    const bids = levels.bid_prices.map((p, i) => ({
      label: `买${i + 1}`, price: p, volume: levels.bid_volumes[i] ?? 0,
    }))
    return [...asks, ...bids]
  }, [levels])

  return (
    <table className="w-full text-sm tabular-nums">
      <thead>
        <tr className="text-xs text-muted-foreground">
          <th className="py-1 pr-3 text-left font-normal">档位</th>
          <th className="py-1 pl-3 text-right font-normal">价格</th>
          <th className="py-1 pl-3 text-right font-normal">挂单量 (手)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const isAsk = r.label.startsWith('卖')
          return (
            <tr key={r.label} className="border-t border-border/40">
              <td className="py-1 pr-3 text-muted-foreground">{r.label}</td>
              <td className={`py-1 pl-3 text-right font-medium ${isAsk ? 'text-emerald-500' : 'text-red-500'}`}>
                {r.price > 0 ? fmtPrice(r.price) : '—'}
              </td>
              <td className="py-1 pl-3 text-right">{r.price > 0 ? r.volume.toLocaleString() : '—'}</td>
            </tr>
          )
        })}
        {rows.length === 0 && (
          <tr>
            <td colSpan={3} className="py-6 text-center text-muted-foreground">暂无盘口数据</td>
          </tr>
        )}
      </tbody>
    </table>
  )
}

export function DepthBoard() {
  const [symbol, setSymbol] = useState('')
  const [provider, setProvider] = useState('')
  const [auto, setAuto] = useState(true)

  const watchlist = useQuery({
    queryKey: QK.watchlist,
    queryFn: () => api.watchlistList(),
    staleTime: 60_000,
  })
  const entries: WatchlistEntry[] = watchlist.data?.symbols ?? []

  useEffect(() => {
    if (!symbol && entries.length > 0) setSymbol(entries[0].symbol)
  }, [entries, symbol])

  const matrix = useQuery({
    queryKey: ['capability-matrix'],
    queryFn: () => api.capabilityMatrix(),
    staleTime: 60_000,
  })
  const depthCap = matrix.data?.capabilities.find((c) => c.id === 'depth5')

  const levels = useQuery({
    queryKey: ['depth-levels', symbol, provider],
    queryFn: () => api.depthLevels(symbol, provider || undefined),
    enabled: symbol.length > 0,
    retry: false,
    refetchInterval: auto ? (isTradingTime() ? LIVE_INTERVAL : IDLE_INTERVAL) : false,
    refetchOnWindowFocus: false,
  })

  const name = entries.find((e) => e.symbol === symbol)?.name

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <PageHeader
        title="五档盘口"
        subtitle="买卖各五档 · 数据源可切换 · 盘口不落盘"
        right={
          <button
            type="button"
            onClick={() => levels.refetch()}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-secondary hover:text-foreground"
          >
            <RefreshCw className="h-3 w-3" />
            刷新
          </button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.trim().toUpperCase())}
          placeholder="600519.SH"
          className="w-40 rounded-md border border-border bg-transparent px-2 py-1 text-sm tabular-nums"
        />
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="rounded-md border border-border bg-transparent px-2 py-1 text-sm"
        >
          <option value="">
            跟随设置 ({depthCap?.effective_display ?? '—'})
          </option>
          {(depthCap?.candidates ?? []).map((c) => (
            <option key={c.name} value={c.name}>{c.display}</option>
          ))}
        </select>
        <label className="flex items-center gap-1 text-xs text-muted-foreground">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
          自动刷新
        </label>
        <span className="text-xs text-muted-foreground">
          {symbol ? `${name ?? ''} ${symbol}` : ''}
          {levels.data ? ` · ${levels.data.provider}` : ''}
        </span>
      </div>

      {entries.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {entries.slice(0, 12).map((e) => (
            <button
              key={e.symbol}
              type="button"
              onClick={() => setSymbol(e.symbol)}
              className={`rounded border border-border px-2 py-0.5 text-xs ${
                e.symbol === symbol ? 'text-foreground' : 'text-muted-foreground'
              }`}
            >
              {e.name || e.symbol}
            </button>
          ))}
        </div>
      )}

      <div className="max-w-md rounded-lg border border-border bg-card/40 p-3">
        {levels.isError ? (
          <div className="py-6 text-center text-sm text-amber-500">
            盘口不可用：{(levels.error as Error)?.message ?? '请检查数据源配置'}
          </div>
        ) : levels.isLoading ? (
          <div className="py-6 text-center text-sm text-muted-foreground">加载中…</div>
        ) : (
          <Levels levels={levels.data} />
        )}
        <div className="mt-2 text-right text-[11px] text-muted-foreground">
          {levels.data?.timestamp
            ? `盘口时间 ${new Date(levels.data.timestamp).toLocaleTimeString('zh-CN', { hour12: false })}`
            : '—'}
        </div>
      </div>
    </div>
  )
}
