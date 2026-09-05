<script setup lang="ts">
import { CategoryScale, Chart, Filler, Legend, LinearScale, LineController, LineElement, PointElement, Tooltip, type ChartConfiguration } from 'chart.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

Chart.register(CategoryScale, LinearScale, LineElement, LineController, PointElement, Tooltip, Legend, Filler)

interface Dataset { label: string; data: (number | null)[]; color?: string; width?: number }
interface Props { labels: string[]; datasets: Dataset[]; height?: string; dualAxis?: boolean; showPoints?: boolean }
const props = withDefaults(defineProps<Props>(), { height: '240px', dualAxis: false, showPoints: false })

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
    type: 'line',
    data: {
      labels: props.labels,
      datasets: props.datasets.map((d, i) => ({
        label: d.label, data: d.data, borderColor: d.color ?? pal[i % pal.length], backgroundColor: 'transparent',
        borderWidth: d.width ?? 2, pointRadius: props.showPoints ? 2.5 : 0, pointHoverRadius: 4, tension: 0.2, spanGaps: true,
        yAxisID: props.dualAxis && i === 1 ? 'y1' : 'y',
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      scales: {
        x: { ticks: { color: text, maxTicksLimit: 8, autoSkip: true, maxRotation: 0 }, grid: { color: grid } },
        y: { ticks: { color: text }, grid: { color: grid } },
        ...(props.dualAxis ? { y1: { position: 'right' as const, ticks: { color: text }, grid: { display: false } } } : {}),
      },
      plugins: { legend: { position: 'top', align: 'end', labels: { color: text, boxWidth: 10, font: { size: 11 } } } },
    },
  }
}
function render() { if (!canvasRef.value) return; if (chart) chart.destroy(); chart = new Chart(canvasRef.value, buildConfig()) }
onMounted(render)
watch(() => [props.labels, props.datasets, props.dualAxis], render, { deep: true })
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div :style="`height: ${height}; position: relative;`"><canvas ref="canvasRef" /></div>
</template>
