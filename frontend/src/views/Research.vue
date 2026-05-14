<template>
  <div>
    <h2 style="margin-bottom: 16px;">研究任务</h2>

    <el-card style="margin-bottom: 16px;">
      <template #header>提交单次回测</template>
      <el-form :model="backtestForm" label-width="120px" inline>
        <el-form-item label="策略 ID">
          <el-input-number v-model="backtestForm.strategy_id" :min="1" />
        </el-form-item>
        <el-form-item label="合约">
          <el-input v-model="backtestForm.symbol" placeholder="KQ.m@SHFE.rb" />
        </el-form-item>
        <el-form-item label="参数 (JSON)">
          <el-input v-model="backtestForm.params" style="width: 200px;" />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-input v-model="backtestForm.start_date" placeholder="2024-01-01" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-input v-model="backtestForm.end_date" placeholder="2024-12-31" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitSingle">提交回测</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-bottom: 16px;">
      <template #header>参数搜索 (双均线)</template>
      <el-form :model="searchForm" label-width="120px" inline>
        <el-form-item label="合约">
          <el-input v-model="searchForm.symbol" placeholder="KQ.m@SHFE.rb" />
        </el-form-item>
        <el-form-item label="快线范围">
          <el-input v-model="searchForm.fast_range" placeholder="5-20" style="width: 100px;" />
        </el-form-item>
        <el-form-item label="慢线范围">
          <el-input v-model="searchForm.slow_range" placeholder="20-60" style="width: 100px;" />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-input v-model="searchForm.start_date" placeholder="2024-01-01" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-input v-model="searchForm.end_date" placeholder="2024-12-31" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitSearch">提交搜索</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header>任务列表</template>
      <el-table :data="store.tasks" v-loading="store.loading" border stripe>
        <el-table-column prop="task_id" label="任务 ID" width="200" show-overflow-tooltip />
        <el-table-column prop="symbol" label="合约" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_return" label="总收益" width="100">
          <template #default="{ row }">
            {{ row.total_return != null ? (row.total_return * 100).toFixed(2) + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="sharpe_ratio" label="夏普" width="80" />
        <el-table-column prop="max_drawdown" label="最大回撤" width="100">
          <template #default="{ row }">
            {{ row.max_drawdown != null ? (row.max_drawdown * 100).toFixed(2) + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useResearchStore } from '../stores/research'

const store = useResearchStore()
const backtestForm = reactive({
  strategy_id: 1,
  symbol: 'KQ.m@SHFE.rb',
  params: '{"fast": 10, "slow": 30}',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
})
const searchForm = reactive({
  symbol: 'KQ.m@SHFE.rb',
  fast_range: '5-20',
  slow_range: '20-60',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
})

onMounted(() => store.fetchTasks())

function statusType(s) {
  return { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }[s] || 'info'
}

async function submitSingle() {
  const payload = {
    ...backtestForm,
    params: JSON.parse(backtestForm.params),
  }
  await store.submitBacktest(payload)
  ElMessage.success('回测任务已提交')
  await store.fetchTasks()
}

async function submitSearch() {
  const [fmin, fmax] = searchForm.fast_range.split('-').map(Number)
  const [smin, smax] = searchForm.slow_range.split('-').map(Number)
  const payload = {
    strategy_type: 'dual_ma',
    param_ranges: { fast_min: fmin, fast_max: fmax, fast_step: 1, slow_min: smin, slow_max: smax, slow_step: 5 },
    symbol: searchForm.symbol,
    start_date: searchForm.start_date,
    end_date: searchForm.end_date,
  }
  await store.submitSearch(payload)
  ElMessage.success('参数搜索任务已提交')
  await store.fetchTasks()
}
</script>
