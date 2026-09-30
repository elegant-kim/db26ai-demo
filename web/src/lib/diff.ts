/** 줄 단위 diff (LCS) — 프롬프트 전/후 비교(PoC 2-C). 수백 줄이면 충분하다. */
export interface DiffLine { kind: 'same' | 'add' | 'del'; text: string }

export function lineDiff(a: string, b: string): DiffLine[] {
  const A = a.split('\n'), B = b.split('\n')
  const n = A.length, m = B.length
  const dp: Uint16Array[] = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1))
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
  const out: DiffLine[] = []
  let i = 0, j = 0
  while (i < n && j < m) {
    if (A[i] === B[j]) { out.push({ kind: 'same', text: A[i] }); i++; j++ }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ kind: 'del', text: A[i] }); i++ }
    else { out.push({ kind: 'add', text: B[j] }); j++ }
  }
  while (i < n) out.push({ kind: 'del', text: A[i++] })
  while (j < m) out.push({ kind: 'add', text: B[j++] })
  return out
}

/** 바뀐 줄 주변 ctx 줄만 남긴다(사이는 '…'). 프롬프트가 1만 자라 전부 보여줄 수 없다 */
export function collapseSame(lines: DiffLine[], ctx = 2): (DiffLine | { kind: 'gap'; count: number })[] {
  const keep = new Array(lines.length).fill(false)
  lines.forEach((l, i) => { if (l.kind !== 'same') for (let k = Math.max(0, i - ctx); k <= Math.min(lines.length - 1, i + ctx); k++) keep[k] = true })
  const out: (DiffLine | { kind: 'gap'; count: number })[] = []
  let gap = 0
  lines.forEach((l, i) => { if (keep[i]) { if (gap) { out.push({ kind: 'gap', count: gap }); gap = 0 } out.push(l) } else gap++ })
  if (gap) out.push({ kind: 'gap', count: gap })
  return out
}
