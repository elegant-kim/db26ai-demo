<script setup lang="ts">
import { Chart, ArcElement, DoughnutController, Tooltip, Legend, type ChartConfiguration } from 'chart.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

Chart.register(ArcElement, DoughnutController, Tooltip, Legend)

interface Props { labels: string[]; values: number[]; colors?: string[]; height?: string; valueFormatter?: (v: number) => string }
const props = withDefaults(defineProps<Props>(), { height: '240px' })

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
  const pal = palette()
  const colors = props.colors ?? props.labels.map((_, i) => pal[i % pal.length])
  return {
    type: 'doughnut',
    data: { labels: props.labels, datasets: [{ data: props.values, backgroundColor: colors, borderWidth: 0 }] },
    options: ({
      responsive: true, maintainAspectRatio: false, cutout: '65%',
      plugins: {
        legend: { position: 'right', labels: { color: readVar('--text-secondary', '#425466'), boxWidth: 10, padding: 12, font: { size: 12 } } },
        tooltip: { callbacks: { label: (ctx: any) => {
          const total = (ctx.dataset.data as number[]).reduce((a: number, b: number) => a + b, 0)
          const pct = total > 0 ? ((ctx.parsed as number) / total * 100).toFixed(1) : '0'
          const amount = props.valueFormatter ? ` (${props.valueFormatter(ctx.parsed as number)})` : ''
          return `${ctx.label}: ${pct}%${amount}`
        } } },
      },
    } as any),
  }
}
function render() { if (!canvasRef.value) return; if (chart) chart.destroy(); chart = new Chart(canvasRef.value, buildConfig()) }
onMounted(render)
watch(() => [props.labels, props.values], render, { deep: true })
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div :style="`height: ${height}; position: relative;`"><canvas ref="canvasRef" /></div>
</template>
