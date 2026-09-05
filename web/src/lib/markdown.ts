import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 레거시의 정규식 렌더러 2개(renderMarkdown / renderDoc)를 이것 하나로 대체한다(설계서 D6).
// 이스케이프는 DOMPurify 가 책임진다 — 가이드 문서의 `<스크립트>` 같은 자리표시자가 안전하다.
marked.setOptions({ gfm: true, breaks: false })

export function renderMarkdown(md: string | null | undefined): string {
  if (!md) return ''
  const html = marked.parse(md, { async: false }) as string
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
