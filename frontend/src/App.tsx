import { useState } from 'react'
import { ChatView } from './components/ChatView'
import { ApprovalDialog } from './components/ApprovalDialog'
import { approve } from './api'

interface PendingAction {
  tool: string
  args: Record<string, unknown>
  thought: string
}

function App() {
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)

  const handleApprove = () => {
    approve('approve')
    setPendingAction(null)
  }

  const handleDeny = () => {
    approve('deny')
    setPendingAction(null)
  }

  const handleModify = (newCommand: string) => {
    approve('modify', { tool: 'run_shell', args: { command: newCommand }, thought: '用户修改' })
    setPendingAction(null)
  }

  return (
    <div className="app">
      <header>
        <h1>NJUSE Coding Agent</h1>
      </header>
      <ChatView />
      {pendingAction && (
        <ApprovalDialog
          action={pendingAction}
          onApprove={handleApprove}
          onDeny={handleDeny}
          onModify={handleModify}
        />
      )}
    </div>
  )
}

export default App
