from app.storage.postgres_storage import PostgresStorage
from app.storage.storage_manager import LayeredSessionStorage, MemorySessionStorage


def _conversation(conversation_id: str = "conversation-1"):
    return {
        "conversation_id": conversation_id,
        "merchant_id": "merchant-1",
        "status": "active",
        "message_count": 2,
        "platform": "pinduoduo",
        "shop_id": "shop-1",
        "rpa_external_conversation_id": "external-1",
    }


def test_sql_session_storage_persists_conversation_messages_and_evidence(tmp_path):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'session.db').as_posix()}"
    storage = PostgresStorage(database_url)
    conversation = _conversation()

    assert storage.save_conversation("conversation-1", conversation)
    assert storage.add_message(
        "conversation-1",
        {
            "role": "user",
            "content": "这款商品有现货吗？",
            "timestamp": "2026-07-09T12:00:00",
        },
    )
    assert storage.add_message(
        "conversation-1",
        {
            "role": "assistant",
            "content": "有现货。",
            "timestamp": "2026-07-09T12:00:01",
            "metadata": {
                "retrieval_type": "hybrid",
                "evidence_sources": [
                    {
                        "type": "structured_data",
                        "platform": "pinduoduo",
                        "shop_id": "shop-1",
                        "product_id": "product-1",
                    }
                ],
            },
        },
    )

    reopened_storage = PostgresStorage(database_url)
    saved_conversation = reopened_storage.get_conversation("conversation-1")
    assert saved_conversation["platform"] == "pinduoduo"
    assert saved_conversation["shop_id"] == "shop-1"

    messages = reopened_storage.get_messages("conversation-1", limit=10)
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["metadata"]["retrieval_type"] == "hybrid"
    assert messages[1]["metadata"]["evidence_sources"][0]["product_id"] == "product-1"

    latest = reopened_storage.get_messages("conversation-1", limit=1)
    previous = reopened_storage.get_messages("conversation-1", limit=1, offset=1)
    assert latest[0]["content"] == "有现货。"
    assert previous[0]["content"] == "这款商品有现货吗？"
    assert reopened_storage.list_conversations("merchant-1") == ["conversation-1"]


def test_sql_session_storage_replaces_and_deletes_messages():
    storage = PostgresStorage("sqlite+pysqlite:///:memory:")
    assert storage.save_conversation("conversation-1", _conversation())
    assert storage.save_messages(
        "conversation-1",
        [
            {"role": "user", "content": "旧消息"},
            {"role": "assistant", "content": "旧回复"},
        ],
    )
    assert storage.save_messages(
        "conversation-1",
        [{"role": "assistant", "content": "替换后的回复"}],
    )

    messages = storage.get_messages("conversation-1", limit=10)
    assert [message["content"] for message in messages] == ["替换后的回复"]

    assert storage.delete_conversation("conversation-1")
    assert storage.get_conversation("conversation-1") is None
    assert storage.get_messages("conversation-1", limit=10) == []


def test_layered_storage_writes_primary_and_cache_but_reads_messages_from_primary():
    primary = MemorySessionStorage()
    cache = MemorySessionStorage()
    storage = LayeredSessionStorage(primary=primary, cache=cache)
    conversation = _conversation()
    message = {
        "role": "assistant",
        "content": "数据库中的完整回复",
        "metadata": {"evidence_sources": [{"type": "rag_chunk", "source": "faq"}]},
    }

    assert storage.save_conversation("conversation-1", conversation)
    assert storage.add_message("conversation-1", message)
    assert primary.get_conversation("conversation-1") is not None
    assert cache.get_conversation("conversation-1") is not None
    assert primary.get_messages("conversation-1", 10) == [message]
    assert cache.get_messages("conversation-1", 10) == [message]

    cache.save_messages("conversation-1", [{"role": "assistant", "content": "缓存中的不完整回复"}])
    assert storage.get_messages("conversation-1", 10) == [message]


def test_layered_storage_falls_back_to_primary_and_warms_conversation_cache():
    primary = MemorySessionStorage()
    cache = MemorySessionStorage()
    primary.save_conversation("conversation-1", _conversation())
    storage = LayeredSessionStorage(primary=primary, cache=cache)

    result = storage.get_conversation("conversation-1")

    assert result["platform"] == "pinduoduo"
    assert cache.get_conversation("conversation-1")["platform"] == "pinduoduo"


def test_layered_storage_migrates_existing_cache_without_overwriting_primary_messages():
    primary = MemorySessionStorage()
    cache = MemorySessionStorage()
    cache.save_conversation("cached-conversation", _conversation("cached-conversation"))
    cache.add_message("cached-conversation", {"role": "user", "content": "缓存历史"})

    primary.save_conversation("durable-conversation", _conversation("durable-conversation"))
    primary.add_message("durable-conversation", {"role": "assistant", "content": "永久历史"})
    cache.save_conversation("durable-conversation", _conversation("durable-conversation"))
    cache.add_message("durable-conversation", {"role": "assistant", "content": "缓存副本"})

    LayeredSessionStorage(primary=primary, cache=cache)

    assert primary.get_messages("cached-conversation", 10)[0]["content"] == "缓存历史"
    assert primary.get_messages("durable-conversation", 10)[0]["content"] == "永久历史"
