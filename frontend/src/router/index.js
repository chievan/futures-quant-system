import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/strategies' },
  { path: '/strategies', name: 'Strategies', component: () => import('../views/Strategies.vue') },
  { path: '/research', name: 'Research', component: () => import('../views/Research.vue') },
  { path: '/backtest-results', name: 'BacktestResults', component: () => import('../views/BacktestResults.vue') },
  { path: '/realtime', name: 'Realtime', component: () => import('../views/Realtime.vue') },
  { path: '/positions', name: 'Positions', component: () => import('../views/Positions.vue') },
  { path: '/data-management', name: 'DataManagement', component: () => import('../views/DataManagement.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
