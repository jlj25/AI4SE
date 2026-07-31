"""记忆存储单测：验证存储与选择性检索。"""

from src.memory.store import MemoryStore
from src.types import FeedbackSignal, FeedbackType, Message


def test_store_and_retrieve_basic():
    store = MemoryStore()
    msg = Message(role="user", content="请帮我修复 bug", feedback=None)
    store.store(msg)
    results = store.retrieve("bug", k=5)
    assert len(results) == 1
    assert "bug" in results[0].content


def test_retrieve_by_keyword():
    store = MemoryStore()
    store.store(Message(role="user", content="安装依赖", feedback=None))
    store.store(Message(role="assistant", content="运行 pytest", feedback=None))
    store.store(Message(role="tool", content="测试通过", feedback=None))
    results = store.retrieve("pytest", k=5)
    assert len(results) == 1
    assert "pytest" in results[0].content


def test_retrieve_top_k():
    store = MemoryStore()
    for i in range(10):
        store.store(Message(role="user", content=f"任务 {i}", feedback=None))
    results = store.retrieve("任务", k=3)
    assert len(results) == 3


def test_retrieve_empty_store():
    store = MemoryStore()
    results = store.retrieve("anything", k=5)
    assert results == []


def test_clear():
    store = MemoryStore()
    store.store(Message(role="user", content="hello", feedback=None))
    store.clear()
    assert store.retrieve("hello", k=5) == []


def test_retrieve_with_feedback_signal():
    """带反馈信号的消息也能被检索。"""
    store = MemoryStore()
    signal = FeedbackSignal(type=FeedbackType.FAILURE, message="测试失败")
    store.store(Message(role="tool", content="pytest 输出", feedback=signal))
    results = store.retrieve("pytest", k=5)
    assert len(results) == 1
    assert results[0].feedback is not None


def test_retrieve_latest_first():
    """多条匹配时最新优先。"""
    store = MemoryStore()
    store.store(Message(role="user", content="bug 第一条", feedback=None))
    store.store(Message(role="user", content="bug 第二条", feedback=None))
    store.store(Message(role="user", content="bug 第三条", feedback=None))
    results = store.retrieve("bug", k=5)
    assert len(results) == 3
    assert "第三条" in results[0].content
    assert "第一条" in results[2].content


def test_all_messages():
    store = MemoryStore()
    store.store(Message(role="user", content="a", feedback=None))
    store.store(Message(role="user", content="b", feedback=None))
    assert len(store.all_messages()) == 2
