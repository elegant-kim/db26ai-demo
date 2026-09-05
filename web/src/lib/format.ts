export function fmtNum(v: number | null | undefined, digits?: number): string {
  if (v == null || !isFinite(v)) return '—'
  return new Intl.NumberFormat('ko-KR', digits == null ? {} : { maximumFractionDigits: digits }).format(v)
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms == null || !isFinite(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)}초`
}

export function fmtBytes(b: number | null | undefined): string {
  if (b == null || !isFinite(b)) return '—'
  if (b < 1024) return `${b}B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)}KB`
  return `${(b / 1024 / 1024).toFixed(1)}MB`
}

/** ISO/Oracle 문자열 → "2026-09-05 09:42" (KST 표기는 백엔드가 이미 KST 라 가정하지 않고 그대로) */
export function fmtDateTime(s: string | null | undefined): string {
  if (!s) return '—'
  const d = new Date(s)
  if (isNaN(d.getTime())) return String(s).slice(0, 16).replace('T', ' ')
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export const isNumeric = (v: unknown): v is number => typeof v === 'number' && isFinite(v)
