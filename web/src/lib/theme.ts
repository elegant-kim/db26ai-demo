export type ThemePref = 'system' | 'light' | 'dark'

const KEY = 'db26ai.theme'

function resolveActual(pref: ThemePref): 'light' | 'dark' {
  if (pref === 'system') return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  return pref
}

export function getThemePref(): ThemePref {
  const v = localStorage.getItem(KEY) as ThemePref | null
  return v ?? 'system'
}

export function setThemePref(pref: ThemePref) {
  localStorage.setItem(KEY, pref)
  applyTheme(pref)
}

export function applyTheme(pref: ThemePref) {
  document.documentElement.setAttribute('data-theme', resolveActual(pref))
}

export function applyThemeFromStorage() {
  // ?theme=light|dark — 캡처·검증용 오버라이드 (헤드리스 Chrome 은 localStorage 를 못 만진다).
  // 저장하지 않으므로 다음 방문에는 영향이 없다.
  const q = new URLSearchParams(location.search).get('theme')
  if (q === 'light' || q === 'dark') { applyTheme(q); return }
  applyTheme(getThemePref())
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (getThemePref() === 'system') applyTheme('system')
  })
}
