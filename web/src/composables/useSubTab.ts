import { ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * 서브탭 ↔ ?sub= 쿼리 동기화 (investhub Invest.vue 의 subtab 감시 패턴을 일반화).
 * 기능 지도의 [이동]·⌘K 가 이 쿼리로 들어온다. 알 수 없는 값은 무시하고 fallback 을 쓴다.
 */
export function useSubTab<T extends string>(ids: readonly T[], fallback: T, key = 'sub'): { sub: Ref<T>; set: (v: T) => void } {
  const route = useRoute()
  const router = useRouter()
  const sub = ref(fallback) as Ref<T>

  watch(
    () => route.query[key],
    (v) => {
      const s = String(v ?? '')
      if ((ids as readonly string[]).includes(s)) sub.value = s as T
    },
    { immediate: true },
  )

  function set(v: T) {
    sub.value = v
    void router.replace({ query: { ...route.query, [key]: v } })
  }
  return { sub, set }
}
