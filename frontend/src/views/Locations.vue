<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
// 每点位的输入草稿与报错；已保存值始终以服务端为准
const drafts = ref<Record<number, string>>({})
const errors = ref<Record<number, string>>({})
const saving = ref<Record<number, boolean>>({})

async function load() {
  rows.value = await api('/locations')
  drafts.value = {}
  errors.value = {}
  for (const r of rows.value) drafts.value[r.id] = String(r.max_fill_qty ?? 0)
}
onMounted(load)

async function save(r: any) {
  const raw = (drafts.value[r.id] ?? '').trim()
  const val = Number(raw)
  // 前端先拦截：负数/非整数不发请求，点位页保持改前值，补货单与汇总完全不受影响。
  if (raw === '' || !Number.isInteger(val)) {
    errors.value[r.id] = '请输入整数（0 表示不限制）'
    drafts.value[r.id] = String(r.max_fill_qty)
    return
  }
  if (val < 0) {
    errors.value[r.id] = '整机补货上限不能为负数'
    drafts.value[r.id] = String(r.max_fill_qty) // 回滚到改前，杜绝“页上新值、单上旧分”
    return
  }
  errors.value[r.id] = ''
  saving.value[r.id] = true
  try {
    const updated = await api(`/locations/${r.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ max_fill_qty: val }),
    })
    r.max_fill_qty = updated.max_fill_qty
    drafts.value[r.id] = String(updated.max_fill_qty)
  } catch (e: any) {
    // 保存失败：以服务端旧值为准，页面不接受半成功的新上限。
    errors.value[r.id] = '保存失败：' + (e?.message || '未知错误')
    drafts.value[r.id] = String(r.max_fill_qty)
  } finally {
    saving.value[r.id] = false
  }
}
</script>
<template>
  <h1>点位 / 机位</h1>
  <p class="sub">左侧机位选择器对应的点位档案 · 登记本机一次补货允许的最大总件数（0 = 不限制，按缺口满补）</p>
  <div class="vf-site-rail" style="flex-direction:row;flex-wrap:wrap;border:none;background:transparent;padding:0;gap:0.5rem;margin-bottom:1rem">
    <div v-for="r in rows" :key="r.id ?? JSON.stringify(r)" class="vf-site-btn" style="min-width:140px">
      <strong style="display:block;color:var(--vf-led)">{{ r.code }}</strong>
      <span style="font-size:0.7rem">{{ r.name }}</span>
    </div>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>地址</th><th style="width:220px">整机补货上限(件)</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.address }}</td>
          <td>
            <input
              v-model="drafts[r.id]"
              type="number"
              min="0"
              step="1"
              style="width:110px"
              :aria-label="`${r.code} 整机补货上限`"
            />
            <div v-if="errors[r.id]" style="color:#c0392b;font-size:0.72rem;margin-top:2px">{{ errors[r.id] }}</div>
          </td>
          <td><button class="btn" :disabled="saving[r.id]" @click="save(r)">保存</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
