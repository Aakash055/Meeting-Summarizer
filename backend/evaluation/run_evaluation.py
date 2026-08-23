import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.ground_truth_transcripts import GROUND_TRUTH
from evaluation.wer import calculate_wer
from evaluation.action_item_eval import EXPECTED_ACTION_ITEMS, evaluate_action_items
import whisper
from dotenv import load_dotenv
from app.utils import chunk_segments
from app.main import summarize_chunk, merge_chunk_results

load_dotenv()

print("Loading Whisper model...")
model = whisper.load_model("base")

for filename, reference_text in GROUND_TRUTH.items():
    file_path = f"/Users/aakash/Desktop/{filename}"
    print(f"\n{'=' * 50}")
    print(f"Evaluating: {filename}")
    print('=' * 50)

    result = model.transcribe(file_path)
    hypothesis_text = result["text"]

    wer_result = calculate_wer(reference_text, hypothesis_text)
    print(f"\n--- Transcription (WER) ---")
    print(f"Reference : {reference_text}")
    print(f"Hypothesis: {hypothesis_text.strip()}")
    print(f"WER: {wer_result['wer_percent']}% ({wer_result['edit_distance']} errors / {wer_result['reference_word_count']} words)")

    segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
        for s in result["segments"]
    ]
    chunks = chunk_segments(segments, max_tokens_per_chunk=1500)
    chunk_results = []
    for chunk in chunks:
        combined_text = " ".join(s["text"] for s in chunk)
        chunk_results.append(summarize_chunk(combined_text))
    final_result = merge_chunk_results(chunk_results)

    print(f"\n--- Action Item Extraction ---")
    print(f"Extracted: {final_result['action_items']}")

    ai_eval = evaluate_action_items(final_result["action_items"], EXPECTED_ACTION_ITEMS)
    print(f"Precision: {ai_eval['precision']}")
    print(f"Recall: {ai_eval['recall']}")
    print(f"F1 Score: {ai_eval['f1_score']}")
    print(f"(TP={ai_eval['true_positives']}, FP={ai_eval['false_positives']}, FN={ai_eval['false_negatives']})")