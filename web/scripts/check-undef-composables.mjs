#!/usr/bin/env node
/**
 * <script setup> 에서 import 없이 쓰인 컴포저블/헬퍼를 잡는다. (investhub 에서 이식)
 * 계기: useRoute() 를 쓰면서 import 를 빠뜨려 화면이 통째로 blank 가 된 사고.
 * vue-tsc 도 vite build 도 이걸 못 잡는다 — 런타임 ReferenceError 로만 드러난다.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const TARGETS = [
  'useRoute', 'useRouter', 'useSystemStore', 'useSubTab',
  'computed', 'watch', 'watchEffect', 'ref', 'reactive', 'nextTick',
  'onMounted', 'onActivated', 'onBeforeUnmount', 'inject', 'provide',
  'defineAsyncComponent',
]

function walk(dir, out = []) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (p.endsWith('.vue')) out.push(p)
  }
  return out
}

let bad = 0
for (const file of walk('src')) {
  const src = readFileSync(file, 'utf8')
  const m = src.match(/<script setup[^>]*>([\s\S]*?)<\/script>/)
  if (!m) continue
  const script = m[1]
  const known = new Set()
  for (const im of script.matchAll(/import\s*\{([^}]*)\}\s*from/g))
    for (const part of im[1].split(','))
      known.add(part.trim().split(/\s+as\s+/).pop().trim())
  for (const im of script.matchAll(/import\s+(\w+)\s+from/g)) known.add(im[1])
  for (const d of script.matchAll(/\b(?:const|let|var|function)\s+(\w+)/g)) known.add(d[1])
  for (const name of TARGETS) {
    if (!new RegExp(`(?<![\\w.])${name}\\s*\\(`).test(script)) continue
    if (known.has(name)) continue
    console.log(`  ✖ ${file}: ${name}() 를 쓰는데 import 가 없습니다`)
    bad++
  }
}
if (bad) { console.error(`\n${bad}건 — 런타임에 blank 페이지가 됩니다. import 를 추가하세요.`); process.exit(1) }
console.log('✔ import 누락 없음')
