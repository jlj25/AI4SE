## Task 15: 前端（React + Vite + Open Design）

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/components/ChatView.tsx`, `frontend/src/components/ApprovalDialog.tsx`
- Create: `frontend/src/api.ts`, `frontend/src/ws.ts`

**说明：** 前端为最小可用实现，展示 agent 对话与 HITL 审批弹窗。

- [ ] **Step 1: 初始化前端项目**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install axios
```

- [ ] **Step 2: 配置 Vite 代理**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
```

- [ ] **Step 3: 实现 API 客户端**

```typescript
// frontend/src/api.ts
import axios from 'axios';

const API = axios.create({ baseURL: '/api' });

export async function health() {
  return API.get('/health');
}

export async function approve(verdict: string, modifiedAction?: any) {
  return API.post('/approve', { verdict, modified_action: modifiedAction });
}
```

```typescript
// frontend/src/ws.ts
export function connectWS(onMessage: (msg: any) => void) {
  const ws = new WebSocket(`ws://${window.location.host}/ws`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}
```

- [ ] **Step 4: 实现 ChatView 组件**

```tsx
// frontend/src/components/ChatView.tsx
import { useState, useEffect } from 'react';

interface Message {
  role: string;
  content: string;
}

export function ChatView() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    // WebSocket 连接逻辑
  }, []);

  const send = () => {
    setMessages([...messages, { role: 'user', content: input }]);
    setInput('');
  };

  return (
    <div className="chat-view">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>{m.content}</div>
        ))}
      </div>
      <div className="input-bar">
        <input value={input} onChange={e => setInput(e.target.value)} />
        <button onClick={send}>发送</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 实现 ApprovalDialog 组件**

```tsx
// frontend/src/components/ApprovalDialog.tsx
interface Props {
  action: { tool: string; args: Record<string, any>; thought: string };
  onApprove: () => void;
  onDeny: () => void;
  onModify: (newCommand: string) => void;
}

export function ApprovalDialog({ action, onApprove, onDeny, onModify }: Props) {
  if (!action) return null;
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
      </div>
    </div>
  );
}
```

- [ ] **Step 6: 实现 App 主组件**

```tsx
// frontend/src/App.tsx
import { useState } from 'react';
import { ChatView } from './components/ChatView';
import { ApprovalDialog } from './components/ApprovalDialog';

function App() {
  const [pendingAction, setPendingAction] = useState<any>(null);

  return (
    <div className="app">
      <header><h1>NJUSE Coding Agent</h1></header>
      <ChatView />
      {pendingAction && (
        <ApprovalDialog
          action={pendingAction}
          onApprove={() => setPendingAction(null)}
          onDeny={() => setPendingAction(null)}
          onModify={() => setPendingAction(null)}
        />
      )}
    </div>
  );
}

export default App;
```

- [ ] **Step 7: 验证前端构建 + 提交**

```bash
cd frontend && npm run build
cd ..
git add frontend/
git commit -m "feat: 前端（React + Vite + ChatView + ApprovalDialog HITL 审批弹窗）"
```

---