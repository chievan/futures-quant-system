<template>
  <el-menu
    :default-active="currentRoute"
    class="sidebar"
    router
    :collapse="false"
  >
    <div class="sidebar-title">交易系统</div>
    <el-menu-item index="/strategies">
      <el-icon><Setting /></el-icon>
      <span>策略管理</span>
    </el-menu-item>
    <el-menu-item index="/research">
      <el-icon><Search /></el-icon>
      <span>研究任务</span>
    </el-menu-item>
    <el-menu-item index="/backtest-results">
      <el-icon><DataAnalysis /></el-icon>
      <span>回测结果</span>
    </el-menu-item>
    <el-menu-item index="/realtime">
      <el-icon><Monitor /></el-icon>
      <span>实时盯盘</span>
    </el-menu-item>
    <el-menu-item index="/positions">
      <el-icon><Coin /></el-icon>
      <span>持仓监控</span>
    </el-menu-item>
    <el-menu-item index="/data-management">
      <el-icon><FolderOpened /></el-icon>
      <span>数据管理</span>
    </el-menu-item>
  </el-menu>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Setting, Search, DataAnalysis, Monitor, Coin, FolderOpened } from '@element-plus/icons-vue'

const route = useRoute()
const currentRoute = computed(() => route.path)
</script>

<style scoped>
.sidebar {
  width: 220px;
  height: 100vh;
  background: #fff;
  border-right: 1px solid #e6e6e6;
  overflow-y: auto;
}
.sidebar-title {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
  border-bottom: 1px solid #e6e6e6;
}
</style>
