<template>
  <div>
    <h2 style="margin-bottom: 16px;">实时盯盘</h2>

    <el-form inline>
      <el-form-item label="合约">
        <el-input v-model="symbol" placeholder="SHFE.rb2410" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :disabled="connected" @click="connect">连接</el-button>
        <el-button type="danger" :disabled="!connected" @click="disconnect">断开</el-button>
      </el-form-item>
      <el-form-item>
        <el-tag :type="connected ? 'success' : 'info'">{{ connected ? '已连接' : '未连接' }}</el-tag>
      </el-form-item>
    </el-form>

    <el-row :gutter="16">
      <el-col :span="6">
        <el-card>
          <template #header>最新价</template>
          <div style="font-size: 28px; font-weight: bold; color: #409eff;">{{ lastPrice || '-' }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>买一</template>
          <div style="font-size: 24px; color: #67c23a;">{{ bidPrice || '-' }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>卖一</template>
          <div style="font-size: 24px; color: #f56c6c;">{{ askPrice || '-' }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>成交量</template>
          <div style="font-size: 24px;">{{ volume || '-' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 16px;">
      <template #header>K 线图</template>
      <div ref="chartRef" style="height: 400px;"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

const symbol = ref('SHFE.rb2410')
const connected = ref(false)
const lastPrice = ref(null)
const bidPrice = ref(null)
const askPrice = ref(null)
const volume = ref(null)
const chartRef = ref(null)

let ws = null
let chart = null
const klineData = []

function connect() {
  if (ws) ws.close()
  ws = new WebSocket(`ws://${location.host}/ws/market/${symbol.value}`)

  ws.onopen = () => {
    connected.value = true
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'kline') {
      klineData.push(data)
      if (klineData.length > 200) klineData.shift()
      updateChart()
    } else {
      lastPrice.value = data.last_price
      bidPrice.value = data.bid_price1
      askPrice.value = data.ask_price1
      volume.value = data.volume
    }
  }

  ws.onclose = () => {
    connected.value = false
  }

  ws.onerror = () => {
    connected.value = false
  }
}

function disconnect() {
  if (ws) ws.close()
  ws = null
  connected.value = false
}

function updateChart() {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: klineData.map(d => new Date(d.datetime / 1e6).toLocaleTimeString()) },
    yAxis: { type: 'value', scale: true },
    series: [
      { type: 'candlestick', data: klineData.map(d => [d.open, d.close, d.low, d.high]) },
    ],
    dataZoom: [{ type: 'inside' }],
  })
}

onUnmounted(() => {
  disconnect()
  if (chart) chart.dispose()
})
</script>
