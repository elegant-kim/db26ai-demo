import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getEmbeddingConfig, getHealth, getProviders } from '@/lib/system'
import { errorMessage } from '@/lib/api'
import type { EmbeddingConfig, Health, LlmProvider } from '@/lib/types/system'

export interface ToastItem { id: number; message: string; type: 'info' | 'success' | 'error' | 'warn' }

/** 앱 전역: /api/health 스냅샷, LLM 제공자, 임베딩 설정, 토스트 */
export const useSystemStore = defineStore('system', () => {
  const health = ref<Health | null>(null)
  const providers = ref<LlmProvider[]>([])
  const embedding = ref<EmbeddingConfig | null>(null)
  const loading = ref(false)
  const lastError = ref<string | null>(null)
  const fetchedAt = ref<number | null>(null)

  async function refresh() {
    loading.value = true
    try {
      const [h, p, e] = await Promise.all([
        getHealth(),
        getProviders().catch(() => [] as LlmProvider[]),
        getEmbeddingConfig().catch(() => null),
      ])
      health.value = h
      providers.value = p
      embedding.value = e
      lastError.value = null
      fetchedAt.value = Date.now()
    } catch (err) {
      lastError.value = errorMessage(err, '서버에 연결할 수 없습니다.')
      health.value = null
    } finally {
      loading.value = false
    }
  }

  const dbOk = computed(() => health.value?.database_connected === true)
  const llmModel = computed(() => {
    const id = health.value?.llm_provider
    const p = providers.value.find((x) => x.id === id || x.provider === id || x.name === id)
    return (p?.model as string | undefined) || id || '—'
  })
  const embeddingModel = computed(() => embedding.value?.model ?? health.value?.embedding_model ?? '—')
  const embeddingSource = computed(() => embedding.value?.source ?? health.value?.embedding_source ?? '—')
  /** 헤더 칩용 짧은 라벨 — 1440px 에서 헤더가 넘치지 않도록 접두사(MULTILINGUAL_)를 뗀다. 전체 이름은 호버 카드에. */
  const embeddingLabel = computed(() => {
    const short = embeddingModel.value.replace(/^MULTILINGUAL_/i, '')
    return `${embeddingSource.value === 'database' ? 'ONNX' : 'API'} · ${short}`
  })

  // ── 토스트 (성공 알림 전용 — 오류는 화면 안에 남긴다, 06 문서 §6.3) ──
  const toasts = ref<ToastItem[]>([])
  let seq = 0
  function toast(message: string, type: ToastItem['type'] = 'info', ms = 3200) {
    const id = ++seq
    toasts.value.push({ id, message, type })
    setTimeout(() => { toasts.value = toasts.value.filter((t) => t.id !== id) }, ms)
  }

  return { health, providers, embedding, loading, lastError, fetchedAt, refresh, dbOk, llmModel, embeddingModel, embeddingSource, embeddingLabel, toasts, toast }
})
