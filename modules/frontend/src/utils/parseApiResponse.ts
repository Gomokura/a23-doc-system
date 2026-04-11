/**
 * 将 fetch 的 Response 按 JSON 解析。
 * 避免后端/代理返回空 body 时 response.json() 抛出
 * "Unexpected end of JSON input"。
 */
export function parseJsonFromText(text: string, status: number): unknown {
  const t = (text ?? '').trim()
  if (!t) {
    throw new Error(
      `服务端返回空响应 (HTTP ${status})。请确认已在项目根目录启动后端（python main.py），且 http://localhost:8000 可访问。`
    )
  }
  try {
    return JSON.parse(t)
  } catch {
    throw new Error(
      `响应不是合法 JSON (HTTP ${status}): ${t.slice(0, 160)}${t.length > 160 ? '…' : ''}`
    )
  }
}

export async function parseResponseJson(res: Response): Promise<unknown> {
  const text = await res.text()
  return parseJsonFromText(text, res.status)
}
