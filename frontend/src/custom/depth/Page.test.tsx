// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, it } from 'vitest'
import { QK } from '@/lib/queryKeys'
import { DepthBoard } from './Page'

const LEVELS = {
  symbol: '600519.SH',
  provider: 'tencent_minute',
  bid_prices: [1435, 1434.8, 1434.68, 1434.6, 1434.55],
  bid_volumes: [1, 2, 3, 4, 5],
  ask_prices: [1435.26, 1435.27, 1435.38, 1435.49, 1435.5],
  ask_volumes: [2, 3, 6, 9, 9],
  timestamp: 1_794_557_695_000,
}

it('renders five ask/bid levels with provider and volumes', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } })
  client.setQueryData(QK.watchlist, { symbols: [{ symbol: '600519.SH', name: '贵州茅台', added_at: '' }] })
  client.setQueryData(['capability-matrix'], {
    capabilities: [{
      id: 'depth5', label: '五档盘口', effective: 'tencent_minute',
      effective_display: '腾讯分钟K+五档', candidates: [{ name: 'tencent_minute', display: '腾讯分钟K+五档' }],
    }],
  })
  client.setQueryData(['depth-levels', '600519.SH', ''], LEVELS)

  const host = document.createElement('div')
  document.body.append(host)
  const root = createRoot(host)
  try {
    await act(async () => root.render(
      <QueryClientProvider client={client}>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <DepthBoard />
        </MemoryRouter>
      </QueryClientProvider>,
    ))

    const text = host.textContent ?? ''
    for (const label of ['卖1', '卖5', '买1', '买5']) expect(text).toContain(label)
    expect(text).toContain('1435.26')
    expect(text).toContain('1435.5')
    expect(text).toContain('贵州茅台')
    expect(text).toContain('tencent_minute')
    // 卖盘 5 档 + 买盘 5 档 = 10 行数据, 首行是最高的卖五
    expect(host.querySelectorAll('tbody tr')).toHaveLength(10)
  } finally {
    await act(async () => root.unmount())
    host.remove()
  }
})
