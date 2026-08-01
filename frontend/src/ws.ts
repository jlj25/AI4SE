export interface WSMessage {
  type: string
  message?: string
  content?: string
  response?: string
  success?: boolean
  stdout?: string
  stderr?: string
  reason?: string
  blocked?: boolean
  step?: number
  action?: { tool: string; args: Record<string, unknown>; thought: string }
}

export function connectWS(onMessage: (msg: WSMessage) => void) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)
  ws.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data))
    } catch {
      // ignore malformed messages
    }
  }
  return ws
}

export function sendWS(ws: WebSocket, data: unknown) {
  ws.send(JSON.stringify(data))
}
