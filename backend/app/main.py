import os
import json
import whisper
from dotenv import load_dotenv
from google import genai
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import Meeting, TranscriptSegment, Summary, Topic, Decision, ActionItem

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "video/mp4",
    "video/quicktime",
}

MAX_FILE_SIZE_MB = 200
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

print("Loading Whisper model... (this happens once at startup)")
whisper_model = whisper.load_model("base")
print("Whisper model loaded.")

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SUMMARY_PROMPT_TEMPLATE = """You are analyzing a transcript segment from a meeting or lecture.

Read the transcript below and extract the following information. Respond ONLY with valid JSON, no other text, no markdown code fences.

{{
  "summary": "A 2-3 sentence summary of what was discussed in this segment",
  "key_points": ["list", "of", "key discussion points as short strings"],
  "decisions": ["list of any decisions that were made, as short strings"],
  "action_items": [
    {{
      "task": "description of the task",
      "assignee": "person's name if mentioned, otherwise 'Not specified'",
      "deadline": "deadline if mentioned, otherwise 'Not specified'",
      "source": "the exact sentence from the transcript this was extracted from"
    }}
  ],
  "topics": ["list", "of", "topic names mentioned"]
}}

Important rules:
- If no action items are mentioned, return an empty list for "action_items".
- Never invent an assignee or deadline that isn't explicitly stated in the transcript.
- If the speaker assigns a task to themselves (e.g. "I'll do it", "I will handle that", "I'm going to..."), set "assignee" to "Speaker (self-assigned)".
- If multiple people are assigned to one task, list all their names together in "assignee" (e.g. "Mark and Priya").
- Only extract genuine tasks or commitments as action items. Do not extract complaints, observations, or general statements that don't involve someone doing something (e.g. "the wifi has been down" is not an action item).
- Vague future intentions without a real commitment (e.g. "we should think about X at some point, no rush") may be omitted from action_items if there's no clear task or owner - use judgment.
- Keep "summary" concise, 2-3 sentences maximum.

Transcript:
{transcript_text}
"""

FINAL_SUMMARY_PROMPT_TEMPLATE = """You are combining several partial summaries from different segments of the same meeting/lecture into one coherent overall summary.

Here are the segment summaries, in order:

{combined_summaries}

Write ONE cohesive summary (3-5 sentences) of the entire meeting/lecture based on all the segments above. Respond with ONLY the summary text, no JSON, no extra formatting.
"""


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


def summarize_chunk(transcript_text: str) -> dict:
    prompt = SUMMARY_PROMPT_TEMPLATE.format(transcript_text=transcript_text)

    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    raw_text = response.text.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()

    return json.loads(raw_text)


def merge_chunk_results(chunk_results: list) -> dict:
    if len(chunk_results) == 1:
        return chunk_results[0]

    all_key_points = []
    all_decisions = []
    all_action_items = []
    all_topics = []

    for result in chunk_results:
        all_key_points.extend(result.get("key_points", []))
        all_decisions.extend(result.get("decisions", []))
        all_action_items.extend(result.get("action_items", []))
        all_topics.extend(result.get("topics", []))

    unique_topics = list(dict.fromkeys(all_topics))

    summaries_text = "\n".join(
        f"Segment {i + 1}: {result['summary']}"
        for i, result in enumerate(chunk_results)
    )
    final_summary_prompt = FINAL_SUMMARY_PROMPT_TEMPLATE.format(combined_summaries=summaries_text)

    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=final_summary_prompt
    )

    return {
        "summary": response.text.strip(),
        "key_points": all_key_points,
        "decisions": all_decisions,
        "action_items": all_action_items,
        "topics": unique_topics
    }


@app.get("/")
def read_root():
    return {"message": "Meeting Summarizer API is running"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Please upload an audio or video file."
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB}MB."
        )

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    meeting = Meeting(filename=file.filename, status="processing")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    result = whisper_model.transcribe(file_path)

    segments = [
        {
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"].strip()
        }
        for segment in result["segments"]
    ]

    for seg in segments:
        db_segment = TranscriptSegment(
            meeting_id=meeting.id,
            start_time=seg["start"],
            end_time=seg["end"],
            text=seg["text"]
        )
        db.add(db_segment)

    chunks = chunk_segments(segments, max_tokens_per_chunk=1500)

    chunk_results = []
    for chunk in chunks:
        combined_text = " ".join(s["text"] for s in chunk)
        summary_data = summarize_chunk(combined_text)
        chunk_results.append(summary_data)

    final_result = merge_chunk_results(chunk_results)

    db_summary = Summary(meeting_id=meeting.id, summary_text=final_result["summary"])
    db.add(db_summary)

    for topic_name in final_result["topics"]:
        db.add(Topic(meeting_id=meeting.id, name=topic_name))

    for decision_text in final_result["decisions"]:
        db.add(Decision(meeting_id=meeting.id, text=decision_text))

    for item in final_result["action_items"]:
        db.add(ActionItem(
            meeting_id=meeting.id,
            task=item.get("task", ""),
            assignee=item.get("assignee", "Not specified"),
            deadline=item.get("deadline", "Not specified"),
            source=item.get("source", "")
        ))

    meeting.status = "done"
    db.commit()

    return {
        "meeting_id": meeting.id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "transcript_text": result["text"],
        "segments": segments,
        "summary": final_result["summary"],
        "key_points": final_result["key_points"],
        "decisions": final_result["decisions"],
        "action_items": final_result["action_items"],
        "topics": final_result["topics"]
    }