import { lazy } from 'react'
import type { FrontendExtension } from '@/extensions/types'
import { IconLadder } from '@/components/BrandIcons'

export const DepthBoard = lazy(() => import('./Page').then(m => ({ default: m.DepthBoard })))

const extension: FrontendExtension = {
  id: 'official.depth',
  apiVersion: 1,
  routes: [
    { id: 'depth', path: '/depth', component: DepthBoard },
  ],
  navigation: [
    { id: 'depth', routeId: 'depth', label: '五档盘口', icon: IconLadder },
  ],
}

export default extension
