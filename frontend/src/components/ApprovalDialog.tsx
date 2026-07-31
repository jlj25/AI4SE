interface PendingAction {
  tool: string
  args: Record<string, unknown>
  thought: string
}

interface Props {
  action: PendingAction
  onApprove: () => void
  onDeny: () => void
  onModify: (newCommand: string) => void
}

export function ApprovalDialog({ action, onApprove, onDeny, onModify }: Props) {
  return (
    <div className="approval-overlay">
      <div className="approval-dialog">
        <h3>危险动作审批</h3>
        <p>工具: {action.tool}</p>
        <p>参数: {JSON.stringify(action.args)}</p>
        <p>理由: {action.thought}</p>
        <div className="buttons">
          <button onClick={onApprove} className="btn-approve">批准</button>
          <button onClick={onDeny} className="btn-deny">拒绝</button>
        </div>
        <div className="buttons" style={{ marginTop: '0.5rem' }}>
          <input
            placeholder="修改后的命令..."
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onModify((e.target as HTMLInputElement).value)
              }
            }}
            style={{ flex: 1, padding: '0.5rem', background: 'var(--bg)', color: 'var(--fg)', border: '1px solid var(--border)', borderRadius: '0.25rem' }}
          />
          <button onClick={(e) => onModify((e.currentTarget.previousSibling as HTMLInputElement).value)} className="btn-modify">修改</button>
        </div>
      </div>
    </div>
  )
}
