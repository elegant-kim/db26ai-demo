/** 대화형 화면(AWR 후속질문 · NL2SQL · RAG) 공통 메시지 */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  elapsedMs?: number | null
  error?: boolean
}
