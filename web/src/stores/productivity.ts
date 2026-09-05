import { defineStore } from 'pinia'
import { ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { runLockFree, runPriorityTx, type Step } from '@/lib/productivity'

export type Sim = 'lockfree' | 'priority'
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * 개발생산성 탭 상태. 시뮬레이션 결과는 한 번에 오지만(SSE 아님) 화면은 한 단계씩 드러낸다 —
 * 동시성 서사는 "순서"가 곧 내용이라 레거시의 연출(첫 단계 0.3초, 이후 1.2초 간격)을 그대로 둔다.
 */
export const useProductivityStore = defineStore('productivity', () => {
  const steps = ref<Record<Sim, Step[] | null>>({ lockfree: null, priority: null })
  const revealed = ref<Record<Sim, number>>({ lockfree: 0, priority: 0 })
  const error = ref<Record<Sim, string | null>>({ lockfree: null, priority: null })
  const busy = ref<'' | Sim>('')
  let token = 0

  async function run(sim: Sim) {
    const my = ++token
    busy.value = sim
    error.value[sim] = null
    steps.value[sim] = null
    revealed.value[sim] = 0
    try {
      const r = await (sim === 'lockfree' ? runLockFree() : runPriorityTx())
      if (!r.success) throw new Error(r.error || '시뮬레이션 실패')
      if (my !== token) return
      steps.value[sim] = r.steps
      for (let i = 0; i < r.steps.length; i++) {
        await sleep(i === 0 ? 300 : 1200)
        if (my !== token) return
        revealed.value[sim] = i + 1
      }
    } catch (e) {
      if (my === token) error.value[sim] = errorMessage(e)
    } finally {
      if (my === token) busy.value = ''
    }
  }

  /** 연출을 건너뛰고 전부 보이기 */
  function revealAll(sim: Sim) {
    const s = steps.value[sim]
    if (s) revealed.value[sim] = s.length
  }

  return { steps, revealed, error, busy, run, revealAll }
})
