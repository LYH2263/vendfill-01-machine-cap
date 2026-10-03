<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const drafts = reactive<Record<number, number | string>>({})
const errors = reactive<Record<number, string>>({})
const savedFlags = reactive<Record<number, boolean>>({})

async function load() {
  rows.value = await api('/locations')
  for (const r of rows.value) drafts[r.id] = r.max_fill_total ?? 0
}

async function save(r: any) {
  errors[r.id] = ''
  savedFlags[r.id] = false
  const raw = drafts[r.id]
  const v = Number(raw)
  if (raw === '' || raw === null || raw === undefined || !Number.isInteger(v) || v < 0) {
    // 非法输入（含负数）：拒绝保存并回退到改前的已保存值
    drafts[r.id] = r.max_fill_total
    errors[r.id] = Number.isInteger(v) && v < 0 ? '整机补货件数上限不能为负数' : '请输入非负整数'
    return
  }
  try {
    const updated = await api(`/locations/${r.id}`, {
      method: 'PUT',
      body: JSON.stringify({ max_fill_total: v }),
    })
    r.max_fill_total = updated.max_fill_total
    drafts[r.id] = updated.max_fill_total
    savedFlags[r.id] = true
  } catch (e: any) {
    // 保存被后端拒绝：回退到改前的已保存值，不出现半成功状态
    drafts[r.id] = r.max_fill_total
    let msg = '保存失败，已保持原值'
    try {
      const detail = JSON.parse(e.message).detail
      if (typeof detail === 'string') msg = detail
    } catch { /* keep default */ }
    errors[r.id] = msg
  }
}

onMounted(load)
</script>
<template>
  <h1>点位 / 机位</h1>
  <p class="sub">左侧机位选择器对应的点位档案 · 整机补货件数上限（0 = 不限制）</p>
  <div class="vf-site-rail" style="flex-direction:row;flex-wrap:wrap;border:none;background:transparent;padding:0;gap:0.5rem;margin-bottom:1rem">
    <div v-for="r in rows" :key="r.id ?? JSON.stringify(r)" class="vf-site-btn" style="min-width:140px">
      <strong style="display:block;color:var(--vf-led)">{{ r.code }}</strong>
      <span style="font-size:0.7rem">{{ r.name }}</span>
    </div>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>地址</th><th>整机补货上限（件）</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.address }}</td>
          <td>
            <input
              type="number"
              min="0"
              step="1"
              style="width:6rem"
              v-model.number="drafts[r.id]"
              @keyup.enter="save(r)"
            />
            <small class="muted" style="margin-left:0.4rem">0 = 不限</small>
          </td>
          <td>
            <button class="btn" @click="save(r)">保存</button>
            <span v-if="savedFlags[r.id]" style="color:#3f7a3f;font-size:0.75rem;margin-left:0.4rem">已保存</span>
            <span v-if="errors[r.id]" style="color:#a33;font-size:0.75rem;margin-left:0.4rem">{{ errors[r.id] }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
