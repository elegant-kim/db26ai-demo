<script setup lang="ts">
import { Chart, BarElement, BarController, CategoryScale, LinearScale, Tooltip, Legend, type ChartConfiguration } from 'chart.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

Chart.register(BarElement, BarController, CategoryScale, LinearScale, Tooltip, Legend)

interface Props { labels: string[]; datasets: { label: string; data: number[]; color?: string | string[] }[]; height?: string; horizontal?: boolean; stacked?: boolean; hideLegend?: boolean }
const props = withDefaults(defineProps<Props>(), { height: '240px', horizontal: false, stacked: false })

function readVar(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}
function palette(): string[] {
  // 첫 색 = 브랜드 액센트(테마에 따라 값이 다르므로 렌더 시점에 읽는다)
  return [readVar('--accent-primary', '#C74634'), '#0a84ff', '#00a82d', '#ff9500', '#7c75ff', '#34c759', '#ffcc00', '#af52de', '#5ac8fa']
}

const canvasRef = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

function buildConfig(): ChartConfiguration {
  const text = readVar('--text-secondary', '#425466')
  const grid = readVar('--border-default', '#eef1f6')
  const pal = palette()
  return {
    type: 'bar',
    data: {
      labels: props.labels,
      datasets: props.datasets.map((d, i) => ({ label: d.label, data: d.data, backgroundColor: d.color ?? (i === 0 ? pal[0] : '#cdd2dd'), borderRadius: 4, barThickness: 'flex' })),
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: props.horizontal ? 'y' : 'x',
      scales: {
        x: { stacked: props.stacked, ticks: { color: text, autoSkip: true, maxRotation: 0 }, grid: { color: grid } },
        y: { stacked: props.stacked, ticks: { color: text, callback: (v) => new Intl.NumberFormat('ko-KR').format(Number(v)) }, grid: { color: grid } },
      },
      plugins: { legend: { display: !props.hideLegend, position: 'top', align: 'end', labels: { color: text, boxWidth: 10, font: { size: 12 } } } },
    },
  }
}
function render() { if (!canvasRef.value) return; if (chart) chart.destroy(); chart = new Chart(canvasRef.value, buildConfig()) }
onMounted(render)
watch(() => [props.labels, props.datasets], render, { deep: true })
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div :style="`height: ${height}; position: relative;`"><canvas ref="canvasRef" /></div>
</template>
