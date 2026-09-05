/** 시뮬레이션·파이프라인의 한 단계 — 백엔드 steps[] 원소 (productivity·duality ETag 공통) */
export interface Step {
  description: string
  sql?: string | null
  success: boolean
  /** duality ETag 시뮬레이션만 — 단계에서 손에 쥔 ETag */
  etag?: string | null
}
