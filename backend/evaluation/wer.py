def calculate_wer(reference: str, hypothesis: str) -> dict:
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()

    ref_words = [w.strip('.,!?"\'') for w in ref_words]
    hyp_words = [w.strip('.,!?"\'') for w in hyp_words]

    n = len(ref_words)
    m = len(hyp_words)

    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                substitution = dp[i - 1][j - 1] + 1
                deletion = dp[i - 1][j] + 1
                insertion = dp[i][j - 1] + 1
                dp[i][j] = min(substitution, deletion, insertion)

    edit_distance = dp[n][m]
    wer = edit_distance / n if n > 0 else 0.0

    return {
        "reference_word_count": n,
        "hypothesis_word_count": m,
        "edit_distance": edit_distance,
        "wer": round(wer, 4),
        "wer_percent": round(wer * 100, 2)
    }