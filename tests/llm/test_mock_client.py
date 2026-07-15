"""MockLLMClient 单测：验证按脚本返回预设响应。"""
from src.llm.mock_client import MockLLMClient
from src.types import Message


def test_mock_returns_scripted_response():
    client = MockLLMClient(script=["第一个响应", "第二个响应"])
    msg = [Message(role="user", content="任务")]
    assert client.chat(msg) == "第一个响应"
    assert client.chat(msg) == "第二个响应"


def test_mock_raises_when_script_exhausted():
    import pytest
    client = MockLLMClient(script=["仅一条"])
    client.chat([Message(role="user", content="")])
    with pytest.raises(IndexError, match="脚本耗尽"):
        client.chat([Message(role="user", content="")])


def test_mock_records_call_history():
    client = MockLLMClient(script=["resp"])
    msgs = [Message(role="user", content="hello")]
    client.chat(msgs)
    assert len(client.call_history) == 1
    assert client.call_history[0] == msgs
