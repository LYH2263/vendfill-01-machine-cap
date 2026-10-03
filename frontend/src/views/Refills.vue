<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
// 新单直接带 reason；历史单仅按状态兜底，capped 仍只会显示“整机件数已满”。
function lineReason(l: any): string {
  if (l.reason) return l.reason
  const fallback: Record<string, string> = {
    need_fill: '待补', full: '满仓', overbooked: '超占', capped: '整机件数已满',
  }
  return fallback[l.status] ?? ''
}
async function run() {
  // 每次落单按点位页保存当下的上限重算，不沿用旧单总分。
  data.value = await api('/refills/run?location_id=1', { method: 'POST' })
}
onMounted(run)
</script>
<template>
  <h1>补货小票</h1>
  <p class="sub">gap = 容量 − 库存 − 在途 · 先按缺口算理想量，再按近七日销量从高到低在整机上限内分配</p>
  <button class="btn" @click="run">生成补货单</button>
  <div style="margin-top:1rem" v-if="data">
    <p class="muted" style="margin:0 0 0.5rem">
      整机补货上限：<strong>{{ data.max_fill_qty > 0 ? data.max_fill_qty + ' 件' : '不限制' }}</strong>
      · 本单合计 <strong>{{ data.total_fill }}</strong> 件
    </p>
    <div class="vf-receipt">
      <h2>*** VendFill 补货单 ***</h2>
      <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
        <span>货道 / 商品</span><span>补量</span>
      </div>
      <div class="vf-receipt-line" v-for="l in data.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small>({{ lineReason(l) }})</small>
        </span>
        <span>{{ l.fill_qty }} / 缺{{ l.gap }}</span>
      </div>
      <p style="text-align:center;margin:1rem 0 0;font-size:0.72rem;color:#6a5e48">谢谢使用 · 请核对后装机</p>
    </div>
  </div>
</template>
