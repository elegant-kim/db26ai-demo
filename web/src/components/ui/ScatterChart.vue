<script setup lang="ts">
/** 산점도 — 벡터 2D 시각화(쿼리 중심 투영). LineChart 와 같은 토큰 읽기 규칙. */
import { Chart, Legend, LinearScale, PointElement, ScatterController, Tooltip, type ChartConfiguration } from 'chart.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

Chart.register(LinearScale, PointElement, ScatterController, Tooltip, Legend)

export interface ScatterPoint { x: number; y: number; meta?: string }
interface Dataset { label: string; data: ScatterPoint[]; color?: string; radius?: number; pointStyle?: 'circle' | 'rectRot' | 'triangle' }
interface Props { datasets: Dataset[]; xTitle?: string; yTitle?: string; height?: string }
const props = withDefaults(defineProps<Props>(), { height: '320px' })

function readVar(name: string, fallback: string): string { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback }
const canvasRef = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

function buildConfig(): ChartConfiguration {
  const text = readVar('--text-secondary', '#425466')
  const grid = readVar('--border-default', '#eef1f6')
  return {
    type: 'scatter',
    data: {
      datasets: props.datasets.map((d) => ({
        label: d.label, data: d.data as any, backgroundColor: d.color ?? readVar('--accent-primary', '#C74634'), borderColor: d.color ?? readVar('--accent-primary', '#C74634'),
        pointRadius: d.radius ?? 4, pointHoverRadius: (d.radius ?? 4) + 2, pointStyle: d.pointStyle ?? 'circle',
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: text, boxWidth: 10, font: { size: 11 } } },
        tooltip: { callbacks: { label: (ctx: any) => ctx.raw?.meta ?? `${ctx.dataset.label} (${Number(ctx.raw?.x).toFixed(3)}, ${Number(ctx.raw?.y).toFixed(3)})` } },
      },
      scales: {
        x: { title: { display: !!props.xTitle, text: props.xTitle, color: text, font: { size: 11 } }, ticks: { color: text }, grid: { color: grid } },
        y: { title: { display: !!props.yTitle, text: props.yTitle, color: text, font: { size: 11 } }, ticks: { color: text }, grid: { color: grid } },
      },
    },
  }
}
function render() { if (!canvasRef.value) return; if (chart) chart.destroy(); chart = new Chart(canvasRef.value, buildConfig()) }
onMounted(render)
watch(() => props.datasets, render, { deep: true })
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div :style="`height: ${height}; position: relative;`"><canvas ref="canvasRef" /></div>
</template>
