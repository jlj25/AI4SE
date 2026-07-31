import { useState, useEffect, useRef } from 'react'
import { connectWS, sendWS, type WSMessage } from '../ws'

interface Message {
  role: string
  content: string
}

export function ChatView() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = connectWS((msg: WSMessage) => {
      if (msg.type === 'status' && msg.message) {
        setMessages((prev) => [...prev, { role: 'assistant', content: msg.message! }])
      }
    })
    wsRef.current = ws
    return () => ws.close()
  }, [])

  const send = () => {
    if (!input.trim() || !wsRef.current) return
    setMessages((prev) => [...prev, { role: 'user', content: input }])
    sendWS(wsRef.current, { type: 'run', input })
    setInput('')
  }

  return (
    <div className="chat-view">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>{m.content}</div>
        ))}
      </div>
      <div className="input-bar">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="输入指令..."
        />
        <button onClick={send}>发送</button>
      </div>
    </div>
  )
}
