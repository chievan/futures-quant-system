<template>
  <div>
    <h2 style="margin-bottom: 16px;">回测结果</h2>

    <el-table :data="store.tasks" v-loading="store.loading" border stripe @row-click="viewDetail">
      <el-table-column prop="task_id" label="任务 ID" width="200" show-overflow-tooltip />
      <el-table-column prop="symbol" label="合约" />
      <el-table-column prop="params" label="参数" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'completed' ? 'success' : 'warning'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_return" label="总收益" width="100">
        <template #default="{ row }">{{ formatPct(row.total_return) }}</template>
      </el-table-column>
      <el-table-column prop="sharpe_ratio" label="夏普" width="80" />
      <el-table-column prop="max_drawdown" label="最大回撤" width="100">
        <template #default="{ row }">{{ formatPct(row.max_drawdown) }}</template>
      </el-table-column>
      <el-table-column prop="win_rate" label="胜率" width="80">
        <template #default="{ row }">{{ formatPct(row.win_rate) }}</template>
      </el-table-column>
      <el-table-column prop="total_trades" label="交易次数" width="90" />
      <el-table-column prop="created_at" label="创建时间" width="170" />
    </el-table>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="回测详情" width="800px">
      <template v-if="detail">
        <h3>基本信息</h3>
        <el-descriptions :column="2" border style="margin-bottom: 16px;">
          <el-descriptions-item label="任务 ID">{{ detail.task_id }}</el-descriptions-item>
          <el-descriptions-item label="合约">{{ detail.symbol }}</el-descriptions-item>
          <el-descriptions-item label="参数">{{ detail.params }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
          <el-descriptions-item label="总收益">{{ formatPct(detail.total_return) }}</el-descriptions-item>
          <el-descriptions-item label="夏普比率">{{ detail.sharpe_ratio }}</el-descriptions-item>
          <el-descriptions-item label="最大回撤">{{ formatPct(detail.max_drawdown) }}</el-descriptions-item>
          <el-descriptions-item label="胜率">{{ formatPct(detail.win_rate) }}</el-descriptions-item>
          <el-descriptions-item label="盈亏比">{{ detail.profit_factor }}</el-descriptions-item>
          <el-descriptions-item label="交易次数">{{ detail.total_trades }}</el-descriptions-item>
        </el-descriptions>

        <h3 v-if="equityData.length">权益曲线</h3>
        <div ref="chartRef" style="height: 300px; margin-bottom: 16px;"></div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useResearchStore } from '../stores/research'
import { researchApi } from '../api/research'
import * as echarts from 'echarts'

const store = useResearchStore()
const detailVisible = ref(false)
const detail = ref(null)
const chartRef = ref(null)
const equityData = ref([])

onMounted(() => store.fetchTasks())

function formatPct(v) {
  return v != null ? (v * 100).toFixed(2) + '%' : '-'
}

async function viewDetail(row) {
  try {
    const data = await researchApi.getTask(row.task_id)
    detail.value = data
    detailVisible.value = true

    if (data.equity_curve) {
      equityData.value = JSON.parse(data.equity_curve)
      await nextTick()
      renderChart()
    }
  } catch (e) {
    ElMessage.error('加载详情失败')
  }
}

function renderChart() {
  if (!chartRef.value || !equityData.value.length) return
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: equityData.value.map(d => d.t), axisLabel: { rotate: 45 } },
    yAxis: [{ type: 'value', name: '价格' }, { type: 'value', name: 'MA' }],
    series: [
      { type: 'line', name: 'Close', data: equityData.value.map(d => d.close), smooth: true },
      { type: 'line', name: 'Fast MA', data: equityData.value.map(d => d.fast_ma), smooth: true, yAxisIndex: 1 },
      { type: 'line', name: 'Slow MA', data: equityData.value.map(d => d.slow_ma), smooth: true, yAxisIndex: 1 },
    ],
    dataZoom: [{ type: 'inside' }],
  })
}
</script>
