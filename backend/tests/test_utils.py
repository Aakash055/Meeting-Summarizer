from app.utils import estimate_tokens, chunk_segments, merge_action_items, deduplicate_topics


def test_estimate_tokens_basic():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 100) == 25


def test_chunk_segments_single_chunk_when_small():
    segments = [
        {"start": 0, "end": 1, "text": "Hello world."},
        {"start": 1, "end": 2, "text": "This is short."},
    ]
    chunks = chunk_segments(segments, max_tokens_per_chunk=1000)
    assert len(chunks) == 1
    assert len(chunks[0]) == 2


def test_chunk_segments_splits_when_over_limit():
    segments = [
        {"start": 0, "end": 1, "text": "a" * 40},
        {"start": 1, "end": 2, "text": "b" * 40},
        {"start": 2, "end": 3, "text": "c" * 40},
    ]
    chunks = chunk_segments(segments, max_tokens_per_chunk=10)
    assert len(chunks) == 3
    for chunk in chunks:
        assert len(chunk) == 1


def test_chunk_segments_never_splits_a_single_segment():
    segments = [
        {"start": 0, "end": 1, "text": "a" * 1000},
    ]
    chunks = chunk_segments(segments, max_tokens_per_chunk=10)
    assert len(chunks) == 1
    assert len(chunks[0]) == 1


def test_chunk_segments_empty_input():
    assert chunk_segments([], max_tokens_per_chunk=100) == []


def test_merge_action_items_combines_across_chunks():
    chunk_results = [
        {"action_items": [{"task": "Task A"}]},
        {"action_items": [{"task": "Task B"}, {"task": "Task C"}]},
    ]
    merged = merge_action_items(chunk_results)
    assert len(merged) == 3
    assert merged[0]["task"] == "Task A"
    assert merged[2]["task"] == "Task C"


def test_merge_action_items_handles_missing_key():
    chunk_results = [{"summary": "no action items key here"}]
    merged = merge_action_items(chunk_results)
    assert merged == []


def test_deduplicate_topics_removes_duplicates_preserving_order():
    topics = ["Budget", "Marketing", "Budget", "Sales", "Marketing"]
    result = deduplicate_topics(topics)
    assert result == ["Budget", "Marketing", "Sales"]


def test_deduplicate_topics_empty_list():
    assert deduplicate_topics([]) == []