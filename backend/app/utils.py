def estimate_tokens(text: str) -> int:
    return len(text) // 4


def chunk_segments(segments, max_tokens_per_chunk=1500):
    chunks = []
    current_chunk_segments = []
    current_chunk_tokens = 0

    for segment in segments:
        segment_tokens = estimate_tokens(segment["text"])

        if current_chunk_tokens + segment_tokens > max_tokens_per_chunk and current_chunk_segments:
            chunks.append(current_chunk_segments)
            current_chunk_segments = []
            current_chunk_tokens = 0

        current_chunk_segments.append(segment)
        current_chunk_tokens += segment_tokens

    if current_chunk_segments:
        chunks.append(current_chunk_segments)

    return chunks


def merge_action_items(chunk_results: list) -> list:
    all_action_items = []
    for result in chunk_results:
        all_action_items.extend(result.get("action_items", []))
    return all_action_items


def deduplicate_topics(topics: list) -> list:
    return list(dict.fromkeys(topics))