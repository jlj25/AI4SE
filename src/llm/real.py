"""真实 LLM 客户端：调用 OpenAI 兼容的 chat completion API。"""

from __future__ import annotations

import httpx

from src.credentials.manager import CredentialManager
from src.llm.base import LLMClient
from src.types import Message


class RealLLMClient(LLMClient):
    """调用 OpenAI 兼容 API 的 LLM 客户端。

    通过 CredentialManager 获取 API key 和 base URL，
    使用 httpx 发送 chat completion 请求。
    """

    def __init__(self, cred: CredentialManager | None = None) -> None:
        self._cred = cred or CredentialManager()

    def chat(self, messages: list[Message]) -> str:
        """发送对话消息，返回 LLM 响应字符串。"""
        api_key = self._cred.get_api_key()
        base_url = self._cred.get_base_url()
        model = self._cred.get_model()

        payload = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])
