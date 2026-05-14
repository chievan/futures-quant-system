<template>
  <div>
    <h2 style="margin-bottom: 16px;">策略管理</h2>
    <el-button type="primary" @click="dialogVisible = true" style="margin-bottom: 16px;">
      新建策略
    </el-button>

    <el-table :data="store.strategies" v-loading="store.loading" border stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="策略名称" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column prop="updated_at" label="更新时间" width="180" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="新建策略" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="策略名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
        <el-form-item label="配置 JSON" required>
          <el-input v-model="form.config_json" type="textarea" rows="6" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useStrategiesStore } from '../stores/strategies'

const store = useStrategiesStore()
const dialogVisible = ref(false)
const form = ref({ name: '', description: '', config_json: '{"type": "dual_ma", "fast": 10, "slow": 30}' })

onMounted(() => store.fetchAll())

async function handleCreate() {
  await store.create({ ...form.value })
  dialogVisible.value = false
  form.value = { name: '', description: '', config_json: '{"type": "dual_ma", "fast": 10, "slow": 30}' }
  ElMessage.success('策略已创建')
}

async function handleDelete(id) {
  await ElMessageBox.confirm('确定删除此策略？')
  await store.remove(id)
  ElMessage.success('已删除')
}
</script>
