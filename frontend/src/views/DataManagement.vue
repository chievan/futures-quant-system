<template>
  <div>
    <h2 style="margin-bottom: 16px;">数据管理</h2>

    <!-- Overview -->
    <el-row :gutter="16" style="margin-bottom: 16px;">
      <el-col :span="6">
        <el-card>
          <template #header>合约数量</template>
          <div style="font-size: 24px; font-weight: bold;">{{ overview.contract_count }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>数据点数</template>
          <div style="font-size: 24px; font-weight: bold;">{{ overview.total_points }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>最早日期</template>
          <div style="font-size: 16px;">{{ overview.earliest_date || '-' }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>最晚日期</template>
          <div style="font-size: 16px;">{{ overview.latest_date || '-' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Download form -->
    <el-card style="margin-bottom: 16px;">
      <template #header>手动下载数据</template>
      <el-form :model="downloadForm" label-width="100px" inline>
        <el-form-item label="合约" required>
          <el-input v-model="downloadForm.symbol" placeholder="KQ.m@SHFE.rb" />
        </el-form-item>
        <el-form-item label="粒度" required>
          <el-select v-model="downloadForm.granularity">
            <el-option label="1分钟" value="1min" />
            <el-option label="5分钟" value="5min" />
            <el-option label="15分钟" value="15min" />
            <el-option label="30分钟" value="30min" />
            <el-option label="60分钟" value="60min" />
            <el-option label="日线" value="day" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期" required>
          <el-input v-model="downloadForm.start_date" placeholder="2024-01-01" />
        </el-form-item>
        <el-form-item label="结束日期" required>
          <el-input v-model="downloadForm.end_date" placeholder="2024-12-31" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitDownload" :loading="downloading">下载</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Data table -->
    <el-card style="margin-bottom: 16px;">
      <template #header>数据列表</template>
      <el-table :data="contracts" border stripe v-loading="loading">
        <el-table-column prop="symbol" label="合约" />
        <el-table-column prop="granularity" label="粒度" />
        <el-table-column prop="start_date" label="开始日期" />
        <el-table-column prop="end_date" label="结束日期" />
        <el-table-column prop="total_bars" label="数据条数" />
        <el-table-column prop="quality" label="质量">
          <template #default="{ row }">
            <el-tag :type="qualityTag(row.quality)">{{ row.quality }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="viewInfo(row.symbol)">详情</el-button>
            <el-button size="small" type="danger" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Download tasks -->
    <el-card>
      <template #header>下载任务队列</template>
      <el-table :data="downloadTasks" border stripe>
        <el-table-column prop="task_id" label="任务 ID" width="200" show-overflow-tooltip />
        <el-table-column prop="symbol" label="合约" />
        <el-table-column prop="granularity" label="粒度" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'warning'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" />
          </template>
        </el-table-column>
        <el-table-column prop="total_bars" label="数据条数" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
      </el-table>
    </el-card>

    <!-- Info dialog -->
    <el-dialog v-model="infoVisible" title="合约详情" width="600px">
      <el-table :data="infoData" border v-if="infoData.length">
        <el-table-column prop="granularity" label="粒度" />
        <el-table-column prop="start_date" label="开始日期" />
        <el-table-column prop="end_date" label="结束日期" />
        <el-table-column prop="total_bars" label="数据条数" />
        <el-table-column prop="quality" label="质量" />
      </el-table>
      <el-empty v-else description="无数据" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { dataApi } from '../api/data'

const contracts = ref([])
const downloadTasks = ref([])
const loading = ref(false)
const downloading = ref(false)
const infoVisible = ref(false)
const infoData = ref([])
const overview = reactive({ contract_count: 0, total_points: 0, earliest_date: null, latest_date: null })

const downloadForm = reactive({
  symbol: 'KQ.m@SHFE.rb',
  granularity: '1min',
  start_date: '',
  end_date: '',
})

onMounted(() => {
  fetchContracts()
  fetchTasks()
})

async function fetchContracts() {
  loading.value = true
  try {
    const data = await dataApi.getContracts()
    contracts.value = data.contracts || []
    overview.contract_count = contracts.value.length
    overview.total_points = contracts.value.reduce((s, c) => s + (c.total_bars || 0), 0)
    const dates = contracts.value.filter(c => c.start_date).map(c => c.start_date)
    if (dates.length) {
      overview.earliest_date = Math.min(...dates.map(d => new Date(d).getTime()))
      overview.latest_date = Math.max(...contracts.value.map(c => new Date(c.end_date).getTime()))
      overview.earliest_date = new Date(overview.earliest_date).toISOString().split('T')[0]
      overview.latest_date = new Date(overview.latest_date).toISOString().split('T')[0]
    }
  } finally {
    loading.value = false
  }
}

async function fetchTasks() {
  try {
    const data = await dataApi.getTasks()
    downloadTasks.value = data.tasks || []
  } catch (e) {
    // ignore
  }
}

async function submitDownload() {
  if (!downloadForm.symbol || !downloadForm.start_date || !downloadForm.end_date) {
    ElMessage.warning('请填写完整信息')
    return
  }
  downloading.value = true
  try {
    await dataApi.download({ ...downloadForm })
    ElMessage.success('下载任务已提交')
    setTimeout(fetchTasks, 1000)
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    downloading.value = false
  }
}

async function viewInfo(symbol) {
  try {
    const data = await dataApi.getInfo(symbol)
    infoData.value = data.contracts || []
    infoVisible.value = true
  } catch (e) {
    ElMessage.error('获取详情失败')
  }
}

async function confirmDelete(row) {
  await ElMessageBox.confirm(`确定删除 ${row.symbol} ${row.granularity} 的数据？`)
  try {
    await dataApi.deleteData({
      symbol: row.symbol,
      granularity: row.granularity,
      start_date: row.start_date,
      end_date: row.end_date,
    })
    ElMessage.success('已删除')
    await fetchContracts()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

function qualityTag(q) {
  return { green: 'success', yellow: 'warning', red: 'danger' }[q] || 'info'
}
</script>
