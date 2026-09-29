import { api } from './api'

/**
 * 장표(PPT/PDF) 연동 — 정본은 Python (app/slides.py 카탈로그 · app/feature_registry.py 의 `slides` 앵커). 2026-09-29 P5.
 * 규칙: docs/slides/README.md. 앱은 쪽 번호가 아니라 꼬리표(`VS-12`)로 장표를 가리킨다.
 */
export interface Deck {
  deck: string; title: string
  pages: number | null                 // pdf 모드(변환 전)는 null
  mode: 'images' | 'pdf'
  code: string | null                  // 덱 코드(꼬리표 접두어)
  tags: Record<string, number>         // 꼬리표 → 쪽(1부터)
  page_tags: (string | null)[]         // 쪽 순서대로 그 쪽의 꼬리표
  page_text: string[]                  // 쪽별 텍스트 앞부분 — ⌘K 검색용
  image_base: string | null            // `/slides/out/<deck>/`
  thumb: string | null
  pdf: string | null                   // `/slides/src/<deck>.pdf`
  generated_at: string | null
}
export interface SlideAnchor { tag: string; feature: string; tab: string; tab_label: string; path: string; deck: string; deck_title: string; page: number }
export interface UnresolvedAnchor { tag: string; feature: string; tab: string; tab_label: string; path: string }
export interface SlidesCatalog { success: boolean; available: boolean; decks: Deck[]; anchors: SlideAnchor[]; unresolved: UnresolvedAnchor[]; slides_dir: string }

export const getSlides = () => api.get<SlidesCatalog>('/api/guide/slides').then((r) => r.data)

export const TAG_RE = /^[A-Z]{2,3}-\d{2,3}$/
export const isTag = (s: string) => TAG_RE.test(s)

/** 쪽 이미지 URL — 001.webp 형식 */
export const pageImage = (d: Deck, page: number) => (d.image_base ? `${d.image_base}${String(page).padStart(3, '0')}.webp` : null)

/** 브라우저 내장 PDF 뷰어 URL — `#page=` 는 Chrome 계열에서만 확실하다 (임시 경로 B) */
export const pdfUrl = (d: Deck, page: number) => (d.pdf ? `${d.pdf}#page=${page}&toolbar=0&view=Fit` : null)

/** 딥링크 `?slide=` 값 — 꼬리표(`VS-12`) 또는 `deck:page`(`vector:3`, 꼬리표 없는 덱용) */
export function parseSlideRef(v: unknown): { tag?: string; deck?: string; page?: number } | null {
  const s = String(v ?? '').trim()
  if (!s) return null
  if (isTag(s)) return { tag: s }
  const m = /^([a-z0-9][a-z0-9-]*)(?::(\d+))?$/.exec(s)
  if (m) return { deck: m[1], page: m[2] ? Math.max(1, parseInt(m[2], 10)) : 1 }
  return null
}

/** 기능 path(`/vector?sub=search&mode=hvi`)가 지금 화면(경로 + ?sub=)에 속하는가 — 헤더 「장표」 버튼이 이 화면의 앵커만 모을 때 쓴다 */
export function pathBelongsTo(featurePath: string, routePath: string, routeSub: string | null): boolean {
  const [p, q = ''] = featurePath.split('?')
  if (p !== routePath) return false
  const fsub = new URLSearchParams(q).get('sub')
  if (!fsub) return true                       // 서브탭을 안 가린 기능(예: /awr)은 그 페이지 어디서나
  return routeSub == null ? true : fsub === routeSub
}
