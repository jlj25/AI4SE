export interface WSMessage {
  type: string
  message?: string
  action?: { tool: string; args: Record<string, unknown>; thought: string }
}

export function connectWS(onMessage: (msg: WSMessage) => void) {
  const ws = new WebSocket(`ws://${window.location.host}/ws`)
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
