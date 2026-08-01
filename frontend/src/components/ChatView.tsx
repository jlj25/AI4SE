import { useState, useEffect, useRef } from 'react'
import { connectWS, sendWS, type WSMessage } from '../ws'

interface Message {
  role: string
  content: string
}

export function ChatView() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = connectWS((msg: WSMessage) => {
      if (msg.type === 'status' && msg.message) {
        setMessages((prev) => [...prev, { role: 'system', content: msg.message! }])
      } else if (msg.type === 'thought') {
        setMessages((prev) => [...prev, { role: 'assistant', content: msg.content || '' }])
      } else if (msg.type === 'action_parsed') {
        const action = msg.action
        if (action) {
          setMessages((prev) => [...prev, {
            role: 'tool',
            content: `[${action.tool}] ${JSON.stringify(action.args)} — ${action.thought}`
          }])
        }
      } else if (msg.type === 'governance_check') {
        if (msg.blocked) {
          setMessages((prev) => [...prev, {
            role: 'system',
            content: `⚠ 治理拦截: ${msg.reason}`
          }])
        }
      } else if (msg.type === 'action_executed') {
        const success = msg.success ? '✓' : '✗'
        const output = msg.stdout || msg.stderr || ''
        setMessages((prev) => [...prev, {
          role: 'tool',
          content: `${success} ${output}`
        }])
      } else if (msg.type === 'task_completed') {
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: msg.response || '完成'
        }])
        setRunning(false)
      } else if (msg.type === 'error') {
        setMessages((prev) => [...prev, {
          role: 'system',
          content: `错误: ${msg.message}`
        }])
        setRunning(false)
      } else if (msg.type === 'max_iterations_reached') {
        setMessages((prev) => [...prev, {
          role: 'system',
          content: '达到最大迭代次数'
        }])
        setRunning(false)
      }
    })
    wsRef.current = ws
    return () => ws.close()
  }, [])

  const send = () => {
    if (!input.trim() || !wsRef.current || running) return
    setMessages((prev) => [...prev, { role: 'user', content: input }])
    sendWS(wsRef.current, { type: 'run', input })
    setInput('')
    setRunning(true)
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
          placeholder={running ? '运行中...' : '输入编码任务...'}
          disabled={running}
        />
        <button onClick={send} disabled={running}>发送</button>
      </div>
    </div>
  )
}
