// 상단 메뉴 정의 — 순서·라벨·아이콘·이식 상태의 정본 (investhub permissions.ts 의 권한 없는 판).
// migrated=false 인 메뉴는 헤더에서 /legacy#tab 으로 전체 이동한다(설계서 05 §5.2).
// 탭을 이식할 때마다 migrated 를 true 로 바꾼다 — 그게 곧 "이 탭은 새 화면" 선언이다.
import {
  MessageSquareText, Search, Braces, Network, Zap, Activity, BookOpen, type LucideIcon,
} from 'lucide-vue-next'

export type MenuId = 'nl2sql' | 'vector' | 'duality' | 'graph' | 'productivity' | 'awr' | 'manual'

export interface MenuDef {
  id: MenuId
  label: string        // 헤더용 짧은 라벨
  title: string        // 페이지 h1 (레거시 탭 라벨과 동일 — 기능 레지스트리 tab_label 정본)
  subtitle: string     // h1 옆 괄호 부제
  icon: LucideIcon
  path: string
  legacyTab: string    // /legacy#<tab>
  migrated: boolean
}

export const MENUS: MenuDef[] = [
  { id: 'nl2sql', label: 'NL2SQL', title: 'NL2SQL(Select AI)', subtitle: '자연어 → SQL 생성·실행', icon: MessageSquareText, path: '/nl2sql', legacyTab: 'nl2sql', migrated: false },
  { id: 'vector', label: 'Vector Search', title: 'AI Vector Search', subtitle: '의미 검색 · 키워드 · 하이브리드 · RAG', icon: Search, path: '/vector', legacyTab: 'vector', migrated: false },
  { id: 'duality', label: 'Duality', title: 'JSON Relational Duality', subtitle: '관계형 ↔ JSON, 하나의 데이터', icon: Braces, path: '/duality', legacyTab: 'duality', migrated: true },
  { id: 'graph', label: 'Property Graph', title: 'Property Graph', subtitle: 'SQL/PGQ — 기존 테이블 위의 그래프', icon: Network, path: '/graph', legacyTab: 'graph', migrated: true },
  { id: 'productivity', label: '생산성', title: '개발생산성 향상', subtitle: 'Lock-Free Reservations · Priority Transactions', icon: Zap, path: '/productivity', legacyTab: 'productivity', migrated: true },
  { id: 'awr', label: 'AWR 분석', title: '기타 부가 기능', subtitle: 'AWR 리포트 AI 분석', icon: Activity, path: '/awr', legacyTab: 'extra', migrated: true },
  { id: 'manual', label: '매뉴얼', title: '매뉴얼', subtitle: '기능 지도 · 사용 설명서 · 현재 상태', icon: BookOpen, path: '/manual', legacyTab: 'manual', migrated: false },
]

export const menuById = (id: MenuId): MenuDef => MENUS.find((m) => m.id === id)!

/** 이식된 메뉴가 있으면 nl2sql 우선, 그다음 첫 이식 메뉴, 하나도 없으면 스타일가이드 */
export function homePath(): string {
  const nl = MENUS.find((m) => m.id === 'nl2sql')
  if (nl?.migrated) return nl.path
  const first = MENUS.find((m) => m.migrated)
  return first ? first.path : '/styleguide'
}

export const legacyUrl = (m: MenuDef) => `/legacy#${m.legacyTab}`
