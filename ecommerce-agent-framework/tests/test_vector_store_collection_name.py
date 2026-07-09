import re

from app.rag.vector_store import normalize_collection_name


def test_valid_collection_name_is_preserved():
    assert normalize_collection_name("merchant_a") == "merchant_a"


def test_invalid_collection_name_is_deterministically_normalized():
    first = normalize_collection_name("__recommend_test__")
    second = normalize_collection_name("__recommend_test__")

    assert first == second
    assert first != "__recommend_test__"
    assert re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{1,510}[a-zA-Z0-9]", first)
