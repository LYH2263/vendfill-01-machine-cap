<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>({})
onMounted(async () => {
  // 与补货单、满仓页读取同一张落库订单，截断口径完全一致。
  s.value = await api('/refills/summary?location_id=1')
})
</script>
<template>
  <h1>汇总</h1>
  <p class="sub">本点位补货建议合计（与补货单逐行相加一致）</p>
  <div class="card grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem">
    <div><div class="muted">建议补货总量</div><div class="stat">{{ s.total_fill }}</div></div>
    <div><div class="muted">整机补货上限</div><div class="stat">{{ s.max_fill_qty > 0 ? s.max_fill_qty : '不限' }}</div></div>
    <div><div class="muted">待补货道</div><div class="stat">{{ s.need_fill_count }}</div></div>
    <div><div class="muted">满仓货道</div><div class="stat">{{ s.full_count }}</div></div>
    <div><div class="muted">超占货道</div><div class="stat">{{ s.overbooked_count }}</div></div>
    <div><div class="muted">整机件数已满</div><div class="stat">{{ s.capped_count ?? 0 }}</div></div>
  </div>
</template>
