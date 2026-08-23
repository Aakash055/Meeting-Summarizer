EXPECTED_ACTION_ITEMS = [
    {"task_keywords": ["finish", "report"], "expected_assignee_contains": "self"},
    {"task_keywords": ["client", "call"], "expected_assignee_contains": "sachin"},
]


def evaluate_action_items(extracted_items: list, expected_items: list) -> dict:
    matched_expected = set()
    true_positives = 0

    for extracted in extracted_items:
        task_lower = extracted.get("task", "").lower()
        assignee_lower = extracted.get("assignee", "").lower()

        for i, expected in enumerate(expected_items):
            if i in matched_expected:
                continue

            keywords_found = all(kw in task_lower for kw in expected["task_keywords"])
            assignee_found = expected["expected_assignee_contains"] in assignee_lower

            if keywords_found and assignee_found:
                true_positives += 1
                matched_expected.add(i)
                break

    false_positives = len(extracted_items) - true_positives
    false_negatives = len(expected_items) - true_positives

    precision = true_positives / len(extracted_items) if extracted_items else 0.0
    recall = true_positives / len(expected_items) if expected_items else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1, 3)
    }