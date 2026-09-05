import { onBeforeUnmount, onMounted } from 'vue'
import { useSystemStore } from '@/stores/system'

let pollers = 0
let timer: number | null = null

/** 마운트된 동안 30초 주기로 /api/health 를 갱신한다. 여러 곳에서 불러도 폴러는 하나. */
export function useHealth(intervalMs = 30_000) {
  const system = useSystemStore()
  onMounted(() => {
    pollers += 1
    if (!system.health && !system.loading) void system.refresh()
    if (!timer) timer = window.setInterval(() => { void system.refresh() }, intervalMs)
  })
  onBeforeUnmount(() => {
    pollers -= 1
    if (pollers <= 0 && timer) { clearInterval(timer); timer = null; pollers = 0 }
  })
  return system
}
