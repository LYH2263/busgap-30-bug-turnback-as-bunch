<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const savedId = ref<number | null>(null)
const error = ref('')
onMounted(async () => { rows.value = await api('/lines') })
async function save(r: any) {
  error.value = ''
  const v = r.min_turnaround_min
  const body = { min_turnaround_min: v === '' || v === null || v === undefined ? null : Number(v) }
  try {
    const updated = await api(`/lines/${r.id}`, { method: 'PATCH', body: JSON.stringify(body) })
    r.min_turnaround_min = updated.min_turnaround_min
    savedId.value = r.id
    setTimeout(() => { if (savedId.value === r.id) savedId.value = null }, 1500)
  } catch (e: any) {
    error.value = `保存失败：${e.message || e}`
  }
}
</script>
<template>
  <h1>线路</h1>
  <p class="sub">运营线路与串车 / 大间隔判定阈值 · 最小折返仅展示不参与判定</p>
  <p class="muted">业务页与检测读口未强制同参与集</p>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>计划间隔(分)</th><th>串车阈值</th><th>大间隔阈值</th><th>最小折返(分)</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.planned_headway_min }}</td><td>{{ r.bunch_threshold }}</td><td>{{ r.large_threshold }}</td>
          <td>
            <input
              class="num-input"
              type="number"
              min="0"
              step="0.5"
              v-model="r.min_turnaround_min"
              placeholder="未配置"
              @change="save(r)"
            >
            <span v-if="savedId === r.id" class="saved-hint">已保存</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="error" class="error-hint">{{ error }}</p>
  </div>
</template>
