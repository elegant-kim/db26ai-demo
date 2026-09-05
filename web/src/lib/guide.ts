import { api } from './api'
import type { MenuId } from './menu'

/** 매뉴얼 탭 · ⌘K 팔레트의 데이터 — 정본은 Python (app/feature_registry.py · app/routes.py 의 화이트리스트, 설계서 D5) */
export interface DocMeta { key: string; title: string; subtitle: string; available: boolean }
export interface GuideDoc { key: string; title: string; subtitle: string; content: string }
export interface FeatureItem { tab: string; tab_label: string; name: string; desc: string; how: string; path: string; keyword: string }
export interface FeatureGroup { tab: string; tab_label: string; items: FeatureItem[] }

export const getGuideDocs = () => api.get<{ success: boolean; guides: DocMeta[]; docs: DocMeta[] }>('/api/guide/docs').then((r) => r.data)
export const getGuideDoc = (key: string) => api.get<{ success: boolean; error?: string } & GuideDoc>(`/api/guide/docs/${encodeURIComponent(key)}`).then((r) => r.data)
export const getFeatures = () => api.get<{ success: boolean; groups: FeatureGroup[]; total: number }>('/api/guide/features').then((r) => r.data)

/** 레지스트리의 탭 id → 새 화면 메뉴 id (레거시 'extra' 탭이 AWR 페이지) */
export const tabToMenuId = (tab: string): MenuId => (tab === 'extra' ? 'awr' : (tab as MenuId))
