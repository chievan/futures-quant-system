<template>
  <div>
    <h2 style="margin-bottom: 16px;">持仓监控分析</h2>

    <el-tabs v-model="activeTab">
      <!-- Real-time positions -->
      <el-tab-pane label="实时持仓" name="current">
        <el-button type="primary" @click="fetchCurrent" style="margin-bottom: 12px;">刷新</el-button>
        <el-table :data="currentPositions" border stripe style="margin-bottom: 16px;">
          <el-table-column prop="symbol" label="合约" />
          <el-table-column prop="direction" label="方向">
            <template #default="{ row }">
              <el-tag :type="row.direction === 'long' ? 'danger' : 'success'">
                {{ row.direction === 'long' ? '多' : '空' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="volume" label="数量" />
          <el-table-column prop="avg_price" label="开仓均价" />
          <el-table-column prop="last_price" label="最新价" />
          <el-table-column prop="float_pnl" label="浮动盈亏">
            <template #default="{ row }">
              <span :style="{ color: row.float_pnl >= 0 ? '#67c23a' : '#f56c6c' }">
                {{ row.float_pnl?.toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="margin" label="保证金" />
          <el-table-column label="保证金占比">
            <template #default="{ row }">
              {{ getMarginRatio(row.margin) }}
            </template>
          </el-table-column>
        </el-table>

        <el-card v-if="currentPositions.length && pieChartData.length">
          <template #header>各品种保证金占比</template>
          <div ref="pieChartRef" style="height: 300px;"></div>
        </el-card>
      </el-tab-pane>

      <!-- History (by task) -->
      <el-tab-pane label="历史持仓" name="history">
        <el-form inline>
          <el-form-item label="回测任务 ID">
            <el-input v-model="historyTaskId" placeholder="输入任务 ID" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchHistory">查询</el-button>
          </el-form-item>
        </el-form>

        <el-table :data="historyItems" border stripe v-if="historyItems.length">
          <el-table-column prop="timestamp" label="时间" width="180" />
          <el-table-column prop="symbol" label="合约" />
          <el-table-column prop="direction" label="方向" />
          <el-table-column prop="volume" label="数量" />
          <el-table-column prop="price" label="价格" />
          <el-table-column prop="pnl" label="盈亏">
            <template #default="{ row }">
              <span :style="{ color: row.pnl >= 0 ? '#67c23a' : '#f56c6c' }">{{ row.pnl?.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="is_rollover" label="移仓">
            <template #default="{ row }">{{ row.is_rollover ? '是' : '否' }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else-if="searched" description="暂无数据" />
      </el-tab-pane>

      <!-- Analysis -->
      <el-tab-pane label="盈亏分析" name="analysis">
        <el-form inline>
          <el-form-item label="回测任务 ID">
            <el-input v-model="analysisTaskId" placeholder="输入任务 ID" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchAnalysis">分析</el-button>
          </el-form-item>
        </el-form>

        <el-descriptions :column="2" border v-if="analysisData.total_pnl != null" style="margin-top: 12px;">
          <el-descriptions-item label="累计盈亏">
            <span :style="{ color: analysisData.total_pnl >= 0 ? '#67c23a' : '#f56c6c', fontWeight: 'bold' }">
              {{ analysisData.total_pnl }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="已实现盈亏">{{ analysisData.realized_pnl }}</el-descriptions-item>
          <el-descriptions-item label="浮动盈亏">{{ analysisData.floating_pnl }}</el-descriptions-item>
          <el-descriptions-item label="胜率">{{ formatPct(analysisData.win_rate) }}</el-descriptions-item>
          <el-descriptions-item label="盈亏比">{{ analysisData.profit_factor }}</el-descriptions-item>
          <el-descriptions-item label="最大回撤">{{ formatPct(analysisData.max_drawdown) }}</el-descriptions-item>
          <el-descriptions-item label="总交易次数">{{ analysisData.total_trades }}</el-descriptions-item>
          <el-descriptions-item label="平均盈利">{{ analysisData.avg_win }}</el-descriptions-item>
          <el-descriptions-item label="平均亏损">{{ analysisData.avg_loss }}</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { positionsApi } from '../api/positions'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const activeTab = ref('current')

const currentPositions = ref([])
const totalMargin = computed(() => currentPositions.value.reduce((s, p) => s + (p.margin || 0), 0))
const pieChartData = computed(() => currentPositions.value.map(p => ({
  name: p.symbol,
  value: p.margin || 0,
})))
const pieChartRef = ref(null)
let pieChart = null

function getMarginRatio(margin) {
  if (!totalMargin.value) return '0%'
  return ((margin / totalMargin.value) * 100).toFixed(1) + '%'
}

async function fetchCurrent() {
  try {
    const data = await positionsApi.getCurrent()
    currentPositions.value = data.positions || []
    ElMessage.success('已刷新')
    await nextTick()
    renderPieChart()
  } catch (e) {
    ElMessage.error('获取持仓失败')
  }
}

function renderPieChart() {
  if (!pieChartRef.value || !pieChartData.value.length) return
  if (!pieChart) pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: pieChartData.value,
      label: { formatter: '{b}\n{d}%' },
    }],
  })
}

const historyTaskId = ref('')
const historyItems = ref([])
const searched = ref(false)
async function fetchHistory() {
  try {
    const data = await positionsApi.getHistory(historyTaskId.value)
    historyItems.value = data.items || []
    searched.value = true
  } catch (e) {
    ElMessage.error('获取历史持仓失败')
  }
}

const analysisTaskId = ref('')
const analysisData = ref({})
async function fetchAnalysis() {
  try {
    analysisData.value = await positionsApi.getAnalysis(analysisTaskId.value)
  } catch (e) {
    ElMessage.error('分析失败')
  }
}

function formatPct(v) {
  return v != null ? (v * 100).toFixed(2) + '%' : '-'
}
</script>
