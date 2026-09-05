/**
 * SSE 수신 — fetch + ReadableStream (설계서 05 §4.4). 이 앱에서 SSE 는 PDF 업로드(POST /api/vector/upload) 뿐이다.
 * 서버 형식: "event: <type>\ndata: <json>\n\n". event-stream 이 아니면(오류 JSON 등) 한 번의 done/error 로 흘려보낸다.
 */
export type SseHandler = (type: string, data: any) => void

export async function postSse(url: string, body: FormData | Record<string, unknown>, onEvent: SseHandler, signal?: AbortSignal): Promise<void> {
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData
  const res = await fetch(url, {
    method: 'POST',
    body: isForm ? (body as FormData) : JSON.stringify(body),
    headers: isForm ? undefined : { 'Content-Type': 'application/json' },
    signal,
  })
  if (!res.headers.get('content-type')?.includes('text/event-stream')) {
    let data: any = null
    try { data = await res.json() } catch { data = { success: false, error: `HTTP ${res.status}` } }
    onEvent(data?.success ? 'done' : 'error', data?.success ? data : { message: data?.error || `HTTP ${res.status}` })
    return
  }
  const reader = res.body!.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      if (!part.trim()) continue
      let type = 'message'
      let data = ''
      for (const line of part.split('\n')) {
        if (line.startsWith('event: ')) type = line.slice(7).trim()
        else if (line.startsWith('data: ')) data = line.slice(6)
      }
      if (!data) continue
      try { onEvent(type, JSON.parse(data)) } catch { /* 깨진 조각은 무시 */ }
    }
  }
}
